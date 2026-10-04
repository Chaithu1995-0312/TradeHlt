"""FM-063 volume_spike — adaptive series-level parity floor.

Ontology formula (rolling_indicators.volume_spike):
  volume_ratio > rolling(adaptive_window, min_periods=min_samples)
                 .quantile(percentile/100);
  where threshold is NaN, fall back to fixed_fallback → int8 {0,1}

Independent pure-pandas recompute vs FeaturePipeline.promote_volume_spike /
full run() output. Config keys read strictly from production feature_pipeline.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from config_layer.production_config import get_prod_section
from features.feature_pipeline import FeaturePipeline
from features.registry import load_ontology


def _fp_cfg() -> dict:
    return get_prod_section("feature_pipeline")


def _require(cfg: dict, key: str):
    if key not in cfg:
        raise KeyError(f"feature_pipeline.{key} required (no silent default)")
    return cfg[key]


def _ontology_volume_spike() -> dict:
    ont = load_ontology()
    entry = ont["rolling_indicators"]["volume_spike"]
    if "lifecycle" not in entry:
        raise KeyError("volume_spike: lifecycle required")
    if entry["id"] != "FM-063":
        raise AssertionError(f"expected FM-063, got {entry['id']}")
    return entry


def _ref_volume_spike(volume_ratio: pd.Series, cfg: dict) -> pd.Series:
    window = int(_require(cfg, "volume_spike_adaptive_window"))
    min_samples = int(_require(cfg, "volume_spike_min_samples"))
    percentile = float(_require(cfg, "volume_spike_percentile"))
    fixed = float(_require(cfg, "volume_spike_fixed_fallback"))
    rolling_thresh = volume_ratio.rolling(
        window=window, min_periods=min_samples
    ).quantile(percentile / 100.0)
    threshold = rolling_thresh.where(rolling_thresh.notna(), fixed)
    return (volume_ratio > threshold).astype(np.int8)


def _synthetic(n: int = 600, seed: int = 63) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    ts = pd.date_range("2024-04-01", periods=n, freq="15min")
    close = 50 + np.cumsum(rng.normal(0, 0.3, n))
    close = np.maximum(close, 5.0)
    open_ = close + rng.normal(0, 0.05, n)
    high = np.maximum(open_, close) + rng.uniform(0.05, 0.5, n)
    low = np.minimum(open_, close) - rng.uniform(0.05, 0.5, n)
    # Volume with occasional spikes so adaptive threshold moves
    volume = rng.uniform(100, 800, n)
    volume[100:110] *= 4.0
    volume[300:305] *= 6.0
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


def test_volume_spike_ontology_declared():
    entry = _ontology_volume_spike()
    assert entry["lifecycle"]
    lineage = entry.get("lineage") or {}
    produced = str(entry.get("impl") or lineage.get("produced_by") or "")
    assert "promote_volume_spike" in produced


def test_adaptive_volume_spike_parity_promote_stage():
    """Parity on promote_volume_spike alone (volume_ratio already present)."""
    cfg = _fp_cfg()
    n = 200
    rng = np.random.default_rng(7)
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=n, freq="15min"),
            "open": np.full(n, 100.0),
            "high": np.full(n, 101.0),
            "low": np.full(n, 99.0),
            "close": np.full(n, 100.0),
            "volume": rng.uniform(100, 2000, n),
            "volume_ratio": rng.uniform(0.3, 3.0, n),
        }
    )
    # Seed fixed-threshold column (pipeline does this before promote)
    fixed = float(_require(cfg, "volume_spike_fixed_fallback"))
    df["volume_spike"] = (df["volume_ratio"] > fixed).astype(np.int8)

    fp = FeaturePipeline(df, cfg=cfg)
    # Input already has volume_ratio; only promote adaptive overwrite
    fp.df = df.copy()
    fp.promote_volume_spike()
    ref = _ref_volume_spike(df["volume_ratio"], cfg)
    np.testing.assert_array_equal(
        fp.df["volume_spike"].to_numpy(),
        ref.to_numpy(),
    )


def test_adaptive_volume_spike_parity_full_pipeline():
    """Full run(): final volume_spike matches pure-pandas adaptive formula."""
    cfg = _fp_cfg()
    raw = _synthetic(600)
    piped, _ = FeaturePipeline(raw, cfg=cfg).run()

    # Rebuild volume_ratio reference from source volume (same as pipeline)
    vol_win = int(_require(cfg, "volume_ma_window"))
    raw_vol = pd.to_numeric(raw["volume"], errors="coerce")
    ma = raw_vol.rolling(vol_win).mean()
    vol_ratio = pd.Series(
        np.where(ma > 0, raw_vol / ma, 1.0),
        index=raw.index,
    )
    ref_spike = _ref_volume_spike(vol_ratio, cfg)
    ref_spike.index = raw["timestamp"]

    joined = piped.set_index("timestamp")
    common = joined.index.intersection(ref_spike.dropna().index)
    # After finalize some early rows drop; still need substantial overlap
    assert len(common) > 100
    np.testing.assert_array_equal(
        joined.loc[common, "volume_spike"].astype(np.int8).to_numpy(),
        ref_spike.loc[common].astype(np.int8).to_numpy(),
    )


def test_volume_spike_domain():
    entry = _ontology_volume_spike()
    domain = {int(s["value"]) for s in entry["states"]}
    raw = _synthetic(400)
    piped, _ = FeaturePipeline(raw, cfg=_fp_cfg()).run()
    vals = set(int(v) for v in piped["volume_spike"].unique())
    assert vals <= domain
