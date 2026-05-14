"""
rr_dataset_builder.py
=====================
Canonical RR dataset builder based on FeaturePipeline output.

FIXES (vs broken version):
  - Removed imports of RR_SCHEMA, assert_schema_version, validate_schema_vector
    which do NOT exist in features.feature_schema (were phantom imports).
  - Fixed wrong import path: was `from feature_pipeline import` (root-level),
    now `from features.feature_pipeline import` (canonical package path).
  - extract_target() supports multiple RR key aliases:
      rr: rr_achieved OR pnl_rr_net OR computed from entry/sl/tp
      win: outcome OR win OR derived from rr > 0
  - Handles missing values, type conversion, and invalid rows gracefully.
  - validate_dataset_integrity() ensures labels are NOT all zeros.
  - Dataset remains schema-aligned to CANONICAL_FEATURES (32 keys).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, List, Optional, Tuple

import pandas as pd

from features.feature_pipeline import FeaturePipeline, build_features, build_feature_vector
from features.feature_schema import CANONICAL_FEATURES, CANONICAL_FEATURE_DIM, SCHEMA_HASH
from features.schema_validator import validate_features, validate_feature_values

logger = logging.getLogger(__name__)

# ── Schema constants (canonical — do NOT change) ──────────────────────────────
N_FEATURES: int = CANONICAL_FEATURE_DIM          # 32
FEATURE_NAMES: List[str] = list(CANONICAL_FEATURES)
MIN_SAMPLES: int = 20


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _to_trade_dict(trade: Any) -> dict:
    """Coerce a trade object to a plain dict."""
    if isinstance(trade, dict):
        return dict(trade)
    if hasattr(trade, "__dict__"):
        return dict(vars(trade))
    return {}


def _safe_float(v: Any) -> Optional[float]:
    """Return float(v) if valid and finite, else None."""
    try:
        f = float(v)
        if f != f or f in (float("inf"), float("-inf")):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _build_canonical_features_df(
    trades: List[Any],
    df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Build an enriched DataFrame with all 32 canonical columns.

    Args:
        trades: list of trade dicts or objects (used when df is None)
        df: optional pre-built DataFrame (takes priority over trades)

    Returns:
        Enriched DataFrame from FeaturePipeline.run(), NaN rows dropped.

    Raises:
        ValueError: if no valid rows can be produced
    """
    src_df = df if df is not None else pd.DataFrame(
        [_to_trade_dict(t) for t in trades]
    )
    if src_df.empty:
        raise ValueError("build_dataset: no rows available for FeaturePipeline input.")

    enriched_df, _ = FeaturePipeline(src_df).run()
    if enriched_df.empty:
        raise ValueError("build_dataset: FeaturePipeline produced no rows after warmup.")

    return enriched_df.reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC: EXTRACT FEATURES
# ─────────────────────────────────────────────────────────────────────────────

def extract_features(features: dict) -> List[float]:
    """
    Convert a canonical feature dict to the model vector (32-width).

    Args:
        features: canonical feature dict keyed by CANONICAL_FEATURES

    Returns:
        List of 32 floats in CANONICAL_FEATURES order

    Raises:
        ValueError: if schema validation fails or values are invalid
    """
    validate_features(features, CANONICAL_FEATURES)
    validate_feature_values(features)
    vec = build_feature_vector(features)
    if len(vec) != N_FEATURES:
        raise ValueError(
            f"extract_features: vector length {len(vec)} != expected {N_FEATURES}"
        )
    return vec


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC: EXTRACT TARGET  (ISSUE 2 FIX — multi-key schema support)
# ─────────────────────────────────────────────────────────────────────────────

def extract_target(trade: Any, features: dict) -> Tuple[float, int]:
    """
    Extract RR regression and win/loss classification targets.

    RR resolution order (first non-None value wins):
      1. trade["rr_achieved"]
      2. trade["pnl_rr_net"]
      3. Computed from trade["entry"], trade["sl"], trade["tp"]

    Win resolution order:
      1. trade["outcome"]  → "WIN"/"W"/"TP"/"1" → 1, else 0
      2. trade["win"]      → int/bool cast
      3. Derived from rr > 0

    Args:
        trade: trade dict or object
        features: canonical feature dict (validated for schema conformance)

    Returns:
        (rr, win): (float, int)

    Raises:
        ValueError: if RR cannot be determined from any key
        ValueError: if computed RR is zero-risk (entry == sl)
    """
    validate_features(features, CANONICAL_FEATURES)

    trade_dict = _to_trade_dict(trade)

    # ── RR: try all known key aliases ────────────────────────────────────────
    rr: Optional[float] = None

    # Key 1: rr_achieved
    rr = _safe_float(trade_dict.get("rr_achieved"))

    # Key 2: pnl_rr_net
    if rr is None:
        rr = _safe_float(trade_dict.get("pnl_rr_net"))

    # Key 3: compute from entry/sl/tp
    if rr is None:
        entry = _safe_float(trade_dict.get("entry"))
        sl    = _safe_float(trade_dict.get("sl"))
        tp    = _safe_float(trade_dict.get("tp"))
        if entry is not None and sl is not None and tp is not None:
            risk   = abs(entry - sl)
            reward = abs(tp - entry)
            if risk == 0.0:
                raise ValueError(
                    "extract_target: computed RR impossible — entry == sl (zero risk)."
                )
            rr = reward / risk

    if rr is None:
        raise ValueError(
            "extract_target: cannot determine RR — rr_achieved, pnl_rr_net, "
            "and entry/sl/tp are all missing or invalid."
        )

    # ── Win: try all known key aliases ───────────────────────────────────────
    win: int

    outcome = trade_dict.get("outcome")
    if outcome is not None:
        if isinstance(outcome, str):
            win = 1 if outcome.strip().upper() in ("WIN", "W", "TP", "TP_HIT", "1") else 0
        else:
            try:
                win = 1 if int(outcome) == 1 else 0
            except (TypeError, ValueError):
                win = 1 if rr > 0 else 0
    elif "win" in trade_dict:
        win_val = trade_dict["win"]
        try:
            win = 1 if int(win_val) == 1 else 0
        except (TypeError, ValueError):
            win = 1 if rr > 0 else 0
    else:
        # Derive from rr sign — positive rr means the trade was profitable
        win = 1 if rr > 0 else 0

    return rr, win


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC: VALIDATE DATASET INTEGRITY
# ─────────────────────────────────────────────────────────────────────────────

def validate_dataset_integrity(
    X: List[List[float]],
    y_rr: List[float],
    y_win: Optional[List[int]] = None,
) -> None:
    """
    Hard validation: dataset must be non-degenerate.

    Raises:
        ValueError: if dataset is empty, all-zero RR, or single-class labels.
    """
    if not X:
        raise ValueError("validate_dataset_integrity: empty dataset — no samples provided")

    if not y_rr:
        raise ValueError("validate_dataset_integrity: empty RR target list")

    if len(X) != len(y_rr):
        raise ValueError(
            f"validate_dataset_integrity: X length {len(X)} != y_rr length {len(y_rr)}"
        )

    if all(r == 0.0 for r in y_rr):
        raise ValueError(
            "validate_dataset_integrity: DEGENERATE DATASET — all RR values are zero. "
            "Check that trade dicts contain rr_achieved, pnl_rr_net, or entry/sl/tp fields."
        )

    unique_rr = set(round(r, 8) for r in y_rr)
    if len(unique_rr) < 2:
        raise ValueError(
            "validate_dataset_integrity: degenerate dataset — all RR values are identical."
        )

    if y_win is not None:
        if len(X) != len(y_win):
            raise ValueError(
                f"validate_dataset_integrity: X length {len(X)} != y_win length {len(y_win)}"
            )
        unique_win = set(y_win)
        if len(unique_win) < 2:
            raise ValueError(
                "validate_dataset_integrity: degenerate win labels — both classes (0 and 1) "
                "are required. Check outcome/win fields or RR sign distribution."
            )


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC: BUILD DATASET
# ─────────────────────────────────────────────────────────────────────────────

def build_dataset(
    trades: List[Any],
    df: Optional[pd.DataFrame] = None,
) -> Tuple[List[List[float]], List[float], List[int]]:
    """
    Build (X, y_rr, y_win) from trades aligned with FeaturePipeline rows.

    Args:
        trades: list of trade dicts/objects; must have RR-related fields
        df: optional pre-built OHLCV DataFrame (overrides trade-dict OHLCV)

    Returns:
        (X, y_rr, y_win): feature matrix, RR labels, win labels

    Raises:
        ValueError: if fewer than MIN_SAMPLES valid rows can be extracted
        ValueError: if dataset integrity check fails
    """
    features_df = _build_canonical_features_df(trades, df=df)

    if len(features_df) > len(trades):
        raise ValueError(
            f"build_dataset: pipeline rows ({len(features_df)}) exceed "
            f"trade rows ({len(trades)})."
        )

    aligned_trades = list(trades)[-len(features_df):]
    cols = list(CANONICAL_FEATURES)

    X: List[List[float]] = []
    y_rr: List[float] = []
    y_win: List[int] = []
    skipped = 0

    for i, trade in enumerate(aligned_trades):
        features = features_df.iloc[i][cols].to_dict()
        try:
            feats = extract_features(features)
            rr, win = extract_target(trade, features)
        except (ValueError, KeyError) as exc:
            skipped += 1
            logger.warning("build_dataset: skipping row %d: %s", i, exc)
            continue

        X.append(feats)
        y_rr.append(rr)
        y_win.append(win)

    if skipped:
        logger.info("build_dataset: skipped %d rows due to extraction errors", skipped)

    if len(X) < MIN_SAMPLES:
        raise ValueError(
            f"Insufficient training data: {len(X)} valid trades found, "
            f"minimum required is {MIN_SAMPLES}."
        )

    validate_dataset_integrity(X, y_rr, y_win)
    return X, y_rr, y_win


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC: SAVE / LOAD DATASET
# ─────────────────────────────────────────────────────────────────────────────

def save_dataset(
    X: List[List[float]],
    y_rr: List[float],
    y_win: List[int],
    path: str = "models/rr_dataset.json",
) -> None:
    """Persist dataset to JSON with schema metadata."""
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    payload = {
        "n_samples":      len(X),
        "n_features":     N_FEATURES,
        "feature_names":  FEATURE_NAMES,
        "schema_hash":    SCHEMA_HASH,          # canonical schema fingerprint
        "X":              X,
        "y_rr":           y_rr,
        "y_win":          y_win,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"))
    logger.info("save_dataset: wrote %d samples to %s", len(X), path)


def load_dataset(
    path: str = "models/rr_dataset.json",
) -> Tuple[List[List[float]], List[float], List[int]]:
    """
    Load and validate a previously saved RR dataset.

    Raises:
        FileNotFoundError: if path does not exist
        ValueError: on schema mismatch or inconsistent lengths
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"load_dataset: file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    # Schema hash check (optional — older files may not have it)
    stored_hash = payload.get("schema_hash")
    if stored_hash is not None and stored_hash != SCHEMA_HASH:
        raise ValueError(
            f"RR dataset schema hash mismatch: "
            f"expected {SCHEMA_HASH}, got {stored_hash}. "
            "Dataset was built with a different canonical schema."
        )

    X     = payload.get("X")     or []
    y_rr  = payload.get("y_rr")  or []
    y_win = payload.get("y_win") or []

    if len(X) != len(y_rr) or len(X) != len(y_win):
        raise ValueError(
            "load_dataset: inconsistent lengths between X, y_rr, and y_win."
        )

    for i, vec in enumerate(X):
        if not isinstance(vec, list) or len(vec) != N_FEATURES:
            raise ValueError(
                f"load_dataset: vector length mismatch at row {i}: "
                f"expected {N_FEATURES}, got "
                f"{len(vec) if isinstance(vec, list) else type(vec).__name__}."
            )

    return X, y_rr, y_win
