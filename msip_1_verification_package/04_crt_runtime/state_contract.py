"""
state_contract.py
═══════════════════════════════════════════════════════════════════════════════
Typed immutable runtime representation of CRT state contracts declared in
active_models.yaml (WHO layer).

Phase 1: validation / inspection only — never owns formulas, thresholds, or
model dispatch. Loaded objects are the sole runtime representation of the
YAML state_contracts block (no parallel STATE_REQUIRED_FM constants).
═══════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Sequence


SCHEMA_VERSION = "1.0"

# Allowed keys inside each state contract block (fail-closed on extras).
ALLOWED_STATE_CONTRACT_FIELDS: frozenset[str] = frozenset(
    {"required_fm", "config_keys", "eligible_models"}
)


@dataclass(frozen=True, slots=True)
class StateContract:
    """Immutable contract for one CRT state (declaration, not execution)."""

    state_id: str
    required_fm: tuple[str, ...]
    config_keys: tuple[str, ...]
    eligible_models: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.state_id or not isinstance(self.state_id, str):
            raise ValueError("StateContract.state_id must be a non-empty string")
        if not self.state_id.isidentifier() and not self.state_id.replace("_", "").isalnum():
            # CRT states are SCREAMING_SNAKE; allow underscores + alnum only.
            if not all(c.isalnum() or c == "_" for c in self.state_id):
                raise ValueError(f"StateContract.state_id invalid: {self.state_id!r}")


@dataclass(frozen=True, slots=True)
class StateContractBundle:
    """
    Full validated bundle: one StateContract per CRT state + declared graph.

    ``transitions`` holds YAML valid_transitions (string keys). Phase-Topology
    converts this into the StateMachine instance graph via state_topology.
    Module VALID_TRANSITIONS remains the code seed + loader parity baseline.
    """

    schema_version: str
    contracts: Mapping[str, StateContract]
    transitions: Mapping[str, tuple[str, ...]]
    source_path: str

    def get(self, state_id: str) -> StateContract:
        try:
            return self.contracts[state_id]
        except KeyError as exc:
            raise KeyError(
                f"No StateContract for state_id={state_id!r}; "
                f"known={sorted(self.contracts)}"
            ) from exc

    def state_ids(self) -> tuple[str, ...]:
        return tuple(self.contracts.keys())


def freeze_bundle(
    contracts: dict[str, StateContract],
    transitions: dict[str, tuple[str, ...]],
    *,
    schema_version: str,
    source_path: str,
) -> StateContractBundle:
    """Build a bundle with MappingProxyType maps (immutable view)."""
    return StateContractBundle(
        schema_version=schema_version,
        contracts=MappingProxyType(dict(contracts)),
        transitions=MappingProxyType({k: tuple(v) for k, v in transitions.items()}),
        source_path=source_path,
    )


def _as_str_tuple(values: Sequence[object], *, field: str, state_id: str) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        raise TypeError(
            f"state_contracts.{state_id}.{field} must be a list, got {type(values).__name__}"
        )
    out: list[str] = []
    seen: set[str] = set()
    for i, v in enumerate(values):
        if isinstance(v, bool) or isinstance(v, (int, float)):
            raise ValueError(
                f"state_contracts.{state_id}.{field}[{i}] must be a string id, "
                f"not a numeric/boolean value ({v!r}) — thresholds/formulas forbidden"
            )
        if not isinstance(v, str):
            raise TypeError(
                f"state_contracts.{state_id}.{field}[{i}] must be str, got {type(v).__name__}"
            )
        if not v.strip():
            raise ValueError(f"state_contracts.{state_id}.{field}[{i}] is empty")
        # Reject formula / expression injection
        if any(ch in v for ch in ("=", "*", "/", "(", ")", " ", "\t", "\n")):
            raise ValueError(
                f"state_contracts.{state_id}.{field}[{i}]={v!r} looks like an "
                f"expression/formula — only bare IDs allowed"
            )
        if v in seen:
            raise ValueError(
                f"state_contracts.{state_id}.{field}: duplicate id {v!r}"
            )
        seen.add(v)
        out.append(v)
    return tuple(out)


def parse_state_contract(state_id: str, raw: object) -> StateContract:
    """Parse one state block; fail-closed on unknown fields / bad types."""
    if not isinstance(raw, dict):
        raise TypeError(
            f"state_contracts.{state_id} must be a mapping, got {type(raw).__name__}"
        )
    unknown = set(raw.keys()) - ALLOWED_STATE_CONTRACT_FIELDS
    if unknown:
        raise ValueError(
            f"state_contracts.{state_id}: unknown field(s) {sorted(unknown)}; "
            f"allowed={sorted(ALLOWED_STATE_CONTRACT_FIELDS)}"
        )
    for req in ALLOWED_STATE_CONTRACT_FIELDS:
        if req not in raw:
            raise ValueError(
                f"state_contracts.{state_id}: missing required field {req!r}"
            )
    return StateContract(
        state_id=state_id,
        required_fm=_as_str_tuple(raw["required_fm"], field="required_fm", state_id=state_id),
        config_keys=_as_str_tuple(raw["config_keys"], field="config_keys", state_id=state_id),
        eligible_models=_as_str_tuple(
            raw["eligible_models"], field="eligible_models", state_id=state_id
        ),
    )
