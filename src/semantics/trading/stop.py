"""TRS-05 stop. The price is ExecutionEngine.stop_price. This module does not recompute it."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from config_layer.crt_engine_v2 import EngineState, ExecutionEngine

from semantics.identity import parameterization_id

STOP = "TRS-05"


@dataclass(frozen=True)
class Stop:
    """TRS-05. buffer_atr is the config value the authority multiplied, not a second formula."""

    concept_id: str
    parameterization_id: str
    available_at: int
    price: float
    anchor: str
    buffer_atr: float


def place_stop(
    config,
    state: EngineState,
    *,
    sl_anchor: str,
    target_policy: str,
    plan_bar: int,
) -> Optional[Stop]:
    """None when stop_price cannot derive a stop. target_policy is required by the
    engine constructor and is not read by stop_price; the caller supplies it."""
    engine = ExecutionEngine(config, sl_anchor=sl_anchor, target_policy=target_policy)
    price = engine.stop_price(state)
    if price is None:
        return None
    buffer = float(config.sl_atr_buffer)
    pid = parameterization_id(STOP, {"anchor": sl_anchor, "buffer_atr": buffer}, ("anchor", "buffer_atr"))
    available = plan_bar
    if state.displacement_candle is not None:
        available = max(available, int(state.displacement_candle.index))
    sweep = state.sweep_event
    if sweep is not None and sweep.candle is not None:
        available = max(available, int(sweep.candle.index))
    return Stop(STOP, pid, available, float(price), sl_anchor, buffer)
