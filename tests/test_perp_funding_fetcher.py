"""Tests for src/inout/perp_funding_fetcher.py — deterministic, no network.

The single network seam (`PerpFundingFetcher._get_json`) is monkeypatched with a
Binance-shaped fake that slices a master list by [startTime, endTime) and honors
`limit`, so pagination, dedup, ordering, and byte-identity are all covered offline.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from inout.perp_funding_fetcher import (
    PerpFetcherConfig,
    PerpFundingFetcher,
    _ms_to_str,
    _date_to_ms,
)

_FUNDING_PATH = "/fapi/v1/fundingRate"
_BASIS_PATH = "/fapi/v1/premiumIndexKlines"
_8H_MS = 8 * 60 * 60 * 1000
_M15_MS = 15 * 60 * 1000
_START = "2024-05-22"
_MANDATORY_KEYS = ["base_url", "funding_path", "basis_path", "interval", "max_limit", "out_dir"]


# ── fixtures / builders ───────────────────────────────────────────────────────

def _section(out_dir: Path, max_limit: int = 1000) -> dict:
    return {
        "base_url": "https://fapi.binance.com",
        "instruments": ["BNBUSDT"],
        "funding_path": _FUNDING_PATH,
        "basis_path": _BASIS_PATH,
        "interval": "15m",
        "request_timeout_s": 5,
        "request_delay_s": 0,   # no sleeping in tests
        "max_limit": max_limit,
        "out_dir": str(out_dir),
    }


def _make_funding(n: int, start_ms: int, step: int = _8H_MS) -> list[dict]:
    return [
        {"symbol": "BNBUSDT", "fundingTime": start_ms + i * step,
         "fundingRate": f"{0.0001 * (i + 1):.8f}"}
        for i in range(n)
    ]


def _make_klines(n: int, start_ms: int, step: int = _M15_MS) -> list[list]:
    # Binance kline array: [openTime, open, high, low, close, volume, closeTime, ...]
    out = []
    for i in range(n):
        ot = start_ms + i * step
        close = f"{0.0001 * (i + 1):.8f}"
        out.append([ot, "0", "0", "0", close, "0", ot + step - 1, "0", 0, "0", "0", "0"])
    return out


def _fake_get_json(master_by_path: dict[str, list], time_of):
    """Binance-shaped fake: slice master by [startTime, endTime), honor limit."""
    def fake(path: str, params: dict):
        st, en, lim = int(params["startTime"]), int(params["endTime"]), int(params["limit"])
        sel = [r for r in master_by_path[path] if st <= time_of(path, r) < en]
        return sel[:lim]
    return fake


def _time_of(path: str, row):
    return int(row["fundingTime"]) if path == _FUNDING_PATH else int(row[0])


# ── pure normalizers ──────────────────────────────────────────────────────────

def test_normalize_funding_schema():
    raw = [
        {"fundingTime": 300, "fundingRate": "0.0003"},
        {"fundingTime": 100, "fundingRate": "0.0001"},
        {"fundingTime": 200, "fundingRate": "0.0002"},
        {"fundingTime": 100, "fundingRate": "0.0001"},  # duplicate
    ]
    rows = PerpFundingFetcher._normalize_funding(raw)
    assert rows == [(100, 0.0001), (200, 0.0002), (300, 0.0003)]
    assert all(isinstance(ts, int) and isinstance(v, float) for ts, v in rows)


def test_normalize_basis_schema():
    raw = [
        [200, "1", "1", "1", "0.002", "0", 1, "0"],
        [100, "1", "1", "1", "0.001", "0", 1, "0"],
        [100, "1", "1", "1", "0.001", "0", 1, "0"],  # duplicate
    ]
    rows = PerpFundingFetcher._normalize_basis(raw)
    assert rows == [(100, 0.001), (200, 0.002)]
    assert all(isinstance(ts, int) and isinstance(v, float) for ts, v in rows)


# ── pagination ────────────────────────────────────────────────────────────────

def test_pagination_advances_no_dup(tmp_path, monkeypatch):
    start_ms = _date_to_ms(_START)
    master = _make_funding(7, start_ms)
    cfg = PerpFetcherConfig.from_section(_section(tmp_path, max_limit=3))
    fetcher = PerpFundingFetcher(cfg)
    monkeypatch.setattr(
        fetcher, "_get_json",
        _fake_get_json({_FUNDING_PATH: master}, _time_of),
    )
    end_ms = start_ms + 8 * _8H_MS
    raw = fetcher._paginate_funding("BNBUSDT", start_ms, end_ms)   # 3+3+1 pages
    rows = PerpFundingFetcher._normalize_funding(raw)
    times = [t for t, _ in rows]
    assert len(rows) == 7
    assert times == sorted(set(times))   # ascending, no duplicates


def test_pagination_non_advancing_raises(tmp_path, monkeypatch):
    start_ms = _date_to_ms(_START)
    master = _make_funding(7, start_ms)
    cfg = PerpFetcherConfig.from_section(_section(tmp_path, max_limit=3))
    fetcher = PerpFundingFetcher(cfg)

    # Buggy endpoint: always returns the same full first page (ignores startTime).
    def buggy(path, params):
        return master[:3]

    monkeypatch.setattr(fetcher, "_get_json", buggy)
    with pytest.raises(RuntimeError, match="not advancing"):
        fetcher._paginate_funding("BNBUSDT", start_ms, start_ms + 8 * _8H_MS)


def test_expected_row_counts_small_fixture(tmp_path, monkeypatch):
    start_ms = _date_to_ms(_START)
    master = _make_funding(1000, start_ms)   # two 500-row pages
    cfg = PerpFetcherConfig.from_section(_section(tmp_path, max_limit=500))
    fetcher = PerpFundingFetcher(cfg)
    monkeypatch.setattr(
        fetcher, "_get_json",
        _fake_get_json({_FUNDING_PATH: master}, _time_of),
    )
    end_ms = start_ms + 1001 * _8H_MS
    raw = fetcher._paginate_funding("BNBUSDT", start_ms, end_ms)
    rows = PerpFundingFetcher._normalize_funding(raw)
    assert len(rows) == 1000   # exactly, no duplicate-page inflation


# ── full fetch / determinism ──────────────────────────────────────────────────

def _wire_full_fetch(tmp_path, monkeypatch, n=50):
    start_ms = _date_to_ms(_START)
    master = {
        _FUNDING_PATH: _make_funding(n, start_ms),
        _BASIS_PATH: _make_klines(n, start_ms),
    }
    cfg = PerpFetcherConfig.from_section(_section(tmp_path, max_limit=1000))
    fetcher = PerpFundingFetcher(cfg)
    monkeypatch.setattr(fetcher, "_get_json", _fake_get_json(master, _time_of))
    return fetcher, start_ms, n


def test_fetch_byte_identical(tmp_path, monkeypatch):
    a, b = tmp_path / "a", tmp_path / "b"
    end = "2026-05-22"

    fetcher_a, _, _ = _wire_full_fetch(a, monkeypatch)
    paths_a = fetcher_a.fetch("BNBUSDT", _START, end)

    fetcher_b, _, _ = _wire_full_fetch(b, monkeypatch)
    paths_b = fetcher_b.fetch("BNBUSDT", _START, end)

    for sig in ("funding", "basis"):
        assert paths_a[sig].read_bytes() == paths_b[sig].read_bytes()


def test_fetch_writes_expected_headers(tmp_path, monkeypatch):
    fetcher, _, _ = _wire_full_fetch(tmp_path, monkeypatch)
    paths = fetcher.fetch("BNBUSDT", _START, "2026-05-22")
    assert paths["funding"].read_text().splitlines()[0] == "timestamp,funding_rate"
    assert paths["basis"].read_text().splitlines()[0] == "timestamp,premium_index"
    assert paths["funding"].name == "BNBUSDT_FUNDING_8H.csv"
    assert paths["basis"].name == "BNBUSDT_BASIS_M15.csv"


def test_timestamp_format_matches_spot(tmp_path, monkeypatch):
    """Emitted timestamps must match the spot CSV format exactly — guards the
    future panel inner-join against ISO8601 / offset drift."""
    fetcher, start_ms, _ = _wire_full_fetch(tmp_path, monkeypatch)
    paths = fetcher.fetch("BNBUSDT", _START, "2026-05-22")
    first_ts = paths["funding"].read_text().splitlines()[1].split(",")[0]
    assert first_ts == "2024-05-22 00:00:00"          # not 2024-05-22T00:00:00Z / +00:00
    assert first_ts == _ms_to_str(start_ms)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", first_ts)


# ── config strictness ─────────────────────────────────────────────────────────

def test_from_prod_config(tmp_path):
    prod_cfg = {"perp_funding_data": _section(tmp_path)}
    cfg = PerpFetcherConfig.from_prod_config(prod_cfg)
    assert cfg.base_url == "https://fapi.binance.com"
    assert cfg.instruments == ("BNBUSDT",)
    assert cfg.funding_path == _FUNDING_PATH
    assert cfg.basis_path == _BASIS_PATH
    assert cfg.interval == "15m"
    assert cfg.max_limit == 1000
    assert cfg.out_dir == Path(str(tmp_path))


@pytest.mark.parametrize("missing", _MANDATORY_KEYS)
def test_missing_config_key_raises(tmp_path, missing):
    section = _section(tmp_path)
    section.pop(missing)
    with pytest.raises(KeyError, match=missing):
        PerpFetcherConfig.from_section(section)
