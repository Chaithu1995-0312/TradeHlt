"""Independent FC1-A oracle parity + synthetic structure scenarios.

Closes the residual series-parity gap for:
  FM-045 swing_high
  FM-046 swing_low
  FM-066 last_swing_high_price
  FM-067 last_swing_low_price
and type-1 scenario checks for FM-057 BOS / FM-058 liquidity_sweep that do NOT
trust pipeline intermediates — they use the independent oracle for expected
values, then assert pipeline matches the oracle.

Contract sources (read-only):
  - feature_pipeline.compute_structure_liquidity (FC1-A split)
  - ontology rolling_indicators FM-045/046 formulas
  - docs/governance/FC1-A-SWING-CAUSAL-implementation-contract-2026-07-11.md

PRODUCTION_BEHAVIOR_CHANGED=NO — tests + test helper only.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

# helpers/ is under tests/; ensure importable when pytest root is repo root
_TESTS = Path(__file__).resolve().parent
if str(_TESTS) not in sys.path:
    sys.path.insert(0, str(_TESTS))

from helpers.fc1a_swing_oracle import (  # noqa: E402
    assert_frame_close,
    fc1a_oracle,
    oracle_from_ohlcv,
    require_k,
)

from config_layer.production_config import get_prod_section  # noqa: E402
from features.feature_pipeline import FeaturePipeline  # noqa: E402
from features.registry import load_ontology  # noqa: E402


def _swing_k() -> int:
    cfg = get_prod_section("feature_pipeline")
    if "swing_window" not in cfg:
        raise KeyError("feature_pipeline.swing_window required (no silent default)")
    return require_k(int(cfg["swing_window"]))


def _synthetic(n: int = 500, seed: int = 19) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    ts = pd.date_range("2024-03-01", periods=n, freq="15min")
    close = 100 + np.cumsum(rng.normal(0, 0.4, n))
    open_ = close + rng.normal(0, 0.05, n)
    high = np.maximum(open_, close) + rng.uniform(0.05, 0.7, n)
    low = np.minimum(open_, close) - rng.uniform(0.05, 0.7, n)
    return pd.DataFrame(
        {
            "timestamp": ts,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": rng.uniform(100, 2000, n),
        }
    )


def _pipeline_structure(df: pd.DataFrame) -> pd.DataFrame:
    """Structure stage only — preserves row count (no finalize drop)."""
    fp = FeaturePipeline(df.copy())
    fp.compute_price_features()
    fp.compute_volume_features()
    fp.compute_indicators()
    fp.compute_structure_liquidity()
    return fp.df


# ── ontology presence ────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "name,fid,section",
    [
        ("swing_high", "FM-045", "rolling_indicators"),
        ("swing_low", "FM-046", "rolling_indicators"),
        ("last_swing_high_price", "FM-066", "rolling_indicators"),
        ("last_swing_low_price", "FM-067", "rolling_indicators"),
    ],
)
def test_swing_features_declared(name: str, fid: str, section: str):
    ont = load_ontology()
    if section not in ont or name not in ont[section]:
        raise KeyError(f"ontology missing {section}.{name}")
    entry = ont[section][name]
    if "lifecycle" not in entry:
        raise KeyError(f"{name}: lifecycle required")
    assert entry["id"] == fid


# ── independent oracle ≡ pipeline (random series) ────────────────────────────

def test_oracle_matches_pipeline_production_swings():
    k = _swing_k()
    raw = _synthetic(500)
    pipe = _pipeline_structure(raw)
    ora = oracle_from_ohlcv(raw, k=k)

    prod_cols = [
        "swing_high",
        "swing_low",
        "last_swing_high_price",
        "last_swing_low_price",
        "higher_high",
        "lower_low",
        "break_of_structure",
        "liquidity_sweep",
    ]
    assert_frame_close(pipe, ora, prod_cols)


def test_oracle_matches_pipeline_centered_batch_identity():
    k = _swing_k()
    raw = _synthetic(400)
    pipe = _pipeline_structure(raw)
    ora = oracle_from_ohlcv(raw, k=k)
    assert_frame_close(
        pipe,
        ora,
        [
            "swing_high_centered_batch",
            "swing_low_centered_batch",
            "last_swing_high_price_centered_batch",
            "last_swing_low_price_centered_batch",
        ],
    )


def test_causal_is_centered_shifted_by_k():
    """Contract identity: production flag == centered.shift(k).fillna(0)."""
    k = _swing_k()
    raw = _synthetic(300)
    ora = oracle_from_ohlcv(raw, k=k)
    sh = ora["swing_high_centered_batch"].shift(k).fillna(0).astype(np.int8)
    sl = ora["swing_low_centered_batch"].shift(k).fillna(0).astype(np.int8)
    np.testing.assert_array_equal(ora["swing_high"].to_numpy(), sh.to_numpy())
    np.testing.assert_array_equal(ora["swing_low"].to_numpy(), sl.to_numpy())


def test_oracle_prefix_invariance_interior():
    """Causal publication: prefix run matches full run on safe interior."""
    k = _swing_k()
    raw = _synthetic(800)
    full = oracle_from_ohlcv(raw, k=k)
    prefix_n = 500
    pref = oracle_from_ohlcv(raw.head(prefix_n), k=k)
    for col in (
        "swing_high",
        "swing_low",
        "liquidity_sweep",
        "higher_high",
        "lower_low",
        "break_of_structure",
    ):
        a = pref[col].iloc[k : prefix_n - k].to_numpy()
        b = full[col].iloc[k : prefix_n - k].to_numpy()
        assert np.array_equal(a, b), f"prefix variance on oracle col {col}"


# ── synthetic scenarios (oracle-expected, then pipeline check) ───────────────

def _scenario_frame(k: int) -> tuple[pd.DataFrame, dict]:
    """Hand-built path with a clear swing high, buy-side sweep, then bullish BOS.

    Layout (k must be production swing_window, typically 2):
      - flat base ~100
      - swing HIGH pivot at index P (high=110), neighbors strictly lower
      - after causal delay (P+k), last_swing_high_price publishes 110
      - SWEEP bar: high>110, close<=110  → liquidity_sweep=+1
      - later BOS bar: close>110         → break_of_structure=+1
      - swing LOW pivot for non-identical high/low flags
    """
    n = 100
    base = 100.0
    # Gentle unique slope so flat plateaus do not mark EVERY bar as a pivot
    # (constant highs → high[j]==roll_max for all j → all swing flags=1 → pipeline guard).
    t = np.arange(n, dtype=float)
    high = base + 0.4 + 0.001 * t
    low = base - 0.4 + 0.001 * t
    open_ = base + 0.001 * t
    close = base + 0.001 * t

    # Pivot high — need k bars of lower highs on each side for centered confirm
    p_hi = 25
    high[p_hi] = 110.0
    open_[p_hi] = 100.0
    close[p_hi] = 101.0
    low[p_hi] = 99.5
    for j in range(1, k + 1):
        high[p_hi - j] = 100.5
        high[p_hi + j] = 100.5

    # Pivot low (ensures swing_high ≠ swing_low as series)
    p_lo = 45
    low[p_lo] = 90.0
    open_[p_lo] = 100.0
    close[p_lo] = 99.0
    high[p_lo] = 100.5
    for j in range(1, k + 1):
        low[p_lo - j] = 99.5
        low[p_lo + j] = 99.5

    # First bar where causal last_high is published: p_hi + k
    # First bar where ref_high (shift 1) is 110: p_hi + k + 1
    confirm_hi = p_hi + k
    first_ref = confirm_hi + 1

    # Buy-side sweep: trade through 110, close back inside
    sweep_i = first_ref + 2
    assert sweep_i < p_lo - k - 2, "sweep must be before low pivot confuses refs"
    high[sweep_i] = 112.0
    low[sweep_i] = 100.0
    open_[sweep_i] = 101.0
    close[sweep_i] = 109.0  # <= 110

    # Bullish BOS: accept above 110 on the close
    bos_i = first_ref + 5
    assert bos_i < p_lo - k - 2
    high[bos_i] = 115.0
    low[bos_i] = 108.0
    open_[bos_i] = 109.0
    close[bos_i] = 114.0  # > 110

    ts = [datetime(2024, 5, 1) + timedelta(minutes=15 * i) for i in range(n)]
    df = pd.DataFrame(
        {
            "timestamp": ts,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": np.full(n, 1000.0),
        }
    )
    meta = {
        "k": k,
        "pivot_high_i": p_hi,
        "pivot_low_i": p_lo,
        "confirm_high_i": confirm_hi,
        "sweep_i": sweep_i,
        "bos_i": bos_i,
        "pivot_high_price": 110.0,
        "pivot_low_price": 90.0,
    }
    return df, meta


def test_scenario_pivot_publishes_after_k_delay():
    k = _swing_k()
    df, m = _scenario_frame(k)
    ora = oracle_from_ohlcv(df, k=k)

    # Centered flag at pivot
    assert int(ora["swing_high_centered_batch"].iloc[m["pivot_high_i"]]) == 1
    # Production flag only after delay
    assert int(ora["swing_high"].iloc[m["pivot_high_i"]]) == 0
    assert int(ora["swing_high"].iloc[m["confirm_high_i"]]) == 1
    # Price published at confirm
    assert ora["last_swing_high_price"].iloc[m["confirm_high_i"]] == pytest.approx(
        m["pivot_high_price"]
    )


def test_scenario_buy_side_sweep_and_bullish_bos():
    k = _swing_k()
    df, m = _scenario_frame(k)
    ora = oracle_from_ohlcv(df, k=k)

    assert int(ora["liquidity_sweep"].iloc[m["sweep_i"]]) == 1, (
        "buy-side sweep: high>ref and close<=ref"
    )
    assert int(ora["break_of_structure"].iloc[m["sweep_i"]]) == 0, (
        "sweep bar must not also be same-side BOS"
    )
    assert int(ora["break_of_structure"].iloc[m["bos_i"]]) == 1
    assert int(ora["liquidity_sweep"].iloc[m["bos_i"]]) == 0, (
        "BOS bar closes outside — not a sweep"
    )


def test_scenario_pipeline_matches_oracle_events():
    """Pipeline must emit the same sweep/BOS events as the independent oracle."""
    k = _swing_k()
    df, m = _scenario_frame(k)
    ora = oracle_from_ohlcv(df, k=k)
    pipe = _pipeline_structure(df)

    assert_frame_close(
        pipe,
        ora,
        [
            "swing_high",
            "swing_low",
            "last_swing_high_price",
            "last_swing_low_price",
            "liquidity_sweep",
            "break_of_structure",
            "higher_high",
            "lower_low",
        ],
    )
    assert int(pipe["liquidity_sweep"].iloc[m["sweep_i"]]) == 1
    assert int(pipe["break_of_structure"].iloc[m["bos_i"]]) == 1


def test_scenario_sell_side_sweep():
    """Mirror: undercut prior swing low, close back above → liquidity_sweep=-1."""
    k = _swing_k()
    n = 80
    base = 100.0
    t = np.arange(n, dtype=float)
    high = base + 0.4 + 0.001 * t
    low = base - 0.4 + 0.001 * t
    open_ = base + 0.001 * t
    close = base + 0.001 * t

    # First establish a swing HIGH so high/low flags diverge
    p_hi = 15
    high[p_hi] = 108.0
    for j in range(1, k + 1):
        high[p_hi - j] = 100.5
        high[p_hi + j] = 100.5

    p_lo = 30
    low[p_lo] = 92.0
    close[p_lo] = 99.0
    for j in range(1, k + 1):
        low[p_lo - j] = 99.5
        low[p_lo + j] = 99.5

    confirm_lo = p_lo + k
    first_ref = confirm_lo + 1
    sweep_i = first_ref + 2
    low[sweep_i] = 90.0
    high[sweep_i] = 100.0
    open_[sweep_i] = 98.0
    close[sweep_i] = 93.0  # >= 92

    ts = [datetime(2024, 6, 1) + timedelta(minutes=15 * i) for i in range(n)]
    df = pd.DataFrame(
        {
            "timestamp": ts,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": np.full(n, 1000.0),
        }
    )
    ora = oracle_from_ohlcv(df, k=k)
    pipe = _pipeline_structure(df)
    assert int(ora["liquidity_sweep"].iloc[sweep_i]) == -1
    assert int(pipe["liquidity_sweep"].iloc[sweep_i]) == -1
    assert int(pipe["break_of_structure"].iloc[sweep_i]) == 0


def test_oracle_requires_explicit_k():
    with pytest.raises(ValueError, match="required"):
        fc1a_oracle([1.0, 2.0, 3.0], [1.0, 2.0, 3.0], [1.0, 2.0, 3.0], k=None)  # type: ignore[arg-type]
