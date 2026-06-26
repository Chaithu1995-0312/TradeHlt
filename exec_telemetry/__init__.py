"""
exec_telemetry — the Execution Quality Observatory (Phase C-op).

A small, read-only layer that characterizes **execution truth** — requested-vs-filled price
(slippage), send→fill latency, and retcode/failure mode — facts that live ONLY at `order_send`
and are permanently unknowable from reconstructed deals. This is the sibling of `mt5_analytics`
(financial truth); the two are kept separate on purpose.

DOCTRINE (OPERATIONAL-ONLY): this layer measures latency / slippage / retcodes / fills — NEVER
profit, expectancy, win-rate, or R (those belong to the truth + insight engines). Conflating
execution robustness with strategy robustness is the prohibited error. Read-model invariant:
`execution telemetry → HUMAN`, never `→ execution decisions`.
"""
