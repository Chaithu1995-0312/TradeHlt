"""SMC zone PRICES per M15 bar (observation only; tools/xau_chart).

The pipeline emits only tanh(distance / ATR) for OB / FVG / breaker / mitigation. This walks the
SAME trailing Candle window the pipeline builds (same k = swing_window, same smc_max_window, same
features.smc functions) and records the active zone's [low, high] in dollars instead.

Rejection block is NOT in the repo. Definition used here (standard ICT reading, declared, not
registered): at a confirmed causal swing high (k bars each side) the bearish rejection block is
the upper wick [max(open, close), high]; at a confirmed swing low the bullish block is the lower
wick [low, min(open, close)]. It goes live at confirmation (bar j+k) and stays active until a
later bar trades into the wick (retest) or closes beyond the extreme (invalidated). The most recent
live block on each side is reported.
"""
from __future__ import annotations

import math

import pandas as pd

from config_layer.crt_engine_v2 import Candle
from config_layer.production_config import get_prod_section
from features.feature_pipeline import resolve_swing_window
from features.smc._geometry import signed_atr_distance
from features.smc.breaker import find_active_breaker
from features.smc.fvg import find_active_fvg
from features.smc.mitigation import find_active_mitigation_block
from features.smc.order_block import _find_break_events, find_active_order_block

KINDS = ("ob", "fvg", "brk", "mit")


def _rejection_blocks(window: list, k: int) -> tuple:
    """(bearish RB above, bullish RB below) as (low, high, formed_index) or None each."""
    n = len(window)
    bear = bull = None
    for j in range(n - 1 - k, k - 1, -1):
        seg = window[j - k:j + k + 1]
        c = window[j]
        later = window[j + k + 1:]
        if bear is None and c.high == max(b.high for b in seg):
            lo = max(c.open, c.close)
            if c.high > lo and not any(b.close > c.high or b.high >= lo for b in later):
                bear = (lo, c.high, c.index)
        if bull is None and c.low == min(b.low for b in seg):
            hi = min(c.open, c.close)
            if hi > c.low and not any(b.close < c.low or b.low <= hi for b in later):
                bull = (c.low, hi, c.index)
        if bear is not None and bull is not None:
            break
    return bear, bull


def zone_prices(raw: pd.DataFrame) -> list[dict]:
    """One dict per raw row: {kind: (low, high, bullish, formed_index) or None, 'rb_bear', 'rb_bull'}."""
    cfg = get_prod_section("feature_pipeline")
    k = resolve_swing_window(cfg)
    max_window = int(cfg["smc_max_window"])
    out, window = [], []
    for i, r in enumerate(raw.itertuples(index=False)):
        window.append(Candle(timestamp=pd.Timestamp(r.timestamp).to_pydatetime(), open=float(r.open),
                             high=float(r.high), low=float(r.low), close=float(r.close), volume=0.0, index=i))
        if len(window) > max_window:
            window = window[-max_window:]
        ev = _find_break_events(window, k)
        zs = {"ob": find_active_order_block(window, k, ev), "fvg": find_active_fvg(window),
              "brk": find_active_breaker(window, k, ev), "mit": find_active_mitigation_block(window, k, ev)}
        rec = {kk: (None if z is None else (z.low, z.high, z.bullish, z.formed_at_index)) for kk, z in zs.items()}
        rec["rb_bear"], rec["rb_bull"] = _rejection_blocks(window, k)
        out.append(rec)
    return out, k, max_window


def parity(rec: dict, close: float, atr_abs: float) -> dict:
    """Rebuild the pipeline's distance value from the recorded zone (near edge = top of a
    bullish zone, bottom of a bearish one) so the prices can be checked against the feature."""
    res = {}
    for kk in KINDS:
        z = rec[kk]
        if z is None or not (atr_abs > 0) or math.isnan(atr_abs):
            res[kk] = 0.0
        elif z[2]:
            res[kk] = signed_atr_distance(close, z[1], atr_abs, favorable_sign=1)
        else:
            res[kk] = signed_atr_distance(close, z[0], atr_abs, favorable_sign=-1)
    return res
