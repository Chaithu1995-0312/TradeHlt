"""Shadow MarketState assembly — pure build + append-only emit.

Never mutates CRT. Never gates execution.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from features.feature_schema import FEATURE_ORDER_HASH, SCHEMA_HASH
from msip.interpretation_config import (
    HOW_LABEL_SPEC,
    Disabled,
    MsipShadowConfig,
)
from msip.market_state_vector import (
    SCHEMA_VERSION,
    CrtPhaseObservation,
    MarketStateVector,
    _jsonable,
)


@dataclass
class ProvenanceContext:
    """Run-level provenance attached to every bar."""

    config_id: str
    config_sha256: str
    repository_commit: str | None = None
    corpus_path: str | None = None
    corpus_sha256: str | None = None
    feature_schema_hash: str = SCHEMA_HASH
    feature_order_hash: str = FEATURE_ORDER_HASH
    parity_audit_refs: list[str] = field(default_factory=list)
    interpretation_schema_version: str = SCHEMA_VERSION


def observe_crt_state(snapshot: Mapping[str, Any]) -> CrtPhaseObservation:
    """Pure read of a CRT observation snapshot — must not mutate anything."""
    if not snapshot:
        return CrtPhaseObservation(crt_state=None, observed=False, bar_index=None)
    state = snapshot.get("crt_state")
    if state is None:
        state = snapshot.get("state")
    observed = bool(snapshot.get("observed", state is not None))
    bar_index = snapshot.get("bar_index")
    if bar_index is not None:
        bar_index = int(bar_index)
    return CrtPhaseObservation(
        crt_state=str(state) if state is not None else None,
        observed=observed,
        bar_index=bar_index,
    )


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return True
    except Exception:
        pass
    try:
        import numpy as np

        if isinstance(value, np.generic):
            return _is_missing(value.item())
        if value is np.nan:
            return True
    except Exception:
        pass
    return False


def _get_feature(bar_features: Mapping[str, Any], name: str) -> Any:
    if name not in bar_features:
        return None
    return bar_features[name]


def _apply_label_bands(value: Any, bands: tuple[dict[str, Any], ...]) -> str | None:
    if not bands or _is_missing(value):
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    for band in bands:
        lt = band.get("lt")
        if lt is None:
            return str(band["label"])
        if v < float(lt):
            return str(band["label"])
    return str(bands[-1]["label"])


def _resolve_label_bands(
    dim_cfg: Any,
    symbol: str,
    timeframe: str,
) -> tuple[dict[str, Any], ...]:
    bands = dim_cfg.label_bands
    # instrument / timeframe overrides (HOW only)
    inst = dim_cfg.instrument_overrides.get(symbol) or {}
    if isinstance(inst, dict) and "label_bands" in inst:
        bands = tuple(inst["label_bands"])
    tf = dim_cfg.timeframe_overrides.get(timeframe) or {}
    if isinstance(tf, dict) and "label_bands" in tf:
        bands = tuple(tf["label_bands"])
    return bands


def build_market_state(
    bar_features: Mapping[str, Any],
    config: MsipShadowConfig | Disabled,
    provenance_ctx: ProvenanceContext,
    crt_obs: CrtPhaseObservation | None = None,
    *,
    symbol: str = "UNKNOWN",
    timeframe: str = "M15",
    bar_timestamp: str | None = None,
    bar_index: int | None = None,
) -> MarketStateVector | None:
    """Assemble one MarketStateVector from FeaturePipeline row + HOW config.

    Pure w.r.t. CRT — no side effects except returning a value object.
    Returns None if config is Disabled.
    """
    if isinstance(config, Disabled) or not getattr(config, "enabled", False):
        return None
    assert isinstance(config, MsipShadowConfig)

    ts = bar_timestamp
    if ts is None:
        ts = str(bar_features.get("timestamp", bar_features.get("bar_timestamp", "")))

    dimensions: dict[str, dict[str, Any]] = {}
    dimension_sources: dict[str, list[dict[str, Any]]] = {}
    partial = False
    invalid_how = False
    how_labels_present: list[str] = []
    how_label_paths: dict[str, str] = {}

    for dim_name, dim_cfg in config.dimensions.items():
        if not dim_cfg.enabled:
            continue
        if dim_name == "crt_phase_observation":
            continue  # handled separately

        payload: dict[str, Any] = {}
        sources_meta: list[dict[str, Any]] = []
        for feat in dim_cfg.source_features:
            val = _get_feature(bar_features, feat)
            if _is_missing(val):
                payload[feat] = None
                partial = True
                sources_meta.append({"feature": feat, "value": None, "missing": True})
            else:
                jv = _jsonable(val)
                payload[feat] = jv
                sources_meta.append({"feature": feat, "value": jv, "missing": False})

        # Optional HOW label
        label_spec = HOW_LABEL_SPEC.get(dim_name)
        bands = _resolve_label_bands(dim_cfg, symbol, timeframe)
        if label_spec and bands:
            primary = label_spec["primary_feature"]
            primary_val = payload.get(primary)
            if primary_val is None:
                primary_val = _get_feature(bar_features, primary)
            label = _apply_label_bands(primary_val, bands)
            # continuous twins must be present
            twins_ok = True
            for twin in label_spec["continuous_twins"]:
                tv = payload.get(twin)
                if tv is None and twin not in dim_cfg.source_features:
                    tv = _jsonable(_get_feature(bar_features, twin))
                    if not _is_missing(tv):
                        payload[twin] = tv
                if twin not in payload or payload[twin] is None:
                    # allow twin missing → drop label (INVALID_HOW for this label)
                    twins_ok = False
            if label is not None and twins_ok:
                payload[label_spec["label_field"]] = label
                how_labels_present.append(f"{dim_name}.{label_spec['label_field']}")
                how_label_paths[f"{dim_name}.{label_spec['label_field']}"] = (
                    f"msip_shadow.dimensions.{dim_name}.label_bands"
                )
            elif label is not None and not twins_ok:
                # drop label; continuous WHAT still emitted
                invalid_how = True
                partial = True

        dimensions[dim_name] = payload
        dimension_sources[dim_name] = sources_meta

    # CRT phase observation — never required for other dimension identity
    if config.crt_phase_observation_enabled:
        if crt_obs is None:
            crt_payload = {"crt_state": None, "observed": False}
        else:
            crt_payload = {
                "crt_state": crt_obs.crt_state,
                "observed": bool(crt_obs.observed),
            }
            if crt_obs.bar_index is not None:
                crt_payload["bar_index"] = crt_obs.bar_index
        dimensions["crt_phase_observation"] = crt_payload

    # Provenance
    prov: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "config_id": provenance_ctx.config_id,
        "config_sha256": provenance_ctx.config_sha256,
        "repository_commit": provenance_ctx.repository_commit,
        "corpus_path": provenance_ctx.corpus_path,
        "corpus_sha256": provenance_ctx.corpus_sha256,
        "feature_schema_hash": provenance_ctx.feature_schema_hash,
        "feature_order_hash": provenance_ctx.feature_order_hash,
        "dimension_sources": dimension_sources,
        "parity_audit_refs": list(provenance_ctx.parity_audit_refs),
        "crt_observation": (
            None
            if crt_obs is None
            else {
                "crt_state": crt_obs.crt_state,
                "bar_index": crt_obs.bar_index,
                "observed": crt_obs.observed,
            }
        ),
    }
    if how_labels_present:
        prov["how_label_provenance"] = {
            "msip_shadow_config_id": config.config_id,
            "msip_shadow_config_sha256": config.config_sha256,
            "interpretation_schema_version": provenance_ctx.interpretation_schema_version,
            "per_label_band_source_path": how_label_paths,
        }
        prov["continuous_twins_present"] = True
    else:
        prov["continuous_twins_present"] = None

    if invalid_how and partial:
        status = "PARTIAL"
    elif invalid_how:
        status = "INVALID_HOW"
    elif partial:
        status = "PARTIAL"
    else:
        status = "COMPLETE"

    # Provenance completeness: required fields
    for req in (
        "schema_version",
        "config_id",
        "config_sha256",
        "feature_schema_hash",
        "feature_order_hash",
        "dimension_sources",
    ):
        if prov.get(req) in (None, ""):
            status = "PARTIAL"
            break

    return MarketStateVector(
        schema_version=SCHEMA_VERSION,
        symbol=symbol,
        timeframe=timeframe,
        bar_timestamp=str(ts),
        bar_index=bar_index,
        dimensions=dimensions,
        provenance=prov,
        status=status,
    )


def emit_jsonl(path: Path, vector: MarketStateVector) -> None:
    """Append one vector as a JSON line (stable key order). Side effect: file I/O only."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(vector.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(line + "\n")


def stable_json_bytes(vector: MarketStateVector) -> bytes:
    """Deterministic serialization for DET-01 comparisons."""
    return json.dumps(
        vector.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
