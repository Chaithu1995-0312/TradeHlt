"""MC-MAGPRIOR-XAUUSD-M15-V1 — trend_bias as magnitude/time prior on a given side.

Object frozen in docs/research/magnitude_prior_object.md. Do not retune PRIMARY after seeing y.
Not SEM-027. Not a side picker.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from data_ingestion.dataset_integrity import validate_dataset
from research.evidence.run_close_out import finalize_run
from research.evidence.asymmetry_contract import (
    CORPUS,
    EMBARGO_BARS,
    HOLDOUT_START,
    HORIZON_BARS,
    _parse_ts,
)
from research.evidence.catalog import SURFACES
from research.evidence.driver import _load_cols
from research.evidence.queries import _as_float_y, _col, _mean

CONTRACT_ID = "MC-MAGPRIOR-XAUUSD-M15-V1"
SEM_ID = "SEM-028"
OUT_DEFAULT = Path("docs/research-readiness/magnitude_prior/mc_magprior_xauusd_m15_v1")
OVERLAY_K = 0.5  # frozen diagnostic; not PRIMARY
_BAR_MINUTES = 15


def _tb_sign(raw: Any) -> int | None:
    if raw is None:
        return None
    try:
        x = float(raw)
    except (TypeError, ValueError):
        return None
    if x != x or x == 0:
        return 0
    return 1 if x > 0 else -1


def _agree(side: str, tb: int) -> bool | None:
    if tb == 0:
        return None
    if side == "long":
        return tb == 1
    if side == "short":
        return tb == -1
    return None


def unit_rows(cols: dict[str, list]) -> list[dict[str, Any]]:
    """One record per (timestamp, side) with finite y_mfe_r. PRIMARY drops tb=0."""
    ts = _col(cols, "decision_ts", "timestamp") or []
    side = [str(s or "").lower() for s in (_col(cols, "side", "direction") or [])]
    mfe = _as_float_y(_col(cols, "y_mfe_r", "path_mfe_r") or [])
    ttm = _as_float_y(_col(cols, "y_time_to_mfe") or [])
    tb_raw = _col(cols, "features.trend_bias") or []
    inst = _col(cols, "instrument") or []
    rows: list[dict[str, Any]] = []
    n = len(ts)
    for i in range(n):
        if i >= len(mfe) or mfe[i] is None:
            continue
        s = side[i] if i < len(side) else ""
        tb = _tb_sign(tb_raw[i] if i < len(tb_raw) else None)
        if tb is None:
            continue
        agree = _agree(s, tb)
        rec = {
            "decision_ts": str(ts[i]),
            "ts": _parse_ts(ts[i]),
            "instrument": str(inst[i] if i < len(inst) else "XAUUSD"),
            "side": s,
            "trend_bias": tb,
            "agree": agree,
            "y_mfe_r": float(mfe[i]),
            "y_time_to_mfe": ttm[i] if i < len(ttm) else None,
        }
        rows.append(rec)
    rows.sort(key=lambda r: (r["ts"], r["side"]))
    return rows


def split_rows(rows: list[dict[str, Any]]) -> tuple[list[dict], list[dict], dict]:
    embargo = timedelta(minutes=_BAR_MINUTES * EMBARGO_BARS)
    purge = timedelta(minutes=_BAR_MINUTES * HORIZON_BARS)
    train_last = HOLDOUT_START - max(embargo, purge)
    train = [r for r in rows if r["ts"] <= train_last]
    hold = [r for r in rows if r["ts"] >= HOLDOUT_START]
    dropped = [r for r in rows if train_last < r["ts"] < HOLDOUT_START]
    manifest = {
        "holdout_start": HOLDOUT_START.isoformat(sep=" "),
        "train_last_allowed": train_last.isoformat(sep=" "),
        "embargo_bars": EMBARGO_BARS,
        "purge_horizon_bars": HORIZON_BARS,
        "n_train": len(train),
        "n_holdout": len(hold),
        "n_embargo_dropped": len(dropped),
        "f086_stride_spent": False,
        "sem027_primary_not_retuned": True,
        "overlay_k_not_primary": OVERLAY_K,
    }
    return train, hold, manifest


def _arm_cells(rows: list[dict], y_key: str) -> dict[str, Any]:
    agree_xs: list[float] = []
    disag_xs: list[float] = []
    n_zero = 0
    n_null_y = 0
    for r in rows:
        y = r.get(y_key)
        if y is None:
            n_null_y += 1
            continue
        if r.get("agree") is None:
            n_zero += 1
            continue
        (agree_xs if r["agree"] else disag_xs).append(float(y))
    ea, ed = _mean(agree_xs), _mean(disag_xs)
    contrast = None if ea is None or ed is None else ea - ed
    pos_a = [x for x in agree_xs if x > 0]
    pos_d = [x for x in disag_xs if x > 0]
    return {
        "agree": {
            "n": len(agree_xs),
            "mean": ea,
            "p_gt_0": (sum(1 for x in agree_xs if x > 0) / len(agree_xs)) if agree_xs else None,
            "e_given_gt_0": _mean(pos_a),
        },
        "disagree": {
            "n": len(disag_xs),
            "mean": ed,
            "p_gt_0": (sum(1 for x in disag_xs if x > 0) / len(disag_xs)) if disag_xs else None,
            "e_given_gt_0": _mean(pos_d),
        },
        "contrast": contrast,
        "n_trend_zero_or_unknown": n_zero,
        "n_null_y": n_null_y,
    }


def overlay_weighted_mean(rows: list[dict], k: float = OVERLAY_K) -> dict[str, Any]:
    """Diagnostic size overlay. Not PRIMARY. k frozen."""
    ys: list[float] = []
    ws: list[float] = []
    for r in rows:
        if r.get("agree") is None:
            continue
        y = r.get("y_mfe_r")
        if y is None:
            continue
        w = (1.0 + k) if r["agree"] else (1.0 - k)
        ys.append(float(y))
        ws.append(w)
    if not ys:
        return {"k": k, "n": 0, "e_y": None, "e_w_y": None}
    e_y = _mean(ys)
    e_wy = sum(w * y for w, y in zip(ws, ys)) / len(ys)
    return {"k": k, "n": len(ys), "e_y": e_y, "e_w_y": e_wy, "delta": None if e_y is None else e_wy - e_y}


def _sign(x: float | None) -> int | None:
    if x is None:
        return None
    if x > 0:
        return 1
    if x < 0:
        return -1
    return 0


def verdict(train_c: dict, hold_c: dict) -> str:
    if hold_c["agree"]["n"] < 30 or hold_c["disagree"]["n"] < 30:
        return "INSUFFICIENT"
    if _sign(train_c["contrast"]) is None or _sign(hold_c["contrast"]) is None:
        return "INSUFFICIENT"
    if _sign(train_c["contrast"]) == _sign(hold_c["contrast"]):
        return "DIAGNOSTIC_PASS"
    return "DIAGNOSTIC_FAIL"


def fingerprint(rows: list[dict]) -> dict[str, Any]:
    h = hashlib.sha256()
    for r in rows:
        h.update(
            f"{r['instrument']}|{r['decision_ts']}|{r['side']}|{r['y_mfe_r']:.10f}".encode()
        )
    return {
        "contract_id": CONTRACT_ID,
        "n": len(rows),
        "sha256": h.hexdigest(),
        "population_hash_inputs": [
            "instrument", "decision_ts", "side", "y_mfe_r",
            "corpus_path", "corpus_sha256", "contract_id",
        ],
    }


def measure(cols: dict[str, list]) -> dict[str, Any]:
    rows = unit_rows(cols)
    train, hold, split = split_rows(rows)
    tr_s = _arm_cells(train, "y_mfe_r")
    ho_s = _arm_cells(hold, "y_mfe_r")
    tr_t = _arm_cells(train, "y_time_to_mfe")
    ho_t = _arm_cells(hold, "y_time_to_mfe")
    return {
        "contract_id": CONTRACT_ID,
        "sem_id": SEM_ID,
        "authority": "RESEARCH_ONLY",
        "economic_claims_allowed": False,
        "p_goal_04_opened": False,
        "side_picker": False,
        "sem027_primary_retuned": False,
        "arm_s": {
            "y": "y_mfe_r",
            "train": tr_s,
            "holdout": ho_s,
            "sign_match": _sign(tr_s["contrast"]) == _sign(ho_s["contrast"]),
            "verdict": verdict(tr_s, ho_s),
        },
        "arm_t": {
            "y": "y_time_to_mfe",
            "train": tr_t,
            "holdout": ho_t,
            "sign_match": _sign(tr_t["contrast"]) == _sign(ho_t["contrast"]),
            "verdict": verdict(tr_t, ho_t),
        },
        "overlay_diagnostic": {
            "train": overlay_weighted_mean(train),
            "holdout": overlay_weighted_mean(hold),
            "not_primary": True,
        },
        "n_units": len(rows),
        "split": split,
        "not": [
            "side picker",
            "SEM-027 ΔMFE PRIMARY",
            "trade PnL",
            "G001",
            "P-GOAL-04",
            "y_R_net size overlay",
            "F-086 stride holdout",
            "session/hour PRIMARY",
            "overlay k as PRIMARY",
        ],
    }


def run(out_dir: Path | None = None) -> dict[str, Any]:
    out_dir = out_dir or OUT_DEFAULT
    validate_dataset(str(CORPUS))
    cols = _load_cols(SURFACES["clean_labels"], None)
    report = measure(cols)
    rows = unit_rows(cols)
    out_dir.mkdir(parents=True, exist_ok=True)
    fp = fingerprint(rows)
    (out_dir / "population_fingerprint.json").write_text(
        json.dumps(fp, indent=2), encoding="utf-8"
    )
    (out_dir / "split_manifest.json").write_text(
        json.dumps(report["split"], indent=2), encoding="utf-8"
    )
    (out_dir / "metrics.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )
    # mt00/mt01/run_manifest: measured, not asserted. See research/evidence/provenance.py for why
    # the previous hardcoded {"status": "UNRUN"} write was a silent gap rather than an honest one.
    report["provenance"] = finalize_run(CONTRACT_ID, out_dir)
    report["fingerprint_sha256"] = fp["sha256"]
    return report


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="MC-MAGPRIOR-XAUUSD-M15-V1 single-pass holdout")
    p.add_argument("--out", default=str(OUT_DEFAULT))
    args = p.parse_args()
    report = run(Path(args.out))
    print(
        f"arm_s={report['arm_s']['verdict']} "
        f"arm_t={report['arm_t']['verdict']} "
        f"holdout_s_contrast={report['arm_s']['holdout']['contrast']} "
        f"holdout_t_contrast={report['arm_t']['holdout']['contrast']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
