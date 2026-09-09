"""
clock_detector.py — ADVISORY evidence for a human clock review. Never a verdict of record.

WHAT THIS IS
------------
`clock_registry.require_reviewed_clock` refuses to run a corpus whose timezone has not been
DECLARED and REVIEWED by a human. This module answers the natural next question — "how am I
supposed to know which clock it is on?" — by re-running the tests that already established the
answer for MT5 corpora, recorded in `features/broker_clock.py`'s module docstring:

  T2  REFERENCE XCORR Cross-correlate the intraday realized-range profile against a corpus already
                      DECLARED `UTC` in the registry. Best circular shift = the offset, in hours.
                      (broker_clock: XAUUSD vs Binance BTCUSDT gave exactly -3h Apr-Sep, -2h
                      Nov-Feb.)
  T1  SEASONAL STEP   T2 run SEPARATELY over America/New_York DST-on vs DST-off dates. A ~1h
                      difference means the feed observes DST; ~0 means a fixed offset.
  T4  NY-vs-EU        T2 restricted to the ~5 weeks/year where the US and EU DST calendars
                      disagree. In every such window NY is on DST while the EU is not, so a
                      server on the NY calendar shows its SUMMER offset there and a server on the
                      EU calendar shows its WINTER one. (broker_clock: the boundary holds through
                      those windows on NY.)
  T3  DAILY BOUNDARY  Where does the trading day start? A genuinely-UTC feed opens 00:00. The MT5
                      broker feed shows 01:00 -> 23:45.

WHY T1 NEEDS A REFERENCE (a defect found by running it)
--------------------------------------------------------
The first cut of T1 compared the modal daily-open time ACROSS DST regimes within a single file and
called a zero step "fixed offset". Measured on `data/mt5/XAUUSD_M15.csv` that returns step=0 and
labelled a DST-observing broker feed `LOOKS_FIXED_OFFSET_NON_UTC`. The cause is structural, not a
tuning miss: **the broker's day boundary is defined in the broker's own clock** (01:00 server
year-round, which is exactly the invariant broker_clock's docstring reports), so a seasonal shift
is absorbed by the clock and is INVISIBLE from the series alone:

    data/mt5/XAUUSD_M15.csv      modal open | NY-DST on: 01:00 | off: 01:00
    data/binance/BTCUSDT_M15.csv                        00:00 |      00:00

DST is therefore only observable against an external absolute reference. T1 and T4 require one and
honestly report INSUFFICIENT without it, rather than emitting a confident wrong verdict — which
would corrupt the very review this module exists to inform.

BOOTSTRAP: with an empty registry there is no declared-UTC reference. Review a Binance corpus
first — Binance klines are UTC epoch by API contract, and T3 corroborates (00:00 open) — then
every MT5 corpus can be measured against it.

AUTHORITY: NONE
---------------
This module NEVER sets `user_reviewed` and NEVER writes a registry record on its own. It reports
evidence plus a `verdict`/`confidence` for a human to accept or reject. Detection informs a review;
it does not substitute for one — which is the whole point of the gate.

It reads corpora RAW (pandas), deliberately bypassing the Phase-3 gate: it must be able to inspect
a file precisely because that file is not yet reviewable.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from data_ingestion.ohlcv_schema import resolve_ohlcv_headers, require_ohlcv_columns
from features.broker_clock import _ny_is_dst_on_date

# Verdict tokens — advisory labels, deliberately distinct from the registry's legal `timezone`
# values so a verdict can never be pasted in as a declaration by accident.
VERDICT_UTC = "LOOKS_UTC"
VERDICT_MT5_NY = "LOOKS_MT5_SERVER_NY_DST"
VERDICT_DST_NON_NY = "LOOKS_DST_ZONE_NOT_NEW_YORK"
VERDICT_FIXED_OFFSET = "LOOKS_FIXED_OFFSET_NON_UTC"
VERDICT_INCONCLUSIVE = "INCONCLUSIVE"

CONF_HIGH = "high"
CONF_MEDIUM = "medium"
CONF_LOW = "low"

_MAX_ROWS = 400_000        # bounded read; intraday profiles converge long before this
_PROFILE_BINS = 96         # 15-minute resolution over 24h
_MIN_DAYS_SUBSET = 20      # below this a seasonal/mismatch subset is not meaningful
_MAX_EMPTY_BIN_FRAC = 0.25  # a 01:00->23:45 broker day legitimately empties ~4% of the bins
_ON_HOUR_TOL = 0.10        # hours; "lands on the hour"
_STEP_TOL = 0.25           # hours; tolerance around a 1h DST step
_MIN_CORR_HIGH = 0.60      # weakest per-regime profile correlation still allowed to claim `high`

# EU DST rule (last Sunday March -> last Sunday October), used ONLY to locate the weeks where the
# US and EU calendars disagree. broker_clock deliberately does not use a Europe/* zone for the
# CONVERSION; here it is just the other candidate calendar in a discriminator.
_EU = ZoneInfo("Europe/Brussels")


@lru_cache(maxsize=4096)
def _eu_is_dst_on_date(d) -> bool:
    probe = datetime(d.year, d.month, d.day, 12, 0, tzinfo=_EU)
    dst = probe.dst()
    return dst is not None and dst.total_seconds() != 0


def load_raw_ohlcv(path: str | Path, *, max_rows: int = _MAX_ROWS) -> pd.DataFrame:
    """Read a corpus RAW for inspection — no Phase-3 gate (see module docstring).

    Returns a frame with a tz-naive `timestamp` column plus the OHLCV columns, canonically named.
    """
    p = Path(path)
    if p.suffix.lower() in (".xlsx", ".xlsm", ".xls"):
        try:
            df = pd.read_excel(p, nrows=max_rows)
        except ImportError as exc:                       # openpyxl absent
            raise ImportError(
                f"Reading {p.name} needs an Excel engine (openpyxl). Install it, or export the "
                f"corpus to CSV first."
            ) from exc
    else:
        df = pd.read_csv(p, nrows=max_rows)

    resolved = resolve_ohlcv_headers(df.columns)
    # Split date+time corpora: synthesize the timestamp the way CandleLoader.stream does.
    if "timestamp" not in resolved:
        lower = {str(c).strip().lower(): c for c in df.columns}
        if "date" in lower and "time" in lower:
            df = df.copy()
            df["timestamp"] = (
                df[lower["date"]].astype(str).str.strip() + " "
                + df[lower["time"]].astype(str).str.strip()
            )
            resolved["timestamp"] = "timestamp"
    require_ohlcv_columns(set(resolved), source=f"Historical dataset {p}")

    out = df.rename(columns={v: k for k, v in resolved.items()})
    out["timestamp"] = pd.to_datetime(out["timestamp"], errors="coerce")
    out = out.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
    if out.empty:
        raise ValueError(f"{p}: no parseable timestamps.")
    return out[["timestamp", "open", "high", "low", "close", "volume"]]


# ── shared machinery ───────────────────────────────────────────────────────────
def _intraday_range_profile(
    df: pd.DataFrame, bins: int
) -> tuple[Optional[np.ndarray], int]:
    """Mean realized range (high-low)/close by minute-of-day bin, z-scored.

    Returns (profile, bins_filled). A broker feed whose trading day runs 01:00->23:45 legitimately
    has NO bars in some minute-of-day bins — measured on `data/mt5/XAUUSD_M15.csv`, the 00:00 hour
    is empty. Those bins are filled with the profile mean (neutral after z-scoring) rather than
    treated as a fatal defect, up to `_MAX_EMPTY_BIN_FRAC`; beyond that the profile is too sparse
    to align and the caller reports INSUFFICIENT. `bins_filled` is surfaced as evidence so a
    reviewer can see how much of the profile was inferred rather than measured.
    """
    ts = df["timestamp"]
    step = 1440 // bins
    idx = ((ts.dt.hour * 60 + ts.dt.minute) // step).astype(int).clip(0, bins - 1)
    close = pd.to_numeric(df["close"], errors="coerce")
    rng = (pd.to_numeric(df["high"], errors="coerce")
           - pd.to_numeric(df["low"], errors="coerce")) / close.replace(0, np.nan)
    prof = pd.Series(rng.values, index=idx.values).groupby(level=0).mean().reindex(range(bins))

    empty = int(prof.isna().sum())
    if empty > int(_MAX_EMPTY_BIN_FRAC * bins):
        return None, empty
    if empty:
        prof = prof.fillna(prof.mean())
    v = prof.to_numpy(dtype=float)
    sd = float(v.std())
    return (None if sd == 0 else (v - v.mean()) / sd), empty


def _shift_vs_reference(
    cand: pd.DataFrame, ref: pd.DataFrame, *, predicate=None, bins: int = _PROFILE_BINS
) -> dict[str, Any]:
    """Best circular shift (hours) aligning `cand`'s intraday profile onto `ref`'s.

    Positive means the candidate's clock RUNS AHEAD of the reference by that many hours — i.e.
    subtract it to reach the reference clock. Restricted to the overlapping date range so a
    structural break in either corpus cannot masquerade as an offset.

    `predicate(date) -> bool` subsets BOTH sides by the SAME dates. Masking only the candidate
    (and leaving the reference at its full range) smears the two DST regimes together: measured on
    XAUUSD vs BTCUSDT, unmatched masking reported +2.0h for both regimes — a spurious zero step
    that contradicted broker_clock's twice-confirmed 1h seasonal split. With matched masks the
    same data yields +3.0h (NY-DST-on) and +2.0h (off), r=0.687/0.712, reproducing broker_clock's
    -3h Apr-Sep / -2h Nov-Feb (r=0.675/0.709). Always mask both sides.
    """
    lo = max(cand["timestamp"].min(), ref["timestamp"].min())
    hi = min(cand["timestamp"].max(), ref["timestamp"].max())
    if lo >= hi:
        return {"status": "NO_OVERLAP",
                "note": "candidate and reference corpora do not overlap in time"}

    a = cand[(cand["timestamp"] >= lo) & (cand["timestamp"] <= hi)]
    b = ref[(ref["timestamp"] >= lo) & (ref["timestamp"] <= hi)]
    if predicate is not None:
        a, b = _mask_by_date(a, predicate), _mask_by_date(b, predicate)
    days = int(a["timestamp"].dt.date.nunique())
    if days < _MIN_DAYS_SUBSET:
        return {"status": "INSUFFICIENT", "days": days,
                "note": f"needs >= {_MIN_DAYS_SUBSET} days in the overlap, have {days}"}

    pa, filled_a = _intraday_range_profile(a, bins)
    pb, filled_b = _intraday_range_profile(b, bins)
    if pa is None or pb is None:
        return {"status": "INSUFFICIENT", "days": days,
                "empty_bins_candidate": filled_a, "empty_bins_reference": filled_b,
                "note": (f"intraday profile too sparse (> {_MAX_EMPTY_BIN_FRAC:.0%} of {bins} "
                         f"bins empty) or zero variance")}

    n = len(pa)
    # corr(pa, pb rolled by s): the roll that best aligns the reference onto the candidate.
    corrs = [(float(np.dot(pa, np.roll(pb, s)) / n), s) for s in range(n)]
    best_corr, best_shift = max(corrs, key=lambda t: t[0])
    hours = ((best_shift * (24.0 / bins)) + 12.0) % 24.0 - 12.0        # wrap to (-12, +12]
    return {
        "status": "OK",
        "days": days,
        "overlap_start": str(lo), "overlap_end": str(hi),
        "shift_hours": round(hours, 3),
        "correlation": round(best_corr, 4),
        "on_the_hour": bool(abs(hours - round(hours)) < _ON_HOUR_TOL),
        "filled_bins_candidate": filled_a,
        "filled_bins_reference": filled_b,
    }


def _mask_by_date(df: pd.DataFrame, predicate) -> pd.DataFrame:
    dates = df["timestamp"].dt.date
    uniq = pd.Index(dates.unique())
    keep = {d: bool(predicate(d)) for d in uniq}
    return df[dates.map(keep).to_numpy(dtype=bool)]


# ── T2: reference cross-correlation (whole overlap) ────────────────────────────
def _t2_reference_xcorr(df: pd.DataFrame, ref: Optional[pd.DataFrame]) -> dict[str, Any]:
    if ref is None:
        return {"status": "NO_REFERENCE",
                "note": ("no corpus is declared UTC in the registry, so there is no absolute "
                         "reference; review a Binance corpus first to bootstrap")}
    return _shift_vs_reference(df, ref)


# ── T1: seasonal step (requires reference) ─────────────────────────────────────
def _t1_seasonal_step(df: pd.DataFrame, ref: Optional[pd.DataFrame]) -> dict[str, Any]:
    if ref is None:
        return {"status": "NO_REFERENCE",
                "note": ("DST is invisible from a single series - the broker's day boundary is "
                         "defined in the broker's own clock, so the seasonal shift is absorbed. "
                         "Needs a declared-UTC reference.")}

    on = _shift_vs_reference(df, ref, predicate=_ny_is_dst_on_date)
    off = _shift_vs_reference(df, ref, predicate=lambda d: not _ny_is_dst_on_date(d))
    if on.get("status") != "OK" or off.get("status") != "OK":
        return {"status": "INSUFFICIENT", "dst_on": on, "dst_off": off,
                "note": "one or both DST regimes lack enough overlapping data"}

    step = round(on["shift_hours"] - off["shift_hours"], 3)
    # A real clock does one of exactly two things across a DST boundary: nothing (fixed offset) or
    # a 1h step. Anything else — measured +6.50h on data/mt5/GBPUSD_M15.csv — is a failed
    # alignment, NOT evidence of a fixed offset. Classifying it UNSTABLE stops the verdict layer
    # from converting measurement noise into a confident claim.
    if abs(step) <= _STEP_TOL:
        step_class = "NO_DST"
    elif abs(abs(step) - 1.0) <= _STEP_TOL:
        step_class = "DST"
    else:
        step_class = "UNSTABLE"
    return {
        "status": "OK",
        "shift_hours_ny_dst_on": on["shift_hours"],
        "shift_hours_ny_dst_off": off["shift_hours"],
        "step_hours": step,
        "step_class": step_class,
        "observes_dst": step_class == "DST",
        "min_regime_correlation": round(min(on["correlation"], off["correlation"]), 4),
        "dst_on": on, "dst_off": off,
    }


# ── T4: which DST calendar (requires reference) ────────────────────────────────
def _t4_ny_vs_eu(df: pd.DataFrame, ref: Optional[pd.DataFrame], t1: dict) -> dict[str, Any]:
    """In every US/EU mismatch window NY is on DST and the EU is not.

    So a server on the NY calendar shows its SUMMER offset there; one on the EU calendar shows its
    WINTER offset. Compare the mismatch-window shift against T1's two seasonal shifts.
    """
    if ref is None:
        return {"status": "NO_REFERENCE"}
    if t1.get("status") != "OK" or not t1.get("observes_dst"):
        return {"status": "NOT_APPLICABLE",
                "note": "only meaningful once T1 shows the feed observes DST"}

    res = _shift_vs_reference(
        df, ref, predicate=lambda d: _ny_is_dst_on_date(d) != _eu_is_dst_on_date(d)
    )
    if res.get("status") != "OK":
        return {"status": "INSUFFICIENT", "detail": res,
                "note": ("the US/EU calendars disagree only ~5 weeks/year; this corpus does not "
                         "cover enough of them to separate the two calendars")}

    d_ny = abs(res["shift_hours"] - t1["shift_hours_ny_dst_on"])
    d_eu = abs(res["shift_hours"] - t1["shift_hours_ny_dst_off"])
    if abs(d_ny - d_eu) < _STEP_TOL:
        calendar = "AMBIGUOUS"
    else:
        calendar = "AMERICA_NEW_YORK" if d_ny < d_eu else "EUROPE"
    return {
        "status": "OK",
        "mismatch_days": res["days"],
        "shift_hours_mismatch_window": res["shift_hours"],
        "distance_to_ny_summer": round(d_ny, 3),
        "distance_to_eu_winter": round(d_eu, 3),
        "calendar": calendar,
    }


# ── T3: daily boundary ─────────────────────────────────────────────────────────
def _t3_daily_boundary(ts: pd.Series) -> dict[str, Any]:
    by_day = ts.groupby(ts.dt.date)
    first = Counter(by_day.min().dt.strftime("%H:%M")).most_common(1)
    last = Counter(by_day.max().dt.strftime("%H:%M")).most_common(1)
    modal_open = first[0][0] if first else None
    return {
        "modal_day_open": modal_open,
        "modal_day_close": last[0][0] if last else None,
        "days_observed": int(by_day.ngroups),
        "opens_at_utc_midnight": modal_open == "00:00",
        "note": ("consistent-with only - the day boundary is expressed in the FILE's own clock, "
                 "so it cannot distinguish a fixed offset from a DST-observing server"),
    }


# ── verdict ────────────────────────────────────────────────────────────────────
def _verdict(t1: dict, t2: dict, t3: dict, t4: dict) -> tuple[str, str, list[str]]:
    why: list[str] = []
    utc_open = t3.get("opens_at_utc_midnight")

    # No absolute reference: T1/T4 are structurally unavailable. Say so; never guess a DST answer.
    if t2.get("status") == "NO_REFERENCE":
        why.append("T2/T1/T4: no declared-UTC reference corpus - DST and offset are not "
                   "measurable from a single series (see module docstring)")
        why.append(f"T3: day opens {t3.get('modal_day_open')} / closes {t3.get('modal_day_close')}")
        if utc_open:
            why.append("T3 is CONSISTENT WITH UTC but cannot confirm it alone")
            return VERDICT_UTC, CONF_LOW, why
        return VERDICT_INCONCLUSIVE, CONF_LOW, why

    if t2.get("status") != "OK":
        why.append(f"T2 {t2.get('status')}: {t2.get('note', 'no usable overlap with the reference')}")
        why.append(f"T3: day opens {t3.get('modal_day_open')}")
        return VERDICT_INCONCLUSIVE, CONF_LOW, why

    shift = t2["shift_hours"]
    why.append(f"T2: {shift:+.2f}h vs the declared-UTC reference "
               f"(r={t2['correlation']}, {t2['days']}d)")

    # Weak profile alignment caps every downstream claim — a shift read off a flat correlation
    # peak is a guess wearing a number.
    r_min = t1.get("min_regime_correlation")
    weak = r_min is not None and r_min < _MIN_CORR_HIGH
    cap = (lambda c: CONF_MEDIUM if (weak and c == CONF_HIGH) else c)
    if weak:
        why.append(f"correlation floor: weakest regime r={r_min} < {_MIN_CORR_HIGH} -> "
                   f"confidence capped")

    if t1.get("step_class") == "UNSTABLE":
        why.append(f"T1: seasonal step {t1['step_hours']:+.2f}h is neither ~0 nor ~1h - a real "
                   f"clock does one or the other, so this alignment is UNRELIABLE, not evidence "
                   f"of a fixed offset")
        return VERDICT_INCONCLUSIVE, CONF_LOW, why

    if t1.get("status") == "OK" and t1.get("observes_dst"):
        why.append(f"T1: seasonal step {t1['step_hours']:+.2f}h "
                   f"({t1['shift_hours_ny_dst_on']:+.2f}h NY-DST-on vs "
                   f"{t1['shift_hours_ny_dst_off']:+.2f}h off) -> the feed OBSERVES DST")
        cal = t4.get("calendar")
        if cal == "AMERICA_NEW_YORK":
            why.append(f"T4: over {t4['mismatch_days']}d of US/EU calendar mismatch the offset "
                       f"matches the NY summer regime -> America/New_York calendar")
            return VERDICT_MT5_NY, cap(CONF_HIGH), why
        if cal == "EUROPE":
            why.append(f"T4: mismatch-window offset matches the EU regime -> NOT New York")
            return VERDICT_DST_NON_NY, cap(CONF_MEDIUM), why
        why.append(f"T4 {t4.get('status')}: {t4.get('note', 'calendar not separable')} - "
                   f"NY-vs-EU unresolved, so this is a DST-observing feed assumed to be the "
                   f"documented MT5 server (broker_clock)")
        return VERDICT_MT5_NY, cap(CONF_MEDIUM), why

    if t1.get("step_class") == "NO_DST":
        why.append(f"T1: seasonal step {t1['step_hours']:+.2f}h -> fixed offset, no DST")
        if abs(shift) < _ON_HOUR_TOL:
            why.append("T2 shift is ~0 -> the candidate is on the reference's clock")
            return VERDICT_UTC, cap(CONF_HIGH), why
        return VERDICT_FIXED_OFFSET, cap(CONF_HIGH), why

    why.append(f"T1 {t1.get('status')}: {t1.get('note', 'seasonal step not determinable')}")
    if abs(shift) < _ON_HOUR_TOL:
        return VERDICT_UTC, CONF_MEDIUM, why
    return VERDICT_FIXED_OFFSET, CONF_LOW, why


def detect_clock(path: str | Path, *, reference: Optional[pd.DataFrame] = None) -> dict[str, Any]:
    """Run T1-T4 and return an ADVISORY evidence bundle. Deterministic; read-only.

    The returned dict is stored in a record's `detector` field and printed during review. It never
    decides anything on its own — see the module docstring.
    """
    df = load_raw_ohlcv(path)
    ts = df["timestamp"]
    t2 = _t2_reference_xcorr(df, reference)
    t1 = _t1_seasonal_step(df, reference)
    t4 = _t4_ny_vs_eu(df, reference, t1)
    t3 = _t3_daily_boundary(ts)
    verdict, confidence, why = _verdict(t1, t2, t3, t4)
    return {
        "verdict": verdict,
        "confidence": confidence,
        "authority": "ADVISORY_ONLY - a human declares the clock; this never sets user_reviewed",
        "reasoning": why,
        "rows_inspected": int(len(df)),
        "first_timestamp": str(ts.min()),
        "last_timestamp": str(ts.max()),
        "tests": {
            "t1_seasonal_step": t1,
            "t2_reference_xcorr": t2,
            "t3_daily_boundary": t3,
            "t4_ny_vs_eu": t4,
        },
    }


def suggested_timezone(detection: dict[str, Any]) -> Optional[str]:
    """Map an advisory verdict to the registry `timezone` a reviewer would most likely pick.

    Returns None when the evidence does not point at one of the two named kinds — the reviewer then
    supplies an explicit IANA zone rather than accepting a guess.
    """
    return {VERDICT_UTC: "UTC", VERDICT_MT5_NY: "MT5_SERVER_NY_DST"}.get(detection.get("verdict"))
