"""Floor for the Visual CRT trade object (SEM-012), Lane 1.

Two jobs:

1. **Isolation** — `src/research/visual_crt/` must never reach the live CRT spine at
   RUNTIME. Enforced with an AST import-walk, not a substring scan: `"crt_engine_v2" not
   in text` would be defeated by `from config_layer import crt_engine_v2`, and this repo
   already has a CT-009 check with exactly that hole. A `TYPE_CHECKING`-guarded import of
   `Candle` IS permitted — that is the sanctioned `research.weekly_sweep` precedent.
2. **Geometry** — pool visibility, sweep direction convention, and every F-074 directional
   gate, on synthetic candles. No CSV dependency, no corpus, no outcomes.

Lane 1 deliberately measures NOTHING. There is no ledger, no expectancy, no win count here.
"""

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

from config_layer.crt_engine_v2 import Candle                      # noqa: E402
from research.visual_crt.geometry import (                         # noqa: E402
    PoolSweepEvent,
    detect_directional_displacement,
    detect_pool_sweep,
)
from research.visual_crt.pools import LiquidityPool, visible_pools  # noqa: E402

_PKG = _SRC / "research" / "visual_crt"
_SPEC = _REPO / "docs" / "research" / "visual_crt_trade_object.md"

#: Runtime imports of these modules would couple the research lane to the live spine.
FORBIDDEN_RUNTIME_MODULES = (
    "config_layer.crt_engine_v2",
    "config_layer.m15_structural_range",
    "config_layer.parent_crt",
    "runtime.backtest_v2",
)
#: Names that must never be pulled in at runtime, whatever module they come from.
FORBIDDEN_RUNTIME_NAMES = (
    "M15StructuralLiquidityRange",
    "RangeDetector",
    "detect_sweep",
    "detect_m15_structural_range",
)

BASE = datetime(2024, 1, 1, 0, 0)


def _c(idx, o, h, l, c, v=10.0):
    return Candle(
        timestamp=BASE + timedelta(minutes=15 * idx),
        open=o, high=h, low=l, close=c, volume=v, index=idx,
    )


# ── 1. isolation ────────────────────────────────────────────────────────────


def _runtime_imports(tree: ast.Module):
    """Every Import/ImportFrom NOT guarded by `if TYPE_CHECKING:`."""
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
            for child in node.body:
                for sub in ast.walk(child):
                    if isinstance(sub, (ast.Import, ast.ImportFrom)):
                        type_only.add(id(sub))
    return [
        n for n in ast.walk(tree)
        if isinstance(n, (ast.Import, ast.ImportFrom)) and id(n) not in type_only
    ]


def _modules_and_names(node) -> tuple[list[str], list[str]]:
    if isinstance(node, ast.Import):
        return [a.name for a in node.names], [(a.asname or a.name) for a in node.names]
    mod = node.module or ""
    names = [a.name for a in node.names]
    # `from config_layer import crt_engine_v2` → module is the dotted join.
    return [mod] + [f"{mod}.{n}" for n in names if mod], names


def _violations(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    bad: list[str] = []
    for node in _runtime_imports(tree):
        mods, names = _modules_and_names(node)
        for m in mods:
            if any(m == f or m.startswith(f + ".") for f in FORBIDDEN_RUNTIME_MODULES):
                bad.append(f"{path.name}:{node.lineno} runtime import of {m}")
        for n in names:
            if n in FORBIDDEN_RUNTIME_NAMES:
                bad.append(f"{path.name}:{node.lineno} runtime import of name {n}")
    return bad


def test_package_has_no_runtime_spine_import():
    files = sorted(_PKG.glob("*.py"))
    assert files, "visual_crt package has no modules"
    found: list[str] = []
    for f in files:
        found.extend(_violations(f))
    assert not found, "research lane must not import the live spine at runtime: " + "; ".join(found)


@pytest.mark.parametrize(
    "snippet",
    [
        "from config_layer.crt_engine_v2 import RangeDetector",
        "from config_layer import crt_engine_v2",          # the substring-check-evading form
        "import config_layer.crt_engine_v2 as eng",
        "from config_layer.m15_structural_range import M15StructuralLiquidityRange",
    ],
)
def test_isolation_check_actually_fails_on_a_violation(tmp_path, snippet):
    """A test that cannot fail is not enforcement (E-001). Prove each form is caught."""
    victim = tmp_path / "violating.py"
    victim.write_text(f"from __future__ import annotations\n{snippet}\n", encoding="utf-8")
    assert _violations(victim), f"isolation check failed to catch: {snippet}"


def test_type_checking_import_of_candle_is_permitted():
    """The sanctioned weekly_sweep precedent must not be flagged."""
    ok = (
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    from config_layer.crt_engine_v2 import Candle\n"
    )
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "fine.py"
        p.write_text(ok, encoding="utf-8")
        assert _violations(p) == []


# ── 2. pools ────────────────────────────────────────────────────────────────


def test_visible_pools_returns_both_edges_of_prior_h4_and_prior_day():
    h4 = [_c(10, 100, 105, 95, 102)]
    d1 = [_c(5, 100, 110, 90, 101)]
    pools = visible_pools(h4, d1)
    by_kind = {p.kind: p for p in pools}
    assert set(by_kind) == {"PRIOR_H4_HIGH", "PRIOR_H4_LOW", "PDH", "PDL"}
    assert by_kind["PRIOR_H4_HIGH"].price == 105
    assert by_kind["PRIOR_H4_LOW"].price == 95
    assert by_kind["PDH"].price == 110
    assert by_kind["PDL"].price == 90


def test_visible_pools_is_empty_without_a_closed_parent():
    assert visible_pools([], []) == ()


def test_pool_rejects_a_side_that_contradicts_its_kind():
    with pytest.raises(ValueError):
        LiquidityPool(kind="PDH", side="LOW", price=1.0, formed_at_index=0, source_rule="D1")


# ── 3. sweep geometry ───────────────────────────────────────────────────────


def _pool(side="HIGH", price=105.0, idx=10):
    kind = "PRIOR_H4_HIGH" if side == "HIGH" else "PRIOR_H4_LOW"
    return LiquidityPool(kind=kind, side=side, price=price, formed_at_index=idx, source_rule="H4")


def test_high_sweep_is_short_and_low_sweep_is_long():
    high_pool = _pool("HIGH", 105.0)
    ev = detect_pool_sweep(_c(20, 103, 107, 102, 104), [high_pool])
    assert ev is not None and ev.direction == "short" and ev.sweep_price == 107

    low_pool = _pool("LOW", 95.0)
    ev = detect_pool_sweep(_c(20, 97, 98, 93, 96), [low_pool])
    assert ev is not None and ev.direction == "long" and ev.sweep_price == 93


def test_no_sweep_when_close_stays_outside():
    """Pierce without closing back inside is a break, not a sweep."""
    assert detect_pool_sweep(_c(20, 103, 107, 102, 106), [_pool("HIGH", 105.0)]) is None


def test_no_sweep_when_pool_is_not_yet_visible():
    """A level formed at or after this bar could not have been drawn in advance."""
    assert detect_pool_sweep(_c(20, 103, 107, 102, 104), [_pool("HIGH", 105.0, idx=20)]) is None
    assert detect_pool_sweep(_c(20, 103, 107, 102, 104), [_pool("HIGH", 105.0, idx=19)]) is not None


def test_deepest_pierced_pool_wins():
    shallow = _pool("HIGH", 105.0)
    deep = LiquidityPool(kind="PDH", side="HIGH", price=103.0, formed_at_index=5, source_rule="D1")
    ev = detect_pool_sweep(_c(20, 102, 107, 101, 102.5), [shallow, deep])
    assert ev is not None and ev.pool.kind == "PDH"


# ── 4. F-074 directional displacement ───────────────────────────────────────

_GATES = dict(
    body_ratio_min=0.65,
    atr_min_displacement=1.2,
    atr_multiplier_min=1.0,
    max_sweep_age_candles=20,
)


def _long_sweep():
    return detect_pool_sweep(_c(20, 97, 98, 93, 96), [_pool("LOW", 95.0)])


def test_bullish_impulse_after_a_low_sweep_is_a_displacement():
    sweep = _long_sweep()
    bar = _c(21, 96, 100.2, 95.8, 100)          # body 4.0, range 4.4, br 0.909
    ev = detect_directional_displacement(bar, sweep, atr_abs=2.0, **_GATES)
    assert ev is not None and ev.direction == "long" and ev.bars_since_sweep == 1


def test_bearish_dump_after_a_long_sweep_is_rejected():
    """F-074's headline case: unsigned energy is no longer a legal SWEEP→DISPLACEMENT."""
    sweep = _long_sweep()
    bar = _c(21, 100, 100.2, 95.8, 96)          # big body, wrong direction
    assert detect_directional_displacement(bar, sweep, atr_abs=2.0, **_GATES) is None


def test_displacement_must_close_beyond_the_swept_level():
    sweep = _long_sweep()                        # swept low = 93
    bar = _c(21, 88, 92.9, 87.8, 92.8)           # bullish and large, but closes below 93
    assert detect_directional_displacement(bar, sweep, atr_abs=2.0, **_GATES) is None


def test_weak_body_is_rejected():
    sweep = _long_sweep()
    bar = _c(21, 96, 104, 95.5, 99.5)            # body 3.5 / range 8.5 = 0.41 < 0.65
    assert detect_directional_displacement(bar, sweep, atr_abs=2.0, **_GATES) is None


def test_small_bar_is_rejected():
    sweep = _long_sweep()
    bar = _c(21, 96, 97.1, 95.9, 97)             # range 1.2 < 1.0 * atr 2.0
    assert detect_directional_displacement(bar, sweep, atr_abs=2.0, **_GATES) is None


def test_stale_sweep_is_rejected():
    sweep = _long_sweep()
    bar = _c(20 + 21, 96, 100.2, 95.8, 100)      # age 21 > 20
    assert detect_directional_displacement(bar, sweep, atr_abs=2.0, **_GATES) is None
    fresh = _c(20 + 20, 96, 100.2, 95.8, 100)    # age 20 == limit, allowed
    assert detect_directional_displacement(fresh, sweep, atr_abs=2.0, **_GATES) is not None


def test_non_positive_atr_yields_no_displacement():
    assert detect_directional_displacement(
        _c(21, 96, 100.2, 95.8, 100), _long_sweep(), atr_abs=0.0, **_GATES
    ) is None


def test_bar_before_the_sweep_raises():
    with pytest.raises(ValueError):
        detect_directional_displacement(
            _c(19, 96, 100.2, 95.8, 100), _long_sweep(), atr_abs=2.0, **_GATES
        )


# ── 5. spec ─────────────────────────────────────────────────────────────────


def test_spec_exists_and_declares_every_mechanical_field():
    assert _SPEC.is_file(), f"missing spec {_SPEC}"
    text = _SPEC.read_text(encoding="utf-8")
    for required in (
        "SEM-012",
        "P-CRT-LIQ-01",
        "F-074",
        "intrabar_fixed",
        "Pool",
        "Sweep",
        "Displacement",
        "Entry",
        "Stop",
        "Target",
        "Cost",
    ):
        assert required in text, f"spec does not declare {required!r}"


def test_spec_refuses_economic_authority():
    text = _SPEC.read_text(encoding="utf-8").lower()
    assert "grants no" in text and "authority" in text


# ── 6. Arm B retest predicate (SEM-012 v2) ──────────────────────────────────

from research.visual_crt.geometry import DisplacementEvent          # noqa: E402
from research.visual_crt.retest import detect_pool_retest           # noqa: E402

_RETEST = dict(
    retest_depth_max=0.15,
    retest_atr_depth_fraction=0.3,
    retest_min_depth_atr_fraction=0.1,
)


def _disp(direction="long", pool_price=95.0, sweep_price=93.0, disp_close=100.0, idx=21):
    pool = _pool("LOW" if direction == "long" else "HIGH", pool_price)
    sweep = PoolSweepEvent(pool=pool, direction=direction, sweep_price=sweep_price, bar_index=20)
    return DisplacementEvent(
        sweep=sweep, direction=direction, bar_index=idx, body_ratio=0.9,
        move=4.0, close=disp_close, bars_since_sweep=1,
    )


def test_retest_fires_inside_the_adaptive_band():
    d = _disp()
    # atr 2.0 -> min_depth 0.2, atr_ceiling 0.6, impulse |100-93|=7 -> static 1.05 -> ceiling 1.05
    bar = _c(25, 96.5, 96.6, 95.8, 95.9)     # depth = 95.9 - 95.0 = 0.9, inside [0.2, 1.05]
    ev = detect_pool_retest(bar, d, 2.0, **_RETEST)
    assert ev is not None and ev.direction == "long"
    assert ev.impulse == 7.0 and ev.bars_since_displacement == 4


def test_retest_rejected_when_still_too_far_from_the_pool():
    bar = _c(25, 99, 99.2, 98.8, 99.0)       # depth 4.0 > ceiling 1.05
    assert detect_pool_retest(bar, _disp(), 2.0, **_RETEST) is None


def test_retest_rejected_when_price_closed_back_through_the_pool():
    """A cross-back is a failed setup, not a very deep retest."""
    bar = _c(25, 95, 95.1, 94.0, 94.2)       # depth negative
    assert detect_pool_retest(bar, _disp(), 2.0, **_RETEST) is None


def test_retest_rejected_on_the_displacement_bar_itself():
    d = _disp(idx=21)
    assert detect_pool_retest(_c(21, 96, 100.2, 95.8, 95.9), d, 2.0, **_RETEST) is None


def test_retest_short_side_is_mirrored():
    d = _disp(direction="short", pool_price=105.0, sweep_price=107.0, disp_close=100.0)
    bar = _c(25, 103.5, 104.2, 103.4, 104.1)  # depth = 105 - 104.1 = 0.9
    ev = detect_pool_retest(bar, d, 2.0, **_RETEST)
    assert ev is not None and ev.direction == "short"


def test_retest_bar_before_displacement_raises():
    with pytest.raises(ValueError):
        detect_pool_retest(_c(19, 96, 97, 95, 96), _disp(idx=21), 2.0, **_RETEST)


# ── 7. duplicate rule (contract-owned) ──────────────────────────────────────

from research.visual_crt.driver import Bar, run_arm, _pool_key      # noqa: E402


def _series() -> list:
    """Two calendar days of flat M15 bars, then a repeated sweep of the same PDL."""
    bars = []
    t0 = datetime(2024, 5, 22, 0, 0)
    for i in range(96 * 3):
        bars.append(Bar(t0 + timedelta(minutes=15 * i), 100.0, 100.4, 99.6, 100.0, 10.0, i))
    return bars


def _spike(bars, idx, low, close, open_=100.0, high=None):
    bars[idx] = Bar(bars[idx].timestamp, open_, high if high is not None else max(open_, close) + 0.1,
                    low, close, 10.0, idx)
    return bars


def test_pool_key_rearms_when_a_newer_parent_replaces_the_level():
    from research.visual_crt.pools import LiquidityPool
    a = LiquidityPool(kind="PDL", side="LOW", price=99.6, formed_at_index=95, source_rule="D1")
    b = LiquidityPool(kind="PDL", side="LOW", price=99.6, formed_at_index=191, source_rule="D1")
    assert _pool_key(a) != _pool_key(b), "a newer closed parent must re-arm the level"


def test_duplicate_rule_suppresses_a_second_fire_on_the_same_pool():
    """Same pool swept + displaced twice -> at most one ledger row from that pool identity."""
    bars = _series()
    for sweep_i, disp_i in ((200, 201), (210, 211)):
        bars = _spike(bars, sweep_i, low=99.0, close=100.0)          # pierce PDL, close back in
        bars = _spike(bars, disp_i, low=99.9, close=103.0, open_=100.0, high=103.1)  # bullish
    rows = run_arm(bars, "A", instrument="TEST", corpus_path="synthetic", corpus_sha256="0" * 8)
    # Non-vacuity first: with zero rows the uniqueness assert below would pass trivially,
    # which is precisely the "test that cannot fail" class E-001 exists to catch.
    assert rows, "synthetic series produced no entries — the duplicate assert would be vacuous"
    keys = [(r.pool_kind, r.pool_price, r.direction) for r in rows]
    assert len(keys) == len(set(keys)), f"duplicate fire on one pool identity: {keys}"


def test_run_arm_rejects_an_unknown_arm():
    with pytest.raises(ValueError):
        run_arm(_series(), "C", instrument="TEST", corpus_path="x", corpus_sha256="y")
