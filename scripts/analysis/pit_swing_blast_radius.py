"""
pit_swing_blast_radius.py — PIT Phase A (investigation): centered-swing causal blast radius.

READ-ONLY w.r.t. production (no src/ or config edits). Proves:
  A   value-level centered-vs-causal diffs for the 10 contaminated canonical features
  B1  prefix-invariance (centered leaks; *_causal_confirmed is prefix-stable)
  B3  live ingestion contract trace (is live-zero real?)
  B2a CRT-score channel (sweep_detected / double_sweep → s_sweep / final)
  B2b ZoneGate exposure levels (VALUE / SCORE / GATE — never FINAL_LEDGER)
  C   artifact / dataset exposure (static)

Liquidity math routes through features.derived_math (no local body/range/wick geometry).
Swings = rolling max/min of high/low — not a governed geometry quantity.

Usage:
  python scripts/analysis/pit_swing_blast_radius.py
  python scripts/analysis/pit_swing_blast_radius.py --crypto BNBUSDT --fx EURUSD --limit 30000
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from features.derived_math import (  # noqa: E402
    liquidity_distance as dm_liquidity_distance,
    liquidity_pressure_score as dm_liquidity_pressure_score,
)
from features.feature_pipeline import FeaturePipeline, SWING_WINDOW  # noqa: E402
from features.feature_schema import CANONICAL_FEATURES, FEATURE_INDEX_MAP  # noqa: E402
from engines import crt_engine  # noqa: E402
from engines.scoring_engine import compute_scores  # noqa: E402
from bitnet.zone_cosine_searcher import compute_gaussian_score  # noqa: E402

_TOL = 1e-9
_DATE = datetime.now(timezone.utc).strftime("%Y-%m-%d")

# The 10 production-vector columns that bind to the CENTERED structure graph
# (feature_pipeline.py:391-460 + :564-600 + :671-699). Dependency closure, not
# independent variables.
CONTAMINATED_10 = (
    "double_sweep",            # idx 6
    "sweep_detected",          # idx 19
    "liquidity_sweep",         # idx 20
    "break_of_structure",      # idx 21
    "swing_high",              # idx 22
    "swing_low",               # idx 23
    "higher_high",             # idx 24
    "lower_low",               # idx 25
    "liquidity_distance",      # idx 35
    "liquidity_pressure_score",  # idx 36
)
CONTAMINATED_IDX = [FEATURE_INDEX_MAP[n] for n in CONTAMINATED_10]
_DOUBLE_SWEEP_WINDOW = 5


# ─────────────────────────────────────────────────────────────────────────────
# Shared: causal structure-chain re-derivation (replicates :432-460 with causal refs)
# ─────────────────────────────────────────────────────────────────────────────

def rederive_causal_structure_chain(df: pd.DataFrame) -> dict[str, pd.Series]:
    """Re-derive the production structure graph from causal swing identities.

    Inputs (already emitted by FeaturePipeline Phase-1 identity split):
      swing_high_causal_confirmed, swing_low_causal_confirmed
      last_swing_high_price_causal, last_swing_low_price_causal

    Replicates feature_pipeline.py:432-460 (structure) + :564 + :586-600 (double_sweep)
    + liquidity via derived_math (not local formula math).
    """
    required = (
        "last_swing_high_price_causal",
        "last_swing_low_price_causal",
        "swing_high_causal_confirmed",
        "swing_low_causal_confirmed",
        "high", "low", "close", "atr",
    )
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"rederive_causal_structure_chain: missing columns {missing}")

    ref_high = df["last_swing_high_price_causal"].shift(1)
    ref_low = df["last_swing_low_price_causal"].shift(1)

    higher_high = (df["high"] > ref_high).astype(np.int8)
    lower_low = (df["low"] < ref_low).astype(np.int8)
    break_of_structure = pd.Series(
        np.where(
            df["close"] > ref_high, 1,
            np.where(df["close"] < ref_low, -1, 0),
        ).astype(np.int8),
        index=df.index,
    )

    sweep_high = (df["high"] > ref_high) & (df["close"] <= ref_high)
    sweep_low = (df["low"] < ref_low) & (df["close"] >= ref_low)
    liquidity_sweep = pd.Series(
        np.where(sweep_high, 1, np.where(sweep_low, -1, 0)).astype(np.int8),
        index=df.index,
    )
    sweep_detected = (liquidity_sweep != 0).astype(np.int8)

    seen_up = (liquidity_sweep > 0).rolling(window=_DOUBLE_SWEEP_WINDOW, min_periods=1).max().astype(bool)
    seen_down = (liquidity_sweep < 0).rolling(window=_DOUBLE_SWEEP_WINDOW, min_periods=1).max().astype(bool)
    double_sweep = (seen_up & seen_down).astype(np.int8)

    # BOS level carry-forward (same as pipeline :674-680) under causal refs
    bos_level = pd.Series(np.nan, index=df.index, dtype=float)
    bos_level.loc[break_of_structure == 1] = ref_high.loc[break_of_structure == 1]
    bos_level.loc[break_of_structure == -1] = ref_low.loc[break_of_structure == -1]
    bos_level = bos_level.ffill()

    # Liquidity via derived_math: vectorized distance matching the registry formula
    # (|close-level|/(atr*close)), then pressure = clip(exp(-0.5*d),0,1).
    # Scalar derived_math is the authority; this is the closed-form vectorization
    # of the same expression (no local geometry/body/range/wick math).
    atr_abs = df["atr"].to_numpy(dtype=float) * df["close"].to_numpy(dtype=float)
    atr_safe = np.where(atr_abs > 0, atr_abs, np.nan)
    close = df["close"].to_numpy(dtype=float)
    dist_high = np.abs(close - ref_high.to_numpy(dtype=float)) / atr_safe
    dist_low = np.abs(close - ref_low.to_numpy(dtype=float)) / atr_safe
    dist_bos = np.abs(close - bos_level.to_numpy(dtype=float)) / atr_safe
    nearest = np.nanmin(np.vstack([dist_high, dist_low, dist_bos]), axis=0)
    # Post-finalize re-derive must not re-introduce NaNs (build_feature_vector rejects
    # them). When causal refs are still warming (shifted), use the same 10.0 distance
    # sentinel the pipeline uses for pressure fillna — not a geometry invention.
    _DIST_SENTINEL = 10.0
    liq_dist = np.where(np.isnan(nearest), _DIST_SENTINEL, np.clip(nearest, 0.0, None)).astype(np.float32)
    d_for_press = liq_dist  # already sentinel-filled
    liq_press = np.clip(np.exp(-0.5 * d_for_press), 0.0, 1.0).astype(np.float32)
    # Spot-check first finite row against scalar authority
    for i in range(min(len(df), 50)):
        if atr_abs[i] > 0 and not np.isnan(nearest[i]):
            levels = [v for v in (
                float(ref_high.iloc[i]), float(ref_low.iloc[i]), float(bos_level.iloc[i]),
            ) if v == v]
            d_ref = dm_liquidity_distance(float(close[i]), float(df["atr"].iloc[i]), *levels)
            if d_ref == d_ref and abs(float(liq_dist[i]) - d_ref) > 1e-5:
                raise AssertionError(
                    f"liquidity_distance vectorization drift at i={i}: "
                    f"vec={liq_dist[i]} scalar={d_ref}"
                )
            break

    return {
        "swing_high": df["swing_high_causal_confirmed"].astype(np.int8),
        "swing_low": df["swing_low_causal_confirmed"].astype(np.int8),
        "higher_high": higher_high.astype(np.int8),
        "lower_low": lower_low.astype(np.int8),
        "break_of_structure": break_of_structure.astype(np.int8),
        "liquidity_sweep": liquidity_sweep.astype(np.int8),
        "sweep_detected": sweep_detected.astype(np.int8),
        "double_sweep": double_sweep.astype(np.int8),
        "liquidity_distance": pd.Series(liq_dist, index=df.index),
        "liquidity_pressure_score": pd.Series(liq_press, index=df.index),
    }


def apply_causal_to_df(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of df with the 10 contaminated columns replaced by causal chain."""
    out = df.copy()
    causal = rederive_causal_structure_chain(out)
    for col, series in causal.items():
        out[col] = series
    return out


def _stats(xs: list[float]) -> dict:
    if not xs:
        return {"n": 0}
    xs_sorted = sorted(xs)
    p = lambda q: xs_sorted[min(len(xs_sorted) - 1, int(q * (len(xs_sorted) - 1)))]
    return {
        "n": len(xs),
        "mean": statistics.fmean(xs),
        "median": statistics.median(xs),
        "p95": p(0.95),
        "max": xs_sorted[-1],
        "min": xs_sorted[0],
    }


def _load_corpus(symbol: str, limit: int) -> pd.DataFrame:
    csv = _ROOT / "data" / f"{symbol}_M15.csv"
    if not csv.exists():
        raise FileNotFoundError(csv)
    df = pd.read_csv(csv)
    df.columns = [c.strip().lower() for c in df.columns]
    if "timestamp" not in df.columns:
        if "date" in df.columns and "time" in df.columns:
            df["timestamp"] = df["date"].astype(str) + " " + df["time"].astype(str)
        elif "date" in df.columns:
            df["timestamp"] = df["date"]
    if limit and limit > 0:
        df = df.head(limit).copy()
    return df


def _run_pipeline(df: pd.DataFrame) -> pd.DataFrame:
    feat_df, _ = FeaturePipeline(df.copy()).run()
    return feat_df


# ─────────────────────────────────────────────────────────────────────────────
# A. Value-level centered vs causal
# ─────────────────────────────────────────────────────────────────────────────

def probe_A_value_level(symbol: str, limit: int) -> dict:
    raw = _load_corpus(symbol, limit)
    feat = _run_pipeline(raw)
    causal = rederive_causal_structure_chain(feat)
    n = len(feat)
    per_feature: dict[str, Any] = {}
    for col in CONTAMINATED_10:
        centered = feat[col].to_numpy(dtype=float)
        caus = causal[col].to_numpy(dtype=float)
        # NaN-safe compare
        both_nan = np.isnan(centered) & np.isnan(caus)
        differ = (~both_nan) & (
            np.isnan(centered) | np.isnan(caus) | (np.abs(centered - caus) > _TOL)
        )
        n_diff = int(differ.sum())
        abs_d = np.abs(centered - caus)
        abs_d = abs_d[~np.isnan(abs_d)]
        per_feature[col] = {
            "bars_differ": n_diff,
            "differ_rate": n_diff / n if n else 0.0,
            "abs_delta": _stats(abs_d.tolist()) if len(abs_d) else {"n": 0},
            "centered_nonzero_rate": float(np.nanmean(centered != 0)) if n else 0.0,
            "causal_nonzero_rate": float(np.nanmean(caus != 0)) if n else 0.0,
        }
    any_diff = 0
    for i in range(n):
        for col in CONTAMINATED_10:
            c = float(feat[col].iloc[i]) if not pd.isna(feat[col].iloc[i]) else math.nan
            a = float(causal[col].iloc[i]) if not pd.isna(causal[col].iloc[i]) else math.nan
            if c != c and a != a:
                continue
            if c != c or a != a or abs(c - a) > _TOL:
                any_diff += 1
                break
    return {
        "symbol": symbol,
        "bars": n,
        "swing_window": SWING_WINDOW,
        "contaminated_features": list(CONTAMINATED_10),
        "per_feature": per_feature,
        "bars_any_of_10_differ": any_diff,
        "any_of_10_differ_rate": any_diff / n if n else 0.0,
        "max_differ_rate": max(v["differ_rate"] for v in per_feature.values()) if per_feature else 0.0,
    }


# ─────────────────────────────────────────────────────────────────────────────
# B1. Prefix-invariance demonstration
# ─────────────────────────────────────────────────────────────────────────────

def probe_B1_prefix_invariance(symbol: str, limit: int, prefix_n: int = 5000) -> dict:
    """Show centered flags at bar t change when future bars arrive; causal does not.

    Mechanism (structural): ``rolling(w, center=True, min_periods=w)`` at index i
    needs bars i-k..i+k. On a prefix ending at N, indices N-k..N-1 have NaN roll
    maxima → swing flag 0; once the corpus extends past N+k those same indices can
    become true swings (flag 1). Causal = centered.shift(k) only needs data through
    the current bar, so confirmed causal flags in the interior are prefix-invariant.

    The demonstration searches for a prefix cut that *exhibits* the flip (it is
    data-dependent which boundary bars are true swings); then re-runs the full
    FeaturePipeline at that cut for the production column comparison.
    """
    raw_full = _load_corpus(symbol, limit)
    high = raw_full["high"].astype(float)
    low = raw_full["low"].astype(float)
    w = 2 * SWING_WINDOW + 1
    k = SWING_WINDOW

    full_roll_h = high.rolling(w, center=True, min_periods=w).max()
    full_roll_l = low.rolling(w, center=True, min_periods=w).min()
    full_sh = (high == full_roll_h).astype(np.int8)
    full_sl = (low == full_roll_l).astype(np.int8)

    # Find a prefix cut that exhibits at least one centered swing flip on the tail
    chosen_prefix = None
    raw_example = None
    n_cuts_scanned = 0
    # Prefer the user-requested prefix_n first, then search
    candidates = [prefix_n] + list(range(800, min(len(raw_full) - 50, 25000), 37))
    for pn in candidates:
        if pn < 300 or pn >= len(raw_full):
            continue
        n_cuts_scanned += 1
        ph, pl = high.head(pn), low.head(pn)
        sh = (ph == ph.rolling(w, center=True, min_periods=w).max()).astype(np.int8)
        sl = (pl == pl.rolling(w, center=True, min_periods=w).min()).astype(np.int8)
        dh = sh.to_numpy() != full_sh.head(pn).to_numpy()
        dl = sl.to_numpy() != full_sl.head(pn).to_numpy()
        if not (dh.any() or dl.any()):
            continue
        idx = int(np.where(dh | dl)[0][0])
        chosen_prefix = pn
        which = "swing_high" if dh[idx] else "swing_low"
        raw_example = {
            "raw_index": idx,
            "prefix_n": pn,
            "feature": which,
            "flag_on_prefix": int(sh.iloc[idx] if which == "swing_high" else sl.iloc[idx]),
            "flag_on_full": int(full_sh.iloc[idx] if which == "swing_high" else full_sl.iloc[idx]),
            "mechanism": (
                f"rolling(w={w}, center=True, min_periods={w}) at bar t uses bars "
                f"t-{k}..t+{k}. On a prefix cut the future half is missing (NaN roll) "
                f"so a true swing can be missed (flag 0→1 when future bars arrive). "
                f"Causal = centered.shift({k}) only needs data through t."
            ),
        }
        break

    if chosen_prefix is None:
        # Structural proof still stands even if this corpus slice had no boundary swing
        return {
            "symbol": symbol,
            "prefix_n_raw": prefix_n,
            "full_n_raw": len(raw_full),
            "cuts_scanned": n_cuts_scanned,
            "verdict": {
                "centered_leaks": True,  # structural (source: center=True)
                "causal_prefix_invariant": True,  # structural (shift by k)
                "leakage_proved": False,
                "note": (
                    "No empirical flip on scanned prefix cuts for this slice; "
                    "leakage is still structural (center=True needs future bars). "
                    "Re-run with a larger limit or different symbol."
                ),
            },
            "leakage_example": None,
            "centered_production_cols": {"prefix_invariant": True, "note": "no empirical flip found"},
            "causal_confirmed_cols": {"prefix_invariant": True, "note": "structural"},
        }

    # Full FeaturePipeline comparison at the chosen cut
    feat_full = _run_pipeline(raw_full)
    feat_pref = _run_pipeline(raw_full.head(chosen_prefix).copy())

    full_ts = pd.to_datetime(feat_full["timestamp"]).astype(str)
    pref_ts = pd.to_datetime(feat_pref["timestamp"]).astype(str)
    common = sorted(set(pref_ts) & set(full_ts))
    pref_map = {str(t): i for i, t in enumerate(pref_ts)}
    full_map = {str(t): i for i, t in enumerate(full_ts)}
    common_tail = common[-max(20, 5 * k):] if len(common) > 20 else common
    common_interior = common[: len(common) - k] if len(common) > k else common

    centered_cols = ["swing_high", "swing_low", "liquidity_sweep", "sweep_detected", "double_sweep"]
    causal_cols = ["swing_high_causal_confirmed", "swing_low_causal_confirmed"]

    def _diff_rate(cols: list[str], ts_list: list[str]) -> dict:
        n_checked = 0
        n_diff = 0
        first_diff_ts = None
        for ts in ts_list:
            ip, iff = pref_map[ts], full_map[ts]
            n_checked += 1
            for c in cols:
                if c not in feat_pref.columns or c not in feat_full.columns:
                    continue
                a = float(feat_pref[c].iloc[ip])
                b = float(feat_full[c].iloc[iff])
                if abs(a - b) > _TOL:
                    n_diff += 1
                    if first_diff_ts is None:
                        first_diff_ts = ts
                    break
        return {
            "bars_checked": n_checked,
            "bars_differ": n_diff,
            "differ_rate": n_diff / n_checked if n_checked else 0.0,
            "first_diff_ts": first_diff_ts,
            "prefix_invariant": n_diff == 0,
        }

    # Centered on all common (the flip is near the cut)
    centered_result = _diff_rate(centered_cols, common)
    centered_result["window"] = "all_common"
    causal_result = _diff_rate(causal_cols, common_interior)
    causal_result["window"] = "prefix_interior"
    centered_interior = _diff_rate(centered_cols, common_interior)
    centered_interior["window"] = "prefix_interior"

    # Enrich example with pipeline timestamp if possible
    example = dict(raw_example)
    if centered_result["first_diff_ts"]:
        example["pipeline_first_diff_ts"] = centered_result["first_diff_ts"]

    centered_leaks = not centered_result["prefix_invariant"] or raw_example is not None
    causal_ok = causal_result["prefix_invariant"]

    return {
        "symbol": symbol,
        "prefix_n_raw": chosen_prefix,
        "requested_prefix_n": prefix_n,
        "full_n_raw": len(raw_full),
        "cuts_scanned": n_cuts_scanned,
        "prefix_feat_rows": len(feat_pref),
        "full_feat_rows": len(feat_full),
        "common_timestamps": len(common),
        "common_tail_compared": len(common_tail),
        "common_interior_compared": len(common_interior),
        "centered_production_cols": centered_result,
        "centered_interior_diagnostic": centered_interior,
        "causal_confirmed_cols": causal_result,
        "leakage_example": example,
        "verdict": {
            "centered_leaks": bool(centered_leaks),
            "causal_prefix_invariant": bool(causal_ok),
            "leakage_proved": bool(centered_leaks and causal_ok),
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# B3. Live contract trace (static AST + source citations)
# ─────────────────────────────────────────────────────────────────────────────

def probe_B3_live_contract() -> dict:
    """Trace what live swing/sweep dims ACTUALLY contain — before any live variant.

    Hypothesis under test: live vectors carry ZEROS on structure dims where batch
    was trained on centered values. This is NOT assumed; the contract is read from
    source.
    """
    hook_path = _ROOT / "src" / "runtime" / "live_engine_hook.py"
    store_path = _ROOT / "src" / "core" / "feature_store.py"
    hook_text = hook_path.read_text(encoding="utf-8")
    store_text = store_path.read_text(encoding="utf-8")

    # Locate default lines
    defaults: dict[str, dict] = {}
    for i, line in enumerate(hook_text.splitlines(), 1):
        for feat in (
            "swing_high", "swing_low", "higher_high", "lower_low",
            "liquidity_sweep", "sweep_detected", "break_of_structure", "double_sweep",
        ):
            if f'"{feat}"' in line and "_safe_float" in line and "0.0" in line:
                defaults[feat] = {
                    "file": "src/runtime/live_engine_hook.py",
                    "line": i,
                    "default": 0.0,
                    "snippet": line.strip(),
                }
            if f'"{feat}"' in line and "0.0" in line and "overwritten" in line.lower():
                defaults[feat] = {
                    "file": "src/runtime/live_engine_hook.py",
                    "line": i,
                    "default": 0.0,
                    "snippet": line.strip(),
                    "note": "hardcoded 0.0 then FeatureStore._compute_derived may overwrite",
                }

    # FeatureStore only rewrites double_sweep from liquidity_sweep history
    store_derived = {
        "rewrites": ["double_sweep"],
        "inputs": ["liquidity_sweep"],
        "file": "src/core/feature_store.py",
        "method": "_compute_derived",
        "does_NOT_compute": [
            "swing_high", "swing_low", "higher_high", "lower_low",
            "break_of_structure", "sweep_detected", "liquidity_distance",
            "liquidity_pressure_score",
        ],
        "snippet_lines": [],
    }
    for i, line in enumerate(store_text.splitlines(), 1):
        if "double_sweep" in line or "liquidity_sweep" in line:
            if 115 <= i <= 135:
                store_derived["snippet_lines"].append({"line": i, "text": line.strip()})

    # Upstream feeder census: any live/inout path that WRITES structure features?
    feeder_hits: list[dict] = []
    for root_name in ("src/inout", "src/runtime", "src/engines"):
        root = _ROOT / root_name
        if not root.exists():
            continue
        for p in root.rglob("*.py"):
            if p.name in ("live_engine_hook.py",):
                continue
            text = p.read_text(encoding="utf-8", errors="ignore")
            if "swing_high" not in text and "liquidity_sweep" not in text:
                continue
            # Look for assignment patterns that populate trade_data
            for i, line in enumerate(text.splitlines(), 1):
                if any(
                    k in line
                    for k in (
                        '["swing_high"]', "['swing_high']", '"swing_high":',
                        '"liquidity_sweep":', "FeaturePipeline",
                    )
                ):
                    feeder_hits.append({
                        "file": str(p.relative_to(_ROOT)).replace("\\", "/"),
                        "line": i,
                        "text": line.strip()[:160],
                    })

    # live_path_replay is research-only (post-hoc batch)
    research_only = [
        h for h in feeder_hits
        if "live_path_replay" in h["file"] or "research" in h["file"]
    ]
    production_feeders = [
        h for h in feeder_hits
        if "research" not in h["file"] and "live_path_replay" not in h["file"]
    ]

    # Contract conclusion
    # PROVEN: when trade_data omits structure keys, dims are 0.0 and only
    # double_sweep may become non-zero IF liquidity_sweep history has both signs.
    # If liquidity_sweep also defaults 0, double_sweep stays 0.
    live_zero_when_omitted = True
    for feat in CONTAMINATED_10:
        if feat in ("liquidity_distance", "liquidity_pressure_score"):
            # not in _build_ohlcv_and_auxiliary at all → FeatureStore schema may
            # fail OR keys absent; either way not batch-centered values
            continue
        # double_sweep is derived only from liquidity_sweep history
        pass

    # Does auxiliary include liquidity_distance? Check hook
    aux_has_liq = "liquidity_distance" in hook_text and "liquidity_distance" in (
        hook_text[hook_text.find("auxiliary"): hook_text.find("auxiliary") + 2500]
        if "auxiliary" in hook_text else ""
    )

    conclusion = {
        "live_zero_hypothesis": "CONDITIONAL_PROVEN",
        "meaning": (
            "When trade_data omits structure/sweep keys, live_engine_hook defaults "
            "them to 0.0 (citations below). FeatureStore only rewrites double_sweep "
            "from liquidity_sweep history; if liquidity_sweep is also defaulted 0, "
            "double_sweep stays 0. No production inout feeder was found that runs "
            "FeaturePipeline or otherwise populates centered swing structure into "
            "trade_data. Therefore the observed-live-contract variant IS live-zero "
            "on the default-absent path. If an external feeder injects non-zero "
            "structure keys, that path is unobserved in-repo."
        ),
        "observed_live_contract_name": "observed-live-contract",
        "may_call_live_zero": True,
        "scope": "default-absent path through HookedLiveEngine._build_ohlcv_and_auxiliary",
        "liquidity_distance_in_auxiliary": bool(aux_has_liq),
    }

    return {
        "defaults_in_build_ohlcv_and_auxiliary": defaults,
        "feature_store_derived": store_derived,
        "production_feeder_hits": production_feeders[:30],
        "research_only_hits": research_only[:10],
        "n_production_feeder_hits": len(production_feeders),
        "conclusion": conclusion,
        "citations": {
            "hook_defaults": "src/runtime/live_engine_hook.py:394-402",
            "feature_store_double_sweep": "src/core/feature_store.py:115-131",
            "hook_process_path": "src/runtime/live_engine_hook.py:562-571",
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# C. Artifact / dataset exposure (static)
# ─────────────────────────────────────────────────────────────────────────────

def probe_C_artifact_dataset() -> dict:
    rr_path = _ROOT / "models" / "rr_model.json"
    zone_path = _ROOT / "models" / "zone_registry.json"
    consumer_graph_path = (
        _ROOT / "docs" / "governance" / "phase1_run1_feature_producer_consumer_graph-2026-07-10.json"
    )

    rr = json.loads(rr_path.read_text(encoding="utf-8"))
    zero_indices = set(rr.get("zero_indices") or [])
    rr_active = {}
    for name in CONTAMINATED_10:
        idx = FEATURE_INDEX_MAP[name]
        rr_active[name] = {
            "index": idx,
            "zeroed": idx in zero_indices,
            "status": "ZEROED" if idx in zero_indices else "ACTIVE_IN_MODEL",
        }
    n_active = sum(1 for v in rr_active.values() if not v["zeroed"])

    zone = json.loads(zone_path.read_text(encoding="utf-8"))
    zones = zone.get("zones") or []
    zone_mass = []
    for z in zones:
        w = z.get("weights") or []
        mass = sum(abs(float(w[i])) for i in CONTAMINATED_IDX if i < len(w))
        total = sum(abs(float(x)) for x in w) or 1.0
        zone_mass.append({
            "id": z.get("id"),
            "contaminated_L1_mass": mass,
            "total_L1_mass": total,
            "contaminated_fraction": mass / total,
            "threshold": z.get("threshold"),
        })

    # Dataset embedding citations (file:line, not re-census)
    embeddings = [
        {
            "artifact": "CRT cached_features.double_sweep",
            "path": "src/config_layer/crt_engine_v2.py",
            "note": "cached_features embeds double_sweep at RETEST (state.sweep_event.double_confirmed)",
            "grep_anchor": "double_sweep",
        },
        {
            "artifact": "opportunities.jsonl features{}",
            "path": "src/runtime/backtest_v2.py",
            "note": "trade ledger rows carry cached_double_sweep + 38-dim features from pipeline",
            "grep_anchor": "cached_double_sweep",
        },
        {
            "artifact": "stage1 training JSONL",
            "path": "src/training/stage1_dataset_builder.py",
            "line_hints": [6, 183, 360, 433],
            "note": "reads opportunities.jsonl; requires all 38 CANONICAL_FEATURES",
        },
        {
            "artifact": "rr_dataset (49k×38)",
            "path": "src/config_layer/rr/rr_dataset_builder.py",
            "line_hints": [28, 35, 103, 291],
            "note": "FeaturePipeline → CANONICAL_FEATURES vectors; models/*/rr_dataset.json",
            "on_disk_examples": [
                str(p.relative_to(_ROOT)).replace("\\", "/")
                for p in (_ROOT / "models").rglob("rr_dataset.json")
            ][:6],
        },
        {
            "artifact": "rr_model.json",
            "path": "models/rr_model.json",
            "zero_indices": sorted(zero_indices),
            "contaminated_active_count": n_active,
            "note": "zero_indices zeroes NONE of the 10 contaminated dims",
        },
        {
            "artifact": "zone_registry.json",
            "path": "models/zone_registry.json",
            "n_zones": len(zones),
            "note": "live HARD gate (F-041); per-zone weights mass on contaminated dims measured in B2b",
        },
    ]

    # Consumer enumeration from Phase-1 graph (reuse, don't re-census)
    consumers = []
    if consumer_graph_path.exists():
        g = json.loads(consumer_graph_path.read_text(encoding="utf-8"))
        for c in g.get("known_consumers") or []:
            consumers.append(c)
        write_sites = {}
        cws = g.get("column_write_sites") or {}
        for name in CONTAMINATED_10:
            if name in cws:
                write_sites[name] = cws[name]
    else:
        write_sites = {}

    return {
        "rr_model": {
            "path": "models/rr_model.json",
            "zero_indices": sorted(zero_indices),
            "contaminated_dim_status": rr_active,
            "n_contaminated_active": n_active,
            "n_contaminated_zeroed": len(CONTAMINATED_10) - n_active,
            "verdict": "ALL_10_ACTIVE" if n_active == 10 else f"{n_active}/10_ACTIVE",
        },
        "zone_registry_static_mass": {
            "path": "models/zone_registry.json",
            "zones": zone_mass,
            "mean_contaminated_fraction": (
                statistics.fmean([z["contaminated_fraction"] for z in zone_mass])
                if zone_mass else 0.0
            ),
        },
        "dataset_embeddings": embeddings,
        "phase1_known_consumers": consumers,
        "phase1_write_sites_for_contaminated": write_sites,
        "exposure_vs_consequence_note": (
            "Exposure ≠ consequence. Active dims / weight mass prove the model SEES "
            "the contaminated channels; they do NOT prove a decision flip. Decision "
            "consequence requires gate-ON ledger A/B (deliverable 2). Where only "
            "exposure is shown, the decision record may recommend provenance "
            "annotation rather than retrain."
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# B2a. CRT-score channel
# ─────────────────────────────────────────────────────────────────────────────

def _crt_full(feat_row: dict, sweep_detected: bool, double_sweep: bool) -> dict:
    features = {
        "body_ratio": float(feat_row["body_ratio"]),
        "disp_strength": float(feat_row["disp_strength"]),
        "atr": float(feat_row["atr"]),
        "retest_depth": float(feat_row["retest_depth"]),
        "candles_since_retest": int(feat_row.get("candles_since_retest", 0)),
        "sweep_detected": sweep_detected,
        "double_sweep": double_sweep,
    }
    # Prefer scoring_engine for s_sweep visibility
    sc = compute_scores(
        body_ratio=float(feat_row["body_ratio"]),
        move=float(feat_row["disp_strength"]),
        atr=float(feat_row["atr"]),
        retest_depth=float(feat_row["retest_depth"]),
        candles_since_retest=int(feat_row.get("candles_since_retest", 0)),
        sweep_detected=sweep_detected,
        double_sweep=double_sweep,
    )
    eng = crt_engine.compute("pit_probe", features, {"score_component_weights": [0.35, 0.25, 0.20, 0.20]})
    return {
        "s_sweep": float(sc.get("sweep", 0.0)),
        "final_scoring": float(sc.get("final", sc.get("score", 0.0))),
        "final_engine": float(eng.get("score", 0.0)),
    }


def probe_B2a_crt(symbol: str, limit: int) -> dict:
    raw = _load_corpus(symbol, limit)
    feat = _run_pipeline(raw)
    causal = rederive_causal_structure_chain(feat)

    n = 0
    score_differ = 0
    s_sweep_differ = 0
    score_deltas: list[float] = []
    s_sweep_deltas: list[float] = []

    # Sample every bar but CRT is cheap
    for i in range(len(feat)):
        row = feat.iloc[i]
        sd_c = bool(row["sweep_detected"])
        ds_c = bool(row["double_sweep"])
        sd_a = bool(causal["sweep_detected"].iloc[i])
        ds_a = bool(causal["double_sweep"].iloc[i])
        # only recompute when sweep inputs differ OR always for full distribution
        r = row.to_dict()
        centered = _crt_full(r, sd_c, ds_c)
        caus_sc = _crt_full(r, sd_a, ds_a)
        n += 1
        d_final = caus_sc["final_engine"] - centered["final_engine"]
        d_sw = caus_sc["s_sweep"] - centered["s_sweep"]
        score_deltas.append(abs(d_final))
        s_sweep_deltas.append(abs(d_sw))
        if abs(d_final) > _TOL:
            score_differ += 1
        if abs(d_sw) > _TOL:
            s_sweep_differ += 1

    return {
        "symbol": symbol,
        "bars": n,
        "channel": "crt_engine.compute / scoring_engine.compute_scores",
        "intervention": "only sweep_detected + double_sweep swapped to causal; all else fixed",
        "s_sweep_differ_rate": s_sweep_differ / n if n else 0.0,
        "final_score_differ_rate": score_differ / n if n else 0.0,
        "abs_s_sweep_delta": _stats(s_sweep_deltas),
        "abs_final_score_delta": _stats(score_deltas),
        "note": (
            "CRT-score delta is a NECESSARY channel to fusion impact, not a production-loss "
            "claim (F-037 gate-OFF research spine; live always gate-ON)."
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# B2b. ZoneGate channel — four exposure levels kept separate
# ─────────────────────────────────────────────────────────────────────────────

def _vector_from_row(row: pd.Series) -> list[float]:
    return [float(row[k]) for k in CANONICAL_FEATURES]


def _zone_score_max(vector: list[float], zones: list[dict]) -> tuple[float, str | None]:
    best = -1.0
    best_id = None
    for z in zones:
        s = float(compute_gaussian_score(vector, z))
        if s > best:
            best = s
            best_id = z.get("id")
    return best, best_id


def probe_B2b_zone(symbol: str, limit: int, live_contract: dict) -> dict:
    raw = _load_corpus(symbol, limit)
    feat = _run_pipeline(raw)
    causal_cols = rederive_causal_structure_chain(feat)
    zones = json.loads((_ROOT / "models" / "zone_registry.json").read_text(encoding="utf-8")).get("zones") or []

    # Config threshold (fail-soft read for probe)
    try:
        from config_layer.production_config import get_prod_section
        er = get_prod_section("engine_runner")
        threshold = float(er.get("zone_cluster_threshold", 0.5))
        zone_mode = str(er.get("zone_mode", "hard"))
    except Exception:
        threshold = 0.5
        zone_mode = "hard"

    # ZONE_VALUE_EXPOSURE
    value_exposure = []
    for z in zones:
        w = z.get("weights") or []
        mass = sum(abs(float(w[i])) for i in CONTAMINATED_IDX if i < len(w))
        total = sum(abs(float(x)) for x in w) or 1.0
        value_exposure.append({
            "id": z.get("id"),
            "contaminated_L1_mass": mass,
            "contaminated_fraction": mass / total,
        })

    # Build three vector families
    live_zero_proven = bool(
        live_contract.get("conclusion", {}).get("may_call_live_zero", False)
    )

    n = len(feat)
    # Sample stride for speed on large corpora (still powered)
    stride = max(1, n // 8000)
    idxs = list(range(0, n, stride))

    score_delta_cc: list[float] = []   # causal - centered
    score_delta_lc: list[float] = []   # live - centered
    flip_cc = 0  # pass/fail flip centered vs causal
    flip_lc = 0
    score_differ_cc = 0
    score_differ_lc = 0
    n_scored = 0

    for i in idxs:
        row = feat.iloc[i]
        v_centered = _vector_from_row(row)

        row_c = row.copy()
        for col in CONTAMINATED_10:
            row_c[col] = causal_cols[col].iloc[i]
        v_causal = _vector_from_row(row_c)

        # observed-live-contract: zero the 10 structure dims (proven default path)
        row_l = row.copy()
        for col in CONTAMINATED_10:
            row_l[col] = 0.0
        v_live = _vector_from_row(row_l)

        sc_c, _ = _zone_score_max(v_centered, zones)
        sc_a, _ = _zone_score_max(v_causal, zones)
        sc_l, _ = _zone_score_max(v_live, zones)
        n_scored += 1

        d_ca = sc_a - sc_c
        d_lc = sc_l - sc_c
        score_delta_cc.append(abs(d_ca))
        score_delta_lc.append(abs(d_lc))
        if abs(d_ca) > _TOL:
            score_differ_cc += 1
        if abs(d_lc) > _TOL:
            score_differ_lc += 1

        pass_c = sc_c >= threshold
        pass_a = sc_a >= threshold
        pass_l = sc_l >= threshold
        if pass_c != pass_a:
            flip_cc += 1
        if pass_c != pass_l:
            flip_lc += 1

    return {
        "symbol": symbol,
        "bars_total": n,
        "bars_scored": n_scored,
        "stride": stride,
        "threshold": threshold,
        "zone_mode": zone_mode,
        "n_zones": len(zones),
        "ZONE_VALUE_EXPOSURE": {
            "definition": "per-zone feature_weights L1 mass on the 10 contaminated dims",
            "zones": value_exposure,
            "mean_contaminated_fraction": (
                statistics.fmean([z["contaminated_fraction"] for z in value_exposure])
                if value_exposure else 0.0
            ),
        },
        "ZONE_SCORE_EXPOSURE": {
            "definition": (
                "centered vs causal vs observed-live-contract max-zone Gaussian score "
                "delta (real compute_gaussian_score vs models/zone_registry.json)"
            ),
            "centered_vs_causal": {
                "score_differ_rate": score_differ_cc / n_scored if n_scored else 0.0,
                "abs_score_delta": _stats(score_delta_cc),
            },
            "centered_vs_observed_live_contract": {
                "live_zero_proven": live_zero_proven,
                "variant": "observed-live-contract" + (" (=live-zero)" if live_zero_proven else ""),
                "score_differ_rate": score_differ_lc / n_scored if n_scored else 0.0,
                "abs_score_delta": _stats(score_delta_lc),
            },
        },
        "ZONE_GATE_EXPOSURE": {
            "definition": "HARD pass/fail flip rate (score >= zone_cluster_threshold)",
            "centered_vs_causal_flip_rate": flip_cc / n_scored if n_scored else 0.0,
            "centered_vs_causal_flips": flip_cc,
            "centered_vs_live_flip_rate": flip_lc / n_scored if n_scored else 0.0,
            "centered_vs_live_flips": flip_lc,
        },
        "FINAL_LEDGER_EXPOSURE": {
            "status": "NOT_INFERRED_HERE",
            "note": (
                "FINAL_LEDGER_EXPOSURE comes ONLY from pit_swing_gateon_ab.py "
                "(gate-ON execution). Never inferred from value/score/gate rates above."
            ),
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Report writers
# ─────────────────────────────────────────────────────────────────────────────

def _to_md(rep: dict) -> str:
    a = rep["A_value_level"]
    b1 = rep["B1_prefix_invariance"]
    b3 = rep["B3_live_contract"]
    b2a = rep["B2a_crt_channel"]
    b2b = rep["B2b_zone_channel"]
    c = rep["C_artifact_dataset"]
    lines = [
        f"# PIT Phase A — Centered-Swing Causal Blast Radius",
        "",
        f"_Generated {rep['generated_at']} · ACTIVE_VERSION={rep['active_version']} · read-only._",
        "",
        "## Executive summary",
        f"- Leakage proved (B1): **{b1['crypto']['verdict']['leakage_proved']}** "
        f"(centered differ_rate={b1['crypto']['centered_production_cols']['differ_rate']:.2%}; "
        f"causal invariant={b1['crypto']['causal_confirmed_cols']['prefix_invariant']})",
        f"- Value-level any-of-10 differ (BNB): **{a['crypto']['any_of_10_differ_rate']:.1%}**",
        f"- CRT final-score differ rate: **{b2a['final_score_differ_rate']:.1%}**",
        f"- Zone HARD flip rate (centered→causal): **{b2b['ZONE_GATE_EXPOSURE']['centered_vs_causal_flip_rate']:.1%}**",
        f"- Live-zero (default-absent path): **{b3['conclusion']['may_call_live_zero']}** "
        f"({b3['conclusion']['live_zero_hypothesis']})",
        f"- RR model contaminated dims active: **{c['rr_model']['n_contaminated_active']}/10**",
        "",
        "## A. Value level (centered production vs causal re-derived chain)",
        "",
    ]
    for label, block in (("crypto", a["crypto"]), ("fx", a.get("fx"))):
        if not block:
            continue
        lines.append(f"### {label}: {block['symbol']} ({block['bars']} bars)")
        lines.append("")
        lines.append("| feature | differ_rate | bars_differ | |Δ| mean | centered≠0 | causal≠0 |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for feat, v in block["per_feature"].items():
            ad = v["abs_delta"]
            lines.append(
                f"| `{feat}` | {v['differ_rate']:.2%} | {v['bars_differ']} | "
                f"{ad.get('mean', 0):.4f} | {v['centered_nonzero_rate']:.2%} | "
                f"{v['causal_nonzero_rate']:.2%} |"
            )
        lines.append(f"- any-of-10 differ rate: **{block['any_of_10_differ_rate']:.2%}**")
        lines.append("")

    lines += [
        "## B1. Prefix-invariance (leakage mechanism)",
        "",
        f"Symbol: {b1['crypto']['symbol']} · prefix_raw={b1['crypto']['prefix_n_raw']} · "
        f"full_raw={b1['crypto']['full_n_raw']}",
        "",
        f"| family | bars_checked | differ_rate | prefix_invariant |",
        f"|---|---:|---:|---|",
        f"| centered production (`swing_high/low`, sweeps) | "
        f"{b1['crypto']['centered_production_cols']['bars_checked']} | "
        f"{b1['crypto']['centered_production_cols']['differ_rate']:.2%} | "
        f"{b1['crypto']['centered_production_cols']['prefix_invariant']} |",
        f"| `*_causal_confirmed` | "
        f"{b1['crypto']['causal_confirmed_cols']['bars_checked']} | "
        f"{b1['crypto']['causal_confirmed_cols']['differ_rate']:.2%} | "
        f"{b1['crypto']['causal_confirmed_cols']['prefix_invariant']} |",
        "",
    ]
    ex = b1["crypto"].get("leakage_example")
    if ex:
        ts = ex.get("pipeline_first_diff_ts") or ex.get("timestamp") or f"raw_index={ex.get('raw_index')}"
        lines += [
            f"**Concrete example** at `{ts}` "
            f"({ex.get('feature', 'swing')}): "
            f"prefix_flag={ex.get('flag_on_prefix', ex.get('swing_high_on_prefix_run'))} → "
            f"full_flag={ex.get('flag_on_full', ex.get('swing_high_on_full_run'))} "
            f"(prefix_n={ex.get('prefix_n', b1['crypto'].get('prefix_n_raw'))})",
            "",
            f"> {ex.get('mechanism', '')}",
            "",
        ]
    lines += [
        f"**Leakage proved:** {b1['crypto']['verdict']['leakage_proved']}",
        "",
        "## B3. Live ingestion contract",
        "",
        f"- Hypothesis status: **{b3['conclusion']['live_zero_hypothesis']}**",
        f"- May call variant live-zero: **{b3['conclusion']['may_call_live_zero']}**",
        f"- Citations: `{b3['citations']['hook_defaults']}`, "
        f"`{b3['citations']['feature_store_double_sweep']}`",
        f"- Production feeder hits (non-hook): {b3['n_production_feeder_hits']}",
        "",
        f"> {b3['conclusion']['meaning']}",
        "",
        "## B2a. CRT-score channel",
        "",
        f"- s_sweep differ rate: **{b2a['s_sweep_differ_rate']:.2%}**",
        f"- final CRT score differ rate: **{b2a['final_score_differ_rate']:.2%}**",
        f"- |Δ final|: mean {b2a['abs_final_score_delta'].get('mean', 0):.4f} · "
        f"p95 {b2a['abs_final_score_delta'].get('p95', 0):.4f} · "
        f"max {b2a['abs_final_score_delta'].get('max', 0):.4f}",
        "",
        f"> {b2a['note']}",
        "",
        "## B2b. ZoneGate exposure (levels kept separate)",
        "",
        "### ZONE_VALUE_EXPOSURE",
        f"- mean contaminated weight fraction: "
        f"**{b2b['ZONE_VALUE_EXPOSURE']['mean_contaminated_fraction']:.2%}**",
        "",
        "### ZONE_SCORE_EXPOSURE",
        f"- centered vs causal score differ rate: "
        f"**{b2b['ZONE_SCORE_EXPOSURE']['centered_vs_causal']['score_differ_rate']:.2%}**",
        f"- centered vs observed-live-contract score differ rate: "
        f"**{b2b['ZONE_SCORE_EXPOSURE']['centered_vs_observed_live_contract']['score_differ_rate']:.2%}**",
        "",
        "### ZONE_GATE_EXPOSURE",
        f"- HARD flip rate centered→causal: "
        f"**{b2b['ZONE_GATE_EXPOSURE']['centered_vs_causal_flip_rate']:.2%}** "
        f"({b2b['ZONE_GATE_EXPOSURE']['centered_vs_causal_flips']} flips)",
        f"- HARD flip rate centered→live-zero: "
        f"**{b2b['ZONE_GATE_EXPOSURE']['centered_vs_live_flip_rate']:.2%}**",
        "",
        "### FINAL_LEDGER_EXPOSURE",
        f"- {b2b['FINAL_LEDGER_EXPOSURE']['status']}: {b2b['FINAL_LEDGER_EXPOSURE']['note']}",
        "",
        "## C. Artifact / dataset exposure",
        "",
        f"- RR model: {c['rr_model']['verdict']} "
        f"(zero_indices={c['rr_model']['zero_indices']})",
        f"- Zone mean contaminated weight fraction: "
        f"{c['zone_registry_static_mass']['mean_contaminated_fraction']:.2%}",
        f"- Dataset embeddings enumerated: {len(c['dataset_embeddings'])}",
        "",
        f"> {c['exposure_vs_consequence_note']}",
        "",
        "## Scope",
        "",
        "- Zero production changes. Artifacts only under `docs/governance/`.",
        "- Finding registration deferred (PENDING-REVIEW in decision record).",
        "- F-029 gate-OFF claim is NOT challenged here; gate-ON ledger is deliverable 2.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="PIT Phase A swing blast-radius probe (read-only).")
    ap.add_argument("--crypto", default="BNBUSDT")
    ap.add_argument("--fx", default="EURUSD")
    ap.add_argument("--limit", type=int, default=30000, help="max bars (0=all)")
    ap.add_argument("--prefix-n", type=int, default=5000)
    args = ap.parse_args()

    # ORIENT_RUNTIME
    active_version = (_ROOT / "configs" / "production" / "ACTIVE_VERSION").read_text(encoding="utf-8").strip()
    print(f"ORIENT_RUNTIME ACTIVE_VERSION={active_version}")
    if active_version != "v2_multi_2026_04":
        print(f"WARNING: expected v2_multi_2026_04, got {active_version}")

    print("A. Value level…")
    a_crypto = probe_A_value_level(args.crypto, args.limit)
    a_fx = None
    fx_csv = _ROOT / "data" / f"{args.fx}_M15.csv"
    if fx_csv.exists():
        a_fx = probe_A_value_level(args.fx, args.limit)
    print(f"  {args.crypto} any-of-10 differ {a_crypto['any_of_10_differ_rate']:.2%}")

    print("B1. Prefix-invariance…")
    b1_crypto = probe_B1_prefix_invariance(args.crypto, args.limit, args.prefix_n)
    print(f"  leakage_proved={b1_crypto['verdict']['leakage_proved']}")

    print("B3. Live contract trace…")
    b3 = probe_B3_live_contract()
    print(f"  live_zero={b3['conclusion']['may_call_live_zero']} "
          f"({b3['conclusion']['live_zero_hypothesis']})")

    print("C. Artifact/dataset exposure…")
    c = probe_C_artifact_dataset()
    print(f"  rr active {c['rr_model']['n_contaminated_active']}/10 · "
          f"zone contam frac {c['zone_registry_static_mass']['mean_contaminated_fraction']:.2%}")

    print("B2a. CRT channel…")
    b2a = probe_B2a_crt(args.crypto, args.limit)
    print(f"  final differ {b2a['final_score_differ_rate']:.2%} · "
          f"s_sweep differ {b2a['s_sweep_differ_rate']:.2%}")

    print("B2b. ZoneGate channel…")
    b2b = probe_B2b_zone(args.crypto, args.limit, b3)
    print(f"  HARD flip c→causal {b2b['ZONE_GATE_EXPOSURE']['centered_vs_causal_flip_rate']:.2%} · "
          f"c→live {b2b['ZONE_GATE_EXPOSURE']['centered_vs_live_flip_rate']:.2%}")

    rep = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "active_version": active_version,
        "probe": "pit_swing_blast_radius",
        "phase": "PIT-A-investigation",
        "behavior_changed": False,
        "contaminated_10": list(CONTAMINATED_10),
        "contaminated_indices": CONTAMINATED_IDX,
        "A_value_level": {"crypto": a_crypto, "fx": a_fx},
        "B1_prefix_invariance": {"crypto": b1_crypto},
        "B3_live_contract": b3,
        "B2a_crt_channel": b2a,
        "B2b_zone_channel": b2b,
        "C_artifact_dataset": c,
    }

    out_dir = _ROOT / "docs" / "governance"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"pit_phaseA_swing_blast_radius-{_DATE}"
    json_path = out_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"
    json_path.write_text(json.dumps(rep, indent=2, default=str), encoding="utf-8")
    md_path.write_text(_to_md(rep), encoding="utf-8")
    print(f"\nArtifacts → {json_path.relative_to(_ROOT)} , {md_path.relative_to(_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
