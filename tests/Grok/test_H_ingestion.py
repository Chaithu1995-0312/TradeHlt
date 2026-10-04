"""H. Data ingestion — duplicates, order, malformed/impossible OHLC, empty, edges.

Semantic invariant: a candle that cannot exist in the market must not become a
CRT Candle. L1 row validation (ohlcv_schema) and L3 sequence validation
(dataset_integrity) are different gates — a file can pass one and fail the other.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from data_ingestion.dataset_integrity import validate_dataset
from data_ingestion.ohlcv_schema import DatasetIntegrityError, validate_ohlcv_row
from runtime.backtest_v2 import CandleLoader


_HEADER = "timestamp,open,high,low,close,volume"
_BASE = datetime(2026, 1, 5, 10, 0, 0)  # Monday


def _row(ts: datetime, o=100.0, h=101.0, l=99.0, c=100.5, v=10.0) -> str:
    return f"{ts.strftime('%Y-%m-%d %H:%M:%S')},{o},{h},{l},{c},{v}"


def _write(tmp: Path, lines: list[str]) -> Path:
    p = tmp / "EURUSD_M15.csv"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def _l3_override() -> dict:
    return {
        "enforce_path_consistency": False,
        "future_ts_tolerance_minutes": 10_000_000,
        "default_bar_minutes": 15,
    }


def test_row_gate_rejects_high_lt_low():
    """Source: ohlcv_schema.validate_ohlcv_row"""
    with pytest.raises(ValueError, match="inconsistent candle"):
        validate_ohlcv_row(100.0, 99.0, 101.0, 100.0, 10.0)


def test_row_gate_rejects_close_above_high():
    with pytest.raises(ValueError, match="inconsistent candle"):
        validate_ohlcv_row(100.0, 101.0, 99.0, 102.0, 10.0)


def test_row_gate_rejects_negative_volume():
    with pytest.raises(ValueError, match="negative volume"):
        validate_ohlcv_row(100.0, 101.0, 99.0, 100.0, -1.0)


def test_loader_stream_rejects_impossible_ohlc(tmp_path: Path):
    """CandleLoader.stream is fail-closed on geometry (backtest_v2.py:839)."""
    ts = _BASE
    p = _write(tmp_path, [_HEADER, _row(ts, h=90.0, l=110.0)])
    with pytest.raises(ValueError, match="inconsistent candle"):
        list(CandleLoader(str(p), instrument="EURUSD").stream())


def test_loader_stream_rejects_duplicate_timestamps(tmp_path: Path):
    ts = _BASE
    p = _write(tmp_path, [_HEADER, _row(ts), _row(ts)])
    with pytest.raises(DatasetIntegrityError, match="Duplicate timestamp"):
        list(CandleLoader(str(p), instrument="EURUSD").stream())


def test_loader_stream_rejects_out_of_order(tmp_path: Path):
    p = _write(
        tmp_path,
        [_HEADER, _row(_BASE + timedelta(minutes=15)), _row(_BASE)],
    )
    with pytest.raises(ValueError, match="Out-of-order"):
        list(CandleLoader(str(p), instrument="EURUSD").stream())


def test_loader_stream_rejects_midfile_blank(tmp_path: Path):
    p = _write(
        tmp_path,
        [_HEADER, _row(_BASE), "", _row(_BASE + timedelta(minutes=15))],
    )
    with pytest.raises(DatasetIntegrityError, match="Blank line"):
        list(CandleLoader(str(p), instrument="EURUSD").stream())


def test_loader_stream_accepts_trailing_blank(tmp_path: Path):
    p = tmp_path / "EURUSD_M15.csv"
    p.write_text(
        _HEADER
        + "\n"
        + _row(_BASE)
        + "\n"
        + _row(_BASE + timedelta(minutes=15))
        + "\n\n",
        encoding="utf-8",
    )
    bars = list(CandleLoader(str(p), instrument="EURUSD").stream())
    assert len(bars) == 2


def test_loader_stream_empty_file_is_not_a_silent_series(tmp_path: Path):
    p = _write(tmp_path, [_HEADER])
    bars = list(CandleLoader(str(p), instrument="EURUSD").stream())
    assert bars == []


def test_l3_sequence_gate_does_not_call_row_geometry():
    """Class C: L3 owns sequence; ohlcv_schema owns high/low consistency.

    Source: dataset_integrity.py module docstring (lines 5–7).
    """
    import inspect

    from data_ingestion import dataset_integrity as di

    src = inspect.getsource(di.validate_dataset)
    assert "validate_ohlcv_row" not in src


def test_l3_does_reject_duplicate_timestamps(tmp_path: Path):
    ts = _BASE
    p = _write(tmp_path, [_HEADER, _row(ts), _row(ts)])
    with pytest.raises(DatasetIntegrityError, match="duplicate"):
        validate_dataset(
            str(p),
            instrument="EURUSD",
            bar_minutes=15,
            write_report=False,
            raise_on_fail=True,
            cfg_override=_l3_override(),
        )


def test_partial_row_is_rejected_by_loader(tmp_path: Path):
    p = tmp_path / "EURUSD_M15.csv"
    p.write_text(
        _HEADER + "\n" + "2026-01-05 10:00:00,100,101,99\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="non-numeric or missing"):
        list(CandleLoader(str(p), instrument="EURUSD").stream())
