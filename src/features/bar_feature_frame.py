"""Canonical per-bar features for the CRT engine's trade intent (EPIC-84 A3b).

`CRTEngine.process_candle(..., bar_features=...)` needs, for every bar, the three canonical
features its trade-intent reads at RETEST and cannot compute itself:

    sweep_detected       canonical slot 20 (the pipeline's own liquidity sweep fired on the bar)
    candles_since_sweep  canonical slot 35, FM-065 (bars since that sweep)
    momentum_score       canonical slot 12 (signed close-to-close move / ATR)

This module is the ONE place that turns a FeaturePipeline frame into that per-bar mapping
("run the layer, never re-implement it"): the backtest, the research adapters and the scripts all
use it. A bar with no feature row (e.g. inside the pipeline warm-up) returns None, and the
engine then rejects a RETEST on that bar (user rule D7) -- never a substituted value.
"""
from __future__ import annotations

from typing import Mapping, Optional

from features.feature_schema import FEATURE_INDEX_MAP

#: The canonical keys the CRT engine's intent contract takes from the bar (order is irrelevant).
BAR_FEATURE_KEYS: tuple[str, ...] = ("sweep_detected", "candles_since_sweep", "momentum_score")
_IDX = {k: FEATURE_INDEX_MAP[k] for k in BAR_FEATURE_KEYS}
_TS_FMT = "%Y-%m-%d %H:%M:%S"


class BarFeatureFrame:
    """Timestamp -> the bar's canonical intent features, over one FeaturePipeline frame."""

    def __init__(self, feature_vectors, feature_ts_to_idx: Mapping[str, int]):
        if feature_vectors is None:
            raise ValueError("BarFeatureFrame needs a built feature frame (got None)")
        self._vectors = feature_vectors
        self._ts_to_idx = feature_ts_to_idx

    @classmethod
    def from_enriched(cls, enriched_df, feature_vectors) -> "BarFeatureFrame":
        """From FeaturePipeline.run()'s (enriched_df, feature_vectors) pair."""
        import pandas as pd

        ts = pd.to_datetime(enriched_df["timestamp"])
        return cls(feature_vectors, {t.strftime(_TS_FMT): i for i, t in enumerate(ts)})

    @classmethod
    def from_csv(cls, csv_path: str) -> "BarFeatureFrame":
        """Build the frame from an OHLCV CSV exactly as BacktestRunner does (same header
        normalisation, same date+time merge, same schema check, same FeaturePipeline)."""
        import pandas as pd

        from data_ingestion.ohlcv_schema import require_ohlcv_columns
        from features.feature_pipeline import FeaturePipeline

        raw_df = pd.read_csv(csv_path)
        raw_df.columns = [c.strip().lower() for c in raw_df.columns]
        if "timestamp" not in raw_df.columns:
            if "date" in raw_df.columns and "time" in raw_df.columns:
                raw_df["timestamp"] = raw_df["date"].astype(str) + " " + raw_df["time"].astype(str)
            elif "date" in raw_df.columns:
                raw_df["timestamp"] = raw_df["date"]
        require_ohlcv_columns(raw_df.columns, source=f"BarFeatureFrame {csv_path}")
        enriched_df, vectors = FeaturePipeline(raw_df).run()
        return cls.from_enriched(enriched_df, vectors)

    @classmethod
    def from_ohlcv_df(cls, df) -> "BarFeatureFrame":
        """Build the frame from an OHLCV DataFrame the caller already loaded (columns
        timestamp/open/high/low/close/volume, any case). Same FeaturePipeline as every path."""
        import pandas as pd

        from features.feature_pipeline import FeaturePipeline

        raw = df.copy()
        raw.columns = [str(c).strip().lower() for c in raw.columns]
        raw["timestamp"] = pd.to_datetime(raw["timestamp"]).dt.strftime(_TS_FMT)
        enriched_df, vectors = FeaturePipeline(raw).run()
        return cls.from_enriched(enriched_df, vectors)

    @classmethod
    def from_candles(cls, candles) -> "BarFeatureFrame":
        """Build the frame from the SAME candle sequence a caller feeds the engine (scripts that
        hold a candle list rather than a CSV path). Same FeaturePipeline as every other path."""
        import pandas as pd

        from features.feature_pipeline import FeaturePipeline

        rows = [
            {"timestamp": c.timestamp.strftime(_TS_FMT), "open": c.open, "high": c.high,
             "low": c.low, "close": c.close, "volume": c.volume}
            for c in candles
        ]
        if not rows:
            raise ValueError("BarFeatureFrame.from_candles needs at least one candle")
        enriched_df, vectors = FeaturePipeline(pd.DataFrame(rows)).run()
        return cls.from_enriched(enriched_df, vectors)

    def for_timestamp(self, ts) -> Optional[dict]:
        idx = self._ts_to_idx.get(ts.strftime(_TS_FMT), -1)
        if idx < 0:
            return None
        row = self._vectors[idx]
        return {k: row[i] for k, i in _IDX.items()}

    def for_candle(self, candle) -> Optional[dict]:
        """The engine's `bar_features` for this candle (None = no feature row for the bar)."""
        return self.for_timestamp(candle.timestamp)
