"""M3 test: the runner is deterministic — same inputs ⇒ byte-identical edge_report.

This matters more than profit factor: reproducible evidence is the foundation M4/M5
stand on.
"""

from datetime import datetime, timedelta

import research.controls   # noqa: F401  (register controls)
import research.hypotheses  # noqa: F401  (register hypotheses)
from research.config import ResearchConfig
from research.runner import HypothesisRunner, edge_report_json

_CFG = {
    "harness": {"warmup": 20, "window_size": 64, "min_samples": 10},
    "forward_walk": {"max_forward": 20, "trail_mult": 0.5},
    "signal": {"apply_signal_defaults": True, "sl_atr_mult": 1.0, "tp_atr_mult": 2.0},
    "costs": {"round_trip_bps": 12.0},
    "universe": {"data_dir": "data", "pattern": "*_M15.csv", "instruments": "ALL"},
}


def _write_csv(path, n=200, start=100.0, step=0.4, wick=0.15):
    lines = ["timestamp,open,high,low,close,volume"]
    prev = start
    t = datetime(2026, 1, 1)
    for i in range(n):
        o = prev
        c = o + step * (1 if i % 3 else -1)             # mild zig-zag, not monotone
        hi = max(o, c) + wick
        lo = min(o, c) - wick
        ts = (t + timedelta(minutes=15 * i)).strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"{ts},{o:.5f},{hi:.5f},{lo:.5f},{c:.5f},1.0")
        prev = c
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_edge_report_is_byte_identical_across_runs(tmp_path):
    csv = tmp_path / "TESTPAIR_M15.csv"
    _write_csv(csv)
    csv_map = {"TESTPAIR": str(csv)}
    cfg = ResearchConfig.from_dict(_CFG)

    j1 = edge_report_json(HypothesisRunner(cfg).run("expansion_breakout", csv_map))
    j2 = edge_report_json(HypothesisRunner(cfg).run("expansion_breakout", csv_map))
    assert j1 == j2                                      # byte-for-byte


def test_report_carries_deterministic_provenance(tmp_path):
    csv = tmp_path / "TESTPAIR_M15.csv"
    _write_csv(csv)
    cfg = ResearchConfig.from_dict(_CFG)
    rr = HypothesisRunner(cfg).run("mean_reversion", {"TESTPAIR": str(csv)})
    assert len(rr.config_sha256) == 64
    assert len(rr.hypothesis_sha256) == 64
    # config hash is stable for identical config content
    assert rr.config_sha256 == ResearchConfig.from_dict(_CFG).sha256()


def test_pooled_aggregates_multiple_instruments(tmp_path):
    a = tmp_path / "AAA_M15.csv"
    b = tmp_path / "BBB_M15.csv"
    _write_csv(a, step=0.4)
    _write_csv(b, step=0.3)
    cfg = ResearchConfig.from_dict(_CFG)
    rr = HypothesisRunner(cfg).run("always_long", {"AAA": str(a), "BBB": str(b)})
    assert set(rr.per_instrument) == {"AAA", "BBB"}
    # pooled n == sum of per-instrument n
    assert rr.pooled.n == rr.per_instrument["AAA"].n + rr.per_instrument["BBB"].n
    assert rr.pooled.instruments == ["AAA", "BBB"]
