"""Floor: SEM-033 Phase-1 manipulation detection is literal, isolated, and founding-free.

Every test here pins one sentence of the Phase-1 specification or one human-bridge
ruling recorded in docs/research/sujan_identity_drift_log.md Record 5.
"""
from __future__ import annotations

import ast
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_SRC = _REPO / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from structure.predicates import swept_high, swept_low  # noqa: E402

from research.sujan_manipulation import (  # noqa: E402
    BULK_CANDLE_SELECTOR,
    Bar,
    ExplicitTimestampSelector,
    ManipulationRunner,
    ManipulationSide,
    ParentBulkCandle,
    ParentRange,
    Phase1State,
    detect_manipulation,
    load_parent_timestamps,
    parent_range,
)
from research.sujan_manipulation.geometry import (  # noqa: E402
    purged_high_closed_inside,
    purged_low_closed_inside,
)
from research.sujan_manipulation.bulk_proxy import (  # noqa: E402
    FROZEN_TOP_N,
    PROXY_ID,
    PROXY_STATUS,
    TopNBodySelector,
    TopNRangeSelector,
    build_selectors,
    overlap_indices,
)
from research.sujan_manipulation.state import PHASE1_PATH, ParentMonitor  # noqa: E402

_PKG = _SRC / "research" / "sujan_manipulation"
_MODULES = [
    "geometry.py", "parent.py", "state.py", "driver.py", "bulk_proxy.py",
    "parquet_check.py", "label_page.py", "__init__.py", "__main__.py",
]
#: Modules that must contain NO magnitude arithmetic at all (the detector proper).
_NO_MAGNITUDE_MODULES = ["geometry.py", "state.py", "parent.py"]

# `research.sujan_crt` is on this list deliberately. Excluding SEM-031 is what makes
# this a NEW object rather than the re-run the identity charter forbids at :382.
FORBIDDEN_RUNTIME_MODULES = (
    "config_layer.crt_engine_v2",
    "config_layer.parent_crt",
    "runtime.backtest_v2",
    "core.engine_runner",
    "research.visual_crt",
    "research.sujan_crt",
    "research.weekly_sweep",
    "research.candle_state",
    "features.feature_pipeline",
    "TradeLib",
    "trade_lib",
)

T0 = datetime(2026, 1, 1, 0, 0, 0)


def _bar(i: int, o: float, h: float, low: float, c: float) -> Bar:
    return Bar(
        timestamp=T0 + timedelta(minutes=15 * i),
        open=o,
        high=h,
        low=low,
        close=c,
        volume=1.0,
        index=i,
    )


def _parent(i: int, h: float, low: float) -> ParentBulkCandle:
    return ParentBulkCandle(
        timestamp=T0 + timedelta(minutes=15 * i),
        high=h,
        low=low,
        index=i,
        source="test fixture (hand-supplied, not selected)",
    )


# A parent whose range is [100, 110], sitting at bar 0.
RNG = ParentRange(high=110.0, low=100.0, parent_index=0, parent_timestamp=T0)


# -------------------------------------------------------------------------
# Isolation
# -------------------------------------------------------------------------

def _runtime_imports(tree: ast.Module) -> set[str]:
    type_only: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        guarded = (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
            isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
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


@pytest.mark.parametrize("rel", _MODULES)
def test_no_forbidden_imports(rel: str):
    tree = ast.parse((_PKG / rel).read_text(encoding="utf-8"))
    imported = _runtime_imports(tree)
    hits = [
        m
        for m in FORBIDDEN_RUNTIME_MODULES
        if any(imp == m or imp.startswith(m + ".") for imp in imported)
    ]
    assert hits == [], f"{rel} imports forbidden modules: {hits}"


# -------------------------------------------------------------------------
# The frozen predicate
# -------------------------------------------------------------------------

def test_predicate_delegates_to_sp001():
    """Over a dense grid, the package predicate == SP-001 AND the inside conjunct."""
    checked = 0
    for high in (105.0, 110.0, 110.5, 115.0):
        for low in (85.0, 99.5, 100.0, 105.0):
            if high <= low:
                continue
            for close in (95.0, 99.9, 100.0, 105.0, 110.0, 112.0):
                bar = _bar(1, 105.0, high, low, close)
                expect_high = swept_high(high, close, RNG.high) and close > RNG.low
                expect_low = swept_low(low, close, RNG.low) and close < RNG.high
                assert purged_high_closed_inside(bar, RNG) is expect_high
                assert purged_low_closed_inside(bar, RNG) is expect_low
                checked += 1
    assert checked > 50


def test_purge_high_closing_below_range_low_is_not_manipulation():
    """Pins the FULLY-INSIDE reading (bridge Record 5).

    This bar purges the high and closes back below the range high, so bare SP-001 would
    call it a sweep - but it closed OUTSIDE the range on the far side, so it did not
    close "back inside the parent range". Under the looser reading this test fails.
    """
    bar = _bar(1, 105.0, 112.0, 98.0, 99.0)
    assert swept_high(bar.high, bar.close, RNG.high) is True  # SP-001 alone says yes
    assert detect_manipulation(bar, RNG) is None  # the literal reading says no


def test_purge_low_closing_above_range_high_is_not_manipulation():
    bar = _bar(1, 105.0, 115.0, 98.0, 112.0)
    assert swept_low(bar.low, bar.close, RNG.low) is True
    assert detect_manipulation(bar, RNG) is None


def test_high_sweep_closing_inside_is_manipulation():
    event = detect_manipulation(_bar(1, 105.0, 112.0, 104.0, 106.0), RNG)
    assert event is not None
    assert event.side is ManipulationSide.HIGH_SWEEP
    assert event.parent_timestamp == T0
    assert event.manipulation_timestamp == T0 + timedelta(minutes=15)


def test_low_sweep_closing_inside_is_manipulation():
    event = detect_manipulation(_bar(1, 105.0, 106.0, 97.0, 103.0), RNG)
    assert event is not None
    assert event.side is ManipulationSide.LOW_SWEEP


def test_both_boundaries_purged_emits_side_both():
    """Outside candle purging both boundaries and closing inside (bridge Record 5)."""
    event = detect_manipulation(_bar(1, 105.0, 114.0, 96.0, 105.0), RNG)
    assert event is not None
    assert event.side is ManipulationSide.BOTH


@pytest.mark.parametrize(
    "o,h,lo,c",
    [
        (105.0, 110.0, 104.0, 106.0),  # touches the high exactly, no purge
        (105.0, 112.0, 104.0, 110.0),  # purges but closes exactly AT the high
        (105.0, 106.0, 100.0, 104.0),  # touches the low exactly, no purge
        (105.0, 106.0, 98.0, 100.0),   # purges but closes exactly AT the low
        (105.0, 108.0, 102.0, 106.0),  # wholly inside, nothing purged
    ],
)
def test_touch_or_close_exactly_at_boundary_is_not_manipulation(o, h, lo, c):
    """SP-001 is strict on both sides; a touch has not demonstrated rejection."""
    assert detect_manipulation(_bar(1, o, h, lo, c), RNG) is None


def test_parent_candle_itself_never_manipulates():
    """"A LATER candle." The parent cannot manipulate its own range."""
    at_parent = _bar(0, 105.0, 112.0, 104.0, 106.0)
    assert detect_manipulation(at_parent, RNG) is None
    monitor = ParentMonitor(_parent(0, 110.0, 100.0))
    monitor.arm()
    assert monitor.step(at_parent) is None


def test_manipulation_need_not_be_the_next_candle():
    """"Manipulation does NOT require the immediately next candle." """
    bars = [
        _bar(0, 100.0, 110.0, 100.0, 105.0),
        _bar(1, 105.0, 108.0, 102.0, 106.0),  # quiet
        _bar(2, 106.0, 109.0, 103.0, 104.0),  # quiet
        _bar(3, 104.0, 113.0, 103.0, 107.0),  # purges the high, closes inside
    ]
    events = ManipulationRunner.from_parents([_parent(0, 110.0, 100.0)]).run(bars)
    assert [e.manipulation_index for e in events] == [3]


# -------------------------------------------------------------------------
# Bridge rulings on lifecycle
# -------------------------------------------------------------------------

def test_alerts_repeat_after_the_first():
    """"The parent range remains the reference object" - alert on every qualifier."""
    bars = [
        _bar(0, 100.0, 110.0, 100.0, 105.0),
        _bar(1, 105.0, 112.0, 104.0, 106.0),  # alert 1
        _bar(2, 106.0, 108.0, 105.0, 107.0),  # quiet
        _bar(3, 107.0, 111.5, 98.0, 104.0),   # alert 2 (BOTH)
        _bar(4, 104.0, 106.0, 97.0, 103.0),   # alert 3 (LOW)
    ]
    events = ManipulationRunner.from_parents([_parent(0, 110.0, 100.0)]).run(bars)
    assert [e.manipulation_index for e in events] == [1, 3, 4]
    assert [e.side for e in events] == [
        ManipulationSide.HIGH_SWEEP,
        ManipulationSide.BOTH,
        ManipulationSide.LOW_SWEEP,
    ]


def test_parents_run_in_parallel_with_no_expiry():
    """Two parents, both armed to the end; neither retires the other."""
    bars = [
        _bar(0, 100.0, 110.0, 100.0, 105.0),
        _bar(1, 105.0, 130.0, 104.0, 120.0),  # parent 2
        _bar(2, 120.0, 132.0, 118.0, 125.0),  # purges P2 high, inside P2; outside P1
        _bar(3, 125.0, 126.0, 95.0, 105.0),   # purges P1 low, closes inside P1
    ]
    parents = [_parent(0, 110.0, 100.0), _parent(1, 130.0, 104.0)]
    events = ManipulationRunner.from_parents(parents).run(bars)
    by_parent = {(e.parent_index, e.manipulation_index) for e in events}
    assert (1, 2) in by_parent, "parent 2 must alert on bar 2"
    assert (0, 3) in by_parent, "parent 0 must still be armed at bar 3 - no expiry"


def test_state_machine_visits_all_five_states_in_order():
    monitor = ParentMonitor(_parent(0, 110.0, 100.0))
    assert monitor.state is Phase1State.IDLE
    monitor.arm()
    monitor.step(_bar(1, 105.0, 112.0, 104.0, 106.0))

    seen = [monitor.trace[0].from_state] + [t.to_state for t in monitor.trace]
    first_visit = []
    for state in seen:
        if state not in first_visit:
            first_visit.append(state)
    assert first_visit == list(PHASE1_PATH)
    # ALERT returns to WAIT_FOR_MANIPULATION, per the bridge ruling.
    assert monitor.state is Phase1State.WAIT_FOR_MANIPULATION


# -------------------------------------------------------------------------
# The founding stays UNRESOLVED
# -------------------------------------------------------------------------

def test_bulk_candle_selector_records_the_approved_proxy():
    """A proxy exists and is recorded, but the CONCEPT is not resolved (UNK-007 open)."""
    assert BULK_CANDLE_SELECTOR == "APPROVED_PROXY_UNVALIDATED"
    assert PROXY_STATUS == "UNVALIDATED"


def test_the_only_selector_is_the_recorded_proxy():
    """Exactly three selectors may exist, and each is accounted for.

    ``ExplicitTimestampSelector`` chooses nothing (built FROM timestamps the caller picked);
    the two proxy selectors are SEM-034, recorded in drift log Record 6. A FOURTH selector
    appearing here without its own freeze is the drift this test exists to catch.
    """
    import research.sujan_manipulation as pkg

    permitted = {ExplicitTimestampSelector, TopNRangeSelector, TopNBodySelector}
    for name in pkg.__all__:
        obj = getattr(pkg, name)
        if obj in permitted or getattr(obj, "_is_protocol", False):
            continue
        if getattr(obj, "select", None) is not None:
            pytest.fail(
                f"{name} exposes an unrecorded bars->parents selector; the only permitted "
                f"selectors are {sorted(c.__name__ for c in permitted)}"
            )


def test_detector_modules_contain_no_magnitude_math():
    """The detector proper stays threshold-free; magnitude lives only in the proxy."""
    for rel in _NO_MAGNITUDE_MODULES:
        imported = _runtime_imports(ast.parse((_PKG / rel).read_text(encoding="utf-8")))
        assert not [
            imp
            for imp in imported
            if imp.endswith("indicators") or imp.endswith("costs") or imp.endswith("candle_math")
        ], f"{rel} reaches a magnitude/cost module; the detector has no thresholds"


def test_no_package_module_imports_a_cost_model():
    """Phase 1 has no economics anywhere, proxy included."""
    for rel in _MODULES:
        imported = _runtime_imports(ast.parse((_PKG / rel).read_text(encoding="utf-8")))
        assert not [
            imp for imp in imported if imp.endswith("costs") or imp.endswith("indicators")
        ], f"{rel} imports a cost/indicator module"


# -------------------------------------------------------------------------
# SEM-034 proxy (APPROVED, UNVALIDATED)
# -------------------------------------------------------------------------

def _ramp(n: int) -> list[Bar]:
    """Bars whose range grows with index, so the expected ranking is known exactly."""
    return [_bar(i, 100.0, 100.0 + i + 1, 100.0 - i, 100.0 + i * 0.5) for i in range(n)]


def test_proxy_returns_exactly_n_in_rank_order():
    bars = _ramp(20)
    ranked = TopNRangeSelector(5).rank(bars)
    assert len(ranked) == 5
    assert [c.rank for c in ranked] == [1, 2, 3, 4, 5]
    assert [c.parent.index for c in ranked] == [19, 18, 17, 16, 15]
    mags = [c.magnitude for c in ranked]
    assert mags == sorted(mags, reverse=True)


def test_proxy_select_is_chronological_and_protocol_conforming():
    bars = _ramp(20)
    chosen = TopNRangeSelector(5).select(bars)
    assert [p.index for p in chosen] == [15, 16, 17, 18, 19]
    assert all(PROXY_ID in p.source and PROXY_STATUS in p.source for p in chosen)


def test_proxy_magnitudes_match_candle_math_exactly():
    """The proxy must not re-derive size arithmetic; it must call the registered functions."""
    from features.candle_math import body_size, candle_range

    bars = _ramp(30)
    for c in TopNRangeSelector(10).rank(bars):
        bar = bars[c.parent.index]
        assert c.magnitude == candle_range(bar.high, bar.low)
    for c in TopNBodySelector(10).rank(bars):
        bar = bars[c.parent.index]
        assert c.magnitude == body_size(bar.open, bar.close)


def test_proxy_source_module_has_no_inline_size_arithmetic():
    """AST guard: `high - low` written inline here would be ungoverned feature math."""
    tree = ast.parse((_PKG / "bulk_proxy.py").read_text(encoding="utf-8"))
    imported = _runtime_imports(tree)
    assert "features.candle_math" in imported
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Sub):
            src = ast.dump(node)
            assert "high" not in src and "low" not in src and "close" not in src, (
                "bulk_proxy.py subtracts OHLC attributes inline; use candle_math instead"
            )


def test_proxy_ties_break_by_ascending_bar_index():
    bars = [_bar(i, 100.0, 110.0, 100.0, 105.0) for i in range(6)]  # all identical ranges
    ranked = TopNRangeSelector(3).rank(bars)
    assert [c.parent.index for c in ranked] == [0, 1, 2]


def test_the_two_rankings_are_separate_and_can_disagree():
    """A wick-dominant candle ranks high on range and low on body, and vice versa."""
    bars = [
        _bar(0, 100.0, 100.5, 99.5, 100.1),          # small
        _bar(1, 100.0, 130.0, 70.0, 100.5),          # huge range, tiny body
        _bar(2, 100.0, 120.0, 99.0, 119.0),          # big body, smaller range
        _bar(3, 100.0, 101.0, 99.0, 100.2),          # small
    ]
    rng, body = build_selectors(1)
    assert rng.rank(bars)[0].parent.index == 1
    assert body.rank(bars)[0].parent.index == 2
    assert overlap_indices(rng.rank(bars), body.rank(bars)) == ()


def test_overlap_is_reported_not_merged():
    bars = _ramp(20)
    rng, body = build_selectors(5)
    a, b = rng.rank(bars), body.rank(bars)
    overlap = overlap_indices(a, b)
    assert set(overlap) <= {c.parent.index for c in a}
    assert set(overlap) <= {c.parent.index for c in b}
    # The lists themselves are untouched by the overlap computation.
    assert len(a) == len(b) == 5


def test_proxy_n_is_required_and_validated():
    with pytest.raises(TypeError):
        TopNRangeSelector()  # type: ignore[call-arg]
    with pytest.raises(ValueError):
        TopNRangeSelector(0)
    with pytest.raises(TypeError):
        TopNRangeSelector(True)  # bool is not an acceptable int


def test_frozen_top_n_is_the_recorded_value():
    assert FROZEN_TOP_N == 50


def test_proxy_refuses_an_empty_corpus():
    with pytest.raises(ValueError):
        TopNRangeSelector(5).rank([])


def test_parquet_check_fails_closed_without_pyarrow(monkeypatch):
    """A skipped check must never be indistinguishable from a passed one."""
    from research.sujan_manipulation import parquet_check as pc

    monkeypatch.setattr(pc, "parquet_available", lambda: False)
    with pytest.raises(pc.ParquetCheckUnavailable, match="pyarrow"):
        pc.cross_check(_ramp(5))


def test_candidate_record_carries_proxy_status_and_no_economics():
    from research.sujan_manipulation.driver import _candidate_record

    rec = _candidate_record(TopNRangeSelector(1).rank(_ramp(5))[0])
    assert rec["proxy_id"] == PROXY_ID
    assert rec["proxy_status"] == "UNVALIDATED"
    assert rec["confirmed"] is False
    assert rec["economic_claims_allowed"] is False
    banned = ("entry", "stop", "target", "outcome", "pnl", "rr", "expectancy")
    assert not [k for k in rec if any(b in k for b in banned)]


def test_label_page_declares_itself_a_curation_tool():
    from research.sujan_manipulation.label_page import FROZEN_QUESTION, render

    bars = _ramp(30)
    rng, body = build_selectors(3)
    page = render(
        bars,
        {rng.ranking: rng.rank(bars), body.ranking: body.rank(bars)},
        corpus_path="fixture.csv",
        overlap=overlap_indices(rng.rank(bars), body.rank(bars)),
    )
    assert "not a measurement instrument" in page
    assert "UNVALIDATED" in page and "UNK-007" in page
    assert FROZEN_QUESTION in page
    assert page.count("<svg") == 6  # one chart per candidate, both lists


def test_explicit_selector_fails_closed_on_unmatched_timestamp():
    bars = [_bar(i, 100.0, 110.0, 100.0, 105.0) for i in range(3)]
    good = ExplicitTimestampSelector([bars[1].timestamp], source="test")
    assert good.select(bars)[0].index == 1

    bad = ExplicitTimestampSelector([datetime(1999, 1, 1)], source="test")
    with pytest.raises(ValueError, match="match no bar"):
        bad.select(bars)


def test_selector_requires_timestamps_and_a_source():
    with pytest.raises(ValueError):
        ExplicitTimestampSelector([], source="test")
    with pytest.raises(ValueError):
        ExplicitTimestampSelector([T0], source="")


def test_parent_range_is_wick_to_wick_and_rejects_degenerate():
    rng = parent_range(_parent(0, 110.0, 100.0))
    assert (rng.high, rng.low) == (110.0, 100.0)
    # Body-only interpretations are REJECTED - they are not constructible from this object.
    assert not hasattr(rng, "open") and not hasattr(rng, "close")
    with pytest.raises(ValueError):
        ParentRange(high=100.0, low=100.0, parent_index=0, parent_timestamp=T0)


def test_load_parent_timestamps_accepts_json_and_csv(tmp_path: Path):
    j = tmp_path / "p.json"
    j.write_text(json.dumps(["2026-01-01 00:00:00", "2026-01-01T00:15:00"]), encoding="utf-8")
    assert load_parent_timestamps(j) == [T0, T0 + timedelta(minutes=15)]

    c = tmp_path / "p.csv"
    c.write_text("timestamp\n2026-01-01 00:00:00\n", encoding="utf-8")
    assert load_parent_timestamps(c) == [T0]

    empty = tmp_path / "e.json"
    empty.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError):
        load_parent_timestamps(empty)


# -------------------------------------------------------------------------
# No lookahead
# -------------------------------------------------------------------------

def test_no_lookahead_prefix_invariance():
    """Alerts on bars[:k] are exactly the full-run alerts with index < k."""
    bars = [
        _bar(0, 100.0, 110.0, 100.0, 105.0),
        _bar(1, 105.0, 112.0, 104.0, 106.0),
        _bar(2, 106.0, 108.0, 105.0, 107.0),
        _bar(3, 107.0, 111.5, 98.0, 104.0),
        _bar(4, 104.0, 106.0, 97.0, 103.0),
        _bar(5, 103.0, 113.0, 102.0, 108.0),
    ]
    parents = [_parent(0, 110.0, 100.0)]
    full = ManipulationRunner.from_parents(parents).run(bars)
    for k in range(1, len(bars) + 1):
        prefix = ManipulationRunner.from_parents(parents).run(bars[:k])
        assert [e.manipulation_index for e in prefix] == [
            e.manipulation_index for e in full if e.manipulation_index < k
        ]


# -------------------------------------------------------------------------
# The firewall
# -------------------------------------------------------------------------

def test_phase1_emits_no_outcome_or_economic_field():
    from research.sujan_manipulation.driver import _alert_record

    event = detect_manipulation(_bar(1, 105.0, 112.0, 104.0, 106.0), RNG)
    record = _alert_record(event)
    assert record["event"] == "SUJAN_MANIPULATION_DETECTED"
    assert record["economic_claims_allowed"] is False
    banned = ("entry", "stop", "target", "rr", "outcome", "pnl", "expectancy", "direction")
    assert not [k for k in record if any(b in k for b in banned)]
