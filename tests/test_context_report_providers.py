"""Provider-dispatch floor for the Context report (zero-cost by default).

`ContextReportAPI.context_analysis(provider=...)` selects who answers the architecture-analyst
prompt: `export` (no LLM — hand to Claude Code), `local`/`groq` (injected free `llm_caller`), or
`api` (metered Anthropic). These tests pin the dispatch + the shared 5-key parse, all offline.
"""
from __future__ import annotations

import json

from src.control_plane.context_report import ContextReportAPI

_RUN = {"command_id": "backtest", "status": "succeeded", "exit_code": 0}
_CC = [{"file": "src/core/engine_runner.py", "symbol": "EngineRunner", "kind": "class",
        "start_line": 1, "code": "class EngineRunner: pass"}]
_GC = {"available": True, "source": "flow_slice", "flow": "runtime", "title": "Runtime",
       "doc": "docs/architecture/signal-flow.md", "edges": [["core.engine_runner", "core.fusion_engine"]]}

_FIVE = {"executive_summary", "architecture_notes", "code_flow", "impact_radius", "structural_observations"}


def _api():
    return ContextReportAPI()


def test_export_default_makes_no_llm_call():
    r = _api().context_analysis(_RUN, {"stdout": "x"}, [], _CC, _GC)  # provider defaults to export
    assert r["ok"] is True
    assert r["source"] == "export"
    assert r["flow"] == "runtime"
    assert "PIPELINE FLOW" in r["prompt"]          # the flow slice is in the prompt
    assert "ARCHITECTURE ANALYST" in r["system"]
    assert "sections" not in r                      # no LLM ran, so no parsed report


def test_local_caller_yields_five_keys_and_coerces_list():
    def caller(system, prompt):
        assert "ARCHITECTURE ANALYST" in system and "PIPELINE FLOW" in prompt
        return json.dumps({
            "executive_summary": "ran", "architecture_notes": "n", "code_flow": "a depends on b",
            "impact_radius": "r", "structural_observations": ["hub", "sink"],
        })
    r = _api().context_analysis(_RUN, {"stdout": "x"}, [], _CC, _GC, provider="local", llm_caller=caller)
    assert r["ok"] is True
    assert set(r["sections"]) == _FIVE
    assert r["sections"]["structural_observations"] == "- hub\n- sink"   # list → bullets
    assert r["model"] == "local"


def test_groq_malformed_falls_back_to_five_key_shape():
    r = _api().context_analysis(_RUN, {"stdout": ""}, [], _CC, _GC,
                                provider="groq", llm_caller=lambda s, p: "not json")
    assert r["ok"] is True
    assert set(r["sections"]) == _FIVE
    assert "parse_warning" in r


def test_empty_output_is_an_error():
    r = _api().context_analysis(_RUN, {"stdout": ""}, [], _CC, _GC,
                                provider="local", llm_caller=lambda s, p: "")
    assert r["ok"] is False and "no output" in r["error"]


def test_unknown_provider_is_an_error():
    r = _api().context_analysis(_RUN, {"stdout": ""}, [], _CC, _GC, provider="bogus")
    assert r["ok"] is False and "unknown context-report provider" in r["error"]
