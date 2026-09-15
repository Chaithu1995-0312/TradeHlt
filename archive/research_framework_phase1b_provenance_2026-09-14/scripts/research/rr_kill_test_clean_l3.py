#!/usr/bin/env python3
"""
RR kill-test on CLEAN L3 dataset — preregistered under RR_L1_FREEZE_CERTIFICATE.

Protocol (from L1 success_failure_rules):
  kill_test_primary: 5_fold_cv_offline_heads_gate_bypassed
  KEEP_CANDIDATE: label_validity_pass AND (rr_corr>0.03 OR pr_auc > shuffle_pr_auc+0.02)
                  AND top_decile_mean_y_rr > random_decile_mean_y_rr
  RETIRE: label_validity_pass AND rr_corr<=0.03 AND pr_auc<=shuffle+0.02
          AND top_decile_mean_y_rr <= random_decile_mean_y_rr
  Authority: RESEARCH_ONLY — never rr_fusion re-enable / promote

Usage (repo root):
  python scripts/research/rr_kill_test_clean_l3.py
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from config_layer.rr.rr_pattern_miner import (  # noqa: E402
    DEFAULT_MODEL_PATH,
    N_FEATURES,
    RRPatternTrainer,
    RR_SCORE_MAX,
    RR_SCORE_MIN,
)

from scripts.governance.rr_l1_freeze_certificate import (  # noqa: E402
    DEFAULT_CERT,
    compute_protocol_hash,
    cmd_assert_signed,
)

_K = 5
_SEED = 0
_RRCORR_KEEP = 0.03
_PR_AUC_MARGIN = 0.02


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(p)


def _auc(scores: np.ndarray, labels: np.ndarray) -> float:
    labels = labels.astype(int)
    n_pos = int(labels.sum())
    n_neg = int(len(labels) - n_pos)
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    order = np.argsort(scores, kind="mergesort")
    ranks = np.empty(len(scores), float)
    ranks[order] = np.arange(1, len(scores) + 1)
    s = scores[order]
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and s[j + 1] == s[i]:
            j += 1
        if j > i:
            ranks[order[i : j + 1]] = (i + 1 + j + 1) / 2.0
        i = j + 1
    return float((ranks[labels == 1].sum() - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


def _average_precision(scores: np.ndarray, labels: np.ndarray) -> float:
    """PR-AUC (average precision) without sklearn."""
    labels = labels.astype(int)
    n_pos = int(labels.sum())
    if n_pos == 0:
        return float("nan")
    order = np.argsort(-scores, kind="mergesort")
    y = labels[order]
    tp = 0
    ap = 0.0
    for i, yi in enumerate(y, start=1):
        if yi == 1:
            tp += 1
            ap += tp / i
    return float(ap / n_pos)


def _corr(a: np.ndarray, b: np.ndarray) -> float:
    if np.std(a) == 0 or np.std(b) == 0:
        return 0.0
    c = float(np.corrcoef(a, b)[0, 1])
    return 0.0 if np.isnan(c) else c


def _raw_model_outputs(state: dict, Xtest: np.ndarray):
    W = np.asarray(state["ridge_w"], dtype=np.float64)
    b = float(state["ridge_b"])
    smu = np.asarray(state["scale_mu"], dtype=np.float64)
    ssig = np.asarray(state["scale_sigma"], dtype=np.float64)
    ssig = np.where(ssig == 0, 1.0, ssig)
    gC0 = np.asarray(state["gnb_C"][0], dtype=np.float64)
    gV0 = np.asarray(state["gnb_V"][0], dtype=np.float64)
    gm0 = np.asarray(state["gnb_mu"][0], dtype=np.float64)
    gC1 = np.asarray(state["gnb_C"][1], dtype=np.float64)
    gV1 = np.asarray(state["gnb_V"][1], dtype=np.float64)
    gm1 = np.asarray(state["gnb_mu"][1], dtype=np.float64)
    zi = [int(i) for i in (state.get("zero_indices") or [])]

    X = np.array(Xtest, dtype=np.float64, copy=True)
    if zi:
        X[:, zi] = 0.0
    Xs = (X - smu) / ssig
    if zi:
        Xs[:, zi] = 0.0
    exp_rr = np.clip(Xs @ W + b, RR_SCORE_MIN, RR_SCORE_MAX)
    ll0 = (gC0 - 0.5 * gV0 * (Xs - gm0) ** 2).sum(axis=1)
    ll1 = (gC1 - 0.5 * gV1 * (Xs - gm1) ** 2).sum(axis=1)
    mx = np.maximum(ll0, ll1)
    e0 = np.exp(ll0 - mx)
    e1 = np.exp(ll1 - mx)
    p_win = e1 / (e0 + e1)
    return exp_rr, p_win


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cert", type=Path, default=DEFAULT_CERT)
    ap.add_argument("--cert-id", type=str, default=None)
    ap.add_argument("--seed", type=int, default=_SEED)
    ap.add_argument("--k-folds", type=int, default=_K)
    args = ap.parse_args(argv)

    cert_path = args.cert if args.cert.is_absolute() else (REPO_ROOT / args.cert)
    if cmd_assert_signed(cert_path) != 0:
        return 2
    cert = json.loads(cert_path.read_text(encoding="utf-8"))
    if compute_protocol_hash(cert["contract"]) != cert["protocol_hash"]:
        print("FAIL: protocol_hash drift", file=sys.stderr)
        return 1

    cert_id = args.cert_id or cert["certificate_id"]
    protocol_hash = cert["protocol_hash"]
    rules = cert["contract"]["success_failure_rules"]
    min_floor = int(cert["contract"]["sampling"].get("min_samples_floor") or 500)

    l3_dir = REPO_ROOT / "results" / "rr_research" / "l3" / cert_id
    l4_dir = REPO_ROOT / "results" / "rr_research" / "l4" / cert_id
    clean_npz = l3_dir / "clean_dataset.npz"
    l3_prov = json.loads((l3_dir / "L3_PROVENANCE.json").read_text(encoding="utf-8"))
    if l3_prov.get("protocol_hash") != protocol_hash:
        print("FAIL: L3 protocol_hash mismatch", file=sys.stderr)
        return 1
    if not clean_npz.is_file():
        print(f"FAIL: missing {clean_npz}", file=sys.stderr)
        return 1

    # Epoch RUNNING
    charter_path = l4_dir / "RR_EPOCH_CHARTER.json"
    if charter_path.is_file():
        charter = json.loads(charter_path.read_text(encoding="utf-8"))
        charter["RUNNING"] = True
        charter["running_started_at_utc"] = _utc_now()
        charter["running_job"] = "rr_kill_test_clean_l3"
        charter_path.write_text(json.dumps(charter, indent=2) + "\n", encoding="utf-8")

    pack = np.load(clean_npz, allow_pickle=True)
    X = np.asarray(pack["X"], dtype=np.float64)
    y_rr = np.asarray(pack["y_rr"], dtype=np.float64)
    y_win = np.asarray(pack["y_win"], dtype=np.int32)
    n = len(y_rr)
    if X.shape[1] != N_FEATURES:
        print(f"FAIL: n_features {X.shape[1]} != {N_FEATURES}", file=sys.stderr)
        return 1
    if n < min_floor:
        print(f"FAIL: n={n} < min_samples_floor={min_floor}", file=sys.stderr)
        return 1

    # Ensure zero mask from certificate / model
    with open(DEFAULT_MODEL_PATH, encoding="utf-8") as f:
        zero_idx = sorted(int(i) for i in json.load(f).get("zero_indices", []))
    for i in zero_idx:
        X[:, i] = 0.0
    dof = N_FEATURES - len(zero_idx)

    print(f"KILL-TEST clean L3 n={n} k={args.k_folds} protocol_hash={protocol_hash[:16]}…")
    print("  5-fold CV train heads on clean y (gate bypassed at predict)…")

    rng = np.random.default_rng(args.seed)
    perm = rng.permutation(n)
    folds = np.array_split(perm, args.k_folds)
    oos_rr = np.full(n, np.nan)
    oos_pw = np.full(n, np.nan)

    for k in range(args.k_folds):
        test_idx = folds[k]
        train_idx = np.concatenate([folds[j] for j in range(args.k_folds) if j != k])
        print(f"  fold {k+1}/{args.k_folds} train={len(train_idx)} test={len(test_idx)}")
        state = RRPatternTrainer().train(
            X[train_idx].tolist(),
            y_rr[train_idx].tolist(),
            y_win[train_idx].tolist(),
        )
        # attach zero_indices for raw predict consistency
        state["zero_indices"] = zero_idx
        rr, pw = _raw_model_outputs(state, X[test_idx])
        oos_rr[test_idx] = rr
        oos_pw[test_idx] = pw

    # Tier 0 — label validity (clean L3)
    wins = y_win > 0
    frac_win_1 = float(np.mean(np.isclose(y_rr[wins], 1.0))) if wins.any() else 0.0
    label_validity_pass = (
        l3_prov.get("degeneracy_check", {}).get("pass", False)
        and frac_win_1 <= 0.99
        and str(l3_prov.get("governing_exit", {}).get("method")) == "forward_walk"
    )
    tier0 = {
        "label_source": "L3 forward_walk(intrabar_fixed) net 12bps",
        "l3_path": _rel(clean_npz),
        "f022_stream_primary": False,
        "frac_win_y_rr_exact_1": frac_win_1,
        "degeneracy_check_pass": bool(l3_prov.get("degeneracy_check", {}).get("pass")),
        "credible": bool(label_validity_pass),
        "label_validity_pass": bool(label_validity_pass),
    }

    # Metrics
    rr_corr = _corr(oos_rr, y_rr)
    auc = _auc(oos_pw, y_win)
    pr_auc = _average_precision(oos_pw, y_win)
    brier = float(np.mean((oos_pw - y_win) ** 2))
    y_shuf = y_win.copy()
    rng.shuffle(y_shuf)
    auc_shuffle = _auc(oos_pw, y_shuf)
    pr_auc_shuffle = _average_precision(oos_pw, y_shuf)

    dec = max(1, n // 10)
    top = np.argsort(-oos_rr)[:dec]
    rand_idx = rng.choice(n, size=dec, replace=False)
    top_mean = float(np.mean(y_rr[top]))
    rand_mean = float(np.mean(y_rr[rand_idx]))
    # also report vs overall mean for context
    overall_mean = float(np.mean(y_rr))

    disc_pass = (rr_corr > _RRCORR_KEEP) or (pr_auc > pr_auc_shuffle + _PR_AUC_MARGIN)
    select_pass = top_mean > rand_mean
    disc_fail = (rr_corr <= _RRCORR_KEEP) and (pr_auc <= pr_auc_shuffle + _PR_AUC_MARGIN)
    select_fail = top_mean <= rand_mean

    if not label_validity_pass:
        classification = "INSUFFICIENT_LABEL_INVALID"
    elif disc_pass and select_pass:
        classification = "KEEP_CANDIDATE"
    elif disc_fail and select_fail:
        classification = "RETIRE"
    else:
        classification = "INDETERMINATE_MIXED"

    report: Dict[str, Any] = {
        "experiment": "rr_kill_test_clean_l3",
        "prereg_rules": rules,
        "certificate_id": cert_id,
        "protocol_hash": protocol_hash,
        "schema_hash": l3_prov.get("schema_hash") or l3_prov.get("l2_schema_hash"),
        "dataset": _rel(clean_npz),
        "n": int(n),
        "k_folds": int(args.k_folds),
        "seed": int(args.seed),
        "effective_dof": int(dof),
        "zero_indices": zero_idx,
        "confidence_gate": "bypassed",
        "authority": "RESEARCH_ONLY (§6.5) — KEEP_CANDIDATE never re-enables rr_fusion",
        "hard_flags": cert["contract"]["hard_flags"],
        "tier0_label_validity": tier0,
        "tier1_discrimination": {
            "rr_corr_pred_rr_vs_y_rr": round(rr_corr, 6),
            "auc_p_win_vs_y_win": round(auc, 6),
            "pr_auc_p_win_vs_y_win": round(pr_auc, 6),
            "auc_shuffle_control": round(auc_shuffle, 6),
            "pr_auc_shuffle_control": round(pr_auc_shuffle, 6),
            "pr_auc_margin_required": _PR_AUC_MARGIN,
            "brier": round(brier, 6),
            "base_win_rate": round(float(y_win.mean()), 6),
            "rr_corr_threshold": _RRCORR_KEEP,
            "disc_pass": bool(disc_pass),
        },
        "tier2_selection": {
            "top_decile_mean_y_rr": round(top_mean, 6),
            "random_decile_mean_y_rr": round(rand_mean, 6),
            "overall_mean_y_rr": round(overall_mean, 6),
            "select_pass": bool(select_pass),
        },
        "gates": {
            "label_validity_pass": bool(label_validity_pass),
            "disc_pass": bool(disc_pass),
            "select_pass": bool(select_pass),
            "disc_fail": bool(disc_fail),
            "select_fail": bool(select_fail),
        },
        "classification": classification,
        "verdict_reason": "",
        "completed_at_utc": _utc_now(),
    }

    if classification == "KEEP_CANDIDATE":
        report["verdict_reason"] = (
            f"Label validity PASS. Discrimination PASS (rr_corr={rr_corr:.4f}, "
            f"pr_auc={pr_auc:.4f} vs shuffle {pr_auc_shuffle:.4f}+margin). "
            f"Selection PASS (top_decile y_rr={top_mean:.4f} > random {rand_mean:.4f}). "
            f"KEEP_CANDIDATE only — research authority; rr_fusion stays disabled; no promote."
        )
    elif classification == "RETIRE":
        report["verdict_reason"] = (
            f"Label validity PASS. Discrimination FAIL (rr_corr={rr_corr:.4f}, "
            f"pr_auc={pr_auc:.4f} vs shuffle {pr_auc_shuffle:.4f}). "
            f"Selection FAIL (top_decile={top_mean:.4f} <= random {rand_mean:.4f}). "
            f"RETIRE trained-RR signal under this protocol — no re-enable path from this result."
        )
    elif classification == "INDETERMINATE_MIXED":
        report["verdict_reason"] = (
            f"Label validity PASS but mixed gates: disc_pass={disc_pass}, select_pass={select_pass}. "
            f"rr_corr={rr_corr:.4f}, pr_auc={pr_auc:.4f} (shuffle {pr_auc_shuffle:.4f}), "
            f"top_decile={top_mean:.4f} random={rand_mean:.4f}. No KEEP/RETIRE under prereg conjunction."
        )
    else:
        report["verdict_reason"] = "Label validity failed; cannot classify KEEP/RETIRE."

    out_dir = REPO_ROOT / "results" / "rr_research" / "epoch" / cert_id / "kill_test"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    t1 = report["tier1_discrimination"]
    t2 = report["tier2_selection"]
    md = f"""# RR Kill-Test — CLEAN L3 (preregistered)

**protocol_hash:** `{protocol_hash}`  
**certificate_id:** `{cert_id}`  
**dataset:** `{report['dataset']}`  
**n={n}** · **{args.k_folds}-fold CV** · gate **bypassed** · dof≈{dof}  
**Authority:** RESEARCH_ONLY — never production / never rr_fusion re-enable

## Tier 0 — Label validity
- source: {tier0['label_source']}
- frac(win ∧ y_rr≈1.0) = {tier0['frac_win_y_rr_exact_1']:.4f}
- **credible / label_validity_pass = {tier0['label_validity_pass']}**

## Tier 1 — Discrimination (OOS)
- rr_corr = **{t1['rr_corr_pred_rr_vs_y_rr']}** (threshold > {_RRCORR_KEEP})
- AUC = **{t1['auc_p_win_vs_y_win']}** (shuffle {t1['auc_shuffle_control']})
- PR-AUC = **{t1['pr_auc_p_win_vs_y_win']}** (shuffle {t1['pr_auc_shuffle_control']}; need +{_PR_AUC_MARGIN})
- Brier = {t1['brier']} · base win-rate = {t1['base_win_rate']}
- disc_pass = **{t1['disc_pass']}**

## Tier 2 — Selection
- top-decile mean y_rr = **{t2['top_decile_mean_y_rr']}**
- random-decile mean y_rr = **{t2['random_decile_mean_y_rr']}**
- overall mean y_rr = {t2['overall_mean_y_rr']}
- select_pass = **{t2['select_pass']}**

## CLASSIFICATION: **{classification}**

{report['verdict_reason']}

---
Prereg rules: `{rules.get('kill_test_primary')}`
"""
    (out_dir / "report.md").write_text(md, encoding="utf-8")

    # Update charter with result pointer (still no production authority)
    if charter_path.is_file():
        charter = json.loads(charter_path.read_text(encoding="utf-8"))
        charter["last_kill_test"] = {
            "path": _rel(out_dir / "report.json"),
            "classification": classification,
            "completed_at_utc": report["completed_at_utc"],
        }
        charter_path.write_text(json.dumps(charter, indent=2) + "\n", encoding="utf-8")

    print(md)
    print(f"\nArtifact: {_rel(out_dir)}/report.json")
    print(f"CLASSIFICATION: {classification}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
