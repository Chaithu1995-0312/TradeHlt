"""CH-timeframe-ssot-v1 — one bar-size truth, and the guards that enforce it.

An H4 research check once read candle-pattern features that FeaturePipeline had computed on 15-minute
candles, and an H1/H4 backtest would have reset its state machine on every bar (gap_reset_minutes=120 is
shorter than one 240-minute bar). Nothing declared or checked the bar size. These tests pin:
  * the one bar-size table + measurer (`features.calendar_periods`) and its agreement with the hour grid;
  * FeaturePipeline refuses a frame whose measured bar size differs from its declared timeframe, and
    accepts it when the right timeframe is declared;
  * the backtest gap-reset guard (G2) fires when one bar is longer than the limit, and only then;
  * the live rail accepts M15 only, with its seconds table derived from the same bar-size table;
  * `contiguous_mask` (now built on the shared measurer) is unchanged.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from features.calendar_periods import BAR_MINUTES, HOUR_GRID_HOURS, modal_bar_minutes, modal_gap_ns  # noqa: E402


def _frame(n: int, minutes: int) -> pd.DataFrame:
    ts = pd.date_range("2026-01-05 00:00:00", periods=n, freq=f"{minutes}min")
    base = 2000.0 + np.cumsum(np.sin(np.arange(n) / 7.0))
    return pd.DataFrame({
        "timestamp": ts, "open": base, "high": base + 1.0, "low": base - 1.0, "close": base + 0.2,
        "volume": np.full(n, 100.0),
    })


# ── bar-size table and measurer ───────────────────────────────────────────────────────────────

def test_bar_minutes_agrees_with_the_hour_grid():
    for rule, hours in HOUR_GRID_HOURS.items():
        assert BAR_MINUTES[rule] == 60 * hours
    assert BAR_MINUTES["M15"] == 15


@pytest.mark.parametrize("minutes", [1, 5, 15, 30, 60, 240])
def test_modal_bar_minutes_measures_the_bar_size(minutes):
    assert modal_bar_minutes(_frame(60, minutes)["timestamp"]) == minutes


def test_modal_bar_minutes_ignores_a_weekend_gap():
    ts = list(pd.date_range("2026-01-02 20:00", periods=8, freq="15min"))        # Friday evening
    ts += list(pd.date_range("2026-01-05 01:00", periods=8, freq="15min"))       # Monday: one 53-hour gap
    assert modal_bar_minutes(pd.Series(ts)) == 15


def test_modal_bar_minutes_min_share_ignores_an_irregular_list():
    irregular = pd.Series(pd.to_datetime(["2024-01-01 03:00", "2024-01-01 10:00", "2024-01-01 20:15",
                                          "2024-01-01 07:59", "2024-01-01 08:00"]))
    assert modal_bar_minutes(irregular) == 1                      # no min_share: the mode is a 1-minute accident
    assert modal_bar_minutes(irregular, min_share=0.5) is None     # not a bar series: nothing to measure
    assert modal_bar_minutes(_frame(60, 15)["timestamp"], min_share=0.5) == 15


def test_feature_pipeline_does_not_check_an_irregular_timestamp_list():
    from features.feature_pipeline import FeaturePipeline

    f = _frame(5, 15)
    f["timestamp"] = pd.to_datetime(["2024-01-01 03:00", "2024-01-01 10:00", "2024-01-01 20:15",
                                     "2024-01-01 07:59", "2024-01-01 08:00"])
    assert FeaturePipeline(f).timeframe == "M15"                  # unmeasurable, declaration trusted


def test_modal_bar_minutes_is_none_without_two_distinct_timestamps():
    assert modal_bar_minutes(pd.Series(pd.to_datetime(["2026-01-05 00:00"]))) is None
    assert modal_gap_ns(pd.Series(pd.to_datetime(["2026-01-05", "2026-01-05"]))) is None


# ── FeaturePipeline declared timeframe ────────────────────────────────────────────────────────

def test_feature_pipeline_refuses_a_frame_of_another_bar_size():
    from features.feature_pipeline import FeaturePipeline

    with pytest.raises(ValueError, match=r"declared timeframe 'M15'.*measured bar size is 240 min"):
        FeaturePipeline(_frame(60, 240))                       # H4 frame, default M15 declaration


def test_feature_pipeline_accepts_the_declared_timeframe():
    from features.feature_pipeline import FeaturePipeline

    assert FeaturePipeline(_frame(60, 240), timeframe="H4").timeframe == "H4"
    assert FeaturePipeline(_frame(60, 15)).timeframe == "M15"


def test_feature_pipeline_refuses_an_unknown_timeframe():
    from features.feature_pipeline import FeaturePipeline

    with pytest.raises(ValueError, match="unknown timeframe"):
        FeaturePipeline(_frame(60, 15), timeframe="H3")


# ── backtest G2: gap reset vs bar size ────────────────────────────────────────────────────────

def _cfg(enabled: bool = True, minutes: int = 120):
    return SimpleNamespace(gap_reset_enabled=enabled, gap_reset_minutes=minutes)


def test_gap_reset_guard_fires_when_one_bar_is_longer_than_the_limit():
    from runtime.backtest_v2 import TimeframeGuardError, _validate_gap_reset_vs_bar_size

    with pytest.raises(TimeframeGuardError, match="fire on every bar"):
        _validate_gap_reset_vs_bar_size(_cfg(), _frame(60, 240)["timestamp"])


def test_gap_reset_guard_passes_for_m15_h1_and_when_disabled():
    from runtime.backtest_v2 import _validate_gap_reset_vs_bar_size

    _validate_gap_reset_vs_bar_size(_cfg(), _frame(60, 15)["timestamp"])
    _validate_gap_reset_vs_bar_size(_cfg(), _frame(60, 60)["timestamp"])           # 60 < 120: only real gaps fire
    _validate_gap_reset_vs_bar_size(_cfg(enabled=False), _frame(60, 240)["timestamp"])


# ── live rail ─────────────────────────────────────────────────────────────────────────────────

def test_live_rail_table_is_derived_and_only_m15_is_supported():
    from inout.live_rail import config as lr

    assert lr._TF_SECONDS == {k: 60 * m for k, m in BAR_MINUTES.items()}
    assert lr._tf_seconds("M15") == 900
    for tf in ("M1", "M5", "M30", "H1", "H4", "D1"):
        with pytest.raises(ValueError, match="not supported"):
            lr._tf_seconds(tf)
    with pytest.raises(KeyError):
        lr._tf_seconds("H3")


# ── contiguous_mask is unchanged by the refactor ──────────────────────────────────────────────

def test_contiguous_mask_golden():
    from features.candle_patterns import contiguous_mask

    ts = pd.to_datetime(["2026-01-05 00:00", "2026-01-05 00:15", "2026-01-05 00:30",
                         "2026-01-05 01:30", "2026-01-05 01:45"])                  # one 60-minute gap
    assert contiguous_mask(ts).tolist() == [False, True, True, False, True]
    assert contiguous_mask(ts[:1]).tolist() == [False]
    assert contiguous_mask(pd.to_datetime([])).tolist() == []
