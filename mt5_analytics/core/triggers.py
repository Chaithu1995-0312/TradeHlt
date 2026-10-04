"""triggers — pure predicates for the daemon loop (new-deal / new-M15-bar)."""
from __future__ import annotations


def has_new_deals(prev_count: int, cur_count: int) -> bool:
    return cur_count > prev_count


def is_new_m15_bar(last_bar_time: int, cur_bar_time: int) -> bool:
    """True when a new M15 bar has opened (tracked by time, NOT `minute % 15`)."""
    return cur_bar_time > last_bar_time
