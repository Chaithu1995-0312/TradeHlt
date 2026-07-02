"""Program 9 — runner routing: 'oco' signals take the new path, everything else verbatim.

The parity contract (plan + pre-reg): adding the OCO branch and the optional `entry_ttl`
config key must leave every long/short hypothesis's edge_report byte-identical — with or
without `entry_ttl` present in the config JSON. Also pins: an 'oco' hypothesis produces
outcomes through `collect()` (the M4 gate path), cancelled straddles are excluded, and an
'oco' signal without `entry_ttl` fails loudly.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import research.controls    # noqa: F401,E402  (register controls)
import research.hypotheses  # noqa: F401,E402  (register hypotheses)
from research.config import ResearchConfig                                # noqa: E402
from research.runner import HypothesisRunner, edge_report_json            # noqa: E402

_CFG = {
    "harness": {"warmup": 30, "window_size": 64, "min_samples": 10},
    "forward_walk": {"max_forward": 20, "trail_mult": 0.5},
    "signal": {"apply_signal_defaults": True, "sl_atr_mult": 1.0, "tp_atr_mult": 2.0},
    "costs": {"round_trip_bps": 12.0},
    "universe": {"data_dir": "data", "pattern": "*_M5.csv", "instruments": "ALL"},
}


def _cfg_with_ttl() -> dict:
    d = {k: dict(v) for k, v in _CFG.items()}
    d["forward_walk"]["entry_ttl"] = 12
    return d


def _write_csv(path, n=400, start=100.0, step=0.4, wick=0.15):
    """Zig-zag with a few tight compression pockets so straddle setups exist."""
    lines = ["timestamp,open,high,low,close,volume"]
    prev = start
    t = datetime(2026, 1, 1)
    for i in range(n):
        o = prev
        if 200 <= i < 206 or 300 <= i < 306:               # tight pockets
            c = o + 0.02 * (1 if i % 2 else -1)
            hi, lo = max(o, c) + 0.02, min(o, c) - 0.02
        else:
            c = o + step * (1 if i % 3 else -1)
            hi, lo = max(o, c) + wick, min(o, c) - wick
        ts = (t + timedelta(minutes=5 * i)).strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"{ts},{o:.5f},{hi:.5f},{lo:.5f},{c:.5f},1.0")
        prev = c
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ── parity: long/short hypotheses are untouched by the OCO branch + entry_ttl ─────────
@pytest.mark.parametrize("hypothesis", ["expansion_breakout", "mean_reversion", "always_long"])
def test_market_direction_reports_identical_with_and_without_entry_ttl(tmp_path, hypothesis):
    csv = tmp_path / "TESTPAIR_M5.csv"
    _write_csv(csv)
    csv_map = {"TESTPAIR": str(csv)}
    rr_base = HypothesisRunner(ResearchConfig.from_dict(_CFG)).run(hypothesis, csv_map)
    rr_ttl = HypothesisRunner(ResearchConfig.from_dict(_cfg_with_ttl())).run(hypothesis, csv_map)
    # identical evidence (the config sha differs BY DESIGN when entry_ttl is present)
    assert rr_base.pooled == rr_ttl.pooled
    assert rr_base.per_instrument == rr_ttl.per_instrument
    assert rr_base.config_sha256 != rr_ttl.config_sha256


def test_edge_report_still_byte_identical_across_runs(tmp_path):
    csv = tmp_path / "TESTPAIR_M5.csv"
    _write_csv(csv)
    csv_map = {"TESTPAIR": str(csv)}
    cfg = ResearchConfig.from_dict(_cfg_with_ttl())
    j1 = edge_report_json(HypothesisRunner(cfg).run("expansion_breakout", csv_map))
    j2 = edge_report_json(HypothesisRunner(cfg).run("expansion_breakout", csv_map))
    assert j1 == j2


# ── oco routing ──────────────────────────────────────────────────────────────────────
def test_oco_hypothesis_flows_through_collect(tmp_path):
    csv = tmp_path / "TESTPAIR_M5.csv"
    _write_csv(csv)
    cfg = ResearchConfig.from_dict(_cfg_with_ttl())
    outs = HypothesisRunner(cfg).collect("compression_box_straddle", {"TESTPAIR": str(csv)})
    assert len(outs["TESTPAIR"]) > 0                       # the fixture really arms straddles
    # every produced outcome carries a RESOLVED direction and the oco provenance marker
    for oc in outs["TESTPAIR"]:
        assert oc.signal.direction in ("long", "short")
        assert oc.signal.meta.get("oco_resolved") is True
        assert oc.signal.meta.get("bars_to_fill", 0) >= 1


def test_oco_without_entry_ttl_fails_loudly(tmp_path):
    csv = tmp_path / "TESTPAIR_M5.csv"
    _write_csv(csv)
    cfg = ResearchConfig.from_dict(_CFG)                   # no entry_ttl in the JSON
    with pytest.raises(ValueError, match="entry_ttl"):
        HypothesisRunner(cfg).run("compression_box_straddle", {"TESTPAIR": str(csv)})


def test_oco_run_is_deterministic(tmp_path):
    csv = tmp_path / "TESTPAIR_M5.csv"
    _write_csv(csv)
    csv_map = {"TESTPAIR": str(csv)}
    cfg = ResearchConfig.from_dict(_cfg_with_ttl())
    j1 = edge_report_json(HypothesisRunner(cfg).run("compression_box_straddle", csv_map))
    j2 = edge_report_json(HypothesisRunner(cfg).run("compression_box_straddle", csv_map))
    assert j1 == j2
