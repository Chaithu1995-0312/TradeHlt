"""F-115: BaseStrategy sizing must route through core.position_sizing for any
instrument with a declared ``instrument_specs`` entry (XAUUSD today). Instruments
with no spec keep the legacy FX pip path byte-for-byte.
"""
import math

import pytest

import strategies.base_strategy as bs
from strategies.base_strategy import BaseStrategy


class _Probe(BaseStrategy):
    @property
    def strategy_id(self) -> str:
        return "SX"

    def compute(self, features, candle):  # pragma: no cover - not exercised
        return self._no_trade()


def _legacy_lot(pip_value: float, sl_pips: float) -> float:
    lot = bs._MAX_RISK_PER_TRADE / (sl_pips * pip_value * bs._USD_TO_INR_RATE)
    return min(math.floor(lot * 100.0 + 1e-9) / 100.0, 100.0)   # F-115: FLOOR, not round


def test_xauusd_s6_reachable_bar_sizes_above_zero():
    s = _Probe("XAUUSD", "M15")
    dist = 5.54 * 0.5  # ATR * sl_atr_mult on the S6-reachable bar
    lot = s._get_lot_size(s._sl_pips(2000.0, 2000.0 - dist))
    assert lot == pytest.approx(1.07)


def test_xauusd_sl_inr_is_within_risk_cap():
    s = _Probe("XAUUSD", "M15")
    dist = 2.77
    lot = s._get_lot_size(s._sl_pips(2000.0, 2000.0 - dist))
    sl_inr = s._calc_sl_inr(2000.0, 2000.0 - dist, lot)
    assert 0.0 < sl_inr <= bs._MAX_RISK_PER_TRADE
    assert sl_inr == pytest.approx(dist * 100.0 * lot * bs._USD_TO_INR_RATE, abs=0.01)


def test_xauusd_tp_inr_uses_contract_size_not_pips():
    s = _Probe("XAUUSD", "M15")
    tp_inr = s._calc_tp_inr(2000.0, 2004.0, 1.0)
    assert tp_inr == pytest.approx(4.0 * 100.0 * 1.0 * bs._USD_TO_INR_RATE, abs=0.01)


def test_xauusd_risk_below_min_lot_returns_zero():
    s = _Probe("XAUUSD", "M15")
    # huge stop: the budget cannot buy lot_min (0.01) -> 0.0 (callers turn it into NO_TRADE)
    assert s._get_lot_size(s._sl_pips(2000.0, 1000.0)) == 0.0


@pytest.mark.parametrize("pair", ["EURUSD", "GBPUSD", "USDJPY"])
def test_fx_pairs_are_byte_identical_to_legacy_formula(pair):
    s = _Probe(pair, "H1")
    assert s._spec is None
    sl_pips = 25.0
    assert s._get_lot_size(sl_pips) == _legacy_lot(s._pip_value, sl_pips)
    entry, sl = (1.1000, 1.0975) if pair != "USDJPY" else (150.00, 149.75)
    lot = s._get_lot_size(s._sl_pips(entry, sl))
    expect = round(
        abs(entry - sl) * s._pips_per_unit() * lot * s._pip_value * bs._USD_TO_INR_RATE, 2
    )
    assert s._calc_sl_inr(entry, sl, lot) == expect


def test_undeclared_instrument_stays_on_legacy_path():
    s = _Probe("NZDCAD", "H1")  # in neither pip_value_per_lot nor instrument_specs
    assert s._spec is None
    assert s._get_lot_size(20.0) == _legacy_lot(s._pip_value, 20.0)


def test_zero_or_negative_stop_returns_zero():
    assert _Probe("XAUUSD", "M15")._get_lot_size(0.0) == 0.0
    assert _Probe("EURUSD", "H1")._get_lot_size(-1.0) == 0.0


# ── F-115 (a): lot rounding never exceeds the INR risk cap (FLOOR, not round-to-nearest) ──

@pytest.mark.parametrize("sl_pips", [7.3, 11.9, 17.77, 23.1, 41.3, 63.9, 88.2, 120.4])
def test_legacy_lot_never_exceeds_risk_cap(sl_pips):
    s = _Probe("EURUSD", "H1")
    lot = s._get_lot_size(sl_pips)
    assert lot * sl_pips * s._pip_value * bs._USD_TO_INR_RATE <= bs._MAX_RISK_PER_TRADE + 1e-9


# ── F-115 (b): price-distance ATR is atr_absolute (FM-074) = relative atr * close ──

def test_atr_price_is_relative_atr_times_close():
    assert BaseStrategy._atr_price({"atr": 0.0015}, 2000.0) == pytest.approx(3.0)
    assert BaseStrategy._atr_price({}, 2000.0) == 0.0


def test_s6_gold_stop_is_dollars_not_fractions_of_a_cent():
    from strategies.s06_scalping import S06Scalping

    s = S06Scalping(pair="XAUUSD", timeframe="M15")
    price = 2400.0
    atr_rel = 0.002  # close-relative canonical ATR ~ $4.8
    feats = {"atr": atr_rel, "macd_hist_z": 3.0, "momentum_score": 0.9, "body_ratio": 0.8,
             "volume_ratio": 1.5, "hour_of_day": 10}
    candle = {"open": price - 1, "high": price + 1, "low": price - 2, "close": price,
              "volume": 100, "timestamp": 0}
    r = s.compute(feats, candle)
    if r.signal == "NO_TRADE":  # session/other gates are not under test; skip rather than fake
        pytest.skip("S6 gates not satisfied by synthetic bar")
    sl_mult = float(s._cfg_s6["sl_atr_mult"])
    assert abs(r.entry - r.sl) == pytest.approx(atr_rel * price * sl_mult)
