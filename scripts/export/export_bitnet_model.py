"""
export_bitnet_model.py — Canonical bitnet_v3 export (random weights smoke).

Produces a model file consumable by BitNetModel under the bitnet_v3 contract:
schema_version, feature_dim, feature_order_hash, feature_names, layers, metadata.
Layer entries follow the export-schema shape {name, weights, scale} expected by
``_forward_export``.
"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
from features.feature_schema import CANONICAL_FEATURES, CANONICAL_FEATURE_DIM
from bitnet.model_contract import build_envelope


def _build_layer(name: str, in_dim: int, out_dim: int) -> dict:
    weights = [[random.choice([0, 1]) for _ in range(in_dim)] for _ in range(out_dim)]
    scale   = [1.0 for _ in range(out_dim)]
    return {"name": name, "weights": weights, "scale": scale}


def main() -> None:
    random.seed(42)
    n_in = CANONICAL_FEATURE_DIM   # 38 — canonical feature vector size
    layers = [
        _build_layer("fc1", n_in, 32),
        _build_layer("fc2", 32, 16),
        _build_layer("fc3", 16, 1),
    ]
    envelope = build_envelope(
        layers,
        feature_names=list(CANONICAL_FEATURES),
        metadata={"source": "export_bitnet_model", "seed": 42},
    )
    with open("model.json", "w", encoding="utf-8") as f:
        json.dump(envelope, f, indent=2)


if __name__ == "__main__":
    main()
