"""
FC1-A acceptance tests — causal delayed production binding for structure graph.

Contract: docs/governance/FC1-A-SWING-CAUSAL-implementation-contract-2026-07-11.md
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from features.causal_structure import causal_structure_series
from features.feature_pipeline import FeaturePipeline, SWING_WINDOW
from features.feature_identity import (
    get_by_feature_id,
    load_identity_registry,
    resolve_by_name,
)
from core.feature_store import FeatureStore

_ROOT = Path(__file__).resolve().parents[1]
REG = _ROOT / "docs" / "governance" / "phase1_feature_identity_registry-2026-07-10.json"

PROD_STRUCTURE = [
    "swing_high",
    "swing_low",
    "higher_high",
    "lower_low",
    "break_of_structure",
    "liquidity_sweep",
    "sweep_detected",
    "double_sweep",
    "liquidity_distance",
    "liquidity_pressure_score",
]


def _synthetic(n: int = 400, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.5, n))
    open_ = close + rng.normal(0, 0.1, n)
    # OHLCV consistency: high >= max(o,c), low <= min(o,c)
    body_top = np.maximum(open_, close)
    body_bot = np.minimum(open_, close)
    high = body_top + rng.uniform(0.05, 0.8, n)
    low = body_bot - rng.uniform(0.05, 0.8, n)
    volume = rng.uniform(100, 1000, n)
    ts = pd.date_range("2024-01-01", periods=n, freq="15min")
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


@pytest.fixture(autouse=True)
def _clear_identity_cache():
    load_identity_registry.cache_clear()
    yield
    load_identity_registry.cache_clear()


def test_production_binds_to_causal_not_centered():
    df = _synthetic(300)
    p = FeaturePipeline(df.copy())
    p.compute_price_features()
    p.compute_indicators()
    p.compute_structure_liquidity()
    assert p.df["swing_high"].equals(p.df["swing_high_causal_confirmed"])
    assert p.df["swing_low"].equals(p.df["swing_low_causal_confirmed"])
    assert "swing_high_centered_batch" in p.df.columns
    # generally not identical to centered (delay)
    assert (
        not p.df["swing_high"].equals(p.df["swing_high_centered_batch"])
        or int(p.df["swing_high_centered_batch"].sum()) == 0
    )


def test_centered_batch_preserved_byte_stable_vs_math():
    """Centered math identity still emitted; production uses causal."""
    df = _synthetic(250)
    p = FeaturePipeline(df.copy())
    p.compute_price_features()
    p.compute_indicators()
    p.compute_structure_liquidity()
    w = 2 * SWING_WINDOW + 1
    roll_h = p.df["high"].rolling(w, center=True, min_periods=w).max()
    expected = (p.df["high"] == roll_h).astype(np.int8)
    assert p.df["swing_high_centered_batch"].astype(np.int8).equals(expected)


def test_no_hybrid_graph_structure_uses_causal_refs():
    """higher_high/BOS/sweep must match re-derive from causal last prices only."""
    df = _synthetic(300)
    p = FeaturePipeline(df.copy())
    p.compute_price_features()
    p.compute_indicators()
    p.compute_structure_liquidity()
    d = p.df
    ref_h = d["last_swing_high_price_causal"].shift(1)
    ref_l = d["last_swing_low_price_causal"].shift(1)
    hh = (d["high"] > ref_h).fillna(False).astype(np.int8)
    ll = (d["low"] < ref_l).fillna(False).astype(np.int8)
    assert d["higher_high"].astype(np.int8).equals(hh.astype(np.int8))
    assert d["lower_low"].astype(np.int8).equals(ll.astype(np.int8))
    # production last prices equal causal
    assert d["last_swing_high_price"].equals(d["last_swing_high_price_causal"])


def test_prefix_invariance_production_structure_interior():
    """
    Production structure on the safe interior of a prefix run must match the
    full-corpus run (causal delay means no future beyond current bar).
    """
    raw = _synthetic(800)
    full = FeaturePipeline(raw.copy())
    # need atr path for full finalize; use structure stage only for flags
    full.compute_price_features()
    full.compute_indicators()
    full.compute_structure_liquidity()

    prefix_n = 500
    pref = FeaturePipeline(raw.head(prefix_n).copy())
    pref.compute_price_features()
    pref.compute_indicators()
    pref.compute_structure_liquidity()

    k = SWING_WINDOW
    # interior: drop last k bars of prefix (and first warm edge)
    n_pref = len(pref.df)
    assert n_pref > 2 * k + 10
    # Align by position on the raw prefix domain (structure computed before finalize dropna)
    # Using structure-stage dfs which share the same index as input
    # columns from compute_structure_liquidity only (canonical structure runs later)
    for col in ("swing_high", "swing_low", "liquidity_sweep", "higher_high", "lower_low", "break_of_structure"):
        a = pref.df[col].iloc[k : n_pref - k].to_numpy()
        b = full.df[col].iloc[k : n_pref - k].to_numpy()
        assert np.array_equal(a, b), f"prefix variance on production col {col}"


def test_trust_env_does_not_mutate_production_or_centered():
    df = _synthetic(200)
    os.environ.pop("TRUST_SWING_CAUSAL", None)
    p1 = FeaturePipeline(df.copy())
    p1.compute_price_features()
    p1.compute_indicators()
    p1.compute_structure_liquidity()
    prod = p1.df["swing_high"].copy()
    cen = p1.df["swing_high_centered_batch"].copy()
    os.environ["TRUST_SWING_CAUSAL"] = "1"
    try:
        p2 = FeaturePipeline(df.copy())
        p2.compute_price_features()
        p2.compute_indicators()
        p2.compute_structure_liquidity()
        assert p2.df["swing_high"].equals(prod)
        assert p2.df["swing_high_centered_batch"].equals(cen)
        assert "swing_high_research_view" in p2.df.columns
    finally:
        os.environ.pop("TRUST_SWING_CAUSAL", None)


def test_registry_bare_name_maps_to_causal():
    ident = resolve_by_name("swing_high", path=str(REG), allow_legacy_alias=True)
    assert ident.feature_id == "FEAT-SWING_HIGH_CAUSAL_CONFIRMED"
    centered = get_by_feature_id("FEAT-SWING_HIGH_CENTERED_BATCH", str(REG))
    assert "swing_high" not in (centered.legacy_names or [])


def test_online_causal_matches_batch_on_history():
    """FeatureStore causal structure last row ≈ pipeline production columns."""
    raw = _synthetic(120)
    pipe = FeaturePipeline(raw.copy())
    # full pipeline for atr + structure
    feat, _ = pipe.run()
    # rebuild structure-only alignment is hard after finalize; compare causal helper to pipeline structure stage
    p = FeaturePipeline(raw.copy())
    p.compute_price_features()
    p.compute_indicators()
    p.compute_structure_liquidity()
    # need atr column for liquidity — compute_canonical path sets atr later; use raw atr_14 style
    # After compute_indicators, atr_14_raw exists; production liquidity needs atr after canonical
    p.compute_canonical_price_features()
    p.compute_canonical_volatility_features()
    p.compute_structure_liquidity()  # already done
    # atr column from volatility features
    if "atr" not in p.df.columns:
        pytest.skip("atr not available on partial pipeline")
    # liquidity/sweep features need atr + canonical EMAs + the structure graph (canonical order)
    p.compute_canonical_ema_features()
    p.compute_canonical_structure_features()
    p.compute_liquidity_distance()
    series = causal_structure_series(
        p.df["high"].to_numpy(),
        p.df["low"].to_numpy(),
        p.df["close"].to_numpy(),
        p.df["atr"].to_numpy(),
    )
    # Full 10-column closure parity (audit A6): int flags exact...
    int_cols = [
        "swing_high", "swing_low", "higher_high", "lower_low",
        "break_of_structure", "liquidity_sweep",
    ]
    int_cols += ["sweep_detected", "double_sweep"]
    for col in int_cols:
        np.testing.assert_array_equal(
            series[col].astype(np.int8),
            p.df[col].to_numpy().astype(np.int8),
            err_msg=col,
        )
    # ...float liquidity dims on the FINITE-batch domain (batch NaN rows are
    # dropped by finalize(); online's 10.0 default only covers bars batch never emits).
    batch_ld = p.df["liquidity_distance"].to_numpy(dtype=np.float64)
    finite = np.isfinite(batch_ld)
    assert finite.sum() > 20, "synthetic corpus produced too few finite liquidity bars"
    np.testing.assert_allclose(
        series["liquidity_distance"][finite], batch_ld[finite],
        rtol=1e-4, atol=1e-4, err_msg="liquidity_distance",
    )
    batch_lp = p.df["liquidity_pressure_score"].to_numpy(dtype=np.float64)
    np.testing.assert_allclose(
        series["liquidity_pressure_score"][finite], batch_lp[finite],
        rtol=1e-4, atol=1e-4, err_msg="liquidity_pressure_score",
    )


def test_feature_store_overwrites_zero_structure_with_causal():
    store = FeatureStore(max_history=200)
    raw = _synthetic(80)
    # feed minimal required fields with structure zeros
    for i, row in raw.iterrows():
        ohlcv = {
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": float(row["volume"]),
        }
        aux = {
            "atr": 0.01,
            "ema_fast": float(row["close"]),
            "ema_slow": float(row["close"]),
            "session": 1,
            "swing_high": 0.0,
            "swing_low": 0.0,
            "higher_high": 0.0,
            "lower_low": 0.0,
            "break_of_structure": 0.0,
            "liquidity_sweep": 0.0,
            "sweep_detected": 0.0,
            "double_sweep": 0.0,
            "body_size": 0.1,
            "candle_range": 0.2,  # v4.0 rename of the wick_size misnomer (schema v4, FM-002)
            "body_ratio": 0.5,
            "volume_ratio": 1.0,
            "trend_bias": 0.0,
            "trend_strength": 0.0,
            "momentum_score": 0.0,
            "volatility_ratio": 1.0,
            "rsi_14": 50.0,
            "macd_line": 0.0,
            "macd_signal": 0.0,
            "macd_hist_raw": 0.0,  # v4.0 MACD split (FM-049/FM-053); macd_hist_z filled below
            "volatility_regime": 0.0,
            "hour_of_day": 12.0,
            "disp_strength": 0.0,
            "retest_depth": 0.0,
            "candles_since_retest": 0,
            "liquidity_distance": 0.0,
            "liquidity_pressure_score": 0.0,
            "volume_spike": 0,
        }
        # fill any remaining canonical keys with 0
        from features.feature_schema import CANONICAL_FEATURES

        for k in CANONICAL_FEATURES:
            if k not in aux and k not in ohlcv:
                aux[k] = 0.0
        try:
            frame = store.process(i, row["timestamp"], ohlcv, aux)
        except Exception as exc:
            # schema may require exact set — soft skip if incomplete
            if i < 20:
                continue
            raise
        # AUDIT A6: the store must emit exactly the causal-structure values for the
        # fed history — a real overwrite proof that CAN fail (not the old in-(0,1) check).
        from features.causal_structure import causal_structure_at_bar

        highs = [float(x) for x in raw["high"].iloc[: i + 1]]
        lows = [float(x) for x in raw["low"].iloc[: i + 1]]
        closes = [float(x) for x in raw["close"].iloc[: i + 1]]
        atrs = [0.01] * (i + 1)
        expected = causal_structure_at_bar(highs, lows, closes, atrs)
        for key in ("swing_high", "swing_low", "higher_high", "lower_low",
                    "break_of_structure", "liquidity_sweep", "sweep_detected"):
            assert frame.features[key] == pytest.approx(expected[key]), (
                f"bar {i}: store {key}={frame.features[key]} != causal {expected[key]}"
            )
    # the corpus must actually exercise the structure path (guard against vacuous pass)
    from features.causal_structure import causal_structure_series
    series = causal_structure_series(
        raw["high"].to_numpy(), raw["low"].to_numpy(),
        raw["close"].to_numpy(), np.full(len(raw), 0.01),
    )
    assert series["swing_high"].sum() > 0 and series["swing_low"].sum() > 0, (
        "synthetic corpus produced no pivots — overwrite proof would be vacuous"
    )


def test_provenance_sidecars_exist():
    rr = _ROOT / "models" / "rr_model.provenance.json"
    zone = _ROOT / "models" / "zone_registry.provenance.json"
    assert rr.is_file()
    assert zone.is_file()
    import json

    for path in (rr, zone):
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["pit_status"] == "PIT_UNCLEAN_CENTERED_SWINGS"
        assert "operational_rule" in data
