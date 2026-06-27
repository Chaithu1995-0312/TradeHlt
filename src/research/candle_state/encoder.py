"""encoder.py — CandleStateEncoder: a candle window -> discrete state + continuous features.

Pure, no-lookahead: `encode(window)` reads only `window` (past + current bar), never future
bars — mirroring `research.indicators` discipline. It reuses the audited research ATR
(`research.indicators.atr`) so the true-range definition is byte-identical to what every
hypothesis/control already uses.

The state vocabulary is the user's Stage-1 alphabet, split into four orthogonal axes so the
multi-timeframe conjunction can pick the aspect that matters per timeframe:

  * direction  — BULL_STRONG | BULL_WEAK | BEAR_STRONG | BEAR_WEAK | DOJI  (body sign + size)
  * vol        — COMPRESSION | NORMAL | EXPANSION                          (current TR / trailing ATR)
  * structure  — INSIDE_BAR | OUTSIDE_BAR | NORMAL                         (range vs previous bar)
  * trend      — UP | DOWN | FLAT                                          (close vs trailing SMA)

All thresholds are constructor args (declared in the Program-4b/c/d pre-registration, NOT a
production config — this is research land, like `conditional_entropy_grid`). Defaults are the
pre-registered values. NO magic numbers leak into call sites.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from research.indicators import atr, sma

# ── state vocabulary (frozen tokens; conjunction keys are built from these) ──────────
DIR_BULL_STRONG = "BULL_STRONG"
DIR_BULL_WEAK = "BULL_WEAK"
DIR_BEAR_STRONG = "BEAR_STRONG"
DIR_BEAR_WEAK = "BEAR_WEAK"
DIR_DOJI = "DOJI"

VOL_COMPRESSION = "COMPRESSION"
VOL_NORMAL = "NORMAL"
VOL_EXPANSION = "EXPANSION"

STRUCT_INSIDE = "INSIDE_BAR"
STRUCT_OUTSIDE = "OUTSIDE_BAR"
STRUCT_NORMAL = "NORMAL"

TREND_UP = "UP"
TREND_DOWN = "DOWN"
TREND_FLAT = "FLAT"


@dataclass(frozen=True)
class CandleState:
    """Encoded state of the bar at the END of the window. All fields deterministic."""

    direction: str
    vol: str
    structure: str
    trend: str
    body_pct: float            # |close-open| / (high-low)
    upper_wick_pct: float      # (high-max(open,close)) / (high-low)
    lower_wick_pct: float      # (min(open,close)-low) / (high-low)
    volume_z: float            # (volume - mean) / std over the trailing volume window
    atr_ratio: float           # current true range / trailing ATR (1.0 == typical)
    range_expansion_ratio: float  # current range / mean prior range over the lookback

    def token(self) -> str:
        """Compact per-timeframe label for conjunction keys: direction+vol (the two axes
        that carry the transition signal). e.g. 'BULL_STRONG/EXPANSION'."""
        return f"{self.direction}/{self.vol}"


class CandleStateEncoder:
    """Encode a candle window into a `CandleState`. Pure; one instance is reusable per TF."""

    def __init__(
        self,
        *,
        atr_period: int = 14,
        sma_period: int = 20,
        volume_window: int = 50,
        body_strong_pct: float = 0.6,   # body_pct >= this => *_STRONG
        doji_body_pct: float = 0.1,     # body_pct <= this => DOJI
        compression_atr_ratio: float = 0.7,  # tr/atr <= this => COMPRESSION
        expansion_atr_ratio: float = 1.5,    # tr/atr >= this => EXPANSION
        trend_flat_pct: float = 0.001,  # |close/sma - 1| <= this => FLAT
        lookback: int = 5,              # bars for range_expansion + inside/outside comparison
    ):
        self.atr_period = atr_period
        self.sma_period = sma_period
        self.volume_window = volume_window
        self.body_strong_pct = body_strong_pct
        self.doji_body_pct = doji_body_pct
        self.compression_atr_ratio = compression_atr_ratio
        self.expansion_atr_ratio = expansion_atr_ratio
        self.trend_flat_pct = trend_flat_pct
        self.lookback = lookback

    # -- internals ------------------------------------------------------------
    @staticmethod
    def _geometry(bar) -> tuple[float, float, float]:
        """(body_pct, upper_wick_pct, lower_wick_pct); 0/0/0 for a zero-range bar."""
        hi, lo = float(bar.high), float(bar.low)
        rng = hi - lo
        if rng <= 0.0:
            return 0.0, 0.0, 0.0
        o, c = float(bar.open), float(bar.close)
        body = abs(c - o) / rng
        upper = (hi - max(o, c)) / rng
        lower = (min(o, c) - lo) / rng
        return body, upper, lower

    def _direction(self, bar, body_pct: float) -> str:
        if body_pct <= self.doji_body_pct:
            return DIR_DOJI
        strong = body_pct >= self.body_strong_pct
        if bool(bar.is_bullish):
            return DIR_BULL_STRONG if strong else DIR_BULL_WEAK
        return DIR_BEAR_STRONG if strong else DIR_BEAR_WEAK

    def _vol(self, atr_ratio: float) -> str:
        if atr_ratio <= 0.0:
            return VOL_NORMAL
        if atr_ratio <= self.compression_atr_ratio:
            return VOL_COMPRESSION
        if atr_ratio >= self.expansion_atr_ratio:
            return VOL_EXPANSION
        return VOL_NORMAL

    def _structure(self, bar, prev) -> str:
        if prev is None:
            return STRUCT_NORMAL
        hi, lo = float(bar.high), float(bar.low)
        ph, pl = float(prev.high), float(prev.low)
        if hi <= ph and lo >= pl:
            return STRUCT_INSIDE
        if hi >= ph and lo <= pl:
            return STRUCT_OUTSIDE
        return STRUCT_NORMAL

    def _trend(self, bar, window) -> str:
        if len(window) < self.sma_period:
            return TREND_FLAT
        ma = sma(window, self.sma_period)
        if ma <= 0.0:
            return TREND_FLAT
        dev = float(bar.close) / ma - 1.0
        if dev > self.trend_flat_pct:
            return TREND_UP
        if dev < -self.trend_flat_pct:
            return TREND_DOWN
        return TREND_FLAT

    def _volume_z(self, window) -> float:
        vols = [float(b.volume) for b in window[-self.volume_window:]]
        if len(vols) < 2:
            return 0.0
        prior = vols[:-1]   # trailing stats exclude the current bar (no self-leak)
        n = len(prior)
        if n < 1:
            return 0.0
        mean = sum(prior) / n
        var = sum((v - mean) ** 2 for v in prior) / n
        std = var ** 0.5
        if std <= 0.0:
            return 0.0
        return (vols[-1] - mean) / std

    def _range_expansion(self, window) -> float:
        bars = window[-(self.lookback + 1):]
        if len(bars) < 2:
            return 1.0
        cur = float(bars[-1].high) - float(bars[-1].low)
        prior = [float(b.high) - float(b.low) for b in bars[:-1]]
        prior = [r for r in prior if r > 0.0]
        if not prior:
            return 1.0
        mean_prior = sum(prior) / len(prior)
        if mean_prior <= 0.0:
            return 1.0
        return cur / mean_prior

    # -- public ---------------------------------------------------------------
    def encode(self, window: Sequence) -> CandleState:
        """Encode the bar at the end of `window`. Requires a non-empty window."""
        bars = list(window)
        if not bars:
            raise ValueError("CandleStateEncoder.encode: empty window")
        bar = bars[-1]
        prev = bars[-2] if len(bars) >= 2 else None

        body_pct, upper, lower = self._geometry(bar)
        a = atr(bars, self.atr_period)
        cur_tr = float(bar.high) - float(bar.low)
        atr_ratio = (cur_tr / a) if a > 0.0 else 0.0

        return CandleState(
            direction=self._direction(bar, body_pct),
            vol=self._vol(atr_ratio),
            structure=self._structure(bar, prev),
            trend=self._trend(bar, bars),
            body_pct=round(body_pct, 6),
            upper_wick_pct=round(upper, 6),
            lower_wick_pct=round(lower, 6),
            volume_z=round(self._volume_z(bars), 6),
            atr_ratio=round(atr_ratio, 6),
            range_expansion_ratio=round(self._range_expansion(bars), 6),
        )
