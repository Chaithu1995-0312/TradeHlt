"""Fail-closed CRTConfig factory for tests — every field declared, no silent engine fallbacks.

EPIC-84 (user rule 2026-09-28: no defaults, no fallbacks). CRTConfig has NO field defaults any
more, so a test config must declare all 53 fields. ``LEGACY_CODE_VALUES_2026_09_28`` is the
exact set of values the CRTConfig dataclass defaults held until 2026-09-28 (captured
programmatically from ``dataclasses.fields(CRTConfig)`` at 75918f50). Tests that used to rely
on those defaults keep the same inputs, now declared here explicitly instead of hidden in
production code. This is a TEST FIXTURE: production reads only declared configs.
"""
from __future__ import annotations

import dataclasses
from datetime import time

from src.config_layer.state_identity import CRTConfig

# Authority (prod params). FOREX/CRYPTO Overrides are separate and must be passed explicitly.
_AUTHORITY = dict(
    body_ratio_min=0.65,
    atr_multiplier_min=1.0,
    retest_depth_max=0.15,
    expansion_atr_min_distance=0.30,
)

# The 49 former CRTConfig code defaults (see module docstring). Do not edit to "fix" a test:
# pass the field as an override instead.
LEGACY_CODE_VALUES_2026_09_28 = dict(
    atr_period=14,
    atr_buffer_multiplier=3,
    max_sweep_age_candles=20,
    retest_atr_depth_fraction=0.5,
    retest_min_depth_atr_fraction=0.1,
    risk_score_weights=(0.35, 0.25, 0.2, 0.2),
    score_component_weights=(0.35, 0.25, 0.2, 0.2),
    max_displacement_strength=2.0,
    score_decay_lambda=0.05,
    score_threshold=0.45,
    max_spread_pct=0.05,
    atr_min_displacement=1.2,
    confirmation_body_min=0.6,
    sl_atr_buffer=0.2,
    tp1_atr_multiplier=1.0,
    tp2_atr_multiplier=2.0,
    exit_model="intrabar_touch",
    breakout_disp_threshold=1.5,
    tp1_atr_multiplier_breakout=1.5,
    tp1_atr_multiplier_pullback=0.8,
    tp1_atr_multiplier_liq_sweep=1.2,
    tp1_atr_multiplier_reversal=1.0,
    bitnet_main_threshold=0.55,
    use_bitnet=False,
    session_windows={
        "LONDON": (time(7, 0), time(10, 0)),
        "NEWYORK": (time(13, 0), time(16, 0)),
        "ASIA": (time(0, 0), time(3, 0)),
    },
    allowed_sessions=("LONDON", "NEWYORK", "OVERLAP"),
    retrace_reset_pct=0.5,
    extension_reset_fib=1.618,
    news_blackout_minutes=15,
    conf_alpha=0.7,
    conf_beta=0.3,
    conf_weights=(0.35, 0.35, 0.15, 0.15),
    conf_floor=0.2,
    weak_link_weight=0.3,
    ema_fast=2,
    ema_slow=5,
    tier_1_threshold=0.75,
    tier_2_threshold=0.3,
    soft_conf_max_candles=3,
    pending_displacement_ttl_candles=4,
    displacement_origin_kill_enabled=False,
    displacement_origin_kill_precedence="after_resting_fills",
    max_expansion_age_candles=495,
    max_expansion_age_hours=124,
    expansion_age_warn_candles=342,
    shadow_age_penalty_lambda=0.0,
    shadow_age_norm_candles=0,
    shadow_advisory_only=False,
    sizing_bands=[(0.75, 0.01), (0.55, 0.005)],
)


def crt_test_fields(**overrides) -> dict:
    """Every CRTConfig field for a test: legacy values + authority four + overrides."""
    kw = dict(LEGACY_CODE_VALUES_2026_09_28)
    # mutable containers: never share one dict/list object across test configs
    kw["session_windows"] = dict(kw["session_windows"])
    kw["sizing_bands"] = list(kw["sizing_bands"])
    kw.update(_AUTHORITY)
    kw.update(overrides)
    return kw


def crt_config_for_test(**overrides) -> CRTConfig:
    """Build a complete CRTConfig: legacy values + authority four keys; tests may override any field."""
    return CRTConfig(**crt_test_fields(**overrides))


#: The engine behaviour arguments as they ran before EPIC-84 A3a removed their defaults
#: (legacy / v5-baseline values). TEST FIXTURE: production uses CRTEngine.from_production.
ENGINE_TEST_KWARGS = dict(
    htf_reset_exempt_sweep=False,
    sl_anchor="displacement",
    exchange_session_windows=None,
    target_policy="fixed_r",
    trade_ttl_candles=None,
    decider="engine",
)


def crt_engine_for_test(cfg=None, sweep_tracer=None, intrabar_exits=None, **kw):
    """CRTEngine with every behaviour argument declared (overridable)."""
    from config_layer.crt_engine_v2 import CRTEngine

    return CRTEngine(cfg if cfg is not None else crt_config_for_test(), sweep_tracer,
                     intrabar_exits, **{**ENGINE_TEST_KWARGS, **kw})


def execution_engine_for_test(cfg=None, **kw):
    """ExecutionEngine with sl_anchor / target_policy declared (overridable)."""
    from config_layer.crt_engine_v2 import ExecutionEngine

    base = {"sl_anchor": ENGINE_TEST_KWARGS["sl_anchor"],
            "target_policy": ENGINE_TEST_KWARGS["target_policy"]}
    return ExecutionEngine(cfg if cfg is not None else crt_config_for_test(), **{**base, **kw})


def reset_logic_for_test(cfg=None, **kw):
    """ResetLogic with htf_reset_exempt_sweep declared (overridable)."""
    from config_layer.crt_engine_v2 import ResetLogic

    base = {"htf_reset_exempt_sweep": ENGINE_TEST_KWARGS["htf_reset_exempt_sweep"]}
    return ResetLogic(cfg if cfg is not None else crt_config_for_test(), **{**base, **kw})


def retest_cache_for_test(**overrides) -> dict:
    """The six-key RETEST cache a real engine always writes before build_trade (EPIC-84 A3a:
    build_trade refuses a state without it). Zeroed geometry = intent "reversal", exactly what
    the removed `cached_features or {}` fallback produced for these unit tests."""
    cache = {
        "displacement_retrace": 0.0,
        "body_ratio": 0.0,
        "displacement_atr_ratio": 0.0,
        "retest_index": 0,
        "session": "UNKNOWN",
        "double_sweep": False,
        # [EPIC-84 A3b] the three canonical bar features the engine now caches at RETEST
        "sweep_detected": False,
        "candles_since_sweep": 99,
        "momentum_score": 0.0,
    }
    cache.update(overrides)
    return cache


def bar_features_for_test(**overrides) -> dict:
    """A bar's canonical intent features (EPIC-84 A3b: process_candle requires them). The values
    are exactly what the removed engine fallbacks supplied (no sweep, 99 bars since, 0 momentum),
    so tests that never exercised intent keep their inputs; override to exercise it."""
    feats = {"sweep_detected": 0, "candles_since_sweep": 99, "momentum_score": 0.0}
    feats.update(overrides)
    return feats


def _check_complete() -> None:
    names = {f.name for f in dataclasses.fields(CRTConfig)}
    have = set(LEGACY_CODE_VALUES_2026_09_28) | set(_AUTHORITY)
    assert have == names, (sorted(names - have), sorted(have - names))


_check_complete()
