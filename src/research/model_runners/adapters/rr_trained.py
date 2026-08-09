"""OFF-spine trained RR (NanoInference rr_model.json) — observe-only.

Not the live fusion RR slot (that is candle polarity). F-038 rr_fusion disabled.

Schema handling (R1/A8): the trained order comes from
``research.model_runners.schema_resolver`` — the single live->trained authority —
selected by the artifact's OWN declared ``feature_schema``. Both generations are
supported (v3 38-dim ``canonical_38`` and v4 39-dim ``canonical_39``); an
undeclared or unknown schema raises rather than assuming one.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from config_layer.rr.rr_pattern_miner import (
    RR_SCORE_MAX,
    RR_SCORE_MIN,
    NanoInferenceEngine,
)
from research.model_runners.contracts import ModelContract
from research.model_runners.require_config import (
    require_key,
    require_section,
    sha256_file,
)
from research.model_runners.schema_resolver import (
    SchemaResolutionError,
    resolve_named,
)
from research.model_runners.substrate import BarContext

# Artifact-declared feature_schema string -> resolver schema id.
# Strict: an artifact declaring anything else raises (no default generation).
_ARTIFACT_SCHEMA_TO_ID: dict[str, str] = {
    "canonical_38": "canonical_38_v3",
    "canonical_39": "canonical_39",
}


def _raw_ml(engine: NanoInferenceEngine, features: list[float]) -> dict[str, Any]:
    """Model arithmetic without the confidence-gate bypass (observe raw outputs).

    F-044: the live gate is mis-scaled for its rank, so raw outputs are the
    honest observation surface. zero_indices are forced to 0.0 in-place (the
    same price-level de-anchoring applied at train time) but the vector keeps
    full width — those slots still flow through every sum.
    """
    n = len(engine.W)
    if len(features) != n:
        raise ValueError(
            f"rr_trained feature dim {len(features)} != model n_features {n}"
        )
    feats = list(features)
    if engine.zero_indices:
        for idx in engine.zero_indices:
            if idx < n:
                feats[idx] = 0.0
    X = [
        (float(feats[i]) - engine.scale_mu[i]) / engine.scale_sigma[i]
        for i in range(n)
    ]
    delta = [X[i] - engine.conf_mu[i] for i in range(n)]
    d_sq = 0.0
    for i in range(n):
        row_dot = 0.0
        Pi = engine.conf_P[i]
        for j in range(n):
            row_dot += Pi[j] * delta[j]
        d_sq += delta[i] * row_dot
    confidence = math.exp(-0.5 * min(d_sq, 1e6))
    confidence = min(1.0, max(0.0, confidence))
    expected_rr = sum(X[i] * engine.W[i] for i in range(n)) + engine.b
    expected_rr = min(RR_SCORE_MAX, max(RR_SCORE_MIN, expected_rr))
    ll_loss = 0.0
    ll_win = 0.0
    for i in range(n):
        ll_loss += engine.gnb_C_loss[i] - 0.5 * engine.gnb_V_loss[i] * (
            X[i] - engine.gnb_mu_loss[i]
        ) ** 2
        ll_win += engine.gnb_C_win[i] - 0.5 * engine.gnb_V_win[i] * (
            X[i] - engine.gnb_mu_win[i]
        ) ** 2
    max_ll = ll_win if ll_win > ll_loss else ll_loss
    exp_loss = math.exp(ll_loss - max_ll)
    exp_win = math.exp(ll_win - max_ll)
    p_win = exp_win / (exp_loss + exp_win)
    ml_score = 1.0 / (1.0 + math.exp(-(expected_rr / 3.0)))
    zi = engine.zero_indices
    if zi is None:
        raise RuntimeError("NanoInferenceEngine.zero_indices is None")
    dof = n - len(zi)
    return {
        "score": float(ml_score),
        "expected_rr_raw": float(expected_rr),
        "p_win_raw": float(p_win),
        "ml_score_raw": float(ml_score),
        "confidence_raw": float(confidence),
        "d_sq": float(d_sq),
        "dof": int(dof),
        "n_features": int(n),
        "semantic": "rr_trained_nano_inference_raw",
    }


class RRTrainedAdapter:
    def __init__(
        self,
        *,
        contract: ModelContract,
        prod_config: dict[str, Any],
        artifact: Path,
    ):
        self.contract = contract
        er = require_section(prod_config, "engine_runner")
        rr_fusion = require_key(er, "rr_fusion", path="engine_runner")
        if not isinstance(rr_fusion, dict):
            raise KeyError("engine_runner.rr_fusion must be a mapping")
        enabled = require_key(rr_fusion, "enabled", path="engine_runner.rr_fusion")
        model_path_cfg = require_key(
            rr_fusion, "model_path", path="engine_runner.rr_fusion"
        )
        if not artifact.is_file():
            raise FileNotFoundError(f"rr_trained artifact missing: {artifact}")

        # Artifact must declare its own schema — no assumed generation.
        bundle = json.loads(artifact.read_text(encoding="utf-8"))
        declared = bundle.get("feature_schema")
        if not declared:
            raise SchemaResolutionError(
                f"rr_trained artifact {artifact} does not declare 'feature_schema'. "
                f"Cannot infer the trained generation — refusing to guess. "
                f"Known: {sorted(_ARTIFACT_SCHEMA_TO_ID)}"
            )
        if not isinstance(declared, str):
            raise SchemaResolutionError(
                f"rr_trained artifact 'feature_schema' must be a schema-name string, "
                f"got {type(declared).__name__}"
            )
        if declared not in _ARTIFACT_SCHEMA_TO_ID:
            raise SchemaResolutionError(
                f"rr_trained artifact declares feature_schema={declared!r}, which "
                f"maps to no known trained schema. Known: "
                f"{sorted(_ARTIFACT_SCHEMA_TO_ID)}"
            )
        self._schema = resolve_named(_ARTIFACT_SCHEMA_TO_ID[declared])

        self._engine = NanoInferenceEngine.load(str(artifact))
        model_n = int(getattr(self._engine, "n_features", len(self._engine.W)))
        self._schema.assert_model_width(model_n)

        self.config_sections_read = ["engine_runner"]
        self.config_keys_read = [
            "engine_runner.rr_fusion.enabled",
            "engine_runner.rr_fusion.model_path",
        ]
        self.artifact_info = {
            "path": str(artifact),
            "sha256": sha256_file(artifact),
            "config_model_path": str(model_path_cfg),
            "rr_fusion_enabled_prod": bool(enabled),
            "model_n_features": model_n,
            "artifact_declared_schema": declared,
            "artifact_schema_version": bundle.get("schema_version"),
            "zero_indices_count": len(self._engine.zero_indices or ()),
            "effective_dof": model_n - len(self._engine.zero_indices or ()),
            "spine_active": False,
            **self._schema.to_manifest(),
        }

    def score_bar(self, bar: BarContext) -> dict[str, Any]:
        vec = self._schema.build_vector(bar.features)
        return _raw_ml(self._engine, vec)
