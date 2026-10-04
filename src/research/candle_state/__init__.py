"""candle_state — non-directional candle-state encoding + multi-timeframe conjunction.

Additive research layer (Program 4b/4c/4d). Builds ON TOP of the frozen research kernel
(`HypothesisRunner`, `forward_walk`, `EdgeAggregator`, `QualificationGate`); it never edits
them. The pieces here supply only what the kernel lacks for the transition frontier:

  * `encoder.CandleStateEncoder` — a candle window -> discrete state vocabulary + features.
  * `mtf_conjunction.MultiTFConjunctionBuilder` — M15 window -> {M15,H1,H4} conjunction key
    (resampled via `research.resample`; only CLOSED higher-timeframe candles are visible, so
    no-lookahead is structural).
  * `transition_target` — non-directional forward target labelers (vol/range expansion,
    state persistence, regime transition) for the Stage-1 information gate.
  * `info_robustness` — Stage-1 robustness kernels (MI stability, cross-market, half-life).
  * `reporting` — reporting-ONLY metrics (streak, rolling-10, win-rate); never feed the gate.

Pure & deterministic: numpy + stdlib, no wall-clock, no spine import, no config writes.
"""

from __future__ import annotations
