"""
trainer.py
═══════════════════════════════════════════════════════════════════════════════
Two model families:

1. TradeNet (PyTorch) — binary classifier for CRT signal quality.
   Architecture: 6 → 32 → 16 → 1 (sigmoid)
   torch is imported LAZILY — module can be imported without torch installed.

2. GaussianNBModel (pure Python) — 4-class Gaussian Naive Bayes for expected RR.
   No external dependencies. Saves/loads as JSON.
   Used by: train_pipeline.run_gaussian_update(), live_engine.LiveEngine
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Optional

# PATCH v3: schema imports from single source of truth
from features.feature_schema import (
    GAUSSIAN_SCHEMA,
    TRADENET_SCHEMA,
    assert_schema_version,
    validate_vector,
    SCHEMA_VERSION,
    CANONICAL_FEATURES,
)
#assert_schema_version()
N_FEATURES = TRADENET_SCHEMA.n_features           # 35 — TradeNet input size (CANONICAL_FEATURE_DIM)
GAUSSIAN_N_FEATURES = GAUSSIAN_SCHEMA.n_features  # 35 — GaussianNBModel input size (CANONICAL_FEATURE_DIM)

log = logging.getLogger("Trainer")

MODELS_DIR = Path("models")
MIN_GAUSSIAN_SAMPLES = 20   # matches dataset_builder.MIN_GAUSSIAN_SAMPLES

# RR weights per class bucket: loss / small win / mid win / big win
_RR_WEIGHTS = [0.0, 0.5, 1.5, 2.5]


# ─────────────────────────────────────────────────────────────────────────────
# GAUSSIAN LAYER: StandardScaler (pure Python, no sklearn)
# ─────────────────────────────────────────────────────────────────────────────

class StandardScaler:
    """
    Pure-Python feature standardiser (mean=0, std=1 per feature).

    Must be fitted on TRAINING data only (no leakage).
    Save alongside GaussianNBModel — same version always used together.

    Methods
    -------
    fit(X)            : compute mean/std from list of feature vectors
    transform(X)      : scale batch of vectors
    transform_one(x)  : scale single vector (for live inference)
    to_dict() / from_dict() : JSON-serialisable
    """

    def __init__(self) -> None:
        self._mean:    list[float] = []
        self._std:     list[float] = []
        self._fitted:  bool        = False
        self.n_features: int       = 0

    def fit(self, X: list[list[float]]) -> "StandardScaler":
        n = len(X)
        if n == 0:
            raise ValueError("StandardScaler.fit: empty dataset")
        self.n_features = len(X[0])
        self._mean = []
        self._std  = []
        for f in range(self.n_features):
            vals = [X[i][f] for i in range(n)]
            mu   = sum(vals) / n
            std  = math.sqrt(sum((v - mu) ** 2 for v in vals) / n)
            self._mean.append(mu)
            self._std.append(std if std > 1e-8 else 1.0)  # avoid div/0
        self._fitted = True
        return self

    def transform(self, X: list[list[float]]) -> list[list[float]]:
        if not self._fitted:
            raise RuntimeError("StandardScaler: call fit() before transform()")
        return [self.transform_one(x) for x in X]

    def transform_one(self, x: list[float]) -> list[float]:
        if not self._fitted:
            raise RuntimeError("StandardScaler: call fit() before transform_one()")
        return [(x[f] - self._mean[f]) / self._std[f] for f in range(self.n_features)]

    def to_dict(self) -> dict:
        return {"mean": self._mean, "std": self._std, "n_features": self.n_features}

    @classmethod
    def from_dict(cls, d: dict) -> "StandardScaler":
        s = cls()
        s._mean      = d["mean"]
        s._std       = d["std"]
        s.n_features = d["n_features"]
        s._fitted    = True
        return s


# ─────────────────────────────────────────────────────────────────────────────
# GAUSSIAN LAYER: GaussianNBModel (pure Python, 4-class)
# ─────────────────────────────────────────────────────────────────────────────

class GaussianNBModel:
    """
    Pure-Python Gaussian Naive Bayes, 4-class classifier.

    Classes:
      0 = loss      (pnl_rr < 0)
      1 = small win (0 ≤ pnl_rr < 1)
      2 = mid win   (1 ≤ pnl_rr < 2)
      3 = big win   (pnl_rr ≥ 2)

    Expects SCALED input (use StandardScaler.transform_one() before predict).

    FIX 2: predict_proba() raises ValueError if len(x) != n_features.
    """

    N_CLASSES    = 4
    VAR_SMOOTHING = 1e-9

    def __init__(self) -> None:
        self.n_features:   int          = 0
        self.class_priors: list[float]  = []
        self.means:        list[list[float]] = []
        self.vars:         list[list[float]] = []
        self._fitted:      bool         = False

    def fit(self, X: list[list[float]], y_cls: list[int]) -> "GaussianNBModel":
        """
        Train on scaled feature vectors and class labels.

        Parameters
        ----------
        X     : scaled feature vectors (from StandardScaler.transform)
        y_cls : class labels 0–3 (from rr_to_class)
        """
        n = len(X)
        if n == 0:
            raise ValueError("GaussianNBModel.fit: empty dataset")
        # PATCH v3: validate all training vectors against GAUSSIAN_SCHEMA before fitting
        for i, x in enumerate(X):
            validate_vector(x, GAUSSIAN_SCHEMA, label=f"trainer.GaussianNBModel.fit[{i}]")
        self.n_features = len(X[0])
        self.class_priors = []
        self.means        = []
        self.vars         = []

        for c in range(self.N_CLASSES):
            rows_c = [X[i] for i in range(n) if y_cls[i] == c]
            count  = len(rows_c)
            prior  = count / n if n > 0 else 0.0
            self.class_priors.append(prior)

            if count == 0:
                self.means.append([0.0] * self.n_features)
                self.vars.append([self.VAR_SMOOTHING] * self.n_features)
                continue

            mu  = [sum(row[f] for row in rows_c) / count for f in range(self.n_features)]
            var = [
                sum((row[f] - mu[f]) ** 2 for row in rows_c) / count + self.VAR_SMOOTHING
                for f in range(self.n_features)
            ]
            self.means.append(mu)
            self.vars.append(var)

        self._fitted = True
        return self

    def predict_proba(self, x: list[float]) -> list[float]:
        """
        Returns P(class | x) for all 4 classes.

        FIX 2: raises ValueError if len(x) != n_features.
        """
        if not self._fitted:
            raise RuntimeError("GaussianNBModel must be fit() before predict_proba()")
        # FIX 2: Hard schema validation — catches train/live feature mismatch immediately
        if len(x) != self.n_features:
            raise ValueError(
                f"GaussianNBModel.predict_proba: feature vector length {len(x)} "
                f"!= trained n_features {self.n_features}. "
                f"Use dataset_builder.build_feature_vector() for ALL inference calls."
            )
        log_posts = []
        for c in range(self.N_CLASSES):
            log_prior = math.log(self.class_priors[c] + 1e-300)
            log_lik = 0.0
            for f in range(self.n_features):
                mu  = self.means[c][f]
                var = self.vars[c][f]
                log_lik += (
                    -0.5 * math.log(2 * math.pi * var)
                    - ((x[f] - mu) ** 2) / (2 * var)
                )
            log_posts.append(log_prior + log_lik)

        # Softmax for numerical stability
        max_lp = max(log_posts)
        exps   = [math.exp(lp - max_lp) for lp in log_posts]
        total  = sum(exps)
        return [e / total for e in exps]

    def predict_expected_rr(self, x: list[float]) -> tuple[float, float, list[float]]:
        # PATCH v3: validate every inference vector against GAUSSIAN_SCHEMA
        validate_vector(x, GAUSSIAN_SCHEMA, label="trainer.GaussianNBModel.predict_expected_rr")
        """
        Returns (expected_rr, confidence, probabilities).

        expected_rr  : Σ P(class_i) × RR_weight_i
        confidence   : max(probabilities) — certainty of dominant class
        probabilities: [P(loss), P(small), P(mid), P(big)]
        """
        probs = self.predict_proba(x)
        expected_rr = sum(p * w for p, w in zip(probs, _RR_WEIGHTS))
        confidence  = max(probs)
        return expected_rr, confidence, probs

    def to_dict(self) -> dict:
        return {
            "n_features":   self.n_features,
            "n_classes":    self.N_CLASSES,
            "var_smoothing": self.VAR_SMOOTHING,
            "class_priors": self.class_priors,
            "means":        self.means,
            "vars":         self.vars,
            "rr_weights":   _RR_WEIGHTS,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "GaussianNBModel":
        m = cls()
        m.n_features   = d["n_features"]
        m.class_priors = d["class_priors"]
        m.means        = d["means"]
        m.vars         = d["vars"]
        m._fitted      = True
        return m


# ─────────────────────────────────────────────────────────────────────────────
# GAUSSIAN LAYER: helpers
# ─────────────────────────────────────────────────────────────────────────────

def _pearson(xs: list[float], ys: list[float]) -> float:
    """Pearson correlation between two lists."""
    n = len(xs)
    if n < 3:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / n
    sx  = math.sqrt(sum((x - mx) ** 2 for x in xs) / n)
    sy  = math.sqrt(sum((y - my) ** 2 for y in ys) / n)
    return cov / (sx * sy) if sx > 0 and sy > 0 else 0.0


def _calibration_error(model: GaussianNBModel, X_scaled: list, y_cls: list) -> float:
    """
    |mean predicted P(win) - actual win rate|
    win = class 2 or 3 (pnl_rr >= 1.0)
    """
    n = len(X_scaled)
    if n == 0:
        return 0.0
    pred_p_win   = [sum(model.predict_proba(x)[2:]) for x in X_scaled]
    actual_wins  = [1 if c >= 2 else 0 for c in y_cls]
    mean_pred    = sum(pred_p_win)   / n
    mean_actual  = sum(actual_wins)  / n
    return abs(mean_pred - mean_actual)


# ─────────────────────────────────────────────────────────────────────────────
# GAUSSIAN LAYER: train_gaussian
# ─────────────────────────────────────────────────────────────────────────────

def train_gaussian(
    X:            list[list[float]],
    y_rr:         list[float],
    train_ratio:  float = 0.70,
) -> tuple[GaussianNBModel, StandardScaler, dict]:
    """
    Train a GaussianNBModel on the full dataset.

    Temporal split for in-sample metrics (no shuffle, no leakage).

    Parameters
    ----------
    X          : raw (unscaled) 11-feature vectors, time-ordered
    y_rr       : raw pnl_rr_net values
    train_ratio: fraction of X used for training scaler + model

    Returns
    -------
    (model, scaler, metrics_dict)
      metrics_dict keys: corr_expected_rr, calibration_error, n_train, n_val
    """
    from features.dataset_builder import rr_to_class

    n = len(X)
    if n < MIN_GAUSSIAN_SAMPLES:
        raise ValueError(
            f"train_gaussian: need >= {MIN_GAUSSIAN_SAMPLES} samples, got {n}"
        )

    split_idx = max(1, int(n * train_ratio))
    X_tr,  y_tr_rr  = X[:split_idx],  y_rr[:split_idx]
    X_val, y_val_rr = X[split_idx:],  y_rr[split_idx:]

    y_cls_tr = [rr_to_class(r) for r in y_tr_rr]

    # Fit scaler on training data only
    scaler = StandardScaler()
    scaler.fit(X_tr)

    X_tr_sc  = scaler.transform(X_tr)
    X_val_sc = scaler.transform(X_val) if X_val else []

    model = GaussianNBModel()
    model.fit(X_tr_sc, y_cls_tr)

    # Metrics on val (or train if no val)
    if X_val_sc:
        pred_rr = [model.predict_expected_rr(x)[0] for x in X_val_sc]
        y_cls_val = [rr_to_class(r) for r in y_val_rr]
        corr    = _pearson(pred_rr, y_val_rr)
        cal_err = _calibration_error(model, X_val_sc, y_cls_val)
        n_val   = len(X_val)
    else:
        pred_rr = [model.predict_expected_rr(x)[0] for x in X_tr_sc]
        y_cls_tr2 = [rr_to_class(r) for r in y_tr_rr]
        corr    = _pearson(pred_rr, y_tr_rr)
        cal_err = _calibration_error(model, X_tr_sc, y_cls_tr2)
        n_val   = 0

    import time as _time
    metrics = {
        "corr_expected_rr":  round(corr,    4),
        "calibration_error": round(cal_err, 4),
        "n_train":           len(X_tr),
        "n_val":             n_val,
        "trained_at":        _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
    }

    log.info(
        f"train_gaussian | n_train={len(X_tr)} n_val={n_val} "
        f"corr={corr:+.4f} cal_err={cal_err:.4f}"
    )
    return model, scaler, metrics


# ─────────────────────────────────────────────────────────────────────────────
# GAUSSIAN LAYER: save / load bundle
# ─────────────────────────────────────────────────────────────────────────────

def save_gaussian_model(
    model:          GaussianNBModel,
    scaler:         StandardScaler,
    metrics:        dict,
    name:           str = "gaussian_model.json",
    feature_schema: list = None,
) -> Path:
    """
    Save model + scaler + metadata as a single JSON bundle.
    NEVER overwrites — caller must use versioned names.

    Returns path to saved file.
    """
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    path = MODELS_DIR / name

    bundle = {
        "model":          model.to_dict(),
        "scaler":         scaler.to_dict(),
        "metrics":        metrics,
        "feature_schema": feature_schema or list(GAUSSIAN_SCHEMA.feature_names),
        "schema_name":    "gaussian",       # PATCH v3: explicit schema tag for safe loading
        "schema_version": GAUSSIAN_SCHEMA.version,  # PATCH v3: version check on load
        "schema_checksum": GAUSSIAN_SCHEMA.checksum,  # PATCH v3: tamper / drift detection
    }
    path.write_text(json.dumps(bundle, indent=2))
    log.info(f"Gaussian model saved → {path}")
    return path


def load_gaussian_model(
    name: str,
) -> tuple[GaussianNBModel, StandardScaler, dict]:
    """
    Load a Gaussian model bundle from models/<name>.

    FIX 2 (hard schema check): raises ValueError if saved feature_schema
    does not match current GAUSSIAN_FEATURE_SCHEMA.

    Returns (model, scaler, metadata_dict)
    """
    from features.dataset_builder import GAUSSIAN_FEATURE_SCHEMA

    path = MODELS_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Gaussian model not found: {path}")

    bundle = json.loads(path.read_text())

    # FIX 2: Hard error on schema mismatch — not just a warning
    saved_schema = bundle.get("feature_schema", [])
    if saved_schema and saved_schema != GAUSSIAN_FEATURE_SCHEMA:
        raise ValueError(
            f"Feature schema mismatch in model '{name}'!\n"
            f"  Saved:   {saved_schema}\n"
            f"  Current: {GAUSSIAN_FEATURE_SCHEMA}\n"
            f"  The model was trained with a different feature set. "
            f"Retrain with the current GAUSSIAN_FEATURE_SCHEMA or "
            f"use the matching model version."
        )

    model  = GaussianNBModel.from_dict(bundle["model"])
    scaler = StandardScaler.from_dict(bundle["scaler"])
    meta   = bundle.get("metrics", {})
    meta["feature_schema"] = saved_schema

    log.info(f"Gaussian model loaded ← {path}")
    return model, scaler, meta


# ─────────────────────────────────────────────────────────────────────────────
# GAUSSIAN LAYER: cross_val_gaussian (FIX 4 — 3-fold time-series CV)
# ─────────────────────────────────────────────────────────────────────────────

def cross_val_gaussian(
    X:       list[list[float]],
    y_rr:    list[float],
    n_folds: int = 3,
) -> dict:
    """
    FIX 4: Time-series cross-validation for stable Gaussian evaluation.

    Uses forward-only expanding window (no shuffle, no leakage):
      Fold 1: train[0:step]    val[step:2*step]
      Fold 2: train[0:2*step]  val[2*step:3*step]
      Fold 3: train[0:3*step]  val[3*step:4*step]

    Parameters
    ----------
    X       : raw unscaled feature vectors, length CANONICAL_FEATURE_DIM=35 (time-ordered)
    y_rr    : raw pnl_rr_net values
    n_folds : number of expanding window folds (default 3)

    Returns
    -------
    dict with:
      corr_mean, corr_std, cal_mean, cal_std
      stable    : True if corr_std < 0.05 (low variance)
      fold_metrics : list of per-fold results
    """
    from features.dataset_builder import rr_to_class

    n = len(X)
    if n < MIN_GAUSSIAN_SAMPLES:
        raise ValueError(
            f"cross_val_gaussian: need >= {MIN_GAUSSIAN_SAMPLES} samples, got {n}"
        )

    fold_corrs   = []
    fold_cals    = []
    fold_metrics = []

    step = n // (n_folds + 1)
    for fold in range(1, n_folds + 1):
        train_end = fold * step
        val_end   = min(n, train_end + step)
        if train_end < 30 or val_end <= train_end + 10:
            continue

        X_tr,  y_tr_rr  = X[:train_end],        y_rr[:train_end]
        X_val, y_val_rr = X[train_end:val_end],  y_rr[train_end:val_end]

        y_cls_tr  = [rr_to_class(r) for r in y_tr_rr]
        y_cls_val = [rr_to_class(r) for r in y_val_rr]

        scaler = StandardScaler()
        scaler.fit(X_tr)
        X_tr_sc  = scaler.transform(X_tr)
        X_val_sc = scaler.transform(X_val)

        model = GaussianNBModel()
        model.fit(X_tr_sc, y_cls_tr)

        pred_rr = [model.predict_expected_rr(x)[0] for x in X_val_sc]
        corr    = _pearson(pred_rr, y_val_rr)
        cal_err = _calibration_error(model, X_val_sc, y_cls_val)

        fold_corrs.append(corr)
        fold_cals.append(cal_err)
        fold_metrics.append({
            "fold":      fold,
            "n_train":   train_end,
            "n_val":     val_end - train_end,
            "corr":      round(corr,    4),
            "cal_error": round(cal_err, 4),
        })

    if not fold_corrs:
        return {
            "corr_mean": 0.0, "corr_std": 0.0,
            "cal_mean":  1.0, "cal_std":  0.0,
            "stable": False, "fold_metrics": [],
        }

    corr_mean = sum(fold_corrs) / len(fold_corrs)
    cal_mean  = sum(fold_cals)  / len(fold_cals)
    corr_std  = math.sqrt(sum((c - corr_mean) ** 2 for c in fold_corrs) / len(fold_corrs))
    cal_std   = math.sqrt(sum((c - cal_mean)  ** 2 for c in fold_cals)  / len(fold_cals))
    stable    = corr_std < 0.05

    log.info(
        f"cross_val_gaussian | {len(fold_corrs)} folds | "
        f"corr={corr_mean:+.4f}±{corr_std:.4f} "
        f"cal={cal_mean:.4f}±{cal_std:.4f} "
        f"stable={stable}"
    )

    return {
        "corr_mean":    round(corr_mean, 4),
        "corr_std":     round(corr_std,  4),
        "cal_mean":     round(cal_mean,  4),
        "cal_std":      round(cal_std,   4),
        "stable":       stable,
        "fold_metrics": fold_metrics,
    }



# ─────────────────────────────────────────────────────────────────────────────
# MODEL DEFINITION
# ─────────────────────────────────────────────────────────────────────────────

def _build_model():
    """Return a fresh TradeNet. Called lazily to avoid torch import at module load."""
    import torch.nn as nn

    class TradeNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(N_FEATURES, 32),
                nn.ReLU(),
                nn.Dropout(0.2),
                nn.Linear(32, 16),
                nn.ReLU(),
                nn.Linear(16, 1),
                nn.Sigmoid(),
            )

        def forward(self, x):
            return self.net(x)

    return TradeNet()


# ─────────────────────────────────────────────────────────────────────────────
# TRAINING
# ─────────────────────────────────────────────────────────────────────────────

def train(
    X: list[list[float]],
    y: list[int],
    epochs:    int   = 100,
    lr:        float = 0.001,
    batch_size: int  = 64,
    verbose:   bool  = True,
):
    """
    Train TradeNet on (X, y).

    Parameters
    ----------
    X       : feature vectors (list of lists, length N_FEATURES each)
    y       : binary labels (1 = win, 0 = loss)
    epochs  : training iterations over full dataset
    lr      : Adam learning rate
    batch_size : mini-batch size; if <= 0 or > len(X), uses full batch

    Returns
    -------
    trained model (eval mode)
    """
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset

    model   = _build_model()
    opt     = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.BCELoss()

    X_t = torch.tensor(X, dtype=torch.float32)
    y_t = torch.tensor(y, dtype=torch.float32).unsqueeze(1)

    dataset = TensorDataset(X_t, y_t)
    bs      = batch_size if 0 < batch_size <= len(X) else len(X)
    loader  = DataLoader(dataset, batch_size=bs, shuffle=True)

    model.train()

    for epoch in range(1, epochs + 1):
        epoch_loss = 0.0
        for xb, yb in loader:
            pred  = model(xb)
            loss  = loss_fn(pred, yb)
            opt.zero_grad()
            loss.backward()
            opt.step()
            epoch_loss += loss.item()

        if verbose and epoch % 20 == 0:
            avg = epoch_loss / len(loader)
            log.info(f"epoch {epoch:>4} / {epochs}  loss={avg:.4f}")
            print(f"  epoch {epoch:>4}/{epochs}  loss={avg:.4f}")

    model.eval()
    return model


# ─────────────────────────────────────────────────────────────────────────────
# SAVE / LOAD
# ─────────────────────────────────────────────────────────────────────────────

def save_model(model, name: str, metrics: dict | None = None) -> Path:
    import torch
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    path = MODELS_DIR / name
    torch.save(model.state_dict(), path)
    log.info("Model saved -> %s", path)

    # ── Register in TradeNet versioned registry (fail-open) ──────────────────
    try:
        from core.model_registry import register_tradenet, promote_tradenet, get_active_tradenet
        # Extract version token from filename: "tradenet_p5_20260406T005347.pth" → "20260406T005347"
        stem   = Path(name).stem           # e.g. "tradenet_p5_20260406T005347"
        parts  = stem.split("_")
        version = parts[-1] if len(parts) >= 3 else stem
        register_tradenet(version, str(path), metrics or {})
        # Auto-promote if no active version exists
        if get_active_tradenet() is None:
            ok, reason = promote_tradenet(version)
            log.info("TradeNet auto-promoted (first deployment): %s | %s", version, reason)
    except Exception as _reg_err:
        log.warning("TradeNet registry update failed (non-fatal): %s", _reg_err)

    return path


def load_model(name: str):
    import torch
    model = _build_model()
    path  = MODELS_DIR / name
    model.load_state_dict(torch.load(path, map_location="cpu"))
    model.eval()
    return model


# ─────────────────────────────────────────────────────────────────────────────
# INFERENCE WRAPPER  (used by FusionEngine as neural_fn)
# ─────────────────────────────────────────────────────────────────────────────

def make_neural_fn(model):
    """
    Returns a callable(features: dict) -> float suitable for FusionEngine.neural_fn.

    Input  : cached_features dict (keys: retest_depth, body_ratio, ...)
    Output : float probability in [0, 1]

    Usage:
      from trainer import load_model, make_neural_fn
      model = load_model("model_v1.pth")
      fn    = make_neural_fn(model)
      fusion = FusionEngine(..., neural_fn=fn)
    """
    import torch
    from features.dataset_builder import extract_feature_vector

    def _infer(features: dict) -> float:
        try:
            vec = extract_feature_vector(features)   # 32-dim canonical vector
            # Correct shape: [1, N_FEATURES] — unsqueeze(0) adds batch dim
            x   = torch.tensor(vec, dtype=torch.float32).unsqueeze(0)
            with torch.no_grad():
                return float(model(x).item())
        except Exception as e:
            log.warning(f"neural_fn inference failed: {e}. Returning 0.5.")
            return 0.5

    return _infer
