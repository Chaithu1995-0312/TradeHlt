"""Floor: SEM-031 nested veto chain is causal, isolated, and not SEM-023 admission."""
from __future__ import annotations

import ast
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_SRC = _REPO / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from research.sujan_crt.geometry import (  # noqa: E402
    Bar,
    VetoParams,
    closed_parents,
    detect_displacement,
    detect_parent_sweep,
    detect_return,
    reward_to_risk,
    structural_stop,
)
from research.sujan_crt.score import WEIGHTS, alignment_score  # noqa: E402
from research.sujan_crt.vetoes import detect_veto_chain_entries  # noqa: E402

_PKG = _SRC / "research" / "sujan_crt"
FORBIDDEN_RUNTIME_MODULES = (
    "config_layer.crt_engine_v2",
    "config_layer.parent_crt",
    "runtime.backtest_v2",
    "research.visual_crt",
    "TradeLib",
    "trade_lib",
)


def _runtime_imports(tree: ast.Module):
    type_only: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        guarded = (
            (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING")
            or (isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING")
        )
        if guarded:
            for inner in node.body:
                type_only.add(id(inner))
    mods: set[str] = set()
    for node in ast.walk(tree):
        if id(node) in type_only:
            continue
        if isinstance(node, ast.Import):
            for alias in node.names:
                mods.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module)
    return mods


@pytest.mark.parametrize("rel", ["geometry.py", "vetoes.py", "score.py", "__init__.py", "driver.py"])
def test_no_spine_or_visual_crt_import(rel: str):
    src = (_PKG / rel).read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported = _runtime_imports(tree)
    hits = [
        m
        for m in FORBIDDEN_RUNTIME_MODULES
        if any(imp == m or imp.startswith(m + ".") for imp in imported)
    ]
    assert hits == [], f"{rel} imports forbidden modules: {hits}"


def test_veto_params_have_no_silent_defaults():
    with pytest.raises(TypeError):
        VetoParams()


def test_sem_023_weights_sum_to_100_and_undefined_is_not_zero():
    assert sum(WEIGHTS.values()) == 100
    assert alignment_score(
        monthly_aligned=True,
        weekly_aligned=True,
        daily_objective_clear=True,
        htf_location=True,
        liquidity_sweep=True,
        rejection_block=True,
        displacement=True,
        bos_choch=True,
    ) == 100
    assert alignment_score(
        monthly_aligned=True,
        weekly_aligned=True,
        daily_objective_clear=True,
        htf_location=True,
        liquidity_sweep=True,
        rejection_block=False,
        displacement=True,
        bos_choch=False,
    ) == 85
    assert (
        alignment_score(
            monthly_aligned=None,
            weekly_aligned=True,
            daily_objective_clear=True,
            htf_location=True,
            liquidity_sweep=True,
            rejection_block=True,
            displacement=True,
            bos_choch=True,
        )
        is None
    )


def test_unmeasurable_rungs_are_not_aggregated():
    from research.sujan_crt.geometry import UNMEASURABLE_PARENTS

    assert UNMEASURABLE_PARENTS == ("6M", "3M")


def test_sweep_displacement_return_and_stop_are_sp001_sp002():
    levels = [("H4_low", 100.0, 0)]
    sweep_bar = _bar(1, datetime(2024, 3, 13, 0, 0), 101.0, 101.5, 99.0, 100.5)
    sweep = detect_parent_sweep(sweep_bar, levels)
    assert sweep is not None
    assert sweep.direction == "long"
    bars = [
        _bar(0, datetime(2024, 3, 12, 0, 0), 100.0, 101.0, 100.0, 100.5),
        sweep_bar,
        _bar(2, datetime(2024, 3, 14, 0, 0), 100.6, 120.0, 100.4, 102.0),
        _bar(3, datetime(2024, 3, 15, 0, 0), 101.8, 102.0, 100.8, 101.2),
    ]
    disp = detect_displacement(bars, sweep, max_age=3)
    assert disp is not None
    ret = detect_return(bars, disp, max_age=3)
    assert ret is not None
    assert ret.index == 3
    stop = structural_stop(disp)
    assert stop == 99.0
    assert reward_to_risk(ret.close, stop, 120.0) == pytest.approx((120.0 - 101.2) / (101.2 - 99.0))


def _params(**overrides) -> VetoParams:
    base = dict(
        expansion_min_range_ratio=1.2,
        accumulation_max_range_ratio=0.7,
        distribution_min_range_ratio=1.0,
        location_tolerance_atr=2.0,
        rr_floor=5.0,
        max_sweep_age_bars=3,
        max_return_age_bars=3,
    )
    base.update(overrides)
    return VetoParams(**base)


def _bar(i: int, ts: datetime, o: float, h: float, l: float, c: float) -> Bar:
    return Bar(timestamp=ts, open=o, high=h, low=l, close=c, volume=1.0, index=i)


def _daily_series() -> list[Bar]:
    """Jan large bearish, Feb small bullish inside, March small bullish inside.

    Daily bars at 00:00. Last three March bars are the sweep/disp/return long.
    """
    bars: list[Bar] = []
    idx = 0
    # January: large bearish 200 -> 100
    for d in range(1, 32):
        ts = datetime(2024, 1, d, 0, 0)
        o = 200.0 - d
        c = o - 2.0
        bars.append(_bar(idx, ts, o, o + 1.0, c - 1.0, c))
        idx += 1
    # February: small bullish 140-160, inside January
    for d in range(1, 30):
        ts = datetime(2024, 2, d, 0, 0)
        o = 145.0 + 0.1 * d
        c = o + 0.4
        bars.append(_bar(idx, ts, o, c + 0.2, o - 0.2, c))
        idx += 1
    # March 1-12: continue small bullish inside
    for d in range(1, 13):
        ts = datetime(2024, 3, d, 0, 0)
        o = 150.0 + 0.1 * d
        c = o + 0.3
        bars.append(_bar(idx, ts, o, c + 0.2, o - 0.2, c))
        idx += 1
    # March 13: sweep prior parent low, close back inside (long)
    # Prior H4/D1 is Mar 12: low ≈ 150.9. Sweep below that, close above.
    ts = datetime(2024, 3, 13, 0, 0)
    bars.append(_bar(idx, ts, 151.2, 151.4, 149.0, 151.1))
    idx += 1
    # March 14: displacement away from the low. High is far so Daily target
    # (this bar is the last closed D1 at the return) leaves RR >= 5.
    ts = datetime(2024, 3, 14, 0, 0)
    bars.append(_bar(idx, ts, 151.2, 170.0, 151.0, 152.2))
    idx += 1
    # March 15: return into displacement range, close still above stop
    ts = datetime(2024, 3, 15, 0, 0)
    bars.append(_bar(idx, ts, 152.0, 152.3, 151.3, 151.6))
    return bars


def test_closed_parents_drop_in_progress_month():
    bars = _daily_series()
    months = closed_parents(bars, "MN1")
    assert months, "expected at least January closed when February starts"
    last_ts = months[-1].timestamp
    assert last_ts.month < 3 or (last_ts.month == 2)


def test_happy_path_long_is_admitted_with_score_below_90():
    bars = _daily_series()
    atr = [1.0] * len(bars)
    found = detect_veto_chain_entries(bars, _params(), atr)
    assert found, "expected at least one long candidate"
    c = found[-1]
    assert c.direction == "long"
    assert c.romeo_clock == "UNUSED"
    assert c.alignment_score == 85
    assert c.alignment_score < 90
    assert c.rr >= 5.0
    assert c.weekly_state != "EXPANSION" or c.daily_state != "EXPANSION"


def test_score_does_not_admit_an_expansion_chase():
    """Weekly+Daily EXPANSION rejects even if a sweep/disp/return is painted on."""
    bars = _daily_series()
    # Replace February and March with large bullish breakouts so last W and D expand.
    out: list[Bar] = []
    for b in bars:
        if b.timestamp.month >= 2:
            o = 150.0 + b.timestamp.day
            c = o + 20.0
            out.append(
                Bar(
                    timestamp=b.timestamp,
                    open=o,
                    high=c + 5.0,
                    low=o - 1.0,
                    close=c,
                    volume=1.0,
                    index=b.index,
                )
            )
        else:
            out.append(b)
    # keep the last three as a pretty long activation
    out[-3] = _bar(out[-3].index, out[-3].timestamp, 200.0, 201.0, 180.0, 199.0)
    out[-2] = _bar(out[-2].index, out[-2].timestamp, 199.0, 230.0, 198.0, 228.0)
    out[-1] = _bar(out[-1].index, out[-1].timestamp, 220.0, 225.0, 210.0, 215.0)
    atr = [1.0] * len(out)
    found = detect_veto_chain_entries(out, _params(), atr)
    assert found == []


def test_mn_week_disagreement_rejects():
    bars = _daily_series()
    # Make February a descending month so the closed MN parent is short
    # while March weeks/days stay long.
    out = []
    for b in bars:
        if b.timestamp.month == 2:
            o = 160.0 - 0.4 * b.timestamp.day
            c = o - 0.5
            out.append(
                Bar(
                    timestamp=b.timestamp,
                    open=o,
                    high=o + 0.1,
                    low=c - 0.1,
                    close=c,
                    volume=1.0,
                    index=b.index,
                )
            )
        else:
            out.append(b)
    atr = [1.0] * len(out)
    found = detect_veto_chain_entries(out, _params(), atr)
    assert found == []


def test_rr_floor_is_lateness_not_a_score():
    assert reward_to_risk(100.0, 99.0, 106.0) == 6.0
    assert reward_to_risk(100.0, 99.0, 104.0) == 4.0
    bars = _daily_series()
    atr = [1.0] * len(bars)
    tight = detect_veto_chain_entries(bars, _params(rr_floor=50.0), atr)
    assert tight == []


def test_atr_length_mismatch_fails_closed():
    bars = _daily_series()
    with pytest.raises(ValueError, match="aligned"):
        detect_veto_chain_entries(bars, _params(), [1.0])
