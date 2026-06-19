"""
regime_engine — volatility-regime label at entry via reused `RegimeLabeler`.

Sentinel discipline (must not be collapsed):
  • C/N/E    — a real label
  • None     — INSUFFICIENT history (< tercile_window trailing bars)
  • "UNKNOWN"— the labeler raised (degenerate/failed computation)
"""
from __future__ import annotations

import logging

from interpreters.regime_observer import RegimeLabeler  # type: ignore

logger = logging.getLogger("mt5_analytics.regime_engine")


def partial(window, entry_index: int, *, atr_period: int, tercile_window: int) -> dict:
    try:
        labeler = RegimeLabeler(atr_period=atr_period, tercile_window=tercile_window)
        regime = labeler.label_at(window, entry_index)   # None when insufficient history
    except Exception as exc:  # noqa: BLE001
        logger.debug("regime_engine: label failed (%s)", exc)
        return {"regime": "UNKNOWN"}
    return {"regime": regime}
