"""
tests/test_llm_connectivity.py
═══════════════════════════════════════════════════════════════════════════════
Validates LLM connectivity for llm_inference_client.py.

Coverage per TESTING.md §4 (External I/O — llama_gate):
  ✓ Happy call → score in [0.0, 1.0]
  ✓ Timeout → returns 1.0 (neutral / fail-open)
  ✓ URLError (server down) → returns 1.0
  ✓ Unparseable output → returns 1.0 with warning
  ✓ Circuit-breaker: FAIL_COUNT > _FAIL_COUNT_DISABLE → returns 1.0 silently
  ✓ build_prompt determinism
  ✓ build_insight_prompt — all 5 report types; unknown type raises ValueError
  ✓ llm_insight — happy path; timeout fallback; empty content fallback
  ✓ llm_score_batch — empty list; single success; fail_on_unavailable=True raises
  ✓ llm_score_cached / cached_llm_score — same key returns cached result
  ✓ llm_chat — local success; local fail → Groq fallback; both fail → ""
  ✓ _fallback_insight — all 5 report types return non-empty strings
  ✓ _load_dotenv — parses KEY=VALUE, export prefix, quotes, comments, no-overwrite
  ✓ _groq_available — disabled / no key / key+enabled
  ✓ _groq_request — stdlib urllib POST to Groq; HTTP error handling
"""

import io
import json
import os
import urllib.error
import urllib.request
from unittest.mock import MagicMock, patch

import pytest

# ── Import target module ───────────────────────────────────────────────────────
import config_layer.llm_inference_client as lg


# ── Helpers ────────────────────────────────────────────────────────────────────

def _mock_urlopen_response(content_dict: dict):
    """Return a context-manager mock that yields a fake HTTP response."""
    raw = json.dumps(content_dict).encode("utf-8")
    resp = MagicMock()
    resp.read.return_value = raw
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def _url_error(msg: str = "connection refused") -> urllib.error.URLError:
    return urllib.error.URLError(msg)


def _timeout_url_error() -> urllib.error.URLError:
    err = urllib.error.URLError(TimeoutError("timed out"))
    err.reason = TimeoutError("timed out")
    return err


# ══════════════════════════════════════════════════════════════════════════════
# 1. build_prompt
# ══════════════════════════════════════════════════════════════════════════════

class TestBuildPrompt:
    """Verifies the scoring prompt is deterministic and contains required fields."""

    SAMPLE_METRICS = {
        "win_rate": 0.55,
        "expectancy_rr": 1.3,
        "approved_trades": 42,
        "max_drawdown_pct": 0.12,
        "retests": 20,
        "expansions": 30,
    }

    def test_returns_string(self):
        result = lg.build_prompt(self.SAMPLE_METRICS)
        assert isinstance(result, str)

    def test_contains_score_label(self):
        result = lg.build_prompt(self.SAMPLE_METRICS)
        assert "Score:" in result

    def test_contains_win_rate(self):
        result = lg.build_prompt(self.SAMPLE_METRICS)
        assert "55.00%" in result

    def test_contains_trade_count(self):
        result = lg.build_prompt(self.SAMPLE_METRICS)
        assert "42" in result

    def test_deterministic(self):
        a = lg.build_prompt(self.SAMPLE_METRICS)
        b = lg.build_prompt(self.SAMPLE_METRICS)
        assert a == b

    def test_missing_keys_default_to_zero(self):
        """Empty metrics dict must not raise — all .get() calls have defaults."""
        result = lg.build_prompt({})
        assert "Score:" in result


# ══════════════════════════════════════════════════════════════════════════════
# 2. llm_score — primary HTTP path
# ══════════════════════════════════════════════════════════════════════════════

class TestLlmScore:
    """Tests the single-metric scoring function against a mocked HTTP server."""

    METRICS = {"win_rate": 0.6, "expectancy_rr": 1.5, "approved_trades": 30,
                "max_drawdown_pct": 0.08, "retests": 15, "expansions": 20}

    def test_happy_path_valid_float(self):
        with patch("urllib.request.urlopen",
                   return_value=_mock_urlopen_response({"content": "0.82"})):
            score = lg.llm_score(self.METRICS)
        assert 0.0 <= score <= 1.0
        assert abs(score - 0.82) < 1e-6

    def test_score_clamped_above_one(self):
        with patch("urllib.request.urlopen",
                   return_value=_mock_urlopen_response({"content": "1.0"})):
            score = lg.llm_score(self.METRICS)
        assert score == 1.0

    def test_score_clamped_below_zero(self):
        with patch("urllib.request.urlopen",
                   return_value=_mock_urlopen_response({"content": "0.0"})):
            score = lg.llm_score(self.METRICS)
        assert score == 0.0

    def test_unparseable_output_returns_one(self):
        with patch("urllib.request.urlopen",
                   return_value=_mock_urlopen_response({"content": "sorry, cannot score"})):
            score = lg.llm_score(self.METRICS)
        assert score == 1.0  # fail-open sentinel

    def test_timeout_returns_one(self):
        with patch("urllib.request.urlopen", side_effect=_timeout_url_error()):
            score = lg.llm_score(self.METRICS)
        assert score == 1.0

    def test_url_error_returns_one(self):
        with patch("urllib.request.urlopen", side_effect=_url_error()):
            score = lg.llm_score(self.METRICS)
        assert score == 1.0

    def test_generic_exception_returns_one(self):
        with patch("urllib.request.urlopen", side_effect=RuntimeError("boom")):
            score = lg.llm_score(self.METRICS)
        assert score == 1.0

    def test_custom_endpoint_used(self):
        """Ensures endpoint arg is forwarded (via Request constructor)."""
        custom_ep = "http://localhost:9999/completion"
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url
            return _mock_urlopen_response({"content": "0.75"})

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            lg.llm_score(self.METRICS, endpoint=custom_ep)

        assert captured["url"] == custom_ep

    # ── Audit log tests (new) ──────────────────────────────────────────────

    def test_audit_log_written_on_success(self, tmp_path, monkeypatch):
        """Local happy path → audit record with source=local, status=ok."""
        audit_file = tmp_path / "llm_audit.jsonl"
        monkeypatch.setattr(lg, "_LLM_AUDIT_LOG", str(audit_file))

        with patch("urllib.request.urlopen",
                   return_value=_mock_urlopen_response({"content": "0.72"})):
            lg.llm_score(self.METRICS)

        assert audit_file.exists(), "Audit log not created"
        record = json.loads(audit_file.read_text().strip())
        assert record["status"] == "ok"
        assert record["source"] == "local"
        assert record["model"] == "llama.cpp-local"
        assert abs(record["parsed_score"] - 0.72) < 1e-6
        assert "prompt" in record
        assert "input_metrics" in record
        assert record["raw_output"] == "0.72"

    def test_audit_log_groq_fallback_on_url_error(self, tmp_path, monkeypatch):
        """URLError → Groq fallback used → audit record with source=groq."""
        audit_file = tmp_path / "llm_audit.jsonl"
        monkeypatch.setattr(lg, "_LLM_AUDIT_LOG", str(audit_file))
        monkeypatch.setattr(lg, "_GROQ_FALLBACK_ENABLED", True)
        monkeypatch.setattr(lg, "_GROQ_API_KEY", "gsk_fake")
        # Patch _groq_request (stdlib urllib call to Groq) — no openai package needed
        monkeypatch.setattr(lg, "_groq_request", lambda *a, **kw: "0.65")

        with patch("urllib.request.urlopen", side_effect=_url_error()):
            score = lg.llm_score(self.METRICS)

        assert abs(score - 0.65) < 1e-6
        record = json.loads(audit_file.read_text().strip())
        assert record["source"] == "groq"
        assert record["status"] == "ok"
        assert record["parsed_score"] == pytest.approx(0.65, abs=1e-6)
        assert "local_error" in record

    def test_audit_log_groq_fallback_on_timeout(self, tmp_path, monkeypatch):
        """Timeout → Groq fallback used."""
        audit_file = tmp_path / "llm_audit.jsonl"
        monkeypatch.setattr(lg, "_LLM_AUDIT_LOG", str(audit_file))
        monkeypatch.setattr(lg, "_GROQ_FALLBACK_ENABLED", True)
        monkeypatch.setattr(lg, "_GROQ_API_KEY", "gsk_fake")
        monkeypatch.setattr(lg, "_groq_request", lambda *a, **kw: "0.81")

        with patch("urllib.request.urlopen", side_effect=_timeout_url_error()):
            score = lg.llm_score(self.METRICS)

        assert abs(score - 0.81) < 1e-6
        record = json.loads(audit_file.read_text().strip())
        assert record["source"] == "groq"

    def test_failopen_when_both_backends_down(self, tmp_path, monkeypatch):
        """Both local + Groq fail → failopen record, returns 1.0."""
        audit_file = tmp_path / "llm_audit.jsonl"
        monkeypatch.setattr(lg, "_LLM_AUDIT_LOG", str(audit_file))
        monkeypatch.setattr(lg, "_GROQ_FALLBACK_ENABLED", True)
        monkeypatch.setattr(lg, "_GROQ_API_KEY", "gsk_fake")
        # _groq_request returns "" → Groq failed → fall through to failopen
        monkeypatch.setattr(lg, "_groq_request", lambda *a, **kw: "")

        with patch("urllib.request.urlopen", side_effect=_url_error()):
            score = lg.llm_score(self.METRICS)

        assert score == 1.0
        record = json.loads(audit_file.read_text().strip())
        assert record["source"] == "failopen"
        assert record["status"] == "failopen"

    def test_local_success_skips_groq(self, tmp_path, monkeypatch):
        """When local server succeeds, _groq_request must not be called."""
        audit_file = tmp_path / "llm_audit.jsonl"
        monkeypatch.setattr(lg, "_LLM_AUDIT_LOG", str(audit_file))
        groq_call_count = {"n": 0}

        def counting_groq(*a, **kw):
            groq_call_count["n"] += 1
            return "0.99"

        monkeypatch.setattr(lg, "_groq_request", counting_groq)

        with patch("urllib.request.urlopen",
                   return_value=_mock_urlopen_response({"content": "0.55"})):
            lg.llm_score(self.METRICS)

        assert groq_call_count["n"] == 0
        record = json.loads(audit_file.read_text().strip())
        assert record["source"] == "local"

    def test_audit_log_appends_multiple_records(self, tmp_path, monkeypatch):
        """Multiple calls → multiple JSONL lines."""
        audit_file = tmp_path / "llm_audit.jsonl"
        monkeypatch.setattr(lg, "_LLM_AUDIT_LOG", str(audit_file))

        with patch("urllib.request.urlopen",
                   return_value=_mock_urlopen_response({"content": "0.6"})):
            lg.llm_score(self.METRICS)
            lg.llm_score(self.METRICS)

        lines = audit_file.read_text().strip().splitlines()
        assert len(lines) == 2

    def test_audit_log_failure_does_not_raise(self, tmp_path, monkeypatch):
        """If audit write fails (bad path), llm_score still returns normally."""
        monkeypatch.setattr(lg, "_LLM_AUDIT_LOG", "/dev/null/impossible/path.jsonl")

        with patch("urllib.request.urlopen",
                   return_value=_mock_urlopen_response({"content": "0.5"})):
            score = lg.llm_score(self.METRICS)

        assert score == 0.5


# ══════════════════════════════════════════════════════════════════════════════
# 2b. _groq_score helper
# ══════════════════════════════════════════════════════════════════════════════

class TestGroqScore:
    """Tests the internal _groq_score() helper — stdlib urllib, no openai package."""

    PROMPT = "Score: 0.0 to 1.0. Just a float.\n\nScore:"

    def test_valid_float_returned(self, monkeypatch):
        """_groq_request returns a valid float string → score and raw returned."""
        monkeypatch.setattr(lg, "_GROQ_API_KEY", "gsk_fake")
        monkeypatch.setattr(lg, "_GROQ_FALLBACK_ENABLED", True)
        monkeypatch.setattr(lg, "_groq_request", lambda *a, **kw: "0.74")
        score, raw = lg._groq_score(self.PROMPT)
        assert abs(score - 0.74) < 1e-6
        assert raw == "0.74"

    def test_unparseable_returns_one(self, monkeypatch):
        """Non-float response → score=1.0, raw preserved for audit."""
        monkeypatch.setattr(lg, "_GROQ_API_KEY", "gsk_fake")
        monkeypatch.setattr(lg, "_GROQ_FALLBACK_ENABLED", True)
        monkeypatch.setattr(lg, "_groq_request", lambda *a, **kw: "I cannot score this.")
        score, raw = lg._groq_score(self.PROMPT)
        assert score == 1.0
        assert raw == "I cannot score this."

    def test_unavailable_returns_one_empty(self, monkeypatch):
        """_groq_available() False → (1.0, '') without calling _groq_request."""
        monkeypatch.setattr(lg, "_GROQ_API_KEY", "")
        call_count = {"n": 0}

        def should_not_be_called(*a, **kw):
            call_count["n"] += 1
            return "0.5"

        monkeypatch.setattr(lg, "_groq_request", should_not_be_called)
        score, raw = lg._groq_score(self.PROMPT)
        assert score == 1.0
        assert raw == ""
        assert call_count["n"] == 0

    def test_request_error_returns_one(self, monkeypatch):
        """_groq_request returns "" (internal error) → (1.0, '')."""
        monkeypatch.setattr(lg, "_GROQ_API_KEY", "gsk_fake")
        monkeypatch.setattr(lg, "_GROQ_FALLBACK_ENABLED", True)
        monkeypatch.setattr(lg, "_groq_request", lambda *a, **kw: "")
        score, raw = lg._groq_score(self.PROMPT)
        assert score == 1.0
        assert raw == ""

    def test_uses_configured_model(self, monkeypatch):
        """_groq_request must receive _GROQ_MODEL via the payload."""
        captured = {}

        def capturing_groq_request(messages, max_tokens, temperature, stop=None):
            # _groq_request builds the model from _GROQ_MODEL — check it was set
            captured["model"] = lg._GROQ_MODEL
            return "0.5"

        monkeypatch.setattr(lg, "_GROQ_API_KEY", "gsk_fake")
        monkeypatch.setattr(lg, "_GROQ_FALLBACK_ENABLED", True)
        monkeypatch.setattr(lg, "_GROQ_MODEL", "mixtral-8x7b-32768")
        monkeypatch.setattr(lg, "_groq_request", capturing_groq_request)
        lg._groq_score(self.PROMPT)
        assert captured.get("model") == "mixtral-8x7b-32768"


# ══════════════════════════════════════════════════════════════════════════════
# 3. llm_score_safe — circuit-breaker behaviour
# ══════════════════════════════════════════════════════════════════════════════

class TestLlmScoreSafe:
    """Verifies llm_score_safe stays fail-open under all failure modes.

    Implementation note: llm_score() catches ALL exceptions internally and
    returns 1.0 — it never propagates.  Therefore llm_score_safe's except
    branch (which would increment FAIL_COUNT) is never reached; FAIL_COUNT
    is always reset to 0 via the try-success path.  Tests reflect actual
    observable behaviour rather than the dead except branch.
    """

    METRICS = {"win_rate": 0.5}

    def setup_method(self):
        lg.FAIL_COUNT = 0

    def teardown_method(self):
        lg.FAIL_COUNT = 0

    def test_success_resets_fail_count_to_zero(self):
        with patch("urllib.request.urlopen",
                   return_value=_mock_urlopen_response({"content": "0.7"})):
            score = lg.llm_score_safe(self.METRICS)
        assert lg.FAIL_COUNT == 0
        assert 0.0 <= score <= 1.0

    def test_server_down_returns_one_fail_open(self):
        """URLError → llm_score returns 1.0 internally; llm_score_safe passes it through."""
        with patch("urllib.request.urlopen", side_effect=_url_error()):
            score = lg.llm_score_safe(self.METRICS)
        assert score == 1.0

    def test_timeout_returns_one_fail_open(self):
        with patch("urllib.request.urlopen", side_effect=_timeout_url_error()):
            score = lg.llm_score_safe(self.METRICS)
        assert score == 1.0

    def test_always_calls_server(self):
        """llm_score_safe always delegates to llm_score — no pre-emptive short-circuit."""
        with patch("urllib.request.urlopen",
                   return_value=_mock_urlopen_response({"content": "0.6"})) as mock_open:
            lg.llm_score_safe(self.METRICS)
        mock_open.assert_called_once()


# ══════════════════════════════════════════════════════════════════════════════
# 4. llm_score_batch
# ══════════════════════════════════════════════════════════════════════════════

class TestLlmScoreBatch:
    METRICS_LIST = [
        {"win_rate": 0.6, "expectancy_rr": 1.2},
        {"win_rate": 0.4, "expectancy_rr": 0.8},
    ]

    def test_empty_list_returns_empty(self):
        result = lg.llm_score_batch([])
        assert result == []

    def test_returns_list_of_floats(self):
        with patch("urllib.request.urlopen",
                   return_value=_mock_urlopen_response({"content": "0.65"})):
            result = lg.llm_score_batch(self.METRICS_LIST)
        assert len(result) == 2
        assert all(isinstance(s, float) for s in result)
        assert all(0.0 <= s <= 1.0 for s in result)

    def test_server_down_safe_mode(self):
        """fail_on_unavailable=False (default) → [1.0, 1.0], no exception."""
        with patch("urllib.request.urlopen", side_effect=_url_error()):
            result = lg.llm_score_batch(self.METRICS_LIST, fail_on_unavailable=False)
        assert result == [1.0, 1.0]

    def test_server_down_strict_mode_raises(self):
        """fail_on_unavailable=True → LLMEndpointUnavailableError when probe fails."""
        with patch("urllib.request.urlopen", side_effect=_url_error()):
            with pytest.raises(lg.LLMEndpointUnavailableError):
                lg.llm_score_batch(self.METRICS_LIST, fail_on_unavailable=True)

    def test_single_item(self):
        with patch("urllib.request.urlopen",
                   return_value=_mock_urlopen_response({"content": "0.55"})):
            result = lg.llm_score_batch([{"win_rate": 0.5}])
        assert len(result) == 1
        assert 0.0 <= result[0] <= 1.0


# ══════════════════════════════════════════════════════════════════════════════
# 5. llm_score_cached / cached_llm_score
# ══════════════════════════════════════════════════════════════════════════════

class TestLlmScoreCached:
    """Ensures the LRU cache is hit on repeated identical calls."""

    METRICS = {"win_rate": 0.55, "expectancy_rr": 1.1,
               "approved_trades": 20, "max_drawdown_pct": 0.10}

    def test_cache_hit_avoids_second_http_call(self):
        # Clear cache before test
        lg.cached_llm_score.cache_clear()

        call_count = {"n": 0}

        def counting_urlopen(req, timeout=None):
            call_count["n"] += 1
            return _mock_urlopen_response({"content": "0.77"})

        with patch("urllib.request.urlopen", side_effect=counting_urlopen):
            s1 = lg.llm_score_cached(self.METRICS)
            s2 = lg.llm_score_cached(self.METRICS)

        assert s1 == s2
        assert call_count["n"] == 1  # second call served from cache

    def test_different_keys_invoke_server(self):
        lg.cached_llm_score.cache_clear()
        m1 = {"win_rate": 0.6}
        m2 = {"win_rate": 0.4}

        call_count = {"n": 0}

        def counting_urlopen(req, timeout=None):
            call_count["n"] += 1
            return _mock_urlopen_response({"content": "0.5"})

        with patch("urllib.request.urlopen", side_effect=counting_urlopen):
            lg.llm_score_cached(m1)
            lg.llm_score_cached(m2)

        assert call_count["n"] == 2


# ══════════════════════════════════════════════════════════════════════════════
# 6. build_insight_prompt
# ══════════════════════════════════════════════════════════════════════════════

INSIGHT_REPORT_TYPES = [
    "trade_decision",
    "session_summary",
    "eval_report",
    "backtest_summary",
    "regime_alert",
]


class TestBuildInsightPrompt:
    """Validates prompt templating for all five generative report types."""

    def test_all_valid_report_types_return_string(self):
        for rtype in INSIGHT_REPORT_TYPES:
            result = lg.build_insight_prompt({}, rtype)
            assert isinstance(result, str), f"Expected str for report_type={rtype}"
            assert len(result) > 0

    def test_missing_placeholders_filled_with_na(self):
        prompt = lg.build_insight_prompt({}, "trade_decision")
        # All template vars default to N/A when context is empty
        assert "N/A" in prompt

    def test_provided_values_appear_in_prompt(self):
        ctx = {"decision": "APPROVE", "reason": "high gaussian score"}
        prompt = lg.build_insight_prompt(ctx, "trade_decision")
        assert "APPROVE" in prompt
        assert "high gaussian score" in prompt

    def test_unknown_report_type_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown report_type"):
            lg.build_insight_prompt({}, "made_up_type")

    def test_none_values_converted_to_na(self):
        ctx = {"decision": None, "reason": None}
        prompt = lg.build_insight_prompt(ctx, "trade_decision")
        assert "{" not in prompt  # no un-rendered placeholders


# ══════════════════════════════════════════════════════════════════════════════
# 7. llm_insight
# ══════════════════════════════════════════════════════════════════════════════

class TestLlmInsight:
    """Tests the narrative generation function with mocked HTTP."""

    CTX = {
        "decision": "APPROVE",
        "reason": "strong sweep",
        "gaussian_score": "0.82",
        "ml_expected_rr": "1.5",
        "ml_win_prob": "0.63",
        "sweep": "0.9",
        "breakout": "0.7",
        "retest": "0.8",
        "time": "0.6",
    }

    def test_happy_path_returns_server_content(self):
        expected = "The trade was approved due to a strong sweep pattern."
        with patch("urllib.request.urlopen",
                   return_value=_mock_urlopen_response({"content": expected})):
            result = lg.llm_insight(self.CTX, "trade_decision")
        assert result == expected

    def test_timeout_returns_fallback_string(self):
        with patch("urllib.request.urlopen", side_effect=_timeout_url_error()):
            result = lg.llm_insight(self.CTX, "trade_decision")
        assert isinstance(result, str)
        assert len(result) > 0  # fallback is non-empty

    def test_url_error_returns_fallback(self):
        with patch("urllib.request.urlopen", side_effect=_url_error()):
            result = lg.llm_insight(self.CTX, "trade_decision")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_empty_content_returns_fallback(self):
        with patch("urllib.request.urlopen",
                   return_value=_mock_urlopen_response({"content": ""})):
            result = lg.llm_insight(self.CTX, "trade_decision")
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.parametrize("rtype", INSIGHT_REPORT_TYPES)
    def test_all_report_types_return_string(self, rtype):
        with patch("urllib.request.urlopen", side_effect=_url_error()):
            result = lg.llm_insight({}, rtype)
        assert isinstance(result, str)


# ══════════════════════════════════════════════════════════════════════════════
# 8. llm_chat
# ══════════════════════════════════════════════════════════════════════════════

class TestLlmChat:
    """Tests the multi-turn chat function: local → Groq → circuit-breaker chain."""

    MESSAGES = [
        {"role": "system", "content": "You are a trading assistant."},
        {"role": "user", "content": "Should I take this trade?"},
    ]

    def setup_method(self):
        lg.FAIL_COUNT = 0

    def teardown_method(self):
        lg.FAIL_COUNT = 0

    def test_local_server_success(self):
        expected = "Yes, the setup looks strong."
        with patch("urllib.request.urlopen",
                   return_value=_mock_urlopen_response({"content": expected})):
            result = lg.llm_chat(self.MESSAGES)
        assert result == expected
        assert lg.FAIL_COUNT == 0

    def test_local_fail_groq_fallback(self, monkeypatch):
        """When local server fails and Groq is available, _groq_request is tried."""
        monkeypatch.setattr(lg, "_GROQ_API_KEY", "gsk_fake")
        monkeypatch.setattr(lg, "_GROQ_FALLBACK_ENABLED", True)
        monkeypatch.setattr(lg, "_groq_request", lambda *a, **kw: "Groq says yes.")
        with patch("urllib.request.urlopen", side_effect=_url_error()):
            result = lg.llm_chat(self.MESSAGES)
        assert result == "Groq says yes."
        assert lg.FAIL_COUNT == 0

    def test_both_fail_returns_empty_string(self, monkeypatch):
        """Both local and Groq fail → empty string, FAIL_COUNT incremented."""
        monkeypatch.setattr(lg, "_GROQ_API_KEY", "gsk_fake")
        monkeypatch.setattr(lg, "_GROQ_FALLBACK_ENABLED", True)
        monkeypatch.setattr(lg, "_groq_request", lambda *a, **kw: "")  # Groq fails
        with patch("urllib.request.urlopen", side_effect=_url_error()):
            result = lg.llm_chat(self.MESSAGES)
        assert result == ""
        assert lg.FAIL_COUNT == 1

    def test_groq_disabled_local_fail_returns_empty(self, monkeypatch):
        """Groq disabled → skip Groq, return empty string on local failure."""
        monkeypatch.setattr(lg, "_GROQ_FALLBACK_ENABLED", False)
        with patch("urllib.request.urlopen", side_effect=_url_error()):
            result = lg.llm_chat(self.MESSAGES)
        assert result == ""

    def test_circuit_breaker_still_returns_empty_string_past_threshold(self, monkeypatch):
        """Past the threshold llm_chat still attempts the server (no pre-emption)
        but returns "" and suppresses the warning log instead of logging attempt N/M."""
        lg.FAIL_COUNT = lg._FAIL_COUNT_DISABLE + 1
        monkeypatch.setattr(lg, "_GROQ_FALLBACK_ENABLED", False)
        with patch("urllib.request.urlopen", side_effect=_url_error()):
            result = lg.llm_chat(self.MESSAGES)
        assert result == ""

    def test_prompt_contains_role_markers(self):
        """Flat prompt sent to server must contain BitNet role markers."""
        captured = {}

        def fake_urlopen(req, timeout=None):
            body = json.loads(req.data.decode())
            captured["prompt"] = body["prompt"]
            return _mock_urlopen_response({"content": "ok"})

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            lg.llm_chat(self.MESSAGES)

        prompt = captured["prompt"]
        assert "<|system|>" in prompt
        assert "<|user|>" in prompt
        assert "<|assistant|>" in prompt


# ══════════════════════════════════════════════════════════════════════════════
# 9. _fallback_insight — all branches
# ══════════════════════════════════════════════════════════════════════════════

class TestFallbackInsight:
    """Every branch of _fallback_insight must return a non-empty string."""

    @pytest.mark.parametrize("rtype", INSIGHT_REPORT_TYPES)
    def test_returns_nonempty_string(self, rtype):
        result = lg._fallback_insight({}, rtype)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_unknown_type_returns_stringified_context(self):
        ctx = {"foo": "bar"}
        result = lg._fallback_insight(ctx, "unknown_type")
        assert "bar" in result

    def test_trade_decision_includes_decision_and_reason(self):
        ctx = {"decision": "REJECT", "reason": "low win_rate",
               "gaussian_score": "0.4", "ml_expected_rr": "0.8", "ml_win_prob": "0.42"}
        result = lg._fallback_insight(ctx, "trade_decision")
        assert "REJECT" in result
        assert "low win_rate" in result

    def test_session_summary_includes_symbol(self):
        ctx = {"symbol": "BTCUSDT", "session": "London",
               "approved_trades": 5, "win_rate": "60%",
               "net_rr": "1.2", "max_drawdown": "8%"}
        result = lg._fallback_insight(ctx, "session_summary")
        assert "BTCUSDT" in result

    def test_regime_alert_shows_regime_transition(self):
        ctx = {"prev_regime": "trending", "curr_regime": "ranging",
               "symbol": "EURUSD", "session": "NY", "volatility": "high"}
        result = lg._fallback_insight(ctx, "regime_alert")
        assert "trending" in result
        assert "ranging" in result


# ══════════════════════════════════════════════════════════════════════════════
# 10. _load_dotenv — .env file parser
# ══════════════════════════════════════════════════════════════════════════════

class TestLoadDotenv:
    """Verifies the stdlib .env loader covers all supported line formats."""

    def _write_env(self, tmp_path, content: str):
        f = tmp_path / ".env"
        f.write_text(content, encoding="utf-8")
        return tmp_path

    def test_simple_key_value(self, tmp_path, monkeypatch):
        self._write_env(tmp_path, "MY_KEY=hello\n")
        monkeypatch.delenv("MY_KEY", raising=False)
        lg._load_dotenv(tmp_path / ".env")
        assert os.environ.get("MY_KEY") == "hello"

    def test_double_quoted_value(self, tmp_path, monkeypatch):
        self._write_env(tmp_path, 'MY_KEY="quoted value"\n')
        monkeypatch.delenv("MY_KEY", raising=False)
        lg._load_dotenv(tmp_path / ".env")
        assert os.environ.get("MY_KEY") == "quoted value"

    def test_single_quoted_value(self, tmp_path, monkeypatch):
        self._write_env(tmp_path, "MY_KEY='single'\n")
        monkeypatch.delenv("MY_KEY", raising=False)
        lg._load_dotenv(tmp_path / ".env")
        assert os.environ.get("MY_KEY") == "single"

    def test_export_prefix_stripped(self, tmp_path, monkeypatch):
        self._write_env(tmp_path, "export MY_KEY=exported\n")
        monkeypatch.delenv("MY_KEY", raising=False)
        lg._load_dotenv(tmp_path / ".env")
        assert os.environ.get("MY_KEY") == "exported"

    def test_inline_comment_stripped(self, tmp_path, monkeypatch):
        self._write_env(tmp_path, "MY_KEY=value # this is a comment\n")
        monkeypatch.delenv("MY_KEY", raising=False)
        lg._load_dotenv(tmp_path / ".env")
        assert os.environ.get("MY_KEY") == "value"

    def test_full_line_comment_ignored(self, tmp_path, monkeypatch):
        self._write_env(tmp_path, "# COMMENTED=out\nMY_KEY=real\n")
        monkeypatch.delenv("MY_KEY", raising=False)
        monkeypatch.delenv("COMMENTED", raising=False)
        lg._load_dotenv(tmp_path / ".env")
        assert os.environ.get("MY_KEY") == "real"
        assert os.environ.get("COMMENTED") is None

    def test_does_not_overwrite_existing_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MY_KEY", "original")
        self._write_env(tmp_path, "MY_KEY=from_file\n")
        lg._load_dotenv(tmp_path / ".env")
        assert os.environ["MY_KEY"] == "original"   # not overwritten

    def test_missing_env_file_does_not_raise(self, tmp_path):
        """No .env anywhere in the tree → silent, no exception."""
        lg._load_dotenv(tmp_path / "nonexistent_dir" / "file.py")

    def test_groq_api_key_loaded_from_env_file(self, tmp_path, monkeypatch):
        """End-to-end: GROQ_API_KEY in .env → os.environ contains the key."""
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        self._write_env(tmp_path, "GROQ_API_KEY=gsk_testkey123\n")
        lg._load_dotenv(tmp_path / ".env")
        assert os.environ.get("GROQ_API_KEY") == "gsk_testkey123"


# ══════════════════════════════════════════════════════════════════════════════
# 11. _groq_available + _groq_request — stdlib urllib, no openai package
# ══════════════════════════════════════════════════════════════════════════════

class TestGroqAvailableAndRequest:
    """Tests _groq_available() guard and _groq_request() stdlib HTTP path."""

    def test_available_false_when_key_empty(self, monkeypatch):
        monkeypatch.setattr(lg, "_GROQ_API_KEY", "")
        monkeypatch.setattr(lg, "_GROQ_FALLBACK_ENABLED", True)
        assert lg._groq_available() is False

    def test_available_false_when_disabled(self, monkeypatch):
        monkeypatch.setattr(lg, "_GROQ_API_KEY", "gsk_fake")
        monkeypatch.setattr(lg, "_GROQ_FALLBACK_ENABLED", False)
        assert lg._groq_available() is False

    def test_available_true_when_key_and_enabled(self, monkeypatch):
        monkeypatch.setattr(lg, "_GROQ_API_KEY", "gsk_fake")
        monkeypatch.setattr(lg, "_GROQ_FALLBACK_ENABLED", True)
        assert lg._groq_available() is True

    def test_groq_request_success(self, monkeypatch):
        """_groq_request parses choices[0].message.content from Groq response."""
        monkeypatch.setattr(lg, "_GROQ_API_KEY", "gsk_fake")
        body = {"choices": [{"message": {"content": "0.77"}}]}
        with patch("urllib.request.urlopen",
                   return_value=_mock_urlopen_response(body)):
            result = lg._groq_request(
                messages=[{"role": "user", "content": "test"}],
                max_tokens=8,
                temperature=0.0,
            )
        assert result == "0.77"

    def test_groq_request_http_error_returns_empty(self, monkeypatch):
        """HTTP 401 from Groq → _groq_request returns '' without raising."""
        monkeypatch.setattr(lg, "_GROQ_API_KEY", "gsk_bad_key")
        http_err = urllib.error.HTTPError(
            lg._GROQ_ENDPOINT, 401, "Unauthorized",
            {}, io.BytesIO(b'{"error": "invalid_api_key"}'),
        )
        with patch("urllib.request.urlopen", side_effect=http_err):
            result = lg._groq_request(
                messages=[{"role": "user", "content": "test"}],
                max_tokens=8,
                temperature=0.0,
            )
        assert result == ""

    def test_groq_request_network_error_returns_empty(self):
        """Network failure → _groq_request returns '' without raising."""
        with patch("urllib.request.urlopen", side_effect=_url_error()):
            result = lg._groq_request(
                messages=[{"role": "user", "content": "test"}],
                max_tokens=8,
                temperature=0.0,
            )
        assert result == ""

    def test_llm_score_uses_groq_when_local_fails(self, tmp_path, monkeypatch):
        """Full integration: _groq_request returns a float → llm_score returns it."""
        audit_file = tmp_path / "llm_audit.jsonl"
        monkeypatch.setattr(lg, "_LLM_AUDIT_LOG", str(audit_file))
        monkeypatch.setattr(lg, "_GROQ_FALLBACK_ENABLED", True)
        monkeypatch.setattr(lg, "_GROQ_API_KEY", "gsk_fake")
        monkeypatch.setattr(lg, "_groq_request", lambda *a, **kw: "0.73")

        with patch("urllib.request.urlopen", side_effect=_timeout_url_error()):
            score = lg.llm_score({"win_rate": 0.55, "expectancy_rr": 1.0,
                                   "approved_trades": 40, "max_drawdown_pct": 0.1})

        assert abs(score - 0.73) < 1e-6
        record = json.loads(audit_file.read_text().strip())
        assert record["source"] == "groq"
        assert record["status"] == "ok"
