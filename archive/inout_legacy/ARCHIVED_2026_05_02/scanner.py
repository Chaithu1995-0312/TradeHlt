"""
inout/scanner.py
═══════════════════════════════════════════════════════════════════════════════
INOUT Strategy — Explosive Move Scanner

Detects fast, explosive market moves on M1/M5 crypto candles.
Operates INDEPENDENTLY from EngineRunner — zero shared state.

Detection logic (Phase 1 — rule-based, config-driven):
    1. Candle expansion  — body >= N × ATR (displacement burst)
    2. Volume spike      — volume >= N × rolling average
    3. Structure breakout — close above/below recent N-candle range

Composite score (0.0–1.0) gates entry:
    score = weighted_sum(condition_scores)
    if score >= min_composite_score → signal fires

Design principles
-----------------
    - Stateless per-call: INOUTScanner holds no candle history.
      The caller (runner) passes a lookback window each call.
    - Pure functions: _score_* methods take data, return float.
    - No EngineRunner, no FusionEngine, no shared pipeline state.

Extension points
----------------
    Phase 2: replace _compute_composite_score() with probability engine output
    Phase 2: add _score_crt_pattern() from historical pattern miner
    Phase 3: add Gemini context layer as optional booster score
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .config import INOUTConfig

logger = logging.getLogger("INOUT.SCANNER")


# ── Signal dataclass ─────────────────────────────────────────────────────────

@dataclass
class INOUTSignal:
    """
    Output of INOUTScanner.scan(). Carries all information needed
    by INOUTController to build a trade plan and pass Ultron.
    """
    symbol: str
    timeframe: str                          # "M1" | "M5"
    direction: str                          # "LONG" | "SHORT"
    composite_score: float                  # 0.0–1.0
    trigger_price: float                    # close of triggering candle
    candle_high: float
    candle_low: float
    atr: float                              # ATR at time of signal
    volume_ratio: float                     # volume / rolling_avg_volume
    candle_expansion: float                 # body_size / atr
    structure_broken: bool
    conditions_met: list[str]              # which conditions triggered
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    raw_candle: dict[str, Any] = field(default_factory=dict)

    # Extension point — Phase 2
    prob_p50_min: float | None = None       # P50 time-to-peak from probability engine
    prob_p75_min: float | None = None       # P75 time-to-peak
    prob_roi_p50: float | None = None       # P50 expected ROI %
    prob_result: dict[str, Any] | None = None   # Full probability engine output (wired Phase 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "direction": self.direction,
            "composite_score": round(self.composite_score, 4),
            "trigger_price": self.trigger_price,
            "candle_high": self.candle_high,
            "candle_low": self.candle_low,
            "atr": self.atr,
            "volume_ratio": round(self.volume_ratio, 4),
            "candle_expansion": round(self.candle_expansion, 4),
            "structure_broken": self.structure_broken,
            "conditions_met": self.conditions_met,
            "timestamp": self.timestamp.isoformat(),
        }


# ── Scanner ───────────────────────────────────────────────────────────────────

class INOUTScanner:
    """
    Explosive move detector for M1/M5 crypto candles.

    Usage
    -----
        scanner = INOUTScanner(cfg)

        # Call on every new candle close:
        signal = scanner.scan(
            symbol="BTCUSDT",
            timeframe="M1",
            candles=last_30_candles,   # list of OHLCV dicts, newest last
        )
        if signal is not None:
            # Forward to INOUTController
            controller.on_signal(signal)

    Candle dict format (compatible with Binance kline response):
        {
            "open": float, "high": float, "low": float, "close": float,
            "volume": float, "atr": float  (pre-computed, or None for auto)
        }
    """

    def __init__(self, cfg: INOUTConfig) -> None:
        self._cfg = cfg
        # Per-symbol cooldown tracker: symbol → last signal epoch seconds
        self._cooldown: dict[str, float] = {}

    # ── Public entry point ────────────────────────────────────────────────────

    def scan(
        self,
        symbol: str,
        timeframe: str,
        candles: list[dict[str, Any]],
        prob_adapter: Any = None,
    ) -> INOUTSignal | None:
        """
        Scan the latest candle for an explosive move signal.

        Parameters
        ----------
        symbol       : e.g. "BTCUSDT"
        timeframe    : "M1" | "M5"
        candles      : ordered list of OHLCV dicts, newest at index -1.
                       Minimum length: volume_lookback + 1
        prob_adapter : optional INOUTScannerProbAdapter — when provided,
                       the composite score is replaced with a probability-
                       enhanced score and INOUTSignal.prob_result is populated.
                       Phase 2 activation point.

        Returns INOUTSignal or None if no signal.
        """
        # ── Guard: allowed symbols ────────────────────────────────────────────
        allowed = self._cfg.scanner("allowed_symbols", [])
        if allowed and symbol not in allowed:
            return None

        # ── Guard: allowed timeframes ─────────────────────────────────────────
        scan_tfs = self._cfg.scanner("scan_timeframes", ["M1", "M5"])
        if timeframe not in scan_tfs:
            return None

        # ── Guard: minimum candles ────────────────────────────────────────────
        lookback = int(self._cfg.scanner("volume_lookback", 20))
        struct_lookback = int(self._cfg.scanner("structure_lookback", 10))
        min_candles = max(lookback, struct_lookback) + 1
        if len(candles) < min_candles:
            logger.debug(
                "INOUT.SCANNER: %s insufficient candles (%d < %d)",
                symbol, len(candles), min_candles,
            )
            return None

        # ── Guard: cooldown ───────────────────────────────────────────────────
        cooldown_sec = float(self._cfg.scanner("cooldown_seconds", 120))
        last = self._cooldown.get(symbol, 0.0)
        if time.time() - last < cooldown_sec:
            return None

        # ── Extract current + history ─────────────────────────────────────────
        current = candles[-1]
        history = candles[:-1]

        # ── ATR (use pre-computed if present, else estimate from candle) ───────
        atr = self._get_atr(current, history)
        min_atr = float(self._cfg.scanner("min_atr_threshold", 0.0003))
        if atr < min_atr:
            return None

        # ── Score each condition ──────────────────────────────────────────────
        expansion_score, body_size, direction = self._score_expansion(current, atr)
        volume_score, vol_ratio = self._score_volume(current, history, lookback)
        breakout_score, struct_broken = self._score_breakout(
            current, history, struct_lookback, direction
        )

        # ── Composite score ───────────────────────────────────────────────────
        composite, conditions_met = self._compute_composite_score(
            expansion_score, volume_score, breakout_score
        )

        # ── Phase 2: probability-enhanced scoring ─────────────────────────────
        # When prob_adapter is wired in (runner passes it), the composite score
        # is replaced with a probability-weighted enhanced score. Falls back to
        # rule-based score transparently if the engine is not yet fitted.
        prob_result: dict[str, Any] | None = None
        if prob_adapter is not None:
            signal_features = {
                "atr": atr,
                "volume_ratio": vol_ratio,
                "candle_expansion": body_size / atr if atr > 0 else 0.0,
                "structure_broken": 1 if struct_broken else 0,
                "direction": "LONG" if direction > 0 else "SHORT",
                "signal_score": composite,
                "rr_ratio": 2.0,  # default RR hint; controller will refine
            }
            enhanced_score, prob_result = prob_adapter.score_signal(composite, signal_features)
            logger.debug(
                "INOUT.SCANNER: %s prob-enhanced score %.3f → %.3f (approach=%s)",
                symbol, composite, enhanced_score,
                prob_result.get("approach", "?"),
            )
            composite = enhanced_score

        # ── Gate ──────────────────────────────────────────────────────────────
        min_score = float(self._cfg.scanner("min_composite_score", 0.55))
        if composite < min_score:
            logger.debug(
                "INOUT.SCANNER: %s score %.3f < %.3f threshold — no signal",
                symbol, composite, min_score,
            )
            return None

        if direction == 0:
            # Expansion detected but no clear direction — skip
            return None

        # ── Signal fired ──────────────────────────────────────────────────────
        self._cooldown[symbol] = time.time()

        signal = INOUTSignal(
            symbol=symbol,
            timeframe=timeframe,
            direction="LONG" if direction > 0 else "SHORT",
            composite_score=composite,
            trigger_price=float(current["close"]),
            candle_high=float(current["high"]),
            candle_low=float(current["low"]),
            atr=atr,
            volume_ratio=vol_ratio,
            candle_expansion=body_size / atr if atr > 0 else 0.0,
            structure_broken=struct_broken,
            conditions_met=conditions_met,
            raw_candle=dict(current),
            prob_result=prob_result,
        )

        scoring_path = "prob-enhanced" if prob_result is not None else "rule-based"
        logger.info(
            "INOUT.SCANNER: SIGNAL %s %s %s score=%.3f price=%.5f conds=%s scoring=%s",
            symbol, timeframe, signal.direction,
            composite, signal.trigger_price, conditions_met, scoring_path,
        )
        return signal

    # ── Scoring functions (Phase 2: replace with probability engine) ──────────

    def _score_expansion(
        self,
        candle: dict[str, Any],
        atr: float,
    ) -> tuple[float, float, int]:
        """
        Candle expansion score.

        Returns (score, body_size, direction)
            direction: +1 (bullish), -1 (bearish), 0 (doji/unclear)
        """
        open_ = float(candle["open"])
        close = float(candle["close"])
        body_size = abs(close - open_)

        mult = float(self._cfg.scanner("candle_expansion_atr_mult", 1.8))
        threshold = atr * mult

        if body_size < threshold:
            return 0.0, body_size, 0

        # Normalised score: how many multiples of threshold?
        # Capped at 3× to avoid outlier dominance
        score = min(body_size / threshold, 3.0) / 3.0
        direction = 1 if close > open_ else -1
        return score, body_size, direction

    def _score_volume(
        self,
        candle: dict[str, Any],
        history: list[dict[str, Any]],
        lookback: int,
    ) -> tuple[float, float]:
        """
        Volume spike score vs rolling average.

        Returns (score, volume_ratio)
        """
        vol = float(candle.get("volume", 0.0))
        if vol == 0.0:
            return 0.0, 0.0

        recent = history[-lookback:]
        vols = [float(c.get("volume", 0.0)) for c in recent if c.get("volume", 0.0) > 0]
        if not vols:
            return 0.0, 0.0

        avg_vol = sum(vols) / len(vols)
        if avg_vol == 0.0:
            return 0.0, 0.0

        vol_ratio = vol / avg_vol
        mult = float(self._cfg.scanner("volume_spike_mult", 2.0))

        if vol_ratio < mult:
            return 0.0, vol_ratio

        # Normalise: ratio / (mult * 3) capped at 1.0
        score = min(vol_ratio / (mult * 3), 1.0)
        return score, vol_ratio

    def _score_breakout(
        self,
        candle: dict[str, Any],
        history: list[dict[str, Any]],
        lookback: int,
        direction: int,
    ) -> tuple[float, bool]:
        """
        Structure breakout score.
        Long → close above recent N-candle high
        Short → close below recent N-candle low

        Returns (score, broken)
        """
        if direction == 0:
            return 0.0, False

        recent = history[-lookback:]
        if not recent:
            return 0.0, False

        close = float(candle["close"])

        if direction > 0:
            structure_level = max(float(c["high"]) for c in recent)
            if close <= structure_level:
                return 0.0, False
            # Score by how far above structure
            excess = (close - structure_level) / structure_level
            score = min(excess * 100, 1.0)   # 1% excess → score=1.0
            return score, True
        else:
            structure_level = min(float(c["low"]) for c in recent)
            if close >= structure_level:
                return 0.0, False
            excess = (structure_level - close) / structure_level
            score = min(excess * 100, 1.0)
            return score, True

    def _compute_composite_score(
        self,
        expansion_score: float,
        volume_score: float,
        breakout_score: float,
    ) -> tuple[float, list[str]]:
        """
        Weighted composite score from the three condition scores.

        Weights (tuned for Phase 1 — config-driven in Phase 2):
            expansion  : 0.45  (primary signal — price moves)
            volume     : 0.30  (confirms commitment)
            breakout   : 0.25  (confirms direction / structure)

        Extension point: Phase 2 replaces this with probability engine output.

        Returns (composite_score, conditions_met)
        """
        weights = {
            "expansion": 0.45,
            "volume": 0.30,
            "breakout": 0.25,
        }

        conditions_met = []
        if expansion_score > 0:
            conditions_met.append("expansion")
        if volume_score > 0:
            conditions_met.append("volume")
        if breakout_score > 0:
            conditions_met.append("breakout")

        require_all = bool(self._cfg.scanner("require_all_conditions", False))
        if require_all and len(conditions_met) < 3:
            return 0.0, conditions_met

        composite = (
            weights["expansion"] * expansion_score
            + weights["volume"] * volume_score
            + weights["breakout"] * breakout_score
        )
        return round(composite, 6), conditions_met

    # ── ATR helper ────────────────────────────────────────────────────────────

    def _get_atr(
        self,
        candle: dict[str, Any],
        history: list[dict[str, Any]],
        period: int = 14,
    ) -> float:
        """
        Use pre-computed ATR from candle dict if present.
        Otherwise compute simple average true range from history.
        """
        if "atr" in candle and candle["atr"] is not None:
            return float(candle["atr"])

        # Fallback: simple average of (high - low) over last `period` candles
        window = history[-period:] if len(history) >= period else history
        if not window:
            return float(candle.get("high", 0.0)) - float(candle.get("low", 0.0))

        tr_values = []
        for i, c in enumerate(window):
            h = float(c.get("high", 0.0))
            lo = float(c.get("low", 0.0))
            prev_close = float(window[i - 1]["close"]) if i > 0 else h
            tr = max(h - lo, abs(h - prev_close), abs(lo - prev_close))
            tr_values.append(tr)

        return sum(tr_values) / len(tr_values) if tr_values else 0.0
