#!/usr/bin/env python3
"""Canonical-feature lineage census: OHLCV → formula → implementation → PIT → consumers.

Filename/artifact-pointer name (feature_38_lineage_census*) is a historical identifier kept
for path stability (referenced by feature_surface_closure_audit.py and the LATEST pointer
convention); it does NOT assert the vector is 38-dim. The census covers every name in
CANONICAL_FEATURES, whatever CANONICAL_FEATURE_DIM currently is (48 as of schema v5.0,
2026-08-15) -- see main()'s `len(CANONICAL_FEATURES) == CANONICAL_FEATURE_DIM` assertion.
The LINEAGE table below must cover every canonical name or main() raises `LINEAGE table
mismatch` and writes nothing -- that fail-closed is why the shipped artifact sat at 39 rows
from the v5.0 SMC bump (2026-08-15) until the 9 SMC entries were added (2026-09-05).

Read-only. Uses frozen XAUUSD Phase-1 candidate only for optional smoke vectors.
Does not change formulas or configs.

  python scripts/analysis/feature_38_lineage_census.py
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from features.feature_schema import (  # noqa: E402
    CANONICAL_FEATURE_DIM,
    CANONICAL_FEATURES,
    FEATURE_ORDER_HASH,
    SCHEMA_HASH,
    SCHEMA_VERSION,
)
# PROVENANCE RULE (resolve_swing_window docstring): a governance artifact must never re-declare
# the swing_window literal, or it can assert a value the pipeline did not actually use. The PEP
# 562 attribute below resolves feature_pipeline.swing_window from the active config.
from features.feature_pipeline import SWING_WINDOW  # noqa: E402

# Dated output (authority for closure audits). DATED FILES ARE IMMUTABLE — a file
# named -YYYY-MM-DD must contain facts generated ON that date (2026-07-11 hardening:
# the old behavior rewrote the 2026-07-10 file on later runs, destroying the semantic
# meaning of the date). Consumers resolve the current artifact through the stable
# pointer feature_38_lineage_census.LATEST.json ({path, generated_at, schema_hash,
# sha256}) or by embedded generated_at_utc — NEVER by filename date.
_DATE_STAMP = datetime.utcnow().strftime("%Y-%m-%d")
OUT_JSON = ROOT / "docs" / "governance" / f"feature_38_lineage_census-{_DATE_STAMP}.json"
OUT_MD = ROOT / "docs" / "governance" / f"feature_38_lineage_census-{_DATE_STAMP}.md"
OUT_LATEST_PTR = ROOT / "docs" / "governance" / "feature_38_lineage_census.LATEST.json"

# Hand-curated lineage table (source-verified against feature_pipeline.py +
# candle_math + derived_math + ontology IDs). PIT: lookback / shift / center.
# Consumers are primary production surfaces, not exhaustive.
LINEAGE: dict[str, dict] = {
    "open": {
        "source_ohlcv": ["open"],
        "formula": "identity: open",
        "formula_id": "RAW-OHLCV",
        "impl": "feature_pipeline / CSV column passthrough",
        "impl_refs": ["src/features/feature_pipeline.py"],
        "pit": "same-bar raw; no lookback",
        "pit_class": "RAW_CONTEMPORANEOUS",
        "consumers": ["FeaturePipeline vector", "CandleLoader.Candle", "CRTEngine"],
    },
    "high": {
        "source_ohlcv": ["high"],
        "formula": "identity: high",
        "formula_id": "RAW-OHLCV",
        "impl": "passthrough",
        "impl_refs": ["src/features/feature_pipeline.py"],
        "pit": "same-bar raw",
        "pit_class": "RAW_CONTEMPORANEOUS",
        "consumers": ["FeaturePipeline", "Candle", "CRT", "candle_math"],
    },
    "low": {
        "source_ohlcv": ["low"],
        "formula": "identity: low",
        "formula_id": "RAW-OHLCV",
        "impl": "passthrough",
        "impl_refs": ["src/features/feature_pipeline.py"],
        "pit": "same-bar raw",
        "pit_class": "RAW_CONTEMPORANEOUS",
        "consumers": ["FeaturePipeline", "Candle", "CRT", "candle_math"],
    },
    "close": {
        "source_ohlcv": ["close"],
        "formula": "identity: close",
        "formula_id": "RAW-OHLCV",
        "impl": "passthrough",
        "impl_refs": ["src/features/feature_pipeline.py"],
        "pit": "same-bar raw",
        "pit_class": "RAW_CONTEMPORANEOUS",
        "consumers": ["FeaturePipeline", "Candle", "indicators", "CRT"],
    },
    "volume": {
        "source_ohlcv": ["volume"],
        "formula": "identity or T-003 proxy high-low if all-zero",
        "formula_id": "RAW-OHLCV / T-003",
        "impl": "feature_pipeline.compute_volume_features",
        "impl_refs": ["src/features/feature_pipeline.py:203-233"],
        "pit": "same-bar; proxy mutates volume column in-place when dead",
        "pit_class": "RAW_OR_SYNTHETIC_SAME_BAR",
        "consumers": ["FeaturePipeline", "volume_ratio", "volume_spike"],
        "mutation_risk": "T-003 silent rename under same key",
    },
    "volume_ratio": {
        "source_ohlcv": ["volume", "high", "low"],
        "formula": "volume / rolling_mean(volume, 20)",
        "formula_id": "DERIVED-VOL",
        "impl": "feature_pipeline.compute_volume_features",
        "impl_refs": ["src/features/feature_pipeline.py:219-228"],
        "pit": "rolling 20 past+current (trailing window)",
        "pit_class": "CAUSAL_ROLLING",
        "consumers": ["FeaturePipeline vector", "volume_spike"],
    },
    "double_sweep": {
        "source_ohlcv": ["high", "low", "close"],
        "formula": "both sweep directions in short window on causal liquidity_sweep",
        "formula_id": "STRUCT-SWEEP",
        "impl": "feature_pipeline structure/sweep block (FC1-A)",
        "impl_refs": ["src/features/feature_pipeline.py"],
        "pit": "production structure graph uses causal last_swing refs (available_at=t+k); rolling window of past sweeps only",
        "pit_class": "STRUCTURE_WITH_CAUSAL_SWING",
        "consumers": ["FeaturePipeline vector", "CRT-related features", "FeatureStore live"],
        "note": "FC1-A 2026-07-11: was STRUCTURE_WITH_CENTERED_SWING",
    },
    "ema_fast": {
        "source_ohlcv": ["close"],
        "formula": "EMA(close, span=fast) — pipeline uses ma aliases / ewm",
        "formula_id": "FM-EMA-FAST",
        "impl": "feature_pipeline.compute_indicators ewm/ma",
        "impl_refs": ["src/features/feature_pipeline.py:238-284"],
        "pit": "ewm causal (adjust=False)",
        "pit_class": "CAUSAL_EWM",
        "consumers": ["FeaturePipeline", "ema_spread", "CRT cached"],
    },
    "ema_slow": {
        "source_ohlcv": ["close"],
        "formula": "EMA(close, span=slow) / ma_50 path",
        "formula_id": "FM-EMA-SLOW",
        "impl": "feature_pipeline.compute_indicators",
        "impl_refs": ["src/features/feature_pipeline.py:238-284"],
        "pit": "causal rolling/ewm",
        "pit_class": "CAUSAL_EWM",
        "consumers": ["FeaturePipeline", "ema_spread"],
    },
    "ema_spread": {
        "source_ohlcv": ["close"],
        "formula": "derived_math.ema_spread / (ema_fast - ema_slow) normalized",
        "formula_id": "FM-022-ish / pipeline trend",
        "impl": "feature_pipeline + derived_math.ema_spread",
        "impl_refs": [
            "src/features/feature_pipeline.py",
            "src/features/derived_math.py",
            "configs/formulas/market_ontology.yaml",
        ],
        "pit": "depends on EMA history; ATR-gated NaN during warmup",
        "pit_class": "CAUSAL_DERIVED",
        "consumers": ["FeaturePipeline vector", "CRT cached_features"],
    },
    "trend_bias": {
        "source_ohlcv": ["close"],
        "formula": "sign of MA relationship / rsi_state-like encoding to {-1,0,1}",
        "formula_id": "DERIVED-TREND",
        "impl": "feature_pipeline.compute_trend_features / finalize encoding",
        "impl_refs": ["src/features/feature_pipeline.py:290-298"],
        "pit": "causal MAs",
        "pit_class": "CAUSAL_DERIVED",
        "consumers": ["FeaturePipeline vector", "Gaussian/BitNet inputs"],
    },
    "trend_strength": {
        "source_ohlcv": ["close"],
        "formula": "rolling mean of ma_20.diff()",
        "formula_id": "DERIVED-TREND",
        "impl": "feature_pipeline.compute_trend_features",
        "impl_refs": ["src/features/feature_pipeline.py:295-296"],
        "pit": "causal rolling 10 on ma_slope",
        "pit_class": "CAUSAL_ROLLING",
        "consumers": ["FeaturePipeline vector"],
    },
    "momentum_score": {
        "source_ohlcv": ["close"],
        "formula": "derived_math.momentum_score / pipeline momentum block",
        "formula_id": "FM-023",
        "impl": "feature_pipeline + derived_math",
        "impl_refs": ["src/features/derived_math.py", "src/features/feature_pipeline.py"],
        "pit": "causal lookback; ATR-gated warmup NaN possible",
        "pit_class": "CAUSAL_DERIVED",
        "consumers": ["FeaturePipeline vector", "CRT telemetry"],
    },
    "atr": {
        "source_ohlcv": ["high", "low", "close"],
        "formula": "Wilder/rolling mean TrueRange(14)",
        "formula_id": "FM-ATR",
        "impl": "feature_pipeline.compute_indicators atr_14",
        "impl_refs": ["src/features/feature_pipeline.py:262-268"],
        "pit": "TR uses close.shift(1); rolling 14 causal",
        "pit_class": "CAUSAL_ROLLING",
        "consumers": ["FeaturePipeline", "disp_strength", "retest_depth", "liquidity_*"],
    },
    "volatility_ratio": {
        "source_ohlcv": ["high", "low", "close"],
        "formula": "atr / close or pipeline volatility ratio",
        "formula_id": "FM-024",
        "impl": "feature_pipeline + derived_math.volatility_ratio",
        "impl_refs": ["src/features/derived_math.py", "src/features/feature_pipeline.py"],
        "pit": "causal atr-based",
        "pit_class": "CAUSAL_DERIVED",
        "consumers": ["FeaturePipeline vector"],
    },
    "rsi_14": {
        "source_ohlcv": ["close"],
        "formula": "Wilder RSI(14) = 100 - 100/(1+RS)",
        "formula_id": "RSI-14",
        "impl": "feature_pipeline.compute_indicators",
        "impl_refs": ["src/features/feature_pipeline.py:246-255"],
        "pit": "diff + rolling 14 causal",
        "pit_class": "CAUSAL_ROLLING",
        "consumers": ["FeaturePipeline vector"],
    },
    "macd_line": {
        "source_ohlcv": ["close"],
        "formula": "EMA12 - EMA26",
        "formula_id": "MACD",
        "impl": "feature_pipeline.compute_indicators",
        "impl_refs": ["src/features/feature_pipeline.py:278-283"],
        "pit": "ewm causal",
        "pit_class": "CAUSAL_EWM",
        "consumers": ["FeaturePipeline", "macd_hist_raw"],
    },
    "macd_signal": {
        "source_ohlcv": ["close"],
        "formula": "EMA9(macd_line)",
        "formula_id": "MACD",
        "impl": "feature_pipeline.compute_indicators",
        "impl_refs": ["src/features/feature_pipeline.py:282"],
        "pit": "ewm causal",
        "pit_class": "CAUSAL_EWM",
        "consumers": ["FeaturePipeline", "macd_hist_raw"],
    },
    # v4.0 MACD split (feature_schema.py:82-84, Semantic Layer Certification Audit 2026-07-31,
    # Tier 1 items 1-2): the single v3.0 `macd_hist` entry below is now two canonical slots.
    "macd_hist_raw": {
        "source_ohlcv": ["close"],
        "formula": "macd_line - macd_signal (FM-049) -- the DECLARED formula, unchanged from v3.0",
        "formula_id": "FM-049",
        "impl": "feature_pipeline.compute_indicators",
        "impl_refs": ["src/features/feature_pipeline.py:283"],
        "pit": "causal",
        "pit_class": "CAUSAL_DERIVED",
        "consumers": ["FeaturePipeline vector", "macd_hist_z"],
        "note": "v4.0 rename of the v3.0 `macd_hist` entry -- same math, index moved 18->18 "
                "(this identity) while the z-scored value it used to silently carry moved to "
                "its own slot, macd_hist_z (index 19).",
    },
    "macd_hist_z": {
        "source_ohlcv": ["close"],
        "formula": "rolling(50) z-score of macd_hist_raw (FM-053)",
        "formula_id": "FM-053",
        "impl": "feature_pipeline.compute_normalization (NORMALIZE_TO_NEW_COL)",
        "impl_refs": ["src/features/feature_pipeline.py"],
        "pit": "causal rolling(50)",
        "pit_class": "CAUSAL_DERIVED",
        "consumers": ["FeaturePipeline vector"],
        "note": "v4.0 new slot (index 19) -- what v3.0's single `macd_hist` column actually "
                "EMITTED (compute_normalization overwrote it in place); now has its own "
                "canonical identity distinct from macd_hist_raw.",
    },
    "sweep_detected": {
        "source_ohlcv": ["high", "low", "close"],
        "formula": "liquidity_sweep != 0 (production liquidity_sweep is causal-graph)",
        "formula_id": "STRUCT-SWEEP",
        "impl": "feature_pipeline compute_canonical_structure_features",
        "impl_refs": ["src/features/feature_pipeline.py"],
        "pit": "derived from causal structure graph (FC1-A)",
        "pit_class": "STRUCTURE_WITH_CAUSAL_SWING",
        "consumers": ["FeaturePipeline vector", "CRT score channel"],
        "note": "FC1-A 2026-07-11",
    },
    "liquidity_sweep": {
        "source_ohlcv": ["high", "low", "close"],
        "formula": "sweep high/low vs causal last_swing refs (shift(1))",
        "formula_id": "STRUCT-LIQ",
        "impl": "feature_pipeline compute_structure_liquidity (FC1-A)",
        "impl_refs": ["src/features/feature_pipeline.py"],
        "pit": "causal last_swing_*_price; bar t uses info through t",
        "pit_class": "STRUCTURE_WITH_CAUSAL_SWING",
        "consumers": ["FeaturePipeline vector", "FeatureStore live"],
        "note": "FC1-A 2026-07-11",
    },
    "break_of_structure": {
        "source_ohlcv": ["high", "low", "close"],
        "formula": "BOS vs causal last_swing refs",
        "formula_id": "STRUCT-BOS",
        "impl": "feature_pipeline compute_structure_liquidity (FC1-A)",
        "impl_refs": ["src/features/feature_pipeline.py"],
        "pit": "causal last_swing refs + shift(1)",
        "pit_class": "STRUCTURE_WITH_CAUSAL_SWING",
        "consumers": ["FeaturePipeline vector"],
        "note": "FC1-A 2026-07-11",
    },
    "swing_high": {
        "source_ohlcv": ["high"],
        "formula": f"centered pivot then delayed publication: centered.shift(k), k=SWING_WINDOW={SWING_WINDOW}",
        "formula_id": "STRUCT-SWING",
        "impl": "feature_pipeline compute_structure_liquidity production bind (FC1-A)",
        "impl_refs": ["src/features/feature_pipeline.py", "src/features/causal_structure.py", f"SWING_WINDOW={SWING_WINDOW}"],
        "pit": "production = causal_confirmed (available_at=t+k); research = swing_high_centered_batch (may leak)",
        "pit_class": "CAUSAL_DELAYED_PUBLICATION",
        "consumers": ["FeaturePipeline", "BOS/sweep features", "FeatureStore live"],
        "note": "FC1-A 2026-07-11: production no longer CENTERED_SWING_LOOKAHEAD_IN_BATCH",
    },
    "swing_low": {
        "source_ohlcv": ["low"],
        "formula": f"centered pivot then delayed publication: centered.shift(k), k=SWING_WINDOW={SWING_WINDOW}",
        "formula_id": "STRUCT-SWING",
        "impl": "feature_pipeline compute_structure_liquidity production bind (FC1-A)",
        "impl_refs": ["src/features/feature_pipeline.py", "src/features/causal_structure.py"],
        "pit": "production = causal_confirmed (available_at=t+k); research = swing_low_centered_batch",
        "pit_class": "CAUSAL_DELAYED_PUBLICATION",
        "consumers": ["FeaturePipeline", "BOS/sweep features", "FeatureStore live"],
        "note": "FC1-A 2026-07-11",
    },
    "higher_high": {
        "source_ohlcv": ["high"],
        "formula": "high > causal last_swing_high_price.shift(1)",
        "formula_id": "STRUCT-HH",
        "impl": "feature_pipeline structure (FC1-A coherent graph)",
        "impl_refs": ["src/features/feature_pipeline.py"],
        "pit": "depends on causal swing last prices",
        "pit_class": "STRUCTURE_WITH_CAUSAL_SWING",
        "consumers": ["FeaturePipeline vector"],
        "note": "FC1-A 2026-07-11",
    },
    "lower_low": {
        "source_ohlcv": ["low"],
        "formula": "low < causal last_swing_low_price.shift(1)",
        "formula_id": "STRUCT-LL",
        "impl": "feature_pipeline structure (FC1-A coherent graph)",
        "impl_refs": ["src/features/feature_pipeline.py"],
        "pit": "depends on causal swing last prices",
        "pit_class": "STRUCTURE_WITH_CAUSAL_SWING",
        "consumers": ["FeaturePipeline vector"],
        "note": "FC1-A 2026-07-11",
    },
    "body_size": {
        "source_ohlcv": ["open", "close"],
        "formula": "|close - open|",
        "formula_id": "FM-001-ish / candle_math.body_size",
        "impl": "candle_math.body_size + pipeline candle_body",
        "impl_refs": ["src/features/candle_math.py:25-27", "src/features/feature_pipeline.py"],
        "pit": "same-bar",
        "pit_class": "RAW_CONTEMPORANEOUS",
        "consumers": ["FeaturePipeline", "body_ratio", "CRT"],
    },
    "candle_range": {
        "source_ohlcv": ["high", "low"],
        "formula": "high - low (FM-002)",
        "formula_id": "FM-002",
        "impl": "candle_math.candle_range",
        "impl_refs": [
            "src/features/candle_math.py:30-32",
            "configs/formulas/market_ontology.yaml primitives.candle_range",
        ],
        "pit": "same-bar",
        "pit_class": "RAW_CONTEMPORANEOUS",
        "consumers": ["FeaturePipeline", "body_ratio", "volatility_ratio", "displacement_atr_ratio"],
        "note": "v4.0 rename (feature_schema.py:89, Semantic Layer Certification Audit "
                "2026-07-31, Tier 1 items 1-2): this entry was `wick_size` in v3.0 -- pure "
                "identity rename, math never changed (always high-low, never a wick "
                "magnitude -- see F-046 / candle_math.py). `wick_size` survives only as a "
                "read-side alias for historical records (SCHEMA_V3_ALIASES); never emitted.",
    },
    "body_ratio": {
        "source_ohlcv": ["open", "high", "low", "close"],
        "formula": "body_size / candle_range, 0 if range<=0",
        "formula_id": "FM-010",
        "impl": "candle_math.body_ratio + feature_pipeline parity",
        "impl_refs": [
            "src/features/candle_math.py:50-59",
            "configs/formulas/market_ontology.yaml body_ratio",
        ],
        "pit": "same-bar geometry",
        "pit_class": "RAW_CONTEMPORANEOUS",
        "consumers": ["FeaturePipeline", "CRT displacement gate body_ratio>=0.70", "FeatureMonitor"],
    },
    "volatility_regime": {
        "source_ohlcv": ["high", "low", "close"],
        "formula": "tercile of ATR rolling percentile rank (N=200); production bind FC1-D",
        "formula_id": "REGIME-VOL-ROLLING-CAUSAL",
        "impl": "feature_pipeline.compute_volatility_regime production → rolling_causal",
        "impl_refs": ["src/features/feature_pipeline.py", "SWING-adjacent: rolling window 200"],
        "pit": "rolling rank uses past+current only (min_periods=1); prefix-invariant interior",
        "pit_class": "CAUSAL_ROLLING",
        "consumers": ["FeaturePipeline vector", "s05_grid", "live_engine_hook pass-through"],
        "note": (
            "FC1-D 2026-07-11: production was GLOBAL_BATCH (non-PIT prefix ~43%). "
            "Adjudication FC-0.5 selected rolling N=200 causal; global preserved as "
            "volatility_regime_global_batch research/legacy only. Semantic is local "
            "ATR-percentile tercile context, not latent Regime Detection."
        ),
    },
    "session": {
        "source_ohlcv": ["timestamp"],
        "formula": "session bucket from hour/tz assumptions → SESSION_MAP float",
        "formula_id": "CAL-SESSION",
        "impl": "feature_pipeline session encode + feature_schema.SESSION_MAP",
        "impl_refs": ["src/features/feature_schema.py:91-100", "src/features/feature_pipeline.py"],
        "pit": "same-bar timestamp; UTC-naive assumption",
        "pit_class": "CALENDAR_SAME_BAR",
        "consumers": ["FeaturePipeline vector", "session filters"],
    },
    "hour_of_day": {
        "source_ohlcv": ["timestamp"],
        "formula": "timestamp.hour (or fraction)",
        "formula_id": "CAL-HOUR",
        "impl": "feature_pipeline",
        "impl_refs": ["src/features/feature_pipeline.py"],
        "pit": "same-bar",
        "pit_class": "CALENDAR_SAME_BAR",
        "consumers": ["FeaturePipeline vector"],
    },
    "disp_strength": {
        "source_ohlcv": ["open", "high", "low", "close"],
        # ONE canonical identity per vector member; colliding/historical identities
        # are related_identities, never blended into the formula (2026-07-11 hardening).
        "formula": "clip(body_size / (atr * close), 0, 3) — FM-020 (pipeline vector definition)",
        "formula_id": "FM-020",
        "related_identities": [
            {"id": "FM-028", "name": "displacement_atr_ratio",
             "role": "distinct CRT range/ATR multiple, historically emitted under 'disp_strength' — renamed off pipeline names by F-050/CH-002"},
            {"id": "FM-029", "name": "disp_strength_atr_rescale",
             "role": "distinct scoring_engine as-wired quantity FM-020/atr_rel — registered + routed by GD-004 closure 2026-07-11"},
        ],
        "impl": "derived_math.disp_strength (scalar authority) + feature_pipeline vectorized",
        "impl_refs": [
            "src/features/derived_math.py",
            "configs/formulas/market_ontology.yaml FM-020",
            "src/features/feature_pipeline.py",
        ],
        "pit": "ATR lookback causal; same-bar body",
        "pit_class": "CAUSAL_DERIVED",
        "consumers": ["FeaturePipeline", "CRT cached_features", "FeatureMonitor"],
        "note": "F-050 (FM-028 emission rename) + GD-004 (FM-029 registration): name collisions closed; this row is FM-020 only",
    },
    "retest_depth": {
        "source_ohlcv": ["high", "low", "close"],
        "formula": "FM-021 pipeline retest vs EMA/ATR; CRT has FM-027 displacement_retrace",
        "formula_id": "FM-021 / FM-027 split (F-050)",
        "impl": "feature_pipeline + derived_math; CRT derived_math FM-027",
        "impl_refs": [
            "src/features/feature_pipeline.py",
            "src/features/derived_math.py",
            "configs/formulas/market_ontology.yaml",
        ],
        "pit": "causal ATR/EMA; structure context",
        "pit_class": "CAUSAL_DERIVED",
        "consumers": ["FeaturePipeline", "CRT", "FeatureMonitor"],
    },
    "candles_since_retest": {
        "source_ohlcv": ["high", "low", "close"],
        "formula": "bars since last retest event flag",
        "formula_id": "STRUCT-COUNT",
        "impl": "feature_pipeline structure counters",
        "impl_refs": ["src/features/feature_pipeline.py"],
        "pit": "causal counter from past events",
        "pit_class": "CAUSAL_COUNTER",
        "consumers": ["FeaturePipeline vector"],
    },
    "liquidity_distance": {
        "source_ohlcv": ["high", "low", "close"],
        "formula": "ATR-normalised distance to nearest liquidity level (causal swing refs)",
        "formula_id": "FM-025/LIQ",
        "impl": "feature_pipeline liquidity block v3 + derived_math (FC1-A refs)",
        "impl_refs": ["src/features/feature_pipeline.py", "src/features/derived_math.py"],
        "pit": "depends on causal last_swing / BOS levels + shift(1)",
        "pit_class": "STRUCTURE_WITH_CAUSAL_SWING",
        "consumers": ["FeaturePipeline vector index 35"],
        "note": "FC1-A 2026-07-11",
    },
    "liquidity_pressure_score": {
        "source_ohlcv": ["high", "low", "close"],
        "formula": "clip(exp(-0.5 * liquidity_distance), 0, 1)",
        "formula_id": "FM-026/LIQ",
        "impl": "feature_pipeline + derived_math.liquidity_pressure_score",
        "impl_refs": ["src/features/feature_pipeline.py", "src/features/derived_math.py"],
        "pit": "derived from causal liquidity_distance",
        "pit_class": "STRUCTURE_WITH_CAUSAL_SWING",
        "consumers": ["FeaturePipeline vector index 36"],
        "note": "FC1-A 2026-07-11",
    },
    "volume_spike": {
        "source_ohlcv": ["volume", "high", "low"],
        "formula": "(volume_ratio > 1.5).astype(int8)",
        "formula_id": "VOL-SPIKE",
        "impl": "feature_pipeline.compute_volume_features",
        "impl_refs": ["src/features/feature_pipeline.py:231"],
        "pit": "causal volume_ratio",
        "pit_class": "CAUSAL_DERIVED",
        "consumers": ["FeaturePipeline vector index 37"],
    },

    # ── schema v5.0 SMC primitives, indices 39-47 (CH-htfcrt-parent-candle-smc-v1,
    # 2026-08-15). These landed AFTER the 2026-07-31 census run, so until this block
    # existed the generator raised `LINEAGE table mismatch` and could not run at all —
    # which is why the shipped artifact stayed at 39 rows and `feature_surface_query
    # --summary` reported `pit: {..., None: 9}` / `closure: {CLOSED: 39, None: 9}`.
    #
    # PIT classes are assigned from the EXISTING vocabulary, source-verified against
    # src/features/smc/ (577 lines, whole package read) — no new class was invented:
    #   · the five swing-founded distances reach price geometry only through
    #     `_geometry.detect_causal_swings`/`collect_causal_swings`, which confirm a pivot
    #     at j only once k later bars have closed (_geometry.py:46-76) — the same
    #     construction that makes liquidity_sweep/break_of_structure
    #     STRUCTURE_WITH_CAUSAL_SWING rather than CAUSAL_DELAYED_PUBLICATION (the latter
    #     is for the swing SLOTS themselves, which are stamped at the pivot bar).
    #   · fvg_distance touches no swing at all; it is a 3-candle test whose zone is
    #     stamped at the MIDDLE candle but is only knowable once bars[i+1] closed
    #     (fvg.py:23-37) — publication lag 1, i.e. exactly CAUSAL_DELAYED_PUBLICATION.
    #   · pdh/pdl read the most recently CLOSED D1 parent (levels.py:26-35), so the
    #     reference is a completed prior calendar unit, never the forming day.
    #   · change_of_character is pure algebra over two already-classified canonical
    #     slots and inherits the weaker parent (break_of_structure).
    # Emission is causal for all nine: compute_smc_features grows `window` strictly to
    # bar i before each call (feature_pipeline.py:1270-1292), and passes ABSOLUTE ATR
    # (`atr * close`, :1255), so the F-072/FM-074 dimensional trap does not apply here.
    "order_block_distance": {
        "source_ohlcv": ["open", "high", "low", "close"],
        "formula": f"tanh(signed ATR distance from close to nearest UNMITIGATED order-block edge); OB = last opposite-colour candle before a causal-swing break, k=SWING_WINDOW={SWING_WINDOW}",
        "formula_id": "SMC-OB",
        "impl": "feature_pipeline.compute_smc_features -> smc.order_block.order_block_distance",
        "impl_refs": ["src/features/feature_pipeline.py:1283", "src/features/smc/order_block.py", "src/features/smc/_geometry.py", f"SWING_WINDOW={SWING_WINDOW}"],
        "pit": "break events use detect_causal_swings(bars[:i], k) — no lookahead (order_block.py:38-50); window grows only to bar i",
        "pit_class": "STRUCTURE_WITH_CAUSAL_SWING",
        "consumers": ["FeaturePipeline vector index 39"],
        "note": "schema v5.0 (F-076); PIT classified 2026-09-05, classification only — grants no closure and no authority",
    },
    "fvg_distance": {
        "source_ohlcv": ["high", "low", "close"],
        "formula": "tanh(signed ATR distance from close to nearest UNFILLED fair-value-gap near edge); 3-candle test bars[i-1].high < bars[i+1].low (bullish) / bars[i-1].low > bars[i+1].high (bearish)",
        "formula_id": "SMC-FVG",
        "impl": "feature_pipeline.compute_smc_features -> smc.fvg.fvg_distance",
        "impl_refs": ["src/features/feature_pipeline.py:1284", "src/features/smc/fvg.py"],
        "pit": "zone is STAMPED at the middle candle (formed_at_index) but only becomes detectable once bars[i+1] has closed — publication lag 1; the interior loop range(1, n-1) never reads past the caller's window, so the EMITTED value at bar i uses only bars <= i (fvg.py:23-37)",
        "pit_class": "CAUSAL_DELAYED_PUBLICATION",
        "consumers": ["FeaturePipeline vector index 40"],
        "note": "schema v5.0 (F-076); the delayed publication is on the zone's backdated stamp, not on the emitted distance. PIT classified 2026-09-05",
    },
    "breaker_distance": {
        "source_ohlcv": ["open", "high", "low", "close"],
        "formula": f"tanh(signed ATR distance to nearest un-retested BREAKER — an order block whose far edge was fully closed through, polarity flipped), k=SWING_WINDOW={SWING_WINDOW}",
        "formula_id": "SMC-BREAKER",
        "impl": "feature_pipeline.compute_smc_features -> smc.breaker.breaker_distance",
        "impl_refs": ["src/features/feature_pipeline.py:1285", "src/features/smc/breaker.py", "src/features/smc/order_block.py"],
        "pit": "reuses order_block._find_break_events (causal swings, bars[:i]); breaker requires a LATER close-through, so it is strictly backward-looking",
        "pit_class": "STRUCTURE_WITH_CAUSAL_SWING",
        "consumers": ["FeaturePipeline vector index 41"],
        "note": "schema v5.0 (F-076); PIT classified 2026-09-05",
    },
    "mitigation_block_distance": {
        "source_ohlcv": ["open", "high", "low", "close"],
        "formula": f"tanh(signed ATR distance to the BODY-only inner zone of the active OB origin whose outer zone was already touched), k=SWING_WINDOW={SWING_WINDOW}",
        "formula_id": "SMC-MITIGATION",
        "impl": "feature_pipeline.compute_smc_features -> smc.mitigation.mitigation_block_distance",
        "impl_refs": ["src/features/feature_pipeline.py:1286", "src/features/smc/mitigation.py", "src/features/smc/order_block.py"],
        "pit": "same causal break-event scan as order_block; the outer-zone touch it gates on is a past event",
        "pit_class": "STRUCTURE_WITH_CAUSAL_SWING",
        "consumers": ["FeaturePipeline vector index 42"],
        "note": "schema v5.0 (F-076); deliberately a DIFFERENT distance from order_block_distance, not an alias. PIT classified 2026-09-05",
    },
    "pdh_distance": {
        "source_ohlcv": ["high", "close"],
        "formula": "tanh(signed ATR distance from close to the most recently CLOSED D1 parent's high); 0.0 before the first D1 parent closes",
        "formula_id": "SMC-PDH",
        "impl": "feature_pipeline.compute_smc_features (ParentCandleBuilder('D1')) -> smc.levels.pdh_pdl_distance",
        "impl_refs": ["src/features/feature_pipeline.py:1287", "src/features/smc/levels.py", "src/features/parent_candle.py"],
        "pit": "reads parent_history[-1] = the last COMPLETED daily candle, never the forming one (levels.py:26-35); reference is a prior calendar unit, so it is delayed relative to the bar that publishes it",
        "pit_class": "CAUSAL_DELAYED_PUBLICATION",
        "consumers": ["FeaturePipeline vector index 43"],
        "note": "schema v5.0 (F-076); NOT CALENDAR_SAME_BAR — session/hour_of_day derive from the bar's OWN timestamp, this derives from a previous completed day. PIT classified 2026-09-05",
    },
    "pdl_distance": {
        "source_ohlcv": ["low", "close"],
        "formula": "tanh(signed ATR distance from close to the most recently CLOSED D1 parent's low); 0.0 before the first D1 parent closes",
        "formula_id": "SMC-PDL",
        "impl": "feature_pipeline.compute_smc_features (ParentCandleBuilder('D1')) -> smc.levels.pdh_pdl_distance",
        "impl_refs": ["src/features/feature_pipeline.py:1287", "src/features/smc/levels.py", "src/features/parent_candle.py"],
        "pit": "reads parent_history[-1] = the last COMPLETED daily candle, never the forming one (levels.py:26-35)",
        "pit_class": "CAUSAL_DELAYED_PUBLICATION",
        "consumers": ["FeaturePipeline vector index 44"],
        "note": "schema v5.0 (F-076); PIT classified 2026-09-05",
    },
    "eqh_distance": {
        "source_ohlcv": ["high", "close"],
        "formula": f"tanh(signed ATR distance to the most recent member of an EQUAL-HIGHS cluster — 2+ confirmed swing highs within tolerance_atr=0.1 * atr), k=SWING_WINDOW={SWING_WINDOW}",
        "formula_id": "SMC-EQH",
        "impl": "feature_pipeline.compute_smc_features -> smc.levels.eqh_eql_distance",
        "impl_refs": ["src/features/feature_pipeline.py:1290", "src/features/smc/levels.py", "src/features/smc/_geometry.py"],
        "pit": "collect_causal_swings only returns pivots confirmed by k closed later bars (_geometry.py:79-101)",
        "pit_class": "STRUCTURE_WITH_CAUSAL_SWING",
        "consumers": ["FeaturePipeline vector index 45"],
        "note": "schema v5.0 (F-076); cluster extension of the single-swing FM-025/026 liquidity reading. PIT classified 2026-09-05",
    },
    "eql_distance": {
        "source_ohlcv": ["low", "close"],
        "formula": f"tanh(signed ATR distance to the most recent member of an EQUAL-LOWS cluster — 2+ confirmed swing lows within tolerance_atr=0.1 * atr), k=SWING_WINDOW={SWING_WINDOW}",
        "formula_id": "SMC-EQL",
        "impl": "feature_pipeline.compute_smc_features -> smc.levels.eqh_eql_distance",
        "impl_refs": ["src/features/feature_pipeline.py:1290", "src/features/smc/levels.py", "src/features/smc/_geometry.py"],
        "pit": "collect_causal_swings only returns pivots confirmed by k closed later bars (_geometry.py:79-101)",
        "pit_class": "STRUCTURE_WITH_CAUSAL_SWING",
        "consumers": ["FeaturePipeline vector index 46"],
        "note": "schema v5.0 (F-076); PIT classified 2026-09-05",
    },
    "change_of_character": {
        "source_ohlcv": ["high", "low", "close"],
        "formula": "break_of_structure if sign(break_of_structure) != sign(trend_bias) and both nonzero, else 0.0",
        "formula_id": "FM-083/SMC-CHOCH",
        "impl": "feature_pipeline.compute_smc_features -> smc.choch.change_of_character",
        "impl_refs": ["src/features/feature_pipeline.py:1303", "src/features/smc/choch.py"],
        "pit": "stateless algebra over two already-classified canonical slots; inherits the weaker parent (break_of_structure = STRUCTURE_WITH_CAUSAL_SWING), trend_bias is CAUSAL_DERIVED",
        "pit_class": "STRUCTURE_WITH_CAUSAL_SWING",
        "consumers": ["FeaturePipeline vector index 47"],
        "note": "schema v5.0 (F-076); adds NO new BOS/CHoCH detection state machine (choch.py:6-15). Registered FM-083 and STATEFUL in the ontology, but named in NO resolver `when:` clause. PIT classified 2026-09-05",
    },
}


def _grep_consumers(name: str) -> list[str]:
    """Cheap static consumer hits in src/ for feature name string."""
    hits = []
    pat = re.compile(rf"\b{re.escape(name)}\b")
    for p in (ROOT / "src").rglob("*.py"):
        try:
            t = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if pat.search(t):
            rel = str(p.relative_to(ROOT)).replace("\\", "/")
            # skip schema self
            if rel.endswith("feature_schema.py"):
                continue
            hits.append(rel)
    return sorted(set(hits))[:12]


def main() -> int:
    # De-literalized 2026-07-31 (Semantic Layer Certification Audit, Tier 1 items 1-3): was
    # `== 38`, pinned to schema v3.0. Schema v4.0 (2026-07-22) raised the dim to 39
    # (feature_schema.py:114); this assertion now tracks the live schema instead of the literal.
    assert len(CANONICAL_FEATURES) == CANONICAL_FEATURE_DIM
    missing = [f for f in CANONICAL_FEATURES if f not in LINEAGE]
    extra = [f for f in LINEAGE if f not in CANONICAL_FEATURES]
    if missing or extra:
        raise SystemExit(f"LINEAGE table mismatch missing={missing} extra={extra}")

    # Optional smoke: build features on frozen XAU
    smoke = {"status": "SKIPPED"}
    try:
        from data_ingestion.xauusd_phase1_candidate import require_phase1_frozen_candidate
        from features.feature_pipeline import FeaturePipeline
        import pandas as pd

        require_phase1_frozen_candidate(repo_root=ROOT)
        df = pd.read_csv(ROOT / "data/mt5/XAUUSD_M15.csv")
        df.columns = [c.strip().lower() for c in df.columns]
        pipe = FeaturePipeline(df)
        enriched, vectors = pipe.run()
        present = [f for f in CANONICAL_FEATURES if f in enriched.columns]
        smoke = {
            "status": "PASS",
            "corpus": "data/mt5/XAUUSD_M15.csv",
            "rows_out": len(enriched),
            "vector_rows": len(vectors) if vectors is not None else 0,
            "canonical_columns_present": f"{len(present)}/{CANONICAL_FEATURE_DIM}",
            "missing_columns": [f for f in CANONICAL_FEATURES if f not in enriched.columns],
        }
    except Exception as e:
        smoke = {"status": "FAIL", "error": repr(e)}

    features_out = []
    for i, name in enumerate(CANONICAL_FEATURES):
        meta = dict(LINEAGE[name])
        meta["index"] = i
        meta["name"] = name
        meta["static_consumers_sample"] = _grep_consumers(name)
        features_out.append(meta)

    pit_classes = Counter = __import__("collections").Counter(
        f["pit_class"] for f in features_out
    )

    report = {
        "_doc": f"Canonical-feature lineage census ({CANONICAL_FEATURE_DIM}-dim, schema "
                f"v{SCHEMA_VERSION}). Source-verified table + optional frozen-XAU smoke. "
                "Dim/version are read from the live schema, never re-declared here — the "
                "hardcoded '39-dim, schema v4.0' text survived the v5.0 bump and described "
                "an artifact that no longer existed (corrected 2026-09-05).",
        "generated_at_utc": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "schema": {
            "canonical_feature_dim": CANONICAL_FEATURE_DIM,
            "schema_hash_md5": SCHEMA_HASH,
            "feature_order_hash": FEATURE_ORDER_HASH
            if isinstance(FEATURE_ORDER_HASH, str)
            else str(FEATURE_ORDER_HASH),
            "n_features": len(CANONICAL_FEATURES),
        },
        "pit_class_counts": dict(pit_classes),
        "smoke_on_frozen_xauusd": smoke,
        "features": features_out,
        "chain_template": "source_ohlcv → formula → impl → pit_class → consumers",
        "authority": "Research/architecture only. No economic claims. No formula changes.",
    }
    # feature_order_hash may be a function in some versions — fix
    try:
        from features.feature_schema import _feature_order_hash

        report["schema"]["feature_order_hash"] = _feature_order_hash(CANONICAL_FEATURES)
    except Exception:
        pass

    report["resync_notes"] = [
        "2026-07-11: FC1-A structure family PIT classes updated to causal delayed publication",
        "2026-07-11: FC1-D volatility_regime production → rolling causal N=200",
        "2026-07-11: wick_size documented as exact FM-002 candle_range alias",
        "2026-07-31 (Semantic Layer Certification Audit, Tier 1 items 1-3): re-synced to "
        "schema v4.0 (39-dim) -- wick_size renamed to candle_range (its own entry, not an "
        "alias, since v4.0 made candle_range the canonical name); macd_hist split into "
        "macd_hist_raw (index 18) + macd_hist_z (index 19); dim assertion de-literalized "
        "38 -> CANONICAL_FEATURE_DIM.",
    ]
    payload = json.dumps(report, indent=2) + "\n"
    OUT_JSON.write_text(payload, encoding="utf-8")
    # Stable pointer (item 5, 2026-07-11 hardening): consumers resolve THROUGH this,
    # dated files are never rewritten after their day.
    import hashlib as _hashlib
    OUT_LATEST_PTR.write_text(json.dumps({
        "_doc": "Stable pointer to the freshest lineage census. Dated artifacts are "
                "immutable; resolve via this pointer (verify sha256) or embedded "
                "generated_at_utc — never by filename date.",
        "path": str(OUT_JSON.relative_to(ROOT)).replace("\\", "/"),
        "generated_at": report["generated_at_utc"],
        "schema_hash": report.get("schema_hash") or SCHEMA_HASH,
        "feature_order_hash": FEATURE_ORDER_HASH,
        "sha256": _hashlib.sha256(payload.encode("utf-8")).hexdigest(),
    }, indent=2) + "\n", encoding="utf-8")

    lines = [
        f"# Canonical-Feature Lineage Census ({CANONICAL_FEATURE_DIM}-dim, schema v{SCHEMA_VERSION})",
        "",
        f"Generated (UTC): `{report['generated_at_utc']}`",
        "",
        f"Schema dim: **{CANONICAL_FEATURE_DIM}** · smoke: **{smoke.get('status')}**",
        "",
        f"_Resync: FC1-A structure + FC1-D volregime + wick_size↔candle_range alias._",
        "",
        "## PIT class rollup",
        "",
        "```json",
        json.dumps(report["pit_class_counts"], indent=2),
        "```",
        "",
        "## Per-feature chain",
        "",
        "| # | Feature | Source OHLCV | Formula ID | PIT class | Primary impl |",
        "|---:|---|---|---|---|---|",
    ]
    for f in features_out:
        lines.append(
            f"| {f['index']} | `{f['name']}` | {', '.join(f['source_ohlcv'])} | "
            f"{f.get('formula_id','')} | `{f['pit_class']}` | `{f['impl_refs'][0] if f.get('impl_refs') else ''}` |"
        )
    lines += [
        "",
        "### Detail blocks",
        "",
    ]
    for f in features_out:
        lines += [
            f"#### {f['index']}. `{f['name']}`",
            "",
            f"- **Source OHLCV:** {f['source_ohlcv']}",
            f"- **Formula:** {f['formula']}",
            f"- **Impl:** {f['impl']} — {f.get('impl_refs')}",
            f"- **PIT:** {f['pit']} (`{f['pit_class']}`)",
            f"- **Consumers (curated):** {f.get('consumers')}",
            f"- **Consumers (static sample):** {f.get('static_consumers_sample')}",
        ]
        if f.get("pit_caveat"):
            lines.append(f"- **Caveat:** {f['pit_caveat']}")
        if f.get("mutation_risk"):
            lines.append(f"- **Mutation risk:** {f['mutation_risk']}")
        if f.get("note"):
            lines.append(f"- **Note:** {f['note']}")
        lines.append("")

    lines += [
        "## Smoke (frozen XAUUSD)",
        "",
        "```json",
        json.dumps(smoke, indent=2),
        "```",
        "",
        f"Machine twin: `{OUT_JSON.name}` (also refreshed stable `feature_38_lineage_census-2026-07-10.json`)",
        "",
    ]
    md_text = "\n".join(lines)
    OUT_MD.write_text(md_text, encoding="utf-8")
    print(f"Wrote {OUT_JSON}")
    print(f"Wrote {OUT_MD}")
    print(f"Wrote pointer {OUT_LATEST_PTR.name}")
    print("smoke", smoke)
    print("pit_classes", dict(pit_classes))
    return 0 if smoke.get("status") in ("PASS", "SKIPPED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
