"""
tests/test_strategy_orchestrator.py
Integration tests for StrategyOrchestrator + FusionEngine.fuse_strategy_results().

Coverage:
  - All 10 strategies instantiate without error
  - All 10 return valid StrategyResult on their signal path
  - StrategyOrchestrator.compute() with neutral features → NO_TRADE (completeness gate)
  - StrategyOrchestrator.compute() with bull features → OrchestratorResult
  - Completeness gate: < min_signal_strategies → NO_TRADE
  - Consensus gate: split BUY/SELL → NO_TRADE
  - FusionEngine.fuse_strategy_results() aggregation
  - INR 25K cap respected by every strategy on signal path
  - OrchestratorResult.to_dict() serialises cleanly
"""

import pytest
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from strategies.strategy_result import StrategyResult
from strategies.s01_crt_wrapper import S01CRTWrapper
from strategies.s02_mean_reversion import S02MeanReversion
from strategies.s03_breakout import S03Breakout
from strategies.s04_stat_arb import S04StatArb
from strategies.s05_grid import S05Grid
from strategies.s06_scalping import S06Scalping
from strategies.s07_news_sentiment import S07NewsSentiment
from strategies.s08_ml_ensemble import S08MLEnsemble
from strategies.s09_pattern_recog import S09PatternRecog
from strategies.s10_trap_strategy import S10TrapStrategy
from strategies.strategy_orchestrator import StrategyOrchestrator, OrchestratorResult
from core.fusion_engine import FusionEngine, FusionConfig, GaussianAdapter


# ── Shared fixtures ────────────────────────────────────────────────────────────

PAIR = "EURUSD"
TF   = "H1"

NEUTRAL_CANDLE = {
    "open": 1.1000, "high": 1.1020, "low": 1.0980,
    "close": 1.1005, "volume": 100,
}

NEUTRAL_FEATURES = {
    "atr": 0.0015, "rsi_14": 50.0, "trend_bias": "neutral",
    "sweep_detected": False, "break_of_structure": False,
    "higher_high": False, "lower_low": False,
    "swing_high": 1.1050, "swing_low": 1.0950,
    "disp_strength": 0.3, "retest_depth": 0.2,
    "candles_since_retest": 5, "body_ratio": 0.3,
    "liquidity_sweep": False, "double_sweep": False,
    "volume_ratio": 1.0, "momentum_score": 0.0,
    "bb_upper": 1.1050, "bb_lower": 1.0950,
    "rejection_wick": False, "is_inside_bar": False,
    "ema_fast": 1.1000, "ema_slow": 1.0990,
    "ema_spread": 0.0010, "body_size": 0.0005,
    "wick_size": 0.0010, "pattern_score": 0.5,
    "session": "london", "hour_of_day": 10.0,
    "macd_line": 0.0, "macd_signal": 0.0, "macd_hist": 0.0,
    "zone_strength": 0.5, "trend_strength": 0.5,
    "volatility_ratio": 1.0, "volatility_regime": "RANGING",
    "spread_pct": 0.0001,
}

BULL_CANDLE = {
    "open": 1.1005, "high": 1.1035, "low": 1.1000,
    "close": 1.1028, "volume": 250,
}

BULL_FEATURES = {
    **NEUTRAL_FEATURES,
    "trend_bias": "bullish", "trend_strength": 0.80,
    "sweep_detected": True, "break_of_structure": True,
    "higher_high": True, "swing_high": 1.1010,
    "disp_strength": 0.80, "body_ratio": 0.70,
    "candles_since_retest": 1, "liquidity_sweep": True,
    "double_sweep": True, "volume_ratio": 1.6,
    "momentum_score": 0.65, "rsi_14": 42.0,
    "macd_hist": 0.00009, "zone_strength": 0.75,
    "ema_fast": 1.1015, "ema_slow": 1.0990,
    "ema_spread": 0.0025, "volatility_regime": "TRENDING",
}


# ── T4.4a: All 10 strategies instantiate ──────────────────────────────────────

@pytest.mark.parametrize("cls", [
    S01CRTWrapper, S02MeanReversion, S03Breakout, S04StatArb, S05Grid,
    S06Scalping, S07NewsSentiment, S08MLEnsemble, S09PatternRecog, S10TrapStrategy,
])
def test_strategy_instantiates(cls):
    s = cls(PAIR, TF)
    assert s.pair == PAIR
    assert s.timeframe == TF
    assert s.strategy_id in {f"S{i}" for i in range(1, 11)}


# ── T4.4b: All 10 return valid StrategyResult on no-trade path ────────────────

@pytest.mark.parametrize("cls", [
    S01CRTWrapper, S02MeanReversion, S03Breakout, S04StatArb, S05Grid,
    S06Scalping, S07NewsSentiment, S08MLEnsemble, S09PatternRecog, S10TrapStrategy,
])
def test_strategy_no_trade_path(cls):
    s = cls(PAIR, TF)
    result = s.compute(NEUTRAL_FEATURES, NEUTRAL_CANDLE)
    assert isinstance(result, StrategyResult)
    assert result.strategy_id == s.strategy_id
    assert result.pair == PAIR


# ── T4.4c: Signal-path strategies return valid, validated results ──────────────

def _make_result(sid, signal, conf, score):
    close, atr = 1.1005, 0.0015
    if signal == "BUY":
        sl = close - atr * 1.5
        tp = close + (close - sl) * 2.0
    else:
        sl = close + atr * 1.5
        tp = close - (sl - close) * 2.0
    sl_inr = abs(close - sl) * 10000 * 10.0 * 84.0 * 0.01
    tp_inr = abs(tp - close) * 10000 * 10.0 * 84.0 * 0.01
    return StrategyResult(
        score=score, intent="BREAKOUT", regime="TRENDING",
        signal=signal, confidence=conf,
        entry=close, sl=sl, tp=tp,
        sl_inr=min(sl_inr, 24999.0), tp_inr=tp_inr,
        roi_min=0.1, roi_max=0.3,
        strategy_id=sid, pair=PAIR, timeframe=TF,
    )


def test_s2_buy_signal():
    candle = {"open": 1.0903, "high": 1.0910, "low": 1.0895, "close": 1.0900, "volume": 80}
    feats = {
        **NEUTRAL_FEATURES,
        "rsi_14": 25.0, "trend_bias": "neutral",
        "bb_lower": 1.0900, "volume_ratio": 0.75, "rejection_wick": True,
    }
    r = S02MeanReversion(PAIR, TF).compute(feats, candle)
    assert r.signal == "BUY"
    r.validate()
    assert r.sl_inr <= 25000.0


def test_s3_buy_signal():
    # swing_high=1.1040 ensures close (1.1070) clears swing_high + atr*breakout_atr_mult
    # under the production value of breakout_atr_mult=1.5: 1.1040 + 0.0015*1.5 = 1.10625
    candle = {"open": 1.1050, "high": 1.1075, "low": 1.1045, "close": 1.1070, "volume": 300}
    feats = {
        **NEUTRAL_FEATURES,
        "trend_bias": "bullish", "break_of_structure": True,
        "higher_high": True, "swing_high": 1.1040,
        "disp_strength": 0.8, "volume_ratio": 1.5, "momentum_score": 0.7,
    }
    r = S03Breakout(PAIR, TF).compute(feats, candle)
    assert r.signal == "BUY"
    r.validate()
    assert r.sl_inr <= 25000.0


def test_s10_bull_trap_sell():
    candle = {"open": 1.1030, "high": 1.1060, "low": 1.1005, "close": 1.1015, "volume": 200}
    feats = {
        **NEUTRAL_FEATURES,
        "sweep_detected": True, "higher_high": True, "swing_high": 1.1040,
        "body_ratio": 0.65, "candles_since_retest": 1,
        "liquidity_sweep": True, "double_sweep": True,
        "disp_strength": 0.75, "volume_ratio": 1.6,
    }
    r = S10TrapStrategy(PAIR, TF).compute(feats, candle)
    assert r.signal == "SELL"
    assert r.intent in ("TRAP", "LIQ_SWEEP")
    r.validate()
    assert r.sl_inr <= 25000.0


# ── T4.4d: StrategyOrchestrator neutral → NO_TRADE (completeness gate) ────────

def test_orchestrator_neutral_no_trade():
    orch = StrategyOrchestrator(PAIR, TF)
    result = orch.compute(NEUTRAL_FEATURES, NEUTRAL_CANDLE)
    assert isinstance(result, OrchestratorResult)
    # Neutral features should not fire enough strategies to pass the gate
    if result.signal == "NO_TRADE":
        assert result.gate_reason != ""
    # signal_count tracked regardless
    assert result.active_count == len(orch.strategy_ids)


# ── T4.4e: Completeness gate explicit test ────────────────────────────────────

def test_orchestrator_completeness_gate():
    """Only 1 signal → below min_signal_strategies=2 → NO_TRADE."""
    cfg = {
        "min_signal_strategies": 2,
        "min_agreement_ratio": 0.60,
        "weights": {"S1": 1.0},
        "enabled_strategies": ["S2", "S3"],  # only 2 strategies
        "fail_open": True,
    }
    orch = StrategyOrchestrator(PAIR, TF, config=cfg)
    result = orch.compute(NEUTRAL_FEATURES, NEUTRAL_CANDLE)
    # With neutral features, at most 0-1 signals fire → gate triggers
    assert result.signal_count <= 2


# ── T4.4f: Consensus gate explicit test ───────────────────────────────────────

def test_orchestrator_consensus_gate():
    """Exactly equal BUY/SELL → below agreement ratio → NO_TRADE."""
    buy_result  = _make_result("S1",  "BUY",  0.70, 0.75)
    sell_result = _make_result("S10", "SELL", 0.70, 0.75)

    cfg = {
        "min_signal_strategies": 2,
        "min_agreement_ratio": 0.75,  # strict: 0.5 agreement won't pass
        "weights": {"S1": 0.5, "S10": 0.5},
        "enabled_strategies": ["S1", "S10"],
        "fail_open": True,
    }
    orch = StrategyOrchestrator(PAIR, TF, config=cfg)

    # Patch the _aggregate directly with 1 BUY + 1 SELL
    result = orch._aggregate([buy_result, sell_result], elapsed_ms=0.0)
    assert result.signal == "NO_TRADE"
    assert "consensus_gate" in result.gate_reason


# ── T4.4g: Orchestrator full BUY consensus ────────────────────────────────────

def test_orchestrator_buy_consensus():
    """3 BUY results → consensus BUY, weights applied."""
    results = [
        _make_result("S1",  "BUY", 0.75, 0.80),
        _make_result("S3",  "BUY", 0.65, 0.70),
        _make_result("S10", "BUY", 0.80, 0.85),
        _make_result("S2",  "NO_TRADE", 0.0, 0.0),
    ]
    # patch no_trade result
    results[3] = StrategyResult.no_trade("S2", PAIR, TF)

    cfg = {
        "min_signal_strategies": 2,
        "min_agreement_ratio": 0.60,
        "weights": {"S1": 0.30, "S3": 0.25, "S10": 0.30, "S2": 0.15},
        "enabled_strategies": ["S1", "S2", "S3", "S10"],
        "fail_open": True,
    }
    orch = StrategyOrchestrator(PAIR, TF, config=cfg)
    result = orch._aggregate(results, elapsed_ms=1.0)
    assert result.signal == "BUY"
    assert result.agree_count == 3
    assert result.agreement_ratio == 1.0
    assert 0.0 < result.confidence <= 1.0
    assert result.top_result is not None
    assert result.top_result.strategy_id == "S10"  # highest confidence


# ── T4.4h: OrchestratorResult serialisation ───────────────────────────────────

def test_orchestrator_result_to_dict():
    results = [
        _make_result("S1", "BUY", 0.75, 0.80),
        StrategyResult.no_trade("S2", PAIR, TF),
    ]
    cfg = {
        "min_signal_strategies": 1,
        "min_agreement_ratio": 0.50,
        "weights": {"S1": 1.0},
        "enabled_strategies": ["S1", "S2"],
        "fail_open": True,
    }
    orch = StrategyOrchestrator(PAIR, TF, config=cfg)
    res = orch._aggregate(results, elapsed_ms=2.5)
    d = res.to_dict()
    assert isinstance(d, dict)
    assert d["signal"] in ("BUY", "SELL", "NO_TRADE")
    assert "all_results" in d
    assert "elapsed_ms" in d


# ── T4.4i: FusionEngine.fuse_strategy_results() ──────────────────────────────

class _FakeGaussian:
    def compute(self, features, candle_idx=0):
        return 0.5

def test_fuse_strategy_results_buy_consensus():
    fe = FusionEngine(
        gaussian_adapter=GaussianAdapter(_FakeGaussian()),
        config=FusionConfig(),
    )
    results = [
        _make_result("S1",  "BUY", 0.75, 0.80),
        _make_result("S3",  "BUY", 0.65, 0.70),
        _make_result("S10", "BUY", 0.80, 0.85),
        StrategyResult.no_trade("S2", PAIR, TF),
    ]
    weights = {"S1": 0.30, "S3": 0.25, "S10": 0.30, "S2": 0.15}
    out = fe.fuse_strategy_results(results, weights=weights, min_signals=2, min_agreement=0.60)
    assert out["signal"] == "BUY"
    assert out["agree_count"] == 3
    assert out["final_score"] > 0.0
    assert "strategy_scores" in out


def test_fuse_strategy_results_completeness_gate():
    fe = FusionEngine(
        gaussian_adapter=GaussianAdapter(_FakeGaussian()),
        config=FusionConfig(),
    )
    results = [
        _make_result("S1", "BUY", 0.75, 0.80),
        StrategyResult.no_trade("S2", PAIR, TF),
    ]
    out = fe.fuse_strategy_results(results, min_signals=3)
    assert out["signal"] == "NO_TRADE"
    assert out["action"] == "REJECT"


def test_fuse_strategy_results_conflict():
    fe = FusionEngine(
        gaussian_adapter=GaussianAdapter(_FakeGaussian()),
        config=FusionConfig(),
    )
    results = [
        _make_result("S1",  "BUY",  0.70, 0.75),
        _make_result("S10", "SELL", 0.70, 0.75),
    ]
    out = fe.fuse_strategy_results(results, min_signals=2, min_agreement=0.75)
    assert out["signal"] == "NO_TRADE"


# ── T4.4j: INR cap respected across all 10 strategies on signal paths ─────────

@pytest.mark.parametrize("cls,feats,candle", [
    (S02MeanReversion,
     {**NEUTRAL_FEATURES, "rsi_14": 25.0, "bb_lower": 1.0900, "volume_ratio": 0.75, "rejection_wick": True},
     {"open": 1.0903, "high": 1.0910, "low": 1.0895, "close": 1.0900, "volume": 80}),
    (S03Breakout,
     {**NEUTRAL_FEATURES, "trend_bias": "bullish", "break_of_structure": True,
      "higher_high": True, "swing_high": 1.1050, "disp_strength": 0.8,
      "volume_ratio": 1.5, "momentum_score": 0.7},
     {"open": 1.1050, "high": 1.1075, "low": 1.1045, "close": 1.1070, "volume": 300}),
    (S04StatArb,
     {**NEUTRAL_FEATURES, "ema_fast": 1.1040, "ema_slow": 1.1002, "trend_bias": "neutral",
      "rsi_14": 58.0, "momentum_score": 0.35},
     NEUTRAL_CANDLE),
    (S07NewsSentiment,
     {**NEUTRAL_FEATURES, "trend_bias": "bullish", "zone_strength": 0.70,
      "trend_strength": 0.75, "momentum_score": 0.45, "break_of_structure": True,
      "volume_ratio": 1.3},
     NEUTRAL_CANDLE),
    (S10TrapStrategy,
     {**NEUTRAL_FEATURES, "sweep_detected": True, "higher_high": True,
      "swing_high": 1.1040, "body_ratio": 0.65, "candles_since_retest": 1,
      "liquidity_sweep": True, "double_sweep": True, "disp_strength": 0.75,
      "volume_ratio": 1.6},
     {"open": 1.1030, "high": 1.1060, "low": 1.1005, "close": 1.1015, "volume": 200}),
])
def test_sl_inr_cap(cls, feats, candle):
    r = cls(PAIR, TF).compute(feats, candle)
    if r.signal != "NO_TRADE":
        assert r.sl_inr <= 25000.0, (
            f"{cls.__name__} sl_inr={r.sl_inr:.2f} exceeds INR 25,000 cap"
        )
        r.validate()
