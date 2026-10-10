# tests/test_swing_causality.py
"""
Causal swing / structure features (structure_mode="causal_v2") and the preserved
non-causal reference ("centred_v1").

- Changing or removing FUTURE bars must not change any already-available canonical feature.
- A swing's event time (the swing bar) and confirmation time (when it is knowable) are
  stored separately; no decision at bar t may use a swing confirmed at or after t.
- centred_v1 still reproduces the original outputs (golden file) and still leaks.
"""

import hashlib
import json
import os

import numpy as np
import pandas as pd
import pytest

from features.feature_pipeline import (
    FeaturePipeline, STRUCTURE_MODE_CAUSAL, STRUCTURE_MODE_CENTRED, SWING_CONFIRM_BARS, SWING_WINDOW,
)
from features.feature_schema import CANONICAL_FEATURES

GOLDEN = os.path.join(os.path.dirname(__file__), "golden", "structure_centred_v1.json")


def _ohlcv(n=700, seed=11):
    rng = np.random.default_rng(seed)
    ts = pd.date_range("2024-01-01", periods=n, freq="15min")
    close = 100 + np.cumsum(rng.normal(0, 0.25, n))
    wick = np.abs(rng.normal(0, 0.35, n)); body = rng.normal(0, 0.25, n)
    o = close - body
    return pd.DataFrame({"timestamp": ts, "open": o, "high": np.maximum(o, close) + wick,
                         "low": np.minimum(o, close) - wick, "close": close,
                         "volume": rng.uniform(100, 2000, n)})


def _structure_frame(df, mode):
    """Pipeline steps up to and including compute_structure_liquidity (pre-finalize rows)."""
    p = FeaturePipeline(df, structure_mode=mode)
    p.compute_price_features(); p.compute_volume_features(); p.compute_indicators()
    p.compute_trend_features(); p.compute_volatility_regime(); p.compute_context()
    p.compute_structure_liquidity()
    return p.df


def _canon(df):
    return df[list(CANONICAL_FEATURES)].astype(float)


def _mutate_future(df, cut, seed=99):
    out = df.copy()
    rng = np.random.default_rng(seed)
    m = len(out) - cut - 1
    close = out["close"].iloc[cut] + np.cumsum(rng.normal(0, 3.0, m))   # wild, different future
    wick = np.abs(rng.normal(0, 2.0, m)); o = close - rng.normal(0, 1.0, m)
    out.loc[out.index[cut + 1:], ["open", "high", "low", "close"]] = np.column_stack(
        [o, np.maximum(o, close) + wick, np.minimum(o, close) - wick, close])
    return out


@pytest.fixture(scope="module")
def frame():
    return _ohlcv()


@pytest.fixture(scope="module")
def full(frame):
    return FeaturePipeline(frame).run()[0]


def test_default_mode_is_causal_and_invalid_mode_rejected(frame):
    assert FeaturePipeline(frame).structure_mode == STRUCTURE_MODE_CAUSAL
    with pytest.raises(ValueError):
        FeaturePipeline(frame, structure_mode="trailing_v9")
    assert SWING_CONFIRM_BARS == SWING_WINDOW == 2


@pytest.mark.parametrize("cut", [300, 420, 560])
def test_mutating_future_bars_changes_no_available_feature(frame, full, cut):
    ts_cut = frame["timestamp"].iloc[cut]
    mutated, _ = FeaturePipeline(_mutate_future(frame, cut)).run()
    a = _canon(full[full["timestamp"] <= ts_cut]).reset_index(drop=True)
    b = _canon(mutated[mutated["timestamp"] <= ts_cut]).reset_index(drop=True)
    assert len(a) == len(b) > 0
    pd.testing.assert_frame_equal(a, b, check_exact=False, rtol=1e-9, atol=1e-9)


@pytest.mark.parametrize("cut", [300, 420, 560])
def test_truncating_future_bars_changes_no_feature_including_the_tail(frame, full, cut):
    part, _ = FeaturePipeline(frame.iloc[: cut + 1]).run()
    a = _canon(part).reset_index(drop=True)
    b = _canon(full[full["timestamp"].isin(part["timestamp"])]).reset_index(drop=True)
    assert len(a) == len(b) > 0
    pd.testing.assert_frame_equal(a, b, check_exact=False, rtol=1e-9, atol=1e-9)


def test_centred_reference_still_leaks_so_the_tests_are_sensitive(frame):
    leaked = False
    for cut in (300, 420, 560):
        base = _structure_frame(frame, STRUCTURE_MODE_CENTRED)
        mut = _structure_frame(_mutate_future(frame, cut), STRUCTURE_MODE_CENTRED)
        sl = slice(0, cut + 1)
        for c in ("swing_high", "swing_low", "higher_high", "lower_low", "break_of_structure", "liquidity_sweep"):
            if not np.array_equal(base[c].to_numpy()[sl], mut[c].to_numpy()[sl]):
                leaked = True
    assert leaked


def test_centred_v1_reproduces_the_original_outputs(frame):
    g = json.load(open(GOLDEN))
    df, _ = FeaturePipeline(frame, structure_mode=STRUCTURE_MODE_CENTRED).run()
    assert len(df) == g["rows"] and str(df["timestamp"].iloc[0]) == g["first_ts"]
    for c, ref in g.items():
        if c in ("rows", "first_ts"):
            continue
        digest = hashlib.sha256(np.ascontiguousarray(df[c].to_numpy(dtype=np.float64)).tobytes()).hexdigest()
        assert digest == ref["sha256"], f"{c} no longer matches the preserved centred_v1 reference"


def test_causal_swing_flag_is_the_centred_flag_delayed_by_the_confirmation_bars(frame):
    c = _structure_frame(frame, STRUCTURE_MODE_CAUSAL).reset_index(drop=True)
    o = _structure_frame(frame, STRUCTURE_MODE_CENTRED).reset_index(drop=True)
    k = SWING_CONFIRM_BARS
    for side in ("swing_high", "swing_low"):
        np.testing.assert_array_equal(c[side].to_numpy()[k + 2 * SWING_WINDOW:],
                                      o[side].shift(k).fillna(0).astype(int).to_numpy()[k + 2 * SWING_WINDOW:])
    assert c["swing_high"].sum() > 20 and c["swing_low"].sum() > 20


def test_event_and_confirmation_times_are_stored_separately(frame):
    c = _structure_frame(frame, STRUCTURE_MODE_CAUSAL).reset_index(drop=True)
    ts = c["timestamp"]
    for side, price_col, fn in (("high", "high", np.max), ("low", "low", np.min)):
        rows = c.index[c[f"swing_{side}"] == 1]
        assert len(rows) > 20
        for r in rows[:40]:
            ev, cf = c.loc[r, f"swing_{side}_event_ts"], c.loc[r, f"swing_{side}_confirm_ts"]
            assert cf == ts[r]                               # known on this row
            assert ev == ts[r - SWING_CONFIRM_BARS]          # the swing bar itself
            assert ev < cf
            win = c[price_col].iloc[r - 2 * SWING_WINDOW: r + 1]
            assert c.loc[r - SWING_CONFIRM_BARS, price_col] == fn(win)   # really the 5-bar extreme
        assert c[f"swing_{side}_event_ts"].isna().sum() == (c[f"swing_{side}"] == 0).sum()


def test_no_decision_uses_a_swing_confirmed_at_or_after_its_own_bar(frame):
    c = _structure_frame(frame, STRUCTURE_MODE_CAUSAL)
    for side in ("high", "low"):
        known = c[f"ref_swing_{side}_confirm_ts"].notna()
        assert (c.loc[known, f"ref_swing_{side}_confirm_ts"] < c.loc[known, "timestamp"]).all()
        assert (c.loc[known, f"ref_swing_{side}_event_ts"] < c.loc[known, f"ref_swing_{side}_confirm_ts"]).all()
    # every structure signal sits on a bar whose reference swing was already confirmed
    sig = c[(c["break_of_structure"] != 0) | (c["liquidity_sweep"] != 0) | (c["higher_high"] == 1) | (c["lower_low"] == 1)]
    assert len(sig) > 20
    assert sig["ref_swing_high_confirm_ts"].notna().all() or sig["ref_swing_low_confirm_ts"].notna().all()


def test_last_bars_are_handled_without_error_and_flags_stay_binary(full):
    for c in ("swing_high", "swing_low", "higher_high", "lower_low"):
        assert set(full[c].unique()) <= {0, 1}
    assert set(full["break_of_structure"].unique()) <= {-1, 0, 1}
    assert set(full["liquidity_sweep"].unique()) <= {-1, 0, 1}
