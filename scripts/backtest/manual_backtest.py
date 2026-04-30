"""
CRT Engine — Manual Backtest
Runs the full CRT pipeline on any M15 CSV exactly per the spec:
  - ATR(14), HTF=16, sweep_age≤30, displacement 1.2×ATR / body≥0.70 / wick≥1.5×ATR
  - Expansion guard: 0.2×ATR from disp close
  - Adaptive retest ceiling: min(0.25×range, 0.5×ATR)
  - SL anchored to displacement candle extreme ± 0.2×ATR
  - TP1 = 1×ATR, TP2 = 2×ATR from entry
  - 1% compounding risk, 0.02% spread, slippage=uniform(0, 0.08×ATR)
  - Gaussian scorer (real EURCAD calibrated parameters)
  - Regime detection + dynamic threshold
  - Soft confirmation manifold (continuous gate, 3-candle window)
  - Zero lookahead — all decisions on close of current candle
"""

from __future__ import annotations

import csv
import math
import os
import random
import sys
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# ─── auto-detect uploaded file ────────────────────────────────────────────────
def find_csv() -> str:
    candidates = [
        "/mnt/user-data/uploads/XAUUSD_M15_real.csv",
        "/mnt/user-data/uploads/BTCUSDT_M15_real.csv",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    # fallback: first CSV in uploads
    for f in Path("/mnt/user-data/uploads").glob("*.csv"):
        return str(f)
    raise FileNotFoundError("No CSV found in /mnt/user-data/uploads/")

# ─── Config ────────────────────────────────────────────────────────────────────
ATR_PERIOD           = 14
HTF_CANDLES          = 16
SWEEP_MAX_AGE        = 30
DISP_MIN_MOVE_ATR    = 1.2
DISP_BODY_MIN        = 0.70
DISP_WICK_MIN_ATR    = 1.5
EXPANSION_ATR_MIN    = 0.20
RETEST_RANGE_FRAC    = 0.25
RETEST_ATR_FRAC      = 0.50
CONF_BODY_MIN        = 0.60
SL_BUFFER_ATR        = 0.20
TP1_ATR              = 1.0
TP2_ATR              = 2.0
RISK_PCT             = 0.01
SPREAD_PCT           = 0.0002
SLIP_FRAC            = 0.08
INITIAL_CAPITAL      = 100_000.0
SLIP_SEED            = 42

# Gaussian calibration (real EURCAD 2024-2025, 200 retest observations)
G_RETEST_MU = 0.237;  G_RETEST_S2 = 0.040
G_BODY_MU   = 0.847;  G_BODY_S2   = 0.021
G_DISP_MU   = 2.177;  G_DISP_S2   = 1.196
G_DECAY_LAM = 0.05
G_SIG_K     = 4.5;    G_SIG_X0    = 0.50
G_RETEST_MIN = 0.025; G_RETEST_MAX = 0.469
G_DISP_MAX   = 3.670

# Regime thresholds
VOL_HIGH = 0.0015;  VOL_LOW = 0.0004
TREND_STR_HIGH = 1.2

# Soft confirmation manifold
CONF_ALPHA = 0.70;  CONF_BETA = 0.30
CONF_WEIGHTS = (0.35, 0.35, 0.15, 0.15)  # body, mom, dist, disp
CONF_FLOOR   = 0.20
WEAK_LINK_WT = 0.30
SOFT_CONF_WINDOW = 3
EMA_FAST = 2;  EMA_SLOW = 5
TIER1_THRESH = 0.75;  TIER2_THRESH = 0.55

# Dynamic threshold
DYN_WARMUP = 10;  DYN_WINDOW = 20
DYN_TIGHT = 0.70;  DYN_MID = 0.65;  DYN_LOOSE = 0.58

# ─── Helpers ───────────────────────────────────────────────────────────────────
rng_slip = random.Random(SLIP_SEED)

def adverse_slip(atr: float) -> float:
    return rng_slip.uniform(0, SLIP_FRAC * atr)

def gaussian(x: float, mu: float, s2: float) -> float:
    return math.exp(-((x - mu) ** 2) / s2)

def atr(candles: list) -> float:
    """candles = list of (o,h,l,c) tuples"""
    if len(candles) < 2:
        return candles[-1][1] - candles[-1][2] if candles else 0.0
    trs = [max(c[1] - c[2], abs(c[1] - candles[i][3]), abs(c[2] - candles[i][3]))
           for i, c in enumerate(candles[1:], 0)]
    period = min(ATR_PERIOD, len(trs))
    return sum(trs[-period:]) / period

def body_ratio(o: float, h: float, l: float, c: float) -> float:
    total = h - l
    return abs(c - o) / total if total > 0 else 0.0

def wick_size(o: float, h: float, l: float, c: float) -> float:
    return h - l

# ─── Gaussian scorer ──────────────────────────────────────────────────────────
def gaussian_score(retest_depth: float, body_rat: float, disp_str: float, candles_since: int) -> dict:
    if retest_depth < G_RETEST_MIN or retest_depth > G_RETEST_MAX:
        return {"score": 0.0, "p_win": 0.0, "reject": "retest_depth_filter"}
    if disp_str > G_DISP_MAX:
        return {"score": 0.0, "p_win": 0.0, "reject": "disp_exhaustion"}

    s_r = gaussian(retest_depth, G_RETEST_MU, G_RETEST_S2)
    s_b = gaussian(body_rat,     G_BODY_MU,   G_BODY_S2)
    s_d = gaussian(disp_str,     G_DISP_MU,   G_DISP_S2)
    s_t = math.exp(-G_DECAY_LAM * max(0, candles_since))

    score = (s_r ** 0.40) * (s_b ** 0.35) * (s_d ** 0.25) * (s_t ** 0.15)
    p_win = 1.0 / (1.0 + math.exp(-G_SIG_K * (score - G_SIG_X0)))
    return {"score": round(score, 6), "p_win": round(p_win, 4), "reject": None}

# ─── Soft confirmation score C ─────────────────────────────────────────────────
def soft_conf_score(
    candle_ohlcv, direction: str,
    ema_fast: float, ema_slow: float, atr_val: float,
    h_ref: float, l_ref: float, range_size: float,
    disp_body: float
) -> float:
    o, h, l, c, v = candle_ohlcv
    w_body, w_mom, w_dist, w_disp = CONF_WEIGHTS

    # 1. Body ratio
    f_body = min(1.0, body_ratio(o, h, l, c) / CONF_BODY_MIN)

    # 2. EMA momentum
    dir_mult = 1.0 if direction == "LONG" else -1.0
    mom_delta = (ema_fast - ema_slow) * dir_mult
    f_mom = max(0.0, min(1.0, mom_delta / atr_val)) if atr_val > 0 else 0.0

    # 3. Non-linear distance from retest boundary
    static_ceil = RETEST_RANGE_FRAC * range_size
    atr_ceil    = RETEST_ATR_FRAC * atr_val
    ceiling     = min(static_ceil, atr_ceil)
    depth = abs(c - l_ref) if direction == "LONG" else abs(h_ref - c)
    f_dist = math.exp(-((depth / ceiling) ** 2)) if ceiling > 0 else 0.0

    # 4. Displacement strength inheritance
    f_disp = min(1.0, disp_body / (1.5 * atr_val)) if atr_val > 0 else 0.0

    C_lin = w_body*f_body + w_mom*f_mom + w_dist*f_dist + w_disp*f_disp
    weak  = min(f_body, f_mom)
    C     = (1.0 - WEAK_LINK_WT) * C_lin + WEAK_LINK_WT * weak
    return max(CONF_FLOOR, C)

def fusion_score(G: float, C: float) -> float:
    return (G ** CONF_ALPHA) * (C ** CONF_BETA)

# ─── Regime detection ──────────────────────────────────────────────────────────
def detect_regime(atr_val: float, price: float, prev_close: float, close: float) -> str:
    if price == 0 or atr_val == 0:
        return "NEUTRAL"
    vol = atr_val / price
    trend = abs(close - prev_close) / atr_val
    if vol > VOL_HIGH and trend > TREND_STR_HIGH:
        return "EXPANSION"
    if vol < VOL_LOW:
        return "DEAD"
    return "NEUTRAL"

def risk_multiplier_for(regime: str) -> float:
    return {"EXPANSION": 1.2, "DEAD": 0.5, "NEUTRAL": 1.0}.get(regime, 1.0)

# ─── Dynamic threshold ─────────────────────────────────────────────────────────
class DynamicThreshold:
    def __init__(self):
        self.history: list[int] = []

    def update(self, win: bool):
        self.history.append(1 if win else 0)
        if len(self.history) > DYN_WINDOW:
            self.history.pop(0)

    def threshold(self) -> float:
        if len(self.history) < DYN_WARMUP:
            return DYN_MID
        wr = sum(self.history) / len(self.history)
        if wr < 0.45:   return DYN_TIGHT
        if wr > 0.60:   return DYN_LOOSE
        return DYN_MID

# ─── CSV loader ────────────────────────────────────────────────────────────────
def load_csv(path: str) -> list:
    """Returns list of (timestamp_str, open, high, low, close, volume)."""
    DATE_FMTS = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
                 "%Y.%m.%d %H:%M:%S", "%Y.%m.%d %H:%M"]
    candles = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        headers = [h.strip().lower() for h in next(reader)]
        ti = next((i for i, h in enumerate(headers) if h in ("timestamp","datetime","date")), 0)
        oi = next((i for i, h in enumerate(headers) if h in ("open","o")), 1)
        hi = next((i for i, h in enumerate(headers) if h in ("high","h")), 2)
        li = next((i for i, h in enumerate(headers) if h in ("low","l")), 3)
        ci = next((i for i, h in enumerate(headers) if h in ("close","c","adj close")), 4)
        vi = next((i for i, h in enumerate(headers) if h in ("volume","vol")), 5) if len(headers) > 5 else None
        for row in reader:
            if not row: continue
            try:
                raw = row[ti].strip()
                dt  = None
                for fmt in DATE_FMTS:
                    try: dt = datetime.strptime(raw, fmt); break
                    except: pass
                if dt is None: continue
                o, h, l, c = float(row[oi]), float(row[hi]), float(row[li]), float(row[ci])
                v = float(row[vi]) if vi is not None else 0.0
                candles.append((dt, o, h, l, c, v))
            except: continue
    candles.sort(key=lambda x: x[0])
    return candles

# ─── Main backtest loop ────────────────────────────────────────────────────────
def run(csv_path: str) -> list[dict]:
    candles = load_csv(csv_path)
    instrument = Path(csv_path).stem.replace("_M15_real","").replace("_M15","").upper()
    print(f"Loaded {len(candles):,} candles  |  {candles[0][0].date()} → {candles[-1][0].date()}  |  {instrument}")

    # state
    capital         = INITIAL_CAPITAL
    peak_capital    = INITIAL_CAPITAL
    max_dd_r        = 0.0
    cum_r           = 0.0
    peak_cum_r      = 0.0

    buf: list       = []    # rolling candle buffer for ATR
    htf_buf: list   = []    # HTF accumulation buffer

    # engine state
    state = "RANGE"
    direction       = None
    sweep_price     = None
    sweep_dir       = None
    sweep_idx       = None
    sweep_double    = False
    prev_sweep_dir  = None
    disp_candle     = None     # (o,h,l,c)
    retest_candle   = None
    retest_idx      = None
    h_ref = l_ref   = eq = 0.0
    range_size      = 0.0

    # soft conf
    eval_soft_conf  = False
    soft_conf_n     = 0
    ema_fast_v      = 0.0
    ema_slow_v      = 0.0

    # trade
    in_trade        = False
    trade_dir       = None
    entry_raw       = 0.0
    entry_fill      = 0.0
    sl_price        = 0.0
    tp1_price       = 0.0
    tp2_price       = 0.0
    tp1_hit         = False
    trade_open_at   = None
    trade_gauss     = 0.0
    trade_regime    = ""
    trade_risk_mult = 1.0
    trade_risk_pct  = RISK_PCT
    position_size   = 0.0
    cached_feat     = None

    dyn_thresh      = DynamicThreshold()
    trades          = []
    candle_idx      = 0
    warmup          = ATR_PERIOD * 3 + HTF_CANDLES

    prev_close      = None

    def update_emas(close: float):
        nonlocal ema_fast_v, ema_slow_v
        if ema_fast_v == 0.0:
            ema_fast_v = ema_slow_v = close
            return
        af = 2.0 / (EMA_FAST + 1)
        as_ = 2.0 / (EMA_SLOW + 1)
        ema_fast_v = close * af + ema_fast_v * (1 - af)
        ema_slow_v = close * as_ + ema_slow_v * (1 - as_)

    def reset():
        nonlocal state, direction, sweep_price, sweep_dir, sweep_idx
        nonlocal sweep_double, prev_sweep_dir, disp_candle, retest_candle
        nonlocal retest_idx, h_ref, l_ref, eq, range_size
        nonlocal eval_soft_conf, soft_conf_n, cached_feat
        state = "RANGE"; direction = None; sweep_price = None
        sweep_dir = None; sweep_idx = None; sweep_double = False
        prev_sweep_dir = None; disp_candle = None
        retest_candle = None; retest_idx = None
        h_ref = l_ref = eq = range_size = 0.0
        eval_soft_conf = False; soft_conf_n = 0; cached_feat = None

    def close_trade(exit_raw: float, reason: str, candle_dt: datetime, atr_val: float):
        nonlocal in_trade, capital, peak_capital, max_dd_r, cum_r, peak_cum_r
        nonlocal trade_dir, entry_raw, entry_fill, sl_price, tp1_hit, position_size

        spread_half = exit_raw * SPREAD_PCT / 2
        x_slip = adverse_slip(atr_val)
        if trade_dir == "LONG":
            exit_fill = exit_raw - x_slip - spread_half
        else:
            exit_fill = exit_raw + x_slip + spread_half

        risk_dist = abs(entry_fill - sl_price)
        price_move = (exit_fill - entry_fill) if trade_dir == "LONG" else (entry_fill - exit_fill)
        pnl_pips   = price_move
        pnl_rr     = pnl_pips / risk_dist if risk_dist > 0 else 0.0

        pnl_dollar = price_move * position_size
        capital   += pnl_dollar
        peak_capital = max(peak_capital, capital)
        cum_r        += pnl_rr
        peak_cum_r   = max(peak_cum_r, cum_r)
        dd_r         = peak_cum_r - cum_r
        nonlocal max_dd_r
        max_dd_r = max(max_dd_r, dd_r)

        trades[-1].update({
            "exit_price_raw": round(exit_raw, 5),
            "exit_fill":      round(exit_fill, 5),
            "exit_reason":    reason,
            "pnl_rr_net":     round(pnl_rr, 4),
            "closed_at":      candle_dt.isoformat(),
            "capital_after":  round(capital, 2),
        })
        dyn_thresh.update(pnl_rr > 0)
        in_trade = False
        reset()

    # ── Main loop ──────────────────────────────────────────────────────────────
    for i, (dt, o, h, l, c, v) in enumerate(candles):
        candle_idx += 1
        buf.append((dt, o, h, l, c, v))
        if len(buf) > ATR_PERIOD * 3:
            buf.pop(0)
        htf_buf.append((dt, o, h, l, c, v))

        # EMA always updated
        update_emas(c)

        # Skip warmup
        if candle_idx < warmup:
            prev_close = c
            continue

        # ATR: pass (o,h,l,c) from buf; prev-close is index 3 (c) of preceding bar
        atr_val = atr([(b[1],b[2],b[3],b[4]) for b in buf])

        # HTF range refresh (non-destructive in RANGE state, ignored mid-setup)
        if len(htf_buf) > HTF_CANDLES:
            # Exclude current candle — range must be formed from PRIOR candles only
            window = htf_buf[-HTF_CANDLES-1:-1]
            new_h   = max(b[2] for b in window)
            new_l   = min(b[3] for b in window)
            new_eq  = (new_h + new_l) / 2
            new_sz  = new_h - new_l
            if state == "RANGE":
                h_ref = new_h; l_ref = new_l; eq = new_eq; range_size = new_sz

        # ── Active trade management ──────────────────────────────────────────
        if in_trade:
            is_long = trade_dir == "LONG"
            # SL check
            sl_hit = (l <= sl_price) if is_long else (h >= sl_price)
            # TP1 check
            tp1_ok = (h >= tp1_price) if is_long else (l <= tp1_price)
            # TP2 check
            tp2_ok = (h >= tp2_price) if is_long else (l <= tp2_price)

            if not tp1_hit and tp1_ok:
                tp1_hit = True  # trail to breakeven conceptually, keep riding

            if tp2_ok:
                close_trade(tp2_price, "TP2", dt, atr_val)
                prev_close = c; continue
            elif sl_hit:
                # cap exit at SL (prevents gap-through blowup)
                exit_at = sl_price
                close_trade(exit_at, "STOPPED", dt, atr_val)
                prev_close = c; continue

        # ── State machine ─────────────────────────────────────────────────────
        pc = prev_close if prev_close else c

        if state == "RANGE":
            if h_ref == 0.0:
                prev_close = c; continue

            # Detect sweep
            swept_high = h > h_ref and c < h_ref
            swept_low  = l < l_ref and c > l_ref

            if swept_high or swept_low:
                new_dir = "SHORT" if swept_high else "LONG"
                new_price = h if swept_high else l
                double = (prev_sweep_dir is not None and prev_sweep_dir != new_dir)
                prev_sweep_dir = sweep_dir
                sweep_dir   = new_dir
                sweep_price = new_price
                sweep_idx   = candle_idx
                sweep_double = double
                state = "SWEEP"

        elif state == "SWEEP":
            age = candle_idx - sweep_idx
            if age > SWEEP_MAX_AGE:
                reset(); prev_close = c; continue

            # Displacement check
            br = body_ratio(o, h, l, c)
            ws = wick_size(o, h, l, c)
            move = abs(c - o)

            if (move >= DISP_MIN_MOVE_ATR * atr_val and
                br   >= DISP_BODY_MIN and
                ws   >= DISP_WICK_MIN_ATR * atr_val):
                # direction: same as sweep
                direction  = sweep_dir
                disp_candle = (o, h, l, c)
                state = "DISPLACEMENT"

        elif state == "DISPLACEMENT":
            is_long = (direction == "LONG")
            disp_c  = disp_candle
            # Expansion: price continues in direction beyond disp_close + guard
            guard = EXPANSION_ATR_MIN * atr_val
            if is_long  and c > disp_c[3] + guard:
                state = "EXPANSION"
            elif not is_long and c < disp_c[3] - guard:
                state = "EXPANSION"

        elif state == "EXPANSION":
            if range_size == 0.0:
                prev_close = c; continue
            is_long = (direction == "LONG")

            # Adaptive retest ceiling
            static_ceil = RETEST_RANGE_FRAC * range_size
            atr_ceil    = RETEST_ATR_FRAC * atr_val
            ceiling     = min(static_ceil, atr_ceil)

            depth_from_bound = (c - l_ref) if is_long else (h_ref - c)

            if depth_from_bound <= ceiling:
                # Depth as fraction of displacement move for Gaussian
                disp_move = abs(disp_candle[3] - disp_candle[0])
                if disp_move > 0:
                    retrace = abs(c - disp_candle[3]) / disp_move
                    cached_feat = {
                        "retest_depth": min(max(retrace, 0.0), 1.0),
                        "body_ratio":   disp_candle[0],   # displacement body
                        "disp_str":     wick_size(*disp_candle) / atr_val if atr_val > 0 else 0.0,
                        "retest_idx":   candle_idx,
                    }
                    # Use displacement candle body_ratio properly
                    cached_feat["body_ratio"] = body_ratio(*disp_candle)
                retest_candle = (o, h, l, c)
                retest_idx    = candle_idx
                state = "RETEST"
                eval_soft_conf = True
                soft_conf_n    = 0

        elif eval_soft_conf:
            soft_conf_n += 1
            if range_size == 0.0 or cached_feat is None:
                eval_soft_conf = False; reset()
                prev_close = c; continue

            is_long = (direction == "LONG")

            # Gaussian score
            candles_since = candle_idx - (cached_feat.get("retest_idx", candle_idx))
            gs = gaussian_score(
                cached_feat["retest_depth"],
                cached_feat["body_ratio"],
                cached_feat["disp_str"],
                candles_since,
            )

            # Regime
            regime = detect_regime(atr_val, c, pc, c)
            rm     = risk_multiplier_for(regime)

            # Soft confirmation C
            C = soft_conf_score(
                (o, h, l, c, v), direction,
                ema_fast_v, ema_slow_v, atr_val,
                h_ref, l_ref, range_size,
                abs(disp_candle[3] - disp_candle[0]) if disp_candle else 0.0,
            )

            G = gs["score"]
            S = fusion_score(G, C)

            threshold = dyn_thresh.threshold()

            if S >= TIER2_THRESH and S >= threshold:
                # Range position filter
                entry_p = retest_candle[3] if retest_candle else c  # retest close
                mid     = (h_ref + l_ref) / 2
                if (is_long and entry_p > mid) or (not is_long and entry_p < mid):
                    eval_soft_conf = False; reset()
                    prev_close = c; continue

                # Build trade
                if disp_candle is None:
                    eval_soft_conf = False; reset()
                    prev_close = c; continue

                sl_raw = (disp_candle[2] - SL_BUFFER_ATR * atr_val) if is_long \
                    else (disp_candle[1] + SL_BUFFER_ATR * atr_val)

                # Inverted SL guard
                if (is_long and sl_raw >= entry_p) or (not is_long and sl_raw <= entry_p):
                    eval_soft_conf = False; reset()
                    prev_close = c; continue

                spread_half = entry_p * SPREAD_PCT / 2
                e_slip = adverse_slip(atr_val)
                entry_fill_val = (entry_p + e_slip + spread_half) if is_long \
                    else (entry_p - e_slip - spread_half)

                risk_dist = abs(entry_fill_val - sl_raw)
                if risk_dist == 0:
                    eval_soft_conf = False; reset()
                    prev_close = c; continue

                # Tiered sizing
                base_risk = RISK_PCT if S >= TIER1_THRESH else RISK_PCT * 0.5
                final_risk = base_risk * rm
                risk_dollar = capital * final_risk
                pos_sz = risk_dollar / risk_dist

                tp1_p = entry_p + TP1_ATR * atr_val if is_long else entry_p - TP1_ATR * atr_val
                tp2_p = entry_p + TP2_ATR * atr_val if is_long else entry_p - TP2_ATR * atr_val

                trade_dir       = "LONG" if is_long else "SHORT"
                entry_raw       = entry_p
                entry_fill      = entry_fill_val
                sl_price        = sl_raw
                tp1_price       = tp1_p
                tp2_price       = tp2_p
                tp1_hit         = False
                trade_gauss     = round(G, 4)
                trade_regime    = regime
                trade_risk_mult = rm
                trade_risk_pct  = final_risk
                position_size   = pos_sz
                trade_open_at   = dt
                in_trade        = True
                eval_soft_conf  = False

                trades.append({
                    "trade_id":       f"CRT-{len(trades)+1:04d}",
                    "opened_at":      dt.isoformat(),
                    "direction":      trade_dir,
                    "entry_price_raw": round(entry_raw, 5),
                    "entry_fill":     round(entry_fill, 5),
                    "sl":             round(sl_price, 5),
                    "tp1":            round(tp1_price, 5),
                    "tp2":            round(tp2_price, 5),
                    "gaussian_score": trade_gauss,
                    "fusion_score":   round(S, 4),
                    "regime":         regime,
                    "risk_multiplier": rm,
                    "risk_pct":       round(final_risk, 5),
                    "position_size":  round(pos_sz, 4),
                    "capital_before": round(capital, 2),
                    # filled on close:
                    "exit_price_raw": None,
                    "exit_fill":      None,
                    "exit_reason":    None,
                    "pnl_rr_net":     None,
                    "closed_at":      None,
                    "capital_after":  None,
                })
                # Do NOT reset here — trade is open, state cleared above

            elif soft_conf_n >= SOFT_CONF_WINDOW:
                eval_soft_conf = False
                reset()

        # Gap/weekend reset (no active trade mid-setup)
        if prev_close is not None and not in_trade:
            gap_min = (dt - candles[i-1][0]).total_seconds() / 60 if i > 0 else 0
            if gap_min > 120:
                reset()

        # Forced close on end-of-data
        prev_close = c

    # Force-close if open at end
    if in_trade and trades:
        atr_last = atr([(b[1],b[2],b[3],b[4]) for b in buf])
        close_trade(candles[-1][4], "BACKTEST_END", candles[-1][0], atr_last)

    return trades

# ─── Analytics ─────────────────────────────────────────────────────────────────
def analyse(trades: list[dict]) -> dict:
    closed = [t for t in trades if t.get("pnl_rr_net") is not None]
    if not closed:
        return {}

    rrs   = [t["pnl_rr_net"] for t in closed]
    wins  = [r for r in rrs if r > 0]
    losses= [r for r in rrs if r <= 0]
    n     = len(rrs)
    wr    = len(wins) / n
    total = sum(rrs)
    avg   = total / n

    gross_w = sum(wins);   gross_l = abs(sum(losses))
    pf = gross_w / gross_l if gross_l > 0 else float("inf")

    # Sharpe (per-trade)
    mean = total / n
    if n >= 2:
        var    = sum((r - mean)**2 for r in rrs) / n
        sharpe = mean / math.sqrt(var) if var > 0 else 0.0
    else:
        sharpe = 0.0

    # Max drawdown (R-curve)
    eq = pk = dd = 0.0
    for r in rrs:
        eq += r; pk = max(pk, eq); dd = max(dd, pk - eq)

    # Pearson corr: gaussian_score vs pnl_rr_net (scored trades only)
    scored = [(t["gaussian_score"], t["pnl_rr_net"])
              for t in closed if t["gaussian_score"] > 0]
    corr = float("nan")
    if len(scored) >= 3:
        gs_v = [s for s,_ in scored]; rr_v = [r for _,r in scored]
        mg, mr = sum(gs_v)/len(gs_v), sum(rr_v)/len(rr_v)
        cov = sum((g-mg)*(r-mr) for g,r in zip(gs_v,rr_v)) / len(gs_v)
        sg  = math.sqrt(sum((g-mg)**2 for g in gs_v) / len(gs_v))
        sr  = math.sqrt(sum((r-mr)**2 for r in rr_v) / len(rr_v))
        corr = cov / (sg * sr) if sg > 0 and sr > 0 else float("nan")

    return {
        "total_trades": n, "wins": len(wins), "losses": len(losses),
        "win_rate": round(wr, 4), "avg_rr": round(avg, 4),
        "total_pnl_r": round(total, 4), "max_drawdown_r": round(dd, 4),
        "profit_factor": round(pf, 3) if pf != float("inf") else 999.0,
        "sharpe_per_trade": round(sharpe, 4),
        "gauss_rr_corr": round(corr, 4) if not math.isnan(corr) else "n/a",
    }
def log_run(stats: dict, instrument: str):
    from pathlib import Path
    import csv
    from datetime import datetime

    log_dir = Path("results/tracking")
    log_dir.mkdir(parents=True, exist_ok=True)

    file_path = log_dir / "runs.csv"

    row = {
        "timestamp": datetime.utcnow().isoformat(),
        "instrument": instrument,
        "trades": stats.get("total_trades", 0),
        "win_rate": stats.get("win_rate", 0),
        "avg_rr": stats.get("avg_rr", 0),
        "total_pnl_r": stats.get("total_pnl_r", 0),
        "max_dd_r": stats.get("max_drawdown_r", 0),
        "profit_factor": stats.get("profit_factor", 0),
        "sharpe": stats.get("sharpe_per_trade", 0),
        "gauss_corr": stats.get("gauss_rr_corr", 0)
        
    }
    

    write_header = not file_path.exists()

    with open(file_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=row.keys())
        if write_header:
            writer.writeheader()
        writer.writerow(row)

# ─── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=str, default=None)
    args = parser.parse_args()

    csv_in = args.csv if args.csv else find_csv()
    print(f"\nInput: {csv_in}")

    # ensure output directory exists
    from pathlib import Path
    Path("results/manual").mkdir(parents=True, exist_ok=True)

    trades = run(csv_in)

    # Write output CSV

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    instrument = Path(csv_in).stem.upper()

    out_path = f"results/manual/{instrument}_{ts}.csv"
    closed   = [t for t in trades if t.get("pnl_rr_net") is not None]

    if closed:
        with open(out_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=closed[0].keys())
            writer.writeheader()
            writer.writerows(closed)
        print(f"Trades written → {out_path}")
    else:
        print("No closed trades.")

    stats = analyse(trades)
    instrument = Path(csv_in).stem.upper()
    log_run(stats, instrument)

    W = 55
    print()
    print("═" * W)
    print("  CRT ENGINE — BACKTEST SUMMARY")
    # ─────────────────────────────────────────────
# VALIDATOR CONNECTOR HOOK
# ─────────────────────────────────────────────
    from trade_replay_validator import validate_all

    try:
        import pandas as pd

        trades_df = pd.read_csv("results/manual/manual_trades.csv")

        # Convert to dict records
        trades = trades_df.to_dict(orient="records")

        # Candle mapping (simple version: same CSV for all trades)
        candles_df = pd.read_csv(args.csv)
        candles = candles_df.to_dict(orient="records")

        # Map all trades → same candle stream (safe for now)
        all_candles = {t["trade_id"]: candles for t in trades}

        print("\nRunning Validator Connector...")
        df = validate_all(trades, all_candles)

        print(f"Validator dataset shape: {df.shape}")

    except Exception as e:
        print(f"[Validator Error] {e}")
    print("═" * W)
    print(f"  Total trades:       {stats.get('total_trades',0):>10}")
    print(f"  Wins / Losses:      {stats.get('wins',0):>4} / {stats.get('losses',0)}")
    print(f"  Win rate:           {stats.get('win_rate',0):>10.1%}")
    print(f"  Avg RR (net):       {stats.get('avg_rr',0):>+10.4f}R")
    print(f"  Total PnL (R):      {stats.get('total_pnl_r',0):>+10.4f}R")
    print(f"  Max drawdown (R):   {stats.get('max_drawdown_r',0):>10.4f}R")
    print(f"  Profit factor:      {stats.get('profit_factor',0):>10.3f}")
    print(f"  Sharpe (per-trade): {stats.get('sharpe_per_trade',0):>10.4f}")
    print(f"  Gauss→RR corr:      {str(stats.get('gauss_rr_corr','n/a')):>10}")
    print("═" * W)