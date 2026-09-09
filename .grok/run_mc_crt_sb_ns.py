"""MC-CRT-SB-XAUUSD-M15-NS-V1: CRT + adapter session vetoes off. Research only."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.chdir(ROOT)
os.environ.pop("BACKTEST_ENGINE_GATE", None)

CONTRACT_ID = "MC-CRT-SB-XAUUSD-M15-NS-V1"
CONTRACT = ROOT / "configs/research/measurement_contracts/instances" / f"{CONTRACT_ID}.json"
SPINE_CFG = ROOT / "configs/research/research_config_mc_crt_sb_xauusd.json"
OUT = ROOT / "results/research/mc_crt_sb_xauusd_m15_ns_v1"
CSV = ROOT / "data/mt5/XAUUSD_M15.csv"
BPS = 12.0
MAX_FORWARD = 200
EMBARGO_BARS = 96
OOS_FRAC = 0.20
N_MIN = 30
ADAPTER_SESSIONS = [
    "asia", "london", "new_york", "overlap", "closed", "off_session",
    "ASIA", "LONDON", "NEWYORK", "OVERLAP", "CLOSED", "OFF_SESSION",
]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _cost_r(entry: float, risk: float) -> float:
    if risk <= 0:
        return float("inf")
    return (BPS / 10_000.0) * entry / risk


def _ns_entries():
    import config_layer.production_config as _pc
    import runtime.backtest_v2 as _bt
    from config_layer.crt_config_provenance import mark_explicit
    from research.adapters.spine_signal_source import ProductionSpineSource

    version = "v2_multi_2026_04"
    out_dir = OUT / "_spine" / f"XAUUSD__{version}"
    out_dir.mkdir(parents=True, exist_ok=True)
    src = ProductionSpineSource(str(SPINE_CFG), out_root=str(OUT / "_spine"))
    _pc_prev, _bt_prev = _pc.PROD_VERSION, _bt.PROD_VERSION
    _gps = _pc.get_prod_section

    def _gps_ns(section, *a, **k):
        out = _gps(section, *a, **k)
        if section == "engine_runner":
            out = dict(out)
            out["allowed_sessions"] = list(ADAPTER_SESSIONS)
        return out

    _pc.get_prod_section = _gps_ns
    _crt = logging.getLogger("CRT")
    _crt_prev = _crt.level
    _crt.setLevel(logging.ERROR)
    try:
        _pc.PROD_VERSION = version
        _bt.PROD_VERSION = version
        crt_cfg = _pc.load_prod_config_from_registry(version, "XAUUSD")
        sess = tuple(crt_cfg.session_windows.keys()) + ("OFF_SESSION",)
        crt_cfg = mark_explicit(
            replace(crt_cfg, allowed_sessions=sess),
            instrument="XAUUSD",
            note="MC-CRT-SB-XAUUSD-M15-NS-V1 research; not production",
        )
        cfg = _bt.BacktestConfig.from_prod_config(
            instrument="XAUUSD",
            pip_size=_bt.MultiInstrumentRunner.INSTRUMENT_PIP.get("XAUUSD", 0.01),
            crt_config=crt_cfg,
        )
        cfg.scorer_mode = "calibrated"
        loader = _bt.CandleLoader(str(CSV), "XAUUSD")
        runner = _bt.BacktestRunner(cfg, csv_path=str(CSV), overrides={"_spine_adapter": "1"})
        runner.run(loader.stream(), loader.count(), str(out_dir))
    finally:
        _pc.get_prod_section = _gps
        _pc.PROD_VERSION = _pc_prev
        _bt.PROD_VERSION = _bt_prev
        _crt.setLevel(_crt_prev)
    trades = sorted(out_dir.rglob("XAUUSD_trades.csv"), key=lambda p: p.stat().st_mtime)
    if not trades:
        return {}, sess
    return src._parse_trades(trades[-1], "XAUUSD"), sess


def main() -> int:
    from research.contracts import Signal
    from research.measurement.forward_walk import forward_walk
    from runtime.backtest_v2 import CandleLoader
    from core.engine_runner import EngineRunner

    OUT.mkdir(parents=True, exist_ok=True)
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    t0 = datetime.now(timezone.utc).isoformat()
    calls = {"n": 0}
    _orig = EngineRunner.run

    def _counted(self, *a, **k):
        calls["n"] += 1
        return _orig(self, *a, **k)

    EngineRunner.run = _counted  # type: ignore[method-assign]
    try:
        entries, sess = _ns_entries()
    finally:
        EngineRunner.run = _orig  # type: ignore[method-assign]

    if calls["n"] == 0:
        print("HARD_STOP: EngineRunner.run called 0 times")
        return 2

    loader = CandleLoader(str(CSV), "XAUUSD")
    candles = list(loader.stream())
    for i, c in enumerate(candles):
        if not hasattr(c, "index") or c.index is None:
            c.index = i

    rows = []
    for idx, ent in sorted(entries.items()):
        if idx < 0 or idx >= len(candles):
            continue
        sig = Signal(
            instrument="XAUUSD",
            timestamp=datetime.fromisoformat(ent.timestamp) if ent.timestamp else datetime.now(),
            entry_index=idx,
            direction=ent.direction,
            entry=ent.entry,
            sl_atr_mult=1.0,
            tp_atr_mult=ent.reward_distance / ent.risk_distance,
            atr=ent.risk_distance,
            meta={},
        )
        outc = forward_walk(sig, candles[idx + 1 :], max_forward=MAX_FORWARD, exit_model="intrabar_fixed")
        cost_r = _cost_r(ent.entry, ent.risk_distance)
        rows.append(
            {
                "trade_id": f"CRT-NS-{idx}",
                "entry_index": idx,
                "entry_ts": ent.timestamp,
                "side": ent.direction,
                "entry": ent.entry,
                "fw_outcome": outc.outcome,
                "fw_rr_gross": outc.rr_achieved,
                "cost_r_12bps": cost_r,
                "fw_rr_net": outc.rr_achieved - cost_r,
                "backtest_pnl_rr_net": ent.meta.get("backtest_pnl_rr_net"),
            }
        )
    rows.sort(key=lambda r: (r["entry_ts"], r["entry_index"]))
    n = len(rows)
    split_i = max(0, int(round(n * (1.0 - OOS_FRAC))))
    train, oos = rows[:split_i], rows[split_i:]
    if oos:
        oos0 = oos[0]["entry_index"]
        train = [r for r in train if r["entry_index"] + EMBARGO_BARS < oos0]

    def _stats(rs):
        if not rs:
            return {"n": 0}
        nets = [r["fw_rr_net"] for r in rs]
        wins = sum(1 for x in nets if x > 0)
        pos = sum(x for x in nets if x > 0)
        neg = abs(sum(x for x in nets if x <= 0))
        return {
            "n": len(rs),
            "win_rate": wins / len(rs),
            "net_expectancy_R": sum(nets) / len(rs),
            "profit_factor": (pos / neg) if neg > 0 else None,
        }

    verdict = "INSUFFICIENT" if n < N_MIN else "DIAGNOSTIC_ONLY"
    pop = {
        "contract_id": CONTRACT_ID,
        "n_trade_opened": n,
        "engine_runner_calls": calls["n"],
        "corpus_sha256": _sha256(CSV),
        "n_bars": len(candles),
        "bar_start": str(getattr(candles[0], "timestamp", "")),
        "bar_end": str(getattr(candles[-1], "timestamp", "")),
        "crt_sessions": list(sess),
        "adapter_sessions": ADAPTER_SESSIONS[:6],
        "not_production": True,
        "v1_n": 3,
        "soff_n": 12,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "population_fingerprint.json").write_text(json.dumps(pop, indent=2, default=str), encoding="utf-8")
    (OUT / "metrics.json").write_text(
        json.dumps(
            {
                "verdict": verdict,
                "economic_claims_allowed": False,
                "n_vs": {"v1": 3, "soff": 12, "ns": n},
                "all": _stats(rows),
                "train": _stats(train),
                "oos": _stats(oos),
                "started_utc": t0,
                "finished_utc": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (OUT / "trades.jsonl").write_text(
        "\n".join(json.dumps(r, default=str) for r in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )
    (OUT / "label_rederive.json").write_text(json.dumps({"n": n}, indent=2), encoding="utf-8")
    (OUT / "split_manifest.json").write_text(
        json.dumps({"n_all": n, "n_train": len(train), "n_oos": len(oos)}, indent=2), encoding="utf-8"
    )
    (OUT / "cost_exit_fixture.json").write_text(
        json.dumps({"bps": BPS, "example": rows[0] if rows else None}, indent=2, default=str),
        encoding="utf-8",
    )
    (OUT / "mt00.json").write_text(json.dumps({"status": "UNRUN", "engine_runner_calls": calls["n"]}, indent=2), encoding="utf-8")
    (OUT / "mt01.json").write_text(json.dumps({"status": "UNRUN", "implemented_classes": 0}, indent=2), encoding="utf-8")

    contract["evidence_artifacts"]["population_fingerprint_path"] = str((OUT / "population_fingerprint.json").as_posix())
    contract["evidence_artifacts"]["metric_compute_path"] = str((OUT / "metrics.json").as_posix())
    contract["evidence_artifacts"]["label_rederive_path"] = str((OUT / "label_rederive.json").as_posix())
    contract["evidence_artifacts"]["split_manifest_path"] = str((OUT / "split_manifest.json").as_posix())
    contract["evidence_artifacts"]["cost_exit_fixture_path"] = str((OUT / "cost_exit_fixture.json").as_posix())
    contract["evidence_artifacts"]["mt00_report_path"] = str((OUT / "mt00.json").as_posix())
    contract["evidence_artifacts"]["mt01_mutation_coverage_path"] = str((OUT / "mt01.json").as_posix())
    contract["evidence_artifacts"]["data_snapshot_ids"] = [f"sha256:{pop['corpus_sha256']}"]
    contract["population"]["calendar_window"]["start"] = str(pop["bar_start"])
    contract["population"]["calendar_window"]["end"] = str(pop["bar_end"])
    contract["trust_status"]["open_risks_non_blocking"] = list(
        dict.fromkeys(
            list(contract["trust_status"].get("open_risks_non_blocking") or [])
            + [f"diagnostic_walk_verdict={verdict}", f"n_trade_opened={n}"]
        )
    )
    CONTRACT.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": verdict, "n": n, "engine_runner_calls": calls["n"], "all": _stats(rows)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
