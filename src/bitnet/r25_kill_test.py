"""
r25_kill_test.py
================
BitNet R2.5 kill-test harness (Spec v1.2.6).

Intent: try to **falsify** that the model learns something useful.
Surviving the suite **earns R3**; failure → investigate pipeline (no R3).

Pre-registered thresholds are frozen in ``R25_THRESHOLDS`` and must not be
tuned after inspecting a given run's results (new threshold version if changed).

Does NOT enable production ``use_bitnet``. Grants no economic authority.
"""
from __future__ import annotations

import json
import logging
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from bitnet.contract_c_trainer import (
    TrainerConfig,
    build_dataset_from_csv,
    build_synthetic_dataset,
    compute_metrics,
    predict_batch,
    train_float_net,
)
from bitnet.label_contracts import get_label_contract

log = logging.getLogger("bitnet.r25_kill_test")

# ── Pre-registered thresholds (Spec v1.2.6) — do not retune post-hoc ─────────

R25_THRESHOLD_VERSION = "r25_thresholds_v1"

R25_THRESHOLDS: Dict[str, float] = {
    # convergence: last train_mse <= first * (1 - min_rel_drop) OR absolute drop
    "min_rel_loss_drop": 0.02,
    # holdout AUC must exceed 0.5 by this margin (nan → fail)
    "min_auc_above_chance": 0.03,
    # expected calibration error upper bound
    "max_ece": 0.30,
    # prediction std floor (collapse detection)
    "min_pred_std": 0.015,
    # multi-seed: max - min holdout accuracy
    "max_seed_acc_range": 0.20,
    # ablation: MSE after zeroing features must rise by at least this
    "min_ablation_mse_increase": 1e-4,
    # kill: |AUC - 0.5| must be within this band (near chance; high skill ⇒ FAIL kill)
    # |AUC-0.5| band for kill tests (finite-sample noise; not economic skill)
    "max_abs_auc_from_chance_kill": 0.15,
}


@dataclass
class R25Config:
    """Harness knobs (not threshold laws)."""

    trainer: TrainerConfig = field(default_factory=TrainerConfig)
    n_seeds: int = 3
    synthetic: bool = True
    synthetic_n: int = 400
    synthetic_signal: str = "strong"  # strong | weak | none
    csv_paths: Optional[List[str]] = None
    out_dir: str = "results/bitnet/r25"
    run_name: Optional[str] = None


def expected_calibration_error(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    n_bins: int = 10,
) -> float:
    """ECE with equal-width bins on [0,1]."""
    y_true = np.asarray(y_true, dtype=np.float64)
    y_pred = np.clip(np.asarray(y_pred, dtype=np.float64), 1e-7, 1.0 - 1e-7)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n = len(y_true)
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        if i == n_bins - 1:
            mask = (y_pred >= lo) & (y_pred <= hi)
        else:
            mask = (y_pred >= lo) & (y_pred < hi)
        if not np.any(mask):
            continue
        conf = float(y_pred[mask].mean())
        acc = float(y_true[mask].mean())
        ece += (mask.sum() / n) * abs(acc - conf)
    return float(ece)


def _split_xy(
    X: np.ndarray, y: np.ndarray, holdout_fraction: float
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    n = len(y)
    n_hold = max(1, int(n * holdout_fraction)) if n > 5 else 0
    n_train = n - n_hold
    return X[:n_train], y[:n_train], X[n_train:], y[n_train:]


def _normalize_train(
    X_tr: np.ndarray, X_ho: np.ndarray
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    mean = X_tr.mean(axis=0)
    std = X_tr.std(axis=0)
    std = np.where(std < 1e-8, 1.0, std)
    return (X_tr - mean) / std, (X_ho - mean) / std, mean, std


def _build_strong_synthetic(
    n: int, feature_names: Sequence[str], seed: int
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    """Clear linear signal so R2.5 can pass on healthy data (not economic)."""
    rng = np.random.RandomState(seed)
    d = len(feature_names)
    X = rng.randn(n, d).astype(np.float64) * 0.3
    # Strong signal on dims 0..2
    score = 3.0 * X[:, 0] + 2.0 * X[:, 1] - 1.5 * X[:, 2]
    # logistic labels with noise
    p = 1.0 / (1.0 + np.exp(-score))
    y = (rng.rand(n) < p).astype(np.float64)
    meta = {
        "n_samples": n,
        "pos_rate": float(y.mean()),
        "synthetic": True,
        "synthetic_signal": "strong",
        "sources": ["synthetic_strong"],
        "feature_dim": d,
        "csv_sha256": {},
    }
    return X, y, meta


def load_dataset(cfg: R25Config) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any], List[str]]:
    try:
        from features.feature_schema import CANONICAL_FEATURES

        feature_names = list(CANONICAL_FEATURES)
    except Exception:
        feature_names = [f"f{i}" for i in range(cfg.trainer.input_dim)]

    if cfg.trainer.input_dim != len(feature_names):
        feature_names = [f"f{i}" for i in range(cfg.trainer.input_dim)]

    if cfg.synthetic:
        if cfg.synthetic_signal == "strong":
            X, y, meta = _build_strong_synthetic(
                cfg.synthetic_n, feature_names, cfg.trainer.seed
            )
        elif cfg.synthetic_signal == "none":
            X, y, meta = build_synthetic_dataset(
                cfg.synthetic_n, feature_names=feature_names, seed=cfg.trainer.seed
            )
            # destroy residual structure from default synthetic
            rng = np.random.RandomState(cfg.trainer.seed + 99)
            y = rng.randint(0, 2, size=len(y)).astype(np.float64)
            meta["synthetic_signal"] = "none"
        else:
            X, y, meta = build_synthetic_dataset(
                cfg.synthetic_n, feature_names=feature_names, seed=cfg.trainer.seed
            )
            meta["synthetic_signal"] = "weak"
    else:
        if not cfg.csv_paths:
            raise ValueError("csv_paths required when synthetic=False")
        label = get_label_contract(cfg.trainer.label_contract_id)
        X, y, meta = build_dataset_from_csv(
            cfg.csv_paths,
            feature_names=feature_names,
            label_contract=label,
            warmup=cfg.trainer.warmup,
            bar_filter_min_retest_depth=cfg.trainer.bar_filter_min_retest_depth,
            max_samples=cfg.trainer.max_samples,
        )
    return X, y, meta, feature_names


def _train_eval(
    X_tr: np.ndarray,
    y_tr: np.ndarray,
    X_ho: np.ndarray,
    y_ho: np.ndarray,
    trainer: TrainerConfig,
) -> Dict[str, Any]:
    net, info = train_float_net(X_tr, y_tr, trainer)
    pred_tr = predict_batch(net, X_tr)
    pred_ho = predict_batch(net, X_ho) if len(y_ho) else pred_tr[:0]
    m_tr = compute_metrics(y_tr, pred_tr)
    m_ho = compute_metrics(y_ho, pred_ho) if len(y_ho) else {}
    ece = expected_calibration_error(y_ho, pred_ho) if len(y_ho) else float("nan")
    return {
        "net": net,
        "history": info["history"],
        "train_metrics": m_tr,
        "holdout_metrics": m_ho,
        "holdout_pred": pred_ho,
        "ece": ece,
        "pred_std": float(pred_ho.std()) if len(pred_ho) else 0.0,
    }


def run_r25_kill_test(cfg: Optional[R25Config] = None) -> Dict[str, Any]:
    """
    Execute full R2.5 suite. Returns report dict with overall_pass and per-test rows.
    Thresholds are read only from R25_THRESHOLDS (pre-registered).
    """
    cfg = cfg or R25Config()
    thr = dict(R25_THRESHOLDS)
    X, y, ds_meta, feature_names = load_dataset(cfg)

    X_tr, y_tr, X_ho, y_ho = _split_xy(X, y, cfg.trainer.holdout_fraction)
    if len(y_ho) < 2:
        raise ValueError("R2.5 requires holdout size >= 2")

    X_tr_n, X_ho_n, mean, std = _normalize_train(X_tr, X_ho)

    tests: List[Dict[str, Any]] = []

    # ── Main train (seed 0 path uses cfg.trainer.seed) ───────────────────────
    main = _train_eval(X_tr_n, y_tr, X_ho_n, y_ho, cfg.trainer)
    hist = main["history"]
    first_loss = float(hist[0]["train_mse"])
    last_loss = float(hist[-1]["train_mse"])
    rel_drop = (first_loss - last_loss) / max(first_loss, 1e-12)
    conv_pass = (
        np.isfinite(first_loss)
        and np.isfinite(last_loss)
        and rel_drop >= thr["min_rel_loss_drop"]
    )
    tests.append({
        "id": "training_convergence",
        "purpose": "Can optimization reduce loss?",
        "pass": bool(conv_pass),
        "observed": {"first_mse": first_loss, "last_mse": last_loss, "rel_drop": rel_drop},
        "threshold": {"min_rel_loss_drop": thr["min_rel_loss_drop"]},
        "criterion": "Loss decreases by min_rel_loss_drop and stays finite",
    })

    # Holdout > random
    auc = main["holdout_metrics"].get("auc_rank", float("nan"))
    if auc != auc:  # nan
        holdout_pass = False
        auc_margin = float("nan")
    else:
        auc_margin = float(auc - 0.5)
        holdout_pass = auc_margin >= thr["min_auc_above_chance"]
    tests.append({
        "id": "holdout_gt_random",
        "purpose": "Is there predictive signal?",
        "pass": bool(holdout_pass),
        "observed": {"holdout_auc": auc, "auc_above_chance": auc_margin},
        "threshold": {"min_auc_above_chance": thr["min_auc_above_chance"]},
        "criterion": "Holdout AUC >= 0.5 + min_auc_above_chance",
    })

    # Calibration
    ece = main["ece"]
    cal_pass = np.isfinite(ece) and ece <= thr["max_ece"]
    tests.append({
        "id": "calibration",
        "purpose": "Are probabilities meaningful?",
        "pass": bool(cal_pass),
        "observed": {"ece": ece},
        "threshold": {"max_ece": thr["max_ece"]},
        "criterion": "ECE <= max_ece",
    })

    # Prediction collapse
    pred_std = main["pred_std"]
    collapse_pass = pred_std >= thr["min_pred_std"]
    tests.append({
        "id": "prediction_collapse",
        "purpose": "Is it predicting one class?",
        "pass": bool(collapse_pass),
        "observed": {"pred_std": pred_std, "pred_mean": main["holdout_metrics"].get("pred_mean")},
        "threshold": {"min_pred_std": thr["min_pred_std"]},
        "criterion": "Holdout prediction std >= min_pred_std",
    })

    # Seed stability
    seed_accs: List[float] = []
    for s in range(cfg.n_seeds):
        tcfg = deepcopy(cfg.trainer)
        tcfg.seed = cfg.trainer.seed + s
        r = _train_eval(X_tr_n, y_tr, X_ho_n, y_ho, tcfg)
        seed_accs.append(float(r["holdout_metrics"].get("accuracy_0.5", 0.0)))
    acc_range = float(max(seed_accs) - min(seed_accs)) if seed_accs else float("inf")
    seed_pass = acc_range <= thr["max_seed_acc_range"]
    tests.append({
        "id": "seed_stability",
        "purpose": "Is training reproducible?",
        "pass": bool(seed_pass),
        "observed": {"seed_accuracies": seed_accs, "acc_range": acc_range},
        "threshold": {"max_seed_acc_range": thr["max_seed_acc_range"], "n_seeds": cfg.n_seeds},
        "criterion": "max(acc)-min(acc) across seeds <= max_seed_acc_range",
    })

    # Feature ablation — zero first half of features on holdout only
    X_ho_ab = X_ho_n.copy()
    half = max(1, X_ho_ab.shape[1] // 2)
    X_ho_ab[:, :half] = 0.0
    pred_ab = predict_batch(main["net"], X_ho_ab)
    mse_base = float(main["holdout_metrics"].get("mse", 0.0))
    mse_ab = float(compute_metrics(y_ho, pred_ab)["mse"])
    ab_delta = mse_ab - mse_base
    ab_pass = ab_delta >= thr["min_ablation_mse_increase"]
    tests.append({
        "id": "feature_ablation",
        "purpose": "Does removing key features matter?",
        "pass": bool(ab_pass),
        "observed": {
            "mse_base": mse_base,
            "mse_ablated": mse_ab,
            "mse_increase": ab_delta,
            "zeroed_dims": half,
        },
        "threshold": {"min_ablation_mse_increase": thr["min_ablation_mse_increase"]},
        "criterion": "Holdout MSE increases after zeroing first half of features",
    })

    # ── Kill: label shuffle ───────────────────────────────────────────────────
    rng = np.random.RandomState(cfg.trainer.seed + 1000)
    y_tr_shuf = y_tr.copy()
    rng.shuffle(y_tr_shuf)
    kill_shuf = _train_eval(X_tr_n, y_tr_shuf, X_ho_n, y_ho, cfg.trainer)
    auc_shuf = kill_shuf["holdout_metrics"].get("auc_rank", float("nan"))
    # PASS of kill-test means the *kill succeeded* (model does NOT look good)
    # Suite "pass" for this row: model fails to beat chance on true holdout after shuffled train
    band = thr["max_abs_auc_from_chance_kill"]

    def _near_chance(auc_v: float) -> bool:
        if auc_v != auc_v:  # NaN — no ranking signal
            return True
        return abs(float(auc_v) - 0.5) <= band

    shuffle_kill_ok = _near_chance(float(auc_shuf) if auc_shuf == auc_shuf else float("nan"))
    tests.append({
        "id": "label_shuffle_kill",
        "purpose": "Can it 'learn' random labels? (should fail to transfer)",
        "pass": bool(shuffle_kill_ok),
        "kill_test": True,
        "observed": {
            "holdout_auc_true_y_after_train_on_shuffled_y": auc_shuf,
            "abs_auc_from_chance": (
                None if auc_shuf != auc_shuf else abs(float(auc_shuf) - 0.5)
            ),
            "holdout_acc": kill_shuf["holdout_metrics"].get("accuracy_0.5"),
        },
        "threshold": {"max_abs_auc_from_chance_kill": band},
        "criterion": (
            "Train on shuffled y_train; evaluate on true y_holdout. "
            "|AUC-0.5| must be <= band (near chance). If far from chance → leakage/eval bug."
        ),
    })

    # ── Kill: constant features ───────────────────────────────────────────────
    X_tr_const = np.zeros_like(X_tr_n)
    X_ho_const = np.zeros_like(X_ho_n)
    kill_const = _train_eval(X_tr_const, y_tr, X_ho_const, y_ho, cfg.trainer)
    auc_const = kill_const["holdout_metrics"].get("auc_rank", float("nan"))
    const_kill_ok = _near_chance(float(auc_const) if auc_const == auc_const else float("nan"))
    tests.append({
        "id": "constant_feature_kill",
        "purpose": "Can it invent signal from constant features?",
        "pass": bool(const_kill_ok),
        "kill_test": True,
        "observed": {
            "holdout_auc_on_true_y": auc_const,
            "abs_auc_from_chance": (
                None if auc_const != auc_const else abs(float(auc_const) - 0.5)
            ),
            "holdout_acc": kill_const["holdout_metrics"].get("accuracy_0.5"),
        },
        "threshold": {"max_abs_auc_from_chance_kill": band},
        "criterion": (
            "Train/eval with all-zero features. |AUC-0.5| must be <= band. "
            "If far from chance → leakage/eval bug."
        ),
    })

    overall = all(bool(t["pass"]) for t in tests)
    decision = "PASS_EARN_R3" if overall else "FAIL_INVESTIGATE_NO_R3"

    report: Dict[str, Any] = {
        "stage": "R2.5",
        "protocol_id": "BITNET_R25_KILL_TEST_V1",
        "threshold_version": R25_THRESHOLD_VERSION,
        "thresholds": thr,
        "status": decision,
        "pass": overall,
        "criteria": (
            "All R2.5 rows pass, including kill tests (shuffle/constant must NOT "
            "show real holdout skill). Surviving earns R3 only — not R4/enable."
        ),
        "tests": tests,
        "dataset": ds_meta,
        "feature_dim": len(feature_names),
        "n_train": int(len(y_tr)),
        "n_holdout": int(len(y_ho)),
        "trainer": {
            "epochs": cfg.trainer.epochs,
            "lr": cfg.trainer.lr,
            "hidden_dim": cfg.trainer.hidden_dim,
            "latent_dim": cfg.trainer.latent_dim,
            "n_residual_blocks": cfg.trainer.n_residual_blocks,
            "seed": cfg.trainer.seed,
            "label_contract_id": cfg.trainer.label_contract_id,
        },
        "main_holdout_metrics": main["holdout_metrics"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "authority": (
            "Research only. PASS grants R3 offline comparison permission only. "
            "No use_bitnet, no economic claim, no production promote."
        ),
        "next_if_pass": "R3 strict offline legacy vs BitLinearRes",
        "next_if_fail": "Investigate pipeline / labels / eval; do not run R3",
    }
    return report


def write_r25_report(report: Mapping[str, Any], out_dir: str | Path, run_name: Optional[str] = None) -> Path:
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = run_name or f"r25_kill_{ts}"
    path = root / f"{name}.json"
    path.write_text(json.dumps(dict(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # also drop evaluation_report-shaped stub for bundle compatibility
    eval_path = root / f"{name}_evaluation_report.json"
    eval_doc = {
        "stage": "R2.5",
        "status": report.get("status"),
        "pass": report.get("pass"),
        "protocol_id": report.get("protocol_id"),
        "threshold_version": report.get("threshold_version"),
        "tests": report.get("tests"),
        "created_at": report.get("created_at"),
        "full_report": str(path),
    }
    eval_path.write_text(json.dumps(eval_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    log.info("R2.5 report → %s (%s)", path, report.get("status"))
    return path
