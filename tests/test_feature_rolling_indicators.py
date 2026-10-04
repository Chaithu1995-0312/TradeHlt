"""Ontology-authoritative parity floor for the 11 standard rolling indicators.

Mirrors the discipline of test_candle_math.py / test_derived_math.py:
  pure-pandas reference columns vs FeaturePipeline output, config periods
  read strictly from production feature_pipeline (no silent defaults).

Covered (non-swing):
  FM-040 true_range
  FM-041 atr
  FM-042 rsi_14
  FM-043 ema_fast
  FM-044 ema_slow
  FM-047 macd_line
  FM-048 macd_signal
  FM-049 macd_hist_raw
  FM-053 macd_hist_z
  FM-050 volatility_regime
  FM-062 volume_ratio

Swing / last_swing (FM-045/046/066/067) and adaptive volume_spike (FM-063)
are intentionally out of this file (complex / separate lifecycle).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from config_layer.production_config import get_prod_section
from features.feature_pipeline import FeaturePipeline
from features.registry import load_ontology


# The 11 indicators this file owns.
_ROLLING_TARGETS = (
    "true_range",
    "atr",
    "rsi_14",
    "ema_fast",
    "ema_slow",
    "macd_line",
    "macd_signal",
    "macd_hist_raw",
    "macd_hist_z",
    "volatility_regime",
    "volume_ratio",
)


def _fp_cfg() -> dict:
    return get_prod_section("feature_pipeline")


def _require_cfg(cfg: dict, key: str):
    if key not in cfg:
        raise KeyError(f"feature_pipeline.{key} missing — no silent default")
    return cfg[key]


def _rolling_entry(name: str) -> dict:
    ont = load_ontology()
    if "rolling_indicators" not in ont:
        raise KeyError("ontology missing rolling_indicators section")
    section = ont["rolling_indicators"]
    if name not in section:
        raise KeyError(f"ontology rolling_indicators missing {name!r}")
    entry = section[name]
    if "lifecycle" not in entry:
        raise KeyError(f"{name}: missing required lifecycle")
    return entry


def _synthetic(n: int = 600, seed: int = 11) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    ts = pd.date_range("2024-01-01", periods=n, freq="15min")
    close = 50 + np.cumsum(rng.normal(0, 0.4, n))
    # keep prices positive
    close = np.maximum(close, 5.0)
    open_ = close + rng.normal(0, 0.08, n)
    high = np.maximum(open_, close) + rng.uniform(0.05, 0.6, n)
    low = np.minimum(open_, close) - rng.uniform(0.05, 0.6, n)
    volume = rng.uniform(100, 3000, n)
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


def _pipeline_pre_finalize(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Full stages through normalization + canonical vol/ema (no finalize)."""
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
    return fp.df, cfg


# ── pure-pandas references (mirror ontology formulas) ────────────────────────

def _ref_true_range(df: pd.DataFrame) -> pd.Series:
    # Must mirror pipeline's np.maximum (NaN-propagating), NOT pandas max(skipna=True).
    tr1 = df["high"] - df["low"]
    tr2 = (df["high"] - df["close"].shift(1)).abs()
    tr3 = (df["low"] - df["close"].shift(1)).abs()
    return pd.Series(
        np.maximum(tr1.to_numpy(), np.maximum(tr2.to_numpy(), tr3.to_numpy())),
        index=df.index,
    )


def _ref_atr(df: pd.DataFrame, period: int) -> pd.Series:
    atr_raw = _ref_true_range(df).rolling(period).mean()
    return np.where(df["close"] > 0, atr_raw / df["close"], 0.0)


def _ref_rsi(df: pd.DataFrame, period: int) -> pd.Series:
    delta = df["close"].diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / (loss + 1e-9)
    return (100.0 - (100.0 / (1.0 + rs))).clip(0.0, 100.0)


def _ref_ema(close: pd.Series, span: int) -> pd.Series:
    return close.ewm(span=span, adjust=False).mean()


def _ref_macd(df: pd.DataFrame, fast: int, slow: int, signal: int):
    line = _ref_ema(df["close"], fast) - _ref_ema(df["close"], slow)
    sig = line.ewm(span=signal, adjust=False).mean()
    hist = line - sig
    return line, sig, hist


def _ref_macd_hist_z(hist: pd.Series, window: int) -> pd.Series:
    mean = hist.rolling(window).mean()
    std = hist.rolling(window).std(ddof=1)
    return (hist - mean) / (std + 1e-9)


def _ref_volatility_regime(
    df: pd.DataFrame, atr_period: int, roll_n: int, terc_lo: float, terc_hi: float
) -> pd.Series:
    atr_abs = _ref_true_range(df).rolling(atr_period).mean()
    pct = atr_abs.rolling(roll_n, min_periods=1).rank(pct=True)
    return np.select(
        [pct < terc_lo, pct < terc_hi],
        [0, 1],
        default=2,
    ).astype(np.int8)


def _ref_volume_ratio(df: pd.DataFrame, window: int) -> pd.Series:
    raw = pd.to_numeric(df["volume"], errors="coerce")
    ma = raw.rolling(window).mean()
    return np.where(ma > 0, raw / ma, 1.0)


# ── ontology lifecycle presence ──────────────────────────────────────────────

@pytest.mark.parametrize("name", _ROLLING_TARGETS)
def test_rolling_indicator_declared_in_ontology(name: str):
    entry = _rolling_entry(name)
    assert entry["lifecycle"]  # non-empty, no silent omit
    assert entry["id"].startswith("FM-")


# ── parity battery ───────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def piped():
    df = _synthetic(600)
    out, cfg = _pipeline_pre_finalize(df)
    return out, cfg, df


def test_true_range_parity(piped):
    out, _cfg, raw = piped
    ref = _ref_true_range(raw)
    # first row has no prev_close → both NaN or equal after
    mask = ref.notna() & out["true_range"].notna()
    np.testing.assert_allclose(
        out.loc[mask, "true_range"].to_numpy(dtype=float),
        ref.loc[mask].to_numpy(dtype=float),
        rtol=1e-5,
        atol=1e-6,
    )


def test_atr_parity(piped):
    """FM-041: atr_14_raw / close (close-relative SMA of true_range)."""
    out, cfg, raw = piped
    period = int(_require_cfg(cfg, "atr_period"))
    ref = pd.Series(_ref_atr(raw, period), index=raw.index)
    mask = ref.notna() & out["atr"].notna()
    np.testing.assert_allclose(
        out.loc[mask, "atr"].to_numpy(dtype=float),
        ref.loc[mask].to_numpy(dtype=float),
        rtol=1e-5,
        atol=1e-6,
    )


def test_rsi_14_parity(piped):
    out, cfg, raw = piped
    period = int(_require_cfg(cfg, "rsi_period"))
    ref = _ref_rsi(raw, period)
    mask = ref.notna() & out["rsi_14"].notna()
    np.testing.assert_allclose(
        out.loc[mask, "rsi_14"].to_numpy(dtype=float),
        ref.loc[mask].to_numpy(dtype=float),
        rtol=1e-5,
        atol=1e-6,
    )


def test_ema_fast_slow_parity(piped):
    out, cfg, raw = piped
    fast_span = int(_require_cfg(cfg, "ema_fast_span"))
    slow_span = int(_require_cfg(cfg, "ema_slow_span"))
    ref_f = _ref_ema(raw["close"], fast_span)
    ref_s = _ref_ema(raw["close"], slow_span)
    np.testing.assert_allclose(
        out["ema_fast"].to_numpy(dtype=float),
        ref_f.to_numpy(dtype=float),
        rtol=1e-5,
        atol=1e-6,
    )
    np.testing.assert_allclose(
        out["ema_slow"].to_numpy(dtype=float),
        ref_s.to_numpy(dtype=float),
        rtol=1e-5,
        atol=1e-6,
    )


def test_macd_line_signal_hist_raw_parity(piped):
    out, cfg, raw = piped
    fast = int(_require_cfg(cfg, "macd_fast"))
    slow = int(_require_cfg(cfg, "macd_slow"))
    signal = int(_require_cfg(cfg, "macd_signal"))
    line, sig, hist = _ref_macd(raw, fast, slow, signal)
    np.testing.assert_allclose(
        out["macd_line"].to_numpy(dtype=float),
        line.to_numpy(dtype=float),
        rtol=1e-5,
        atol=1e-6,
    )
    np.testing.assert_allclose(
        out["macd_signal"].to_numpy(dtype=float),
        sig.to_numpy(dtype=float),
        rtol=1e-5,
        atol=1e-6,
    )
    # macd_hist_raw is written before z-score; column name is macd_hist_raw
    assert "macd_hist_raw" in out.columns
    np.testing.assert_allclose(
        out["macd_hist_raw"].to_numpy(dtype=float),
        hist.to_numpy(dtype=float),
        rtol=1e-5,
        atol=1e-6,
    )


def test_macd_hist_z_parity(piped):
    """FM-053: rolling z-score of macd_hist_raw (NOT overwriting the raw column)."""
    out, cfg, raw = piped
    zwin = int(_require_cfg(cfg, "zscore_window"))
    fast = int(_require_cfg(cfg, "macd_fast"))
    slow = int(_require_cfg(cfg, "macd_slow"))
    signal = int(_require_cfg(cfg, "macd_signal"))
    _line, _sig, hist = _ref_macd(raw, fast, slow, signal)
    ref_z = _ref_macd_hist_z(hist, zwin)
    mask = ref_z.notna() & out["macd_hist_z"].notna()
    np.testing.assert_allclose(
        out.loc[mask, "macd_hist_z"].to_numpy(dtype=float),
        ref_z.loc[mask].to_numpy(dtype=float),
        rtol=1e-5,
        atol=1e-6,
    )


def test_volatility_regime_parity(piped):
    out, cfg, raw = piped
    atr_p = int(_require_cfg(cfg, "atr_period"))
    roll_n = int(_require_cfg(cfg, "volatility_percentile_window"))
    terc_lo = float(_require_cfg(cfg, "volatility_tercile_low"))
    terc_hi = float(_require_cfg(cfg, "volatility_tercile_high"))
    ref = pd.Series(
        _ref_volatility_regime(raw, atr_p, roll_n, terc_lo, terc_hi),
        index=raw.index,
    )
    # atr warmup: first atr_period-1 rows may be NaN in absolute atr → still ranked
    # with min_periods=1 on rank; match pipeline on all rows where both finite
    mask = out["volatility_regime"].notna()
    np.testing.assert_array_equal(
        out.loc[mask, "volatility_regime"].astype(np.int8).to_numpy(),
        ref.loc[mask].astype(np.int8).to_numpy(),
    )
    domain = set(int(s["value"]) for s in _rolling_entry("volatility_regime")["states"])
    assert set(np.unique(out["volatility_regime"].dropna().astype(int))) <= domain


def test_volume_ratio_parity(piped):
    out, cfg, raw = piped
    window = int(_require_cfg(cfg, "volume_ma_window"))
    ref = pd.Series(_ref_volume_ratio(raw, window), index=raw.index)
    mask = np.isfinite(ref.to_numpy(dtype=float)) & out["volume_ratio"].notna()
    np.testing.assert_allclose(
        out.loc[mask, "volume_ratio"].to_numpy(dtype=float),
        ref.loc[mask].to_numpy(dtype=float),
        rtol=1e-5,
        atol=1e-6,
    )


def test_full_run_keeps_rolling_parity_on_surviving_rows():
    """After finalize(), timestamp-aligned rows still match pure-pandas refs."""
    raw = _synthetic(600)
    cfg = _fp_cfg()
    piped_df, _ = FeaturePipeline(raw, cfg=cfg).run()

    period = int(_require_cfg(cfg, "atr_period"))
    ref_atr = pd.Series(_ref_atr(raw, period), index=raw.index)
    # align by original integer index preserved only if finalize resets — use timestamp
    raw_ts = raw.set_index("timestamp")
    ref_atr.index = raw["timestamp"]
    joined = piped_df.set_index("timestamp")
    common = joined.index.intersection(ref_atr.dropna().index)
    assert len(common) > 100
    np.testing.assert_allclose(
        joined.loc[common, "atr"].to_numpy(dtype=float),
        ref_atr.loc[common].to_numpy(dtype=float),
        rtol=1e-5,
        atol=1e-6,
    )
