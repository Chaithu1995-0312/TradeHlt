"""
session_classifier.py — THE single owner of "what session is this?".

TWO CONCEPTS, ONE MODULE, DELIBERATELY DIFFERENT NAMES
------------------------------------------------------
The word "session" named two incompatible things in this repository, which is what made the
collision hard to see. They are both owned here, and they are NOT interchangeable:

1. `classify_session_feature(hour, cfg)` -> int
   The FM-052 canonical FEATURE (vector slot). A total classification of every bar: the answer is
   never "none", because a bar that exists was traded. Domain {0..4} — see `SessionOrdinal`.

2. `resolve_session_window(t, windows)` -> str
   The FILTER POLICY. Answers "is this instant inside a tradable window we allow?", and therefore
   CAN answer OFF_SESSION. Its windows are narrow high-activity bands
   (`state_identity.CRTConfig.session_windows`, e.g. LONDON 07:00-10:00) and its vocabulary is what
   `production_config.resolve_allowed_sessions` / `engine_runner.allowed_sessions` already use.

Merging them would be a category error: the filter's windows leave most of the day uncovered, so
using them as the feature would collapse ~60% of bars into a single "closed" bucket and destroy the
feature's information content. Conversely the feature's broad windows would admit trades the filter
is specifically designed to exclude.

WHY THE FEATURE DOMAIN CHANGED (schema v4.0, 2026-07-22)
--------------------------------------------------------
v3.0 FM-052 was a 3-value hour PARTITION: `0 if h < asia_end else (1 if h < london_end else 2)`.
That has no notion of the London/New-York overlap — the single most liquid window of the day — and
mislabels the late-NY and pre-Asia hours as "NEWYORK". v4.0 uses real market windows and adds
OVERLAP and CLOSED. The three original ordinals are UNCHANGED (ASIA=0, LONDON=1, NEWYORK=2) so that
existing decoders keep decoding the values they already knew; only the new values extend the domain.

PRECEDENCE (deterministic, and it matters — the windows genuinely overlap)
--------------------------------------------------------------------------
With the defaults below, ASIA and LONDON overlap at 07:00-08:59 and LONDON and NEWYORK overlap at
12:00-15:59. Resolution order:

    LONDON and NEWYORK  -> OVERLAP     (the liquidity event worth naming)
    NEWYORK             -> NEWYORK
    LONDON              -> LONDON      (so ASIA-LONDON resolves to LONDON: later session wins)
    ASIA                -> ASIA
    none                -> CLOSED

Bounds are half-open `[start, end)`, matching v3.0's `hour < end` convention.
"""
from __future__ import annotations

from datetime import time
from enum import IntEnum
from typing import Mapping, Optional, Sequence


class SessionOrdinal(IntEnum):
    """FM-052 canonical feature domain (schema v4.0).

    ASIA/LONDON/NEWYORK keep their v3.0 ordinals so historical decoders stay correct for those
    three values; OVERLAP and CLOSED extend the domain.
    """

    ASIA = 0
    LONDON = 1
    NEWYORK = 2
    OVERLAP = 3        # LONDON and NEWYORK simultaneously — the deep-liquidity window
    CLOSED = 4         # NO MAJOR SESSION ACTIVE — *not* "the market is shut".

    # CLOSED is named for the session calendar, not the exchange. Crypto trades 24/7, so a
    # CLOSED bar on BNBUSDT is a real, tradable bar in the thin post-NY / pre-Asia window; that
    # thinness is exactly the information the label carries. Whether an instrument is TRADABLE at
    # an instant is a different question owned by `dataset_integrity`'s session calendar
    # (holidays, broker masks, weekends) — never infer tradability from this feature.


# Canonical name -> ordinal. The single mapping every consumer must use; replaces the private
# copies that had drifted (`strategy_backtest` mapped a 4th value "overlap" the pipeline never
# emitted; `trap_validator_engine` and `live_engine_hook` each kept their own dict).
SESSION_NAME_TO_ORDINAL: dict[str, int] = {s.name: int(s) for s in SessionOrdinal}
SESSION_ORDINAL_TO_NAME: dict[int, str] = {int(s): s.name for s in SessionOrdinal}

# Legacy spellings seen in stored records / configs. Read-side only — never emit these.
_NAME_ALIASES: dict[str, str] = {
    "NEW_YORK": "NEWYORK",
    "NY": "NEWYORK",
    "ASIAN": "ASIA",
    "TOKYO": "ASIA",
    "OFF_SESSION": "CLOSED",
    "OFFSESSION": "CLOSED",
}

# The FEATURE's windows: real market sessions in UTC, half-open [start_hour, end_hour).
# DISTINCT from CRTConfig.session_windows (the FILTER's narrow bands) — see module docstring.
# Config-overridable via `feature_pipeline.session_windows_utc`.
DEFAULT_SESSION_WINDOWS_UTC: dict[str, tuple[int, int]] = {
    "ASIA":    (0, 9),
    "LONDON":  (7, 16),
    "NEWYORK": (12, 21),
}

_CONFIG_KEY = "session_windows_utc"


def canonical_session_name(raw) -> Optional[str]:
    """Normalize any spelling to a canonical name, or None if unrecognised."""
    if raw is None:
        return None
    s = str(raw).strip().upper().replace("-", "_").replace(" ", "_")
    s = _NAME_ALIASES.get(s, s)
    return s if s in SESSION_NAME_TO_ORDINAL else None


def encode_session_ordinal(session) -> int:
    """Encode a session name (or an already-encoded ordinal) to its canonical ordinal.

    Returns -1 for unknown/None, preserving the v3.0 `feature_schema.encode_session_ordinal`
    sentinel so existing callers keep their error handling.
    """
    if isinstance(session, bool):
        return -1
    if isinstance(session, (int, float)) and not isinstance(session, bool):
        iv = int(session)
        return iv if iv in SESSION_ORDINAL_TO_NAME else -1
    name = canonical_session_name(session)
    return SESSION_NAME_TO_ORDINAL[name] if name else -1


def decode_session_ordinal(value) -> str:
    """Ordinal -> canonical name. Raises on an out-of-domain value (fail loud, never guess)."""
    try:
        iv = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"session ordinal must be an int, got {value!r}") from exc
    if iv not in SESSION_ORDINAL_TO_NAME:
        raise ValueError(
            f"session ordinal {iv} is outside the FM-052 domain {sorted(SESSION_ORDINAL_TO_NAME)}. "
            f"A record carrying this value predates schema v4.0 or came from a diverged encoder."
        )
    return SESSION_ORDINAL_TO_NAME[iv]


def resolve_feature_windows(cfg: Optional[Mapping] = None) -> dict[str, tuple[int, int]]:
    """Resolve the FEATURE's session windows from a `feature_pipeline` config section.

    `cfg=None` means "use the registered defaults" — this function is also called from tests and
    standalone tooling. The PIPELINE always passes its strict-resolved config, so the live path has
    no silent default (CLAUDE.md 6.5).
    """
    if cfg is None:
        return dict(DEFAULT_SESSION_WINDOWS_UTC)
    raw = cfg.get(_CONFIG_KEY)
    if raw is None:
        raise KeyError(
            f"Required config key 'feature_pipeline.{_CONFIG_KEY}' missing. It replaces the v3.0 "
            f"session_asia_end_hour / session_london_end_hour pair, which defined a different "
            f"(3-value partition) identity and must not be reused."
        )
    out: dict[str, tuple[int, int]] = {}
    for name, bounds in raw.items():
        cname = canonical_session_name(name)
        if cname not in ("ASIA", "LONDON", "NEWYORK"):
            raise ValueError(
                f"feature_pipeline.{_CONFIG_KEY} names {name!r}; only ASIA/LONDON/NEWYORK carry "
                f"windows (OVERLAP and CLOSED are DERIVED, never configured)."
            )
        if not isinstance(bounds, Sequence) or len(bounds) != 2:
            raise ValueError(f"{_CONFIG_KEY}[{name!r}] must be [start_hour, end_hour], got {bounds!r}")
        start, end = int(bounds[0]), int(bounds[1])
        if not (0 <= start < 24 and 0 < end <= 24 and start < end):
            raise ValueError(
                f"{_CONFIG_KEY}[{name!r}] = [{start}, {end}) is not a valid half-open UTC hour "
                f"window (0 <= start < end <= 24). Wrap-around windows are not supported."
            )
        out[cname] = (start, end)
    missing = {"ASIA", "LONDON", "NEWYORK"} - set(out)
    if missing:
        raise ValueError(f"feature_pipeline.{_CONFIG_KEY} is missing window(s): {sorted(missing)}")
    return out


def classify_session_feature(hour, cfg: Optional[Mapping] = None) -> int:
    """FM-052: classify a UTC hour into the canonical session ordinal {0..4}.

    Total by construction — every hour maps to exactly one value, CLOSED included.
    """
    windows = resolve_feature_windows(cfg)
    h = int(hour)
    if not 0 <= h <= 23:
        raise ValueError(f"hour_of_day must be in [0, 23], got {h}")

    in_london = windows["LONDON"][0] <= h < windows["LONDON"][1]
    in_ny = windows["NEWYORK"][0] <= h < windows["NEWYORK"][1]
    in_asia = windows["ASIA"][0] <= h < windows["ASIA"][1]

    if in_london and in_ny:
        return int(SessionOrdinal.OVERLAP)
    if in_ny:
        return int(SessionOrdinal.NEWYORK)
    if in_london:
        return int(SessionOrdinal.LONDON)
    if in_asia:
        return int(SessionOrdinal.ASIA)
    return int(SessionOrdinal.CLOSED)


def classify_session_feature_series(hours):
    """Vectorized `classify_session_feature` over a pandas Series of UTC hours.

    Kept beside the scalar so the batch pipeline and any scalar consumer cannot drift apart — the
    same single-source discipline `candle_math` / `derived_math` use.
    """
    import numpy as np

    windows = resolve_feature_windows(_SERIES_CFG_HOLDER.get("cfg"))
    h = np.asarray(hours, dtype=np.int16)
    in_london = (h >= windows["LONDON"][0]) & (h < windows["LONDON"][1])
    in_ny = (h >= windows["NEWYORK"][0]) & (h < windows["NEWYORK"][1])
    in_asia = (h >= windows["ASIA"][0]) & (h < windows["ASIA"][1])

    out = np.full(h.shape, int(SessionOrdinal.CLOSED), dtype=np.int8)
    out = np.where(in_asia, int(SessionOrdinal.ASIA), out)
    out = np.where(in_london, int(SessionOrdinal.LONDON), out)
    out = np.where(in_ny, int(SessionOrdinal.NEWYORK), out)
    out = np.where(in_london & in_ny, int(SessionOrdinal.OVERLAP), out)
    return out.astype(np.int8)


# Series-path config injection. The pipeline sets this immediately before calling the series
# helper; a module-level holder keeps the numpy path free of a config argument while still
# forbidding a silent default on the live path.
_SERIES_CFG_HOLDER: dict = {"cfg": None}


def set_series_config(cfg: Optional[Mapping]) -> None:
    """Bind the config the vectorized helper resolves windows from."""
    _SERIES_CFG_HOLDER["cfg"] = cfg


# ─────────────────────────────────────────────────────────────────────────────
# FILTER POLICY — a DIFFERENT question (see module docstring). Behavior preserved
# byte-for-byte from backtest_v2._session; this is only its canonical home.
# ─────────────────────────────────────────────────────────────────────────────

OFF_SESSION = "OFF_SESSION"


def resolve_session_window(t: time, windows: Mapping[str, tuple]) -> str:
    """Which named TRADING window contains `t`? `OFF_SESSION` when none does.

    NOTE the deliberate differences from `classify_session_feature`:
      * inclusive bounds (`start <= t <= end`), preserving the incumbent filter behavior;
      * `time` granularity, not whole hours;
      * windows come from `CRTConfig.session_windows` (narrow bands), not the feature's windows;
      * returns a NAME, and can legitimately return OFF_SESSION.
    Do not "unify" these two functions — see the module docstring.
    """
    for name, (start, end) in windows.items():
        if start <= t <= end:
            return name
    return OFF_SESSION
