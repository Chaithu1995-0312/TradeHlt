"""
session_metrics — trading-session band from the entry UTC hour.

Bands are `_require()`d from `config/analytics.json` (no silent defaults). A trade in both
the London and NY windows is OVERLAP; otherwise the single owning session, else OFF.
"""
from __future__ import annotations

from datetime import datetime

from ...analytics_config import _require


def _in_band(hour: int, start: int, end: int) -> bool:
    """Half-open [start, end) membership; wraps past midnight when start > end."""
    if start <= end:
        return start <= hour < end
    return hour >= start or hour < end


def _classify(hour: int, sessions: dict) -> str:
    in_london = _in_band(hour, int(_require(sessions, "london_start")),
                         int(_require(sessions, "london_end")))
    in_ny = _in_band(hour, int(_require(sessions, "ny_start")),
                    int(_require(sessions, "ny_end")))
    in_asia = _in_band(hour, int(_require(sessions, "asia_start")),
                      int(_require(sessions, "asia_end")))
    if in_london and in_ny:
        return "OVERLAP"
    if in_london:
        return "LONDON"
    if in_ny:
        return "NY"
    if in_asia:
        return "ASIA"
    return "OFF"


def partial(episode, cfg: dict) -> dict:
    dt = datetime.fromisoformat(episode.entry_time.replace("Z", "+00:00"))
    sessions = _require(cfg, "sessions")
    return {
        "entry_hour": dt.hour,
        "weekday": dt.strftime("%A"),
        "session": _classify(dt.hour, sessions),
    }
