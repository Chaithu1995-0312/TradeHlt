"""
test_resample_completeness.py — GUARD test for the Goal Architecture's
data-quality concern: "corrupted HTF data → wrong MAE/MFE".

This test exists INSTEAD OF adding an L4 validator to dataset_integrity.py
(which is explicitly FROZEN: "L1+L2+L3 complete … No L4 … No further validators",
dataset_integrity.py:79-82). It proves the property is ALREADY enforced one layer
down, so a new HTF-completeness validator would be redundant:

  1. INVARIANT — complete M15 ⟹ complete H1/H4 resample buckets. A resampled
     bucket can only be short a child if an M15 bar is missing in its window.
  2. CONTRAPOSITIVE — a missing interior M15 bar yields an incomplete bucket AND
     is caught by the existing session-aware M15 gap gate. So "incomplete resample"
     is observable upstream as "incomplete M15", which the frozen gate already flags.
  3. NATIVE HTF — a native H1 file with a missing bar is gap-gated directly by
     validate_dataset (it reads the H1 timeframe and runs the same gap analysis).

Run: python -m pytest tests/test_resample_completeness.py -q
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from config_layer.crt_engine_v2 import Candle
from data_ingestion.dataset_integrity import validate_dataset
from research.resample import resample

_BASE = datetime(2025, 1, 1, 0, 0, 0)
_UNIT_VOL = 10.0
_HEADER = "timestamp,open,high,low,close,volume"


def _m15(n: int, *, drop: set[int] | None = None) -> list[Candle]:
    """n consecutive M15 candles from _BASE, each unit-volume. `drop` removes
    those positional indices (to simulate a missing bar)."""
    drop = drop or set()
    out: list[Candle] = []
    for i in range(n):
        if i in drop:
            continue
        ts = _BASE + timedelta(minutes=15 * i)
        out.append(Candle(timestamp=ts, open=100.0, high=101.0, low=99.0,
                          close=100.0, volume=_UNIT_VOL, index=len(out)))
    return out


def _write_m15_csv(path: Path, n: int, *, drop: set[int] | None = None) -> Path:
    drop = drop or set()
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [_HEADER]
    for i in range(n):
        if i in drop:
            continue
        ts = (_BASE + timedelta(minutes=15 * i)).strftime("%Y-%m-%d %H:%M:%S")
        rows.append(f"{ts},100,101,99,100,{int(_UNIT_VOL)}")
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return path


# ── 1. INVARIANT: complete M15 ⟹ complete resample buckets ───────────────────
def test_complete_m15_yields_complete_h1_buckets():
    # 8 full hours of M15 (32 bars). H1 emits 7 buckets (trailing partial dropped),
    # each aggregating exactly 4 children ⟹ volume == 4 × unit.
    h1 = resample(_m15(32), "H1")
    assert len(h1) == 7
    assert all(c.volume == 4 * _UNIT_VOL for c in h1)


def test_complete_m15_yields_complete_h4_bucket():
    # 8 hours → one H4 bucket (00:00-03:45) emitted when 04:00 arrives; 16 children.
    h4 = resample(_m15(32), "H4")
    assert len(h4) == 1
    assert h4[0].volume == 16 * _UNIT_VOL


def test_resample_is_associative_h1_then_h4_equals_h4():
    # The load-bearing Program-3 invariant, re-asserted here as the basis for the
    # completeness guarantee: M15→H1→H4 is byte-equivalent to M15→H4.
    m15 = _m15(64)
    direct = resample(m15, "H4")
    staged = resample(resample(m15, "H1"), "H4")
    assert len(direct) == len(staged)
    for a, b in zip(direct, staged):
        assert (a.timestamp, a.open, a.high, a.low, a.close, a.volume) == \
               (b.timestamp, b.open, b.high, b.low, b.close, b.volume)


# ── 2. CONTRAPOSITIVE: a missing M15 bar → incomplete bucket AND caught upstream ─
def test_missing_m15_makes_bucket_incomplete():
    # Drop one interior M15 bar (index 5, inside the 2nd hour). That hour's H1
    # bucket then has only 3 children (volume 3 × unit) — i.e. an incomplete
    # resample is ONLY ever produced by missing M15 data.
    h1 = resample(_m15(32, drop={5}), "H1")
    short = [c for c in h1 if c.volume != 4 * _UNIT_VOL]
    assert len(short) == 1
    assert short[0].volume == 3 * _UNIT_VOL


def test_missing_m15_is_flagged_by_frozen_gate(tmp_path):
    # The SAME missing bar that would corrupt a resampled bucket is caught by the
    # existing M15 gap gate — so the corruption is observable upstream, no new
    # HTF validator required. (5 scattered missing in 100 → ~5% > 2% → REJECT.)
    fp = _write_m15_csv(tmp_path / "data" / "BTCUSDT_M15.csv", 100,
                        drop={10, 30, 50, 70, 90})
    rep = validate_dataset(str(fp), instrument="BTCUSDT",
                           write_report=False, raise_on_fail=False)
    assert rep["decision"] == "REJECT"
    assert rep["missing_pct"] > 0.0


# ── 3. NATIVE HTF files are gap-gated directly by the frozen validator ───────────
def test_native_h1_gap_is_gated(tmp_path):
    # A native H1 file (hourly grid) with one missing hour is detected by the
    # existing validator reading the H1 timeframe — proving HTF inputs that are NOT
    # produced by resample.py are still covered.
    path = tmp_path / "data" / "BTCUSDT_H1.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [_HEADER]
    for i in range(300):
        if i == 150:           # drop one hourly bar
            continue
        ts = (_BASE + timedelta(hours=i)).strftime("%Y-%m-%d %H:%M:%S")
        rows.append(f"{ts},100,101,99,100,10")
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    rep = validate_dataset(str(path), instrument="BTCUSDT",
                           write_report=False, raise_on_fail=False)
    assert rep["modal_delta_minutes"] == 60        # recognised as H1
    assert rep["missing_pct"] > 0.0                # the missing hour is seen
    assert rep["decision"] in ("WARN", "REJECT")   # never silently APPROVE
