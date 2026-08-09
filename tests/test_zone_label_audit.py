"""Tests for the F-041B ZoneGate label-provenance audit (src/research/zone_label_audit.py).

Covers the pure logic: the tiered membership gate (incl. the permuted-partition guard that a
same-size swap does NOT reach VERIFIED), bootstrap CI determinism, per-zone sufficiency, the
pre-registered verdict classifier, and honest_outcome (SL-first + no-lookahead).
"""
from __future__ import annotations

import os
import sys
from dataclasses import replace
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from research.zone_label_audit import (  # noqa: E402
    ZoneAudit, verify_membership, _bootstrap_ci, audit_zones, classify_verdict,
    honest_outcome, net_r, MIN_N,
)
from research.contracts import Signal  # noqa: E402
from research.measurement.forward_walk import forward_walk  # noqa: E402


# ── tiny candle stub (forward_walk reads .high/.low/.close/.index/.timestamp) ──────
class _Bar:
    def __init__(self, index, high, low, close, ts=None):
        self.index, self.high, self.low, self.close = index, high, low, close
        self.timestamp = ts or datetime(2026, 1, 1) + timedelta(minutes=15 * index)


def _stored_zone(zid, n, mean_rr, sl):
    return {"id": zid, "meta": {"n_samples": n, "mean_rr": mean_rr, "sl_hit_rate": sl}}


# ─────────────────────────────────────────────────────────────────────────────────
# Membership verification — tiered gate
# ─────────────────────────────────────────────────────────────────────────────────
def test_membership_verified_when_stats_reproduce():
    # 5 records: zone A (idx 0,1,2 = SL,SL,TP), zone B (idx 3,4 = TP,SL)
    outcomes = ["SL_HIT", "SL_HIT", "TP_HIT", "TP_HIT", "SL_HIT"]
    rrs = [-1.0, -1.0, 2.0, 2.0, -1.0]
    # stored stats computed from those exact memberships
    stored = [_stored_zone("zone_0", 3, round((-1 - 1 + 2) / 3, 4), round(2 / 3, 4)),
              _stored_zone("zone_1", 2, round((2 - 1) / 2, 4), round(1 / 2, 4))]
    reconstructed = [[0, 1, 2], [3, 4]]
    res = verify_membership(stored, reconstructed, outcomes, rrs)
    assert res["status"] == "VERIFIED"
    assert res["counts_match"] and res["stats_reproduced"]
    assert res["mapping"] == {0: 0, 1: 1}


def test_membership_permuted_same_size_is_not_verified():
    # Two EQUAL-size zones; swap members → counts still match but per-zone stats do not reproduce.
    outcomes = ["SL_HIT", "SL_HIT", "TP_HIT", "TP_HIT"]
    rrs = [-1.0, -1.0, 2.0, 2.0]
    stored = [_stored_zone("zone_0", 2, -1.0, 1.0),   # the two SL members
              _stored_zone("zone_1", 2, 2.0, 0.0)]    # the two TP members
    reconstructed = [[2, 3], [0, 1]]                  # SWAPPED
    res = verify_membership(stored, reconstructed, outcomes, rrs)
    assert res["counts_match"] is True
    assert res["stats_reproduced"] is False
    assert res["status"] == "PARTIALLY_VERIFIED"


def test_membership_count_mismatch_is_failed():
    outcomes = ["SL_HIT", "TP_HIT", "TP_HIT"]
    rrs = [-1.0, 2.0, 2.0]
    stored = [_stored_zone("zone_0", 2, 0.0, 0.5), _stored_zone("zone_1", 1, 2.0, 0.0)]
    reconstructed = [[0], [1, 2]]  # sizes {1,2} vs stored {2,1} → multiset equal? {1,2}=={1,2} → matches
    # force a real mismatch: reconstructed sizes {3,0}
    reconstructed = [[0, 1, 2], []]
    res = verify_membership(stored, reconstructed, outcomes, rrs)
    assert res["status"] == "FAILED"
    assert res["counts_match"] is False


# ─────────────────────────────────────────────────────────────────────────────────
# Bootstrap CI
# ─────────────────────────────────────────────────────────────────────────────────
def test_bootstrap_ci_deterministic_and_brackets_mean():
    vals = [(-1.0) if i % 3 else 2.0 for i in range(90)]
    mean = sum(vals) / len(vals)
    lo1, hi1 = _bootstrap_ci(vals)
    lo2, hi2 = _bootstrap_ci(vals)
    assert (lo1, hi1) == (lo2, hi2)          # deterministic (seeded)
    assert lo1 <= mean <= hi1                # CI brackets the point estimate


# ─────────────────────────────────────────────────────────────────────────────────
# Per-zone audit — sufficiency gating
# ─────────────────────────────────────────────────────────────────────────────────
def _fake_outcome(rr, outcome):
    sig = Signal(instrument="X", timestamp=datetime(2026, 1, 1), entry_index=0,
                 direction="long", entry=100.0, sl_atr_mult=1.0, tp_atr_mult=2.0, atr=1.0)
    from research.contracts import Outcome
    return Outcome(signal=sig, outcome=outcome, rr_achieved=rr, mfe=0.0, mae=0.0,
                   duration_candles=1, time_to_tp=None, time_to_failure=1, reached_1r=False)


def test_audit_zones_insufficient_makes_no_expectancy_claim():
    small = [[i for i in range(5)]]          # n=5 < MIN_N
    honest = [_fake_outcome(-1.0, "SL_HIT") for _ in range(5)]
    stored = [_stored_zone("zone_0", 5, -1.0, 1.0)]
    audits = audit_zones(small, {0: 0}, stored, honest)
    assert audits[0].sufficiency == "INSUFFICIENT"
    assert audits[0].honest_expectancy is None
    assert audits[0].ci_low is None


def test_audit_zones_sufficient_computes_expectancy():
    members = [list(range(MIN_N + 5))]
    honest = [_fake_outcome(-1.0, "SL_HIT") for _ in range(MIN_N + 5)]
    stored = [_stored_zone("zone_0", MIN_N + 5, -1.0, 1.0)]
    audits = audit_zones(members, {0: 0}, stored, honest)
    assert audits[0].sufficiency == "SUFFICIENT"
    assert audits[0].honest_expectancy is not None
    assert audits[0].honest_sl_rate == 1.0


# ─────────────────────────────────────────────────────────────────────────────────
# Verdict classifier — pre-registered outcomes
# ─────────────────────────────────────────────────────────────────────────────────
def _audit(zid, n, stored_sl, honest_sl, stored_mean_rr, exp, ci_low, ci_high, suff):
    return ZoneAudit(zid, n, stored_sl, honest_sl, round(honest_sl - stored_sl, 4),
                     stored_mean_rr, exp, ci_low, ci_high, suff)


def test_verdict_contaminated_on_sl_delta():
    a = [_audit("z0", 100, 0.98, 0.40, -0.03, -0.2, -0.3, -0.1, "SUFFICIENT")]  # Δ=-0.58
    v = classify_verdict(a, "VERIFIED")
    assert v["verdict"] == "CONTAMINATED"
    assert v["contaminated_by_sl_delta"] is True


def test_verdict_honest_no_edge():
    a = [_audit("z0", 100, 0.98, 0.97, -0.03, -0.15, -0.25, -0.05, "SUFFICIENT")]
    v = classify_verdict(a, "VERIFIED")
    assert v["verdict"] == "HONEST_NO_EDGE"


def test_verdict_honest_edge_requires_positive_ci_low():
    a = [_audit("z0", 100, 0.30, 0.30, 0.05, 0.20, 0.05, 0.35, "SUFFICIENT")]
    v = classify_verdict(a, "VERIFIED")
    assert v["verdict"] == "HONEST_EDGE"
    assert v["edge_zones"] == ["z0"]


# ─────────────────────────────────────────────────────────────────────────────────
# honest_outcome — SL-first geometry + no-lookahead
# ─────────────────────────────────────────────────────────────────────────────────
def test_honest_outcome_sl_first_returns_sl_hit():
    # long entry 100, sl 99 (risk 1), tp 102. First forward bar dips to 98 → SL.
    opp = {"timestamp": "2026-01-01 00:15:00", "direction": "long",
           "entry": 100.0, "sl": 99.0, "tp": 102.0, "instrument": "X"}
    candles = [_Bar(0, 100.5, 99.8, 100.0, ts=datetime(2026, 1, 1, 0, 0)),
               _Bar(1, 100.2, 98.0, 99.0)]   # index 1 = the entry bar's ts is idx via ts_to_idx
    ts_to_idx = {"2026-01-01 00:15:00": 0}   # entry maps to candle 0; future = candles[1:]
    o = honest_outcome(opp, candles, ts_to_idx)
    assert o is not None and o.outcome == "SL_HIT"


def test_honest_outcome_skips_when_no_candle():
    opp = {"timestamp": "1999-01-01 00:00:00", "direction": "long",
           "entry": 100.0, "sl": 99.0, "tp": 102.0}
    assert honest_outcome(opp, [], {}) is None


def test_forward_walk_rejects_leaked_bar():
    sig = Signal(instrument="X", timestamp=datetime(2026, 1, 1), entry_index=5,
                 direction="long", entry=100.0, sl_atr_mult=1.0, tp_atr_mult=2.0, atr=1.0)
    leaked = [_Bar(5, 101.0, 100.5, 100.8)]  # index 5 == entry_index → must raise
    with pytest.raises(ValueError):
        forward_walk(sig, leaked, exit_model="intrabar_fixed")
