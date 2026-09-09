"""Diagnostic walk for MC-CRT-SB-XAUUSD-M15-SOFF-V1. Research session policy. No production write."""
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

CONTRACT_ID = "MC-CRT-SB-XAUUSD-M15-SOFF-V1"
CONTRACT = ROOT / "configs/research/measurement_contracts/instances" / f"{CONTRACT_ID}.json"
SPINE_CFG = ROOT / "configs/research/research_config_mc_crt_sb_xauusd.json"
OUT = ROOT / "results/research/mc_crt_sb_xauusd_m15_soff_v1"
CSV = ROOT / "data/mt5/XAUUSD_M15.csv"
BPS = 12.0
MAX_FORWARD = 200
EMBARGO_BARS = 96
OOS_FRAC = 0.20
N_MIN = 30


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


def _soff_entries():
    """Same spine as ProductionSpineSource, but allowed_sessions = all windows + OFF_SESSION."""
    import config_layer.production_config as _pc
    import runtime.backtest_v2 as _bt
    from research.adapters.spine_signal_source import ProductionSpineSource

    version = "v2_multi_2026_04"
    out_dir = OUT / "_spine" / f"XAUUSD__{version}"
    out_dir.mkdir(parents=True, exist_ok=True)
    src = ProductionSpineSource(str(SPINE_CFG), out_root=str(OUT / "_spine"))
    _pc_prev, _bt_prev = _pc.PROD_VERSION, _bt.PROD_VERSION
    _crt = logging.getLogger("CRT")
    _crt_prev = _crt.level
    _crt.setLevel(logging.ERROR)
    try:
        _pc.PROD_VERSION = version
        _bt.PROD_VERSION = version
        crt_cfg = _pc.load_prod_config_from_registry(version, "XAUUSD")
        sess = tuple(crt_cfg.session_windows.keys()) + ("OFF_SESSION",)
        from config_layer.crt_config_provenance import mark_explicit
        crt_cfg = mark_explicit(
            replace(crt_cfg, allowed_sessions=sess),
            instrument="XAUUSD",
            note="MC-CRT-SB-XAUUSD-M15-SOFF-V1 research session policy; not production",
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
        entries, sess = _soff_entries()
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
        atr = ent.risk_distance
        sig = Signal(
            instrument="XAUUSD",
            timestamp=datetime.fromisoformat(ent.timestamp) if ent.timestamp else datetime.now(),
            entry_index=idx,
            direction=ent.direction,
            entry=ent.entry,
            sl_atr_mult=1.0,
            tp_atr_mult=ent.reward_distance / ent.risk_distance,
            atr=atr,
            meta={"trade_id": f"CRT-SOFF-{idx}"},
        )
        outc = forward_walk(sig, candles[idx + 1 :], max_forward=MAX_FORWARD, exit_model="intrabar_fixed")
        cost_r = _cost_r(ent.entry, ent.risk_distance)
        rows.append(
            {
                "trade_id": f"CRT-SOFF-{idx}",
                "entry_index": idx,
                "entry_ts": ent.timestamp,
                "side": ent.direction,
                "entry": ent.entry,
                "risk_distance": ent.risk_distance,
                "fw_outcome": outc.outcome,
                "fw_rr_gross": outc.rr_achieved,
                "cost_r_12bps": cost_r,
                "fw_rr_net": outc.rr_achieved - cost_r,
                "backtest_pnl_rr_net": ent.meta.get("backtest_pnl_rr_net"),
                "backtest_exit_reason": ent.meta.get("backtest_exit_reason"),
            }
        )

    rows.sort(key=lambda r: (r["entry_ts"], r["entry_index"]))
    n = len(rows)
    split_i = max(0, int(round(n * (1.0 - OOS_FRAC))))
    train, oos = rows[:split_i], rows[split_i:]
    if oos:
        oos0 = oos[0]["entry_index"]
        train = [r for r in train if r["entry_index"] + EMBARGO_BARS < oos0]

    def _agree(rs):
        comps = [r for r in rs if r["backtest_pnl_rr_net"] is not None]
        if not comps:
            return {"n_compared": 0, "agree_sign": None}
        agree = sum(
            1 for r in comps if (r["fw_rr_net"] > 0) == (float(r["backtest_pnl_rr_net"]) > 0)
        )
        return {"n_compared": len(comps), "agree_sign": agree / len(comps)}

    def _max_dd(xs):
        eq = peak = dd = 0.0
        for x in xs:
            eq += x
            peak = max(peak, eq)
            dd = min(dd, eq - peak)
        return dd

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
            "max_drawdown_R": _max_dd(nets),
        }

    agree_all = _agree(rows)
    block = (
        agree_all["n_compared"] > 0
        and agree_all["agree_sign"] is not None
        and agree_all["agree_sign"] < 0.99
    )
    verdict = "INSUFFICIENT" if n < N_MIN else ("BLOCK_EXPERIMENT" if block else "DIAGNOSTIC_ONLY")

    pop = {
        "contract_id": CONTRACT_ID,
        "instrument": "XAUUSD",
        "corpus_path": str(CSV.as_posix()),
        "corpus_sha256": _sha256(CSV),
        "n_bars": len(candles),
        "bar_start": str(getattr(candles[0], "timestamp", "")),
        "bar_end": str(getattr(candles[-1], "timestamp", "")),
        "n_trade_opened": n,
        "engine_runner_calls": calls["n"],
        "session_policy": list(sess),
        "not_production_session_filter": True,
        "v1_n_was": 3,
    }
    (OUT / "population_fingerprint.json").write_text(json.dumps(pop, indent=2, default=str), encoding="utf-8")
    (OUT / "label_rederive.json").write_text(
        json.dumps({"agreement": agree_all, "blocked": block}, indent=2), encoding="utf-8"
    )
    (OUT / "split_manifest.json").write_text(
        json.dumps(
            {"n_all": n, "n_train_after_embargo": len(train), "n_oos": len(oos)},
            indent=2,
        ),
        encoding="utf-8",
    )
    metrics = {
        "verdict": verdict,
        "economic_claims_allowed": False,
        "n_declared_min": N_MIN,
        "n_vs_V1": {"v1": 3, "soff": n},
        "all": _stats(rows),
        "train": _stats(train),
        "oos": _stats(oos),
        "started_utc": t0,
        "finished_utc": datetime.now(timezone.utc).isoformat(),
    }
    (OUT / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    (OUT / "trades.jsonl").write_text(
        "\n".join(json.dumps(r, default=str) for r in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )
    (OUT / "cost_exit_fixture.json").write_text(
        json.dumps({"round_trip_bps": BPS, "example": rows[0] if rows else None}, indent=2, default=str),
        encoding="utf-8",
    )
    (OUT / "mt00.json").write_text(
        json.dumps({"status": "UNRUN", "engine_runner_calls": calls["n"]}, indent=2), encoding="utf-8"
    )
    (OUT / "mt01.json").write_text(
        json.dumps({"status": "UNRUN", "implemented_classes": 0, "declared_classes": 27}, indent=2),
        encoding="utf-8",
    )

    contract["evidence_artifacts"]["population_fingerprint_path"] = str((OUT / "population_fingerprint.json").as_posix())
    contract["evidence_artifacts"]["label_rederive_path"] = str((OUT / "label_rederive.json").as_posix())
    contract["evidence_artifacts"]["cost_exit_fixture_path"] = str((OUT / "cost_exit_fixture.json").as_posix())
    contract["evidence_artifacts"]["split_manifest_path"] = str((OUT / "split_manifest.json").as_posix())
    contract["evidence_artifacts"]["metric_compute_path"] = str((OUT / "metrics.json").as_posix())
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
    print(json.dumps({"verdict": verdict, "n": n, "engine_runner_calls": calls["n"], "sess": list(sess), "oos": _stats(oos)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
