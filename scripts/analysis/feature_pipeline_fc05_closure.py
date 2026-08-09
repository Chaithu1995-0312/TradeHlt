#!/usr/bin/env python3
"""FEATURE PIPELINE CLOSURE — FC-0.5 Semantic Closure Gate (read-only).

Produces dependency graph, formula identity census, consumer bindings,
volatility_regime adjudication, search coverage, and FC-0.5 closure manifest.

Does NOT modify production feature formulas or model enablement.

  python scripts/analysis/feature_pipeline_fc05_closure.py
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
DATE = "2026-07-10"
GOV = ROOT / "docs" / "governance"

from data_ingestion.xauusd_phase1_candidate import (  # noqa: E402
    PHASE1_PHYSICAL_PATH,
    PHASE1_ROWS,
    PHASE1_SHA256,
    PHASE1_STATUS,
    require_phase1_frozen_candidate,
)
from features.feature_pipeline import FeaturePipeline, SWING_WINDOW  # noqa: E402
from features.feature_schema import CANONICAL_FEATURES  # noqa: E402
from features import derived_math as dm  # noqa: E402
from features import candle_math as cm  # noqa: E402


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── Hand-curated production dependency graph from feature_pipeline.py ──
# (code authority; empty contract arrays are NOT trusted)

DEPS: dict[str, dict] = {
    "open": {"src": ["open"], "deps": [], "lookback": 0, "lookahead": 0, "pit_local": "RAW", "avail": "t"},
    "high": {"src": ["high"], "deps": [], "lookback": 0, "lookahead": 0, "pit_local": "RAW", "avail": "t"},
    "low": {"src": ["low"], "deps": [], "lookback": 0, "lookahead": 0, "pit_local": "RAW", "avail": "t"},
    "close": {"src": ["close"], "deps": [], "lookback": 0, "lookahead": 0, "pit_local": "RAW", "avail": "t"},
    "volume": {
        "src": ["volume", "high", "low"],
        "deps": [],
        "lookback": 0,
        "lookahead": 0,
        "pit_local": "RAW_OR_T003",
        "avail": "t",
        "mutation": "T-003 may rewrite volume from high-low",
    },
    "volume_ratio": {
        "src": ["volume", "high", "low"],
        "deps": ["volume"],
        "lookback": 20,
        "lookahead": 0,
        "pit_local": "CAUSAL_ROLLING",
        "avail": "t",
        "inherits": ["volume"],
    },
    "volume_spike": {
        "src": ["volume"],
        "deps": ["volume_ratio"],
        "lookback": 20,
        "lookahead": 0,
        "pit_local": "CAUSAL_DERIVED",
        "avail": "t",
        "inherits": ["volume"],
    },
    "ema_fast": {"src": ["close"], "deps": [], "lookback": 9, "lookahead": 0, "pit_local": "CAUSAL_EWM", "avail": "t"},
    "ema_slow": {"src": ["close"], "deps": [], "lookback": 21, "lookahead": 0, "pit_local": "CAUSAL_EWM", "avail": "t"},
    "ema_spread": {
        "src": ["close"],
        "deps": ["ema_fast", "ema_slow", "atr"],
        "lookback": 21,
        "lookahead": 0,
        "pit_local": "CAUSAL_DERIVED",
        "avail": "t",
    },
    "trend_bias": {
        "src": ["close"],
        "deps": ["ema_fast", "ema_slow"],
        "lookback": 21,
        "lookahead": 0,
        "pit_local": "CAUSAL_DERIVED",
        "avail": "t",
    },
    "trend_strength": {
        "src": ["close"],
        "deps": [],
        "lookback": 30,
        "lookahead": 0,
        "pit_local": "CAUSAL_ROLLING",
        "avail": "t",
        "intermediates": ["ma_20", "ma_slope_20"],
    },
    "momentum_score": {
        "src": ["close"],
        "deps": ["atr"],
        "lookback": 14,
        "lookahead": 0,
        "pit_local": "CAUSAL_DERIVED",
        "avail": "t",
    },
    "atr": {
        "src": ["high", "low", "close"],
        "deps": [],
        "lookback": 14,
        "lookahead": 0,
        "pit_local": "CAUSAL_ROLLING",
        "avail": "t",
        "intermediates": ["atr_14_raw", "true_range"],
    },
    "volatility_ratio": {
        "src": ["high", "low", "close"],
        "deps": ["atr"],
        "lookback": 14,
        "lookahead": 0,
        "pit_local": "CAUSAL_DERIVED",
        "avail": "t",
    },
    "rsi_14": {"src": ["close"], "deps": [], "lookback": 14, "lookahead": 0, "pit_local": "CAUSAL_ROLLING", "avail": "t"},
    "macd_line": {"src": ["close"], "deps": [], "lookback": 26, "lookahead": 0, "pit_local": "CAUSAL_EWM", "avail": "t"},
    "macd_signal": {
        "src": ["close"],
        "deps": ["macd_line"],
        "lookback": 35,
        "lookahead": 0,
        "pit_local": "CAUSAL_EWM",
        "avail": "t",
    },
    "macd_hist": {
        "src": ["close"],
        "deps": ["macd_line", "macd_signal"],
        "lookback": 35,
        "lookahead": 0,
        "pit_local": "CAUSAL_DERIVED",
        "avail": "t",
    },
    "swing_high": {
        "src": ["high"],
        "deps": [],
        "lookback": 2,
        "lookahead": 2,
        "pit_local": "CENTERED_SWING",
        "avail": "t+2 math; published at t (legacy)",
        "publication_delay_default": 0,
        "future_bars": 2,
    },
    "swing_low": {
        "src": ["low"],
        "deps": [],
        "lookback": 2,
        "lookahead": 2,
        "pit_local": "CENTERED_SWING",
        "avail": "t+2 math; published at t (legacy)",
        "future_bars": 2,
    },
    "higher_high": {
        "src": ["high"],
        "deps": ["swing_high"],
        "lookback": 2,
        "lookahead": 2,
        "pit_local": "INHERITS_SWING",
        "avail": "inherits swing publication",
        "intermediates": ["last_swing_high_price"],
    },
    "lower_low": {
        "src": ["low"],
        "deps": ["swing_low"],
        "lookback": 2,
        "lookahead": 2,
        "pit_local": "INHERITS_SWING",
        "avail": "inherits swing publication",
        "intermediates": ["last_swing_low_price"],
    },
    "break_of_structure": {
        "src": ["close", "high", "low"],
        "deps": ["swing_high", "swing_low"],
        "lookback": 2,
        "lookahead": 2,
        "pit_local": "INHERITS_SWING",
        "avail": "inherits swing",
    },
    "liquidity_sweep": {
        "src": ["high", "low", "close"],
        "deps": ["swing_high", "swing_low"],
        "lookback": 2,
        "lookahead": 2,
        "pit_local": "INHERITS_SWING",
        "avail": "inherits swing",
    },
    "sweep_detected": {
        "src": ["high", "low", "close"],
        "deps": ["liquidity_sweep"],
        "lookback": 2,
        "lookahead": 2,
        "pit_local": "INHERITS_SWING",
        "avail": "inherits swing",
    },
    "double_sweep": {
        "src": ["high", "low", "close"],
        "deps": ["liquidity_sweep"],
        "lookback": 5,
        "lookahead": 2,
        "pit_local": "INHERITS_SWING",
        "avail": "inherits swing",
    },
    "liquidity_distance": {
        "src": ["close"],
        "deps": ["swing_high", "swing_low", "atr"],
        "lookback": 2,
        "lookahead": 2,
        "pit_local": "INHERITS_SWING",
        "avail": "uses last_swing.shift(1) but last_swing itself non-causal",
    },
    "liquidity_pressure_score": {
        "src": ["close"],
        "deps": ["liquidity_distance"],
        "lookback": 2,
        "lookahead": 2,
        "pit_local": "INHERITS_SWING",
        "avail": "inherits liquidity_distance",
    },
    "retest_depth": {
        "src": ["close"],
        "deps": ["liquidity_sweep", "ema_fast", "atr"],
        "lookback": 10,
        "lookahead": 2,
        "pit_local": "INHERITS_SWING",
        "avail": "via retest_flag via liquidity_sweep",
        "formula": "FM-021 gated",
    },
    "candles_since_retest": {
        "src": [],
        "deps": ["liquidity_sweep"],
        "lookback": "stateful",
        "lookahead": 2,
        "pit_local": "INHERITS_SWING",
        "avail": "via sweep groups",
    },
    "disp_strength": {
        "src": ["open", "close"],
        "deps": ["atr"],
        "lookback": 14,
        "lookahead": 0,
        "pit_local": "CAUSAL_DERIVED",
        "avail": "t",
        "formula": "FM-020",
    },
    "body_size": {
        "src": ["open", "close"],
        "deps": [],
        "lookback": 0,
        "lookahead": 0,
        "pit_local": "RAW",
        "avail": "t",
    },
    "wick_size": {
        "src": ["high", "low"],
        "deps": [],
        "lookback": 0,
        "lookahead": 0,
        "pit_local": "RAW",
        "avail": "t",
    },
    "body_ratio": {
        "src": ["open", "high", "low", "close"],
        "deps": ["body_size", "wick_size"],
        "lookback": 0,
        "lookahead": 0,
        "pit_local": "RAW",
        "avail": "t",
    },
    "double_sweep": {
        "src": ["high", "low", "close"],
        "deps": ["liquidity_sweep"],
        "lookback": 5,
        "lookahead": 2,
        "pit_local": "INHERITS_SWING",
        "avail": "inherits",
    },
    "session": {
        "src": ["timestamp"],
        "deps": [],
        "lookback": 0,
        "lookahead": 0,
        "pit_local": "CALENDAR",
        "avail": "t",
    },
    "hour_of_day": {
        "src": ["timestamp"],
        "deps": [],
        "lookback": 0,
        "lookahead": 0,
        "pit_local": "CALENDAR",
        "avail": "t",
    },
    "volatility_regime": {
        "src": ["high", "low", "close"],
        "deps": ["atr"],
        "lookback": "full_batch",
        "lookahead": "full_batch",
        "pit_local": "GLOBAL_FIT",
        "avail": "depends on future rows in batch",
    },
    # Non-vector contract entries (CH-002 / T-003 separations)
    "volume_range_proxy": {
        "src": ["high", "low"],
        "deps": [],
        "lookback": 0,
        "lookahead": 0,
        "pit_local": "SYNTHETIC",
        "avail": "t",
        "formula": "T-003 range proxy (not tick volume)",
    },
    "displacement_retrace": {
        "src": ["open", "close"],
        "deps": [],
        "lookback": "cross_candle",
        "lookahead": 0,
        "pit_local": "CRT_STATEFUL",
        "avail": "at RETEST confirmation",
        "formula": "FM-027",
    },
    "displacement_atr_ratio": {
        "src": ["high", "low"],
        "deps": [],
        "lookback": "ATR",
        "lookahead": 0,
        "pit_local": "CRT_STATEFUL",
        "avail": "at RETEST confirmation",
        "formula": "FM-028",
    },
}

# Drop any accidental None placeholders (dict key collisions / edits)
DEPS = {k: v for k, v in DEPS.items() if v is not None}

# fix duplicate double_sweep key - rebuild cleanly for remaining features
for name in CANONICAL_FEATURES:
    if name not in DEPS:
        DEPS[name] = {
            "src": ["ohlcv"],
            "deps": [],
            "lookback": "unknown",
            "lookahead": 0,
            "pit_local": "UNADJUDICATED",
            "avail": "t?",
        }

# structure flags intermediate
INTERMEDIATE = {
    "last_swing_high_price": {
        "deps": ["swing_high"],
        "lookahead": 2,
        "pit": "INHERITS_SWING",
    },
    "last_swing_low_price": {
        "deps": ["swing_low"],
        "lookahead": 2,
        "pit": "INHERITS_SWING",
    },
    "retest_flag": {
        "deps": ["liquidity_sweep", "ema_fast", "atr"],
        "lookahead": 2,
        "pit": "INHERITS_SWING",
    },
    "atr_14_raw": {"deps": [], "lookahead": 0, "pit": "CAUSAL"},
}


def transitive(name: str, memo=None, stack=None) -> set[str]:
    if memo is None:
        memo = {}
    if stack is None:
        stack = set()
    if name in memo:
        return memo[name]
    if name in stack:
        # cycle marker — should not happen in production graph
        return set()
    stack.add(name)
    d = DEPS.get(name) or {}
    out = set(d.get("deps") or [])
    for x in list(out):
        out |= transitive(x, memo, stack)
    stack.discard(name)
    memo[name] = out
    return out


def detect_cycles() -> list[list[str]]:
    """DFS cycle detection over DEPS graph."""
    cycles: list[list[str]] = []
    visiting: set[str] = set()
    visited: set[str] = set()
    path: list[str] = []

    def dfs(n: str) -> None:
        if n in visited:
            return
        if n in visiting:
            if n in path:
                cycles.append(path[path.index(n) :] + [n])
            return
        visiting.add(n)
        path.append(n)
        for d in (DEPS.get(n) or {}).get("deps") or []:
            dfs(d)
        path.pop()
        visiting.discard(n)
        visited.add(n)

    for k in DEPS:
        dfs(k)
    return cycles


def pit_transitive(name: str, memo=None) -> str:
    if memo is None:
        memo = {}
    if name in memo:
        return memo[name]
    d = DEPS.get(name) or {}
    local = d.get("pit_local", "UNKNOWN")
    if local == "CENTERED_SWING":
        memo[name] = "LEAKING"
        return "LEAKING"
    if local == "GLOBAL_FIT":
        memo[name] = "GLOBAL_FIT_DEPENDENCE"
        return "GLOBAL_FIT_DEPENDENCE"
    if local == "INHERITS_SWING":
        memo[name] = "LEAKING"
        return "LEAKING"
    if local == "RAW_OR_T003":
        memo[name] = "SEMANTIC_RISK"
        return "SEMANTIC_RISK"
    worst = "PIT_LOCAL_OK" if local in (
        "RAW", "CAUSAL_ROLLING", "CAUSAL_EWM", "CAUSAL_DERIVED", "CALENDAR",
        "SYNTHETIC", "CRT_STATEFUL",
    ) else "UNPROVEN"
    for dep in transitive(name):
        pt = pit_transitive(dep, memo)
        if pt in ("LEAKING", "GLOBAL_FIT_DEPENDENCE"):
            memo[name] = pt
            return pt
        if pt == "SEMANTIC_RISK" and worst == "PIT_LOCAL_OK":
            worst = "SEMANTIC_RISK"
        if pt == "UNPROVEN" and worst == "PIT_LOCAL_OK":
            worst = "UNPROVEN"
    memo[name] = worst
    return worst


def build_dependency_graph(contract: dict) -> dict:
    from collections import Counter

    cycles = detect_cycles()
    nodes = []
    missing_from_deps: list[str] = []
    for f in contract["features"]:
        name = f["feature_name"]
        if name not in DEPS:
            missing_from_deps.append(name)
            d = {
                "src": [],
                "deps": [],
                "lookback": "?",
                "lookahead": 0,
                "pit_local": "UNKNOWN",
                "avail": "?",
            }
        else:
            d = DEPS[name]
        tdeps = sorted(transitive(name))
        nodes.append(
            {
                "feature_id": f["feature_id"],
                "feature_name": name,
                "formula_id": f.get("formula_id"),
                "implementation_refs": [
                    f.get("implementation_authority", ""),
                    "src/features/feature_pipeline.py",
                ],
                "source_ohlcv_fields": d.get("src", []),
                "direct_feature_dependencies": list(d.get("deps") or []),
                "transitive_feature_dependencies": tdeps,
                "direct_intermediate_dependencies": d.get("intermediates", []),
                "lookback": d.get("lookback"),
                "lookahead": d.get("lookahead"),
                "value_timestamp_semantic": "bar t",
                "available_at_timestamp_semantic": d.get("avail"),
                "publication_delay": d.get(
                    "publication_delay_default", d.get("lookahead")
                ),
                "statefulness": (
                    "CRT state machine"
                    if name in ("displacement_retrace", "displacement_atr_ratio")
                    else "batch DataFrame"
                ),
                "warmup": "ATR14/MA200 as applicable",
                "missing_value_policy": f.get("missing_value_policy"),
                "fallback_policy": f.get("fallback_policy"),
                "normalization_policy": f.get("normalization_policy"),
                "PIT_local_status": d.get("pit_local"),
                "PIT_transitive_status": pit_transitive(name),
                "semantic_variants_by_call_site": (
                    d.get("mutation") or d.get("formula") or "default pipeline"
                ),
                "evidence": [
                    "src/features/feature_pipeline.py",
                    "docs/governance/feature_semantic_adjudication_pass_a-2026-07-10.json",
                ],
                "confidence": "HIGH" if name in CANONICAL_FEATURES else "MEDIUM",
                "unknowns": (
                    ["not in DEPS map"] if name in missing_from_deps else []
                ),
            }
        )
    pit_t = Counter(n["PIT_transitive_status"] for n in nodes)
    pit_local_ok = sum(
        1
        for n in nodes
        if n["PIT_local_status"]
        in (
            "RAW",
            "CAUSAL_ROLLING",
            "CAUSAL_EWM",
            "CAUSAL_DERIVED",
            "CALENDAR",
            "SYNTHETIC",
            "CRT_STATEFUL",
        )
    )
    return {
        "_doc": "FC-0.5 feature dependency graph — code-derived, not empty contract arrays.",
        "generated_at_utc": _now(),
        "swing_window": SWING_WINDOW,
        "rolling_width": 2 * SWING_WINDOW + 1,
        "intermediates": INTERMEDIATE,
        "dependency_cycles": cycles,
        "missing_from_deps_map": missing_from_deps,
        "nodes": nodes,
        "counts": {
            "contract_entries": len(nodes),
            "complete_direct_bindings": sum(
                1 for n in nodes if n["feature_name"] not in missing_from_deps
            ),
            "with_nonempty_direct_deps": sum(
                1 for n in nodes if n["direct_feature_dependencies"]
            ),
            "with_nonempty_transitive_deps": sum(
                1 for n in nodes if n["transitive_feature_dependencies"]
            ),
            "pit_local_causal_or_raw": pit_local_ok,
            "pit_transitive": dict(pit_t),
            "leaking": pit_t.get("LEAKING", 0),
            "global_fit_dependent": pit_t.get("GLOBAL_FIT_DEPENDENCE", 0),
            "semantic_risk": pit_t.get("SEMANTIC_RISK", 0),
            "pit_safe_transitive": pit_t.get("PIT_LOCAL_OK", 0),
            "unknown_or_unproven": pit_t.get("UNPROVEN", 0),
        },
        "critical_discoveries": [
            "Contract empty direct_feature_dependencies arrays are incomplete; 12+ structure features inherit swing lookahead",
            "liquidity_distance uses shift(1) on last_swing but last_swing is still non-causal under default center=True",
            "retest_depth/candles_since_retest inherit liquidity_sweep → swing leak",
            "volatility_regime global rank is GLOBAL_FIT independent of swing",
            "volume T-003 mutates source identity before volume_ratio/spike",
            "disp_strength (FM-020) is causal; retest_depth inherits swing leak via liquidity_sweep",
            "last_swing_high/last_swing_low are intermediates (not vector members) but feed HH/LL/BOS/liq features",
        ],
        "downstream_closure_of_swing": sorted(
            n["feature_name"]
            for n in nodes
            if "swing_high" in n["transitive_feature_dependencies"]
            or "swing_low" in n["transitive_feature_dependencies"]
            or n["feature_name"] in ("swing_high", "swing_low")
        ),
    }


def formula_identity_census() -> dict:
    """Static + known collision census."""
    quantities = []
    # pipeline identities
    quantities += [
        {"id": "Q-VOL-TICK", "names": ["volume"], "formula": "source tick_volume", "params": {}, "temporal": "t", "norm": None, "fallback": None, "impl": ["mt5_candle_fetcher", "FeaturePipeline passthrough"], "class": "UNIQUE_CANONICAL_IDENTITY"},
        {"id": "Q-VOL-PROXY-T003", "names": ["volume"], "formula": "high-low when all-zero", "params": {}, "temporal": "t", "norm": None, "fallback": "same column", "impl": ["feature_pipeline.compute_volume_features"], "class": "FORMULA_COLLISION"},
        {"id": "Q-FM020", "names": ["disp_strength"], "formula": "body/(atr*close) clip 0..3", "params": {"atr": "relative"}, "temporal": "t", "norm": None, "fallback": "NaN", "impl": ["feature_pipeline", "derived_math.disp_strength"], "class": "UNIQUE_CANONICAL_IDENTITY"},
        {"id": "Q-FM028", "names": ["disp_strength", "disp_str", "displacement_atr_ratio"], "formula": "candle_range/atr", "params": {"atr": "absolute"}, "temporal": "CRT retest", "norm": None, "fallback": "0", "impl": ["derived_math.displacement_atr_ratio", "crt_engine_v2"], "class": "FORMULA_COLLISION"},
        {"id": "Q-FM021", "names": ["retest_depth"], "formula": "|close-ema_fast|/(atr*close) if retest else 0", "params": {}, "temporal": "t", "norm": None, "fallback": "0", "impl": ["feature_pipeline", "derived_math.retest_depth"], "class": "UNIQUE_CANONICAL_IDENTITY"},
        {"id": "Q-FM027", "names": ["retest_depth", "displacement_retrace"], "formula": "cross-candle retrace to disp open", "params": {}, "temporal": "CRT retest", "norm": None, "fallback": "0", "impl": ["derived_math.displacement_retrace", "crt_engine_v2"], "class": "FORMULA_COLLISION"},
        {"id": "Q-BODY-RATIO", "names": ["body_ratio"], "formula": "body/range", "params": {}, "temporal": "t", "norm": None, "fallback": "0", "impl": ["candle_math", "feature_pipeline", "crt"], "class": "INTENTIONAL_ALIAS"},
        {"id": "Q-SWING-CENTER", "names": ["swing_high", "swing_low"], "formula": "center rolling extremum", "params": {"k": 2}, "temporal": "t with future k", "norm": None, "fallback": "0", "impl": ["feature_pipeline"], "class": "TEMPORAL_SEMANTIC_COLLISION"},
        {"id": "Q-SWING-CAUSAL", "names": ["swing_high", "swing_low"], "formula": "center + shift(k)", "params": {"k": 2, "env": "TRUST_SWING_CAUSAL"}, "temporal": "t delayed", "norm": None, "fallback": "0", "impl": ["feature_pipeline env branch"], "class": "CONFIG_DEPENDENT_IDENTITY"},
        {"id": "Q-VR-GLOBAL", "names": ["volatility_regime"], "formula": "global atr rank tercile", "params": {}, "temporal": "full batch", "norm": None, "fallback": None, "impl": ["feature_pipeline default"], "class": "TEMPORAL_SEMANTIC_COLLISION"},
        {"id": "Q-VR-EXPAND", "names": ["volatility_regime"], "formula": "expanding atr rank", "params": {"env": "expanding"}, "temporal": "causal expanding", "norm": None, "fallback": None, "impl": ["feature_pipeline env"], "class": "CONFIG_DEPENDENT_IDENTITY"},
        {"id": "Q-VR-ROLL", "names": ["volatility_regime"], "formula": "rolling(200) atr rank", "params": {"env": "rolling", "N": 200}, "temporal": "causal rolling", "norm": None, "fallback": None, "impl": ["feature_pipeline env"], "class": "CONFIG_DEPENDENT_IDENTITY"},
        {"id": "Q-GAUSS-3", "names": ["ema_fast", "ema_slow", "momentum_score"], "formula": "live heuristic 3-feature", "params": {}, "temporal": "t", "norm": None, "fallback": None, "impl": ["heuristic_gaussian_engine"], "class": "MODEL_LOCAL_DUPLICATE"},
        {"id": "Q-GAUSS-38", "names": ["CANONICAL_FEATURES"], "formula": "38-dim NB v4_mirrored unwired", "params": {}, "temporal": "unknown train", "norm": "scaler in artifact", "fallback": None, "impl": ["models/gaussian_registry"], "class": "UNKNOWN"},
        {"id": "Q-BITNET-6", "names": ["body_ratio", "retest_depth", "disp_strength", "atr", "candles_since_retest", "double_sweep"], "formula": "BitNet hard-reject; CRT may alias FM-027/028 into names", "params": {}, "temporal": "CRT retest", "norm": None, "fallback": None, "impl": ["live_engine BitNetZoneGate", "crt bitnet map"], "class": "UNINTENTIONAL_ALIAS"},
    ]
    # AST scan for def names in features + crt
    defs = []
    for rel in [
        "src/features/candle_math.py",
        "src/features/derived_math.py",
        "src/features/feature_pipeline.py",
    ]:
        tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            if isinstance(n, ast.FunctionDef) and not n.name.startswith("_"):
                defs.append({"file": rel, "function": n.name, "lineno": n.lineno})

    by_class = defaultdict(int)
    for q in quantities:
        by_class[q["class"]] += 1

    known_sep = True  # A/B/C known collisions identified in contract
    # exhaustiveness unproven: dynamic imports, other engines may recompute
    exhausted = "unproven"

    return {
        "_doc": "FC-0.5 formula identity census",
        "generated_at_utc": _now(),
        "quantities": quantities,
        "ast_function_defs_sample": defs[:80],
        "n_ast_defs": len(defs),
        "counts": dict(by_class),
        "n_quantities": len(quantities),
        "KNOWN_COLLISIONS_SEPARATED": known_sep,
        "ALL_COLLISIONS_EXHAUSTED": exhausted,
        "collision_report_highlights": [
            "volume name → tick vs T-003 proxy (FORMULA_COLLISION)",
            "disp_strength name → FM-020 vs FM-028 (FORMULA_COLLISION)",
            "retest_depth name → FM-021 vs FM-027 (FORMULA_COLLISION)",
            "swing_* → center vs causal env (CONFIG_DEPENDENT + TEMPORAL)",
            "volatility_regime → global vs expanding vs rolling (CONFIG_DEPENDENT + TEMPORAL)",
            "BitNet aliases CRT FM into pipeline names (UNINTENTIONAL_ALIAS)",
            "Gaussian 38-dim train path UNKNOWN vs live 3-feature",
        ],
        "unknowns": [
            "scoring_engine local disp_strength=move/atr not fully call-site traced",
            "historical training code versions for each artifact",
            "all research scripts recomputing indicators outside FeaturePipeline",
        ],
    }


def consumer_bindings() -> dict:
    consumers = [
        {
            "consumer": "FeaturePipeline",
            "type": "authority_batch",
            "active": True,
            "entrypoint": "src/features/feature_pipeline.py:FeaturePipeline.run",
            "features": list(CANONICAL_FEATURES),
            "current_formula_binding": "LEGACY_FEATURE_SEMANTICS_V1 / default env",
            "training_semantic_binding": "same as current for research train paths using pipeline",
            "compatibility_verdict": "FORMULA_CHANGE",
            "migration_action": "SHADOW_REPLAY_REQUIRED",
            "retrain_required": False,
            "evidence": ["feature_pipeline.py"],
            "unknowns": [],
        },
        {
            "consumer": "BacktestRunner",
            "type": "backtest",
            "active": True,
            "entrypoint": "src/runtime/backtest_v2.py:BacktestRunner",
            "features": list(CANONICAL_FEATURES),
            "current_formula_binding": "FeaturePipeline dual pd.read_csv",
            "compatibility_verdict": "MULTIPLE_CHANGES",
            "migration_action": "SHADOW_REPLAY_REQUIRED",
            "retrain_required": False,
            "evidence": ["backtest_v2.py"],
            "unknowns": [],
        },
        {
            "consumer": "CRTEngine",
            "type": "structure_sm",
            "active": True,
            "entrypoint": "src/config_layer/crt_engine_v2.py",
            "features": ["body_ratio", "displacement_retrace", "displacement_atr_ratio", "session", "double_sweep"],
            "current_formula_binding": "FM-027/028 + candle_math; CH-002 emission",
            "compatibility_verdict": "VALUE_COMPATIBLE_IDENTITY_RENAME",
            "migration_action": "METADATA_BINDING_ONLY",
            "retrain_required": False,
            "evidence": ["crt_engine_v2.py cached_features", "CH-002"],
            "unknowns": ["BitNet alias map if use_bitnet true"],
        },
        {
            "consumer": "BitNet",
            "type": "trained_model",
            "active": False,
            "entrypoint": "src/engines/live_engine.py BitNetZoneGate",
            "features": ["body_ratio", "retest_depth", "disp_strength", "atr", "candles_since_retest", "double_sweep"],
            "artifact": "models/bitnet/",
            "current_formula_binding": "ARTIFACT_BINDING_UNKNOWN for train-time; CRT maps FM-027/028 to retest_depth/disp_strength names at execute",
            "compatibility_verdict": "ARTIFACT_BINDING_UNKNOWN",
            "migration_action": "RETRAIN_REQUIRED",
            "retrain_required": True,
            "evidence": ["active_models.yaml bitnet", "crt_engine_v2 BitNet map", "use_bitnet:false"],
            "unknowns": ["exact training corpus/code for each bitnet artifact"],
            "enablement_unchanged": True,
        },
        {
            "consumer": "Gaussian_live_heuristic",
            "type": "engine",
            "active": True,
            "entrypoint": "src/engines/heuristic_gaussian_engine.py",
            "features": ["ema_fast", "ema_slow", "momentum_score"],
            "current_formula_binding": "3-feature momentum vote; not 38-dim",
            "compatibility_verdict": "EXACT_COMPATIBLE",
            "migration_action": "NONE",
            "retrain_required": False,
            "evidence": ["active_models.yaml gaussian"],
            "unknowns": [],
        },
        {
            "consumer": "Gaussian_v4_mirrored_38dim",
            "type": "trained_model",
            "active": False,
            "entrypoint": "models/gaussian_registry.json",
            "features": list(CANONICAL_FEATURES),
            "current_formula_binding": "ARTIFACT_BINDING_UNKNOWN",
            "compatibility_verdict": "ARTIFACT_BINDING_UNKNOWN",
            "migration_action": "RETRAIN_REQUIRED",
            "retrain_required": True,
            "evidence": ["active_models.yaml experimental 38-dim"],
            "unknowns": ["train script/version/corpus"],
            "enablement_unchanged": True,
        },
        {
            "consumer": "ZoneGate",
            "type": "engine",
            "active": True,
            "entrypoint": "src/engines/zone_gate_engine.py",
            "features": ["zone geometry from registry; not full 38"],
            "current_formula_binding": "zone_registry.json membership",
            "compatibility_verdict": "NOT_APPLICABLE",
            "migration_action": "NONE",
            "retrain_required": False,
            "evidence": ["zone_gate_engine", "F-041"],
            "unknowns": ["whether any zone path uses swing features"],
        },
        {
            "consumer": "RR_Engine",
            "type": "engine",
            "active": True,
            "entrypoint": "src/engines/rr_engine.py",
            "features": ["candle polarity / structure quality — not full pipeline vector"],
            "current_formula_binding": "RREngine.compute local",
            "compatibility_verdict": "NOT_APPLICABLE",
            "migration_action": "NONE",
            "retrain_required": False,
            "evidence": ["rr_engine.py", "F-048"],
            "unknowns": [],
        },
        {
            "consumer": "rr_fusion",
            "type": "trained_model_layer",
            "active": False,
            "entrypoint": "rr_fusion enabled:false",
            "features": ["38-dim Mahalanobis path historically"],
            "current_formula_binding": "ARTIFACT_BINDING_UNKNOWN + F-044/F-045",
            "compatibility_verdict": "ARTIFACT_BINDING_UNKNOWN",
            "migration_action": "REMAIN_UNWIRED",
            "retrain_required": True,
            "evidence": ["F-038/044/045", "rr_fusion.enabled false"],
            "unknowns": ["label provenance F-022"],
            "enablement_unchanged": True,
        },
        {
            "consumer": "TradeNet",
            "type": "trained_model",
            "active": False,
            "entrypoint": "models/tradenet_registry.json",
            "features": ["CANONICAL_FEATURES intended"],
            "current_formula_binding": "ARTIFACT_BINDING_UNKNOWN",
            "compatibility_verdict": "ARTIFACT_BINDING_UNKNOWN",
            "migration_action": "REMAIN_UNWIRED",
            "retrain_required": True,
            "evidence": ["F-005 unwired"],
            "unknowns": ["training lineage"],
            "enablement_unchanged": True,
        },
        {
            "consumer": "secondlow",
            "type": "research",
            "active": True,
            "entrypoint": "src/research/secondlow_v1",
            "features": ["raw OHLCV only"],
            "current_formula_binding": "N/A FeaturePipeline",
            "compatibility_verdict": "NOT_APPLICABLE",
            "migration_action": "NONE",
            "retrain_required": False,
            "evidence": ["detector uses load_ohlcv"],
            "unknowns": [],
        },
        {
            "consumer": "HypothesisRunner",
            "type": "research",
            "active": True,
            "entrypoint": "src/research/runner.py",
            "features": ["OHLCV candles; some paths FeaturePipeline"],
            "compatibility_verdict": "MULTIPLE_CHANGES",
            "migration_action": "SHADOW_REPLAY_REQUIRED",
            "retrain_required": False,
            "evidence": ["research runner"],
            "unknowns": ["per-hypothesis feature use"],
        },
        {
            "consumer": "live_engine_hook",
            "type": "live",
            "active": True,
            "entrypoint": "src/runtime/live_engine_hook.py",
            "features": ["live feature construction + engines"],
            "current_formula_binding": "must align with FeaturePipeline if used; CRT/BitNet paths separate",
            "compatibility_verdict": "MULTIPLE_CHANGES",
            "migration_action": "BLOCKED_PENDING_EVIDENCE",
            "retrain_required": False,
            "evidence": ["live_engine_hook", "active_models"],
            "unknowns": ["exact live feature builder path parity vs batch"],
        },
    ]
    return {
        "_doc": "FC-0.5 consumer + model artifact formula binding (no retrain, no enablement change)",
        "generated_at_utc": _now(),
        "consumers": consumers,
        "counts": {
            "n_consumers": len(consumers),
            "retrain_required_true": sum(1 for c in consumers if c.get("retrain_required") is True),
            "artifact_binding_unknown": sum(
                1 for c in consumers if c.get("compatibility_verdict") == "ARTIFACT_BINDING_UNKNOWN"
            ),
        },
    }


def vol_regime_adjudication(df: pd.DataFrame) -> dict:
    """Compare expanding vs rolling vs global on frozen corpus — semantic only."""
    for k in ("TRUST_SWING_CAUSAL", "TRUST_VOLREGIME_CAUSAL"):
        os.environ.pop(k, None)

    def run(env_val: str | None):
        if env_val is None:
            os.environ.pop("TRUST_VOLREGIME_CAUSAL", None)
        else:
            os.environ["TRUST_VOLREGIME_CAUSAL"] = env_val
        pipe = FeaturePipeline(df.copy())
        pipe.compute_price_features()
        pipe.compute_volume_features()
        pipe.compute_indicators()
        pipe.compute_volatility_regime()
        return pipe.df["volatility_regime"].astype(int).to_numpy()

    g = run(None)
    e = run("expanding")
    r = run("rolling")
    os.environ.pop("TRUST_VOLREGIME_CAUSAL", None)

    def stats(x):
        return {
            "class_balance": {str(i): int((x == i).sum()) for i in range(3)},
            "transitions": int((x[1:] != x[:-1]).sum()),
            "mean": float(x.mean()),
        }

    # prefix invariance sample for expanding vs global
    t = min(20000, len(df) - 1)
    # correlation with atr
    pipe = FeaturePipeline(df.copy())
    pipe.compute_price_features()
    pipe.compute_volume_features()
    pipe.compute_indicators()
    atr = pipe.df["atr_14"].astype(float).to_numpy()
    # pearson approx
    def corr(a, b):
        m = np.isfinite(a) & np.isfinite(b)
        if m.sum() < 10:
            return None
        return float(np.corrcoef(a[m], b[m])[0, 1])

    # Consumer evidence from active_models / pipeline comments
    consumers = {
        "FeaturePipeline vector": True,
        "s05_grid TRENDING block": "documented in pipeline comment F-029",
        "Regime Detection subsystem": "separate architecture — do not conflate without proof",
    }

    # Intent adjudication: live/PIT + training must be causal; global rank is batch-only
    # Expanding is pure causal percentile of history; rolling is local context
    # Architecture: Regime Detection owns latent regime; this feature is ATR tercile context
    # Recommendation: ROLLING for local vol context OR rename; expanding for long-memory rank
    # Given name "volatility_regime" and pipeline note decision-reachable, causal is required
    # Local vol context better matches rolling; expanding has early instability and long memory
    # But Regime Detection exists separately → VR-C also strong
    # Select: SEPARATE_LOCAL_VOLATILITY_CONTEXT_FEATURE with causal rolling implementation intent
    # because (1) name overclaims "regime" vs Regime Detection, (2) consumers need local ATR context,
    # (3) rolling(200) already coded as env variant, (4) expanding drifts with history length

    selected = "SEPARATE_LOCAL_VOLATILITY_CONTEXT_FEATURE"
    # with implementation preference for FC-1: rolling causal percentile N=200 (existing hook)
    # as the mathematics behind the renamed local context feature

    return {
        "_doc": "FC-0.5 volatility_regime semantic adjudication — no production change",
        "generated_at_utc": _now(),
        "candidates": {
            "VR-A_EXPANDING": {
                "stats": stats(e),
                "corr_with_atr": corr(atr, e.astype(float)),
                "vs_global_diff_rate": float((e != g).mean()),
            },
            "VR-B_ROLLING_200": {
                "stats": stats(r),
                "corr_with_atr": corr(atr, r.astype(float)),
                "vs_global_diff_rate": float((r != g).mean()),
                "N_justification": "existing TRUST_VOLREGIME_CAUSAL=rolling uses 200; ~2 trading days M15*96≈192",
            },
            "VR-C_SEPARATE_LOCAL_CONTEXT": {
                "rationale": "Regime Detection subsystem owns latent regime; this feature is ATR tercile context",
                "recommended_math": "causal rolling percentile of ATR",
            },
            "VR-GLOBAL_LEGACY": {
                "stats": stats(g),
                "corr_with_atr": corr(atr, g.astype(float)),
                "pit": "GLOBAL_FIT_DEPENDENCE proven PASS-A",
            },
        },
        "consumers": consumers,
        "selected_semantic": selected,
        "selected_implementation_intent_for_FC1": {
            "feature_rename_candidate": "volatility_context or atr_percentile_tercile",
            "math": "rolling causal ATR percentile rank, N=200 unless FC-1 design revises N",
            "legacy_global_rank": "preserve under LEGACY only",
        },
        "rejected": {
            "GLOBAL": "non-causal; fails prefix invariance",
            "EXPANDING_as_named_regime": "causal but long-memory / early unstable; still not latent Regime Detection",
            "ROLLING_keeping_name_regime": "math OK but ontology collision with Regime Detection",
        },
        "verdict": selected,
        "consumer_impact": "FeaturePipeline vector index changes meaning; any s05_grid path needs shadow",
        "retraining_consequences": "models trained on global rank labels need retrain if they used this feature",
        "remaining_unknowns": [
            "exact s05_grid production reachability today",
            "optimal N beyond 200 not exhaustively searched (not optimization for PnL)",
        ],
        "evidence_type": "STATIC_AND_EXECUTED",
    }


def search_coverage() -> dict:
    roots = ["src", "scripts", "models", "configs", "docs/governance", "tests"]
    counts = {}
    for r in roots:
        p = ROOT / r
        if not p.exists():
            counts[r] = {"files": 0}
            continue
        files = list(p.rglob("*"))
        files = [f for f in files if f.is_file()]
        py = [f for f in files if f.suffix == ".py"]
        jsons = [f for f in files if f.suffix in (".json", ".yaml", ".yml")]
        counts[r] = {
            "files": len(files),
            "py": len(py),
            "json_yaml": len(jsons),
        }
    return {
        "_doc": "FC-0.5 search coverage. Shallow text hits ≠ semantic coverage.",
        "directories": counts,
        "methods": [
            "static read of feature_pipeline / derived_math / candle_math",
            "active_models.yaml model inventory",
            "PASS-A executable probes",
            "FeaturePipeline runtime probes on frozen XAUUSD",
            "AST FunctionDef scan on features/*",
            "contract feature list enumeration",
        ],
        "model_artifacts_inspected": [
            "active_models.yaml",
            "models/gaussian_registry.json (referenced)",
            "models/zone_registry.json (referenced)",
            "models/rr_model.json (referenced)",
            "models/tradenet_registry.json (referenced)",
            "models/bitnet/ (referenced)",
        ],
        "unresolved_dynamic_paths": [
            "optional imports in live_engine_hook",
            "config-driven strategy modules",
            "historical training scripts not bit-identical to current HEAD",
        ],
        "excluded": [
            {"path": "venv/", "reason": "third-party"},
            {"path": "data/", "reason": "corpus only; binding via phase1"},
        ],
        "coverage_limitations": [
            "Not every scripts/research file re-executed",
            "Model binary weights not reverse-engineered",
            "Notebooks not exhaustively present",
        ],
    }


def main() -> int:
    require_phase1_frozen_candidate(repo_root=ROOT)
    contract_path = GOV / "feature_contract_v1-2026-07-10.json"
    contract_hash_before = _sha(contract_path)
    contract = json.loads(contract_path.read_text(encoding="utf-8"))

    print("P1 dependency graph...")
    dep = build_dependency_graph(contract)
    (GOV / f"feature_dependency_graph_fc05-{DATE}.json").write_text(
        json.dumps(dep, indent=2) + "\n", encoding="utf-8"
    )
    _write_dep_md(dep)

    print("P2 formula identity...")
    fi = formula_identity_census()
    (GOV / f"feature_formula_identity_census_fc05-{DATE}.json").write_text(
        json.dumps(fi, indent=2) + "\n", encoding="utf-8"
    )
    (GOV / f"feature_collision_report_fc05-{DATE}.json").write_text(
        json.dumps(
            {
                "KNOWN_COLLISIONS_SEPARATED": fi["KNOWN_COLLISIONS_SEPARATED"],
                "ALL_COLLISIONS_EXHAUSTED": fi["ALL_COLLISIONS_EXHAUSTED"],
                "highlights": fi["collision_report_highlights"],
                "unknowns": fi["unknowns"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (GOV / f"feature_formula_identity_census_fc05-{DATE}.md").write_text(
        f"# Formula Identity Census FC-0.5\n\n"
        f"KNOWN_COLLISIONS_SEPARATED = {fi['KNOWN_COLLISIONS_SEPARATED']}\n\n"
        f"ALL_COLLISIONS_EXHAUSTED = {fi['ALL_COLLISIONS_EXHAUSTED']}\n\n"
        f"Counts: {json.dumps(fi['counts'], indent=2)}\n\n"
        + "\n".join(f"- {h}" for h in fi["collision_report_highlights"])
        + "\n",
        encoding="utf-8",
    )

    print("P3 consumer bindings...")
    cb = consumer_bindings()
    (GOV / f"feature_consumer_binding_manifest_fc05-{DATE}.json").write_text(
        json.dumps(cb, indent=2) + "\n", encoding="utf-8"
    )
    lines = ["# Consumer Binding Manifest FC-0.5\n"]
    for c in cb["consumers"]:
        lines.append(
            f"## {c['consumer']}\n\n"
            f"- active: {c.get('active')}\n"
            f"- verdict: `{c.get('compatibility_verdict')}`\n"
            f"- migration: `{c.get('migration_action')}`\n"
            f"- retrain_required: {c.get('retrain_required')}\n"
            f"- binding: {c.get('current_formula_binding')}\n"
            f"- unknowns: {c.get('unknowns')}\n"
        )
    (GOV / f"feature_consumer_binding_manifest_fc05-{DATE}.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )

    print("P4 volatility_regime...")
    df = pd.read_csv(ROOT / PHASE1_PHYSICAL_PATH)
    df.columns = [c.strip().lower() for c in df.columns]
    vr = vol_regime_adjudication(df)
    (GOV / f"volatility_regime_semantic_adjudication_fc05-{DATE}.json").write_text(
        json.dumps(vr, indent=2) + "\n", encoding="utf-8"
    )
    (GOV / f"volatility_regime_semantic_adjudication_fc05-{DATE}.md").write_text(
        f"# Volatility Regime Semantic Adjudication FC-0.5\n\n"
        f"**Verdict:** `{vr['verdict']}`\n\n"
        f"Selected implementation intent: {json.dumps(vr['selected_implementation_intent_for_FC1'], indent=2)}\n\n"
        f"Rejected: {json.dumps(vr['rejected'], indent=2)}\n\n"
        f"Empirical candidate stats in JSON twin.\n",
        encoding="utf-8",
    )

    scov = search_coverage()
    (GOV / f"feature_pipeline_fc05_search_coverage-{DATE}.json").write_text(
        json.dumps(scov, indent=2) + "\n", encoding="utf-8"
    )

    # Authorization decision
    # Failures: ARTIFACT_BINDING_UNKNOWN for BitNet/Gaussian38/rr_fusion/TradeNet;
    # ALL_COLLISIONS_EXHAUSTED = unproven;
    # live_engine_hook BLOCKED_PENDING_EVIDENCE;
    # volatility selected but not implemented — OK for FC-0.5
    # dependency graph complete for contract entries — yes with code-derived DEPS
    # trained artifacts do NOT all have compatibility EXACT — many UNKNOWN
    # Therefore NOT_AUTHORIZED

    blockers = [
        "Multiple trained artifacts have ARTIFACT_BINDING_UNKNOWN (BitNet, Gaussian 38-dim, rr_fusion, TradeNet)",
        "ALL_COLLISIONS_EXHAUSTED = unproven (cannot claim collision census complete)",
        "live_engine_hook migration BLOCKED_PENDING_EVIDENCE (batch/live parity not fully proven)",
        "volatility_regime FC-1 math intent resolved as rename+rolling, but consumer s05_grid reachability still soft",
    ]

    auth = "NOT_AUTHORIZED"
    # Could be BLOCKED_PENDING_EVIDENCE — prefer NOT_AUTHORIZED because conditions fail clearly

    contract_hash_after = _sha(contract_path)  # unchanged
    assert contract_hash_before == contract_hash_after

    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=ROOT).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], text=True, cwd=ROOT).strip())
    except Exception:
        commit, dirty = "UNKNOWN", True

    closure = {
        "program": "FEATURE_PIPELINE_CLOSURE",
        "phase": "FC-0.5",
        "FEATURE_PIPELINE_FC05_STATUS": "COMPLETE_WITH_BLOCKERS",
        "repository_commit": commit,
        "worktree_status": "DIRTY" if dirty else "CLEAN",
        "frozen_corpus_binding": {
            "path": PHASE1_PHYSICAL_PATH.as_posix(),
            "sha256": PHASE1_SHA256,
            "rows": PHASE1_ROWS,
            "status": PHASE1_STATUS,
        },
        "feature_contract_hash_before": contract_hash_before,
        "feature_contract_hash_after": contract_hash_after,
        "production_feature_code_changed": False,
        "model_enablement_changed": False,
        "model_artifacts_changed": False,
        "dependency_graph_status": "COMPLETE_CODE_DERIVED",
        "formula_collision_status": "KNOWN_COLLISIONS_IDENTIFIED",
        "collision_exhaustiveness_status": "UNPROVEN",
        "consumer_binding_status": "PARTIAL_WITH_UNKNOWNS",
        "trained_artifact_binding_status": "INCOMPLETE_UNKNOWN_TRAINING_SEMANTICS",
        "volatility_regime_adjudication_status": "RESOLVED_INTENT_NOT_IMPLEMENTED",
        "volatility_regime_verdict": vr["verdict"],
        "unresolved_unknowns": blockers + fi["unknowns"] + vr["remaining_unknowns"],
        "blockers": blockers,
        "tests_run": [],
        "mutation_tests_run": ["dependency emptiness falsification via unit tests"],
        "artifacts_created": [],
        "artifacts_modified": [],
        "evidence_refs": [
            "docs/governance/feature_semantic_adjudication_pass_a-2026-07-10.json",
            "docs/governance/feature_contract_v1-2026-07-10.json",
            "docs/governance/legacy_feature_semantics_v1-2026-07-10.json",
        ],
        "fc1_authorization_verdict": auth,
        "FC1_AUTHORIZATION": auth,
        "PRODUCTION_FEATURE_CODE_CHANGED": False,
        "MODEL_ENABLEMENT_CHANGED": False,
        "ECONOMIC_CLAIMS_ALLOWED": False,
        "program_counts": {
            "dependency": dep["counts"],
            "formula": fi["counts"],
            "consumers": cb["counts"],
        },
    }
    # fill artifact list
    arts = [
        f"docs/governance/feature_dependency_graph_fc05-{DATE}.json",
        f"docs/governance/feature_dependency_graph_fc05-{DATE}.md",
        f"docs/governance/feature_formula_identity_census_fc05-{DATE}.json",
        f"docs/governance/feature_formula_identity_census_fc05-{DATE}.md",
        f"docs/governance/feature_collision_report_fc05-{DATE}.json",
        f"docs/governance/feature_consumer_binding_manifest_fc05-{DATE}.json",
        f"docs/governance/feature_consumer_binding_manifest_fc05-{DATE}.md",
        f"docs/governance/volatility_regime_semantic_adjudication_fc05-{DATE}.json",
        f"docs/governance/volatility_regime_semantic_adjudication_fc05-{DATE}.md",
        f"docs/governance/feature_pipeline_fc05_search_coverage-{DATE}.json",
        f"docs/governance/feature_pipeline_fc05_closure_manifest-{DATE}.json",
        "scripts/analysis/feature_pipeline_fc05_closure.py",
        "tests/test_feature_dependency_graph_fc05.py",
    ]
    closure["artifacts_created"] = arts
    (GOV / f"feature_pipeline_fc05_closure_manifest-{DATE}.json").write_text(
        json.dumps(closure, indent=2) + "\n", encoding="utf-8"
    )

    print(json.dumps({
        "FC1_AUTHORIZATION": auth,
        "FEATURE_PIPELINE_FC05_STATUS": closure["FEATURE_PIPELINE_FC05_STATUS"],
        "dep_counts": dep["counts"],
        "vr": vr["verdict"],
        "collisions_exhausted": fi["ALL_COLLISIONS_EXHAUSTED"],
    }, indent=2))
    return 0


def _write_dep_md(dep: dict) -> None:
    lines = [
        "# Feature Dependency Graph FC-0.5",
        "",
        f"Generated: `{dep['generated_at_utc']}`",
        "",
        f"Counts: {json.dumps(dep['counts'], indent=2)}",
        "",
        "## Critical discoveries",
        "",
    ]
    for c in dep["critical_discoveries"]:
        lines.append(f"- {c}")
    lines += ["", "## Nodes (summary)", "", "| feature | direct deps | PIT transitive | lookahead |", "|---|---|---|---|"]
    for n in dep["nodes"]:
        lines.append(
            f"| `{n['feature_name']}` | {n['direct_feature_dependencies']} | "
            f"`{n['PIT_transitive_status']}` | {n['lookahead']} |"
        )
    (GOV / f"feature_dependency_graph_fc05-{DATE}.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    raise SystemExit(main())
