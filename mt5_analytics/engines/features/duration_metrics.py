"""duration_metrics — holding-time partial (deterministic, no candles needed)."""
from __future__ import annotations

_M15_SECONDS = 900


def partial(episode) -> dict:
    secs = float(episode.duration_seconds)
    return {
        "duration_minutes": round(secs / 60.0, 2),
        "duration_hours": round(secs / 3600.0, 4),
        "bars_held": int(secs // _M15_SECONDS),
    }
