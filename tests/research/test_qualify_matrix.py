"""Parity pins for the shared QUALIFY-family scope-loop helpers in `research.qualify_matrix`.

Research-framework consolidation Phase 2 replaced private `_csv_map` / `_winning_control` copies
in 11 scripts/research/qualify_*.py drivers with same-named imports of these functions. The
replacement is only lossless if the shared function behaves exactly like every variant it
replaced — so the two `_csv_map` variants and the one `_winning_control` variant are copied here
VERBATIM (originals archived under archive/research_framework_phase2*_2026-09-14/) and compared on
the same inputs.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from research.costs import CostModel
from research.contracts import Outcome, Signal
from research.measurement.metrics import EdgeAggregator
from research.qualification import _net_rrs
from research import qualify_matrix as qm


# ── verbatim originals ──────────────────────────────────────────────────────────────────────
# variant b83c62316c (e.g. qualify_carry.py, qualify_majors.py, qualify_weekly_sweep.py, …)
def _orig_csv_map_a(cfg, instruments: list[str]) -> dict[str, str]:
    data_dir = Path(cfg.data_dir)
    keep = set(instruments)
    out: dict[str, str] = {}
    for p in sorted(data_dir.glob(cfg.pattern)):
        inst = p.stem.split("_")[0]
        if inst in keep:
            out[inst] = str(p)
    return out


# variant 08e71a58eb (e.g. qualify_transitions.py, qualify_m5_straddle.py, …) — inlines Path()
def _orig_csv_map_b(cfg, instruments: list[str]) -> dict[str, str]:
    keep = set(instruments)
    out: dict[str, str] = {}
    for p in sorted(Path(cfg.data_dir).glob(cfg.pattern)):
        inst = p.stem.split("_")[0]
        if inst in keep:
            out[inst] = str(p)
    return out


# variant 7c421cd3a9 (e.g. qualify_majors.py, qualify_htf.py, qualify_weekly_sweep.py, …)
def _orig_winning_control(per_by_hyp, control_names, scope_instruments, agg, cost):
    win_name, win_rrs, win_exp = "none", [], float("-inf")
    for name in sorted(control_names):
        per = {i: per_by_hyp[name][i] for i in scope_instruments}
        rrs: list[float] = []
        for outs in per.values():
            rrs.extend(_net_rrs(outs, cost))
        rep = agg.aggregate(name, sorted(scope_instruments),
                            [o for outs in per.values() for o in outs], cost_model=cost)
        if rep.expectancy_rr > win_exp:
            win_name, win_rrs, win_exp = name, rrs, rep.expectancy_rr
    if win_exp == float("-inf"):
        win_name, win_rrs, win_exp = "none", [], 0.0
    return win_name, win_rrs, win_exp


@pytest.fixture()
def universe(tmp_path: Path) -> tuple[SimpleNamespace, list[str]]:
    for name in ("BNBUSDT_M15.csv", "ETHUSDT_M15.csv", "BTCUSDT_M15.csv", "OTHERX_M15.csv"):
        (tmp_path / name).write_text("open,high,low,close\n", encoding="utf-8")
    (tmp_path / "not_matched.txt").write_text("x", encoding="utf-8")
    cfg = SimpleNamespace(data_dir=str(tmp_path), pattern="*_M15.csv")
    return cfg, ["BNBUSDT", "ETHUSDT", "BTCUSDT"]


def test_csv_map_matches_both_replaced_variants(universe) -> None:
    cfg, instruments = universe
    expected = {"BNBUSDT": str(Path(cfg.data_dir) / "BNBUSDT_M15.csv"),
                "ETHUSDT": str(Path(cfg.data_dir) / "ETHUSDT_M15.csv"),
                "BTCUSDT": str(Path(cfg.data_dir) / "BTCUSDT_M15.csv")}
    assert _orig_csv_map_a(cfg, instruments) == expected
    assert _orig_csv_map_b(cfg, instruments) == expected
    assert qm.csv_map(cfg, instruments) == expected


def test_csv_map_excludes_unrequested_and_nonmatching_instruments(universe) -> None:
    cfg, _ = universe
    assert qm.csv_map(cfg, ["BNBUSDT"]) == {"BNBUSDT": str(Path(cfg.data_dir) / "BNBUSDT_M15.csv")}
    assert qm.csv_map(cfg, ["NOPE"]) == {}


def test_csv_map_empty_instruments_and_no_glob_matches(tmp_path: Path) -> None:
    cfg = SimpleNamespace(data_dir=str(tmp_path), pattern="*_M15.csv")
    assert qm.csv_map(cfg, []) == {}
    (tmp_path / "SOLUSDT_H1.csv").write_text("x", encoding="utf-8")  # wrong pattern
    assert qm.csv_map(cfg, ["SOLUSDT"]) == {}


def _outcome(rr: float) -> Outcome:
    """A minimal SL_HIT outcome whose rr_achieved is exactly `rr`. risk_distance=1 (sl_atr_mult=
    atr=1) with CostModel(round_trip_bps=0.0) below makes cost_r == 0, so net_rr == rr_achieved
    and the highest-`rr` control is unambiguously the expected winner."""
    sig = Signal(instrument="X", timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
                 entry_index=0, direction="long", entry=1.0, sl_atr_mult=1.0, tp_atr_mult=2.0, atr=1.0)
    return Outcome(signal=sig, outcome="SL_HIT", rr_achieved=rr, mfe=max(rr, 0.0), mae=min(rr, 0.0),
                   duration_candles=1, time_to_tp=None, time_to_failure=None, reached_1r=rr >= 1.0)


def _build_per_by_hyp(seed_map: dict[str, dict[str, float]]) -> dict[str, dict[str, list[Outcome]]]:
    """seed_map: {control_name: {instrument: constant_rr}} -> 5 outcomes per instrument."""
    return {name: {inst: [_outcome(rr)] * 5 for inst, rr in insts.items()}
            for name, insts in seed_map.items()}


def test_winning_control_matches_original_variant() -> None:
    cost = CostModel(round_trip_bps=0.0)
    agg = EdgeAggregator()
    per_by_hyp = _build_per_by_hyp({
        "long_only": {"BNBUSDT": 0.2, "ETHUSDT": 0.1},
        "random_entry": {"BNBUSDT": 0.5, "ETHUSDT": 0.4},
    })
    scope = ["BNBUSDT", "ETHUSDT"]
    controls = ["long_only", "random_entry"]
    expected = _orig_winning_control(per_by_hyp, controls, scope, agg, cost)
    actual = qm.winning_control(per_by_hyp, controls, scope, agg, cost)
    assert actual == expected
    assert actual[0] == "random_entry"  # sanity: higher expectancy wins


def test_winning_control_empty_controls_returns_none_sentinel() -> None:
    cost = CostModel(round_trip_bps=0.0)
    agg = EdgeAggregator()
    expected = _orig_winning_control({}, [], [], agg, cost)
    actual = qm.winning_control({}, [], [], agg, cost)
    assert actual == expected == ("none", [], 0.0)


def test_winning_control_single_scope_instrument() -> None:
    cost = CostModel(round_trip_bps=0.0)
    agg = EdgeAggregator()
    per_by_hyp = _build_per_by_hyp({"a": {"BNBUSDT": -0.1}, "b": {"BNBUSDT": 0.3}})
    expected = _orig_winning_control(per_by_hyp, ["a", "b"], ["BNBUSDT"], agg, cost)
    actual = qm.winning_control(per_by_hyp, ["a", "b"], ["BNBUSDT"], agg, cost)
    assert actual == expected
