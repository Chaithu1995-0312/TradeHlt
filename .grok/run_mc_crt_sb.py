"""Diagnostic walk for MC-CRT-SB-XAUUSD-M15-V1. Not E-MT-00. Grants no edge."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.chdir(ROOT)
os.environ.pop("BACKTEST_ENGINE_GATE", None)

CONTRACT_ID = "MC-CRT-SB-XAUUSD-M15-V1"
CONTRACT = ROOT / "configs/research/measurement_contracts/instances" / f"{CONTRACT_ID}.json"
SPINE_CFG = ROOT / "configs/research/research_config_mc_crt_sb_xauusd.json"
OUT = ROOT / "results/research/mc_crt_sb_xauusd_m15_v1"
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


def main() -> int:
    from research.adapters.spine_signal_source import ProductionSpineSource
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

    src = ProductionSpineSource(str(SPINE_CFG), out_root=str(OUT / "_spine"))
    try:
        entries = src.entries("XAUUSD")
    finally:
        EngineRunner.run = _orig  # type: ignore[method-assign]

    if calls["n"] == 0:
        (OUT / "mt00.json").write_text(
            json.dumps({"status": "HARD_STOP", "reason": "EngineRunner.run called 0 times"}, indent=2),
            encoding="utf-8",
        )
        print("HARD_STOP: EngineRunner.run called 0 times — gate did not engage")
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
        sl_m = 1.0
        tp_m = ent.reward_distance / ent.risk_distance
        sig = Signal(
            instrument="XAUUSD",
            timestamp=datetime.fromisoformat(ent.timestamp) if ent.timestamp else datetime.now(),
            entry_index=idx,
            direction=ent.direction,
            entry=ent.entry,
            sl_atr_mult=sl_m,
            tp_atr_mult=tp_m,
            atr=atr,
            meta={"sl": ent.meta.get("sl"), "tp": ent.meta.get("tp"), "trade_id": f"CRT-SB-{idx}"},
        )
        future = candles[idx + 1 :]
        outc = forward_walk(sig, future, max_forward=MAX_FORWARD, exit_model="intrabar_fixed")
        cost_r = _cost_r(ent.entry, ent.risk_distance)
        net_r = outc.rr_achieved - cost_r
        bt_net = ent.meta.get("backtest_pnl_rr_net")
        rows.append(
            {
                "trade_id": f"CRT-SB-{idx}",
                "entry_index": idx,
                "entry_ts": ent.timestamp,
                "side": ent.direction,
                "entry": ent.entry,
                "risk_distance": ent.risk_distance,
                "reward_distance": ent.reward_distance,
                "fw_outcome": outc.outcome,
                "fw_rr_gross": outc.rr_achieved,
                "cost_r_12bps": cost_r,
                "fw_rr_net": net_r,
                "fw_duration": outc.duration_candles,
                "backtest_exit_reason": ent.meta.get("backtest_exit_reason"),
                "backtest_pnl_rr_net": bt_net,
                "crt_state_at_open": "EXECUTION",
                "setup_id": f"CRT-SB-{idx}",
            }
        )

    rows.sort(key=lambda r: (r["entry_ts"], r["entry_index"]))
    n = len(rows)
    split_i = max(0, int(round(n * (1.0 - OOS_FRAC))))
    train, oos = rows[:split_i], rows[split_i:]
    # embargo: drop train whose entry is within 96 bars of first OOS entry
    if oos:
        oos0 = oos[0]["entry_index"]
        train = [r for r in train if r["entry_index"] + EMBARGO_BARS < oos0]

    def _agree(rs):
        comps = [
            r
            for r in rs
            if r["backtest_pnl_rr_net"] is not None
            and r["fw_rr_net"] is not None
        ]
        if not comps:
            return {"n_compared": 0, "agree_sign": None}
        agree = sum(
            1
            for r in comps
            if (r["fw_rr_net"] > 0) == (float(r["backtest_pnl_rr_net"]) > 0)
        )
        return {"n_compared": len(comps), "agree_sign": agree / len(comps)}

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

    def _max_dd(xs):
        eq = 0.0
        peak = 0.0
        dd = 0.0
        for x in xs:
            eq += x
            peak = max(peak, eq)
            dd = min(dd, eq - peak)
        return dd

    agree_all = _agree(rows)
    block = (
        agree_all["n_compared"] > 0
        and agree_all["agree_sign"] is not None
        and agree_all["agree_sign"] < 0.99
    )
    power = n >= N_MIN
    verdict = "INSUFFICIENT" if not power else ("BLOCK_EXPERIMENT" if block else "DIAGNOSTIC_ONLY")

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
        "active_version": "v2_multi_2026_04",
        "f074_directional_displacement": True,
        "unit_of_analysis": "trade_decision",
        "detection_vs_trade": "trade_ledger",
    }
    (OUT / "population_fingerprint.json").write_text(json.dumps(pop, indent=2, default=str), encoding="utf-8")
    (OUT / "label_rederive.json").write_text(
        json.dumps(
            {
                "matcher": "trade_id+entry_ts+side",
                "min_agreement": 0.99,
                "on_fail": "BLOCK_EXPERIMENT",
                "agreement": agree_all,
                "blocked": block,
                "note": "Sign agreement fw_rr_net vs backtest_pnl_rr_net. Geometry is single-TP2; spine may scale out.",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (OUT / "split_manifest.json").write_text(
        json.dumps(
            {
                "scheme": "single_holdout_chronologic",
                "oos_fraction": OOS_FRAC,
                "embargo_bars": EMBARGO_BARS,
                "n_all": n,
                "n_train_after_embargo": len(train),
                "n_oos": len(oos),
                "oos_first_ts": oos[0]["entry_ts"] if oos else None,
                "oos_last_ts": oos[-1]["entry_ts"] if oos else None,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    metrics = {
        "verdict": verdict,
        "economic_claims_allowed": False,
        "n_declared_min": N_MIN,
        "all": _stats(rows),
        "train": _stats(train),
        "oos": _stats(oos),
        "cost_model": "CM-XAUUSD-LEGACY-12BPS-UNCALIBRATED",
        "max_forward": MAX_FORWARD,
        "partial_tp_not_reproduced": True,
        "started_utc": t0,
        "finished_utc": datetime.now(timezone.utc).isoformat(),
    }
    (OUT / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    (OUT / "trades.jsonl").write_text(
        "\n".join(json.dumps(r, default=str) for r in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )
    (OUT / "cost_exit_fixture.json").write_text(
        json.dumps(
            {
                "exit_model": "intrabar_fixed",
                "max_forward": MAX_FORWARD,
                "round_trip_bps": BPS,
                "example": rows[0] if rows else None,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    (OUT / "mt00.json").write_text(
        json.dumps(
            {
                "status": "UNRUN",
                "note": "This walk is diagnostic. E-MT-00 official probe set was not executed. 27 E-MT-01 classes remain unimplemented.",
                "engine_runner_calls": calls["n"],
                "non_vacuity_gate_engaged": True,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (OUT / "mt01.json").write_text(
        json.dumps({"status": "UNRUN", "implemented_classes": 0, "declared_classes": 27}, indent=2),
        encoding="utf-8",
    )

    # Update contract evidence paths only — do not flip economic_admissible.
    contract["evidence_artifacts"]["population_fingerprint_path"] = str(
        (OUT / "population_fingerprint.json").as_posix()
    )
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

    print(json.dumps({"verdict": verdict, "n": n, "engine_runner_calls": calls["n"], "oos": _stats(oos)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
