"""Episode-chain persistence helpers shared by sweep/state probes."""
from __future__ import annotations


def walk_episode_chain(episodes: list[dict], start_k: int, horizon: int) -> dict:
    """episodes[start_k] is the SWEEP episode itself. Walk forward summing `bars`."""
    cum = 0
    lag_disp = lag_exp = lag_range = None
    k = start_k + 1
    n = len(episodes)
    while k < n and cum < horizon:
        ep = episodes[k]
        cum += ep["bars"]
        if lag_disp is None and ep["state"] == "DISPLACEMENT":
            lag_disp = cum
        elif lag_disp is not None and lag_exp is None and ep["state"] == "EXPANSION":
            lag_exp = cum
        if ep["state"] == "RANGE":
            lag_range = cum
            break  # BOUNDARY: stop here, never walk past a RANGE episode.
        if ep.get("right_censored"):
            break
        k += 1
    reached_progress = lag_disp is not None
    return {
        "reached_displacement": lag_disp is not None and lag_disp <= horizon,
        "lag_to_displacement": lag_disp if (lag_disp is not None and lag_disp <= horizon) else None,
        "reached_expansion": lag_exp is not None and lag_exp <= horizon,
        "lag_to_expansion": lag_exp if (lag_exp is not None and lag_exp <= horizon) else None,
        "reverted_never_progressed": (lag_range is not None and lag_range <= horizon
                                       and not reached_progress),
        "lag_to_reversion": (lag_range if (lag_range is not None and lag_range <= horizon
                                            and not reached_progress) else None),
        "right_censored_in_window": k < n and bool(episodes[k].get("right_censored")) and cum <= horizon,
    }

