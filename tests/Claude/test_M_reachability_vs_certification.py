"""M. Reachability is not certification (F-073 / F-075).

Semantic invariant: `parent_crt.enabled: true` on the ACTIVE config arms the
M15 EXECUTION-gate bias check, and CH-parent-crt-caller-wire threads
ParentCRTFeed.bias into BacktestRunner — so the gate is REACHABLE. Reachable is
not certified and not live. CRT closure stays OPEN (reopened by F-074, widened
by F-075), the objective gate stays OFF by default, every research call site
still defaults parent_state to None, and there is still no live execution rail:
the class that would run one is never instantiated and its would-be caller
imports a name that does not exist (F-073).

Ordinary tests pin the parent track, the feed, and the wiring — that the gate
works when it is called. They do not assert the four boundaries around it: armed
is not certified, wired is not live, default-None is the research path, and a
swallowed ImportError is not a working entry point.
"""
from __future__ import annotations

import ast
import inspect
import json
import re
from pathlib import Path

import pytest

from config_layer.crt_engine_v2 import CRTEngine
from config_layer.production_config import get_active_version, get_prod_section

_REPO = Path(__file__).resolve().parents[2]


def test_parent_crt_is_armed_on_the_active_config():
    """The bias gate is switched ON at Tier 0, not merely available in code.

    Source: configs/production/ACTIVE_VERSION -> v2_htfcrt_2026_08, section
    parent_crt.enabled (CH-htfcrt-parent-candle-smc-v1, 2026-08-15)
    Failure mode: a session reasons about parent bias from the code alone and
    misses that this version, unlike v2_multi_2026_04, actually arms it.
    """
    assert get_active_version() == "v2_htfcrt_2026_08"
    parent_crt = get_prod_section("parent_crt")
    assert parent_crt["enabled"] is True
    assert parent_crt["timeframe"]


def test_objective_gate_stays_off_by_default():
    """HTF objective activation is present, configured, and deliberately not on.

    Source: parent_crt.objective_gate on the ACTIVE config (F-078; P-HTF-01
    measured n=3 UNDETERMINED)
    Failure mode: the objective gate is read as active because parent_crt is
    active, so an EXECUTION rejection is attributed to the wrong dimension.
    """
    objective_gate = get_prod_section("parent_crt")["objective_gate"]
    assert objective_gate["enabled"] is False
    assert objective_gate["mode"] == "allow_exists_only"


@pytest.mark.parametrize("keyword", ["parent_state", "parent_objective"])
def test_process_candle_parent_keywords_default_to_none(keyword: str):
    """Armed config plus defaulted keyword means research paths get no bias at all.

    Source: crt_engine_v2.CRTEngine.process_candle signature — both parent keywords
    are optional and default to None, so only a caller that threads the feed sees
    the gate.
    Failure mode: a research or analysis backtest is reported as "ran with parent
    bias" because the config had it armed, when that call site passed None.
    Why ordinary tests miss it: the wiring test constructs the feed, so it proves
    the wired path and never exercises the defaulted one.
    """
    parameters = inspect.signature(CRTEngine.process_candle).parameters
    assert keyword in parameters
    assert parameters[keyword].default is None


def test_crt_closure_surface_is_still_open():
    """Wiring the parent graph did not re-certify the state machine.

    Source: docs/governance/closure_authority_index.json, surface_id "CRT"
    Failure mode: "the parent CRT is wired" is read as "CRT is CLOSED", so a
    12-state re-certification is skipped on the strength of a reachability result.
    """
    index = json.loads(
        (_REPO / "docs" / "governance" / "closure_authority_index.json").read_text(
            encoding="utf-8"
        )
    )
    crt = next(s for s in index["surfaces"] if s["surface_id"] == "CRT")
    assert crt["status"] == "OPEN"
    assert crt["status"] in index["allowed_status"]


def test_the_live_engine_hook_name_does_not_exist():
    """The symbol pipeline_mode imports is absent; the real class is named otherwise.

    Source: runtime.live_engine_hook defines HookedLiveEngine, not LiveEngineHook
    Failure mode: F-073 is read as "the live rail exists but is unused" when the
    entry point cannot even resolve its class.
    """
    import runtime.live_engine_hook as live_engine_hook

    assert hasattr(live_engine_hook, "HookedLiveEngine")
    assert not hasattr(live_engine_hook, "LiveEngineHook")


def test_hooked_live_engine_paper_callers_are_allowlisted():
    """Paper callers exist (PR-4c/4d). Production ACTIVE loop still does not.

    Source: LiveRailOrchestrator.from_config and pipeline_mode._live_dry_run.
    Failure mode: treating those as a live book (F-073 stays OPEN).
    """
    allowed = {
        "src/runtime/live_rail_orchestrator.py",
        "src/agent/modes/pipeline_mode.py",
    }
    call_sites = []
    for path in (_REPO / "src").rglob("*.py"):
        rel = str(path.relative_to(_REPO)).replace("\\", "/")
        for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if re.search(r"\bHookedLiveEngine\s*\(", line) and not line.lstrip().startswith("class "):
                call_sites.append(rel)
    unexpected = sorted({p for p in call_sites if p not in allowed})
    assert unexpected == [], unexpected
    assert allowed.issubset(set(call_sites))


def test_the_agent_live_entry_point_imports_hooked_live_engine():
    """PR-4d: dry_run imports HookedLiveEngine, not the absent LiveEngineHook.

    Failure mode: a rename-only fix that still calls simulate_one / dry_run_ok.
    """
    src = (_REPO / "src" / "agent" / "modes" / "pipeline_mode.py").read_text(encoding="utf-8")
    assert "LiveEngineHook" not in src
    assert "simulate_one" not in src
    assert "dry_run_ok" not in src
    tree = ast.parse(src)
    fn = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_live_dry_run"
    )
    names = [
        alias.name
        for node in ast.walk(fn)
        if isinstance(node, ast.ImportFrom)
        and node.module == "runtime.live_engine_hook"
        for alias in node.names
    ]
    assert names == ["HookedLiveEngine"]


def test_smc_is_feature_pipeline_config_not_a_promotable_gate_section():
    """SMC has no top-level config section — it tunes the pipeline, it gates nothing.

    Source: the ACTIVE config exposes parent_crt as a top-level section but carries
    SMC only as feature_pipeline.smc_max_window
    Failure mode: SMC is discussed as if it had an enable/disable gate of its own,
    inventing an authority the 39->48 schema growth never granted (F-076).
    """
    with pytest.raises(RuntimeError):
        get_prod_section("smc")
    feature_pipeline = get_prod_section("feature_pipeline")
    assert "smc_max_window" in feature_pipeline
