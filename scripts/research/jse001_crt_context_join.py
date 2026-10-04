#!/usr/bin/env python3
"""JSE-001: engine_state_asof vs joint-state membership (BNB-only).
NOT a CRT claim; CRT Context ≠ engine_state_asof.

MeasurementProcess: engine_state_asof
  Piecewise-constant state from ONE runtime BNBUSDT_events.jsonl
  (STATE_TRANSITION + RESET -> RANGE), as-of joined to anatomy entry timestamps.

Does NOT claim full CRT ontology / HTF / parent. No L-003 doctrine edits.
No src/ edits. No edge/attribution promotion. No "which outcome is right".
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import OneHotEncoder

# L-003M canonical map: (Y_scanner, Y_oracle) -> STATE_*
# Columns: art_outcome = scanner_terminal_label, outcome = oracle_terminal_label
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


def load_engine_state_series(events_path: Path) -> pd.DataFrame:
    """Build piecewise-constant updates from STATE_TRANSITION + RESET.

    RESET rule (documented): RESET events carry state_to='RANGE' in this stream
    and are treated as clearing CRT path state back to RANGE (include in series).
    Non-STATE_TRANSITION / non-RESET events are ignored for the state series
    (GT-3: single events population only; SWEEP etc. may set state_to null).
    """
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
    # Deduplicate identical timestamps: keep last update in file order (already sorted stable)
    df = df.drop_duplicates(subset=["timestamp"], keep="last").reset_index(drop=True)
    return df, dict(n_by_event)


def asof_join(anatomy: pd.DataFrame, series: pd.DataFrame) -> pd.DataFrame:
    a = anatomy.sort_values("timestamp").copy()
    s = series[["timestamp", "engine_state"]].sort_values("timestamp").copy()
    a["timestamp"] = pd.to_datetime(a["timestamp"])
    s["timestamp"] = pd.to_datetime(s["timestamp"])
    joined = pd.merge_asof(
        a, s, on="timestamp", direction="backward", suffixes=("", "_eng")
    )
    return joined


def chi2_independence(counts_2d: np.ndarray) -> dict:
    """Simple chi-square for contingency; returns chi2, dof, p (approx via scipy if present else None)."""
    observed = counts_2d.astype(float)
    if observed.size == 0 or observed.sum() == 0:
        return {"chi2": None, "dof": None, "p": None}
    row = observed.sum(axis=1, keepdims=True)
    col = observed.sum(axis=0, keepdims=True)
    expected = row @ col / observed.sum()
    with np.errstate(divide="ignore", invalid="ignore"):
        mask = expected > 0
        chi2 = float(np.sum((observed[mask] - expected[mask]) ** 2 / expected[mask]))
    dof = int((observed.shape[0] - 1) * (observed.shape[1] - 1))
    p = None
    try:
        from scipy.stats import chi2 as chi2_dist

        p = float(chi2_dist.sf(chi2, dof)) if dof > 0 else None
    except Exception:
        p = None
    return {"chi2": chi2, "dof": dof, "p": p, "expected_min": float(expected.min()) if expected.size else None}


def one_vs_rest_auc_from_state(
    engine_state: pd.Series, y_binary: np.ndarray, train_idx, test_idx
) -> dict:
    """One-hot engine_state -> LogisticRegression; report train/test AUC for STATE_SL_TP."""
    enc = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    X = enc.fit_transform(engine_state.astype(str).to_frame())
    X_tr, X_te = X[train_idx], X[test_idx]
    y_tr, y_te = y_binary[train_idx], y_binary[test_idx]
    if y_tr.sum() == 0 or y_tr.sum() == len(y_tr) or y_te.sum() == 0 or y_te.sum() == len(y_te):
        return {
            "auc_train": None,
            "auc_test": None,
            "n_train": int(len(y_tr)),
            "n_test": int(len(y_te)),
            "base_test": float(y_te.mean()) if len(y_te) else None,
            "note": "degenerate class split",
        }
    clf = LogisticRegression(max_iter=1000, solver="lbfgs")
    clf.fit(X_tr, y_tr)
    p_tr = clf.predict_proba(X_tr)[:, 1]
    p_te = clf.predict_proba(X_te)[:, 1]
    return {
        "auc_train": float(roc_auc_score(y_tr, p_tr)),
        "auc_test": float(roc_auc_score(y_te, p_te)),
        "n_train": int(len(y_tr)),
        "n_test": int(len(y_te)),
        "base_test": float(y_te.mean()),
        "n_features": int(X.shape[1]),
        "categories": [str(c) for c in enc.categories_[0]],
    }


def multiclass_ovr_macro_auc(engine_state: pd.Series, y_state: pd.Series, train_idx, test_idx, targets) -> dict:
    """One-vs-rest macro AUC across target joint states from engine_state only."""
    enc = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    X = enc.fit_transform(engine_state.astype(str).to_frame())
    X_tr, X_te = X[train_idx], X[test_idx]
    aucs = {}
    for t in targets:
        y = (y_state == t).astype(int).to_numpy()
        y_tr, y_te = y[train_idx], y[test_idx]
        if len(np.unique(y_tr)) < 2 or len(np.unique(y_te)) < 2:
            aucs[t] = None
            continue
        clf = LogisticRegression(max_iter=1000, solver="lbfgs")
        clf.fit(X_tr, y_tr)
        p_te = clf.predict_proba(X_te)[:, 1]
        aucs[t] = float(roc_auc_score(y_te, p_te))
    vals = [v for v in aucs.values() if v is not None]
    return {
        "per_state_auc_test": aucs,
        "macro_auc_test": float(np.mean(vals)) if vals else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, default=Path(r"D:\Tradelatest"))
    ap.add_argument(
        "--anatomy",
        type=Path,
        default=None,
        help="Default: results/research/bnbusdt_trade_anatomy/trade_dataset_BNBUSDT.csv",
    )
    ap.add_argument(
        "--events",
        type=Path,
        default=None,
        help="Default: largest results/run_*_BNBUSDT/BNBUSDT_events.jsonl",
    )
    ap.add_argument("--min-n-state", type=int, default=500)
    ap.add_argument("--holdout-frac", type=float, default=0.30)
    ap.add_argument("--run-id", type=str, default=None)
    args = ap.parse_args()

    repo = args.repo
    anatomy_path = args.anatomy or (
        repo / "results/research/bnbusdt_trade_anatomy/trade_dataset_BNBUSDT.csv"
    )
    events_path = args.events or find_largest_events(repo / "results")

    now = datetime.now(timezone.utc)
    run_id = args.run_id or f"jse001_crt_context_bnbusdt_{now.strftime('%Y%m%d_%H%M%S')}"
    version = "JSE-001.v1"

    anatomy = pd.read_csv(anatomy_path, usecols=["timestamp", "art_outcome", "outcome", "hour", "session_derived"])
    anatomy["timestamp"] = pd.to_datetime(anatomy["timestamp"])
    anatomy["Y_joint"] = [
        y_joint_state(a, o) for a, o in zip(anatomy["art_outcome"], anatomy["outcome"])
    ]
    anatomy["scanner_terminal_label"] = anatomy["art_outcome"]
    anatomy["oracle_terminal_label"] = anatomy["outcome"]

    series, event_counts = load_engine_state_series(events_path)
    joined = asof_join(anatomy, series)

    n_total = len(joined)
    n_joined = int(joined["engine_state"].notna().sum())
    coverage = float(n_joined / n_total) if n_total else 0.0
    crt_join_weak = coverage < 0.50

    sub = joined[joined["engine_state"].notna()].copy()
    base_rates = sub["Y_joint"].value_counts(normalize=True).to_dict()
    base_counts = sub["Y_joint"].value_counts().to_dict()
    state_marginals = sub["engine_state"].value_counts().to_dict()

    focus = ["STATE_SL_TP", "STATE_SL_SL", "STATE_TP_TP"]
    lifts = []
    for eng, n in sorted(state_marginals.items(), key=lambda x: -x[1]):
        if n < args.min_n_state:
            continue
        g = sub[sub["engine_state"] == eng]
        row = {"engine_state": eng, "n": int(n)}
        for s in focus:
            rate = float((g["Y_joint"] == s).mean())
            base = float(base_rates.get(s, 0.0))
            row[f"rate_{s}"] = rate
            row[f"base_{s}"] = base
            row[f"lift_{s}"] = (rate / base) if base > 0 else None
            row[f"delta_{s}"] = rate - base
        lifts.append(row)

    # Contingency chi-square: engine_state (n>=min) x focus states + OTHER
    eng_keep = [e for e, n in state_marginals.items() if n >= args.min_n_state]
    if eng_keep:
        mat = []
        for e in eng_keep:
            g = sub[sub["engine_state"] == e]
            mat.append([(g["Y_joint"] == s).sum() for s in focus])
        chi = chi2_independence(np.array(mat))
    else:
        chi = {"chi2": None, "dof": None, "p": None}

    # Chronological holdout within BNB joined subset
    sub = sub.sort_values("timestamp").reset_index(drop=True)
    n_sub = len(sub)
    cut = int(math.floor(n_sub * (1.0 - args.holdout_frac)))
    train_idx = np.arange(0, cut)
    test_idx = np.arange(cut, n_sub)
    y_sl_tp = (sub["Y_joint"] == "STATE_SL_TP").astype(int).to_numpy()

    pred_sl_tp = one_vs_rest_auc_from_state(sub["engine_state"], y_sl_tp, train_idx, test_idx)
    pred_multi = multiclass_ovr_macro_auc(
        sub["engine_state"], sub["Y_joint"], train_idx, test_idx, focus
    )

    # Optional: engine_state + hour (report engine_state-only first; include secondary)
    hour_auc = None
    try:
        enc = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
        feats = sub[["engine_state"]].astype(str).copy()
        feats["hour"] = sub["hour"].fillna(-1).astype(int).astype(str)
        X = enc.fit_transform(feats)
        X_tr, X_te = X[train_idx], X[test_idx]
        y_tr, y_te = y_sl_tp[train_idx], y_sl_tp[test_idx]
        if len(np.unique(y_tr)) >= 2 and len(np.unique(y_te)) >= 2:
            clf = LogisticRegression(max_iter=1000, solver="lbfgs")
            clf.fit(X_tr, y_tr)
            hour_auc = {
                "auc_test": float(roc_auc_score(y_te, clf.predict_proba(X_te)[:, 1])),
                "auc_train": float(roc_auc_score(y_tr, clf.predict_proba(X_tr)[:, 1])),
                "features": "engine_state + hour",
            }
    except Exception as ex:
        hour_auc = {"error": str(ex)}

    l003g_prior_auc = 0.516
    auc_test = pred_sl_tp.get("auc_test")
    # Primary falsification target = STATE_SL_TP (episode question); other states reported separately
    lifts_null = True
    for row in lifts:
        lift = row.get("lift_STATE_SL_TP")
        if lift is not None and abs(lift - 1.0) >= 0.10:
            lifts_null = False
            break

    if auc_test is None:
        lean = "INCONCLUSIVE"
        lean_reason = "AUC unavailable (degenerate split or empty join)"
    elif 0.5 <= auc_test <= 0.55 and lifts_null:
        lean = "FALSIFY"
        lean_reason = (
            "AUC in ~0.5-0.55 and STATE_SL_TP lifts ~null => CRT/engine context on this join does NOT "
            "explain STATE_SL_TP membership (BNB-only). Valid negative result."
        )
    elif auc_test > 0.55 and not lifts_null:
        lean = "SUPPORT_LEAN"
        lean_reason = "AUC > 0.55 with non-null STATE_SL_TP lifts; engine_state_asof may associate (not causal claim)"
    else:
        lean = "WEAK_MIXED"
        lean_reason = f"auc_test={auc_test:.4f}, lifts_null_STATE_SL_TP={lifts_null}"

    better_than_l003g = None if auc_test is None else bool(auc_test > l003g_prior_auc + 0.02)

    out_dir = repo / "results/research/jse001_crt_context_bnbusdt"
    out_dir.mkdir(parents=True, exist_ok=True)

    artifact = {
        "finding_id": "JSE-001",
        "version": version,
        "run_id": run_id,
        "generated_at_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit_sha": "d7c25f6e55616261b8b229b000875abd3bd315eb",
        "branch": "feature/trace-parquet-duckdb-query",
        "episode": "JOINT_STATE_EXPLAINABILITY",
        "scope": "BNB-only (honest scope)",
        "question": "Does engine_state_asof explain / predict joint-state membership on this join?",
        "measurement_process": {
            "name": "engine_state_asof",
            "definition": (
                "As-of last known engine state_to at or before anatomy entry timestamp, "
                "from piecewise-constant series built from STATE_TRANSITION (+ RESET->RANGE) "
                "in ONE runtime BNBUSDT_events.jsonl population (GT-3)."
            ),
            "not_claimed": [
                "full CRT ontology",
                "HTF parent context",
                "parent_crt without evidence",
            ],
        },
        "reset_rule": {
            "rule": "RESET updates engine state to state_to (observed RANGE in this stream)",
            "interpretation": "RESET clears engine path state back to RANGE for the piecewise series (not a CRT ontology claim)",
            "included_in_series": True,
        },
        "data": {
            "anatomy_path": str(anatomy_path),
            "anatomy_n": int(n_total),
            "anatomy_ts_min": str(anatomy["timestamp"].min()),
            "anatomy_ts_max": str(anatomy["timestamp"].max()),
            "events_path": str(events_path),
            "events_run_dir": events_path.parent.name,
            "events_bytes": int(events_path.stat().st_size),
            "events_series_n_updates": int(len(series)),
            "events_ts_min": str(series["timestamp"].min()),
            "events_ts_max": str(series["timestamp"].max()),
            "event_type_counts_in_file": event_counts,
            "gt3": "ONE runtime events population only; no integrity_events / secondlow / other instruments mixed",
            "Y_scanner_col": "art_outcome",
            "Y_oracle_col": "outcome",
            "state_map": "L-003M canonical STATE_* from (scanner_terminal_label, oracle_terminal_label)",
        },
        "coverage": {
            "n_anatomy": n_total,
            "n_joined_non_null": n_joined,
            "fraction": coverage,
            "CRT_JOIN_WEAK": crt_join_weak,
            "threshold": 0.50,
        },
        "joined_subset": {
            "n": int(n_sub),
            "Y_joint_counts": {k: int(v) for k, v in base_counts.items()},
            "Y_joint_base_rates": {k: float(v) for k, v in base_rates.items()},
            "engine_state_marginals": {k: int(v) for k, v in state_marginals.items()},
        },
        "lifts_by_engine_state_n_ge_500": lifts,
        "chi_square_engine_state_x_focus_joint": chi,
        "predictability": {
            "target_primary": "STATE_SL_TP membership (one-vs-rest)",
            "features_primary": "engine_state only (one-hot)",
            "holdout": {
                "scheme": "chronological within BNB joined subset",
                "train_frac": 1.0 - args.holdout_frac,
                "test_frac": args.holdout_frac,
                "cut_index": cut,
            },
            "engine_state_only_STATE_SL_TP": pred_sl_tp,
            "engine_state_only_multiclass_ovr_focus": pred_multi,
            "secondary_engine_state_plus_hour": hour_auc,
            "L003G_prior_entry_time_AUC": l003g_prior_auc,
            "engine_state_better_than_L003G_by_0p02": better_than_l003g,
        },
        "falsification": {
            "stance": "If AUC≈0.5–0.55 and lifts null → engine_state_asof on this join does not explain STATE_SL_TP (BNB). Not a CRT-falsified claim.",
            "lifts_null_STATE_SL_TP_abs_lt_0p10": lifts_null,
            "primary_target": "STATE_SL_TP",
            "lean": lean,
            "lean_reason": lean_reason,
        },
        "non_promotions": {
            "edge": False,
            "attribution": False,
            "which_outcome_correct": False,
            "l003_doctrine_edit": False,
            "full_crt_ontology_claim": False,
        },
        "artifacts": [
            "docs/research/JOINT_STATE_EXPLAINABILITY.md",
            "docs/research/jse001_crt_context_bnbusdt-2026-09-07.json",
            "scripts/research/jse001_crt_context_join.py",
            "results/research/jse001_crt_context_bnbusdt/",
            "docs/research/joint_state_explainability_pin.json",
        ],
    }

    json_path = repo / "docs/research/jse001_crt_context_bnbusdt-2026-09-07.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")

    summary_path = out_dir / f"{run_id}_summary.json"
    summary_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")

    # Compact CSV lifts
    if lifts:
        pd.DataFrame(lifts).to_csv(out_dir / f"{run_id}_lifts.csv", index=False)

    print(json.dumps({
        "run_id": run_id,
        "coverage": coverage,
        "CRT_JOIN_WEAK": crt_join_weak,
        "n_joined": n_joined,
        "auc_test": auc_test,
        "lean": lean,
        "events": events_path.parent.name,
        "json_path": str(json_path),
        "summary_path": str(summary_path),
        "top_lifts": lifts[:8],
    }, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
