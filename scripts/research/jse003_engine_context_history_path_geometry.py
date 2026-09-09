#!/usr/bin/env python3
"""JSE-003: engine_context_history -> path geometry (BNB-only)

Predictor family MeasurementObject = engine_context_history
(NOT CRT Context). Built from ONE GT-3-clean events run
(same as JSE-001/JSE-002 when present).

Compares asof-only baseline vs history feature set on peak_bucket / mfe_bucket.

No L-003 doctrine. No src/. No commit/add. No edge/attribution.
Never call this CRT unless measuring declared CRT objects.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, roc_auc_score
from sklearn.preprocessing import OneHotEncoder, StandardScaler

LABEL_TO_COORD = {"SL_HIT": "SL", "TP_HIT": "TP", "TIMEOUT": "TO"}
KEY_STATES = ["RANGE", "SWEEP", "EXPANSION", "DISPLACEMENT", "EXECUTION"]
BAR_TD = pd.Timedelta(minutes=15)
LOOKBACKS = (4, 16, 64)


def y_joint_state(scanner_label: str, oracle_label: str) -> str:
    a = LABEL_TO_COORD.get(str(scanner_label), "?")
    b = LABEL_TO_COORD.get(str(oracle_label), "?")
    return f"STATE_{a}_{b}"


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


def preferred_events(repo: Path) -> Path:
    preferred = repo / "results/run_20260603_122112_BNBUSDT/BNBUSDT_events.jsonl"
    if preferred.exists():
        return preferred
    best = None
    best_sz = -1
    for d in (repo / "results").iterdir():
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
        raise FileNotFoundError("No BNBUSDT_events.jsonl found")
    return best


def load_transition_series(events_path: Path):
    """Piecewise updates from STATE_TRANSITION + RESET (same rule as JSE-001/002)."""
    rows = []
    sweep_ts = []
    n_by_event = Counter()
    with events_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            o = json.loads(line)
            ev = o.get("event")
            n_by_event[ev] += 1
            ts = o.get("timestamp")
            if ts is None:
                continue
            ts = pd.Timestamp(ts)
            if ev == "SWEEP":
                sweep_ts.append(ts)
            if ev not in ("STATE_TRANSITION", "RESET"):
                continue
            st = o.get("state_to")
            if st is None:
                continue
            rows.append(
                {
                    "timestamp": ts,
                    "engine_state": str(st),
                    "event": ev,
                    "state_from": o.get("state_from"),
                }
            )
    if not rows:
        raise RuntimeError(f"No STATE_TRANSITION/RESET with state_to in {events_path}")
    df = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
    df = df.drop_duplicates(subset=["timestamp"], keep="last").reset_index(drop=True)
    sweep_arr = np.array(sorted(set(sweep_ts)), dtype="datetime64[ns]")
    return df, dict(n_by_event), sweep_arr


def build_bar_history(series: pd.DataFrame, sweep_ts: np.ndarray) -> pd.DataFrame:
    """M15 bar grid with forward-filled state + rolling history features.

    Mechanical definitions (documented):
    - bar = 15 minutes (M15 time-equivalent)
    - dwell_bars_in_current_state = bars since last STATE_TRANSITION/RESET update
    - n_transitions_lookback_W = count of update events in (t-W, t] on bar grid
    - frac_time_in_state_W = fraction of bars in lookback W equal to that state
    - last_k_states = previous 1..3 distinct states before current (as-of)
    - bars_since_last_sweep = bars since last SWEEP event timestamp
    """
    t0 = series["timestamp"].iloc[0].floor("15min")
    t1 = series["timestamp"].iloc[-1].ceil("15min")
    bars = pd.date_range(t0, t1, freq="15min")
    bar_df = pd.DataFrame({"bar_ts": bars})

    upd = series.rename(columns={"timestamp": "bar_ts"}).copy()
    upd["bar_ts"] = pd.to_datetime(upd["bar_ts"]).dt.floor("15min")
    upd["is_transition"] = 1
    # last update within a bar wins
    upd = upd.drop_duplicates(subset=["bar_ts"], keep="last")

    bar_df = bar_df.merge(
        upd[["bar_ts", "engine_state", "is_transition"]],
        on="bar_ts",
        how="left",
    )
    bar_df["is_transition"] = bar_df["is_transition"].fillna(0).astype(int)
    bar_df["engine_state"] = bar_df["engine_state"].ffill()
    # Drop leading bars before first known state
    bar_df = bar_df[bar_df["engine_state"].notna()].reset_index(drop=True)

    # dwell: bars since last transition (inclusive of current bar as 0-start after event)
    # After a transition bar, dwell starts at 0; each subsequent non-transition bar +1
    dwell = np.zeros(len(bar_df), dtype=np.int32)
    cur = 0
    is_tr = bar_df["is_transition"].to_numpy()
    for i in range(len(bar_df)):
        if is_tr[i] == 1:
            cur = 0
        else:
            cur += 1
        dwell[i] = cur
    bar_df["dwell_bars_in_current_state"] = dwell

    # n_transitions lookbacks
    trans = bar_df["is_transition"].astype(float).to_numpy()
    for W in LOOKBACKS:
        # rolling sum over last W bars including current
        s = pd.Series(trans).rolling(window=W, min_periods=1).sum().to_numpy()
        bar_df[f"n_transitions_lookback_{W}"] = s.astype(np.float32)

    # frac_time_in_state over W=64
    W = 64
    st = bar_df["engine_state"].astype(str)
    for ks in KEY_STATES:
        ind = (st == ks).astype(float)
        frac = ind.rolling(window=W, min_periods=1).mean()
        bar_df[f"frac_time_in_{ks}_W{W}"] = frac.astype(np.float32)

    # last_k distinct states before current (walk back through transition points)
    # Precompute at each bar the previous distinct state sequence
    last1 = np.array([None] * len(bar_df), dtype=object)
    last2 = np.array([None] * len(bar_df), dtype=object)
    last3 = np.array([None] * len(bar_df), dtype=object)
    # Maintain stack of distinct states as we walk forward through transitions
    # At bar i, last_k are from history strictly before the current state's start
    hist_distinct: list[str] = []
    prev_state = None
    states = bar_df["engine_state"].astype(str).to_numpy()
    for i in range(len(bar_df)):
        cur_s = states[i]
        if prev_state is None:
            # first state: no prior
            last1[i] = "NONE"
            last2[i] = "NONE"
            last3[i] = "NONE"
            prev_state = cur_s
            hist_distinct = [cur_s]
            continue
        if is_tr[i] == 1 and cur_s != prev_state:
            # transition into cur_s: priors are previous hist_distinct (before appending)
            # hist_distinct currently ends with prev_state
            priors = list(reversed(hist_distinct[:-1])) if len(hist_distinct) > 1 else []
            # Actually hist_distinct is chronological; previous distinct before current =
            # the states before the one we're entering. Before transition, hist ends with prev.
            # last_1 = prev_state (immediate previous), last_2 = before that, etc.
            # But "previous 1-3 distinct states" relative to current AFTER transition:
            # last_1 should be prev_state.
            seq = list(reversed(hist_distinct))  # most recent first
            last1[i] = seq[0] if len(seq) >= 1 else "NONE"
            last2[i] = seq[1] if len(seq) >= 2 else "NONE"
            last3[i] = seq[2] if len(seq) >= 3 else "NONE"
            # update hist
            if cur_s in hist_distinct:
                hist_distinct = [s for s in hist_distinct if s != cur_s]
            hist_distinct.append(cur_s)
            prev_state = cur_s
        else:
            # same state continuation: last_k = states before current dwell start
            # hist_distinct ends with current state; priors exclude current
            priors = list(reversed(hist_distinct[:-1]))
            last1[i] = priors[0] if len(priors) >= 1 else "NONE"
            last2[i] = priors[1] if len(priors) >= 2 else "NONE"
            last3[i] = priors[2] if len(priors) >= 3 else "NONE"
            # if first bars without prior transitions, keep NONE

    bar_df["last_1_state"] = last1
    bar_df["last_2_state"] = last2
    bar_df["last_3_state"] = last3
    # hashed triple
    triples = [
        f"{a}|{b}|{c}" for a, b, c in zip(bar_df["last_1_state"], bar_df["last_2_state"], bar_df["last_3_state"])
    ]
    bar_df["last_3_states_hash"] = [
        int(hashlib.md5(t.encode()).hexdigest()[:8], 16) % 97 for t in triples
    ]
    bar_df["last_3_states_str"] = triples

    # bars since last SWEEP event
    if len(sweep_ts) == 0:
        bar_df["bars_since_last_sweep"] = np.nan
    else:
        bar_np = bar_df["bar_ts"].to_numpy(dtype="datetime64[ns]")
        # searchsorted: index of rightmost sweep <= bar
        idx = np.searchsorted(sweep_ts, bar_np, side="right") - 1
        bars_since = np.full(len(bar_df), np.nan, dtype=np.float64)
        valid = idx >= 0
        bars_since[valid] = (bar_np[valid] - sweep_ts[idx[valid]]).astype("timedelta64[m]").astype(np.float64) / 15.0
        bar_df["bars_since_last_sweep"] = bars_since.astype(np.float32)

    return bar_df


def asof_join_history(anatomy: pd.DataFrame, bar_df: pd.DataFrame) -> pd.DataFrame:
    a = anatomy.sort_values("timestamp").copy()
    a["timestamp"] = pd.to_datetime(a["timestamp"])
    b = bar_df.sort_values("bar_ts").copy()
    b = b.rename(columns={"bar_ts": "timestamp"})
    return pd.merge_asof(a, b, on="timestamp", direction="backward")


def _fit_multiclass(X_tr, y_tr, X_te, y_te, labels_order):
    present = sorted(set(y_tr) | set(y_te), key=lambda z: labels_order.index(z) if z in labels_order else 999)
    train_labels = set(y_tr)
    present = [p for p in present if p in train_labels]
    if len(present) < 2:
        return {"error": "degenerate label set", "labels": present}
    clf = LogisticRegression(max_iter=2500, solver="lbfgs")
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
    maj = Counter(y_tr).most_common(1)[0][0]
    maj_bal = float(balanced_accuracy_score(y_te, np.array([maj] * len(y_te))))
    return {
        "n_train": int(len(y_tr)),
        "n_test": int(len(y_te)),
        "labels": present,
        "classes_fit": [str(c) for c in classes],
        "per_class_auc_test_ovr": per_class_auc,
        "macro_auc_test_ovr": float(np.mean(vals)) if vals else None,
        "balanced_accuracy_test": bal_acc,
        "majority_baseline_balanced_accuracy_test": maj_bal,
        "test_base_rates": {str(k): float(v) for k, v in pd.Series(y_te).value_counts(normalize=True).items()},
        "n_features": int(X_tr.shape[1]),
    }


def _fit_binary(X_tr, y_tr, X_te, y_te):
    if len(np.unique(y_tr)) < 2 or len(np.unique(y_te)) < 2:
        return {"auc_train": None, "auc_test": None, "note": "degenerate"}
    clf = LogisticRegression(max_iter=2000, solver="lbfgs")
    clf.fit(X_tr, y_tr)
    return {
        "auc_train": float(roc_auc_score(y_tr, clf.predict_proba(X_tr)[:, 1])),
        "auc_test": float(roc_auc_score(y_te, clf.predict_proba(X_te)[:, 1])),
        "n_train": int(len(y_tr)),
        "n_test": int(len(y_te)),
        "base_test": float(np.mean(y_te)),
        "n_features": int(X_tr.shape[1]),
    }


def build_asof_matrix(engine_state: pd.Series, fit_idx, transform_idx):
    enc = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    X_fit = enc.fit_transform(engine_state.iloc[fit_idx].astype(str).to_frame())
    X_all = enc.transform(engine_state.astype(str).to_frame())
    return X_all, enc, [f"asof__{c}" for c in enc.categories_[0]]


def build_history_matrix(df: pd.DataFrame, fit_idx):
    """Numeric history + one-hot asof + one-hot last_k states. Fit encoders on train only."""
    num_cols = [
        "dwell_bars_in_current_state",
        "n_transitions_lookback_4",
        "n_transitions_lookback_16",
        "n_transitions_lookback_64",
        "frac_time_in_RANGE_W64",
        "frac_time_in_SWEEP_W64",
        "frac_time_in_EXPANSION_W64",
        "frac_time_in_DISPLACEMENT_W64",
        "frac_time_in_EXECUTION_W64",
        "bars_since_last_sweep",
        "last_3_states_hash",
    ]
    cat_cols = ["engine_state", "last_1_state", "last_2_state", "last_3_state"]

    X_num = df[num_cols].astype(np.float64).copy()
    # impute bars_since_last_sweep with train median
    med = float(np.nanmedian(X_num.iloc[fit_idx]["bars_since_last_sweep"].to_numpy()))
    if not np.isfinite(med):
        med = 0.0
    X_num["bars_since_last_sweep"] = X_num["bars_since_last_sweep"].fillna(med)

    scaler = StandardScaler()
    num_fit = scaler.fit_transform(X_num.iloc[fit_idx])
    num_all = scaler.transform(X_num)

    enc = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    cat_frame = df[cat_cols].astype(str)
    enc.fit(cat_frame.iloc[fit_idx])
    cat_all = enc.transform(cat_frame)

    feature_names = [f"num__{c}" for c in num_cols]
    for col_name, cats in zip(cat_cols, enc.categories_):
        for c in cats:
            feature_names.append(f"cat__{col_name}__{c}")

    X_all = np.hstack([num_all, cat_all])
    return X_all, feature_names, {"num_cols": num_cols, "cat_cols": cat_cols, "sweep_impute_median": med}


def univariate_ranking(df: pd.DataFrame, y: pd.Series, train_idx, test_idx, labels_order, top_n=20):
    """Strong univariate ranking: each history feature -> OVR macro AUC on test."""
    candidates = []
    # numeric
    for col in [
        "dwell_bars_in_current_state",
        "n_transitions_lookback_4",
        "n_transitions_lookback_16",
        "n_transitions_lookback_64",
        "frac_time_in_RANGE_W64",
        "frac_time_in_SWEEP_W64",
        "frac_time_in_EXPANSION_W64",
        "frac_time_in_DISPLACEMENT_W64",
        "frac_time_in_EXECUTION_W64",
        "bars_since_last_sweep",
        "last_3_states_hash",
        "bars_to_peak_within_trade",  # not a predictor; skip below
    ]:
        if col == "bars_to_peak_within_trade":
            continue
        if col not in df.columns:
            continue
        candidates.append(("numeric", col))
    for col in ["engine_state", "last_1_state", "last_2_state", "last_3_state"]:
        candidates.append(("categorical", col))

    mask = y.notna()
    tr = np.array([i for i in train_idx if bool(mask.iloc[i])])
    te = np.array([i for i in test_idx if bool(mask.iloc[i])])
    y_tr = y.iloc[tr].astype(str).to_numpy()
    y_te = y.iloc[te].astype(str).to_numpy()

    rows = []
    for kind, col in candidates:
        try:
            if kind == "numeric":
                x = df[col].astype(np.float64).to_numpy()
                # impute
                med = float(np.nanmedian(x[tr]))
                if not np.isfinite(med):
                    med = 0.0
                x = np.where(np.isfinite(x), x, med).reshape(-1, 1)
                # standardize using train
                mu, sd = float(x[tr].mean()), float(x[tr].std())
                if sd < 1e-12:
                    sd = 1.0
                x = (x - mu) / sd
                feat_names = [col]
            else:
                enc = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
                enc.fit(df.iloc[tr][[col]].astype(str))
                x = enc.transform(df[[col]].astype(str))
                feat_names = [f"{col}={c}" for c in enc.categories_[0]]
            res = _fit_multiclass(x[tr], y_tr, x[te], y_te, labels_order)
            # also binary extremes if applicable later
            rows.append(
                {
                    "feature": col,
                    "kind": kind,
                    "macro_auc_test_ovr": res.get("macro_auc_test_ovr"),
                    "balanced_accuracy_test": res.get("balanced_accuracy_test"),
                    "n_features_expanded": int(x.shape[1]),
                    "per_class_auc_test_ovr": res.get("per_class_auc_test_ovr"),
                }
            )
        except Exception as e:
            rows.append({"feature": col, "kind": kind, "error": str(e)})
    rows = [r for r in rows if r.get("macro_auc_test_ovr") is not None]
    rows.sort(key=lambda r: -(r["macro_auc_test_ovr"] or 0))
    return rows[:top_n], rows


def spearman_like_rank_auc(df, col, y_cont, train_idx, test_idx):
    """Binary? Use continuous target via rank: actually report Spearman corr on test + optional.
    For bars_to_peak continuous: use logistic on discretized? Brief asks continuous rank.
    Report |Spearman| on test between feature and continuous target.
    """
    from scipy.stats import spearmanr

    mask = y_cont.notna() & df[col].notna()
    te = np.array([i for i in test_idx if bool(mask.iloc[i])])
    if len(te) < 50:
        return None
    a = df[col].iloc[te].astype(float).to_numpy()
    b = y_cont.iloc[te].astype(float).to_numpy()
    if np.nanstd(a) < 1e-12 or np.nanstd(b) < 1e-12:
        return {"spearman": 0.0, "n": int(len(te))}
    r, p = spearmanr(a, b)
    return {"spearman": float(r), "pvalue": float(p), "n": int(len(te))}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, default=Path(r"D:\Tradelatest"))
    ap.add_argument("--anatomy", type=Path, default=None)
    ap.add_argument("--events", type=Path, default=None)
    ap.add_argument("--holdout-frac", type=float, default=0.30)
    ap.add_argument("--run-id", type=str, default=None)
    args = ap.parse_args()

    repo = args.repo
    anatomy_path = args.anatomy or (
        repo / "results/research/bnbusdt_trade_anatomy/trade_dataset_BNBUSDT.csv"
    )
    events_path = args.events or preferred_events(repo)
    events_changed = str(events_path) != str(
        repo / "results/run_20260603_122112_BNBUSDT/BNBUSDT_events.jsonl"
    )

    now = datetime.now(timezone.utc)
    run_id = args.run_id or f"jse003_engine_context_history_path_geometry_{now.strftime('%Y%m%d_%H%M%S')}"
    version = "JSE-003.v1"

    usecols = [
        "timestamp",
        "direction",
        "entry",
        "art_outcome",
        "outcome",
        "bars_to_peak_within_trade",
        "mfe_r",
        "time_to_bottom_path",
    ]
    anatomy = pd.read_csv(anatomy_path, usecols=usecols)
    anatomy["timestamp"] = pd.to_datetime(anatomy["timestamp"])
    anatomy["Y_joint"] = [
        y_joint_state(a, o) for a, o in zip(anatomy["art_outcome"], anatomy["outcome"])
    ]
    anatomy["peak_bucket"] = anatomy["bars_to_peak_within_trade"].map(peak_bucket)
    anatomy["mfe_bucket"] = anatomy["mfe_r"].map(mfe_bucket)
    anatomy["t_mae_dist_bucket"] = anatomy["time_to_bottom_path"].map(t_mae_dist_bucket)

    series, event_counts, sweep_ts = load_transition_series(events_path)
    bar_df = build_bar_history(series, sweep_ts)
    joined = asof_join_history(anatomy, bar_df)

    n_total = len(joined)
    n_joined = int(joined["engine_state"].notna().sum())
    coverage = float(n_joined / n_total) if n_total else 0.0

    sub = joined[joined["engine_state"].notna()].copy()
    sub = sub.sort_values("timestamp").reset_index(drop=True)
    n_sub = len(sub)
    cut = int(math.floor(n_sub * (1.0 - args.holdout_frac)))
    train_idx = np.arange(0, cut)
    test_idx = np.arange(cut, n_sub)

    peak_order = ["<=2", "3-5", "6-10", ">10"]
    mfe_order = ["<2", "2-4", "4-6", "6+"]
    tmae_order = ["<=5", "6-20", "21-40", "41-70", ">70"]

    # --- matrices ---
    X_asof, enc_asof, asof_names = build_asof_matrix(sub["engine_state"], train_idx, test_idx)
    X_hist, hist_names, hist_meta = build_history_matrix(sub, train_idx)

    def run_target(y_col, labels_order, tag):
        y = sub[y_col]
        mask = y.notna()
        tr = np.array([i for i in train_idx if bool(mask.iloc[i])])
        te = np.array([i for i in test_idx if bool(mask.iloc[i])])
        y_tr = y.iloc[tr].astype(str).to_numpy()
        y_te = y.iloc[te].astype(str).to_numpy()
        asof_res = _fit_multiclass(X_asof[tr], y_tr, X_asof[te], y_te, labels_order)
        hist_res = _fit_multiclass(X_hist[tr], y_tr, X_hist[te], y_te, labels_order)
        uni_top, uni_all = univariate_ranking(sub, y, train_idx, test_idx, labels_order)
        return {
            "target": tag,
            "asof_only": asof_res,
            "history_set": hist_res,
            "delta_macro_auc_history_minus_asof": (
                None
                if asof_res.get("macro_auc_test_ovr") is None
                or hist_res.get("macro_auc_test_ovr") is None
                else float(hist_res["macro_auc_test_ovr"] - asof_res["macro_auc_test_ovr"])
            ),
            "univariate_top": uni_top,
            "univariate_all": uni_all,
        }

    pred_peak = run_target("peak_bucket", peak_order, "peak_bucket")
    pred_mfe = run_target("mfe_bucket", mfe_order, "mfe_bucket")
    pred_tmae = run_target("t_mae_dist_bucket", tmae_order, "t_mae_dist_bucket")

    # Binary extremes
    def run_binary(mask_series, y_bin):
        ok = mask_series.to_numpy()
        tr = train_idx[ok[train_idx]]
        te = test_idx[ok[test_idx]]
        return {
            "asof_only": _fit_binary(X_asof[tr], y_bin[tr], X_asof[te], y_bin[te]),
            "history_set": _fit_binary(X_hist[tr], y_bin[tr], X_hist[te], y_bin[te]),
        }

    peak_ok = sub["peak_bucket"].notna()
    mfe_ok = sub["mfe_bucket"].notna()
    t_ok = sub["t_mae_dist_bucket"].notna()
    bin_peak = run_binary(peak_ok, (sub["peak_bucket"] == ">10").astype(int).to_numpy())
    bin_mfe = run_binary(mfe_ok, (sub["mfe_bucket"] == "6+").astype(int).to_numpy())
    bin_tmae = run_binary(t_ok, (sub["t_mae_dist_bucket"] == "<=5").astype(int).to_numpy())

    # Continuous rank associations for top numeric features vs bars_to_peak
    cont_rank = {}
    for col in [
        "dwell_bars_in_current_state",
        "n_transitions_lookback_4",
        "n_transitions_lookback_16",
        "n_transitions_lookback_64",
        "frac_time_in_RANGE_W64",
        "frac_time_in_SWEEP_W64",
        "frac_time_in_EXPANSION_W64",
        "frac_time_in_DISPLACEMENT_W64",
        "frac_time_in_EXECUTION_W64",
        "bars_since_last_sweep",
    ]:
        try:
            cont_rank[col] = spearman_like_rank_auc(
                sub, col, sub["bars_to_peak_within_trade"], train_idx, test_idx
            )
        except Exception as e:
            cont_rank[col] = {"error": str(e)}

    # Chrono stability: also evaluate on first 50% train / last 50% of test? 
    # Simpler: second cut at 50/50 for sensitivity
    cut2 = int(math.floor(n_sub * 0.5))
    tr2 = np.arange(0, cut2)
    te2 = np.arange(cut2, n_sub)
    X_asof2, _, _ = build_asof_matrix(sub["engine_state"], tr2, te2)
    X_hist2, _, _ = build_history_matrix(sub, tr2)

    def stability_target(y_col, labels_order):
        y = sub[y_col]
        mask = y.notna()
        tr = np.array([i for i in tr2 if bool(mask.iloc[i])])
        te = np.array([i for i in te2 if bool(mask.iloc[i])])
        y_tr = y.iloc[tr].astype(str).to_numpy()
        y_te = y.iloc[te].astype(str).to_numpy()
        a = _fit_multiclass(X_asof2[tr], y_tr, X_asof2[te], y_te, labels_order)
        h = _fit_multiclass(X_hist2[tr], y_tr, X_hist2[te], y_te, labels_order)
        return {
            "asof_macro_auc": a.get("macro_auc_test_ovr"),
            "history_macro_auc": h.get("macro_auc_test_ovr"),
        }

    stability = {
        "scheme": "chrono 50/50 sensitivity",
        "peak_bucket": stability_target("peak_bucket", peak_order),
        "mfe_bucket": stability_target("mfe_bucket", mfe_order),
    }

    # Headline metrics
    asof_peak = pred_peak["asof_only"].get("macro_auc_test_ovr")
    hist_peak = pred_peak["history_set"].get("macro_auc_test_ovr")
    asof_mfe = pred_mfe["asof_only"].get("macro_auc_test_ovr")
    hist_mfe = pred_mfe["history_set"].get("macro_auc_test_ovr")
    asof_best = max([x for x in [asof_peak, asof_mfe] if x is not None], default=None)
    hist_best = max([x for x in [hist_peak, hist_mfe] if x is not None], default=None)
    bin_hist_best = max(
        [
            x
            for x in [
                bin_peak["history_set"].get("auc_test"),
                bin_mfe["history_set"].get("auc_test"),
                bin_tmae["history_set"].get("auc_test"),
            ]
            if x is not None
        ],
        default=None,
    )

    def near_chance(a, lo=0.50, hi=0.55):
        return a is not None and lo <= a <= hi

    hist_macros = [x for x in [hist_peak, hist_mfe, pred_tmae["history_set"].get("macro_auc_test_ovr")] if x is not None]
    material_beat = (
        hist_best is not None
        and asof_best is not None
        and (hist_best - asof_best) >= 0.03
        and hist_best >= 0.58
    )
    # also check stability
    stab_hist = [
        stability["peak_bucket"].get("history_macro_auc"),
        stability["mfe_bucket"].get("history_macro_auc"),
    ]
    stab_ok = all(a is not None and a >= 0.56 for a in stab_hist) if material_beat else False

    if material_beat and stab_ok:
        lean = "SUPPORT_ASSOCIATION"
        lean_reason = (
            f"History feature set macro AUC (best={hist_best:.4f}) materially beats asof-only "
            f"(best={asof_best:.4f}) with chrono stability; association not causation; BNB-only; "
            "NOT CRT."
        )
    elif all(near_chance(a) or (a is not None and a < 0.55) for a in hist_macros) and (
        hist_best is None or hist_best < 0.58
    ):
        lean = "FALSIFY"
        lean_reason = (
            f"History AUC still ~chance (peak_macro={hist_peak}, mfe_macro={hist_mfe}); "
            "lean FALSIFY for engine_context_history->path_geometry on this join "
            "(BNB-only; one events run; not CRT)."
        )
    elif hist_best is not None and asof_best is not None and hist_best > asof_best + 0.02:
        lean = "WEAK_HISTORY_EDGE"
        lean_reason = (
            f"History beats asof modestly (hist_best={hist_best:.4f}, asof_best={asof_best:.4f}) "
            "but below SUPPORT threshold (AUC>=0.58 + stability)."
        )
    else:
        lean = "WEAK_MIXED"
        lean_reason = (
            f"asof_peak={asof_peak}, hist_peak={hist_peak}, asof_mfe={asof_mfe}, hist_mfe={hist_mfe}"
        )

    # Top history features across peak+mfe univariate
    top_merge = {}
    for blob in (pred_peak["univariate_all"], pred_mfe["univariate_all"]):
        for r in blob:
            if r.get("macro_auc_test_ovr") is None:
                continue
            f = r["feature"]
            top_merge.setdefault(f, []).append(r["macro_auc_test_ovr"])
    top_features = [
        {"feature": f, "mean_macro_auc_peak_mfe": float(np.mean(v)), "n_targets": len(v)}
        for f, v in top_merge.items()
    ]
    top_features.sort(key=lambda r: -r["mean_macro_auc_peak_mfe"])

    out_dir = repo / "results/research/jse003_engine_context_history_path_geometry"
    out_dir.mkdir(parents=True, exist_ok=True)

    feature_defs = {
        "engine_state_asof": "Piecewise-constant state_to as-of entry (baseline; JSE-001/002)",
        "dwell_bars_in_current_state": "M15 bars since last STATE_TRANSITION/RESET update",
        "n_transitions_lookback_W": "Count of STATE_TRANSITION/RESET bars in last W M15 bars; W in {4,16,64}",
        "frac_time_in_state_W64": "Fraction of last 64 M15 bars equal to RANGE/SWEEP/EXPANSION/DISPLACEMENT/EXECUTION",
        "last_k_states": "Previous 1-3 distinct states before current (categorical + md5-hash%97 of triple)",
        "bars_since_last_sweep": "Optional: M15 bars since last SWEEP event timestamp in same events file",
        "bar_definition": "1 bar = 15 minutes (M15 time-equivalent)",
        "not_invented": ["Parent", "HTF", "manipulation"],
    }

    artifact = {
        "finding_id": "JSE-003",
        "version": version,
        "run_id": run_id,
        "generated_at_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit_sha": "d7c25f6e55616261b8b229b000875abd3bd315eb",
        "branch": "feature/trace-parquet-duckdb-query",
        "episode": "JOINT_STATE_EXPLAINABILITY",
        "scope": "BNB-only (honest scope)",
        "title": "Does engine_context_history predict path geometry? (NOT CRT)",
        "question": (
            "Do history features from the same BNB runtime events timeline predict path geometry "
            "descriptors better than chance / better than single as-of state_to?"
        ),
        "ontology": {
            "predictor_family": "engine_context_history",
            "not_CRT_Context": True,
            "CRT_Context_equivalent_to_engine_context_history": False,
            "never_say": ["CRT falsified", "CRT Context", "upgrade to CRT"],
            "note": "Never call this CRT unless measuring declared CRT objects.",
        },
        "measurement_process": {
            "name": "engine_context_history",
            "built_from": str(events_path),
            "events_run_dir": events_path.parent.name,
            "same_as_jse001_preferred": not events_changed,
            "events_path_changed_from_preferred": events_changed,
            "population": "BNBUSDT anatomy rows with path geometry columns",
            "feature_definitions": feature_defs,
            "history_meta": hist_meta,
            "n_history_features_expanded": len(hist_names),
            "n_asof_features_expanded": len(asof_names),
        },
        "targets": {
            "peak_bucket": "L-003D buckets from bars_to_peak_within_trade",
            "mfe_bucket": "L-003D buckets from mfe_r",
            "t_mae_dist_bucket": "optional L-003E from time_to_bottom_path",
            "bars_to_peak_continuous_rank": "Spearman vs numeric history features on test",
        },
        "data": {
            "anatomy_path": str(anatomy_path),
            "anatomy_n": int(n_total),
            "events_path": str(events_path),
            "events_bytes": int(events_path.stat().st_size),
            "events_series_n_updates": int(len(series)),
            "event_type_counts_in_file": event_counts,
            "bar_grid_n": int(len(bar_df)),
            "n_sweep_events": int(len(sweep_ts)),
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
            "feature_null_rates": {
                "bars_since_last_sweep": float(sub["bars_since_last_sweep"].isna().mean()),
                "dwell_bars_in_current_state": float(sub["dwell_bars_in_current_state"].isna().mean()),
            },
        },
        "design": {
            "holdout": {
                "scheme": "chronological within BNB joined subset",
                "train_frac": 1.0 - args.holdout_frac,
                "test_frac": args.holdout_frac,
                "cut_index": cut,
                "n_train": int(len(train_idx)),
                "n_test": int(len(test_idx)),
            },
            "model": "sklearn LogisticRegression (multivariate); univariate ranking of history features",
            "stability_check": stability,
        },
        "headline": {
            "asof_only_macro_auc_peak_bucket": asof_peak,
            "history_macro_auc_peak_bucket": hist_peak,
            "asof_only_macro_auc_mfe_bucket": asof_mfe,
            "history_macro_auc_mfe_bucket": hist_mfe,
            "delta_peak": pred_peak["delta_macro_auc_history_minus_asof"],
            "delta_mfe": pred_mfe["delta_macro_auc_history_minus_asof"],
            "best_asof_macro": asof_best,
            "best_history_macro": hist_best,
            "best_history_binary_auc": bin_hist_best,
            "top_history_features_mean_macro_auc": top_features[:12],
        },
        "predictability": {
            "peak_bucket": {
                "asof_only": pred_peak["asof_only"],
                "history_set": pred_peak["history_set"],
                "delta_macro_auc": pred_peak["delta_macro_auc_history_minus_asof"],
                "univariate_top": pred_peak["univariate_top"],
            },
            "mfe_bucket": {
                "asof_only": pred_mfe["asof_only"],
                "history_set": pred_mfe["history_set"],
                "delta_macro_auc": pred_mfe["delta_macro_auc_history_minus_asof"],
                "univariate_top": pred_mfe["univariate_top"],
            },
            "t_mae_dist_bucket": {
                "asof_only": pred_tmae["asof_only"],
                "history_set": pred_tmae["history_set"],
                "delta_macro_auc": pred_tmae["delta_macro_auc_history_minus_asof"],
                "univariate_top": pred_tmae["univariate_top"],
            },
            "binary_peak_gt10": bin_peak,
            "binary_mfe_6plus": bin_mfe,
            "binary_t_mae_early_le5": bin_tmae,
            "bars_to_peak_spearman_vs_numeric_history": cont_rank,
        },
        "falsification": {
            "stance": (
                "If history AUC still ~0.50-0.55, lean FALSIFY for engine_context_history->path_geometry "
                "on this join. If history beats asof materially (AUC>=0.58+ with chrono stability), "
                "lean SUPPORT_ASSOCIATION (not cause)."
            ),
            "lean": lean,
            "lean_reason": lean_reason,
            "material_beat_threshold": {
                "delta_ge": 0.03,
                "history_auc_ge": 0.58,
                "stability_macro_ge": 0.56,
            },
        },
        "limitations": [
            "one instrument (BNBUSDT)",
            "one runtime events run (GT-3)",
            "history derived only from STATE_TRANSITION/RESET (+ SWEEP timestamps optional)",
            "not Parent/HTF/manipulation",
            "NOT CRT Context / never upgrade to CRT",
            "M15 bar grid approximation for lookbacks",
        ],
        "observation_hierarchy_banner": (
            "Entry weak (L-003G) · Current engine_state_asof weak (JSE-001/002) · "
            "Path geometry strong (L-003C–E) · engine_context_history = JSE-003"
        ),
        "non_promotions": {
            "edge": False,
            "attribution": False,
            "which_outcome_correct": False,
            "l003_doctrine_edit": False,
            "full_crt_ontology_claim": False,
            "crt_falsified_claim": False,
            "causal_claim": False,
        },
        "artifacts": [
            "docs/research/jse003_engine_context_history_path_geometry-2026-09-07.json",
            "docs/research/JOINT_STATE_EXPLAINABILITY.md",
            "scripts/research/jse003_engine_context_history_path_geometry.py",
            "results/research/jse003_engine_context_history_path_geometry/",
            "docs/research/joint_state_explainability_pin.json",
        ],
    }

    json_path = repo / "docs/research/jse003_engine_context_history_path_geometry-2026-09-07.json"
    json_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    summary_path = out_dir / f"{run_id}_summary.json"
    summary_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")

    # Compact CSVs
    pd.DataFrame(top_features).to_csv(out_dir / f"{run_id}_top_history_features.csv", index=False)
    pd.DataFrame(pred_peak["univariate_all"]).to_csv(
        out_dir / f"{run_id}_univariate_peak_bucket.csv", index=False
    )
    pd.DataFrame(pred_mfe["univariate_all"]).to_csv(
        out_dir / f"{run_id}_univariate_mfe_bucket.csv", index=False
    )

    print(
        json.dumps(
            {
                "run_id": run_id,
                "coverage": coverage,
                "lean": lean,
                "asof_peak_macro": asof_peak,
                "hist_peak_macro": hist_peak,
                "asof_mfe_macro": asof_mfe,
                "hist_mfe_macro": hist_mfe,
                "bin_peak_hist": bin_peak["history_set"].get("auc_test"),
                "bin_mfe_hist": bin_mfe["history_set"].get("auc_test"),
                "top3_features": top_features[:3],
                "events_path": str(events_path),
                "json_path": str(json_path),
                "stability": stability,
            },
            indent=2,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

