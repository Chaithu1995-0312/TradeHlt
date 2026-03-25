"""
rr_pattern_miner.py
===================
Feature → RR Pattern Miner — offline trainer + ultra-fast pure-Python inference.

# ─────────────────────────────────────────────────────────────────────────────
# DESIGN OVERVIEW
# ─────────────────────────────────────────────────────────────────────────────
#
# TRAINING PHASE  (offline, uses sklearn + numpy)
#   RRPatternTrainer.train(X, y_rr, y_win)
#     1. Normalize features (StandardScaler → scale_mu, scale_sigma)
#     2. Fit Ridge regression → W[11], b
#     3. Fit GaussianNB manually → C[2][11], V[2][11], mu[2][11]
#     4. Fit Ledoit-Wolf covariance → conf_mu[11], conf_P[11][11] (precision)
#     5. LOOCV evaluation → RR corr, Brier score, calibration buckets
#     6. Serialize to JSON (< 5 KB)
#
# INFERENCE PHASE  (pure Python, <1ms, O(K²), no imports except math)
#   NanoInferenceEngine(state_dict).predict(...)
#     Step 1: Assemble raw 11-vector (O(1) trig lookup, one-hot session)
#     Step 2: Normalize X (11 ops)
#     Step 3C: Mahalanobis d² → confidence  (early exit < 0.3)
#     Step 3A: expected_rr = dot(W, X) + b  (11 FMAs, clamped [-3, 5])
#     Step 3B: GNB log-likelihood → softmax → p_win  (22 ops + 2 exp)
#     Step 4: Fusion + safeguards
#
# ─────────────────────────────────────────────────────────────────────────────
# FEATURE SCHEMA v2 (11 features — NO Gaussian leakage)
#   [depth, body, disp,
#    is_asia, is_london, is_newyork,   ← one-hot session (replaces ordinal)
#    sin_hour, cos_hour,
#    depth_body, depth_disp, body_disp]
#
#   gaussian_score, gaussian_p_win are NOT in X.
#   They are passed separately for the fusion formula only.
#
# ─────────────────────────────────────────────────────────────────────────────
# ASSUMPTIONS
#   • Dataset size: 20–500 trades (LOOCV is O(N * K²), feasible)
#   • Feature distributions are roughly Gaussian (Naive Bayes valid)
#   • Ledoit-Wolf shrinkage handles collinear interaction features
#   • Ridge alpha=10.0 for regularization on small datasets
#
# INVARIANTS
#   • Feature vector always exactly 11 elements
#   • state_dict keys are stable — loading without sklearn is safe
#   • NanoInferenceEngine is stateless after __init__ (thread-safe)
#   • gaussian_score passed through unmodified when confidence < 0.3
#
# EDGE CASES
#   • std == 0 feature column → scale_sigma element set to 1.0
#   • Only one class in y_win → GNB log-prior for missing class = log(ε)
#   • N < MIN_SAMPLES → ValueError raised before training
#   • All trades same session → one-hot std = 0, handled by std guard
#
# FAILURE MODES
#   • Covariance matrix singular: Ledoit-Wolf + ε=1e-6 diagonal guard
#   • model JSON missing: RRFusionLayer catches FileNotFoundError gracefully
#   • math.exp overflow: d² clamped ≤ 500, RR clamped [-3, 5]
#
# RISKS
#   • Overfitting: LOOCV RR corr < 0.05 triggers warning
#   • Covariance instability: Ledoit-Wolf mitigates
#
# ROLLBACK
#   • Delete/rename rr_model.json → RRFusionLayer returns gaussian_score unchanged
"""

import json
import math
import os
import warnings
from typing import List, Tuple, Dict, Any, Optional

N_FEATURES = 11
MIN_SAMPLES = 20
DEFAULT_MODEL_PATH = "models/rr_model.json"

# ─────────────────────────────────────────────────────────────────────────────
# Shared constants
# ─────────────────────────────────────────────────────────────────────────────

_SIN_HOUR: Tuple[float, ...] = tuple(
    math.sin(2.0 * math.pi * h / 24.0) for h in range(24)
)
_COS_HOUR: Tuple[float, ...] = tuple(
    math.cos(2.0 * math.pi * h / 24.0) for h in range(24)
)


def _sigmoid(x: float) -> float:
    """Numerically stable sigmoid. Clamps at ±20 to prevent exp overflow."""
    if x >= 20.0:
        return 1.0
    if x <= -20.0:
        return 0.0
    return 1.0 / (1.0 + math.exp(-x))


# ─────────────────────────────────────────────────────────────────────────────
# TRAINING PHASE
# ─────────────────────────────────────────────────────────────────────────────

class RRPatternTrainer:
    """
    Offline trainer that generates the state_dict for NanoInferenceEngine.

    Usage:
        trainer = RRPatternTrainer()
        trainer.train(X, y_rr, y_win)
        trainer.save("models/rr_model.json")
        report = trainer.loocv_report(X, y_rr, y_win)
    """

    def __init__(self, ridge_alpha: float = 10.0, gnb_var_smoothing: float = 1e-9):
        self.ridge_alpha = ridge_alpha
        self.gnb_var_smoothing = gnb_var_smoothing
        self.state: Optional[Dict[str, Any]] = None

    def train(
        self,
        X: List[List[float]],
        y_rr: List[float],
        y_win: List[int],
    ) -> Dict[str, Any]:
        """
        Fit all model components and return the serializable state_dict.

        Args:
            X:     (N, 11) feature matrix  [no Gaussian features]
            y_rr:  (N,)   regression targets (actual RR)
            y_win: (N,)   classification targets (0/1)

        Returns:
            state_dict compatible with NanoInferenceEngine
        """
        try:
            import numpy as np
            from sklearn.linear_model import Ridge
            from sklearn.covariance import LedoitWolf
        except ImportError as e:
            raise ImportError(
                "Training requires numpy and scikit-learn. "
                "Install with: pip install numpy scikit-learn"
            ) from e

        N = len(X)
        if N < MIN_SAMPLES:
            raise ValueError(f"Need >= {MIN_SAMPLES} samples, got {N}.")

        Xnp = np.array(X, dtype=np.float64)
        yr  = np.array(y_rr, dtype=np.float64)
        yw  = np.array(y_win, dtype=np.int32)

        # ── 1. Normalization ──────────────────────────────────────────────
        scale_mu  = Xnp.mean(axis=0)
        scale_std = Xnp.std(axis=0)
        scale_std[scale_std == 0.0] = 1.0  # Guard: zero-variance feature
        Xs = (Xnp - scale_mu) / scale_std

        # ── 2. Ridge Regression ───────────────────────────────────────────
        ridge = Ridge(alpha=self.ridge_alpha, fit_intercept=True)
        ridge.fit(Xs, yr)
        ridge_w = ridge.coef_.tolist()
        ridge_b = float(ridge.intercept_)

        # ── 3. Gaussian Naive Bayes ───────────────────────────────────────
        gnb_C: List[List[float]] = []
        gnb_V: List[List[float]] = []
        gnb_mu: List[List[float]] = []
        for c in [0, 1]:
            mask = yw == c
            n_c  = int(mask.sum())
            if n_c == 0:
                prior_c = 1e-10
                mu_c    = Xs.mean(axis=0)
                var_c   = np.ones(N_FEATURES)
            else:
                prior_c = n_c / N
                mu_c    = Xs[mask].mean(axis=0)
                var_c   = Xs[mask].var(axis=0) + self.gnb_var_smoothing

            C_c = np.log(prior_c) - 0.5 * np.log(2.0 * math.pi * var_c)
            V_c = 1.0 / var_c

            gnb_C.append(C_c.tolist())
            gnb_V.append(V_c.tolist())
            gnb_mu.append(mu_c.tolist())

        # ── 4. Mahalanobis Confidence (Ledoit-Wolf precision) ─────────────
        eps = 1e-6
        try:
            lw = LedoitWolf(assume_centered=False)
            lw.fit(Xs)
            conf_mu = lw.location_.tolist()
            conf_P  = lw.get_precision().tolist()
        except Exception as exc:
            warnings.warn(
                f"LedoitWolf failed ({exc}); falling back to diagonal precision."
            )
            conf_mu = Xs.mean(axis=0).tolist()
            var_all = Xs.var(axis=0) + eps
            P_diag  = np.diag(1.0 / var_all)
            conf_P  = P_diag.tolist()

        # ── 5. Assemble state dict ────────────────────────────────────────
        self.state = {
            "ridge_w":      ridge_w,
            "ridge_b":      ridge_b,
            "gnb_C":        gnb_C,
            "gnb_V":        gnb_V,
            "gnb_mu":       gnb_mu,
            "conf_mu":      conf_mu,
            "conf_P":       conf_P,
            "scale_mu":     scale_mu.tolist(),
            "scale_sigma":  scale_std.tolist(),
            "n_features":   N_FEATURES,
            "n_train":      N,
            "ridge_alpha":  self.ridge_alpha,
            "feature_schema": "v2_no_gaussian_onehot_session",
        }
        return self.state

    def save(self, path: str = DEFAULT_MODEL_PATH) -> None:
        """Serialize state_dict to JSON (< 5 KB for K=11)."""
        if self.state is None:
            raise RuntimeError("Call train() before save().")
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.state, f, separators=(",", ":"))
        size_kb = os.path.getsize(path) / 1024.0
        if size_kb > 5.0:
            warnings.warn(f"Model file {path} is {size_kb:.1f}KB — exceeds 5KB target.")

    def loocv_report(
        self,
        X: List[List[float]],
        y_rr: List[float],
        y_win: List[int],
    ) -> Dict[str, Any]:
        """
        Leave-One-Out Cross-Validation evaluation.

        Reports:
          - RR Pearson correlation
          - Brier score
          - Calibration buckets (10 decile bins)
        """
        try:
            import numpy as np
            from sklearn.linear_model import Ridge
        except ImportError as e:
            raise ImportError("LOOCV requires numpy and scikit-learn.") from e

        N = len(X)
        if N < MIN_SAMPLES:
            raise ValueError(f"Need >= {MIN_SAMPLES} samples for LOOCV, got {N}.")

        Xnp = np.array(X, dtype=np.float64)
        yr  = np.array(y_rr,  dtype=np.float64)
        yw  = np.array(y_win, dtype=np.int32)

        pred_rr   = np.zeros(N)
        pred_pwin = np.zeros(N)

        for i in range(N):
            idx_tr = list(range(N))
            idx_tr.pop(i)
            Xtr  = Xnp[idx_tr]
            ytr  = yr[idx_tr]
            ywtr = yw[idx_tr]

            mu  = Xtr.mean(axis=0)
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
                n_c  = int(mask.sum())
                if n_c == 0:
                    log_probs.append(-1e9)
                    continue
                prior_c = n_c / len(ywtr)
                mu_c    = Xtr_s[mask].mean(axis=0)
                var_c   = Xtr_s[mask].var(axis=0) + self.gnb_var_smoothing
                C_c = math.log(prior_c) - 0.5 * float(np.log(2.0 * math.pi * var_c).sum())
                ll  = C_c - 0.5 * float(((Xte_s - mu_c) ** 2 / var_c).sum())
                log_probs.append(ll)

            max_lp = max(log_probs)
            exps   = [math.exp(lp - max_lp) for lp in log_probs]
            pred_pwin[i] = exps[1] / (exps[0] + exps[1])

        rr_corr = float(np.corrcoef(pred_rr, yr)[0, 1])
        if math.isnan(rr_corr):
            rr_corr = 0.0
        if abs(rr_corr) < 0.05:
            warnings.warn(
                f"LOOCV RR correlation is very low ({rr_corr:.3f}). "
                "Model may not be learning meaningful RR patterns."
            )

        brier = float(((pred_pwin - yw.astype(float)) ** 2).mean())

        n_buckets = 10
        buckets = []
        sorted_idx = np.argsort(pred_pwin)
        chunk = N // n_buckets
        for b in range(n_buckets):
            start = b * chunk
            end   = start + chunk if b < n_buckets - 1 else N
            bi    = sorted_idx[start:end]
            buckets.append({
                "predicted_p_win": round(float(pred_pwin[bi].mean()), 4),
                "actual_win_rate": round(float(yw[bi].mean()), 4),
                "n": int(len(bi)),
            })

        return {
            "rr_corr":             round(rr_corr, 4),
            "brier_score":         round(brier, 4),
            "calibration_buckets": buckets,
            "n_samples":           N,
        }


# ─────────────────────────────────────────────────────────────────────────────
# INFERENCE PHASE — Pure Python, zero sklearn, zero numpy
# ─────────────────────────────────────────────────────────────────────────────

class NanoInferenceEngine:
    """
    Ultra-fast pure-Python inference engine.

    Feature schema v2 (K=11):
      [depth, body, disp,
       is_asia, is_london, is_newyork,
       sin_hour, cos_hour,
       depth_body, depth_disp, body_disp]

    gaussian_score and gaussian_p_win are NOT ML features — they are
    passed separately and used only in the fusion formula.

    Latency estimate (K=11):
      ~7–10 µs total (well under 1ms target)

    Memory:  ~2.1KB (W + conf_P + gnb arrays + lookups)
    Thread-safety: STATELESS after __init__ — safe for concurrent calls.
    """

    __slots__ = (
        "W", "b",
        "conf_mu", "conf_P",
        "gnb_C_loss", "gnb_V_loss", "gnb_mu_loss",
        "gnb_C_win",  "gnb_V_win",  "gnb_mu_win",
        "scale_mu", "scale_sigma",
        "sin_lookup", "cos_lookup",
    )

    def __init__(self, state_dict: Dict[str, Any]) -> None:
        """
        Initialize from state_dict.
        All matrices converted to nested tuples for immutable, GC-friendly storage.
        """
        self.W = tuple(float(x) for x in state_dict["ridge_w"])
        self.b = float(state_dict["ridge_b"])

        self.scale_mu    = tuple(float(x) for x in state_dict["scale_mu"])
        self.scale_sigma = tuple(float(x) for x in state_dict["scale_sigma"])

        self.gnb_C_loss  = tuple(float(x) for x in state_dict["gnb_C"][0])
        self.gnb_V_loss  = tuple(float(x) for x in state_dict["gnb_V"][0])
        self.gnb_mu_loss = tuple(float(x) for x in state_dict["gnb_mu"][0])
        self.gnb_C_win   = tuple(float(x) for x in state_dict["gnb_C"][1])
        self.gnb_V_win   = tuple(float(x) for x in state_dict["gnb_V"][1])
        self.gnb_mu_win  = tuple(float(x) for x in state_dict["gnb_mu"][1])

        self.conf_mu = tuple(float(x) for x in state_dict["conf_mu"])
        self.conf_P  = tuple(
            tuple(float(x) for x in row) for row in state_dict["conf_P"]
        )

        self.sin_lookup = _SIN_HOUR
        self.cos_lookup = _COS_HOUR

    @classmethod
    def load(cls, path: str = DEFAULT_MODEL_PATH) -> "NanoInferenceEngine":
        """Load from JSON file."""
        with open(path, "r") as f:
            state = json.load(f)
        return cls(state)

    def predict(
        self,
        depth:          float,
        body:           float,
        disp:           float,
        gaussian_score: float,   # for fusion formula + safeguard — NOT in X
        gaussian_p_win: float,   # fallback p_win for bypassed status
        is_asia:        float,   # one-hot session
        is_london:      float,
        is_newyork:     float,
        hour:           int,
        threshold:      float = 0.5,
    ) -> Dict[str, Any]:
        """
        Run full inference pipeline.

        Args:
            depth, body, disp:       market microstructure features
            gaussian_score:          Gaussian engine score (0-1) — fusion only
            gaussian_p_win:          Gaussian p(win) — returned on bypass
            is_asia, is_london, is_newyork: one-hot session encoding
            hour:                    integer hour (0-23)
            threshold:               gaussian_score below which ML cannot raise score

        Returns:
            dict: final_score, expected_rr, probability_of_win, confidence, status
        """
        # Localize for hot-path performance
        sin_l  = self.sin_lookup
        cos_l  = self.cos_lookup
        smu    = self.scale_mu
        ssig   = self.scale_sigma
        W      = self.W
        b      = self.b
        cmu    = self.conf_mu
        P      = self.conf_P

        # ── Step 1: Feature Assembly ──────────────────────────────────────
        hour_idx = int(hour) % 24
        sin_h    = sin_l[hour_idx]
        cos_h    = cos_l[hour_idx]
        d_b      = depth * body
        d_d      = depth * disp
        b_d      = body  * disp

        # ── Step 2: Normalize (11 divisions) ─────────────────────────────
        X = (
            (depth      - smu[0])  / ssig[0],
            (body       - smu[1])  / ssig[1],
            (disp       - smu[2])  / ssig[2],
            (is_asia    - smu[3])  / ssig[3],
            (is_london  - smu[4])  / ssig[4],
            (is_newyork - smu[5])  / ssig[5],
            (sin_h      - smu[6])  / ssig[6],
            (cos_h      - smu[7])  / ssig[7],
            (d_b        - smu[8])  / ssig[8],
            (d_d        - smu[9])  / ssig[9],
            (b_d        - smu[10]) / ssig[10],
        )

        # ── Step 3C: Mahalanobis (early exit if low confidence) ───────────
        d0  = X[0]  - cmu[0];  d1  = X[1]  - cmu[1];  d2  = X[2]  - cmu[2]
        d3  = X[3]  - cmu[3];  d4  = X[4]  - cmu[4];  d5  = X[5]  - cmu[5]
        d6  = X[6]  - cmu[6];  d7  = X[7]  - cmu[7];  d8  = X[8]  - cmu[8]
        d9  = X[9]  - cmu[9];  d10 = X[10] - cmu[10]
        delta = (d0, d1, d2, d3, d4, d5, d6, d7, d8, d9, d10)

        d_sq = 0.0
        for i in range(11):
            Pi       = P[i]
            di       = delta[i]
            row_dot  = (
                Pi[0]*delta[0]  + Pi[1]*delta[1]  + Pi[2]*delta[2]  +
                Pi[3]*delta[3]  + Pi[4]*delta[4]  + Pi[5]*delta[5]  +
                Pi[6]*delta[6]  + Pi[7]*delta[7]  + Pi[8]*delta[8]  +
                Pi[9]*delta[9]  + Pi[10]*delta[10]
            )
            d_sq += di * row_dot

        # Clamp d² to prevent exp underflow → confidence = 0
        if d_sq > 500.0:
            d_sq = 500.0

        confidence = math.exp(-0.5 * d_sq)
        # Hard bounds: confidence ∈ [0, 1]
        if confidence > 1.0:
            confidence = 1.0
        elif confidence < 0.0:
            confidence = 0.0

        # SAFEGUARD 1: Low confidence → bypass ML entirely
        if confidence < 0.3:
            return {
                "final_score":        float(gaussian_score),
                "expected_rr":        0.0,
                "probability_of_win": float(gaussian_p_win),
                "confidence":         float(confidence),
                "status":             "bypassed_low_confidence",
            }

        # ── Step 3A: Expected RR — Ridge dot product ──────────────────────
        expected_rr = (
            X[0]*W[0]  + X[1]*W[1]  + X[2]*W[2]  + X[3]*W[3]  +
            X[4]*W[4]  + X[5]*W[5]  + X[6]*W[6]  + X[7]*W[7]  +
            X[8]*W[8]  + X[9]*W[9]  + X[10]*W[10]
        ) + b

        # Sanity clamp: expected_rr ∈ [-3, 5]
        if expected_rr > 5.0:
            expected_rr = 5.0
        elif expected_rr < -3.0:
            expected_rr = -3.0

        # ── Step 3B: GNB log-likelihood → softmax → p_win ─────────────────
        CL = self.gnb_C_loss;  VL = self.gnb_V_loss;  ML = self.gnb_mu_loss
        ll_loss = (
            CL[0]  - 0.5*VL[0]  *(X[0] -ML[0]) **2 +
            CL[1]  - 0.5*VL[1]  *(X[1] -ML[1]) **2 +
            CL[2]  - 0.5*VL[2]  *(X[2] -ML[2]) **2 +
            CL[3]  - 0.5*VL[3]  *(X[3] -ML[3]) **2 +
            CL[4]  - 0.5*VL[4]  *(X[4] -ML[4]) **2 +
            CL[5]  - 0.5*VL[5]  *(X[5] -ML[5]) **2 +
            CL[6]  - 0.5*VL[6]  *(X[6] -ML[6]) **2 +
            CL[7]  - 0.5*VL[7]  *(X[7] -ML[7]) **2 +
            CL[8]  - 0.5*VL[8]  *(X[8] -ML[8]) **2 +
            CL[9]  - 0.5*VL[9]  *(X[9] -ML[9]) **2 +
            CL[10] - 0.5*VL[10] *(X[10]-ML[10])**2
        )

        CW = self.gnb_C_win;   VW = self.gnb_V_win;   MW = self.gnb_mu_win
        ll_win = (
            CW[0]  - 0.5*VW[0]  *(X[0] -MW[0]) **2 +
            CW[1]  - 0.5*VW[1]  *(X[1] -MW[1]) **2 +
            CW[2]  - 0.5*VW[2]  *(X[2] -MW[2]) **2 +
            CW[3]  - 0.5*VW[3]  *(X[3] -MW[3]) **2 +
            CW[4]  - 0.5*VW[4]  *(X[4] -MW[4]) **2 +
            CW[5]  - 0.5*VW[5]  *(X[5] -MW[5]) **2 +
            CW[6]  - 0.5*VW[6]  *(X[6] -MW[6]) **2 +
            CW[7]  - 0.5*VW[7]  *(X[7] -MW[7]) **2 +
            CW[8]  - 0.5*VW[8]  *(X[8] -MW[8]) **2 +
            CW[9]  - 0.5*VW[9]  *(X[9] -MW[9]) **2 +
            CW[10] - 0.5*VW[10] *(X[10]-MW[10])**2
        )

        max_ll   = ll_win if ll_win > ll_loss else ll_loss
        exp_loss = math.exp(ll_loss - max_ll)
        exp_win  = math.exp(ll_win  - max_ll)
        p_win    = exp_win / (exp_loss + exp_win)

        # ── Step 4: Fusion ────────────────────────────────────────────────
        ml_score    = _sigmoid(expected_rr / 3.0)
        final_score = (
            0.5 * gaussian_score +
            0.3 * ml_score +
            0.2 * confidence
        )

        # SAFEGUARD 2: ML cannot raise score below gaussian threshold
        status = "success"
        if gaussian_score < threshold and final_score > gaussian_score:
            final_score = gaussian_score
            status = "capped_by_threshold"

        return {
            "final_score":        float(final_score),
            "expected_rr":        float(expected_rr),
            "probability_of_win": float(p_win),
            "confidence":         float(confidence),
            "status":             status,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Convenience wrapper
# ─────────────────────────────────────────────────────────────────────────────

def train_and_save(
    X:           List[List[float]],
    y_rr:        List[float],
    y_win:       List[int],
    path:        str = DEFAULT_MODEL_PATH,
    ridge_alpha: float = 10.0,
) -> Dict[str, Any]:
    """
    Train model and save to JSON. Returns LOOCV report.

    Usage:
        from rr_dataset_builder import build_dataset
        from rr_pattern_miner import train_and_save

        X, y_rr, y_win = build_dataset(trades)
        report = train_and_save(X, y_rr, y_win)
        print(report)
    """
    trainer = RRPatternTrainer(ridge_alpha=ridge_alpha)
    trainer.train(X, y_rr, y_win)
    trainer.save(path)
    return trainer.loocv_report(X, y_rr, y_win)


# ─────────────────────────────────────────────────────────────────────────────
# Standalone test
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import random
    random.seed(42)

    N = 60
    sessions = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]
    X = []
    for i in range(N):
        depth = random.uniform(0.1, 0.6)
        body  = random.uniform(0.3, 0.8)
        disp  = random.uniform(0.1, 0.5)
        sa, sl, sn = sessions[i % 3]
        h = random.randint(0, 23)
        X.append([
            depth, body, disp,
            sa, sl, sn,
            _SIN_HOUR[h], _COS_HOUR[h],
            depth * body, depth * disp, body * disp,
        ])

    y_rr  = [random.uniform(-2.0, 4.0) for _ in range(N)]
    y_win = [1 if rr > 0 else 0 for rr in y_rr]

    print("Training v2 model (no Gaussian leakage, one-hot session)...")
    trainer = RRPatternTrainer()
    state = trainer.train(X, y_rr, y_win)
    trainer.save("models/rr_model_test.json")
    print(f"Schema: {state.get('feature_schema')}")

    print("\nRunning LOOCV...")
    report = trainer.loocv_report(X, y_rr, y_win)
    print(f"RR Correlation: {report['rr_corr']}")
    print(f"Brier Score:    {report['brier_score']}")

    print("\nLoading engine and running inference...")
    engine = NanoInferenceEngine.load("models/rr_model_test.json")
    result = engine.predict(
        depth=0.35, body=0.55, disp=0.25,
        gaussian_score=0.65, gaussian_p_win=0.60,
        is_asia=0.0, is_london=1.0, is_newyork=0.0,
        hour=14, threshold=0.5,
    )
    print(f"Inference result: {result}")
    assert result["status"] in ("success", "capped_by_threshold", "bypassed_low_confidence")
    assert -3.0 <= result["expected_rr"] <= 5.0, "RR clamp violated"
    assert 0.0 <= result["confidence"] <= 1.0, "Confidence bounds violated"
    print("\nSelf-test PASSED.")