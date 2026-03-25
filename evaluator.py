"""
evaluator.py
═══════════════════════════════════════════════════════════════════════════════
Model evaluation: accuracy, confidence buckets, score-outcome calibration.

The composite score used for model selection (see model_registry.py) weights
high-confidence bucket win rates more than raw accuracy — because you only
trade when confidence is high. A model that's 60% accurate overall but 75%
accurate in the 0.7+ bucket is far more useful than one that's 65% flat.

Also provides:
  evaluate_gaussian() — evaluate a GaussianNBModel against raw pnl_rr
  should_update()     — safe gate: ML must beat Gaussian by margin + stability
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger("Evaluator")

CONFIDENCE_BUCKETS = [
    (0.50, 0.60, "0.50-0.60"),
    (0.60, 0.70, "0.60-0.70"),
    (0.70, 0.80, "0.70-0.80"),
    (0.80, 1.01, "0.80-1.00"),
]


# ─────────────────────────────────────────────────────────────────────────────
# GAUSSIAN EVALUATION (FIX 5: use corr(expected_rr, pnl_rr) not gaussian_score)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class GaussianEvalResult:
    n_samples:         int
    corr_expected_rr:  float   # Pearson corr(expected_rr, pnl_rr_net) — FIX 5
    calibration_error: float   # |predicted_win_rate - actual_win_rate|
    mean_expected_rr:  float
    mean_actual_rr:    float
    class_distribution: dict

    def print(self, label: str = "", reporter=None) -> None:
        """
        Print evaluation summary.

        Parameters
        ----------
        label    : optional tag shown in the header
        reporter : optional InsightReporter — if provided, generates LLM narrative
                   in addition to the static table output
        """
        tag = f" [{label}]" if label else ""
        print(f"\n  GaussianEval{tag}  n={self.n_samples}")
        print(f"  corr(expected_rr, pnl_rr): {self.corr_expected_rr:+.4f}")
        print(f"  Calibration error:          {self.calibration_error:+.4f}")
        print(f"  Mean expected_rr:           {self.mean_expected_rr:.4f}")
        print(f"  Mean actual_rr:             {self.mean_actual_rr:.4f}")
        print(f"  Class distribution:         {self.class_distribution}")
        print()
        if reporter is not None:
            try:
                reporter.eval_report(self, model_type=f"Gaussian{tag}")
            except Exception as e:
                log.debug(f"GaussianEvalResult.print: reporter error (non-fatal): {e}")


def _pearson(xs: list, ys: list) -> float:
    """Pearson correlation between two lists."""
    n = len(xs)
    if n < 3:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / n
    sx  = math.sqrt(sum((x - mx) ** 2 for x in xs) / n)
    sy  = math.sqrt(sum((y - my) ** 2 for y in ys) / n)
    return cov / (sx * sy) if sx > 0 and sy > 0 else 0.0


def evaluate_gaussian(
    model,
    scaler,
    X: list[list[float]],
    y_rr: list[float],
) -> GaussianEvalResult:
    """
    Evaluate a GaussianNBModel on (X_raw, y_rr_actual).

    Uses corr(expected_rr, pnl_rr) — FIX 5 from design review.
    X must be RAW (unscaled) — function applies scaler internally.

    Parameters
    ----------
    model  : GaussianNBModel
    scaler : StandardScaler (trained with model — same version)
    X      : raw 11-feature vectors
    y_rr   : actual pnl_rr_net values

    Returns
    -------
    GaussianEvalResult
    """
    n = len(X)
    if n == 0:
        return GaussianEvalResult(0, 0.0, 0.0, 0.0, 0.0, {})

    # Scale using saved scaler
    X_scaled = scaler.transform(X)

    # Predict expected_rr for each sample
    pred_rr = []
    pred_p_win = []
    for x in X_scaled:
        exp_rr, conf, probs = model.predict_expected_rr(x)
        pred_rr.append(exp_rr)
        pred_p_win.append(sum(probs[2:]))  # P(class 2 or 3) = P(RR >= 1)

    # FIX 5: correlation against actual pnl_rr_net (not gaussian_score)
    corr = _pearson(pred_rr, y_rr)

    # Calibration error: |mean predicted win rate - actual win rate|
    actual_wins = [1 if r >= 1.0 else 0 for r in y_rr]
    mean_pred_win   = sum(pred_p_win) / n
    mean_actual_win = sum(actual_wins) / n
    cal_error = abs(mean_pred_win - mean_actual_win)

    # Class distribution (from actual y)
    from dataset_builder import rr_to_class
    y_cls = [rr_to_class(r) for r in y_rr]
    class_dist = {f"class_{c}": y_cls.count(c) for c in range(4)}

    return GaussianEvalResult(
        n_samples         = n,
        corr_expected_rr  = round(corr, 4),
        calibration_error = round(cal_error, 4),
        mean_expected_rr  = round(sum(pred_rr) / n, 4),
        mean_actual_rr    = round(sum(y_rr) / n, 4),
        class_distribution = class_dist,
    )


def should_update(
    ml_metrics: dict,
    gaussian_metrics: dict,
    corr_margin: float = 0.02,
) -> tuple[bool, str]:
    """
    Safe ML → Gaussian update gate.

    ML is accepted ONLY IF:
      1. ml_corr > gaussian_corr + margin (statistically better)
      2. ml_calibration_error < gaussian_calibration_error
      3. Both correlations are well-defined (n >= 3)

    Parameters
    ----------
    ml_metrics       : dict with keys corr_expected_rr, calibration_error
    gaussian_metrics : dict with keys corr_expected_rr, calibration_error
    corr_margin      : minimum improvement required (default 0.02)

    Returns
    -------
    (should_update: bool, reason: str)
    """
    ml_corr    = ml_metrics.get("corr_expected_rr",  0.0)
    ml_cal     = ml_metrics.get("calibration_error",  1.0)
    gauss_corr = gaussian_metrics.get("corr_expected_rr", 0.0)
    gauss_cal  = gaussian_metrics.get("calibration_error", 1.0)

    corr_better = ml_corr > gauss_corr + corr_margin
    cal_better  = ml_cal  < gauss_cal

    if corr_better and cal_better:
        reason = (
            f"ML approved: corr {gauss_corr:+.4f} → {ml_corr:+.4f} "
            f"(+{ml_corr - gauss_corr:.4f} > margin={corr_margin}) "
            f"AND calibration {gauss_cal:.4f} → {ml_cal:.4f}"
        )
        return True, reason
    elif corr_better and not cal_better:
        reason = (
            f"ML BLOCKED: corr improvement passes ({ml_corr:+.4f} > "
            f"{gauss_corr:+.4f} + {corr_margin}) BUT calibration worsened "
            f"({ml_cal:.4f} > {gauss_cal:.4f})"
        )
        return False, reason
    elif cal_better and not corr_better:
        reason = (
            f"ML BLOCKED: calibration improved ({ml_cal:.4f} < {gauss_cal:.4f}) "
            f"BUT correlation gain insufficient "
            f"({ml_corr:+.4f} - {gauss_corr:+.4f} = {ml_corr - gauss_corr:.4f} < {corr_margin})"
        )
        return False, reason
    else:
        reason = (
            f"ML BLOCKED: no improvement — "
            f"corr {gauss_corr:+.4f} → {ml_corr:+.4f}, "
            f"calibration {gauss_cal:.4f} → {ml_cal:.4f}"
        )
        return False, reason


# ─────────────────────────────────────────────────────────────────────────────
# RESULT (neural net evaluator — unchanged)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class EvalResult:
    n_samples:     int
    accuracy:      float
    precision:     float
    recall:        float
    bucket_stats:  dict[str, dict]   # label → {count, win_rate}
    composite_score: float           # used for model selection

    def print(self, label: str = "", reporter=None) -> None:
        """
        Print evaluation summary.

        Parameters
        ----------
        label    : optional tag shown in the header
        reporter : optional InsightReporter — if provided, generates LLM narrative
        """
        tag = f" [{label}]" if label else ""
        print(f"\n  Eval{tag}  n={self.n_samples}")
        print(f"  Accuracy:  {self.accuracy:.4f}")
        print(f"  Precision: {self.precision:.4f}")
        print(f"  Recall:    {self.recall:.4f}")
        print(f"  Composite: {self.composite_score:.4f}")
        print(f"  Confidence buckets:")
        for bucket_label, stats in self.bucket_stats.items():
            wr = stats.get("win_rate")
            wr_str = f"{wr:.3f}" if wr is not None else "  N/A"
            print(f"    {bucket_label}  count={stats['count']:>4}  win_rate={wr_str}")
        print()
        if reporter is not None:
            eval_dict = {
                "n_samples":          self.n_samples,
                "corr_expected_rr":   self.composite_score,
                "calibration_error":  1.0 - self.accuracy,
                "mean_expected_rr":   self.composite_score,
                "mean_actual_rr":     self.accuracy,
                "class_distribution": self.bucket_stats,
            }
            try:
                reporter.eval_report(eval_dict, model_type=f"ML{tag}")
            except Exception as e:
                log.debug(f"EvalResult.print: reporter error (non-fatal): {e}")


# ─────────────────────────────────────────────────────────────────────────────
# EVALUATOR (neural net — unchanged)
# ─────────────────────────────────────────────────────────────────────────────

def evaluate(
    model,
    X: list[list[float]],
    y: list[int],
    threshold: float = 0.5,
) -> EvalResult:
    """
    Evaluate a trained TradeNet on held-out validation data.

    Parameters
    ----------
    model     : trained model (eval mode)
    X         : feature vectors (validation set — future data only)
    y         : ground-truth labels
    threshold : decision threshold for binary predictions

    Returns
    -------
    EvalResult
    """
    import torch

    model.eval()
    X_t = torch.tensor(X, dtype=torch.float32)
    y_arr = list(y)

    with torch.no_grad():
        preds_raw = model(X_t).numpy().flatten().tolist()

    n = len(preds_raw)
    pred_labels = [1 if p >= threshold else 0 for p in preds_raw]

    # ── Accuracy ──────────────────────────────────────────────────────────────
    correct  = sum(pl == yl for pl, yl in zip(pred_labels, y_arr))
    accuracy = correct / n if n > 0 else 0.0

    # ── Precision / Recall ────────────────────────────────────────────────────
    tp = sum(pl == 1 and yl == 1 for pl, yl in zip(pred_labels, y_arr))
    fp = sum(pl == 1 and yl == 0 for pl, yl in zip(pred_labels, y_arr))
    fn = sum(pl == 0 and yl == 1 for pl, yl in zip(pred_labels, y_arr))
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0

    # ── Confidence buckets ────────────────────────────────────────────────────
    bucket_stats: dict[str, dict] = {}
    for lo, hi, label in CONFIDENCE_BUCKETS:
        bucket = [
            yl for p, yl in zip(preds_raw, y_arr)
            if lo <= p < hi
        ]
        if bucket:
            bucket_stats[label] = {
                "count":    len(bucket),
                "win_rate": sum(bucket) / len(bucket),
            }
        else:
            bucket_stats[label] = {"count": 0, "win_rate": None}

    # ── Composite score (trading-weighted) ────────────────────────────────────
    composite = _composite_score(accuracy, bucket_stats)

    return EvalResult(
        n_samples       = n,
        accuracy        = accuracy,
        precision       = precision,
        recall          = recall,
        bucket_stats    = bucket_stats,
        composite_score = composite,
    )


# ─────────────────────────────────────────────────────────────────────────────
# COMPOSITE SCORE
# ─────────────────────────────────────────────────────────────────────────────

def _composite_score(accuracy: float, bucket_stats: dict) -> float:
    """
    Weighted score that rewards high-confidence bucket accuracy.
    Trading only happens at high confidence — overall accuracy is secondary.

    Weights:
      40% overall accuracy
      30% win_rate in [0.70-0.80] bucket
      30% win_rate in [0.80-1.00] bucket
    """
    wr_high  = bucket_stats.get("0.70-0.80", {}).get("win_rate") or 0.0
    wr_elite = bucket_stats.get("0.80-1.00", {}).get("win_rate") or 0.0

    return (0.40 * accuracy) + (0.30 * wr_high) + (0.30 * wr_elite)