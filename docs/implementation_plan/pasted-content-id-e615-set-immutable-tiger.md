# Candle-pattern observations into the linear feature flow (schema v8.0)

## Context
The user's candle-theory cards (docs/reference/candle_theory/) and the multi-LLM corrected spec define
pin bars, hammer / shooting star, doji variants, engulfing, inside bar, compression and rejection
intensity. None exist in the repo: `is_inside_bar` is a hard-coded `False` (`src/governance/strategy_backtest.py:315`)
and `rejection_wick` is "upper wick ≠ 0" (`:314`), both read by S02/S05. The user directs: adopt the corrected
designs, no separate decisions, no parity requirement (early stage, existing results may move), align them in
the system's linear flow, and don't break the system (green floor = the 8 pre-existing reds only).

Linear flow being built:
`OHLC → candle anatomy (candle_math) → normalized geometry → pattern observations → canonical vector
(FeaturePipeline) → live/backtest feature dicts → consumers (S02/S05 now; CRT/context later) → outcome measurement`.

## Resolved design choices (recommendations adopted, per user)
1. **ATR** = the canonical ATR in price units: `atr * close` (FM-074 `atr_absolute`, == `atr_14_raw`, SMA14 of TR).
   No second ATR definition.
2. **Size gate** `G = range>0 ∧ range ≥ k·ATR_abs`, `k` from config (default 0.5); applied to single-bar
   patterns + continuous intensities only, not engulfing / inside bar.
3. **Inclusive** comparisons (`<=`/`>=`) everywhere the spec says so; `body > body_prev` kept for engulfing.
4. **Names** from the corrected spec: `pin_lower`, `pin_upper`, `hammer`, `shooting_star`, `doji_material`,
   `dragonfly_doji`, `gravestone_doji`, `engulfing_bull`, `engulfing_bear`, `inside_bar`.
5. **Hammer / star** = wick geometry + at-or-beyond prior 5-bar extreme (current bar excluded); no trend condition.
6. **Gap guard**: two-bar patterns (engulfing, inside_bar, compression_ratio) are 0/neutral when the previous row
   is not the immediately preceding bar (timestamp diff ≠ frame's modal bar interval). 516 such gaps on XAUUSD M15.
7. **Placement**: into the canonical vector (schema 7.0 → 8.0, slots 0–53 unchanged, appended).
8. **S02/S05**: wire the dead fields to real producers.
9. Zero-range bars: ratios 0, gate false (no epsilon). Warmup: NaN-safe (first bar / first 5 bars → flags 0).

## New canonical slots 54–69 (16, all float32; flags 0/1)
| idx | name | definition |
|---|---|---|
| 54 | `upper_wick_ratio` | Û = U/R (0 if R=0) |
| 55 | `lower_wick_ratio` | D̂ = D/R (body share already = `body_ratio`) |
| 56 | `pin_lower` | D̂≥0.60 ∧ B̂≤0.25 ∧ Û≤0.15 ∧ G |
| 57 | `pin_upper` | Û≥0.60 ∧ B̂≤0.25 ∧ D̂≤0.15 ∧ G |
| 58 | `hammer` | D≥2B ∧ Û≤0.10 ∧ L ≤ min(L[i-5..i-1]) ∧ G |
| 59 | `shooting_star` | U≥2B ∧ D̂≤0.10 ∧ H ≥ max(H[i-5..i-1]) ∧ G |
| 60 | `doji_material` | B̂≤0.10 ∧ |Û−D̂|≤0.20 ∧ G |
| 61 | `dragonfly_doji` | B̂≤0.05 ∧ D̂≥0.75 ∧ G |
| 62 | `gravestone_doji` | B̂≤0.05 ∧ Û≥0.75 ∧ G |
| 63 | `engulfing_bull` | prev bear ∧ cur bull ∧ O≤C₋₁ ∧ C≥O₋₁ ∧ B>B₋₁ ∧ contiguous |
| 64 | `engulfing_bear` | mirror |
| 65 | `inside_bar` | H≤H₋₁ ∧ L≥L₋₁ ∧ contiguous |
| 66 | `compression_ratio` | R/R₋₁ (1.0 if R₋₁=0 or not contiguous), clipped [0,10] for the vector |
| 67 | `rejection_intensity_signed` | G ? clip(D̂−Û,−1,1) : 0 |
| 68 | `rejection_intensity_lower` | G ? clip(D̂−B̂,0,1) : 0 |
| 69 | `engulfing_strength` | engulf ? min(B/B₋₁,3) : 0 (B₋₁>0 guaranteed by the pattern) |
`rejection_intensity_upper` is the mirror of 68 — include as slot 70 → **CANONICAL_FEATURE_DIM = 71** (17 new).
All thresholds (0.60/0.25/0.15/2.0/0.10/0.20/0.05/0.75/k/lookback 5/caps 3,10) live in config.

## Implementation (one change id `CH-candle-pattern-observations-v8`, same path as CH-feature-semantic-fixes-v7)
1. **Ontology first** — `configs/formulas/market_ontology.yaml`: FM-103..FM-119 (17 entries, `vector_index` 54–70,
   `depends_on` OHLC / FM-074 / prior-bar), `primitives` stays flat (§6.6 constraint). Representation entries in
   `configs/formulas/representation_registry/feature_pipeline.yaml` (concept ids grounded via
   `query_semantic_os.py --ground --kind CONCEPT`; add concept contracts if absent, side in encoding).
2. **Math** — new `src/features/candle_patterns.py`: vectorized pure functions on numpy arrays
   (`wick_ratios`, `size_gate`, `pin_flags`, `probe_flags`, `doji_flags`, `engulfing`, `inside_bar`,
   `compression_ratio`, `rejection_intensities`, `contiguous_mask`), reusing `candle_math` identities for
   U/D/B/R; scalar twins for live parity live in the same module. Register in
   `src/features/registry/derived_registry.py` + `fm_resolve` (as FM-096..102 were).
3. **Config** — `feature_pipeline.candle_patterns` block (all thresholds, `size_gate_k`, `swing_lookback`,
   caps) on all 12 configs carrying `feature_pipeline`; strict read via `_require_fp_cfg`
   (`feature_pipeline.py:220`), hash-neutral (not `params`).
4. **Pipeline** — `FeaturePipeline.compute_candle_patterns()` after `compute_canonical_volatility_features`
   (needs `atr`) and before `compute_smc_features`; call in `run()` (`feature_pipeline.py:1522`).
5. **Schema** — `src/features/feature_schema.py`: append 17 names, DIM 71, `SCHEMA_VERSION="8.0"`;
   `src/identity/tokens.py` (`SCHEMA_VERSIONS`, `SCHEMA_DIM["8.0"]=71`); `schema_version_registry.json`;
   `_V5_ONLY_FEATURES` exclusions in `research/model_runners/schema_resolver.py` and `research/clean_labels/builder.py`;
   `_NODES` in `scripts/analysis/feature_dag_layers.py`; live required-key lists
   (`runtime/live_engine_hook.py` `_req`, `features/crt_feature_builder.py` `_require`).
6. **Consumers** — `strategy_backtest.py:314-315`: `rejection_wick = pin_lower or pin_upper or hammer or shooting_star`,
   `is_inside_bar = inside_bar`; same mapping wherever the live strategy dict is built (grep `rejection_wick`),
   and `uat_runner.py:460` fixture stays as-is. S02/S05 logic unchanged.
7. **Governance** — impact + completion manifests; freeze pin regenerated with waiver entry; finding **F-118**
   (+ CLAUDE.md row, `data/findings.jsonl` export); `active_models.yaml` slots; `docs/reference/schemas.md`,
   `docs/topics/feature-schema.md`; candle_theory README rows point at the new FM ids; reachability golden
   regenerated; tests updated 54→71 where pinned; SESSION LOG. No commit unless asked.

## Verification
1. New `tests/test_candle_patterns.py`: synthetic bars for every pattern (positive + the boundary/equality case +
   zero-range + gap + first-bar), Û+D̂+B̂=1, vector↔scalar parity, gate uses `atr*close`.
2. Full XAUUSD corpus: per-pattern fire counts, slots 0–53 bit-identical to the v7 vector, no NaN/inf in 54–70,
   inside_bar never across a gap.
3. Backtest before/after (active config): report the diff (S02/S05 confidence moves expected; CRT spine unchanged).
4. Floors: formula registry / lineage / pipeline / freeze / schema registry / semantic + representation registry /
   feature_math_lint / findings; then `check_governance_invariants.py --all` = only the 8 pre-existing reds.
5. `construction_protocol.py validate-completion` on the manifest (BLOCKED only by other sessions' WIP is acceptable, recorded).
6. Artifact: add a pattern row/markers to the XAUUSD page (follow-up).
