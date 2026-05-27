"""
train_trade_net_v2.py
=====================
Train TradeNet v2 — 3-head survival classifier on the 38-dim canonical feature
vector. One model per instrument. Writes a JSON envelope (no PyTorch state_dict
at the production boundary) and registers it via the per-instrument TradeNet
registry.

Labels are derived from opportunity outcomes:
  reaches_tp1   = 1 iff outcome reached TP1
  reaches_tp2   = 1 iff outcome reached TP2
  survives_be   = 1 iff mfe >= 1R    (MFE-based BE-survival proxy; 1R = |entry - sl|)

Sample gate honors ``training_trigger.min_new_samples`` from the production
config and counts closed records only.

Usage:
    py train_trade_net_v2.py --instrument ETHUSDT
    py train_trade_net_v2.py --instrument ETHUSDT --shadow         # train + register, do not promote
    py train_trade_net_v2.py --instrument ETHUSDT --force-promote  # bypass regression guard
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import sys
import time
from pathlib import Path
from typing import Iterable, Optional

import numpy as np

_REPO = Path(__file__).resolve().parents[2]
_SRC = _REPO / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from features.feature_schema import (  # noqa: E402
    CANONICAL_FEATURES,
    CANONICAL_FEATURE_DIM,
    CANONICAL_FEATURE_ORDER,
)
from features.dataset_builder import extract_feature_vector  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
log = logging.getLogger("train_trade_net_v2")

# Public so verification snippets can import the constant.
INPUT_DIM: int = CANONICAL_FEATURE_DIM  # 38
HIDDEN_1: int = 32
HIDDEN_2: int = 16
HEAD_NAMES = ("p_tp1", "p_tp2", "p_survives_be")
COMPOSITE_WEIGHTS = (0.4, 0.4, 0.2)
SCHEMA_VERSION_V2 = "tradenet_v2"

# Outcome strings that count as "reached TP1" and "reached TP2".
# Covers backtest_v2 (TP1, TP2) and opportunity_scanner (TP1_HIT, TP2_HIT) variants.
_TP1_OUTCOMES = frozenset({"TP1", "TP2", "TP1_HIT", "TP2_HIT"})
_TP2_OUTCOMES = frozenset({"TP2", "TP2_HIT"})


# ─────────────────────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────────────────────

def _glob_opportunity_files(root: Path, instrument: str) -> list[Path]:
    """Find opportunities_*.jsonl files relevant to the instrument.

    Matches both ``logs/opportunities_{INSTR}.jsonl`` and
    ``logs/{INSTR}/**/opportunities.jsonl``. Returns files in deterministic order.
    """
    candidates: list[Path] = []
    candidates.extend(root.glob(f"opportunities_{instrument}.jsonl"))
    candidates.extend(root.glob(f"opportunities_{instrument}_*.jsonl"))
    candidates.extend(root.glob(f"{instrument}/**/opportunities.jsonl"))
    candidates.extend(root.glob(f"{instrument}/**/opportunities_*.jsonl"))
    # Dedup, keep stable order.
    seen: set[Path] = set()
    out: list[Path] = []
    for p in candidates:
        if p in seen:
            continue
        seen.add(p)
        out.append(p)
    return sorted(out)


def load_opportunity_records(
    paths: Iterable[Path],
    instrument: str,
) -> list[dict]:
    """Stream JSONL files and keep only records matching the instrument."""
    out: list[dict] = []
    for p in paths:
        try:
            with p.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if rec.get("instrument") and rec["instrument"] != instrument:
                        continue
                    out.append(rec)
        except OSError as exc:
            log.warning("could not read %s — %s", p, exc)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Label + matrix construction
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_outcome(rec: dict) -> str:
    return str(rec.get("exit_reason") or rec.get("outcome") or "")


def _one_r(rec: dict) -> float:
    try:
        entry = float(rec["entry"])
        sl = float(rec["sl"])
        return abs(entry - sl)
    except (KeyError, TypeError, ValueError):
        return 0.0


def is_closed(rec: dict) -> bool:
    """True when the record has a non-OPEN, non-empty outcome string."""
    return _resolve_outcome(rec).upper() not in ("", "OPEN")


def extract_labels(records: list[dict]) -> np.ndarray:
    """Build (N, 3) label matrix [reaches_tp1, reaches_tp2, survives_be]."""
    labels = np.zeros((len(records), 3), dtype=np.float32)
    survives_unresolved = 0
    for i, rec in enumerate(records):
        outcome = _resolve_outcome(rec).upper()
        labels[i, 0] = 1.0 if outcome in _TP1_OUTCOMES else 0.0
        labels[i, 1] = 1.0 if outcome in _TP2_OUTCOMES else 0.0
        if "mfe" in rec:
            one_r = _one_r(rec)
            try:
                mfe = float(rec["mfe"])
            except (TypeError, ValueError):
                mfe = 0.0
            labels[i, 2] = 1.0 if (one_r > 0 and mfe >= one_r) else 0.0
        else:
            labels[i, 2] = 0.0
            survives_unresolved += 1
    if survives_unresolved:
        _emit("TRADENET_SURVIVES_BE_UNRESOLVED", "INFO",
              {"n_unresolved": survives_unresolved,
               "note": "records lacking 'mfe' default to survives_be=0"})
    return labels


def build_input_matrix(records: list[dict]) -> np.ndarray:
    """Build (N, 38) feature matrix from opportunity records.

    Records without a usable ``features`` dict are skipped silently — callers
    should keep the index alignment with ``extract_labels`` by filtering both
    through ``filter_usable_records`` first.
    """
    rows: list[list[float]] = []
    for rec in records:
        feats = rec.get("features")
        if not isinstance(feats, dict):
            continue
        try:
            vec = extract_feature_vector(feats)
        except (ValueError, KeyError, TypeError, AssertionError):
            continue
        rows.append(vec)
    if not rows:
        return np.zeros((0, INPUT_DIM), dtype=np.float32)
    return np.asarray(rows, dtype=np.float32)


def filter_usable_records(records: list[dict]) -> list[dict]:
    """Drop records lacking a complete 38-dim features dict."""
    out: list[dict] = []
    required = set(CANONICAL_FEATURES)
    for rec in records:
        feats = rec.get("features")
        if not isinstance(feats, dict):
            continue
        if not required.issubset(feats.keys()):
            continue
        out.append(rec)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Training (PyTorch)
# ─────────────────────────────────────────────────────────────────────────────

class _Trunk:
    """Plain shape container for the 38 -> 32 -> 16 trunk + 3 heads. Built by
    ``_build_torch_model``; weights flow through ``_export_envelope``."""


def _build_torch_model():
    import torch
    import torch.nn as nn

    class TradeNetV2Net(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.fc1 = nn.Linear(INPUT_DIM, HIDDEN_1)
            self.drop1 = nn.Dropout(0.2)
            self.fc2 = nn.Linear(HIDDEN_1, HIDDEN_2)
            self.head_tp1 = nn.Linear(HIDDEN_2, 1)
            self.head_tp2 = nn.Linear(HIDDEN_2, 1)
            self.head_be = nn.Linear(HIDDEN_2, 1)

        def forward(self, x):
            h = torch.relu(self.fc1(x))
            h = self.drop1(h)
            h = torch.relu(self.fc2(h))
            return (
                torch.sigmoid(self.head_tp1(h)),
                torch.sigmoid(self.head_tp2(h)),
                torch.sigmoid(self.head_be(h)),
            )

    return TradeNetV2Net()


def _pos_weight(labels_col: np.ndarray) -> float:
    n_pos = float((labels_col > 0.5).sum())
    n_neg = float((labels_col <= 0.5).sum())
    if n_pos <= 0:
        return 1.0
    return max(1.0, n_neg / n_pos)


def _train_model(
    X: np.ndarray,
    Y: np.ndarray,
    *,
    epochs: int = 100,
    lr: float = 1e-3,
    batch_size: int = 64,
):
    """Train the 3-head model. Returns (model, scaler_mean, scaler_std, metrics)."""
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset

    mean = X.mean(axis=0)
    std = X.std(axis=0)
    std = np.where(std < 1e-8, 1.0, std)
    Xs = (X - mean) / std

    pw = [_pos_weight(Y[:, i]) for i in range(3)]
    log.info("class balance pos_weight | tp1=%.2f tp2=%.2f survives_be=%.2f", *pw)

    model = _build_torch_model()
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    bce = nn.BCELoss(reduction="none")

    Xt = torch.tensor(Xs, dtype=torch.float32)
    Yt = torch.tensor(Y, dtype=torch.float32)
    ds = TensorDataset(Xt, Yt)
    bs = batch_size if 0 < batch_size <= len(Xt) else len(Xt)
    loader = DataLoader(ds, batch_size=bs, shuffle=True)

    model.train()
    for epoch in range(1, epochs + 1):
        total = 0.0
        for xb, yb in loader:
            p1, p2, pb = model(xb)
            loss = (
                _weighted_bce(bce, p1, yb[:, 0:1], pw[0])
                + _weighted_bce(bce, p2, yb[:, 1:2], pw[1])
                + _weighted_bce(bce, pb, yb[:, 2:3], pw[2])
            )
            opt.zero_grad()
            loss.backward()
            opt.step()
            total += float(loss.item()) * xb.shape[0]
        if epoch % 10 == 0 or epoch == 1 or epoch == epochs:
            log.info("epoch %3d/%d | loss=%.4f", epoch, epochs, total / len(Xt))

    model.eval()
    metrics = _eval_metrics(model, Xt, Yt)
    return model, mean, std, metrics


def _weighted_bce(bce, pred, target, pos_w: float):
    raw = bce(pred, target)
    import torch
    w = torch.where(target > 0.5, torch.full_like(target, pos_w), torch.ones_like(target))
    return (raw * w).mean()


def _eval_metrics(model, Xt, Yt) -> dict:
    import torch
    with torch.no_grad():
        p1, p2, pb = model(Xt)
        preds = {"p_tp1": p1.cpu().numpy().ravel(),
                 "p_tp2": p2.cpu().numpy().ravel(),
                 "p_survives_be": pb.cpu().numpy().ravel()}
    y = Yt.cpu().numpy()
    out: dict = {}
    for i, head in enumerate(HEAD_NAMES):
        out[f"auc_{head}"] = _auc(y[:, i], preds[head])
        out[f"pos_rate_{head}"] = float(y[:, i].mean())
    return out


def _auc(y_true: np.ndarray, y_score: np.ndarray) -> float:
    """Stdlib AUC via Mann-Whitney U; returns 0.5 when one class is absent."""
    y_true = np.asarray(y_true).astype(np.int8)
    pos = y_score[y_true == 1]
    neg = y_score[y_true == 0]
    if len(pos) == 0 or len(neg) == 0:
        return 0.5
    order = np.argsort(np.concatenate([pos, neg]))
    ranks = np.empty_like(order, dtype=np.float64)
    ranks[order] = np.arange(1, len(order) + 1)
    rank_pos = ranks[: len(pos)].sum()
    u = rank_pos - len(pos) * (len(pos) + 1) / 2.0
    return float(u / (len(pos) * len(neg)))


# ─────────────────────────────────────────────────────────────────────────────
# Envelope export
# ─────────────────────────────────────────────────────────────────────────────

def _layer_dict(linear) -> dict:
    return {
        "type": "linear",
        "in": int(linear.in_features),
        "out": int(linear.out_features),
        "weight": linear.weight.detach().cpu().numpy().tolist(),
        "bias": linear.bias.detach().cpu().numpy().tolist(),
    }


def _export_envelope(
    model,
    mean: np.ndarray,
    std: np.ndarray,
    *,
    instrument: str,
    version: str,
    metrics: dict,
    n_total: int,
    n_closed: int,
    class_balance: dict,
    output_path: Path,
) -> Path:
    feature_order_hash = hashlib.sha256(
        json.dumps(list(CANONICAL_FEATURE_ORDER), sort_keys=False).encode()
    ).hexdigest()[:16]

    envelope = {
        "schema_version": SCHEMA_VERSION_V2,
        "feature_dim": INPUT_DIM,
        "feature_order_hash": feature_order_hash,
        "feature_names": list(CANONICAL_FEATURE_ORDER),
        "trunk": [
            _layer_dict(model.fc1),
            {"type": "relu"},
            _layer_dict(model.fc2),
            {"type": "relu"},
        ],
        "heads": {
            "p_tp1":         _head_dict(model.head_tp1),
            "p_tp2":         _head_dict(model.head_tp2),
            "p_survives_be": _head_dict(model.head_be),
        },
        "scaler": {
            "mean": mean.astype(float).tolist(),
            "std":  std.astype(float).tolist(),
        },
        "metadata": {
            "version": version,
            "instrument": instrument,
            "trained_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "n_samples_total": int(n_total),
            "n_samples_closed": int(n_closed),
            "class_balance": class_balance,
            "metrics": metrics,
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = output_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(envelope, indent=2), encoding="utf-8")
    tmp.replace(output_path)
    log.info("envelope saved -> %s", output_path)
    return output_path


def _head_dict(linear) -> dict:
    return {
        "weight": linear.weight.detach().cpu().numpy().tolist(),
        "bias":   linear.bias.detach().cpu().numpy().tolist(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Config + telemetry
# ─────────────────────────────────────────────────────────────────────────────

def _load_min_new_samples() -> int:
    """Read training_trigger.min_new_samples from the production config; falls
    back to 500 if the key is absent. Mirrors the Gaussian/RR pipeline floor."""
    try:
        from config_layer.production_loader import get_prod_config
        cfg = get_prod_config()
    except Exception:
        try:
            cfg_path = _REPO / "configs" / "production" / "v1_multi_2026_03.json"
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            return 500
    # Two possible nesting paths — direct or under "training".
    for path in (("training", "training_trigger"), ("training_trigger",)):
        node = cfg
        for k in path:
            if not isinstance(node, dict):
                node = None
                break
            node = node.get(k)
        if isinstance(node, dict) and "min_new_samples" in node:
            try:
                return int(node["min_new_samples"])
            except (TypeError, ValueError):
                pass
    return 500


def _emit(event: str, severity: str, payload: dict) -> None:
    try:
        from utils.integrity_events import emit_integrity_event
        emit_integrity_event(event, severity, "train_trade_net_v2", payload)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="Train TradeNet v2 for a single instrument.")
    ap.add_argument("--instrument", required=True, help="Target instrument (e.g. ETHUSDT)")
    ap.add_argument("--logs-root", default="logs", help="Root directory for opportunities JSONLs")
    ap.add_argument("--epochs", type=int, default=100)
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--shadow", action="store_true",
                    help="Register only, do not promote (for shadow validation)")
    ap.add_argument("--force-promote", action="store_true",
                    help="Bypass auc_p_tp1 regression guard during promotion")
    ap.add_argument("--version", default=None,
                    help="Explicit version label; defaults to v2_{INSTR}_{YYYYMMDDHHMMSS}")
    args = ap.parse_args()

    logs_root = Path(args.logs_root)
    if not logs_root.is_absolute():
        logs_root = _REPO / logs_root

    paths = _glob_opportunity_files(logs_root, args.instrument)
    if not paths:
        log.error("No opportunities files found for %s under %s", args.instrument, logs_root)
        return 2
    log.info("found %d opportunity file(s) for %s", len(paths), args.instrument)
    records = load_opportunity_records(paths, args.instrument)
    log.info("loaded %d raw records (instrument-filtered)", len(records))

    records = filter_usable_records(records)
    closed = [r for r in records if is_closed(r)]
    log.info("usable=%d  closed=%d", len(records), len(closed))

    min_samples = _load_min_new_samples()
    if len(closed) < min_samples:
        _emit("TRADENET_INSUFFICIENT_DATA", "WARNING",
              {"instrument": args.instrument,
               "n_closed": len(closed), "floor": min_samples})
        log.error(
            "Insufficient closed records: %d < %d. Skipping train. (Override the "
            "floor by editing training_trigger.min_new_samples in the production "
            "config.)", len(closed), min_samples)
        return 1

    X = build_input_matrix(closed)
    Y = extract_labels(closed)
    if X.shape[0] != Y.shape[0]:
        log.error("X/Y row mismatch: X=%s Y=%s — aborting", X.shape, Y.shape)
        return 1
    if X.shape[0] == 0:
        log.error("No usable records after feature extraction")
        return 1

    class_balance = {
        head: [int((Y[:, i] <= 0.5).sum()), int((Y[:, i] > 0.5).sum())]
        for i, head in enumerate(HEAD_NAMES)
    }
    log.info("class_balance | tp1=%s tp2=%s be=%s",
             class_balance["p_tp1"], class_balance["p_tp2"], class_balance["p_survives_be"])

    model, mean, std, metrics = _train_model(
        X, Y, epochs=args.epochs, lr=args.lr, batch_size=args.batch_size,
    )
    log.info("training complete | metrics=%s", metrics)

    ts = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
    version = args.version or f"v2_{args.instrument.lower()}_{ts}"
    model_dir = _REPO / "models" / args.instrument / ts
    model_path = model_dir / f"tradenet_v2_{args.instrument}_{ts}.json"
    _export_envelope(
        model, mean, std,
        instrument=args.instrument,
        version=version,
        metrics=metrics,
        n_total=len(records),
        n_closed=len(closed),
        class_balance=class_balance,
        output_path=model_path,
    )

    try:
        from core.model_registry import register_tradenet, promote_tradenet
    except Exception as exc:
        log.error("Could not import model_registry helpers: %s", exc)
        return 1

    register_tradenet(
        version=version,
        model_file=str(model_path),
        metrics=metrics,
        instrument=args.instrument,
        run_id=ts,
    )
    log.info("registered TradeNet v2 version=%s", version)

    if args.shadow:
        log.info("shadow mode — skipping promotion. Validate then run promote_tradenet manually.")
        return 0

    ok, reason = promote_tradenet(
        version, instrument=args.instrument, force=args.force_promote,
    )
    log.info("promotion result | ok=%s reason=%s", ok, reason)
    return 0 if ok else 3


if __name__ == "__main__":
    raise SystemExit(main())
