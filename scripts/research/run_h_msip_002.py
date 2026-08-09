#!/usr/bin/env python3
"""H-018 / H-MSIP-002 — match attrition & estimand robustness (EXPLORATORY_RESEARCH).

MANDATORY order:
  1) composition diagnostics matched vs unmatched (freeze + hash)
  2) only then E0 / E1 / E2 outcomes
  3) evidence → critique → findings → decision ledger → STOP

Fixed target: P-BOS=+1, R_h@h=8. No new partitions/horizons.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT / "scripts" / "research"))

import run_h_msip_001 as h017  # noqa: E402

# ── frozen H-018 constants ──────────────────────────────────────────────
PROGRAM_ALIAS = "H-MSIP-002"
REGISTRY_ID = "H-018"
ALPHA = 0.05
PRIMARY_H = 8
BOS_LEVEL = 1
N_PERM = 2000
PERM_SEED = 20260714
MIN_N = 80
MIN_STRATUM = 20
COMMON_SUPPORT_ALPHA = 0.05
MIN_TREATMENT_RETAINED = 0.50
SMD_FLAG = 0.25
PBOS_GAP_PP = 10.0
HELD_OUT_FOLD = 3

# H-017 reference (from frozen evidence)
H017_DELTA = -7.261302150346537e-05
H017_N = 2311
# E0 reproduction tolerance (frozen at run authorization — documented in evidence)
E0_ABS_TOL = max(1e-5, 0.25 * abs(H017_DELTA))
E0_N_TOL = 0.05  # relative n

PREREG_JSON = _ROOT / "docs/research-readiness/h-msip-002-experiment-definition.json"
PREREG_MD = _ROOT / "docs/research-readiness/h-msip-002-match-attrition-preregistration.md"
OUT_DIR = _ROOT / "results" / "research" / "h_msip_002"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return h017._sha256_file(path)


def _git_meta() -> dict[str, Any]:
    return h017._git_meta(_ROOT)


def _bos(b: h017.BarRec) -> int | None:
    try:
        v = b.dims.get("structure_state", {}).get("break_of_structure")
        if v is None:
            return None
        return int(v)
    except Exception:
        return None


def _covars(b: h017.BarRec) -> tuple[int, int, int] | None:
    """session, vol_regime, trend_bias from block (same matching covariates)."""
    if b.block is None:
        return None
    return (int(b.block[0]), int(b.block[1]), int(b.block[2]))


def _episode_stats(bars: list[h017.BarRec]) -> dict[int, dict[str, int]]:
    """episode_id -> {duration, start_idx, end_idx}."""
    by_ep: dict[int, list[int]] = defaultdict(list)
    for b in bars:
        if b.candidate_episode_id is not None:
            by_ep[int(b.candidate_episode_id)].append(b.bar_index)
    out = {}
    for ep, idxs in by_ep.items():
        idxs = sorted(idxs)
        out[ep] = {
            "duration": idxs[-1] - idxs[0] + 1 if idxs else 0,
            "start": idxs[0] if idxs else -1,
            "end": idxs[-1] if idxs else -1,
            "n_bars": len(idxs),
        }
    return out


def _prop(counter: Counter, total: int) -> dict[str, float]:
    if total <= 0:
        return {}
    return {str(k): float(v) / total for k, v in sorted(counter.items(), key=lambda x: str(x[0]))}


def _smd_binary_or_cat(p1: float, p0: float) -> float:
    """SMD for proportions."""
    p = 0.5 * (p1 + p0)
    denom = math.sqrt(max(p * (1 - p), 1e-12))
    return (p1 - p0) / denom


def build_composition(
    bars: list[h017.BarRec],
    match_info: dict,
) -> dict[str, Any]:
    matches = match_info["matches"]
    treatment = [b for b in bars if b.occupancy_active]
    matched_t = [b for b in treatment if b.bar_index in matches]
    unmatched_t = [b for b in treatment if b.bar_index not in matches]
    ep_stats = _episode_stats(bars)

    def profile(group: list[h017.BarRec], label: str) -> dict[str, Any]:
        n = len(group)
        months = Counter(b.ts.strftime("%Y-%m") for b in group)
        folds = Counter(int(b.fold) for b in group)
        states = Counter(b.crt_state for b in group)
        sessions = Counter(_covars(b)[0] if _covars(b) else "NA" for b in group)
        vols = Counter(_covars(b)[1] if _covars(b) else "NA" for b in group)
        trends = Counter(_covars(b)[2] if _covars(b) else "NA" for b in group)
        bos_c = Counter(_bos(b) for b in group)
        ages = []
        durs = []
        for b in group:
            ep = b.candidate_episode_id
            if ep is None or ep not in ep_stats:
                continue
            st = ep_stats[ep]
            ages.append(b.bar_index - st["start"])
            durs.append(st["duration"])
        ages_a = np.asarray(ages, dtype=float) if ages else np.array([])
        durs_a = np.asarray(durs, dtype=float) if durs else np.array([])
        p_bos_plus1 = float(bos_c.get(BOS_LEVEL, 0) / n) if n else 0.0
        return {
            "label": label,
            "n": n,
            "calendar_month": dict(months),
            "calendar_fold": {str(k): v for k, v in folds.items()},
            "crt_lifecycle_state": dict(states),
            "session": {str(k): v for k, v in sessions.items()},
            "volatility_regime": {str(k): v for k, v in vols.items()},
            "trend_bias": {str(k): v for k, v in trends.items()},
            "P_BOS_counts": {str(k): v for k, v in bos_c.items()},
            "P_BOS_plus1_share": p_bos_plus1,
            "episode_age_at_bar": {
                "mean": float(ages_a.mean()) if len(ages_a) else None,
                "median": float(np.median(ages_a)) if len(ages_a) else None,
                "p90": float(np.percentile(ages_a, 90)) if len(ages_a) else None,
            },
            "episode_duration": {
                "mean": float(durs_a.mean()) if len(durs_a) else None,
                "median": float(np.median(durs_a)) if len(durs_a) else None,
                "p90": float(np.percentile(durs_a, 90)) if len(durs_a) else None,
            },
        }

    pm = profile(matched_t, "matched_treatment")
    pu = profile(unmatched_t, "unmatched_treatment")

    # SMDs on matching covariates (categorical as one-vs-rest for each level)
    smds = {}
    flags = []
    for name, extractor in (
        ("session", lambda b: _covars(b)[0] if _covars(b) else None),
        ("volatility_regime", lambda b: _covars(b)[1] if _covars(b) else None),
        ("trend_bias", lambda b: _covars(b)[2] if _covars(b) else None),
    ):
        levels = set()
        for b in matched_t + unmatched_t:
            v = extractor(b)
            if v is not None:
                levels.add(v)
        for lev in sorted(levels, key=str):
            p1 = sum(1 for b in matched_t if extractor(b) == lev) / max(len(matched_t), 1)
            p0 = sum(1 for b in unmatched_t if extractor(b) == lev) / max(len(unmatched_t), 1)
            smd = _smd_binary_or_cat(p1, p0)
            key = f"{name}={lev}"
            smds[key] = {"p_matched": p1, "p_unmatched": p0, "smd": smd}
            if abs(smd) > SMD_FLAG:
                flags.append({"field": key, "smd": smd, "flag": "SMD_GT_0.25"})

    gap_pp = abs(pm["P_BOS_plus1_share"] - pu["P_BOS_plus1_share"]) * 100.0
    if gap_pp > PBOS_GAP_PP:
        flags.append(
            {
                "field": "P_BOS_plus1_share",
                "gap_pp": gap_pp,
                "flag": "PBOS_PLUS1_PREVALENCE_GAP_GT_10PP",
            }
        )

    selective = len(flags) > 0
    statement = (
        "H-017 matched population appears compositionally SELECTIVE relative to unmatched "
        "treatment on one or more pre-registered imbalance flags."
        if selective
        else "H-017 matched population does not exceed pre-registered imbalance flags vs unmatched "
        "treatment on matching covariates / P-BOS=+1 prevalence (other differences may still exist)."
    )

    return {
        "schema_id": "H_018_COMPOSITION_DIAGNOSTICS_V1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol": "frozen_before_E1_E2_outcomes",
        "counts": {
            "treatment_total": len(treatment),
            "matched_treatment": len(matched_t),
            "unmatched_treatment": len(unmatched_t),
            "attrition_rate": len(unmatched_t) / max(len(treatment), 1),
        },
        "matched_treatment": pm,
        "unmatched_treatment": pu,
        "standardized_differences": smds,
        "imbalance_flags": flags,
        "compositionally_selective": selective,
        "explicit_statement": statement,
        "smd_flag_threshold": SMD_FLAG,
        "p_bos_gap_pp_threshold": PBOS_GAP_PP,
    }


def _is_target(b: h017.BarRec) -> bool:
    return b.occupancy_active and _bos(b) == BOS_LEVEL and b.r8 is not None


def estimand_e0(
    bars: list[h017.BarRec], match_info: dict
) -> dict[str, Any]:
    matches = match_info["matches"]
    by_idx = {b.bar_index: b for b in bars}
    t_y, c_y, folds = [], [], []
    for b in bars:
        if not _is_target(b):
            continue
        if b.bar_index not in matches:
            continue
        ctrl = by_idx.get(matches[b.bar_index])
        if ctrl is None or ctrl.r8 is None:
            continue
        t_y.append(b.r8)
        c_y.append(ctrl.r8)
        folds.append(b.fold)
    t_y_a = np.asarray(t_y, dtype=float)
    c_y_a = np.asarray(c_y, dtype=float)
    n = len(t_y_a)
    if n < MIN_N:
        return {
            "id": "E0",
            "support": "INSUFFICIENT",
            "n_treatment": n,
            "delta": None,
        }
    delta = float(t_y_a.mean() - c_y_a.mean())
    se = float(math.sqrt(t_y_a.var(ddof=1) / n + c_y_a.var(ddof=1) / n))
    # held-out fold
    mask_h = np.array([f == HELD_OUT_FOLD for f in folds], dtype=bool)
    if mask_h.sum() >= 5 and (~mask_h).sum() >= 5:
        d_hold = float(t_y_a[mask_h].mean() - c_y_a[mask_h].mean())
    else:
        d_hold = None
    # fold estimates
    fold_d = []
    for f in range(4):
        m = np.array([ff == f for ff in folds], dtype=bool)
        if m.sum() >= 5:
            fold_d.append(float(t_y_a[m].mean() - c_y_a[m].mean()))
        else:
            fold_d.append(None)

    # permutation within blocks among matched targets vs other matched occupancy
    # simpler: shuffle labels of matched occupancy for BOS==1 association vs matched control residual
    # Protocol: same seed; for E0 use permutation of treatment R8 vs control pairing integrity
    # Use sign of delta stability: permute which treatment rows get their control outcome
    rng = np.random.default_rng(PERM_SEED)
    diffs = t_y_a - c_y_a
    real = float(diffs.mean())
    nulls = np.empty(N_PERM)
    for i in range(N_PERM):
        # flip random half signs as null of no systematic difference? Better: shuffle t_y vs c_y pairing
        nulls[i] = float((t_y_a - rng.permutation(c_y_a)).mean())
    p_perm = float((np.abs(nulls) >= abs(real)).mean())

    same_sign = (delta < 0 and H017_DELTA < 0) or (delta > 0 and H017_DELTA > 0)
    abs_ok = abs(delta - H017_DELTA) <= E0_ABS_TOL
    n_ok = abs(n - H017_N) / H017_N <= E0_N_TOL
    reproduces = bool(same_sign and abs_ok and n_ok)

    return {
        "id": "E0",
        "name": "h017_matched_subpopulation_replication",
        "support": "OK",
        "n_treatment": n,
        "n_control": n,
        "delta": delta,
        "se": se,
        "mean_r8_treatment": float(t_y_a.mean()),
        "mean_r8_control": float(c_y_a.mean()),
        "direction": "negative" if delta < 0 else ("positive" if delta > 0 else "zero"),
        "held_out_delta": d_hold,
        "held_out_direction": (
            "negative" if d_hold is not None and d_hold < 0 else (
                "positive" if d_hold is not None and d_hold > 0 else None
            )
        ),
        "held_out_direction_matches": (
            d_hold is not None and ((d_hold < 0 and delta < 0) or (d_hold > 0 and delta > 0))
        ),
        "fold_deltas": fold_d,
        "p_perm": p_perm,
        "h017_reference_delta": H017_DELTA,
        "h017_reference_n": H017_N,
        "reproduction_tolerance": {
            "abs_tol": E0_ABS_TOL,
            "n_rel_tol": E0_N_TOL,
            "same_sign": same_sign,
            "abs_ok": abs_ok,
            "n_ok": n_ok,
        },
        "reproduces_h017": reproduces,
    }


def _design_matrix(covars: list[tuple[int, int, int]]) -> np.ndarray:
    """One-hot for session, vol, trend (levels observed)."""
    sessions = sorted({c[0] for c in covars})
    vols = sorted({c[1] for c in covars})
    trends = sorted({c[2] for c in covars})
    rows = []
    for s, v, t in covars:
        row = []
        for ss in sessions[:-1]:
            row.append(1.0 if s == ss else 0.0)
        for vv in vols[:-1]:
            row.append(1.0 if v == vv else 0.0)
        for tt in trends[:-1]:
            row.append(1.0 if t == tt else 0.0)
        row.append(1.0)  # intercept
        rows.append(row)
    return np.asarray(rows, dtype=float), sessions, vols, trends


def _logistic_irls(X: np.ndarray, y: np.ndarray, max_iter: int = 50) -> np.ndarray:
    """Simple logistic regression via IRLS; returns coefficients."""
    n, p = X.shape
    beta = np.zeros(p)
    for _ in range(max_iter):
        eta = X @ beta
        eta = np.clip(eta, -20, 20)
        mu = 1.0 / (1.0 + np.exp(-eta))
        w = mu * (1 - mu)
        w = np.clip(w, 1e-6, None)
        z = eta + (y - mu) / w
        # weighted least squares
        WX = X * w[:, None]
        try:
            beta_new = np.linalg.solve(X.T @ WX, X.T @ (w * z))
        except np.linalg.LinAlgError:
            beta_new = np.linalg.lstsq(X.T @ WX, X.T @ (w * z), rcond=None)[0]
        if np.max(np.abs(beta_new - beta)) < 1e-8:
            beta = beta_new
            break
        beta = beta_new
    return beta


def estimand_e1(bars: list[h017.BarRec]) -> dict[str, Any]:
    """Overlap-weighted: all occupancy P-BOS=+1 vs RANGE, covariates session/vol/trend only."""
    treat = [b for b in bars if _is_target(b) and _covars(b) is not None]
    control = [
        b
        for b in bars
        if b.crt_state == "RANGE" and b.r8 is not None and _covars(b) is not None
    ]
    n_t0, n_c0 = len(treat), len(control)
    if n_t0 < MIN_N or n_c0 < MIN_N:
        return {
            "id": "E1",
            "support": "INSUFFICIENT",
            "n_treatment_raw": n_t0,
            "n_control_raw": n_c0,
            "severe_overlap_violation": True,
        }

    y_t = np.array([b.r8 for b in treat], dtype=float)
    y_c = np.array([b.r8 for b in control], dtype=float)
    cov_t = [_covars(b) for b in treat]
    cov_c = [_covars(b) for b in control]
    folds_t = np.array([b.fold for b in treat], dtype=int)

    # Fit propensity on pooled sample: T=1 treatment, T=0 RANGE
    all_cov = cov_t + cov_c
    X, _, _, _ = _design_matrix(all_cov)  # type: ignore
    y_bin = np.concatenate([np.ones(n_t0), np.zeros(n_c0)])
    beta = _logistic_irls(X, y_bin)
    eta = np.clip(X @ beta, -20, 20)
    ps = 1.0 / (1.0 + np.exp(-eta))
    ps_t = ps[:n_t0]
    ps_c = ps[n_t0:]

    a = COMMON_SUPPORT_ALPHA
    # common support on pooled
    in_cs_t = (ps_t >= a) & (ps_t <= 1 - a)
    in_cs_c = (ps_c >= a) & (ps_c <= 1 - a)
    retained_frac = float(in_cs_t.mean())
    severe_overlap = retained_frac < MIN_TREATMENT_RETAINED

    # stabilized IPTW: w_t = p_bar / ps, w_c = (1-p_bar)/(1-ps)
    p_bar = float(y_bin.mean())
    w_t = np.where(in_cs_t, p_bar / np.clip(ps_t, 1e-6, 1 - 1e-6), 0.0)
    w_c = np.where(in_cs_c, (1 - p_bar) / np.clip(1 - ps_c, 1e-6, 1 - 1e-6), 0.0)
    # no extra clipping beyond common-support zeroing (protocol: no unspec clipping)

    def wmean(y, w):
        sw = w.sum()
        if sw <= 0:
            return float("nan")
        return float((y * w).sum() / sw)

    def ess(w):
        s = w.sum()
        if s <= 0:
            return 0.0
        return float((s * s) / (w * w).sum())

    delta = wmean(y_t, w_t) - wmean(y_c, w_c)
    ess_t, ess_c = ess(w_t), ess(w_c)
    support_ok = ess_t >= MIN_N and ess_c >= MIN_N and not severe_overlap

    # held-out: recompute weights frozen; restrict treatment fold==3
    mask_h = folds_t == HELD_OUT_FOLD
    if mask_h.sum() >= 10 and (~mask_h).sum() >= 10:
        # use same ps; subset
        d_hold = wmean(y_t[mask_h], w_t[mask_h]) - wmean(y_c, w_c)
    else:
        d_hold = None

    # balance before/after: SMD of session levels among T vs C with weights
    def balance(weights_t, weights_c):
        out = {}
        for j, name in enumerate(("session", "vol", "trend")):
            levels = sorted({c[j] for c in all_cov})
            for lev in levels:
                ind_t = np.array([c[j] == lev for c in cov_t], dtype=float)
                ind_c = np.array([c[j] == lev for c in cov_c], dtype=float)
                p1 = wmean(ind_t, weights_t) if weights_t.sum() > 0 else float(ind_t.mean())
                p0 = wmean(ind_c, weights_c) if weights_c.sum() > 0 else float(ind_c.mean())
                out[f"{name}={lev}"] = {
                    "p_t": p1,
                    "p_c": p0,
                    "smd": _smd_binary_or_cat(p1, p0),
                }
        return out

    w_t_unit = np.ones(n_t0)
    w_c_unit = np.ones(n_c0)
    bal_before = balance(w_t_unit, w_c_unit)
    bal_after = balance(w_t, w_c)

    # permutation: shuffle treatment outcomes under fixed weights
    rng = np.random.default_rng(PERM_SEED)
    real = delta
    nulls = np.empty(N_PERM)
    for i in range(N_PERM):
        yt_p = rng.permutation(y_t)
        nulls[i] = wmean(yt_p, w_t) - wmean(y_c, w_c)
    p_perm = float((np.abs(nulls) >= abs(real)).mean()) if not math.isnan(real) else 1.0

    return {
        "id": "E1",
        "name": "overlap_weighted_broader_treatment",
        "estimand_definition": (
            "E[R8|occupancy,P-BOS=+1] - E[R8|RANGE] with stabilized IPTW on "
            "session×vol×trend; common support ps in [α,1-α], α=0.05; no extra weight clip"
        ),
        "common_support_alpha": COMMON_SUPPORT_ALPHA,
        "covariates_only": ["session", "volatility_regime", "trend_bias"],
        "n_treatment_raw": n_t0,
        "n_control_raw": n_c0,
        "n_treatment_cs": int(in_cs_t.sum()),
        "n_control_cs": int(in_cs_c.sum()),
        "treatment_retained_fraction": retained_frac,
        "severe_overlap_violation": severe_overlap,
        "propensity": {
            "mean_t": float(ps_t.mean()),
            "mean_c": float(ps_c.mean()),
            "min_t": float(ps_t.min()),
            "max_t": float(ps_t.max()),
        },
        "weights": {
            "mean_t": float(w_t[w_t > 0].mean()) if (w_t > 0).any() else None,
            "max_t": float(w_t.max()),
            "max_c": float(w_c.max()),
            "ess_treatment": ess_t,
            "ess_control": ess_c,
        },
        "balance_before_weighting": bal_before,
        "balance_after_weighting": bal_after,
        "delta": float(delta) if not math.isnan(delta) else None,
        "direction": (
            "negative" if isinstance(delta, float) and delta < 0 else (
                "positive" if isinstance(delta, float) and delta > 0 else None
            )
        ),
        "held_out_delta": d_hold,
        "held_out_direction": (
            "negative" if d_hold is not None and d_hold < 0 else (
                "positive" if d_hold is not None and d_hold > 0 else None
            )
        ),
        "held_out_direction_matches": (
            d_hold is not None
            and not math.isnan(delta)
            and ((d_hold < 0 and delta < 0) or (d_hold > 0 and delta > 0))
        ),
        "p_perm": p_perm,
        "support": "OK" if support_ok else "INSUFFICIENT",
    }


def estimand_e2(bars: list[h017.BarRec]) -> dict[str, Any]:
    """Time-blocked stratified: within session×vol×trend×calendar_fold."""
    treat = [b for b in bars if _is_target(b) and _covars(b) is not None]
    control = [
        b
        for b in bars
        if b.crt_state == "RANGE" and b.r8 is not None and _covars(b) is not None
    ]

    # group by (session, vol, trend, fold)
    t_groups: dict[tuple, list[float]] = defaultdict(list)
    c_groups: dict[tuple, list[float]] = defaultdict(list)
    for b in treat:
        cv = _covars(b)
        assert cv is not None
        key = (cv[0], cv[1], cv[2], int(b.fold))
        t_groups[key].append(b.r8)  # type: ignore
    for b in control:
        cv = _covars(b)
        assert cv is not None
        key = (cv[0], cv[1], cv[2], int(b.fold))
        c_groups[key].append(b.r8)  # type: ignore

    strata = []
    unsupported = []
    for key in sorted(set(t_groups) | set(c_groups)):
        yt = t_groups.get(key, [])
        yc = c_groups.get(key, [])
        n_t, n_c = len(yt), len(yc)
        if n_t < MIN_STRATUM or n_c < MIN_STRATUM:
            unsupported.append(
                {
                    "stratum": {
                        "session": key[0],
                        "vol": key[1],
                        "trend": key[2],
                        "fold": key[3],
                    },
                    "n_treatment": n_t,
                    "n_control": n_c,
                }
            )
            continue
        yt_a = np.asarray(yt, dtype=float)
        yc_a = np.asarray(yc, dtype=float)
        d = float(yt_a.mean() - yc_a.mean())
        var = yt_a.var(ddof=1) / n_t + yc_a.var(ddof=1) / n_c
        strata.append(
            {
                "stratum": {
                    "session": key[0],
                    "vol": key[1],
                    "trend": key[2],
                    "fold": key[3],
                },
                "n_treatment": n_t,
                "n_control": n_c,
                "delta": d,
                "var": float(var) if var > 0 else 1e-12,
            }
        )

    if not strata:
        return {
            "id": "E2",
            "support": "INSUFFICIENT",
            "n_supported_strata": 0,
            "unsupported_strata_count": len(unsupported),
            "unsupported_strata": unsupported[:50],
        }

    # sample-size weighted
    w_n = np.array([s["n_treatment"] + s["n_control"] for s in strata], dtype=float)
    d_a = np.array([s["delta"] for s in strata], dtype=float)
    delta_ss = float((d_a * w_n).sum() / w_n.sum())
    # inverse-variance
    w_iv = np.array([1.0 / s["var"] for s in strata], dtype=float)
    delta_iv = float((d_a * w_iv).sum() / w_iv.sum())
    # primary aggregate pre-registered both; decision uses sample-size weighted as primary
    # (document both); held-out = fold 3 strata only
    hold = [s for s in strata if s["stratum"]["fold"] == HELD_OUT_FOLD]
    if hold:
        wn = np.array([s["n_treatment"] + s["n_control"] for s in hold], dtype=float)
        da = np.array([s["delta"] for s in hold], dtype=float)
        d_hold = float((da * wn).sum() / wn.sum())
    else:
        d_hold = None

    fold_est = []
    for f in range(4):
        fs = [s for s in strata if s["stratum"]["fold"] == f]
        if not fs:
            fold_est.append(None)
            continue
        wn = np.array([s["n_treatment"] + s["n_control"] for s in fs], dtype=float)
        da = np.array([s["delta"] for s in fs], dtype=float)
        fold_est.append(float((da * wn).sum() / wn.sum()))

    # counts by fold
    fold_counts = {}
    for f in range(4):
        nt = sum(s["n_treatment"] for s in strata if s["stratum"]["fold"] == f)
        nc = sum(s["n_control"] for s in strata if s["stratum"]["fold"] == f)
        fold_counts[str(f)] = {"n_treatment": nt, "n_control": nc}

    n_t_tot = sum(s["n_treatment"] for s in strata)
    n_c_tot = sum(s["n_control"] for s in strata)
    support_ok = n_t_tot >= MIN_N and n_c_tot >= MIN_N and len(strata) >= 1

    # permutation: shuffle treatment outcomes globally then re-stratum? 
    # Approximate: permute signs of stratum deltas weighted
    rng = np.random.default_rng(PERM_SEED)
    real = delta_ss
    nulls = np.empty(N_PERM)
    for i in range(N_PERM):
        signs = rng.choice([-1.0, 1.0], size=len(d_a))
        nulls[i] = float((d_a * signs * w_n).sum() / w_n.sum())
    p_perm = float((np.abs(nulls) >= abs(real)).mean())

    return {
        "id": "E2",
        "name": "time_blocked_stratified",
        "time_block_definition": "fold 0..3 = four contiguous equal-count eligible-bar folds (H-017)",
        "stratum_definition": "session × volatility_regime × trend_bias × calendar_fold",
        "min_n_per_stratum_arm": MIN_STRATUM,
        "n_supported_strata": len(strata),
        "unsupported_strata_count": len(unsupported),
        "unsupported_strata_sample": unsupported[:30],
        "fold_counts": fold_counts,
        "aggregation": {
            "sample_size_weighted_delta": delta_ss,
            "inverse_variance_weighted_delta": delta_iv,
            "primary_for_decision": "sample_size_weighted_delta",
        },
        "delta": delta_ss,
        "direction": "negative" if delta_ss < 0 else ("positive" if delta_ss > 0 else "zero"),
        "fold_estimates": fold_est,
        "held_out_delta": d_hold,
        "held_out_direction": (
            "negative" if d_hold is not None and d_hold < 0 else (
                "positive" if d_hold is not None and d_hold > 0 else None
            )
        ),
        "held_out_direction_matches": (
            d_hold is not None and ((d_hold < 0 and delta_ss < 0) or (d_hold > 0 and delta_ss > 0))
        ),
        "n_treatment_supported": n_t_tot,
        "n_control_supported": n_c_tot,
        "p_perm": p_perm,
        "support": "OK" if support_ok else "INSUFFICIENT",
        "strata_table": strata,
    }


def classify(e0: dict, e1: dict, e2: dict, composition: dict) -> str:
    if not e0.get("reproduces_h017"):
        return "PROTOCOL_FAILURE"
    if e0.get("support") != "OK":
        return "PROTOCOL_FAILURE"

    # severe overlap on E1 cannot be erased by favorable result
    e1_severe = bool(e1.get("severe_overlap_violation"))
    e1_ok = e1.get("support") == "OK" and not e1_severe
    e2_ok = e2.get("support") == "OK"

    if not e1_ok and not e2_ok:
        return "INCONCLUSIVE"
    if e1.get("support") != "OK" and e1_severe:
        # E1 unusable; if E2 also insufficient → inconclusive; if E2 only...
        if not e2_ok:
            return "INCONCLUSIVE"

    def dir_neg(d: dict) -> bool:
        return d.get("direction") == "negative"

    def hold_ok(d: dict) -> bool:
        return bool(d.get("held_out_direction_matches"))

    e0_neg = dir_neg(e0) and hold_ok(e0)
    # E1: if severe overlap, does not count toward ROBUST
    e1_survives = e1_ok and dir_neg(e1) and hold_ok(e1)
    e2_survives = e2_ok and dir_neg(e2) and hold_ok(e2)

    if e0_neg and e1_survives and e2_survives and not e1_severe:
        return "ROBUST"

    # MATCHING_DEPENDENT: E0 preserves direction but broader estimands lose/reverse
    e1_fails = (not e1_ok) or (e1_ok and not dir_neg(e1)) or e1_severe
    e2_fails = (not e2_ok) or (e2_ok and not dir_neg(e2))
    if e0_neg and (e1_fails or e2_fails):
        # if both broader fail or reverse while E0 holds
        if (e1_fails and e2_fails) or (
            e1_ok and not dir_neg(e1)
        ) or (e2_ok and not dir_neg(e2)):
            return "MATCHING_DEPENDENT"

    if not e1_ok or not e2_ok:
        return "INCONCLUSIVE"

    return "INCONCLUSIVE"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("H-018: building panel (FeaturePipeline + CRT + MSV)...", flush=True)
    bars, meta, _ = h017.build_panel()
    print(f"Eligible={len(bars)} occupancy={meta['active_occupancy_bars']}", flush=True)
    match_info = h017.match_controls(bars)
    print(
        f"Match {match_info['n_matched']}/{match_info['n_treatment']} "
        f"unmatched={match_info['n_unmatched']}",
        flush=True,
    )

    # ── STEP 1: composition BEFORE outcomes ─────────────────────────────
    print("STEP1: composition diagnostics (matched vs unmatched)...", flush=True)
    composition = build_composition(bars, match_info)
    comp_path = OUT_DIR / "H_018_COMPOSITION_DIAGNOSTICS_V1.json"
    comp_bytes = json.dumps(composition, indent=2, sort_keys=True, default=str).encode("utf-8")
    comp_path.write_bytes(comp_bytes + b"\n")
    comp_hash = _sha256_bytes(comp_bytes)
    (OUT_DIR / "H_018_COMPOSITION_SHA256.txt").write_text(comp_hash + "\n", encoding="utf-8")
    print(f"Composition frozen sha256={comp_hash[:16]}...", flush=True)
    print(f"Selective={composition['compositionally_selective']}", flush=True)

    # ── STEP 2: estimands only after composition hash exists ────────────
    print("STEP2: E0 / E1 / E2...", flush=True)
    e0 = estimand_e0(bars, match_info)
    print(f"E0 delta={e0.get('delta')} reproduces={e0.get('reproduces_h017')}", flush=True)
    e1 = estimand_e1(bars)
    print(
        f"E1 delta={e1.get('delta')} support={e1.get('support')} "
        f"overlap_viol={e1.get('severe_overlap_violation')}",
        flush=True,
    )
    e2 = estimand_e2(bars)
    print(f"E2 delta={e2.get('delta')} support={e2.get('support')}", flush=True)

    verdict = classify(e0, e1, e2, composition)
    print(f"VERDICT={verdict}", flush=True)

    git = _git_meta()
    evidence = {
        "schema_id": "H_018_EXPERIMENT_EVIDENCE_V1",
        "program_alias": PROGRAM_ALIAS,
        "registry_id": REGISTRY_ID,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "task_class": "EXPLORATORY_RESEARCH",
        "authority": "RESEARCH_ONLY",
        "order_of_operations": [
            "composition_frozen",
            "composition_hashed",
            "E0",
            "E1",
            "E2",
            "classify",
        ],
        "composition_sha256": comp_hash,
        "composition_path": str(comp_path.relative_to(_ROOT)).replace("\\", "/"),
        "frozen_protocol": {
            "prereg_json_sha256": _sha256_file(PREREG_JSON),
            "prereg_md_sha256": _sha256_file(PREREG_MD),
            "fixed_target": "P-BOS=+1",
            "primary_outcome": "R_h@h=8",
            "alpha": ALPHA,
            "e0_reproduction_tolerance": {
                "abs_tol": E0_ABS_TOL,
                "n_rel_tol": E0_N_TOL,
                "h017_delta": H017_DELTA,
                "h017_n": H017_N,
            },
        },
        "hard_flags": {
            "CRT_BEHAVIOR_CHANGE": False,
            "MSIP_SHADOW_AUTHORITY_CHANGE": False,
            "THRESHOLD_RESEARCH": False,
            "MIGRATION_AUTHORIZED": False,
            "PRODUCTION_AUTHORITY": False,
            "FOLLOW_UP_EXECUTION_AUTHORIZED": False,
        },
        "repository": git,
        "population_meta": meta,
        "matching_summary": {k: v for k, v in match_info.items() if k != "matches"},
        "composition_summary": {
            "counts": composition["counts"],
            "compositionally_selective": composition["compositionally_selective"],
            "explicit_statement": composition["explicit_statement"],
            "imbalance_flags": composition["imbalance_flags"],
        },
        "E0": e0,
        "E1": e1,
        "E2": {k: v for k, v in e2.items() if k != "strata_table"},
        "E2_strata_path": "H_018_E2_STRATA.json",
        "verdict": verdict,
        "h017_scope_note": (
            "A null/MATCHING_DEPENDENT result does not retroactively invalidate H-017; "
            "it reclassifies H-017 estimand scope (matched subpopulation)."
        ),
    }
    # write E2 strata separately (large)
    (OUT_DIR / "H_018_E2_STRATA.json").write_text(
        json.dumps(e2.get("strata_table", []), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    ev_path = OUT_DIR / "H_018_EXPERIMENT_EVIDENCE_V1.json"
    ev_path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )

    # critique
    critique = f"""# H-018 / H-MSIP-002 Critique

**Verdict:** `{verdict}`  
**Authority:** RESEARCH_ONLY  
**Stop:** OWNER_REVIEW

## Order of operations

1. Composition diagnostics frozen and hashed **before** E1/E2 outcomes.  
2. Composition sha256: `{comp_hash}`  
3. E0 → E1 → E2 under frozen definitions.

## Composition (matched vs unmatched treatment)

| | Count |
|--|------:|
| Treatment total | {composition['counts']['treatment_total']} |
| Matched | {composition['counts']['matched_treatment']} |
| Unmatched | {composition['counts']['unmatched_treatment']} |
| Attrition | {composition['counts']['attrition_rate']:.1%} |

**Selective?** {composition['compositionally_selective']}

{composition['explicit_statement']}

Imbalance flags: {json.dumps(composition['imbalance_flags'], indent=2)}

## E0 — H-017 reference replication

| Field | Value |
|-------|------:|
| n | {e0.get('n_treatment')} |
| Δ | {e0.get('delta')} |
| H-017 Δ | {H017_DELTA} |
| reproduces_h017 | **{e0.get('reproduces_h017')}** |
| held-out Δ | {e0.get('held_out_delta')} |
| held-out matches | {e0.get('held_out_direction_matches')} |
| p_perm | {e0.get('p_perm')} |

## E1 — Overlap-weighted broader treatment

| Field | Value |
|-------|------:|
| support | {e1.get('support')} |
| retained frac | {e1.get('treatment_retained_fraction')} |
| severe_overlap_violation | **{e1.get('severe_overlap_violation')}** |
| ESS T/C | {e1.get('weights',{}).get('ess_treatment')} / {e1.get('weights',{}).get('ess_control')} |
| max weight T | {e1.get('weights',{}).get('max_t')} |
| Δ | {e1.get('delta')} |
| held-out Δ | {e1.get('held_out_delta')} |
| held-out matches | {e1.get('held_out_direction_matches')} |
| p_perm | {e1.get('p_perm')} |

## E2 — Time-blocked stratified

| Field | Value |
|-------|------:|
| support | {e2.get('support')} |
| supported strata | {e2.get('n_supported_strata')} |
| unsupported strata | {e2.get('unsupported_strata_count')} |
| Δ (SSW) | {e2.get('delta')} |
| Δ (IVW) | {e2.get('aggregation',{}).get('inverse_variance_weighted_delta')} |
| fold estimates | {e2.get('fold_estimates')} |
| held-out Δ | {e2.get('held_out_delta')} |
| held-out matches | {e2.get('held_out_direction_matches')} |
| p_perm | {e2.get('p_perm')} |

## Classification

- **ROBUST**: direction survives E0+E1+E2, held-out each, no severe overlap  
- **MATCHING_DEPENDENT**: E0 holds direction; broader estimands lose/reverse  
- **INCONCLUSIVE**: support/overlap insufficient  
- **PROTOCOL_FAILURE**: E0 fails reproduction or ordering/provenance break  

**This run: `{verdict}`**

## Non-claims

Does not invalidate H-017's matched-subpopulation finding if MATCHING_DEPENDENT.  
No trading, MSIP authority, CRT change, thresholds, migration, or production authority.

Generated: {evidence['generated_at_utc']}
"""
    (OUT_DIR / "H_018_CRITIQUE.md").write_text(critique, encoding="utf-8")

    findings = f"""# H-MSIP-002 / H-018 Run Findings (maintained)

**Date:** {evidence['generated_at_utc'][:10]}  
**Verdict:** `{verdict}`  
**Authority:** RESEARCH_ONLY  
**Execution:** COMPLETE — **OWNER REVIEW**

## Parent (H-017)

- Owner-accepted: RESEARCH_SUPPORTIVE_MICRO_EFFECT on **matched subpopulation**
- Thread: SUPPORTED_BUT_NOT_CLOSED until attrition robustness resolved

## Composition (frozen before outcomes)

- sha256: `{comp_hash}`
- Matched / unmatched: {composition['counts']['matched_treatment']} / {composition['counts']['unmatched_treatment']}
- Selective: **{composition['compositionally_selective']}**
- Statement: {composition['explicit_statement']}

## Estimands (P-BOS=+1, R_8)

| Estimand | Support | Δ | Direction | Held-out match | Notes |
|----------|---------|--:|-----------|:--------------:|-------|
| E0 match rep | {e0.get('support')} | {e0.get('delta')} | {e0.get('direction')} | {e0.get('held_out_direction_matches')} | reproduces_h017={e0.get('reproduces_h017')} |
| E1 overlap IPTW | {e1.get('support')} | {e1.get('delta')} | {e1.get('direction')} | {e1.get('held_out_direction_matches')} | overlap_viol={e1.get('severe_overlap_violation')} retained={e1.get('treatment_retained_fraction')} |
| E2 time-block | {e2.get('support')} | {e2.get('delta')} | {e2.get('direction')} | {e2.get('held_out_direction_matches')} | strata={e2.get('n_supported_strata')} |

## Verdict meaning

`{verdict}`

H-017 is **not** retroactively void if MATCHING_DEPENDENT — scope stays matched-subpopulation.

## Non-authority

CRT · MSIP trading · thresholds · migration · production: **NO**

## Artifacts

- `results/research/h_msip_002/H_018_COMPOSITION_DIAGNOSTICS_V1.json`
- `results/research/h_msip_002/H_018_EXPERIMENT_EVIDENCE_V1.json`
- `results/research/h_msip_002/H_018_CRITIQUE.md`
- `results/research/h_msip_002/H_018_DECISION_LEDGER_ENTRY.json`
"""
    findings_path = _ROOT / "docs/research-readiness/h-msip-002-run-findings.md"
    findings_path.write_text(findings, encoding="utf-8")

    ledger = {
        "schema_id": "RESEARCH_DECISION_LEDGER_ENTRY_V1",
        "id": "DLE-H018-001",
        "registry_id": REGISTRY_ID,
        "program_alias": PROGRAM_ALIAS,
        "timestamp_utc": evidence["generated_at_utc"],
        "task_class": "EXPLORATORY_RESEARCH",
        "authority": "RESEARCH_ONLY",
        "verdict": verdict,
        "parent_h017_scope": "MATCHED_SUBPOPULATION_UNDER_FROZEN_H017_PROTOCOL",
        "composition_sha256": comp_hash,
        "grants": {
            "crt_behavior_change": False,
            "msip_shadow_authority_change": False,
            "threshold_research": False,
            "migration": False,
            "production": False,
            "follow_up_execution": False,
        },
        "evidence_ref": str(ev_path.relative_to(_ROOT)).replace("\\", "/"),
        "critique_ref": "results/research/h_msip_002/H_018_CRITIQUE.md",
        "findings_ref": "docs/research-readiness/h-msip-002-run-findings.md",
        "stop_boundary": "OWNER_REVIEW",
    }
    (OUT_DIR / "H_018_DECISION_LEDGER_ENTRY.json").write_text(
        json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    ledger_path = _ROOT / "results/research/decision_ledger.jsonl"
    with ledger_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(ledger, sort_keys=True) + "\n")

    (OUT_DIR / "RUN_STATUS.json").write_text(
        json.dumps(
            {
                "H-018_STATUS": "COMPLETE_AWAITING_OWNER_REVIEW",
                "verdict": verdict,
                "STOP_BOUNDARY": "OWNER_REVIEW",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    # update experiment definition status
    try:
        ed = json.loads(PREREG_JSON.read_text(encoding="utf-8"))
        ed["status"] = "RUN_COMPLETE_AWAITING_OWNER_REVIEW"
        ed["execution_authorized"] = True
        ed["run_verdict"] = verdict
        ed["run_artifacts"] = "results/research/h_msip_002/"
        PREREG_JSON.write_text(json.dumps(ed, indent=2) + "\n", encoding="utf-8")
    except Exception as exc:
        print(f"WARN update prereg json: {exc}", flush=True)

    print(json.dumps({"out_dir": str(OUT_DIR), "verdict": verdict, "composition_sha256": comp_hash}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
