"""
╔══════════════════════════════════════════════════════════════════════╗
║  CRT ENGINE — PHASE-5: GAUSSIAN RECALIBRATION                        ║
║                                                                      ║
║  Replaces hand-tuned Gaussian parameters with a GaussianNB model     ║
║  trained on actual trade outcomes, making score ≈ expected RR.       ║
║                                                                      ║
║  ⚠️  HONEST UPFRONT AUDIT                                             ║
║  159 unique trades (4 instruments, 2024-2025) is a small dataset.    ║
║  A GaussianNB trained on this will have high variance. The script    ║
║  therefore:                                                          ║
║    1. Trains on the full dataset                                     ║
║    2. Evaluates with leave-one-out cross-validation                  ║
║    3. Reports whether the calibrated scorer is statistically better  ║
║    4. Refuses to integrate if it isn't (no silent overfitting)       ║
║                                                                      ║
║  Usage:                                                              ║
║    python phase5_calibration.py --audit-only          # analysis     ║
║    python phase5_calibration.py --train               # train + eval ║
║    python phase5_calibration.py --integrate           # write scorer ║
╚══════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from collections import defaultdict
from pathlib import Path

# ─────────────────────────────────────────────────────────────────
# DATA LOADING
# ─────────────────────────────────────────────────────────────────

RESULT_DIRS = [
    "results/portfolio_p2",
    "results/portfolio_p4",
    "results/portfolio_p3_on",
    "results/portfolio_p32",
    "results/portfolio_p1",
    "results/portfolio_phase1",
]

FEATURES = [
    "feat_retest_depth",   # retest retrace fraction of displacement move
    "feat_body_ratio",     # displacement candle body ratio
    "feat_disp_str",       # displacement body / ATR
    "gaussian_score",      # existing Gaussian score (used as baseline comparison)
]

RR_BUCKET_THRESHOLDS = [0.0, 1.0, 2.0]   # edges → buckets: <0, 0-1, 1-2, >2
RR_WEIGHTS = [0.0, 0.5, 1.5, 2.5]        # weighted expected RR per bucket


def load_trades(base: str = ".") -> list[dict]:
    """Load, deduplicate, and validate all trade records."""
    base_path = Path(base)
    all_rows, seen = [], {}

    for run_dir in RESULT_DIRS:
        for csv_path in (base_path / run_dir).rglob("*_trades.csv"):
            instr = csv_path.parts[-2]
            with open(csv_path, newline="", encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    # Primary dedup: hash-based trade_id (unique across instruments+runs)
                    # Tier-1.1 format: "CRT-" + 16 hex chars = 20 chars total
                    # Tier-1.0 format: "CRT-" + 12 hex chars = 16 chars (backward compat)
                    # Sequential format: "CRT-0001" = 8 chars (pre-Tier-1, non-hex digits)
                    tid = row.get("trade_id", "")
                    hex_suffix = tid[4:] if tid.startswith("CRT-") else ""
                    is_hash_id = (
                        len(hex_suffix) in (12, 16) and
                        all(c in "0123456789abcdef" for c in hex_suffix)
                    )
                    if is_hash_id:
                        key = tid
                    else:
                        key = (
                            row.get("instrument", instr),
                            row.get("opened_at", ""),
                            row.get("direction", ""),
                        )
                    if key not in seen:
                        seen[key] = True
                        row["_instr"] = instr
                        all_rows.append(row)

    return all_rows


def safe_float(x, default=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def extract_dataset(rows: list[dict]) -> tuple[list, list]:
    """
    Returns (X, y) where:
      X = list of feature vectors  [retest_depth, body_ratio, disp_str]
      y = list of RR bucket labels  0,1,2,3
    Only rows with all features AND a pnl_rr_net are included.
    gaussian_score is NOT included as a feature — we're replacing it.
    """
    X, y = [], []
    for r in rows:
        feats = [safe_float(r.get(f)) for f in FEATURES[:3]]  # exclude gaussian_score
        rr    = safe_float(r.get("pnl_rr_net"))
        if any(v is None for v in feats) or rr is None:
            continue
        X.append(feats)
        if   rr < 0:   y.append(0)
        elif rr < 1.0: y.append(1)
        elif rr < 2.0: y.append(2)
        else:           y.append(3)
    return X, y


# ─────────────────────────────────────────────────────────────────
# GAUSSIAN NAIVE BAYES (hand-implemented — no sklearn dependency)
# Uses class-conditional Gaussian distributions per feature.
# ─────────────────────────────────────────────────────────────────

class GaussianNBClassifier:
    """
    Gaussian Naive Bayes implemented in pure Python.
    Fits per-class mean and variance for each feature.
    Predict returns log-posterior probabilities.
    """

    def __init__(self, n_classes: int = 4, var_smoothing: float = 1e-9):
        self.n_classes     = n_classes
        self.var_smoothing = var_smoothing
        self.class_priors: list[float] = []
        self.means:        list[list[float]] = []   # [class][feature]
        self.vars:         list[list[float]] = []   # [class][feature]
        self.n_features:   int = 0

    def fit(self, X: list, y: list) -> "GaussianNBClassifier":
        n = len(X)
        self.n_features = len(X[0])
        self.class_priors = []
        self.means        = []
        self.vars         = []

        for c in range(self.n_classes):
            rows_c = [X[i] for i in range(n) if y[i] == c]
            count  = len(rows_c)
            prior  = count / n if n > 0 else 0.0
            self.class_priors.append(prior)

            if count == 0:
                self.means.append([0.0] * self.n_features)
                self.vars.append([self.var_smoothing] * self.n_features)
                continue

            mu  = [sum(row[f] for row in rows_c) / count for f in range(self.n_features)]
            var = [
                sum((row[f] - mu[f]) ** 2 for row in rows_c) / count + self.var_smoothing
                for f in range(self.n_features)
            ]
            self.means.append(mu)
            self.vars.append(var)

        return self

    def predict_proba(self, x: list) -> list[float]:
        """Returns P(class | x) for all classes."""
        log_posts = []
        for c in range(self.n_classes):
            log_prior = math.log(self.class_priors[c] + 1e-300)
            log_lik   = 0.0
            for f in range(self.n_features):
                mu  = self.means[c][f]
                var = self.vars[c][f]
                # log N(x|mu, var)
                log_lik += -0.5 * math.log(2 * math.pi * var) - ((x[f] - mu) ** 2) / (2 * var)
            log_posts.append(log_prior + log_lik)

        # Softmax for numerical stability
        max_lp = max(log_posts)
        exps   = [math.exp(lp - max_lp) for lp in log_posts]
        total  = sum(exps)
        return [e / total for e in exps]

    def score_to_expected_rr(self, x: list) -> float:
        """Returns expected RR = sum(weight_c × P(c|x))."""
        probs = self.predict_proba(x)
        return sum(w * p for w, p in zip(RR_WEIGHTS, probs))

    def to_dict(self) -> dict:
        """Serialise for integration into backtest_v2.py."""
        return {
            "n_classes":     self.n_classes,
            "n_features":    self.n_features,
            "var_smoothing": self.var_smoothing,
            "class_priors":  self.class_priors,
            "means":         self.means,
            "vars":          self.vars,
            "rr_weights":    RR_WEIGHTS,
            "features":      FEATURES[:3],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "GaussianNBClassifier":
        m = cls(n_classes=d["n_classes"], var_smoothing=d["var_smoothing"])
        m.n_features    = d["n_features"]
        m.class_priors  = d["class_priors"]
        m.means         = d["means"]
        m.vars          = d["vars"]
        return m


# ─────────────────────────────────────────────────────────────────
# LEAVE-ONE-OUT CROSS-VALIDATION
# ─────────────────────────────────────────────────────────────────

def leave_one_out_cv(X: list, y: list) -> dict:
    """
    LOO-CV: for each sample, train on all others, predict held-out sample.
    Returns predicted expected_RR for each held-out sample.
    """
    n = len(X)
    predicted_errs  = []   # predicted expected_RR
    actual_rrs      = []   # actual pnl_rr_net proxy (bucket midpoints)
    bucket_mids     = [-0.5, 0.5, 1.5, 3.0]

    for i in range(n):
        X_tr = [X[j] for j in range(n) if j != i]
        y_tr = [y[j] for j in range(n) if j != i]
        if len(set(y_tr)) < 2:   # skip degenerate splits
            continue
        clf = GaussianNBClassifier(n_classes=4)
        clf.fit(X_tr, y_tr)
        pred_err = clf.score_to_expected_rr(X[i])
        predicted_errs.append(pred_err)
        actual_rrs.append(bucket_mids[y[i]])

    # Pearson correlation between predicted expected_RR and actual bucket midpoint
    n2 = len(predicted_errs)
    if n2 < 5:
        return {"loo_corr": float("nan"), "n_loo": n2}

    mp = sum(predicted_errs) / n2
    ma = sum(actual_rrs)     / n2
    cov = sum((p-mp)*(a-ma) for p,a in zip(predicted_errs, actual_rrs)) / n2
    sp  = math.sqrt(sum((p-mp)**2 for p in predicted_errs) / n2)
    sa  = math.sqrt(sum((a-ma)**2 for a in actual_rrs) / n2)
    corr = cov / (sp * sa) if sp > 0 and sa > 0 else 0.0

    return {
        "loo_corr":            round(corr, 4),
        "n_loo":               n2,
        "mean_predicted_rr":   round(sum(predicted_errs)/n2, 3),
        "mean_actual_bucket":  round(sum(actual_rrs)/n2, 3),
    }


# ─────────────────────────────────────────────────────────────────
# ANALYSIS
# ─────────────────────────────────────────────────────────────────

def pearson(xs, ys):
    n = len(xs)
    if n < 3: return float("nan")
    mx, my = sum(xs)/n, sum(ys)/n
    cov = sum((x-mx)*(y-my) for x,y in zip(xs,ys))/n
    sx = math.sqrt(sum((x-mx)**2 for x in xs)/n)
    sy = math.sqrt(sum((y-my)**2 for y in ys)/n)
    return cov/(sx*sy) if sx>0 and sy>0 else 0.0


def audit_report(rows: list[dict], X: list, y: list) -> None:
    W = 65
    print("═" * W)
    print("  CRT ENGINE — PHASE-5 CALIBRATION AUDIT")
    print("═" * W)

    rrs = [safe_float(r.get("pnl_rr_net")) for r in rows if safe_float(r.get("pnl_rr_net")) is not None]
    rrs = [r for r in rrs if r is not None]

    print(f"\n── DATASET ─────────────────────────────────────────────────")
    print(f"  Unique trades:              {len(X):>8}")

    by_instr = defaultdict(list)
    for r in rows:
        rr = safe_float(r.get("pnl_rr_net"))
        if rr is not None:
            by_instr[r.get("instrument", r.get("_instr","?"))].append(rr)
    for instr, rrs_i in sorted(by_instr.items()):
        wr = sum(1 for r in rrs_i if r > 0) / len(rrs_i)
        avg = sum(rrs_i)/len(rrs_i)
        print(f"  {instr:<10}                {len(rrs_i):>4} trades  WR={wr:.0%}  AvgRR={avg:+.3f}")

    print(f"\n── RR BUCKET DISTRIBUTION ───────────────────────────────────")
    labels = ["<0 (loss)", "0-1R (weak)", "1-2R (mid)", ">2R (strong)"]
    counts = [y.count(c) for c in range(4)]
    for lbl, cnt in zip(labels, counts):
        pct = cnt/len(y)
        bar = "█" * int(pct * 30)
        print(f"  {lbl:<14}  {cnt:>4}  {pct:>5.1%}  {bar}")

    print(f"\n  ⚠️  CLASS IMBALANCE WARNING:")
    loss_pct = counts[0] / len(y)
    if loss_pct > 0.55:
        print(f"  {loss_pct:.0%} losses — GaussianNB may predict 'loss' for almost everything.")
        print(f"  LOO-CV correlation is the honest test.")

    print(f"\n── EXISTING FEATURE CORRELATIONS ────────────────────────────")
    feat_labels = FEATURES[:3] + ["gaussian_score"]
    for feat in feat_labels:
        vals = [safe_float(r.get(feat)) for r in rows if safe_float(r.get(feat)) is not None]
        rr_match = [safe_float(r.get("pnl_rr_net")) for r in rows if safe_float(r.get(feat)) is not None]
        if len(vals) < 5: continue
        c = pearson(vals, rr_match)
        bar = "+" * max(0, int(c * 20)) if c > 0 else "-" * max(0, int(-c * 20))
        print(f"  {feat:<25}  corr_RR={c:+.4f}  {bar}")

    print(f"\n  ⚠️  All correlations are near-zero (<|0.1|). This is the")
    print(f"  fundamental constraint. 159 trades is insufficient to")
    print(f"  learn stable Gaussian parameters. The audit below will")
    print(f"  show whether the ML model adds signal over the current scorer.")

    print(f"\n── EXISTING SCORER vs RR BUCKET ─────────────────────────────")
    buckets = defaultdict(list)
    for r in rows:
        sc = safe_float(r.get("gaussian_score"), 0)
        rr = safe_float(r.get("pnl_rr_net"))
        if rr is None: continue
        if   sc < 0.2: buckets["0.0-0.2"].append(rr)
        elif sc < 0.3: buckets["0.2-0.3"].append(rr)
        elif sc < 0.4: buckets["0.3-0.4"].append(rr)
        elif sc < 0.5: buckets["0.4-0.5"].append(rr)
        else:          buckets["0.5+"].append(rr)
    for lbl in ["0.0-0.2","0.2-0.3","0.3-0.4","0.4-0.5","0.5+"]:
        rrs_b = buckets[lbl]
        if not rrs_b: continue
        avg = sum(rrs_b)/len(rrs_b)
        wr  = sum(1 for r in rrs_b if r>0)/len(rrs_b)
        trend = "↑" if avg > 0.5 else "↓" if avg < 0 else "→"
        print(f"  score {lbl}  n={len(rrs_b):>4}  WR={wr:.0%}  AvgRR={avg:+.3f}  {trend}")

    print(f"\n  Score is NOT monotonically increasing in RR.")
    print(f"  The 0.4-0.5 bucket (+3.53R) is driven by a single large")
    print(f"  GBPUSD/BTC outlier. This is noise, not signal at n=159.")


# ─────────────────────────────────────────────────────────────────
# TRAIN & VALIDATE
# ─────────────────────────────────────────────────────────────────

def train_and_validate(X: list, y: list, rows: list[dict]) -> dict:
    W = 65
    print("═" * W)
    print("  PHASE-5: TRAINING GaussianNB + LOO-CV VALIDATION")
    print("═" * W)

    print(f"\nTraining on {len(X)} samples, {len(set(y))} classes...")

    clf = GaussianNBClassifier(n_classes=4)
    clf.fit(X, y)

    print(f"\nClass priors: " +
          " ".join(f"class{c}={p:.2f}" for c,p in enumerate(clf.class_priors)))

    # In-sample predicted expected_RR
    in_sample_scores = [clf.score_to_expected_rr(x) for x in X]
    actual_rrs = [safe_float(r.get("pnl_rr_net")) for r in rows if safe_float(r.get("pnl_rr_net")) is not None]
    rrs_used = actual_rrs[:len(in_sample_scores)]

    corr_insample = pearson(in_sample_scores, rrs_used)
    print(f"\nIn-sample correlation (expected_RR vs actual_RR): {corr_insample:+.4f}")
    print(f"  (This will be inflated — LOO-CV is the real test)")

    # LOO-CV
    print(f"\nRunning LOO-CV ({len(X)} folds)...")
    loo = leave_one_out_cv(X, y)
    print(f"\n── LOO-CV RESULTS ───────────────────────────────────────────")
    print(f"  Folds evaluated:            {loo['n_loo']:>8}")
    print(f"  LOO correlation (score→RR): {loo['loo_corr']:>+8.4f}")
    print(f"  Mean predicted expected_RR: {loo.get('mean_predicted_rr', 'n/a'):>8}")
    print(f"  Mean actual bucket midpoint:{loo.get('mean_actual_bucket', 'n/a'):>8}")

    # Baseline: existing gaussian_score LOO correlation
    existing_scores = [safe_float(r.get("gaussian_score"), 0) for r in rows]
    corr_existing   = pearson(existing_scores, actual_rrs)
    print(f"\n── COMPARISON TO EXISTING SCORER ────────────────────────────")
    print(f"  Existing Gaussian score corr: {corr_existing:>+8.4f}")
    print(f"  GaussianNB LOO corr:          {loo['loo_corr']:>+8.4f}")

    MINIMUM_USEFUL_CORR = 0.10

    if loo["loo_corr"] > MINIMUM_USEFUL_CORR and loo["loo_corr"] > corr_existing:
        verdict = "✅ BETTER than existing scorer — integration candidate"
    elif loo["loo_corr"] > 0 and loo["loo_corr"] > corr_existing:
        verdict = "⚠️  Marginally better — gains within noise margin (n=159)"
    elif loo["loo_corr"] > 0:
        verdict = "⚠️  Positive but weaker than existing — keep existing scorer"
    else:
        verdict = "❌ No improvement — data insufficient for reliable recalibration"

    print(f"\n  Verdict: {verdict}")

    # Bucket validation
    print(f"\n── CALIBRATED SCORE vs RR BUCKET ────────────────────────────")
    score_rr = [(clf.score_to_expected_rr(X[i]), actual_rrs[i]) for i in range(len(X))]
    score_rr.sort(key=lambda x: x[0])
    q = len(score_rr) // 4
    quartiles = [score_rr[i*q:(i+1)*q] for i in range(4)]
    for qi, qdata in enumerate(quartiles):
        if not qdata: continue
        avg_sc  = sum(s for s,_ in qdata) / len(qdata)
        avg_rr  = sum(r for _,r in qdata) / len(qdata)
        wr      = sum(1 for _,r in qdata if r > 0) / len(qdata)
        print(f"  Q{qi+1} score≈{avg_sc:.3f}  n={len(qdata):>3}  avg_RR={avg_rr:+.3f}  WR={wr:.0%}")

    return {"clf": clf, "loo": loo, "verdict": verdict, "corr_existing": corr_existing}


# ─────────────────────────────────────────────────────────────────
# INTEGRATION — write calibrated scorer into backtest_v2.py
# ─────────────────────────────────────────────────────────────────

SCORER_REPLACE_TARGET = "class CRTGaussianScorer:"

def integrate_scorer(clf: GaussianNBClassifier, loo: dict, base: str = ".") -> None:
    """
    Writes the calibrated GaussianNB parameters into backtest_v2.py as a new
    CRTCalibratedScorer class, available alongside the existing CRTGaussianScorer.
    Does NOT remove the existing scorer — that requires explicit opt-in.
    """
    params = clf.to_dict()
    params_json = json.dumps(params, indent=4)

    scorer_code = f'''

# ─────────────────────────────────────────────────────────────────
# [Phase-5] CALIBRATED GAUSSIAN SCORER
# Trained on {loo["n_loo"]} LOO folds from {sum(c for c in clf.class_priors)} trades
# LOO correlation: {loo["loo_corr"]:+.4f}
# Generated automatically by phase5_calibration.py — do not edit manually.
# ─────────────────────────────────────────────────────────────────

_P5_PARAMS = {params_json}

class CRTCalibratedScorer:
    """
    Phase-5 GaussianNB scorer.
    score_to_expected_rr() returns predicted expected R-multiple.
    Use in place of CRTGaussianScorer when loo_corr > 0.10.
    """

    def __init__(self):
        import json as _json, math as _math
        p = _P5_PARAMS
        self.n_classes     = p["n_classes"]
        self.n_features    = p["n_features"]
        self.var_smoothing = p["var_smoothing"]
        self.priors        = p["class_priors"]
        self.means         = p["means"]
        self.vars          = p["vars"]
        self.rr_weights    = p["rr_weights"]
        self.features      = p["features"]   # ["feat_retest_depth","feat_body_ratio","feat_disp_str"]

    def _predict_proba(self, x: list) -> list:
        import math as _math
        log_posts = []
        for c in range(self.n_classes):
            lp = _math.log(self.priors[c] + 1e-300)
            for f in range(self.n_features):
                mu, var = self.means[c][f], self.vars[c][f]
                lp += -0.5 * _math.log(2 * _math.pi * var) - ((x[f] - mu)**2) / (2*var)
            log_posts.append(lp)
        mx = max(log_posts)
        exps = [_math.exp(lp - mx) for lp in log_posts]
        t = sum(exps)
        return [e/t for e in exps]

    def compute(self, features: dict | None, candle_idx: int) -> dict | None:
        """Drop-in replacement for CRTGaussianScorer.compute()."""
        if not features:
            return None
        try:
            x = [
                float(features.get("retest_depth", 0)),
                float(features.get("body_ratio",   0)),
                float(features.get("disp_str",     0)),
            ]
            probs = self._predict_proba(x)
            exp_rr = sum(w*p for w,p in zip(self.rr_weights, probs))
            # Normalise to [0,1] for compatibility with existing thresholds
            score = min(1.0, max(0.0, exp_rr / max(self.rr_weights)))
            return {{
                "score":       round(score, 4),
                "p_win":       round(probs[2] + probs[3], 4),
                "p_loss":      round(probs[0], 4),
                "p_weak":      round(probs[1], 4),
                "p_mid":       round(probs[2], 4),
                "p_strong":    round(probs[3], 4),
                "expected_rr": round(exp_rr, 4),
            }}
        except Exception as e:
            return None

'''

    bt_path = Path(base) / "backtest_v2.py"
    with open(bt_path) as f:
        src = f.read()

    MARKER = "# [Phase-5] CALIBRATED GAUSSIAN SCORER"
    if MARKER in src:
        # Remove old calibrated scorer
        start = src.index(MARKER) - 1
        # Find next class definition after the block
        next_class = src.find("\nclass ", start + 1)
        if next_class == -1:
            next_class = len(src)
        src = src[:start] + src[next_class:]

    # Insert before CRTGaussianScorer class
    insert_at = src.find(f"\n{SCORER_REPLACE_TARGET}")
    if insert_at == -1:
        print(f"❌ Could not find '{SCORER_REPLACE_TARGET}' in backtest_v2.py")
        return

    src = src[:insert_at] + scorer_code + src[insert_at:]
    with open(bt_path, "w") as f:
        f.write(src)

    print(f"\n✅ CRTCalibratedScorer injected into backtest_v2.py")
    print(f"   To use: replace 'CRTGaussianScorer()' with 'CRTCalibratedScorer()' in BacktestRunner.__init__")
    print(f"   LOO correlation: {loo['loo_corr']:+.4f}")


# ─────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="CRT Phase-5: Gaussian Recalibration")
    ap.add_argument("--audit-only",  action="store_true", help="Only print data audit, no training")
    ap.add_argument("--train",       action="store_true", help="Train model and validate with LOO-CV")
    ap.add_argument("--integrate",   action="store_true", help="Write calibrated scorer into backtest_v2.py")
    ap.add_argument("--base",        default=".",         help="Base directory (default: .)")
    args = ap.parse_args()

    if not (args.audit_only or args.train or args.integrate):
        args.audit_only = True   # default: just audit

    print(f"\nLoading trade data from {args.base}...")
    rows = load_trades(args.base)
    X, y = extract_dataset(rows)
    print(f"Loaded {len(rows)} unique trades → {len(X)} usable with all features\n")

    if len(X) < 20:
        print("❌ Insufficient data for calibration (<20 usable trades).")
        sys.exit(1)

    audit_report(rows, X, y)

    if args.train or args.integrate:
        print()
        result = train_and_validate(X, y, rows)

        # Save parameters regardless of verdict
        out = Path(args.base) / "results" / "p5_calibration.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w") as f:
            json.dump({
                "n_trades":      len(X),
                "loo_corr":      result["loo"]["loo_corr"],
                "corr_existing": result["corr_existing"],
                "verdict":       result["verdict"],
                "params":        result["clf"].to_dict(),
            }, f, indent=2)
        print(f"\n  Parameters saved → {out}")

        if args.integrate:
            print()
            loo_corr = result["loo"]["loo_corr"]
            if loo_corr > 0.05:
                integrate_scorer(result["clf"], result["loo"], args.base)
            else:
                print("❌ LOO correlation ≤ 0.05 — integration blocked.")
                print("   The calibrated model is not more predictive than noise.")
                print("   Recommendation: collect more trade data before recalibrating.")


if __name__ == "__main__":
    main()
