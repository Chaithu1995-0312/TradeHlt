"""Program 12 Slice 1 — one-month projector parity.

Synthetic candles only. Does not require MT5 or on-disk corpora.
"""

from __future__ import annotations

import ast
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from config_layer.crt_engine_v2 import Candle
from research.timeframe_ladder import parity as parity_mod
from research.timeframe_ladder.parity import (
    DECLARED_PARENT_END,
    DECLARED_PARENT_N,
    DECLARED_PARENT_PATH,
    DECLARED_PARENT_START,
    compare_projected_vs_native,
    is_daily_open_slot,
    load_ohlcv_csv,
    parent_window_report,
    project,
)
from research.resample import write_csv


def _c(ts: datetime, o, h, l, c, v=1.0, idx=0) -> Candle:
    return Candle(timestamp=ts, open=o, high=h, low=l, close=c, volume=v, index=idx)


def _m15(start: datetime, n: int, *, base=2000.0) -> list[Candle]:
    out = []
    prev = base
    for i in range(n):
        o = prev
        cl = o + (0.4 if i % 3 else -0.3)
        hi = max(o, cl) + 0.2
        lo = min(o, cl) - 0.2
        out.append(_c(start + timedelta(minutes=15 * i), o, hi, lo, cl, 1.0 + i, i))
        prev = cl
    return out


def test_declared_window_constants():
    assert DECLARED_PARENT_PATH == "data/XAUUSD_M15.csv"
    assert DECLARED_PARENT_N == 2116
    assert DECLARED_PARENT_START == datetime(2026, 7, 7, 1, 0, 0)
    assert DECLARED_PARENT_END == datetime(2026, 8, 6, 23, 45, 0)


def _imported_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module.split(".")[0])
            names.update(a.name for a in node.names)
    return names


def test_module_does_not_import_admission():
    forbidden = {"admit_csv_path", "CandleLoader"}
    lib = Path(parity_mod.__file__)
    cli = Path(__file__).resolve().parents[2] / "scripts" / "research" / "program12_parity_one_month.py"
    assert forbidden.isdisjoint(_imported_names(lib))
    assert forbidden.isdisjoint(_imported_names(cli))


def test_load_ohlcv_csv_roundtrip(tmp_path):
    start = datetime(2026, 7, 7, 1, 0, 0)
    candles = _m15(start, 8)
    path = tmp_path / "parent.csv"
    write_csv(candles, path)
    loaded = load_ohlcv_csv(path)
    assert len(loaded) == 8
    assert loaded[0].timestamp == start
    assert loaded[-1].timestamp == start + timedelta(minutes=15 * 7)
    for a, b in zip(candles, loaded):
        assert a.timestamp == b.timestamp
        assert a.open == b.open
        assert a.high == b.high
        assert a.low == b.low
        assert a.close == b.close


def test_load_ohlcv_csv_survives_admission_monkeypatch(tmp_path, monkeypatch):
    def _boom(*_a, **_k):
        raise AssertionError("admission must not run")

    monkeypatch.setattr(
        "data_ingestion.dataset_registry.admit_csv_path", _boom, raising=False
    )
    path = tmp_path / "XAUUSD_M15.csv"
    write_csv(_m15(datetime(2026, 7, 7, 1, 0, 0), 4), path)
    loaded = load_ohlcv_csv(path)
    assert len(loaded) == 4


def test_load_rejects_non_increasing(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text(
        "timestamp,open,high,low,close,volume\n"
        "2026-07-07 01:15:00,1,1,1,1,1\n"
        "2026-07-07 01:00:00,1,1,1,1,1\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="non-increasing"):
        load_ohlcv_csv(path)


def test_project_h4_from_full_bucket():
    start = datetime(2026, 7, 7, 0, 0, 0)
    m15 = _m15(start, 33)  # two full H4 buckets + first child of the third (closes bucket 2)
    h4 = project(m15, "H4")
    assert len(h4) == 2
    assert h4[0].timestamp == datetime(2026, 7, 7, 0, 0, 0)
    assert h4[1].timestamp == datetime(2026, 7, 7, 4, 0, 0)
    assert h4[0].open == m15[0].open
    assert h4[0].close == m15[15].close
    assert h4[0].high == max(c.high for c in m15[:16])
    assert h4[0].low == min(c.low for c in m15[:16])


def test_is_daily_open_slot():
    assert is_daily_open_slot(datetime(2026, 7, 7, 0, 0, 0), "H4") is True
    assert is_daily_open_slot(datetime(2026, 7, 7, 4, 0, 0), "H4") is False
    assert is_daily_open_slot(datetime(2026, 7, 7, 0, 0, 0), "H1") is True
    assert is_daily_open_slot(datetime(2026, 7, 7, 1, 0, 0), "H1") is False


def test_compare_exact_pass():
    start = datetime(2026, 7, 7, 0, 0, 0)
    m15 = _m15(start, 49)
    h4 = project(m15, "H4")
    native = list(h4) + [_c(datetime(2026, 7, 7, 12, 0, 0), 1, 1, 1, 1)]  # trailing in-progress
    report = compare_projected_vs_native(h4, native, rule="H4")
    assert report["status"] == "PASS"
    assert report["n_other"] == 0
    assert report["n_daily_open_slot"] == 0
    assert report["n_agree"] == len(h4)


def test_compare_daily_open_classified():
    start = datetime(2026, 7, 7, 0, 0, 0)
    m15 = _m15(start, 33)
    h4 = project(m15, "H4")
    native = [Candle(**{**h4[0].__dict__, "open": h4[0].open + 5.0})] + list(h4[1:])
    native.append(_c(datetime(2026, 7, 7, 8, 0, 0), 1, 1, 1, 1))
    report = compare_projected_vs_native(h4, native, rule="H4")
    assert report["status"] == "PASS_DAILY_OPEN_ONLY"
    assert report["n_daily_open_slot"] == 1
    assert report["n_other"] == 0
    assert report["mismatches"][0]["class"] == "daily_open_slot"
    assert report["mismatches"][0]["field"] == "open"


def test_compare_other_mismatch_fails():
    start = datetime(2026, 7, 7, 0, 0, 0)
    m15 = _m15(start, 33)
    h4 = project(m15, "H4")
    native = [h4[0], Candle(**{**h4[1].__dict__, "close": h4[1].close + 1.0})]
    native.append(_c(datetime(2026, 7, 7, 8, 0, 0), 1, 1, 1, 1))
    report = compare_projected_vs_native(h4, native, rule="H4")
    assert report["status"] == "FAIL"
    assert report["n_other"] == 1
    assert report["mismatches"][0]["class"] == "other"


def test_parent_window_report_flags_mismatch():
    rows = _m15(datetime(2026, 7, 7, 1, 0, 0), 4)
    report = parent_window_report(rows)
    assert report["n"] == 4
    assert report["matches_declared_window"] is False
