"""
broker_clock.py — converts MT5 broker-server timestamps to true UTC.

WHY THIS EXISTS (evidence, not assertion)
------------------------------------------
`inout/mt5_candle_fetcher.py:186` does `datetime.fromtimestamp(r["time"], tz=timezone.utc)` on
MT5's `copy_rates` `time` field. That field is a **server-time** epoch (documented MT5 behavior),
so every MT5-derived corpus (`data/mt5/*.csv`) has its `timestamp` column labeled UTC while
actually holding broker-server local time.

Measured this session, two independent tests, both CONFIRM:
  * Cross-correlating 15-min intraday realized-range profile of XAUUSD (MT5) against BTCUSDT
    (Binance, genuinely UTC-epoch klines): best alignment shift is exactly -3h00m Apr-Sep
    (r=0.675) and exactly -2h00m Nov-Feb (r=0.709) -- on-the-hour, differing by precisely the
    1-hour DST step.
  * NFP release (08:30 America/New_York, first Friday/month) lands on the SAME server clock time
    (15:30) in both seasons -- season-invariance is exactly what an EET/EEST-tracking server
    predicts; true-UTC stamps would alternate 12:30 <-> 13:30.
  * The daily bar boundary (01:00 -> 23:45 server) holds THROUGH the US/EU DST-mismatch windows
    (2025-03-10..27, 2025-10-27..31, 2024-10-28..11-01) -- proving the server follows
    **America/New_York** DST transitions, not Europe/Athens. A fixed EET/EEST (Europe/*) zone
    would be off by 1 hour for ~5 weeks/year; this module deliberately does NOT use zoneinfo's
    Europe/Athens and instead derives the seasonal offset from New York's own transition dates.

Full derivation: docs/research/preregistration-blind-label-descriptive-fidelity.md session log /
the plan record for this investigation. This module implements the CONVERSION only; whether to
route production through it is a separate, config-gated decision
(`feature_pipeline.session_timestamp_basis`, see `feature_pipeline.py:compute_context`).

SCOPE
-----
Applies ONLY to timestamps that came from `mt5_candle_fetcher.py` (i.e. every `data/mt5/*.csv`
corpus: XAUUSD + the FX majors). Binance-sourced corpora (`data/binance/*.csv`) use genuinely
UTC epoch timestamps and must NEVER be passed through this conversion.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

_NY = ZoneInfo("America/New_York")


@lru_cache(maxsize=4096)
def _ny_is_dst_on_date(d) -> bool:
    """Whether America/New_York observes DST at local noon on calendar date `d`.

    Noon is used (not midnight) so the query always lands well inside the day, never in the
    2 AM local transition-ambiguous hour itself -- this is a date-level lookup, not an
    instant-level one, and the daily-boundary invariant proven above confirms the broker's own
    calendar date is a safe proxy for "which DST regime applies," except within the transition
    weekend itself (already empirically verified to resolve correctly, see module docstring).
    """
    probe = datetime(d.year, d.month, d.day, 12, 0, tzinfo=_NY)
    dst = probe.dst()
    return dst is not None and dst.total_seconds() != 0


def mt5_server_offset_hours(broker_timestamps: pd.Series) -> pd.Series:
    """Per-row hours to SUBTRACT from an MT5 broker-server timestamp to reach true UTC.

    3 when New York observes EDT (summer) -- broker runs EEST (UTC+3).
    2 when New York observes EST (winter) -- broker runs EET  (UTC+2).
    """
    dates = broker_timestamps.dt.date
    unique_dates = pd.Index(dates.unique())
    dst_by_date = {d: _ny_is_dst_on_date(d) for d in unique_dates}
    is_dst = dates.map(dst_by_date)
    return is_dst.map({True: 3, False: 2}).astype(np.int8)


def mt5_server_to_utc(broker_timestamps: pd.Series) -> pd.Series:
    """Convert a Series of MT5 broker-server-time timestamps (tz-naive) to true UTC
    (tz-naive, UTC wall-clock values -- callers that need it explicit can localize after).

    Does NOT mutate its input. Callers must keep the raw broker `timestamp` column around
    separately for OHLCV identity/hash purposes -- this function is for deriving session/
    hour-of-day semantics only, never for re-labeling the corpus's own timestamp column.
    """
    offsets_h = mt5_server_offset_hours(broker_timestamps)
    return broker_timestamps - pd.to_timedelta(offsets_h, unit="h")


def mt5_server_to_utc_scalar(ts: datetime) -> datetime:
    """Scalar counterpart to mt5_server_to_utc — one candle at a time (CRT engine's per-bar
    session filter, which cannot use the vectorized Series path). Reuses `_ny_is_dst_on_date`
    (already `lru_cache`d) so the DST rule has one source, not two.

    Same MT5-only scope caveat as the vectorized function: never call this on a genuinely-UTC
    (Binance) timestamp — see the module docstring's SCOPE section.
    """
    offset_h = 3 if _ny_is_dst_on_date(ts.date()) else 2
    return ts - timedelta(hours=offset_h)
