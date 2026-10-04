"""
Phase 3 (Kernel 2) — feature-generation tests.

Protects the SECOND sacred boundary (PositionEpisode → FeatureRecord) with the same rigor
as reconstruction: hand-computed MFE/MAE parity, realized-R, session/duration, regime
sentinels (None vs UNKNOWN), the purity invariant (no aggregate keys), and determinism.
"""
from __future__ import annotations

import pytest

from conftest import M15, BASE_TIME, flat_bars, make_bar  # type: ignore

from mt5_analytics.analytics_config import load_config
from mt5_analytics.engines.features import feature_engine, regime_engine
from mt5_analytics.engines.features._bars import build_window
from mt5_analytics.engines.features.feature_record_builder import build
from mt5_analytics.schemas.feature_v1_0 import FORBIDDEN_AGGREGATE_KEYS
from mt5_analytics.schemas.position_episode_v1_0 import (
    PositionEpisode,
    make_episode_id,
)

CFG = load_config()


def _episode(
    *,
    direction="long",
    entry_vwap=100.0,
    exit_vwap=106.0,
    entry_t=BASE_TIME + 20 * M15,
    exit_t=BASE_TIME + 23 * M15,
    symbol="EURUSD",
):
    entry_iso = "2023-11-14T14:00:00Z"
    exit_iso = "2023-11-14T15:00:00Z"
    return PositionEpisode(
        position_id=42,
        episode_id=make_episode_id(42, entry_iso, [1, 2]),
        symbol=symbol,
        direction=direction,
        entry_time=entry_iso,
        exit_time=exit_iso,
        entry_vwap=entry_vwap,
        exit_vwap=exit_vwap,
        volume=1.0,
        net_pnl=6.0,
        gross_profit=6.0,
        commission=0.0,
        swap=0.0,
        duration_seconds=3600.0,
    )


def _long_window():
    """20 flat warmup bars + entry bar + 3 post-entry bars with known excursions.

    entry=100, SL=98 -> risk=2. Post bars: +1 (h102/l99), +2 (h106/l101), +3 (h104/l103).
    => mfe=+6 (3R), mae=-1 (-0.5R).
    """
    warm = flat_bars(21, start_t=BASE_TIME, price=100.0)   # bars 0..20 (entry at 20)
    entry_t = BASE_TIME + 20 * M15
    post = [
        make_bar(entry_t + 1 * M15, 100, 102, 99, 101),
        make_bar(entry_t + 2 * M15, 101, 106, 101, 105),
        make_bar(entry_t + 3 * M15, 105, 104, 103, 104),
    ]
    window, entry_index = build_window(warm + post, entry_t)
    return window, entry_index


# ── MFE/MAE parity (exact, hand-computed) ─────────────────────────────────────────
def test_mfe_mae_in_trade_R():
    window, entry_index = _long_window()
    rec = feature_engine.compute(_episode(), window, entry_index, sl_price=98.0, cfg=CFG)
    assert rec["mfe_r"] == 3.0          # +6 / risk 2
    assert rec["mae_r"] == -0.5         # -1 / risk 2
    assert rec["reached_1r"] is True
    assert rec["reached_3r"] is True
    assert rec["risk_distance"] == 2.0


def test_realized_r_sign_and_magnitude():
    window, entry_index = _long_window()
    rec = feature_engine.compute(_episode(exit_vwap=106.0), window, entry_index,
                                 sl_price=98.0, cfg=CFG)
    assert rec["realized_r"] == 3.0     # (106-100)/2 long
    # short loser: exit above entry on a short
    rec_s = feature_engine.compute(
        _episode(direction="short", entry_vwap=100.0, exit_vwap=102.0),
        window, entry_index, sl_price=102.0, cfg=CFG,
    )
    assert rec_s["realized_r"] == -1.0  # (100-102)/|100-102| short


def test_atr_fallback_when_no_sl():
    # No SL -> risk basis comes from ATR over warmup bars (spread => non-zero ATR).
    warm = flat_bars(21, start_t=BASE_TIME, price=100.0, spread=1.0)  # TR ~2 => atr ~2
    entry_t = BASE_TIME + 20 * M15
    post = [make_bar(entry_t + M15, 100, 104, 99, 103)]
    window, entry_index = build_window(warm + post, entry_t)
    rec = feature_engine.compute(_episode(), window, entry_index, sl_price=None, cfg=CFG)
    assert rec["risk_distance"] is not None and rec["risk_distance"] > 0.0
    assert rec["realized_r"] is not None


# ── duration / session ────────────────────────────────────────────────────────────
def test_duration_metrics():
    window, entry_index = _long_window()
    rec = feature_engine.compute(_episode(), window, entry_index, sl_price=98.0, cfg=CFG)
    assert rec["duration_minutes"] == 60.0
    assert rec["duration_hours"] == 1.0
    assert rec["bars_held"] == 4


def test_session_overlap_hour_14():
    window, entry_index = _long_window()
    rec = feature_engine.compute(_episode(), window, entry_index, sl_price=98.0, cfg=CFG)
    assert rec["entry_hour"] == 14
    assert rec["session"] == "OVERLAP"   # 14:00 UTC ∈ London(7-16) ∩ NY(13-22)


# ── regime sentinels ──────────────────────────────────────────────────────────────
def test_regime_none_when_insufficient_history():
    window, entry_index = _long_window()   # ~24 bars << tercile_window 480
    rec = feature_engine.compute(_episode(), window, entry_index, sl_price=98.0, cfg=CFG)
    assert rec["regime"] is None           # insufficient, NOT "UNKNOWN"


def test_regime_unknown_on_failure():
    # Bars lacking .high force the labeler to raise -> "UNKNOWN" (distinct from None).
    bad_window = [1, 2, 3, 4, 5]
    out = regime_engine.partial(bad_window, 2, atr_period=14, tercile_window=3)
    assert out["regime"] == "UNKNOWN"


# ── purity invariant ──────────────────────────────────────────────────────────────
def test_no_aggregate_keys_in_record():
    window, entry_index = _long_window()
    rec = feature_engine.compute(_episode(), window, entry_index, sl_price=98.0, cfg=CFG)
    assert FORBIDDEN_AGGREGATE_KEYS.isdisjoint(rec.keys())
    assert "engine_versions" in rec and "episode_id" in rec


def test_builder_rejects_reserved_key_collision():
    with pytest.raises(ValueError):
        build(_episode(), [{"symbol": "XXX"}])


def test_builder_rejects_forbidden_aggregate_key():
    with pytest.raises(ValueError):
        build(_episode(), [{"profit_factor": 1.5}])


# ── determinism ───────────────────────────────────────────────────────────────────
def test_determinism_same_window_same_record():
    window, entry_index = _long_window()
    a = feature_engine.compute(_episode(), window, entry_index, sl_price=98.0, cfg=CFG)
    b = feature_engine.compute(_episode(), window, entry_index, sl_price=98.0, cfg=CFG)
    assert a == b


# ── build_window ──────────────────────────────────────────────────────────────────
def test_build_window_locates_entry_bar():
    bars = flat_bars(10, start_t=BASE_TIME, price=100.0)
    entry_t = BASE_TIME + 5 * M15
    window, entry_index = build_window(bars, entry_t)
    assert entry_index == 5
    assert [b.index for b in window] == list(range(10))   # re-indexed 0..n-1
