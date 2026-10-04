"""GATE-O nonlinear learnability probes on TN_ENV_CLEAN_L2 (research only).

Uses sklearn HistGradientBoosting (+ linear baseline). No production train/promote.

Usage:
  python scripts/research/gate_o_nonlinear_probe.py
  python scripts/research/gate_o_nonlinear_probe.py --max-rows 40000 --folds 3
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from features.feature_schema import CANONICAL_FEATURES  # noqa: E402

TARGETS_BINARY = ["y_tp1", "y_tp2", "y_survives_be"]
TARGETS_REG = ["y_mfe_r", "y_mae_r_heat", "y_holding_bars", "y_time_to_mfe"]


def _load(path: Path, max_rows: int | None) -> tuple[np.ndarray, dict[str, np.ndarray], dict]:
    X_list = []
    ys: dict[str, list] = {t: [] for t in TARGETS_BINARY + TARGETS_REG}
    meta_side = []
    meta_ei = []
    meta_vol = []
    n = 0
    feat_i = {n: i for i, n in enumerate(CANONICAL_FEATURES)}
    vol_i = feat_i.get("volatility_ratio", 14)

    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if max_rows is not None and n >= max_rows:
                break
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            vec = r.get("feature_vector")
            if not isinstance(vec, list) or len(vec) != 38:
                continue
            # skip rows with missing regression targets needed
            row_ok = True
            vals = {}
            for t in TARGETS_BINARY:
                v = r.get(t)
                if v is None:
                    row_ok = False
                    break
                vals[t] = float(v)
            if not row_ok:
                continue
            for t in TARGETS_REG:
                v = r.get(t)
                if v is None or (isinstance(v, float) and math.isnan(v)):
                    # time_to_mfe may be null — use nan and mask later
                    vals[t] = float("nan") if v is None else float(v)
                else:
                    vals[t] = float(v)
            X_list.append([float(x) for x in vec])
            for t, v in vals.items():
                ys[t].append(v)
            meta_side.append(1.0 if str(r.get("side")).lower() == "long" else 0.0)
            meta_ei.append(float(r.get("entry_index", n)))
            meta_vol.append(float(vec[vol_i]))
            n += 1

    X = np.asarray(X_list, dtype=np.float64)
    Y = {k: np.asarray(v, dtype=np.float64) for k, v in ys.items()}
    meta = {
        "side_long": np.asarray(meta_side),
        "entry_index": np.asarray(meta_ei),
        "vol": np.asarray(meta_vol),
        "n": n,
        "protocol": None,
    }
    return X, Y, meta


def _time_folds(entry_index: np.ndarray, n_folds: int) -> list[tuple[np.ndarray, np.ndarray]]:
    """Contiguous time-ordered folds (train = past, test = next block)."""
    order = np.argsort(entry_index, kind="mergesort")
    n = len(order)
    fold_sizes = [n // n_folds] * n_folds
    for i in range(n % n_folds):
        fold_sizes[i] += 1
    folds = []
    start = 0
    blocks = []
    for fs in fold_sizes:
        blocks.append(order[start : start + fs])
        start += fs
    # expanding window: train = all before test block
    for i in range(1, n_folds):
        te = blocks[i]
        tr = np.concatenate(blocks[:i])
        if len(tr) < 200 or len(te) < 100:
            continue
        folds.append((tr, te))
    return folds


def _auc(y_true: np.ndarray, scores: np.ndarray) -> float:
    # Mann-Whitney AUC
    y_true = y_true.astype(int)
    pos = scores[y_true == 1]
    neg = scores[y_true == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    # rank-based
    order = np.argsort(scores)
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(1, len(scores) + 1)
    # average ranks for ties
    # simple: use mean rank of positives
    sum_ranks_pos = ranks[y_true == 1].sum()
    n_pos, n_neg = len(pos), len(neg)
    return float((sum_ranks_pos - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def _brier(y_true: np.ndarray, prob: np.ndarray) -> float:
    return float(np.mean((prob - y_true) ** 2))


def _ece(y_true: np.ndarray, prob: np.ndarray, n_bins: int = 10) -> float:
    bins = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        m = (prob >= bins[i]) & (prob < bins[i + 1] if i < n_bins - 1 else prob <= bins[i + 1])
        if m.sum() == 0:
            continue
        ece += (m.sum() / len(prob)) * abs(y_true[m].mean() - prob[m].mean())
    return float(ece)


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() < 30:
        return float("nan")
    aa, bb = a[m], b[m]
    ra = aa.argsort().argsort().astype(float)
    rb = bb.argsort().argsort().astype(float)
    ra -= ra.mean()
    rb -= rb.mean()
    den = np.sqrt((ra ** 2).sum() * (rb ** 2).sum())
    if den <= 0:
        return float("nan")
    return float((ra * rb).sum() / den)


def _rmse(y, p):
    return float(np.sqrt(np.mean((y - p) ** 2)))


def _r2(y, p):
    ss_res = np.sum((y - p) ** 2)
    ss_tot = np.sum((y - y.mean()) ** 2)
    if ss_tot <= 0:
        return float("nan")
    return float(1 - ss_res / ss_tot)


def eval_binary(X, y, folds, feature_names) -> dict[str, Any]:
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    lin_auc, nlin_auc = [], []
    lin_brier, nlin_brier = [], []
    nlin_ece = []
    # feature importance aggregate
    imp = np.zeros(X.shape[1])

    for tr, te in folds:
        Xtr, Xte = X[tr], X[te]
        ytr, yte = y[tr], y[te]
        if ytr.min() == ytr.max() or yte.min() == yte.max():
            continue
        # linear
        lin = make_pipeline(
            StandardScaler(),
            LogisticRegression(max_iter=500, class_weight="balanced"),
        )
        lin.fit(Xtr, ytr)
        pl = lin.predict_proba(Xte)[:, 1]
        lin_auc.append(_auc(yte, pl))
        lin_brier.append(_brier(yte, pl))
        # nonlinear
        clf = HistGradientBoostingClassifier(
            max_depth=6,
            max_iter=80,
            learning_rate=0.08,
            min_samples_leaf=40,
            random_state=42,
        )
        clf.fit(Xtr, ytr)
        pn = clf.predict_proba(Xte)[:, 1]
        nlin_auc.append(_auc(yte, pn))
        nlin_brier.append(_brier(yte, pn))
        nlin_ece.append(_ece(yte, pn))
        # permutation-free: use sklearn feature_importances_ if available
        if hasattr(clf, "feature_importances_"):
            imp += clf.feature_importances_
        else:
            # HGB may not expose importances on all versions — skip
            pass

    def _summ(xs):
        xs = [x for x in xs if x == x]
        if not xs:
            return {"mean": None, "std": None, "per_fold": []}
        return {
            "mean": round(float(np.mean(xs)), 4),
            "std": round(float(np.std(xs)), 4),
            "per_fold": [round(float(x), 4) for x in xs],
        }

    top_feat = []
    if imp.sum() > 0:
        order = np.argsort(-imp)[:8]
        top_feat = [
            {"feature": feature_names[i], "importance": round(float(imp[i] / max(imp.sum(), 1e-12)), 4)}
            for i in order
        ]

    return {
        "n_pos": int(y.sum()),
        "base_rate": round(float(y.mean()), 6),
        "linear": {"auc": _summ(lin_auc), "brier": _summ(lin_brier)},
        "nonlinear": {
            "model": "HistGradientBoostingClassifier",
            "auc": _summ(nlin_auc),
            "brier": _summ(nlin_brier),
            "ece": _summ(nlin_ece),
        },
        "top_features_nonlinear": top_feat,
        "learnability": _tag_binary(_summ(nlin_auc)["mean"], _summ(lin_auc)["mean"]),
    }


def _tag_binary(nlin_auc, lin_auc) -> str:
    if nlin_auc is None:
        return "INDETERMINATE"
    if nlin_auc >= 0.60:
        return "CANDIDATE_LEARNABLE"
    if nlin_auc >= 0.55:
        return "WEAK_SIGNAL"
    return "NOISY"


def eval_reg(X, y, folds, feature_names) -> dict[str, Any]:
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    mask_all = np.isfinite(y)
    lin_r2, nlin_r2 = [], []
    lin_rmse, nlin_rmse = [], []
    nlin_ic = []
    imp = np.zeros(X.shape[1])

    for tr, te in folds:
        tr = tr[mask_all[tr]]
        te = te[mask_all[te]]
        if len(tr) < 200 or len(te) < 100:
            continue
        Xtr, Xte = X[tr], X[te]
        ytr, yte = y[tr], y[te]
        lin = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
        lin.fit(Xtr, ytr)
        pl = lin.predict(Xte)
        lin_r2.append(_r2(yte, pl))
        lin_rmse.append(_rmse(yte, pl))
        reg = HistGradientBoostingRegressor(
            max_depth=6,
            max_iter=80,
            learning_rate=0.08,
            min_samples_leaf=40,
            random_state=42,
        )
        reg.fit(Xtr, ytr)
        pn = reg.predict(Xte)
        nlin_r2.append(_r2(yte, pn))
        nlin_rmse.append(_rmse(yte, pn))
        nlin_ic.append(_spearman(pn, yte))
        if hasattr(reg, "feature_importances_"):
            imp += reg.feature_importances_

    def _summ(xs):
        xs = [x for x in xs if x == x]
        if not xs:
            return {"mean": None, "std": None, "per_fold": []}
        return {
            "mean": round(float(np.mean(xs)), 4),
            "std": round(float(np.std(xs)), 4),
            "per_fold": [round(float(x), 4) for x in xs],
        }

    top_feat = []
    if imp.sum() > 0:
        order = np.argsort(-imp)[:8]
        top_feat = [
            {"feature": feature_names[i], "importance": round(float(imp[i] / max(imp.sum(), 1e-12)), 4)}
            for i in order
        ]

    ic_m = _summ(nlin_ic)["mean"]
    r2_m = _summ(nlin_r2)["mean"]
    return {
        "n_finite": int(mask_all.sum()),
        "missing_rate": round(float(1 - mask_all.mean()), 6),
        "y_mean": round(float(np.nanmean(y)), 6),
        "y_std": round(float(np.nanstd(y)), 6),
        "linear": {"r2": _summ(lin_r2), "rmse": _summ(lin_rmse)},
        "nonlinear": {
            "model": "HistGradientBoostingRegressor",
            "r2": _summ(nlin_r2),
            "rmse": _summ(nlin_rmse),
            "spearman_ic": _summ(nlin_ic),
        },
        "top_features_nonlinear": top_feat,
        "learnability": _tag_reg(r2_m, ic_m),
    }


def _tag_reg(r2, ic) -> str:
    if r2 is None and ic is None:
        return "INDETERMINATE"
    r2 = r2 or 0.0
    ic = abs(ic or 0.0)
    if r2 >= 0.05 or ic >= 0.15:
        return "CANDIDATE_LEARNABLE"
    if r2 >= 0.02 or ic >= 0.08:
        return "WEAK_SIGNAL"
    return "NOISY"


def regime_slice_binary(X, y, vol, side, model_factory) -> dict:
    """In-sample fit on all; report AUC on vol terciles and sides (descriptive)."""
    from sklearn.ensemble import HistGradientBoostingClassifier

    m = np.isfinite(y)
    if m.sum() < 500 or y[m].min() == y[m].max():
        return {}
    clf = HistGradientBoostingClassifier(
        max_depth=5, max_iter=60, learning_rate=0.1, min_samples_leaf=50, random_state=0
    )
    clf.fit(X[m], y[m])
    p = clf.predict_proba(X[m])[:, 1]
    out = {}
    v = vol[m]
    yy = y[m]
    pp = p
    v1, v2 = np.percentile(v, [33.3, 66.7])
    for name, mask in [
        ("low_vol", v <= v1),
        ("mid_vol", (v > v1) & (v <= v2)),
        ("high_vol", v > v2),
        ("long", side[m] == 1),
        ("short", side[m] == 0),
    ]:
        if mask.sum() < 50 or yy[mask].min() == yy[mask].max():
            out[name] = None
        else:
            out[name] = round(_auc(yy[mask], pp[mask]), 4)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset", default=None)
    ap.add_argument("--max-rows", type=int, default=60000)
    ap.add_argument("--folds", type=int, default=4)
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args(argv)

    if args.dataset:
        dataset = Path(args.dataset)
        if not dataset.is_absolute():
            dataset = ROOT / dataset
    else:
        pointer = ROOT / "results" / "clean_labels" / "BNBUSDT" / "LATEST" / "pointer.json"
        dataset = Path(json.loads(pointer.read_text(encoding="utf-8"))["paths"]["dataset"])

    if not dataset.is_file():
        print(f"ERROR: dataset not found: {dataset}")
        return 2

    # require L2
    meta_path = dataset.parent / "dataset_meta.json"
    if meta_path.is_file():
        dm = json.loads(meta_path.read_text(encoding="utf-8"))
        if dm.get("protocol_id") != "TN_ENV_CLEAN_L2":
            print(f"WARNING: dataset protocol_id={dm.get('protocol_id')} (expected TN_ENV_CLEAN_L2)")

    print(f"[gate-o] loading {dataset} max_rows={args.max_rows}")
    X, Y, meta = _load(dataset, args.max_rows)
    print(f"[gate-o] n={meta['n']} features={X.shape[1]}")
    folds = _time_folds(meta["entry_index"], args.folds)
    print(f"[gate-o] time folds used={len(folds)}")

    feat_names = list(CANONICAL_FEATURES)
    results: dict[str, Any] = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": str(dataset),
        "n_rows_used": meta["n"],
        "n_folds": len(folds),
        "models": {
            "linear_clf": "LogisticRegression+StandardScaler",
            "linear_reg": "Ridge+StandardScaler",
            "nonlinear": "HistGradientBoosting (sklearn)",
        },
        "authority": "GATE-O research only — no promote/wire",
        "binary": {},
        "regression": {},
    }

    for t in TARGETS_BINARY:
        print(f"[gate-o] binary {t}…")
        results["binary"][t] = eval_binary(X, Y[t], folds, feat_names)
        results["binary"][t]["regime_auc_insample"] = regime_slice_binary(
            X, Y[t], meta["vol"], meta["side_long"], None
        )

    for t in TARGETS_REG:
        print(f"[gate-o] reg {t}…")
        results["regression"][t] = eval_reg(X, Y[t], folds, feat_names)

    # architectural answers
    tn_tags = {t: results["binary"][t]["learnability"] for t in TARGETS_BINARY}
    env_tags = {t: results["regression"][t]["learnability"] for t in TARGETS_REG}

    def _go(tags: dict, kind: str) -> str:
        good = sum(1 for v in tags.values() if v == "CANDIDATE_LEARNABLE")
        weak = sum(1 for v in tags.values() if v == "WEAK_SIGNAL")
        if kind == "tradenet":
            # need at least one distinct outcome head learnable; tp1/tp2 both matter
            if tags.get("y_tp1") == "CANDIDATE_LEARNABLE" or tags.get("y_survives_be") == "CANDIDATE_LEARNABLE":
                if tags.get("y_tp2") == "NOISY" and tags.get("y_tp1") != "NOISY":
                    return "CONDITIONAL_GO — train without dead heads; drop noisy y_tp2 if still dead"
                return "GO_RESEARCH — offline KEEP_CANDIDATE path eligible (not production)"
            if good + weak == 0:
                return "NO_GO — all outcome heads noisy under nonlinear probe"
            return "CONDITIONAL_GO — weak only; more features/regimes before train charter"
        # envelope
        if good >= 2:
            return "GO_RESEARCH — multi-head EnvelopeNet offline training eligible"
        if good == 1:
            return "CONDITIONAL_GO — single strong head; others diagnostic"
        if weak >= 1:
            return "CONDITIONAL_GO — weak signals only"
        return "NO_GO — envelope continuous targets noisy under nonlinear probe"

    # compare linear vs nonlinear lifts
    lifts = {}
    for t in TARGETS_BINARY:
        la = results["binary"][t]["linear"]["auc"]["mean"]
        na = results["binary"][t]["nonlinear"]["auc"]["mean"]
        lifts[t] = {
            "linear_auc": la,
            "nonlinear_auc": na,
            "lift": None if la is None or na is None else round(na - la, 4),
        }
    for t in TARGETS_REG:
        lr = results["regression"][t]["linear"]["r2"]["mean"]
        nr = results["regression"][t]["nonlinear"]["r2"]["mean"]
        lifts[t] = {
            "linear_r2": lr,
            "nonlinear_r2": nr,
            "lift": None if lr is None or nr is None else round(nr - lr, 4),
        }

    env_better = 0
    for t in TARGETS_REG:
        if env_tags[t] == "CANDIDATE_LEARNABLE":
            env_better += 1
    tn_good = sum(1 for t in TARGETS_BINARY if tn_tags[t] == "CANDIDATE_LEARNABLE")

    results["architecture"] = {
        "tradenet_tags": tn_tags,
        "envelope_tags": env_tags,
        "linear_vs_nonlinear_lift": lifts,
        "q1_envelope_more_learnable_than_outcome": env_better >= tn_good,
        "q2_nonlinear_changes_prior": any(
            (lifts[t].get("lift") or 0) >= 0.03 for t in lifts
        ),
        "fundamentally_noisy": [t for t, tag in {**tn_tags, **env_tags}.items() if tag == "NOISY"],
        "deserve_production_models": "NONE yet — GATE-O is learnability only; production needs GATE-S/P + ΔG001",
        "diagnostic_only": [t for t, tag in {**tn_tags, **env_tags}.items() if tag in ("NOISY", "WEAK_SIGNAL")],
        "tradenet_go_nogo": _go(tn_tags, "tradenet"),
        "envelope_go_nogo": _go(env_tags, "envelope"),
        "multi_head_envelope_still_justified": env_better >= 2 or (
            env_better >= 1 and sum(1 for t in env_tags.values() if t == "WEAK_SIGNAL") >= 1
        ),
    }

    # dataset hash of first/last unit ids sample
    h = hashlib.sha256()
    with dataset.open("rb") as fh:
        for i, chunk in enumerate(iter(lambda: fh.read(1 << 20), b"")):
            h.update(chunk)
            if i > 200:  # partial for huge files — full hash on whole file better
                break
    # full file hash
    h2 = hashlib.sha256()
    with dataset.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h2.update(chunk)
    results["dataset_sha256"] = h2.hexdigest()

    out_dir = Path(args.out_dir) if args.out_dir else dataset.parent / f"gate_o_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "gate_o_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")

    report = _render(results)
    (out_dir / "report.md").write_text(report, encoding="utf-8")
    docs = ROOT / "docs" / "analysis" / "gate-o-nonlinear-BNBUSDT.LATEST.md"
    docs.write_text(report, encoding="utf-8")
    (ROOT / "docs" / "analysis" / "gate-o-nonlinear-BNBUSDT.LATEST.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )

    print(f"[gate-o] TN {results['architecture']['tradenet_go_nogo']}")
    print(f"[gate-o] ENV {results['architecture']['envelope_go_nogo']}")
    print(f"[gate-o] wrote {out_dir}")
    return 0


def _render(r: dict) -> str:
    lines = [
        "# GATE-O Nonlinear Learnability — TN_ENV_CLEAN_L2",
        "",
        f"| Field | Value |",
        f"|-------|--------|",
        f"| created | {r['created_utc']} |",
        f"| dataset | `{r['dataset']}` |",
        f"| n_rows_used | {r['n_rows_used']} |",
        f"| folds | {r['n_folds']} (time-ordered expanding) |",
        f"| dataset_sha256 | `{r.get('dataset_sha256', '')[:16]}…` |",
        f"| authority | {r['authority']} |",
        "",
        "## TradeNet binary heads",
        "",
        "| Label | base_rate | Lin AUC | NLin AUC | Lift | ECE | Tag |",
        "|-------|-----------|---------|----------|------|-----|-----|",
    ]
    for t, d in r["binary"].items():
        la = d["linear"]["auc"]["mean"]
        na = d["nonlinear"]["auc"]["mean"]
        lift = None if la is None or na is None else round(na - la, 4)
        ece = d["nonlinear"]["ece"]["mean"]
        lines.append(
            f"| `{t}` | {d['base_rate']} | {la} | {na} | {lift} | {ece} | **{d['learnability']}** |"
        )
    lines += ["", "## Envelope regression heads", "",
              "| Label | y_mean | Lin R² | NLin R² | Spearman IC | Tag |",
              "|-------|--------|--------|---------|-------------|-----|"]
    for t, d in r["regression"].items():
        lines.append(
            f"| `{t}` | {d['y_mean']} | {d['linear']['r2']['mean']} | "
            f"{d['nonlinear']['r2']['mean']} | {d['nonlinear']['spearman_ic']['mean']} | "
            f"**{d['learnability']}** |"
        )
    a = r["architecture"]
    lines += [
        "",
        "## Architectural answers",
        "",
        f"1. Envelope more learnable than outcomes? **{a['q1_envelope_more_learnable_than_outcome']}**",
        f"2. Nonlinear changes prior conclusions? **{a['q2_nonlinear_changes_prior']}**",
        f"3. Fundamentally noisy: `{a['fundamentally_noisy']}`",
        f"4. Deserve production models: {a['deserve_production_models']}",
        f"5. Diagnostic-only candidates: `{a['diagnostic_only']}`",
        f"6. Multi-head envelope still justified? **{a['multi_head_envelope_still_justified']}**",
        "",
        f"### TradeNet GO/NO-GO: **{a['tradenet_go_nogo']}**",
        f"### EnvelopeNet GO/NO-GO: **{a['envelope_go_nogo']}**",
        "",
        "### Regime / side AUC (in-sample descriptive — not CV)",
        "",
    ]
    for t, d in r["binary"].items():
        lines.append(f"- `{t}`: {d.get('regime_auc_insample')}")
    lines += [
        "",
        "---",
        "",
        "GATE-O does **not** authorize training promotion, shadow weight, or spine wire.",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
