# Close the two residual gaps in the feature-pipeline config migration

## Context

The Phase-A/Phase-B `feature_pipeline` config migration (2026-07-18/19) is
substantially complete: 40 keys in `configs/production/v2_multi_2026_04.json`
under a three-tier risk taxonomy, strict `_require_fp_cfg()` enforcement (no
silent defaults), ontology formula strings synced with `<feature_pipeline.X>`
placeholders + `config_key`/`config_keys` fields, and `swing_window` made
config-derived via a PEP 562 lazy module attribute that preserves the nine
existing `from features.feature_pipeline import SWING_WINDOW` call sites
without creating a `features -> config_layer` import cycle.

A source walkthrough found two residuals. Neither causes divergence *today*
(both current values happen to equal the config values), but both are latent
split-brains of exactly the class §6.5's hard rule exists to eliminate.

## Gap 1 — `double_sweep_window` is not threaded to the live path (T-7)

`src/core/feature_store.py:141` calls `causal_structure_at_bar(...)` with only
`liquidity_sweep_history`, so live falls back to the module default
`_DOUBLE_SWEEP_WINDOW_DEFAULT = 5`. Batch uses
`self._fp_cfg["double_sweep_window"]` (`feature_pipeline.py:800`). The pipeline
already carries a comment admitting this (lines 793-800).

Config is currently `5`, so batch == live. Changing the config moves batch only.

**Fix:** resolve the value from config at the `feature_store.py` call site and
pass it through, mirroring how `causal_structure._resolve_k` handles
`swing_window` — a deferred function-local import, `None` meaning "resolve from
config". Prefer adding a `_resolve_double_sweep_window(w: int | None) -> int`
helper in `causal_structure.py` and defaulting the parameter to `None`, so the
resolution rule lives in one module rather than being duplicated at each caller.
Keep the explicit-arg-wins semantics.

Then delete the now-stale `feature_pipeline.py:793-800` comment.

## Gap 2 — hardcoded `swing_window` provenance literal in the census

`resolve_swing_window()`'s docstring states the provenance rule: every
governance/certification script recording a `swing_window` fact MUST resolve it
through that function, never re-declare the literal — so an artifact can never
assert a value the pipeline did not use.

`scripts/analysis/feature_38_lineage_census.py` violates it in the `swing_high`
and `swing_low` entries (lines ~275, ~278, ~286, ~289):
- `"formula": "... k=SWING_WINDOW=2"`
- `"impl_refs": [..., "SWING_WINDOW=2"]`

**Fix:** import `SWING_WINDOW` from `features.feature_pipeline` (the PEP 562
attribute already returns the config value) and interpolate it, matching the
pattern the other 8 script call sites already use — e.g.
`scripts/analysis/phase1_run1_feature_truth.py:480` builds its formula string
with an f-string over the imported symbol. The remaining 8 call sites are
already correct and need no change.

## Files to modify

- `src/core/feature_store.py` (call site, ~line 141)
- `src/features/causal_structure.py` (add `_resolve_double_sweep_window`, change
  `double_sweep_window` default to `None` on both public functions)
- `src/features/feature_pipeline.py` (remove stale comment, lines 793-800)
- `scripts/analysis/feature_38_lineage_census.py` (4 literal sites)

## Verification

1. **Parity floor (the decisive check):** `pytest tests/test_fc1a_swing_causal.py`
   — `test_fc1a_swing_causal.py:296-302` already compares the live
   `causal_structure_at_bar` output against the batch binding. This is the test
   that would catch a bad thread-through.
2. `pytest tests/test_feature_pipeline.py tests/test_candle_math.py tests/test_formula_registry.py tests/test_feature_dag_structural_certification.py`
   — the last one contains `test_double_sweep_window_boundary_semantics`.
3. `pytest tests/test_behavior_census.py` — pins per-module config maturity so a
   knob cannot drift back into code.
4. **Divergence proof (the point of the exercise):** temporarily set
   `feature_pipeline.double_sweep_window` to `3` in a scratch config copy,
   confirm batch AND live both move together, then revert. Before the fix only
   batch moves. Do not commit the scratch config.
5. Re-run the census: `python scripts/analysis/feature_38_lineage_census.py` and
   confirm the emitted artifact reports `k=2` sourced from config rather than a
   baked literal.

## Notes / non-goals

- **`src/features/causal_structure.py` is currently untracked (`??` in git
  status)** despite carrying the FC1-A contract that both the parity tests and
  the live `FeatureStore` depend on. Worth committing before any branch
  operation. Flagging, not acting on it, without your say-so.
- Hash-neutral: no `params`-block edit, so no `_compute_hash.py` re-run needed.
- `PRODUCTION_BEHAVIOR_CHANGED = NO` — config values equal current effective
  values byte-for-byte; this closes a latent divergence, it does not change
  today's output. Ledger must stay byte-identical.
- Grants no authority (§6.5): threading a knob to live is tunability, not
  evidence. No promotion, no re-certification implied.
