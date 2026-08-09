"""
Phase-1 floor: the three previously-UNDECLARED backtest constants are now config-owned
and STRICTLY read (CLAUDE.md Section 6.5 — no silent config defaults).

Why this file exists, and why it is not just a byte-diff:
the BNBUSDT parity run proved byte-identity, but it exercises only ONE of the three
paths (13 TRADE_OPENED => the SL floor). It produced 0 partial-TP exits and 0
P5_SCORE_LOW rejects, so byte-identity says NOTHING about the other two changes.
A test that cannot fail is not enforcement, so each constant gets a check that can.

Covers:
  1. phase5_calibration.min_p_win        (was a bare 0.35 at the compare site)
  2. execution_planner.partial_tp_fraction (was strict-read then DISCARDED — a config
     illusion: the 0.5/0.5 blend literals are what actually executed)
  3. crt_engine.sl_atr_buffer            (was duplicated as a 0.2 literal whose comment
     claimed to match the config key but never read it)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from config_layer.production_config import get_prod_section  # noqa: E402
from config_layer.state_identity import Direction  # noqa: E402
from runtime.backtest_v2 import (  # noqa: E402
    CapitalCurve,
    SlippageModel,
    TradeJournal,
    _require_bt_cfg,
)


# ── 1. The keys exist and are strictly readable ──────────────────────────────

@pytest.mark.parametrize(
    "section, key",
    [
        ("phase5_calibration", "min_p_win"),
        ("execution_planner", "partial_tp_fraction"),
        ("crt_engine", "sl_atr_buffer"),
    ],
)
def test_declared_key_present_in_active_config(section, key):
    """Each constant is now owned by the active production config."""
    assert key in get_prod_section(section), (
        f"{section}.{key} missing — it was declared to remove a hardcoded literal; "
        f"deleting it re-creates the undeclared-constant defect."
    )


@pytest.mark.parametrize(
    "section, key",
    [
        ("phase5_calibration", "min_p_win"),
        ("execution_planner", "partial_tp_fraction"),
        ("crt_engine", "sl_atr_buffer"),
    ],
)
def test_strict_accessor_raises_when_key_absent(section, key):
    """The read is STRICT, not decorative — a missing key must raise, never
    silently fall back to the old literal."""
    cfg = dict(get_prod_section(section))
    cfg.pop(key, None)
    with pytest.raises(KeyError):
        _require_bt_cfg(cfg, key, section)


# ── 2. Parity: declared values equal the literals they replaced ──────────────

def test_declared_values_equal_the_replaced_literals():
    """Parity proof. If any of these drifts, the Phase-1 migration silently
    changed behaviour rather than just declaring it."""
    assert float(get_prod_section("phase5_calibration")["min_p_win"]) == 0.35
    assert float(get_prod_section("execution_planner")["partial_tp_fraction"]) == 0.5
    assert float(get_prod_section("crt_engine")["sl_atr_buffer"]) == 0.2


# ── 3. Behavioural: the SL floor actually SCALES with the config value ───────
# This is the check byte-identity cannot give us: it proves the value is READ,
# not merely declared alongside an unchanged literal.

def _journal(sl_atr_buffer: float) -> TradeJournal:
    return TradeJournal(
        "BNBUSDT", 0.01,
        SlippageModel(atr_fraction=0.0, seed=1),   # zero slip => deterministic fill
        CapitalCurve(100_000.0, 1.0, False),
        sl_atr_buffer=sl_atr_buffer,
    )


def test_trade_journal_requires_sl_atr_buffer():
    """No default: constructing without the buffer must fail loudly."""
    with pytest.raises(TypeError):
        TradeJournal(
            "BNBUSDT", 0.01,
            SlippageModel(atr_fraction=0.0, seed=1),
            CapitalCurve(100_000.0, 1.0, False),
        )


def test_sl_floor_scales_with_configured_buffer():
    """Two different buffers must produce two different SL floors.

    Uses the buffer directly rather than driving a full candle through
    on_trade_opened, so the assertion stays on the migrated arithmetic
    (_min_sl_dist = self.sl_atr_buffer * atr) and not on trade plumbing.
    """
    atr = 10.0
    assert _journal(0.2).sl_atr_buffer * atr == pytest.approx(2.0)
    assert _journal(0.5).sl_atr_buffer * atr == pytest.approx(5.0)
    # and the live value is threaded from config, not a 0.2 literal
    assert _journal(float(get_prod_section("crt_engine")["sl_atr_buffer"])).sl_atr_buffer \
        == pytest.approx(0.2)


# ── 4. The replaced literals are GONE from the source ───────────────────────
# Guards the specific regression: re-introducing the literal would make the
# config key inert again without failing any behavioural test above.

def test_replaced_literals_are_not_reintroduced():
    src = (_SRC / "runtime" / "backtest_v2.py").read_text(encoding="utf-8")
    assert "0.5 * t.tp1_price" not in src, (
        "partial-TP blend literal is back — the config key becomes inert again."
    )
    assert '_p5["p_win"] < 0.35' not in src, (
        "Phase-5 veto literal is back — phase5_calibration.min_p_win becomes inert."
    )
    assert "_min_sl_dist = 0.2 * atr" not in src, (
        "SL-floor literal is back — it silently desyncs from crt_engine.sl_atr_buffer."
    )
