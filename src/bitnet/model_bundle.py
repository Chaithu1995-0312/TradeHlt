"""
model_bundle.py
===============
Write / validate CONTRACT-C model.bundle packages (Spec v1.2.4).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Union

REQUIRED_FILES = (
    "envelope.json",
    "metadata.json",
    "feature_schema.json",
    "label_contract.json",
    "metrics.json",
    "training_manifest.json",
    "evaluation_report.json",
    "sha256.txt",
)
# weights.bin optional if weights fully inlined in envelope


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_model_bundle(
    bundle_dir: Union[str, Path],
    *,
    envelope: Mapping[str, Any],
    metadata: Mapping[str, Any],
    feature_schema: Mapping[str, Any],
    label_contract: Mapping[str, Any],
    metrics: Mapping[str, Any],
    training_manifest: Mapping[str, Any],
    evaluation_report: Mapping[str, Any],
    weights_bin: Optional[bytes] = None,
) -> Path:
    """
    Create a complete model.bundle directory and return its path.

    Raises ValueError if required CONTRACT-C identity fields are missing.
    """
    _require_contract_c_fields(envelope, feature_schema, label_contract)

    root = Path(bundle_dir)
    root.mkdir(parents=True, exist_ok=True)

    files: Dict[str, Path] = {
        "envelope.json": root / "envelope.json",
        "metadata.json": root / "metadata.json",
        "feature_schema.json": root / "feature_schema.json",
        "label_contract.json": root / "label_contract.json",
        "metrics.json": root / "metrics.json",
        "training_manifest.json": root / "training_manifest.json",
        "evaluation_report.json": root / "evaluation_report.json",
    }
    write_json(files["envelope.json"], dict(envelope))
    write_json(files["metadata.json"], dict(metadata))
    write_json(files["feature_schema.json"], dict(feature_schema))
    write_json(files["label_contract.json"], dict(label_contract))
    write_json(files["metrics.json"], dict(metrics))
    write_json(files["training_manifest.json"], dict(training_manifest))
    write_json(files["evaluation_report.json"], dict(evaluation_report))

    hashed_names: List[str] = list(files.keys())
    if weights_bin is not None:
        wpath = root / "weights.bin"
        wpath.write_bytes(weights_bin)
        hashed_names.append("weights.bin")

    lines = []
    for name in sorted(hashed_names):
        lines.append(f"{_sha256_file(root / name)}  {name}")
    (root / "sha256.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return root


def _require_contract_c_fields(
    envelope: Mapping[str, Any],
    feature_schema: Mapping[str, Any],
    label_contract: Mapping[str, Any],
) -> None:
    if not label_contract.get("label_contract_id"):
        raise ValueError("label_contract.json missing label_contract_id")
    if not label_contract.get("economic_authority"):
        raise ValueError("label_contract.json missing economic_authority")
    ids = feature_schema.get("train_feature_identities")
    if not ids:
        raise ValueError("feature_schema.json missing train_feature_identities")
    bb = envelope.get("backbone") or {}
    for k in ("id", "input_dim", "hidden_dim", "latent_dim", "n_residual_blocks", "stages"):
        if k not in bb:
            raise ValueError(f"envelope.backbone missing {k}")
    if "heads" not in envelope:
        raise ValueError("envelope missing heads")


def validate_model_bundle(bundle_dir: Union[str, Path]) -> Dict[str, Any]:
    """
    Validate bundle layout + sha256 + CONTRACT-C required fields.
    Returns loaded envelope dict on success.
    """
    root = Path(bundle_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"model.bundle not a directory: {root}")

    missing = [f for f in REQUIRED_FILES if not (root / f).exists()]
    if missing:
        raise ValueError(f"model.bundle incomplete; missing {missing}")

    # Verify hashes
    sha_lines = (root / "sha256.txt").read_text(encoding="utf-8").strip().splitlines()
    expected: Dict[str, str] = {}
    for line in sha_lines:
        parts = line.split()
        if len(parts) >= 2:
            expected[parts[-1]] = parts[0]
    for name, digest in expected.items():
        path = root / name
        if not path.exists():
            raise ValueError(f"sha256 lists missing file {name}")
        got = _sha256_file(path)
        if got != digest:
            raise ValueError(f"sha256 mismatch for {name}: {got} != {digest}")

    label = json.loads((root / "label_contract.json").read_text(encoding="utf-8"))
    schema = json.loads((root / "feature_schema.json").read_text(encoding="utf-8"))
    envelope = json.loads((root / "envelope.json").read_text(encoding="utf-8"))
    _require_contract_c_fields(envelope, schema, label)
    return envelope


def load_composition_from_bundle(bundle_dir: Union[str, Path]):
    """Load BitNetComposition from a validated model.bundle."""
    from bitnet.composition import load_bitlinear_composition

    envelope = validate_model_bundle(bundle_dir)
    return load_bitlinear_composition(envelope)
