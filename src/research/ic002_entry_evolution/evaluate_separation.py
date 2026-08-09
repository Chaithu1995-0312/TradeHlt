"""IC-002 primary evaluation: path vs static baseline under time-ordered OOS."""
from __future__ import annotations

import json
import logging
import math
import random
from pathlib import Path
from typing import Any

import numpy as np

from research.ic002_entry_evolution.io_util import DEFAULT_OUT, load_batch, load_prereg
from research.ic002_entry_evolution.schema import (
    AUC_PATH_MIN,
    DELTA_AUC_MIN,
    LOGISTIC_C_IS_GRID,
    MIN_N_OOS,
    N_GRID,
    N_PERM,
    OOS_SPLIT,
    SEED,
    SHUFFLE_PATH_GAP_MIN,
    flatten_Z,
    static_baseline_vector,
)

logger = logging.getLogger("ic002.eval")


def _auc(y_true: np.ndarray, scores: np.ndarray) -> float | None:
    y_true = np.asarray(y_true, dtype=int)
    scores = np.asarray(scores, dtype=float)
    mask = np.isfinite(scores)
    y_true, scores = y_true[mask], scores[mask]
    n_pos = int(y_true.sum())
    n_neg = int(len(y_true) - n_pos)
    if n_pos == 0 or n_neg == 0 or len(y_true) < 2:
        return None
    try:
        from sklearn.metrics import roc_auc_score

        return float(roc_auc_score(y_true, scores))
    except Exception:
        # Mann-Whitney fallback
        order = np.argsort(scores)
        ranks = np.empty(len(scores), dtype=float)
        ranks[order] = np.arange(1, len(scores) + 1, dtype=float)
        s_sorted = scores[order]
        i = 0
        while i < len(s_sorted):
            j = i
            while j + 1 < len(s_sorted) and s_sorted[j + 1] == s_sorted[i]:
                j += 1
            if j > i:
                avg = (i + 1 + j + 1) / 2.0
                ranks[order[i : j + 1]] = avg
            i = j + 1
        sum_pos = ranks[y_true == 1].sum()
        u = sum_pos - n_pos * (n_pos + 1) / 2.0
        return float(u / (n_pos * n_neg))


def _time_split_indices(timestamps: list[str], entry_indices: list[int], oos_split: float):
    # sort by timestamp then entry_index
    order = sorted(
        range(len(entry_indices)),
        key=lambda i: (timestamps[i] or "", entry_indices[i]),
    )
    cut = int(round(len(order) * (1.0 - oos_split)))
    is_idx = order[:cut]
    oos_idx = order[cut:]
    return is_idx, oos_idx


def _design_matrix_path(Z: np.ndarray) -> np.ndarray:
    n, N, D = Z.shape
    return Z.reshape(n, N * D)


def _design_matrix_static(X0: np.ndarray, N: int) -> np.ndarray:
    # raw x0 repeated N times
    return np.tile(X0, (1, N))


def _design_matrix_shuffle_path(Z: np.ndarray, rng: random.Random) -> np.ndarray:
    Zs = Z.copy()
    n, N, D = Zs.shape
    for i in range(n):
        perm = list(range(N))
        rng.shuffle(perm)
        Zs[i] = Zs[i, perm, :]
    return Zs.reshape(n, N * D)


def _fit_predict_logistic(
    X_tr: np.ndarray,
    y_tr: np.ndarray,
    X_te: np.ndarray,
    C: float,
) -> np.ndarray:
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    scaler = StandardScaler()
    Xtr = scaler.fit_transform(X_tr)
    Xte = scaler.transform(X_te)
    clf = LogisticRegression(
        C=C,
        max_iter=500,
        solver="lbfgs",
        random_state=SEED,
    )
    clf.fit(Xtr, y_tr)
    if hasattr(clf, "predict_proba"):
        return clf.predict_proba(Xte)[:, 1]
    return clf.decision_function(Xte)


def _choose_C_is(
    X: np.ndarray, y: np.ndarray, is_idx: list[int], C_grid: tuple[float, ...]
) -> float:
    """Pick C on IS via internal 3-fold time order on IS only (no OOS leak)."""
    from sklearn.model_selection import KFold

    if len(is_idx) < 60:
        return 1.0
    Xis = X[is_idx]
    yis = y[is_idx]
    best_C, best_auc = 1.0, -1.0
    kf = KFold(n_splits=3, shuffle=False)
    for C in C_grid:
        fold_aucs = []
        for tr, te in kf.split(Xis):
            if yis[tr].sum() == 0 or yis[tr].sum() == len(tr):
                continue
            if yis[te].sum() == 0 or yis[te].sum() == len(te):
                continue
            scores = _fit_predict_logistic(Xis[tr], yis[tr], Xis[te], C)
            a = _auc(yis[te], scores)
            if a is not None:
                fold_aucs.append(a)
        m = float(np.mean(fold_aucs)) if fold_aucs else -1.0
        if m > best_auc:
            best_auc, best_C = m, C
    return best_C


def _perm_p_auc(y: np.ndarray, scores: np.ndarray, n_perm: int, seed: int) -> float | None:
    obs = _auc(y, scores)
    if obs is None:
        return None
    rng = np.random.RandomState(seed)
    more = 0
    y_work = y.copy()
    for _ in range(n_perm):
        rng.shuffle(y_work)
        a = _auc(y_work, scores)
        if a is None:
            continue
        if abs(a - 0.5) >= abs(obs - 0.5) - 1e-12:
            more += 1
    return (more + 1) / (n_perm + 1)


def evaluate_N(out_dir: Path, N: int) -> dict[str, Any]:
    batch = load_batch(out_dir, N)
    Z = np.asarray(batch.Z, dtype=np.float64)
    X0 = np.asarray(batch.X0, dtype=np.float64)
    y = np.asarray(batch.y, dtype=int)
    n = len(y)
    if n == 0:
        return {"N": N, "verdict": "INSUFFICIENT", "reason": "no_trajectories"}

    is_idx, oos_idx = _time_split_indices(batch.timestamps, batch.entry_indices, OOS_SPLIT)
    n_oos = len(oos_idx)

    X_path = _design_matrix_path(Z)
    X_static = _design_matrix_static(X0, N)
    rng = random.Random(SEED + N)
    X_shuf = _design_matrix_shuffle_path(Z, rng)

    # sanitize non-finite
    for X in (X_path, X_static, X_shuf):
        X[~np.isfinite(X)] = 0.0

    C_path = _choose_C_is(X_path, y, is_idx, LOGISTIC_C_IS_GRID)
    C_static = _choose_C_is(X_static, y, is_idx, LOGISTIC_C_IS_GRID)

    def eval_pair(X, C):
        scores_is = _fit_predict_logistic(X[is_idx], y[is_idx], X[is_idx], C)
        scores_oos = _fit_predict_logistic(X[is_idx], y[is_idx], X[oos_idx], C)
        return _auc(y[is_idx], scores_is), _auc(y[oos_idx], scores_oos), scores_oos

    auc_path_is, auc_path_oos, scores_path_oos = eval_pair(X_path, C_path)
    auc_static_is, auc_static_oos, _ = eval_pair(X_static, C_static)
    _, auc_shuf_oos, _ = eval_pair(X_shuf, C_path)

    delta = None
    if auc_path_oos is not None and auc_static_oos is not None:
        delta = auc_path_oos - auc_static_oos

    perm_p = None
    if scores_path_oos is not None and n_oos >= 20:
        perm_p = _perm_p_auc(y[oos_idx], scores_path_oos, N_PERM, SEED + 17 * N)

    retention_ok = False
    if auc_path_is is not None and auc_path_oos is not None and auc_path_is > 0.52:
        retention_ok = (auc_path_oos / auc_path_is) >= 0.85 if auc_path_is > 0 else False

    shuffle_gap_ok = False
    if auc_path_oos is not None and auc_shuf_oos is not None:
        shuffle_gap_ok = (auc_path_oos - auc_shuf_oos) >= SHUFFLE_PATH_GAP_MIN

    # verdict
    if n_oos < MIN_N_OOS:
        verdict = "INSUFFICIENT"
    elif (
        auc_path_oos is not None
        and delta is not None
        and auc_path_oos >= AUC_PATH_MIN
        and delta >= DELTA_AUC_MIN
        and retention_ok
        and perm_p is not None
        and perm_p <= 0.05
        and shuffle_gap_ok
    ):
        verdict = "RESEARCH_SUPPORTIVE"
    else:
        verdict = "REJECT"

    return {
        "N": N,
        "n": n,
        "n_is": len(is_idx),
        "n_oos": n_oos,
        "base_rate": float(y.mean()),
        "C_path": C_path,
        "C_static": C_static,
        "AUC_path_IS": auc_path_is,
        "AUC_path_OOS": auc_path_oos,
        "AUC_static_IS": auc_static_is,
        "AUC_static_OOS": auc_static_oos,
        "AUC_shuffle_path_OOS": auc_shuf_oos,
        "delta_AUC_OOS": delta,
        "perm_p_auc_path": perm_p,
        "retention_ok": retention_ok,
        "shuffle_gap_ok": shuffle_gap_ok,
        "verdict": verdict,
        "gates": {
            "min_n_oos": MIN_N_OOS,
            "auc_path_min": AUC_PATH_MIN,
            "delta_auc_min": DELTA_AUC_MIN,
            "shuffle_path_gap_min": SHUFFLE_PATH_GAP_MIN,
        },
    }


def evaluate_all(out_dir: Path | None = None, n_grid: tuple[int, ...] = N_GRID) -> dict[str, Any]:
    out_dir = out_dir or DEFAULT_OUT
    prereg = load_prereg()
    cells = {}
    for N in n_grid:
        npz = out_dir / f"trajectories_N{N}.npz"
        if not npz.exists():
            cells[str(N)] = {"N": N, "verdict": "INSUFFICIENT", "reason": "missing_batch"}
            continue
        logger.info("evaluate N=%s", N)
        cells[str(N)] = evaluate_N(out_dir, N)

    any_supportive = any(c.get("verdict") == "RESEARCH_SUPPORTIVE" for c in cells.values())
    all_reject = all(c.get("verdict") in ("REJECT", "INSUFFICIENT") for c in cells.values())

    report = {
        "program": "H-IC002-001",
        "schema_id": prereg.get("schema_id"),
        "status": "RUN_COMPLETE",
        "authority": "research_only",
        "hard_flags": prereg.get("hard_flags"),
        "cells": cells,
        "program_verdict": {
            "any_RESEARCH_SUPPORTIVE": any_supportive,
            "all_reject_or_insufficient": all_reject,
            "recommendation": (
                "IC-002 shows path information beyond static snapshot (research only; no prod)."
                if any_supportive
                else "IC-002 H0 not rejected on primary gates — no new IC value over static baseline; do not reopen IC-001."
            ),
        },
        "production_config_changed": False,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8"
    )

    lines = [
        "# H-IC002-001 — Entry Evolution Report",
        "",
        "> RESEARCH_ONLY · IC-002 / RC-005 · pre-registered before measurement",
        "",
        f"**Program verdict:** {report['program_verdict']['recommendation']}",
        "",
        "| N | n_oos | AUC_path_OOS | AUC_static_OOS | ΔAUC | perm_p | shuffle_gap_ok | verdict |",
        "|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for k in sorted(cells, key=lambda x: int(x)):
        c = cells[k]
        lines.append(
            f"| {c.get('N')} | {c.get('n_oos')} | {c.get('AUC_path_OOS')} | "
            f"{c.get('AUC_static_OOS')} | {c.get('delta_AUC_OOS')} | "
            f"{c.get('perm_p_auc_path')} | {c.get('shuffle_gap_ok')} | "
            f"**{c.get('verdict')}** |"
        )
    lines += [
        "",
        "## Gates (frozen)",
        f"- AUC_path_OOS ≥ {AUC_PATH_MIN}",
        f"- ΔAUC ≥ {DELTA_AUC_MIN}",
        f"- n_oos ≥ {MIN_N_OOS}",
        f"- perm p ≤ 0.05, shuffle-path gap ≥ {SHUFFLE_PATH_GAP_MIN}",
        "",
        "## Explicit non-actions",
        "- No production config change",
        "- No new engines",
        "- Static-only ML is not IC-002",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # update prereg status
    prereg_path = (
        Path(__file__).resolve().parents[3]
        / "docs"
        / "research-readiness"
        / "h-ic002-entry-evolution-experiment-definition.json"
    )
    if prereg_path.exists():
        prereg["status"] = "RUN_COMPLETE"
        prereg["run_artifacts"] = str(out_dir)
        prereg["run_verdict"] = report["program_verdict"]
        prereg_path.write_text(json.dumps(prereg, indent=2) + "\n", encoding="utf-8")

    return report
