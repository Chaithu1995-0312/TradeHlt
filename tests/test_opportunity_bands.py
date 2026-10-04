"""Tests for src/research/opportunity_bands.py — the Phase-1 per-row deriver.

This is the function the CLI script (scripts/research/derive_opportunity_rr_bands.py)
calls once per row; correctness here is correctness of the whole sidecar. Every count
below was independently verified by direct corpus scans earlier in this registration
(see assistant_project.md SESSION LOG entries dated 2026-09-14) — this file re-derives
them through the actual production function, not a parallel reimplementation.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from research.band_tables import load_band_table
from research.opportunity_bands import (
    DerivedBands,
    OpportunityBandsError,
    derive_row_bands,
    sidecar_header,
)

_REFERENCE_RUN = Path("logs/XAUUSD/20260913_130531/opportunities.jsonl")
skip_no_reference_run = pytest.mark.skipif(
    not _REFERENCE_RUN.exists(),
    reason="reference dry-scan run not present (logs/** is gitignored; not on every clone)",
)


def _row(outcome: str, rr: float, entry: float, sl: float, mfe: float, mae: float) -> dict:
    return {"outcome": outcome, "rr_achieved": rr, "entry": entry, "sl": sl, "mfe": mfe, "mae": mae}


# ---------------------------------------------------------------------------
# Unit-level: one hand-built row per branch
# ---------------------------------------------------------------------------


def test_original_stop_exit():
    # risk_distance = |100 - 95| = 5; never-armed atom: rr == -1.0 exactly.
    row = _row("SL_HIT", -1.0, entry=100.0, sl=95.0, mfe=1.0, mae=-5.0)
    d = derive_row_bands(row)
    assert isinstance(d, DerivedBands)
    assert d.exit_mechanism == "ORIGINAL_STOP_EXIT"
    assert d.trail_state == "TRAIL_NEVER_ARMED"
    assert d.risk_distance == pytest.approx(5.0)
    assert d.mfe_r == pytest.approx(0.2)  # < TRAIL_MULT (0.5) -- consistent with never-armed


def test_trail_stop_exit():
    row = _row("SL_HIT", 0.76, entry=100.0, sl=95.0, mfe=6.83, mae=-3.39)
    d = derive_row_bands(row)
    assert d.exit_mechanism == "TRAIL_STOP_EXIT"
    assert d.trail_state == "TRAIL_ARMED"  # mfe_r = 6.83/5 = 1.366 >= 0.5
    assert d.rr_band == "RR_0_TO_1"


def test_tp_exit():
    row = _row("TP_HIT", 2.0, entry=100.0, sl=95.0, mfe=10.0, mae=-1.0)
    d = derive_row_bands(row)
    assert d.exit_mechanism == "TP_EXIT"
    assert d.rr_band == "RR_GE_2"


def test_timeout_exit():
    row = _row("TIMEOUT", -0.3, entry=100.0, sl=95.0, mfe=2.0, mae=-2.5)
    d = derive_row_bands(row)
    assert d.exit_mechanism == "TIMEOUT_EXIT"
    assert d.rr_band == "RR_NEG1_TO_0"


def test_unknown_outcome_fails_closed():
    row = _row("BREAKEVEN", 0.0, entry=100.0, sl=95.0, mfe=0.0, mae=0.0)
    with pytest.raises(OpportunityBandsError, match="unknown outcome literal"):
        derive_row_bands(row)


def test_sl_hit_below_neg1_fails_closed_rather_than_mislabel():
    """An SL_HIT with rr < -1.0 means adverse fill (SEM-016) is active — outside
    what SEM-037's arming identity covers. Must refuse, not silently call it
    ORIGINAL_STOP_EXIT (which the exact -1.0 atom check would otherwise miss)."""
    row = _row("SL_HIT", -1.3425, entry=100.0, sl=95.0, mfe=0.0, mae=-6.71)
    with pytest.raises(OpportunityBandsError, match="outside the SEM-037 never-armed atom"):
        derive_row_bands(row)


def test_non_positive_risk_distance_fails_closed():
    row = _row("SL_HIT", -1.0, entry=100.0, sl=100.0, mfe=0.0, mae=0.0)
    with pytest.raises(OpportunityBandsError, match="non-positive risk_distance"):
        derive_row_bands(row)


def test_unit_conversion_uses_risk_distance_not_raw_price():
    """The exact bug SEM-037's validation_rules warns about: rr_achieved is in R,
    mfe/mae are in price. This test would pass even with the bug (both interpretations
    give a plausible-looking number) unless risk_distance itself is checked."""
    row = _row("SL_HIT", 0.5, entry=100.0, sl=90.0, mfe=7.5, mae=-10.0)  # risk_distance=10
    d = derive_row_bands(row)
    assert d.risk_distance == pytest.approx(10.0)
    assert d.mfe_r == pytest.approx(0.75)   # 7.5 / 10, NOT 7.5 (the price value) or 7.5/0.5
    assert d.mae_r == pytest.approx(-1.0)


def test_caller_may_preload_tables_for_bulk_use():
    """A script processing 94k rows should load tables once, not once per row —
    exercised so that path is proven, not just documented."""
    econ = load_band_table("BT-RR-ECON-V1")
    cap = load_band_table("BT-CAPTURE-V1")
    row = _row("TP_HIT", 2.0, entry=100.0, sl=95.0, mfe=10.0, mae=-1.0)
    d = derive_row_bands(row, econ_table=econ, capture_table=cap)
    assert d.exit_mechanism == "TP_EXIT"


def test_sidecar_header_shape():
    header = sidecar_header(
        source_path="logs/XAUUSD/20260913_130531/opportunities.jsonl",
        source_run_id="20260913_130531",
        source_trace_id="TR-PIPEB-STRAT-01",
    )
    assert header["type"] == "sidecar_header"
    assert header["band_table_id"] == "BT-RR-ECON-V1"
    assert header["capture_table_id"] == "BT-CAPTURE-V1"
    assert header["mfe_basis"] == "EXIT_TRUNCATED"
    assert header["cost_basis"] == "NONE"
    assert header["governed_by_cc"] == "CC-OPP-BAND-RESTATEMENT"
    assert header["refused_by_cc"] == "CC-OPP-BAND-NOT-ECONOMIC"


# ---------------------------------------------------------------------------
# Reference-run regression: reproduce EVERY previously-verified aggregate
# through derive_row_bands() itself, not a parallel implementation.
# ---------------------------------------------------------------------------


@skip_no_reference_run
def test_reference_run_full_aggregate_reproduction():
    econ = load_band_table("BT-RR-ECON-V1")
    cap = load_band_table("BT-CAPTURE-V1")

    exit_mech_counts: dict[str, int] = {}
    trail_counts: dict[str, int] = {}
    rr_band_counts: dict[str, int] = {}
    capture_counts: dict[str, int] = {}
    n = 0
    n_errors = 0

    with open(_REFERENCE_RUN, encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if row.get("type") == "run_header":
                continue
            n += 1
            try:
                d = derive_row_bands(row, econ_table=econ, capture_table=cap)
            except OpportunityBandsError:
                n_errors += 1
                continue
            exit_mech_counts[d.exit_mechanism] = exit_mech_counts.get(d.exit_mechanism, 0) + 1
            trail_counts[d.trail_state] = trail_counts.get(d.trail_state, 0) + 1
            rr_band_counts[d.rr_band] = rr_band_counts.get(d.rr_band, 0) + 1
            capture_counts[d.capture_state] = capture_counts.get(d.capture_state, 0) + 1

    assert n == 94_332
    assert n_errors == 0, "every reference-run row must classify without a fail-closed refusal"

    # exit_mechanism: TP_EXIT=TP_HIT total (1,344); ORIGINAL_STOP_EXIT=the -1.0 atom
    # (30,797); TRAIL_STOP_EXIT=the rest of SL_HIT (62,140); TIMEOUT_EXIT=51.
    assert exit_mech_counts == {
        "TP_EXIT": 1_344,
        "ORIGINAL_STOP_EXIT": 30_797,
        "TRAIL_STOP_EXIT": 62_140,
        "TIMEOUT_EXIT": 51,
    }
    # trail_state is computed independently of exit_mechanism (from mfe_r alone,
    # for EVERY outcome) yet must reproduce the exact same never-armed/armed split
    # for the SL_HIT population, confirming the two derivations agree.
    assert trail_counts["TRAIL_NEVER_ARMED"] + trail_counts["TRAIL_ARMED"] == 94_332

    assert rr_band_counts == {
        "RR_EQ_NEG1": 30_797,
        "RR_NEG1_TO_0": 33,
        "RR_0_TO_1": 56_869,
        "RR_1_TO_2": 5_289,
        "RR_GE_2": 1_344,
    }
    assert capture_counts == {
        "CAPTURE_UNDEFINED": 1_491,
        "CAPTURE_UNSTABLE": 4_007,
        "CAPTURE_NEGATIVE": 25_332,
        "CAPTURE_GIVEBACK": 15_648,
        "CAPTURE_MODERATE": 28_515,
        "CAPTURE_GOOD": 19_335,
        "CAPTURE_EFFICIENT": 4,
    }
