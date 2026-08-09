"""Envelope shadow weight-0 logging — ENV_SHADOW_W0_V1.

Batch observe-only. Never imported by EngineRunner / Fusion / Planner.
Every emitted line hard-codes decision_weight=0.0.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import joblib
import numpy as np

from research.envelope_offline.train import HEADS, HEAD_KEYS

SHADOW_CHARTER_ID = "ENV_SHADOW_W0_V1"
TRAIN_CHARTER_ID = "ENV_OFFLINE_TRAIN_V1"
REQUIRED_PROTOCOL = "TN_ENV_CLEAN_L2"
ALLOWED_ROLLUPS = frozenset({"SIGNAL_RETAINED", "SIGNAL_WEAK"})
HEAD_PRED_KEYS = tuple(HEAD_KEYS[h] for h in HEADS)


@dataclass
class ShadowConfig:
    bundle_dir: str
    dataset_path: str
    out_dir: str
    instrument: str = "BNBUSDT"
    max_rows: int | None = None


def _spearman(a: np.ndarray, b: np.ndarray) -> float | None:
    m = np.isfinite(a) & np.isfinite(b)
    if int(m.sum()) < 30:
        return None
    aa, bb = a[m], b[m]
    ra = aa.argsort().argsort().astype(float)
    rb = bb.argsort().argsort().astype(float)
    ra -= ra.mean()
    rb -= rb.mean()
    den = float(np.sqrt((ra ** 2).sum() * (rb ** 2).sum()))
    if den <= 0:
        return None
    return float((ra * rb).sum() / den)


def load_shadow_bundle(bundle_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load envelope_bundle.json + head models. Validates charter gates."""
    bundle_dir = Path(bundle_dir)
    bundle_path = bundle_dir / "envelope_bundle.json"
    if not bundle_path.is_file():
        raise FileNotFoundError(f"missing envelope_bundle.json under {bundle_dir}")
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    if bundle.get("charter_id") != TRAIN_CHARTER_ID:
        raise ValueError(
            f"bundle charter_id={bundle.get('charter_id')!r} != {TRAIN_CHARTER_ID}"
        )
    rollup = bundle.get("signal_rollup")
    if rollup not in ALLOWED_ROLLUPS:
        raise ValueError(
            f"bundle signal_rollup={rollup!r} not in {sorted(ALLOWED_ROLLUPS)}"
        )
    if bundle.get("required_protocol") not in (None, REQUIRED_PROTOCOL):
        # train bundle stamps required_protocol
        if bundle.get("dataset_protocol_id") not in (None, REQUIRED_PROTOCOL):
            raise ValueError(
                f"bundle protocol mismatch: {bundle.get('dataset_protocol_id')}"
            )

    models: dict[str, Any] = {}
    for key in HEAD_PRED_KEYS:
        rel = bundle["head_artifacts"].get(key)
        if not rel:
            raise ValueError(f"bundle missing head artifact for {key}")
        path = Path(rel)
        if not path.is_file():
            # try relative to bundle_dir
            path = bundle_dir / f"head_{key}.joblib"
        if not path.is_file():
            raise FileNotFoundError(f"head artifact not found: {rel}")
        payload = joblib.load(path)
        models[key] = payload["model"]
    return bundle, models


def predict_heads(models: dict[str, Any], feature_vector: list[float] | np.ndarray) -> dict[str, float]:
    x = np.asarray(feature_vector, dtype=np.float64).reshape(1, -1)
    if x.shape[1] != 38:
        raise ValueError(f"expected 38 features, got {x.shape[1]}")
    return {key: float(models[key].predict(x)[0]) for key in HEAD_PRED_KEYS}


def _actuals_from_row(row: dict) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for h, key in HEAD_KEYS.items():
        v = row.get(h)
        if v is None:
            out[key] = None
        else:
            try:
                fv = float(v)
                out[key] = fv if math.isfinite(fv) else None
            except (TypeError, ValueError):
                out[key] = None
    return out


def iter_shadow_lines(
    dataset_path: Path,
    models: dict[str, Any],
    bundle: dict[str, Any],
    *,
    instrument: str,
    max_rows: int | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield weight-0 shadow records. Never mutates decision state."""
    n = 0
    with dataset_path.open(encoding="utf-8") as fh:
        for line in fh:
            if max_rows is not None and n >= max_rows:
                break
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            vec = row.get("feature_vector")
            if not isinstance(vec, list) or len(vec) != 38:
                continue
            try:
                pred = predict_heads(models, vec)
            except Exception as exc:  # noqa: BLE001
                yield {
                    "kind": "envelope_shadow_w0_error",
                    "charter_id": SHADOW_CHARTER_ID,
                    "error": f"{type(exc).__name__}: {exc}",
                    "decision_weight": 0.0,
                    "fusion_weight": 0.0,
                    "planner_influence": False,
                    "spine_consumed": False,
                }
                n += 1
                continue

            rec = {
                "kind": "envelope_shadow_w0",
                "charter_id": SHADOW_CHARTER_ID,
                "train_charter_id": TRAIN_CHARTER_ID,
                "protocol_id": REQUIRED_PROTOCOL,
                "instrument": instrument,
                "unit_id": row.get("unit_id"),
                "decision_ts": row.get("decision_ts"),
                "entry_index": row.get("entry_index"),
                "side": row.get("side"),
                "pred": pred,
                "actual": _actuals_from_row(row),
                "decision_weight": 0.0,
                "fusion_weight": 0.0,
                "planner_influence": False,
                "spine_consumed": False,
                "bundle_dataset_protocol_hash": bundle.get("dataset_protocol_hash"),
                "train_signal_rollup": bundle.get("signal_rollup"),
            }
            # hard invariants
            assert rec["decision_weight"] == 0.0
            assert rec["fusion_weight"] == 0.0
            assert rec["planner_influence"] is False
            assert rec["spine_consumed"] is False
            yield rec
            n += 1


def run_shadow(cfg: ShadowConfig) -> dict[str, Any]:
    """Write shadow.jsonl + summary.json. Returns summary dict."""
    bundle_dir = Path(cfg.bundle_dir)
    dataset_path = Path(cfg.dataset_path)
    out_dir = Path(cfg.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    bundle, models = load_shadow_bundle(bundle_dir)
    shadow_path = out_dir / "shadow.jsonl"

    preds: dict[str, list[float]] = {k: [] for k in HEAD_PRED_KEYS}
    actuals: dict[str, list[float]] = {k: [] for k in HEAD_PRED_KEYS}
    n_ok = 0
    n_err = 0
    weight_violations = 0

    with shadow_path.open("w", encoding="utf-8") as out:
        for rec in iter_shadow_lines(
            dataset_path,
            models,
            bundle,
            instrument=cfg.instrument,
            max_rows=cfg.max_rows,
        ):
            # stamp bundle path once written
            rec["bundle_dir"] = str(bundle_dir)
            if rec.get("decision_weight") != 0.0 or rec.get("fusion_weight") != 0.0:
                weight_violations += 1
            if rec.get("kind") == "envelope_shadow_w0_error":
                n_err += 1
            else:
                n_ok += 1
                for k in HEAD_PRED_KEYS:
                    preds[k].append(float(rec["pred"][k]))
                    av = rec["actual"].get(k)
                    if av is not None:
                        actuals[k].append(float(av))
                    else:
                        actuals[k].append(float("nan"))
            out.write(json.dumps(rec, default=str) + "\n")

    cal: dict[str, Any] = {}
    all_ic_pos = True
    for k in HEAD_PRED_KEYS:
        p = np.asarray(preds[k], dtype=float)
        a = np.asarray(actuals[k], dtype=float)
        ic = _spearman(p, a)
        cal[k] = {
            "n_pred": int(len(p)),
            "spearman_ic_vs_actual": None if ic is None else round(ic, 4),
            "pred_mean": round(float(np.mean(p)), 6) if len(p) else None,
            "actual_mean": round(float(np.nanmean(a)), 6) if len(a) else None,
        }
        if ic is None or ic <= 0:
            all_ic_pos = False

    if weight_violations > 0:
        status = "SHADOW_FAIL"
    elif n_ok == 0:
        status = "SHADOW_FAIL"
    else:
        status = "SHADOW_COMPLETE"

    summary = {
        "charter_id": SHADOW_CHARTER_ID,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "calibration_ok": bool(all_ic_pos and n_ok > 0),
        "instrument": cfg.instrument,
        "bundle_dir": str(bundle_dir),
        "dataset_path": str(dataset_path),
        "shadow_path": str(shadow_path),
        "n_ok": n_ok,
        "n_err": n_err,
        "weight_violations": weight_violations,
        "train_signal_rollup": bundle.get("signal_rollup"),
        "dataset_protocol_hash": bundle.get("dataset_protocol_hash"),
        "calibration": cal,
        "authority": {
            "decision_weight": 0.0,
            "fusion_weight": 0.0,
            "planner_influence": False,
            "spine_consumed": False,
            "production": False,
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "report.md").write_text(_render(summary), encoding="utf-8")
    return summary


def _render(s: dict) -> str:
    lines = [
        f"# Envelope Shadow Weight-0 — {s['charter_id']}",
        "",
        f"| Field | Value |",
        f"|-------|--------|",
        f"| created | {s['created_utc']} |",
        f"| status | **{s['status']}** |",
        f"| calibration_ok | {s['calibration_ok']} |",
        f"| n_ok | {s['n_ok']} |",
        f"| n_err | {s['n_err']} |",
        f"| weight_violations | {s['weight_violations']} |",
        f"| decision_weight | **0.0** (hard) |",
        f"| spine_consumed | **false** |",
        "",
        "## Calibration vs clean actuals (diagnostic)",
        "",
        "| Head | Spearman IC | pred_mean | actual_mean |",
        "|------|-------------|-----------|-------------|",
    ]
    for k, c in s["calibration"].items():
        lines.append(
            f"| `{k}` | {c['spearman_ic_vs_actual']} | {c['pred_mean']} | {c['actual_mean']} |"
        )
    lines += [
        "",
        "## Non-claims",
        "",
        "- Zero decision / fusion / planner influence",
        "- Not ENV-P, not production KEEP",
        "- Not a TradeNet reopen",
        "",
    ]
    return "\n".join(lines)
