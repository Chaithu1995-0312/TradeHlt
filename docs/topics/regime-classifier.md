# Topic: Regime Classifier

> **Topic-visibility unit.** The deterministic market-regime detector and the config/weight router it
> drives — it runs *before* the engines on the live path and tells fusion which weight profile to use.
>
> Created: 2026-06-05 · Updated: 2026-06-05 · Status: living

## In plain language
Markets behave differently when trending vs ranging vs wildly volatile. Before scoring a candle, the
system classifies the current **regime** (`TRENDING` / `RANGING` / `HIGH_VOLATILITY`) from ATR + trend
features, then a **router** picks the matching fusion-weight profile so the four engines are blended
differently per regime. It's deterministic (same inputs → same regime), has a cooldown so it can't
flip every candle, and always falls back to `RANGING` on error.

## Code covered
- [`src/regime/regime_classifier.py:25`](../../src/regime/regime_classifier.py) — `RegimeClassifier` — deterministic detector; `classify()` at :58 returns the regime string; 5-candle switch cooldown.
- [`src/regime/config_router.py:43`](../../src/regime/config_router.py) — `ConfigRouter` — regime → profile (SAFE/BALANCED/AGGRESSIVE); `get_fusion_weights()` at :150 returns per-regime fusion weights.

## Ins / Outs
- **Ins:** feature dict (`atr`, `trend_score`, optional `volatility`/`adx`); router loads `configs/production/regime_map.json` (or hardcoded defaults).
- **Outs:** a regime string + a fusion-weight dict injected into the engine context; consumed by `FusionEngine.compute(regime=…)` to select per-regime weights.

## Entry points & validations
- **Reached via:** the live path — `runtime.live_engine_hook` lazily builds the classifier (`_get_regime_classifier`) and calls `classify()` per candle *before* `EngineRunner`, injecting `get_fusion_weights(regime)` into context.
- **Validated by:** deterministic classification + `RANGING` exception fallback; cooldown guard; `test_regime_classifier.py` covers detection, cooldown, and routing.

## Tests
- [`tests/test_regime_classifier.py`](../../tests/test_regime_classifier.py) — regime detection (each class), cooldown guard, custom thresholds, exception → RANGING, ConfigRouter profile routing + unknown→SAFE.

## Fits in architecture
Sits at the front of the scoring stage ([`signal-flow.md`](../architecture/signal-flow.md)) feeding
[`fusion-decision.md`](fusion-decision.md) (regime-aware weights) and [`scoring-engines.md`](scoring-engines.md).
Live-wired via `live_engine_hook`.

## Discussion (filled in-session)
- **Risks:** 2026-06-05 — regime drives weight blending but the *re-tuning* of those weights is offline (see [`search`](../topics/readme.md)); `update_regime_weights`/`save_map` exist but aren't called in the live path.
- **Ambiguities:** 2026-06-05 — regime thresholds are config-set; confirm `regime_map.json` matches the active production config's intent.
- **Reconciled:** 2026-06-05 — verdict **IMPLEMENTED** (regime re-detected in `engine_runner.py:765`, fusion call at `engine_runner.py:777`, weights applied in `fusion_engine.py:290`); `integration-audit.md`'s "never injected" is stale. The live `context["fusion_weights"]` injection (`live_engine_hook.py:659`) is an unread/orphaned path. See `analysis/intent-vs-code-reconciliation-2026-06-05.md` item 1.
