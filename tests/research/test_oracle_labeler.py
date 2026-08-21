"""Floor for the oracle labeler (SEM-018) and the scan statistics.

Two things are protected here:

  GEOMETRY  the labeler must place SL/TP1/TP2 exactly where `build_trade` does, must
            refuse an inverted stop rather than fabricating a label for it, and must
            derive its labels rather than read them from a stream.

  STATISTICS the block bootstrap must actually account for label overlap. A test that
            only checked "an interval was produced" would pass against an i.i.d.
            bootstrap, which is precisely the bug that would manufacture significance.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from research.costs import ComponentCostModel  # noqa: E402
from research.oracle.labeler import (  # noqa: E402
    SL_GEOMETRIES,
    TIE_BREAKS,
    _nights_held,
    _tp1_multiplier,
    label_corpus,
)
from research.oracle.scan import (  # noqa: E402
    block_bootstrap_mean_ci,
    effective_n,
    l2_state_cells,
    partition,
    rank_auc,
)

_CRT_CFG = {
    "sl_atr_buffer": 0.2,
    "tp1_atr_multiplier": 1.0,
    "tp1_atr_multiplier_breakout": 1.5,
    "tp1_atr_multiplier_pullback": 0.8,
    "tp1_atr_multiplier_liq_sweep": 1.2,
    "tp1_atr_multiplier_reversal": 1.0,
    "tp2_atr_multiplier": 2.0,
}


def _cost_model() -> ComponentCostModel:
    return ComponentCostModel(
        half_spread=0.045, commission=0.04, entry_slippage=0.09, stop_slippage=0.09,
        swap_long_per_night=-0.56, swap_short_per_night=0.38,
        instrument="TEST", source="SYNTHETIC", status="MEASURED",
    )


def _synthetic(n=300, seed=7):
    rng = np.random.default_rng(seed)
    px = 2000.0 + np.cumsum(rng.normal(0, 1.5, n))
    hi = px + np.abs(rng.normal(0, 0.8, n))
    lo = px - np.abs(rng.normal(0, 0.8, n))
    op = px + rng.normal(0, 0.3, n)
    t0 = datetime(2024, 5, 22, 1, 0, 0)
    raw = pd.DataFrame({
        "timestamp": [t0 + timedelta(minutes=15 * i) for i in range(n)],
        "open": op, "high": np.maximum.reduce([hi, op, px]),
        "low": np.minimum.reduce([lo, op, px]), "close": px,
        "volume": rng.integers(100, 900, n).astype(float),
    })
    raw["_pos"] = range(n)
    matrix = pd.DataFrame({
        "_pos": raw["_pos"], "timestamp": raw["timestamp"], "close": raw["close"],
        "atr_abs": np.full(n, 2.0), "trade_intent": ["breakout"] * n,
    })
    return matrix, raw


# ─────────────────────────────────────────────────────────────────────────────
# Geometry
# ─────────────────────────────────────────────────────────────────────────────
def test_tp1_multiplier_resolves_per_intent_with_fallback():
    assert _tp1_multiplier(_CRT_CFG, "breakout") == 1.5
    assert _tp1_multiplier(_CRT_CFG, "pullback") == 0.8
    assert _tp1_multiplier(_CRT_CFG, "liq_sweep") == 1.2
    assert _tp1_multiplier(_CRT_CFG, "reversal") == 1.0
    # An unknown intent must fall back to the base key, mirroring build_trade's getattr.
    assert _tp1_multiplier(_CRT_CFG, "not_a_real_intent") == 1.0


def test_unit_count_is_the_declared_cartesian_product():
    matrix, raw = _synthetic(n=200)
    labels, stats = label_corpus(matrix, raw, cost_model=_cost_model(),
                                 adverse_fill=None, max_forward=40, crt_cfg=_CRT_CFG)
    per_bar = 2 * len(SL_GEOMETRIES) * len(TIE_BREAKS)
    assert per_bar == 8
    assert len(labels) == stats["bars_labelled"] * per_bar
    # Bars without a full forward window are excluded and COUNTED, not silently dropped.
    assert stats["rejects"]["insufficient_forward_window"] == 40


def test_sl_geometry_matches_build_trade():
    matrix, raw = _synthetic(n=150)
    labels, _ = label_corpus(matrix, raw, cost_model=_cost_model(), adverse_fill=None,
                             max_forward=40, crt_cfg=_CRT_CFG)
    atr_abs, buf = 2.0, 0.2
    for _, r in labels.sample(30, random_state=3).iterrows():
        bar = raw.loc[raw["_pos"] == r["_pos"]].iloc[0]
        if r["sl_geom"] == "disp_bar":
            want = (bar["low"] - buf * atr_abs) if r["direction"] == "long" else (
                bar["high"] + buf * atr_abs)
        else:
            want = (r["entry"] - atr_abs) if r["direction"] == "long" else (
                r["entry"] + atr_abs)
        assert r["sl"] == pytest.approx(want, abs=1e-9)


def test_targets_are_r_anchored_not_atr_anchored():
    """The config keys say `_atr_multiplier` but the arithmetic is R-multiples of risk."""
    matrix, raw = _synthetic(n=150)
    labels, _ = label_corpus(matrix, raw, cost_model=_cost_model(), adverse_fill=None,
                             max_forward=40, crt_cfg=_CRT_CFG)
    for _, r in labels.sample(30, random_state=5).iterrows():
        sign = 1 if r["direction"] == "long" else -1
        risk = r["risk_distance"]
        assert r["tp1"] == pytest.approx(r["entry"] + sign * 1.5 * risk, abs=1e-9)
        assert r["tp2"] == pytest.approx(r["entry"] + sign * 2.0 * risk, abs=1e-9)
        # ...and specifically NOT anchored to ATR, unless risk happens to equal ATR.
        if abs(risk - 2.0) > 1e-6:
            assert r["tp1"] != pytest.approx(r["entry"] + sign * 1.5 * 2.0, abs=1e-9)


def test_labels_are_derived_not_read_from_a_stream():
    """No banned stream field may appear as a label source (F-022 class)."""
    matrix, raw = _synthetic(n=120)
    labels, _ = label_corpus(matrix, raw, cost_model=_cost_model(), adverse_fill=None,
                             max_forward=40, crt_cfg=_CRT_CFG)
    banned = {"rr_achieved", "outcome_stream", "pnl_rr_net", "rr"}
    assert not (banned & set(labels.columns))
    assert {"y_R_gross", "y_R_net", "y_win", "outcome"} <= set(labels.columns)


def test_cost_is_proportional_to_r_so_tight_stops_pay_more():
    """cost_r is cost_price/risk_distance, so geometry moves cost. Guards the caveat."""
    matrix, raw = _synthetic(n=200)
    labels, _ = label_corpus(matrix, raw, cost_model=_cost_model(), adverse_fill=None,
                             max_forward=40, crt_cfg=_CRT_CFG)
    tight = labels[labels["sl_geom"] == "disp_bar"]["cost_r"].mean()
    wide = labels[labels["sl_geom"] == "fixed_atr"]["cost_r"].mean()
    assert tight > wide, (tight, wide)


def test_nights_held_counts_date_boundaries():
    a = datetime(2024, 5, 22, 23, 45)
    assert _nights_held(a, a + timedelta(minutes=30)) == 1
    assert _nights_held(a, a + timedelta(minutes=10)) == 0
    assert _nights_held(a, a + timedelta(days=2)) == 2


# ─────────────────────────────────────────────────────────────────────────────
# Statistics
# ─────────────────────────────────────────────────────────────────────────────
def test_rank_auc_known_cases():
    assert rank_auc(np.array([1.0, 2, 3, 4]), np.array([0, 0, 1, 1])) == pytest.approx(1.0)
    assert rank_auc(np.array([4.0, 3, 2, 1]), np.array([0, 0, 1, 1])) == pytest.approx(0.0)
    # A constant feature must be exactly 0.5, not an artefact of tie handling.
    assert rank_auc(np.ones(100), np.r_[np.zeros(50), np.ones(50)]) == pytest.approx(0.5)


def test_block_bootstrap_is_wider_than_iid_on_autocorrelated_data():
    """THE test that matters: blocks must actually account for overlap.

    An i.i.d. bootstrap on autocorrelated values produces an interval that is far too
    narrow. If this test ever fails, every interval in the program is overconfident and
    the pattern scan is manufacturing significance.
    """
    rng = np.random.default_rng(11)
    n_blocks, block_size = 200, 40
    # Strong within-block correlation: one draw per block, repeated across it.
    per_block = rng.normal(0, 1, n_blocks)
    values = np.repeat(per_block, block_size) + rng.normal(0, 0.05, n_blocks * block_size)
    blocks = np.repeat(np.arange(n_blocks), block_size)

    _, blo, bhi = block_bootstrap_mean_ci(values, blocks, n_boot=2000, seed=1)
    iid_blocks = np.arange(values.size)  # every row its own block == i.i.d. resampling
    _, ilo, ihi = block_bootstrap_mean_ci(values, iid_blocks, n_boot=2000, seed=1)

    block_width, iid_width = bhi - blo, ihi - ilo
    assert block_width > 3 * iid_width, (block_width, iid_width)


def test_partition_has_no_leakage_and_a_non_overlapping_test_set():
    df = pd.DataFrame({"_pos": np.arange(10_000), "direction": "long",
                       "y_R_net": 0.0, "y_win": 0})
    part = partition(df, oos_fraction=0.2, embargo_bars=96, horizon=40)
    train_max = part.train["_pos"].max()
    test_min = part.test_stride["_pos"].min()
    # A train row's forward horizon must not reach the test region.
    assert train_max + 40 < test_min
    assert test_min - train_max > 96
    # No two test labels may share a forward bar.
    gaps = np.diff(np.sort(part.test_stride["_pos"].unique()))
    assert (gaps >= 40).all()


def test_effective_n_is_blocks_not_rows():
    df = pd.DataFrame({"_pos": np.arange(4000)})
    assert effective_n(df, horizon=40) == 100
    assert effective_n(df, horizon=40) != len(df)


def test_l2_flags_insufficient_cells_rather_than_dropping_them():
    """A thin cell is INSUFFICIENT, not absent. Silent dropping hides the sample size."""
    n = 2000
    df = pd.DataFrame({
        "_pos": np.arange(n),
        "y_R_net": np.random.default_rng(2).normal(0, 1, n),
        "y_win": np.random.default_rng(3).integers(0, 2, n),
        "state__thing": ["common"] * (n - 5) + ["rare"] * 5,
    })
    out = l2_state_cells(df, ["state__thing"], horizon=40, min_eff_n=30, n_boot=200)
    assert set(out["cell"]) == {"common", "rare"}
    assert out.loc[out["cell"] == "rare", "status"].iloc[0] == "INSUFFICIENT"
    assert out.loc[out["cell"] == "common", "status"].iloc[0] == "OK"


def test_l2_separates_beats_base_from_beats_zero():
    """Beating a negative base is not profitability. Both flags must exist and differ."""
    n = 4000
    rng = np.random.default_rng(4)
    y = rng.normal(-0.5, 1.0, n)          # base well below zero
    cell = np.array(["a"] * n, dtype=object)
    cell[: n // 2] = "b"
    y[:n // 2] += 0.3                      # 'b' beats base, still negative
    df = pd.DataFrame({"_pos": np.arange(n), "y_R_net": y,
                       "y_win": (y > 0).astype(int), "state__f": cell})
    out = l2_state_cells(df, ["state__f"], horizon=40, min_eff_n=10, n_boot=500)
    b = out[out["cell"] == "b"].iloc[0]
    assert b["beats_base"] and not b["beats_zero"]
