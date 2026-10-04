"""MC-VCRTPRIOR-XAUUSD-M15-V1 — sparse Visual CRT entries x FM-054 trend prior.

Object frozen in docs/research/visual_crt_prior_object.md. Do not retune PRIMARY after seeing y.
Sparse independent SIGNAL = SEM-012 Arm A and Arm B entries (visual_crt.driver.run_arm).
Prior = SEM-028 agree rule. Not F-081 walk R. Not SEM-030 mother-range.
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
    CORPUS_SHA,
    EMBARGO_BARS,
    HOLDOUT_START,
    HORIZON_BARS,
    _parse_ts,
)
from research.evidence.catalog import SURFACES
from research.evidence.driver import _load_cols
from research.evidence.magnitude_prior import _sign, _tb_sign, _agree
from research.evidence.queries import _as_float_y, _col, _mean
from research.visual_crt.driver import ARMS, load_bars, run_arm

CONTRACT_ID = "MC-VCRTPRIOR-XAUUSD-M15-V1"
SEM_ID = "SEM-032"
OUT_DEFAULT = Path("docs/research-readiness/visual_crt_prior/mc_vcrtprior_xauusd_m15_v1")
_BAR_MINUTES = 15
VISUAL_ARMS = ARMS  # ("A", "B") — both frozen


def _ts(ts: Any) -> str:
    if isinstance(ts, str):
        return _parse_ts(ts).strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(ts, datetime):
        return ts.strftime("%Y-%m-%d %H:%M:%S")
    return str(ts)


def _label_lookup(cols: dict[str, list]) -> dict[tuple[str, str], dict[str, Any]]:
    ts_col = _col(cols, "decision_ts", "timestamp") or []
    side_col = [str(s or "").lower() for s in (_col(cols, "side", "direction") or [])]
    mfe = _as_float_y(_col(cols, "y_mfe_r", "path_mfe_r") or [])
    ttm = _as_float_y(_col(cols, "y_time_to_mfe") or [])
    tb_raw = _col(cols, "features.trend_bias") or []
    inst = _col(cols, "instrument") or []
    lookup: dict[tuple[str, str], dict[str, Any]] = {}
    for i, raw_ts in enumerate(ts_col):
        side = side_col[i] if i < len(side_col) else ""
        if side == "":
            continue
        lookup[(_ts(raw_ts), side)] = {
            "y_mfe_r": mfe[i] if i < len(mfe) else None,
            "y_time_to_mfe": ttm[i] if i < len(ttm) else None,
            "trend_bias": _tb_sign(tb_raw[i] if i < len(tb_raw) else None),
            "instrument": str(inst[i] if i < len(inst) else "XAUUSD"),
        }
    return lookup


def unit_rows(cols: dict[str, list], bars: list[Any]) -> list[dict[str, Any]]:
    if not bars:
        return []
    lookup = _label_lookup(cols)
    if not lookup:
        return []
    rows: list[dict[str, Any]] = []
    for arm in VISUAL_ARMS:
        detected = run_arm(
            bars, arm,
            instrument="XAUUSD",
            corpus_path=str(CORPUS),
            corpus_sha256=CORPUS_SHA,
        )
        for ev in detected:
            key = (_ts(ev.entry_ts), str(ev.direction).lower())
            row = lookup.get(key)
            if row is None:
                continue
            agree = _agree(str(ev.direction).lower(), row["trend_bias"])
            rows.append({
                "decision_ts": key[0],
                "ts": _parse_ts(ev.entry_ts),
                "entry_index": ev.entry_index,
                "instrument": row["instrument"],
                "side": str(ev.direction).lower(),
                "visual_arm": arm,
                "trend_bias": row["trend_bias"],
                "agree": agree,
                "y_mfe_r": row["y_mfe_r"],
                "y_time_to_mfe": row["y_time_to_mfe"],
            })
    rows.sort(key=lambda r: (r["ts"], r["visual_arm"], r["side"]))
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
        "f081_entry_fraction_oos_spent": False,
        "sparse_signal_is_sem012_entries": True,
        "sem030_not_retuned": True,
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


def _gate(train: list[dict], hold: list[dict], y_key: str) -> dict[str, Any]:
    tr = _arm_cells(train, y_key)
    ho = _arm_cells(hold, y_key)
    return {
        "y": y_key,
        "train": tr,
        "holdout": ho,
        "sign_match": _sign(tr["contrast"]) == _sign(ho["contrast"]),
        "verdict": verdict(tr, ho),
    }


def fingerprint(rows: list[dict]) -> dict[str, Any]:
    h = hashlib.sha256()
    for r in rows:
        c = r["y_mfe_r"]
        v = (
            f"{r['instrument']}|{r['decision_ts']}|{r['side']}|{r['visual_arm']}|"
            + (f"{float(c):.10f}" if c is not None else "None")
        )
        h.update(v.encode())
    return {
        "contract_id": CONTRACT_ID,
        "n": len(rows),
        "sha256": h.hexdigest(),
        "population_hash_inputs": [
            "instrument", "entry_ts", "side", "visual_arm", "y_mfe_r",
            "corpus_path", "corpus_sha256", "contract_id",
        ],
    }


def measure(cols: dict[str, list], bars: list[Any]) -> dict[str, Any]:
    rows = unit_rows(cols, bars)
    by_arm = {arm: [r for r in rows if r["visual_arm"] == arm] for arm in VISUAL_ARMS}
    split_all = split_rows(rows)
    report_arms: dict[str, Any] = {}
    for arm in VISUAL_ARMS:
        train, hold, split = split_rows(by_arm[arm])
        report_arms[arm] = {
            "n_entries": len(by_arm[arm]),
            "split": split,
            "arm_s": _gate(train, hold, "y_mfe_r"),
            "arm_t": _gate(train, hold, "y_time_to_mfe"),
        }
    return {
        "contract_id": CONTRACT_ID,
        "sem_id": SEM_ID,
        "authority": "RESEARCH_ONLY",
        "economic_claims_allowed": False,
        "p_goal_04_opened": False,
        "side_picker": False,
        "sem028_primary_not_retuned": True,
        "sem030_not_retuned": True,
        "f081_y_not_used": True,
        "visual_arms": report_arms,
        "n_entries": len(rows),
        "split": split_all[2],
        "not": [
            "trade PnL",
            "G001",
            "P-GOAL-04",
            "F-081 walk R",
            "SEM-030 mother-range",
            "SEM-029 y_R_net overlay",
            "SEM-028 every-bar agree",
            "side picker",
            "F-086 stride holdout",
            "F-081 entry-fraction OOS",
            "session/hour PRIMARY",
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
    report["provenance"] = finalize_run(CONTRACT_ID, out_dir)
    report["fingerprint_sha256"] = fp["sha256"]
    return report


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="MC-VCRTPRIOR-XAUUSD-M15-V1 single-pass holdout")
    p.add_argument("--out", default=str(OUT_DEFAULT))
    args = p.parse_args()
    report = run(Path(args.out))
    va = report["visual_arms"]
    print(
        f"A_s={va['A']['arm_s']['verdict']} A_t={va['A']['arm_t']['verdict']} "
        f"B_s={va['B']['arm_s']['verdict']} B_t={va['B']['arm_t']['verdict']} "
        f"n_entries={report['n_entries']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
