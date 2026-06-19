"""
feature_engine — orchestrator ONLY (PositionEpisode + bar window → one FeatureRecord).

Pure: it never touches MT5, never reads/writes files, never aggregates. It computes the
risk basis once (SL distance if known, else ATR-at-entry), calls each pure sub-engine for
its partial dict, and hands them to `feature_record_builder`. The bar `window` + its
`entry_index` are supplied by the caller (a `CandleProvider`, wired in Phase 4) so this
stays deterministically testable with synthetic candles and no live terminal.
"""
from __future__ import annotations

from research.indicators import atr  # type: ignore

from ...analytics_config import _require, load_config
from ..entry_tracker import partial as entry_partial
from . import (
    duration_metrics,
    mfe_mae_engine,
    regime_engine,
    rr_engine,
    session_metrics,
)
from .feature_record_builder import build


def compute(
    episode,
    window,
    entry_index: int,
    *,
    sl_price: "float | None" = None,
    cfg: "dict | None" = None,
) -> dict:
    """Build one FeatureRecord for `episode` over the supplied bar window."""
    cfg = cfg or load_config()
    atr_period = int(_require(cfg, "atr_period"))
    tercile_window = int(_require(cfg, "regime_tercile_window"))

    # Risk basis: SL distance if known, else ATR over bars up to & including entry.
    atr_value = atr(list(window)[: entry_index + 1], atr_period)
    risk = rr_engine.risk_distance(episode, sl_price, atr_value=atr_value)

    partials = [
        rr_engine.partial(episode, risk),
        mfe_mae_engine.partial(episode, window, entry_index, risk),
        duration_metrics.partial(episode),
        session_metrics.partial(episode, cfg),
        regime_engine.partial(
            window, entry_index, atr_period=atr_period, tercile_window=tercile_window
        ),
        entry_partial(episode, window, entry_index),
    ]
    return build(episode, partials)
