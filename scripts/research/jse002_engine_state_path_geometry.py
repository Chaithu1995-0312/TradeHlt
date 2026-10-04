#!/usr/bin/env python3
"""JSE-002: Does engine_state_asof predict path geometry? (BNB-only)

Context MeasurementObject = engine_state_asof (SAME join as JSE-001).
Do NOT call this CRT. Title clearly: context = engine_state_asof.

Hypothesis framing (not claim):
  engine_state_asof / richer CRT later → ? → path geometry descriptors → Y_joint

No L-003 doctrine reopen. No src/. No commit/add. No edge/attribution.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, roc_auc_score
from sklearn.preprocessing import OneHotEncoder

LABEL_TO_COORD = {"SL_HIT": "SL", "TP_HIT": "TP", "TIMEOUT": "TO"}


def y_joint_state(scanner_label: str, oracle_label: str) -> str:
    a = LABEL_TO_COORD.get(str(scanner_label), "?")
    b = LABEL_TO_COORD.get(str(oracle_label), "?")
    return f"STATE_{a}_{b}"


def find_largest_events(results_root: Path) -> Path:
    best = None
    best_sz = -1
    for d in results_root.iterdir():
        if not d.is_dir():
            continue
        if not (d.name.startswith("run_") and d.name.endswith("_BNBUSDT")):
            continue
        ev = d / "BNBUSDT_events.jsonl"
        if ev.exists():
            sz = ev.stat().st_size
            if sz > best_sz:
                best_sz = sz
                best = ev
    if best is None:
        raise FileNotFoundError("No results/run_*_BNBUSDT/BNBUSDT_events.jsonl found")
    return best


def load_engine_state_series(events_path: Path):
    """Piecewise-constant updates from STATE_TRANSITION + RESET (same as JSE-001)."""
    rows = []
    n_by_event = Counter()
    with events_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            o = json.loads(line)
            ev = o.get("event")
            n_by_event[ev] += 1
            if ev not in ("STATE_TRANSITION", "RESET"):
                continue
            ts = o.get("timestamp")
            st = o.get("state_to")
            if ts is None or st is None:
                continue
            rows.append(
                {
                    "timestamp": pd.Timestamp(ts),
                    "engine_state": str(st),
                    "event": ev,
                    "state_from": o.get("state_from"),
                }
            )
    if not rows:
        raise RuntimeError(f"No STATE_TRANSITION/RESET with state_to in {events_path}")
    df = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
    df = df.drop_duplicates(subset=["timestamp"], keep="last").reset_index(drop=True)
    return df, dict(n_by_event)


def asof_join(anatomy: pd.DataFrame, series: pd.DataFrame) -> pd.DataFrame:
    a = anatomy.sort_values("timestamp").copy()
    s = series[["timestamp", "engine_state"]].sort_values("timestamp").copy()
    a["timestamp"] = pd.to_datetime(a["timestamp"])
    s["timestamp"] = pd.to_datetime(s["timestamp"])
    return pd.merge_asof(a, s, on="timestamp", direction="backward", suffixes=("", "_eng"))


def peak_bucket(x):
    if pd.isna(x):
        return None
    x = float(x)
    if x <= 2:
        return "<=2"
    if x <= 5:
        return "3-5"
    if x <= 10:
        return "6-10"
    return ">10"


def mfe_bucket(x):
    if pd.isna(x):
        return None
    x = float(x)
    if x < 2:
        return "<2"
    if x < 4:
        return "2-4"
    if x < 6:
        return "4-6"
    return "6+"


def t_mae_dist_bucket(x):
    """L-003E distribution-aware T_MAE buckets."""
    if pd.isna(x):
        return None
    x = float(x)
    if x <= 5:
        return "<=5"
    if x <= 20:
        return "6-20"
    if x <= 40:
        return "21-40"
    if x <= 70:
        return "41-70"
    return ">70"


def t_mae_short_bucket(x):
    """L-003E user-style short T_MAE buckets."""
    if pd.isna(x):
        return None
    x = float(x)
    if x <= 2:
        return "<=2"
    if x <= 5:
        return "3-5"
    if x <= 10:
        return "6-10"
    return ">10"


def effect_sizes_continuous(sub: pd.DataFrame, col: str, min_n: int) -> list:
    overall = sub[col].dropna()
    base_mean = float(overall.mean()) if len(overall) else None
    base_median = float(overall.median()) if len(overall) else None
    rows = []
    for eng, g in sub.groupby("engine_state"):
        vals = g[col].dropna()
        n = int(len(vals))
        if n < min_n:
            continue
        mean_v = float(vals.mean())
        med_v = float(vals.median())
        rows.append(
            {
                "engine_state": str(eng),
                "n": n,
                "mean": mean_v,
                "median": med_v,
                "base_mean": base_mean,
                "base_median": base_median,
                "delta_mean": mean_v - base_mean if base_mean is not None else None,
                "delta_median": med_v - base_median if base_median is not None else None,
            }
        )
    rows.sort(key=lambda r: -r["n"])
    return rows


def bucket_lifts(sub: pd.DataFrame, bucket_col: str, min_n: int) -> dict:
    base = sub[bucket_col].dropna().value_counts(normalize=True).to_dict()
    counts = sub[bucket_col].dropna().value_counts().to_dict()
    by_state = []
    for eng, g in sub.groupby("engine_state"):
        vals = g[bucket_col].dropna()
        n = int(len(vals))
        if n < min_n:
            continue
        rates = vals.value_counts(normalize=True).to_dict()
        row = {"engine_state": str(eng), "n": n}
        for b, br in base.items():
            r = float(rates.get(b, 0.0))
            row[f"rate_{b}"] = r
            row[f"base_{b}"] = float(br)
            row[f"lift_{b}"] = (r / float(br)) if br else None
            row[f"delta_{b}"] = r - float(br)
        by_state.append(row)
    by_state.sort(key=lambda r: -r["n"])
    return {
        "base_rates": {str(k): float(v) for k, v in base.items()},
        "base_counts": {str(k): int(v) for k, v in counts.items()},
        "by_engine_state_n_ge_min": by_state,
    }


def multiclass_predictability(
    engine_state: pd.Series, y_bucket: pd.Series, train_idx, test_idx, labels_order
) -> dict:
    """One-hot engine_state -> multiclass LR; OVR AUCs + balanced accuracy."""
    mask = y_bucket.notna()
    # Work on full arrays aligned to sub index; caller already reset_index
    y = y_bucket.astype(object)
    enc = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    X = enc.fit_transform(engine_state.astype(str).to_frame())

    # Restrict train/test to non-null labels
    tr = np.array([i for i in train_idx if bool(mask.iloc[i])])
    te = np.array([i for i in test_idx if bool(mask.iloc[i])])
    if len(tr) < 50 or len(te) < 50:
        return {"error": "insufficient non-null rows in holdout", "n_train": int(len(tr)), "n_test": int(len(te))}

    y_tr = y.iloc[tr].astype(str).to_numpy()
    y_te = y.iloc[te].astype(str).to_numpy()
    X_tr, X_te = X[tr], X[te]

    present = sorted(set(y_tr) | set(y_te), key=lambda z: labels_order.index(z) if z in labels_order else 999)
    # Drop labels missing from train
    train_labels = set(y_tr)
    present = [p for p in present if p in train_labels]
    if len(present) < 2:
        return {"error": "degenerate label set", "labels": present}

    clf = LogisticRegression(max_iter=2000, solver="lbfgs")
    clf.fit(X_tr, y_tr)
    proba = clf.predict_proba(X_te)
    classes = list(clf.classes_)
    pred = clf.predict(X_te)

    per_class_auc = {}
    for lab in present:
        if lab not in classes:
            per_class_auc[lab] = None
            continue
        j = classes.index(lab)
        y_bin = (y_te == lab).astype(int)
        if y_bin.sum() == 0 or y_bin.sum() == len(y_bin):
            per_class_auc[lab] = None
            continue
        per_class_auc[lab] = float(roc_auc_score(y_bin, proba[:, j]))
    vals = [v for v in per_class_auc.values() if v is not None]
    bal_acc = float(balanced_accuracy_score(y_te, pred))

    # Also report majority-class baseline bal_acc on test
    maj = Counter(y_tr).most_common(1)[0][0]
    maj_pred = np.array([maj] * len(y_te))
    maj_bal = float(balanced_accuracy_score(y_te, maj_pred))

    return {
        "n_train": int(len(tr)),
        "n_test": int(len(te)),
        "labels": present,
        "classes_fit": [str(c) for c in classes],
        "per_class_auc_test_ovr": per_class_auc,
        "macro_auc_test_ovr": float(np.mean(vals)) if vals else None,
        "balanced_accuracy_test": bal_acc,
        "majority_baseline_balanced_accuracy_test": maj_bal,
        "test_base_rates": {str(k): float(v) for k, v in pd.Series(y_te).value_counts(normalize=True).items()},
        "n_features": int(X.shape[1]),
        "engine_state_categories": [str(c) for c in enc.categories_[0]],
    }


def binary_auc_from_state(engine_state: pd.Series, y_binary: np.ndarray, train_idx, test_idx) -> dict:
    enc = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    X = enc.fit_transform(engine_state.astype(str).to_frame())
    X_tr, X_te = X[train_idx], X[test_idx]
    y_tr, y_te = y_binary[train_idx], y_binary[test_idx]
    if len(np.unique(y_tr)) < 2 or len(np.unique(y_te)) < 2:
        return {"auc_train": None, "auc_test": None, "note": "degenerate"}
    clf = LogisticRegression(max_iter=1000, solver="lbfgs")
    clf.fit(X_tr, y_tr)
    return {
        "auc_train": float(roc_auc_score(y_tr, clf.predict_proba(X_tr)[:, 1])),
        "auc_test": float(roc_auc_score(y_te, clf.predict_proba(X_te)[:, 1])),
        "n_train": int(len(y_tr)),
        "n_test": int(len(y_te)),
        "base_test": float(y_te.mean()),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, default=Path(r"D:\Tradelatest"))
    ap.add_argument("--anatomy", type=Path, default=None)
    ap.add_argument("--events", type=Path, default=None)
    ap.add_argument("--l003h-bnb", type=Path, default=None)
    ap.add_argument("--min-n-state", type=int, default=500)
    ap.add_argument("--holdout-frac", type=float, default=0.30)
    ap.add_argument("--run-id", type=str, default=None)
    args = ap.parse_args()

    repo = args.repo
    anatomy_path = args.anatomy or (
        repo / "results/research/bnbusdt_trade_anatomy/trade_dataset_BNBUSDT.csv"
    )
    events_path = args.events or find_largest_events(repo / "results")
    l003h_path = args.l003h_bnb or (
        repo
        / "results/research/l003h_trail_exit_transitions"
        / "l003h_trail_exit_transitions_20260907_192115_BNBUSDT_events.csv"
    )

    now = datetime.now(timezone.utc)
    run_id = args.run_id or f"jse002_engine_state_path_geometry_{now.strftime('%Y%m%d_%H%M%S')}"
    version = "JSE-002.v1"

    usecols = [
        "timestamp",
        "direction",
        "entry",
        "art_outcome",
        "outcome",
        "bars_to_peak_within_trade",
        "mfe_r",
        "time_to_bottom_path",
        "mae_r",
    ]
    anatomy = pd.read_csv(anatomy_path, usecols=usecols)
    anatomy["timestamp"] = pd.to_datetime(anatomy["timestamp"])
    anatomy["Y_joint"] = [
        y_joint_state(a, o) for a, o in zip(anatomy["art_outcome"], anatomy["outcome"])
    ]
    anatomy["peak_bucket"] = anatomy["bars_to_peak_within_trade"].map(peak_bucket)
    anatomy["mfe_bucket"] = anatomy["mfe_r"].map(mfe_bucket)
    anatomy["t_mae_dist_bucket"] = anatomy["time_to_bottom_path"].map(t_mae_dist_bucket)
    anatomy["t_mae_short_bucket"] = anatomy["time_to_bottom_path"].map(t_mae_short_bucket)

    # Optional L-003H exit-ordering join (BNB events; same n as anatomy)
    exit_join_note = None
    if l003h_path.exists():
        h = pd.read_csv(
            l003h_path,
            usecols=[
                "timestamp",
                "direction",
                "entry",
                "scanner_exit_before_oracle_tp",
            ],
        )
        h["timestamp"] = pd.to_datetime(h["timestamp"])
        # Alias L-003M noun
        h["scanner_exit_precedes_oracle_tp"] = h["scanner_exit_before_oracle_tp"].astype(bool)
        before = len(anatomy)
        anatomy = anatomy.merge(
            h[["timestamp", "direction", "entry", "scanner_exit_precedes_oracle_tp"]],
            on=["timestamp", "direction", "entry"],
            how="left",
            validate="one_to_one",
        )
        n_ok = int(anatomy["scanner_exit_precedes_oracle_tp"].notna().sum())
        exit_join_note = {
            "source": str(l003h_path),
            "column_source": "scanner_exit_before_oracle_tp",
            "noun_alias": "scanner_exit_precedes_oracle_tp",
            "n_matched": n_ok,
            "n_anatomy": before,
            "matched_fraction": float(n_ok / before) if before else 0.0,
        }
    else:
        exit_join_note = {"skipped": True, "reason": f"missing {l003h_path}"}

    series, event_counts = load_engine_state_series(events_path)
    joined = asof_join(anatomy, series)

    n_total = len(joined)
    n_joined = int(joined["engine_state"].notna().sum())
    coverage = float(n_joined / n_total) if n_total else 0.0

    sub = joined[joined["engine_state"].notna()].copy()
    sub = sub.sort_values("timestamp").reset_index(drop=True)
    n_sub = len(sub)
    cut = int(math.floor(n_sub * (1.0 - args.holdout_frac)))
    train_idx = np.arange(0, cut)
    test_idx = np.arange(cut, n_sub)

    # Continuous effect sizes
    cont = {
        "bars_to_peak_within_trade": effect_sizes_continuous(
            sub, "bars_to_peak_within_trade", args.min_n_state
        ),
        "mfe_r": effect_sizes_continuous(sub, "mfe_r", args.min_n_state),
        "time_to_bottom_path": effect_sizes_continuous(
            sub, "time_to_bottom_path", args.min_n_state
        ),
    }

    # Bucket lifts
    peak_order = ["<=2", "3-5", "6-10", ">10"]
    mfe_order = ["<2", "2-4", "4-6", "6+"]
    tmae_dist_order = ["<=5", "6-20", "21-40", "41-70", ">70"]
    tmae_short_order = ["<=2", "3-5", "6-10", ">10"]

    lifts = {
        "peak_bucket_L003D": bucket_lifts(sub, "peak_bucket", args.min_n_state),
        "mfe_bucket_L003D": bucket_lifts(sub, "mfe_bucket", args.min_n_state),
        "t_mae_dist_bucket_L003E": bucket_lifts(sub, "t_mae_dist_bucket", args.min_n_state),
        "t_mae_short_bucket_L003E": bucket_lifts(sub, "t_mae_short_bucket", args.min_n_state),
    }

    # Predictability
    pred_peak = multiclass_predictability(
        sub["engine_state"], sub["peak_bucket"], train_idx, test_idx, peak_order
    )
    pred_mfe = multiclass_predictability(
        sub["engine_state"], sub["mfe_bucket"], train_idx, test_idx, mfe_order
    )
    pred_tmae = multiclass_predictability(
        sub["engine_state"], sub["t_mae_dist_bucket"], train_idx, test_idx, tmae_dist_order
    )

    # Binary extremes (often more sensitive than full multiclass)
    y_peak_long = (sub["peak_bucket"] == ">10").astype(int).to_numpy()
    # null peaks -> 0; but also mask missing peak as nan handling: treat missing as 0 for binary? better drop
    peak_ok = sub["peak_bucket"].notna().to_numpy()
    tr_p = train_idx[peak_ok[train_idx]]
    te_p = test_idx[peak_ok[test_idx]]
    pred_peak_gt10 = binary_auc_from_state(sub["engine_state"], y_peak_long, tr_p, te_p)

    y_mfe_ge6 = (sub["mfe_bucket"] == "6+").astype(int).to_numpy()
    mfe_ok = sub["mfe_bucket"].notna().to_numpy()
    tr_m = train_idx[mfe_ok[train_idx]]
    te_m = test_idx[mfe_ok[test_idx]]
    pred_mfe_6p = binary_auc_from_state(sub["engine_state"], y_mfe_ge6, tr_m, te_m)

    y_early_mae = (sub["t_mae_dist_bucket"] == "<=5").astype(int).to_numpy()
    t_ok = sub["t_mae_dist_bucket"].notna().to_numpy()
    tr_t = train_idx[t_ok[train_idx]]
    te_t = test_idx[t_ok[test_idx]]
    pred_early_mae = binary_auc_from_state(sub["engine_state"], y_early_mae, tr_t, te_t)

    # Optional exit-ordering predictability
    pred_exit = None
    if "scanner_exit_precedes_oracle_tp" in sub.columns and sub[
        "scanner_exit_precedes_oracle_tp"
    ].notna().any():
        y_ex = sub["scanner_exit_precedes_oracle_tp"].fillna(False).astype(int).to_numpy()
        pred_exit = binary_auc_from_state(sub["engine_state"], y_ex, train_idx, test_idx)
        # lifts
        exit_lifts = []
        base_ex = float(sub["scanner_exit_precedes_oracle_tp"].mean())
        for eng, g in sub.groupby("engine_state"):
            n = int(len(g))
            if n < args.min_n_state:
                continue
            rate = float(g["scanner_exit_precedes_oracle_tp"].mean())
            exit_lifts.append(
                {
                    "engine_state": str(eng),
                    "n": n,
                    "rate": rate,
                    "base": base_ex,
                    "lift": (rate / base_ex) if base_ex else None,
                    "delta": rate - base_ex,
                }
            )
        exit_lifts.sort(key=lambda r: -r["n"])
    else:
        exit_lifts = None

    # Replay JSE-001 baseline on same join: STATE_SL_TP AUC
    y_sl_tp = (sub["Y_joint"] == "STATE_SL_TP").astype(int).to_numpy()
    jse001_replay = binary_auc_from_state(sub["engine_state"], y_sl_tp, train_idx, test_idx)

    jse001_auc_ref = 0.500400830066991
    path_macro_aucs = [
        pred_peak.get("macro_auc_test_ovr"),
        pred_mfe.get("macro_auc_test_ovr"),
        pred_tmae.get("macro_auc_test_ovr"),
    ]
    path_macro_aucs_f = [a for a in path_macro_aucs if a is not None]
    best_path_macro = max(path_macro_aucs_f) if path_macro_aucs_f else None
    binary_aucs = [
        pred_peak_gt10.get("auc_test"),
        pred_mfe_6p.get("auc_test"),
        pred_early_mae.get("auc_test"),
    ]
    if pred_exit and pred_exit.get("auc_test") is not None:
        binary_aucs.append(pred_exit.get("auc_test"))
    binary_aucs_f = [a for a in binary_aucs if a is not None]
    best_binary = max(binary_aucs_f) if binary_aucs_f else None

    # Falsification logic for path geometry
    # If path-geometry AUCs also ≈0.5, engine_state_asof weak for both
    def near_chance(a, lo=0.48, hi=0.55):
        return a is not None and lo <= a <= hi

    all_path_near_chance = all(near_chance(a) for a in path_macro_aucs_f) and all(
        near_chance(a) for a in binary_aucs_f
    )
    better_than_yjoint = (
        best_path_macro is not None
        and best_path_macro > (jse001_replay.get("auc_test") or jse001_auc_ref) + 0.02
    ) or (
        best_binary is not None
        and best_binary > (jse001_replay.get("auc_test") or jse001_auc_ref) + 0.02
    )

    if all_path_near_chance:
        lean = "FALSIFY_PATH_AND_YJOINT"
        lean_reason = (
            "Path-geometry AUCs also ≈0.5 on this join => engine_state_asof is weak for both "
            "direct Y_joint membership and path geometry descriptors (BNB-only; this join surface)."
        )
    elif better_than_yjoint and (
        (best_path_macro and best_path_macro > 0.55)
        or (best_binary and best_binary > 0.55)
    ):
        lean = "SUPPORT_LEAN_PATH_OVER_YJOINT"
        lean_reason = (
            "engine_state_asof separates some path-geometry targets better than chance and better "
            "than STATE_SL_TP membership on the same join (not a CRT claim; not causal)."
        )
    elif better_than_yjoint:
        lean = "WEAK_PATH_BETTER_THAN_YJOINT"
        lean_reason = (
            "Path-geometry predictability slightly exceeds Y_joint null but remains weak overall "
            "(AUC not clearly >0.55)."
        )
    else:
        lean = "WEAK_MIXED"
        lean_reason = (
            f"best_path_macro={best_path_macro}, best_binary={best_binary}, "
            f"jse001_replay_auc={jse001_replay.get('auc_test')}"
        )

    out_dir = repo / "results/research/jse002_engine_state_path_geometry_bnbusdt"
    out_dir.mkdir(parents=True, exist_ok=True)

    artifact = {
        "finding_id": "JSE-002",
        "version": version,
        "run_id": run_id,
        "generated_at_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit_sha": "d7c25f6e55616261b8b229b000875abd3bd315eb",
        "branch": "feature/trace-parquet-duckdb-query",
        "episode": "JOINT_STATE_EXPLAINABILITY",
        "scope": "BNB-only (honest scope)",
        "title": "Does engine_state_asof predict path geometry? (context = engine_state_asof, NOT CRT)",
        "question": "Does engine_state_asof (same join as JSE-001) predict / associate with path geometry descriptors?",
        "hypothesis_framing_not_claim": (
            "engine_state_asof / richer CRT later → ? → path geometry descriptors → Y_joint"
        ),
        "ontology": {
            "context_measurement_object": "engine_state_asof",
            "CRT_Context_equivalent_to_engine_state_asof": False,
            "note": "CRT Context ≠ engine_state_asof unless declared equivalent (it is not).",
            "never_say": ["CRT falsified", "CRT does not explain Y_joint", "CRT/engine context falsified"],
        },
        "measurement_process": {
            "name": "engine_state_asof",
            "definition": (
                "As-of last known engine state_to at or before anatomy entry timestamp, "
                "from piecewise-constant series built from STATE_TRANSITION (+ RESET->RANGE) "
                "in ONE runtime BNBUSDT_events.jsonl population (GT-3). Same construction as JSE-001."
            ),
            "not_claimed": [
                "full CRT ontology",
                "HTF parent context",
                "parent_crt without evidence",
                "manipulation/liquidity/range/transition history",
            ],
        },
        "targets": {
            "bars_to_peak_within_trade": "continuous + L-003D peak buckets (<=2, 3-5, 6-10, >10)",
            "mfe_r": "continuous + L-003D mfe buckets (<2, 2-4, 4-6, 6+)",
            "time_to_bottom_path": "T_MAE continuous + L-003E dist/short buckets",
            "scanner_exit_precedes_oracle_tp": "optional via L-003H BNB events join",
        },
        "data": {
            "anatomy_path": str(anatomy_path),
            "anatomy_n": int(n_total),
            "events_path": str(events_path),
            "events_run_dir": events_path.parent.name,
            "events_bytes": int(events_path.stat().st_size),
            "events_series_n_updates": int(len(series)),
            "event_type_counts_in_file": event_counts,
            "l003h_exit_join": exit_join_note,
            "gt3": "ONE runtime events population only",
        },
        "coverage": {
            "n_anatomy": n_total,
            "n_joined_non_null": n_joined,
            "fraction": coverage,
        },
        "joined_subset": {
            "n": int(n_sub),
            "engine_state_marginals": {
                k: int(v) for k, v in sub["engine_state"].value_counts().items()
            },
            "Y_joint_counts": {k: int(v) for k, v in sub["Y_joint"].value_counts().items()},
        },
        "effect_sizes_continuous_by_engine_state_n_ge_500": cont,
        "bucket_lifts": lifts,
        "predictability": {
            "holdout": {
                "scheme": "chronological within BNB joined subset",
                "train_frac": 1.0 - args.holdout_frac,
                "test_frac": args.holdout_frac,
                "cut_index": cut,
            },
            "features": "engine_state only (one-hot categorical state_to)",
            "peak_bucket_multiclass": pred_peak,
            "mfe_bucket_multiclass": pred_mfe,
            "t_mae_dist_bucket_multiclass": pred_tmae,
            "binary_peak_gt10": pred_peak_gt10,
            "binary_mfe_6plus": pred_mfe_6p,
            "binary_t_mae_early_le5": pred_early_mae,
            "binary_scanner_exit_precedes_oracle_tp": pred_exit,
        },
        "exit_ordering_lifts_by_engine_state": exit_lifts,
        "comparison_vs_jse001": {
            "jse001_auc_test_STATE_SL_TP_recorded": jse001_auc_ref,
            "jse001_STATE_SL_TP_replay_this_run": jse001_replay,
            "best_path_macro_auc_ovr": best_path_macro,
            "best_path_binary_auc": best_binary,
            "path_better_than_yjoint_by_0p02": bool(better_than_yjoint),
            "interpretation": (
                "Compare whether engine_state_asof separates path geometry better than it separates "
                "STATE_SL_TP membership on the same join."
            ),
        },
        "falsification": {
            "stance": (
                "If path-geometry AUCs also ≈0.5, engine_state_asof is weak for both direct Y_joint "
                "and path geometry on this join (BNB-only)."
            ),
            "all_path_aucs_near_chance": bool(all_path_near_chance),
            "lean": lean,
            "lean_reason": lean_reason,
        },
        "limitations": [
            "one instrument (BNBUSDT)",
            "one runtime events run (GT-3)",
            "predictor = categorical state_to (engine_state_asof) only",
            "not Parent/HTF/manipulation/liquidity/range/transition history",
            "CRT Context ≠ engine_state_asof",
        ],
        "observation_hierarchy_banner": (
            "Entry weak (L-003G) · Current engine_state_asof weak (JSE-001) · Path geometry strong (L-003C–E)"
        ),
        "non_promotions": {
            "edge": False,
            "attribution": False,
            "which_outcome_correct": False,
            "l003_doctrine_edit": False,
            "full_crt_ontology_claim": False,
            "crt_falsified_claim": False,
        },
        "artifacts": [
            "docs/research/JOINT_STATE_EXPLAINABILITY.md",
            "docs/research/jse002_engine_state_path_geometry_bnbusdt-2026-09-07.json",
            "scripts/research/jse002_engine_state_path_geometry.py",
            "results/research/jse002_engine_state_path_geometry_bnbusdt/",
            "docs/research/joint_state_explainability_pin.json",
        ],
    }

    json_path = repo / "docs/research/jse002_engine_state_path_geometry_bnbusdt-2026-09-07.json"
    json_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    summary_path = out_dir / f"{run_id}_summary.json"
    summary_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")

    # Compact CSVs
    for name, rows in cont.items():
        if rows:
            pd.DataFrame(rows).to_csv(out_dir / f"{run_id}_effect_{name}.csv", index=False)
    for name, blob in lifts.items():
        rows = blob.get("by_engine_state_n_ge_min") or []
        if rows:
            pd.DataFrame(rows).to_csv(out_dir / f"{run_id}_lifts_{name}.csv", index=False)

    print(
        json.dumps(
            {
                "run_id": run_id,
                "coverage": coverage,
                "lean": lean,
                "best_path_macro_auc_ovr": best_path_macro,
                "best_path_binary_auc": best_binary,
                "jse001_replay_auc": jse001_replay.get("auc_test"),
                "pred_peak_macro": pred_peak.get("macro_auc_test_ovr"),
                "pred_mfe_macro": pred_mfe.get("macro_auc_test_ovr"),
                "pred_tmae_macro": pred_tmae.get("macro_auc_test_ovr"),
                "pred_peak_gt10": pred_peak_gt10.get("auc_test"),
                "pred_mfe_6p": pred_mfe_6p.get("auc_test"),
                "pred_early_mae": pred_early_mae.get("auc_test"),
                "pred_exit": None if not pred_exit else pred_exit.get("auc_test"),
                "json_path": str(json_path),
            },
            indent=2,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
