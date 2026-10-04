"""features.smc — CH-htfcrt-parent-candle-smc-v1 (2026-08-15, user-authorized): the 9 SMC
(smart-money-concepts) primitives absent from the codebase before this program (order block,
fair value gap, breaker block, mitigation block, previous-day high/low, equal highs/lows,
change of character).

ISOLATION: pure geometry, window-bounded, no spine import, no config reads at import time —
the same discipline `research.weekly_sweep.weekly_range` established. Each submodule exposes
one deterministic `compute_*(window, ...) -> float` scalar function, consumed by
`features.feature_pipeline`'s `compute_smc_*` steps (Phase 3 vector wiring) but independently
testable and usable without the pipeline.

Every distance-type scalar follows the same convention as the repo's existing `liquidity_distance`
(FM-025): ATR-normalized, signed, tanh-bounded to keep the value finite when a zone is very far
away, and exactly `0.0` when no qualifying structure exists yet (never NaN, never a fabricated
"no data" sentinel that could be confused with a genuine zero-distance reading).
"""

from __future__ import annotations
