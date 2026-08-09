#!/usr/bin/env python
"""
20-Day Purge + Delayed-Entry Detection (standalone, read-only).

Mechanically identifies a liquidity-sweep setup on an OHLCV file:

    1. Compute the prior 20-DAY high (HH20) and low (LL20) from completed daily bars.
    2. Mark a HIGHER purge when an intraday bar's high pierces HH20 (SELL / mean-reversion),
       or a LOWER purge when its low pierces LL20 (BUY).
    3. Emit the entry signal a fixed delay later (default 2 hours).

This is DETECTION ONLY -- no backtest, PnL, cost model, or statistical test. Whether the
rule predicts anything is a separate question and is out of scope here.

Correctness note: the data on disk is intraday (M15 / H1), so a naive rolling(20) over rows
is a 5-hour window, NOT 20 days. We resample to daily for the level, then `.shift(1)` so the
level a bar is tested against uses only PRIOR completed days (no lookahead).

Usage:
    python scripts/analysis/purge_delay_scan.py --file data/EURUSD_M15.csv
    python scripts/analysis/purge_delay_scan.py --file data/BNBUSDT_M15_2year.xlsx --delay-hours 2
    python scripts/analysis/purge_delay_scan.py --file data/binance/BTCUSDT_H1.csv --min-penetration-atr 0.25
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

CANONICAL = ["open", "high", "low", "close", "volume"]
_TS_ALIASES = ("timestamp", "datetime", "date time", "open time", "date")


def _load_ohlcv(path: Path) -> pd.DataFrame:
    """Load a CSV/XLSX OHLCV file into a time-indexed, sorted DataFrame."""
    if path.suffix.lower() in (".xlsx", ".xlsm", ".xls"):
        df = pd.read_excel(path)
    else:
        df = pd.read_csv(path)

    df.columns = [str(c).strip().lower() for c in df.columns]

    ts_col = next((c for c in _TS_ALIASES if c in df.columns), None)
    if ts_col is None:
        raise SystemExit(
            f"No timestamp column found in {path.name}. "
            f"Looked for {_TS_ALIASES}; got {list(df.columns)}"
        )

    # Column aliases -> canonical names.
    rename = {"o": "open", "h": "high", "l": "low", "c": "close",
              "vol": "volume", "tickvol": "volume", "tick volume": "volume"}
    df = df.rename(columns=rename)

    missing = [c for c in ("open", "high", "low", "close") if c not in df.columns]
    if missing:
        raise SystemExit(f"Missing OHLC columns {missing} in {path.name}; got {list(df.columns)}")
    if "volume" not in df.columns:
        df["volume"] = 0.0

    df[ts_col] = pd.to_datetime(df[ts_col])
    df = df.set_index(ts_col).sort_index()
    df = df[CANONICAL].astype(float)
    if df.index.has_duplicates:
        df = df[~df.index.duplicated(keep="first")]
    return df


def _infer_bar_minutes(index: pd.DatetimeIndex) -> float:
    """Median spacing between consecutive bars, in minutes."""
    deltas = index.to_series().diff().dropna()
    if deltas.empty:
        raise SystemExit("Need at least 2 rows to infer the bar interval.")
    return float(deltas.median().total_seconds() / 60.0)


def _true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [df["high"] - df["low"],
         (df["high"] - prev_close).abs(),
         (df["low"] - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr


def scan(
    df: pd.DataFrame,
    *,
    lookback_days: int,
    delay_bars: int,
    min_penetration_atr: float,
    atr_window: int,
    mode: str = "reversion",
    atr_pctile_window: int = 2000,
) -> pd.DataFrame:
    """Annotate the intraday frame with 20-day levels, purge flags, and delayed entries."""
    # --- Prior N-day high/low from COMPLETED daily bars (no lookahead via shift(1)) ---
    daily = df.resample("1D").agg(High=("high", "max"), Low=("low", "min")).dropna(how="all")
    daily["HH20"] = daily["High"].rolling(lookback_days).max().shift(1)
    daily["LL20"] = daily["Low"].rolling(lookback_days).min().shift(1)

    # Second-lowest low over the same prior-20d window (for second-low purge detection).
    # Using np.partition(..., 1)[1] = second smallest = O(n) instead of O(n log n) sort.
    daily["LL20_2nd"] = daily["Low"].rolling(lookback_days).apply(
        lambda x: np.partition(x.dropna().to_numpy(), 1)[1] if len(x.dropna()) >= 2 else np.nan
    ).shift(1)

    # Broadcast each day's prior-20d level onto that day's intraday bars.
    day_key = df.index.normalize()
    df["HH20"] = daily["HH20"].reindex(day_key).to_numpy()
    df["LL20"] = daily["LL20"].reindex(day_key).to_numpy()
    df["LL20_2nd"] = daily["LL20_2nd"].reindex(day_key).to_numpy()

    # --- ATR (computed unconditionally: powers the guard AND the R-normalization/slicing) ---
    atr = _true_range(df).rolling(atr_window).mean()
    df["atr"] = atr
    # Trailing volatility-regime rank (causal: right-most value's rank in its trailing window).
    df["atr_pctile"] = atr.rolling(atr_pctile_window, min_periods=min(200, atr_pctile_window)).rank(pct=True)
    pad = (min_penetration_atr * atr).to_numpy() if min_penetration_atr > 0.0 else np.zeros(len(df))

    high = df["high"].to_numpy()
    low = df["low"].to_numpy()
    hh20 = df["HH20"].to_numpy()
    ll20 = df["LL20"].to_numpy()
    ll20_2nd = df["LL20_2nd"].to_numpy()

    # Raw per-bar breach (wick pierces the prior 20-day extreme). NaN levels -> False.
    df["higher_purge"] = high > (hh20 + pad)
    df["lower_purge"] = low < (ll20 - pad)

    # --- Debounce = stateful latch: once purged, stay armed until a FULL BAR trades back
    #     inside the 20-day range; only then can that side fire again (per user #4).
    #     Measured: resetting on a full bar inside (high<=HH20) is the least trend-spammy
    #     rule -- a close-based reset re-arms every wick-out/close-in purge bar (~2x events). ---
    n = len(df)
    higher_event = np.zeros(n, dtype=bool)
    lower_event = np.zeros(n, dtype=bool)
    armed_h = False
    armed_l = False
    for i in range(n):
        hi_level = hh20[i] + pad[i]
        lo_level = ll20[i] - pad[i]
        # higher side
        if high[i] > hi_level and not armed_h:
            higher_event[i] = True
            armed_h = True
        if armed_h and high[i] <= hh20[i]:   # whole bar back inside -> re-arm
            armed_h = False
        # lower side
        if low[i] < lo_level and not armed_l:
            lower_event[i] = True
            armed_l = True
        if armed_l and low[i] >= ll20[i]:
            armed_l = False
    df["higher_event"] = higher_event
    df["lower_event"] = lower_event

    # Second-low lower purge detection (parallel latch using LL20_2nd).
    lower_event_2nd = np.zeros(n, dtype=bool)
    armed_l_2nd = False
    for i in range(n):
        if low[i] < ll20_2nd[i] and not armed_l_2nd:
            lower_event_2nd[i] = True
            armed_l_2nd = True
        if armed_l_2nd and low[i] >= ll20_2nd[i]:
            armed_l_2nd = False
    df["lower_event_2nd"] = lower_event_2nd

    # --- Delayed entry. reversion: LOWER->BUY, HIGHER->SELL. continuation: the reverse. ---
    buy_event, sell_event = ("lower_event", "higher_event") if mode == "reversion" \
        else ("higher_event", "lower_event")
    df["entry_buy"] = df[buy_event].shift(delay_bars, fill_value=False)
    df["entry_sell"] = df[sell_event].shift(delay_bars, fill_value=False)
    return df


def _session(hour: int) -> str:
    """Approximate UTC session block (documented; crypto is 24/7 but the clock still conditions)."""
    if 0 <= hour < 7:
        return "Asia"
    if 7 <= hour < 12:
        return "London"
    if 12 <= hour < 16:
        return "Overlap"
    if 16 <= hour < 21:
        return "NY"
    return "Late"


def _build_setups(df: pd.DataFrame, delay_bars: int, mode: str = "reversion",
                  second_low: bool = False) -> pd.DataFrame:
    """One row per purge event with its (positional) delayed entry + conditioning features.

    When *second_low=True*, uses the LL20_2nd level and lower_event_2nd detection
    (only LOWER events), and adds purge_depth_price / purge_depth_atr columns.
    """
    ts = df.index
    n = len(df)
    open_ = df["open"].to_numpy()
    high = df["high"].to_numpy()
    low = df["low"].to_numpy()
    hh20 = df["HH20"].to_numpy()
    ll20 = df["LL20"].to_numpy()
    ll20_2nd = df["LL20_2nd"].to_numpy() if "LL20_2nd" in df.columns else ll20
    atr = df["atr"].to_numpy()
    atr_pctile = df["atr_pctile"].to_numpy()

    rows = []
    if second_low:
        event_positions = [(p, "LOWER") for p in np.flatnonzero(df["lower_event_2nd"].to_numpy())]
    else:
        event_positions = (
            [(p, "HIGHER") for p in np.flatnonzero(df["higher_event"].to_numpy())]
            + [(p, "LOWER") for p in np.flatnonzero(df["lower_event"].to_numpy())]
        )

    for pos, kind in event_positions:
        e = pos + delay_bars
        level = (hh20[pos] if kind == "HIGHER"
                 else (ll20_2nd[pos] if second_low else ll20[pos]))
        purge_px = high[pos] if kind == "HIGHER" else low[pos]
        atr_p = atr[pos]
        pen_atr = (abs(purge_px - level) / atr_p) if atr_p and atr_p == atr_p else np.nan
        entry_px = open_[e] if e < n else np.nan
        atr_e = atr[e] if e < n else np.nan
        atr_frac_entry = (atr_e / entry_px) if (e < n and entry_px and entry_px == entry_px
                                                and atr_e == atr_e) else np.nan

        row = {
            "purge_time": ts[pos],
            "purge_type": kind,
            "purge_price": purge_px,
            "level": level,
            "signal": (("SELL" if kind == "HIGHER" else "BUY") if mode == "reversion"
                       else ("BUY" if kind == "HIGHER" else "SELL")),
            "session": _session(ts[pos].hour),
            "pen_atr": pen_atr,                               # purge magnitude beyond level, ATR units
            "atr_pctile": atr_pctile[pos],                    # trailing volatility-regime rank
            "atr_frac_entry": atr_frac_entry,                 # R denominator = ATR_at_entry / entry_px
            "entry_pos": e,                                   # positional index (internal)
            "entry_time": ts[e] if e < n else pd.NaT,
            "entry_price": entry_px,
        }
        if second_low and kind == "LOWER":
            purge_depth_price = level - purge_px              # second_low_20d - purge_low (positive)
            purge_depth_atr = (purge_depth_price / atr_p
                               if atr_p and atr_p == atr_p else np.nan)
            row["purge_depth_price"] = purge_depth_price
            row["purge_depth_atr"] = purge_depth_atr
        rows.append(row)

    setups = pd.DataFrame(rows)
    if not setups.empty:
        setups = setups.sort_values("purge_time").reset_index(drop=True)
    return setups


def post_purge_analysis(df: pd.DataFrame, setups: pd.DataFrame,
                        bar_minutes: float = 15) -> pd.DataFrame:
    r"""Extract exact 8-bar post-window for each second-low purge event and compute metrics.

    Uses positional indexing (``iloc``) to avoid inclusive-endpoint off-by-one errors
    that ``df.loc[purge_time : purge_time + 2h]`` would produce (9 bars instead of 8).

    Validates:
    * exactly 8 bars in the window
    * first bar timestamp == purge_time + bar_minutes
    * last bar timestamp  == purge_time + 8 * bar_minutes

    Invalid windows are flagged (window_valid=False) rather than producing silent bad metrics.

    Metrics computed (for a LOWER purge / BUY bias):
        post_high          — highest high in the 8-bar window
        post_low           — lowest low  in the 8-bar window
        post_close         — close of the 8th bar (2h after purge)
        mfe                — maximum favourable excursion = post_high - purge_low
        mae                — maximum adverse   excursion = purge_low - post_low
        close_displacement — post_close - purge_low  (positive = price above purge low)
        time_to_high_min   — minutes from purge_time to the bar containing post_high
        time_to_low_min    — minutes from purge_time to the bar containing post_low
    """
    N_POST = 8
    step = pd.Timedelta(minutes=bar_minutes)
    purge_col = "purge_low"
    post_rows = []

    for _, row in setups.iterrows():
        purge_time = row["purge_time"]
        purge_low = row["purge_price"]

        # Locate the purge bar's positional index.
        try:
            purge_pos = df.index.get_loc(purge_time)
        except (KeyError, TypeError):
            post_rows.append({
                "purge_time": purge_time, purge_col: purge_low,
                "window_valid": False, "window_n_bars": 0,
                "window_msg": "purge_time_not_found_in_df",
            })
            continue

        # Handle potential duplicate timestamps (keep first occurrence).
        if isinstance(purge_pos, slice):
            purge_pos = purge_pos.start
        elif isinstance(purge_pos, np.ndarray):
            purge_pos = int(np.flatnonzero(purge_pos)[0])

        # Slice: iloc[pos+1 : pos+1+N_POST] = exactly N_POST bars after (excluding) purge bar.
        if purge_pos + 1 + N_POST > len(df):
            actual = len(df) - purge_pos - 1
            post_rows.append({
                "purge_time": purge_time, purge_col: purge_low,
                "window_valid": False, "window_n_bars": max(0, actual),
                "window_msg": f"insufficient_bars_after_purge_need_{N_POST}_got_{actual}",
            })
            continue

        post = df.iloc[purge_pos + 1: purge_pos + 1 + N_POST]

        # --- Validation ---
        valid = True
        msg = "ok"
        if len(post) != N_POST:
            valid = False
            msg = f"expected_{N_POST}_bars_got_{len(post)}"
        elif post.index[0] != purge_time + step:
            valid = False
            msg = "first_bar_offset_mismatch"
        elif post.index[-1] != purge_time + N_POST * step:
            valid = False
            msg = "last_bar_offset_mismatch"

        # --- Metrics (computed regardless of validity for debugging) ---
        post_high = float(post["high"].max())
        post_low = float(post["low"].min())
        post_close = float(post["close"].iloc[-1])
        mfe = post_high - purge_low          # max favourable  (for BUY)
        mae = purge_low - post_low            # max adverse     (for BUY)
        close_disp = post_close - purge_low   # close displacement

        # Time to extreme (minutes from purge bar).
        tth = int((post["high"].idxmax() - purge_time).total_seconds() / 60.0)
        ttl = int((post["low"].idxmin() - purge_time).total_seconds() / 60.0)

        post_rows.append({
            "purge_time": purge_time,
            purge_col: purge_low,
            "level_2nd": row.get("level", np.nan),
            "purge_depth_price": row.get("purge_depth_price", np.nan),
            "purge_depth_atr": row.get("purge_depth_atr", np.nan),
            "window_valid": valid,
            "window_msg": msg,
            "post_high": post_high,
            "post_low": post_low,
            "post_close": post_close,
            "mfe": mfe,
            "mae": mae,
            "close_displacement": close_disp,
            "time_to_high_min": tth,
            "time_to_low_min": ttl,
        })

    return pd.DataFrame(post_rows)


def _parse_horizons(spec: str, bar_minutes: float) -> list[tuple[str, float, int]]:
    """'1,2,4,24' (hours) -> [(label, hours, bars), ...] with bars inferred from timeframe."""
    out = []
    for tok in spec.split(","):
        tok = tok.strip()
        if not tok:
            continue
        h = float(tok)
        bars = max(1, int(round(h * 60.0 / bar_minutes)))
        label = f"{int(h // 24)}d" if h >= 24 and h % 24 == 0 else f"{h:g}h"
        out.append((label, h, bars))
    return out


def add_forward_returns(df: pd.DataFrame, setups: pd.DataFrame,
                        horizons: list[tuple[str, float, int]]) -> pd.DataFrame:
    """Direction-adjusted % return from the ENTRY bar to each horizon (mark-to-market)."""
    close = df["close"].to_numpy()
    n = len(df)
    entry_pos = setups["entry_pos"].to_numpy()
    entry_px = setups["entry_price"].to_numpy()
    is_buy = (setups["signal"] == "BUY").to_numpy()
    atr_frac = setups["atr_frac_entry"].to_numpy()

    for label, _h, bars in horizons:
        col = np.full(len(setups), np.nan)
        for i in range(len(setups)):
            e = int(entry_pos[i])
            fut = e + bars
            if e >= n or fut >= n or np.isnan(entry_px[i]):
                continue
            raw = close[fut] / entry_px[i] - 1.0
            col[i] = (raw if is_buy[i] else -raw) * 100.0
        setups[f"ret_{label}"] = col
        # ATR-normalized R-multiple = fractional move / (ATR_at_entry / entry_px).
        with np.errstate(divide="ignore", invalid="ignore"):
            r = (col / 100.0) / np.where((atr_frac > 0), atr_frac, np.nan)
        setups[f"ret_R_{label}"] = r
    return setups


def _baseline(close: np.ndarray, bars: int) -> tuple[float, float, float]:
    """All-bars forward drift: (long_mean%, P(up)%, P(down)%)."""
    if bars >= len(close):
        return np.nan, np.nan, np.nan
    a = close[bars:] / close[:-bars] - 1.0
    a = a[~np.isnan(a)]
    if a.size == 0:
        return np.nan, np.nan, np.nan
    return a.mean() * 100.0, (a > 0).mean() * 100.0, (a < 0).mean() * 100.0


def forward_return_summary(df: pd.DataFrame, setups: pd.DataFrame,
                           horizons: list[tuple[str, float, int]]) -> pd.DataFrame:
    """Per (direction, horizon): signal stats + direction-matched all-bars baseline + edge."""
    close = df["close"].to_numpy()
    n_buy = int((setups["signal"] == "BUY").sum())
    n_sell = int((setups["signal"] == "SELL").sum())
    tot = n_buy + n_sell
    rows = []
    for label, _h, bars in horizons:
        col = f"ret_{label}"
        long_mean, up, down = _baseline(close, bars)
        for direction in ("BUY", "SELL", "ALL"):
            if direction == "ALL":
                sub = setups[col].dropna()
                base_mean = (n_buy * long_mean + n_sell * (-long_mean)) / tot if tot else np.nan
                base_win = (n_buy * up + n_sell * down) / tot if tot else np.nan
            else:
                sub = setups.loc[setups["signal"] == direction, col].dropna()
                base_mean = long_mean if direction == "BUY" else -long_mean
                base_win = up if direction == "BUY" else down
            if sub.empty:
                rows.append({"dir": direction, "horizon": label, "n": 0, "mean%": np.nan,
                             "median%": np.nan, "win%": np.nan, "base_mean%": round(base_mean, 3),
                             "base_win%": round(base_win, 1), "edge%": np.nan})
                continue
            rows.append({
                "dir": direction, "horizon": label, "n": int(len(sub)),
                "mean%": round(float(sub.mean()), 3), "median%": round(float(sub.median()), 3),
                "win%": round(float((sub > 0).mean()) * 100.0, 1),
                "base_mean%": round(base_mean, 3), "base_win%": round(base_win, 1),
                "edge%": round(float(sub.mean()) - base_mean, 3),
            })
    return pd.DataFrame(rows)


def _main_second_low(df: pd.DataFrame, path: Path, delay_bars: int,
                     bar_minutes: float, args) -> int:
    """Second-low purge analysis: builds setups, extracts 8-bar post-window, prints report.

    Produces separate output files to avoid overwriting absolute-level artifacts.
    """
    setups = _build_setups(df, delay_bars, mode=args.mode, second_low=True)

    # Write annotated df and setups.
    out_path = path.with_name(f"{path.stem}_second_low_scan.csv")
    df.to_csv(out_path)
    print(f"File            : {path}")
    print(f"Rows            : {len(df):,}  ({df.index[0]} -> {df.index[-1]})")
    print(f"Bar interval    : {bar_minutes:.0f} min")
    print(f"Mode            : second-low (LL20_2nd, LOWER only)")
    print(f"Lookback        : {args.lookback_days} days")
    n_2nd = int(df["lower_event_2nd"].sum())
    print(f"Second-low events : {n_2nd}  (detected using 2nd-lowest low of prior {args.lookback_days}d)")
    print(f"Annotated CSV   : {out_path}")
    print()

    if setups.empty:
        print("No second-low purge events detected.")
        return 0

    # Post-purge metrics.
    metrics = post_purge_analysis(df, setups, bar_minutes)

    # Write outputs.
    setups_path = path.with_name(f"{path.stem}_second_low_events.csv")
    setups.drop(columns=["entry_pos"]).to_csv(setups_path, index=False)
    metrics_path = path.with_name(f"{path.stem}_second_low_metrics.csv")
    metrics.to_csv(metrics_path, index=False)

    valid = metrics[metrics["window_valid"]]
    n_valid = len(valid)
    n_invalid = len(metrics) - n_valid

    # ---- Console report ----
    print("Second-Low Purge Events — Post-Purge 2h Window Metrics")
    print("=" * 72)
    print(f"Total events           : {len(metrics)}")
    print(f"Valid windows (8 bars) : {n_valid}")
    print(f"Incomplete windows     : {n_invalid}")
    if n_invalid > 0:
        print(f"  Incomplete details   :")
        for _, r in metrics[~metrics["window_valid"]].iterrows():
            print(f"    {r['purge_time']}: {r['window_msg']}")
    print()

    if n_valid == 0:
        print("No valid post-windows to report.")
        return 0

    # Summary stats on valid windows.
    pd.set_option("display.float_format", lambda x: f"{x:.4f}")
    print("Metric summary (valid windows only):")
    print(f"  purge_depth_price  — mean={valid['purge_depth_price'].mean():.4f}  "
          f"median={valid['purge_depth_price'].median():.4f}")
    print(f"  purge_depth_atr    — mean={valid['purge_depth_atr'].mean():.4f}  "
          f"median={valid['purge_depth_atr'].median():.4f}")
    print(f"  MFE                — mean={valid['mfe'].mean():.4f}  "
          f"median={valid['mfe'].median():.4f}")
    print(f"  MAE                — mean={valid['mae'].mean():.4f}  "
          f"median={valid['mae'].median():.4f}")
    print(f"  close_displacement — mean={valid['close_displacement'].mean():.4f}  "
          f"median={valid['close_displacement'].median():.4f}")
    win_rate = (valid["close_displacement"] > 0).mean() * 100.0
    print(f"  Win rate (close>purge_low) : {win_rate:.1f}%")
    print(f"  Avg time-to-high   : {valid['time_to_high_min'].mean():.1f} min")
    print(f"  Avg time-to-low    : {valid['time_to_low_min'].mean():.1f} min")
    print()
    print(f"Per-event metrics CSV  : {metrics_path}")
    print(f"Setups CSV             : {setups_path}")
    print()

    # Show recent events table.
    show_cols = ["purge_time", "purge_depth_price", "purge_depth_atr",
                 "mfe", "mae", "close_displacement", "time_to_high_min", "time_to_low_min"]
    show = valid[show_cols].tail(20).copy()
    for c in ["purge_depth_price", "purge_depth_atr", "mfe", "mae", "close_displacement"]:
        show[c] = show[c].map(lambda v: f"{v:.4f}" if pd.notna(v) else "")
    with pd.option_context("display.max_rows", 20, "display.width", 260):
        print(show.to_string(index=False))
    if len(valid) > 20:
        print(f"\n... {len(valid)} valid events total.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="20-day purge + delayed-entry detector (read-only).")
    ap.add_argument("--file", required=True, help="Path to an OHLCV CSV or XLSX file.")
    ap.add_argument("--lookback-days", type=int, default=20, help="Range lookback in days (default 20).")
    ap.add_argument("--delay-hours", type=float, default=2.0, help="Entry delay after purge, in hours (default 2).")
    ap.add_argument("--delay-bars", type=int, default=None, help="Override the delay in bars (else derived from --delay-hours).")
    ap.add_argument("--min-penetration-atr", type=float, default=0.0, help="Suppress micro-breaks < k*ATR (default 0 = off).")
    ap.add_argument("--atr-window", type=int, default=14, help="ATR window (default 14).")
    ap.add_argument("--atr-pctile-window", type=int, default=2000, help="Trailing window for the volatility-regime rank (default 2000).")
    ap.add_argument("--mode", choices=("reversion", "continuation"), default="reversion",
                    help="reversion (default): HIGHER->SELL, LOWER->BUY. continuation: HIGHER->BUY, LOWER->SELL.")
    ap.add_argument("--horizons", default="1,2,4,24", help="Forward-return horizons in hours, comma-separated (default 1,2,4,24).")
    ap.add_argument("--out", default=None, help="Annotated CSV output path (default: <input>_purge_scan.csv).")
    ap.add_argument("--second-low", action="store_true",
                    help="Second-low purge analysis: uses LL20_2nd level for LOWER events only, "
                         "extracts exactly 8 post-purge bars, computes MFE/MAE/displacement. "
                         "Produces separate output files without overwriting absolute-level artifacts.")
    args = ap.parse_args(argv)

    path = Path(args.file)
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

    df = _load_ohlcv(path)
    bar_minutes = _infer_bar_minutes(df.index)
    if args.delay_bars is not None:
        delay_bars = args.delay_bars
    else:
        delay_bars = int(round(args.delay_hours * 60.0 / bar_minutes))

    df = scan(
        df,
        lookback_days=args.lookback_days,
        delay_bars=delay_bars,
        min_penetration_atr=args.min_penetration_atr,
        atr_window=args.atr_window,
        mode=args.mode,
        atr_pctile_window=args.atr_pctile_window,
    )

    if args.second_low:
        return _main_second_low(df, path, delay_bars, bar_minutes, args)

    setups = _build_setups(df, delay_bars, mode=args.mode)
    horizons = _parse_horizons(args.horizons, bar_minutes)
    if not setups.empty:
        setups = add_forward_returns(df, setups, horizons)

    out_path = Path(args.out) if args.out else path.with_name(f"{path.stem}_purge_scan.csv")
    df.to_csv(out_path)

    # ---- Report (ASCII only, Windows-console safe) ----
    n_higher = int(df["higher_event"].sum())
    n_lower = int(df["lower_event"].sum())
    print(f"File            : {path}")
    print(f"Rows            : {len(df):,}  ({df.index[0]} -> {df.index[-1]})")
    print(f"Bar interval    : {bar_minutes:.0f} min")
    print(f"Mode            : {args.mode}"
          + ("  (HIGHER->SELL, LOWER->BUY)" if args.mode == "reversion" else "  (HIGHER->BUY, LOWER->SELL)"))
    print(f"Lookback        : {args.lookback_days} days")
    print(f"Entry delay     : {args.delay_hours}h -> {delay_bars} bars"
          + (f"  (min penetration {args.min_penetration_atr} ATR)" if args.min_penetration_atr > 0 else ""))
    print(f"Purge events    : {n_higher} higher (SELL), {n_lower} lower (BUY), {n_higher + n_lower} total")
    print(f"Annotated CSV   : {out_path}")
    print()

    if setups.empty:
        print("No purge events detected (need at least lookback_days+1 days of history).")
        return 0

    # Per-signal output (drop the internal positional index).
    setups_out = setups.drop(columns=["entry_pos"])
    setups_path = path.with_name(f"{path.stem}_setups_{args.mode}.csv")
    setups_out.to_csv(setups_path, index=False)

    # ---- Forward-return summary (direction-adjusted % vs all-bars baseline) ----
    summary = forward_return_summary(df, setups, horizons)
    print("Forward returns (direction-adjusted %, mark-to-market from entry; NO SL/TP, NO cost):")
    print(f"  horizons: " + ", ".join(f"{lbl}={bars}b" for lbl, _h, bars in horizons))
    with pd.option_context("display.width", 200, "display.max_rows", 60):
        print(summary.to_string(index=False))
    print("  edge% = signal mean - direction-matched baseline (what price did anyway). "
          "Descriptive only, not a significance test.")
    print(f"  Per-signal CSV : {setups_path}")
    print()

    # ---- Setup sample (most recent) — focused columns; full detail lives in the CSV ----
    ret_cols = [f"ret_{lbl}" for lbl, _h, _b in horizons]
    show = setups_out[["purge_time", "session", "signal", "pen_atr", "atr_pctile",
                       "entry_price"] + ret_cols].copy()
    show["pen_atr"] = show["pen_atr"].map(lambda v: "" if pd.isna(v) else f"{v:.2f}")
    show["atr_pctile"] = show["atr_pctile"].map(lambda v: "" if pd.isna(v) else f"{v:.2f}")
    show["entry_price"] = show["entry_price"].map(lambda v: "" if pd.isna(v) else f"{v:.5f}")
    for c in ret_cols:
        show[c] = show[c].map(lambda v: "" if pd.isna(v) else f"{v:+.2f}")
    with pd.option_context("display.max_rows", 20, "display.width", 220):
        print(show.tail(20).to_string(index=False))
    if len(setups) > 20:
        print(f"\n... {len(setups)} setups total (full detail in {setups_path}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
