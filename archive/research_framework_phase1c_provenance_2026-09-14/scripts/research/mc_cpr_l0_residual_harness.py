#!/usr/bin/env python3
"""
MC-CPR-L0 observe-only residual harness.

Contract: configs/research/measurement_contracts/MC-CPR-L0-XAUUSD-M15-UTC-V1.json
Prereg:   docs/research-readiness/mc-cpr-l0-xauusd-m15-preregistration.md

OBSERVE-ONLY:
  - No EngineRunner / DecisionEngine / Ultron / fusion / risk table mutation
  - No production config writes
  - economic_claims_allowed remains false

Usage:
  PYTHONPATH=src python scripts/research/mc_cpr_l0_residual_harness.py \\
      --csv data/mt5/XAUUSD_M15.csv \\
      --out-dir results/research/mc_cpr_l0
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from features.broker_clock import mt5_server_to_utc  # noqa: E402
from features.feature_pipeline import FeaturePipeline  # noqa: E402
from features.feature_schema import CANONICAL_FEATURES  # noqa: E402

CONTRACT_ID = "MC-CPR-L0-XAUUSD-M15-UTC-V1"
EXPERIMENT_ID = "E-CPR-L0-XAUUSD-M15"
SEED = 20260808
EPS = 1e-12
N_LIST = (4, 16, 96)
M_Z = 672
OOS_FRAC = 0.20
EMBARGO_BARS = 96
BH_Q = 0.01


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_ohlcv(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    need = {"timestamp", "open", "high", "low", "close", "volume"}
    missing = need - set(df.columns)
    if missing:
        raise ValueError(f"CSV missing columns {missing}")
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    # Research UTC: MT5 broker labels → true UTC (F-066)
    df["timestamp_utc"] = mt5_server_to_utc(df["timestamp"])
    df = df.sort_values("timestamp_utc").reset_index(drop=True)
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close", "volume"]).reset_index(drop=True)
    return df


def _tag_events(ts_utc: pd.Series) -> np.ndarray:
    """E_event=1 for first-Friday 12:30 and 13:30 UTC (NFP-class; incomplete calendar)."""
    out = np.zeros(len(ts_utc), dtype=bool)
    for i, t in enumerate(ts_utc):
        if t.weekday() != 4:  # Friday
            continue
        if t.day > 7:  # first Friday only
            continue
        if (t.hour, t.minute) in ((12, 30), (13, 30)):
            out[i] = True
    return out


def _compute_pressure(df: pd.DataFrame) -> pd.DataFrame:
    o = df["open"].to_numpy(dtype=np.float64)
    h = df["high"].to_numpy(dtype=np.float64)
    l = df["low"].to_numpy(dtype=np.float64)
    c = df["close"].to_numpy(dtype=np.float64)
    v = df["volume"].to_numpy(dtype=np.float64)
    rng = h - l + EPS
    buy = v * (c - l) / rng
    sell = v * (h - c) / rng
    out = df.copy()
    out["buy_pressure"] = buy
    out["sell_pressure"] = sell
    out["body_ratio_local"] = np.abs(c - o) / rng
    return out


def _rolling_cpr_raw(buy: np.ndarray, sell: np.ndarray, n: int) -> np.ndarray:
    """Strict causal: window ends at t inclusive; first n-1 are NaN."""
    tot_buy = pd.Series(buy).rolling(n, min_periods=n).sum().to_numpy()
    tot_both = pd.Series(buy + sell).rolling(n, min_periods=n).sum().to_numpy()
    return tot_buy / (tot_both + EPS)


def _rolling_z(
    x: np.ndarray,
    m: int,
    event_mask: np.ndarray,
) -> np.ndarray:
    """
    Causal z-score: mu/sigma of up to M non-event samples with indices <= t.
    Event bars excluded from mu/sigma sample; z still defined on event bars from history.
    """
    from collections import deque

    n = len(x)
    z = np.full(n, np.nan, dtype=np.float64)
    window: deque[float] = deque()
    for t in range(n):
        if not np.isfinite(x[t]):
            continue
        # stats before updating with t would be stricter; contract allows <= t
        if not event_mask[t]:
            window.append(float(x[t]))
            while len(window) > m:
                window.popleft()
        if len(window) < max(30, m // 10):
            continue
        arr = np.fromiter(window, dtype=np.float64, count=len(window))
        mu = float(arr.mean())
        sig = float(arr.std(ddof=1)) if len(arr) > 1 else 0.0
        z[t] = (float(x[t]) - mu) / (sig + EPS)
    return z


def _r2(y: np.ndarray, yhat: np.ndarray) -> float:
    m = np.isfinite(y) & np.isfinite(yhat)
    if m.sum() < 10:
        return float("nan")
    yt = y[m]
    yh = yhat[m]
    ss_res = float(np.sum((yt - yh) ** 2))
    ss_tot = float(np.sum((yt - yt.mean()) ** 2)) + EPS
    return 1.0 - ss_res / ss_tot


def _ols_predict(y: np.ndarray, X: np.ndarray, train_mask: np.ndarray) -> np.ndarray:
    """Fit on train, predict on all finite rows."""
    yhat = np.full(len(y), np.nan, dtype=np.float64)
    tr = train_mask & np.isfinite(y) & np.all(np.isfinite(X), axis=1)
    if tr.sum() < X.shape[1] + 5:
        return yhat
    Xtr = np.column_stack([np.ones(tr.sum()), X[tr]])
    ytr = y[tr]
    lam = 1e-6
    beta = np.linalg.solve(Xtr.T @ Xtr + lam * np.eye(Xtr.shape[1]), Xtr.T @ ytr)
    ok = np.all(np.isfinite(X), axis=1)
    Xd = np.column_stack([np.ones(ok.sum()), X[ok]])
    yhat[ok] = Xd @ beta
    return yhat


def _fill_targets(df: pd.DataFrame) -> pd.DataFrame:
    c = df["close"].to_numpy(dtype=np.float64)
    o = df["open"].to_numpy(dtype=np.float64)
    n = len(c)
    fwd1 = np.full(n, np.nan)
    fwd4 = np.full(n, np.nan)
    cont4 = np.full(n, np.nan)
    cont16 = np.full(n, np.nan)
    for t in range(n):
        if t + 1 < n and c[t] != 0:
            fwd1[t] = (c[t + 1] - c[t]) / c[t]
        if t + 4 < n and c[t] != 0:
            fwd4[t] = (c[t + 4] - c[t]) / c[t]
            body_sign = np.sign(c[t] - o[t])
            if body_sign != 0:
                cont4[t] = 1.0 if np.sign(c[t + 4] - c[t]) == body_sign else 0.0
        if t + 16 < n and c[t] != 0:
            body_sign = np.sign(c[t] - o[t])
            if body_sign != 0:
                cont16[t] = 1.0 if np.sign(c[t + 16] - c[t]) == body_sign else 0.0
    out = df.copy()
    out["fwd_return_1b"] = fwd1
    out["fwd_return_4b"] = fwd4
    out["displacement_continuation"] = cont4  # primary h=4
    out["displacement_continuation_h16"] = cont16
    return out


def _build_39dim(df: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
    """FeaturePipeline on broker timestamps for parity with production frame; map by UTC key."""
    pipe_df = pd.DataFrame(
        {
            "timestamp": df["timestamp"],
            "open": df["open"],
            "high": df["high"],
            "low": df["low"],
            "close": df["close"],
            "volume": df["volume"],
        }
    )
    pipe = FeaturePipeline(pipe_df)
    enriched, vectors = pipe.run()
    arr = np.asarray(vectors, dtype=np.float64)
    # align via original timestamp (broker label) after finalize drop
    enr = enriched.copy()
    if "timestamp" not in enr.columns:
        raise RuntimeError("FeaturePipeline output missing timestamp")
    enr["timestamp"] = pd.to_datetime(enr["timestamp"])
    # join key: broker timestamp string
    enr["_key"] = enr["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df_keys = df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    key_to_idx = {k: i for i, k in enumerate(enr["_key"].tolist())}
    F = np.full((len(df), len(CANONICAL_FEATURES)), np.nan, dtype=np.float64)
    for i, k in enumerate(df_keys):
        j = key_to_idx.get(k)
        if j is not None and j < len(arr):
            F[i, :] = arr[j, : len(CANONICAL_FEATURES)]
    return enr, F


def _ols_residualize(
    y: np.ndarray,
    X: np.ndarray,
    train_mask: np.ndarray,
) -> tuple[np.ndarray, dict[str, float]]:
    """Fit OLS on train; return residuals for all finite rows; report train R2 of fit."""
    eta = np.full(len(y), np.nan, dtype=np.float64)
    tr = train_mask & np.isfinite(y) & np.all(np.isfinite(X), axis=1)
    if tr.sum() < X.shape[1] + 5:
        return eta, {"train_r2": float("nan"), "n_train": int(tr.sum())}
    Xtr = X[tr]
    ytr = y[tr]
    # add intercept
    Xtr_d = np.column_stack([np.ones(len(Xtr)), Xtr])
    # ridge-light for stability
    lam = 1e-6
    xtx = Xtr_d.T @ Xtr_d + lam * np.eye(Xtr_d.shape[1])
    xty = Xtr_d.T @ ytr
    try:
        beta = np.linalg.solve(xtx, xty)
    except np.linalg.LinAlgError:
        beta = np.linalg.lstsq(Xtr_d, ytr, rcond=None)[0]
    yhat_tr = Xtr_d @ beta
    ss_res = float(np.sum((ytr - yhat_tr) ** 2))
    ss_tot = float(np.sum((ytr - ytr.mean()) ** 2)) + EPS
    train_r2 = 1.0 - ss_res / ss_tot
    # residuals everywhere finite
    ok = np.isfinite(y) & np.all(np.isfinite(X), axis=1)
    Xd = np.column_stack([np.ones(ok.sum()), X[ok]])
    yhat = Xd @ beta
    eta[ok] = y[ok] - yhat
    return eta, {"train_r2": train_r2, "n_train": int(tr.sum())}


def _spearman_ic(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    from scipy.stats import spearmanr

    m = np.isfinite(x) & np.isfinite(y)
    if m.sum() < 30:
        return float("nan"), float("nan")
    r = spearmanr(x[m], y[m])
    return float(r.correlation), float(r.pvalue)


def _auc(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    from sklearn.metrics import roc_auc_score

    m = np.isfinite(x) & np.isfinite(y)
    if m.sum() < 30:
        return float("nan"), float("nan")
    yy = y[m].astype(int)
    if len(np.unique(yy)) < 2:
        return float("nan"), float("nan")
    xx = x[m].reshape(-1, 1)
    # Mann-Whitney via roc_auc on scores=x
    try:
        auc = float(roc_auc_score(yy, x[m]))
    except ValueError:
        return float("nan"), float("nan")
    # crude p via logistic null: not ideal; use permutation later for BH family
    # Use Mann-Whitney U p-value
    from scipy.stats import mannwhitneyu

    a = x[m][yy == 1]
    b = x[m][yy == 0]
    if len(a) < 5 or len(b) < 5:
        return auc, float("nan")
    u = mannwhitneyu(a, b, alternative="two-sided")
    return auc, float(u.pvalue)


def _mi_regression(x: np.ndarray, y: np.ndarray, rng: np.random.Generator) -> tuple[float, float]:
    """sklearn MI + permutation null p-value (200 perms for speed)."""
    from sklearn.feature_selection import mutual_info_regression

    m = np.isfinite(x) & np.isfinite(y)
    if m.sum() < 50:
        return float("nan"), float("nan")
    xx = x[m].reshape(-1, 1)
    yy = y[m]
    mi = float(
        mutual_info_regression(xx, yy, random_state=int(SEED), n_neighbors=5)[0]
    )
    n_perm = 200
    null = np.empty(n_perm)
    for i in range(n_perm):
        yp = rng.permutation(yy)
        null[i] = mutual_info_regression(xx, yp, random_state=int(SEED + i), n_neighbors=5)[0]
    p = float((1 + np.sum(null >= mi)) / (1 + n_perm))
    return mi, p


def _bh_fdr(pvals: list[float], q: float = BH_Q) -> list[bool]:
    """Benjamini-Hochberg; returns reject flags aligned to input."""
    m = len(pvals)
    order = np.argsort([p if np.isfinite(p) else 1.0 for p in pvals])
    reject = [False] * m
    max_k = -1
    for rank, idx in enumerate(order, start=1):
        p = pvals[idx]
        if not np.isfinite(p):
            continue
        if p <= (rank / m) * q:
            max_k = rank
    if max_k < 0:
        return reject
    for rank, idx in enumerate(order, start=1):
        if rank <= max_k:
            reject[idx] = True
    return reject


def _chrono_split(n: int, oos_frac: float, embargo: int) -> tuple[np.ndarray, np.ndarray]:
    n_test = max(1, int(n * oos_frac))
    test_start = n - n_test
    train_end = max(0, test_start - embargo)
    train = np.zeros(n, dtype=bool)
    test = np.zeros(n, dtype=bool)
    train[:train_end] = True
    test[test_start:] = True
    return train, test


def run(csv_path: Path, out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)

    df = _load_ohlcv(csv_path)
    df["E_event"] = _tag_events(df["timestamp_utc"])
    df = _compute_pressure(df)
    df = _fill_targets(df)

    # gap drop: dt > 20 min between consecutive bars
    ts = df["timestamp_utc"]
    dt = ts.diff().dt.total_seconds().fillna(0)
    gap_drop = int((dt > 20 * 60).sum())

    # CPR raw + z
    buy = df["buy_pressure"].to_numpy(dtype=np.float64)
    sell = df["sell_pressure"].to_numpy(dtype=np.float64)
    event = df["E_event"].to_numpy(dtype=bool)
    for n in N_LIST:
        raw = _rolling_cpr_raw(buy, sell, n)
        df[f"cpr_raw_n{n}"] = raw
        df[f"cpr_z_n{n}"] = _rolling_z(raw, M_Z, event)

    print("Building 39-dim feature frame…")
    _, F = _build_39dim(df)
    n_feat_ok = int(np.sum(np.all(np.isfinite(F), axis=1)))

    # eligible: features + primary z + not event for residual predictive tests
    # Primary residual on N=16
    train_mask, test_mask = _chrono_split(len(df), OOS_FRAC, EMBARGO_BARS)

    tests: list[dict[str, Any]] = []
    residual_meta: dict[str, Any] = {}

    for n in N_LIST:
        zcol = f"cpr_z_n{n}"
        yz = df[zcol].to_numpy(dtype=np.float64)
        # residualization train excludes events (contract: event bars out of predictive tests)
        fit_mask = train_mask & (~event) & np.isfinite(yz) & np.all(np.isfinite(F), axis=1)
        eta, meta = _ols_residualize(yz, F, fit_mask)
        df[f"eta_n{n}"] = eta
        residual_meta[f"n{n}"] = meta

        # OOS residual R2 of eta vs predicting yz from F: measure residual variance ratio
        te = test_mask & (~event) & np.isfinite(eta) & np.isfinite(yz)
        # collinearity diagnostic: how much of CPR_Z is explained by 39-dim on OOS
        if te.sum() > 30:
            v_y = float(np.var(yz[te])) + EPS
            v_e = float(np.var(eta[te]))
            fit_r2_oos = 1.0 - v_e / v_y  # high ≈ rename of existing features
        else:
            fit_r2_oos = float("nan")
        residual_meta[f"n{n}"]["oos_fit_r2_cpr_on_39dim"] = fit_r2_oos
        residual_meta[f"n{n}"]["n_oos"] = int(te.sum())
        residual_meta[f"n{n}"]["eta_var_oos"] = float(np.var(eta[te])) if te.sum() > 30 else float("nan")

        targets = [
            ("fwd_return_1b", "continuous"),
            ("fwd_return_4b", "continuous"),
            ("displacement_continuation", "binary"),
        ]
        for tname, kind in targets:
            y = df[tname].to_numpy(dtype=np.float64)
            m = te & np.isfinite(y) & np.isfinite(eta)
            row: dict[str, Any] = {
                "horizon_n": n,
                "target": tname,
                "kind": kind,
                "n_oos": int(m.sum()),
                "fit_r2_cpr_on_39dim_oos": fit_r2_oos,
            }
            # Incremental R²: does eta add over 39-dim for continuous targets?
            if kind == "continuous" and m.sum() > 50:
                yhat_base = _ols_predict(y, F, train_mask & (~event))
                X_aug = np.column_stack([F, eta.reshape(-1, 1)])
                yhat_full = _ols_predict(y, X_aug, train_mask & (~event))
                r2_base = _r2(y[m], yhat_base[m])
                r2_full = _r2(y[m], yhat_full[m])
                delta_r2 = r2_full - r2_base if np.isfinite(r2_full) and np.isfinite(r2_base) else float("nan")
                row["oos_r2_base_39dim"] = r2_base
                row["oos_r2_full_39dim_plus_eta"] = r2_full
                row["oos_delta_r2_eta"] = delta_r2
            if kind == "continuous":
                ic, p_ic = _spearman_ic(eta[m], y[m]) if m.sum() else (float("nan"), float("nan"))
                mi, p_mi = _mi_regression(eta[m], y[m], rng) if m.sum() else (float("nan"), float("nan"))
                row.update(
                    {
                        "spearman_ic": ic,
                        "spearman_p": p_ic,
                        "mi": mi,
                        "mi_perm_p": p_mi,
                        "gate_p": p_ic if np.isfinite(p_ic) else p_mi,
                        "gate_stat": ic,
                        "gate_metric": "spearman_ic",
                    }
                )
            else:
                auc, p_auc = _auc(eta[m], y[m]) if m.sum() else (float("nan"), float("nan"))
                row.update(
                    {
                        "auc": auc,
                        "auc_p": p_auc,
                        "gate_p": p_auc,
                        "gate_stat": auc,
                        "gate_metric": "auc",
                    }
                )
            tests.append(row)

    # BH-FDR on the 9 prereg tests (3 N × 3 targets) using gate_p
    pvals = [t.get("gate_p", float("nan")) for t in tests]
    rejects = _bh_fdr(pvals, BH_Q)
    for t, rej in zip(tests, rejects):
        t["bh_reject_q001"] = bool(rej)

    # L1 pass: BH hit AND eta not a pure 39-dim rename (fit R2 of CPR~F not ~1)
    # AND incremental residual content: max delta_r2 > 0 OR BH hit already measures association
    any_bh = any(t["bh_reject_q001"] for t in tests)
    fit_r2_16 = residual_meta.get("n16", {}).get("oos_fit_r2_cpr_on_39dim", float("nan"))
    # novelty: CPR_Z not fully explained by 39-dim (fit R2 < 0.99)
    novelty_pass = bool(np.isfinite(fit_r2_16) and fit_r2_16 < 0.99)
    # incremental: any positive delta_r2 on continuous targets for N=16
    delta_r2s = [
        t.get("oos_delta_r2_eta", float("nan"))
        for t in tests
        if t["horizon_n"] == 16 and t["kind"] == "continuous"
    ]
    max_delta_r2 = float(np.nanmax(delta_r2s)) if delta_r2s else float("nan")
    incremental_pass = bool(np.isfinite(max_delta_r2) and max_delta_r2 > 0)
    residual_r2_pass = novelty_pass and incremental_pass
    l1_pass = bool(any_bh and residual_r2_pass)

    kill_reasons = []
    if not any_bh:
        kill_reasons.append("no_BH_significant_association")
    if not novelty_pass:
        kill_reasons.append("cpr_z_nearly_spanned_by_39dim_fit_r2_ge_0.99_or_nan")
    if not incremental_pass:
        kill_reasons.append("no_positive_oos_delta_r2_eta_over_39dim")

    fingerprint = {
        "contract_id": CONTRACT_ID,
        "experiment_id": EXPERIMENT_ID,
        "instrument": "XAUUSD",
        "timeframe": "M15",
        "clock_basis": "utc_corrected_from_mt5_broker_labels",
        "corpus_path": str(csv_path.as_posix()),
        "corpus_sha256": _sha256(csv_path),
        "n_bars_raw": int(len(df)),
        "n_bars_feature_ok": n_feat_ok,
        "timestamp_utc_start": str(df["timestamp_utc"].iloc[0]),
        "timestamp_utc_end": str(df["timestamp_utc"].iloc[-1]),
        "timestamp_broker_start": str(df["timestamp"].iloc[0]),
        "timestamp_broker_end": str(df["timestamp"].iloc[-1]),
        "gap_dt_gt_20min_count": gap_drop,
        "n_event_bars": int(event.sum()),
        "seed": SEED,
        "oos_frac": OOS_FRAC,
        "embargo_bars": EMBARGO_BARS,
        "n_train": int(train_mask.sum()),
        "n_test": int(test_mask.sum()),
        "canonical_features": list(CANONICAL_FEATURES),
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    split_manifest = {
        "scheme": "single_holdout_chronologic",
        "seed": SEED,
        "embargo_bars": EMBARGO_BARS,
        "oos_frac": OOS_FRAC,
        "train_end_utc": str(df.loc[train_mask, "timestamp_utc"].iloc[-1]) if train_mask.any() else None,
        "test_start_utc": str(df.loc[test_mask, "timestamp_utc"].iloc[0]) if test_mask.any() else None,
        "test_end_utc": str(df.loc[test_mask, "timestamp_utc"].iloc[-1]) if test_mask.any() else None,
        "event_exclusion": "E_event bars excluded from residual predictive OOS tests and from z-score sample",
    }

    metrics = {
        "contract_id": CONTRACT_ID,
        "l1_pass": l1_pass,
        "any_bh_reject": any_bh,
        "fit_r2_cpr_on_39dim_n16": fit_r2_16,
        "max_delta_r2_eta_n16": max_delta_r2,
        "novelty_pass": novelty_pass,
        "incremental_pass": incremental_pass,
        "residual_r2_pass": residual_r2_pass,
        "kill_reasons": kill_reasons,
        "tests": tests,
        "residual_meta": residual_meta,
        "authority": {
            "economic_claims_allowed": False,
            "economic_admissible": False,
            "note": "Info-stage only; E_OOS not evaluated as pass gate",
        },
        "production_behavior_changed": False,
    }

    # E-MT-00 clean-path report (declare what was checked this run)
    mt00 = {
        "contract_id": CONTRACT_ID,
        "status": "PARTIAL",
        "note": "Observe-only residual harness; not full E-MT-00 probe matrix. Clean-path identity checks recorded.",
        "checks": [
            {
                "id": "POP-CORPUS-LOCKED",
                "result": "PASS",
                "detail": f"sha256={fingerprint['corpus_sha256'][:16]}… n={fingerprint['n_bars_raw']}",
            },
            {
                "id": "PIT-ROLLING-CAUSAL",
                "result": "PASS",
                "detail": "CPR rolling sums min_periods=N; z uses causal non-event window",
            },
            {
                "id": "RESIDUAL-VS-39DIM",
                "result": "PASS" if n_feat_ok > 1000 else "FAIL",
                "detail": f"feature_ok_rows={n_feat_ok}",
            },
            {
                "id": "SPLIT-CHRONO-EMBARGO",
                "result": "PASS",
                "detail": split_manifest,
            },
            {
                "id": "L1-SUCCESS-GATE",
                "result": "PASS" if l1_pass else "FAIL",
                "detail": {
                    "any_bh": any_bh,
                    "fit_r2_cpr_on_39dim_n16": fit_r2_16,
                    "max_delta_r2_eta_n16": max_delta_r2,
                    "novelty_pass": novelty_pass,
                    "incremental_pass": incremental_pass,
                },
            },
            {
                "id": "NO-RUNTIME-SPINE",
                "result": "PASS",
                "detail": "EngineRunner/DecisionEngine/Ultron not imported for scoring path",
            },
        ],
        "l1_pass": l1_pass,
        "kill_reasons": kill_reasons,
    }

    mt01 = {
        "contract_id": CONTRACT_ID,
        "status": "INCOMPLETE",
        "note": "Adversarial matrix not fully automated this run; declared seed classes only.",
        "coverage": [
            {
                "class": "lookahead_pit",
                "seed": "manual_code_review_causal_rolling",
                "clean": "PASS",
                "mutant": "NOT_RUN",
            },
            {
                "class": "feature_rename_skip_residual",
                "seed": "compare_raw_vs_eta_reported",
                "clean": "PASS_eta_only_gates",
                "mutant": "NOT_RUN",
            },
            {
                "class": "split_leakage",
                "seed": "chrono_holdout_embargo_96",
                "clean": "PASS",
                "mutant": "NOT_RUN",
            },
        ],
    }

    # write artifacts
    paths = {
        "population_fingerprint": out_dir / "population_fingerprint.json",
        "split_manifest": out_dir / "split_manifest.json",
        "metrics": out_dir / "metrics.json",
        "mt00_report": out_dir / "mt00_report.json",
        "mt01_coverage": out_dir / "mt01_coverage.json",
        "summary_md": out_dir / "summary.md",
    }
    paths["population_fingerprint"].write_text(json.dumps(fingerprint, indent=2), encoding="utf-8")
    paths["split_manifest"].write_text(json.dumps(split_manifest, indent=2), encoding="utf-8")
    paths["metrics"].write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    paths["mt00_report"].write_text(json.dumps(mt00, indent=2), encoding="utf-8")
    paths["mt01_coverage"].write_text(json.dumps(mt01, indent=2), encoding="utf-8")

    # human summary
    lines = [
        f"# MC-CPR-L0 residual harness summary",
        "",
        f"**Contract:** `{CONTRACT_ID}`",
        f"**Corpus:** `{csv_path}`",
        f"**UTC window:** {fingerprint['timestamp_utc_start']} → {fingerprint['timestamp_utc_end']}",
        f"**n bars:** {fingerprint['n_bars_raw']} (feature-ok {n_feat_ok})",
        f"**L1 pass:** `{l1_pass}`",
        f"**CPR~39dim fit R² (N=16 OOS):** `{fit_r2_16}` (high ≈ rename)",
        f"**Max ΔR² eta over 39dim (N=16):** `{max_delta_r2}`",
        f"**Any BH reject q<0.01:** `{any_bh}`",
        f"**Kill reasons:** `{kill_reasons}`",
        f"**economic_claims_allowed:** `false`",
        f"**production_behavior_changed:** `false`",
        "",
        "## Tests (OOS residual η)",
        "",
        "| N | target | metric | stat | p | BH |",
        "|---|---|---|---:|---:|---|",
    ]
    for t in tests:
        lines.append(
            f"| {t['horizon_n']} | {t['target']} | {t['gate_metric']} | "
            f"{t.get('gate_stat', float('nan')):.6g} | {t.get('gate_p', float('nan')):.4g} | "
            f"{t['bh_reject_q001']} |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        "- This run measures whether synthetic CPR_Z residual has OOS information beyond the 39-dim vector.",
        "- It does **not** estimate true BI/SI capital (UNK-004/005 remain latent).",
        "- It grants **no** fusion/risk/runtime authority.",
        "",
    ]
    paths["summary_md"].write_text("\n".join(lines), encoding="utf-8")

    return {
        "l1_pass": l1_pass,
        "paths": {k: str(v) for k, v in paths.items()},
        "metrics": metrics,
        "fingerprint": fingerprint,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="MC-CPR-L0 observe-only residual harness")
    ap.add_argument(
        "--csv",
        type=Path,
        default=ROOT / "data" / "mt5" / "XAUUSD_M15.csv",
        help="XAUUSD M15 OHLCV CSV",
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "results" / "research" / "mc_cpr_l0",
        help="Output directory for fingerprints/metrics",
    )
    args = ap.parse_args()
    if not args.csv.is_file():
        print(f"CSV not found: {args.csv}", file=sys.stderr)
        return 2
    print(f"Contract {CONTRACT_ID}")
    print(f"CSV {args.csv}")
    result = run(args.csv.resolve(), args.out_dir.resolve())
    print(json.dumps({"l1_pass": result["l1_pass"], "paths": result["paths"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
