"""OFF-spine ML Gaussian (GaussianNB) adapter.

The fusion slot is fixed to EmaMomentumKernel. This adapter does not read
engine_runner and is not a fusion slot. Scoring requires an explicit
``--artifact`` path to a trained GaussianNB bundle under models/.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from research.model_runners.contracts import ModelContract
from research.model_runners.require_config import sha256_file
from research.model_runners.schema_resolver import identify_registered, resolve_declared
from research.model_runners.substrate import BarContext


class GaussianMLAdapter:
    def __init__(
        self,
        *,
        contract: ModelContract,
        prod_config: dict[str, Any],
        artifact: Path,
        instrument: str,
        repo_root: Path,
    ):
        self.contract = contract
        _ = prod_config  # intentionally unused — not a fusion slot
        if not instrument:
            raise ValueError("instrument is required for nb_outcome_classifier")
        if artifact is None:
            raise ValueError("nb_outcome_classifier requires --artifact")
        art = artifact if artifact.is_absolute() else (repo_root / artifact)
        if not art.is_file():
            # also accept path relative to models/
            alt = repo_root / "models" / artifact
            if alt.is_file():
                art = alt
            else:
                raise FileNotFoundError(f"nb_outcome_classifier artifact missing: {artifact}")

        # load_gaussian_model expects path relative to models/ (no models/ prefix)
        rel = art.resolve().relative_to((repo_root / "models").resolve())
        from training.trainer import load_gaussian_model

        model, scaler, meta = load_gaussian_model(str(rel).replace("\\", "/"))
        if model is None or scaler is None:
            raise RuntimeError(f"load_gaussian_model returned empty for {rel}")
        if not isinstance(meta, dict):
            raise RuntimeError(f"nb_outcome_classifier meta missing for {rel}")
        resolved = list(meta.get("feature_schema_resolved") or meta.get("feature_schema") or [])
        if not resolved:
            raise RuntimeError(
                f"nb_outcome_classifier artifact lacks feature_schema_resolved: {art}"
            )
        n_feat = int(getattr(model, "n_features", 0))
        if n_feat != len(resolved):
            raise RuntimeError(
                f"nb_outcome_classifier n_features={n_feat} != resolved schema len {len(resolved)}"
            )

        # R1/A8: route the artifact-declared schema through the single resolver so
        # the trained order is reported under a stable id (matching a known
        # generation when it equals one) instead of an ad-hoc per-adapter list.
        saved = list(meta.get("feature_schema") or resolved)
        schema = resolve_declared(saved)
        registered_id = identify_registered(schema.live_names)
        if registered_id is not None:
            schema = resolve_declared(saved, schema_id=registered_id)
        schema.assert_model_width(n_feat)
        if list(schema.live_names) != list(resolved):
            raise RuntimeError(
                "nb_outcome_classifier schema resolver disagrees with loader-resolved order: "
                f"resolver={list(schema.live_names)[:5]}... "
                f"loader={list(resolved)[:5]}..."
            )

        self._model = model
        self._scaler = scaler
        self._schema = schema
        self._instrument = instrument
        self.config_sections_read: list[str] = []
        self.config_keys_read: list[str] = []
        self.artifact_info = {
            "path": str(art),
            "sha256": sha256_file(art),
            "n_features": n_feat,
            "feature_schema_resolved_dim": len(resolved),
            "schema_alignment": meta.get("schema_alignment"),
            "feature_order_hash": meta.get("feature_order_hash"),
            "spine_active": False,
            "note": "offline model_id nb_outcome_classifier — not a fusion slot",
            "prod_removed_selector_ignored": True,
            **schema.to_manifest(),
        }

    def score_bar(self, bar: BarContext) -> dict[str, Any]:
        # R1: name-anchored extraction in trained order via the single authority.
        vec = self._schema.build_vector(bar.features)

        if len(vec) != self._model.n_features:
            raise RuntimeError(
                f"nb_outcome_classifier dim mismatch got={len(vec)} "
                f"expected={self._model.n_features}"
            )

        scaled = self._scaler.transform_one(vec)
        expected_rr, confidence, probs = self._model.predict_expected_rr(scaled)
        score = 1.0 / (1.0 + math.exp(-float(expected_rr)))
        score = max(0.0, min(1.0, score))
        return {
            "score": round(score, 4),
            "reason": "ml_gaussian_offline",
            "expected_rr": round(float(expected_rr), 4),
            "confidence": round(float(confidence), 4),
            "n_features": int(self._model.n_features),
            "semantic": "gaussian_nb_ml_offline",
            "prod_removed_selector_ignored": True,
        }
