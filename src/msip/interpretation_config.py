"""HOW config for MSIP shadow — `msip_shadow` section only.

Absent section or enabled:false → Disabled (shadow off).
enabled:true with missing required keys → fail-closed at load (not mid-bar).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Mapping


SCHEMA_VERSION_PIN = "1.0.0"

# Dimension name → default WHAT source features (from MARKET_STATE_VECTOR_SCHEMA_V1)
DEFAULT_DIMENSION_SOURCES: dict[str, list[str]] = {
    "structure_state": [
        "higher_high",
        "lower_low",
        "break_of_structure",
        "liquidity_sweep",
        "sweep_detected",
    ],
    "liquidity_state": [
        "liquidity_distance",
        "liquidity_pressure_score",
    ],
    "volatility_state": [
        "volatility_regime",
        "atr",
        "volatility_ratio",
    ],
    "session_state": [
        "session",
        "hour_of_day",
    ],
    "trend_state": [
        "trend_strength",
        "trend_bias",
        "ema_fast",
        "ema_slow",
    ],
    "candle_quality_state": [
        "body_ratio",
        "body_size",
        "wick_size",
    ],
    "crt_phase_observation": [],  # observational join only
}

# Optional HOW label field name per dimension + continuous twins
HOW_LABEL_SPEC: dict[str, dict[str, Any]] = {
    "structure_state": {
        "label_field": "structure_label",
        "primary_feature": "liquidity_sweep",
        "continuous_twins": [
            "higher_high",
            "lower_low",
            "break_of_structure",
            "liquidity_sweep",
            "sweep_detected",
        ],
    },
    "liquidity_state": {
        "label_field": "liquidity_band_label",
        "primary_feature": "liquidity_distance",
        "continuous_twins": ["liquidity_distance", "liquidity_pressure_score"],
    },
    "volatility_state": {
        "label_field": "volatility_band_label",
        "primary_feature": "volatility_ratio",
        "continuous_twins": ["atr", "volatility_ratio", "volatility_regime"],
    },
    "session_state": {
        "label_field": "session_policy_label",
        "primary_feature": "session",
        "continuous_twins": ["session", "hour_of_day"],
    },
    "trend_state": {
        "label_field": "trend_band_label",
        "primary_feature": "trend_strength",
        "continuous_twins": ["trend_strength", "trend_bias"],
    },
    "candle_quality_state": {
        "label_field": "candle_quality_label",
        "primary_feature": "body_ratio",
        "continuous_twins": ["body_ratio", "wick_size"],
    },
}

FORBIDDEN_CRT_LOCAL_SOURCE_NAMES = frozenset(
    {
        "crt_local_atr",
        "crt_local_ema_fast",
        "crt_local_ema_slow",
        "crt_local_body_ratio",
        "crt_local_wick_size",
    }
)


class Disabled:
    """Sentinel: shadow is off (section absent or enabled:false)."""

    enabled: bool = False

    def __repr__(self) -> str:
        return "Disabled(msip_shadow)"


@dataclass(frozen=True)
class DimensionHowConfig:
    enabled: bool
    source_features: tuple[str, ...]
    label_bands: tuple[dict[str, Any], ...] = ()
    instrument_overrides: Mapping[str, Any] = field(default_factory=dict)
    timeframe_overrides: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MsipShadowConfig:
    """Strict HOW configuration for shadow emission."""

    enabled: bool
    config_id: str
    schema_version_required: str
    dimensions: Mapping[str, DimensionHowConfig]
    emit_disagreement_events: bool
    crt_phase_observation_enabled: bool
    output_path_template: str
    include_provenance: bool
    config_sha256: str
    raw_section: Mapping[str, Any]

    def dimension_enabled(self, name: str) -> bool:
        d = self.dimensions.get(name)
        return bool(d and d.enabled)


def _require(cfg: Mapping[str, Any], key: str) -> Any:
    if key not in cfg:
        raise KeyError(
            f"Required msip_shadow key '{key}' missing (fail-closed). "
            "Add it to the msip_shadow section or set enabled:false."
        )
    return cfg[key]


def _validate_label_bands(bands: list[Any], dim_name: str) -> tuple[dict[str, Any], ...]:
    if not bands:
        return ()
    out: list[dict[str, Any]] = []
    prev_lt: float | None = None
    for i, band in enumerate(bands):
        if not isinstance(band, dict) or "label" not in band:
            raise ValueError(
                f"msip_shadow.dimensions.{dim_name}.label_bands[{i}] "
                "must be object with 'label'"
            )
        lt = band.get("lt", band.get("max"))
        if lt is not None:
            lt_f = float(lt)
            if prev_lt is not None and lt_f < prev_lt:
                raise ValueError(
                    f"msip_shadow.dimensions.{dim_name}.label_bands must be monotonic "
                    f"(lt non-decreasing); got {lt_f} after {prev_lt}"
                )
            if not (lt_f == lt_f):  # NaN
                raise ValueError(f"label_bands lt must be finite for {dim_name}")
            prev_lt = lt_f
            out.append({"label": str(band["label"]), "lt": lt_f})
        else:
            out.append({"label": str(band["label"]), "lt": None})
    return tuple(out)


def _parse_dimension(name: str, raw: Mapping[str, Any]) -> DimensionHowConfig:
    if not isinstance(raw, dict):
        raise TypeError(f"msip_shadow.dimensions.{name} must be an object")
    enabled = bool(raw.get("enabled", True))
    default_src = DEFAULT_DIMENSION_SOURCES.get(name, [])
    src = raw.get("source_features", default_src)
    if not isinstance(src, (list, tuple)):
        raise TypeError(f"source_features for {name} must be a list")
    sources = tuple(str(s) for s in src)
    for s in sources:
        if s in FORBIDDEN_CRT_LOCAL_SOURCE_NAMES:
            raise ValueError(
                f"source_feature '{s}' is CRT-local and FORBIDDEN until parity audit "
                f"+ migration authority (dimension {name})"
            )
    bands_raw = raw.get("label_bands") or []
    if not isinstance(bands_raw, list):
        raise TypeError(f"label_bands for {name} must be a list")
    # Overrides may only carry label_bands / enables — never re-encode WHAT
    inst = raw.get("instrument_overrides") or {}
    tf = raw.get("timeframe_overrides") or {}
    if not isinstance(inst, dict) or not isinstance(tf, dict):
        raise TypeError(f"overrides for {name} must be objects")
    for omap_name, omap in (("instrument_overrides", inst), ("timeframe_overrides", tf)):
        for k, v in omap.items():
            if not isinstance(v, dict):
                raise TypeError(f"{omap_name}.{k} must be object")
            illegal = set(v.keys()) - {"label_bands", "enabled"}
            if illegal:
                raise ValueError(
                    f"{omap_name}.{k} may only set label_bands/enabled (HOW); "
                    f"illegal keys: {sorted(illegal)}"
                )
    return DimensionHowConfig(
        enabled=enabled,
        source_features=sources,
        label_bands=_validate_label_bands(list(bands_raw), name),
        instrument_overrides=dict(inst),
        timeframe_overrides=dict(tf),
    )


def config_section_sha256(section: Mapping[str, Any]) -> str:
    payload = json.dumps(section, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_msip_shadow_config(prod_cfg: Mapping[str, Any]) -> MsipShadowConfig | Disabled:
    """Load msip_shadow from a production-like config dict.

    Absent section → Disabled.
    enabled false/missing → Disabled.
    enabled true → fail-closed on required keys.
    """
    section = prod_cfg.get("msip_shadow")
    if section is None:
        return Disabled()
    if not isinstance(section, dict):
        raise TypeError("msip_shadow section must be an object")
    if not bool(section.get("enabled", False)):
        return Disabled()

    config_id = str(_require(section, "config_id"))
    schema_ver = str(_require(section, "schema_version_required"))
    if schema_ver != SCHEMA_VERSION_PIN:
        raise ValueError(
            f"msip_shadow.schema_version_required={schema_ver!r} does not match "
            f"pinned MARKET_STATE_VECTOR schema {SCHEMA_VERSION_PIN!r}"
        )
    dims_raw = _require(section, "dimensions")
    if not isinstance(dims_raw, dict) or not dims_raw:
        raise ValueError("msip_shadow.dimensions must be a non-empty object when enabled")

    dimensions: dict[str, DimensionHowConfig] = {}
    for name, raw in dims_raw.items():
        dimensions[str(name)] = _parse_dimension(str(name), raw)

    if not any(d.enabled for d in dimensions.values()):
        raise ValueError("enabled:true requires at least one enabled dimension")

    comparison = section.get("comparison") or {}
    if not isinstance(comparison, dict):
        raise TypeError("msip_shadow.comparison must be an object")
    output = section.get("output") or {}
    if not isinstance(output, dict):
        raise TypeError("msip_shadow.output must be an object")

    return MsipShadowConfig(
        enabled=True,
        config_id=config_id,
        schema_version_required=schema_ver,
        dimensions=dimensions,
        emit_disagreement_events=bool(comparison.get("emit_disagreement_events", True)),
        crt_phase_observation_enabled=bool(
            comparison.get("crt_phase_observation_enabled", True)
        ),
        output_path_template=str(
            output.get("path_template", "results/msip_shadow/{run_id}/market_state.jsonl")
        ),
        include_provenance=bool(output.get("include_provenance", True)),
        config_sha256=config_section_sha256(section),
        raw_section=dict(section),
    )


def default_experimental_section(
    *,
    config_id: str = "msip_shadow_experimental_v1",
    with_how_labels: bool = False,
) -> dict[str, Any]:
    """Build a minimal experimental msip_shadow section (not production CRT config)."""
    dims: dict[str, Any] = {}
    for name, sources in DEFAULT_DIMENSION_SOURCES.items():
        entry: dict[str, Any] = {
            "enabled": True,
            "source_features": list(sources),
        }
        if with_how_labels and name in HOW_LABEL_SPEC and name != "structure_state":
            # simple two-band on primary continuous twin
            entry["label_bands"] = [
                {"label": "low", "lt": 0.5},
                {"label": "high"},
            ]
        dims[name] = entry
    return {
        "enabled": True,
        "config_id": config_id,
        "schema_version_required": SCHEMA_VERSION_PIN,
        "dimensions": dims,
        "comparison": {
            "emit_disagreement_events": True,
            "crt_phase_observation_enabled": True,
        },
        "output": {
            "path_template": "results/msip_shadow/{run_id}/market_state.jsonl",
            "include_provenance": True,
        },
    }
