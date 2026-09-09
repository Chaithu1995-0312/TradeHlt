"""SEM-021 Displacement-Origin Invalidation — the floor.

Five things are protected here, in descending order of how badly a failure would mislead:

  CLOSE-TRIGGERED  a wick through the origin that closes back INSIDE must not fire. This is
                   the property the whole rule's measurability rests on: F-087 put the
                   same-bar ambiguity band of every extreme-reading arm at 0.261R, 12-15x the
                   0.0198-0.0212R spread it would be used to measure, versus ~0.0005R for
                   close/elapsed-time arms. An extreme-triggered variant is not a slightly
                   different rule, it is an unrankable one.
  DEFAULT-INERT    with the flag off the rule must be a structural no-op, not a rule that
                   happens not to fire on the fixtures. A silently-inert arm is
                   indistinguishable from one measured and found ineffective (F-083, F-085).
  ORIGIN SURVIVAL  the origin is captured on the Trade, because reset_to_range moves
                   state.displacement_candle into pending_displacement_candle while the trade
                   may still be open.
  PRECEDENCE       the two config arms are NOT equivalent and must be separable.
  FAIL-CLOSED      an unrecognised precedence raises rather than defaulting, so a typo cannot
                   produce a run mislabelled as the other arm.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from config_layer.crt_engine_v2 import (  # noqa: E402
    Candle,
    Direction,
    ExecutionEngine,
    Trade,
)
from config_layer.state_identity import CRTConfig  # noqa: E402


# ── helpers ──────────────────────────────────────────────────────────────────────────
def _candle(o: float, h: float, l: float, c: float, idx: int = 1) -> Candle:
    return Candle(timestamp=None, open=o, high=h, low=l, close=c, volume=1000.0, index=idx)


def _trade(direction: Direction, origin: float | None, status: str = "OPEN") -> Trade:
    is_long = direction == Direction.LONG
    entry = 100.0
    t = Trade(
        id="T-1",
        direction=direction,
        entry_price=entry,
        sl_price=99.0 if is_long else 101.0,
        tp1_price=102.0 if is_long else 98.0,
        tp2_price=104.0 if is_long else 96.0,
        displacement_origin=origin,
    )
    t.status = status
    return t


class _Runner:
    """Minimal host exposing the predicate under test, without booting a full engine."""

    def __init__(self, cfg: CRTConfig):
        self.config = cfg

    from config_layer.crt_engine_v2 import CRTEngine as _E  # noqa: N801
    _displacement_origin_kill = _E._displacement_origin_kill


def _cfg(**kw) -> CRTConfig:
    return CRTConfig(**kw)


# ── CLOSE-TRIGGERED: the load-bearing property ───────────────────────────────────────
def test_long_kill_fires_when_close_is_below_the_displacement_origin():
    r = _Runner(_cfg(displacement_origin_kill_enabled=True))
    t = _trade(Direction.LONG, origin=99.5)
    assert r._displacement_origin_kill(t, _candle(100.0, 100.2, 98.0, 99.0)) is True


def test_short_kill_fires_when_close_is_above_the_displacement_origin():
    r = _Runner(_cfg(displacement_origin_kill_enabled=True))
    t = _trade(Direction.SHORT, origin=100.5)
    assert r._displacement_origin_kill(t, _candle(100.0, 102.0, 99.8, 101.0)) is True


@pytest.mark.parametrize(
    "direction,origin,bar",
    [
        # long: low pierces 99.5 but the bar closes back above it
        (Direction.LONG, 99.5, (100.0, 100.4, 98.2, 100.1)),
        # short: high pierces 100.5 but the bar closes back below it
        (Direction.SHORT, 100.5, (100.0, 101.9, 99.6, 99.9)),
    ],
)
def test_a_wick_through_the_origin_that_closes_back_inside_does_NOT_fire(direction, origin, bar):
    """THE test. If this ever passes on a wick, the rule has become extreme-triggered and
    inherits F-087's 0.261R ambiguity band -- 12-15x the effect it would be used to measure --
    i.e. it stops being rankable from M15 OHLC at all."""
    r = _Runner(_cfg(displacement_origin_kill_enabled=True))
    t = _trade(direction, origin=origin)
    assert r._displacement_origin_kill(t, _candle(*bar)) is False


def test_close_exactly_at_the_origin_does_not_fire():
    """Strict inequality: `at` the origin is not `beyond` it."""
    r = _Runner(_cfg(displacement_origin_kill_enabled=True))
    assert r._displacement_origin_kill(
        _trade(Direction.LONG, origin=99.5), _candle(100.0, 100.2, 99.0, 99.5)
    ) is False


# ── DEFAULT-INERT ────────────────────────────────────────────────────────────────────
def test_disabled_by_default_and_inert_even_on_a_violating_bar():
    assert CRTConfig().displacement_origin_kill_enabled is False
    r = _Runner(_cfg())  # defaults
    t = _trade(Direction.LONG, origin=99.5)
    assert r._displacement_origin_kill(t, _candle(100.0, 100.2, 98.0, 99.0)) is False


def test_missing_origin_is_fail_quiet_not_fail_open():
    """A trade with no displacement origin must behave exactly as before this rule existed."""
    r = _Runner(_cfg(displacement_origin_kill_enabled=True))
    t = _trade(Direction.LONG, origin=None)
    assert r._displacement_origin_kill(t, _candle(100.0, 100.2, 90.0, 91.0)) is False


@pytest.mark.parametrize("status", ["PENDING", "TP2", "STOPPED", "STOPPED_STRUCTURAL"])
def test_kill_does_not_reanimate_a_non_live_trade(status):
    r = _Runner(_cfg(displacement_origin_kill_enabled=True))
    t = _trade(Direction.LONG, origin=99.5, status=status)
    assert r._displacement_origin_kill(t, _candle(100.0, 100.2, 98.0, 99.0)) is False


# ── ORIGIN SURVIVAL ──────────────────────────────────────────────────────────────────
def test_displacement_origin_is_a_trade_field_not_an_engine_state_read():
    """Captured on the Trade at build time. reset_to_range moves
    state.displacement_candle into pending_displacement_candle while the trade may still be
    open, so an engine-state read at kill time would silently no-op after any reset."""
    import dataclasses
    names = {f.name for f in dataclasses.fields(Trade)}
    assert "displacement_origin" in names
    t = _trade(Direction.LONG, origin=99.5)
    assert t.displacement_origin == 99.5


# ── close_structural booking ─────────────────────────────────────────────────────────
def test_structural_close_books_at_the_bar_close_not_at_the_origin():
    """Booking at the origin would assume a fill at a level the bar may never have offered
    after the trigger became knowable -- lookahead wearing a structural argument."""
    ex = ExecutionEngine(CRTConfig())
    t = _trade(Direction.LONG, origin=99.5)
    assert ex.close_structural(t, 99.0) == "STOPPED_STRUCTURAL"
    assert t.pnl == pytest.approx(99.0 - 100.0)   # close, not origin (which would be -0.5)
    assert t.status == "STOPPED_STRUCTURAL"


def test_structural_close_after_tp1_keeps_the_partial_and_only_kills_the_runner():
    """This is what 'preempts the SEM-017 trail' means concretely: the TP1 fill genuinely
    happened and is kept; only the runner that the half-way trail would have carried is cut."""
    ex = ExecutionEngine(CRTConfig())
    t = _trade(Direction.LONG, origin=99.5, status="TP1")
    t.partial_pnl = 1.0
    assert ex.close_structural(t, 99.0) == "STOPPED_STRUCTURAL"
    assert t.pnl == pytest.approx(1.0 + 0.5 * (99.0 - 100.0))


def test_structural_close_is_a_noop_on_an_already_closed_trade():
    ex = ExecutionEngine(CRTConfig())
    t = _trade(Direction.LONG, origin=99.5, status="STOPPED")
    assert ex.close_structural(t, 99.0) == "UNCHANGED"


# ── PRECEDENCE + FAIL-CLOSED ─────────────────────────────────────────────────────────
def test_both_precedence_arms_are_constructible_and_distinct():
    a = _cfg(displacement_origin_kill_enabled=True, displacement_origin_kill_precedence="after_resting_fills")
    b = _cfg(displacement_origin_kill_enabled=True, displacement_origin_kill_precedence="absolute")
    assert a.displacement_origin_kill_precedence != b.displacement_origin_kill_precedence


def test_default_precedence_is_after_resting_fills():
    assert CRTConfig().displacement_origin_kill_precedence == "after_resting_fills"


def test_unknown_precedence_fails_closed():
    """A typo must NOT silently fall back. The two arms are not equivalent, so a run
    mislabelled as the other arm is worse than a crash -- it looks like evidence."""
    with pytest.raises(ValueError, match="displacement_origin_kill_precedence"):
        _cfg(displacement_origin_kill_precedence="fires_first")


def test_enabled_flag_rejects_non_bool():
    with pytest.raises(ValueError, match="displacement_origin_kill_enabled"):
        _cfg(displacement_origin_kill_enabled="true")


# ── shadow-config containment ────────────────────────────────────────────────────────
def test_the_arm_is_reachable_only_from_a_non_promoted_shadow_config():
    import json
    active = Path("configs/production/ACTIVE_VERSION").read_text(encoding="utf-8").strip()
    assert active != "v2_dispkill_shadow_2026_08", "the shadow config must never be ACTIVE"
    act = json.loads(Path(f"configs/production/{active}.json").read_text(encoding="utf-8"))
    assert act["crt_engine"].get("displacement_origin_kill_enabled", False) is False, (
        "SEM-021 must stay OFF on the active config; enabling it is a separate gated decision "
        "requiring freeze-pin re-certification"
    )
    shadow = json.loads(
        Path("configs/production/v2_dispkill_shadow_2026_08.json").read_text(encoding="utf-8")
    )
    assert shadow["crt_engine"]["displacement_origin_kill_enabled"] is True
