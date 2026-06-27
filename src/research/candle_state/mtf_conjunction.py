"""mtf_conjunction.py — MultiTFConjunctionBuilder: M15 window -> {M15,H1,H4} state key.

The genuinely-untested frontier: does the SIMULTANEOUS conjunction of the M15 state AND the
last-closed H1 state AND the last-closed H4 state carry information a single timeframe does not?

NO-LOOKAHEAD IS STRUCTURAL (not asserted, guaranteed by construction):
  * `detect()` already hands us only `window` = bars up to & including the current M15 bar.
  * `research.resample` emits a higher-timeframe bucket ONLY when the first child of the NEXT
    bucket arrives, and drops the trailing in-progress bucket unconditionally. The current M15
    bar lives in the in-progress H1/H4 bucket, so that bucket is dropped — the last emitted H1/H4
    candle is the most recent FULLY-CLOSED hour/4-hour, whose close is already known. We can never
    see a not-yet-closed higher-timeframe bar.

Pure & deterministic: reuses `research.resample.resample` + `CandleStateEncoder` verbatim; no
config, no I/O, no spine import.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from research.candle_state.encoder import CandleState, CandleStateEncoder
from research.resample import _RULE_HOURS, _bucket_start, resample

_MISSING = "NA"   # token used when a timeframe has no closed candle yet (warmup)


@dataclass(frozen=True)
class Conjunction:
    """The multi-timeframe state at the current M15 bar. `key` is the deterministic
    conjunction label used as the partition cell in the Stage-1 information gate."""

    m15: CandleState
    h1: CandleState | None
    h4: CandleState | None
    key: str


class MultiTFConjunctionBuilder:
    """Build the {M15,H1,H4} conjunction from an M15 window. One reusable instance.

    `htf_window` caps how many trailing HTF candles are fed to the encoder (enough for its
    ATR/SMA periods); keeping it bounded makes per-bar resampling cheap on long series.
    """

    def __init__(
        self,
        encoder: CandleStateEncoder | None = None,
        *,
        rules: Sequence[str] = ("H1", "H4"),
        htf_window: int = 60,
    ):
        self.encoder = encoder or CandleStateEncoder()
        self.rules = tuple(rules)
        self.htf_window = htf_window

    def _htf_state(self, m15_window: list, rule: str) -> CandleState | None:
        htf = resample(m15_window, rule)        # CLOSED buckets only (trailing dropped)
        if not htf:
            return None
        return self.encoder.encode(htf[-self.htf_window:])

    def build(self, m15_window: Sequence) -> Conjunction:
        bars = list(m15_window)
        if not bars:
            raise ValueError("MultiTFConjunctionBuilder.build: empty window")
        m15_state = self.encoder.encode(bars)
        states: dict[str, CandleState | None] = {}
        for rule in self.rules:
            states[rule] = self._htf_state(bars, rule)

        parts = [f"M15={m15_state.token()}"]
        for rule in self.rules:
            st = states.get(rule)
            parts.append(f"{rule}={st.token() if st is not None else _MISSING}")
        key = "|".join(parts)

        return Conjunction(
            m15=m15_state,
            h1=states.get("H1"),
            h4=states.get("H4"),
            key=key,
        )

    # -- efficient whole-series conjunction keys ------------------------------
    def key_series(self, m15_candles: Sequence) -> list[str]:
        """Per-bar conjunction `key` for an entire M15 series in O(n log n).

        Equivalent to calling `build(candles[:t+1]).key` for every t, but it resamples each
        higher timeframe ONCE and maps each M15 bar to its last CLOSED HTF bucket by timestamp
        (the bucket strictly before the in-progress one — exactly what `build` drops). Verified
        against `build` in tests. Used by the Stage-1 driver on long (~70k-bar) series.
        """
        import bisect

        bars = list(m15_candles)
        n = len(bars)
        # Trailing M15 encoder state per bar (incremental window slice; matches encode()).
        # `win` is the MINIMAL trailing length that makes the capped slice byte-identical to the
        # full-prefix encode (encode internally slices to each indicator's own lookback).
        enc = self.encoder
        m15_tokens: list[str] = []
        win = max(enc.atr_period + 1, enc.sma_period, enc.volume_window, enc.lookback + 1)
        for t in range(n):
            lo = max(0, t - win + 1)
            m15_tokens.append(self.encoder.encode(bars[lo:t + 1]).token())

        # Per-rule: resample once, encode each HTF bar with a trailing window, then for each
        # M15 bar pick the last HTF bucket whose start < floor(current bar, rule).
        htf_tokens: dict[str, list[str]] = {}
        for rule in self.rules:
            htf = resample(bars, rule)
            starts = [c.timestamp for c in htf]
            states = [self.encoder.encode(htf[max(0, i - self.htf_window + 1):i + 1]).token()
                      for i in range(len(htf))]
            col: list[str] = []
            for t in range(n):
                floor_t = _bucket_start(bars[t].timestamp, _RULE_HOURS[rule])
                j = bisect.bisect_left(starts, floor_t) - 1   # last start strictly < floor_t
                col.append(states[j] if j >= 0 else _MISSING)
            htf_tokens[rule] = col

        keys: list[str] = []
        for t in range(n):
            parts = [f"M15={m15_tokens[t]}"]
            for rule in self.rules:
                parts.append(f"{rule}={htf_tokens[rule][t]}")
            keys.append("|".join(parts))
        return keys
