"""market_reality_contract.py — read-only loader/validator for
`configs/market_reality/market_reality_v1.yaml`.

CH-htfcrt-parent-candle-smc-v1 (2026-08-15): this file was previously loaded by NOTHING (grep-
confirmed: zero Python readers) and guarded by NOTHING (zero tests) — so a duplicate top-level
`authority` key silently dropped the WHO-layer marker on every parse, with nothing to catch it.
This module closes that gap with the minimum needed to make the contract inspectable and its
own internal invariants machine-checked, WITHOUT granting the file any new authority: it is a
validating loader/accessor, not a new consumer wiring the Market Reality layer into the spine.
The file's own doctrine (`enabled: false`, "CONTRACT ONLY — no runtime") is unchanged.

CONTRACT CHECKS this loader enforces (fail-closed — a violation raises, never silently repairs):
  - the file parses as YAML and is a mapping
  - `enabled` is exactly `False` (flipping it is a deliberate, reviewed decision this module
    does not make and will not silently tolerate a drift on)
  - the top-level `authority` scalar (WHO-layer marker) and `authority_capabilities` mapping
    (decision-authority flags) are BOTH present and are NOT the same key — the exact defect
    class this module exists to prevent from recurring silently
  - every entry in `dimensions` carries the `_dimension_defaults` anchor's required fields
  - every entry in `dimensions` / `temporal_derivations` has `enabled: false` (per-entry, not
    just the file-level switch — belt and suspenders against a partial, unreviewed activation)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_PATH = _REPO_ROOT / "configs" / "market_reality" / "market_reality_v1.yaml"

_REQUIRED_DIMENSION_FIELDS = (
    "enabled", "min_evidence", "thresholds", "hysteresis", "persistence",
    "confidence_policy", "insufficient_evidence_behavior", "state_labels", "evidence",
)


class MarketRealityContractError(ValueError):
    """Fail-closed validation error — the contract file itself is malformed or drifted."""


@dataclass(frozen=True)
class MarketRealityContract:
    """Validated, read-only view of the Market Reality configuration contract."""

    schema_version: str
    who_authority: str                       # top-level `authority` scalar
    enabled: bool                             # hard fail-closed master switch
    mode: str
    dimensions: dict
    temporal_derivations: dict
    authority_capabilities: dict
    raw: dict                                 # full parsed document, for callers needing more

    def dimension_names(self) -> list[str]:
        return sorted(self.dimensions)

    def dimensions_with_evidence(self) -> list[str]:
        """Dimension names whose `evidence` list is non-empty — i.e. at least one canonical
        or registered feature currently supports them (still `enabled: false` regardless)."""
        return sorted(
            name for name, spec in self.dimensions.items()
            if (spec.get("evidence") or [])
        )

    def any_capability_granted(self) -> bool:
        """True iff any `authority_capabilities` flag is not False — should always be False;
        exposed so a caller can assert this explicitly rather than re-deriving the check."""
        return any(bool(v) for v in self.authority_capabilities.values())


def load_market_reality_contract(path: "Path | str | None" = None) -> MarketRealityContract:
    """Load and validate the Market Reality contract. Raises `MarketRealityContractError` on
    any structural violation — never repairs, never falls back to a default."""
    import yaml

    p = Path(path) if path is not None else _DEFAULT_PATH
    if not p.exists():
        raise MarketRealityContractError(f"market reality contract not found: {p}")

    doc = yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise MarketRealityContractError(f"{p}: root must be a mapping, got {type(doc).__name__}")

    for key in ("schema_version", "authority", "enabled", "mode", "dimensions",
                "temporal_derivations", "authority_capabilities"):
        if key not in doc:
            raise MarketRealityContractError(f"{p}: missing required top-level key {key!r}")

    who_authority = doc["authority"]
    if not isinstance(who_authority, str) or not who_authority:
        raise MarketRealityContractError(
            f"{p}: top-level `authority` must be a non-empty string (WHO-layer marker), "
            f"got {who_authority!r} — a duplicate `authority:` key elsewhere in the file "
            f"would silently produce this (the exact 2026-08-15 defect this loader guards)."
        )

    capabilities = doc["authority_capabilities"]
    if not isinstance(capabilities, dict):
        raise MarketRealityContractError(
            f"{p}: `authority_capabilities` must be a mapping, got {type(capabilities).__name__}"
        )
    if any(bool(v) for v in capabilities.values()):
        raise MarketRealityContractError(
            f"{p}: authority_capabilities grants a capability (expected all-False, fail-closed): "
            f"{capabilities!r}"
        )

    if doc["enabled"] is not False:
        raise MarketRealityContractError(
            f"{p}: top-level `enabled` must be exactly False (fail-closed contract) — "
            f"got {doc['enabled']!r}. Flipping this is a deliberate, reviewed activation "
            f"decision, not something this loader will silently pass through."
        )

    dimensions = doc["dimensions"]
    if not isinstance(dimensions, dict) or not dimensions:
        raise MarketRealityContractError(f"{p}: `dimensions` must be a non-empty mapping")

    problems: list[str] = []
    for name, spec in dimensions.items():
        if not isinstance(spec, dict):
            problems.append(f"dimensions.{name}: not a mapping")
            continue
        missing = [f for f in _REQUIRED_DIMENSION_FIELDS if f not in spec]
        if missing:
            problems.append(f"dimensions.{name}: missing fields {missing}")
        if spec.get("enabled") is not False:
            problems.append(f"dimensions.{name}: enabled must be False, got {spec.get('enabled')!r}")
    if problems:
        raise MarketRealityContractError(f"{p}: dimension contract violations:\n" + "\n".join(problems))

    temporal_derivations = doc["temporal_derivations"]
    if not isinstance(temporal_derivations, dict) or not temporal_derivations:
        raise MarketRealityContractError(f"{p}: `temporal_derivations` must be a non-empty mapping")
    for name, spec in temporal_derivations.items():
        if not isinstance(spec, dict) or spec.get("enabled") is not False:
            problems.append(f"temporal_derivations.{name}: enabled must be False")
    if problems:
        raise MarketRealityContractError(f"{p}: temporal_derivation violations:\n" + "\n".join(problems))

    return MarketRealityContract(
        schema_version=doc["schema_version"],
        who_authority=who_authority,
        enabled=doc["enabled"],
        mode=doc["mode"],
        dimensions=dimensions,
        temporal_derivations=temporal_derivations,
        authority_capabilities=capabilities,
        raw=doc,
    )
