"""Five-stage analysis of TN_ENV_CLEAN_L1 clean labels (read-only).

Stages:
  1 Validate dataset (inventory, missing, distributions, imbalance, correlations)
  2 Semantic redundancy (conditional rates, mutual dependence)
  3 Architectural grouping (intelligence domains)
  4 Predictability (feature association, temporal/side/vol stability)
  5 Architecture implications + ownership matrix (written into report)

Usage:
  python scripts/research/analyze_clean_labels_tn_env.py
  python scripts/research/analyze_clean_labels_tn_env.py --dataset results/clean_labels/BNBUSDT/20260721T221711Z/clean_labels.jsonl
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from features.feature_schema import CANONICAL_FEATURES  # noqa: E402

# ── label catalog ────────────────────────────────────────────────────────────
LABEL_CATALOG: list[dict[str, Any]] = [
    # TradeNet / outcome
    {"name": "y_tp1", "domain": "outcome", "kind": "binary", "unit": "{0,1}",
     "question": "Will the first target (unit TP) be reached before hard SL?"},
    {"name": "y_tp2", "domain": "outcome", "kind": "binary", "unit": "{0,1}",
     "question": "Will +2R (surrogate TP2) be reached before hard SL?"},
    {"name": "y_survives_be", "domain": "outcome", "kind": "binary", "unit": "{0,1}",
     "question": "Does path MFE reach ≥1R before/at exit (survive to breakeven room)?"},
    {"name": "y_R_net", "domain": "outcome", "kind": "continuous", "unit": "R (net of 12bps)",
     "question": "What is realized net R under governing walk + cost?"},
    {"name": "y_expired_timeout", "domain": "timing", "kind": "binary", "unit": "{0,1}",
     "question": "Does the walk expire at max_forward without TP/SL?"},
    # Envelope excursion
    {"name": "y_mfe_r", "domain": "envelope_excursion", "kind": "continuous", "unit": "R",
     "question": "How far can price move favorably over the horizon (exit-agnostic)?"},
    {"name": "y_mae_r_heat", "domain": "envelope_risk", "kind": "continuous", "unit": "R (heat)",
     "question": "How much adverse movement is likely over the horizon?"},
    {"name": "path_mfe_r", "domain": "envelope_excursion", "kind": "continuous", "unit": "R (walk-bounded)",
     "question": "MFE realized on the governing walk path (bounded by SL/TP exit)?"},
    {"name": "path_mae_r_heat", "domain": "envelope_risk", "kind": "continuous", "unit": "R (walk-bounded)",
     "question": "MAE heat on the governing walk path?"},
    # Timing
    {"name": "y_holding_bars", "domain": "timing", "kind": "ordinal_time", "unit": "bars",
     "question": "How long until hard exit under governing walk?"},
    {"name": "y_time_to_mfe", "domain": "timing", "kind": "ordinal_time", "unit": "bars",
     "question": "When is maximum favorable excursion first attained?"},
    {"name": "y_time_to_1r", "domain": "timing", "kind": "ordinal_time", "unit": "bars (nullable)",
     "question": "When does path first reach +1R (horizon)?"},
    {"name": "path_time_to_tp", "domain": "timing", "kind": "ordinal_time", "unit": "bars (nullable)",
     "question": "Bars to first TP touch on primary walk?"},
    {"name": "path_time_to_failure", "domain": "timing", "kind": "ordinal_time", "unit": "bars (nullable)",
     "question": "Bars to SL hit on primary walk?"},
    # Horizon reach flags (derived envelope)
    {"name": "y_reached_0_5r", "domain": "envelope_excursion", "kind": "binary", "unit": "{0,1}",
     "question": "Does exit-agnostic path reach +0.5R?"},
    {"name": "y_reached_1r_horizon", "domain": "envelope_excursion", "kind": "binary", "unit": "{0,1}",
     "question": "Does exit-agnostic path reach +1R?"},
    {"name": "y_reached_2r_horizon", "domain": "envelope_excursion", "kind": "binary", "unit": "{0,1}",
     "question": "Does exit-agnostic path reach +2R (horizon, not walk SL-gated)?"},
    # Geometry context (not ML targets, inventory)
    {"name": "risk_distance", "domain": "risk_geometry", "kind": "continuous", "unit": "price",
     "question": "What SL distance was planned (|entry−sl|)?"},
]

PRIMARY_Y = [
    "y_tp1", "y_tp2", "y_survives_be", "y_R_net",
    "y_mfe_r", "y_mae_r_heat", "y_holding_bars", "y_time_to_mfe",
    "y_time_to_1r", "y_expired_timeout",
    "y_reached_0_5r", "y_reached_1r_horizon", "y_reached_2r_horizon",
    "path_mfe_r", "path_mae_r_heat",
]

# Feature indices for light predictability probes
PROBE_FEATS = [
    "atr", "body_ratio", "disp_strength", "retest_depth", "momentum_score",
    "ema_spread", "volatility_ratio", "volume_ratio", "rsi_14", "trend_strength",
    "session", "hour_of_day", "candles_since_retest",
]


def _to_float(x) -> float:
    if x is None:
        return float("nan")
    if x is True:
        return 1.0
    if x is False:
        return 0.0
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    """Spearman rho on finite pairs; returns nan if <30 pairs."""
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() < 30:
        return float("nan")
    aa, bb = a[m], b[m]
    ra = aa.argsort().argsort().astype(float)
    rb = bb.argsort().argsort().astype(float)
    ra -= ra.mean()
    rb -= rb.mean()
    den = np.sqrt((ra ** 2).sum() * (rb ** 2).sum())
    if den <= 0:
        return float("nan")
    return float((ra * rb).sum() / den)


def _pearson(a: np.ndarray, b: np.ndarray) -> float:
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() < 30:
        return float("nan")
    aa, bb = a[m], b[m]
    aa = aa - aa.mean()
    bb = bb - bb.mean()
    den = np.sqrt((aa ** 2).sum() * (bb ** 2).sum())
    if den <= 0:
        return float("nan")
    return float((aa * bb).sum() / den)


def _quantiles(x: np.ndarray, ps=(5, 20, 50, 80, 95)) -> dict[str, float | None]:
    m = x[np.isfinite(x)]
    if m.size == 0:
        return {f"q{p}": None for p in ps}
    return {f"q{p}": float(np.percentile(m, p)) for p in ps}


def _hist(x: np.ndarray, bins: int = 20) -> dict[str, Any]:
    m = x[np.isfinite(x)]
    if m.size == 0:
        return {"counts": [], "edges": []}
    # clip extreme for hist readability
    lo, hi = np.percentile(m, [1, 99])
    if lo == hi:
        lo, hi = float(m.min()), float(m.max() + 1e-9)
    counts, edges = np.histogram(np.clip(m, lo, hi), bins=bins)
    return {"counts": counts.tolist(), "edges": edges.tolist(), "clip_lo": float(lo), "clip_hi": float(hi)}


def load_columns(path: Path) -> dict[str, np.ndarray]:
    """Stream JSONL into column arrays (labels + probe features + meta)."""
    cols: dict[str, list] = defaultdict(list)
    feat_idx = {n: i for i, n in enumerate(CANONICAL_FEATURES)}
    probe_set = [f for f in PROBE_FEATS if f in feat_idx]

    n = 0
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            n += 1
            for name in PRIMARY_Y:
                cols[name].append(_to_float(r.get(name)))
            cols["risk_distance"].append(_to_float(r.get("risk_distance")))
            cols["entry_index"].append(_to_float(r.get("entry_index")))
            side = str(r.get("side", "")).lower()
            cols["side_long"].append(1.0 if side == "long" else 0.0)
            # path outcome one-hot light
            po = str(r.get("path_outcome", ""))
            cols["path_sl"].append(1.0 if po == "SL_HIT" else 0.0)
            cols["path_tp"].append(1.0 if po == "TP_HIT" else 0.0)
            cols["path_timeout"].append(1.0 if po == "TIMEOUT" else 0.0)
            # stream diagnostic
            d = r.get("diagnostics") or {}
            cols["stream_y_tp1"].append(_to_float(d.get("stream_y_tp1")))
            vec = r.get("feature_vector") or []
            for f in probe_set:
                i = feat_idx[f]
                cols[f"f_{f}"].append(_to_float(vec[i]) if i < len(vec) else float("nan"))
            # decision_ts for temporal — use entry_index as time order proxy
    out: dict[str, Any] = {k: np.asarray(v, dtype=float) for k, v in cols.items()}
    out["_n"] = np.array([float(n)])
    out["_probe_feats"] = list(probe_set)
    return out


def stage1(cols: dict) -> dict[str, Any]:
    n = int(cols["_n"][0])
    inventory = []
    for spec in LABEL_CATALOG:
        name = spec["name"]
        if name not in cols and name not in ("risk_distance",):
            # skip if not loaded
            if name not in cols:
                continue
        x = cols[name]
        finite = np.isfinite(x)
        n_miss = int((~finite).sum())
        n_ok = int(finite.sum())
        entry: dict[str, Any] = {
            **spec,
            "n": n,
            "n_finite": n_ok,
            "n_missing": n_miss,
            "missing_rate": round(n_miss / n, 6) if n else None,
        }
        if spec["kind"] == "binary":
            # treat nan as missing; rate among finite
            if n_ok:
                rate = float(np.nanmean(x))
                entry["positive_rate"] = round(rate, 6)
                entry["imbalance_ratio_pos_neg"] = (
                    round(rate / (1 - rate), 4) if 0 < rate < 1 else None
                )
                entry["class_balance"] = (
                    "severe_imbalance" if rate < 0.05 or rate > 0.95
                    else "moderate_imbalance" if rate < 0.2 or rate > 0.8
                    else "usable"
                )
        else:
            m = x[finite]
            if m.size:
                entry["mean"] = round(float(m.mean()), 6)
                entry["std"] = round(float(m.std()), 6)
                entry["min"] = round(float(m.min()), 6)
                entry["max"] = round(float(m.max()), 6)
                entry["quantiles"] = {k: (round(v, 6) if v is not None else None)
                                      for k, v in _quantiles(x).items()}
                entry["histogram"] = _hist(x)
                # zero/near-zero mass
                entry["frac_zero"] = round(float((np.abs(m) < 1e-12).mean()), 6)
        inventory.append(entry)

    # correlation matrix on primary continuous+binary labels
    corr_names = [c for c in PRIMARY_Y if c in cols]
    mat = []
    for a in corr_names:
        row = []
        for b in corr_names:
            row.append(round(_spearman(cols[a], cols[b]), 4))
        mat.append(row)

    # high pairs |rho|>=0.7
    high = []
    for i, a in enumerate(corr_names):
        for j, b in enumerate(corr_names):
            if j <= i:
                continue
            rho = mat[i][j]
            if rho is not None and abs(rho) >= 0.7:
                high.append({"a": a, "b": b, "spearman": rho})

    return {
        "n_rows": n,
        "inventory": inventory,
        "correlation": {"names": corr_names, "spearman": mat, "high_pairs_abs_ge_0.7": high},
        "stream_vs_clean_tp1_agree": float(
            np.nanmean(cols["stream_y_tp1"] == cols["y_tp1"])
        ) if "stream_y_tp1" in cols else None,
    }


def stage2(cols: dict) -> dict[str, Any]:
    """Semantic redundancy: conditional rates and near-deterministic links."""
    n = len(cols["y_tp1"])
    def rate(mask) -> float | None:
        m = mask & np.isfinite(cols["y_tp1"])  # any finite anchor
        if m.sum() == 0:
            return None
        return float(np.nanmean(cols["y_tp1"][m]))  # placeholder unused

    def cond_binary(target: str, condition: np.ndarray) -> dict[str, Any]:
        m = condition & np.isfinite(cols[target])
        if m.sum() == 0:
            return {"n": 0, "rate": None}
        return {"n": int(m.sum()), "rate": round(float(cols[target][m].mean()), 6)}

    def cond_cont(target: str, condition: np.ndarray) -> dict[str, Any]:
        m = condition & np.isfinite(cols[target])
        if m.sum() == 0:
            return {"n": 0, "mean": None, "q50": None}
        x = cols[target][m]
        return {
            "n": int(m.sum()),
            "mean": round(float(x.mean()), 6),
            "q50": round(float(np.median(x)), 6),
        }

    y_tp1 = cols["y_tp1"] == 1
    y_tp2 = cols["y_tp2"] == 1
    y_be = cols["y_survives_be"] == 1
    mfe = cols["y_mfe_r"]
    mae = cols["y_mae_r_heat"]

    # MFE terciles
    mfe_ok = np.isfinite(mfe)
    t1, t2 = np.nanpercentile(mfe[mfe_ok], [33.3, 66.7])
    low_mfe = mfe_ok & (mfe <= t1)
    mid_mfe = mfe_ok & (mfe > t1) & (mfe <= t2)
    high_mfe = mfe_ok & (mfe > t2)

    # MAE terciles
    mae_ok = np.isfinite(mae)
    a1, a2 = np.nanpercentile(mae[mae_ok], [33.3, 66.7])
    low_mae = mae_ok & (mae <= a1)
    high_mae = mae_ok & (mae > a2)

    # time-to-mfe terciles among finite
    ttm = cols["y_time_to_mfe"]
    ttm_ok = np.isfinite(ttm)
    if ttm_ok.sum() > 100:
        u1, u2 = np.nanpercentile(ttm[ttm_ok], [33.3, 66.7])
        fast_mfe = ttm_ok & (ttm <= u1)
        slow_mfe = ttm_ok & (ttm > u2)
    else:
        fast_mfe = slow_mfe = np.zeros(n, dtype=bool)

    checks = {
        "P_tp1_given_high_mfe": cond_binary("y_tp1", high_mfe),
        "P_tp1_given_low_mfe": cond_binary("y_tp1", low_mfe),
        "P_tp2_given_high_mfe": cond_binary("y_tp2", high_mfe),
        "P_tp2_given_y_reached_2r_horizon": cond_binary(
            "y_tp2", cols["y_reached_2r_horizon"] == 1
        ),
        "P_survives_be_given_high_mae": cond_binary("y_survives_be", high_mae),
        "P_survives_be_given_low_mae": cond_binary("y_survives_be", low_mae),
        "P_tp2_given_fast_time_to_mfe": cond_binary("y_tp2", fast_mfe),
        "P_tp2_given_slow_time_to_mfe": cond_binary("y_tp2", slow_mfe),
        "P_tp1_given_survives_be": cond_binary("y_tp1", y_be),
        "P_tp2_given_tp1": cond_binary("y_tp2", y_tp1),
        "P_survives_be_given_tp1": cond_binary("y_survives_be", y_tp1),
        "mean_mfe_given_tp1": cond_cont("y_mfe_r", y_tp1),
        "mean_mfe_given_not_tp1": cond_cont("y_mfe_r", ~y_tp1 & np.isfinite(cols["y_tp1"])),
        "mean_mae_given_survives_be": cond_cont("y_mae_r_heat", y_be),
        "mean_mae_given_not_survives": cond_cont(
            "y_mae_r_heat", ~y_be & np.isfinite(cols["y_survives_be"])
        ),
        "mean_holding_given_tp1": cond_cont("y_holding_bars", y_tp1),
        "mean_holding_given_sl": cond_cont("y_holding_bars", cols["path_sl"] == 1),
        # near identity: y_tp2 vs horizon 2R (different SL gating)
        "agree_y_tp2_vs_reached_2r_horizon": float(
            np.nanmean(cols["y_tp2"] == cols["y_reached_2r_horizon"])
        ),
        "agree_y_survives_be_vs_reached_1r_horizon": float(
            np.nanmean(cols["y_survives_be"] == cols["y_reached_1r_horizon"])
        ),
        "spearman_mfe_tp1": round(_spearman(cols["y_mfe_r"], cols["y_tp1"]), 4),
        "spearman_mfe_tp2": round(_spearman(cols["y_mfe_r"], cols["y_tp2"]), 4),
        "spearman_mae_survives_be": round(_spearman(cols["y_mae_r_heat"], cols["y_survives_be"]), 4),
        "spearman_ttm_tp2": round(_spearman(cols["y_time_to_mfe"], cols["y_tp2"]), 4),
        "spearman_holding_mfe": round(_spearman(cols["y_holding_bars"], cols["y_mfe_r"]), 4),
        "spearman_path_mfe_vs_horizon_mfe": round(
            _spearman(cols["path_mfe_r"], cols["y_mfe_r"]), 4
        ),
        "spearman_path_mae_vs_horizon_mae": round(
            _spearman(cols["path_mae_r_heat"], cols["y_mae_r_heat"]), 4
        ),
        "mfe_tercile_cuts": {"t1": float(t1), "t2": float(t2)},
        "mae_tercile_cuts": {"a1": float(a1), "a2": float(a2)},
    }

    # Independence classification heuristics
    independent = []
    redundant = []
    related = []

    def classify(pair: str, rho: float | None, note: str):
        if rho is None or (isinstance(rho, float) and math.isnan(rho)):
            return
        item = {"pair": pair, "spearman": rho, "note": note}
        if abs(rho) >= 0.85:
            redundant.append(item)
        elif abs(rho) >= 0.5:
            related.append(item)
        else:
            independent.append(item)

    classify("y_mfe_r↔y_tp1", checks["spearman_mfe_tp1"], "excursion vs discrete TP1")
    classify("y_mfe_r↔y_tp2", checks["spearman_mfe_tp2"], "excursion vs discrete TP2")
    classify("y_mae_r_heat↔y_survives_be", checks["spearman_mae_survives_be"], "heat vs BE survival")
    classify("y_time_to_mfe↔y_tp2", checks["spearman_ttm_tp2"], "timing vs TP2")
    classify("y_holding_bars↔y_mfe_r", checks["spearman_holding_mfe"], "duration vs MFE")
    classify(
        "path_mfe_r↔y_mfe_r",
        checks["spearman_path_mfe_vs_horizon_mfe"],
        "walk-bounded vs exit-agnostic MFE",
    )
    classify(
        "path_mae↔horizon_mae",
        checks["spearman_path_mae_vs_horizon_mae"],
        "walk-bounded vs exit-agnostic MAE",
    )
    # binary agreements as soft redundancy
    if checks["agree_y_tp2_vs_reached_2r_horizon"] >= 0.9:
        redundant.append({
            "pair": "y_tp2↔y_reached_2r_horizon",
            "agreement": checks["agree_y_tp2_vs_reached_2r_horizon"],
            "note": "near-duplicate if SL rarely truncates before 2R",
        })
    elif checks["agree_y_tp2_vs_reached_2r_horizon"] >= 0.7:
        related.append({
            "pair": "y_tp2↔y_reached_2r_horizon",
            "agreement": checks["agree_y_tp2_vs_reached_2r_horizon"],
            "note": "related; SL-gating differs from pure horizon",
        })
    if checks["agree_y_survives_be_vs_reached_1r_horizon"] >= 0.9:
        redundant.append({
            "pair": "y_survives_be↔y_reached_1r_horizon",
            "agreement": checks["agree_y_survives_be_vs_reached_1r_horizon"],
            "note": "near-duplicate 1R definitions",
        })
    else:
        related.append({
            "pair": "y_survives_be↔y_reached_1r_horizon",
            "agreement": checks["agree_y_survives_be_vs_reached_1r_horizon"],
            "note": "walk MFE@exit vs full-horizon 1R",
        })

    # dependency graph edges
    edges = []
    for item in redundant:
        edges.append({"from": item["pair"].split("↔")[0], "to": item["pair"].split("↔")[1],
                      "type": "redundant", **{k: v for k, v in item.items() if k != "pair"}})
    for item in related:
        edges.append({"from": item["pair"].split("↔")[0], "to": item["pair"].split("↔")[1],
                      "type": "related", **{k: v for k, v in item.items() if k != "pair"}})
    for item in independent:
        edges.append({"from": item["pair"].split("↔")[0], "to": item["pair"].split("↔")[1],
                      "type": "independent", **{k: v for k, v in item.items() if k != "pair"}})

    return {
        "conditional": checks,
        "classification": {
            "redundant": redundant,
            "related": related,
            "independent": independent,
        },
        "dependency_edges": edges,
    }


def stage3() -> dict[str, Any]:
    """Architectural grouping (static + informed by catalog)."""
    domains = defaultdict(list)
    for spec in LABEL_CATALOG:
        domains[spec["domain"]].append({
            "name": spec["name"],
            "kind": spec["kind"],
            "question": spec["question"],
        })
    return {
        "domains": dict(domains),
        "proposed_model_families": [
            {
                "id": "outcome_path",
                "name": "TradeNet (path milestones)",
                "owns": ["y_tp1", "y_tp2", "y_survives_be"],
                "diagnostic": ["y_R_net", "y_expired_timeout"],
            },
            {
                "id": "excursion_envelope",
                "name": "Excursion intelligence",
                "owns": ["y_mfe_r", "path_mfe_r", "y_reached_0_5r", "y_reached_1r_horizon", "y_reached_2r_horizon"],
                "diagnostic": [],
            },
            {
                "id": "risk_envelope",
                "name": "Risk / heat intelligence",
                "owns": ["y_mae_r_heat", "path_mae_r_heat"],
                "context_not_target": ["risk_distance"],
            },
            {
                "id": "timing_envelope",
                "name": "Time intelligence",
                "owns": ["y_holding_bars", "y_time_to_mfe", "y_time_to_1r"],
                "diagnostic": ["path_time_to_tp", "path_time_to_failure", "y_expired_timeout"],
            },
        ],
        "single_vs_multi_hypothesis": (
            "If Stage-2 shows MFE/MAE/holding weakly coupled AND Stage-4 shows "
            "learnability in more than one domain, multi-head EnvelopeNet is justified; "
            "if only one domain is learnable, collapse or demote the others to diagnostic."
        ),
    }


def stage4(cols: dict) -> dict[str, Any]:
    """Predictability probes — association + stability, not full ML authority."""
    probe_feats: list[str] = cols.get("_probe_feats", [])  # type: ignore
    n = int(cols["_n"][0])
    # temporal split by entry_index median
    ei = cols["entry_index"]
    mid = float(np.nanmedian(ei))
    early = ei <= mid
    late = ei > mid

    targets = [
        "y_tp1", "y_tp2", "y_survives_be", "y_mfe_r", "y_mae_r_heat",
        "y_holding_bars", "y_time_to_mfe", "y_R_net", "y_expired_timeout",
    ]
    per_target = {}
    for t in targets:
        y = cols[t]
        # top feature |spearman|
        feat_scores = []
        for f in probe_feats:
            rho = _spearman(cols[f"f_{f}"], y)
            if not math.isnan(rho):
                feat_scores.append({"feature": f, "spearman": round(rho, 4)})
        feat_scores.sort(key=lambda d: abs(d["spearman"]), reverse=True)

        # best single-feature |rho|
        best = feat_scores[0] if feat_scores else None
        max_abs = abs(best["spearman"]) if best else 0.0

        # temporal base rate / mean stability
        if t.startswith("y_") and t in (
            "y_tp1", "y_tp2", "y_survives_be", "y_expired_timeout"
        ):
            early_m = float(np.nanmean(y[early]))
            late_m = float(np.nanmean(y[late]))
            stability = {
                "early_rate": round(early_m, 6),
                "late_rate": round(late_m, 6),
                "abs_delta": round(abs(early_m - late_m), 6),
                "relative_delta": round(
                    abs(early_m - late_m) / max(early_m, 1e-6), 4
                ),
            }
        else:
            early_m = float(np.nanmean(y[early]))
            late_m = float(np.nanmean(y[late]))
            stability = {
                "early_mean": round(early_m, 6),
                "late_mean": round(late_m, 6),
                "abs_delta": round(abs(early_m - late_m), 6),
            }

        # side
        long_m = float(np.nanmean(y[cols["side_long"] == 1]))
        short_m = float(np.nanmean(y[cols["side_long"] == 0]))

        # vol regime via volatility_ratio terciles if available
        vol_key = "f_volatility_ratio"
        vol_slice = {}
        if vol_key in cols:
            v = cols[vol_key]
            vok = np.isfinite(v) & np.isfinite(y)
            if vok.sum() > 300:
                v1, v2 = np.nanpercentile(v[vok], [33.3, 66.7])
                vol_slice = {
                    "low_vol_mean": round(float(np.nanmean(y[vok & (v <= v1)])), 6),
                    "mid_vol_mean": round(float(np.nanmean(y[vok & (v > v1) & (v <= v2)])), 6),
                    "high_vol_mean": round(float(np.nanmean(y[vok & (v > v2)])), 6),
                }

        # learnability heuristic
        if max_abs >= 0.15:
            learn_tag = "CANDIDATE_LEARNABLE"
        elif max_abs >= 0.08:
            learn_tag = "WEAK_SIGNAL"
        else:
            learn_tag = "NOISY_OR_UNINFORMATIVE_LINEAR"

        # temporal instability flag
        if "abs_delta" in stability and "early_rate" in stability:
            unstable = stability["abs_delta"] > 0.08
        else:
            unstable = stability.get("abs_delta", 0) > max(0.5, 0.25 * abs(early_m))

        per_target[t] = {
            "best_feature_spearman": best,
            "top5_features": feat_scores[:5],
            "max_abs_feature_spearman": round(max_abs, 4),
            "learnability_tag": learn_tag,
            "temporal_stability": stability,
            "temporal_unstable_flag": unstable,
            "by_side": {"long_mean": round(long_m, 6), "short_mean": round(short_m, 6),
                        "abs_delta": round(abs(long_m - short_m), 6)},
            "by_vol_tercile": vol_slice,
            "label_std": round(float(np.nanstd(y)), 6),
            "note": (
                "Spearman vs stored features is a lower bound on learnability; "
                "nonlinear models may do better. Tag is NOT GATE-O authority."
            ),
        }

    return {
        "n": n,
        "probe_features": probe_feats,
        "temporal_split": {"entry_index_median": mid},
        "per_target": per_target,
        "instrument_scope": "BNBUSDT_only — instrument-specificity OPEN until multi-inst",
    }


def stage5(s1: dict, s2: dict, s3: dict, s4: dict) -> dict[str, Any]:
    """Architecture implications driven by evidence."""
    # summarize learnable envelope labels
    env_targets = ["y_mfe_r", "y_mae_r_heat", "y_holding_bars", "y_time_to_mfe"]
    tags = {t: s4["per_target"][t]["learnability_tag"] for t in env_targets if t in s4["per_target"]}
    n_learnable = sum(1 for t in tags.values() if t == "CANDIDATE_LEARNABLE")
    n_weak = sum(1 for t in tags.values() if t == "WEAK_SIGNAL")

    if n_learnable >= 2:
        envelope_structure = "MULTI_HEAD_ENVELOPE_JUSTIFIED"
        rationale = (
            f"{n_learnable} envelope targets show candidate linear association; "
            "keep multi-head EnvelopeNet (excursion + risk + timing) rather than collapse."
        )
    elif n_learnable == 1 and n_weak >= 1:
        envelope_structure = "MULTI_HEAD_WITH_DIAGNOSTIC_SECONDARIES"
        rationale = (
            "One strong domain + weak secondaries: train multi-head but Fusion should "
            "only consume the strong head until GATE-O proves others."
        )
    elif n_learnable == 1:
        envelope_structure = "SINGLE_DOMAIN_ENVELOPE"
        rationale = "Only one envelope domain looks learnable at linear probe; specialize."
    else:
        envelope_structure = "ENVELOPE_PREDICTABILITY_WEAK"
        rationale = (
            "No envelope target clears CANDIDATE_LEARNABLE on linear probe — "
            "do not add model capacity yet; GATE-O must confirm or RETIRE interest."
        )

    # fusion consumption proposal
    fusion = {
        "direct_candidates": [],
        "diagnostic_only": [],
        "planner_candidates": [],
    }
    for t, tag in s4["per_target"].items():
        lt = tag["learnability_tag"]
        if t in ("y_tp1", "y_tp2", "y_survives_be"):
            fusion["direct_candidates"].append({
                "label": t, "consumer": "TradeNet → Fusion neural (after GATE-O/S/P)",
                "probe": lt,
            })
        elif t in ("y_mfe_r", "y_mae_r_heat") and lt == "CANDIDATE_LEARNABLE":
            fusion["direct_candidates"].append({
                "label": t, "consumer": "Envelope coherence / risk_mult (ENV soft channels)",
                "probe": lt,
            })
            fusion["planner_candidates"].append({
                "label": t, "consumer": "TP band / SL heat room",
            })
        elif t in ("y_holding_bars", "y_time_to_mfe") and lt in (
            "CANDIDATE_LEARNABLE", "WEAK_SIGNAL"
        ):
            fusion["planner_candidates"].append({
                "label": t, "consumer": "TTL / time management",
            })
            if lt != "CANDIDATE_LEARNABLE":
                fusion["diagnostic_only"].append({"label": t, "reason": lt})
        elif t in env_targets:
            fusion["diagnostic_only"].append({"label": t, "reason": lt})
        elif t in ("y_R_net", "y_expired_timeout"):
            fusion["diagnostic_only"].append({"label": t, "reason": "diagnostic by design"})

    ownership = [
        {"label": "y_tp1", "market_question": "Will the first target be reached before SL?",
         "existing_model": "TradeNet", "candidate_owner": "TradeNet",
         "overlap_risk": "low", "evidence_note": "Bernoulli path milestone"},
        {"label": "y_tp2", "market_question": "Will +2R be reached before SL?",
         "existing_model": "TradeNet (surrogate policy)", "candidate_owner": "TradeNet",
         "overlap_risk": "medium with y_reached_2r_horizon",
         "evidence_note": f"agree_horizon={s2['conditional'].get('agree_y_tp2_vs_reached_2r_horizon')}"},
        {"label": "y_survives_be", "market_question": "Does path achieve ≥1R MFE (BE room)?",
         "existing_model": "TradeNet", "candidate_owner": "TradeNet",
         "overlap_risk": "medium with y_reached_1r_horizon",
         "evidence_note": f"agree_horizon={s2['conditional'].get('agree_y_survives_be_vs_reached_1r_horizon')}"},
        {"label": "y_R_net", "market_question": "What net R is realized under walk+cost?",
         "existing_model": "RR-B intent (payoff); unused", "candidate_owner": "Diagnostic / GATE-O",
         "overlap_risk": "do not train as TradeNet head", "evidence_note": "continuous economic diagnostic"},
        {"label": "y_mfe_r", "market_question": "How far can price realistically run (horizon)?",
         "existing_model": "No", "candidate_owner": "EnvelopeNet (excursion)",
         "overlap_risk": "related to TP heads but continuous support",
         "evidence_note": f"rho(tp1)={s2['conditional'].get('spearman_mfe_tp1')}"},
        {"label": "y_mae_r_heat", "market_question": "How much adverse heat is likely?",
         "existing_model": "No", "candidate_owner": "EnvelopeNet (risk)",
         "overlap_risk": "not the same as survives_be",
         "evidence_note": f"rho(survives_be)={s2['conditional'].get('spearman_mae_survives_be')}"},
        {"label": "y_holding_bars", "market_question": "How long until hard exit?",
         "existing_model": "Planner TTL (policy, not learned)", "candidate_owner": "EnvelopeNet (timing)",
         "overlap_risk": "low with outcome heads", "evidence_note": "ordinal time"},
        {"label": "y_time_to_mfe", "market_question": "When does maximum opportunity occur?",
         "existing_model": "No", "candidate_owner": "EnvelopeNet (timing)",
         "overlap_risk": "low–medium with holding", "evidence_note": f"rho(tp2)={s2['conditional'].get('spearman_ttm_tp2')}"},
        {"label": "y_time_to_1r", "market_question": "When is +1R first seen?",
         "existing_model": "No", "candidate_owner": "EnvelopeNet (timing) or diagnostic",
         "overlap_risk": "linked to survives_be timing", "evidence_note": "nullable censored"},
        {"label": "y_expired_timeout", "market_question": "Does opportunity expire without TP/SL?",
         "existing_model": "No", "candidate_owner": "Diagnostic (rare event)",
         "overlap_risk": "low", "evidence_note": "check imbalance in Stage 1"},
        {"label": "path_mfe_r / path_mae_r_heat", "market_question": "Walk-bounded excursions under SL/TP",
         "existing_model": "No", "candidate_owner": "Diagnostic twin of horizon envelope",
         "overlap_risk": "high with horizon if path rarely times out",
         "evidence_note": f"rho_mfe={s2['conditional'].get('spearman_path_mfe_vs_horizon_mfe')}"},
        {"label": "risk_distance", "market_question": "What SL distance was set?",
         "existing_model": "CRT / Planner geometry", "candidate_owner": "Context feature — NOT a label",
         "overlap_risk": "n/a", "evidence_note": "input geometry, not prediction target"},
    ]

    return {
        "envelope_structure_recommendation": envelope_structure,
        "rationale": rationale,
        "learnability_tags": tags,
        "fusion_consumption": fusion,
        "ownership_matrix": ownership,
        "do_not_train_yet": [
            "Any head with learnability_tag NOISY_OR_UNINFORMATIVE_LINEAR until nonlinear GATE-O",
            "y_expired_timeout if severe class imbalance",
            "path_* as primary heads if highly redundant with horizon y_*",
        ],
        "authority": "ANALYSIS_ONLY — no train/wire; informs ENV_ARCH_V1 refinement",
    }


def _ascii_hist(counts: list[int], width: int = 40) -> str:
    if not counts:
        return "(empty)"
    m = max(counts) or 1
    lines = []
    for c in counts:
        bar = "#" * int(round(width * c / m))
        lines.append(f"  {bar} {c}")
    return "\n".join(lines)


def render_report(
    s1: dict, s2: dict, s3: dict, s4: dict, s5: dict, meta: dict
) -> str:
    lines = [
        "# Clean-Label Intelligence Analysis — TN_ENV_CLEAN_L1",
        "",
        f"| Field | Value |",
        f"|-------|--------|",
        f"| created_utc | {meta['created_utc']} |",
        f"| dataset | `{meta['dataset']}` |",
        f"| n_rows | {s1['n_rows']} |",
        f"| protocol | TN_ENV_CLEAN_L1 |",
        f"| instrument | BNBUSDT |",
        f"| authority | ANALYSIS_ONLY — no train/wire |",
        "",
        "---",
        "",
        "## Stage 1 — Validate the dataset",
        "",
        "### Label inventory",
        "",
        "| Label | Domain | Kind | Missing% | Key stats |",
        "|-------|--------|------|----------|-----------|",
    ]
    for inv in s1["inventory"]:
        if inv["kind"] == "binary":
            stats = (
                f"pos={inv.get('positive_rate')} ({inv.get('class_balance')})"
            )
        else:
            q = inv.get("quantiles") or {}
            stats = (
                f"mean={inv.get('mean')} std={inv.get('std')} "
                f"q50={q.get('q50')} q80={q.get('q80')}"
            )
        lines.append(
            f"| `{inv['name']}` | {inv['domain']} | {inv['kind']} | "
            f"{round(100*(inv.get('missing_rate') or 0), 2)}% | {stats} |"
        )

    lines += [
        "",
        "### High correlations (|Spearman| ≥ 0.7)",
        "",
    ]
    high = s1["correlation"]["high_pairs_abs_ge_0.7"]
    if not high:
        lines.append("_None at |ρ|≥0.7._")
    else:
        lines.append("| A | B | Spearman |")
        lines.append("|---|---|---------|")
        for h in high:
            lines.append(f"| `{h['a']}` | `{h['b']}` | {h['spearman']} |")

    lines += [
        "",
        f"Stream vs clean y_tp1 agreement: **{s1.get('stream_vs_clean_tp1_agree')}** (F-022 diagnostic).",
        "",
        "### Distribution sketches (1–99% clipped histograms)",
        "",
    ]
    for inv in s1["inventory"]:
        if inv["kind"] != "binary" and inv.get("histogram"):
            lines.append(f"**`{inv['name']}`** clip=[{inv['histogram'].get('clip_lo')}, {inv['histogram'].get('clip_hi')}]")
            lines.append("```")
            lines.append(_ascii_hist(inv["histogram"]["counts"]))
            lines.append("```")
            lines.append("")

    lines += [
        "---",
        "",
        "## Stage 2 — Semantic redundancy",
        "",
        "### Key conditionals",
        "",
        "```json",
        json.dumps(s2["conditional"], indent=2)[:8000],
        "```",
        "",
        "### Classification",
        "",
        f"- **Redundant:** {len(s2['classification']['redundant'])}",
        f"- **Related:** {len(s2['classification']['related'])}",
        f"- **Independent (probed pairs):** {len(s2['classification']['independent'])}",
        "",
        "#### Redundant",
        "",
    ]
    for item in s2["classification"]["redundant"]:
        lines.append(f"- `{item.get('pair')}` — {item}")
    lines += ["", "#### Related", ""]
    for item in s2["classification"]["related"]:
        lines.append(f"- `{item.get('pair')}` — {item}")
    lines += ["", "#### Independent", ""]
    for item in s2["classification"]["independent"]:
        lines.append(f"- `{item.get('pair')}` — {item}")

    lines += [
        "",
        "### Dependency graph (edges)",
        "",
        "```mermaid",
        "graph LR",
    ]
    for e in s2["dependency_edges"]:
        style = {"redundant": "-->", "related": "-.->", "independent": "---"}[e["type"]]
        lines.append(f"  {e['from']} {style}|{e['type']}| {e['to']}")
    lines += ["```", ""]

    lines += [
        "---",
        "",
        "## Stage 3 — Architectural grouping",
        "",
    ]
    for fam in s3["proposed_model_families"]:
        lines.append(f"### {fam['name']} (`{fam['id']}`)")
        lines.append(f"- Owns: {', '.join(f'`{x}`' for x in fam.get('owns', []))}")
        if fam.get("diagnostic"):
            lines.append(f"- Diagnostic: {', '.join(f'`{x}`' for x in fam['diagnostic'])}")
        if fam.get("context_not_target"):
            lines.append(f"- Context (not target): {', '.join(f'`{x}`' for x in fam['context_not_target'])}")
        lines.append("")
    lines.append(f"> {s3['single_vs_multi_hypothesis']}")
    lines.append("")

    lines += [
        "---",
        "",
        "## Stage 4 — Predictability (probe, not GATE-O)",
        "",
        f"Temporal split: entry_index median = {s4['temporal_split']['entry_index_median']}",
        f"Instrument scope: {s4['instrument_scope']}",
        "",
        "| Label | Learnability | Best feature ρ | Temporal unstable? | Side Δ |",
        "|-------|--------------|----------------|--------------------|--------|",
    ]
    for t, info in s4["per_target"].items():
        bf = info["best_feature_spearman"]
        bf_s = f"{bf['feature']}={bf['spearman']}" if bf else "—"
        lines.append(
            f"| `{t}` | {info['learnability_tag']} | {bf_s} | "
            f"{info['temporal_unstable_flag']} | {info['by_side']['abs_delta']} |"
        )
    lines += [
        "",
        "Per-target detail (top features, vol slices) is in `stage4_predictability.json`.",
        "",
        "---",
        "",
        "## Stage 5 — Architecture implications",
        "",
        f"**Envelope structure recommendation:** `{s5['envelope_structure_recommendation']}`",
        "",
        s5["rationale"],
        "",
        "### Fusion / Planner consumption",
        "",
        "```json",
        json.dumps(s5["fusion_consumption"], indent=2),
        "```",
        "",
        "### Ownership matrix (labels → market questions → owners)",
        "",
        "| Label | Market question | Existing model? | Candidate owner | Overlap |",
        "|-------|-----------------|-----------------|-----------------|---------|",
    ]
    for row in s5["ownership_matrix"]:
        lines.append(
            f"| `{row['label']}` | {row['market_question']} | {row['existing_model']} | "
            f"**{row['candidate_owner']}** | {row['overlap_risk']} |"
        )
    lines += [
        "",
        "### Do not train yet",
        "",
    ]
    for d in s5["do_not_train_yet"]:
        lines.append(f"- {d}")
    lines += [
        "",
        "---",
        "",
        "## Bottom line",
        "",
        "1. Clean labels are **complete enough** for research (Stage 1).",
        "2. Outcome heads and envelope continuous targets are **related but not identical** — "
        "envelope still answers *bounds*, TradeNet answers *milestones* (Stage 2).",
        "3. Group into **Outcome / Excursion / Risk / Timing** domains (Stage 3).",
        "4. Learnability is **probe-level only** — GATE-O required before any train authority (Stage 4).",
        "5. Architecture choice (`single` vs `multi-head` envelope) follows Stage 4 tags (Stage 5).",
        "",
        f"**Authority:** {s5['authority']}",
        "",
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--dataset",
        default=None,
        help="path to clean_labels.jsonl (default: BNBUSDT LATEST pointer)",
    )
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args(argv)

    if args.dataset:
        dataset = Path(args.dataset)
        if not dataset.is_absolute():
            dataset = ROOT / dataset
    else:
        pointer = ROOT / "results" / "clean_labels" / "BNBUSDT" / "LATEST" / "pointer.json"
        p = json.loads(pointer.read_text(encoding="utf-8"))
        dataset = Path(p["paths"]["dataset"])

    if not dataset.is_file():
        print(f"ERROR: dataset not found: {dataset}")
        return 2

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = (
        Path(args.out_dir)
        if args.out_dir
        else dataset.parent / f"analysis_{run_id}"
    )
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[analyze] loading {dataset}")
    cols = load_columns(dataset)
    n = int(cols["_n"][0])
    print(f"[analyze] n={n} stage1…")
    s1 = stage1(cols)
    print("[analyze] stage2…")
    s2 = stage2(cols)
    print("[analyze] stage3…")
    s3 = stage3()
    print("[analyze] stage4…")
    s4 = stage4(cols)
    print("[analyze] stage5…")
    s5 = stage5(s1, s2, s3, s4)

    meta = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": str(dataset),
        "n_rows": n,
        "out_dir": str(out_dir),
    }
    (out_dir / "stage1_inventory.json").write_text(
        json.dumps(s1, indent=2), encoding="utf-8"
    )
    (out_dir / "stage2_redundancy.json").write_text(
        json.dumps(s2, indent=2), encoding="utf-8"
    )
    (out_dir / "stage3_grouping.json").write_text(
        json.dumps(s3, indent=2), encoding="utf-8"
    )
    (out_dir / "stage4_predictability.json").write_text(
        json.dumps(s4, indent=2), encoding="utf-8"
    )
    (out_dir / "stage5_architecture.json").write_text(
        json.dumps(s5, indent=2), encoding="utf-8"
    )
    # correlation CSV
    names = s1["correlation"]["names"]
    mat = s1["correlation"]["spearman"]
    with (out_dir / "label_correlation_spearman.csv").open("w", encoding="utf-8") as fh:
        fh.write("," + ",".join(names) + "\n")
        for i, name in enumerate(names):
            fh.write(name + "," + ",".join(str(x) for x in mat[i]) + "\n")

    report = render_report(s1, s2, s3, s4, s5, meta)
    report_path = out_dir / "report.md"
    report_path.write_text(report, encoding="utf-8")

    # durable docs copy
    docs_path = ROOT / "docs" / "analysis" / "clean-label-intelligence-analysis-BNBUSDT.LATEST.md"
    docs_path.parent.mkdir(parents=True, exist_ok=True)
    docs_path.write_text(report, encoding="utf-8")
    (ROOT / "docs" / "analysis" / "clean-label-intelligence-analysis-BNBUSDT.LATEST.json").write_text(
        json.dumps(
            {"meta": meta, "stage5": s5, "stage4_summary": {
                t: {
                    "learnability_tag": s4["per_target"][t]["learnability_tag"],
                    "max_abs_feature_spearman": s4["per_target"][t]["max_abs_feature_spearman"],
                    "best_feature": s4["per_target"][t]["best_feature_spearman"],
                }
                for t in s4["per_target"]
            }, "stage2_classification": s2["classification"]},
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"[analyze] envelope_structure={s5['envelope_structure_recommendation']}")
    print(f"[analyze] wrote {out_dir}")
    print(f"[analyze] docs {docs_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
