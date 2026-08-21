"""Triangulation floor for the SEM-017 two-target exit kernel.

Three independent checks, because parity against a single reference proves consistency,
not correctness (this program treats existing measurement workflows as unverified):

  1. LEDGER FIXTURE   — a real on-disk TRADE_OPENED row reproduces to full precision.
  2. NAIVE TWIN       — `reference_walk` (two summed legs) agrees with `multi_tp_walk`
                        (one blended position) over randomised bar paths.
  3. FORWARD_WALK     — under a degenerate config the kernel reduces to the existing
                        `forward_walk(intrabar_fixed)`. A CONSISTENCY signal only: a
                        disagreement is a finding about one of the two, not an auto-fail
                        of this kernel.

Plus the invariants that make a label trustworthy: the R ladder, no-lookahead, the
inverted-stop guard, optimistic-dominates-production, and gap fills.
"""

from __future__ import annotations

import random
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from research.oracle.multi_tp_walk import (  # noqa: E402
    OUT_STOPPED,
    OUT_TIMEOUT,
    OUT_TP1_BE_STOP,
    OUT_TP1_TP2,
    RUNNER_ENGINE_PNL,
    TIE_BREAK_OPTIMISTIC,
    TIE_BREAK_PRODUCTION,
    multi_tp_walk,
)
from research.oracle.reference_walker import reference_walk  # noqa: E402


@dataclass
class Bar:
    """Minimal bar. Mirrors what the labeler will feed the kernel."""

    high: float
    low: float
    close: float
    open: float = 0.0
    index: int = 0


def _levels(entry, atr_abs, disp_low, *, tp1_mult, tp2_mult=2.0, sl_buffer=0.2):
    """Reproduce `crt_engine_v2.ExecutionEngine.build_trade` LONG geometry."""
    sl = disp_low - sl_buffer * atr_abs
    risk = abs(entry - sl)
    return sl, entry + tp1_mult * risk, entry + tp2_mult * risk, risk


# ─────────────────────────────────────────────────────────────────────────────
# 1. LEDGER FIXTURE
# ─────────────────────────────────────────────────────────────────────────────
def test_ledger_fixture_levels_reproduce_exactly():
    """XAUUSD CRT-0001 from a real events.jsonl row.

    Recorded: sl 2317.4565714285714, tp1 2319.3401428571433, tp2 2319.7168571428574
    for entry 2318.21 under the `breakout` intent (tp1_mult 1.5).
    If this drifts, the geometry this program claims to reproduce is not the one
    production trades.
    """
    # atr_abs is the engine's full-precision value (14 true ranges summing to 30.34).
    # The CSV column rounds to 8dp, which is what leaves a ~1e-9 residual if used here.
    atr_abs = 30.34 / 14.0
    sl, tp1, tp2, risk = _levels(2318.21, atr_abs, 2317.89, tp1_mult=1.5)
    assert sl == pytest.approx(2317.4565714285714, abs=1e-10)
    assert tp1 == pytest.approx(2319.3401428571433, abs=1e-10)
    assert tp2 == pytest.approx(2319.7168571428574, abs=1e-10)
    assert risk == pytest.approx(0.7534285714285714, abs=1e-10)


# ─────────────────────────────────────────────────────────────────────────────
# 2. THE R LADDER — the discrete outcomes a two-target label can take
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "tp1_mult,expected_tp1_tp2,expected_be_stop",
    [
        (1.0, 1.5, 0.75),    # 0.5*1.0 + 0.5*2.0 ; 0.5*1.0 + 0.5*0.5
        (1.5, 1.75, 1.125),  # breakout intent
        (0.8, 1.4, 0.6),     # pullback intent
        (1.2, 1.6, 0.9),     # liq_sweep intent
    ],
)
def test_r_ladder(tp1_mult, expected_tp1_tp2, expected_be_stop):
    entry, atr, disp_low = 100.0, 1.0, 99.5
    sl, tp1, tp2, risk = _levels(entry, atr, disp_low, tp1_mult=tp1_mult)

    # TP1 on bar 1, TP2 on bar 2. Both lows must stay ABOVE the post-TP1 trail: once TP1
    # is booked the stop sits at entry + 0.5*(tp1-entry), so a pullback to entry would
    # take the runner out rather than letting it reach TP2.
    trail_lvl = entry + 0.5 * (tp1 - entry)
    path = [Bar(high=tp1, low=entry, close=tp1, open=entry, index=1),
            Bar(high=tp2, low=trail_lvl + 1e-6, close=tp2, open=tp1, index=2)]
    out = multi_tp_walk(entry, "long", sl, tp1, tp2, path, entry_index=0)
    assert out.outcome == OUT_TP1_TP2
    assert out.rr_gross == pytest.approx(expected_tp1_tp2, abs=1e-9)

    # TP1 on bar 1, then the trail is taken on bar 2.
    trail = entry + 0.5 * (tp1 - entry)
    path = [Bar(high=tp1, low=entry, close=tp1, open=entry, index=1),
            Bar(high=tp1, low=trail - 1.0, close=trail, open=tp1, index=2)]
    out = multi_tp_walk(entry, "long", sl, tp1, tp2, path, entry_index=0)
    assert out.outcome == OUT_TP1_BE_STOP  # noqa: the trail, not the original stop
    assert out.rr_gross == pytest.approx(expected_be_stop, abs=1e-9)
    assert out.reached_tp1 and out.bars_to_tp1 == 1


def test_clean_stop_is_exactly_minus_one_r():
    entry, sl, tp1, tp2 = 100.0, 99.0, 101.0, 102.0
    path = [Bar(high=100.2, low=98.5, close=99.0, open=100.1, index=1)]
    out = multi_tp_walk(entry, "long", sl, tp1, tp2, path, entry_index=0)
    assert out.outcome == OUT_STOPPED
    assert out.rr_gross == pytest.approx(-1.0, abs=1e-12)
    assert out.exit_kind == "SL_HIT"


def test_runner_stop_pricing_bases_disagree_by_design():
    """The engine credits a stopped runner nothing; the ledger prices it at the trail.

    This is the second declared basis ambiguity (SEM-017). The test asserts the gap
    EXISTS and is the expected size, so it cannot be silently closed in either direction.
    """
    entry, atr, disp_low = 100.0, 1.0, 99.5
    sl, tp1, tp2, _ = _levels(entry, atr, disp_low, tp1_mult=1.0)
    trail = entry + 0.5 * (tp1 - entry)
    path = [Bar(high=tp1, low=entry, close=tp1, open=entry, index=1),
            Bar(high=tp1, low=trail - 1.0, close=trail, open=tp1, index=2)]

    ledger = multi_tp_walk(entry, "long", sl, tp1, tp2, path, entry_index=0)
    engine = multi_tp_walk(entry, "long", sl, tp1, tp2, path,
                           runner_stop_pricing=RUNNER_ENGINE_PNL, entry_index=0)
    assert ledger.rr_gross == pytest.approx(0.75, abs=1e-9)
    assert engine.rr_gross == pytest.approx(0.50, abs=1e-9)


# ─────────────────────────────────────────────────────────────────────────────
# 3. NAIVE TWIN — randomised triangulation
# ─────────────────────────────────────────────────────────────────────────────
def _random_path(rng, entry, n=40):
    bars, px = [], entry
    for i in range(n):
        drift = rng.gauss(0, 0.45)
        nxt = px + drift
        hi = max(px, nxt) + abs(rng.gauss(0, 0.30))
        lo = min(px, nxt) - abs(rng.gauss(0, 0.30))
        bars.append(Bar(high=hi, low=lo, close=nxt, open=px, index=i + 1))
        px = nxt
    return bars


@pytest.mark.parametrize("tie_break", [TIE_BREAK_PRODUCTION, TIE_BREAK_OPTIMISTIC])
@pytest.mark.parametrize("direction", ["long", "short"])
def test_kernel_agrees_with_naive_twin(tie_break, direction):
    """5,000 randomised paths per (tie_break, direction). Any divergence fails loudly."""
    rng = random.Random(20260820)
    entry = 100.0
    checked = 0
    for _ in range(5000):
        risk = rng.uniform(0.2, 2.0)
        tp1_mult = rng.choice([0.8, 1.0, 1.2, 1.5])
        if direction == "long":
            sl = entry - risk
            tp1, tp2 = entry + tp1_mult * risk, entry + 2.0 * risk
        else:
            sl = entry + risk
            tp1, tp2 = entry - tp1_mult * risk, entry - 2.0 * risk
        path = _random_path(rng, entry)
        kw = dict(tie_break=tie_break, entry_index=0, max_forward=40)
        fast = multi_tp_walk(entry, direction, sl, tp1, tp2, path, **kw)
        slow = reference_walk(entry, direction, sl, tp1, tp2, path, **kw)
        assert fast.outcome == slow.outcome, (fast, slow)
        assert fast.rr_gross == pytest.approx(slow.rr_gross, abs=1e-9), (fast, slow)
        assert fast.duration_candles == slow.duration_candles
        assert fast.reached_tp1 == slow.reached_tp1
        assert fast.bars_to_tp1 == slow.bars_to_tp1
        assert fast.mfe == pytest.approx(slow.mfe, abs=1e-9)
        assert fast.mae == pytest.approx(slow.mae, abs=1e-9)
        checked += 1
    assert checked == 5000


def test_naive_twin_agrees_under_adverse_fill():
    """Gap/slippage fills must triangulate too — that is where R stops being a constant."""
    from research.measurement.forward_walk import AdverseFill

    rng = random.Random(4242)
    entry, adverse = 100.0, AdverseFill(stop_slippage=0.09, model_gaps=True)
    saw_gap = False
    for _ in range(3000):
        risk = rng.uniform(0.3, 1.5)
        sl, tp1, tp2 = entry - risk, entry + risk, entry + 2 * risk
        path = _random_path(rng, entry)
        fast = multi_tp_walk(entry, "long", sl, tp1, tp2, path,
                             adverse_fill=adverse, entry_index=0)
        slow = reference_walk(entry, "long", sl, tp1, tp2, path,
                              adverse_fill=adverse, entry_index=0)
        assert fast.outcome == slow.outcome
        assert fast.rr_gross == pytest.approx(slow.rr_gross, abs=1e-9)
        assert fast.gapped_stop == slow.gapped_stop
        saw_gap = saw_gap or fast.gapped_stop
    # Non-vacuity: if no path ever gapped, this test proved nothing about the gap branch.
    assert saw_gap, "no gap-through occurred; the adverse-fill branch was never exercised"


# ─────────────────────────────────────────────────────────────────────────────
# 4. FORWARD_WALK REDUCTION — consistency signal, not proof
# ─────────────────────────────────────────────────────────────────────────────
def test_degenerate_config_reduces_to_forward_walk():
    """partial_fraction=0 makes TP1 a non-event, collapsing to a single fixed-stop walk.

    Agreement here is reassuring but is NOT this kernel's correctness proof: it would be
    circular to certify a new kernel against a workflow this program treats as unverified.
    A disagreement is a finding about one of the two implementations and must be resolved.
    """
    from research.contracts import Signal
    from research.measurement.forward_walk import forward_walk

    rng = random.Random(99)
    entry = 100.0
    outcomes = {"TP_HIT": 0, "SL_HIT": 0, "TIMEOUT": 0}
    for _ in range(3000):
        sl_mult, tp_mult, atr = 1.0, 2.0, rng.uniform(0.2, 1.2)
        risk = sl_mult * atr
        sl, tp2 = entry - risk, entry + tp_mult * atr
        path = _random_path(rng, entry)

        mine = multi_tp_walk(entry, "long", sl, tp2, tp2, path,
                             partial_fraction=0.0, tie_break=TIE_BREAK_PRODUCTION,
                             entry_index=0, max_forward=40)
        sig = Signal(instrument="TEST", timestamp=None, entry_index=0, direction="long",
                     entry=entry, sl_atr_mult=sl_mult, tp_atr_mult=tp_mult, atr=atr)
        theirs = forward_walk(sig, path, max_forward=40, exit_model="intrabar_fixed")

        assert mine.rr_gross == pytest.approx(theirs.rr_achieved, abs=1e-4), (mine, theirs)
        assert mine.duration_candles == theirs.duration_candles
        outcomes[theirs.outcome] += 1
    # Non-vacuity: all three exit kinds must have been exercised, or agreement is trivial.
    assert all(v > 0 for v in outcomes.values()), outcomes


# ─────────────────────────────────────────────────────────────────────────────
# 5. INVARIANTS
# ─────────────────────────────────────────────────────────────────────────────
def test_no_lookahead_guard_fires():
    entry, sl, tp1, tp2 = 100.0, 99.0, 101.0, 102.0
    path = [Bar(high=101.5, low=99.9, close=101.0, open=100.0, index=5)]
    with pytest.raises(ValueError, match="lookahead"):
        multi_tp_walk(entry, "long", sl, tp1, tp2, path, entry_index=5)
    with pytest.raises(ValueError, match="lookahead"):
        reference_walk(entry, "long", sl, tp1, tp2, path, entry_index=5)


def test_inverted_stop_is_rejected_not_walked():
    """The engine returns None on an inverted stop; a silent walk would fabricate a label."""
    path = [Bar(high=101.0, low=99.0, close=100.0, open=100.0, index=1)]
    with pytest.raises(ValueError, match="stop"):
        multi_tp_walk(100.0, "long", 100.5, 101.0, 102.0, path, entry_index=0)
    with pytest.raises(ValueError, match="stop"):
        multi_tp_walk(100.0, "short", 99.5, 99.0, 98.0, path, entry_index=0)


def test_optimistic_weakly_dominates_production():
    """The two conventions differ only by who wins a spanning bar, so optimistic R can
    never be WORSE than production R. Predicting which bars span is unreliable (after
    TP1 the binding stop is the trail, not the original SL), so assert the invariant that
    actually holds rather than a hand-rolled span predicate.

    Also reports how often they diverge — the SEM-017 epistemic block asks exactly this.
    """
    rng = random.Random(7)
    entry = 100.0
    compared = differed = 0
    for _ in range(4000):
        risk = rng.uniform(0.3, 1.2)
        sl, tp1, tp2 = entry - risk, entry + risk, entry + 2 * risk
        path = _random_path(rng, entry)
        a = multi_tp_walk(entry, "long", sl, tp1, tp2, path,
                          tie_break=TIE_BREAK_PRODUCTION, entry_index=0)
        b = multi_tp_walk(entry, "long", sl, tp1, tp2, path,
                          tie_break=TIE_BREAK_OPTIMISTIC, entry_index=0)
        assert b.rr_gross >= a.rr_gross - 1e-9, (a, b)
        compared += 1
        differed += (a.outcome != b.outcome)
    assert compared == 4000
    # Non-vacuity in BOTH directions: the arms must actually diverge somewhere (else the
    # band is inert and the test proves nothing), but not everywhere (else one arm is broken).
    assert 0 < differed < compared, f"divergence {differed}/{compared} is degenerate"


def test_timeout_marks_to_close():
    entry, sl, tp1, tp2 = 100.0, 99.0, 105.0, 110.0
    path = [Bar(high=100.3, low=99.7, close=100.2, open=100.0, index=i + 1) for i in range(40)]
    out = multi_tp_walk(entry, "long", sl, tp1, tp2, path, entry_index=0)
    assert out.outcome == OUT_TIMEOUT
    assert out.rr_gross == pytest.approx((100.2 - 100.0) / 1.0, abs=1e-9)
    assert out.duration_candles == 40


def test_short_side_mirrors_long():
    """A mirrored path must give a mirrored R, or the sign convention is broken."""
    entry, risk = 100.0, 1.0
    long_path = [Bar(high=102.5, low=99.8, close=102.0, open=100.0, index=1)]
    short_path = [Bar(high=100.2, low=97.5, close=98.0, open=100.0, index=1)]
    lo = multi_tp_walk(entry, "long", entry - risk, entry + risk, entry + 2 * risk,
                       long_path, entry_index=0)
    sh = multi_tp_walk(entry, "short", entry + risk, entry - risk, entry - 2 * risk,
                       short_path, entry_index=0)
    assert lo.outcome == sh.outcome
    assert lo.rr_gross == pytest.approx(sh.rr_gross, abs=1e-9)
