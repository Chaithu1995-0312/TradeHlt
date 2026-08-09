"""Spine-as-Hypothesis tests — pure (canned SpineSignalSource; no backtest run).

Covers the four guarantees the adapter must hold:
  1. price->ATR conversion is byte-exact (recovered risk/reward distances == spine geometry);
  2. detect() emits ONLY at committed entry bars (pure lookup, no signal elsewhere);
  3. determinism — same source + same candles => identical Signals;
  4. isolation — no spine module (core/engines/config_layer/runtime) imports `research`.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from research.adapters.spine_signal_source import SpineEntry
from research.hypotheses.spine_hypothesis import SpineHypothesis
from research.indicators import atr
from research.measurement.forward_walk import forward_walk

_T0 = datetime(2025, 1, 1)


def _candle(i: int, close: float, hl: float = 5.0):
    return SimpleNamespace(
        index=i, timestamp=_T0 + timedelta(minutes=15 * i),
        high=close + hl, low=close - hl, close=close,
        is_bullish=True, body_ratio=0.6,
    )


def _candles(n: int = 80):
    # gently drifting price so atr() > 0 over any window
    return [_candle(i, 600.0 + (i % 7)) for i in range(n)]


class _FakeSource:
    """Canned SpineSignalSource for one instrument."""

    def __init__(self, entries: dict[int, SpineEntry]):
        self._entries = entries

    def entries(self, instrument: str) -> dict[int, SpineEntry]:
        return self._entries


def _entry_at(idx: int, *, entry=600.0, risk=3.0, reward=6.0, direction="long", ts=""):
    return SpineEntry(entry_index=idx, entry=entry, direction=direction,
                      risk_distance=risk, reward_distance=reward, timestamp=ts, meta={})


# ── 1. price -> ATR conversion is byte-exact ─────────────────────────────────
def test_price_to_atr_conversion_roundtrips_exactly():
    candles = _candles()
    idx = 50
    src = _FakeSource({idx: _entry_at(idx, entry=613.0, risk=4.0, reward=9.0, direction="short")})
    hyp = SpineHypothesis(source=src)

    window = candles[: idx + 1]
    sigs = hyp.detect(window, {}, {"instrument": "BNBUSDT"})
    assert len(sigs) == 1
    s = sigs[0]

    # The Signal must reproduce the spine's exact price geometry.
    assert s.entry == 613.0
    assert s.direction == "short"
    assert s.entry_index == idx
    assert abs(s.sl_atr_mult * s.atr - 4.0) < 1e-9      # risk_distance recovered
    assert abs(s.tp_atr_mult * s.atr - 9.0) < 1e-9      # reward_distance recovered
    # atr used is the SAME research ATR a toy hypothesis would compute on this window.
    assert s.atr == atr(window, hyp.atr_period)


# ── 2. detect emits ONLY at committed entry bars ─────────────────────────────
def test_detect_only_at_entry_bars():
    candles = _candles()
    src = _FakeSource({50: _entry_at(50)})
    hyp = SpineHypothesis(source=src)
    fired = [i for i in range(30, len(candles))
             if hyp.detect(candles[: i + 1], {}, {"instrument": "BNBUSDT"})]
    assert fired == [50]


# ── 3. determinism: identical signals across independent instances ────────────
def test_determinism_identical_signals():
    candles = _candles()
    entries = {40: _entry_at(40, direction="long"), 60: _entry_at(60, direction="short")}

    def run():
        hyp = SpineHypothesis(source=_FakeSource(dict(entries)))
        out = []
        for i in range(30, len(candles)):
            for s in hyp.detect(candles[: i + 1], {}, {"instrument": "BNBUSDT"}):
                out.append((s.entry_index, s.direction, s.entry, s.sl_atr_mult, s.tp_atr_mult, s.atr))
        return out

    assert run() == run()


# ── 3b. end-to-end: produced Signal is valid for the research forward-walk ────
def test_signal_feeds_forward_walk():
    candles = _candles(120)
    idx = 50
    src = _FakeSource({idx: _entry_at(idx, entry=candles[idx].close, risk=3.0, reward=6.0)})
    hyp = SpineHypothesis(source=src)
    s = hyp.detect(candles[: idx + 1], {}, {"instrument": "BNBUSDT"})[0]
    future = candles[idx + 1: idx + 1 + 40]
    out = forward_walk(s, future, max_forward=40, exit_model="intrabar_fixed")
    assert out.outcome in ("TP_HIT", "SL_HIT", "TIMEOUT")
    assert out.signal is s


# ── 3c. index/timestamp alignment guard fires on off-by-one ──────────────────
def test_timestamp_mismatch_raises():
    candles = _candles()
    idx = 50
    # entry carries a DIFFERENT timestamp than the window bar at idx -> must raise.
    bad_ts = (_T0 + timedelta(minutes=15 * (idx + 1))).isoformat()
    src = _FakeSource({idx: _entry_at(idx, ts=bad_ts)})
    hyp = SpineHypothesis(source=src)
    try:
        hyp.detect(candles[: idx + 1], {}, {"instrument": "BNBUSDT"})
        assert False, "expected ValueError on index/timestamp mismatch"
    except ValueError as e:
        assert "mismatch" in str(e)


# ── 3d. version selection restores PROD_VERSION even on failure ──────────────
def test_prod_version_restored_after_run():
    import config_layer.production_config as pc
    import runtime.backtest_v2 as bt
    from research.adapters.spine_signal_source import ProductionSpineSource

    pc_before, bt_before = pc.PROD_VERSION, bt.PROD_VERSION
    src = ProductionSpineSource()
    # Real instrument (CSV resolves) but a non-existent registry version, so the failure
    # lands INSIDE the try-block AFTER PROD_VERSION is set — exercising finally-restore
    # without launching a real backtest.
    src._spine_cfg = {"universe": {"data_dir": "data", "pattern": "*_M15.csv"},
                      "spine": {"prod_version": "__BADVERSION__"}}
    try:
        src._compute_entries("BNBUSDT", "__BADVERSION__")
    except Exception:
        pass
    assert pc.PROD_VERSION == pc_before, "production_config.PROD_VERSION not restored"
    assert bt.PROD_VERSION == bt_before, "backtest_v2.PROD_VERSION not restored"


# ── 4. isolation: the live spine never imports research ──────────────────────
def test_spine_does_not_import_research():
    src_root = Path(__file__).resolve().parents[2] / "src"
    spine_dirs = ["core", "engines", "config_layer", "runtime"]
    offenders = []
    pat = re.compile(r"^\s*(from|import)\s+research(\.|\s|$)", re.MULTILINE)
    for d in spine_dirs:
        for py in (src_root / d).rglob("*.py"):
            text = py.read_text(encoding="utf-8", errors="ignore")
            if pat.search(text):
                offenders.append(str(py.relative_to(src_root)))
    assert not offenders, f"spine modules import research (isolation breach): {offenders}"
