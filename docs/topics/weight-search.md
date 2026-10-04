# Topic: Regime Weight Search

> **Topic-visibility unit.** Offline, LLM-guided search for the best per-regime fusion weights +
> BitNet threshold, validated by backtest with hard guardrails. Produces the weights the live regime
> router then serves.
>
> Created: 2026-06-05 · Updated: 2026-06-05 · Status: living

## In plain language
The live system blends the four engines with **per-regime weights** ([`regime-classifier.md`](regime-classifier.md)).
Where do those weights come from? This searcher finds them: for each regime it summarizes historical
trades, asks an LLM to propose a few weight/threshold candidates, **backtests each**, keeps only those
that don't hurt PnL or drawdown (same guardrails as the expansion engine), and returns the best with an
LLM-written rationale. It's offline tuning — the output feeds the live fusion config, the search itself
never trades.

## Code covered
- [`src/search/regime_weight_searcher.py:36`](../../src/search/regime_weight_searcher.py) — `RegimeWeightSearcher` — `run()` at :46 iterates regimes; `_search_regime()` at :69 is the per-regime loop.
- [`src/search/regime_weight_searcher.py:249`](../../src/search/regime_weight_searcher.py) — `_suggest_candidates` — LLM proposes weight configs (renormalized; equal-weight fallback).
- [`src/search/regime_weight_searcher.py:373`](../../src/search/regime_weight_searcher.py) — `_mutate_config` — deep-copy + apply candidate weights/threshold (never mutates the base).

## Ins / Outs
- **Ins:** base config + `csv_paths` + an LLM chat fn + a backtest runner + evaluator; guardrails reused from `expansion.policy_schema` (`MIN_PNL_RATIO`, `MAX_DRAWDOWN_RATIO`, `PARAM_BOUNDS`).
- **Outs:** `List[RegimeSearchResult]` (best candidate + improvement % + insights per regime); audit lines to `logs/regime_search.jsonl`. Final weights are intended for the production `fusion_engine` / `regime_map`.

## Entry points & validations
- **Reached via:** offline tuner flow (e.g. `scripts/training/auto_tuner_multi.py`) / programmatic. Requires an LLM service for suggestions + analysis.
- **Validated by:** per-candidate backtest + PnL/drawdown guardrails before acceptance; weights renormalized + bounds-clipped. **Gap:** no dedicated test file (see Discussion).

## Tests
- _None yet_ — `tests/test_regime_weight_searcher.py` does not exist. `tests/test_regime_classifier.py` covers the *consumer* (router), not this searcher.

## Fits in architecture
The offline producer of the per-regime weights that [`regime-classifier.md`](regime-classifier.md) +
[`fusion-decision.md`](fusion-decision.md) consume live. A tuning sibling of
[`expansion-engine.md`](expansion-engine.md) (shares its guardrail schema).

## Discussion (filled in-session)
- **Blockers:** 2026-06-05 — **untested** (no test file) → a Tier-2 validation gap; LLM-guided (non-deterministic suggestions), so reproducibility hinges on the backtest guardrails, not the LLM.
- **Risks:** 2026-06-05 — output directly shapes live fusion weights; a bad search that passes guardrails could still ship suboptimal weights. Backtest-only validation ⇒ inherits F-010 (live unverified).
