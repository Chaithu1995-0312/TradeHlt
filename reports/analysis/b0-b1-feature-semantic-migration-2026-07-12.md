# B0/B1 — Feature Semantic-Migration Governance + Base Identity Remediation

**Date:** 2026-07-12
**Targets:** `ema_spread`, `momentum_score`, `atr`, `rsi_14`, `wick_size`
**Scope:** B0 (migration governance) + B1 (base identity remediation). No Market Reality runtime.

---

## 1. Executive conclusion

All five findings (F1–F5) were **independently reproduced** from the current working tree. The
consumer census + trained-artifact inspection prove that **none of the five formulas can be safely
changed in this task**:

- `ema_spread` / `momentum_score` have a **real dimensional defect** (scale with price level), but are
  consumed by **active, threshold-calibrated runtime code** (`engine_runner.detect_regime` /
  `breakout_engine`, the active heuristic Gaussian) **and** by **inactive trained artifacts**
  (`rr_model.json` 38-vec idx 9/12; 38-dim Gaussian variants). Correcting the math would change
  live+backtest behavior **and** silently poison the legacy artifacts. Retraining + threshold
  recalibration are out of scope → **LEGACY_PRESERVED**, corrected identities registered **inactive**.
- `atr` / `rsi_14` are **internally coherent** (SMA-of-TR close-relative ATR; SMA gain/loss RSI). The
  defect is a **false declaration** (RSI docstring claimed "Standard Wilder formula") → **IDENTITY_CLARIFIED**.
- `wick_size` is the **full candle range** (misnomer). Slot math frozen → **LEGACY_MISNOMER_GOVERNED**.

**The remediation is governance/identity only. No production math changed. `CANONICAL_FEATURE_DIM`
stays 38, order unchanged, `PRODUCTION_BEHAVIOR_CHANGED = NO`.**

## 2. Contamination rule

All prior verdicts (CLOSED/PASS/PIT/finding labels/config comments/test pass counts) were treated as
potentially contaminated. Every finding below was re-reproduced from the current implementation via
fresh runtime probes (a focused pytest suite that imports the real `FeaturePipeline`). Governance
artifacts (`rr_model.provenance.json`, `active_models.yaml`, the ontology) were used only as **indexes
/ declarations**, not as proof; their claims were cross-checked against config values and code.

## 3. Exact files inspected

| File | Role in census |
|---|---|
| `src/features/feature_pipeline.py` | Producer authority: `ema_spread` (:561), `momentum_score` (:567), `atr` (:532/`atr_14_raw`:274), `rsi_14` (:258, SMA), `wick_size` (:514 = high-low). |
| `configs/formulas/market_ontology.yaml` | WHAT-layer formula identity contract (FM-022/023, FM-002; base_inputs `atr`). The authoritative machine-readable identity source. |
| `src/features/derived_math.py`, `registry/derived_registry.py`, `registry/_loader.py`, `formula_registry.py` | Scalar impls + registry dispatch + `validate_registry`/`build_lineage_graph` (3-section iterators). |
| `configs/production/v2_multi_2026_04.json` (active) | Gates: `rr_fusion.enabled=false`, `use_bitnet=false`, `gaussian_impl=heuristic`, `dual_engine.{trend_strength_threshold=0.15, momentum_threshold=0.3}`. |
| `models/rr_model.json` + `.meta.json` + `.provenance.json` | Trained artifact: `n_features=38`, `zero_indices=[0,1,2,3,4,7,8,16,17,26,27]` (idx 9 `ema_spread` and 12 `momentum_score` are **active** non-zero dims); `path_active_on_config=false`. |
| `models/gaussian_registry.json` | 38-dim Gaussian variants (v5_tradenet/v6) embed `ema_spread`/`momentum_score`/`rsi_14`/`wick_size`; not the active impl (heuristic is). |
| `src/engines/rr_engine.py` | Base RREngine = Candle Polarity (close/high/low only); does **not** load `rr_model.json` or read the two features. |
| `src/core/engine_runner.py` (:150-185), `src/engines/heuristic_gaussian_engine.py` (:308), `crt_engine_v2.py` (:1996), `execution_planner.py` (:352), `gate_intelligence.py` (:217) | **Active** code consumers of `ema_spread`/`momentum_score`. |
| `tests/test_feature_lineage.py`, `test_feature_math_lint.py` | Governance guards I had to keep green. |

## 4. Exact commands executed

```
venv/Scripts/python.exe -c "<inspect active config gates: rr_fusion/use_bitnet/gaussian_impl/dual_engine>"
venv/Scripts/python.exe -c "<read models/rr_model.json keys, n_features, zero_indices; rr_model.meta/provenance>"
venv/Scripts/python.exe -c "import features.formula_registry as fr; fr.validate_registry(); fr.build_lineage_graph()"
venv/Scripts/python.exe -m pytest tests/test_b0b1_feature_semantic_migration.py -q          # new suite (14)
venv/Scripts/python.exe -m pytest tests/test_feature_lineage.py tests/test_feature_math_lint.py \
    tests/test_derived_math.py tests/test_candle_math.py tests/test_feature_pipeline.py \
    tests/features/ tests/test_feature_contract_v1.py tests/test_feature_dependency_graph_fc05.py -q
```
Grep census (`ripgrep`) for `ema_spread|momentum_score|wick_size|rsi_14|atr` across `src/` and
`"(ema_spread|momentum_score)"` for direct-dict reads.

## 5. Fresh reproduction results (F1–F5)

Reproduced via `tests/test_b0b1_feature_semantic_migration.py` (real `FeaturePipeline` on synthetic
frames at price ×1 and ×100, aligned by timestamp):

| Finding | Reproduced result | Verdict |
|---|---|---|
| **F1 ema_spread** | legacy scales with price: median ratio(×100/×1) = **100.0** | REPRODUCED (defect real) |
| **F2 momentum_score** | legacy scales with price: median ratio = **100.0** | REPRODUCED (defect real) |
| corrected `(ema_fast-ema_slow)/(atr·close)` | scale-**invariant** (max diff < 1e-3) | corrected math confirmed |
| corrected `close_delta/(atr·close)` | scale-**invariant** | corrected math confirmed |
| **F3 atr** | prod `atr_14_raw` vs SMA-TR maxdiff **0.0**; vs Wilder **>1e-3** | REPRODUCED: SMA, not Wilder |
| **F4 rsi_14** | prod `rsi_14` vs SMA-RSI maxdiff **0.0**; vs Wilder **>1.0** | REPRODUCED: SMA, not Wilder |
| **F5 wick_size** | `wick_size == high-low` (all rows); `!= total_wick` on body candles | REPRODUCED: full range, misnomer |

**Findings reproduced = 5. Findings rejected = 0.**

## 6. Consumer-impact census

| Feature | Producer | Active code consumers (calibrated) | Trained-artifact consumers | Runtime reachable? |
|---|---|---|---|---|
| `ema_spread` (idx 9) | `feature_pipeline:561` / `derived_math.ema_spread` | `engine_runner.detect_regime` (vs `trend_strength_threshold=0.15`), `breakout_engine` (vs `breakout_min_score`), `gate_intelligence`, `sl_tp_comparator`, `crt_feature_builder`, strategies s03/07/08 | `rr_model.json` (idx 9, **active** dim) — path **inactive**; Gaussian-38 variants — **inactive** | **YES via active code**; NO via trained artifact |
| `momentum_score` (idx 12) | `feature_pipeline:567` / `derived_math.momentum_score` | `engine_runner.detect_regime`/`breakout_engine` (vs `momentum_threshold=0.3`), **active heuristic Gaussian** (`:308`), `crt_engine_v2:1996`, `execution_planner:352`, `gate_intelligence:217`, `sl_tp_comparator`, strategies s02-s09 | `rr_model.json` (idx 12) — inactive; Gaussian-38 — inactive | **YES via active code** |
| `atr` (idx 13) | `feature_pipeline:274/532` | foundational: every derived metric (`atr*close`), `min_atr` gate, execution planner | `rr_model.json` (idx 13) — inactive | **YES** (foundational) |
| `rsi_14` (idx 15) | `feature_pipeline:258` | vector member; `model_registry` schema list | `rr_model.json` (idx 15) — inactive; Gaussian-38 — inactive | via vector only |
| `wick_size` (idx 27) | `feature_pipeline:514` | `body_ratio` denominator (`body_size/wick_size`), vector member | `rr_model.json` (idx 27 — **in `zero_indices`**, degenerate) | via vector; artifact dim zeroed |

Feature-order slots pinned by test: `ema_spread`=9, `momentum_score`=12, `atr`=13, `rsi_14`=15,
`wick_size`=**27**, `body_ratio`=28 (the pre-probe note that had `wick_size`=28 was **corrected** here
from the live schema). Config dependency: `engine_runner.gaussian_impl=heuristic`,
`rr_fusion.enabled=false`, `use_bitnet=false`. Tests asserting exact values: none on these two features
found; shape/order tests: `test_feature_pipeline`, `test_feature_contract_v1`. Stale/dead consumer:
`crt_feature_builder.py` (0 call sites).

## 7. Trained-artifact compatibility evidence

Inspected metadata, not names:

- `rr_model.json`: `n_features=38`, `zero_indices=[0,1,2,3,4,7,8,16,17,26,27]`. **Indices 9 (`ema_spread`)
  and 12 (`momentum_score`) are NOT zeroed → the model's learned weights depend on the legacy math**;
  idx 27 (`wick_size`) **is** zeroed (degenerate). `n_train=49000`.
- `rr_model.provenance.json`: `"path_active_on_config": false`, operational rule "Must not promote /
  re-enable (rr_fusion) / use as economic evidence without causal re-dataset → retrain". Confirmed
  against config (`rr_fusion.enabled=false`) and code (`rr_engine.py` base engine does not load it).
- `gaussian_registry.json`: 38-dim variants embed the two features; active impl is `heuristic`
  (verified), which reads `ema_fast/ema_slow/momentum_score` heuristically — **not** the 38-dim model.

**Compatibility status = MIXED** (legacy-bound artifacts exist but their runtime paths are inactive;
active code paths are legacy-calibrated). Changing the vector math would silently invalidate both →
**RETRAIN + RECALIBRATION required to ever activate a correction** (out of scope). Not `UNKNOWN` — the
dependency is proven — so no fail-closed BLOCK is triggered for the *governance* remediation.

## 8. Formula identity contract — BEFORE

`configs/formulas/market_ontology.yaml` (WHAT layer, v1.1) already carried per-entry `id`/`version`/
`lifecycle`/`formula`/`impl`/`depends_on`/`source_of_truth`. Gaps: no `units`/`normalization_basis`/
`semantic_version`/`replacement_identity`/`artifact_compatibility`; `atr`/`rsi_14` were **out of scope**
(rolling-indicator boundary freeze) with only a one-line base_input comment; RSI docstring in
`feature_pipeline.py` **falsely claimed Wilder**; `wick_size` governed as `candle_range` (FM-002 alias)
but without an explicit `deprecated_misnomer` status.

## 9. Migration policy

| Class | Applied to | Rule |
|---|---|---|
| `FORMULA_CORRECTION_DEFERRED` | ema_spread, momentum_score | Corrected identity registered (versioned, **inactive**); legacy math preserved; activation gated on retrain + recalibration. |
| `IDENTITY_CLARIFICATION` | atr, rsi_14 | Declaration corrected at authoritative source; runtime math unchanged; full FM-id/parity registration deferred to the boundary-freeze architectural review (B2/B3). |
| `LEGACY_MISNOMER_GOVERNED` | wick_size | Slot math frozen; identity made unmistakable via `semantic_quantity`+`deprecated_misnomer_alias`. |

Hard rules honored: (1) no trained artifact silently receives changed math — no math changed; (2) no
canonical feature silently changes meaning with an indistinguishable version — legacy `semantic_version`
is now explicit and the corrected identity has a distinct id/version; (3) historical reproducibility
preserved (legacy formulas byte-identical, pinned by test); (4) order-compat ≠ formula-compat (documented);
(5) dim-38 ≠ semantic-compat (documented); (6) no config alias hides a formula change; (7) formula
versions machine-readable; (8) unknown compatibility fails closed (n/a — determined).

## 10. Per-feature decision

- **`ema_spread`** → **LEGACY_PRESERVED**. FM-022 unchanged (`(ema_fast-ema_slow)/atr`, `semantic_version:
  1.0-legacy-price-scaled`, `units: price_scaled`, `known_issue`, `replacement_identity: FM-030`,
  `artifact_compatibility: LEGACY_BOUND`). Corrected **FM-030 `ema_spread_atr`** registered in
  `migration_candidates` (`active:false`, `2.0-atr-absolute`).
- **`momentum_score`** → **LEGACY_PRESERVED**. FM-023 unchanged; corrected **FM-031 `momentum_score_atr`**
  registered inactive.
- **`atr`** → **IDENTITY_CLARIFIED**. New `indicator_identities.atr` (IND-001): `smoothing_method: SMA`,
  `lookback: 14`, `output: close_relative`, `normalization_basis: close`, `units: dimensionless`,
  false-Wilder/absolute-ATR misreadings corrected. Math unchanged.
- **`rsi_14`** → **IDENTITY_CLARIFIED**. New `indicator_identities.rsi_14` (IND-002): `smoothing_method:
  SMA`, warmup/zero-loss/zero-gain behaviors; **false "Standard Wilder formula" docstring corrected** at
  `feature_pipeline.py` `compute_indicators`. Math unchanged.
- **`wick_size`** → **LEGACY_MISNOMER_GOVERNED** (Option C). FM-002 extended: `semantic_quantity:
  candle_range`, `misnomer_alias: wick_size`, `status: deprecated_misnomer_alias`, `wick_magnitude_is:
  total_wick`. Slot math frozen.

## 11. Code/config/governance changes

- `configs/formulas/market_ontology.yaml` (v1.1 → **v1.2**): FM-022/FM-023 identity+migration fields;
  FM-002 misnomer governance; new `indicator_identities` (atr, rsi_14) and `migration_candidates`
  (FM-030, FM-031) sections. **Source-of-truth edit** (not a generated artifact).
- `src/features/feature_pipeline.py`: RSI docstring corrected (comment-only, behavior-neutral).
- `tests/test_b0b1_feature_semantic_migration.py`: new focused suite (14 tests).

No generated governance artifact was hand-edited. `validate_registry()` returns `[]`; `build_lineage_graph`
unchanged (new sections are invisible to the 3-section iterators — verified).

## 12. Formula identity contract — AFTER

Machine-readable, in the single authoritative WHAT artifact. Legacy identities carry
`semantic_version`/`units`/`normalization_basis`/`known_issue`/`replacement_identity`/
`artifact_compatibility`; corrected identities are explicit, versioned, and **inactive**; rolling
indicators have descriptive `smoothing_method`/`lookback`/`normalization_basis`/`units`; the misnomer
slot is unmistakable. A future consumer/runtime can read a stable `semantic_version` and
`artifact_compatibility` per identity.

## 13. Runtime compatibility enforcement

**RUNTIME_COMPATIBILITY_ENFORCEMENT = NOT_REQUIRED_WITH_EVIDENCE.** No feature math changed, so no
"corrected contract" is active at runtime; the legacy-artifact-vs-corrected-contract mismatch scenario
is **not triggerable today** (evidence: `rr_fusion.enabled=false`, `use_bitnet=false`,
`gaussian_impl=heuristic`, `rr_model.provenance.path_active_on_config=false`, vector math byte-identical).
Per the task's "if no trained artifacts are runtime reachable for a changed feature, implement only the
minimum necessary enforcement," the minimum fail-closed mechanism is a **governance test floor** (rather
than a runtime feature-hash framework the task says to avoid): `test_legacy_formula_strings_pinned` +
`test_legacy_scalar_math_unchanged` make any silent future semantic change of FM-022/FM-023 fail closed;
`semantic_version`/`artifact_compatibility` fields are the forward hook for a future runtime check when a
correction is actually activated (B2+).

## 14. Tests added

`tests/test_b0b1_feature_semantic_migration.py` (14): F1/F2 legacy scale-dependence; corrected FM-030/031
scale-invariance; F3 ATR=SMA≠Wilder; F4 RSI=SMA≠Wilder; F5 wick_size=candle_range≠wick-magnitude;
dim==38 + order/slot pins; legacy formula-string pins (fail-closed); ontology identity fields present;
indicator_identities declare SMA; migration_candidates proposed+inactive; RSI docstring no longer claims
Wilder; legacy scalar math unchanged.

## 15. Fresh test results

- **New suite:** `14 passed`.
- **Regression (fresh):** `test_feature_lineage` + `test_feature_math_lint` + `test_derived_math` +
  `test_candle_math` + `test_feature_pipeline` + `tests/features/` + `test_feature_dependency_graph_fc05`
  → **all green** (≈85 passed with the new suite). Model-loading/contract discovery (`-k model_registry
  or rr_model or gaussian_registry`) → `14 passed`.
- **One PRE-EXISTING, UNRELATED failure:** `test_feature_contract_v1.py::test_change_contracts_drafted`
  asserts `docs/governance/feature_pipeline_change_contracts/FC1-A-*.json` / `FC1-D-*.json` have
  `status=="DRAFTED_FC0_NOT_IMPLEMENTED"`, but they read `IMPLEMENTED`. That directory is **untracked**
  (prior FC1-A/FC1-D work by another session) and **outside my task surface** (my targets are the 5
  features). Not caused by, and not fixed by, this task (out of scope).

## 16. Canonical dimension/order proof

`CANONICAL_FEATURE_DIM == 38`, `len(CANONICAL_FEATURES) == 38`; slot pins asserted: `ema_spread`=9,
`momentum_score`=12, `atr`=13, `rsi_14`=15, `wick_size`=27, `body_ratio`=28. `CANONICAL_FEATURES` tuple
untouched. `CANONICAL_FEATURE_ORDER_CHANGED = NO`.

## 17. Historical reproducibility proof

FM-022/FM-023 `formula` strings and `derived_math.ema_spread`/`momentum_score` scalars are byte-identical
(pinned by `test_legacy_formula_strings_pinned` + `test_legacy_scalar_math_unchanged`). No model artifact
was modified. Any historical vector is reproducible by the unchanged pipeline; the corrected identities
are additive/inactive and change nothing that was ever emitted.

## 18. Remaining blockers

- Activating FM-030/FM-031 requires **retraining** the inactive `rr_model.json` / Gaussian-38 artifacts
  **and recalibrating** `dual_engine.{trend_strength_threshold, momentum_threshold}` — both out of scope.
- `atr`/`rsi_14` full FM-id + parity registration is blocked by the ontology **rolling-indicator boundary
  freeze** (a separate architectural review).
- Pre-existing unrelated red: `test_change_contracts_drafted` (FC1-A/FC1-D status drift) — flagged, not owned here.

## 19. Deferred B2/B3 work

- **B2:** wire FM-030/FM-031 behind a versioned migration + retrain the inactive artifacts + recalibrate
  the active thresholds + runtime `semantic_version`/`artifact_compatibility` enforcement gate.
- **B3:** the volume/session/liquidity/retest/sweep group (explicitly out of scope here); the ATR/RSI
  boundary-freeze architectural review (promote IND-001/IND-002 to first-class parity-verified identities).

## 20. Git diff / status

**Task surface** (both edited files were already `M` at session start from prior work — my additions are
identifiable by the `B0/B1` / `FM-030` / `indicator_identities` / `migration_candidates` sentinels):
```
 M configs/formulas/market_ontology.yaml   (v1.2: +FM-022/023 fields, FM-002 misnomer, +2 sections, +FM-030/031)
 M src/features/feature_pipeline.py         (RSI docstring corrected — comment only, behavior-neutral)
?? tests/test_b0b1_feature_semantic_migration.py
?? reports/analysis/b0-b1-feature-semantic-migration-2026-07-12.md
```
Regenerated generated artifacts: **none** (the ontology is a source-of-truth file, hand-maintained).

## 21. Production behavior changes

**NONE.** No feature math changed; the only production-file edit is a comment. No engine/fusion/decision/
execution/risk code, no config `params`/thresholds, no model artifact, no `CANONICAL_FEATURES` touched.
`PRODUCTION_BEHAVIOR_CHANGED = NO`.
