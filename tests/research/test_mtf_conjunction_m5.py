"""Program 9 — MultiTFConjunctionBuilder with an M5 base (`base_label` + minute rules).

Pins: (a) the DEFAULT builder still emits Program-4 keys byte-identically ("M15=..." base
label, H1/H4 parts); (b) an M5-base builder emits "M5=...|M15=...|H1=...|H4=..." keys;
(c) no-lookahead across the M15 boundary — appending M5 bars inside the in-progress M15
bucket must not change the M15 token; (d) `key_series` == per-bar `build` for the M5 base.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from config_layer.crt_engine_v2 import Candle                            # noqa: E402
from research.candle_state.encoder import CandleStateEncoder             # noqa: E402
from research.candle_state.mtf_conjunction import MultiTFConjunctionBuilder  # noqa: E402


def _series(start: datetime, n: int, *, step_min: int, base=100.0) -> list[Candle]:
    out = []
    prev = base
    for i in range(n):
        o = prev
        cl = o + (0.4 if i % 3 else -0.3)
        hi = max(o, cl) + 0.2 + 0.001 * i
        lo = min(o, cl) - 0.2 - 0.001 * i
        out.append(Candle(timestamp=start + timedelta(minutes=step_min * i),
                          open=o, high=hi, low=lo, close=cl, volume=1.0 + 0.5 * i, index=i))
        prev = cl
    return out


# ── default (Program-4) parity ────────────────────────────────────────────────────────
def test_default_builder_emits_m15_base_keys():
    m15 = _series(datetime(2026, 1, 1), 300, step_min=15)
    b = MultiTFConjunctionBuilder(CandleStateEncoder())
    conj = b.build(m15)
    parts = conj.key.split("|")
    assert parts[0].startswith("M15=")
    assert parts[1].startswith("H1=") and parts[2].startswith("H4=")
    # base_label default reproduces the hand-assembled Program-4 key exactly
    enc = CandleStateEncoder()
    assert parts[0] == f"M15={enc.encode(m15).token()}"


def test_default_key_series_equals_build_regression():
    m15 = _series(datetime(2026, 1, 1), 120, step_min=15)
    b = MultiTFConjunctionBuilder(CandleStateEncoder())
    keys = b.key_series(m15)
    for t in (0, 50, 119):
        assert keys[t] == b.build(m15[:t + 1]).key


# ── M5 base ──────────────────────────────────────────────────────────────────────────
def _m5_builder() -> MultiTFConjunctionBuilder:
    return MultiTFConjunctionBuilder(
        CandleStateEncoder(), rules=("M15", "H1", "H4"), base_label="M5")


def test_m5_base_key_format():
    m5 = _series(datetime(2026, 1, 1), 600, step_min=5)
    conj = _m5_builder().build(m5)
    parts = conj.key.split("|")
    assert [p.split("=")[0] for p in parts] == ["M5", "M15", "H1", "H4"]
    assert all(p.split("=", 1)[1] for p in parts)          # every token non-empty


def test_m5_base_no_lookahead_within_m15_bucket():
    """Appending M5 bars INSIDE the in-progress M15 bucket must not change the M15 token
    (the last CLOSED M15 bucket is the same until a new bucket opens)."""
    b = _m5_builder()
    m5 = _series(datetime(2026, 1, 1), 600, step_min=5)    # ends at a :45+10 boundary? -> compute
    # Find a prefix ending mid-M15-bucket: bar at minute % 15 == 5 (2nd bar of its bucket).
    t = next(i for i in range(500, 600) if m5[i].timestamp.minute % 15 == 5)
    key_mid = b.build(m5[:t + 1]).key
    key_next = b.build(m5[:t + 2]).key                     # still inside the same bucket
    m15_tok = lambda k: k.split("|")[1]                    # noqa: E731
    assert m15_tok(key_mid) == m15_tok(key_next)


def test_m5_key_series_equals_build():
    m5 = _series(datetime(2026, 1, 1), 400, step_min=5)
    b = _m5_builder()
    keys = b.key_series(m5)
    assert len(keys) == 400
    for t in (0, 37, 200, 399):
        assert keys[t] == b.build(m5[:t + 1]).key


def test_m5_key_series_deterministic():
    m5 = _series(datetime(2026, 1, 1), 300, step_min=5)
    b = _m5_builder()
    assert b.key_series(m5) == b.key_series(m5)
