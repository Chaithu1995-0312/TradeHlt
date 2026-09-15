"""
tests/test_dashboard_run_scope.py
==================================

Floor for the run-scoped Executive Overview surface added to
``src/control_plane/dashboard_api.py`` (instrument discovery from disk,
``_resolve_run``, ``executive_payload``) and the ordinal/name session-bucket
mapping real trade CSVs depend on.

No prior test covered this module (``test_control_plane_api.py`` exercises
only the generic job-lifecycle API). ``results/`` and ``logs/`` are gitignored
data trees, so every test here skips cleanly when the fixture it needs is
absent — this floor asserts real-corpus invariants where a run exists, and
never fabricates one, per CLAUDE.md §1.1 evidence discipline.
"""
from __future__ import annotations

import pytest

from src.control_plane.dashboard_api import (
    TradingDashboardAPI,
    _instruments_from_disk,
    _iter_run_dirs,
    _resolve_run,
    _session_bucket_ui,
    _volatility_regime_label,
)


def _any_instrument_with_runs() -> str | None:
    """First instrument (by disk scan) that has at least one backtest run."""
    for name in sorted(_instruments_from_disk()):
        if next(_iter_run_dirs(name), None) is not None:
            return name
    return None


# ── instrument discovery ────────────────────────────────────────────────────

def test_instruments_payload_includes_disk_only_instrument():
    """
    A regression guard for the XAUUSD bug: an instrument with runs on disk but
    absent from the active config's pairs/allowed_symbols must still appear.
    """
    inst = _any_instrument_with_runs()
    if inst is None:
        pytest.skip("no results/run_*_<INSTR>/ fixtures on disk in this clone")
    api = TradingDashboardAPI()
    names = api.instruments_payload()["instruments"]
    assert inst in names


# ── run resolution ──────────────────────────────────────────────────────────

def test_resolve_run_latest_and_exact_and_foreign_id():
    inst = _any_instrument_with_runs()
    if inst is None:
        pytest.skip("no results/run_*_<INSTR>/ fixtures on disk in this clone")

    runs = list(_iter_run_dirs(inst))
    assert runs, "sanity: _any_instrument_with_runs found none"

    latest = _resolve_run(inst, None)
    assert latest is not None
    assert latest.run_id == runs[-1].run_id  # lexicographic == chronological

    exact = _resolve_run(inst, runs[0].run_id)
    assert exact is not None
    assert exact.run_id == runs[0].run_id

    # Fail-closed: a run_id that exists for a DIFFERENT instrument must not
    # resolve here (prevents cross-coin runid confusion).
    foreign = _resolve_run(inst, "run_00000000_000000_NOT_A_REAL_INSTRUMENT")
    assert foreign is None


def test_resolve_run_none_when_instrument_has_no_runs():
    assert _resolve_run("NOT_A_REAL_INSTRUMENT_XYZ", None) is None


# ── executive_payload ───────────────────────────────────────────────────────

def test_executive_payload_unknown_run_id_is_not_ok():
    inst = _any_instrument_with_runs()
    if inst is None:
        pytest.skip("no results/run_*_<INSTR>/ fixtures on disk in this clone")
    api = TradingDashboardAPI()
    out = api.executive_payload(inst, "run_00000000_000000_" + inst)
    assert out["ok"] is False


def test_executive_payload_kpi_self_consistency():
    """expectancy_rr * n_trades must reconstruct total_pnl_rr_net (both are
    derived from the same trade list; divergence would mean a bug in either
    the KPI block or the pnl_over_time aggregation)."""
    inst = _any_instrument_with_runs()
    if inst is None:
        pytest.skip("no results/run_*_<INSTR>/ fixtures on disk in this clone")
    api = TradingDashboardAPI()
    out = api.executive_payload(inst)  # latest run
    assert out["ok"] is True
    kpis = out["kpis"]
    n = kpis["n_trades"]
    if n:
        assert kpis["expectancy_rr"] * n == pytest.approx(kpis["total_pnl_rr_net"], abs=1e-3)
    # Opportunity density rows carry exactly 12 cells (Jan..Dec) when present.
    for row in out["opportunity_density"]:
        assert len(row["cells"]) == 12
    assert out["alerts"]["status"] == "yet_to_integrate"


def test_runs_payload_newest_first_and_scoped_to_instrument():
    inst = _any_instrument_with_runs()
    if inst is None:
        pytest.skip("no results/run_*_<INSTR>/ fixtures on disk in this clone")
    api = TradingDashboardAPI()
    out = api.runs_payload(inst)
    ids = [r["run_id"] for r in out["runs"]]
    assert ids == sorted(ids, reverse=True)
    assert all(rid.endswith(f"_{inst}") for rid in ids)


# ── session bucket mapping (what real trade CSVs carry) ────────────────────

@pytest.mark.parametrize(
    "value,expected",
    [
        ("3.0", "overlap"),      # ordinal float form (OVERLAP), as emitted by backtest_v2
        ("0", "asian"),
        ("1", "london"),
        ("2", "ny"),
        ("NEWYORK", "ny"),
        ("NEW_YORK", "ny"),
        ("overlap", "overlap"),  # already-named, case-insensitive
        (None, None),
        ("", None),
        ("garbage", None),
    ],
)
def test_session_bucket_ui_mapping(value, expected):
    assert _session_bucket_ui(value) == expected


# ── volatility regime label mapping (what real trade CSVs carry) ───────────

@pytest.mark.parametrize(
    "value,expected",
    [
        (0, "LOW"), (1, "NORMAL"), (2, "HIGH"),
        ("0.0", "LOW"), ("1.0", "NORMAL"), ("2.0", "HIGH"),  # ordinal float-string form
        (None, None),
        ("", None),
        ("garbage", None),
        (3, None),  # out-of-range ordinal — never invent a 4th label
    ],
)
def test_volatility_regime_label_mapping(value, expected):
    assert _volatility_regime_label(value) == expected


def test_trades_payload_carries_conf_and_regime_fields():
    """Regression guard for the page1_runtime.jsx `t.conf.toFixed` crash: every
    trade record must carry a numeric risk_score and a resolved regime label
    (or an explicit None), never a missing key."""
    inst = _any_instrument_with_runs()
    if inst is None:
        pytest.skip("no results/run_*_<INSTR>/ fixtures on disk in this clone")
    api = TradingDashboardAPI()
    out = api.trades_payload(inst)
    for r in out["records"]:
        assert "risk_score" in r
        assert "volatility_regime_label" in r
        if r["risk_score"] is not None:
            assert isinstance(r["risk_score"], float)
        if r["volatility_regime_label"] is not None:
            assert r["volatility_regime_label"] in ("LOW", "NORMAL", "HIGH")
