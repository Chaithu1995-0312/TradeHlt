"""
test_agent_intent_router.py
===========================
Tests for src/agent/intent_router.py.

Actual API:
  IntentRouter(llm_chat_fn: Callable, patterns_path=..., use_llm=True, confidence_floor=0.6)
  classify(user_input: str, conversation: list) -> {"mode": str|None, "intent_key": str, "confidence": float}

Notes:
  - Patterns loaded from src/agent/prompts/intent_patterns.json (relative to CWD = repo root)
  - Regex match → confidence=0.85
  - LLM lazy import: patch "config_layer.llm_inference_client.llm_chat"
  - Unclassified returns mode=None, intent_key="ask_user", confidence=0.0
"""

import pytest
from unittest.mock import MagicMock, patch

from agent.intent_router import IntentRouter


def _router(use_llm=False, confidence_floor=0.6):
    """Create IntentRouter with a mock llm_chat_fn and standard settings."""
    return IntentRouter(
        llm_chat_fn=MagicMock(),
        use_llm=use_llm,
        confidence_floor=confidence_floor,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Regex classification
# ─────────────────────────────────────────────────────────────────────────────

def test_regex_pipeline_tune_promote():
    """'tune.*and.*promot' pattern → tune_and_promote, mode=pipeline."""
    router = _router(use_llm=False)
    result = router.classify("tune and promote EURUSD", [])
    assert result["mode"] == "pipeline"
    assert result["intent_key"] == "tune_and_promote"
    assert result["confidence"] == pytest.approx(0.85)


def test_regex_pipeline_backtest():
    """'run.*backtest' pattern → backtest_only, mode=pipeline."""
    router = _router(use_llm=False)
    result = router.classify("run backtest on AUDUSD", [])
    assert result["mode"] == "pipeline"
    assert result["intent_key"] == "backtest_only"


def test_regex_pipeline_validate():
    """'run.*valid' pattern → validate_only, mode=pipeline."""
    router = _router(use_llm=False)
    result = router.classify("run validation on current config", [])
    assert result["mode"] == "pipeline"
    assert result["intent_key"] == "validate_only"


def test_regex_copilot_advise():
    """'advise.*signal' pattern → advise_signal, mode=copilot."""
    router = _router(use_llm=False)
    result = router.classify("advise on current BTCUSDT signal", [])
    assert result["mode"] == "copilot"
    assert result["intent_key"] == "advise_signal"


def test_regex_copilot_veto():
    """'veto' pattern → veto_query, mode=copilot."""
    router = _router(use_llm=False)
    result = router.classify("should I veto this trade?", [])
    assert result["mode"] == "copilot"
    assert result["intent_key"] == "veto_query"


def test_regex_governance_run():
    """'run.*governance' pattern → governance_run, mode=governance."""
    router = _router(use_llm=False)
    result = router.classify("run governance on yesterday's trades", [])
    assert result["mode"] == "governance"
    assert result["intent_key"] == "governance_run"


def test_regex_governance_run_reflect():
    """'run.*reflect' pattern → governance_run, mode=governance."""
    router = _router(use_llm=False)
    result = router.classify("run reflect on last week", [])
    assert result["mode"] == "governance"
    assert result["intent_key"] == "governance_run"


def test_regex_full_pipeline():
    """'full.*pipeline' pattern → full_pipeline, mode=pipeline."""
    router = _router(use_llm=False)
    result = router.classify("run the full pipeline", [])
    assert result["mode"] == "pipeline"
    assert result["intent_key"] == "full_pipeline"


# ─────────────────────────────────────────────────────────────────────────────
# Unclassified / unknown input
# ─────────────────────────────────────────────────────────────────────────────

def test_unknown_input_returns_ask_user():
    """Input matching no patterns and no LLM → ask_user with confidence=0.0."""
    router = _router(use_llm=False)
    result = router.classify("what is the weather today?", [])
    assert result["intent_key"] == "ask_user"
    assert result["confidence"] == pytest.approx(0.0)
    assert result["mode"] is None


def test_unknown_input_returns_mode_none():
    """mode must be None (not 'unknown') for unclassified input."""
    router = _router(use_llm=False)
    result = router.classify("show me the latest memes", [])
    assert result["mode"] is None


# ─────────────────────────────────────────────────────────────────────────────
# LLM classification path
# ─────────────────────────────────────────────────────────────────────────────

def test_llm_classify_high_confidence():
    """LLM response with valid intent_key + confidence >= floor → used as result."""
    router = _router(use_llm=True, confidence_floor=0.6)
    mock_response = '{"intent_key": "tune_and_promote", "confidence": 0.92}'
    with patch("config_layer.llm_inference_client.llm_chat", return_value=mock_response):
        result = router.classify("retrain the model please", [])
    assert result["mode"] == "pipeline"
    assert result["intent_key"] == "tune_and_promote"
    assert result["confidence"] >= 0.6


def test_llm_classify_invalid_intent_key_falls_back_to_ask_user():
    """LLM returning an unrecognised intent_key must be reset to ask_user."""
    router = _router(use_llm=True, confidence_floor=0.6)
    mock_response = '{"intent_key": "totally_unknown_intent", "confidence": 0.95}'
    with patch("config_layer.llm_inference_client.llm_chat", return_value=mock_response):
        result = router.classify("do the mysterious thing", [])
    # Unrecognised key → ask_user; below floor after reset → fallback
    assert result["intent_key"] == "ask_user"


def test_llm_classify_low_confidence_falls_back():
    """LLM confidence below floor → result not used; regex fallback applies."""
    router = _router(use_llm=True, confidence_floor=0.6)
    mock_response = '{"intent_key": "tune_and_promote", "confidence": 0.3}'
    with patch("config_layer.llm_inference_client.llm_chat", return_value=mock_response):
        # Input that won't match regex either → ask_user
        result = router.classify("do the thing", [])
    # Either regex matched something OR fallback ask_user — must not be the low-conf LLM answer
    assert result["confidence"] != pytest.approx(0.3)


def test_llm_failure_falls_back_to_regex():
    """LLM RuntimeError → regex takes over; clear regex match must be returned."""
    router = _router(use_llm=True, confidence_floor=0.6)
    with patch("config_layer.llm_inference_client.llm_chat", side_effect=RuntimeError("LLM down")):
        # "run.*backtest" pattern → backtest_only
        result = router.classify("run backtest on GBPUSD", [])
    assert result["mode"] == "pipeline"
    assert result["intent_key"] == "backtest_only"
    assert result["confidence"] == pytest.approx(0.85)


# ─────────────────────────────────────────────────────────────────────────────
# Return dict structure invariant
# ─────────────────────────────────────────────────────────────────────────────

def test_classify_always_returns_required_keys():
    """classify() must always return mode, intent_key, confidence regardless of path."""
    router = _router(use_llm=False)
    for text in (
        "tune and promote EURUSD",      # regex hit
        "what is the weather today?",   # no hit
    ):
        result = router.classify(text, [])
        for key in ("mode", "intent_key", "confidence"):
            assert key in result, f"Missing key '{key}' for input '{text}'"
        assert isinstance(result["intent_key"], str)
        assert isinstance(result["confidence"], float)
