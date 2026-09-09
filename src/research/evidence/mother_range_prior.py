"""MC-MRPRIOR-XAUUSD-M15-V1 — sparse mother-range inside signal x FM-054 trend prior.

Object frozen in docs/research/mother_range_prior_object.md. Do not retune PRIMARY after seeing y.
P-EVID-01: the sparse independent SIGNAL is the causal SEM-026 mother inside-close entry set
(not every-bar x side, the F-092/F-093 grain that collapsed); the prior is the SEM-028 agree rule.
Not SEM-026 trade ledger (no walk, no SL/TP).
"""
from __future__ import annotations

import csv
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
from research.evidence.magnitude_prior import _sign, _tb_sign, _agree
from research.evidence.queries import _as_float_y, _col, _mean
from research.mother_range.geometry import Bar, detect_inside_close_entries

CONTRACT_ID = "MC-MRPRIOR-XAUUSD-M15-V1"
SEM_ID = "SEM-030"
OUT_DEFAULT = Path("docs/research-readiness/mother_range_prior/mc_mrprior_xauusd_m15_v1")
_BAR_MINUTES = 15


def load_bars(path: Path) -> list[Bar]:
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    bars: list[Bar] = []
    for i, row in enumerate(rows):
        bars.append(Bar(
            timestamp=_parse_ts(row["timestamp"]),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row["volume"]),
            index=i,
        ))
    return bars


def _ts(ts: Any) -> str:
    """Normalize a decision/entry timestamp to 'YYYY-MM-DD HH:MM:SS'."""
    if isinstance(ts, str):
        return _parse_ts(ts).strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(ts, datetime):
        return ts.strftime("%Y-%m-%d %H:%M:%S")
    return str(ts)


def unit_rows(cols: dict[str, list], bars: list[Any]) -> list[dict[str, Any]]:
    ts_col = _col(cols, "decision_ts", "timestamp") or []
    side_col = [str(s or "").lower() for s in (_col(cols, "side", "direction") or [])]
    mfe = _as_float_y(_col(cols, "y_mfe_r", "path_mfe_r") or [])
    ttm = _as_float_y(_col(cols, "y_time_to_mfe") or [])
    tb_raw = _col(cols, "features.trend_bias") or []
    inst = _col(cols, "instrument") or []

    if not ts_col:
        return []

    n = len(ts_col)
    lookup: dict[tuple[str, str], dict[str, Any]] = {}
    for i in range(n):
        key = (_ts(ts_col[i]), side_col[i] if i < len(side_col) else "")
        if key[1] == "":
            continue
        lookup[key] = {
            "y_mfe_r": mfe[i] if i < len(mfe) else None,
            "y_time_to_mfe": ttm[i] if i < len(ttm) else None,
            "trend_bias": _tb_sign(tb_raw[i] if i < len(tb_raw) else None),
            "instrument": str(inst[i] if i < len(inst) else "XAUUSD"),
            "decision_ts": str(ts_col[i]),
        }

    detected = detect_inside_close_entries(bars)
    rows: list[dict[str, Any]] = []
    for ev in detected:
        key = (_ts(ev.timestamp), str(ev.direction).lower())
        row = lookup.get(key)
        if row is None:
            continue
        agree = _agree(str(ev.direction).lower(), row["trend_bias"])
        rows.append({
            "decision_ts": _ts(ev.timestamp),
            "ts": ev.timestamp,
            "entry_index": ev.entry_index,
            "instrument": row["instrument"],
            "side": str(ev.direction).lower(),
            "trend_bias": row["trend_bias"],
            "agree": agree,
            "y_mfe_r": row["y_mfe_r"],
            "y_time_to_mfe": row["y_time_to_mfe"],
        })
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
        "sem030_primary_not_retuned": True,
        "sparse_signal_is_sem026_entries": True,
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
    return {
        "agree": {
            "n": len(agree_xs),
            "mean": ea,
            "p_gt_0": (sum(1 for x in agree_xs if x > 0) / len(agree_xs)) if agree_xs else None,
            "e_given_gt_0": _mean([x for x in agree_xs if x > 0]),
        },
        "disagree": {
            "n": len(disag_xs),
            "mean": ed,
            "p_gt_0": (sum(1 for x in disag_xs if x > 0) / len(disag_xs)) if disag_xs else None,
            "e_given_gt_0": _mean([x for x in disag_xs if x > 0]),
        },
        "contrast": None if ea is None or ed is None else ea - ed,
        "n_trend_zero_or_unknown": n_zero,
        "n_null_y": n_null_y,
    }


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
        c = r["y_mfe_r"]
        v = f"{r['instrument']}|{r['decision_ts']}|{r['side']}|" + (
            f"{float(c):.10f}" if c is not None else "None"
        )
        h.update(v.encode())
    return {
        "contract_id": CONTRACT_ID,
        "n": len(rows),
        "sha256": h.hexdigest(),
        "population_hash_inputs": [
            "instrument", "entry_ts", "side", "y_mfe_r",
            "corpus_path", "corpus_sha256", "contract_id",
        ],
    }


def measure(cols: dict[str, list], bars: list[Any]) -> dict[str, Any]:
    rows = unit_rows(cols, bars)
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
        "sem028_primary_not_retuned": True,
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
        "n_entries": len(rows),
        "split": split,
        "not": [
            "trade PnL",
            "G001",
            "P-GOAL-04",
            "SEM-026 ledger SL/TP walk",
            "SEM-029 y_R_net overlay",
            "SEM-028 every-bar agree",
            "side picker",
            "F-086 stride holdout",
            "session/hour PRIMARY",
            "xauusd_identity_l5",
        ],
    }


def run(out_dir: Path | None = None) -> dict[str, Any]:
    out_dir = out_dir or OUT_DEFAULT
    validate_dataset(str(CORPUS))
    cols = _load_cols(SURFACES["clean_labels"], None)
    bars = load_bars(CORPUS)
    report = measure(cols, bars)
    rows = unit_rows(cols, bars)
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
    p = argparse.ArgumentParser(description="MC-MRPRIOR-XAUUSD-M15-V1 single-pass holdout")
    p.add_argument("--out", default=str(OUT_DEFAULT))
    args = p.parse_args()
    report = run(Path(args.out))
    print(
        f"arm_s={report['arm_s']['verdict']} "
        f"arm_t={report['arm_t']['verdict']} "
        f"holdout_s_contrast={report['arm_s']['holdout']['contrast']} "
        f"holdout_t_contrast={report['arm_t']['holdout']['contrast']} "
        f"n_entries={report['n_entries']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())