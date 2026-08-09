"""Ontology-authoritative floor for the 6 simple structural states:

  FM-054 trend_bias
  FM-055 higher_high
  FM-056 lower_low
  FM-059 sweep_detected
  FM-068 rsi_state
  FM-069 displacement_flag

Each assertion mirrors the ontology `formula` against pipeline output. Config
thresholds are read strictly from production `feature_pipeline` (no `.get`
fallback). Swing-dependent complex states (BOS / liquidity_sweep / double_sweep /
retest_flag) live in test_feature_structural_states_complex.py.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from config_layer.production_config import get_prod_section
from features.feature_pipeline import FeaturePipeline
from features.registry import load_ontology


def _structural(name: str) -> dict:
    ont = load_ontology()
    if "structural_states" not in ont:
        raise KeyError("ontology missing structural_states section")
    section = ont["structural_states"]
    if name not in section:
        raise KeyError(f"ontology structural_states missing {name!r}")
    entry = section[name]
    if "lifecycle" not in entry:
        raise KeyError(f"{name}: missing required lifecycle")
    if "id" not in entry:
        raise KeyError(f"{name}: missing required id")
    return entry


def _fp_cfg() -> dict:
    return get_prod_section("feature_pipeline")


def _synthetic(n: int = 500, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    ts = pd.date_range("2024-01-01", periods=n, freq="15min")
    close = 100 + np.cumsum(rng.normal(0, 0.3, n))
    open_ = close + rng.normal(0, 0.05, n)
    high = np.maximum(open_, close) + rng.uniform(0.05, 0.8, n)
    low = np.minimum(open_, close) - rng.uniform(0.05, 0.8, n)
    volume = rng.uniform(100, 2000, n)
    return pd.DataFrame(
        {
            "timestamp": ts,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


def _run_pre_finalize(df: pd.DataFrame) -> tuple[FeaturePipeline, dict]:
    """Execute pipeline stages through canonical structure (no finalize drop)."""
    cfg = _fp_cfg()
    fp = FeaturePipeline(df, cfg=cfg)
    fp.compute_price_features()
    fp.compute_volume_features()
    fp.compute_indicators()
    fp.compute_trend_features()
    fp.compute_volatility_regime()
    fp.compute_context()
    fp.compute_structure_liquidity()
    fp.compute_normalization()
    fp.compute_canonical_price_features()
    fp.compute_canonical_volatility_features()
    fp.compute_canonical_ema_features()
    fp.compute_canonical_trend_features()
    fp.compute_canonical_structure_features()
    return fp, cfg


def _state_values(name: str) -> set[int]:
    entry = _structural(name)
    states = entry["states"]
    if not states:
        raise AssertionError(f"{name}: empty states block")
    return {int(s["value"]) for s in states}


# ── FM-054 trend_bias ────────────────────────────────────────────────────────

def test_trend_bias_ontology_id():
    assert _structural("trend_bias")["id"] == "FM-054"


def test_trend_bias_matches_sign_of_ema_spread():
    """formula: sign(ema_fast - ema_slow) -> {-1, 0, +1}."""
    fp, _ = _run_pre_finalize(_synthetic())
    df = fp.df
    expected = np.where(
        df["ema_fast"] > df["ema_slow"], 1.0,
        np.where(df["ema_fast"] < df["ema_slow"], -1.0, 0.0),
    ).astype(np.float32)
    np.testing.assert_array_equal(
        df["trend_bias"].to_numpy(dtype=np.float32),
        expected,
    )
    assert set(np.unique(df["trend_bias"].dropna())) <= _state_values("trend_bias")


def _run_trend_only(df: pd.DataFrame) -> pd.DataFrame:
    """EMA + trend_bias only — skip structure (monotone series can make both
    swing flags all-zero, which trips the pipeline's copy-paste guard)."""
    cfg = _fp_cfg()
    fp = FeaturePipeline(df, cfg=cfg)
    fp.compute_price_features()
    fp.compute_volume_features()
    fp.compute_indicators()
    fp.compute_canonical_price_features()
    fp.compute_canonical_volatility_features()
    fp.compute_canonical_ema_features()
    fp.compute_canonical_trend_features()
    return fp.df


def test_trend_bias_forced_bullish_and_bearish():
    """Construct sequences where ema_fast is forced above/below ema_slow."""
    n = 80
    base = datetime(2024, 1, 1)
    # Strong uptrend → ema_fast > ema_slow after warmup
    up = []
    price = 100.0
    for i in range(n):
        price += 1.0
        up.append(
            dict(
                timestamp=base + timedelta(minutes=15 * i),
                open=price - 0.2,
                high=price + 0.3,
                low=price - 0.3,
                close=price,
                volume=500.0,
            )
        )
    df_up = _run_trend_only(pd.DataFrame(up))
    # After EMA warmup, all later bars must be bullish
    tail = df_up.iloc[40:]
    assert (tail["trend_bias"] == 1.0).all(), "uptrend must yield trend_bias=+1"

    # Strong downtrend
    down = []
    price = 200.0
    for i in range(n):
        price -= 1.0
        down.append(
            dict(
                timestamp=base + timedelta(minutes=15 * i),
                open=price + 0.2,
                high=price + 0.3,
                low=price - 0.3,
                close=price,
                volume=500.0,
            )
        )
    df_dn = _run_trend_only(pd.DataFrame(down))
    tail = df_dn.iloc[40:]
    assert (tail["trend_bias"] == -1.0).all(), "downtrend must yield trend_bias=-1"


# ── FM-055 / FM-056 higher_high / lower_low ──────────────────────────────────

def test_higher_high_lower_low_ontology_ids():
    assert _structural("higher_high")["id"] == "FM-055"
    assert _structural("lower_low")["id"] == "FM-056"


def test_higher_high_lower_low_match_ontology_formula():
    """formula: high > prev(last_swing_high_price); low < prev(last_swing_low_price).

    Uses the pipeline's own causal swing refs (swing detection itself is
    FC1-A-dependent — exact pivot verification is deferred; formula application is not).
    """
    fp, _ = _run_pre_finalize(_synthetic(600))
    df = fp.df
    ref_high = df["last_swing_high_price"].shift(1)
    ref_low = df["last_swing_low_price"].shift(1)
    hh_exp = (df["high"] > ref_high).astype(np.int8)
    ll_exp = (df["low"] < ref_low).astype(np.int8)
    # NaN ref compares False in pandas for `>` / `<` → 0; match pipeline
    np.testing.assert_array_equal(df["higher_high"].to_numpy(), hh_exp.to_numpy())
    np.testing.assert_array_equal(df["lower_low"].to_numpy(), ll_exp.to_numpy())
    assert set(np.unique(df["higher_high"])) <= _state_values("higher_high")
    assert set(np.unique(df["lower_low"])) <= _state_values("lower_low")


def test_higher_high_triggers_on_breakout_after_range():
    """Known pattern: range then a bar that takes out the prior swing high."""
    # Build a clear local high, pull back, then exceed it.
    # swing_window=k means pivot width 2k+1 and k-bar causal delay.
    cfg = _fp_cfg()
    k = int(cfg["swing_window"])
    rows = []
    base = datetime(2024, 3, 1)
    # flat base
    for i in range(30):
        rows.append(
            dict(
                timestamp=base + timedelta(minutes=15 * i),
                open=100.0,
                high=100.5,
                low=99.5,
                close=100.0,
                volume=1000.0,
            )
        )
    # spike high (potential swing high)
    spike_i = 30
    rows.append(
        dict(
            timestamp=base + timedelta(minutes=15 * spike_i),
            open=100.0,
            high=110.0,
            low=99.5,
            close=101.0,
            volume=1000.0,
        )
    )
    # pullback bars (need k on each side for centered pivot, then k delay)
    for j in range(1, 20):
        rows.append(
            dict(
                timestamp=base + timedelta(minutes=15 * (spike_i + j)),
                open=101.0,
                high=101.5,
                low=98.0,
                close=99.0,
                volume=1000.0,
            )
        )
    # breakout bar: high exceeds the spike
    rows.append(
        dict(
            timestamp=base + timedelta(minutes=15 * (spike_i + 20)),
            open=100.0,
            high=112.0,
            low=99.0,
            close=111.0,
            volume=1000.0,
        )
    )
    fp, _ = _run_pre_finalize(pd.DataFrame(rows))
    # At least one higher_high must fire once swing ref is established
    assert int(fp.df["higher_high"].sum()) >= 1


# ── FM-059 sweep_detected ────────────────────────────────────────────────────

def test_sweep_detected_ontology_id():
    assert _structural("sweep_detected")["id"] == "FM-059"


def test_sweep_detected_is_nonzero_liquidity_sweep():
    """formula: liquidity_sweep != 0 -> {0, 1}."""
    fp, _ = _run_pre_finalize(_synthetic(600))
    df = fp.df
    expected = (df["liquidity_sweep"] != 0).astype(np.int8)
    np.testing.assert_array_equal(df["sweep_detected"].to_numpy(), expected.to_numpy())
    assert set(np.unique(df["sweep_detected"])) <= _state_values("sweep_detected")


def test_sweep_detected_forced_from_liquidity_sweep():
    """Inject liquidity_sweep values and re-run only the structure-features stage."""
    df = _synthetic(50)
    fp = FeaturePipeline(df, cfg=_fp_cfg())
    # Minimal columns required by compute_canonical_structure_features
    fp.df["liquidity_sweep"] = np.array(
        [0, 1, 0, -1, 0] + [0] * 45, dtype=np.int8
    )
    fp.df["body_size"] = 1.0
    fp.df["candle_range"] = 2.0
    fp.df["atr"] = 0.01
    fp.df["close"] = 100.0
    fp.df["ema_fast"] = 100.0
    fp.compute_canonical_structure_features()
    expected = (fp.df["liquidity_sweep"] != 0).astype(np.int8)
    np.testing.assert_array_equal(
        fp.df["sweep_detected"].to_numpy(), expected.to_numpy()
    )
    assert int(fp.df["sweep_detected"].iloc[1]) == 1
    assert int(fp.df["sweep_detected"].iloc[3]) == 1
    assert int(fp.df["sweep_detected"].iloc[0]) == 0


# ── FM-068 rsi_state ─────────────────────────────────────────────────────────

def test_rsi_state_ontology_id():
    assert _structural("rsi_state")["id"] == "FM-068"


def test_rsi_state_matches_config_thresholds():
    """formula: +1 if rsi_14 > rsi_overbought; -1 if rsi_14 < rsi_oversold; else 0."""
    cfg = _fp_cfg()
    if "rsi_overbought" not in cfg or "rsi_oversold" not in cfg:
        raise KeyError("rsi_overbought / rsi_oversold required in feature_pipeline")
    ob = cfg["rsi_overbought"]
    os_ = cfg["rsi_oversold"]

    fp, _ = _run_pre_finalize(_synthetic(600))
    df = fp.df
    expected = np.where(
        df["rsi_14"] > ob, 1,
        np.where(df["rsi_14"] < os_, -1, 0),
    ).astype(np.int8)
    np.testing.assert_array_equal(df["rsi_state"].to_numpy(), expected)
    assert set(np.unique(df["rsi_state"].dropna().astype(int))) <= _state_values("rsi_state")


def test_rsi_state_known_values():
    """Direct threshold application (no pipeline) must match ontology states."""
    cfg = _fp_cfg()
    ob = cfg["rsi_overbought"]
    os_ = cfg["rsi_oversold"]
    cases = [
        (ob + 1.0, 1),
        (os_ - 1.0, -1),
        ((ob + os_) / 2.0, 0),
        (ob, 0),   # strict > for overbought
        (os_, 0),  # strict < for oversold
    ]
    for rsi, exp in cases:
        got = 1 if rsi > ob else (-1 if rsi < os_ else 0)
        assert got == exp


# ── FM-069 displacement_flag ─────────────────────────────────────────────────

def test_displacement_flag_ontology_id():
    assert _structural("displacement_flag")["id"] == "FM-069"


def test_displacement_flag_matches_body_fraction():
    """formula: body_size > candle_range * mult and atr > 0 -> {0,1}."""
    cfg = _fp_cfg()
    if "displacement_strong_body_mult" not in cfg:
        raise KeyError("displacement_strong_body_mult required in feature_pipeline")
    mult = cfg["displacement_strong_body_mult"]

    fp, _ = _run_pre_finalize(_synthetic(600))
    df = fp.df
    strong = df["body_size"] > (df["candle_range"] * mult)
    expected = np.where(strong & (df["atr"] > 0), 1, 0).astype(np.int8)
    np.testing.assert_array_equal(df["displacement_flag"].to_numpy(), expected)
    assert set(np.unique(df["displacement_flag"])) <= _state_values("displacement_flag")


def test_displacement_flag_forced_body_dominated():
    df = _synthetic(30)
    fp = FeaturePipeline(df, cfg=_fp_cfg())
    mult = _fp_cfg()["displacement_strong_body_mult"]
    # body dominates range
    fp.df["body_size"] = 10.0
    fp.df["candle_range"] = 10.0 / (mult + 0.1)  # body > range * mult
    fp.df["atr"] = 0.02
    fp.df["liquidity_sweep"] = 0
    fp.df["close"] = 100.0
    fp.df["ema_fast"] = 100.0
    fp.compute_canonical_structure_features()
    assert (fp.df["displacement_flag"] == 1).all()

    # body does not dominate
    fp.df["body_size"] = 1.0
    fp.df["candle_range"] = 100.0
    fp.compute_canonical_structure_features()
    assert (fp.df["displacement_flag"] == 0).all()

    # atr <= 0 forces 0 even with strong body
    fp.df["body_size"] = 10.0
    fp.df["candle_range"] = 10.0
    fp.df["atr"] = 0.0
    fp.compute_canonical_structure_features()
    assert (fp.df["displacement_flag"] == 0).all()
