"""Structural kernel parity — SP-001 / SP-002 vs the inline expressions they replace.

SK-1 (CH-structural-kernel, 2026-08-19).

The kernel is a pure-function extraction, so its proof does not need a backtest: the
predicates are total boolean functions of a few floats, and this module compares them
against REFERENCE IMPLEMENTATIONS transcribed verbatim from the pre-migration source.

Two evidence layers:

  1. **Real bars** — every bar of the pinned slice (`data/mt5/XAUUSD_M15.csv`, 2026-03,
     2,020 bars) against a rolling envelope, with a NON-VACUITY guard asserting both the
     high side and the low side actually fired (121 / 128 at time of pinning). A parity test
     over a slice that never exercises the predicate would pass whether or not the kernel is
     correct — the F-079 silent-gap failure mode.

  2. **Adversarial scalars** — the boundary cases real data almost never contains:
     `close == ref` exactly, `high == ref` exactly, zero-range bars. This is where strict-vs
     -inclusive differs, so this is where a regression would actually hide.

Also pins the two things the kernel must NOT become:
  * `swept_*` must stay STRICT — the inclusive form is FM-058's, a different quantity.
  * `directional_impulse` must keep inheriting direction, never re-derive it from the bar.
"""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from structure.predicates import directional_impulse, swept_high, swept_low

_SLICE_MONTH = "2026-03"          # pinned gate slice (SP-GATE-xauusd-1m)
_ENVELOPE = 14                    # rolling founding window, mirrors CRTConfig.atr_period
_CSV = Path(__file__).resolve().parents[1] / "data" / "mt5" / "XAUUSD_M15.csv"


# ── Reference implementations: transcribed VERBATIM from the pre-migration sources ──
# crt_engine_v2.py:882-883 · parent_crt.py:154-155 · weekly_range.py:185-186
# · crt_state_resolver.py:1083-1084 · visual_crt/geometry.py:93,101
def _ref_swept_high(high: float, close: float, h_ref: float) -> bool:
    return high > h_ref and close < h_ref


def _ref_swept_low(low: float, close: float, l_ref: float) -> bool:
    return low < l_ref and close > l_ref


# parent_crt.py:169/171 · visual_crt/geometry.py:162-171 (gates 3+4)
def _ref_impulse(open_: float, close: float, sweep_price: float, is_long: bool) -> bool:
    if is_long:
        return close > open_ and close > sweep_price
    return close < open_ and close < sweep_price


@pytest.fixture(scope="module")
def bars() -> list[dict]:
    if not _CSV.exists():                                    # pragma: no cover
        pytest.skip(f"pinned corpus absent: {_CSV}")
    rows = [
        r for r in csv.DictReader(_CSV.open(encoding="utf-8"))
        if r["timestamp"][:7] == _SLICE_MONTH
    ]
    if not rows:                                             # pragma: no cover
        pytest.skip(f"pinned slice {_SLICE_MONTH} not present in corpus")
    return rows


def test_slice_is_the_pinned_one(bars) -> None:
    """The gate compares against a FROZEN window; a drifting slice is not a gate."""
    assert len(bars) == 2020, (
        f"pinned slice {_SLICE_MONTH} changed size ({len(bars)} != 2020) — the corpus moved. "
        "Re-pin deliberately and re-verify density; do not silently accept a new window."
    )


def test_sweep_parity_over_pinned_slice_with_non_vacuity_guard(bars) -> None:
    """Exhaustive per-bar differential, plus proof the predicate actually fired."""
    H = [float(r["high"]) for r in bars]
    L = [float(r["low"]) for r in bars]
    C = [float(r["close"]) for r in bars]

    hi_fired = lo_fired = compared = 0
    for i in range(_ENVELOPE, len(bars)):
        h_ref = max(H[i - _ENVELOPE:i])
        l_ref = min(L[i - _ENVELOPE:i])

        got_h, exp_h = swept_high(H[i], C[i], h_ref), _ref_swept_high(H[i], C[i], h_ref)
        got_l, exp_l = swept_low(L[i], C[i], l_ref), _ref_swept_low(L[i], C[i], l_ref)
        assert got_h == exp_h, f"swept_high diverged at bar {i} ({bars[i]['timestamp']})"
        assert got_l == exp_l, f"swept_low diverged at bar {i} ({bars[i]['timestamp']})"

        compared += 1
        hi_fired += bool(got_h)
        lo_fired += bool(got_l)

    assert compared >= 2000, f"only {compared} comparisons — slice too small to be decisive"
    # NON-VACUITY: a slice where the predicate never fires proves nothing (F-079).
    assert hi_fired > 0, "VACUOUS: no high-side sweep in the pinned slice"
    assert lo_fired > 0, "VACUOUS: no low-side sweep in the pinned slice"


def test_impulse_parity_over_pinned_slice_with_non_vacuity_guard(bars) -> None:
    O = [float(r["open"]) for r in bars]
    C = [float(r["close"]) for r in bars]
    L = [float(r["low"]) for r in bars]
    H = [float(r["high"]) for r in bars]

    long_fired = short_fired = 0
    for i in range(1, len(bars)):
        # prior bar's extreme stands in for a sweep price — exercises both branches densely
        for is_long, sweep_price in ((True, L[i - 1]), (False, H[i - 1])):
            got = directional_impulse(O[i], C[i], sweep_price, is_long=is_long)
            exp = _ref_impulse(O[i], C[i], sweep_price, is_long)
            assert got == exp, f"directional_impulse diverged at bar {i}, is_long={is_long}"
            if got and is_long:
                long_fired += 1
            elif got:
                short_fired += 1

    assert long_fired > 0 and short_fired > 0, (
        f"VACUOUS: impulse never fired on one side (long={long_fired}, short={short_fired})"
    )


# ── Adversarial scalars: the boundary cases real bars almost never contain ──

@pytest.mark.parametrize(
    "high,close,h_ref,expected",
    [
        (101.0, 99.0, 100.0, True),    # pierced and rejected
        (100.0, 99.0, 100.0, False),   # touched exactly — NOT a pierce (strict)
        (101.0, 100.0, 100.0, False),  # closed exactly AT ref — NOT rejection (strict)
        (101.0, 101.0, 100.0, False),  # closed beyond — a break, not a sweep
        (99.0, 98.0, 100.0, False),    # never reached ref
    ],
)
def test_swept_high_boundary_cases(high, close, h_ref, expected) -> None:
    assert swept_high(high, close, h_ref) is expected


@pytest.mark.parametrize(
    "low,close,l_ref,expected",
    [
        (99.0, 101.0, 100.0, True),
        (100.0, 101.0, 100.0, False),
        (99.0, 100.0, 100.0, False),
        (99.0, 99.0, 100.0, False),
        (101.0, 102.0, 100.0, False),
    ],
)
def test_swept_low_boundary_cases(low, close, l_ref, expected) -> None:
    assert swept_low(low, close, l_ref) is expected


def test_sweep_is_strict_not_inclusive() -> None:
    """Guards the FM-058 boundary: this predicate must NEVER become `close <= ref`.

    The inclusive form is a DIFFERENT registered quantity (swing reference, feature vector).
    Someone "harmonising" the two would silently move the 48-dim vector.
    """
    assert swept_high(101.0, 100.0, 100.0) is False, "went inclusive — that is FM-058, not SP-001"
    assert swept_low(99.0, 100.0, 100.0) is False, "went inclusive — that is FM-058, not SP-001"


def test_impulse_rejects_wrong_direction_f074() -> None:
    """F-074: energy alone is not displacement. The Jul-28 XAUUSD shape must REJECT."""
    # LONG sweep at 4053.91, then a large RED body — the case F-074 outlawed.
    assert directional_impulse(4058.08, 4047.41, 4053.91, is_long=True) is False
    # and the mirror
    assert directional_impulse(4047.41, 4058.08, 4053.91, is_long=False) is False


def test_impulse_requires_clearing_the_swept_level() -> None:
    """Right-coloured body is not enough — it must also clear the swept price."""
    assert directional_impulse(100.0, 102.0, 103.0, is_long=True) is False   # bullish, short of level
    assert directional_impulse(100.0, 104.0, 103.0, is_long=True) is True
    assert directional_impulse(100.0, 98.0, 97.0, is_long=False) is False    # bearish, short of level
    assert directional_impulse(100.0, 96.0, 97.0, is_long=False) is True


def test_impulse_direction_is_inherited_not_derived() -> None:
    """The same bar yields opposite verdicts depending on the INHERITED sweep direction.

    Pins the F-074 contract structurally: if direction were re-derived from the bar, these
    two calls could not disagree, and the unsigned-energy defect would be back.
    """
    o, c = 100.0, 104.0            # one bullish bar
    assert directional_impulse(o, c, 103.0, is_long=True) is True
    assert directional_impulse(o, c, 103.0, is_long=False) is False
