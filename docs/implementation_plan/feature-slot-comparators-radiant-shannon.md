# Plan: FM-021 fix — declare the transitive E01 retest identities and prove live parity

## Context
The consumer A/B (`docs/analysis/e01-lifecycle-downstream-consumers-2026-10-03.md`) found that
under `feature_pipeline.sweep_semantics = e01_lifecycle` five vector values change, not the four
Step 6 registered. `retest_depth` (FM-021, slot 34) changes on 17.4% of XAUUSD bars.

Two gaps were recorded in F-112 as an E-001 correction:
1. **Undeclared identity change.** Step 6 registered FM-090..093 for the four sweep slots only.
2. **Untested live parity.** The Step 6 parity tests covered the four sweep slots only.

What exploration established (read-only):
- **The code is already right; only the declaration is missing.** The ontology already declares the
  chain: FM-061 `retest_flag` depends on `liquidity_sweep`, and FM-021 `retest_depth` depends on
  `retest_flag`. In e01 mode the pipeline feeds the e01 `liquidity_sweep` into both, so the values
  are the honest consequence of the switch. What is missing is a registered identity for them.
- **The ontology closure is exactly two nodes.** The transitive closure of the four sweep slots adds
  only FM-061 (internal column) and FM-021 (vector slot 34). The A/B independently asserted that the
  other 43 vector slots are identical.
- **Live parity should hold by construction; it is untested.** `runtime/live_rail_feeder.py` keeps
  every pushed bar and re-runs the full `FeaturePipeline` each bar, then takes the last row. So live
  `retest_depth` equals batch at the same history. `core/feature_store.py` overrides only the four
  sweep slots and never touches `retest_depth` (grep-confirmed).
  - Correction to my last message: the live/batch mismatch I flagged is unlikely; it is unproven,
    not likely broken.
- **Retest meaning is still PROPOSED.** The retest semantics are not frozen
  (`concept_contracts.yaml`, SP-003 / OQ7). So the new identities say only "the same formula, fed
  by the MKT-E01 sweep". They do not claim the contract's retest meaning.
  - Separately, the contract's divergence row says `retest_flag` has "no FM id" and cites stale
    lines. That is drift: FM-061 exists.

Boundaries (unchanged): no activation, no config change, no retrain, no schema change, no change to
any emitted value. Default `latest_unconsumed` stays byte-identical.

## Approach (the Step 6 / F-061 pattern, reused)
1. **Ontology** (`configs/formulas/market_ontology.yaml`). Next free ids are FM-094/095.
   - `retest_flag_e01`, **FM-094**:
     - Placed in `structural_states`, beside FM-061.
     - Same formula, with `liquidity_sweep_e01 != 0` in place of the legacy slot.
     - `depends_on: [liquidity_sweep_e01, close, ema_fast, atr]`, `active: false`, `replaces: FM-061`.
     - `config_key: feature_pipeline.sweep_semantics`, `migration_class: FORMULA_CORRECTION`.
   - `retest_depth_e01`, **FM-095**:
     - Placed in `derived_metrics` (the flat, additive frozen key), beside FM-021.
     - Same formula and the same `impl: derived_math.retest_depth`, so the existing `DERIVED` map
       entry is reused and no new callable is needed.
     - Gated on `retest_flag_e01`; `active: false`, `replaces: FM-021`, same `config_key`.
     - `lineage.vector_key: []`, matching how FM-090..093 are declared.
   - Each note says why the id is new: the value identity changes through a dependency, and the
     F-054 `dependency_contract_hash` rule treats that as a new node. Each also notes that retest
     semantics remain PROPOSED (OQ7).
   - Extend the FM-090..092 program comment to read "FM-090..095".
2. **Comment-only source drift fix** (`src/features/feature_pipeline.py`, in
   `compute_structure_liquidity`'s retest block):
   - Replace the stale "`retest_flag` is an internal column, no FM id" with "FM-061; FM-094 under
     e01_lifecycle (retest_depth FM-021 / FM-095)".
   - No logic change. The XAUUSD vector regression proves it byte-identical.
3. **Semantic registries:**
   - `concept_contracts.yaml` retest divergence row: `current` → "FM-061 (legacy sweep input) /
     FM-094 (MKT-E01 sweep input), internal ATR band". Refresh the stale line citation.
     `disposition` stays RECORDED, because retest is still undefined.
   - `representation_registry/feature_pipeline.yaml`: add to the `retest_depth` note that it is
     identity-bearing on `sweep_semantics` (FM-021 / FM-095).
4. **Parity test.** Add a test to `tests/test_e01_sweep_semantics.py`.
   - Reuse `tests/test_live_rail_feeder.py::_bar` (synthetic `ClosedBar`) and the monkeypatch idea of
     `test_live_store_carries_the_lifecycle_and_matches_batch`. Patch
     `config_layer.production_config.get_prod_section("feature_pipeline")` so the feeder's `cfg=None`
     pipeline resolves to e01.
   - Push N≈200 bars into `LiveRailFeeder`. At every ready step k, compare the feeder's last-row
     `retest_depth` and the four sweep slots with a batch `FeaturePipeline` run over all N bars at
     row k. This proves prefix invariance and live = batch.
   - Non-vacuity asserts: `retest_depth` is non-zero on some rows, and differs from the legacy arm
     somewhere.
   - Same comparison for the legacy arm, as a control.
   - Also add a batch assertion that, in e01 mode, `retest_flag` equals FM-061's rule applied to the
     e01 `liquidity_sweep`. That pins FM-094's declared formula to the code.
   - If the parity test fails, stop and report it before anything is fixed.
5. **Governance plumbing:**
   - Freeze pin: add a waiver entry `E01-LIFECYCLE-RETEST-IDENTITY` refreshing the
     `market_ontology.yaml` and `feature_pipeline.py` SHAs (same scratch-script pattern as Step 6).
   - New impact manifest `docs/governance/build_manifests/CH-e01-lifecycle-retest-identity.impact.json`
     (FORMULA_CHANGE + SEMANTIC_REGISTRY_CHANGE; MODEL_INPUT_CHANGE as potential only). It
     references `CH-e01-lifecycle-sweep-identity` as the change it completes. The approved Step 6
     manifest stays untouched (append discipline). Then run
     `construction_protocol.py validate-impact` and `validate-completion`.
6. **Records:**
   - F-112: Evidence gains FM-094/095; the earlier "UNVERIFIED" live-parity clause becomes the
     measured result, marked `CORRECTED: <old> -> <new>`; the CLAUDE.md row is synced.
   - Addendum to the downstream-consumers evidence doc. Re-export `data/findings.jsonl`.
   - `docs/topics/feature-schema.md` discussion entry (§6.4).
   - SESSION LOG.

## Verification
- `pytest tests/test_e01_sweep_semantics.py tests/test_level_lifecycle.py tests/test_live_rail_feeder.py -q`
  (the new parity test is green).
- Registry and lint: `tests/test_formula_registry.py`, `tests/test_semantic_registry.py`,
  `tests/test_feature_lineage.py`, `tests/test_feature_math_lint.py`,
  `tests/test_active_models_registry.py`, `tests/test_derived_math.py`.
- `tests/test_feature_layer_freeze.py`: XAUUSD vector regression unchanged; pins match after the waiver.
- `pytest tests/semantics -q`; `construction_protocol.py check` (construction floor GREEN).
- Findings: `test_current_findings`, `test_findings_export`, `test_doc_citations`, `test_session_log`.
- Governance floor `check_governance_invariants.py --all` in the background, expected at the same 7
  known reds.
- No config edit; params hash `7de09f62` unchanged.

## Not in scope
Activation; deciding the retest meaning (OQ7); fixing the C5 TRS-06 / `RETEST_REPLAY.tp1_mult`
gaps; C03; the arm-independent C2/C4/C03 rows; commit.
