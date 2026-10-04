"""ComponentCostModel floor — SEM-015 BROKER_EXECUTION_COST_DECOMPOSITION.

Guards the three properties that make this model *honest* rather than merely
decomposed:

  1. leg asymmetry   — stop slippage is charged on a stop exit and NOT on a
                       take-profit; a limit order does not slip favourably.
  2. never-fabricate — an unmeasured component raises instead of becoming 0.0.
                       This is the failure mode that manufactures apparent edge.
  3. flat-model parity — `CostModel` and `DEFAULT_COST_MODEL` are untouched, so
                       every pre-existing research result stays reproducible.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from research.costs import (  # noqa: E402
    DEFAULT_COST_MODEL,
    DEFAULT_ROUND_TRIP_BPS,
    ENTRY_SLIP_PROXY_FROM_STOP,
    MEASURED,
    ComponentCostModel,
    CostModel,
    UnmeasuredCostError,
)

MANIFEST = (
    _ROOT
    / "results/research/xauusd_mt5_cost_calibration"
    / "xauusd_mt5_cost_calibration_manifest_20260806T134255Z.json"
)


def _model(**over) -> ComponentCostModel:
    base = dict(
        half_spread=0.045, commission=0.04, entry_slippage=0.09, stop_slippage=0.09,
        swap_long_per_night=-0.5601, swap_short_per_night=0.38338,
        instrument="XAUUSD", source="unit-fixture", status=MEASURED,
    )
    base.update(over)
    return ComponentCostModel(**base)


# ── 1. leg asymmetry ─────────────────────────────────────────────────────────

def test_stop_slippage_charged_only_on_stop_exit():
    m = _model()
    sl = m.cost_price(exit_kind="SL_HIT")
    tp = m.cost_price(exit_kind="TP_HIT")
    assert sl - tp == pytest.approx(m.stop_slippage), (
        "a stop exit must cost exactly one stop_slippage more than a limit exit"
    )
    assert tp < sl, "a take-profit must never cost more than a stop exit"


def test_take_profit_never_slips_favourably():
    """A resting limit order does not fill better than its level."""
    generous = _model(stop_slippage=5.0)
    assert generous.cost_price(exit_kind="TP_HIT") == pytest.approx(
        _model(stop_slippage=0.0).cost_price(exit_kind="TP_HIT")
    ), "stop_slippage must not leak into the take-profit leg in either direction"


def test_leg_decomposition_is_not_twice_c_per_side():
    """Regression on the ZONE-X convention mismatch.

    The source calibration's `c_per_side` bundles stop slippage into every side
    because ZONE-X places stops on BOTH legs. This architecture enters on a market
    order, so doubling c_per_side would double-charge stop slippage on a TP exit.
    """
    m = _model()
    c_per_side = m.half_spread + m.commission + m.stop_slippage
    assert m.cost_price(exit_kind="TP_HIT") < 2 * c_per_side


def test_cost_r_is_ratio_to_risk_distance():
    """Tight stops must still be penalised proportionally (CostModel semantics)."""
    m = _model()
    wide = m.cost_r(3300.0, 10.0, exit_kind="SL_HIT")
    tight = m.cost_r(3300.0, 5.0, exit_kind="SL_HIT")
    assert tight == pytest.approx(2 * wide)


def test_net_rr_subtracts_cost_r():
    m = _model()
    assert m.net_rr(2.0, 3300.0, 7.342, exit_kind="TP_HIT") == pytest.approx(
        2.0 - m.cost_r(3300.0, 7.342, exit_kind="TP_HIT")
    )


# ── 2. never fabricate ───────────────────────────────────────────────────────

def test_partial_manifest_raises_rather_than_defaulting_to_zero():
    bad = {"statuses": {"spread": MEASURED, "commission": "INSUFFICIENT_DATA",
                        "slippage_stop": MEASURED}}
    with pytest.raises(UnmeasuredCostError, match="commission"):
        ComponentCostModel.from_manifest(bad, instrument="XAUUSD", source="s")


def test_unmeasured_model_refuses_to_charge():
    with pytest.raises(UnmeasuredCostError, match="only MEASURED"):
        _model(status="INSUFFICIENT_DATA").cost_price(exit_kind="SL_HIT")


def test_unmeasured_swap_refuses_overnight_carry():
    """Carry must never be silently free."""
    m = _model(swap_long_per_night=None, swap_short_per_night=None)
    assert m.cost_price(exit_kind="SL_HIT", nights_held=0) > 0, "intraday still prices"
    with pytest.raises(UnmeasuredCostError, match="UNMEASURED"):
        m.cost_price(exit_kind="SL_HIT", direction="long", nights_held=1)


def test_swap_debit_charged_credit_not_netted_off():
    """A positive swap is a credit; crediting it would smuggle in the F-034 payoff."""
    m = _model()
    flat = m.cost_price(exit_kind="SL_HIT", nights_held=0)
    long_2n = m.cost_price(exit_kind="SL_HIT", direction="long", nights_held=2)
    short_2n = m.cost_price(exit_kind="SL_HIT", direction="short", nights_held=2)
    assert long_2n == pytest.approx(flat + 2 * abs(m.swap_long_per_night)), "debit charged"
    assert short_2n == pytest.approx(flat), "credit must NOT reduce a directional trade's cost"


def test_source_and_negative_components_rejected():
    with pytest.raises(ValueError, match="source"):
        _model(source="")
    with pytest.raises(ValueError, match="half_spread"):
        _model(half_spread=-0.01)


# ── 3. the real measured manifest ────────────────────────────────────────────

@pytest.mark.skipif(not MANIFEST.is_file(), reason="calibration manifest not present")
def test_from_real_manifest_uses_conservative_entry_proxy():
    m = ComponentCostModel.from_manifest(
        json.loads(MANIFEST.read_text(encoding="utf-8")),
        instrument="XAUUSD", source=str(MANIFEST),
    )
    assert m.status == MEASURED
    # MARKET slippage is INSUFFICIENT_DATA (n=0) in this run -> proxy, never zero.
    assert m.entry_slippage_basis == ENTRY_SLIP_PROXY_FROM_STOP
    assert m.entry_slippage == pytest.approx(m.stop_slippage)
    assert m.entry_slippage > 0.0, "entry slippage must never silently be zero"
    # swap is read from its sidecar, not defaulted
    assert m.swap_long_per_night is not None and m.swap_long_per_night < 0
    assert m.provenance()["ontology_id"] == "SEM-015"


@pytest.mark.skipif(not MANIFEST.is_file(), reason="calibration manifest not present")
def test_flat_model_overcharges_xauusd_by_an_order_of_magnitude():
    """The measured claim behind SEM-015, pinned so a silent revert is caught."""
    m = ComponentCostModel.from_manifest(
        json.loads(MANIFEST.read_text(encoding="utf-8")),
        instrument="XAUUSD", source=str(MANIFEST),
    )
    entry, risk_distance = 3300.0, 7.342           # XAUUSD median ATR, sl_atr_mult=1.0
    flat = DEFAULT_COST_MODEL.cost_r(entry, risk_distance)
    measured = m.cost_r(entry, risk_distance, exit_kind="SL_HIT")
    assert flat / measured > 10.0, (
        f"flat 12bps charges {flat:.4f}R vs measured {measured:.4f}R; the "
        "order-of-magnitude over-charge is the finding this model corrects"
    )


# ── 4. the flat model is untouched ───────────────────────────────────────────

def test_flat_cost_model_unchanged():
    assert DEFAULT_ROUND_TRIP_BPS == 12.0
    assert DEFAULT_COST_MODEL.round_trip_bps == 12.0
    # exact historical arithmetic: cost_price / risk_distance
    assert CostModel(12.0).cost_r(1000.0, 10.0) == pytest.approx((12.0 / 10_000.0) * 1000.0 / 10.0)
