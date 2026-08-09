#!/usr/bin/env python3
"""
feature_trace_report.py
========================
Deterministic, per-bar explainability trace over the real XAUUSD M15 feature pipeline.

For each bar in [--start-bar, --end-bar] (1-based; bar 1 == the first data row of the CSV,
literal chronological order, no sampling), renders the walk

    OHLCV -> primitive calculations -> derived mathematics -> normalization
          -> semantic features -> canonical 39-dim feature vector

citing, for every one of the 39 CANONICAL_FEATURES, its real formula/source/function pulled
PROGRAMMATICALLY from configs/formulas/market_ontology.yaml (never hardcoded), its actual
computed value from a real run of FeaturePipeline over the COMPLETE dataset, and a short
interpretation (ontology-authored where the ontology declares one).

Warmup-gap policy (read this before trusting a "NOT_YET_AVAILABLE" bar): FeaturePipeline.run()
calls finalize() at the end, which drops every row where ANY canonical feature is still NaN
(rolling-window warmup). That would silently delete the early bars this report exists to show.
So this script calls the SAME public compute_*()/promote_*() methods run() calls, in the SAME
order, on the FULL CSV -- but deliberately never calls finalize()/build_feature_vector(). Any
feature still NaN at a given bar is rendered as the literal string NOT_YET_AVAILABLE, with the
exact warmup requirement -- never a fabricated number. This is the more honest choice and it
visibly demonstrates the system's no-lookahead guarantee (CLAUDE.md Section 4).

Read-only. Introduces no new formula, config key, or tunable behavior -- it only renders
already-registered math. No src/ package added; this follows the analysis-script precedent of
scripts/governance/feature_surface_query.py and scripts/analysis/crt_xauusd_runtime_trace.py.

Usage:
    PYTHONPATH=src python scripts/analysis/feature_trace_report.py
    PYTHONPATH=src python scripts/analysis/feature_trace_report.py --start-bar 1 --end-bar 100
    PYTHONPATH=src python scripts/analysis/feature_trace_report.py --csv data/mt5/XAUUSD_M15.csv \\
        --output-dir results/feature_trace
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import pandas as pd

from features.feature_pipeline import FeaturePipeline, NORMALIZE_COLS, NORMALIZE_TO_NEW_COL
from features.feature_schema import CANONICAL_FEATURES, FEATURE_INDEX_MAP, SCHEMA_VERSION
from features import candle_math
from features.registry import build_lineage_graph, compute_composition, compute_derived, load_ontology
import logging

logger = logging.getLogger("FEATURE_TRACE_REPORT")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE-STAGE DRIFT GUARD
#
# Verbatim copy of the ordered method-call sequence inside FeaturePipeline.run()
# (feature_pipeline.py:1263-1281), EXCLUDING finalize()/log_critical_feature_health()/
# build_feature_vector() -- this script must call the same compute_*/promote_* methods, in the
# same order, on the full dataset, but never finalize() (which would drop the warmup bars this
# report exists to show). If run() is ever edited, _assert_stage_list_matches_run_source() below
# fails LOUDLY at startup instead of silently tracing a stale sequence.
# ─────────────────────────────────────────────────────────────────────────────
PIPELINE_STAGES = [
    "compute_price_features", "compute_volume_features", "compute_indicators",
    "compute_trend_features", "compute_volatility_regime", "compute_context",
    "compute_structure_liquidity", "compute_normalization",
    "compute_canonical_price_features", "compute_canonical_volatility_features",
    "compute_canonical_ema_features", "compute_canonical_trend_features",
    "compute_canonical_structure_features", "compute_canonical_temporal_features",
    "compute_liquidity_distance", "promote_volume_spike", "compute_canonical_session",
]

_RUN_STAGE_RE = re.compile(r"self\.(compute_\w+|promote_\w+)\(\)")


def _assert_stage_list_matches_run_source() -> None:
    src = inspect.getsource(FeaturePipeline.run)
    live_calls = _RUN_STAGE_RE.findall(src)
    if live_calls != PIPELINE_STAGES:
        raise RuntimeError(
            "feature_trace_report.PIPELINE_STAGES is out of sync with FeaturePipeline.run()'s "
            f"actual call sequence.\n  hardcoded : {PIPELINE_STAGES}\n  live run(): {live_calls}\n"
            "Update PIPELINE_STAGES (and the stage narrative below it) to match the real pipeline."
        )


# ─────────────────────────────────────────────────────────────────────────────
# ONTOLOGY CITATION INDEX (programmatic — never hardcode a formula string)
# ─────────────────────────────────────────────────────────────────────────────
_ONTOLOGY_SECTIONS = (
    "primitives", "feature_compositions", "derived_metrics",
    "rolling_indicators", "temporal_context", "structural_states",
)

# The only 5 canonical features with no ontology entry: raw base inputs, not derived quantities.
RAW_OHLCV_NOTES = {
    "open":   "Raw CSV column 'open' (this bar's opening trade price).",
    "high":   "Raw CSV column 'high' (this bar's highest traded price).",
    "low":    "Raw CSV column 'low' (this bar's lowest traded price).",
    "close":  "Raw CSV column 'close' (this bar's closing trade price).",
    "volume": "Raw CSV column 'volume' (tick/trade volume; some FX brokers report 0 -- see "
              "FeaturePipeline.compute_volume_features 'dead volume' handling).",
}
RAW_OHLCV_SOURCE = "data_ingestion.ohlcv_schema.require_ohlcv_columns (input validation) + source CSV"


def _build_ontology_index(ont: dict) -> dict:
    index: dict = {}
    for section in _ONTOLOGY_SECTIONS:
        for name, spec in (ont.get(section) or {}).items():
            vk = (spec.get("lineage") or {}).get("vector_key")
            if vk:
                index[vk] = {"section": section, "name": name, "spec": spec}
    missing = [n for n in CANONICAL_FEATURES if n not in index and n not in RAW_OHLCV_NOTES]
    if missing:
        raise RuntimeError(
            f"feature_trace_report: no ontology citation source for canonical feature(s) {missing}. "
            "Add a lineage.vector_key entry in configs/formulas/market_ontology.yaml, or extend "
            "RAW_OHLCV_NOTES if this is a genuine base input."
        )
    return index


def _citation_for(name: str, ontology_index: dict) -> dict:
    if name in RAW_OHLCV_NOTES:
        return {
            "is_raw_input": True, "section": "base_input",
            "formula": None, "source": RAW_OHLCV_SOURCE, "id": None,
            "note": RAW_OHLCV_NOTES[name], "spec": {},
        }
    entry = ontology_index[name]
    spec = entry["spec"]
    section = entry["section"]
    if section == "feature_compositions":
        # feature_compositions entries declare numerator/denominator/bounded instead of a
        # formula/impl string -- construct the citation from those declared fields.
        num, den, bounded = spec.get("numerator"), spec.get("denominator"), spec.get("bounded")
        formula = f"{num} / {den}" + (f", bounded {bounded}" if bounded else "")
        source = f"features.registry.compute_composition (numerator={num}, denominator={den})"
        return {
            "is_raw_input": False, "section": section,
            "formula": formula, "source": source, "id": spec.get("id"),
            "note": None, "spec": spec,
        }
    return {
        "is_raw_input": False, "section": section,
        "formula": spec.get("formula"), "source": spec.get("impl"), "id": spec.get("id"),
        "note": None, "spec": spec,
    }


# ─────────────────────────────────────────────────────────────────────────────
# LINEAGE ENGINE — dependency chains, FM-IDs, and the DAG.
#
# Built on features.registry.build_lineage_graph() (the repo's OWN public lineage API) --
# deliberately NOT a second graph implementation. The graph's `depends_on` edges come from the
# ontology's declared `depends_on` lists and ground in its declared `base_inputs`.
#
# IMPORTANT SEMANTIC CAVEAT (surfaced in the report header, not just here): the ontology's
# depends_on is a SEMANTIC lineage, not always a column-level one. `trend_strength` declares
# `close` directly even though the pipeline materializes ma_20 -> ma_slope_20 in between. So the
# DAG shows DECLARED lineage; the Pipeline Stage Column Ledger shows ACTUAL materialization.
# Neither is presented as the other.
# ─────────────────────────────────────────────────────────────────────────────
_TREE_DEPTH_CAP = 24


def _build_fm_id_index(ont: dict) -> dict:
    """Map EVERY ontology node name -> its FM id (not just canonical-vector ones).

    Intermediate nodes carry ids too (true_range FM-040, retest_flag FM-061), so a dependency
    tree can be annotated at every node rather than only at its canonical root.
    """
    fm: dict = {}
    for section in _ONTOLOGY_SECTIONS:
        for name, spec in (ont.get(section) or {}).items():
            if spec.get("id"):
                fm[name] = spec["id"]
    return fm


def _build_lineage_index(ont: dict) -> dict:
    graph = build_lineage_graph(ont)
    return {
        "depends_on": graph["depends_on"],
        "base_inputs": set(graph["base_inputs"]),
        "fm_ids": _build_fm_id_index(ont),
    }


def _transitive_deps(name: str, lineage: dict) -> list:
    """Every transitive dependency of `name`, de-duplicated, in discovery order."""
    out, seen, stack = [], set(), list(lineage["depends_on"].get(name, []))
    while stack:
        node = stack.pop(0)
        if node in seen:
            continue
        seen.add(node)
        out.append(node)
        stack.extend(lineage["depends_on"].get(node, []))
    return out


def _build_dep_tree(name: str, row: "pd.Series", lineage: dict, _depth: int = 0,
                    _ancestors: tuple = ()) -> dict:
    """Recursive dependency tree with this bar's ACTUAL value substituted at every node.

    Grounds at the ontology's declared `base_inputs`. A cycle or a depth-cap hit raises rather
    than silently truncating -- a quietly-truncated lineage tree is worse than no tree.
    """
    if name in _ancestors:
        raise RuntimeError(f"dependency cycle detected: {' -> '.join(_ancestors + (name,))}")
    if _depth > _TREE_DEPTH_CAP:
        raise RuntimeError(
            f"dependency tree exceeded depth cap {_TREE_DEPTH_CAP} at {name!r} "
            f"(path: {' -> '.join(_ancestors)})"
        )
    value, note = _dependency_value(name, row)
    is_base = name in lineage["base_inputs"]
    node = {
        "name": name,
        "value": _to_native(value),
        "note": note,
        "fm_id": lineage["fm_ids"].get(name),
        "is_base_input": is_base,
        "children": [],
    }
    if not is_base:
        for dep in lineage["depends_on"].get(name, []):
            node["children"].append(
                _build_dep_tree(dep, row, lineage, _depth + 1, _ancestors + (name,))
            )
    return node


def _tree_depth(node: dict) -> int:
    return 0 if not node["children"] else 1 + max(_tree_depth(c) for c in node["children"])


def _tree_fm_ids(node: dict) -> list:
    """Flat, de-duplicated FM-id list for every node BELOW the root (discovery order)."""
    out, seen = [], set()

    def walk(n, is_root):
        if not is_root:
            key = n["name"]
            if key not in seen:
                seen.add(key)
                out.append({
                    "name": key,
                    "fm_id": n["fm_id"] or ("[base]" if n["is_base_input"] else None),
                    "is_base_input": n["is_base_input"],
                })
        for c in n["children"]:
            walk(c, False)

    walk(node, True)
    return out


def _tree_unresolved_leaves(node: dict) -> list:
    """Leaf nodes that are NOT declared base_inputs -- i.e. the tree failed to ground."""
    out = []
    if not node["children"] and not node["is_base_input"]:
        out.append(node["name"])
    for c in node["children"]:
        out.extend(_tree_unresolved_leaves(c))
    return out


def _render_dep_tree_lines(node: dict, indent: int = 0, is_root: bool = True) -> list:
    """ASCII indented DAG with values substituted. Root line is the feature itself."""
    lines = []
    fm = f" [{node['fm_id']}]" if node["fm_id"] else (" [base input]" if node["is_base_input"] else "")
    if node["value"] is not None:
        val = _fmt_value(node["value"])
    elif node["note"]:
        val = f"({node['note']})"
    else:
        val = "NOT_YET_AVAILABLE"
    prefix = "" if is_root else "|  " * (indent - 1) + "+- "
    lines.append(f"{prefix}{node['name']} = {val}{fm}")
    for child in node["children"]:
        lines.extend(_render_dep_tree_lines(child, indent + 1, False))
    return lines


# ─────────────────────────────────────────────────────────────────────────────
# NORMALIZATION-METHOD CLASSIFICATION
#
# Describes HOW the pipeline scales each feature (documentation of existing behavior, not a new
# formula). Every one of the 39 CANONICAL_FEATURES must resolve to exactly one label; coverage is
# asserted at startup.
# ─────────────────────────────────────────────────────────────────────────────
_ATR_ABSOLUTE_DIRECT = ("disp_strength", "retest_depth", "volatility_ratio", "liquidity_distance")
_STRUCTURAL_ENUM = (
    "swing_high", "swing_low", "higher_high", "lower_low", "break_of_structure",
    "liquidity_sweep", "sweep_detected", "double_sweep", "trend_bias", "session",
)
_RAW_UNSCALED = ("ema_fast", "ema_slow", "macd_line", "macd_signal", "macd_hist_raw",
                 "body_size", "candle_range")


def _normalization_method(name: str, cfg: dict) -> str:
    if name in NORMALIZE_COLS or name in NORMALIZE_TO_NEW_COL.values():
        return f"ROLLING_ZSCORE_{cfg['zscore_window']}"
    if name == "volume_spike":
        return (f"ADAPTIVE_PERCENTILE_{cfg['volume_spike_percentile']} "
                f"(fixed {cfg['volume_spike_fixed_fallback']}x fallback when window < "
                f"{cfg['volume_spike_min_samples']} samples)")
    if name in ("ema_spread", "momentum_score"):
        basis = cfg["normalization_basis"]
        return "ATR_RELATIVE (divides by close-relative atr)" if basis == "atr_relative" \
            else "ATR_ABSOLUTE (divides by atr*close, scale-invariant)"
    if name in _ATR_ABSOLUTE_DIRECT:
        return "ATR_ABSOLUTE (divides by atr*close directly, basis-independent)"
    if name == "liquidity_pressure_score":
        return "EXPONENTIAL_DECAY of ATR-normalized distance, bounded [0, 1]"
    if name == "body_ratio":
        return "BOUNDED_RATIO_NO_SCALING (body_size/candle_range, structurally in [0, 1])"
    if name == "atr":
        return "CLOSE_RELATIVE_RATIO (atr_14_raw/close), no further scaling"
    if name == "rsi_14":
        return "BOUNDED_OSCILLATOR_NO_SCALING (formula bounds to [0, 100])"
    if name == "volatility_regime":
        return f"ROLLING_RANK_TERCILE (window={cfg['volatility_percentile_window']})"
    if name == "volume_ratio":
        return "RATIO_TO_ROLLING_MEAN (volume / volume_ma20), not further scaled"
    if name == "candles_since_retest":
        return "NONE (raw bar count since the last liquidity sweep)"
    if name == "hour_of_day":
        return "NONE (raw calendar integer 0-23, cyclic not linear)"
    if name in _RAW_UNSCALED:
        return "NONE (raw price/geometry units, not normalized)"
    if name in _STRUCTURAL_ENUM:
        return "NONE (enumerated/categorical state, not a scaled magnitude)"
    if name in RAW_OHLCV_NOTES:
        return "NONE (raw input)"
    raise RuntimeError(f"feature_trace_report: '{name}' has no normalization-method classification")


# ─────────────────────────────────────────────────────────────────────────────
# DEPENDENCY ("intermediates") LOOKUP — sourced from the ontology's own depends_on list
# ─────────────────────────────────────────────────────────────────────────────
_DEP_COMPUTED_INLINE = {
    "close_delta": lambda row: float(row["close"]) - float(row["prev_close"]),
}
_DEP_UNMATERIALIZED_NOTE = {
    "ref_high": "internal Series in FeaturePipeline.compute_liquidity_distance "
                "(last_swing_high_price.shift(1)); not persisted as a DataFrame column",
    "ref_low": "internal Series in FeaturePipeline.compute_liquidity_distance "
               "(last_swing_low_price.shift(1)); not persisted as a DataFrame column",
    "bos_level": "internal Series in FeaturePipeline.compute_liquidity_distance "
                 "(forward-filled break-of-structure level); not persisted as a DataFrame column",
}


def _dependency_value(dep: str, row: "pd.Series"):
    """Returns (value_or_None, note_or_None). Never fabricates -- a genuinely unrecoverable
    dependency gets an explicit note instead of a number."""
    if dep == "timestamp":
        return None, "shown as this bar's own timestamp above, not a numeric intermediate"
    if dep in row.index:
        val = row[dep]
        return (None if val != val else float(val)), None
    if dep in _DEP_COMPUTED_INLINE:
        return _DEP_COMPUTED_INLINE[dep](row), None
    if dep in _DEP_UNMATERIALIZED_NOTE:
        return None, _DEP_UNMATERIALIZED_NOTE[dep]
    return None, f"dependency {dep!r} not found as a materialized column"


# ─────────────────────────────────────────────────────────────────────────────
# BIRTH CERTIFICATE — first available bar AND the derived reason.
#
# The reason is DERIVED, never asserted: take the transitive dependency with the largest
# first_valid_index (the binding constraint), and the remainder is this feature's OWN rolling
# contribution. Measured examples on the active config: disp_strength/ema_spread/momentum_score/
# liquidity_distance add +0 of their own (pure `atr` inheritance); atr adds +13 over true_range;
# rsi_14 +14 over close; macd_hist_z +49 over macd_hist_raw; trend_strength +78 over close.
#
# HONESTY CONSTRAINT: an "own contribution" spanning a multi-stage chain (trend_strength's +78 is
# ma_20 -> diff -> rolling(10) -> z-score(50), across TWO pipeline functions) must NOT be collapsed
# into a single window number. It is reported as a multi-stage chain citing every relevant config
# key, because the ontology's declared depends_on for that feature is semantic (`close`) and skips
# the materialized intermediates.
# ─────────────────────────────────────────────────────────────────────────────

# Config keys that shape a feature's OWN rolling contribution, beyond what the ontology's
# per-entry `config_key`/`config_keys` already declares. Only needed where the declared
# dependency chain is semantic rather than column-level.
_EXTRA_WINDOW_CONFIG_KEYS = {
    "trend_strength": ("ma_periods", "trend_strength_window", "zscore_window"),
    "macd_hist_z": ("zscore_window",),
}


def _declared_window_keys(name: str, citation: dict) -> list:
    spec = citation.get("spec") or {}
    keys = []
    if spec.get("config_key"):
        keys.append(spec["config_key"])
    keys.extend(spec.get("config_keys") or [])
    keys.extend(f"feature_pipeline.{k}" for k in _EXTRA_WINDOW_CONFIG_KEYS.get(name, ()))
    seen, out = set(), []
    for k in keys:
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


def _birth_certificate(name: str, citation: dict, lineage: dict, first_valid: dict,
                       col_first_valid: dict, cfg: dict) -> dict:
    own_fv = first_valid.get(name)
    own_bar = None if own_fv is None else own_fv + 1  # 1-based

    cands = [(d, col_first_valid[d]) for d in _transitive_deps(name, lineage)
             if col_first_valid.get(d) is not None]
    binding_dep, binding_fv = max(cands, key=lambda kv: kv[1]) if cands else (None, 0)

    own_window_bars = None if own_fv is None else own_fv - binding_fv
    keys = _declared_window_keys(name, citation)
    config_keys = {}
    for k in keys:
        short = k.split(".", 1)[1] if k.startswith("feature_pipeline.") else k
        if short in cfg:
            config_keys[k] = cfg[short]

    declared_lookback = (citation.get("spec") or {}).get("lookback")

    if own_fv is None or own_fv == 0:
        reason = "Available from bar 1 -- no rolling history required."
    elif own_window_bars == 0 and binding_dep:
        reason = (f"Inherited entirely from `{binding_dep}` (first valid at bar {binding_fv + 1}); "
                  f"this feature adds no rolling window of its own.")
    else:
        base = (f"`{binding_dep}` is valid from bar {binding_fv + 1}; this feature adds "
                f"{own_window_bars} more bar(s) of its own"
                if binding_dep else
                f"Requires {own_window_bars} bar(s) of rolling history")
        if name in _EXTRA_WINDOW_CONFIG_KEYS:
            base += (" via a MULTI-STAGE rolling chain (the ontology's declared dependency is "
                     "semantic and skips the materialized intermediates -- see the Pipeline "
                     "Stage Column Ledger for actual materialization)")
        if config_keys:
            base += " (config: " + ", ".join(f"{k}={v}" for k, v in config_keys.items()) + ")"
        reason = base + "."

    return {
        "first_available_bar": own_bar,
        "binding_dependency": binding_dep,
        "binding_dep_first_bar": None if binding_dep is None else binding_fv + 1,
        "own_window_bars": own_window_bars,
        "declared_lookback": declared_lookback,
        "config_keys": config_keys,
        "reason_text": reason,
    }


# ─────────────────────────────────────────────────────────────────────────────
# INTERPRETATION — [ONTOLOGY] exact state match, [HEURISTIC-BUCKET] ontology text with a
# heuristic high/low selection, or [SCRIPT-NOTE] for the 5 raw OHLCV columns only.
# ─────────────────────────────────────────────────────────────────────────────

def _parse_numeric_bounds(spec: dict):
    for key in ("clip", "bounded"):
        val = spec.get(key)
        if isinstance(val, (list, tuple)) and len(val) == 2:
            try:
                return float(val[0]), float(val[1])
            except (TypeError, ValueError):
                pass
    bounds = spec.get("bounds")
    if isinstance(bounds, str):
        s = bounds.strip()
        if s.startswith("[") and s.endswith("]"):
            try:
                lo_s, hi_s = s[1:-1].split(",")
                return float(lo_s), float(hi_s)
            except ValueError:
                return None
    return None


def _interpret(name: str, value: float, citation: dict, rank_lookup: "pd.Series"):
    if citation["is_raw_input"]:
        return citation["note"], "SCRIPT-NOTE"
    spec = citation["spec"]
    states = spec.get("states") or []
    if states:
        for st in states:
            try:
                if float(st["value"]) == float(value):
                    return f"{st['name']} -- {st['description']}", "ONTOLOGY"
            except (TypeError, ValueError):
                continue
        return f"(bar value {value!r} matched no declared state for {name})", "SCRIPT-NOTE"
    interp = (spec.get("semantics") or {}).get("interpretation") or {}
    high_txt, low_txt = interp.get("high"), interp.get("low")
    if not (high_txt or low_txt):
        return "(ontology declares no interpretation text for this feature)", "SCRIPT-NOTE"
    bounds = _parse_numeric_bounds(spec)
    if bounds is not None:
        lo, hi = bounds
        mid = (lo + hi) / 2.0
        chosen = high_txt if value >= mid else low_txt
        note = f"(bar value {value:.6g} vs declared range [{lo:g}, {hi:g}], midpoint {mid:g})"
    else:
        pct = rank_lookup.get(name)
        if pct is None or pct != pct:
            chosen, note = (high_txt or low_txt or ""), "(no full-dataset percentile available)"
        else:
            chosen = high_txt if pct >= 0.5 else low_txt
            note = f"(bar value ranks at the {pct * 100:.1f} percentile of this feature's full-dataset distribution)"
    text = f"{chosen} {note}"
    caveat = interp.get("caveat")
    if caveat:
        text += f" CAVEAT: {caveat}"
    return text, "HEURISTIC-BUCKET"


# ─────────────────────────────────────────────────────────────────────────────
# SCALAR CROSS-CHECK (secondary verification only — the report always DISPLAYS the pipeline's
# own column value, never this one). Doubles as a live registry/pipeline parity probe.
# ─────────────────────────────────────────────────────────────────────────────

def _cross_check(name: str, citation: dict, row: "pd.Series", cfg: dict, ont: dict):
    if citation["is_raw_input"]:
        return None, None
    o, h, l, c = float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"])
    try:
        if name == "body_size":
            val = candle_math.body_size(o, c)
        elif name == "candle_range":
            val = candle_math.candle_range(h, l)
        elif name == "body_ratio":
            val = compute_composition("body_ratio", o, h, l, c, ontology=ont)
        elif citation["section"] == "derived_metrics":
            atr = float(row["atr"])
            if name == "disp_strength":
                val = compute_derived(
                    "disp_strength", ontology=ont, body_size=float(row["body_size"]), atr=atr,
                    close=c, clip_low=cfg["disp_strength_clip_low"], clip_high=cfg["disp_strength_clip_high"],
                )
            elif name == "retest_depth":
                if int(row["retest_flag"]) == 0:
                    val = 0.0
                else:
                    val = compute_derived(
                        "retest_depth", ontology=ont, close=c, ema_fast=float(row["ema_fast"]), atr=atr,
                        clip_low=cfg["retest_depth_clip_low"], clip_high=cfg["retest_depth_clip_high"],
                    )
            elif name == "ema_spread" and cfg["normalization_basis"] == "atr_relative":
                val = compute_derived("ema_spread", ontology=ont, ema_fast=float(row["ema_fast"]),
                                       ema_slow=float(row["ema_slow"]), atr=atr)
            elif name == "momentum_score" and cfg["normalization_basis"] == "atr_relative":
                close_delta = float(row["close"]) - float(row["prev_close"])
                val = compute_derived("momentum_score", ontology=ont, close_delta=close_delta, atr=atr)
            elif name == "volatility_ratio":
                val = compute_derived("volatility_ratio", ontology=ont, high=h, low=l, atr=atr, close=c)
            elif name == "liquidity_pressure_score":
                val = compute_derived(
                    "liquidity_pressure_score", ontology=ont, distance=float(row["liquidity_distance"]),
                    decay_coeff=cfg["liquidity_decay_coeff"], nan_sentinel=cfg["liquidity_nan_sentinel"],
                )
            else:
                return None, None
        else:
            return None, None
    except Exception as exc:  # pragma: no cover -- defensive; a cross-check failure must not crash the report
        logger.warning("cross-check failed for %s: %s", name, exc)
        return None, None

    pipeline_val = row[name]
    if pipeline_val != pipeline_val:  # NaN -- warmup, nothing to compare against
        return float(val), None
    matches = abs(float(val) - float(pipeline_val)) <= max(1e-4, 1e-4 * abs(float(pipeline_val)))
    return float(val), bool(matches)


# ─────────────────────────────────────────────────────────────────────────────
# EXECUTION-STAGE PROVENANCE ("created by" + column-birth ledger)
#
# Derived EMPIRICALLY from the real stage loop: a column's birth stage is the first stage after
# which it exists in df.columns, and its rewrite stages are those after which its values changed.
#
# This REPLACES an earlier version that inferred the stage from the ontology SECTION -- which filed
# swing_high under "derived mathematics" when it is in fact born in compute_structure_liquidity.
# The section is a semantic grouping; this is the actual execution stage.
#
# SCOPE LABEL (load-bearing): rewrite detection compares values over the RENDERED BARS ONLY. A
# column that is rewritten only outside that window is reported as unmodified, so the ledger says
# "detected across the rendered bars" and never claims a dataset-wide property.
# ─────────────────────────────────────────────────────────────────────────────

def _build_stage_provenance(raw_cols: set, col_sets: list, window_snaps: list) -> dict:
    """col_sets[i] / window_snaps[i] are the column set and rendered-window frame AFTER stage i.
    `raw_cols` are the columns present BEFORE any stage runs (the raw OHLCV input) -- these are
    never attributed to stage 1, they predate the pipeline entirely.

    Returns {column: {"born_stage_index", "born_stage_name", "rewritten_by"}} (1-based indices;
    born_stage_index=0 means "raw input, no pipeline stage produced it").
    """
    prov: dict = {col: {"born_stage_index": 0, "born_stage_name": None, "rewritten_by": []}
                  for col in raw_cols}
    for i, cols in enumerate(col_sets):
        prev = col_sets[i - 1] if i else raw_cols
        for col in cols - prev:
            prov[col] = {
                "born_stage_index": i + 1,
                "born_stage_name": PIPELINE_STAGES[i],
                "rewritten_by": [],
            }
    # Rewrite detection: same column, different values across consecutive stage snapshots.
    for i in range(1, len(window_snaps)):
        prev_df, cur_df = window_snaps[i - 1], window_snaps[i]
        for col in set(prev_df.columns) & set(cur_df.columns):
            a, b = prev_df[col], cur_df[col]
            if not a.equals(b):
                prov.setdefault(col, {"born_stage_index": None, "born_stage_name": None,
                                      "rewritten_by": []})
                prov[col]["rewritten_by"].append(
                    {"stage_index": i + 1, "stage_name": PIPELINE_STAGES[i]}
                )
    return prov


_STAGE_TITLES = {
    0: "Raw OHLCV (input columns, no pipeline stage)",
}


def _stage_group_title(stage_index) -> str:
    if stage_index is None or stage_index == 0:
        return _STAGE_TITLES[0]
    return f"Pipeline stage {stage_index}/{len(PIPELINE_STAGES)} -- {PIPELINE_STAGES[stage_index - 1]}()"


def _to_native(v):
    if v is None:
        return None
    if isinstance(v, np.floating):
        v = float(v)
    elif isinstance(v, np.integer):
        v = int(v)
    if isinstance(v, float) and (v != v or math.isinf(v)):
        return None
    return v


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# PER-BAR RECORD BUILDING
# ─────────────────────────────────────────────────────────────────────────────

def _build_feature_entry(name: str, row: "pd.Series", ontology_index: dict, rank_lookup: "pd.Series",
                          cfg: dict, ont: dict, bar_number: int, first_valid: dict,
                          snap_vol_seed, snap_pre_norm_trend, lineage: dict,
                          stage_provenance: dict, col_first_valid: dict) -> dict:
    citation = _citation_for(name, ontology_index)
    raw_value = row[name]
    is_nan = raw_value != raw_value
    warmup_gap = None
    if is_nan:
        fv = first_valid[name]
        warmup_gap = f"NOT_YET_AVAILABLE (warmup: needs {fv + 1} bars, have {bar_number})"
        interpretation_text, interpretation_class = (
            "(warmup -- not yet computable; see warmup_gap)", "SCRIPT-NOTE",
        )
    else:
        interpretation_text, interpretation_class = _interpret(name, float(raw_value), citation, rank_lookup)

    intermediates = []
    if not citation["is_raw_input"]:
        for dep in (citation["spec"].get("depends_on") or []):
            dep_val, dep_note = _dependency_value(dep, row)
            intermediates.append({"name": dep, "value": _to_native(dep_val), "note": dep_note})

    cross_val, cross_matches = (None, None) if is_nan else _cross_check(name, citation, row, cfg, ont)

    # ── Dependency tree (items 1, 3, 5): grounds at base_inputs; raises if it doesn't. ──
    dep_tree = _build_dep_tree(name, row, lineage)
    unresolved = _tree_unresolved_leaves(dep_tree)
    if unresolved:
        raise RuntimeError(
            f"feature_trace_report: dependency tree for '{name}' has unresolved leaf node(s) "
            f"{unresolved} that are neither materialized columns nor declared base_inputs. "
            "This must be fixed in market_ontology.yaml (depends_on / base_inputs), never "
            "silently truncated."
        )
    declared_depth = (citation.get("spec") or {}).get("lineage", {}).get("derivation_depth")

    # ── Created-by / modified-by (items 2, 4): empirically detected from the real stage loop. ──
    prov = stage_provenance.get(name, {"born_stage_index": None, "born_stage_name": None,
                                        "rewritten_by": []})
    created_by = {
        "function": (f"FeaturePipeline.{prov['born_stage_name']}" if prov["born_stage_name"]
                     else "raw input (predates the pipeline)"),
        "stage_index": prov["born_stage_index"],
        "stage_name": prov["born_stage_name"],
        "column": name,
    }

    # ── Birth certificate (item 6): first available bar + a DERIVED (not asserted) reason. ──
    birth_cert = _birth_certificate(name, citation, lineage, first_valid, col_first_valid, cfg)

    entry = {
        "vector_index": FEATURE_INDEX_MAP[name],
        "formula": citation["formula"] or citation["note"],
        "source": citation["source"],
        "ontology_id": citation["id"],
        "value": None if is_nan else _to_native(raw_value),
        "warmup_gap": warmup_gap,
        "intermediates": intermediates,
        "normalization_method": _normalization_method(name, cfg),
        "interpretation": interpretation_text,
        "interpretation_class": interpretation_class,
        "cross_check_value": cross_val,
        "cross_check_matches": cross_matches,
        "dependency_tree": dep_tree,
        "dependency_fm_ids": _tree_fm_ids(dep_tree),
        "declared_derivation_depth": declared_depth,
        "computed_tree_depth": _tree_depth(dep_tree),
        "created_by": created_by,
        "modified_by_stages": prov["rewritten_by"],
        "birth_certificate": birth_cert,
    }
    if name == "trend_strength" and snap_pre_norm_trend is not None:
        entry["pre_normalization_raw_value"] = _to_native(snap_pre_norm_trend.iloc[row.name])
    if name == "volume_spike" and snap_vol_seed is not None:
        entry["pre_normalization_seed_value"] = _to_native(snap_vol_seed.iloc[row.name])
    return entry


def _build_bar_record(bar_number: int, row: "pd.Series", ontology_index: dict, rank_lookup: "pd.Series",
                       cfg: dict, ont: dict, first_valid: dict, snap_vol_seed, snap_pre_norm_trend,
                       csv_path: Path, csv_sha256: str, prod_version: str, lineage: dict,
                       stage_provenance: dict, col_first_valid: dict) -> dict:
    features = {}
    for name in CANONICAL_FEATURES:
        features[name] = _build_feature_entry(
            name, row, ontology_index, rank_lookup, cfg, ont, bar_number, first_valid,
            snap_vol_seed, snap_pre_norm_trend, lineage, stage_provenance, col_first_valid,
        )
    canonical_vector = [features[n]["value"] for n in CANONICAL_FEATURES]
    ts = row["timestamp"]
    ts_str = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
    return {
        "schema_version": SCHEMA_VERSION,
        "generator": "scripts/analysis/feature_trace_report.py",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_csv": str(csv_path),
        "source_csv_sha256": csv_sha256,
        "prod_config_version": prod_version,
        "bar_number": bar_number,
        "row_index_0based": bar_number - 1,
        "timestamp": ts_str,
        "ohlcv": {
            "open": _to_native(row["open"]), "high": _to_native(row["high"]),
            "low": _to_native(row["low"]), "close": _to_native(row["close"]),
            "volume": _to_native(row["volume"]),
        },
        "features": features,
        "canonical_vector": canonical_vector,
    }


# ─────────────────────────────────────────────────────────────────────────────
# MARKDOWN RENDERING
# ─────────────────────────────────────────────────────────────────────────────

def _fmt_value(v) -> str:
    if v is None:
        return "NOT_YET_AVAILABLE"
    if isinstance(v, float):
        return f"{v:.6g}"
    return str(v)


def _render_bar_markdown(record: dict) -> str:
    lines = []
    lines.append(f"## Bar {record['bar_number']} -- {record['timestamp']} UTC "
                 f"(schema v{record['schema_version']}, PROD_VERSION={record['prod_config_version']})")
    lines.append("")
    o = record["ohlcv"]
    lines.append("### Raw OHLCV")
    lines.append(f"open={_fmt_value(o['open'])}  high={_fmt_value(o['high'])}  "
                 f"low={_fmt_value(o['low'])}  close={_fmt_value(o['close'])}  volume={_fmt_value(o['volume'])}")
    lines.append("")
    lines.append("### Stage trace: OHLCV -> primitive -> derived -> normalization -> semantic -> canonical")
    lines.append("(grouped by the REAL pipeline execution stage that materializes each column -- see "
                 "the Pipeline Stage Column Ledger in the header for the full stage-by-stage picture)")
    lines.append("")

    by_stage: dict = {}
    for name, entry in record["features"].items():
        idx = entry["created_by"]["stage_index"] or 0
        by_stage.setdefault(idx, []).append((name, entry))

    for idx in sorted(by_stage):
        lines.append(f"**{_stage_group_title(idx)}**")
        for name, entry in by_stage[idx]:
            val = _fmt_value(entry["value"]) if entry["warmup_gap"] is None else entry["warmup_gap"]
            lines.append(f"  {name} = {val}")
        lines.append("")

    lines.append("### Full per-feature ledger (all 39, CANONICAL_FEATURES order)")
    lines.append("")
    for name, entry in record["features"].items():
        idx = entry["vector_index"]
        oid = f" ({entry['ontology_id']})" if entry["ontology_id"] else ""
        lines.append(f"[{idx:02d}] {name}{oid}")
        lines.append(f"  formula:        {entry['formula']}")
        lines.append(f"  created by:     {entry['created_by']['function']}"
                     + (f" (pipeline stage {entry['created_by']['stage_index']}/{len(PIPELINE_STAGES)})"
                        if entry['created_by']['stage_index'] else "")
                     + f" -> writes column `{entry['created_by']['column']}`")
        if entry["modified_by_stages"]:
            mods = ", ".join(f"{m['stage_name']}() (stage {m['stage_index']})"
                             for m in entry["modified_by_stages"])
            lines.append(f"  rewritten by:   {mods} (detected across the rendered bars)")
        val_str = entry["warmup_gap"] if entry["warmup_gap"] else _fmt_value(entry["value"])
        lines.append(f"  value:          {val_str}")
        lines.append(f"  dependency tree (declared depth {entry['declared_derivation_depth']}, "
                     f"computed depth {entry['computed_tree_depth']}):")
        for tree_line in _render_dep_tree_lines(entry["dependency_tree"]):
            lines.append(f"    {tree_line}")
        if entry["dependency_fm_ids"]:
            fm_parts = [f"{d['name']}={d['fm_id']}" for d in entry["dependency_fm_ids"]]
            lines.append(f"  depends on (FM-IDs): {', '.join(fm_parts)}")
        if "pre_normalization_raw_value" in entry:
            lines.append(f"  pre-zscore raw: {_fmt_value(entry['pre_normalization_raw_value'])}")
        if "pre_normalization_seed_value" in entry:
            lines.append(f"  pre-adaptive fixed-threshold seed: {_fmt_value(entry['pre_normalization_seed_value'])}")
        lines.append(f"  normalization:  {entry['normalization_method']}")
        if entry["cross_check_value"] is not None:
            match_str = "MATCH" if entry["cross_check_matches"] else "MISMATCH"
            lines.append(f"  cross-check:    {_fmt_value(entry['cross_check_value'])} ({match_str} vs pipeline column)")
        bc = entry["birth_certificate"]
        lines.append(f"  birth certificate: first available bar {bc['first_available_bar']} -- {bc['reason_text']}")
        lines.append(f"  interpretation: [{entry['interpretation_class']}] {entry['interpretation']}")
        lines.append("")

    lines.append(f"### Canonical feature vector (39-dim, CANONICAL_FEATURES order, schema v{record['schema_version']})")
    vec_str = "[" + ", ".join(_fmt_value(v) for v in record["canonical_vector"]) + "]"
    lines.append(vec_str)
    lines.append("")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def _render_pipeline_stage_ledger(stage_provenance: dict) -> list:
    """Global, once-per-report section: which pipeline stage introduces / rewrites which columns.

    Cross-feature by nature (a stage introduces many columns at once), so it does NOT belong in a
    per-bar per-feature entry -- rendered once, here, in the header.
    """
    by_stage: dict = {}
    rewrites: dict = {}
    for col, prov in stage_provenance.items():
        idx = prov["born_stage_index"] or 0
        by_stage.setdefault(idx, []).append(col)
        for m in prov["rewritten_by"]:
            rewrites.setdefault(m["stage_index"], []).append((col, m["stage_name"]))

    lines = ["## Pipeline Stage Column Ledger", ""]
    lines.append(
        "Empirically detected from the real stage loop (column existence + value diffs across "
        "consecutive stage snapshots over the RENDERED bars) -- not asserted from the ontology. "
        "`FeaturePipeline.run()`'s real call order: " + " -> ".join(PIPELINE_STAGES) + "."
    )
    lines.append("")
    # Union of both maps' keys: a stage that introduces ZERO new columns (e.g. promote_volume_spike,
    # which only rewrites the pre-existing volume_spike column) must still get a line so its
    # rewrite is visible -- iterating by_stage alone silently drops exactly that case.
    for idx in sorted(set(by_stage) | set(rewrites)):
        cols = sorted(by_stage.get(idx, []))
        intro = f"introduces `{', '.join(cols)}`" if cols else "introduces no new columns"
        lines.append(f"- **{_stage_group_title(idx)}**: {intro}")
        for rw_col, rw_stage in rewrites.get(idx, []):
            lines.append(f"    - rewrites `{rw_col}` (previously born earlier; value changes "
                         "detected across the rendered bars)")
    lines.append("")
    return lines


def _render_header(args, csv_path: Path, csv_sha256: str, prod_version: str, first_valid: dict,
                   n_total_rows: int, stage_provenance: dict) -> str:
    lines = []
    lines.append("# XAUUSD M15 Feature Explainability Trace")
    lines.append("")
    lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"Source CSV: `{csv_path}` (SHA-256: `{csv_sha256}`), {n_total_rows} total rows")
    lines.append(f"Active production config: `{prod_version}`")
    lines.append(f"Canonical feature schema version: v{SCHEMA_VERSION} ({len(CANONICAL_FEATURES)}-dim)")
    lines.append(f"Bars rendered: {args.start_bar}-{args.end_bar} (1-based; bar 1 = the first CSV "
                 "data row after the header, in original chronological order, no sampling/skipping)")
    lines.append("")
    lines.append(
        "**Warmup-gap policy:** the real pipeline's `finalize()` step drops every row where any "
        "canonical feature is still NaN (rolling-window warmup) -- this would silently delete the "
        "early bars this report shows. This report calls the same `compute_*`/`promote_*` methods "
        "`FeaturePipeline.run()` calls, in the same order, over the COMPLETE dataset, but never "
        "calls `finalize()`. Any feature still NaN at a bar is rendered as the literal string "
        "`NOT_YET_AVAILABLE (warmup: needs N bars, have M)` -- never a fabricated number."
    )
    lines.append("")
    gaps = {n: fv for n, fv in first_valid.items() if fv is not None and fv > 0}
    if gaps:
        lines.append("**Warmup gaps within the rendered window** (computed from the real pipeline "
                     "output via `Series.first_valid_index()`, not hardcoded):")
        for name, fv in sorted(gaps.items(), key=lambda kv: kv[1]):
            lines.append(f"  - `{name}`: NaN through bar {fv}, first valid at bar {fv + 1}")
    else:
        lines.append("**Warmup gaps within the rendered window:** none -- every rendered bar has "
                     "all 39 canonical features populated.")
    lines.append("")
    lines.append(
        "Interpretation-text provenance tags: `[ONTOLOGY]` = exact enumerated-state match from "
        "`configs/formulas/market_ontology.yaml`; `[HEURISTIC-BUCKET]` = ontology-authored high/low "
        "text, selected by a heuristic (bounds midpoint or full-dataset percentile rank) -- only the "
        "*selection* is heuristic, the sentence itself is ontology text; `[SCRIPT-NOTE]` = the 5 raw "
        "OHLCV columns only (no ontology entry -- they are base inputs, not derived quantities)."
    )
    lines.append("")
    lines.append(
        "**Two DISTINCT lineage views in this report -- do not conflate them.** The per-feature "
        "*dependency tree* below is the ontology's DECLARED (semantic) lineage: what a feature "
        "means it depends on. The *Pipeline Stage Column Ledger* right below is the ACTUAL column "
        "materialization order. These can differ: `trend_strength` declares `close` directly (the "
        "semantic dependency), but the pipeline actually computes it through the materialized chain "
        "`ma_20 -> ma_slope_20 -> trend_strength` across two separate stage functions. Presenting "
        "either view as the other would be exactly the kind of overclaim this report exists to avoid."
    )
    lines.append("")
    lines.extend(_render_pipeline_stage_ledger(stage_provenance))
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# CLI / MAIN
# ─────────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--csv", default="data/mt5/XAUUSD_M15.csv",
                    help="Path to the OHLCV CSV (default: data/mt5/XAUUSD_M15.csv)")
    p.add_argument("--start-bar", type=int, default=1,
                    help="First bar to render, 1-based (bar 1 = first CSV data row). Default: 1")
    p.add_argument("--end-bar", type=int, default=100,
                    help="Last bar to render, 1-based, inclusive. Default: 100")
    p.add_argument("--output-dir", default="results/feature_trace",
                    help="Output directory for the .md and .jsonl artifacts. Default: results/feature_trace")
    p.add_argument("--run-tag", default=None,
                    help="Optional filename suffix, for side-by-side reruns.")
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    if args.start_bar < 1 or args.end_bar < args.start_bar:
        print(f"ERROR: invalid bar range --start-bar {args.start_bar} --end-bar {args.end_bar}", file=sys.stderr)
        return 1

    _assert_stage_list_matches_run_source()

    csv_path = Path(args.csv)
    if not csv_path.is_absolute():
        csv_path = ROOT / csv_path
    if not csv_path.exists():
        print(f"ERROR: csv not found: {csv_path}", file=sys.stderr)
        return 1

    logger.info("Loading %s ...", csv_path)
    raw = pd.read_csv(csv_path)
    csv_sha256 = _sha256(csv_path)

    from config_layer.production_config import get_active_version, get_prod_section
    prod_version = get_active_version()
    fp_cfg = get_prod_section("feature_pipeline")

    if args.end_bar > len(raw):
        print(f"ERROR: --end-bar {args.end_bar} exceeds dataset length {len(raw)}", file=sys.stderr)
        return 1

    pipe = FeaturePipeline(raw, cfg=fp_cfg)
    raw_cols = set(pipe.df.columns)  # columns present BEFORE any stage runs (predates the pipeline)
    logger.info("Running FeaturePipeline stages over %d raw bars (complete dataset; finalize() "
                "deliberately SKIPPED so warmup bars survive) ...", len(raw))

    snap_vol_seed = None
    snap_pre_norm_trend = None
    col_sets = []
    window_snaps = []
    for stage in PIPELINE_STAGES:
        getattr(pipe, stage)()
        if stage == "compute_volume_features":
            snap_vol_seed = pipe.df["volume_spike"].iloc[:args.end_bar].copy()
        elif stage == "compute_trend_features":
            snap_pre_norm_trend = pipe.df["trend_strength"].iloc[:args.end_bar].copy()
        col_sets.append(set(pipe.df.columns))
        window_snaps.append(pipe.df.iloc[:args.end_bar].copy())

    df = pipe.df  # full 47,275-row (or whatever the CSV has), pre-finalize, NaN-intact frame
    stage_provenance = _build_stage_provenance(raw_cols, col_sets, window_snaps)
    del window_snaps  # no longer needed once provenance is derived

    ont = load_ontology()
    ontology_index = _build_ontology_index(ont)
    lineage = _build_lineage_index(ont)
    for name in CANONICAL_FEATURES:
        _normalization_method(name, fp_cfg)  # coverage assertion by call (raises if unclassified)

    first_valid = {name: df[name].first_valid_index() for name in CANONICAL_FEATURES}
    col_first_valid = {col: df[col].first_valid_index() for col in df.columns}
    numeric_cols = [n for n in CANONICAL_FEATURES if n not in RAW_OHLCV_NOTES]
    rank_df = df[numeric_cols].rank(pct=True)

    out_dir = Path(args.output_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = f"_{args.run_tag}" if args.run_tag else ""
    stem = f"xauusd_m15_bars_{args.start_bar:04d}_{args.end_bar:04d}{tag}"
    md_path = out_dir / f"{stem}.md"
    jsonl_path = out_dir / f"{stem}.jsonl"

    md_parts = [_render_header(args, csv_path, csv_sha256, prod_version, first_valid, len(df),
                               stage_provenance)]
    jsonl_lines = []

    for bar_number in range(args.start_bar, args.end_bar + 1):
        row_idx = bar_number - 1
        row = df.iloc[row_idx]
        rank_row = rank_df.iloc[row_idx]
        record = _build_bar_record(
            bar_number, row, ontology_index, rank_row, fp_cfg, ont, first_valid,
            snap_vol_seed, snap_pre_norm_trend, csv_path, csv_sha256, prod_version,
            lineage, stage_provenance, col_first_valid,
        )
        md_parts.append(_render_bar_markdown(record))
        jsonl_lines.append(json.dumps(record, sort_keys=False))

    md_path.write_text("\n".join(md_parts), encoding="utf-8")
    jsonl_path.write_text("\n".join(jsonl_lines) + "\n", encoding="utf-8")

    print(f"Wrote {md_path}")
    print(f"Wrote {jsonl_path}")
    print(f"Rendered bars {args.start_bar}-{args.end_bar} ({args.end_bar - args.start_bar + 1} total).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
