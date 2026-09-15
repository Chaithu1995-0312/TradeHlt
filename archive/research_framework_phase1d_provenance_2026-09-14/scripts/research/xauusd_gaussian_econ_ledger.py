#!/usr/bin/env python3
"""
xauusd_gaussian_econ_ledger.py — Phase E1
=========================================
Economic ledger on E0 scored units (pre-registered arms).

Design: docs/implementation_plan/xauusd-gaussian-toward-economics-2026-07-23.md §E1

Pre-registered (frozen before run — do not retune after seeing OOS):
  * exit_model = intrabar_fixed, max_forward = 40
  * cost = 12 bps (CostModel)
  * SL/TP arm A = 1.0 / 1.0 ATR (same as train label geometry)
  * score quantiles p10/p90 computed on TRAIN split only
  * arms: all_units, nb_top_decile, nb_bottom_decile, random_match_n,
          long_only, short_only
  * RNG seed for random arm: hash of "xauusd_gaussian_e1_v1"
  * kill: OOS top_decile E[R] <= OOS all_units AND <= OOS random → NO_SKILL

Authority: RESEARCH_ONLY. Not M4. Not ΔG001. Not production wire.

Usage:
  python scripts/research/xauusd_gaussian_econ_ledger.py
  python scripts/research/xauusd_gaussian_econ_ledger.py \\
      --units results/gaussian_xauusd_econ/units_LATEST.jsonl
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

INSTRUMENT = "XAUUSD"
PHASE = "E1_ECONOMIC_LEDGER"
PROTOCOL_ID = "xauusd_gaussian_e1_v1"
AUTHORITY = (
    "RESEARCH_ONLY — E1 economic measurement only; not M4 PROMOTE; "
    "not ΔG001; REGISTRY_ACTIVE ≠ ECONOMIC_AUTHORITY"
)

# ── pre-registered constants (frozen) ──────────────────────────────────
EXIT_MODEL = "intrabar_fixed"
MAX_FORWARD = 40
COST_BPS = 12.0
SL_ATR_MULT = 1.0
TP_ATR_MULT = 1.0
QUANTILE_LOW = 10.0   # train-only
QUANTILE_HIGH = 90.0  # train-only
DEFAULT_UNITS = "results/gaussian_xauusd_econ/units_LATEST.jsonl"
DEFAULT_CORPUS = "data/mt5/XAUUSD_M15.csv"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _seed_u32(s: str) -> int:
    return int(hashlib.sha256(s.encode("utf-8")).hexdigest()[:8], 16)


@dataclass
class Bar:
    index: int
    timestamp: Any
    open: float
    high: float
    low: float
    close: float
    volume: float


def load_units(path: Path) -> list[dict]:
    units = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            units.append(json.loads(line))
    units.sort(key=lambda u: (u["timestamp"], u["direction"], u.get("journal_line", 0)))
    return units


def train_quantiles(units: list[dict]) -> dict:
    """p10/p90 from TRAIN scores only — never peek at OOS."""
    scores = [float(u["score"]) for u in units if u.get("split") == "train"]
    if len(scores) < 10:
        raise ValueError(f"need >=10 train scores for quantiles, got {len(scores)}")
    a = np.asarray(scores, dtype=float)
    return {
        "n_train_scores": int(a.size),
        "p10": float(np.percentile(a, QUANTILE_LOW)),
        "p50": float(np.percentile(a, 50)),
        "p90": float(np.percentile(a, QUANTILE_HIGH)),
        "mean": float(a.mean()),
        "std": float(a.std()),
        "quantile_low_pct": QUANTILE_LOW,
        "quantile_high_pct": QUANTILE_HIGH,
        "source_split": "train_only",
    }


def assign_arms(units: list[dict], q: dict, seed: int) -> dict[str, list[int]]:
    """Map arm_id → list of unit indices. Quantiles from train; applied to all."""
    p10, p90 = q["p10"], q["p90"]
    n = len(units)
    all_idx = list(range(n))
    top = [i for i, u in enumerate(units) if float(u["score"]) >= p90]
    bot = [i for i, u in enumerate(units) if float(u["score"]) <= p10]
    long_only = [i for i, u in enumerate(units) if u.get("direction") == "long"]
    short_only = [i for i, u in enumerate(units) if u.get("direction") == "short"]

    # random_match_n: size-match top-decile *overall* count, deterministic
    rng = random.Random(seed)
    k = len(top)
    if k >= n:
        rand_idx = all_idx[:]
    else:
        rand_idx = rng.sample(all_idx, k)
    rand_idx.sort()

    # Also size-match within each split for fair IS/OOS tables
    def _rand_match_split(split: str) -> list[int]:
        pool = [i for i, u in enumerate(units) if u.get("split") == split]
        top_s = [i for i in top if units[i].get("split") == split]
        k_s = len(top_s)
        if k_s == 0:
            return []
        if k_s >= len(pool):
            return sorted(pool)
        # independent stream per split
        r = random.Random(seed + (1 if split == "train" else 2))
        return sorted(r.sample(pool, k_s))

    return {
        "all_units": all_idx,
        "nb_top_decile": top,
        "nb_bottom_decile": bot,
        "random_match_n": rand_idx,
        "random_match_n_train": _rand_match_split("train"),
        "random_match_n_oos": _rand_match_split("oos"),
        "long_only": long_only,
        "short_only": short_only,
    }


def load_bars(corpus_path: Path) -> list[Bar]:
    from data_ingestion.xauusd_phase1_candidate import guard_xauusd_csv_path

    guarded = Path(guard_xauusd_csv_path(str(corpus_path), INSTRUMENT))
    df = pd.read_csv(guarded)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    bars: list[Bar] = []
    for i in range(len(df)):
        bars.append(
            Bar(
                index=i,
                timestamp=df.iloc[i]["timestamp"].to_pydatetime()
                if hasattr(df.iloc[i]["timestamp"], "to_pydatetime")
                else df.iloc[i]["timestamp"],
                open=float(df.iloc[i]["open"]),
                high=float(df.iloc[i]["high"]),
                low=float(df.iloc[i]["low"]),
                close=float(df.iloc[i]["close"]),
                volume=float(df.iloc[i].get("volume", 0.0) or 0.0),
            )
        )
    return bars


def resolve_entry_geometry(unit: dict, bars: list[Bar]) -> tuple[int, float, float]:
    """Return (entry_index, entry_price, atr_abs)."""
    # Prefer train payload when present (LABEL_ACCEPTED)
    if unit.get("train_entry") is not None and unit.get("train_atr_abs") is not None:
        idx = int(unit.get("bar_index") or 0)
        if 0 <= idx < len(bars):
            return idx, float(unit["train_entry"]), float(unit["train_atr_abs"])
        # fall through if index bad

    # Resolve by timestamp
    ts = pd.Timestamp(unit["timestamp"])
    idx = int(unit.get("bar_index") or -1)
    if idx < 0 or idx >= len(bars):
        # linear search by timestamp (units are sparse; OK)
        for i, b in enumerate(bars):
            if pd.Timestamp(b.timestamp) == ts:
                idx = i
                break
    if idx < 0 or idx >= len(bars) - 1:
        raise ValueError(f"cannot resolve bar for unit ts={unit.get('timestamp')}")

    entry = float(bars[idx].close)
    # ATR: prefer train_atr_abs; else bar range proxy
    atr = unit.get("train_atr_abs")
    if atr is None or float(atr) <= 0:
        atr = max(bars[idx].high - bars[idx].low, 1e-8)
    else:
        atr = float(atr)
    return idx, entry, atr


def compute_net_rr_for_unit(unit: dict, bars: list[Bar], cost) -> dict:
    """Governing exit geometry + cost → net R for one unit."""
    from research.contracts import Signal
    from research.measurement.forward_walk import forward_walk

    # Fast path: train units already carry train_y_rr (same protocol as train labels)
    if (
        unit.get("split") == "train"
        and unit.get("train_y_rr") is not None
        and unit.get("train_sl_atr_mult") == SL_ATR_MULT
        and unit.get("train_tp_atr_mult") == TP_ATR_MULT
    ):
        return {
            "net_rr": float(unit["train_y_rr"]),
            "gross_rr": float(unit.get("train_rr_gross") or 0.0),
            "exit_reason": str(unit.get("train_exit_reason") or ""),
            "source": "train_label_payload",
            "entry": float(unit.get("train_entry") or 0.0),
            "atr_abs": float(unit.get("train_atr_abs") or 0.0),
            "entry_index": int(unit.get("bar_index") or -1),
        }

    idx, entry, atr = resolve_entry_geometry(unit, bars)
    direction = unit["direction"]
    ts = bars[idx].timestamp
    if not isinstance(ts, datetime):
        ts = pd.Timestamp(ts).to_pydatetime()

    sig = Signal(
        instrument=INSTRUMENT,
        timestamp=ts,
        entry_index=idx,
        direction=direction,
        entry=entry,
        sl_atr_mult=SL_ATR_MULT,
        tp_atr_mult=TP_ATR_MULT,
        atr=atr,
        meta={"phase": PHASE, "unit_ts": unit.get("timestamp")},
    )
    future = bars[idx + 1 :]
    outcome = forward_walk(
        sig, future, max_forward=MAX_FORWARD, exit_model=EXIT_MODEL
    )
    gross = float(outcome.rr_achieved)
    risk = SL_ATR_MULT * atr
    net = float(cost.net_rr(gross, entry, risk))
    return {
        "net_rr": net,
        "gross_rr": gross,
        "exit_reason": str(outcome.outcome),
        "source": "forward_walk",
        "entry": entry,
        "atr_abs": atr,
        "entry_index": idx,
    }


def arm_metrics(net_rrs: list[float]) -> dict:
    if not net_rrs:
        return {
            "n": 0,
            "mean_net_rr": None,
            "pf": None,
            "win_rate": None,
            "sum_net_rr": 0.0,
            "n_pos": 0,
            "n_neg": 0,
            "n_zero": 0,
        }
    a = np.asarray(net_rrs, dtype=float)
    pos = a[a > 0]
    neg = a[a < 0]
    gross_win = float(pos.sum()) if pos.size else 0.0
    gross_loss = float(-neg.sum()) if neg.size else 0.0
    pf = (gross_win / gross_loss) if gross_loss > 0 else (float("inf") if gross_win > 0 else None)
    return {
        "n": int(a.size),
        "mean_net_rr": float(a.mean()),
        "std_net_rr": float(a.std()),
        "min_net_rr": float(a.min()),
        "max_net_rr": float(a.max()),
        "sum_net_rr": float(a.sum()),
        "pf": pf if pf is None or math.isfinite(pf) else None,
        "pf_raw": pf,
        "win_rate": float((a > 0).mean()),
        "n_pos": int((a > 0).sum()),
        "n_neg": int((a < 0).sum()),
        "n_zero": int((a == 0).sum()),
    }


def evaluate_arms(
    units: list[dict],
    net_by_idx: list[dict],
    arms: dict[str, list[int]],
) -> dict:
    """Per-arm metrics overall + train + oos."""
    report = {}
    primary_arms = [
        "all_units",
        "nb_top_decile",
        "nb_bottom_decile",
        "random_match_n",
        "long_only",
        "short_only",
    ]
    for arm in primary_arms:
        idxs = arms[arm]
        overall = [net_by_idx[i]["net_rr"] for i in idxs if net_by_idx[i] is not None]
        is_rr = [
            net_by_idx[i]["net_rr"]
            for i in idxs
            if net_by_idx[i] is not None and units[i].get("split") == "train"
        ]
        oos_rr = [
            net_by_idx[i]["net_rr"]
            for i in idxs
            if net_by_idx[i] is not None and units[i].get("split") == "oos"
        ]
        # Prefer split-matched random for IS/OOS comparison fairness
        if arm == "random_match_n":
            is_rr = [
                net_by_idx[i]["net_rr"]
                for i in arms["random_match_n_train"]
                if net_by_idx[i] is not None
            ]
            oos_rr = [
                net_by_idx[i]["net_rr"]
                for i in arms["random_match_n_oos"]
                if net_by_idx[i] is not None
            ]
        report[arm] = {
            "n_members": len(idxs),
            "overall": arm_metrics(overall),
            "is": arm_metrics(is_rr),
            "oos": arm_metrics(oos_rr),
        }
    return report


def apply_kill_criteria(arm_report: dict) -> dict:
    """Pre-registered kill: OOS top_decile E ≤ all_units AND ≤ random → NO_SKILL."""
    top = (arm_report.get("nb_top_decile") or {}).get("oos") or {}
    allu = (arm_report.get("all_units") or {}).get("oos") or {}
    rand = (arm_report.get("random_match_n") or {}).get("oos") or {}

    e_top = top.get("mean_net_rr")
    e_all = allu.get("mean_net_rr")
    e_rand = rand.get("mean_net_rr")
    n_top = top.get("n") or 0

    if e_top is None or e_all is None or e_rand is None:
        return {
            "verdict": "INSUFFICIENT",
            "reason": "missing OOS mean_net_rr for top/all/random",
            "e_top_oos": e_top,
            "e_all_oos": e_all,
            "e_random_oos": e_rand,
            "n_top_oos": n_top,
        }

    beats_all = e_top > e_all
    beats_rand = e_top > e_rand
    if (not beats_all) and (not beats_rand):
        verdict = "NO_SKILL_KILL"
        reason = (
            "OOS nb_top_decile E[R] does not beat all_units AND does not beat "
            "random_match_n (pre-registered E1 kill)"
        )
    elif beats_all or beats_rand:
        # skill signal vs at least one control — still NOT economic authority
        verdict = "SKILL_SIGNAL_RESEARCH_ONLY"
        reason = (
            "OOS top-decile beats at least one control; requires E2 M4 before any authority"
        )
    else:
        verdict = "INCONCLUSIVE"
        reason = "unexpected branch"

    return {
        "verdict": verdict,
        "reason": reason,
        "e_top_oos": e_top,
        "e_all_oos": e_all,
        "e_random_oos": e_rand,
        "n_top_oos": n_top,
        "beats_all_units_oos": beats_all,
        "beats_random_oos": beats_rand,
        "authority": AUTHORITY,
        "not_m4": True,
        "not_economic_authority": True,
    }


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="E1: XAUUSD Gaussian economic ledger")
    ap.add_argument("--units", default=DEFAULT_UNITS)
    ap.add_argument("--corpus", default=DEFAULT_CORPUS)
    ap.add_argument("--out-dir", default="results/gaussian_xauusd_econ")
    ap.add_argument(
        "--recompute-all-walks",
        action="store_true",
        help="Ignore train_y_rr; forward_walk every unit (slower, strict)",
    )
    args = ap.parse_args(argv)

    units_path = ROOT / args.units
    if not units_path.exists():
        print(f"ERROR: units not found: {units_path}", file=sys.stderr)
        return 2

    from research.costs import CostModel

    cost = CostModel(round_trip_bps=COST_BPS)
    seed = _seed_u32(PROTOCOL_ID)

    print(f"[E1] protocol={PROTOCOL_ID}")
    print(f"[E1] units={units_path}")
    print(f"[E1] authority={AUTHORITY}")

    units = load_units(units_path)
    print(f"[E1] n_units={len(units)}")
    q = train_quantiles(units)
    print(f"[E1] train quantiles p10={q['p10']:.6f} p90={q['p90']:.6f} (train n={q['n_train_scores']})")

    arms = assign_arms(units, q, seed)
    print(
        f"[E1] arm sizes: "
        + ", ".join(f"{k}={len(v)}" for k, v in arms.items() if not k.startswith("random_match_n_"))
    )

    print("[E1] loading OHLCV bars for forward_walk (oos + optional recompute)...")
    bars = load_bars(ROOT / args.corpus)
    print(f"[E1] bars={len(bars)}")

    net_by_idx: list[Optional[dict]] = [None] * len(units)
    fails = Counter()
    for i, u in enumerate(units):
        try:
            if args.recompute_all_walks:
                # force walk path by clearing train payload flags
                u2 = dict(u)
                u2["train_y_rr"] = None
                net_by_idx[i] = compute_net_rr_for_unit(u2, bars, cost)
            else:
                net_by_idx[i] = compute_net_rr_for_unit(u, bars, cost)
        except Exception as e:
            fails[type(e).__name__] += 1
            net_by_idx[i] = None

    n_ok = sum(1 for x in net_by_idx if x is not None)
    print(f"[E1] net_rr computed={n_ok}/{len(units)} fails={dict(fails)}")

    arm_report = evaluate_arms(units, net_by_idx, arms)
    kill = apply_kill_criteria(arm_report)

    # Per-unit ledger rows (compact)
    ledger_rows = []
    for i, u in enumerate(units):
        nr = net_by_idx[i]
        if nr is None:
            continue
        membership = [arm for arm, idxs in arms.items() if i in idxs and not arm.startswith("random_match_n_")]
        # include split-specific random membership
        if i in arms.get("random_match_n_train", []):
            membership.append("random_match_n_train")
        if i in arms.get("random_match_n_oos", []):
            membership.append("random_match_n_oos")
        ledger_rows.append(
            {
                "timestamp": u["timestamp"],
                "split": u["split"],
                "direction": u["direction"],
                "score": u["score"],
                "bar_index": u.get("bar_index"),
                "net_rr": nr["net_rr"],
                "gross_rr": nr["gross_rr"],
                "exit_reason": nr["exit_reason"],
                "net_source": nr["source"],
                "arms": membership,
                "reason_code_origin": u.get("reason_code_origin"),
                "journal_kind": u.get("journal_kind"),
            }
        )

    ts = _utc()
    out_dir = ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = out_dir / f"ledger_{ts}.jsonl"
    with ledger_path.open("w", encoding="utf-8") as f:
        for row in ledger_rows:
            f.write(json.dumps(row, default=str) + "\n")
    latest_ledger = out_dir / "ledger_LATEST.jsonl"
    latest_ledger.write_text(ledger_path.read_text(encoding="utf-8"), encoding="utf-8")

    # serialize arm report with finite-safe PF
    def _clean_metrics(m: dict) -> dict:
        out = dict(m)
        if out.get("pf_raw") == float("inf"):
            out["pf"] = None
            out["pf_infinite"] = True
        out.pop("pf_raw", None)
        return out

    arms_clean = {}
    for arm, block in arm_report.items():
        arms_clean[arm] = {
            "n_members": block["n_members"],
            "overall": _clean_metrics(block["overall"]),
            "is": _clean_metrics(block["is"]),
            "oos": _clean_metrics(block["oos"]),
        }

    manifest = {
        "phase": PHASE,
        "protocol_id": PROTOCOL_ID,
        "run_id": f"xauusd_gaussian_econ_ledger_{ts}",
        "timestamp_utc": ts,
        "authority": AUTHORITY,
        "design_doc": (
            "docs/implementation_plan/xauusd-gaussian-toward-economics-2026-07-23.md"
        ),
        "pre_registered": {
            "exit_model": EXIT_MODEL,
            "max_forward": MAX_FORWARD,
            "cost_bps": COST_BPS,
            "sl_atr_mult": SL_ATR_MULT,
            "tp_atr_mult": TP_ATR_MULT,
            "quantile_low_pct": QUANTILE_LOW,
            "quantile_high_pct": QUANTILE_HIGH,
            "quantiles_from": "train_split_only",
            "random_seed_material": PROTOCOL_ID,
            "random_seed_u32": seed,
            "kill_rule": (
                "OOS nb_top_decile mean_net_rr <= OOS all_units AND "
                "<= OOS random_match_n → NO_SKILL_KILL"
            ),
        },
        "inputs": {
            "units_path": str(units_path).replace("\\", "/"),
            "units_sha256": _sha256_file(units_path),
            "n_units": len(units),
            "corpus": str((ROOT / args.corpus)).replace("\\", "/"),
            "recompute_all_walks": bool(args.recompute_all_walks),
        },
        "train_score_quantiles": q,
        "arm_sizes": {k: len(v) for k, v in arms.items()},
        "runtime": {
            "n_net_ok": n_ok,
            "fail_counts": dict(fails),
            "net_source_counts": dict(
                Counter(
                    (net_by_idx[i] or {}).get("source")
                    for i in range(len(units))
                    if net_by_idx[i] is not None
                )
            ),
        },
        "arms": arms_clean,
        "kill_criteria": kill,
        "outputs": {
            "ledger_jsonl": str(ledger_path).replace("\\", "/"),
            "ledger_latest": str(latest_ledger).replace("\\", "/"),
            "ledger_sha256": _sha256_file(ledger_path),
            "n_ledger_rows": len(ledger_rows),
        },
        "not_in_scope": [
            "M4 QualificationGate (E2)",
            "gaussian_impl config change (E3)",
            "economic authority / production sizing",
            "post-hoc threshold retuning",
        ],
        "next_phase": (
            "E2 M4 only if kill verdict is SKILL_SIGNAL_RESEARCH_ONLY "
            "and n_oos is adequate; else CLOSE as NO_SKILL / research-only"
        ),
    }

    man_path = out_dir / f"e1_manifest_{ts}.json"
    latest_man = out_dir / "e1_manifest_LATEST.json"
    for p in (man_path, latest_man):
        p.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    print("--- E1 DONE ---")
    print(f"verdict:  {kill['verdict']}")
    print(f"reason:   {kill['reason']}")
    print(
        f"OOS E[R]: top={kill.get('e_top_oos')} all={kill.get('e_all_oos')} "
        f"rand={kill.get('e_random_oos')} n_top={kill.get('n_top_oos')}"
    )
    for arm in ("all_units", "nb_top_decile", "nb_bottom_decile", "random_match_n"):
        oos = arms_clean[arm]["oos"]
        print(
            f"  {arm:18s} oos n={oos.get('n')} mean={oos.get('mean_net_rr')} "
            f"pf={oos.get('pf')} wr={oos.get('win_rate')}"
        )
    print(f"ledger:   {ledger_path}")
    print(f"manifest: {man_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
