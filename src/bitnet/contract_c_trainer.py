"""
contract_c_trainer.py
=====================
CONTRACT-C trainer for BitLinear residual family (Spec R1).

- Builds governed dataset (default: ATR-race bullish DIAGNOSTIC_ONLY)
- Trains float trunk matching bb_bitlinear_res_v1 topology
- Exports ternary+scale envelope (PTQ) into self-contained model.bundle
- Does NOT enable production use_bitnet; economic_authority stays DIAGNOSTIC_ONLY
  unless explicitly set (still no enable authority)

Usage (library)::

    from bitnet.contract_c_trainer import train_and_export
    path = train_and_export(csv_paths=[...], out_dir=\"results/bitnet/bundles\")
"""
from __future__ import annotations

import hashlib
import json
import logging
import platform
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from bitnet.defaults import (
    ACTIVATION_ID,
    BB_BITLINEAR_RES_ID,
    DEFAULT_HIDDEN_DIM,
    DEFAULT_INPUT_DIM,
    DEFAULT_LATENT_DIM,
    DEFAULT_N_RESIDUAL_BLOCKS,
    DEFAULTS_PROFILE,
    ENC_CANONICAL38_ID,
    HD_CONFIDENCE_ID,
    QUANTIZATION_ID,
    RESIDUAL_ID,
)
from bitnet.label_contracts import get_label_contract
from bitnet.model_bundle import write_model_bundle

log = logging.getLogger("bitnet.contract_c_trainer")

# Partial FM map for train_feature_identities (unknown → empty fm_id)
_KNOWN_FM: Dict[str, str] = {
    "body_ratio": "FM-010",
    "body_size": "FM-008",
    "wick_size": "FM-009",
    "disp_strength": "FM-020",
    "retest_depth": "FM-021",
    "atr": "FM-041",
    "rsi_14": "FM-042",
    "ema_fast": "FM-043",
    "ema_slow": "FM-044",
    "momentum_score": "FM-031",  # atr-scaled family when present
}


@dataclass
class TrainerConfig:
    label_contract_id: str = "BITNET_LABEL_ATR_RACE_BULL_V1"
    input_dim: int = DEFAULT_INPUT_DIM
    hidden_dim: int = DEFAULT_HIDDEN_DIM
    latent_dim: int = DEFAULT_LATENT_DIM
    n_residual_blocks: int = DEFAULT_N_RESIDUAL_BLOCKS
    defaults_profile: str = DEFAULTS_PROFILE
    warmup: int = 60
    bar_filter_min_retest_depth: float = 0.05
    bar_filter_id: str = "retest_depth_gt_0.05_FM021"
    holdout_fraction: float = 0.2
    epochs: int = 30
    lr: float = 1e-3
    batch_size: int = 64
    seed: int = 42
    weight_decay: float = 1e-4
    max_samples: Optional[int] = None  # cap for tests / smoke


@dataclass
class TrainResult:
    bundle_path: Path
    metrics: Dict[str, Any]
    n_train: int
    n_holdout: int


# ── Numeric helpers ───────────────────────────────────────────────────────────

def _sigmoid(z: np.ndarray) -> np.ndarray:
    z = np.clip(z, -40.0, 40.0)
    return 1.0 / (1.0 + np.exp(-z))


def _hardtanh(x: np.ndarray) -> np.ndarray:
    return np.clip(x, -1.0, 1.0)


def _hardtanh_grad(x: np.ndarray) -> np.ndarray:
    return ((x > -1.0) & (x < 1.0)).astype(np.float64)


def _xavier(rng: np.random.RandomState, fan_in: int, fan_out: int) -> np.ndarray:
    lim = np.sqrt(6.0 / (fan_in + fan_out))
    return rng.uniform(-lim, lim, size=(fan_out, fan_in)).astype(np.float64)


def float_to_ternary(W: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """PTQ: per-row threshold → ternary + scale so W ≈ scale[:,None] * Wt."""
    abs_mean = np.mean(np.abs(W), axis=1, keepdims=True) + 1e-8
    thr = 0.5 * abs_mean
    Wt = np.zeros_like(W)
    Wt[W > thr] = 1.0
    Wt[W < -thr] = -1.0
    scale = np.ones(W.shape[0], dtype=np.float64)
    for i in range(W.shape[0]):
        mask = Wt[i] != 0
        if np.any(mask):
            scale[i] = float(np.mean(W[i, mask] / Wt[i, mask]))
        else:
            scale[i] = float(abs_mean[i, 0])
    return Wt.astype(np.float64), scale


# ── Dataset ───────────────────────────────────────────────────────────────────

def _extract_row_vector(row, feature_names: Sequence[str]) -> np.ndarray:
    vec = np.zeros(len(feature_names), dtype=np.float64)
    for i, name in enumerate(feature_names):
        v = row.get(name, 0.0) if hasattr(row, "get") else row[name] if name in row else 0.0
        try:
            fv = float(v)
        except (TypeError, ValueError):
            fv = 0.0
        if fv != fv or fv in (float("inf"), float("-inf")):
            fv = 0.0
        vec[i] = fv
    return vec


def build_dataset_from_csv(
    csv_paths: Sequence[str],
    *,
    feature_names: Sequence[str],
    label_contract: Mapping[str, Any],
    warmup: int = 60,
    bar_filter_min_retest_depth: float = 0.05,
    max_samples: Optional[int] = None,
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    """
    FeaturePipeline → 38-vector + ATR-race labels.
    Returns X (n,d), y (n,), meta dict with fingerprints.
    """
    import pandas as pd
    from features.feature_pipeline import FeaturePipeline

    tp_m = float(label_contract["tp_atr_mult"])
    sl_m = float(label_contract["sl_atr_mult"])
    max_fwd = int(label_contract["max_fwd"])

    Xs: List[np.ndarray] = []
    ys: List[float] = []
    sources: List[str] = []
    file_hashes: Dict[str, str] = {}

    for csv_path in csv_paths:
        p = Path(csv_path)
        if not p.exists():
            log.warning("SKIP missing csv %s", csv_path)
            continue
        raw = p.read_bytes()
        file_hashes[str(p)] = hashlib.sha256(raw).hexdigest()
        df = pd.read_csv(p, parse_dates=["timestamp"])
        if len(df) < warmup + max_fwd + 20:
            log.warning("SKIP short csv %s n=%d", csv_path, len(df))
            continue
        try:
            pipe = FeaturePipeline(df)
            feat_df, _ = pipe.run()
        except Exception as exc:
            log.warning("SKIP FeaturePipeline failed %s: %s", csv_path, exc)
            continue

        highs = feat_df["high"].to_numpy(dtype=np.float64)
        lows = feat_df["low"].to_numpy(dtype=np.float64)
        closes = feat_df["close"].to_numpy(dtype=np.float64)
        n = len(feat_df)

        for i in range(warmup, n - max_fwd):
            row = feat_df.iloc[i]
            atr = float(row.get("atr", 0.0) or 0.0)
            if atr <= 0:
                continue
            retest = float(row.get("retest_depth", 0.0) or 0.0)
            if retest <= bar_filter_min_retest_depth:
                continue

            close = closes[i]
            tp = close + atr * tp_m
            sl = close - atr * sl_m
            label = None
            for j in range(i + 1, min(i + max_fwd + 1, n)):
                if highs[j] >= tp:
                    label = 1.0
                    break
                if lows[j] <= sl:
                    label = 0.0
                    break
            if label is None:
                continue

            Xs.append(_extract_row_vector(row, feature_names))
            ys.append(label)
            sources.append(str(p))
            if max_samples is not None and len(Xs) >= max_samples:
                break
        if max_samples is not None and len(Xs) >= max_samples:
            break

    if not Xs:
        raise ValueError("Empty dataset — no CONTRACT-C samples found.")

    X = np.stack(Xs, axis=0)
    y = np.asarray(ys, dtype=np.float64)
    meta = {
        "n_samples": int(len(y)),
        "pos_rate": float(y.mean()),
        "csv_sha256": file_hashes,
        "sources": sorted(set(sources)),
        "feature_dim": int(X.shape[1]),
    }
    return X, y, meta


def build_synthetic_dataset(
    n: int = 256,
    *,
    feature_names: Sequence[str],
    seed: int = 0,
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    """Deterministic synthetic data for unit tests (not economic)."""
    rng = np.random.RandomState(seed)
    d = len(feature_names)
    X = rng.randn(n, d).astype(np.float64) * 0.1
    # Make label weakly dependent on mean of first 3 dims
    logit = X[:, :3].sum(axis=1)
    y = (logit > 0).astype(np.float64)
    meta = {
        "n_samples": n,
        "pos_rate": float(y.mean()),
        "csv_sha256": {},
        "sources": ["synthetic"],
        "feature_dim": d,
        "synthetic": True,
    }
    return X, y, meta


# ── Model (float train) ───────────────────────────────────────────────────────

@dataclass
class _FloatNet:
    layers_W: List[np.ndarray]  # each (out, in)
    layers_b: List[np.ndarray]
    head_W: np.ndarray  # (1, L)
    head_b: np.ndarray  # (1,)
    n_residual_blocks: int
    hidden_dim: int
    latent_dim: int


def _init_net(cfg: TrainerConfig, rng: np.random.RandomState) -> _FloatNet:
    stages: List[Tuple[int, int]] = [(cfg.input_dim, cfg.hidden_dim)]
    for _ in range(cfg.n_residual_blocks):
        stages.append((cfg.hidden_dim, cfg.hidden_dim))
        stages.append((cfg.hidden_dim, cfg.hidden_dim))
    stages.append((cfg.hidden_dim, cfg.latent_dim))
    Ws, bs = [], []
    for din, dout in stages:
        Ws.append(_xavier(rng, din, dout))
        bs.append(np.zeros(dout, dtype=np.float64))
    head_W = _xavier(rng, cfg.latent_dim, 1)
    head_b = np.zeros(1, dtype=np.float64)
    return _FloatNet(
        layers_W=Ws,
        layers_b=bs,
        head_W=head_W,
        head_b=head_b,
        n_residual_blocks=cfg.n_residual_blocks,
        hidden_dim=cfg.hidden_dim,
        latent_dim=cfg.latent_dim,
    )


def _forward_net(net: _FloatNet, x: np.ndarray) -> Tuple[float, Dict[str, Any]]:
    """Single sample x (d,). Returns pred and cache for backward."""
    cache: Dict[str, Any] = {"xs": [], "pre_acts": [], "hs": []}
    h = x
    # projection
    z0 = net.layers_W[0] @ h + net.layers_b[0]
    h0 = _hardtanh(z0)
    cache["xs"].append(h)
    cache["pre_acts"].append(z0)
    cache["hs"].append(h0)
    h = h0
    idx = 1
    for _ in range(net.n_residual_blocks):
        residual = h
        z1 = net.layers_W[idx] @ h + net.layers_b[idx]
        u1 = _hardtanh(z1)
        cache["xs"].append(h)
        cache["pre_acts"].append(z1)
        cache["hs"].append(u1)
        z2 = net.layers_W[idx + 1] @ u1 + net.layers_b[idx + 1]
        u2 = _hardtanh(z2)
        cache["xs"].append(u1)
        cache["pre_acts"].append(z2)
        cache["hs"].append(u2)
        pre_sum = residual + u2
        h = _hardtanh(pre_sum)
        cache["res_in"] = cache.get("res_in", []) + [residual]
        cache["res_pre"] = cache.get("res_pre", []) + [pre_sum]
        cache["res_out"] = cache.get("res_out", []) + [h]
        idx += 2
    zL = net.layers_W[idx] @ h + net.layers_b[idx]
    latent = _hardtanh(zL)
    cache["xs"].append(h)
    cache["pre_acts"].append(zL)
    cache["hs"].append(latent)
    logit = float((net.head_W @ latent + net.head_b)[0])
    pred = float(_sigmoid(np.array([logit]))[0])
    cache["latent"] = latent
    cache["logit"] = logit
    cache["pred"] = pred
    return pred, cache


def _backward_net(
    net: _FloatNet,
    cache: Dict[str, Any],
    y: float,
    lr: float,
    weight_decay: float,
) -> float:
    """MSE on sigmoid; returns loss. In-place SGD update."""
    pred = cache["pred"]
    loss = (pred - y) ** 2
    # dL/dlogit
    d_pred = 2.0 * (pred - y)
    d_logit = d_pred * pred * (1.0 - pred)

    latent = cache["latent"]
    d_latent = net.head_W.T.flatten() * d_logit  # (L,)
    # head update
    net.head_W -= lr * (d_logit * latent[None, :] + weight_decay * net.head_W)
    net.head_b -= lr * np.array([d_logit])

    # latent layer
    n_layers = len(net.layers_W)
    # Walk backward through stages
    # Structure: [in] + 2*N_res + [lat] = n_layers
    # We stored xs/pre_acts/hs in order for each linear (not residual add as linear)
    # Residual blocks: two linears each, then hardtanh(residual+u2)

    # Start from last linear (latent proj)
    i = n_layers - 1
    zL = cache["pre_acts"][i]
    xL = cache["xs"][i]
    d_z = d_latent * _hardtanh_grad(zL)
    d_W = np.outer(d_z, xL) + weight_decay * net.layers_W[i]
    d_b = d_z
    d_h = net.layers_W[i].T @ d_z
    net.layers_W[i] -= lr * d_W
    net.layers_b[i] -= lr * d_b

    # Residual blocks reverse
    res_idx = net.n_residual_blocks - 1
    lin_idx = n_layers - 2  # last linear inside last residual (f1)
    while res_idx >= 0:
        # post residual hardtanh
        pre_sum = cache["res_pre"][res_idx]
        residual_in = cache["res_in"][res_idx]
        d_pre_sum = d_h * _hardtanh_grad(pre_sum)
        d_u2 = d_pre_sum
        d_residual = d_pre_sum

        # f1 linear at lin_idx
        z2 = cache["pre_acts"][lin_idx]
        x2 = cache["xs"][lin_idx]
        d_z2 = d_u2 * _hardtanh_grad(z2)
        d_W2 = np.outer(d_z2, x2) + weight_decay * net.layers_W[lin_idx]
        net.layers_W[lin_idx] -= lr * d_W2
        net.layers_b[lin_idx] -= lr * d_z2
        d_u1 = net.layers_W[lin_idx].T @ d_z2

        # f0 linear at lin_idx-1
        z1 = cache["pre_acts"][lin_idx - 1]
        x1 = cache["xs"][lin_idx - 1]
        d_z1 = d_u1 * _hardtanh_grad(z1)
        d_W1 = np.outer(d_z1, x1) + weight_decay * net.layers_W[lin_idx - 1]
        net.layers_W[lin_idx - 1] -= lr * d_W1
        net.layers_b[lin_idx - 1] -= lr * d_z1
        d_from_f0 = net.layers_W[lin_idx - 1].T @ d_z1

        d_h = d_residual + d_from_f0
        lin_idx -= 2
        res_idx -= 1

    # Input projection (layer 0)
    z0 = cache["pre_acts"][0]
    x0 = cache["xs"][0]
    d_z0 = d_h * _hardtanh_grad(z0)
    d_W0 = np.outer(d_z0, x0) + weight_decay * net.layers_W[0]
    net.layers_W[0] -= lr * d_W0
    net.layers_b[0] -= lr * d_z0
    return loss


def train_float_net(
    X: np.ndarray,
    y: np.ndarray,
    cfg: TrainerConfig,
) -> Tuple[_FloatNet, Dict[str, Any]]:
    rng = np.random.RandomState(cfg.seed)
    net = _init_net(cfg, rng)
    n = len(y)
    idx = np.arange(n)
    history = []
    for epoch in range(1, cfg.epochs + 1):
        rng.shuffle(idx)
        total = 0.0
        for start in range(0, n, cfg.batch_size):
            batch = idx[start : start + cfg.batch_size]
            for j in batch:
                pred, cache = _forward_net(net, X[j])
                total += _backward_net(net, cache, float(y[j]), cfg.lr, cfg.weight_decay)
        mean_loss = total / max(n, 1)
        history.append({"epoch": epoch, "train_mse": mean_loss})
        if epoch == 1 or epoch == cfg.epochs or epoch % max(1, cfg.epochs // 5) == 0:
            log.info("epoch %d train_mse=%.6f", epoch, mean_loss)
    return net, {"history": history}


def _predict_batch(net: _FloatNet, X: np.ndarray) -> np.ndarray:
    preds = np.zeros(len(X), dtype=np.float64)
    for i in range(len(X)):
        preds[i], _ = _forward_net(net, X[i])
    return preds


def predict_batch(net: _FloatNet, X: np.ndarray) -> np.ndarray:
    """Public alias for research harnesses (R2.5)."""
    return _predict_batch(net, X)


def _metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    mse = float(np.mean((y_pred - y_true) ** 2))
    # accuracy at 0.5
    acc = float(np.mean((y_pred >= 0.5) == (y_true >= 0.5)))
    # AUC-ish rank (Mann-Whitney) if both classes
    if y_true.min() < y_true.max():
        pos = y_pred[y_true >= 0.5]
        neg = y_pred[y_true < 0.5]
        if len(pos) and len(neg):
            # simple AUC
            correct = 0.0
            for p in pos:
                correct += np.mean(p > neg) + 0.5 * np.mean(p == neg)
            auc = float(correct / len(pos))
        else:
            auc = float("nan")
    else:
        auc = float("nan")
    brier = mse  # for binary targets
    return {
        "mse": mse,
        "brier": brier,
        "accuracy_0.5": acc,
        "auc_rank": auc,
        "pred_mean": float(y_pred.mean()),
        "label_pos_rate": float(y_true.mean()),
    }


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """Public alias for research harnesses (R2.5)."""
    return _metrics(y_true, y_pred)


# ── Export ────────────────────────────────────────────────────────────────────

def net_to_envelope(
    net: _FloatNet,
    *,
    feature_names: Sequence[str],
    mean: np.ndarray,
    std: np.ndarray,
    feature_order_hash: str,
    cfg: TrainerConfig,
    label_contract: Dict[str, Any],
) -> Dict[str, Any]:
    stages = []
    # names
    names = ["in"]
    for i in range(net.n_residual_blocks):
        names.append(f"res{i}_f0")
        names.append(f"res{i}_f1")
    names.append("lat")
    for name, W, b in zip(names, net.layers_W, net.layers_b):
        Wt, scale = float_to_ternary(W)
        stages.append({
            "name": name,
            "type": "bitlinear",
            "in": int(W.shape[1]),
            "out": int(W.shape[0]),
            "W_ternary": Wt.tolist(),
            "scale": scale.tolist(),
            "bias": b.tolist(),
        })
    heads = {
        "confidence": {
            "weight": net.head_W.tolist(),
            "bias": net.head_b.tolist(),
        }
    }
    return {
        "schema_version": "bitnet_cpp_v1",
        "backbone": {
            "id": BB_BITLINEAR_RES_ID,
            "defaults_profile": cfg.defaults_profile,
            "input_dim": cfg.input_dim,
            "hidden_dim": cfg.hidden_dim,
            "latent_dim": cfg.latent_dim,
            "n_residual_blocks": cfg.n_residual_blocks,
            "activation": ACTIVATION_ID,
            "residual": RESIDUAL_ID,
            "layernorm": False,
            "quantization": QUANTIZATION_ID,
            "bias": True,
            "stages": stages,
        },
        "heads": heads,
        "encoder": {
            "id": ENC_CANONICAL38_ID,
            "feature_names": list(feature_names),
            "feature_order_hash": feature_order_hash,
            "mean": mean.tolist(),
            "std": std.tolist(),
        },
        "metadata": {
            "label_contract_id": label_contract["label_contract_id"],
            "economic_authority": label_contract["economic_authority"],
            "heads_id": HD_CONFIDENCE_ID,
        },
    }


def _feature_schema_doc(feature_names: Sequence[str], feature_order_hash: str) -> Dict[str, Any]:
    identities = []
    for name in feature_names:
        identities.append({
            "name": name,
            "fm_id": _KNOWN_FM.get(name, ""),
            "formula_id": "",
        })
    return {
        "feature_dim": len(feature_names),
        "feature_names": list(feature_names),
        "feature_order_hash": feature_order_hash,
        "train_feature_identities": identities,
        "encoder_id": ENC_CANONICAL38_ID,
    }


def train_and_export(
    *,
    csv_paths: Optional[Sequence[str]] = None,
    out_dir: str | Path = "results/bitnet/bundles",
    cfg: Optional[TrainerConfig] = None,
    synthetic: bool = False,
    synthetic_n: int = 256,
    bundle_name: Optional[str] = None,
) -> TrainResult:
    """
    Full R1 path: dataset → train → model.bundle.

    synthetic=True builds fake data (tests only).
    """
    cfg = cfg or TrainerConfig()
    label = get_label_contract(cfg.label_contract_id)

    try:
        from features.feature_schema import CANONICAL_FEATURES, FEATURE_ORDER_HASH
        feature_names = list(CANONICAL_FEATURES)
        foh = FEATURE_ORDER_HASH
    except Exception:
        feature_names = [f"f{i}" for i in range(cfg.input_dim)]
        foh = ""

    if len(feature_names) != cfg.input_dim:
        # Allow any L2 custom dim in synthetic mode via synthetic short feature names.
        # PREVIOUSLY gated on `cfg.input_dim != 38` -- a stale literal from when
        # CANONICAL_FEATURES was 38-dim (schema v3.0). This branch only executes when
        # len(feature_names) != cfg.input_dim, so at write time (feature_names always 38-long)
        # the `!= 38` clause was tautologically true and silently redundant; it broke into a
        # false-negative the moment schema v4.0 grew CANONICAL_FEATURES to 39 (cfg.input_dim
        # defaults to 38, the FROZEN enc_canonical38_v1 architecture dim from bitnet/defaults.py,
        # which is intentionally decoupled from the live canonical vector length -- see that
        # module's own docstring: "NOT architectural laws. Artifacts must self-describe actual
        # dims."). Dropped rather than re-literalized to "39", which would just reintroduce the
        # same fragility at the next schema migration.
        if synthetic:
            feature_names = [f"f{i}" for i in range(cfg.input_dim)]
            foh = ""
        else:
            raise ValueError(
                f"feature_names len {len(feature_names)} != input_dim {cfg.input_dim}"
            )

    if synthetic:
        X, y, ds_meta = build_synthetic_dataset(
            synthetic_n, feature_names=feature_names, seed=cfg.seed
        )
    else:
        if not csv_paths:
            raise ValueError("csv_paths required when synthetic=False")
        X, y, ds_meta = build_dataset_from_csv(
            csv_paths,
            feature_names=feature_names,
            label_contract=label,
            warmup=cfg.warmup,
            bar_filter_min_retest_depth=cfg.bar_filter_min_retest_depth,
            max_samples=cfg.max_samples,
        )

    # Time-ordered split (no shuffle across time for CSV; synthetic ok sequential)
    n = len(y)
    n_hold = max(1, int(n * cfg.holdout_fraction)) if n > 5 else 0
    n_train = n - n_hold
    X_tr, y_tr = X[:n_train], y[:n_train]
    X_ho, y_ho = X[n_train:], y[n_train:]

    # Normalize on train only
    mean = X_tr.mean(axis=0)
    std = X_tr.std(axis=0)
    std = np.where(std < 1e-8, 1.0, std)
    X_tr_n = (X_tr - mean) / std
    X_ho_n = (X_ho - mean) / std if n_hold else X_ho

    net, train_info = train_float_net(X_tr_n, y_tr, cfg)
    pred_tr = _predict_batch(net, X_tr_n)
    metrics_tr = _metrics(y_tr, pred_tr)
    if n_hold:
        pred_ho = _predict_batch(net, X_ho_n)
        metrics_ho = _metrics(y_ho, pred_ho)
    else:
        metrics_ho = {}

    envelope = net_to_envelope(
        net,
        feature_names=feature_names,
        mean=mean,
        std=std,
        feature_order_hash=foh,
        cfg=cfg,
        label_contract=label,
    )

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = bundle_name or f"bitnet_c_{cfg.defaults_profile}_{ts}"
    bundle_path = Path(out_dir) / name

    metrics_doc = {
        "stage": "R2_partial",
        "train": metrics_tr,
        "holdout": metrics_ho,
        "history": train_info["history"],
        "note": "ML metrics only — NOT ΔG001; economic_authority remains DIAGNOSTIC_ONLY",
    }
    training_manifest = {
        "label_contract_id": label["label_contract_id"],
        "economic_authority": label["economic_authority"],
        "dataset": ds_meta,
        "bar_filter_id": cfg.bar_filter_id,
        "bar_filter_min_retest_depth": cfg.bar_filter_min_retest_depth,
        "warmup": cfg.warmup,
        "holdout_fraction": cfg.holdout_fraction,
        "n_train": int(n_train),
        "n_holdout": int(n_hold),
        "split": "time_ordered_prefix_train",
        "optimizer": "sgd",
        "lr": cfg.lr,
        "epochs": cfg.epochs,
        "batch_size": cfg.batch_size,
        "seed": cfg.seed,
        "weight_decay": cfg.weight_decay,
        "quantization_export": "PTQ_float_to_ternary_per_row",
        "defaults_profile": cfg.defaults_profile,
        "backbone_id": BB_BITLINEAR_RES_ID,
        "software": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "numpy": np.__version__,
        },
        "normalization": "train_mean_std",
    }
    evaluation_report = {
        "stage": "R1",
        "status": "TRAIN_COMPLETE",
        "protocol_id": "CONTRACT_C_R1_BUNDLE_EMIT",
        "pass": True,
        "criteria": "bundle CONTRACT-C complete; reproducible train under declared label contract",
        "metrics_ref": "metrics.json",
        "baselines_compared": [],
        "note": "R3/R4 evaluation_report fields filled only after offline/shadow stages",
    }
    metadata = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "instrument_scope": "multi" if (ds_meta.get("sources") and len(ds_meta["sources"]) > 1) else (
            ds_meta.get("sources", ["unknown"])[0]
        ),
        "defaults_profile": cfg.defaults_profile,
        "schema_version": "bitnet_cpp_v1",
        "label_contract_id": label["label_contract_id"],
        "economic_authority": label["economic_authority"],
    }

    write_model_bundle(
        bundle_path,
        envelope=envelope,
        metadata=metadata,
        feature_schema=_feature_schema_doc(feature_names, foh),
        label_contract=label,
        metrics=metrics_doc,
        training_manifest=training_manifest,
        evaluation_report=evaluation_report,
    )
    log.info("Wrote model.bundle → %s", bundle_path)
    return TrainResult(
        bundle_path=bundle_path,
        metrics=metrics_doc,
        n_train=n_train,
        n_holdout=n_hold,
    )
