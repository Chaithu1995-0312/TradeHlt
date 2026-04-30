"""
test_portfolio_allocator.py
============================
Phase C: Portfolio Capital Allocator tests.

Covers:
  ExposureTracker:
    - add/remove positions
    - total_risk accumulates correctly
    - exposure_by_symbol aggregates per symbol
    - duplicate trade_id overwrites

  CorrelationEngine:
    - same symbol → 1.0
    - same crypto group → 0.8
    - same FX group → 0.8
    - cross asset class → 0.2
    - FX major vs USD short → 0.4
    - empty/None → 0.0

  CapitalPolicy:
    - base risk returned on clean portfolio
    - exposure reduction applied
    - correlation reduction applied
    - confidence boost applied
    - hard cap at max_per_trade
    - portfolio_at_capacity gate

  PortfolioAllocator:
    - ALLOCATE action returned with risk for clean portfolio
    - REJECT when portfolio at max risk
    - risk trimmed to fit within cap
    - max_corr influences sizing
    - open/close position updates tracker
"""
import pytest

from src.portfolio.exposure_tracker import ExposureTracker
from src.portfolio.correlation_engine import CorrelationEngine
from src.portfolio.capital_policy import CapitalPolicy
from src.portfolio.allocator import PortfolioAllocator


# ── ExposureTracker ─────────────────────────────────────────────────────────

def test_tracker_add_position():
    t = ExposureTracker()
    t.add_position({"trade_id": "t1", "symbol": "BTCUSDT", "risk": 0.005})
    assert t.total_risk() == pytest.approx(0.005)


def test_tracker_multiple_positions():
    t = ExposureTracker()
    t.add_position({"trade_id": "t1", "symbol": "BTC", "risk": 0.005})
    t.add_position({"trade_id": "t2", "symbol": "ETH", "risk": 0.003})
    assert t.total_risk() == pytest.approx(0.008)


def test_tracker_remove_position():
    t = ExposureTracker()
    t.add_position({"trade_id": "t1", "symbol": "BTC", "risk": 0.005})
    t.add_position({"trade_id": "t2", "symbol": "ETH", "risk": 0.003})
    removed = t.remove_position("t1")
    assert removed["trade_id"] == "t1"
    assert t.total_risk() == pytest.approx(0.003)


def test_tracker_remove_nonexistent_returns_none():
    t = ExposureTracker()
    result = t.remove_position("nonexistent")
    assert result is None


def test_tracker_exposure_by_symbol():
    t = ExposureTracker()
    t.add_position({"trade_id": "t1", "symbol": "BTC", "risk": 0.005})
    t.add_position({"trade_id": "t2", "symbol": "BTC", "risk": 0.003})
    t.add_position({"trade_id": "t3", "symbol": "ETH", "risk": 0.002})
    by_sym = t.exposure_by_symbol()
    assert by_sym["BTC"] == pytest.approx(0.008)
    assert by_sym["ETH"] == pytest.approx(0.002)


def test_tracker_position_count():
    t = ExposureTracker()
    assert t.position_count() == 0
    t.add_position({"trade_id": "t1", "symbol": "BTC", "risk": 0.005})
    assert t.position_count() == 1


def test_tracker_duplicate_trade_id_overwrites():
    t = ExposureTracker()
    t.add_position({"trade_id": "t1", "symbol": "BTC", "risk": 0.005})
    t.add_position({"trade_id": "t1", "symbol": "BTC", "risk": 0.009})
    assert t.total_risk() == pytest.approx(0.009)
    assert t.position_count() == 1


def test_tracker_clear():
    t = ExposureTracker()
    t.add_position({"trade_id": "t1", "symbol": "BTC", "risk": 0.005})
    t.clear()
    assert t.total_risk() == 0.0
    assert t.position_count() == 0


def test_tracker_raises_on_missing_trade_id():
    t = ExposureTracker()
    with pytest.raises(ValueError, match="trade_id"):
        t.add_position({"symbol": "BTC", "risk": 0.005})


# ── CorrelationEngine ────────────────────────────────────────────────────────

def test_corr_same_symbol():
    e = CorrelationEngine()
    assert e.correlation("BTCUSDT", "BTCUSDT") == pytest.approx(1.0)


def test_corr_same_crypto_group():
    e = CorrelationEngine()
    assert e.correlation("BTCUSDT", "ETHUSDT") == pytest.approx(0.8)


def test_corr_same_fx_majors():
    e = CorrelationEngine()
    assert e.correlation("EURUSD", "GBPUSD") == pytest.approx(0.8)


def test_corr_cross_asset_class():
    e = CorrelationEngine()
    assert e.correlation("BTCUSDT", "EURUSD") == pytest.approx(0.2)


def test_corr_fx_major_vs_usd_short():
    e = CorrelationEngine()
    assert e.correlation("EURUSD", "USDJPY") == pytest.approx(0.4)


def test_corr_empty_symbol_returns_zero():
    e = CorrelationEngine()
    assert e.correlation("", "BTCUSDT") == pytest.approx(0.0)
    assert e.correlation("BTCUSDT", "") == pytest.approx(0.0)


def test_corr_max_with_existing():
    e = CorrelationEngine()
    # BTC vs [ETH, EURUSD] → max(0.8, 0.2) = 0.8
    result = e.max_correlation_with_existing("BTCUSDT", ["ETHUSDT", "EURUSD"])
    assert result == pytest.approx(0.8)


def test_corr_max_with_empty_existing():
    e = CorrelationEngine()
    result = e.max_correlation_with_existing("BTCUSDT", [])
    assert result == pytest.approx(0.0)


# ── CapitalPolicy ─────────────────────────────────────────────────────────────

def test_policy_base_risk_clean_portfolio():
    p = CapitalPolicy(base_risk=0.005)
    risk = p.compute_risk(
        signal={"confidence": 0.5},
        current_exposure=0.0,
        max_correlation=0.0,
    )
    assert risk == pytest.approx(0.005)


def test_policy_high_exposure_reduces_risk():
    p = CapitalPolicy(base_risk=0.005, high_exposure_threshold=0.015, high_exposure_factor=0.5)
    risk = p.compute_risk(
        signal={"confidence": 0.5},
        current_exposure=0.016,  # > 0.015
        max_correlation=0.0,
    )
    assert risk == pytest.approx(0.0025)  # 0.005 * 0.5


def test_policy_high_correlation_reduces_risk():
    p = CapitalPolicy(base_risk=0.005, high_correlation_threshold=0.7, high_correlation_factor=0.6)
    risk = p.compute_risk(
        signal={"confidence": 0.5},
        current_exposure=0.0,
        max_correlation=0.8,  # > 0.7
    )
    assert risk == pytest.approx(0.003)  # 0.005 * 0.6


def test_policy_confidence_boost():
    p = CapitalPolicy(base_risk=0.005, confidence_boost_threshold=0.75, confidence_boost_factor=1.3)
    risk = p.compute_risk(
        signal={"confidence": 0.8},  # > 0.75
        current_exposure=0.0,
        max_correlation=0.0,
    )
    assert risk == pytest.approx(0.0065)  # 0.005 * 1.3


def test_policy_hard_cap_applied():
    p = CapitalPolicy(base_risk=0.005, max_per_trade=0.004, confidence_boost_factor=1.3, confidence_boost_threshold=0.75)
    risk = p.compute_risk(
        signal={"confidence": 0.9},
        current_exposure=0.0,
        max_correlation=0.0,
    )
    # 0.005 * 1.3 = 0.0065 → capped at 0.004
    assert risk == pytest.approx(0.004)


def test_policy_portfolio_at_capacity():
    p = CapitalPolicy(max_portfolio_risk=0.02)
    assert p.portfolio_at_capacity(0.02) is True
    assert p.portfolio_at_capacity(0.019) is False
    assert p.portfolio_at_capacity(0.025) is True


# ── PortfolioAllocator ────────────────────────────────────────────────────────

def test_allocator_allocate_clean_portfolio():
    alloc = PortfolioAllocator()
    result = alloc.allocate({"symbol": "BTCUSDT", "confidence": 0.6})
    assert result["action"] == "ALLOCATE"
    assert result["risk"] > 0


def test_allocator_reject_at_max_risk():
    policy = CapitalPolicy(max_portfolio_risk=0.02)
    tracker = ExposureTracker()
    tracker.add_position({"trade_id": "t1", "symbol": "BTC", "risk": 0.02})

    alloc = PortfolioAllocator(exposure_tracker=tracker, capital_policy=policy)
    result = alloc.allocate({"symbol": "ETHUSDT", "confidence": 0.7})
    assert result["action"] == "REJECT"
    assert result["risk"] == 0.0


def test_allocator_risk_trimmed_to_fit_cap():
    """When adding full base_risk would breach cap, risk is trimmed."""
    policy = CapitalPolicy(max_portfolio_risk=0.02, base_risk=0.005)
    tracker = ExposureTracker()
    tracker.add_position({"trade_id": "t1", "symbol": "BTC", "risk": 0.018})

    alloc = PortfolioAllocator(exposure_tracker=tracker, capital_policy=policy)
    result = alloc.allocate({"symbol": "ETHUSDT", "confidence": 0.5})
    # remaining cap = 0.02 - 0.018 = 0.002
    assert result["action"] == "ALLOCATE"
    assert result["risk"] == pytest.approx(0.002)


def test_allocator_open_close_position():
    alloc = PortfolioAllocator()
    alloc.open_position({"trade_id": "t1", "symbol": "BTC", "risk": 0.005})
    assert alloc.current_exposure() == pytest.approx(0.005)
    alloc.close_position("t1")
    assert alloc.current_exposure() == pytest.approx(0.0)


def test_allocator_correlated_signal_reduced():
    """High-correlation trade gets smaller risk than uncorrelated."""
    policy = CapitalPolicy(
        base_risk=0.005,
        high_correlation_threshold=0.7,
        high_correlation_factor=0.6,
    )
    tracker = ExposureTracker()
    tracker.add_position({"trade_id": "t1", "symbol": "BTCUSDT", "risk": 0.005})

    alloc = PortfolioAllocator(exposure_tracker=tracker, capital_policy=policy)
    # ETHUSDT is in same crypto group → high correlation → reduced risk
    result_correlated = alloc.allocate({"symbol": "ETHUSDT", "confidence": 0.5})

    alloc2 = PortfolioAllocator(capital_policy=policy)
    result_uncorrelated = alloc2.allocate({"symbol": "EURUSD", "confidence": 0.5})

    assert result_correlated["risk"] < result_uncorrelated["risk"]


def test_allocator_exposure_by_symbol():
    alloc = PortfolioAllocator()
    alloc.open_position({"trade_id": "t1", "symbol": "BTC", "risk": 0.005})
    alloc.open_position({"trade_id": "t2", "symbol": "ETH", "risk": 0.003})
    by_sym = alloc.exposure_by_symbol()
    assert "BTC" in by_sym
    assert "ETH" in by_sym