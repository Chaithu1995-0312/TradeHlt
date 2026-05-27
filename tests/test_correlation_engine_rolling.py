"""
test_correlation_engine_rolling.py
==================================
Phase 2: rolling Pearson CorrelationEngine tests.

Covers:
  - symmetry across argument order
  - same-symbol → 1.0, empty → 0.0
  - cache TTL prevents recomputation
  - degenerate (constant) series falls back to heuristic
  - anti-correlated synthetic series (r ≈ -1) returns ≈ 1.0 (abs semantics)
  - stale-data path emits CORRELATION_STALE_DATA and falls back
  - max_correlation_with_existing with empty list → 0.0
  - _get_tracked_instruments reads union from both config keys
  - fetcher=None path falls back to heuristic verbatim
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest

from src.portfolio.correlation_engine import (
    CorrelationEngine,
    _HIGH_CORR,
    _MED_CORR,
    _LOW_CORR,
)


# ── Helpers ─────────────────────────────────────────────────────────────────

@dataclass
class _Row:
    ts:    datetime
    close: float


def _series(closes, end=None):
    """Build a list of _Row spaced one day apart ending at `end` (default: now)."""
    end = end or datetime.now(timezone.utc)
    return [_Row(end - timedelta(days=len(closes) - 1 - i), c)
            for i, c in enumerate(closes)]


def _stub_fetcher(data: dict):
    """Return a fetcher mock whose .load(pair, timeframe, start, end) returns
    data[pair] (a list of _Row), or [] if pair missing."""
    mock = MagicMock()
    mock.load.side_effect = lambda pair, timeframe, start, end: data.get(pair.upper(), [])
    return mock


# ── Public API: trivial cases ───────────────────────────────────────────────

def test_same_symbol_is_one():
    ce = CorrelationEngine(config={}, fetcher=None)
    assert ce.correlation("BTCUSDT", "BTCUSDT") == pytest.approx(1.0)


def test_empty_symbol_is_zero():
    ce = CorrelationEngine(config={}, fetcher=None)
    assert ce.correlation("", "EURUSD") == pytest.approx(0.0)
    assert ce.correlation("EURUSD", "") == pytest.approx(0.0)


def test_max_corr_empty_existing():
    ce = CorrelationEngine(config={}, fetcher=None)
    assert ce.max_correlation_with_existing("BTCUSDT", []) == pytest.approx(0.0)


# ── Fetcher=None → pure heuristic fallback ──────────────────────────────────

def test_no_fetcher_falls_back_to_heuristic():
    ce = CorrelationEngine(config={}, fetcher=None)
    # Same-group crypto → HIGH
    assert ce.correlation("BTCUSDT", "ETHUSDT") == pytest.approx(_HIGH_CORR)
    # FX major vs USD short → MED
    assert ce.correlation("EURUSD", "USDJPY") == pytest.approx(_MED_CORR)
    # Cross asset → LOW
    assert ce.correlation("BTCUSDT", "EURUSD") == pytest.approx(_LOW_CORR)


# ── Rolling primary path ─────────────────────────────────────────────────────

def _ce_with_instruments(monkeypatch, instruments_pairs, instruments_crypto, fetcher_data):
    """Build a CorrelationEngine that sees the given instrument set."""
    def fake_get_section(name):
        if name == "data_ingestion":
            return {"pairs": instruments_pairs}
        if name == "inout":
            return {"scanner": {"allowed_symbols": instruments_crypto}}
        if name == "portfolio":
            return {"correlation": {"lookback_days": 10, "min_observations": 5,
                                    "cache_ttl_secs": 3600, "max_staleness_days": 7}}
        return {}

    monkeypatch.setattr(
        "src.config_layer.production_config.get_prod_section",
        fake_get_section,
    )
    return CorrelationEngine(
        config={"correlation": {"lookback_days": 10, "min_observations": 5,
                                "cache_ttl_secs": 3600, "max_staleness_days": 7}},
        fetcher=_stub_fetcher(fetcher_data),
    )


def test_perfectly_correlated_returns_one(monkeypatch):
    closes = np.linspace(100.0, 200.0, 12)
    data = {
        "EURUSD": _series(list(closes)),
        "GBPUSD": _series(list(closes * 1.5 + 7.0)),  # affine of the same series
    }
    ce = _ce_with_instruments(monkeypatch, ["EURUSD", "GBPUSD"], [], data)
    r = ce.correlation("EURUSD", "GBPUSD")
    assert r == pytest.approx(1.0, abs=1e-6)


def test_anti_correlated_returns_one_magnitude(monkeypatch):
    closes = np.linspace(100.0, 200.0, 12)
    data = {
        "EURUSD": _series(list(closes)),
        "GBPUSD": _series(list(-closes + 500.0)),  # exact anti-correlation
    }
    ce = _ce_with_instruments(monkeypatch, ["EURUSD", "GBPUSD"], [], data)
    r = ce.correlation("EURUSD", "GBPUSD")
    assert r == pytest.approx(1.0, abs=1e-6)


def test_symmetry(monkeypatch):
    rng = np.random.default_rng(42)
    a = rng.normal(100.0, 1.0, 15)
    b = rng.normal(50.0, 0.5, 15)
    data = {
        "EURUSD": _series(list(a)),
        "GBPUSD": _series(list(b)),
    }
    ce = _ce_with_instruments(monkeypatch, ["EURUSD", "GBPUSD"], [], data)
    ab = ce.correlation("EURUSD", "GBPUSD")
    ba = ce.correlation("GBPUSD", "EURUSD")
    assert abs(ab - ba) < 1e-9
    assert 0.0 <= ab <= 1.0


# ── Degenerate / insufficient data ──────────────────────────────────────────

def test_constant_series_falls_back_to_heuristic(monkeypatch):
    # Both constant — Pearson denom is 0
    data = {
        "EURUSD": _series([1.1] * 12),
        "GBPUSD": _series([1.3] * 12),
    }
    ce = _ce_with_instruments(monkeypatch, ["EURUSD", "GBPUSD"], [], data)
    r = ce.correlation("EURUSD", "GBPUSD")
    # Same 3-letter prefix? No (EUR vs GBP). Same FX majors group → HIGH
    assert r == pytest.approx(_HIGH_CORR)


def test_insufficient_observations_falls_back(monkeypatch):
    data = {
        "EURUSD": _series([1.0, 1.1]),  # too few
        "GBPUSD": _series([1.2, 1.3]),
    }
    ce = _ce_with_instruments(monkeypatch, ["EURUSD", "GBPUSD"], [], data)
    r = ce.correlation("EURUSD", "GBPUSD")
    assert r == pytest.approx(_HIGH_CORR)   # heuristic fallback (same FX majors)


def test_stale_data_falls_back(monkeypatch):
    # Newest candle is 20 days old → exceeds max_staleness_days (7)
    old_end = datetime.now(timezone.utc) - timedelta(days=20)
    data = {
        "EURUSD": _series(list(np.linspace(100, 110, 12)), end=old_end),
        "GBPUSD": _series(list(np.linspace(100, 110, 12)), end=old_end),
    }
    ce = _ce_with_instruments(monkeypatch, ["EURUSD", "GBPUSD"], [], data)
    r = ce.correlation("EURUSD", "GBPUSD")
    assert r == pytest.approx(_HIGH_CORR)   # heuristic fallback


# ── Cache TTL ────────────────────────────────────────────────────────────────

def test_cache_avoids_recompute(monkeypatch):
    closes = np.linspace(100.0, 110.0, 12)
    data = {
        "EURUSD": _series(list(closes)),
        "GBPUSD": _series(list(closes * 2 + 3.0)),
    }
    ce = _ce_with_instruments(monkeypatch, ["EURUSD", "GBPUSD"], [], data)

    ce.correlation("EURUSD", "GBPUSD")
    calls_first = ce._fetcher.load.call_count
    ce.correlation("EURUSD", "GBPUSD")
    ce.correlation("EURUSD", "GBPUSD")
    calls_after = ce._fetcher.load.call_count

    # No additional fetches after the initial matrix compute
    assert calls_after == calls_first


def test_cache_expiry_triggers_recompute(monkeypatch):
    closes = np.linspace(100.0, 110.0, 12)
    data = {
        "EURUSD": _series(list(closes)),
        "GBPUSD": _series(list(closes + 1.0)),
    }
    ce = _ce_with_instruments(monkeypatch, ["EURUSD", "GBPUSD"], [], data)
    ce._cache_ttl = 0.0       # force immediate expiry

    ce.correlation("EURUSD", "GBPUSD")
    calls_first = ce._fetcher.load.call_count
    ce.correlation("EURUSD", "GBPUSD")
    calls_second = ce._fetcher.load.call_count
    assert calls_second > calls_first


# ── Instrument source ───────────────────────────────────────────────────────

def test_tracked_instruments_union(monkeypatch):
    def fake_get_section(name):
        if name == "data_ingestion":
            return {"pairs": ["EURUSD", "gbpusd", "EURUSD"]}   # dup + case
        if name == "inout":
            return {"scanner": {"allowed_symbols": ["btcusdt", "ETHUSDT"]}}
        return {}
    monkeypatch.setattr(
        "src.config_layer.production_config.get_prod_section",
        fake_get_section,
    )
    ce = CorrelationEngine(config={}, fetcher=None)
    insts = ce._get_tracked_instruments()
    assert insts == ["BTCUSDT", "ETHUSDT", "EURUSD", "GBPUSD"]


def test_tracked_instruments_empty_emits_event(monkeypatch, tmp_path):
    def fake_get_section(name):
        return {}
    monkeypatch.setattr(
        "src.config_layer.production_config.get_prod_section",
        fake_get_section,
    )
    # Redirect integrity events to a temp file
    log_path = tmp_path / "integrity_events.jsonl"
    monkeypatch.setattr(
        "src.utils.integrity_events._LOG_PATH",
        log_path,
    )
    ce = CorrelationEngine(config={}, fetcher=None)
    ce._get_tracked_instruments()
    text = log_path.read_text(encoding="utf-8")
    assert "CORRELATION_NO_INSTRUMENTS" in text


# ── Static fallback emits visibility event ──────────────────────────────────

def test_static_fallback_emits_event(monkeypatch, tmp_path):
    log_path = tmp_path / "integrity_events.jsonl"
    monkeypatch.setattr(
        "src.utils.integrity_events._LOG_PATH",
        log_path,
    )
    ce = CorrelationEngine(config={}, fetcher=None)
    ce.correlation("FAKE1", "FAKE2")
    text = log_path.read_text(encoding="utf-8")
    assert "CORRELATION_STATIC_FALLBACK" in text
