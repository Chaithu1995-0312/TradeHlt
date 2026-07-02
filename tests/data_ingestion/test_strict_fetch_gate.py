"""Strict zero-tolerance fetch gate — the hard-stop data-integrity contract.

Pins: (1) ANY tradable missing bar hard-stops (crypto 24/7 AND FX weekday); (2) legitimate FX
weekend/rollover closures pass (session-aware, NOT false-stopped); (3) a reviewed holiday date in
config makes that closure pass; (4) OHLCV defects raise at L1; (5) cfg_override=None is byte-parity
with the loaded config (the strict profile changes behavior, the default does not).
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from data_ingestion.dataset_integrity import (                       # noqa: E402
    DatasetDecision, MarketType, _is_tradable, classify_market, validate_dataset,
)
from data_ingestion.ohlcv_schema import DatasetIntegrityError        # noqa: E402

# Hermetic session calendar (independent of the prod config), and the strict zero-tolerance profile.
_SC = {
    "crypto_quote_suffixes": ["USDT", "USDC", "BUSD"],
    "weekday_open_hour": 22, "weekday_close_hour": 21, "weekday_daily_break_hours": [21],
    "holidays": [],
}
_STRICT = {"enforce_path_consistency": False, "max_missing_pct": 0.0,
           "max_single_gap_candles": 0, "max_gap_span_minutes": 0,
           "future_ts_tolerance_minutes": 0}


def _override(*, holidays=None, **extra):
    sc = {**_SC, "holidays": list(holidays or [])}
    return {**_STRICT, "session_calendar": sc, **extra}


def _grid(start: datetime, end: datetime, market: MarketType, bar_min: int, sc=None) -> list[datetime]:
    """Every TRADABLE grid slot in [start, end) — a perfectly-complete series for that market."""
    sc = sc or _SC
    step = timedelta(minutes=bar_min)
    t, out = start, []
    while t < end:
        if _is_tradable(t, market, sc):
            out.append(t)
        t += step
    return out


def _write(path: Path, timestamps, *, defect_row: int | None = None) -> None:
    lines = ["timestamp,open,high,low,close,volume"]
    for i, ts in enumerate(timestamps):
        if defect_row is not None and i == defect_row:
            lines.append(f"{ts:%Y-%m-%d %H:%M:%S},1.0,1.1,0.9,,100")   # missing close → L1 defect
        else:
            lines.append(f"{ts:%Y-%m-%d %H:%M:%S},1.0,1.1,0.9,1.05,100")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ── (1) ANY tradable hole hard-stops ─────────────────────────────────────────
def test_crypto_single_missing_5min_bar_hard_stops(tmp_path):
    ts = _grid(datetime(2024, 5, 21, 0, 0), datetime(2024, 5, 21, 4, 0), MarketType.CRYPTO, 5)
    del ts[20]                                   # punch one 5-min hole mid-stream
    p = tmp_path / "BTCUSDT_M5.csv"
    _write(p, ts)
    with pytest.raises(DatasetIntegrityError):
        validate_dataset(str(p), instrument="BTCUSDT", raise_on_fail=True,
                         write_report=False, cfg_override=_override())


def test_fx_weekday_hole_hard_stops(tmp_path):
    ts = _grid(datetime(2024, 5, 21, 0, 0), datetime(2024, 5, 21, 12, 0), MarketType.WEEKDAY, 15)
    del ts[10]
    p = tmp_path / "EURUSD_M15.csv"
    _write(p, ts)
    rep = validate_dataset(str(p), instrument="EURUSD", raise_on_fail=False,
                           write_report=False, cfg_override=_override())
    assert rep["decision"] == DatasetDecision.REJECT.value


# ── (2) legitimate FX weekend/rollover closures pass ─────────────────────────
def test_fx_complete_grid_across_weekend_passes(tmp_path):
    # Fri → Tue spans the Fri-close, all of Sat, the Sun-open, and daily 21:00 rollover breaks.
    ts = _grid(datetime(2024, 5, 24, 0, 0), datetime(2024, 5, 28, 0, 0), MarketType.WEEKDAY, 15)
    p = tmp_path / "EURUSD_M15.csv"
    _write(p, ts)
    rep = validate_dataset(str(p), instrument="EURUSD", raise_on_fail=True,
                           write_report=False, cfg_override=_override())
    assert rep["decision"] == DatasetDecision.APPROVE.value
    assert rep["missing_pct"] == 0.0


# ── (3) reviewed holiday date makes that closure pass ────────────────────────
def test_holiday_closure_passes_only_when_listed(tmp_path):
    # A complete weekday grid, then delete an entire weekday (Tue) → those are tradable → REJECT;
    # listing that date as a holiday makes the same series APPROVE.
    full = _grid(datetime(2024, 5, 20, 0, 0), datetime(2024, 5, 23, 0, 0), MarketType.WEEKDAY, 15)
    holiday = datetime(2024, 5, 21).date()       # Tuesday
    kept = [t for t in full if t.date() != holiday]
    p = tmp_path / "EURUSD_M15.csv"
    _write(p, kept)

    rep_no = validate_dataset(str(p), instrument="EURUSD", raise_on_fail=False,
                              write_report=False, cfg_override=_override())
    assert rep_no["decision"] == DatasetDecision.REJECT.value

    rep_yes = validate_dataset(str(p), instrument="EURUSD", raise_on_fail=False,
                               write_report=False, cfg_override=_override(holidays=["2024-05-21"]))
    assert rep_yes["decision"] == DatasetDecision.APPROVE.value


# ── (4) OHLCV completeness enforced (L1 raises) ──────────────────────────────
def test_missing_ohlcv_field_raises(tmp_path):
    ts = _grid(datetime(2024, 5, 21, 0, 0), datetime(2024, 5, 21, 4, 0), MarketType.CRYPTO, 5)
    p = tmp_path / "BTCUSDT_M5.csv"
    _write(p, ts, defect_row=5)                  # one row with an empty close
    with pytest.raises((DatasetIntegrityError, ValueError)):
        validate_dataset(str(p), instrument="BTCUSDT", raise_on_fail=True,
                         write_report=False, cfg_override=_override())


# ── (5) parity: default vs strict ────────────────────────────────────────────
def test_default_tolerates_small_gap_but_strict_rejects(tmp_path):
    """A single missing crypto bar is WITHIN the lenient default tolerance (2% / 100 candles) but
    fails the zero-tolerance strict profile — proving the override is what changes behavior."""
    ts = _grid(datetime(2024, 5, 21, 0, 0), datetime(2024, 5, 21, 6, 0), MarketType.CRYPTO, 5)
    del ts[30]
    p = tmp_path / "BTCUSDT_M5.csv"
    _write(p, ts)
    lenient = {"enforce_path_consistency": False, "session_calendar": _SC,
               "future_ts_tolerance_minutes": 0}   # prod-like thresholds (2% / 100 / 1440)
    rep_default = validate_dataset(str(p), instrument="BTCUSDT", raise_on_fail=False,
                                   write_report=False, cfg_override=lenient)
    rep_strict = validate_dataset(str(p), instrument="BTCUSDT", raise_on_fail=False,
                                  write_report=False, cfg_override=_override())
    assert rep_default["decision"] in (DatasetDecision.APPROVE.value, DatasetDecision.WARN.value)
    assert rep_strict["decision"] == DatasetDecision.REJECT.value


def test_config_mode_crypto_ignores_holidays(tmp_path):
    """24x7 spot crypto trades through TradFi holidays — in config-calendar mode a holiday date
    must NOT suppress crypto bars (regression guard: holidays apply to WEEKDAY markets only)."""
    ts = _grid(datetime(2024, 12, 24, 0, 0), datetime(2024, 12, 27, 0, 0), MarketType.CRYPTO, 5)
    p = tmp_path / "BTCUSDT_M5.csv"
    _write(p, ts)
    # 2024-12-25 is in the listed holidays, but crypto is 24x7 → a complete grid still APPROVES,
    # and a genuine hole still REJECTS regardless of the holiday list.
    ov = _override(holidays=["2024-12-25"])
    assert validate_dataset(str(p), instrument="BTCUSDT", raise_on_fail=False, write_report=False,
                            cfg_override=ov)["decision"] == DatasetDecision.APPROVE.value
    del ts[100]
    _write(p, ts)
    assert validate_dataset(str(p), instrument="BTCUSDT", raise_on_fail=False, write_report=False,
                            cfg_override=ov)["decision"] == DatasetDecision.REJECT.value


def test_known_gaps_accepts_specific_range_only(tmp_path):
    """A reviewed known_gaps range accepts a genuine intraday hole WITHOUT whole-day marking; a
    DIFFERENT hole still hard-stops; a symbol-scoped entry does not accept another symbol."""
    full = _grid(datetime(2024, 5, 21, 0, 0), datetime(2024, 5, 21, 12, 0), MarketType.WEEKDAY, 15)
    hole = datetime(2024, 5, 21, 3, 0)                       # drop 03:00 & 03:15 (2 bars)
    kept = [t for t in full if t not in (hole, hole.replace(minute=15))]
    p = tmp_path / "EURUSD_M15.csv"
    _write(p, kept)

    kg = [{"symbol": "EURUSD", "from": "2024-05-21T03:00:00", "to": "2024-05-21T03:30:00",
           "reason": "reviewed broker outage"}]
    ov = _override()
    ov["session_calendar"] = {**_SC, "known_gaps": kg}
    assert validate_dataset(str(p), instrument="EURUSD", raise_on_fail=False, write_report=False,
                            cfg_override=ov)["decision"] == DatasetDecision.APPROVE.value

    # a DIFFERENT hole (not covered by known_gaps) still REJECTS
    kept2 = [t for t in kept if t != datetime(2024, 5, 21, 8, 0)]
    _write(p, kept2)
    assert validate_dataset(str(p), instrument="EURUSD", raise_on_fail=False, write_report=False,
                            cfg_override=ov)["decision"] == DatasetDecision.REJECT.value

    # symbol-scoped to EURUSD → does NOT accept the same clock-time hole on GBPUSD
    pg = tmp_path / "GBPUSD_M15.csv"
    _write(pg, kept)
    assert validate_dataset(str(pg), instrument="GBPUSD", raise_on_fail=False, write_report=False,
                            cfg_override=ov)["decision"] == DatasetDecision.REJECT.value


def test_known_gaps_empty_is_parity(tmp_path):
    """Empty known_gaps ⇒ identical decision to not specifying it (byte-parity)."""
    full = _grid(datetime(2024, 5, 21, 0, 0), datetime(2024, 5, 21, 12, 0), MarketType.WEEKDAY, 15)
    p = tmp_path / "EURUSD_M15.csv"
    _write(p, full)
    a = validate_dataset(str(p), instrument="EURUSD", raise_on_fail=False, write_report=False,
                         cfg_override=_override())
    ov = _override(); ov["session_calendar"] = {**_SC, "known_gaps": []}
    b = validate_dataset(str(p), instrument="EURUSD", raise_on_fail=False, write_report=False,
                         cfg_override=ov)
    assert a["decision"] == b["decision"] == DatasetDecision.APPROVE.value


def test_cfg_override_none_is_parity(tmp_path):
    """cfg_override=None must be byte-identical to passing the loaded config's own values."""
    ts = _grid(datetime(2024, 5, 21, 0, 0), datetime(2024, 5, 21, 4, 0), MarketType.CRYPTO, 5)
    p = tmp_path / "BTCUSDT_M5.csv"
    _write(p, ts)
    a = validate_dataset(str(p), instrument="BTCUSDT", raise_on_fail=False, write_report=False)
    b = validate_dataset(str(p), instrument="BTCUSDT", raise_on_fail=False, write_report=False,
                         cfg_override=None)
    assert a["decision"] == b["decision"] and a["hard_failures"] == b["hard_failures"]
