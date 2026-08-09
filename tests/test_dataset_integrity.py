"""
test_dataset_integrity.py — L2 whole-dataset sequence integrity gate +
L1 duplicate-header extension + inline CandleLoader guard.

Run: python -m pytest tests/test_dataset_integrity.py -q
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from data_ingestion.dataset_integrity import (
    MarketType,
    classify_market,
    validate_dataset,
    validate_universe,
)
from data_ingestion.ohlcv_schema import (
    DatasetIntegrityError,
    require_unique_ohlcv_headers,
)

_SESSION_SC = {"weekday_open_hour": 22, "weekday_close_hour": 21}


def _weekday_tradable(dt) -> bool:
    # Mirrors the validator's WEEKDAY session: Sun>=22 open, Fri<21 close,
    # Sat closed, daily rollover break at hour 21.
    wd = dt.weekday()
    if wd == 5:
        return False
    if wd == 6:
        return dt.hour >= 22
    if wd == 4 and dt.hour >= 21:
        return False
    return dt.hour != 21

_BASE = datetime(2025, 1, 1, 0, 0, 0)
_HEADER = "timestamp,open,high,low,close,volume"


def _row(ts: datetime) -> str:
    # A valid, self-consistent candle (high>=open/close, low<=open/close).
    return f"{ts.strftime('%Y-%m-%d %H:%M:%S')},100,101,99,100,10"


def _write_csv(path: Path, timestamps, header: str = _HEADER) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [header] + [_row(ts) for ts in timestamps]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _grid(n: int, step_min: int = 15, start: datetime = _BASE):
    return [start + timedelta(minutes=step_min * i) for i in range(n)]


def _data_file(tmp_path: Path, name: str, timestamps, header: str = _HEADER) -> Path:
    # Place under a "data" subdir so path-consistency passes by default.
    return _write_csv(tmp_path / "data" / name, timestamps, header)


# ── pass path ───────────────────────────────────────────────────────────────
def test_clean_dataset_approves(tmp_path):
    fp = _data_file(tmp_path, "BTCUSDT_M15.csv", _grid(500))
    rep = validate_dataset(str(fp), instrument="BTCUSDT", write_report=False)
    assert rep["decision"] == "APPROVE"
    assert rep["severity"] == "INFO"
    assert rep["rows"] == 500
    assert rep["missing_pct"] == 0.0
    assert rep["modal_delta_minutes"] == 15


def test_small_gap_reports_only_warn(tmp_path):
    # 800 bars with one 240-min gap (15 missing candles ~1.8% < 2%).
    ts = _grid(400) + _grid(400, start=_BASE + timedelta(minutes=15 * (400 + 15)))
    fp = _data_file(tmp_path, "BTCUSDT_M15.csv", ts)
    rep = validate_dataset(str(fp), instrument="BTCUSDT", write_report=False)
    assert rep["decision"] == "WARN"
    assert rep["severity"] == "WARN"
    assert rep["warnings"]
    assert rep["modal_delta_minutes"] == 15  # mode survives the gap (mean would not)


# ── hard / structural branches ──────────────────────────────────────────────
def test_duplicate_timestamp_raises(tmp_path):
    ts = _grid(50)
    ts[25] = ts[24]  # duplicate
    fp = _data_file(tmp_path, "BTCUSDT_M15.csv", ts)
    with pytest.raises(DatasetIntegrityError, match="duplicate timestamp"):
        validate_dataset(str(fp), instrument="BTCUSDT", write_report=False)


def test_out_of_order_timestamp_raises(tmp_path):
    ts = _grid(50)
    # Backwards but off-grid (7 min) so it is not an already-seen duplicate.
    ts[30] = ts[29] - timedelta(minutes=7)
    fp = _data_file(tmp_path, "BTCUSDT_M15.csv", ts)
    with pytest.raises(DatasetIntegrityError, match="out-of-order"):
        validate_dataset(str(fp), instrument="BTCUSDT", write_report=False)


def test_future_timestamp_raises(tmp_path):
    ts = _grid(20) + [datetime(2090, 1, 1, 0, 0, 0)]
    fp = _data_file(tmp_path, "BTCUSDT_M15.csv", ts)
    with pytest.raises(DatasetIntegrityError, match="future timestamp"):
        validate_dataset(str(fp), instrument="BTCUSDT", write_report=False)


def test_timeframe_mismatch_raises(tmp_path):
    # 5-min spacing but filename says M15 → modal 5 != 15.
    fp = _data_file(tmp_path, "BTCUSDT_M15.csv", _grid(100, step_min=5))
    with pytest.raises(DatasetIntegrityError, match="timeframe mismatch"):
        validate_dataset(str(fp), instrument="BTCUSDT", write_report=False)


def test_path_outside_root_raises(tmp_path):
    # Not under a canonical "data" root.
    fp = _write_csv(tmp_path / "backup" / "BTCUSDT_M15.csv", _grid(50))
    with pytest.raises(DatasetIntegrityError, match="outside canonical data roots"):
        validate_dataset(str(fp), instrument="BTCUSDT", write_report=False)


def test_symbol_mismatch_raises(tmp_path):
    fp = _data_file(tmp_path, "BTCUSDT_M15.csv", _grid(50))
    with pytest.raises(DatasetIntegrityError, match="disagrees with instrument"):
        validate_dataset(str(fp), instrument="ETHUSDT", write_report=False)


# ── missing-candle threshold branches ───────────────────────────────────────
def test_excess_missing_pct_raises(tmp_path):
    # 100-bar grid, drop 5 scattered single bars → ~5% missing, tiny gaps.
    ts = [t for i, t in enumerate(_grid(100)) if i not in (10, 30, 50, 70, 90)]
    fp = _data_file(tmp_path, "BTCUSDT_M15.csv", ts)
    with pytest.raises(DatasetIntegrityError, match="missing .* exceeds"):
        validate_dataset(str(fp), instrument="BTCUSDT", write_report=False)


def test_single_large_gap_span_raises(tmp_path):
    # One 2-day jump → span exceeds 1440 min.
    ts = _grid(50) + _grid(50, start=_BASE + timedelta(days=2, minutes=15 * 50))
    fp = _data_file(tmp_path, "BTCUSDT_M15.csv", ts)
    with pytest.raises(DatasetIntegrityError, match="gap span|single gap"):
        validate_dataset(str(fp), instrument="BTCUSDT", write_report=False)


def test_recon_mode_does_not_raise(tmp_path):
    ts = _grid(50)
    ts[25] = ts[24]
    fp = _data_file(tmp_path, "BTCUSDT_M15.csv", ts)
    rep = validate_dataset(str(fp), instrument="BTCUSDT",
                           write_report=False, raise_on_fail=False)
    assert rep["decision"] == "REJECT"
    assert rep["severity"] == "FATAL"


# ── L1 duplicate-header extension ───────────────────────────────────────────
def test_duplicate_header_raises_directly():
    with pytest.raises(ValueError, match="duplicate column headers"):
        require_unique_ohlcv_headers(
            ["timestamp", "open", "high", "low", "close", "volume", "volume"]
        )


def test_duplicate_header_in_file_raises(tmp_path):
    fp = _data_file(tmp_path, "BTCUSDT_M15.csv", _grid(20),
                    header=_HEADER + ",volume")
    with pytest.raises(ValueError, match="duplicate column headers"):
        validate_dataset(str(fp), instrument="BTCUSDT", write_report=False)


# ── session-aware FX/metals handling ────────────────────────────────────────
def test_classify_market():
    cfg = {"session_calendar": {"crypto_quote_suffixes": ["USDT", "USDC", "BUSD"]}}
    assert classify_market("BTCUSDT", cfg) is MarketType.CRYPTO
    assert classify_market("BNBUSDT", cfg) is MarketType.CRYPTO
    assert classify_market("GBPUSD", cfg) is MarketType.WEEKDAY   # FX
    assert classify_market("XAUUSD", cfg) is MarketType.WEEKDAY   # metals


def test_fx_weekend_gaps_approve(tmp_path):
    # Build an FX dataset that is exactly the tradable weekday grid across two
    # weekends. The Fri->Sun closes must NOT be flagged (session-aware): a 24x7
    # model would reject this at ~30% "missing".
    start = datetime(2025, 1, 5, 22, 0, 0)  # a Sunday 22:00
    grid = [start + timedelta(minutes=15 * i) for i in range(14 * 96)]
    ts = [t for t in grid if _weekday_tradable(t)]
    fp = _data_file(tmp_path, "GBPUSD_M15.csv", ts)
    rep = validate_dataset(str(fp), instrument="GBPUSD", write_report=False)
    assert rep["market_type"] == "weekday"
    assert rep["decision"] in ("APPROVE", "WARN")  # weekend closes excluded
    assert rep["missing_pct"] == 0.0


def test_fx_real_midweek_outage_still_rejects(tmp_path):
    # A genuine mid-week (Tue->Wed) outage of >100 tradable candles must reject
    # even for FX — session-awareness must not blind the gate to real corruption.
    start = datetime(2025, 1, 6, 0, 0, 0)  # Monday 00:00
    grid = [start + timedelta(minutes=15 * i) for i in range(7 * 96)]
    full = [t for t in grid if _weekday_tradable(t)]
    # Drop a contiguous Tue block of ~150 tradable candles.
    drop = set(full[100:250])
    ts = [t for t in full if t not in drop]
    fp = _data_file(tmp_path, "GBPUSD_M15.csv", ts)
    with pytest.raises(DatasetIntegrityError):
        validate_dataset(str(fp), instrument="GBPUSD", write_report=False)


# ── inline CandleLoader guard (defense-in-depth) ────────────────────────────
def test_candleloader_inline_guard_duplicate(tmp_path):
    from runtime.backtest_v2 import CandleLoader
    ts = _grid(20)
    ts[10] = ts[9]
    fp = _data_file(tmp_path, "BTCUSDT_M15.csv", ts)
    with pytest.raises(DatasetIntegrityError, match="Duplicate timestamp"):
        list(CandleLoader(str(fp), "BTCUSDT").stream())


def test_candleloader_inline_guard_out_of_order(tmp_path):
    from runtime.backtest_v2 import CandleLoader
    ts = _grid(20)
    ts[15] = ts[5]
    fp = _data_file(tmp_path, "BTCUSDT_M15.csv", ts)
    with pytest.raises(ValueError, match="Out-of-order"):
        list(CandleLoader(str(fp), "BTCUSDT").stream())


# ── Change 1: fingerprint stats baseline ────────────────────────────────────
def test_stats_baseline_present(tmp_path):
    fp = _data_file(tmp_path, "BTCUSDT_M15.csv", _grid(300))
    rep = validate_dataset(str(fp), instrument="BTCUSDT", write_report=False)
    st = rep["stats"]
    assert st["median_volume"] == 10
    assert st["zero_volume_pct"] == 0.0
    assert st["largest_candle_pct"] >= st["median_range_pct"]
    assert st["min_close"] <= st["median_close"] <= st["max_close"]
    assert st["modal_delta_minutes"] == 15


def test_stats_zero_volume_fraction(tmp_path):
    # 10 rows, 3 with volume 0 → zero_volume_pct == 0.3
    ts = _grid(10)
    path = tmp_path / "data" / "BTCUSDT_M15.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [_HEADER]
    for i, t in enumerate(ts):
        vol = 0 if i < 3 else 10
        lines.append(f"{t:%Y-%m-%d %H:%M:%S},100,101,99,100,{vol}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    rep = validate_dataset(str(path), instrument="BTCUSDT", write_report=False)
    assert rep["stats"]["zero_volume_pct"] == 0.3


# ── L3: validate_universe (cross-file) ──────────────────────────────────────
def test_universe_exact_duplicate_rejects_all(tmp_path):
    # Two byte-identical files under different symbols → same SHA-256 → REJECT both.
    grid = _grid(300)
    _data_file(tmp_path, "BTCUSDT_M15.csv", grid)
    _data_file(tmp_path, "ETHUSDT_M15.csv", grid)  # identical content
    res = validate_universe(str(tmp_path / "data"), write_report=False)
    decisions = res["decisions"]
    assert all(d == "REJECT" for d in decisions.values())  # every member rejected
    dups = res["report"]["exact_duplicates"]
    assert len(dups) == 1
    assert dups[0]["severity"] == "FATAL"
    assert set(dups[0]["files"]) == {"BTCUSDT_M15.csv", "ETHUSDT_M15.csv"}


def test_universe_same_instrument_overlap_warns(tmp_path):
    # Same symbol (BTCUSDT), different timeframe files, overlapping dates, DIFFERENT
    # content (so not an exact duplicate) → WARN, never REJECT.
    _data_file(tmp_path, "BTCUSDT_M15.csv", _grid(300, step_min=15))
    _data_file(tmp_path, "BTCUSDT_M5.csv", _grid(300, step_min=5))
    res = validate_universe(str(tmp_path / "data"), write_report=False)
    assert res["report"]["exact_duplicates"] == []
    overlaps = res["report"]["overlaps"]
    assert len(overlaps) == 1
    assert overlaps[0]["symbol"] == "BTCUSDT"
    assert overlaps[0]["severity"] == "WARN"
    assert all(d != "REJECT" for d in res["decisions"].values())


def test_universe_cross_symbol_no_false_overlap(tmp_path):
    grid = _grid(300)
    # Different symbols, same dates, but DIFFERENT content (avoid exact-dup).
    _data_file(tmp_path, "BTCUSDT_M15.csv", grid)
    eth = tmp_path / "data" / "ETHUSDT_M15.csv"
    eth.parent.mkdir(parents=True, exist_ok=True)
    eth.write_text(
        _HEADER + "\n" + "\n".join(
            f"{t:%Y-%m-%d %H:%M:%S},200,201,199,200,10" for t in grid
        ) + "\n", encoding="utf-8")
    res = validate_universe(str(tmp_path / "data"), write_report=False)
    assert res["report"]["overlaps"] == []
    assert res["report"]["exact_duplicates"] == []


def test_universe_report_summary_and_versioning(tmp_path):
    _data_file(tmp_path, "BTCUSDT_M15.csv", _grid(300))
    res = validate_universe(str(tmp_path / "data"), write_report=False)
    rep = res["report"]
    assert rep["duplicate_resolution_mode"] == "reject_all"
    assert rep["universe_validator_version"]
    assert rep["summary"]["n_files"] == 1
    assert rep["summary"]["n_approve"] == 1
    assert rep["files"][0]["stats"]["median_volume"] == 10


# ── P3 pre-flight gate wiring (skip-not-abort) ──────────────────────────────
def test_preflight_helper_approve_and_reject(tmp_path):
    import logging
    from runtime.backtest_v2 import _preflight_dataset
    log = logging.getLogger("test.preflight")

    ok = _data_file(tmp_path, "BTCUSDT_M15.csv", _grid(500))
    assert _preflight_dataset(str(ok), "BTCUSDT", log) is True  # APPROVE → run

    bad_ts = _grid(50)
    bad_ts[25] = bad_ts[24]  # duplicate → REJECT
    bad = _data_file(tmp_path, "ETHUSDT_M15.csv", bad_ts)
    assert _preflight_dataset(str(bad), "ETHUSDT", log) is False  # REJECT → skip
