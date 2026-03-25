"""
dataset_builder.py
═══════════════════════════════════════════════════════════════════════════════
Builds train / validation splits from validated fusion log records.

LEAKAGE PREVENTION RULES (non-negotiable):
  1. Records MUST be time-ordered (log file is append-only → guaranteed).
  2. Split is performed on temporal index, never shuffled.
  3. Validation set is always the MOST RECENT slice of data — it represents
     the future relative to the training window.
  4. Model NEVER sees validation data during training.

Usage:
  from dataset_validator import validate_logs
  from dataset_builder import build_splits

  records, _ = validate_logs("logs/GBPUSD_fusion.jsonl")
  splits = build_splits(records)
  # splits.X_train, splits.y_train, splits.X_val, splits.y_val

  # OR — build from TradeRecord list (backtest trades)
  from dataset_builder import build_gaussian_dataset
  X, y_rr = build_gaussian_dataset(trade_records)
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any

log = logging.getLogger("DatasetBuilder")

# ─────────────────────────────────────────────────────────────────────────────
# MINIMUM DATASET SIZE GUARD
# ─────────────────────────────────────────────────────────────────────────────

MIN_GAUSSIAN_SAMPLES = 100   # dataset integrity gate (CHECK 3)

# ─────────────────────────────────────────────────────────────────────────────
# ENCODING HELPERS (no leakage, no raw prices)
# ─────────────────────────────────────────────────────────────────────────────

SESSION_ENCODE = {"ASIA": 0, "LONDON": 1, "NEWYORK": 2}
REGIME_ENCODE  = {"DEAD": 0, "NEUTRAL": 1, "EXPANSION": 2}

LAMBDA_DECAY_DEFAULT = 0.05

# Frozen 11-feature schema — matches scoring_engine.FEATURE_SCHEMA
GAUSSIAN_FEATURE_SCHEMA = [
    "retest_depth",        # 0
    "body_ratio",          # 1
    "disp_strength",       # 2
    "volatility",          # 3
    "range_size",          # 4
    "session_encoded",     # 5
    "hour_of_day",         # 6
    "time_decay_feature",  # 7
    "regime_encoded",      # 8
    "retest_disp",         # 9  (interaction)
    "vol_disp",            # 10 (interaction)
]


# ─────────────────────────────────────────────────────────────────────────────
# SCHEMA VALIDATION GUARD (used at inference time — raises hard error)
# ─────────────────────────────────────────────────────────────────────────────

def validate_feature_vector(vec: list, context: str = "") -> None:
    """
    Hard validation: raises ValueError if feature vector length != 11.
    Call before every inference call (trainer.predict_proba, phase5_calibration).

    Parameters
    ----------
    vec     : feature vector to validate
    context : caller label for error message clarity
    """
    expected = len(GAUSSIAN_FEATURE_SCHEMA)
    if len(vec) != expected:
        tag = f" [{context}]" if context else ""
        raise ValueError(
            f"Feature vector length mismatch{tag}: "
            f"got {len(vec)}, expected {expected} ({GAUSSIAN_FEATURE_SCHEMA}). "
            f"Ensure build_feature_vector() from dataset_builder is the ONLY "
            f"feature construction path."
        )


def _safe_float(val: Any, default: float = 0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _safe_int(val: Any, default: int = 0) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def build_feature_vector(trade: Any, lambda_decay: float = LAMBDA_DECAY_DEFAULT) -> list:
    """
    Build 11-feature vector from a TradeRecord or dict.
    No raw prices. No leakage (dynamic_threshold / risk_multiplier excluded).

    Parameters
    ----------
    trade : TradeRecord dataclass or dict
    lambda_decay : time decay constant

    Returns
    -------
    list[float] of length 11
    """
    def _get(key, default=0.0):
        if isinstance(trade, dict):
            return trade.get(key, default)
        return getattr(trade, key, default)

    retest_depth  = _safe_float(_get("retest_depth",          0.0))
    body_ratio    = _safe_float(_get("body_ratio_feat",        0.0))
    disp_strength = _safe_float(_get("disp_str_feat",          0.0))
    volatility    = _safe_float(_get("volatility",             0.0))
    range_size    = _safe_float(_get("range_size",             0.0))
    session       = str(_get("session", "LONDON"))
    hour_of_day   = _safe_float(_get("hour_of_day",            0.0))
    candles_since = _safe_int(_get("candles_since_retest",     0))
    regime        = str(_get("regime", "NEUTRAL"))

    session_encoded  = float(SESSION_ENCODE.get(session, 1))
    regime_encoded   = float(REGIME_ENCODE.get(regime, 1))
    time_decay_feat  = math.exp(-lambda_decay * max(0, candles_since))
    retest_disp      = retest_depth * disp_strength
    vol_disp         = volatility * disp_strength

    return [
        retest_depth,
        body_ratio,
        disp_strength,
        volatility,
        range_size,
        session_encoded,
        hour_of_day,
        time_decay_feat,
        regime_encoded,
        retest_disp,
        vol_disp,
    ]


def rr_to_class(rr: float) -> int:
    """
    Discretise pnl_rr_net into 4 RR buckets for GaussianNB training.

    Bucket definitions:
        0 — loss     (rr < 0)
        1 — small win (0 ≤ rr < 1)
        2 — medium win (1 ≤ rr < 2)
        3 — big win   (rr ≥ 2)
    """
    if rr < 0:   return 0
    if rr < 1.0: return 1
    if rr < 2.0: return 2
    return 3


def build_gaussian_dataset(
    trades: list,
    lambda_decay: float = LAMBDA_DECAY_DEFAULT,
) -> tuple[list[list[float]], list[float]]:
    """
    Build (X, y_rr) from a list of TradeRecord objects or dicts.

    Returns
    -------
    X     : list of 11-feature vectors
    y_rr  : list of raw pnl_rr_net values (NOT bucketed — caller decides)
    """
    X, y = [], []
    skipped = 0
    for t in trades:
        def _get(key, default=0.0):
            if isinstance(t, dict):
                return t.get(key, default)
            return getattr(t, key, default)

        rr = _safe_float(_get("pnl_rr_net", None))
        if rr is None:
            skipped += 1
            continue

        vec = build_feature_vector(t, lambda_decay)
        X.append(vec)
        y.append(rr)

    if skipped:
        log.warning(f"build_gaussian_dataset: skipped {skipped} records (missing pnl_rr_net)")

    # Dataset integrity guard (CHECK 3)
    if len(X) < MIN_GAUSSIAN_SAMPLES:
        raise ValueError(
            f"Dataset too small: {len(X)} samples < minimum {MIN_GAUSSIAN_SAMPLES}. "
            "Run more backtests to accumulate sufficient trade history."
        )

    log.info(f"build_gaussian_dataset: {len(X)} samples, 11 features")
    return X, y


def build_gaussian_dataset_classified(
    trades: list,
    lambda_decay: float = LAMBDA_DECAY_DEFAULT,
) -> tuple[list[list[float]], list[int]]:
    """
    Same as build_gaussian_dataset but returns bucketed class labels.

    Returns
    -------
    X     : list of 11-feature vectors
    y_cls : list of class labels (0, 1, 2, 3)
    """
    X, y_rr = build_gaussian_dataset(trades, lambda_decay)
    y_cls = [rr_to_class(r) for r in y_rr]
    return X, y_cls


def validate_dataset_quality(X: list[list[float]], y_rr: list[float]) -> dict:
    """
    Run data quality checks before ML training.

    Checks:
      1. Feature variance (dead features = std ≈ 0)
      2. Feature vs target correlation
      3. Target distribution
      4. Class balance
      5. Feature independence (pairwise correlation)

    Returns
    -------
    dict with issues and recommendations
    """
    import math as _math

    n = len(X)
    if n == 0:
        return {"issues": ["empty dataset"], "recommendations": []}

    n_feat = len(X[0])
    issues = []
    recommendations = []

    # ── 1. Feature variance ──────────────────────────────────────────────
    feature_variance = {}
    for f in range(n_feat):
        vals = [X[i][f] for i in range(n)]
        mean_v = sum(vals) / n
        std_v  = _math.sqrt(sum((v - mean_v) ** 2 for v in vals) / n)
        fname  = GAUSSIAN_FEATURE_SCHEMA[f] if f < len(GAUSSIAN_FEATURE_SCHEMA) else f"feat_{f}"
        feature_variance[fname] = round(std_v, 6)
        if std_v < 1e-6:
            issues.append(f"Dead feature: {fname} (std ≈ 0)")
            recommendations.append(f"Remove or replace {fname}")

    # ── 2. Feature vs target correlation ─────────────────────────────────
    mean_y = sum(y_rr) / n
    correlation_with_target = {}
    for f in range(n_feat):
        vals  = [X[i][f] for i in range(n)]
        mean_x = sum(vals) / n
        cov = sum((vals[i] - mean_x) * (y_rr[i] - mean_y) for i in range(n)) / n
        sx  = _math.sqrt(sum((v - mean_x) ** 2 for v in vals) / n)
        sy  = _math.sqrt(sum((y - mean_y) ** 2 for y in y_rr) / n)
        corr = cov / (sx * sy) if sx > 0 and sy > 0 else 0.0
        fname = GAUSSIAN_FEATURE_SCHEMA[f] if f < len(GAUSSIAN_FEATURE_SCHEMA) else f"feat_{f}"
        correlation_with_target[fname] = round(corr, 4)

    if all(abs(v) < 0.02 for v in correlation_with_target.values()):
        issues.append("All feature-target correlations near zero — dataset may lack signal")
        recommendations.append("Collect more diverse trade data or add context features")

    # ── 3. Target distribution ────────────────────────────────────────────
    buckets = {"loss": 0, "small_win": 0, "mid_win": 0, "big_win": 0}
    for rr in y_rr:
        if rr < 0:   buckets["loss"] += 1
        elif rr < 1: buckets["small_win"] += 1
        elif rr < 2: buckets["mid_win"] += 1
        else:        buckets["big_win"] += 1
    target_distribution = {k: round(v / n, 4) for k, v in buckets.items()}

    # ── 4. Class balance ─────────────────────────────────────────────────
    y_cls = [rr_to_class(r) for r in y_rr]
    class_counts = [y_cls.count(c) for c in range(4)]
    class_balance = {f"class_{c}": class_counts[c] for c in range(4)}
    for c, count in enumerate(class_counts):
        if count < 20:
            issues.append(f"Class {c} has only {count} samples (minimum 20 recommended)")
            recommendations.append(f"Collect more class-{c} outcomes")

    # ── 5. Feature independence ───────────────────────────────────────────
    feature_independence = {}
    high_corr_pairs = []
    for i in range(n_feat):
        for j in range(i + 1, n_feat):
            xi = [X[k][i] for k in range(n)]
            xj = [X[k][j] for k in range(n)]
            mi, mj = sum(xi) / n, sum(xj) / n
            cov = sum((xi[k] - mi) * (xj[k] - mj) for k in range(n)) / n
            si  = _math.sqrt(sum((v - mi) ** 2 for v in xi) / n)
            sj  = _math.sqrt(sum((v - mj) ** 2 for v in xj) / n)
            corr = cov / (si * sj) if si > 0 and sj > 0 else 0.0
            fi = GAUSSIAN_FEATURE_SCHEMA[i] if i < len(GAUSSIAN_FEATURE_SCHEMA) else f"feat_{i}"
            fj = GAUSSIAN_FEATURE_SCHEMA[j] if j < len(GAUSSIAN_FEATURE_SCHEMA) else f"feat_{j}"
            feature_independence[f"{fi}×{fj}"] = round(corr, 4)
            if abs(corr) > 0.8:
                high_corr_pairs.append((fi, fj, round(corr, 4)))

    if high_corr_pairs:
        for fi, fj, c in high_corr_pairs:
            issues.append(f"High feature correlation: {fi} × {fj} = {c:.3f}")
            recommendations.append(f"Consider removing one of {fi} or {fj}")

    return {
        "n_samples":                n,
        "n_features":               n_feat,
        "feature_variance":         feature_variance,
        "correlation_with_target":  correlation_with_target,
        "target_distribution":      target_distribution,
        "class_balance":            class_balance,
        "feature_independence":     feature_independence,
        "issues":                   issues,
        "recommendations":          recommendations,
    }


# ─────────────────────────────────────────────────────────────────────────────
# OUTPUT
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DataSplits:
    X_train:    list[list[float]]
    y_train:    list[int]
    X_val:      list[list[float]]
    y_val:      list[int]
    n_features: int
    split_idx:  int

    @property
    def n_train(self) -> int: return len(self.X_train)

    @property
    def n_val(self) -> int: return len(self.X_val)

    @property
    def class_balance_train(self) -> float:
        """Fraction of wins in training set."""
        return sum(self.y_train) / len(self.y_train) if self.y_train else 0.0

    @property
    def class_balance_val(self) -> float:
        return sum(self.y_val) / len(self.y_val) if self.y_val else 0.0

    def print_summary(self) -> None:
        print(f"\n  Dataset splits:")
        print(f"    Train:      {self.n_train:>5} records  ({self.class_balance_train:.1%} wins)")
        print(f"    Validation: {self.n_val:>5} records  ({self.class_balance_val:.1%} wins)")
        print(f"    Features:   {self.n_features}")
        print(f"    Split idx:  {self.split_idx} (time-ordered, no shuffle)\n")


# ─────────────────────────────────────────────────────────────────────────────
# BUILDER
# ─────────────────────────────────────────────────────────────────────────────

def build_splits(
    records:     list[dict],
    train_ratio: float = 0.70,
) -> DataSplits:
    """
    Build time-ordered train/val splits.

    Parameters
    ----------
    records     : validated records from dataset_validator (time-ordered)
    train_ratio : fraction used for training (default 0.70 = 70% past, 30% future)

    Returns
    -------
    DataSplits
    """
    if not records:
        raise ValueError("No records provided to build_splits.")

    X: list[list[float]] = []
    y: list[int]         = []

    for r in records:
        vec = r.get("feature_vec")
        if not vec:
            continue
        outcome = r.get("outcome", {})
        label   = 1 if outcome.get("win", False) else 0
        X.append(vec)
        y.append(label)

    if not X:
        raise ValueError("No valid feature vectors found in records.")

    n         = len(X)
    split_idx = max(1, int(n * train_ratio))

    # Strict temporal split — no shuffle ever
    X_train, y_train = X[:split_idx], y[:split_idx]
    X_val,   y_val   = X[split_idx:], y[split_idx:]

    from feature_builder import N_FEATURES
    splits = DataSplits(
        X_train    = X_train,
        y_train    = y_train,
        X_val      = X_val,
        y_val      = y_val,
        n_features = N_FEATURES,
        split_idx  = split_idx,
    )

    splits.print_summary()
    return splits


def build_full(records: list[dict]) -> tuple[list[list[float]], list[int]]:
    """
    Return full dataset without splitting (used for final re-training
    after validation confirms the model is safe to promote).
    """
    X, y = [], []
    for r in records:
        vec = r.get("feature_vec")
        if not vec:
            continue
        label = 1 if r.get("outcome", {}).get("win", False) else 0
        X.append(vec)
        y.append(label)
    return X, y
