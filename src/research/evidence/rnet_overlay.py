"""MC-RNET-OVERLAY-XAUUSD-M15-V1 — y_R_net size overlay on independent entry.

Object frozen in docs/research/rnet_size_overlay_object.md. Do not retune PRIMARY after seeing y.
Not SEM-028. Not a side picker. k is PRIMARY and frozen.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from data_ingestion.dataset_integrity import validate_dataset
from research.evidence.run_close_out import finalize_run
from research.evidence.catalog import SURFACES
from research.evidence.driver import _load_cols
from research.evidence.magnitude_prior import (
    OVERLAY_K,
    _agree,
    _sign,
    _tb_sign,
    split_rows,
)
from research.evidence.asymmetry_contract import CORPUS, _parse_ts
from research.evidence.queries import _as_float_y, _col, _mean

CONTRACT_ID = "MC-RNET-OVERLAY-XAUUSD-M15-V1"
SEM_ID = "SEM-029"
K = OVERLAY_K  # 0.5 frozen; now PRIMARY for this object
OUT_DEFAULT = Path("docs/research-readiness/rnet_overlay/mc_rnet_overlay_xauusd_m15_v1")


def unit_rows(cols: dict[str, list]) -> list[dict[str, Any]]:
    """One record per (timestamp, side) with finite y_R_net. PRIMARY drops tb=0."""
    ts = _col(cols, "decision_ts", "timestamp") or []
    side = [str(s or "").lower() for s in (_col(cols, "side", "direction") or [])]
    y = _as_float_y(_col(cols, "y_R_net") or [])
    tb_raw = _col(cols, "features.trend_bias") or []
    inst = _col(cols, "instrument") or []
    rows: list[dict[str, Any]] = []
    for i, t in enumerate(ts):
        if i >= len(y) or y[i] is None:
            continue
        s = side[i] if i < len(side) else ""
        tb = _tb_sign(tb_raw[i] if i < len(tb_raw) else None)
        if tb is None:
            continue
        rows.append({
            "decision_ts": str(t),
            "ts": _parse_ts(t),
            "instrument": str(inst[i] if i < len(inst) else "XAUUSD"),
            "side": s,
            "trend_bias": tb,
            "agree": _agree(s, tb),
            "y_R_net": float(y[i]),
        })
    rows.sort(key=lambda r: (r["ts"], r["side"]))
    return rows


def overlay(rows: list[dict], k: float = K) -> dict[str, Any]:
    """Mean-preserving size overlay. PRIMARY. k frozen."""
    agree_xs: list[float] = []
    disag_xs: list[float] = []
    n_zero = 0
    for r in rows:
        if r.get("agree") is None:
            n_zero += 1
            continue
        (agree_xs if r["agree"] else disag_xs).append(float(r["y_R_net"]))
    ys = agree_xs + disag_xs
    if not ys:
        return {"k": k, "n": 0, "e_y": None, "e_w_y": None, "delta": None}
    e_y = _mean(ys)
    e_wy = (
        sum((1.0 + k) * x for x in agree_xs)
        + sum((1.0 - k) * x for x in disag_xs)
    ) / len(ys)
    ea, ed = _mean(agree_xs), _mean(disag_xs)
    return {
        "k": k,
        "n": len(ys),
        "e_y": e_y,
        "e_w_y": e_wy,
        "delta": None if e_y is None else e_wy - e_y,
        "n_trend_zero_or_unknown": n_zero,
        "agree": {
            "n": len(agree_xs),
            "mean": ea,
            "p_gt_0": (sum(1 for x in agree_xs if x > 0) / len(agree_xs)) if agree_xs else None,
        },
        "disagree": {
            "n": len(disag_xs),
            "mean": ed,
            "p_gt_0": (sum(1 for x in disag_xs if x > 0) / len(disag_xs)) if disag_xs else None,
        },
        "contrast": None if ea is None or ed is None else ea - ed,
    }


def verdict(train_o: dict, hold_o: dict) -> str:
    if hold_o.get("agree", {}).get("n", 0) < 30 or hold_o.get("disagree", {}).get("n", 0) < 30:
        return "INSUFFICIENT"
    if _sign(train_o.get("delta")) is None or _sign(hold_o.get("delta")) is None:
        return "INSUFFICIENT"
    if _sign(train_o["delta"]) == _sign(hold_o["delta"]):
        return "DIAGNOSTIC_PASS"
    return "DIAGNOSTIC_FAIL"


def fingerprint(rows: list[dict]) -> dict[str, Any]:
    h = hashlib.sha256()
    for r in rows:
        h.update(
            f"{r['instrument']}|{r['decision_ts']}|{r['side']}|{r['y_R_net']:.10f}".encode()
        )
    return {
        "contract_id": CONTRACT_ID,
        "n": len(rows),
        "sha256": h.hexdigest(),
        "population_hash_inputs": [
            "instrument", "decision_ts", "side", "y_R_net",
            "corpus_path", "corpus_sha256", "contract_id",
        ],
    }


def measure(cols: dict[str, list]) -> dict[str, Any]:
    rows = unit_rows(cols)
    train, hold, split = split_rows(rows)
    split = dict(split)
    split["k_is_primary"] = True
    split["sem028_primary_not_retuned"] = True
    split.pop("overlay_k_not_primary", None)
    tr = overlay(train)
    ho = overlay(hold)
    return {
        "contract_id": CONTRACT_ID,
        "sem_id": SEM_ID,
        "authority": "RESEARCH_ONLY",
        "economic_claims_allowed": False,
        "p_goal_04_opened": False,
        "side_picker": False,
        "k_primary": K,
        "cost_bps_baked": 12.0,
        "sem015_retuned": False,
        "train": tr,
        "holdout": ho,
        "sign_match": _sign(tr.get("delta")) == _sign(ho.get("delta")),
        "verdict": verdict(tr, ho),
        "n_units": len(rows),
        "split": split,
        "not": [
            "side picker",
            "SEM-028 y_mfe_r PRIMARY",
            "SEM-027 ΔMFE PRIMARY",
            "E>0 gate",
            "G001",
            "P-GOAL-04",
            "SEM-015 cost swap",
            "F-086 stride holdout",
            "k sweep",
            "live size overlay",
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
    p = argparse.ArgumentParser(description="MC-RNET-OVERLAY-XAUUSD-M15-V1 single-pass holdout")
    p.add_argument("--out", default=str(OUT_DEFAULT))
    args = p.parse_args()
    report = run(Path(args.out))
    print(
        f"verdict={report['verdict']} "
        f"train_delta={report['train']['delta']} "
        f"holdout_delta={report['holdout']['delta']} "
        f"holdout_e_y={report['holdout']['e_y']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
