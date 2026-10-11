"""
feature_contract.py -- feature-definition contract and identity.

One feature meaning; many consumers.  This module is the single place that states what a canonical
feature *means* and that derives a verifiable identity for it.  It does not compute features for
production use: the batch pipeline (features/feature_pipeline.py) stays the producer, and every
other implementation must demonstrate parity with this contract (see tests/test_feature_contract.py).

Contract identity (`contract_hash`) covers:
  - contract version and the ordered canonical feature names (feature_schema.CANONICAL_FEATURES)
  - formal specifications (formula, zero-range behaviour, dtype, missing-value policy) for the
    features formalised so far (body_size, wick_size, body_ratio)
  - for every feature, a digest of the normalised AST (docstrings, comments and formatting removed)
    of the FeaturePipeline method(s) that assign it
  - a digest of everything else in feature_pipeline.py that can change a value (module constants,
    module-level functions, orchestration methods)
Any change to a formula, window, constant or encoding therefore changes the hash; comment and
formatting edits do not.

Fail-closed rule: a model artifact is compatible only if it carries the current contract hash.
Artifacts without a hash are *legacy*: they are ineligible unless a caller explicitly asks for
`allow_legacy=True` (audit use), and even then they are reported as `legacy_unverified`.
"""
from __future__ import annotations

import ast
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

import numpy as np

from features.feature_schema import CANONICAL_FEATURES, SCHEMA_HASH

CONTRACT_VERSION = "1.0"
_PIPELINE_PATH = Path(__file__).with_name("feature_pipeline.py")

# --------------------------------------------------------------------------------------------
# Formal specifications (authoritative statements of meaning)
# --------------------------------------------------------------------------------------------
FORMAL_SPECS: dict = {
    "body_size": {
        "formula": "abs(close - open)",
        "dtype_batch": "float64",
        "missing_value_policy": "inputs must be finite; non-finite inputs are an error for the caller, never zero-filled",
    },
    "wick_size": {
        "formula": "high - low",
        "note": "Historical name. It is the full candle range, NOT the shadow length. The name is kept for compatibility; "
                "implementations that subtract the body (high - low - body) do not satisfy this contract.",
        "dtype_batch": "float64",
        "missing_value_policy": "inputs must be finite; non-finite inputs are an error for the caller, never zero-filled",
    },
    "body_ratio": {
        "formula": "body_size / wick_size",
        "zero_range_behavior": "0.0 when wick_size (high - low) <= 0",
        "range": "[0.0, 1.0] for valid candles (low <= open, close <= high)",
        "dtype_batch": "float32",
        "dtype_note": "the batch pipeline casts to float32; consumers compare with relative tolerance 1e-6",
        "missing_value_policy": "inputs must be finite; non-finite inputs are an error for the caller, never zero-filled",
        "authority": "matches FeaturePipeline.compute_canonical_price_features, config_layer.crt_engine_v2.Candle and "
                     "scripts/backtest/manual_backtest.py; body_ratio_min thresholds (0.65 to 0.70) in the production "
                     "config were calibrated on this definition.",
    },
}


# --------------------------------------------------------------------------------------------
# Reference implementations of the formalised features
# --------------------------------------------------------------------------------------------
def ref_body_size(open_, high, low, close):
    return np.abs(np.asarray(close, dtype=float) - np.asarray(open_, dtype=float))


def ref_wick_size(open_, high, low, close):
    return np.asarray(high, dtype=float) - np.asarray(low, dtype=float)


def ref_body_ratio(open_, high, low, close):
    """body_size / (high - low); 0.0 where the range is not positive. Scalar or array input."""
    body = ref_body_size(open_, high, low, close)
    rng = ref_wick_size(open_, high, low, close)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(rng > 0, body / np.where(rng > 0, rng, 1.0), 0.0)
    return float(out) if np.ndim(out) == 0 else out


# --------------------------------------------------------------------------------------------
# Code-derived digests (normalised AST)
# --------------------------------------------------------------------------------------------
def _strip_doc(node):
    body = getattr(node, "body", None)
    if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
            and isinstance(body[0].value.value, str):
        node.body = body[1:] or [ast.Pass()]
    return node


def _digest(nodes) -> str:
    h = hashlib.sha256()
    for n in nodes:
        for sub in ast.walk(n):
            if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
                _strip_doc(sub)
        h.update(ast.dump(n, annotate_fields=True, include_attributes=False).encode())
    return h.hexdigest()


def _assigned_features(fn: ast.FunctionDef) -> set:
    found = set()
    for n in ast.walk(fn):
        targets = n.targets if isinstance(n, ast.Assign) else [n.target] if isinstance(n, ast.AugAssign) else []
        for tg in targets:
            if isinstance(tg, ast.Subscript) and isinstance(tg.slice, ast.Constant) and isinstance(tg.slice.value, str) \
                    and tg.slice.value in set(CANONICAL_FEATURES):
                found.add(tg.slice.value)
    return found


@lru_cache(maxsize=1)
def _pipeline_digests() -> tuple[dict, str]:
    """-> ({feature: digest of defining method(s)}, digest of all remaining pipeline code)."""
    tree = ast.parse(_PIPELINE_PATH.read_text(encoding="utf-8"))
    per_feature: dict = {f: [] for f in CANONICAL_FEATURES}
    rest = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "FeaturePipeline":
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    feats = _assigned_features(item)
                    if feats and item.name not in ("run", "finalize", "__init__"):
                        for f in feats:
                            per_feature[f].append(item)
                    else:
                        rest.append(item)
                else:
                    rest.append(item)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        elif isinstance(node, ast.Expr) and isinstance(getattr(node, "value", None), ast.Constant) and isinstance(node.value.value, str):
            continue  # module docstring
        else:
            rest.append(node)
    feat_digest = {f: (_digest(sorted(ms, key=lambda m: m.name)) if ms else "input_column") for f, ms in per_feature.items()}
    return feat_digest, _digest(rest)


# --------------------------------------------------------------------------------------------
# The contract
# --------------------------------------------------------------------------------------------
@lru_cache(maxsize=1)
def build_contract() -> dict:
    feat_digest, rest_digest = _pipeline_digests()
    feats = []
    for i, name in enumerate(CANONICAL_FEATURES):
        spec = FORMAL_SPECS.get(name)
        feats.append({
            "index": i, "name": name,
            "definition_status": "formal" if spec else ("raw_input" if feat_digest[name] == "input_column" else "implementation_digest"),
            "spec": spec, "implementation_digest": feat_digest[name],
        })
    return {"contract_version": CONTRACT_VERSION, "ordered_features": list(CANONICAL_FEATURES), "features": feats,
            "pipeline_remaining_code_digest": rest_digest, "schema_hash_names_only": SCHEMA_HASH,
            "scope_note": "Only body_size, wick_size and body_ratio are formally specified so far; all other features are "
                          "identified by the digest of their defining code, which detects change but does not yet state meaning."}


@lru_cache(maxsize=1)
def contract_hash() -> str:
    return hashlib.sha256(json.dumps(build_contract(), sort_keys=True, default=str).encode()).hexdigest()


def contract_identity() -> dict:
    return {"feature_contract_version": CONTRACT_VERSION, "feature_contract_hash": contract_hash()}


# --------------------------------------------------------------------------------------------
# Fail-closed compatibility check
# --------------------------------------------------------------------------------------------
class ContractMismatchError(ValueError):
    """Artifact is not compatible with the current feature-definition contract."""


def verify_bundle_contract(bundle: dict, label: str = "artifact") -> None:
    got = bundle.get("feature_contract_hash")
    if got is None:
        raise ContractMismatchError(
            f"{label}: no feature_contract_hash (legacy artifact). It is ineligible until retrained or re-verified "
            f"against contract {contract_hash()[:12]}...")
    if got != contract_hash():
        raise ContractMismatchError(
            f"{label}: feature contract mismatch (artifact {str(got)[:12]}... vs current {contract_hash()[:12]}...). "
            "The feature definitions changed since this artifact was produced.")


def contract_status_of(bundle: dict) -> str:
    h = bundle.get("feature_contract_hash")
    return "verified" if h == contract_hash() else "mismatched" if h else "legacy_unverified"


if __name__ == "__main__":  # python src/features/feature_contract.py  -> prints the contract and its hash
    print(json.dumps({"contract_hash": contract_hash(), "contract": build_contract()}, indent=2))
