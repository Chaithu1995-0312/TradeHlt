"""Independent FC1-A swing / structure oracle — pure pandas/numpy from OHLC + k.

Does NOT import FeaturePipeline.compute_structure_liquidity or causal_structure
for the algorithm. Re-expresses the published contract:

  1. Centered pivot: local max/min of high/low over width w=2k+1 (center=True)
  2. Causal publication: centered flags/prices shifted by k (available_at = t+k)
  3. Structure graph: HH/LL/BOS/sweep vs prev(last_swing_*_price)  [shift 1]

Used by tests/test_fc1a_swing_oracle_parity.py to prove pipeline production
columns ≡ this recompute (type-1 series parity for FM-045/046/066/067 + graph).

Authority: research/test only. Grants no production change authority.
"""
from __future__ import annotations

from typing import Mapping

import numpy as np
import pandas as pd


def require_k(k: int | None) -> int:
    if k is None:
        raise ValueError("swing half-window k is required (no silent default)")
    k = int(k)
    if k < 1:
        raise ValueError(f"swing half-window k must be >= 1, got {k}")
    return k


def fc1a_oracle(
    high: pd.Series | np.ndarray | list,
    low: pd.Series | np.ndarray | list,
    close: pd.Series | np.ndarray | list,
    *,
    k: int,
) -> pd.DataFrame:
    """Return oracle columns aligned to the input index length.

    Columns:
      swing_high_centered_batch, swing_low_centered_batch,
      last_swing_high_price_centered_batch, last_swing_low_price_centered_batch,
      swing_high, swing_low,                     # production = causal delayed
      last_swing_high_price, last_swing_low_price,
      higher_high, lower_low, break_of_structure, liquidity_sweep
    """
    k = require_k(k)
    w = 2 * k + 1
    high_s = pd.Series(np.asarray(high, dtype=float), name="high")
    low_s = pd.Series(np.asarray(low, dtype=float), name="low")
    close_s = pd.Series(np.asarray(close, dtype=float), name="close")
    if not (len(high_s) == len(low_s) == len(close_s)):
        raise ValueError("high/low/close length mismatch")

    # ── CENTERED_BATCH (research identity; may use future bars relative to pivot) ──
    roll_high = high_s.rolling(w, center=True, min_periods=w).max()
    roll_low = low_s.rolling(w, center=True, min_periods=w).min()
    sh_c = (high_s == roll_high).astype(np.int8)
    sl_c = (low_s == roll_low).astype(np.int8)
    last_h_c = high_s.where(sh_c == 1).ffill()
    last_l_c = low_s.where(sl_c == 1).ffill()

    # ── CAUSAL_CONFIRMED (production publication) ──
    sh = sh_c.shift(k).fillna(0).astype(np.int8)
    sl = sl_c.shift(k).fillna(0).astype(np.int8)
    last_h = last_h_c.shift(k)
    last_l = last_l_c.shift(k)

    # ── Structure graph on causal refs only ──
    ref_h = last_h.shift(1)
    ref_l = last_l.shift(1)
    higher_high = (high_s > ref_h).astype(np.int8)
    lower_low = (low_s < ref_l).astype(np.int8)
    bos = np.where(
        close_s > ref_h, 1,
        np.where(close_s < ref_l, -1, 0),
    ).astype(np.int8)
    sweep_hi = (high_s > ref_h) & (close_s <= ref_h)
    sweep_lo = (low_s < ref_l) & (close_s >= ref_l)
    sweep = np.where(sweep_hi, 1, np.where(sweep_lo, -1, 0)).astype(np.int8)

    return pd.DataFrame(
        {
            "swing_high_centered_batch": sh_c,
            "swing_low_centered_batch": sl_c,
            "last_swing_high_price_centered_batch": last_h_c,
            "last_swing_low_price_centered_batch": last_l_c,
            "swing_high": sh,
            "swing_low": sl,
            "last_swing_high_price": last_h,
            "last_swing_low_price": last_l,
            "higher_high": higher_high,
            "lower_low": lower_low,
            "break_of_structure": bos,
            "liquidity_sweep": sweep,
        }
    )


def oracle_from_ohlcv(df: pd.DataFrame, *, k: int) -> pd.DataFrame:
    """OHLCV frame → oracle; requires columns high, low, close."""
    for col in ("high", "low", "close"):
        if col not in df.columns:
            raise KeyError(f"oracle_from_ohlcv: missing column {col!r}")
    out = fc1a_oracle(df["high"], df["low"], df["close"], k=k)
    out.index = df.index
    return out


def assert_frame_close(
    got: Mapping[str, pd.Series] | pd.DataFrame,
    exp: pd.DataFrame,
    cols: list[str],
    *,
    rtol: float = 1e-9,
    atol: float = 1e-9,
) -> None:
    """Strict column equality for int flags; approx for float prices (NaN-aware)."""
    for col in cols:
        if col not in got.columns if hasattr(got, "columns") else col not in got:
            raise KeyError(f"got missing column {col!r}")
        if col not in exp.columns:
            raise KeyError(f"expected missing column {col!r}")
        g = pd.Series(got[col]).reset_index(drop=True)
        e = exp[col].reset_index(drop=True)
        if col.startswith("last_swing"):
            # float prices; NaN positions must match
            g_nan = g.isna()
            e_nan = e.isna()
            if not g_nan.equals(e_nan):
                raise AssertionError(f"{col}: NaN mask mismatch")
            mask = ~g_nan
            if mask.any():
                np.testing.assert_allclose(
                    g.loc[mask].to_numpy(dtype=float),
                    e.loc[mask].to_numpy(dtype=float),
                    rtol=rtol,
                    atol=atol,
                    err_msg=col,
                )
        else:
            np.testing.assert_array_equal(
                g.to_numpy(),
                e.to_numpy(),
                err_msg=col,
            )
