# BG-001 Binding Gap Analysis

**Status:** OBSERVATION ONLY · READ-ONLY · NO AUTHORITY · NO PROMOTION  
**Date:** 2026-09-09  
**Phase 0 commit:** `578e38e`  
**Question:** how widespread is the unresolved-binding pattern beyond the L-003 sample?

---

## 1. Scope

Paths examined (read-only, no file edited other than this report):

| Path | What was read |
|---|---|
| `configs/research/measurement_contracts/` | 18 contract documents (MC-* instances, drafts, MP-* profiles) |
| `docs/research/reports/l003_jse_falsify_evidence_pack-2026-09-08.json` | 4 normalized FalsifyRecords |
| `docs/governance/measurement_object_registry.json` | 3 registered MeasurementObjects |
| `docs/governance/population_registry.json` | 3 registered Populations |
| `docs/research/reports/SCHEMAS_README.md` | 5 declared binding rules |
| `docs/governance/measurement_contract.schema.json` + the 2 provenance schemas | frozen-schema field inventory |

**Excluded:** `src/`, `.venv/`, `.claude/`, `logs/`, and the 18 pre-existing GREEN_FLOOR failures.

### Scope correction (recorded, not silently applied)

The manifest scoped `MC-*.json` / `MP-*.json` to **`docs/governance/`** and excluded `configs/`. Measured before executing:

- `find docs/governance -name 'MC-*.json' -o -name 'MP-*.json'` -> **0 files**.
- All 18 contract documents live under `configs/research/measurement_contracts/`.

Executing the declared scope verbatim would have produced a vacuous *"0 contracts found"* and a BG-001 result of 0%, which measures nothing. The manifest's **intent** (contract linkage prevalence) is preserved by measuring where the contracts actually are. The `configs/` exclusion is therefore narrowed to *contract documents only* — no production config, no `src/`, nothing executable was read.

## 2. Method

Pure read: `json.loads` on every contract, registry and the evidence pack; a recursive key search (`deep_find_keys`) for dataset linkage under any nesting depth, since a dataset reference need not be top-level. Cross-references are set-membership checks against the two tracked registries. No file was staged, edited or executed; the analysis script itself lives in the session scratchpad, deliberately **not** under `scripts/`, because `script_census.py` scans the filesystem (the 6 unregistered paths in the current `test_script_registry` red are untracked files) — a `.py` there would become a 7th unregistered path and worsen an existing baseline red.

## 3. BG-003: Declared vs enforced matrix

| Link | Declared (prose/schema) | Mechanically enforced | Mechanism |
|---|---|---|---|
| FalsifyRecord -> MeasurementObject (object_id) | Yes (rule 1) | **Yes** | tests/governance/test_falsify_record_binding.py::test_rule1_* |
| FalsifyRecord -> Population (population_id) | Yes (rule 2) | **Yes** | tests/governance/test_falsify_record_binding.py::test_rule2_* |
| FalsifyRecord -> JointStateSpace (target_coordinate in S) | Yes (rule 3) | **Yes** | tests/governance/test_falsify_record_binding.py::test_rule3_* |
| FalsifyRecord -> falsify_record.schema.json (shape) | Yes (rule 4) | **Yes** | test_rule4_* (required-list + declared primitive types; jsonschema absent from venv) |
| MeasurementObject -> formula_map.notation | Yes (rule 5) | **Yes** | tests/governance/test_falsify_record_binding.py::test_rule5_* |
| Artifacts are git-tracked (resolves) | Yes (provenance_record.schema.json) | **Yes** | test_every_artifact_is_git_tracked (git ls-files, not filesystem) |
| MeasurementContract -> Population Registry | Yes (prose, SCHEMAS_README) | **No** | TruthConflict: contract embeds population inline, no population_id; frozen schema |
| MeasurementContract -> DatasetIdentity | Yes (prose, arch review) | **No** | TruthConflict: no dataset field in the frozen contract at all |
| MeasurementExecution -> MeasurementContract (contract_id) | Yes (schema pattern) | Partial | Pattern `^(MC\|MP)-.+$` constrains SHAPE; no test resolves the id to a file |
| ProvenanceRecord -> 4 origin slots | Yes (schema) | Partial | chain_complete/resolves are COMPUTED by src/governance/provenance_record.py |
| CorpusAuthorityDecision -> DatasetIdentity | Implied (both carry volume/status enums) | **No** | No typed reference field in either schema; only shared enum vocabulary |

**6 enforced · 2 partial · 3 declared-only** out of 11 linkages examined.

All 6 enforced links were enforced by Phase 0; before it, **0 of 11 were mechanically checked**. The 3 declared-only links are the same two frozen-schema gaps plus the CorpusAuthorityDecision/DatasetIdentity pair, which share enum vocabulary but have no typed reference field in either direction.

## 4. BG-001: Contract linkage prevalence

**N = 18 contract documents** (13 sealed instances, 5 drafts/profiles).

| Category | Count | % of N |
|---|---|---|
| `population` embedded | 15 | 83.3% |
| dataset linkage embedded | 0 | 0.0% |
| **both** embedded | 0 | 0.0% |
| **neither** embedded | 3 | 16.7% |
| population only (no dataset link) | 15 | 83.3% |

- **% self-contained for population:** 83.3% — `population` is a *required* field of the frozen schema, so this is structural, not a choice any contract made.
- **% requiring a sidecar for dataset linkage:** 100.0%.

Sample ids:

| Category | Sample ids |
|---|---|
| population only | `MC-SUJAN-XAUUSD-M15-V1`, `MC-ASYM-XAUUSD-M15-V1`, `MC-CRT-SB-XAUUSD-M15-NS-V1`, `MC-CRT-SB-XAUUSD-M15-SOFF-V1`, `MC-CRT-SB-XAUUSD-M15-V1` (+10 more) |
| both | _none_ |
| dataset only | _none_ |
| neither | `MP-CRYPTO-MAJORS`, `MP-FX-MAJORS`, `MP-METALS-MT5` |

**The `neither` category is a shape difference, not a gap.** All 3 are MP-* *profiles* (`MP-CRYPTO-MAJORS`, `MP-FX-MAJORS`, `MP-METALS-MT5`), which declare reusable per-asset-class defaults rather than a concrete experiment population. Split by kind:

| Kind | N | `population` embedded | dataset linkage |
|---|---|---|---|
| MC-* (contract instances + drafts) | 15 | 15 (100.0%) | 0 (0.0%) |
| MP-* (profiles) | 3 | 0 | 0 (0.0%) |

So among actual contracts, `population` embedding is **100.0%** and dataset linkage is **0.0%** — uniform, with no contract deviating in either direction.

## 5. BG-002: Registry resolution prevalence

| Reference type | Refs found | Resolved | Unresolved |
|---|---|---|---|
| `object_id` -> measurement_object_registry.json | 2 | 2 | 0 |
| `population_id` -> population_registry.json | 4 | 4 | 0 |

**Unresolved ids:** _none_

**Declared-absent `object_id` (null + reason):** 2 of 4 records — `FALSIFY-JSE002-ENGINESTATE-PATHGEOM`, `FALSIFY-JSE003-ENGINEHIST-PATHGEOM`. These target path-geometry descriptor buckets that have no registered MeasurementObject. They are counted as **declared gaps, not unresolved references**: an invented id would have been fabrication, and a bare missing key is what the floor test rejects.

Registry contents actually reachable from the evidence:

- MeasurementObjects registered: 3 (`Y_joint`, `Y_oracle`, `Y_scanner`); referenced by the pack: 1.
- Populations registered: 3 (`Omega_anatomy_opportunity`, `Omega_bnb_anatomy`, `STATE_SL_TP_anatomy`); referenced by the pack: 2.

## 6. BG-004: TruthConflict census

How many artifacts would need a **frozen-schema mutation** versus a **sidecar expression**, if the two declared-only contract links were to be made resolvable?

| Route | Artifacts affected | Note |
|---|---|---|
| Schema mutation | **3 schema files**, invalidating **18 contract documents** | Every sealed instance would need revalidation; `measurement_contract.schema.json` is FROZEN v1.0.0 with `additionalProperties:false` |
| Sidecar expression | **0 existing files changed**; up to 18 new optional rows | `measurement_binding.schema.json` (template, 0 instances today) |

**Qualitative assessment:** the frozen-schema doctrine is creating **2 exceptions, not 200**. Both are the *same* structural gap (contract -> population, contract -> dataset) repeated uniformly across all contracts, not a growing family of special cases. The count scales with contract volume (18 today) but the number of distinct *kinds* of exception is 2 and has not grown since the frozen schema was sealed. That is a bounded cost, not an accumulating one.

## 7. Non-claims

This analysis measures **resolution**, not correctness. Specifically it does **not** determine:

- whether any linkage is *semantically* correct — only whether a referenced id exists in a registry;
- whether the contract's embedded `population` block and the L-003 `Omega` Population Registry describe the same set — they are different objects sharing a word, and no mapping was attempted;
- whether any measurement is economically meaningful, admissible, or trustworthy (mt00/mt01 coverage is unchanged; 0/27 probes exist);
- whether the declared-only links *should* be made resolvable;
- anything about `src/`, production configs, or the live path.

No registry was promoted, no entry elevated, no schema altered. Grants no authority (CLAUDE.md §6.5).

## 8. Recommended next observations

Observation proposals only — no architectural change is proposed.

1. **Contract population vs registry population overlap.** Measure whether any contract's embedded `population` block describes a set already registered as an `Omega_*`. Today this is unknown; it decides whether a contract->population reference would even have a target.
2. **Extend BG-002 to the MPA ledger.** The provenance spine reports 4 provenance-complete chains over 168 records; measuring how many of those resolve to *tracked* targets would apply the same git-tracked standard the floor test now applies to the pack.
3. **Re-run BG-001 after any new sealed contract.** The count is a moving denominator; the 2-exception assessment holds only while the *kinds* stay at 2.

---

_Generated read-only. Contract documents scanned: 18. FalsifyRecords: 4. No file other than this report was written._
