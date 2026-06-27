"""Auto-derived per-provider session calendar — learns the tradable mask from the data.

Pins: (1) derive_weekly_mask learns Mon-Fri (no weekend) from a weekday-only series; (2) the mask
hook in _is_tradable makes validate_dataset(tradability_mode=autoderive) ACCEPT a broker that has
no Sunday session (the IC-Markets case) without a hardcoded calendar; (3) a genuine weekday hole
still hard-stops; (4) a full-day holiday passes only when listed. This is the fix for the
real-world REJECTs the default Sun-22:00 calendar produced on IC-Markets data.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from data_ingestion.dataset_integrity import DatasetDecision, validate_dataset   # noqa: E402
from data_ingestion.ohlcv_schema import DatasetIntegrityError                    # noqa: E402
from data_ingestion.session_autoderive import (                                  # noqa: E402
    derive_weekly_mask, is_tradable_by_mask,
)

_AUTODERIVE = {"enforce_path_consistency": False, "max_missing_pct": 0.0,
               "max_single_gap_candles": 0, "max_gap_span_minutes": 0,
               "future_ts_tolerance_minutes": 0, "tradability_mode": "autoderive",
               "autoderive_presence_min": 0.5}


def _weekday_only_m15(start_monday: datetime, weeks: int):
    """A broker-like M15 series: Mon 00:00 -> Fri 23:45 each week, NO Sunday, NO daily break."""
    out = []
    for w in range(weeks):
        wk = start_monday + timedelta(days=7 * w)
        for d in range(5):                      # Mon..Fri
            day = wk + timedelta(days=d)
            for slot in range(96):              # 96 M15 bars/day
                out.append(day + timedelta(minutes=15 * slot))
    return out


def _write(path: Path, timestamps, *, defect_row=None):
    lines = ["timestamp,open,high,low,close,volume"]
    for i, ts in enumerate(timestamps):
        if defect_row is not None and i == defect_row:
            lines.append(f"{ts:%Y-%m-%d %H:%M:%S},1.0,1.1,0.9,,100")
        else:
            lines.append(f"{ts:%Y-%m-%d %H:%M:%S},1.0,1.1,0.9,1.05,100")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ── module: derive_weekly_mask ────────────────────────────────────────────────
def test_mask_learns_weekday_only():
    ts = _weekday_only_m15(datetime(2024, 1, 1), 8)   # 2024-01-01 is a Monday
    mask = derive_weekly_mask(ts, presence_min=0.5)
    assert len(mask) == 96 * 5                          # Mon-Fri, 96 slots each
    assert (0, 0) in mask                               # Monday 00:00 tradable
    assert (5, 12 * 60) not in mask                     # Saturday noon not tradable
    assert (6, 22 * 60) not in mask                     # Sunday 22:00 not tradable (no session)


def test_is_tradable_by_mask_respects_holidays():
    ts = _weekday_only_m15(datetime(2024, 1, 1), 8)
    mask = derive_weekly_mask(ts)
    wed_noon = datetime(2024, 1, 3, 12, 0)             # Wednesday — in mask
    assert is_tradable_by_mask(wed_noon, mask, holidays=set())
    assert not is_tradable_by_mask(wed_noon, mask, holidays={"2024-01-03"})   # holiday wins
    assert not is_tradable_by_mask(datetime(2024, 1, 6, 12, 0), mask, set())  # Saturday


# ── integration: validate_dataset autoderive mode ────────────────────────────
def test_autoderive_accepts_no_sunday_broker(tmp_path):
    """The exact real-world case: a broker with NO Sunday session must APPROVE under autoderive
    (the default Sun-22:00 calendar would REJECT every Sunday slot it never serves)."""
    ts = _weekday_only_m15(datetime(2024, 1, 1), 12)
    p = tmp_path / "EURUSD_M15.csv"
    _write(p, ts)
    rep = validate_dataset(str(p), instrument="EURUSD", raise_on_fail=True,
                           write_report=False, cfg_override=_AUTODERIVE)
    assert rep["decision"] == DatasetDecision.APPROVE.value
    assert rep["tradability_mode"] == "autoderive"
    assert rep["missing_pct"] == 0.0


def test_autoderive_still_catches_weekday_hole(tmp_path):
    ts = _weekday_only_m15(datetime(2024, 1, 1), 12)
    del ts[200]                                         # punch a mid-week hole
    p = tmp_path / "EURUSD_M15.csv"
    _write(p, ts)
    with pytest.raises(DatasetIntegrityError):
        validate_dataset(str(p), instrument="EURUSD", raise_on_fail=True,
                         write_report=False, cfg_override=_AUTODERIVE)


def test_autoderive_holiday_passes_only_when_listed(tmp_path):
    ts = _weekday_only_m15(datetime(2024, 1, 1), 12)
    holiday = datetime(2024, 1, 17).date()             # a Wednesday
    kept = [t for t in ts if t.date() != holiday]
    p = tmp_path / "EURUSD_M15.csv"
    _write(p, kept)
    rep_no = validate_dataset(str(p), instrument="EURUSD", raise_on_fail=False,
                              write_report=False, cfg_override=_AUTODERIVE)
    assert rep_no["decision"] == DatasetDecision.REJECT.value
    sc = {"holidays": ["2024-01-17"]}
    rep_yes = validate_dataset(str(p), instrument="EURUSD", raise_on_fail=False, write_report=False,
                               cfg_override={**_AUTODERIVE, "session_calendar": sc})
    assert rep_yes["decision"] == DatasetDecision.APPROVE.value
