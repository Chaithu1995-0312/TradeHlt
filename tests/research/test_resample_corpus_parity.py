"""Program 9 — on-disk corpus parity: resampled M5 ladder == independently fetched files.

The strongest possible resampler validation: `resample(M5, rule)` must reproduce the
provider-fetched M15/H1/H4 files byte-for-byte (minus each fetched file's final row —
the resampler drops the trailing in-progress bucket unconditionally). One symbol per
provider group runs here (the full 12-symbol sweep is
`scripts/research/verify_m5_resample_parity.py`, gated before any Program-9 run).

Skips cleanly when the corpus is not on disk (data/*.csv is gitignored).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from research.resample import resample                                  # noqa: E402

CASES = [
    ("binance", "BNBUSDT"),
    ("mt5", "EURUSD"),
]
RULES = ("M15", "H1", "H4")
VOL_REL_TOL = 1e-8


def _load(path: Path, symbol: str) -> list:
    from runtime.backtest_v2 import CandleLoader
    candles = list(CandleLoader(str(path), symbol).stream())
    for i, c in enumerate(candles):
        c.index = i
    return candles


@pytest.mark.parametrize("group,symbol", CASES)
@pytest.mark.parametrize("rule", RULES)
def test_resampled_m5_matches_fetched_file(group, symbol, rule):
    gdir = _ROOT / "data" / group
    m5_path = gdir / f"{symbol}_M5.csv"
    ref_path = gdir / f"{symbol}_{rule}.csv"
    if not (m5_path.exists() and ref_path.exists()):
        pytest.skip(f"corpus not on disk: {m5_path} / {ref_path}")

    resampled = resample(_load(m5_path, symbol), rule)
    ref = _load(ref_path, symbol)[:-1]      # resampler drops the trailing bucket

    # STRICT over the coverage INTERSECTION (provider ladders have different depths:
    # MT5 M5 retention ~270d vs 2yr M15/H1/H4 — F-035-era fetch boundary).
    lo = max(resampled[0].timestamp, ref[0].timestamp)
    hi = min(resampled[-1].timestamp, ref[-1].timestamp)
    resampled = [c for c in resampled if lo <= c.timestamp <= hi]
    ref = [c for c in ref if lo <= c.timestamp <= hi]

    assert len(resampled) > 0
    assert len(resampled) == len(ref)
    for a, b in zip(resampled, ref):
        assert a.timestamp == b.timestamp
        assert float(a.open) == float(b.open)
        assert float(a.high) == float(b.high)
        assert float(a.low) == float(b.low)
        assert float(a.close) == float(b.close)
        va, vb = float(a.volume), float(b.volume)
        assert abs(va - vb) / max(abs(va), abs(vb), 1e-12) <= VOL_REL_TOL
