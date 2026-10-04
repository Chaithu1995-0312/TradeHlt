"""
state_topology.py
═══════════════════════════════════════════════════════════════════════════════
Phase-Topology — runtime CRT state identity + legal transition graph from
active_models.yaml (via StateContractBundle).

Authority after this phase:
  WHO  active_models.yaml valid_transitions / state_contracts  → loaded graph
  Code CRTState enum                                        → structural identity set
  Code VALID_TRANSITIONS module dict                        → seed + parity baseline
                                                              (loader still fails closed
                                                              if YAML ≠ code edges)
  Python try_* guards                                       → unchanged control flow

Never:
  - invent states not in CRTState
  - eval YAML expressions
  - dispatch models
  - change detector/guard algorithms
═══════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Mapping, Sequence

from config_layer.crt_engine_v2 import CRTState, VALID_TRANSITIONS


class StateTopologyError(ValueError):
    """Fail-closed topology construction error."""


def _name_to_state(name: str) -> CRTState:
    try:
        return CRTState[name]
    except KeyError as exc:
        raise StateTopologyError(
            f"Unknown CRT state identity {name!r} — not a CRTState member. "
            f"Known={sorted(s.name for s in CRTState)}"
        ) from exc


def build_runtime_transition_graph(
    transitions: Mapping[str, Sequence[str]],
) -> Mapping[CRTState, tuple[CRTState, ...]]:
    """
    Convert string-keyed WHO transitions into an immutable CRTState graph.

    Fail-closed on unknown state names or empty source set.
    """
    if not transitions:
        raise StateTopologyError("transition graph is empty")

    graph: dict[CRTState, tuple[CRTState, ...]] = {}
    for src_name, targets in transitions.items():
        if not isinstance(src_name, str):
            raise StateTopologyError(
                f"transition source must be str, got {type(src_name).__name__}"
            )
        src = _name_to_state(src_name)
        if not isinstance(targets, (list, tuple)):
            raise StateTopologyError(
                f"valid_transitions.{src_name} must be a sequence, "
                f"got {type(targets).__name__}"
            )
        ordered: list[CRTState] = []
        seen: set[CRTState] = set()
        for t_name in targets:
            if not isinstance(t_name, str):
                raise StateTopologyError(
                    f"valid_transitions.{src_name} target must be str, got {t_name!r}"
                )
            dst = _name_to_state(t_name)
            if dst in seen:
                raise StateTopologyError(
                    f"valid_transitions.{src_name}: duplicate target {t_name!r}"
                )
            seen.add(dst)
            ordered.append(dst)
        graph[src] = tuple(ordered)

    # Every CRTState must appear as a source (complete identity set)
    code_states = set(CRTState)
    declared = set(graph)
    if declared != code_states:
        raise StateTopologyError(
            f"state identity set incomplete: "
            f"missing={sorted(s.name for s in code_states - declared)} "
            f"extra={sorted(s.name for s in declared - code_states)}"
        )

    return MappingProxyType(graph)


def build_runtime_transition_graph_from_bundle(bundle) -> Mapping[CRTState, tuple[CRTState, ...]]:
    """Build graph from a StateContractBundle.transitions mapping."""
    return build_runtime_transition_graph(bundle.transitions)


def module_seed_transition_graph() -> Mapping[CRTState, tuple[CRTState, ...]]:
    """
    Immutable view of the module-level VALID_TRANSITIONS seed.

    Used when StateMachine is constructed without a WHO-loaded graph
    (unit tests / legacy call sites). Production CRTEngine always loads WHO first.
    """
    return MappingProxyType(
        {src: tuple(targets) for src, targets in VALID_TRANSITIONS.items()}
    )


def graphs_equal(
    a: Mapping[CRTState, Sequence[CRTState]],
    b: Mapping[CRTState, Sequence[CRTState]],
) -> bool:
    """Set-equality of edges (order of targets ignored)."""
    if set(a) != set(b):
        return False
    for k in a:
        if set(a[k]) != set(b[k]):
            return False
    return True
