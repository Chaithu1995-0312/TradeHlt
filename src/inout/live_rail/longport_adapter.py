"""LongPort reservation. Zero repo presence — do not pretend an SDK is wired."""
from __future__ import annotations

from typing import AsyncIterator

from inout.live_rail.types import NormalizedTick, VenueName


class LongPortAdapter:
    """Interface reservation only. Implement only after an authorized adapter PR."""

    name = VenueName.LONGPORT

    async def start(self) -> None:
        raise NotImplementedError(
            "LongPortAdapter is a stub. Do not select venue=longport. "
            "Implement only after an authorized adapter PR + clock declaration."
        )

    async def stop(self) -> None:
        return None

    async def ticks(self) -> AsyncIterator[NormalizedTick]:
        raise NotImplementedError("LongPortAdapter is a stub")
        if False:  # pragma: no cover — keep this an AsyncIterator
            yield None  # type: ignore[misc]
