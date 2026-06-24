# Topic: Portfolio Allocation

> **Topic-visibility unit.** Capital sizing across instruments — exposure tracking, cross-instrument
> correlation, and the risk-sizing policy. Fully built + tested, but **orthogonal** to the per-candle
> live decision path (it belongs to the multi-signal ExecutionLoop, which is itself dormant).
>
> Created: 2026-06-05 · Updated: 2026-06-05 · Status: living

## In plain language
When you trade several instruments, you can't size each in isolation — total exposure and correlation
matter (two correlated longs are really one bigger bet). This package decides **how much capital** a
signal gets: it tracks open exposure, estimates correlation to existing positions, and applies a risk
policy (base risk, trimmed for high exposure/correlation, boosted for strong signals, hard-capped).
Note: the live one-candle path uses `UltronRiskGate`'s own sizing — this allocator runs in the
multi-signal ranking loop, which is not currently wired in.

## Code covered
- [`src/portfolio/allocator.py:12`](../../src/portfolio/allocator.py) — `PortfolioAllocator` — orchestrator; `allocate()` at :49 → `{action: ALLOCATE|REJECT, risk, reason}`.
- [`src/portfolio/exposure_tracker.py:9`](../../src/portfolio/exposure_tracker.py) — `ExposureTracker` — open positions + `total_risk()` at :48.
- [`src/portfolio/correlation_engine.py:44`](../../src/portfolio/correlation_engine.py) — `CorrelationEngine` — `correlation()` at :98 (20-day Pearson primary; static-heuristic fallback).
- [`src/portfolio/capital_policy.py:11`](../../src/portfolio/capital_policy.py) — `CapitalPolicy` — `compute_risk()` at :60 (exposure/correlation/confidence → risk fraction, hard-capped).

## Ins / Outs
- **Ins:** a signal dict (`symbol`, `confidence`, optional `rr`/`regime`) + current exposure state; config `get_prod_section("portfolio")` (`capital_policy`, `correlation` lookback/cache).
- **Outs:** an allocation decision `{action, risk, reason}`; exposure-tracker mutations on open/close; integrity events when correlation data is missing/stale.

## Entry points & validations
- **Reached via:** `src/execution/loop.py` (`ExecutionLoop` injects the allocator) — the batch rank-and-allocate workflow. **Not** called from `runtime.live_engine_hook` (the per-candle path).
- **Validated by:** sequential gates (portfolio-capacity → correlation → policy → trim-to-cap); `test_portfolio_allocator.py` (25 tests) covers all four sub-modules.

## Tests
- [`tests/test_portfolio_allocator.py`](../../tests/test_portfolio_allocator.py) — ExposureTracker, CorrelationEngine (groups/majors/fallback), CapitalPolicy (reductions/cap), PortfolioAllocator (ALLOCATE/REJECT/trim).

## Fits in architecture
A risk-layer sibling to [`ultron-risk-gate.md`](ultron-risk-gate.md): Ultron is the *live per-trade*
authority; PortfolioAllocator is *multi-signal capital allocation* for the (dormant) ExecutionLoop
([`execution-loop.md`](execution-loop.md)). Orthogonal to the live `EngineRunner → … → Ultron` spine.

## Discussion (filled in-session)
- **Risks:** 2026-06-05 — fully built + tested but **not on the live decision path**; don't assume portfolio-level risk limits are enforced live (Ultron does its own, independently).
- **Ambiguities:** 2026-06-05 — `CorrelationEngine`'s rolling-Pearson primary path needs a data fetcher not present in the live process, so the static heuristic is what actually runs.
- **Reconciled:** 2026-06-05 — `CorrelationEngine` is **IMPLEMENTED** (rolling Pearson + fallback), but this whole allocator path is **ORPHANED** from the live spine (finding **F-013**): portfolio risk limits are not enforced on the live per-candle path. See `analysis/intent-vs-code-reconciliation-2026-06-05.md` items 2 + 6.
