"""
test_analytics.py
==================
Phase F: Journal + Analytics + AI Feedback tests.

Covers:
  TradeRecord / TradeLogger:
    - to_dict / from_dict round-trip
    - log() writes to JSONL file
    - load_all() reads records back

  PerformanceAnalyzer:
    - win_rate, expectancy, profit_factor computed correctly
    - by_regime breakdown
    - by_config breakdown
    - empty input returns zero metrics

  TradeClustering:
    - clusters losses by condition
    - small clusters filtered (< min_cluster_size)
    - loss_rate_by_condition correct

  AIFeedback:
    - skips when trade_count < min_trades
    - rule-based fallback when no LLM
    - LLM fn called and result parsed
    - LLM failure falls back to rule-based
"""
import json
import pytest
from pathlib import Path

from src.journal.schema import TradeRecord
from src.journal.trade_logger import TradeLogger
from src.analytics.performance import PerformanceAnalyzer
from src.analytics.clustering import TradeClustering
from src.feedback.ai_feedback import AIFeedback


# ── TradeRecord ────────────────────────────────────────────────────────────────

def _make_record(**kwargs):
    defaults = {"trade_id": "t1", "timestamp": "2026-01-01T00:00:00Z", "symbol": "BTCUSDT"}
    defaults.update(kwargs)
    return TradeRecord(**defaults)


def test_trade_record_to_dict():
    r = _make_record(result="WIN", pnl=500.0)
    d = r.to_dict()
    assert d["trade_id"] == "t1"
    assert d["result"] == "WIN"
    assert d["pnl"] == 500.0


def test_trade_record_from_dict_round_trip():
    r = _make_record(result="LOSS", pnl=-200.0, confidence=0.7)
    d = r.to_dict()
    r2 = TradeRecord.from_dict(d)
    assert r2.trade_id == r.trade_id
    assert r2.pnl == r.pnl
    assert r2.confidence == r.confidence


def test_trade_record_to_json():
    r = _make_record()
    js = r.to_json()
    parsed = json.loads(js)
    assert parsed["trade_id"] == "t1"


# ── TradeLogger ────────────────────────────────────────────────────────────────

def test_trade_logger_writes_to_file(tmp_path):
    log_file = tmp_path / "journal.jsonl"
    logger = TradeLogger(log_path=str(log_file))
    r = _make_record(result="WIN", pnl=300.0)
    logger.log(r)
    assert log_file.exists()
    lines = log_file.read_text().strip().split("\n")
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["trade_id"] == "t1"
    assert entry["pnl"] == 300.0


def test_trade_logger_appends_multiple(tmp_path):
    log_file = tmp_path / "journal.jsonl"
    logger = TradeLogger(log_path=str(log_file))
    for i in range(3):
        logger.log(_make_record(trade_id=f"t{i}", result="WIN"))
    records = logger.load_all()
    assert len(records) == 3


def test_trade_logger_load_all_empty(tmp_path):
    log_file = tmp_path / "journal.jsonl"
    logger = TradeLogger(log_path=str(log_file))
    assert logger.load_all() == []


# ── PerformanceAnalyzer ────────────────────────────────────────────────────────

def _make_trades():
    return [
        {"result": "WIN", "pnl": 500.0, "regime": "TRENDING", "config_profile": "BALANCED", "zone": 0.7, "rr": 2.5},
        {"result": "WIN", "pnl": 300.0, "regime": "TRENDING", "config_profile": "BALANCED", "zone": 0.6, "rr": 2.0},
        {"result": "LOSS", "pnl": -200.0, "regime": "RANGING", "config_profile": "SAFE", "zone": 0.4, "rr": 1.5},
        {"result": "LOSS", "pnl": -150.0, "regime": "RANGING", "config_profile": "SAFE", "zone": 0.5, "rr": 1.8},
        {"result": "WIN", "pnl": 400.0, "regime": "TRENDING", "config_profile": "BALANCED", "zone": 0.8, "rr": 3.0},
    ]


def test_analyzer_win_rate():
    pa = PerformanceAnalyzer()
    result = pa.compute(_make_trades())
    assert result["win_rate"] == pytest.approx(3 / 5)


def test_analyzer_total_pnl():
    pa = PerformanceAnalyzer()
    result = pa.compute(_make_trades())
    assert result["total_pnl"] == pytest.approx(500 + 300 - 200 - 150 + 400)


def test_analyzer_expectancy_positive_for_winning_system():
    pa = PerformanceAnalyzer()
    result = pa.compute(_make_trades())
    assert result["expectancy"] > 0


def test_analyzer_profit_factor():
    pa = PerformanceAnalyzer()
    result = pa.compute(_make_trades())
    total_wins = 500 + 300 + 400
    total_losses = 200 + 150
    assert result["profit_factor"] == pytest.approx(total_wins / total_losses)


def test_analyzer_empty_input():
    pa = PerformanceAnalyzer()
    result = pa.compute([])
    assert result["total_trades"] == 0
    assert result["win_rate"] == 0.0


def test_analyzer_by_regime():
    pa = PerformanceAnalyzer()
    breakdown = pa.by_regime(_make_trades())
    assert "TRENDING" in breakdown
    assert "RANGING" in breakdown
    assert breakdown["TRENDING"]["win_rate"] == 1.0
    assert breakdown["RANGING"]["win_rate"] == 0.0


def test_analyzer_by_config():
    pa = PerformanceAnalyzer()
    breakdown = pa.by_config(_make_trades())
    assert "BALANCED" in breakdown
    assert "SAFE" in breakdown


# ── TradeClustering ───────────────────────────────────────────────────────────

def _make_cluster_trades():
    trades = []
    # 5 losses with low_zone
    for i in range(5):
        trades.append({"result": "LOSS", "pnl": -100.0, "zone": 0.4, "rr": 2.5, "confidence": 0.7, "regime": "TRENDING"})
    # 4 losses with low_rr
    for i in range(4):
        trades.append({"result": "LOSS", "pnl": -80.0, "zone": 0.7, "rr": 1.5, "confidence": 0.7, "regime": "TRENDING"})
    # 2 losses with ranging (below min_cluster_size=3)
    for i in range(2):
        trades.append({"result": "LOSS", "pnl": -50.0, "zone": 0.7, "rr": 2.5, "confidence": 0.7, "regime": "RANGING"})
    # Wins
    for i in range(10):
        trades.append({"result": "WIN", "pnl": 200.0, "zone": 0.8, "rr": 3.0, "confidence": 0.85, "regime": "TRENDING"})
    return trades


def test_clustering_finds_low_zone():
    tc = TradeClustering(min_cluster_size=3)
    clusters = tc.cluster_losses(_make_cluster_trades())
    assert "low_zone" in clusters
    assert len(clusters["low_zone"]) == 5


def test_clustering_finds_low_rr():
    tc = TradeClustering(min_cluster_size=3)
    clusters = tc.cluster_losses(_make_cluster_trades())
    assert "low_rr" in clusters


def test_clustering_filters_small_clusters():
    tc = TradeClustering(min_cluster_size=3)
    clusters = tc.cluster_losses(_make_cluster_trades())
    # ranging_regime cluster has only 2 → filtered out
    assert "ranging_regime" not in clusters


def test_clustering_empty_when_no_losses():
    tc = TradeClustering()
    trades = [{"result": "WIN", "pnl": 100.0, "zone": 0.8, "rr": 2.5, "confidence": 0.8, "regime": "TRENDING"}]
    clusters = tc.cluster_losses(trades)
    assert clusters == {}


def test_clustering_loss_rate_by_condition():
    tc = TradeClustering(min_cluster_size=3)
    result = tc.loss_rate_by_condition(_make_cluster_trades())
    assert "low_zone" in result
    assert 0 < result["low_zone"]["loss_rate"] <= 1.0


# ── AIFeedback ────────────────────────────────────────────────────────────────

def test_ai_feedback_skips_insufficient_trades():
    fb = AIFeedback(min_trades=30)
    result = fb.generate({}, {}, trade_count=10)
    assert result["skipped"] is True
    assert result["insights"] == []


def test_ai_feedback_rule_based_no_llm():
    fb = AIFeedback(llm_fn=None, min_trades=5)
    summary = {"win_rate": 0.35, "expectancy": -0.5}
    clusters = {"low_zone": [{"result": "LOSS"}] * 4}
    result = fb.generate(summary, clusters, trade_count=30)
    assert result["skipped"] is False
    assert len(result["insights"]) > 0
    assert len(result["suggestions"]) > 0


def test_ai_feedback_llm_called():
    llm_output = json.dumps({
        "insights": ["test insight"],
        "suggestions": [{"param": "fusion_min_score", "change": "+0.05", "reason": "test"}]
    })
    fb = AIFeedback(llm_fn=lambda prompt: llm_output, min_trades=5)
    result = fb.generate({"win_rate": 0.5}, {}, trade_count=50)
    assert result["skipped"] is False
    assert result["insights"] == ["test insight"]
    assert len(result["suggestions"]) == 1


def test_ai_feedback_llm_failure_falls_back():
    def bad_llm(prompt):
        raise RuntimeError("LLM unavailable")

    fb = AIFeedback(llm_fn=bad_llm, min_trades=5)
    result = fb.generate({"win_rate": 0.35, "expectancy": -0.3}, {}, trade_count=50)
    # Should fall back to rule-based (not raise)
    assert result["skipped"] is False


def test_ai_feedback_low_winrate_suggestion():
    fb = AIFeedback(llm_fn=None, min_trades=5)
    result = fb.generate({"win_rate": 0.30, "expectancy": 0.5}, {}, trade_count=50)
    params = [s["param"] for s in result["suggestions"]]
    assert "fusion_min_score" in params