"""
test_scanner_ranker.py
=======================
Phase D: Multi-Symbol Scanner + Opportunity Ranker tests.

Covers:
  Universe:
    - default symbols available
    - filter by asset_class
    - add/remove symbol
    - unknown asset_class returns empty

  OpportunityRanker:
    - score formula is correct
    - signals below min_score discarded
    - ranked order is best-first
    - RR normalised correctly
    - empty input returns empty

  SignalPool.top_k:
    - returns at most k signals
    - hard cap at _MAX_K=3
    - with correlation dedup: correlated signals skipped

  MultiSymbolScanner:
    - returns only BUY signals by default
    - errors on individual symbols don't crash scan
    - NO_SIGNAL skipped correctly
    - all symbols scanned from universe
"""
import pytest
from unittest.mock import MagicMock

from src.scanner.universe import Universe
from src.scanner.ranker import OpportunityRanker
from src.scanner.signal_pool import SignalPool
from src.scanner.scanner import MultiSymbolScanner
from src.portfolio.correlation_engine import CorrelationEngine


# ── Universe ───────────────────────────────────────────────────────────────────

def test_universe_returns_all_default_symbols():
    uni = Universe()
    all_syms = uni.symbols()
    assert "BTCUSDT" in all_syms
    assert "EURUSD" in all_syms
    assert len(all_syms) > 0


def test_universe_filter_crypto():
    uni = Universe()
    crypto = uni.symbols(asset_class="crypto")
    assert "BTCUSDT" in crypto
    assert "EURUSD" not in crypto


def test_universe_filter_fx():
    uni = Universe()
    fx = uni.symbols(asset_class="fx")
    assert "EURUSD" in fx
    assert "BTCUSDT" not in fx


def test_universe_unknown_class_returns_empty():
    uni = Universe()
    result = uni.symbols(asset_class="NONEXISTENT")
    assert result == []


def test_universe_add_symbol():
    uni = Universe()
    uni.add_symbol("XYZUSDT", asset_class="crypto")
    assert "XYZUSDT" in uni.symbols(asset_class="crypto")


def test_universe_remove_symbol():
    uni = Universe()
    uni.remove_symbol("BTCUSDT")
    assert "BTCUSDT" not in uni.symbols()


def test_universe_custom_map():
    uni = Universe(symbol_map={"test": ["TSTUSD"]})
    assert uni.symbols() == ["TSTUSD"]
    assert uni.asset_classes() == ["test"]


# ── OpportunityRanker ─────────────────────────────────────────────────────────

def test_ranker_score_correct():
    """score = confidence*0.5 + (rr/3.0)*0.3 + zone*0.2"""
    ranker = OpportunityRanker(
        confidence_weight=0.5, rr_weight=0.3, zone_weight=0.2,
        min_score=0.0, rr_normalizer=3.0
    )
    # confidence=0.8, rr=3.0 (normalised=1.0), zone=0.7
    # score = 0.8*0.5 + 1.0*0.3 + 0.7*0.2 = 0.40 + 0.30 + 0.14 = 0.84
    score = ranker.score_signal({"confidence": 0.8, "rr": 3.0, "zone": 0.7})
    assert score == pytest.approx(0.84)


def test_ranker_rr_normalised_capped():
    """RR > rr_normalizer is capped at 1.0."""
    ranker = OpportunityRanker(min_score=0.0, rr_normalizer=3.0)
    score_high_rr = ranker.score_signal({"confidence": 0.5, "rr": 10.0, "zone": 0.5})
    score_cap_rr = ranker.score_signal({"confidence": 0.5, "rr": 3.0, "zone": 0.5})
    assert score_high_rr == pytest.approx(score_cap_rr)


def test_ranker_below_min_score_discarded():
    ranker = OpportunityRanker(min_score=0.70)
    signals = [
        {"symbol": "A", "confidence": 0.3, "rr": 1.0, "zone": 0.2},  # low score
        {"symbol": "B", "confidence": 0.9, "rr": 3.0, "zone": 0.8},  # high score
    ]
    ranked = ranker.rank(signals)
    assert len(ranked) == 1
    assert ranked[0]["symbol"] == "B"


def test_ranker_order_best_first():
    ranker = OpportunityRanker(min_score=0.0)
    signals = [
        {"symbol": "LOW", "confidence": 0.3, "rr": 1.0, "zone": 0.3},
        {"symbol": "HIGH", "confidence": 0.9, "rr": 3.0, "zone": 0.9},
        {"symbol": "MED", "confidence": 0.6, "rr": 2.0, "zone": 0.5},
    ]
    ranked = ranker.rank(signals)
    assert ranked[0]["symbol"] == "HIGH"
    assert ranked[-1]["symbol"] == "LOW"


def test_ranker_score_added_to_signal():
    ranker = OpportunityRanker(min_score=0.0)
    signals = [{"symbol": "A", "confidence": 0.7, "rr": 2.0, "zone": 0.6}]
    ranked = ranker.rank(signals)
    assert "_score" in ranked[0]
    assert isinstance(ranked[0]["_score"], float)


def test_ranker_empty_input():
    ranker = OpportunityRanker()
    assert ranker.rank([]) == []


def test_ranker_missing_fields_default_to_zero():
    ranker = OpportunityRanker(min_score=0.0)
    ranked = ranker.rank([{"symbol": "A"}])  # no confidence/rr/zone
    assert len(ranked) == 1
    assert ranked[0]["_score"] == pytest.approx(0.0)


# ── SignalPool ─────────────────────────────────────────────────────────────────

def _make_ranked_signals(n=5):
    return [
        {"symbol": f"SYM{i}", "_score": 0.9 - i * 0.05, "confidence": 0.8}
        for i in range(n)
    ]


def test_signal_pool_top_k_basic():
    pool = SignalPool()
    signals = _make_ranked_signals(5)
    top = pool.top_k(signals, k=2)
    assert len(top) == 2
    assert top[0]["symbol"] == "SYM0"  # best first


def test_signal_pool_hard_cap_3():
    """Even if k>3, hard cap limits to _MAX_K=3."""
    pool = SignalPool()
    signals = _make_ranked_signals(10)
    top = pool.top_k(signals, k=10)
    assert len(top) <= 3


def test_signal_pool_fewer_than_k_available():
    pool = SignalPool()
    signals = _make_ranked_signals(2)
    top = pool.top_k(signals, k=3)
    assert len(top) == 2


def test_signal_pool_dedup_correlated():
    """Correlated assets skipped when correlation_engine provided."""
    corr_engine = CorrelationEngine()
    pool = SignalPool(correlation_engine=corr_engine, corr_threshold=0.7)

    # BTC and ETH are in same crypto group → corr 0.8 > threshold
    signals = [
        {"symbol": "BTCUSDT", "_score": 0.9, "confidence": 0.9},
        {"symbol": "ETHUSDT", "_score": 0.85, "confidence": 0.85},  # correlated with BTC
        {"symbol": "EURUSD", "_score": 0.80, "confidence": 0.80},  # not correlated
    ]
    top = pool.top_k(signals, k=2)
    symbols = [s["symbol"] for s in top]

    assert "BTCUSDT" in symbols       # best signal, taken first
    assert "ETHUSDT" not in symbols   # skipped (correlated with BTC)
    assert "EURUSD" in symbols        # taken (not correlated)


def test_signal_pool_no_dedup_without_engine():
    """Without correlation_engine, correlated signals are NOT filtered."""
    pool = SignalPool()  # no correlation engine
    signals = [
        {"symbol": "BTCUSDT", "_score": 0.9},
        {"symbol": "ETHUSDT", "_score": 0.85},
        {"symbol": "EURUSD", "_score": 0.80},
    ]
    top = pool.top_k(signals, k=3)
    assert len(top) == 3


# ── MultiSymbolScanner ────────────────────────────────────────────────────────

def test_scanner_returns_buy_signals_only():
    uni = Universe(symbol_map={"test": ["A", "B", "C"]})

    def engine(symbol, data):
        if symbol == "A":
            return {"action": "BUY", "confidence": 0.8, "rr": 2.0, "zone": 0.7}
        if symbol == "B":
            return {"action": "NO_SIGNAL", "confidence": 0.5, "rr": 1.0, "zone": 0.5}
        return {"action": "SELL", "confidence": 0.6, "rr": 1.5, "zone": 0.6}

    scanner = MultiSymbolScanner(universe=uni, engine_runner=engine)
    signals = scanner.scan()
    assert len(signals) == 1
    assert signals[0]["symbol"] == "A"
    assert signals[0]["action"] == "BUY"


def test_scanner_error_on_symbol_doesnt_crash():
    uni = Universe(symbol_map={"test": ["GOOD", "BAD", "ALSO_GOOD"]})

    def engine(symbol, data):
        if symbol == "BAD":
            raise RuntimeError("simulated engine error")
        return {"action": "BUY", "confidence": 0.7, "rr": 2.0, "zone": 0.6}

    scanner = MultiSymbolScanner(universe=uni, engine_runner=engine)
    signals = scanner.scan()
    # BAD errored but GOOD + ALSO_GOOD should still be returned
    assert len(signals) == 2
    syms = [s["symbol"] for s in signals]
    assert "BAD" not in syms


def test_scanner_none_result_skipped():
    uni = Universe(symbol_map={"test": ["X", "Y"]})

    def engine(symbol, data):
        if symbol == "X":
            return None
        return {"action": "BUY", "confidence": 0.7, "rr": 2.0, "zone": 0.6}

    scanner = MultiSymbolScanner(universe=uni, engine_runner=engine)
    signals = scanner.scan()
    assert len(signals) == 1
    assert signals[0]["symbol"] == "Y"


def test_scanner_asset_class_filter():
    uni = Universe()  # default with crypto + fx + stocks

    def engine(symbol, data):
        return {"action": "BUY", "confidence": 0.8, "rr": 2.5, "zone": 0.7}

    scanner = MultiSymbolScanner(universe=uni, engine_runner=engine)
    crypto_signals = scanner.scan(asset_class="crypto")
    fx_signals = scanner.scan(asset_class="fx")

    crypto_syms = [s["symbol"] for s in crypto_signals]
    fx_syms = [s["symbol"] for s in fx_signals]

    assert "BTCUSDT" in crypto_syms
    assert "EURUSD" not in crypto_syms
    assert "EURUSD" in fx_syms
    assert "BTCUSDT" not in fx_syms


def test_scanner_with_data_fetcher():
    uni = Universe(symbol_map={"test": ["SYM1"]})
    fetched = {}

    def fetcher(symbol):
        fetched[symbol] = True
        return {"bars": [1, 2, 3]}

    def engine(symbol, data):
        assert "bars" in data
        return {"action": "BUY", "confidence": 0.7, "rr": 2.0, "zone": 0.6}

    scanner = MultiSymbolScanner(universe=uni, engine_runner=engine, data_fetcher=fetcher)
    signals = scanner.scan()
    assert "SYM1" in fetched
    assert len(signals) == 1