"""Reconnect backoff + fail-closed circuit breaker for live-rail I/O."""
from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass

from utils.logging_config import get_flow_logger

logger = get_flow_logger("LIVE_RAIL")


@dataclass
class ReconnectPolicy:
    """Exponential backoff + jitter. Constructed from live_rail.reconnect — no silent default."""

    base_delay_s: float
    max_delay_s: float
    max_attempts: int

    async def sleep(self, attempt: int) -> None:
        if attempt >= self.max_attempts:
            raise RuntimeError(
                f"ReconnectPolicy: attempt {attempt} >= max_attempts={self.max_attempts} "
                "— fail-closed (do not invent ticks, do not place orders)"
            )
        delay = min(self.max_delay_s, self.base_delay_s * (2 ** attempt))
        delay = delay * (0.5 + random.random())
        logger.warning("LIVE_RAIL: reconnect sleep %.2fs (attempt=%d)", delay, attempt)
        await asyncio.sleep(delay)


class CircuitBreaker:
    """Shape matches docs/reference/example-service.py _CircuitBreaker.

    POLICY DIVERGENCE (intentional): example-service fail-OPENs advisory I/O.
    Live-rail market data and order I/O fail-CLOSED when open — callers must
    not emit ticks or submit orders. Kill-switch *file read* remains fail-open
    inside UltronRiskGate._load_ks_state (do not change that here).
    """

    def __init__(self, fail_count_disable: int) -> None:
        self._fail_count_disable = fail_count_disable
        self._fails = 0
        self._open = False

    def is_open(self) -> bool:
        return self._open

    def record_failure(self) -> None:
        self._fails += 1
        if self._fails > self._fail_count_disable and not self._open:
            self._open = True
            logger.error(
                "LIVE_RAIL: circuit OPEN after %d failures — fail-closed", self._fails
            )

    def record_success(self) -> None:
        if self._fails or self._open:
            logger.info("LIVE_RAIL: circuit reset after recovery")
        self._fails = 0
        self._open = False
