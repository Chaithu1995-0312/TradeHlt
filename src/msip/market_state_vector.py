"""MarketStateVector value object — schema pin MARKET_STATE_VECTOR_SCHEMA_V1."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping

SCHEMA_VERSION = "1.0.0"

# Field authority classes from design contract
AUTHORITY_WHAT = frozenset(
    {
        "GOVERNED_OBSERVABLE",
        "DETERMINISTIC_DERIVED_WHAT",
    }
)
AUTHORITY_HOW = "INTERPRETED_STATE_LABEL_HOW"
AUTHORITY_OBS = "OBSERVATIONAL_JOIN_ONLY"

# dimension_name → field → authority (subset used for validation)
FIELD_AUTHORITY: dict[str, dict[str, str]] = {
    "structure_state": {
        "higher_high": "DETERMINISTIC_DERIVED_WHAT",
        "lower_low": "DETERMINISTIC_DERIVED_WHAT",
        "break_of_structure": "DETERMINISTIC_DERIVED_WHAT",
        "liquidity_sweep": "DETERMINISTIC_DERIVED_WHAT",
        "sweep_detected": "DETERMINISTIC_DERIVED_WHAT",
        "structure_label": AUTHORITY_HOW,
    },
    "liquidity_state": {
        "liquidity_distance": "DETERMINISTIC_DERIVED_WHAT",
        "liquidity_pressure_score": "DETERMINISTIC_DERIVED_WHAT",
        "liquidity_band_label": AUTHORITY_HOW,
    },
    "volatility_state": {
        "volatility_regime": "DETERMINISTIC_DERIVED_WHAT",
        "atr": "DETERMINISTIC_DERIVED_WHAT",
        "volatility_ratio": "DETERMINISTIC_DERIVED_WHAT",
        "volatility_band_label": AUTHORITY_HOW,
    },
    "session_state": {
        "session": "DETERMINISTIC_DERIVED_WHAT",
        "hour_of_day": "GOVERNED_OBSERVABLE",
        "session_policy_label": AUTHORITY_HOW,
    },
    "trend_state": {
        "trend_strength": "DETERMINISTIC_DERIVED_WHAT",
        "trend_bias": "DETERMINISTIC_DERIVED_WHAT",
        "ema_fast": "DETERMINISTIC_DERIVED_WHAT",
        "ema_slow": "DETERMINISTIC_DERIVED_WHAT",
        "trend_band_label": AUTHORITY_HOW,
    },
    "candle_quality_state": {
        "body_ratio": "DETERMINISTIC_DERIVED_WHAT",
        "body_size": "DETERMINISTIC_DERIVED_WHAT",
        "wick_size": "DETERMINISTIC_DERIVED_WHAT",
        "candle_quality_label": AUTHORITY_HOW,
    },
    "crt_phase_observation": {
        "crt_state": AUTHORITY_OBS,
        "observed": AUTHORITY_OBS,
    },
}

HOW_LABEL_FIELDS: frozenset[str] = frozenset(
    {
        "structure_label",
        "liquidity_band_label",
        "volatility_band_label",
        "session_policy_label",
        "trend_band_label",
        "candle_quality_label",
    }
)


@dataclass(frozen=True)
class CrtPhaseObservation:
    crt_state: str | None
    observed: bool
    bar_index: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "crt_state": self.crt_state,
            "observed": self.observed,
            "bar_index": self.bar_index,
        }


def _jsonable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return float(value)
    if isinstance(value, str):
        return value
    # numpy scalars
    try:
        import numpy as np

        if isinstance(value, np.generic):
            return _jsonable(value.item())
    except Exception:
        pass
    return value


@dataclass
class MarketStateVector:
    """Immutable-by-convention shadow observation for one bar.

    shadow_flags are hard-wired false — cannot influence CRT/execution/events.
    """

    schema_version: str
    symbol: str
    timeframe: str
    bar_timestamp: str
    bar_index: int | None
    dimensions: dict[str, dict[str, Any]]
    provenance: dict[str, Any]
    status: str  # COMPLETE | PARTIAL | INVALID_HOW
    shadow_flags: dict[str, bool] = field(
        default_factory=lambda: {
            "affects_crt": False,
            "affects_execution": False,
            "affects_events": False,
        }
    )

    def __post_init__(self) -> None:
        # Enforce hard flags even if caller passes wrong values
        self.shadow_flags = {
            "affects_crt": False,
            "affects_execution": False,
            "affects_events": False,
        }
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(
                f"schema_version {self.schema_version!r} != pin {SCHEMA_VERSION!r}"
            )
        for flag in ("affects_crt", "affects_execution", "affects_events"):
            if self.shadow_flags.get(flag) is not False:
                raise ValueError(f"shadow_flags.{flag} MUST_BE_FALSE")

    def to_dict(self) -> dict[str, Any]:
        dims_out: dict[str, Any] = {}
        for dname, payload in self.dimensions.items():
            dims_out[dname] = {
                k: _jsonable(v) for k, v in sorted(payload.items(), key=lambda x: x[0])
            }
        return {
            "schema_version": self.schema_version,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "bar_timestamp": str(self.bar_timestamp),
            "bar_index": self.bar_index,
            "status": self.status,
            "dimensions": dict(sorted(dims_out.items(), key=lambda x: x[0])),
            "provenance": self.provenance,
            "shadow_flags": {
                "affects_crt": False,
                "affects_execution": False,
                "affects_events": False,
            },
        }

    def has_how_labels(self) -> bool:
        for payload in self.dimensions.values():
            for k, v in payload.items():
                if k in HOW_LABEL_FIELDS and v is not None:
                    return True
        return False


def validate_field_authorities(dimensions: Mapping[str, Mapping[str, Any]]) -> list[str]:
    """Return list of unknown field names (non-blocking warnings for extra keys)."""
    unknown: list[str] = []
    for dname, payload in dimensions.items():
        known = FIELD_AUTHORITY.get(dname)
        if known is None:
            unknown.append(f"unknown_dimension:{dname}")
            continue
        for key in payload:
            if key not in known and key not in ("confidence",):
                unknown.append(f"{dname}.{key}")
    return unknown
