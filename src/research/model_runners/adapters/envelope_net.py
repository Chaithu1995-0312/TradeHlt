"""EnvelopeNet offline adapter — requires --artifact (bundle dir or envelope_bundle.json).

Uses 38-dim LEGACY feature order (TN_ENV_CLEAN_L2 / ENV_OFFLINE_TRAIN_V1).
Does not depend on production fusion flags.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from research.envelope_offline.shadow import load_shadow_bundle, predict_heads
from research.model_runners.contracts import ModelContract
from research.model_runners.require_config import sha256_file
from research.model_runners.schema_resolver import resolve_named
from research.model_runners.substrate import BarContext

# R1: the trained order now comes from the single schema authority.
# `legacy_38_env` is parity-proven equal to research.clean_labels.builder
# .LEGACY_FEATURE_NAMES (see tests/test_model_runners_schema_resolver.py).
_SCHEMA_ID = "legacy_38_env"


class EnvelopeNetAdapter:
    def __init__(
        self,
        *,
        contract: ModelContract,
        prod_config: dict[str, Any],
        artifact: Path,
        repo_root: Path,
    ):
        self.contract = contract
        _ = prod_config
        if artifact is None:
            raise ValueError("envelope requires --artifact (bundle dir or envelope_bundle.json)")
        path = artifact if artifact.is_absolute() else (repo_root / artifact)
        if path.is_file() and path.name == "envelope_bundle.json":
            bundle_dir = path.parent
        elif path.is_dir():
            bundle_dir = path
        else:
            raise FileNotFoundError(f"envelope artifact not found: {path}")

        bundle, models = load_shadow_bundle(bundle_dir)
        self._models = models
        self._bundle = bundle
        self._schema = resolve_named(_SCHEMA_ID)
        bundle_json = bundle_dir / "envelope_bundle.json"
        self.config_sections_read: list[str] = []
        self.config_keys_read: list[str] = []
        self.artifact_info = {
            "path": str(bundle_dir),
            "bundle_sha256": sha256_file(bundle_json) if bundle_json.is_file() else None,
            "charter_id": bundle.get("charter_id"),
            "signal_rollup": bundle.get("signal_rollup"),
            "feature_dim": self._schema.dim,
            "feature_names": list(self._schema.live_names),
            "spine_active": False,
            "miar_alignment": "DESIGN_ONLY",
            "note": (
                "observe-only EnvelopeNet; decision_weight conceptually 0. "
                "MIAR: registered as a DESIGN_ONLY concept (no production intent, "
                "no wired consumer) — see docs/governance/miar_registry.json."
            ),
            **self._schema.to_manifest(),
        }

    def score_bar(self, bar: BarContext) -> dict[str, Any]:
        # Name-anchored trained order via the single schema authority (R1).
        vec = self._schema.build_vector(bar.features)
        preds = predict_heads(self._models, vec)
        out = dict(preds)
        # CONTRACT RULE (R6, enforced by tests/test_model_runners_contract_rules.py):
        # an adapter must NOT synthesise a composite it was not trained to emit.
        # EnvelopeNet has four independent heads and no composite head, so no
        # "score" key is produced. Averaging them would be an invented quantity.
        out["semantic"] = "envelope_heads_observe"
        out["feature_dim"] = self._schema.dim
        return out
