"""Tests for config_layer.rr.rr_optimal_exit.OptimalExitLabeler."""

import pytest

from config_layer.rr.rr_optimal_exit import OptimalExitConfig, OptimalExitLabeler


def _cfg(**overrides) -> OptimalExitConfig:
    base = dict(
        max_forward_bars=10,
        fee_pct_per_side=0.0005,
        slippage_pct_per_side=0.0001,
        spread_pct=0.0002,
        sl_range_buffer_frac=0.1,
        min_net_return_pct=0.0,
        same_bar_policy="sl_first",
    )
    base.update(overrides)
    return OptimalExitConfig(**base)


def _label(labeler, **kw):
    args = dict(
        direction="LONG", entry_price=100.0, entry_idx=0,
        range_high=101.0, range_low=99.0, investment=1000.0,
    )
    args.update(kw)
    return labeler.label(**args)


def test_prod_config_loads():
    assert OptimalExitLabeler()._cfg.same_bar_policy in ("sl_first", "tp_first")


def test_long_approve_tp_is_max_before_sl():
    # entry bar idx 0; highs peak at 103 on bar 3, SL (98.8) hit on bar 5 — later 110 ignored
    highs = [100.5, 101.0, 102.0, 103.0, 102.5, 101.0, 110.0]
    lows  = [ 99.5, 100.2, 100.8, 101.5, 101.0,  98.5, 105.0]
    r = _label(OptimalExitLabeler(_cfg()), highs=highs, lows=lows)
    m = r["metrics"]
    assert r["decision"] == "APPROVE"
    assert m["sl"] == pytest.approx(98.8)
    assert m["tp_max"] == 103.0
    assert m["bars_to_tp"] == 3
    assert m["sl_hit_bar"] == 5
    assert m["rr"] == pytest.approx(3.0 / 1.2)
    assert m["net_profit"] > 0
    assert m["net_loss_at_sl"] < 0


def test_short_approve():
    highs = [100.5, 100.0, 99.0, 99.5, 101.5]
    lows  = [ 99.5,  98.0, 96.0, 97.0, 99.0]
    r = _label(OptimalExitLabeler(_cfg()), direction="SHORT", highs=highs, lows=lows)
    assert r["decision"] == "APPROVE"
    assert r["metrics"]["sl"] == pytest.approx(101.2)
    assert r["metrics"]["tp_max"] == 96.0
    assert r["metrics"]["sl_hit_bar"] == 4


def test_reject_when_move_does_not_cover_round_trip():
    # +0.05% move < ~0.14% round-trip cost
    highs = [100.0, 100.05, 100.03]
    lows  = [ 99.9,  99.95,  99.96]
    r = _label(OptimalExitLabeler(_cfg()), highs=highs, lows=lows)
    assert r["decision"] == "REJECT"
    assert r["metrics"]["net_profit"] <= 0


def test_min_profitable_tp_is_breakeven_exactly():
    lab = OptimalExitLabeler(_cfg())
    for d in ("LONG", "SHORT"):
        tp = lab.min_profitable_tp(d, 100.0)
        assert lab.net_profit(d, 100.0, tp, 1000.0) == pytest.approx(0.0, abs=1e-9)


def test_min_net_return_threshold_enforced():
    highs = [100.0, 101.0]
    lows  = [ 99.9, 100.0]
    lab = OptimalExitLabeler(_cfg(min_net_return_pct=0.02))  # need >2% net
    assert _label(lab, highs=highs, lows=lows)["decision"] == "REJECT"


def test_same_bar_policy():
    # bar 1 makes new high 105 AND hits SL
    highs = [100.0, 105.0]
    lows  = [ 99.9,  98.0]
    pess = _label(OptimalExitLabeler(_cfg()), highs=highs, lows=lows)
    opt = _label(OptimalExitLabeler(_cfg(same_bar_policy="tp_first")), highs=highs, lows=lows)
    assert pess["decision"] == "REJECT" and pess["metrics"]["tp_max"] == 100.0
    assert opt["decision"] == "APPROVE" and opt["metrics"]["tp_max"] == 105.0


def test_window_capped_and_short_data_warns():
    highs = [100.0] + [101.0] * 3 + [120.0]
    lows  = [ 99.9] + [100.5] * 4
    r = _label(OptimalExitLabeler(_cfg(max_forward_bars=3)), highs=highs, lows=lows)
    assert r["metrics"]["tp_max"] == 101.0 and r["metrics"]["bars_scanned"] == 3
    r2 = _label(OptimalExitLabeler(_cfg(max_forward_bars=50)), highs=highs, lows=lows)
    assert r2["warnings"]


@pytest.mark.parametrize("kw", [
    dict(direction="FLAT"),
    dict(range_high=99.0),
    dict(entry_idx=1),
    dict(investment=0.0),
])
def test_input_validation_rejects(kw):
    r = _label(OptimalExitLabeler(_cfg()), highs=[100.0, 101.0], lows=[99.9, 100.0], **kw)
    assert r["decision"] == "REJECT" and r["hard_failures"]


def test_sl_on_wrong_side_rejected():
    # entry below the range → LONG SL above entry
    r = _label(OptimalExitLabeler(_cfg()), entry_price=95.0,
               highs=[95.0, 96.0], lows=[94.0, 95.0])
    assert r["decision"] == "REJECT"


def test_invalid_policy_raises():
    with pytest.raises(ValueError):
        OptimalExitConfig.from_prod_config({
            "max_forward_bars": 1, "fee_pct_per_side": 0, "slippage_pct_per_side": 0,
            "spread_pct": 0, "sl_range_buffer_frac": 0, "min_net_return_pct": 0,
            "same_bar_policy": "random",
        })
