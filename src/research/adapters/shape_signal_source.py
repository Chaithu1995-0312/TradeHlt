"""shape_signal_source.py — precompute MarketShape directional signals per bar (Program 11 / B1).

Like ProductionSpineSource: run the heavy FeaturePipeline + MarketShape classification ONCE per
instrument and cache it, so the research `Hypothesis.detect()` is a pure O(1) index lookup that
satisfies the no-lookahead / purity contract.

INDEX CONTRACT (load-bearing). The research runner assigns `c.index = i` = the 0-based CandleLoader
stream position, and `detect()` looks up by that index. This source builds the FeaturePipeline
input frame DIRECTLY FROM the same CandleLoader stream and carries `_pos` = stream position, so the
join from a pipeline row (FeaturePipeline drops ~78 warmup rows + resets the index) back to the
stream index is position-identical BY CONSTRUCTION — no timestamp parsing, no off-by-one.

Direction is the shape's DECLARED, non-fitted bias (frozen: Program 11 pre-registration §11a).
Non-directional shapes (Compression, DoubleSweepTrap, UNNAMED) emit nothing.
"""
from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

log = logging.getLogger("research.adapters.shape")

# directional coarse shape -> declared direction (FROZEN by the pre-registration; do not tune).
DIRECTION_MAP: dict[str, str] = {
    "BullishBreakoutExpansion": "long",
    "BearishBreakoutExpansion": "short",
    "BullishStructuralBreak": "long",
    "BearishStructuralBreak": "short",
    "SellSideLiquidityGrab": "long",     # stops below prior low grabbed & rejected → bullish
    "BuySideLiquidityGrab": "short",     # stops above prior high grabbed & rejected → bearish
}


@runtime_checkable
class ShapeSignalSourceProto(Protocol):
    def signals(self, instrument: str) -> dict[int, str]:
        ...


class ShapeSignalSource:
    """Classify every bar's MarketShape once per instrument; return {stream_index: direction}."""

    def __init__(self, classifier=None):
        self._clf = classifier                      # lazy: MarketShapeClassifier built on first use
        self._cache: dict[str, dict[int, str]] = {}

    def _classifier(self):
        if self._clf is None:
            from features.market_shape import MarketShapeClassifier
            self._clf = MarketShapeClassifier()
        return self._clf

    def _resolve_csv(self, instrument: str) -> str:
        if instrument == "XAUUSD":
            from data_ingestion.xauusd_phase1_candidate import guard_xauusd_csv_path
            return guard_xauusd_csv_path("data/XAUUSD_M15.csv", instrument)
        raise ValueError(f"ShapeSignalSource: Program 11 is XAUUSD-only, got {instrument!r}")

    def signals(self, instrument: str) -> dict[int, str]:
        if instrument not in self._cache:
            self._cache[instrument] = self._compute(instrument)
        return self._cache[instrument]

    def _compute(self, instrument: str) -> dict[int, str]:
        import pandas as pd
        from runtime.backtest_v2 import CandleLoader
        from features.feature_pipeline import FeaturePipeline

        csv_path = self._resolve_csv(instrument)
        candles = list(CandleLoader(csv_path, instrument).stream())
        n = len(candles)
        df_in = pd.DataFrame({
            "timestamp": [c.timestamp for c in candles],
            "open": [c.open for c in candles], "high": [c.high for c in candles],
            "low": [c.low for c in candles], "close": [c.close for c in candles],
            "volume": [c.volume for c in candles],
        })
        df_in["_pos"] = range(n)                    # == CandleLoader stream index == runner c.index
        feat_df, vectors = FeaturePipeline(df_in).run()
        if "_pos" not in feat_df.columns:
            raise RuntimeError("ShapeSignalSource: _pos did not survive FeaturePipeline.run()")
        pos = feat_df["_pos"].to_numpy()
        clf = self._classifier()

        out: dict[int, str] = {}
        for row_i in range(len(pos)):
            d = DIRECTION_MAP.get(clf.classify_vector(vectors[row_i]).name)
            if d is not None:
                out[int(pos[row_i])] = d
        log.info("ShapeSignalSource: %s -> %d directional shape signals (of %d bars)",
                 instrument, len(out), n)
        return out
