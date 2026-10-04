"""MC-ASYM-XAUUSD-M15-V1 — same-timestamp ΔMFE holdout.

Object frozen in docs/research/asymmetry_object.md. Do not retune PRIMARY after seeing y.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from data_ingestion.dataset_integrity import validate_dataset
from research.evidence.run_close_out import finalize_run
from research.evidence.catalog import SURFACES
from research.evidence.driver import _load_cols
from research.evidence.queries import _as_float_y, _col, _mean

CONTRACT_ID = "MC-ASYM-XAUUSD-M15-V1"
SEM_ID = "SEM-027"
HORIZON_BARS = 40
EMBARGO_BARS = 96
HOLDOUT_START = datetime(2025, 12, 24, 19, 15, 0)
CORPUS = Path("data/mt5/XAUUSD_M15.csv")
CORPUS_SHA = "4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56"
OUT_DEFAULT = Path("docs/research-readiness/asymmetry/mc_asym_xauusd_m15_v1")

_BAR_MINUTES = 15


def _parse_ts(raw: Any) -> datetime:
    s = str(raw).strip().replace("T", " ")
    return datetime.fromisoformat(s[:19])


def pair_rows(cols: dict[str, list]) -> list[dict[str, Any]]:
    """One record per timestamp that has both long and short y_mfe_r."""
    ts = _col(cols, "decision_ts", "timestamp") or []
    side = [str(s or "").lower() for s in (_col(cols, "side", "direction") or [])]
    mfe = _as_float_y(_col(cols, "y_mfe_r", "path_mfe_r") or [])
    tb = _col(cols, "features.trend_bias") or []
    sess = _col(cols, "features.session") or []
    vol = _col(cols, "features.volatility_regime") or []
    inst = _col(cols, "instrument") or []
    by: dict[str, dict[str, int]] = {}
    for i, t in enumerate(ts):
        by.setdefault(str(t), {})[side[i] if i < len(side) else ""] = i
    pairs: list[dict[str, Any]] = []
    for t, d in by.items():
        if "long" not in d or "short" not in d:
            continue
        li, si = d["long"], d["short"]
        if li >= len(mfe) or si >= len(mfe):
            continue
        if mfe[li] is None or mfe[si] is None:
            continue
        pairs.append({
            "decision_ts": t,
            "ts": _parse_ts(t),
            "instrument": str(inst[li] if li < len(inst) else "XAUUSD"),
            "delta_mfe": float(mfe[li]) - float(mfe[si]),
            "trend_bias": tb[li] if li < len(tb) else None,
            "session": sess[li] if li < len(sess) else None,
            "volatility": vol[li] if li < len(vol) else None,
        })
    pairs.sort(key=lambda r: r["ts"])
    return pairs


def split_pairs(pairs: list[dict[str, Any]]) -> tuple[list[dict], list[dict], dict]:
    embargo = timedelta(minutes=_BAR_MINUTES * EMBARGO_BARS)
    purge = timedelta(minutes=_BAR_MINUTES * HORIZON_BARS)
    train_last = HOLDOUT_START - max(embargo, purge)
    train = [p for p in pairs if p["ts"] <= train_last]
    hold = [p for p in pairs if p["ts"] >= HOLDOUT_START]
    dropped = [
        p for p in pairs
        if train_last < p["ts"] < HOLDOUT_START
    ]
    manifest = {
        "holdout_start": HOLDOUT_START.isoformat(sep=" "),
        "train_last_allowed": train_last.isoformat(sep=" "),
        "embargo_bars": EMBARGO_BARS,
        "purge_horizon_bars": HORIZON_BARS,
        "n_train": len(train),
        "n_holdout": len(hold),
        "n_embargo_dropped": len(dropped),
        "f086_stride_spent": False,
        "full_sample_atlas_is_not_this_split": True,
    }
    return train, hold, manifest


def _cell_mean(rows: list[dict], key: str, value: Any) -> dict[str, Any]:
    xs = [r["delta_mfe"] for r in rows if r.get(key) is not None and float(r[key]) == float(value)]
    return {"n": len(xs), "e_delta_mfe": _mean(xs)}


def contrast_trend_bias(rows: list[dict]) -> dict[str, Any]:
    pos = _cell_mean(rows, "trend_bias", 1.0)
    neg = _cell_mean(rows, "trend_bias", -1.0)
    c = None
    if pos["e_delta_mfe"] is not None and neg["e_delta_mfe"] is not None:
        c = pos["e_delta_mfe"] - neg["e_delta_mfe"]
    return {"plus": pos, "minus": neg, "contrast": c}


def _sign(x: float | None) -> int | None:
    if x is None:
        return None
    if x > 0:
        return 1
    if x < 0:
        return -1
    return 0


def verdict(train_c: dict, hold_c: dict, n_hold: int) -> str:
    if n_hold < 30 or hold_c["plus"]["n"] < 30 or hold_c["minus"]["n"] < 30:
        return "INSUFFICIENT"
    if _sign(train_c["contrast"]) is None or _sign(hold_c["contrast"]) is None:
        return "INSUFFICIENT"
    if _sign(train_c["contrast"]) == _sign(hold_c["contrast"]):
        return "DIAGNOSTIC_PASS"
    return "DIAGNOSTIC_FAIL"


def fingerprint(pairs: list[dict]) -> dict[str, Any]:
    h = hashlib.sha256()
    for p in pairs:
        h.update(f"{p['instrument']}|{p['decision_ts']}|{p['delta_mfe']:.10f}".encode())
    return {
        "contract_id": CONTRACT_ID,
        "n": len(pairs),
        "sha256": h.hexdigest(),
        "population_hash_inputs": [
            "instrument", "decision_ts", "delta_mfe",
            "corpus_path", "corpus_sha256", "contract_id",
        ],
    }


def measure(cols: dict[str, list]) -> dict[str, Any]:
    pairs = pair_rows(cols)
    train, hold, split = split_pairs(pairs)
    tr = contrast_trend_bias(train)
    ho = contrast_trend_bias(hold)
    v = verdict(tr, ho, len(hold))
    return {
        "contract_id": CONTRACT_ID,
        "sem_id": SEM_ID,
        "authority": "RESEARCH_ONLY",
        "economic_claims_allowed": False,
        "verdict": v,
        "n_pairs": len(pairs),
        "train": {
            "n": len(train),
            "e_delta_mfe": _mean([p["delta_mfe"] for p in train]),
            "trend_bias": tr,
        },
        "holdout": {
            "n": len(hold),
            "e_delta_mfe": _mean([p["delta_mfe"] for p in hold]),
            "trend_bias": ho,
        },
        "sign_match": _sign(tr["contrast"]) == _sign(ho["contrast"]),
        "split": split,
        "diagnostic_cells": {
            "session_holdout": {
                str(s): _cell_mean(hold, "session", s)
                for s in sorted({r["session"] for r in hold if r["session"] is not None})
            },
            "volatility_holdout": {
                str(s): _cell_mean(hold, "volatility", s)
                for s in sorted({r["volatility"] for r in hold if r["volatility"] is not None})
            },
        },
        "not": [
            "trade PnL",
            "G001",
            "full-sample atlas as this holdout",
            "F-086 stride holdout",
            "session/hour PRIMARY",
        ],
    }


def run(out_dir: Path | None = None) -> dict[str, Any]:
    out_dir = out_dir or OUT_DEFAULT
    validate_dataset(str(CORPUS))
    cols = _load_cols(SURFACES["clean_labels"], None)
    report = measure(cols)
    pairs = pair_rows(cols)
    out_dir.mkdir(parents=True, exist_ok=True)
    fp = fingerprint(pairs)
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
    p = argparse.ArgumentParser(description="MC-ASYM-XAUUSD-M15-V1 single-pass holdout")
    p.add_argument("--out", default=str(OUT_DEFAULT))
    args = p.parse_args()
    report = run(Path(args.out))
    print(
        f"verdict={report['verdict']} holdout_n={report['holdout']['n']} "
        f"train_contrast={report['train']['trend_bias']['contrast']} "
        f"holdout_contrast={report['holdout']['trend_bias']['contrast']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
