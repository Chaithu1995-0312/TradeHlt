"""
Floor for the generated CRT state identity — CH-crt-state-generation-v1 (2026-08-31).

`CRTState`, `VALID_TRANSITIONS`, `PARENT_TIMEFRAME_STATES` and `EXECUTION_TIMEFRAME_STATES` are
emitted from `active_models.yaml` by `scripts/maintenance/gen_crt_state_identity.py` into
`src/config_layer/_crt_state_generated.py`, and re-exported by `config_layer.state_identity`.

WHAT THIS FLOOR IS FOR, AND WHAT IT IS NOT
-------------------------------------------
Generating from `active_models.yaml` converts two pre-existing guards --
`tests/test_crt_state_invariants.py` (active_models <-> code) and the runtime
`state_contract_loader._validate_transition_graph` -- from INDEPENDENT cross-record drift
detectors into FRESHNESS checks, because both sides now derive from one file. That is a real
downgrade, stated plainly rather than glossed. This floor is what replaces the lost independence
on that axis: it pins the generated OUTPUT against values transcribed by hand from the
pre-generation `state_identity.py`, so the generator producing something different is caught even
though YAML and code now agree with each other by construction.

Genuinely independent guards that are UNAFFECTED (different source file, not the generation
source): `tests/test_crt_states_yaml_transition_parity.py` (SK-0) and
`tests/test_crt_states_yaml_state_names.py` (Phase F1), both of which compare against
`configs/formulas/market_crt_states.yaml`.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "src"))

from config_layer.state_identity import (  # noqa: E402
    CRTState,
    EXECUTION_TIMEFRAME_STATES,
    PARENT_TIMEFRAME_STATES,
    VALID_TRANSITIONS,
)

_GEN = _REPO / "scripts" / "maintenance" / "gen_crt_state_identity.py"

# Transcribed BY HAND from state_identity.py as it stood BEFORE generation (2026-08-31).
# This is the anchor: it does not come from the YAML the generator reads, so it catches a
# generator that faithfully renders a WRONG source just as well as a stale artifact.
_PRE_GENERATION_VALUES = {
    "RANGE": 1, "SHADOW_PENDING": 2, "SWEEP": 3, "DISPLACEMENT": 4, "EXPANSION": 5,
    "EXPIRED": 6, "RETEST": 7, "EXECUTION": 8, "RESOLUTION": 9,
    "RANGE_C1": 10, "MANIPULATION_C2": 11, "DISTRIBUTION_C3": 12,
}
_PRE_GENERATION_TRANSITIONS = {
    "RANGE": ["SWEEP", "SHADOW_PENDING"],
    "SHADOW_PENDING": ["SWEEP", "RANGE"],
    "SWEEP": ["DISPLACEMENT", "EXPANSION", "RANGE"],
    "DISPLACEMENT": ["EXPANSION", "RANGE"],
    "EXPANSION": ["RETEST", "EXPIRED", "RANGE"],
    "EXPIRED": ["RANGE"],
    "RETEST": ["EXECUTION", "RANGE"],
    "EXECUTION": ["RESOLUTION"],
    "RESOLUTION": ["RANGE"],
    "RANGE_C1": ["MANIPULATION_C2", "RANGE_C1"],
    "MANIPULATION_C2": ["DISTRIBUTION_C3", "RANGE_C1"],
    "DISTRIBUTION_C3": ["RANGE_C1"],
}
_PRE_GENERATION_PARENT = {"RANGE_C1", "MANIPULATION_C2", "DISTRIBUTION_C3"}


def _load_generator():
    spec = importlib.util.spec_from_file_location("gen_crt_state_identity", _GEN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_enum_name_to_value_map_is_unchanged_by_generation():
    """`auto()` values are positional and reach user-visible strings via `.value`, so a
    reordered `state_list` would silently renumber them. Pin the whole map."""
    assert {s.name: s.value for s in CRTState} == _PRE_GENERATION_VALUES


def test_transition_graph_is_unchanged_by_generation():
    """Target ORDER is compared too, not just edge sets -- the generator preserves it."""
    actual = {k.name: [t.name for t in v] for k, v in VALID_TRANSITIONS.items()}
    assert actual == _PRE_GENERATION_TRANSITIONS


def test_partition_is_unchanged_by_generation():
    assert {s.name for s in PARENT_TIMEFRAME_STATES} == _PRE_GENERATION_PARENT
    assert {s.name for s in EXECUTION_TIMEFRAME_STATES} == (
        set(_PRE_GENERATION_VALUES) - _PRE_GENERATION_PARENT
    )
    assert len(EXECUTION_TIMEFRAME_STATES) == 9
    assert not (PARENT_TIMEFRAME_STATES & EXECUTION_TIMEFRAME_STATES), "partition must be disjoint"


def test_committed_artifact_is_current():
    """`--check` must pass: the committed file equals a fresh render."""
    proc = subprocess.run(
        [sys.executable, str(_GEN), "--check"],
        cwd=str(_REPO), capture_output=True, text=True,
    )
    assert proc.returncode == 0, f"generated artifact is stale:\n{proc.stdout}\n{proc.stderr}"


def test_state_identity_reexports_the_generated_objects():
    """Re-export must be the SAME object, not a copy -- `is` comparisons are used across the
    codebase and a duplicate enum would break every one of them."""
    from config_layer import _crt_state_generated as gen
    from config_layer import state_identity as si
    assert si.CRTState is gen.CRTState
    assert si.VALID_TRANSITIONS is gen.VALID_TRANSITIONS
    assert si.PARENT_TIMEFRAME_STATES is gen.PARENT_TIMEFRAME_STATES


def test_hand_authored_symbols_survived_the_rewire():
    """Direction / RejectReason / CRTConfig are NOT generated and must remain."""
    from config_layer.state_identity import CRTConfig, Direction, RejectReason
    assert [d.value for d in Direction] == ["LONG", "SHORT", "NONE"]
    assert len(list(RejectReason)) == 6
    assert len(CRTConfig.__dataclass_fields__) == 53


# ── Mutation tests: prove the generator actually rejects bad sources ──────────────────────

def test_generator_rejects_state_count_mismatch(monkeypatch):
    gen = _load_generator()
    monkeypatch.setattr(gen, "_load_runtime", lambda: {
        "states": 99, "state_list": ["RANGE"], "valid_transitions": {"RANGE": []},
        "parent_timeframe_states": [],
    })
    with __import__("pytest").raises(SystemExit, match="states=99"):
        gen.render()


def test_generator_rejects_transition_to_undeclared_state(monkeypatch):
    gen = _load_generator()
    monkeypatch.setattr(gen, "_load_runtime", lambda: {
        "states": 1, "state_list": ["RANGE"], "valid_transitions": {"RANGE": ["GHOST"]},
        "parent_timeframe_states": [],
    })
    with __import__("pytest").raises(SystemExit, match="undeclared states"):
        gen.render()


def test_generator_rejects_parent_state_not_in_state_list(monkeypatch):
    gen = _load_generator()
    monkeypatch.setattr(gen, "_load_runtime", lambda: {
        "states": 1, "state_list": ["RANGE"], "valid_transitions": {"RANGE": []},
        "parent_timeframe_states": ["NOT_A_STATE"],
    })
    with __import__("pytest").raises(SystemExit, match="parent_timeframe_states"):
        gen.render()


def test_generator_rejects_transitions_keyset_mismatch(monkeypatch):
    gen = _load_generator()
    monkeypatch.setattr(gen, "_load_runtime", lambda: {
        "states": 2, "state_list": ["RANGE", "SWEEP"], "valid_transitions": {"RANGE": []},
        "parent_timeframe_states": [],
    })
    with __import__("pytest").raises(SystemExit, match="valid_transitions keys"):
        gen.render()
