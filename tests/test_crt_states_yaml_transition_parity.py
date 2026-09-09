"""CRT transition-graph parity — configs/formulas/market_crt_states.yaml vs the code seed.

SK-0 (CH-structural-kernel, 2026-08-18).

The repository declares the CRT transition graph in THREE places:

  1. src/config_layer/state_identity.py :: VALID_TRANSITIONS   — the §4.0 Tier-1 authority
  2. active_models.yaml :: crt.runtime.valid_transitions       — ALREADY gated, fail-closed at
     every CRTEngine() construction by
     config_layer.state_contract_loader._validate_transition_graph
  3. configs/formulas/market_crt_states.yaml :: valid_transitions — the CRTStateResolver's
     authority, and until this module UNGATED

(3) is the gap this file closes. Its own header comment states the intent —
"Kept in sync per CLAUDE.md §6.2 rule 6 (two records of one edge set must not silently
diverge)" — but nothing mechanically enforced it, so the sync was a convention rather
than a contract.

THE ONE DECLARED DIFFERENCE
---------------------------
`SHADOW_PENDING` carries an extra `EXPANSION` target in the YAML. That is DELIBERATE and
is documented in the YAML at the edge itself (the `B1d` comment): the engine's
`StateMachine.try_shadow_pending_to_expansion` performs SHADOW_PENDING→SWEEP→EXPANSION as
two internal transitions inside ONE `process_candle`, so a resolver observing only the
per-bar EXIT state sees a direct SHADOW_PENDING→EXPANSION edge.

It is pinned below as an explicit allowance, NOT waved through — and the pin is
self-justifying in two directions:

  * `test_allowance_is_grounded_in_engine_behaviour` proves the collapse really is a
    two-step walk through SWEEP, behaviourally (not by grepping a comment — the F-068
    lesson: a code comment cited as evidence did not exist in source).
  * `test_no_stale_allowances` fails if the code seed ever gains the edge directly, at
    which point the allowance is obsolete and must be deleted rather than left to rot.
    This mirrors the stale-pin ratchet in scripts/analysis/feature_math_lint.py.

Grants no authority (§6.5). Declaration parity only — this says nothing about whether the
resolver's *construction* matches the engine's (it does not; see F-069 and ontology node
UNK-006, which stays open).
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
import yaml

from config_layer.crt_engine_v2 import (
    Candle,
    CRTConfig,
    CRTState,
    Direction,
    EngineState,
    StateMachine,
)
from config_layer.state_identity import VALID_TRANSITIONS

_YAML_PATH = Path(__file__).resolve().parents[1] / "configs" / "formulas" / "market_crt_states.yaml"

# ── Declared allowances: (source_state, extra_target_in_yaml) -> why it is legitimate ──
# Add an entry ONLY with a source-verified reason. An allowance that stops being needed
# is a test failure, not dead weight.
_DECLARED_ALLOWANCES: dict[tuple[str, str], str] = {
    ("SHADOW_PENDING", "EXPANSION"): (
        "B1d: StateMachine.try_shadow_pending_to_expansion collapses SHADOW_PENDING -> SWEEP "
        "-> EXPANSION into one process_candle; a per-bar exit-state observer sees the direct "
        "edge. Proven behaviourally by test_allowance_is_grounded_in_engine_behaviour."
    ),
}


def _yaml_graph() -> dict[str, set[str]]:
    doc = yaml.safe_load(_YAML_PATH.read_text(encoding="utf-8"))
    raw = doc.get("valid_transitions")
    assert isinstance(raw, dict), "market_crt_states.yaml: valid_transitions must be a mapping"
    return {src: set(targets) for src, targets in raw.items()}


def _code_graph() -> dict[str, set[str]]:
    return {src.name: {t.name for t in targets} for src, targets in VALID_TRANSITIONS.items()}


def test_state_identity_sets_match() -> None:
    """Both records must describe the SAME set of states — all 12, parent sub-graph included."""
    assert set(_yaml_graph()) == set(_code_graph())


def test_every_yaml_state_is_a_real_crtstate() -> None:
    """No YAML-only state names: the enum is the identity authority (§4.0 Tier 1)."""
    known = {s.name for s in CRTState}
    unknown = sorted(set(_yaml_graph()) - known)
    assert not unknown, f"market_crt_states.yaml declares non-CRTState names: {unknown}"


def test_edge_sets_match_modulo_declared_allowances() -> None:
    """Edge-set equality after subtracting the explicitly declared allowances.

    The YAML may not DROP an edge the code has, and may not ADD one that is not pinned
    above with a reason.
    """
    y, c = _yaml_graph(), _code_graph()

    missing: list[str] = []
    extra: list[str] = []
    for src in sorted(c):
        allowed_extra = {tgt for (s, tgt) in _DECLARED_ALLOWANCES if s == src}
        for gone in sorted(c[src] - y[src]):
            missing.append(f"{src} -> {gone}")
        for added in sorted(y[src] - c[src] - allowed_extra):
            extra.append(f"{src} -> {added}")

    assert not missing, (
        "market_crt_states.yaml is MISSING edges present in state_identity.VALID_TRANSITIONS: "
        f"{missing}. The code seed is the authority (§4.0 Tier 1) — fix the YAML."
    )
    assert not extra, (
        "market_crt_states.yaml declares edges absent from state_identity.VALID_TRANSITIONS: "
        f"{extra}. Either the edge is wrong, or it is a deliberate observer-level collapse — "
        "in which case add it to _DECLARED_ALLOWANCES with a source-verified reason and a "
        "behavioural test, as SHADOW_PENDING -> EXPANSION has."
    )


def test_no_stale_allowances() -> None:
    """An allowance whose edge now exists in the code seed is obsolete — delete it.

    Same ratchet discipline as feature_math_lint's stale-pin check: a pin that no longer
    corresponds to a live divergence silently weakens the gate.
    """
    c = _code_graph()
    stale = [
        f"{src} -> {tgt}"
        for (src, tgt) in _DECLARED_ALLOWANCES
        if tgt in c.get(src, set())
    ]
    assert not stale, (
        f"stale allowance(s) {stale}: the code seed now declares this edge directly, so the "
        "allowance is no longer needed. Remove it from _DECLARED_ALLOWANCES."
    )


def test_allowance_is_grounded_in_engine_behaviour() -> None:
    """SHADOW_PENDING -> EXPANSION really is a two-step walk through SWEEP.

    Behavioural, not textual. F-068's lesson was that a code comment cited as evidence did
    not exist in source; an allowance justified only by a comment is worth nothing.
    """
    cfg = CRTConfig()
    sm = StateMachine(cfg)
    st = EngineState()
    st.current_state = CRTState.SHADOW_PENDING
    st.atr_abs = 1.0

    bar = Candle(
        timestamp=datetime(2026, 8, 18, 0, 0, 0),
        open=100.0, high=112.0, low=99.0, close=111.0, volume=1.0, index=5,
    )
    st.pending_displacement_candle = bar
    st.pending_displacement_dir = Direction.LONG
    st.pending_displacement_formed_idx = 3

    assert sm.try_shadow_pending_to_expansion(st, bar) is True, (
        "the collapse path did not fire — the allowance's premise is unverified"
    )
    assert st.current_state is CRTState.EXPANSION, (
        "exit state must be EXPANSION: that is why a per-bar observer records the direct edge"
    )
    # The intermediate SWEEP is what makes the code seed's [SWEEP, RANGE] correct AND the
    # YAML's extra EXPANSION target correct — two records of one behaviour, at different
    # observation granularity.
    assert CRTState.SWEEP in VALID_TRANSITIONS[CRTState.SHADOW_PENDING]
    assert CRTState.EXPANSION in VALID_TRANSITIONS[CRTState.SWEEP]


@pytest.mark.parametrize("src,tgt", sorted(_DECLARED_ALLOWANCES))
def test_every_allowance_carries_a_reason(src: str, tgt: str) -> None:
    reason = _DECLARED_ALLOWANCES[(src, tgt)]
    assert reason and len(reason.strip()) > 40, (
        f"allowance {src} -> {tgt} needs a substantive source-verified reason"
    )
