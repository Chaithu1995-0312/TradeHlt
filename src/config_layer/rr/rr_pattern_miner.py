"""
rr_pattern_miner.py
Feature -> RR Pattern Miner trainer and pure-Python inference.
Canonical contract: 24-feature vectors from CANONICAL_FEATURES.
"""

from __future__ import annotations

import json
import math
import os
import warnings
from typing import Any, Dict, List, Optional

from features.feature_schema import CANONICAL_FEATURE_DIM

# RR_SCHEMA was removed — use the single source of truth for feature dimensionality.
# CANONICAL_FEATURE_DIM tracks the live canonical schema width (currently 35).
# Older saved models with n_features=24 or n_features=11 will fail the shape
# check in train() and in NanoInferenceEngine.predict() — this is intentional:
# those models were trained on stale data and must be retrained.
N_FEATURES = CANONICAL_FEATURE_DIM

# ── Load from production config; fall back to coded defaults if unavailable ──
try:
    try:
        from config_layer.production_config import get_prod_section as _get_section
    except ImportError:
        from production_config import get_prod_section as _get_section  # standalone script path
    _RR_CFG = _get_section("rr_model")
except Exception:
    _RR_CFG = {}

MIN_SAMPLES:          int   = _RR_CFG.get("min_samples", 20)
DEFAULT_MODEL_PATH:   str   = _RR_CFG.get("model_path", "models/rr_model.json")
_MAHAL_CLIP:          float = _RR_CFG.get("mahal_clip", 500.0)
_CONF_BYPASS:         float = _RR_CFG.get("confidence_bypass_threshold", 0.3)
_RR_MIN:              float = _RR_CFG.get("score_weights", {}).get("_rr_min", -3.0)
_RR_MAX:              float = _RR_CFG.get("score_weights", {}).get("_rr_max", 5.0)
_W_GAUSSIAN:          float = _RR_CFG.get("score_weights", {}).get("gaussian", 0.5)
_W_ML:                float = _RR_CFG.get("score_weights", {}).get("ml", 0.3)
_W_CONFIDENCE:        float = _RR_CFG.get("score_weights", {}).get("confidence", 0.2)


def _sigmoid(x: float) -> float:
    if x >= 20.0:
        return 1.0
    if x <= -20.0:
        return 0.0
    return 1.0 / (1.0 + math.exp(-x))


class RRPatternTrainer:
    """Offline trainer that generates state_dict for NanoInferenceEngine."""

    def __init__(
        self,
        ridge_alpha: float = _RR_CFG.get("ridge_alpha", 10.0),
        gnb_var_smoothing: float = _RR_CFG.get("gnb_var_smoothing", 1e-9),
    ):
        self.ridge_alpha = ridge_alpha
        self.gnb_var_smoothing = gnb_var_smoothing
        self.state: Optional[Dict[str, Any]] = None

    def train(
        self,
        X: List[List[float]],
        y_rr: List[float],
        y_win: List[int],
    ) -> Dict[str, Any]:
        try:
            import numpy as np
            from sklearn.covariance import LedoitWolf
            from sklearn.linear_model import Ridge
        except ImportError as e:
            raise ImportError(
                "Training requires numpy and scikit-learn. Install with: pip install numpy scikit-learn"
            ) from e

        n = len(X)
        if n < MIN_SAMPLES:
            raise ValueError(f"Need >= {MIN_SAMPLES} samples, got {n}.")

        Xnp = np.array(X, dtype=np.float64)
        yr = np.array(y_rr, dtype=np.float64)
        yw = np.array(y_win, dtype=np.int32)

        if Xnp.ndim != 2 or Xnp.shape[1] != N_FEATURES:
            raise ValueError(
                f"RRPatternTrainer.train: expected X shape (*,{N_FEATURES}), got {Xnp.shape}."
            )

        scale_mu = Xnp.mean(axis=0)
        scale_std = Xnp.std(axis=0)
        scale_std[scale_std == 0.0] = 1.0
        Xs = (Xnp - scale_mu) / scale_std

        ridge = Ridge(alpha=self.ridge_alpha, fit_intercept=True)
        ridge.fit(Xs, yr)
        ridge_w = ridge.coef_.tolist()
        ridge_b = float(ridge.intercept_)

        gnb_C: List[List[float]] = []
        gnb_V: List[List[float]] = []
        gnb_mu: List[List[float]] = []
        for c in [0, 1]:
            mask = yw == c
            n_c = int(mask.sum())
            if n_c == 0:
                prior_c = 1e-10
                mu_c = Xs.mean(axis=0)
                var_c = np.ones(N_FEATURES)
            else:
                prior_c = n_c / n
                mu_c = Xs[mask].mean(axis=0)
                var_c = Xs[mask].var(axis=0) + self.gnb_var_smoothing

            C_c = np.log(prior_c) - 0.5 * np.log(2.0 * math.pi * var_c)
            V_c = 1.0 / var_c

            gnb_C.append(C_c.tolist())
            gnb_V.append(V_c.tolist())
            gnb_mu.append(mu_c.tolist())

        eps = 1e-6
        try:
            lw = LedoitWolf(assume_centered=False)
            lw.fit(Xs)
            conf_mu = lw.location_.tolist()
            conf_P = lw.get_precision().tolist()
        except Exception as exc:
            warnings.warn(f"LedoitWolf failed ({exc}); falling back to diagonal precision.")
            conf_mu = Xs.mean(axis=0).tolist()
            var_all = Xs.var(axis=0) + eps
            conf_P = np.diag(1.0 / var_all).tolist()

        self.state = {
            "ridge_w": ridge_w,
            "ridge_b": ridge_b,
            "gnb_C": gnb_C,
            "gnb_V": gnb_V,
            "gnb_mu": gnb_mu,
            "conf_mu": conf_mu,
            "conf_P": conf_P,
            "scale_mu": scale_mu.tolist(),
            "scale_sigma": scale_std.tolist(),
            "n_features": N_FEATURES,
            "n_train": n,
            "ridge_alpha": self.ridge_alpha,
            "feature_schema": f"canonical_{N_FEATURES}",
        }
        return self.state

    def save(self, path: str = DEFAULT_MODEL_PATH) -> None:
        if self.state is None:
            raise RuntimeError("Call train() before save().")
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.state, f, separators=(",", ":"))

    def loocv_report(
        self,
        X: List[List[float]],
        y_rr: List[float],
        y_win: List[int],
    ) -> Dict[str, Any]:
        try:
            import numpy as np
            from sklearn.linear_model import Ridge
        except ImportError as e:
            raise ImportError("LOOCV requires numpy and scikit-learn.") from e

        n = len(X)
        if n < MIN_SAMPLES:
            raise ValueError(f"Need >= {MIN_SAMPLES} samples for LOOCV, got {n}.")

        Xnp = np.array(X, dtype=np.float64)
        yr = np.array(y_rr, dtype=np.float64)
        yw = np.array(y_win, dtype=np.int32)

        pred_rr = np.zeros(n)
        pred_pwin = np.zeros(n)

        for i in range(n):
            idx_tr = list(range(n))
            idx_tr.pop(i)
            Xtr = Xnp[idx_tr]
            ytr = yr[idx_tr]
            ywtr = yw[idx_tr]

            mu = Xtr.mean(axis=0)
            std = Xtr.std(axis=0)
            std[std == 0.0] = 1.0
            Xtr_s = (Xtr - mu) / std
            Xte_s = (Xnp[i] - mu) / std

            ridge = Ridge(alpha=self.ridge_alpha, fit_intercept=True)
            ridge.fit(Xtr_s, ytr)
            pred_rr[i] = ridge.coef_.dot(Xte_s) + float(ridge.intercept_)

            log_probs = []
            for c in [0, 1]:
                mask = ywtr == c
                n_c = int(mask.sum())
                if n_c == 0:
                    log_probs.append(-1e9)
                    continue
                prior_c = n_c / len(ywtr)
                mu_c = Xtr_s[mask].mean(axis=0)
                var_c = Xtr_s[mask].var(axis=0) + self.gnb_var_smoothing
                C_c = math.log(prior_c) - 0.5 * float(np.log(2.0 * math.pi * var_c).sum())
                ll = C_c - 0.5 * float(((Xte_s - mu_c) ** 2 / var_c).sum())
                log_probs.append(ll)

            max_lp = max(log_probs)
            exps = [math.exp(lp - max_lp) for lp in log_probs]
            pred_pwin[i] = exps[1] / (exps[0] + exps[1])

        rr_corr = float(np.corrcoef(pred_rr, yr)[0, 1])
        if math.isnan(rr_corr):
            rr_corr = 0.0

        brier = float(((pred_pwin - yw.astype(float)) ** 2).mean())

        n_buckets = 10
        buckets = []
        sorted_idx = np.argsort(pred_pwin)
        chunk = n // n_buckets
        for b in range(n_buckets):
            start = b * chunk
            end = start + chunk if b < n_buckets - 1 else n
            bi = sorted_idx[start:end]
            buckets.append(
                {
                    "predicted_p_win": round(float(pred_pwin[bi].mean()), 4),
                    "actual_win_rate": round(float(yw[bi].mean()), 4),
                    "n": int(len(bi)),
                }
            )

        return {
            "rr_corr": round(rr_corr, 4),
            "brier_score": round(brier, 4),
            "calibration_buckets": buckets,
            "n_samples": n,
        }


class NanoInferenceEngine:
    """Pure-Python inference engine for canonical 24-feature vectors."""

    __slots__ = (
        "W",
        "b",
        "conf_mu",
        "conf_P",
        "gnb_C_loss",
        "gnb_V_loss",
        "gnb_mu_loss",
        "gnb_C_win",
        "gnb_V_win",
        "gnb_mu_win",
        "scale_mu",
        "scale_sigma",
        "zero_indices",   # tuple[int] — features zeroed at train-time; same mask applied at predict-time
    )

    def __init__(self, state_dict: Dict[str, Any]) -> None:
        self.W = tuple(float(x) for x in state_dict["ridge_w"])
        self.b = float(state_dict["ridge_b"])

        self.scale_mu = tuple(float(x) for x in state_dict["scale_mu"])
        self.scale_sigma = tuple(float(x) for x in state_dict["scale_sigma"])

        self.gnb_C_loss = tuple(float(x) for x in state_dict["gnb_C"][0])
        self.gnb_V_loss = tuple(float(x) for x in state_dict["gnb_V"][0])
        self.gnb_mu_loss = tuple(float(x) for x in state_dict["gnb_mu"][0])
        self.gnb_C_win = tuple(float(x) for x in state_dict["gnb_C"][1])
        self.gnb_V_win = tuple(float(x) for x in state_dict["gnb_V"][1])
        self.gnb_mu_win = tuple(float(x) for x in state_dict["gnb_mu"][1])

        self.conf_mu = tuple(float(x) for x in state_dict["conf_mu"])
        self.conf_P = tuple(tuple(float(x) for x in row) for row in state_dict["conf_P"])
        # zero_indices: features zeroed at train-time — apply same mask at predict-time.
        # Empty tuple when loading models trained without --zero-price-features (backward compat).
        self.zero_indices = tuple(int(i) for i in state_dict.get("zero_indices", []))

    @classmethod
    def load(cls, path: str = DEFAULT_MODEL_PATH) -> "NanoInferenceEngine":
        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)
        return cls(state)

    def predict(
        self,
        features: List[float],
        gaussian_score: float,
        gaussian_p_win: float,
        threshold: float = 0.5,
    ) -> Dict[str, Any]:
        n = len(self.W)
        # Backward compat: if caller provides more features than the model expects
        # (schema v3.0 → 38 features, model trained on v2.0 → 35), silently truncate.
        if len(features) > n:
            features = list(features)[:n]
        if len(features) != n:
            raise ValueError(f"NanoInferenceEngine.predict: expected {n} features, got {len(features)}.")

        # Apply same feature zeroing used at train-time (price-level de-anchoring).
        # Mutating caller data is unexpected; always work on a copy when zeroing.
        if self.zero_indices:
            features = list(features)
            for idx in self.zero_indices:
                if idx < n:
                    features[idx] = 0.0

        X = [
            (float(features[i]) - self.scale_mu[i]) / self.scale_sigma[i]
            for i in range(n)
        ]

        delta = [X[i] - self.conf_mu[i] for i in range(n)]
        d_sq = 0.0
        for i in range(n):
            row_dot = 0.0
            Pi = self.conf_P[i]
            for j in range(n):
                row_dot += Pi[j] * delta[j]
            d_sq += delta[i] * row_dot

        if d_sq > _MAHAL_CLIP:
            d_sq = _MAHAL_CLIP

        confidence = math.exp(-0.5 * d_sq)
        confidence = min(1.0, max(0.0, confidence))

        if confidence < _CONF_BYPASS:
            return {
                "final_score": float(gaussian_score),
                "expected_rr": 0.0,
                "probability_of_win": float(gaussian_p_win),
                "confidence": float(confidence),
                "status": "bypassed_low_confidence",
            }

        expected_rr = sum(X[i] * self.W[i] for i in range(n)) + self.b
        expected_rr = min(_RR_MAX, max(_RR_MIN, expected_rr))

        ll_loss = 0.0
        ll_win = 0.0
        for i in range(n):
            ll_loss += self.gnb_C_loss[i] - 0.5 * self.gnb_V_loss[i] * (X[i] - self.gnb_mu_loss[i]) ** 2
            ll_win += self.gnb_C_win[i] - 0.5 * self.gnb_V_win[i] * (X[i] - self.gnb_mu_win[i]) ** 2

        max_ll = ll_win if ll_win > ll_loss else ll_loss
        exp_loss = math.exp(ll_loss - max_ll)
        exp_win = math.exp(ll_win - max_ll)
        p_win = exp_win / (exp_loss + exp_win)

        ml_score = _sigmoid(expected_rr / 3.0)
        final_score = _W_GAUSSIAN * gaussian_score + _W_ML * ml_score + _W_CONFIDENCE * confidence

        status = "success"
        if gaussian_score < threshold and final_score > gaussian_score:
            final_score = gaussian_score
            status = "capped_by_threshold"

        return {
            "final_score": float(final_score),
            "expected_rr": float(expected_rr),
            "probability_of_win": float(p_win),
            "confidence": float(confidence),
            "status": status,
        }


def train_and_save(
    X: List[List[float]],
    y_rr: List[float],
    y_win: List[int],
    path: str = DEFAULT_MODEL_PATH,
    ridge_alpha: float = _RR_CFG.get("ridge_alpha", 10.0),
) -> Dict[str, Any]:
    trainer = RRPatternTrainer(ridge_alpha=ridge_alpha)
    trainer.train(X, y_rr, y_win)
    trainer.save(path)
    return trainer.loocv_report(X, y_rr, y_win)

