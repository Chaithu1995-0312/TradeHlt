# GD-004 / GD-005 `disp_strength` identity closure — 2026-07-11

Micro-phase executing backlog item **FU-SCORING-DISP** (the one formula collision directly
connected to the Phase-1 identity family), per the post-Phase-1 critical review. Identity-only:
**zero behavior change** (byte-identical routing), hash-neutral, no model artifacts, no economic
claims. Change id: `CH-gd004-gd005-disp-strength-closure`.

## Adjudication

### GD-004 — `scoring_engine.compute_scores` local `disp_strength = move/atr`

**Verdict: a genuinely NEW third identity → registered as FM-029 `disp_strength_atr_rescale`.**

- Site: `src/engines/scoring_engine.py` (`compute_scores`), sole caller
  `src/engines/crt_engine.py:23` passes `move = features["disp_strength"]` — the pipeline
  **FM-020** value (`body/(atr·close)`, clipped [0,3]) — and `atr = features["atr"]` (the
  close-relative pipeline ATR; `"atr"` is CANONICAL_FEATURES index 13, so the
  `setdefault("atr", engine.state.atr)` at `backtest_v2.py:2141` never fires).
- So the as-wired quantity is `FM-020 / atr_rel == body_size·close / atr_14_raw²` — **not**
  FM-028 (`candle_range/atr`), **not** FM-020.
- Probe (`docs/governance/gd004_disp_rescale_probe-2026-07-11.json`, BNBUSDT 29,922 bars,
  read-only):
  - ATR-unit assumption verified: pipeline `atr` == `atr_14_raw/close` on **100.0%** of
    checkable bars.
  - equals FM-020 on **2.08%** of bars (only the zero-displacement bars where both are 0),
    equals FM-028 on **0.00%** → third identity confirmed.
  - Characterization: the as-wired value saturates `s_breakout`'s `min(x/2, 1)` at 1.0 on
    **97.5%** of bars — the displacement term of `s_breakout` carries near-zero information
    as wired. (Descriptive only; impact bounded: backtests run gate-OFF per F-037, `run()`
    never executes per F-048.)
- **Deferred (FU-CRT-MOVE-MISWIRE):** the signature (`move`, `atr`) suggests a raw price move
  (FM-028-like input) was plausibly intended; `crt_engine.py:23` feeding FM-020 instead is a
  suspected call-site mis-wire. Fixing it CHANGES gate-ON fusion behavior → out of
  identity-closure scope (user decision 2026-07-11: identity-only). HYPOTHESIS status, queued
  for the post-PIT behavior phase.

### GD-005 — `crt_engine_v2` [PATCH 7] `_disp_strength = wick_size/atr`

**Verdict: EXACTLY FM-028 `displacement_atr_ratio` (already registered).**

- CRT `Candle.wick_size` ≡ `candle_range` (F-046); FM-028's `source_of_truth` already cites
  this site family (`crt_engine_v2.py:1355`).
- Routed through `derived_math.displacement_atr_ratio`, local renamed
  `_displacement_atr_ratio`. Behavior-identical: the site only computes when `atr > 0`,
  matching the impl's `atr<=0 → 0.0` convention.

## Changes shipped

1. `configs/formulas/market_ontology.yaml`: FM-029 registered (`derived_metrics`); FM-020 note
   updated (collision closed).
2. `src/features/derived_math.py`: `disp_strength_atr_rescale` scalar (verbatim as-wired math).
3. `src/features/registry/derived_registry.py`: impl registered.
4. `src/engines/scoring_engine.py`: GD-004 site routed through the registry, local renamed.
5. `src/config_layer/crt_engine_v2.py`: GD-005 site routed through FM-028, local renamed.
6. `scripts/analysis/feature_math_lint.py`: GD-004/GD-005 pins removed;
   `docs/governance/feature-math-grandfather-retirements.json`: two retirement entries
   (durable_keys `1405f7559de41144` / `206cdd6e726430d1` gone from scan). **No `disp_strength`
   pin remains → bare `disp_strength` derivation in the scanned live surface is now a hard
   lint failure.**
7. Geometry census + Gate-2B adjudication regenerated per the construction protocol
   (110→117 governed / 117 adjudicated / 0 missing) — absorbs the pre-existing Phase-1
   staleness (volume-proxy split, live-hook routed calls, FM-013 impl, probe/test sites) plus
   this change's delta; `tests/test_gate5_lineage_report.py` denominator updated with a dated
   addendum in `geometry_static_lineage_report.md`.
8. Tests: `tests/test_gd004_gd005_identity_closure.py` (272 parity/registration cases —
   scalar parity vs old inline math incl. guard edges, `compute_scores` output identity vs
   OLD-formula expected values, registry dispatch, FM-029 ontology registration, three-way
   identity distinctness).

## Out of scope (unchanged)

- `crt_engine.py:23` mis-wire (FU-CRT-MOVE-MISWIRE, new backlog id).
- PIT phases A/B/C; model lineage; any economic claim.
- Pre-existing branch failure `tests/test_reachability_golden.py::test_registry_summary_matches_golden`
  (zone registry summary vs golden — unrelated to feature math; reproduced with this change
  fully stashed).
