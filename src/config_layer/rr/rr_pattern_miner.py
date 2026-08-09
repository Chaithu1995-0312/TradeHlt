"""
rr_pattern_miner.py
Feature -> RR Pattern Miner trainer and pure-Python inference.
Canonical contract: feature vectors matching the model’s trained n_features and
the live CANONICAL_FEATURE_DIM (schema v4.0 = 39). Dimension mismatch is
fail-closed — never silently truncated (P0 2026-07-22).
"""

from __future__ import annotations

import json
import math
import os
import warnings
from typing import Any, Dict, List, Optional

from features.feature_schema import CANONICAL_FEATURE_DIM

# RR_SCHEMA was removed — use the single source of truth for feature dimensionality.
# CANONICAL_FEATURE_DIM tracks the live canonical schema width (schema v4.0 = 39).
# Older saved models with n_features=35/38/24/11 fail the shape check in train() and
# in NanoInferenceEngine.predict() — intentional: remap or retrain, never silent-slice.
N_FEATURES = CANONICAL_FEATURE_DIM


class FeatureDimensionError(ValueError):
    """Feature vector width does not match the loaded RR model.

    Raised instead of silent index truncation. Callers must remap/retrain;
    swallowing this into a plausible score is a fail-open defect (P0).
    """

# ── Load from production config (strict — the rr_model section + keys are governed) ──
# Fallback sweep RR-001/fail-fast: the outer `except → {}` config mask was removed. The
# `rr_model` section and these keys are present in the active config; a missing section/key is
# now a load-time error, not a silent default. The inner ImportError dual-path (package vs
# standalone-script import) is legitimate optional-import resilience and is preserved.
try:
    from config_layer.production_config import get_prod_section as _get_section
except ImportError:
    from production_config import get_prod_section as _get_section  # standalone script path
_RR_CFG = _get_section("rr_model")

# RR raw-score clamp bounds: STRUCTURAL algorithm constants, not config knobs (RR-001).
# Algorithm boundaries belong in code, not config — no fallback, no degrees of freedom.
RR_SCORE_MIN: float = -3.0
RR_SCORE_MAX: float = 5.0

MIN_SAMPLES:          int   = _RR_CFG["min_samples"]
DEFAULT_MODEL_PATH:   str   = _RR_CFG["model_path"]
_MAHAL_CLIP:          float = _RR_CFG["mahal_clip"]
_CONF_BYPASS:         float = _RR_CFG["confidence_bypass_threshold"]
_SCORE_WEIGHTS:       dict  = _RR_CFG["score_weights"]
_W_GAUSSIAN:          float = _SCORE_WEIGHTS["gaussian"]
_W_ML:                float = _SCORE_WEIGHTS["ml"]
_W_CONFIDENCE:        float = _SCORE_WEIGHTS["confidence"]

# ── Confidence-gate mode (F-044) ────────────────────────────────────────────────────────────
# The legacy gate `confidence = exp(-0.5·d_sq) < confidence_bypass_threshold` is mis-specified for
# its dimensionality: `d_sq` is a Mahalanobis distance over a rank-`dof` form (n_features minus the
# zeroed indices), whose in-distribution E[d_sq]=dof, so confidence ≈ exp(-0.5·dof) ≪ threshold for
# ~every input — including the model's own training data (100% in-sample bypass; F-044). This adds a
# dof-AWARE gate behind `rr_model.confidence_gate.mode`.
#
# Parity: default `legacy_scalar` reproduces `confidence < _CONF_BYPASS` byte-for-byte (mirrors the
# parity-preserving default of the existing `engine_runner.rr_fusion.full_feature_vector` knob — a
# missing subsection maps to the IDENTITY behavior, not a new/possibly-wrong default). The dof-aware
# modes are validated capability for a future, ΔG001-gated re-enable of rr_fusion:
#   • `chi2_tail`   — bypass iff Q(dof/2, d_sq/2) < p_threshold (the χ²-tail the Mahalanobis implies);
#   • `dof_scaled`  — bypass iff d_sq/dof > dof_scaled_max (pragmatic normalization);
#   • `percentile`  — bypass iff d_sq > d_sq_cut, the cut calibrated from the EMPIRICAL training-d_sq
#                     CDF (most robust; the empirical d_sq is heavy-tailed vs χ²(dof), so theory
#                     p-values mis-estimate real bypass — F-044 refinement 2026-07-05).
# In all modes the operating point is chosen via `target_bypass_fraction → empirical threshold`
# (rr_confidence_probe.py emits the calibration table). They grant NO authority (§6.5); rr_fusion
# stays `enabled:false` and the gate is inert until a measured ΔG001 re-enable.
_GATE_CFG: dict = dict(_RR_CFG.get("confidence_gate") or {})
_GATE_MODE: str = str(_GATE_CFG.get("mode", "legacy_scalar"))
_GATE_P_THRESHOLD: float = float(_GATE_CFG.get("p_threshold", 0.01))    # for chi2_tail
_GATE_DOF_SCALED_MAX: float = float(_GATE_CFG.get("dof_scaled_max", 3.0))  # for dof_scaled
# `percentile` mode (most robust to the heavy-tailed / mis-conditioned empirical d_sq — F-044
# refinement 2026-07-05): bypass iff d_sq > a cut calibrated from the training-d_sq empirical CDF.
# The cut is NOT theory-derived; it is chosen via `target_bypass_fraction → empirical threshold`
# (scripts/analysis/rr_confidence_probe.py emits the calibration table). `d_sq_cut` is model-specific.
_GATE_DSQ_CUT_RAW = _GATE_CFG.get("d_sq_cut", None)
_GATE_MODES = ("legacy_scalar", "chi2_tail", "dof_scaled", "percentile")
if _GATE_MODE not in _GATE_MODES:
    raise ValueError(
        f"rr_model.confidence_gate.mode must be one of {_GATE_MODES}, got {_GATE_MODE!r}"
    )
if _GATE_MODE == "percentile" and _GATE_DSQ_CUT_RAW is None:
    raise ValueError("rr_model.confidence_gate.mode='percentile' requires 'd_sq_cut' (calibrated cut)")
_GATE_DSQ_CUT: float = float(_GATE_DSQ_CUT_RAW) if _GATE_DSQ_CUT_RAW is not None else float("inf")


def _chi2_sf(x: float, dof: int) -> float:
    """Survival function P(χ²_dof > x) = Q(dof/2, x/2), regularized upper incomplete gamma.
    Pure-Python (Numerical Recipes gammq); the inference hot-path stays numpy-free."""
    if dof <= 0:
        return 1.0
    return _gammq(dof / 2.0, x / 2.0)


def _gammq(s: float, x: float) -> float:
    if x < 0.0 or s <= 0.0:
        raise ValueError("_gammq: require x>=0, s>0")
    if x == 0.0:
        return 1.0
    if x < s + 1.0:
        return 1.0 - _gser(s, x)          # series gives P; Q = 1 - P
    return _gcf(s, x)                       # continued fraction gives Q directly


def _gser(s: float, x: float) -> float:
    ap = s
    total = 1.0 / s
    delta = total
    for _ in range(1000):
        ap += 1.0
        delta *= x / ap
        total += delta
        if abs(delta) < abs(total) * 1e-15:
            break
    return total * math.exp(-x + s * math.log(x) - math.lgamma(s))


def _gcf(s: float, x: float) -> float:
    tiny = 1e-300
    b = x + 1.0 - s
    c = 1.0 / tiny
    d = 1.0 / b
    h = d
    for i in range(1, 1000):
        an = -i * (i - s)
        b += 2.0
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    return math.exp(-x + s * math.log(x) - math.lgamma(s)) * h


def _confidence_bypass(d_sq_raw: float, dof: int, confidence: float) -> bool:
    """True → bypass rr_fusion to the Gaussian score. Dispatches on `_GATE_MODE`.
    `d_sq_raw` is the UN-clipped Mahalanobis distance; `confidence` is exp(-0.5·clipped d_sq)."""
    if _GATE_MODE == "legacy_scalar":
        return confidence < _CONF_BYPASS                       # byte-identical to the historical gate
    if _GATE_MODE == "chi2_tail":
        return _chi2_sf(d_sq_raw, dof) < _GATE_P_THRESHOLD     # bypass only genuine upper-tail outliers
    if _GATE_MODE == "dof_scaled":
        return (d_sq_raw / dof) > _GATE_DOF_SCALED_MAX if dof > 0 else True
    if _GATE_MODE == "percentile":
        return d_sq_raw > _GATE_DSQ_CUT                         # cut calibrated from training-d_sq CDF
    raise ValueError(f"unknown _GATE_MODE {_GATE_MODE!r}")      # unreachable (validated at import)


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

        # Training-distribution metadata (F-044 percentile-gate provenance): per-row Mahalanobis d_sq
        # (SAME definition as predict()) → percentiles. Makes `confidence_gate.mode=percentile`
        # d_sq_cut a reproducible contract instead of an implicit assumption. effective_dof accounts
        # for constant-zero (price-anchored) columns, which contribute 0 to d_sq.
        _delta = Xs - np.asarray(conf_mu)
        _d_sq = np.einsum("ij,jk,ik->i", _delta, np.asarray(conf_P), _delta)
        _n_const_zero = int(np.sum(scale_std == 1.0))  # cols the trainer forced to unit std (const)
        training_distribution = {
            "n": int(n),
            "effective_dof": int(N_FEATURES - _n_const_zero),
            "d_sq_p50": float(np.percentile(_d_sq, 50)),
            "d_sq_p90": float(np.percentile(_d_sq, 90)),
            "d_sq_p95": float(np.percentile(_d_sq, 95)),
            "d_sq_p99": float(np.percentile(_d_sq, 99)),
        }

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
            "training_distribution": training_distribution,
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
    """Pure-Python inference engine for RR fusion feature vectors.

    Contract: ``len(features)`` must equal ``len(self.W)`` (the model's trained
    width). Longer or shorter vectors raise ``FeatureDimensionError`` — never
    silently truncated or padded (P0 2026-07-22; closes FAIL_OPEN under schema v4).
    """

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
        "n_features",
    )

    def __init__(self, state_dict: Dict[str, Any]) -> None:
        self.W = tuple(float(x) for x in state_dict["ridge_w"])
        self.b = float(state_dict["ridge_b"])
        self.n_features = len(self.W)

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
        # P0 FAIL-CLOSED (2026-07-22): never silently truncate longer vectors.
        # Schema v4 (39-dim) vs v3 models (38-dim) would misalign every trailing
        # feature under index truncation — that is a fail-open scoring path.
        # Exact width only; remap or retrain to change width.
        got = len(features)
        if got != n:
            raise FeatureDimensionError(
                f"NanoInferenceEngine.predict: expected exactly {n} features "
                f"(model n_features={n}), got {got}. "
                f"Refusing silent truncate/pad — remap or retrain for the live "
                f"schema (CANONICAL_FEATURE_DIM={CANONICAL_FEATURE_DIM})."
            )

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

        d_sq_raw = d_sq                        # F-044: keep pre-clip distance for the dof-aware gate
        if d_sq > _MAHAL_CLIP:
            d_sq = _MAHAL_CLIP

        confidence = math.exp(-0.5 * d_sq)
        confidence = min(1.0, max(0.0, confidence))

        dof = n - len(self.zero_indices)       # rank of the Mahalanobis form (zeroed dims contribute 0)
        if _confidence_bypass(d_sq_raw, dof, confidence):
            return {
                "final_score": float(gaussian_score),
                "expected_rr": 0.0,
                "probability_of_win": float(gaussian_p_win),
                "confidence": float(confidence),
                "status": "bypassed_low_confidence",
            }

        expected_rr = sum(X[i] * self.W[i] for i in range(n)) + self.b
        expected_rr = min(RR_SCORE_MAX, max(RR_SCORE_MIN, expected_rr))

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

