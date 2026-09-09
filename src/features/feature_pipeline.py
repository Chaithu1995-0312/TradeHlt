"""
feature_pipeline.py
====================
Production-grade feature engineering pipeline for M15 OHLCV data.

Produces a deterministic feature vector of length ``CANONICAL_FEATURE_DIM`` aligned to
CANONICAL_FEATURES from features.feature_schema.py (the single source of truth).
That dim is **39** under schema v4.0 — quote the constant, not the number: this docstring
carried a stale "32" and "38" simultaneously across the v2->v3->v4 migrations.

Only pandas + numpy are used (no TA-lib or other external TA libraries).

Pipeline contract
-----------------
    build_features(row)        → Dict[str, float]   (CANONICAL_FEATURES keys)
    validate_features(f, schema)                     (fail-fast — no return)
    build_feature_vector(f)    → List[float]         (CANONICAL_FEATURE_DIM values, strict order)

Batch usage
-----------
    pipeline = FeaturePipeline(df)
    enriched_df, vectors = pipeline.run()
    # Drift report available after run():
    print(pipeline.monitor.summary())

Edge Cases:
    - Zero volume (Forex): source `volume` is preserved (TICK_VOLUME identity).
      A distinct `volume_range_proxy = high-low` column is emitted (Phase-1 identity
      closure). The legacy T-003 path that overwrote `volume` with the proxy is
      retired from governed authority.
    - Flat market (ATR ≈ 0): bb_position has a 1e-9 denominator guard.
      ATR-gated features (ema_spread, momentum_score, disp_strength,
      retest_depth) emit NaN during the 14-bar ATR warmup; finalize()
      drops those rows cleanly.
    - Warmup NaNs: finalize() drops all NaN rows. Empirically ~78 rows for the 38
      canonical columns, driven by the rolling(50) z-score stacked on trend_strength/
      macd_hist. NOT driven by ma_200: that column has a 199-row NaN tail but is not
      a canonical feature, so it never reaches finalize()'s dropna subset.
      Callers must ensure sufficient history.

Failure Modes:
    - Feature drift: pipeline is stateless. If market regime shifts, retrain.
    - Lookahead bias: swing reference prices use .shift(1) so current-bar data
      never influences the same bar's BOS/sweep decision.
    - Swing detection (FC1-A, 2026-07-11): the centered (center=True) pivot is
      computed only for the research/legacy ``*_centered_batch`` columns; the
      PRODUCTION swing columns bind to the CAUSAL-DELAYED publication (centered
      pivot shifted by k=swing_window, available_at=t+k) in
      compute_structure_liquidity — so batch and live are already trailing-only,
      no separate live swing detector is required. (This bullet previously said
      "replace with a trailing-only swing detector for live inference"; that was
      the pre-FC1-A text, corrected 2026-07-19 per §6.2.)
"""

import math
import logging
from typing import Optional

import pandas as pd
import numpy as np

from features.feature_schema import CANONICAL_FEATURES
from features.schema_validator import validate_features, validate_feature_values, validate_vector
from features.feature_monitor import FeatureMonitor
from data_ingestion.ohlcv_schema import require_ohlcv_columns, validate_ohlcv_frame
from utils.logging_config import get_flow_logger

logger = get_flow_logger("FEATURE_PIPELINE")

# `SWING_WINDOW` is defined LAZILY via module __getattr__ at the bottom of this file (PEP 562).
# See resolve_swing_window() for the rationale — it must not be an independent literal, but it
# also must not force a config load at import time (that would create a module-level
# features -> config_layer edge, the cycle risk the deferred imports elsewhere guard against).

# Indicator period keys required in the `feature_pipeline` production-config section.
# CLAUDE.md Section 6.5 exception (2026-07-18): these are the ONLY constants reclassified
# BEHAVIORAL/config-driven by that exception. Scope is rolling-window/span PERIOD NUMBERS
# only -- the geometric primitives (body_size/wick_size/body_ratio/candle_body/upper_wick/
# lower_wick) remain STRUCTURAL/immutable per candle_math.py's own doctrine and are NOT
# covered here.
_FP_CFG_KEYS = (
    # Indicator periods (2026-07-18 migration).
    "rsi_period", "atr_period", "ma_periods", "bb_period", "bb_std",
    "macd_fast", "macd_slow", "macd_signal", "trend_strength_window",
    "ema_fast_span", "ema_slow_span",
    # ── Tier 3 BEHAVIORAL (Phase A, 2026-07-19) — no registered identity affected. ──
    "volume_ma_window", "volume_spike_fixed_fallback",
    "rsi_overbought", "rsi_oversold",
    "range_size_window", "displacement_strong_body_mult",
    "retest_lookback", "retest_atr_band_mult", "double_sweep_window",
    "volume_spike_adaptive_window", "volume_spike_min_samples", "volume_spike_percentile",
    # ── Tier 2 TUNABLE STRUCTURAL (Phase A, 2026-07-19) — each shapes a REGISTERED identity;
    # changing one redefines that feature, requires an ontology formula re-sync, and invalidates
    # trained artifacts. `swing_window` is deliberately NOT here (Phase B: it is a cross-module
    # import and sets the FC1-A causal delay, not just a window). ──
    "disp_strength_clip_low", "disp_strength_clip_high",      # FM-020
    "retest_depth_clip_low", "retest_depth_clip_high",        # FM-021
    "liquidity_decay_coeff", "liquidity_nan_sentinel",        # FM-026
    "volatility_percentile_window",                           # FM-050
    "volatility_tercile_low", "volatility_tercile_high",      # FM-050
    "zscore_window",                                          # FM-049
    # FM-052 (v4.0): REPLACES session_asia_end_hour / session_london_end_hour. Those two defined
    # a 3-value hour PARTITION; this defines the 5-value WINDOW model. The old keys are removed
    # rather than reused, because silently changing a key's meaning is the config-illusion class
    # F-056 closed — a stale config must FAIL, not be reinterpreted.
    "session_windows_utc",                                    # FM-052
    "swing_window",                                           # FM-045/046 + FC1-A PIT delay
    # ── FM-030/031 identity selector (2026-07-22) — NOT a period. Chooses which registered
    # identity `ema_spread` / `momentum_score` emit. "atr_relative" == the legacy FM-022/FM-023
    # math verbatim (the default; byte-identical to the pre-2026-07-22 pipeline);
    # "atr_absolute" == the scale-invariant FM-030/FM-031 corrections. Program
    # FM-030-031-DIMENSIONAL-MIX-MIGRATION under the 2026-07-20 feature-layer freeze. ──
    "normalization_basis",                                    # FM-022/023 <-> FM-030/031
    # ── session/hour_of_day timestamp domain selector (F-066, 2026-08-01) — NOT a window.
    # Chooses which clock `hour_of_day`/`session` (FM-052) are derived from. "broker_local" ==
    # the legacy behavior (byte-identical to every pipeline run before this key existed): derives
    # from the raw `timestamp` column AS-IS, which for every MT5-sourced corpus is actually
    # broker-server time (EET/EEST, NY-DST-tracking), not UTC, despite `session_windows_utc`'s
    # name and the "real market sessions in UTC" doctrine in session_classifier.py. Measured this
    # session (docs/research/preregistration-blind-label-descriptive-fidelity.md investigation):
    # two independent tests (BTCUSDT cross-correlation, NFP-release alignment) confirm the offset
    # and its New-York DST tracking; 53.36% of XAUUSD bars carry the wrong session label under the
    # legacy basis. "utc_corrected" == derive from `broker_clock.mt5_server_to_utc(timestamp)`,
    # making `session`/`hour_of_day` true UTC as `session_windows_utc` already claims.
    # SCOPE (updated 2026-08-05): this key now ALSO gates the `crt_engine` trade-gating session
    # FILTER (`CRTEngine.__init__` resolves `self._session_ts_basis` from this same key; the
    # filter block converts `candle.timestamp` via `broker_clock.mt5_server_to_utc_scalar` before
    # its window comparison when set to "utc_corrected"). Originally (2026-08-01) this key only
    # reached the FM-052 FEATURE, leaving the FILTER reading the raw broker timestamp regardless
    # of this setting — that gap is closed. `crt_engine.session_windows`'s own numeric values are
    # UNCHANGED (they were already authored as UTC per `CRTConfig.session_windows`'s "(UTC)"
    # comment; only the comparison basis was wrong).
    # SCOPE WARNING (corrected same-session after an initial drafting error — CLAUDE.md E-001):
    # "utc_corrected" shifts WHATEVER timestamp it is given by the NY-DST offset; it does NOT
    # detect data provenance. It is only valid for MT5-sourced frames (data/mt5/*.csv). Feeding it
    # an already-true-UTC corpus (Binance) would WRONGLY subtract 2-3h and corrupt session/
    # hour_of_day AND the trade filter on that corpus — there is no automatic guard, since the
    # DataFrame carries no provenance marker; this is a per-config/per-caller responsibility. See
    # tests/test_session_timestamp_basis.py for a regression proving the shift is NOT a no-op on
    # non-MT5 timestamps (documented, not just asserted away). ──
    "session_timestamp_basis",                                # FM-052 clock domain + crt_engine filter
    # ── SMC primitives (CH-htfcrt-parent-candle-smc-v1, 2026-08-15) — `compute_smc_features`
    # reuses the EXISTING `swing_window` key above (no duplicate) for its causal swing half-
    # window; `smc_max_window` is the ONE genuinely new key, a trailing-candle-buffer bound
    # for the OB/FVG/breaker/mitigation scanners (a performance/scope bound, not a registered
    # identity parameter — smaller values simply forget older, likely-stale zones sooner).
    "smc_max_window",
)

# Legal values for `feature_pipeline.normalization_basis`. Anything else is a config-authoring
# error and raises -- there is deliberately NO silent fall-through to the legacy arm (§6.5).
_NORMALIZATION_BASES = ("atr_relative", "atr_absolute")

# Legal values for `feature_pipeline.session_timestamp_basis`. Same no-silent-fallback rule.
_SESSION_TIMESTAMP_BASES = ("broker_local", "utc_corrected")

# C2 (2026-07-31 semantic layer audit, extends F-061 from crypto to XAUUSD): "atr_relative"
# selects FM-022/FM-023, which the feature certification ledger marks SUPERSEDED by FM-030/031
# (2026-07-31 re-certification) -- yet it remains the ACTIVE default. Measured on XAUUSD
# (data/mt5/XAUUSD_M15.csv, n=19,922): |ema_spread| exceeds the dual_engine trend threshold
# (0.15) on 99.99% of bars, |tanh(momentum_score)| saturates (>0.999) on 99.70% of bars, and the
# emitted magnitude scales exactly 100x under a 100x price shift (vs. 1.000x for every other
# ATR-normalized dim) -- confirming the dimensional-mix defect on a non-crypto instrument.
# Log-only: fires once per process, does not change normalization_basis or any emitted value.
# Declaration only per §6.5 (tunability is not authority; activation needs demonstrated G001
# improvement plus dual_engine threshold recalibration -- see market_ontology.yaml FM-022/023).
_C2_SUPERSEDED_BASIS_WARNED = False


def _warn_once_if_superseded_basis(basis: str) -> None:
    global _C2_SUPERSEDED_BASIS_WARNED
    if basis == "atr_relative" and not _C2_SUPERSEDED_BASIS_WARNED:
        _C2_SUPERSEDED_BASIS_WARNED = True
        logger.warning(
            "feature_pipeline.normalization_basis='atr_relative': binding FM-022 ema_spread / "
            "FM-023 momentum_score, both marked SUPERSEDED in the feature certification ledger "
            "(superseded by FM-030/FM-031). Measured decision-surface cost on XAUUSD: "
            "|ema_spread|>0.15 on 99.99 pct of bars, |tanh(momentum_score)|>0.999 on 99.70 pct "
            "of bars (C2, extends F-061). This is the ACTIVE default and no config was changed "
            "by this warning -- see market_ontology.yaml FM-022/FM-023 for the correction path."
        )


# F-066 (2026-08-01 blind-label investigation). Declaration only, mirrors _warn_once_if_
# superseded_basis's pattern exactly -- logs once, changes no emitted value.
_F066_BROKER_LOCAL_BASIS_WARNED = False


def _warn_once_if_mislabeled_session_basis(basis: str) -> None:
    global _F066_BROKER_LOCAL_BASIS_WARNED
    if basis == "broker_local" and not _F066_BROKER_LOCAL_BASIS_WARNED:
        _F066_BROKER_LOCAL_BASIS_WARNED = True
        logger.warning(
            "feature_pipeline.session_timestamp_basis='broker_local': `session`/`hour_of_day` "
            "(FM-052) AND the crt_engine session-gating FILTER are both derived from the raw "
            "timestamp AS-IS. On MT5-sourced corpora (data/mt5/*.csv) that raw timestamp is "
            "broker-server time (EET/EEST, NY-DST-tracking), not UTC, though session_windows_utc's "
            "name and docstring claim UTC. F-066: measured 53.36 pct of XAUUSD bars carry the "
            "wrong session label under this basis (two independent cross-instrument tests confirm "
            "the offset). This is the ACTIVE default and no config was changed by this warning -- "
            "see docs/research/preregistration-blind-label-descriptive-fidelity.md and "
            "features/broker_clock.py for the correction path ('utc_corrected', which as of "
            "2026-08-05 also gates CRTEngine's session filter, not just the FM-052 feature)."
        )


def _require_fp_cfg(cfg: dict, key: str) -> object:
    """Strict accessor for the `feature_pipeline` config section.

    No `.get(key, literal)` fallback -- a missing key is a config authoring error
    (CLAUDE.md Section 6.5 hard rule), not a silent revert to the old hardcoded value.
    """
    if key not in cfg:
        raise KeyError(
            f"Required config key 'feature_pipeline.{key}' missing. "
            "Add it to the active production config's 'feature_pipeline' section "
            "(see configs/production/v2_multi_2026_04.json for the reference values)."
        )
    return cfg[key]


def _resolve_feature_pipeline_cfg(cfg: Optional[dict]) -> dict:
    """Resolve the feature_pipeline config section, strict on every key.

    If *cfg* is None, load from the active production config via a function-local
    import (established repo convention -- see agent/cli.py, findings_synthesizer.py,
    groq_client.py -- avoids a module-level features<->config_layer import cycle;
    config_layer.production_config itself imports no features.* module, but
    config_layer.crt_engine_v2 / config_layer.rr.rr_dataset_builder DO import
    features.*, so the reverse edge is deferred rather than risked).
    """
    if cfg is None:
        from config_layer.production_config import get_prod_section
        cfg = get_prod_section("feature_pipeline")
    for key in _FP_CFG_KEYS:
        _require_fp_cfg(cfg, key)
    _basis = cfg["normalization_basis"]
    if _basis not in _NORMALIZATION_BASES:
        raise ValueError(
            f"feature_pipeline.normalization_basis={_basis!r} is not one of "
            f"{_NORMALIZATION_BASES}. An unrecognised value must NOT silently fall through to "
            "the legacy arm -- it would emit a different feature identity than the config declares."
        )
    _warn_once_if_superseded_basis(_basis)
    _ts_basis = cfg["session_timestamp_basis"]
    if _ts_basis not in _SESSION_TIMESTAMP_BASES:
        raise ValueError(
            f"feature_pipeline.session_timestamp_basis={_ts_basis!r} is not one of "
            f"{_SESSION_TIMESTAMP_BASES}. An unrecognised value must NOT silently fall through "
            "to the legacy arm -- it would emit a different session/hour_of_day identity than "
            "the config declares."
        )
    _warn_once_if_mislabeled_session_basis(_ts_basis)
    return cfg


def resolve_swing_window(cfg: Optional[dict] = None) -> int:
    """THE single source of truth for the swing half-window `k` (PHASE B, 2026-07-19).

    `swing_window` is TUNABLE STRUCTURAL with the largest blast radius in the feature layer: it
    sets BOTH the pivot half-window (rolling width ``2k+1``) AND the FC1-A causal publication
    delay (``available_at = t+k``) — i.e. WHEN a feature becomes knowable, not merely how it is
    sized. It also defines ``lookback`` on FM-045/FM-046.

    **Provenance rule (why this function exists):** every governance/certification script that
    records a `swing_window` fact MUST resolve it through here — never re-declare the literal —
    so an artifact can never assert a value the pipeline did not actually use. Changing this
    value invalidates artifacts certified against the old one: re-certification, not a re-run.
    """
    if cfg is None:
        from config_layer.production_config import get_prod_section
        cfg = get_prod_section("feature_pipeline")
    return int(_require_fp_cfg(cfg, "swing_window"))


def resolve_double_sweep_window(cfg: Optional[dict] = None) -> int:
    """THE single source of truth for the `double_sweep` lookback window (T-7, 2026-07-19).

    Tier 3 BEHAVIORAL — `double_sweep` carries no FM id, so tuning this redefines no registered
    identity. It is nonetheless resolved through one function because the window is consumed on
    BOTH sides of the batch/live boundary (``compute_structure_liquidity`` and, via
    ``causal_structure``, the live ``FeatureStore``); before T-7 the live side defaulted to a
    literal 5 and silently ignored config.
    """
    if cfg is None:
        from config_layer.production_config import get_prod_section
        cfg = get_prod_section("feature_pipeline")
    return int(_require_fp_cfg(cfg, "double_sweep_window"))


def required_warmup_rows(cfg: Optional[dict] = None) -> int:
    """THE single source of truth for the canonical feature warmup (rows `finalize()` drops).

    `finalize()` drops every row carrying NaN in ANY column of ``CANONICAL_FEATURES``. Exactly one
    canonical column sets that floor — ``trend_strength`` — through a four-stage rolling chain:

        ma_20          = close.rolling(ma_periods[0]).mean()      first valid @ ma_periods[0] - 1
        ma_slope_20    = ma_20.diff()                             first valid @ ma_periods[0]
        trend_strength = ma_slope_20.rolling(trend_window).mean() first valid @ + trend_window - 1
        z-score        = .rolling(zscore_window).mean()/.std()    first valid @ + zscore_window - 1

    The first VALID index is therefore ``(ma_periods[0] - 1) + 1 + (trend_window - 1) +
    (zscore_window - 1)``, and rows ``0..first_valid-1`` are dropped — so the DROP COUNT equals
    that index:

    ⇒ ``ma_periods[0] + (trend_strength_window - 1) + (zscore_window - 1)``. On the active config
    (20 / 10 / 50) that is **78**, matching the measured drop count at 3,949 / 47,275 / 50,169
    rows. (Returning the first-valid *index* and the *count* of dropped rows are the same number
    only because the drop is a prefix; `tests/test_feature_warmup_coupling.py` pins this against
    the real pipeline so the identity cannot drift into an off-by-one.)

    NOT the longest NaN prefix in the frame — ``price_vs_ma50`` z-scores out to 98 and ``ma_200``
    to 199 — but neither is canonical, so neither reaches this dropna. ``macd_hist_z`` clears at 49
    because MACD uses ``ewm(adjust=False)`` (valid from row 0).

    **Why this function exists (T-16, 2026-07-23):** `backtest.warmup_candles` was an unrelated
    literal (30) that had no mechanical relationship to this quantity, so bars 30..77 ran through
    the CRT state machine with NO feature row behind them — a second, silent declaration of one
    number (the F-018/F-056/F-057 split-brain class). `BacktestRunner` now resolves the true value
    here and refuses to start when its configured warmup is shorter.
    """
    cfg = _resolve_feature_pipeline_cfg(cfg)
    ma_fast = int(_require_fp_cfg(cfg, "ma_periods")[0])
    trend_window = int(_require_fp_cfg(cfg, "trend_strength_window"))
    zscore_window = int(_require_fp_cfg(cfg, "zscore_window"))
    return ma_fast + (trend_window - 1) + (zscore_window - 1)


def __getattr__(name: str):
    """PEP 562 lazy module attribute — resolves `SWING_WINDOW` from config on first access.

    Deliberately lazy rather than a module-level assignment: resolving at import would create a
    module-execution-time ``features -> config_layer`` edge, which is precisely the cycle risk
    the deferred imports elsewhere in this file guard against (``config_layer.rr.rr_dataset_builder``
    and ``config_layer.crt_engine_v2`` import ``features.*`` in the other direction).

    Nine modules do ``from features.feature_pipeline import SWING_WINDOW``; PEP 562 keeps that
    import working while making the value CONFIG-DERIVED rather than an independent literal, so
    importers and the pipeline can no longer disagree.
    """
    if name == "SWING_WINDOW":
        return resolve_swing_window()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# Columns subject to rolling z-score normalization (MUST NOT include
# categoricals, RSI, volume_ratio, or placeholder scalars)
NORMALIZE_COLS = [
    "price_vs_ma20",
    "price_vs_ma50",
    "bb_width",
    "trend_strength",
]

# v4.0 MACD split: columns z-scored into a NEW column instead of being overwritten in place.
# v3.0 listed `macd_hist` in NORMALIZE_COLS, so the emitted `macd_hist` was the z-score, not the
# `macd_line - macd_signal` its ontology formula declared (FM-049's note warned about exactly
# this). Both quantities now have their own canonical slot.
NORMALIZE_TO_NEW_COL = {
    "macd_hist_raw": "macd_hist_z",
}


# ─────────────────────────────────────────────────────────────────────────────
# STANDALONE FUNCTIONS (canonical pipeline contract)
# ─────────────────────────────────────────────────────────────────────────────

def build_features(row: "pd.Series") -> dict:
    """
    Compute every canonical feature from a single enriched DataFrame row.

    The row MUST come from a DataFrame that has been processed by
    FeaturePipeline.run() — i.e., all intermediate columns must be present.

    CANONICAL_FEATURES is the SINGLE SOURCE OF TRUTH (48 names under schema v5.0, F-076).
    This function returns EXACTLY those keys — no more, no less.

    Args:
        row: a single pandas Series from the enriched DataFrame

    Returns:
        dict with EXACTLY the CANONICAL_FEATURES keys

    Raises:
        ValueError: if any required column is missing from row
        ValueError: if any computed feature is NaN or infinite
    """
    required_cols = list(CANONICAL_FEATURES)
    missing_cols = [c for c in required_cols if c not in row.index]
    if missing_cols:
        raise ValueError(
            f"build_features: row is missing required columns: {missing_cols}. "
            "Ensure FeaturePipeline.run() has been called on the DataFrame first."
        )

    # Build dict with every canonical feature — exact keys, float values
    features = {col: float(row[col]) for col in CANONICAL_FEATURES}

    # NaN guard — fail fast rather than poisoning the model
    for k, v in features.items():
        if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
            raise ValueError(
                f"build_features: feature '{k}' = {v} is invalid (NaN/inf/None). "
                "Check input data quality or warmup period."
            )

    return features

def build_feature_vector(features: dict) -> list:
    """
    Convert a canonical feature dict to a deterministically-ordered list.

    Order is defined by CANONICAL_FEATURES (imported from features.feature_schema).
    This is the ONLY place where dict → vector conversion happens.

    Args:
        features: canonical feature dict (MUST pass validate_features first)

    Returns:
        list of CANONICAL_FEATURE_DIM floats in canonical order
    """
    return [features[f] for f in CANONICAL_FEATURES]


# ─────────────────────────────────────────────────────────────────────────────
# BATCH PIPELINE CLASS
# ─────────────────────────────────────────────────────────────────────────────

class FeaturePipeline:
    """
    Full feature engineering pipeline for batch DataFrame processing.

    Usage
    -----
    >>> pipeline = FeaturePipeline(df)
    >>> enriched_df, vectors = pipeline.run()
    >>> print(pipeline.monitor.summary())   # drift report after run()

    The enriched DataFrame can then be used row-by-row with build_features().
    A FeatureMonitor is attached automatically and updated with every row
    produced by run() so that drift statistics accumulate across batches when
    the same pipeline instance is reused (e.g. incremental live data ingestion).
    """

    def __init__(
        self,
        df: pd.DataFrame,
        monitor: Optional[FeatureMonitor] = None,
        cfg: Optional[dict] = None,
    ):
        self.df = df.copy()
        # Drift monitor: injected or created fresh (window_size=500 default).
        # Pass an existing monitor to accumulate statistics across multiple run() calls.
        self.monitor: FeatureMonitor = monitor if monitor is not None else FeatureMonitor()
        # Indicator periods: optional injected cfg, else resolved from the active
        # production config's 'feature_pipeline' section (CLAUDE.md Section 6.5
        # exception, 2026-07-18). `cfg=None` means "resolve from canonical config",
        # never "use a hardcoded fallback" -- resolution is strict, no silent defaults.
        self._fp_cfg = _resolve_feature_pipeline_cfg(cfg)
        self._validate_input()

    # ------------------------------------------------------------------
    # VALIDATION
    # ------------------------------------------------------------------
    def _validate_input(self) -> None:
        # Phase 1 — all six OHLCV columns must physically exist. No defaults,
        # no auto-generated volume column.
        require_ohlcv_columns(self.df.columns, source="FeaturePipeline")

        # Coerce numeric columns (unparseable cells become NaN, caught below).
        for col in ["open", "high", "low", "close", "volume"]:
            self.df[col] = pd.to_numeric(self.df[col], errors="coerce")

        # Phase 2 — value integrity: no NaN/non-numeric, volume >= 0, candles
        # high/low-consistent. An all-zero (but numeric) volume column is valid
        # data and is later handled by compute_volume_features()'s proxy.
        validate_ohlcv_frame(self.df, source="FeaturePipeline")

    # ------------------------------------------------------------------
    # PRICE FEATURES
    # ------------------------------------------------------------------
    def compute_price_features(self) -> None:
        df = self.df

        df["prev_close"] = df["close"].shift(1)
        df["delta_close"] = df["close"] - df["prev_close"]

        df["candle_body"] = df["close"] - df["open"]
        df["upper_wick"] = df["high"] - np.maximum(df["open"], df["close"])
        df["lower_wick"] = np.minimum(df["open"], df["close"]) - df["low"]

        df["direction"] = np.where(
            df["close"] > df["open"], 1,
            np.where(df["close"] < df["open"], -1, 0)
        ).astype(np.int8)

        self.df = df

    # ------------------------------------------------------------------
    # VOLUME FEATURES
    # Volume identity split (Phase-1 DUPLICATE_FORMULA_IDENTITY_CLOSURE):
    #   FEAT-VOLUME              — source tick/trade volume (never rewritten)
    #   FEAT-VOLUME_RANGE_PROXY  — high-low price-range proxy (explicit column)
    # Legacy T-003 overwrote `volume` with high-low under the same name; that path
    # is no longer a governed authority (shadow evidence only).
    # ------------------------------------------------------------------
    def compute_volume_features(self) -> None:
        df = self.df

        raw_vol = pd.to_numeric(df["volume"], errors="coerce")
        # Detect FX "dead volume": all zeros or all NaN after numeric coercion
        vol_is_dead = bool(raw_vol.fillna(0.0).max() == 0)

        # Always emit explicit proxy identity (formula: high - low).
        proxy = df["high"] - df["low"]
        df["volume_range_proxy"] = proxy.astype(np.float64)

        if vol_is_dead:
            logger.info(
                "compute_volume_features: volume column is all-zero/NaN — "
                "preserving source volume identity; emitting volume_range_proxy "
                "(high-low) as FEAT-VOLUME_RANGE_PROXY (no same-name substitution)."
            )

        # volume_ratio / volume_spike bind to SOURCE volume only (FEAT-VOLUME family).
        # Window: config feature_pipeline.volume_ma_window (Tier 3 BEHAVIORAL).
        _vol_win = self._fp_cfg["volume_ma_window"]
        df["volume_ma20"] = raw_vol.rolling(_vol_win).mean()
        df["volume_ratio"] = np.where(
            df["volume_ma20"] > 0,
            raw_vol / df["volume_ma20"],
            1.0,
        )
        # Proxy-derived ratio available only under an explicit name (not volume_ratio).
        proxy_ma20 = proxy.rolling(_vol_win).mean()
        df["volume_range_proxy_ratio"] = np.where(
            proxy_ma20 > 0,
            proxy / proxy_ma20,
            1.0,
        )

        # Fixed-threshold seed; promote_volume_spike() later overwrites this with the adaptive
        # percentile version. SAME constant as that method's fallback -> ONE config key
        # (feature_pipeline.volume_spike_fixed_fallback), deliberately not two.
        df["volume_spike"] = (
            df["volume_ratio"] > self._fp_cfg["volume_spike_fixed_fallback"]
        ).astype(np.int8)

        self.df = df

    # ------------------------------------------------------------------
    # INDICATORS  (pure pandas / numpy — no TA-lib)
    # ------------------------------------------------------------------
    def compute_indicators(self) -> None:
        df = self.df
        _cfg = self._fp_cfg
        _rsi_p, _atr_p = _cfg["rsi_period"], _cfg["atr_period"]
        _ma_periods = _cfg["ma_periods"]
        _bb_p, _bb_std_mult = _cfg["bb_period"], _cfg["bb_std"]
        _macd_fast, _macd_slow, _macd_sig = _cfg["macd_fast"], _cfg["macd_slow"], _cfg["macd_signal"]

        # ── Moving Averages ───────────────────────────────────────────
        # ma_200 is NOT a canonical feature and is currently consumed by nothing.
        # RESTORED 2026-07-19 by explicit decision after a brief removal: kept
        # available for future features and to keep the survivorship-budget rationale
        # below coherent. NOTE it does NOT affect warmup drop -- finalize() drops on
        # CANONICAL_FEATURES only, and ma_200 is not one, so its 199-row NaN tail has
        # never contributed to the drop count (measured canonical warmup: 78 rows,
        # identical with or without it).
        df["ma_20"] = df["close"].rolling(_ma_periods[0]).mean()
        df["ma_50"] = df["close"].rolling(_ma_periods[1]).mean()
        df["ma_200"] = df["close"].rolling(_ma_periods[2]).mean()

        # ── RSI ───────────────────────────────────────────────────────
        # RS = avg_gain / avg_loss, RSI = 100 − 100/(1+RS).
        # NOTE (B0/B1 identity clarification 2026-07-12): avg_gain/avg_loss are SIMPLE rolling means
        # (rolling(period).mean()) — this is SMA-smoothed RSI, NOT Wilder's recursive EWMA smoothing.
        # The RS *ratio form* matches Wilder; the *averaging* does not. Authoritative identity:
        # configs/formulas/market_ontology.yaml rolling_indicators.rsi_14 (FM-042, smoothing_method=SMA).
        # Do NOT silently switch to Wilder EWMA — it changes trained-artifact inputs and gate thresholds.
        # Period is config-driven (feature_pipeline.rsi_period, CLAUDE.md Section 6.5 exception
        # 2026-07-18) — the overbought/oversold THRESHOLDS below (70/30) are NOT in that exception's
        # scope and remain hardcoded.
        # Correct range is strictly [0, 100]; clip guards the 1e-9 denominator edge.
        # Prior bug: formula 100*(gain−loss)/(gain+loss) produced [−100, 100] with
        # mean≈0 and std≈52 — confirmed in gaussian_v5_tradenet scaler statistics.
        delta = df["close"].diff()
        gain = delta.clip(lower=0).rolling(_rsi_p).mean()
        loss = (-delta.clip(upper=0)).rolling(_rsi_p).mean()
        rs = gain / (loss + 1e-9)
        df["rsi_14"] = (100.0 - (100.0 / (1.0 + rs))).clip(0.0, 100.0)

        # rsi_state thresholds: config feature_pipeline.rsi_overbought / rsi_oversold.
        # Tier 3 BEHAVIORAL — `rsi_state` is NON-canonical and is not part of FM-042's formula,
        # so tuning these does not redefine a registered identity.
        df["rsi_state"] = np.where(
            df["rsi_14"] > self._fp_cfg["rsi_overbought"], 1,
            np.where(df["rsi_14"] < self._fp_cfg["rsi_oversold"], -1, 0)
        ).astype(np.int8)

        # ── ATR ───────────────────────────────────────────────────────
        # Period is config-driven (feature_pipeline.atr_period).
        tr1 = df["high"] - df["low"]
        tr2 = (df["high"] - df["close"].shift(1)).abs()
        tr3 = (df["low"]  - df["close"].shift(1)).abs()
        df["true_range"] = np.maximum(tr1, np.maximum(tr2, tr3))
        df["atr_14_raw"] = df["true_range"].rolling(_atr_p).mean()
        df["atr_14"] = df["atr_14_raw"]

        # ── Bollinger Bands ──────────────────────────────────────────
        # Period/std multiplier are config-driven (feature_pipeline.bb_period/bb_std).
        bb_ma = df["close"].rolling(_bb_p).mean()
        bb_std = df["close"].rolling(_bb_p).std(ddof=1)
        df["bb_upper"] = bb_ma + _bb_std_mult * bb_std
        df["bb_lower"] = bb_ma - _bb_std_mult * bb_std
        df["bb_width"] = df["bb_upper"] - df["bb_lower"]
        df["bb_position"] = (df["close"] - df["bb_lower"]) / (df["bb_width"] + 1e-9)

        # ── MACD ─────────────────────────────────────────────────────
        # Fast/slow/signal spans are config-driven (feature_pipeline.macd_fast/slow/signal).
        ema_fast_macd = df["close"].ewm(span=_macd_fast, adjust=False).mean()
        ema_slow_macd = df["close"].ewm(span=_macd_slow, adjust=False).mean()
        df["macd_line"] = ema_fast_macd - ema_slow_macd
        df["macd_signal"] = df["macd_line"].ewm(span=_macd_sig, adjust=False).mean()
        df["macd_hist_raw"] = df["macd_line"] - df["macd_signal"]   # FM-049 (v4.0: raw, not overwritten)

        self.df = df

    # ------------------------------------------------------------------
    # TREND FEATURES
    # ------------------------------------------------------------------
    def compute_trend_features(self) -> None:
        df = self.df
        # Window is config-driven (feature_pipeline.trend_strength_window).
        _trend_window = self._fp_cfg["trend_strength_window"]

        df["price_vs_ma20"] = df["close"] - df["ma_20"]
        df["price_vs_ma50"] = df["close"] - df["ma_50"]
        df["ma_slope_20"] = df["ma_20"].diff()
        df["trend_strength"] = df["ma_slope_20"].rolling(_trend_window).mean()

        self.df = df

    # ------------------------------------------------------------------
    # VOLATILITY REGIME
    # ------------------------------------------------------------------
    def compute_volatility_regime(self) -> None:
        """Emit three distinct volatility-rank identities (Phase-1 + FC1-D).

        Production vector column ``volatility_regime`` binds to
        **ROLLING_CAUSAL** ATR percentile terciles (N=200) — FC1-D (2026-07-11),
        per FC-0.5 adjudication (``SEPARATE_LOCAL_VOLATILITY_CONTEXT_FEATURE``).
        Semantic: local ATR-percentile context, **not** latent Regime Detection.

        GLOBAL_BATCH rank remains on ``volatility_regime_global_batch`` only
        (research/legacy; non-PIT full-frame rank). Expanding remains a distinct
        causal column. Env ``TRUST_VOLREGIME_CAUSAL`` may dual-emit research_view
        but must NOT mutate production or identity columns.
        """
        df = self.df
        atr = df["atr_14"]
        # TUNABLE STRUCTURAL — config-driven, but changing these redefines FM-050; requires
        # ontology formula sync + artifact re-certification. (Was the FC-0.5 adjudicated N=200.)
        _ROLL_N = self._fp_cfg["volatility_percentile_window"]
        _terc_lo = self._fp_cfg["volatility_tercile_low"]
        _terc_hi = self._fp_cfg["volatility_tercile_high"]

        def _tercile(atr_pct: pd.Series) -> pd.Series:
            return np.select(
                [atr_pct < _terc_lo, atr_pct < _terc_hi],
                [0, 1],
                default=2,
            ).astype(np.int8)

        # GLOBAL_BATCH — research/legacy only (non-PIT full-frame rank)
        global_pct = atr.rank(pct=True, method="average")
        df["volatility_regime_global_batch"] = _tercile(global_pct)

        # EXPANDING_CAUSAL — distinct identity (long-memory; not production)
        expand_pct = atr.expanding(min_periods=1).rank(pct=True)
        df["volatility_regime_expanding_causal"] = _tercile(expand_pct)

        # ROLLING_CAUSAL — production bind (FC1-D)
        roll_pct = atr.rolling(_ROLL_N, min_periods=1).rank(pct=True)
        df["volatility_regime_rolling_causal"] = _tercile(roll_pct)
        df["volatility_regime"] = df["volatility_regime_rolling_causal"]

        # Research convenience: env may *select which column to copy* into a
        # shadow view, but must not rewrite production or identity columns.
        import os as _os
        _vr_mode = _os.environ.get("TRUST_VOLREGIME_CAUSAL", "").strip().lower()
        if _vr_mode == "expanding":
            df["volatility_regime_research_view"] = df["volatility_regime_expanding_causal"]
        elif _vr_mode in ("rolling", "global", "global_batch"):
            # rolling is already production; global is legacy view
            if _vr_mode in ("global", "global_batch"):
                df["volatility_regime_research_view"] = df["volatility_regime_global_batch"]
            else:
                df["volatility_regime_research_view"] = df["volatility_regime_rolling_causal"]
        elif _vr_mode:
            logger.warning(
                "compute_volatility_regime: unknown TRUST_VOLREGIME_CAUSAL=%r — ignored",
                _vr_mode,
            )

        self.df = df

    # ------------------------------------------------------------------
    # CONTEXT FEATURES
    # ------------------------------------------------------------------
    def compute_context(self) -> None:
        df = self.df

        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["day_of_week"] = df["timestamp"].dt.dayofweek.astype(np.int8)

        # F-066 (2026-08-01): which clock feeds hour_of_day/session (FM-052). "broker_local"
        # (legacy default, byte-identical) uses `timestamp` as-is. "utc_corrected" derives from
        # the true-UTC conversion in features/broker_clock.py -- see that module's docstring for
        # the evidence. The raw `timestamp` COLUMN ITSELF IS NEVER MUTATED either way: OHLCV
        # identity/hashing must stay byte-identical regardless of this selector.
        _session_ts_basis = self._fp_cfg["session_timestamp_basis"]
        if _session_ts_basis == "utc_corrected":
            from features import broker_clock as _bc
            session_ts = _bc.mt5_server_to_utc(df["timestamp"])
        else:
            session_ts = df["timestamp"]
        df["hour_of_day"] = session_ts.dt.hour.astype(np.int8)

        # FM-052 session encoding — v4.0 window model {ASIA, LONDON, NEWYORK, OVERLAP, CLOSED}.
        # The math is NOT inlined here: features/session_classifier.py is the single owner, and it
        # also owns the (deliberately separate) session FILTER vocabulary. Inlining it here is how
        # the v3.0 encoding drifted away from feature_schema.SESSION_MAP by a permutation.
        from features import session_classifier as _sc
        _sc.set_series_config(self._fp_cfg)
        try:
            df["session"] = _sc.classify_session_feature_series(df["hour_of_day"])
        finally:
            _sc.set_series_config(None)

        self.df = df

    # ------------------------------------------------------------------
    # STRUCTURE + LIQUIDITY  (swing detection, BOS, trap logic)
    # ------------------------------------------------------------------
    def compute_structure_liquidity(self) -> None:
        """Structure + liquidity with explicit swing identity split (FC1-A).

        Pivot *math* is unchanged (local max/min over ``w=2·k+1``, center=True).
        **Publication** for production columns is CAUSAL DELAYED: flags and last
        swing prices are the centered pivot shifted by ``k=SWING_WINDOW`` so bar
        ``t`` only uses information through ``t`` (available_at = t+k relative
        to the pivot event). Centered-batch identities remain on explicit
        ``*_centered_batch`` columns for research/legacy. The full structure
        graph (HH/LL/BOS/sweep/liquidity/retest secondaries) binds only to the
        causal last-swing prices — no hybrid centered→causal graph.

        Env ``TRUST_SWING_CAUSAL`` must NOT mutate either identity; it may only
        dual-emit research_view columns.
        """
        df = self.df
        # TUNABLE STRUCTURAL — from this instance's config, NOT the module attribute, so an
        # injected cfg is honoured. k sets the pivot width (2k+1) AND the FC1-A causal delay.
        _s = self._fp_cfg["swing_window"]
        w = 2 * _s + 1

        # ── CENTERED_BATCH swing (research / legacy identity; may leak) ─
        roll_high = df["high"].rolling(w, center=True, min_periods=w).max()
        roll_low  = df["low"].rolling(w, center=True, min_periods=w).min()

        swing_high_centered = (df["high"] == roll_high).astype(np.int8)
        swing_low_centered  = (df["low"]  == roll_low).astype(np.int8)

        if swing_high_centered.equals(swing_low_centered):
            raise AssertionError(
                "compute_structure_liquidity: swing_high and swing_low are "
                "bit-for-bit identical — column reference bug detected."
            )

        df["swing_high_centered_batch"] = swing_high_centered
        df["swing_low_centered_batch"] = swing_low_centered

        last_high_centered = df["high"].where(swing_high_centered == 1).ffill()
        last_low_centered = df["low"].where(swing_low_centered == 1).ffill()
        df["last_swing_high_price_centered_batch"] = last_high_centered
        df["last_swing_low_price_centered_batch"] = last_low_centered

        # ── CAUSAL_CONFIRMED swing (production publication; shift by k) ─
        swing_high_causal = swing_high_centered.shift(_s).fillna(0).astype(np.int8)
        swing_low_causal = swing_low_centered.shift(_s).fillna(0).astype(np.int8)
        last_high_causal = last_high_centered.shift(_s)
        last_low_causal = last_low_centered.shift(_s)

        df["swing_high_causal_confirmed"] = swing_high_causal
        df["swing_low_causal_confirmed"] = swing_low_causal
        df["last_swing_high_price_causal"] = last_high_causal
        df["last_swing_low_price_causal"] = last_low_causal

        # Production vector columns → CAUSAL delayed publication (FC1-A)
        df["swing_high"] = swing_high_causal
        df["swing_low"] = swing_low_causal
        df["last_swing_high_price"] = last_high_causal
        df["last_swing_low_price"] = last_low_causal

        # Research dual-emit only — never mutate production or centered_batch.
        import os as _os
        if _os.environ.get("TRUST_SWING_CAUSAL") == "1":
            df["swing_high_research_view"] = swing_high_causal
            df["swing_low_research_view"] = swing_low_causal

        # Structure graph: causal refs only (coherent closure; no hybrid)
        ref_high = df["last_swing_high_price"].shift(1)
        ref_low  = df["last_swing_low_price"].shift(1)

        # Bullish structure: current HIGH exceeds previous swing high
        df["higher_high"] = (df["high"] > ref_high).astype(np.int8)
        # Bearish structure: current LOW undercuts previous swing low — must use LOW/ref_low
        df["lower_low"]   = (df["low"]  < ref_low).astype(np.int8)

        # Guard against copy-paste regression
        if df["higher_high"].equals(df["lower_low"]):
            raise AssertionError(
                "compute_structure_liquidity: higher_high and lower_low are "
                "bit-for-bit identical — column reference bug detected."
            )

        df["break_of_structure"] = np.where(
            df["close"] > ref_high,  1,
            np.where(df["close"] < ref_low, -1, 0)
        ).astype(np.int8)

        sweep_high = (df["high"] > ref_high) & (df["close"] <= ref_high)
        sweep_low  = (df["low"]  < ref_low)  & (df["close"] >= ref_low)

        df["liquidity_sweep"] = np.where(
            sweep_high,  1,
            np.where(sweep_low, -1, 0)
        ).astype(np.int8)

        self.df = df

    # ------------------------------------------------------------------
    # NORMALIZATION  (rolling z-score, 50-bar window)
    # ------------------------------------------------------------------
    def compute_normalization(self) -> None:
        df = self.df
        for col in NORMALIZE_COLS:
            if col not in df.columns:
                raise ValueError(
                    f"compute_normalization: column '{col}' not found. "
                    "Ensure indicators and trend features are computed first."
                )
            # TUNABLE STRUCTURAL — config-driven, but this window is written into FM-049's
            # formula (macd_hist's emitted value is the z-scored one) and it is what sets the
            # ~78-row canonical warmup. Changing it moves BOTH (see T-5: the fixed
            # _warmup_budget=300 does not track this value).
            _z_win = self._fp_cfg["zscore_window"]
            rolling_mean = df[col].rolling(_z_win).mean()
            rolling_std  = df[col].rolling(_z_win).std(ddof=1)
            df[col] = (df[col] - rolling_mean) / (rolling_std + 1e-9)

        # v4.0: z-score into a SEPARATE column so the source keeps its declared meaning.
        _z_win = self._fp_cfg["zscore_window"]
        for src_col, dst_col in NORMALIZE_TO_NEW_COL.items():
            if src_col not in df.columns:
                raise ValueError(
                    f"compute_normalization: column '{src_col}' not found. "
                    "Ensure indicators and trend features are computed first."
                )
            rolling_mean = df[src_col].rolling(_z_win).mean()
            rolling_std  = df[src_col].rolling(_z_win).std(ddof=1)
            df[dst_col] = (df[src_col] - rolling_mean) / (rolling_std + 1e-9)
        self.df = df

    # ------------------------------------------------------------------
    # CANONICAL FEATURE COMPUTATION
    # ------------------------------------------------------------------

    def compute_canonical_price_features(self) -> None:
        """Compute body_ratio, candle_range, body_size, price_position from OHLC.

        Canonical definitions live in src/features/candle_math.py (body_size,
        candle_range, body_ratio). These vectorized numpy forms MUST equal the scalar
        primitives — enforced by tests/test_candle_math.py (parity battery).

        v4.0: the column formerly named `wick_size` is now `candle_range`. Pure rename, zero math
        change — it always held `high - low`, never a wick magnitude (those are upper_wick /
        lower_wick). The ontology already declared FM-002 `candle_range` with
        `misnomer_alias: wick_size`; the vector now agrees with the ontology.
        """
        df = self.df

        df["body_size"] = (df["close"] - df["open"]).abs()         # == candle_math.body_size
        df["candle_range"] = df["high"] - df["low"]                 # == candle_math.candle_range

        df["body_ratio"] = np.where(                               # == candle_math.body_ratio
            df["candle_range"] > 0,
            df["body_size"] / df["candle_range"],
            0.0
        ).astype(np.float32)

        df["price_position"] = np.where(
            df["candle_range"] > 0,
            (df["close"] - df["low"]) / df["candle_range"],
            0.5
        ).astype(np.float32)

    def compute_canonical_volatility_features(self) -> None:
        """Compute atr, range_size, volatility_ratio."""
        df = self.df

        df["atr"] = np.where(
            df["close"] > 0,
            df["atr_14_raw"] / df["close"],
            0.0
        ).astype(np.float32)

        # Window: config feature_pipeline.range_size_window (Tier 3 — `range_size` is
        # non-canonical, no FM id).
        _rng_win = self._fp_cfg["range_size_window"]
        range_high = df["high"].rolling(_rng_win).max()
        range_low = df["low"].rolling(_rng_win).min()
        df["range_size"] = np.where(
            df["close"] > 0,
            (range_high - range_low) / df["close"],
            0.0
        ).astype(np.float32)

        df["volatility_ratio"] = np.where(
            (df["atr"] > 0) & (df["close"] > 0),
            (df["high"] - df["low"]) / (df["atr"] * df["close"]),
            1.0
        ).astype(np.float32)

    def compute_canonical_ema_features(self) -> None:
        """Compute ema_fast, ema_slow, ema_spread, momentum_score.

        Spans are config-driven (feature_pipeline.ema_fast_span/ema_slow_span,
        CLAUDE.md Section 6.5 exception 2026-07-18). NOTE: unrelated to
        crt_engine.ema_fast/ema_slow (a different EMA pair, soft-confirmation logic,
        default 2/5) -- same bare names, different modules, do not conflate.

        `ema_spread` / `momentum_score` emit ONE of two registered identities, selected by
        `feature_pipeline.normalization_basis` (2026-07-22, program
        FM-030-031-DIMENSIONAL-MIX-MIGRATION):

          atr_relative (DEFAULT)  FM-022 / FM-023 -- numerator / `atr`. `atr` is close-relative
                                  (atr_14_raw/close), so an ABSOLUTE-price numerator over it
                                  scales with price level. This arm is the pre-2026-07-22
                                  expression verbatim; the freeze-pin vector SHA is its proof.
          atr_absolute            FM-030 / FM-031 -- numerator / (`atr` * `close`), i.e.
                                  divided by absolute-price ATR. Scale-invariant. Identical to
                                  the legacy arm divided by `close`.

        Scalar equivalents: derived_math.ema_spread / momentum_score (legacy) and
        derived_math.ema_spread_atr / momentum_score_atr (corrected). Column NAMES and the
        canonical vector (39-dim, schema v4.0) are the same under either basis -- this selects
        the math, not the schema.
        """
        df = self.df
        _ema_fast_span = self._fp_cfg["ema_fast_span"]
        _ema_slow_span = self._fp_cfg["ema_slow_span"]
        _basis = self._fp_cfg["normalization_basis"]

        df["ema_fast"] = df["close"].ewm(span=_ema_fast_span, adjust=False).mean().astype(np.float32)
        df["ema_slow"] = df["close"].ewm(span=_ema_slow_span, adjust=False).mean().astype(np.float32)

        # Use np.nan (not 0.0) when the denominator is unavailable so finalize() drops the
        # warmup rows instead of silently injecting 0.0 into training samples. Both arms share
        # this discipline, so warm-up drop semantics are basis-independent.
        if _basis == "atr_relative":
            _denom = df["atr"]
            _valid = df["atr"] > 0
        else:  # "atr_absolute" -- validated in _resolve_feature_pipeline_cfg
            _denom = df["atr"] * df["close"]
            _valid = (df["atr"] > 0) & (df["close"] > 0)

        df["ema_spread"] = np.where(
            _valid,
            (df["ema_fast"] - df["ema_slow"]) / _denom,
            np.nan
        ).astype(np.float32)

        df["momentum_score"] = np.where(
            _valid,
            df["close"].diff() / _denom,
            np.nan
        ).astype(np.float32)

    def compute_canonical_trend_features(self) -> None:
        """Compute trend_bias from EMA fast/slow state."""
        df = self.df
        df["trend_bias"] = np.where(
            df["ema_fast"] > df["ema_slow"], 1,
            np.where(df["ema_fast"] < df["ema_slow"], -1, 0)
        ).astype(np.float32)

    def compute_canonical_structure_features(self) -> None:
        """Compute sweep_detected, displacement_flag, retest_flag, double_sweep."""
        df = self.df

        df["sweep_detected"] = (df["liquidity_sweep"] != 0).astype(np.int8)
        # Trap-first displacement marker: strong candle body vs total wick/range.
        # Multiplier: config feature_pipeline.displacement_strong_body_mult (Tier 3 —
        # `displacement_flag` is non-canonical, no FM id).
        strong_body = df["body_size"] > (
            df["candle_range"] * self._fp_cfg["displacement_strong_body_mult"]
        )
        df["displacement_flag"] = np.where(
            strong_body & (df["atr"] > 0),
            1,
            0,
        ).astype(np.int8)

        # Retest: after a sweep, price returns close to fast EMA within ATR-based band.
        # Rolling window so retests up to N bars after the sweep are captured (was a 1-bar
        # .shift(1) which forced candles_since_retest=1 always).
        # Config: feature_pipeline.retest_lookback / retest_atr_band_mult (Tier 3 —
        # `retest_flag` is an internal column, no FM id).
        _RETEST_LOOKBACK = self._fp_cfg["retest_lookback"]
        recent_sweep = (
            (df["liquidity_sweep"] != 0)
            .rolling(window=_RETEST_LOOKBACK, min_periods=1)
            .max()
            .astype(bool)
        )
        near_fast_ema = (df["close"] - df["ema_fast"]).abs() <= (
            self._fp_cfg["retest_atr_band_mult"] * df["atr"] * df["close"]
        )
        df["retest_flag"] = (recent_sweep & near_fast_ema).astype(np.int8)

        # Double sweep: both sweep directions seen in a short recent window.
        # Config: feature_pipeline.double_sweep_window (Tier 3 — `double_sweep` is unregistered).
        # T-7 CLOSED (2026-07-19): the LIVE path (core/feature_store.py ->
        # causal_structure.causal_structure_at_bar) now resolves the same key through
        # resolve_double_sweep_window() instead of a signature literal, so batch and live are a
        # single source. Parity floor: tests/test_fc1a_swing_causal.py.
        window = self._fp_cfg["double_sweep_window"]
        seen_up = (
            (df["liquidity_sweep"] > 0)
            .rolling(window=window, min_periods=1)
            .max()
            .astype(bool)
        )
        seen_down = (
            (df["liquidity_sweep"] < 0)
            .rolling(window=window, min_periods=1)
            .max()
            .astype(bool)
        )
        df["double_sweep"] = (seen_up & seen_down).astype(np.int8)

    def compute_canonical_temporal_features(self) -> None:
        """Compute candles_since_retest, retest_depth, disp_strength."""
        df = self.df

        # np.nan fallbacks — finalize() drops these rows; 0.0 would silently
        # inject invalid samples during the ATR warmup period.
        df["disp_strength"] = np.where(
            (df["atr"] > 0) & (df["close"] > 0),
            df["body_size"] / (df["atr"] * df["close"]),
            np.nan,
        ).astype(np.float32)
        # TUNABLE STRUCTURAL — these bounds ARE part of FM-020's registered formula
        # ("clip(body_size / (atr * close), 0.0, 3.0)"); changing them redefines the identity.
        df["disp_strength"] = df["disp_strength"].clip(
            lower=self._fp_cfg["disp_strength_clip_low"],
            upper=self._fp_cfg["disp_strength_clip_high"],
        ).astype(np.float32)

        # retest_depth is only defined when retest_flag == 1; on every other bar
        # the feature is semantically "no retest", which we encode as 0.0 (NOT NaN).
        # NaN would propagate into finalize()'s dropna(subset=CANONICAL_FEATURES)
        # and silently delete ~52% of bars — breaking the timestamp → row-index map
        # the backtest loop uses (see backtest_v2.py:1500-1530). ATR-warmup rows are
        # still cleanly dropped via the NaN fallbacks in disp_strength / ema_spread
        # / momentum_score, so no invalid warm-up samples leak through.
        df["retest_depth"] = np.where(
            (df["retest_flag"] == 1) & (df["atr"] > 0) & (df["close"] > 0),
            (df["close"] - df["ema_fast"]).abs() / (df["atr"] * df["close"]),
            0.0,
        ).astype(np.float32)
        # TUNABLE STRUCTURAL — bounds are part of FM-021's registered formula.
        df["retest_depth"] = df["retest_depth"].clip(
            lower=self._fp_cfg["retest_depth_clip_low"],
            upper=self._fp_cfg["retest_depth_clip_high"],
        ).astype(np.float32)

        # Count bars since the last liquidity sweep (the event that SET UP the
        # retest), not since the retest_flag itself.  Previously this used
        # retest_flag.cumsum(), which made cumcount()=0 at every retest candle
        # (the retest_flag candle IS the first candle of its group) — giving
        # zero variance in training data.  Grouping by sweep events instead
        # yields N=2–5 at a typical retest candle, producing a meaningful signal.
        # Guard: `liquidity_sweep` may be absent in minimal test DataFrames or
        # partial pipeline runs; fall back to retest_flag grouping in that case.
        if "liquidity_sweep" in df.columns:
            sweep_groups = (df["liquidity_sweep"] != 0).astype(int).cumsum()
        else:
            sweep_groups = df["retest_flag"].eq(1).cumsum()
        bars_since_sweep = df.groupby(sweep_groups).cumcount()
        df["candles_since_retest"] = np.where(
            sweep_groups > 0,
            bars_since_sweep,
            0,
        ).astype(np.int16)

    def compute_liquidity_distance(self) -> None:
        """
        Compute ATR-normalised distance to nearest liquidity level.

        No lookahead: all reference levels use .shift(1) so they reflect
        the state BEFORE the current bar opens.

        Populates:
          liquidity_distance       — abs(close - nearest_level) / (atr * close);
                                     NaN when atr=0 or no level available
          liquidity_pressure_score — exp(-0.5 * liquidity_distance), clipped [0, 1];
                                     higher = price is closer to a sweep zone

        Live safety note (FC1-A):
          Production last_swing_*_price are causal-delayed (available_at=t+k).
          This method shifts them again by 1 so refs are pre-open state. Live
          FeatureStore re-derives the same causal structure from OHLCV history.
        """
        df = self.df

        # Reference levels (all trailing — no lookahead)
        ref_high = df["last_swing_high_price"].shift(1)
        ref_low  = df["last_swing_low_price"].shift(1)

        # Last BOS level: carry forward the price level at which BOS occurred.
        bos_level = pd.Series(np.nan, index=df.index)
        bos_bullish = df["break_of_structure"] == 1
        bos_bearish = df["break_of_structure"] == -1
        bos_level.loc[bos_bullish] = ref_high.loc[bos_bullish]
        bos_level.loc[bos_bearish] = ref_low.loc[bos_bearish]
        bos_level = bos_level.ffill()

        # ATR in absolute price units (atr column is close-relative; multiply back).
        # Guard: atr_safe is NaN when atr is 0 or NaN — produces NaN distance.
        atr_abs  = df["atr"] * df["close"]
        atr_safe = atr_abs.where(atr_abs > 0, np.nan)

        # Candidate distances (non-negative, ATR-normalised)
        dist_high = (df["close"] - ref_high).abs() / atr_safe
        dist_low  = (df["close"] - ref_low).abs()  / atr_safe
        dist_bos  = (df["close"] - bos_level).abs() / atr_safe

        # Nearest of the three candidates
        nearest = pd.concat([dist_high, dist_low, dist_bos], axis=1).min(axis=1)
        df["liquidity_distance"] = nearest.clip(lower=0.0).astype(np.float32)

        # Pressure score: exp(decay × distance) → high score when price near liquidity.
        # TUNABLE STRUCTURAL — the decay coefficient and the NaN sentinel are both written into
        # FM-026's registered formula ("clip(exp(-0.5 * liquidity_distance), 0.0, 1.0); nan
        # distance -> treated as 10.0"); changing either redefines the identity.
        df["liquidity_pressure_score"] = (
            np.exp(
                self._fp_cfg["liquidity_decay_coeff"]
                * df["liquidity_distance"].fillna(self._fp_cfg["liquidity_nan_sentinel"])
            )
        ).clip(0.0, 1.0).astype(np.float32)

        self.df = df

    def promote_volume_spike(self) -> None:
        """
        Replace fixed-threshold volume_spike with adaptive 75th-percentile threshold.

        Rationale: fixed 1.5× threshold is not forex-safe across instruments with
        different volume characteristics. Adaptive percentile adjusts to the
        instrument's own distribution.

        Overwrites the 'volume_spike' column (computed earlier in
        compute_volume_features() with a fixed threshold).

        Falls back to fixed 1.5× threshold when rolling window has < 20 samples.
        No lookahead: rolling window uses trailing only (no center=True).
        """
        df = self.df

        # Tier 3 BEHAVIORAL — `volume_spike` has no FM id. Note _FIXED_FALLBACK reads the SAME
        # config key as the seed threshold in compute_volume_features(); one concept, one key.
        _ADAPTIVE_WINDOW     = self._fp_cfg["volume_spike_adaptive_window"]
        _FIXED_FALLBACK      = self._fp_cfg["volume_spike_fixed_fallback"]
        _MIN_SAMPLES         = self._fp_cfg["volume_spike_min_samples"]
        _PERCENTILE          = self._fp_cfg["volume_spike_percentile"]

        vol_ratio = df["volume_ratio"]
        rolling_thresh = vol_ratio.rolling(
            window=_ADAPTIVE_WINDOW, min_periods=_MIN_SAMPLES
        ).quantile(_PERCENTILE / 100.0)

        # Where rolling threshold is available use adaptive; else use fixed fallback
        threshold = rolling_thresh.where(rolling_thresh.notna(), _FIXED_FALLBACK)
        df["volume_spike"] = (vol_ratio > threshold).astype(np.int8)

        self.df = df

    def compute_canonical_session(self) -> None:
        """Ensure session is int-encoded properly."""
        df = self.df
        df["session"] = df["session"].astype(np.int8)

    def compute_smc_features(self) -> None:
        """CH-htfcrt-parent-candle-smc-v1 (2026-08-15): the 9 SMC (smart-money-concepts)
        primitives — order_block_distance, fvg_distance, breaker_distance,
        mitigation_block_distance, pdh_distance, pdl_distance, eqh_distance, eql_distance,
        change_of_character.

        UNLIKE every other `compute_*` method in this class, this is NOT vectorized: the
        underlying `features.smc.*` functions are pure, window-based `Candle` scanners
        (deliberately isolated from pandas/config, per `research.weekly_sweep`'s reimplement-
        rather-than-couple precedent — see `features/smc/_geometry.py`'s LAYERING note). This
        method runs ONE Python loop building a trailing `Candle` window (bounded by
        `smc_max_window`, oldest candles dropped) plus a parallel D1 `ParentCandleBuilder` for
        PDH/PDL, calling the already-unit-tested `features.smc` functions at each closed bar.
        Known cost: O(n * smc_max_window * swing_window) — a one-time feature-build cost, not
        a per-backtest cost (pipeline output is typically cached). A vectorized reimplementation
        is a legitimate future optimization but was deliberately NOT attempted here: reusing the
        already-adversarially-tested pure functions verbatim is safer than a second, unverified
        vectorized reimplementation of the same OB/FVG/breaker/mitigation geometry.

        `change_of_character` is the one exception — it is a pure per-row algebraic combination
        of the ALREADY-COMPUTED `break_of_structure`/`trend_bias` columns (see
        `features.smc.choch`'s module doc on why this does not reopen the ontology's BOS/CHoCH
        detection-state-machine exclusion) and is vectorized normally alongside the loop.

        No lookahead: the Candle window and D1 builder are built incrementally in chronological
        row order, so row i only ever sees candles/D1-closes from rows < i (`ParentCandleBuilder`
        additionally never exposes an in-progress D1 period — see its own no-lookahead tests).
        """
        from config_layer.crt_engine_v2 import Candle
        from features.parent_candle import ParentCandleBuilder
        from features.smc.breaker import breaker_distance
        from features.smc.choch import change_of_character
        from features.smc.fvg import fvg_distance
        from features.smc.levels import eqh_eql_distance, pdh_pdl_distance
        from features.smc.mitigation import mitigation_block_distance
        from features.smc.order_block import order_block_distance

        df = self.df
        n = len(df)
        k = resolve_swing_window(self._fp_cfg)
        max_window = int(self._fp_cfg["smc_max_window"])

        opens = df["open"].to_numpy()
        highs = df["high"].to_numpy()
        lows = df["low"].to_numpy()
        closes = df["close"].to_numpy()
        # atr column is close-relative (normalization_basis governs this elsewhere); the SMC
        # primitives need ABSOLUTE (price-unit) ATR, same F-072/FM-074 atr_absolute pattern
        # `compute_liquidity_distance` already uses just above.
        atr_abs = (df["atr"] * df["close"]).to_numpy()
        timestamps = df["timestamp"].to_numpy()

        ob_d = np.zeros(n, dtype=np.float32)
        fvg_d = np.zeros(n, dtype=np.float32)
        brk_d = np.zeros(n, dtype=np.float32)
        mit_d = np.zeros(n, dtype=np.float32)
        pdh_d = np.zeros(n, dtype=np.float32)
        pdl_d = np.zeros(n, dtype=np.float32)
        eqh_d = np.zeros(n, dtype=np.float32)
        eql_d = np.zeros(n, dtype=np.float32)

        window: list = []
        d1_builder = ParentCandleBuilder("D1", keep=2)

        for i in range(n):
            ts = pd.Timestamp(timestamps[i]).to_pydatetime()
            c = Candle(
                timestamp=ts, open=float(opens[i]), high=float(highs[i]), low=float(lows[i]),
                close=float(closes[i]), volume=0.0, index=i,
            )
            window.append(c)
            if len(window) > max_window:
                window = window[-max_window:]
            d1_builder.push(c)

            atr_i = float(atr_abs[i]) if not np.isnan(atr_abs[i]) else 0.0

            ob_d[i] = order_block_distance(window, k, atr_i)
            fvg_d[i] = fvg_distance(window, atr_i)
            brk_d[i] = breaker_distance(window, k, atr_i)
            mit_d[i] = mitigation_block_distance(window, k, atr_i)
            pdh, pdl = pdh_pdl_distance(float(closes[i]), d1_builder.parent_history, atr_i)
            pdh_d[i] = pdh
            pdl_d[i] = pdl
            eqh, eql = eqh_eql_distance(window, k, atr_i)
            eqh_d[i] = eqh
            eql_d[i] = eql

        df["order_block_distance"] = ob_d
        df["fvg_distance"] = fvg_d
        df["breaker_distance"] = brk_d
        df["mitigation_block_distance"] = mit_d
        df["pdh_distance"] = pdh_d
        df["pdl_distance"] = pdl_d
        df["eqh_distance"] = eqh_d
        df["eql_distance"] = eql_d

        # change_of_character: vectorized, pure algebra over already-computed columns.
        df["change_of_character"] = [
            change_of_character(float(b), float(t))
            for b, t in zip(df["break_of_structure"].to_numpy(), df["trend_bias"].to_numpy())
        ]
        df["change_of_character"] = df["change_of_character"].astype(np.float32)

        self.df = df

    # ------------------------------------------------------------------
    # FINAL CLEANUP
    # ------------------------------------------------------------------
    def finalize(self) -> pd.DataFrame:
        n_before = len(self.df)
        df = self.df
        df = df.replace([np.inf, -np.inf], np.nan)
        df = df.dropna(subset=list(CANONICAL_FEATURES)).reset_index(drop=True)
        n_after    = len(df)
        drop_count = n_before - n_after
        drop_pct   = 100.0 * drop_count / max(n_before, 1)

        # Structured telemetry — trendable; catches gradual degradation across runs.
        _fp_log = logging.getLogger("FeaturePipeline")
        _fp_log.info(
            "finalize | rows_before=%d rows_after=%d drop=%d drop_pct=%.2f%%",
            n_before, n_after, drop_count, drop_pct,
            extra={
                "event":       "FEATURE_FINALIZE",
                "rows_before": n_before,
                "rows_after":  n_after,
                "drop_count":  drop_count,
                "drop_pct":    round(drop_pct, 2),
            },
        )

        # Survivorship guard (absolute budget, not survival ratio).
        # Ratio permits ~5k silent loss on 100k datasets; absolute budget does not.
        # CORRECTED 2026-07-18: the old rationale here ("ma_200(200) + z-score(50) +
        # swing edges(4) = ~300") was never load-bearing — ma_200 is NOT a canonical
        # column, so its 199-row NaN tail never reached this dropna. MEASURED canonical
        # warmup is 78 rows (rolling(50) z-score stacked on trend_strength/macd_hist),
        # constant across dataset sizes (verified at 3,949 / 47,275 / 50,169 rows).
        # 300 is therefore a deliberately generous ceiling, NOT a derived sum.
        # T-16 (2026-07-23): that measured 78 now has a DERIVED source —
        # `required_warmup_rows()` above computes it from ma_periods[0]/trend_strength_window/
        # zscore_window. This budget still does not track it (it is a generous ceiling by
        # design); the consumer that MUST track it is BacktestRunner's warmup assert.
        # Beyond that, any large drop indicates an unintended NaN in CANONICAL_FEATURES.
        _warmup_budget = 300
        _allowed_drop  = max(_warmup_budget, int(n_before * 0.02))  # 2% OR warmup, whichever larger
        if drop_count > _allowed_drop:
            _fp_log.error(
                "finalize(): drop count %d exceeds allowed budget %d (%.1f%% of input). "
                "Likely unintended NaN in CANONICAL_FEATURES. Check recent feature additions.",
                drop_count, _allowed_drop, drop_pct,
            )

        self.df = df
        return df

    def log_critical_feature_health(self) -> None:
        """Log zero-rate, NaN-rate, and range stats for critical canonical features."""
        df = self.df
        critical = [
            "retest_depth",
            "disp_strength",
            "trend_bias",
            "momentum_score",
            "ema_spread",
            "atr",
            "liquidity_distance",       # v3.0
            "volume_spike",             # v3.0
        ]
        for col in critical:
            if col not in df.columns:
                logger.warning("Feature health check skipped missing column: %s", col)
                continue

            s = pd.to_numeric(df[col], errors="coerce")
            nan_rate = float(s.isna().mean())
            zero_rate = float(s.abs().lt(1e-12).mean())
            logger.info(
                "FeatureHealth %s | zero_rate=%.2f%% nan_rate=%.2f%% min=%.6g max=%.6g mean=%.6g",
                col,
                zero_rate * 100.0,
                nan_rate * 100.0,
                float(s.min(skipna=True)),
                float(s.max(skipna=True)),
                float(s.mean(skipna=True)),
            )

    # ------------------------------------------------------------------
    # BATCH FEATURE VECTOR (DataFrame → numpy array)
    # ------------------------------------------------------------------
    def build_feature_vector(self) -> np.ndarray:
        """
        Build the (N, len(CANONICAL_FEATURES)) feature matrix from the enriched DataFrame
        (48 under schema v5.0, F-076; the docstring no longer hardcodes the dim -- see the v3.0/v4.0
        migration note on CANONICAL_FEATURES in features/feature_schema.py).

        Uses CANONICAL_FEATURES from features.feature_schema — NOT a local list.
        """
        df = self.df

        # Assertion 1: all canonical columns present
        missing = [c for c in CANONICAL_FEATURES if c not in df.columns]
        if missing:
            raise ValueError(
                f"FeaturePipeline.build_feature_vector: missing columns: {missing}"
            )

        vectors = df[list(CANONICAL_FEATURES)].astype(np.float32).values

        # Assertion 2: correct shape
        expected_width = len(CANONICAL_FEATURES)
        if vectors.shape[1] != expected_width:
            raise ValueError(
                f"FeaturePipeline: vector width mismatch — "
                f"expected {expected_width}, got {vectors.shape[1]}"
            )

        # Assertion 3: no NaN
        nan_count = np.isnan(vectors).sum()
        if nan_count > 0:
            raise ValueError(
                f"FeaturePipeline: feature vector contains {nan_count} NaN value(s). "
                "Check warmup period or input data quality."
            )

        return vectors

    # ------------------------------------------------------------------
    # FULL PIPELINE (CANONICAL)
    # ------------------------------------------------------------------
    def run(self) -> tuple:
        """
        Execute the full pipeline in canonical feature order.

        Returns
        -------
        df : pd.DataFrame
            Enriched, NaN-free DataFrame with all len(CANONICAL_FEATURES) canonical features
            (48 under schema v5.0, F-076).
        vectors : np.ndarray, shape (N, len(CANONICAL_FEATURES)), dtype float32
            Feature matrix in canonical CANONICAL_FEATURES order.
        """
        # Base computations (OHLCV + indicators)
        self.compute_price_features()
        self.compute_volume_features()
        self.compute_indicators()
        self.compute_trend_features()
        self.compute_volatility_regime()
        self.compute_context()
        self.compute_structure_liquidity()
        self.compute_normalization()

        # Canonical feature computation (MUST run after base)
        self.compute_canonical_price_features()
        self.compute_canonical_volatility_features()
        self.compute_canonical_ema_features()
        self.compute_canonical_trend_features()
        self.compute_canonical_structure_features()
        self.compute_canonical_temporal_features()
        self.compute_liquidity_distance()     # v3.0: index 35 + 36 (after structure)
        self.promote_volume_spike()           # v3.0: index 37 (adaptive percentile)
        self.compute_canonical_session()
        self.compute_smc_features()           # v5.0: indices 39-47 (9 SMC primitives)

        # Finalize and build vectors
        df = self.finalize()
        self.log_critical_feature_health()
        vectors = self.build_feature_vector()

        # ── FeatureMonitor: update rolling window, log drift summary ─────────
        # Monitor tracks the 3 primary CRT features (retest_depth, body_ratio,
        # disp_strength) that are most predictive of distribution shift.
        _drift_cols = {"retest_depth", "body_ratio", "disp_strength"}
        _available  = _drift_cols.intersection(df.columns)
        if _available == _drift_cols:
            n_drift = 0
            for _, row in df[list(_drift_cols)].iterrows():
                feat = row.to_dict()
                self.monitor.update(feat)
                if self.monitor.detect_drift(feat):
                    n_drift += 1
            if n_drift > 0:
                logger.warning(
                    "FeatureMonitor: %d/%d rows flagged as drift in this batch "
                    "(Z > %.1f on retest_depth/body_ratio/disp_strength).",
                    n_drift, len(df), 2.5,
                )
            else:
                logger.info(
                    "FeatureMonitor: batch clean — 0/%d rows flagged for drift.", len(df)
                )
            logger.debug("FeatureMonitor stats: %s", self.monitor.summary())
        else:
            logger.warning(
                "FeatureMonitor: skipped — missing columns %s.",
                _drift_cols - _available,
            )

        return df, vectors
