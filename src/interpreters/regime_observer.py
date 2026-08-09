"""regime_observer.py — non-directional volatility-regime reading (Program 4 / Program 4b).

Three objects, one logic:

  * `RegimeLabeler` — the pure, no-lookahead core. Classifies each bar into a volatility
    regime {C, N, E} from a TRAILING window only (the last `tercile_window` ATR values up
    to and including the bar), split at that window's own 33.3/66.7 ATR percentiles. This
    is deliberately NOT the production `volatility_regime` global-percentile rank (F-029) —
    a whole-series statistic would leak the future into the forecast target. The conditioning
    harness (`research.regime_conditioning`) consumes this label series.

  * `MarkovRegimeForecaster` — Program 4b's forward Markov `P^H` transition forecast. Consumes
    the SAME `RegimeLabeler` state series (reused, never reimplemented) and projects it `h`
    bars ahead via a trailing transition-count matrix. See its own docstring for the
    no-lookahead contract. Genuinely different question from the level channel (F-030,
    KILLED): "what regime is coming" vs. "what regime is now."

  * `RegimeObserver` — the contract-compliant home: a `BaseInterpreter` that emits a single
    `EventKind.OBSERVATION` event carrying the current regime (non-directional, `direction=None`).
    This exercises the Interpreter Contract's dormant OBSERVATION branch (the adapter skips
    non-directional events) so a future fusion layer has a measured, pure regime sensor to
    consume. The harness reads `RegimeLabeler` directly — never `event.meta` — so the
    contract's identity-blind boundary is respected.

Pure & deterministic: numpy + stdlib only; trailing-window only; same window → same label.
Grants no authority (§6.5): a regime reading is *information*, never production weight.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Sequence

import numpy as np

from research.indicators import atr

# Canonical regime order — fixed so partitions are diff-stable regardless of which
# regimes the data exercises. C=Compression, N=Normal, E=Expansion (volatility terciles).
REGIMES: tuple[str, str, str] = ("C", "N", "E")

_LOW_PCT = 100.0 / 3.0    # 33.33rd ATR percentile — Compression / Normal cut
_HIGH_PCT = 200.0 / 3.0   # 66.67th ATR percentile — Normal / Expansion cut


@dataclass(frozen=True)
class RegimeLabeler:
    """Trailing-window volatility-regime classifier. No-lookahead by construction.

    `atr_period`   — ATR lookback (matches consumers / process_characterization).
    `tercile_window` — # of trailing ATR readings used to compute the local terciles.
    """

    atr_period: int = 14
    tercile_window: int = 480

    def _trailing_atr(self, candles: Sequence) -> np.ndarray:
        """ATR at each bar i (i in [0, n)), each from a trailing window only.

        Mirrors `process_characterization.atr_series` (which starts at i=1); here we
        keep a full-length array aligned 1:1 with candle index so a lookup by
        `signal.entry_index` is direct. atr[0] is 0.0 (no prior bar)."""
        bars = list(candles)
        n = len(bars)
        if n == 0:
            return np.empty(0, dtype=float)
        out = np.zeros(n, dtype=float)
        for i in range(1, n):
            out[i] = atr(bars[max(0, i - self.atr_period): i + 1], self.atr_period)
        return out

    def label_series(self, candles: Sequence) -> list[str | None]:
        """Label every bar by absolute index. `None` where the trailing window is not yet
        full (those bars are excluded from all cells AND from the unconditioned baseline).

        At bar i: terciles are computed over atr[i-tercile_window+1 : i+1] (trailing only),
        then atr[i] is classified C/N/E. Strictly no-lookahead — only past+current bars."""
        atrs = self._trailing_atr(candles)
        n = atrs.size
        labels: list[str | None] = [None] * n
        w = self.tercile_window
        for i in range(n):
            if i + 1 < w:
                continue                       # trailing window not yet full
            window = atrs[i - w + 1: i + 1]
            av = float(atrs[i])
            if av <= 0.0 or not np.any(window > 0.0):
                continue                       # degenerate / flat — leave unlabeled
            lo = float(np.percentile(window, _LOW_PCT))
            hi = float(np.percentile(window, _HIGH_PCT))
            labels[i] = "C" if av <= lo else ("N" if av <= hi else "E")
        return labels

    def label_at(self, candles: Sequence, index: int) -> str | None:
        """Convenience single-bar lookup (recomputes the series; use label_series in loops)."""
        series = self.label_series(candles)
        return series[index] if 0 <= index < len(series) else None


@dataclass(frozen=True)
class MarkovRegimeForecaster:
    """Forward Markov `P^H` regime-transition forecast (Program 4b). Pure, no-lookahead.

    Consumes the SAME trailing-window vol-tercile states `S_t in {C,N,E}` as `RegimeLabeler`
    (reused verbatim via an owned `RegimeLabeler` instance — never reimplemented) and
    projects them forward: at each bar `t`, a trailing transition-COUNT matrix `P_t` is built
    from the last `w_markov` COMPLETED transitions `tau -> tau+1` with `tau+1 <= t` (rows
    with zero occurrences fall back to uniform `1/3`, since every row of a transition matrix
    must sum to 1). Raising `P_t` to the `h`-th power and projecting the current one-hot
    state gives the H-step-ahead forecast distribution; `Ŝ_{t+h} = argmax`.

    `forecast_series()[t]` is the prediction MADE AT bar `t` for bar `t+h`, using only data
    through `t` — NEVER the realized regime at `t+h`. This is the load-bearing no-lookahead
    property, and it is why the algorithm processes bars strictly in order, incrementally
    (a sliding window of the trailing `w_markov` completed transitions), never touching any
    bar beyond `t` while computing the value at `t` — truncating the input to `candles[:k+1]`
    reproduces `forecast_series(candles)[:k+1]` exactly (see
    `tests/test_markov_regime_forecaster.py`). This makes `forecast_series()` a drop-in
    replacement for `RegimeLabeler.label_series()`'s shape/semantics wherever a label series
    is consumed (e.g. `research.regime_conditioning.evaluate_scope`).

    `atr_period`/`tercile_window` MUST match the `RegimeLabeler` instance whose CURRENT-level
    series is used elsewhere in the same run (Program 4b's within-tercile-shuffle control
    depends on both series sharing the identical `S_t` definition).
    """

    atr_period: int = 14
    tercile_window: int = 480
    w_markov: int = 480
    h: int = 8

    def _labeler(self) -> RegimeLabeler:
        return RegimeLabeler(atr_period=self.atr_period, tercile_window=self.tercile_window)

    def _forecast_and_confidence(
        self, candles: Sequence
    ) -> tuple[list[str | None], list[float | None]]:
        states = self._labeler().label_series(candles)
        n = len(states)
        idx = {g: i for i, g in enumerate(REGIMES)}
        k = len(REGIMES)
        forecasts: list[str | None] = [None] * n
        confidences: list[float | None] = [None] * n

        counts = np.zeros((k, k), dtype=float)
        window: deque[tuple[int, int]] = deque()   # trailing completed (from_idx, to_idx) pairs

        for t in range(n):
            if t >= 1:
                a, b = states[t - 1], states[t]     # the transition (t-1 -> t) just completed
                if a is not None and b is not None:
                    ai, bi = idx[a], idx[b]
                    window.append((ai, bi))
                    counts[ai, bi] += 1.0
                    if len(window) > self.w_markov:
                        oa, ob = window.popleft()
                        counts[oa, ob] -= 1.0

            if states[t] is None or not window:
                continue    # unlabeled current state, or no completed transition observed yet

            row_sums = counts.sum(axis=1, keepdims=True)
            matrix = np.full((k, k), 1.0 / k, dtype=float)
            np.divide(counts, row_sums, out=matrix, where=row_sums > 0)
            p_h = np.linalg.matrix_power(matrix, self.h)

            v_t = np.zeros(k, dtype=float)
            v_t[idx[states[t]]] = 1.0
            projected = v_t @ p_h
            best = int(np.argmax(projected))
            forecasts[t] = REGIMES[best]
            confidences[t] = float(projected[best])
        return forecasts, confidences

    def forecast_series(self, candles: Sequence) -> list[str | None]:
        """`Ŝ_{t+h}` at every bar `t` — see class docstring for the no-lookahead contract."""
        forecasts, _ = self._forecast_and_confidence(candles)
        return forecasts

    def confidence_series(self, candles: Sequence) -> list[float | None]:
        """`max(f_{t+h})` at each bar `t` — forecast confidence, DIAGNOSTIC ONLY (never
        gated on; the M4 economic gate is the sole source of authority, per CLAUDE.md §6.5)."""
        _, confidences = self._forecast_and_confidence(candles)
        return confidences


# ── contract-compliant home: the OBSERVATION-emitting interpreter ─────────────
# Imported lazily-safe: BaseInterpreter pulls config_layer.crt_engine_v2 (Candle/Direction),
# so keep this import at module scope but the class lightweight.
from interpreters.contract import (  # noqa: E402
    BaseInterpreter,
    EventKind,
    InterpreterEvent,
)


class RegimeObserver(BaseInterpreter):
    """A non-directional volatility-regime sensor (Interpreter Contract, Schema 1.0).

    Emits one `OBSERVATION` event per reading carrying the current regime in `meta`
    (OPAQUE telemetry — never a decision input downstream). `direction=None` ⇒ the
    adapter correctly skips it for trade generation; it is context for fusion.

    `_observe` treats the supplied `window` as the trailing window (it does not reach
    outside it), so the contract's no-lookahead guarantee holds. `confidence` reflects
    whether the window was long enough to classify; `strength` is the within-window
    position of the current ATR (a powerfulness proxy), both clamped to [0,1]."""

    name = "regime_observer"
    family = "observation"
    economic_rationale = (
        "volatility regime is persistent (H_atr>0.5); a non-directional context reading "
        "for fusion/conditioning — earns no trade authority on its own"
    )

    def __init__(self, atr_period: int = 14, tercile_window: int = 480):
        self._labeler = RegimeLabeler(atr_period=atr_period, tercile_window=tercile_window)

    def _observe(self, window, features, ctx):
        bars = list(window)
        atrs = self._labeler._trailing_atr(bars)
        if atrs.size == 0 or not np.any(atrs > 0.0):
            ev = InterpreterEvent(kind=EventKind.OBSERVATION, confidence=0.0, strength=0.0,
                                  meta={"regime": "UNKNOWN"})
            return [ev], 0.0
        av = float(atrs[-1])
        pos_atrs = atrs[atrs > 0.0]
        lo = float(np.percentile(pos_atrs, _LOW_PCT))
        hi = float(np.percentile(pos_atrs, _HIGH_PCT))
        regime = "C" if av <= lo else ("N" if av <= hi else "E")
        span = max(float(pos_atrs.max()) - float(pos_atrs.min()), 1e-12)
        strength = min(1.0, max(0.0, (av - float(pos_atrs.min())) / span))
        # Confidence: full only once the configured trailing window is available.
        confidence = 1.0 if atrs.size >= self._labeler.tercile_window else 0.5
        ev = InterpreterEvent(kind=EventKind.OBSERVATION, confidence=confidence,
                              strength=strength, meta={"regime": regime})
        return [ev], confidence

    def explain(self) -> dict:
        return {
            "observation": "volatility-regime classification (C/N/E) from trailing ATR terciles",
            "reasoning": "non-directional; trailing-window only (no global-rank lookahead)",
            "unknowns": ["whether the regime is economically consumable by a directional strategy"],
        }
