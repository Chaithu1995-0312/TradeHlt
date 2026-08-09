"""
CRT executable state-graph parity — Phase 3 CRT Closure.

Pins docs/governance/crt_executable_state_graph.json against
config_layer.crt_engine_v2.CRTState + VALID_TRANSITIONS so the frozen graph
cannot silently drift from code.

Also encodes force-reset and shadow double-transition as intentional governance
facts (not bugs).
"""
from __future__ import annotations

import json
from pathlib import Path

from config_layer.state_identity import CRTState, VALID_TRANSITIONS

_ROOT = Path(__file__).resolve().parents[1]
_GRAPH_PATH = _ROOT / "docs" / "governance" / "crt_executable_state_graph.json"


def _load_graph() -> dict:
    assert _GRAPH_PATH.is_file(), f"missing CRT state graph artifact: {_GRAPH_PATH}"
    with open(_GRAPH_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def test_graph_file_exists_and_schema():
    g = _load_graph()
    assert g.get("schema") == "crt_executable_state_graph.v1"
    assert g.get("phase") == 3
    assert g.get("phase3_status") == "PASS"
    assert g.get("state_count") == 9


def test_graph_states_match_crtstate_exactly():
    g = _load_graph()
    graph_states = {s["name"] for s in g["states"]}
    code_states = {s.name for s in CRTState}
    assert graph_states == code_states
    assert len(graph_states) == 9
    # historical drift memory (shared with test_crt_state_invariants)
    assert "CANCELLED" not in graph_states
    assert "RESOLVED" not in graph_states


def test_valid_transitions_parity_code_vs_graph_edges():
    """Every VALID_TRANSITIONS edge must appear as a governed_transition record."""
    g = _load_graph()
    code = {s.name: {t.name for t in ts} for s, ts in VALID_TRANSITIONS.items()}

    # Build set of (from,to) that are via _transition or listed as valid
    graph_edges = set()
    for edge in g["governed_transitions"]:
        graph_edges.add((edge["from"], edge["to"]))

    missing = []
    for src, targets in code.items():
        for dst in targets:
            if (src, dst) not in graph_edges:
                missing.append(f"{src}->{dst}")
    assert not missing, f"VALID_TRANSITIONS edges missing from graph: {missing}"


def test_transition_methods_only_target_legal_states():
    """Method→target pairs that use _transition must be legal in VALID_TRANSITIONS."""
    code = {s.name: {t.name for t in ts} for s, ts in VALID_TRANSITIONS.items()}
    legal_method_edges = {
        ("RANGE", "SWEEP"),
        ("RANGE", "SHADOW_PENDING"),
        ("SHADOW_PENDING", "SWEEP"),
        ("SWEEP", "DISPLACEMENT"),
        ("SWEEP", "EXPANSION"),  # shadow hop
        ("DISPLACEMENT", "EXPANSION"),
        ("EXPANSION", "RETEST"),
        ("EXPANSION", "EXPIRED"),
        ("RETEST", "EXECUTION"),
        ("EXECUTION", "RESOLUTION"),
        # EXPIRED→RANGE and *→RANGE often force-reset; RESOLUTION→RANGE force-reset
    }
    for src, dst in legal_method_edges:
        assert dst in code[src], f"illegal method edge {src}->{dst} vs VALID_TRANSITIONS"


def test_force_reset_documented_as_bypass():
    g = _load_graph()
    fr = g["force_reset_semantics"]
    assert fr["bypasses_valid_transitions"] is True
    assert fr["method"] == "StateMachine.reset_to_range"
    assert "L1508" in fr["mechanism"] or "1508" in fr["mechanism"]


def test_shadow_double_transition_documented():
    g = _load_graph()
    shadow = next(s for s in g["states"] if s["name"] == "SHADOW_PENDING")
    two_step = [b for b in shadow["behaviors"] if b.get("governed_double_transition")]
    assert two_step, "shadow two-step must be marked governed_double_transition"
    assert two_step[0]["sequence"] == ["SHADOW_PENDING→SWEEP", "SWEEP→EXPANSION"]


def test_order_dependent_rules_present():
    g = _load_graph()
    ids = {r["id"] for r in g["order_dependent_rules"]}
    required = {
        "ORD-RESET-FALLTHROUGH",
        "ORD-RETEST-BEFORE-TTL",
        "ORD-SHADOW-DOUBLE-TRANSITION",
        "ORD-ACTIVE-TRADE-BEFORE-SM",
        "ORD-SOFT-CONF-FLAG-NOT-STATE",
    }
    assert required <= ids


def test_machine_checks_block_true():
    g = _load_graph()
    mc = g["machine_checks"]
    for k, v in mc.items():
        assert v is True, f"machine check {k} not true"
