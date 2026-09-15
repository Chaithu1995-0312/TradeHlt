# Who consumes `active_models.yaml`

## Context
User asked a pure information/lookup question — "who all are consuming `active_models.yaml`" —
not a code-change request. Per CLAUDE.md §1.1 (Evidence & Verification Discipline), every claim
below was grep/read-verified at source, not taken from memory or a prior summary. No repository
files are modified by this task; this is a report only.

`active_models.yaml` is CLAUDE.md's declared "loaded first in every Claude session" doc, but
source inspection shows it is **also** a genuine runtime-loaded config parsed by production
Python code (`yaml.safe_load`), not merely an LLM-context artifact.

## 1. Programmatic consumers (open/`yaml.safe_load` the file)

| File:Line | Role |
|---|---|
| [src/features/model_evidence.py:79,257-263](src/features/model_evidence.py:257) | `load_active_models()` — feeds `ModelDeclaration`/evidence building |
| [src/config_layer/model_resolver.py:29,103-115](src/config_layer/model_resolver.py:103) | `_load_identity_doc()` — reconciles WHO identity vs runtime model selection (`resolve_model`, `resolve_zone_gate_runtime`) |
| [src/config_layer/state_contract_loader.py:38,55-65](src/config_layer/state_contract_loader.py:55) | Loads + validates `crt.runtime` state_contracts/valid_transitions; raises `StateContractError` on malformed/missing |
| [src/config_layer/stack_version.py:185,192](src/config_layer/stack_version.py:185) | SHA-256 hashes the raw file **and** parses `meta.schema_version` into stack-version provenance |
| [src/config_layer/production_bundle.py:39-45](src/config_layer/production_bundle.py:39) | Indirect — imports `model_resolver`'s loader to build the Selected-vs-Enabled bundle |
| [src/governance/hypothesis_registry.py](src/governance/hypothesis_registry.py) | Confirmed via grep as an additional consumer (not in the original agent report — validated to exist) |
| [scripts/maintenance/gen_crt_state_identity.py:77,119-120](scripts/maintenance/gen_crt_state_identity.py:119) | Parses `crt.runtime` and **generates** `src/config_layer/_crt_state_generated.py` (the `CRTState` enum / `VALID_TRANSITIONS`) — the one case of regenerating checked-in source, not a `data/`/`context/` artifact |

**Runtime call sites (confirms this is a live-engine dependency, verified directly):**
- [src/core/engine_runner.py:373](src/core/engine_runner.py:373) — `from config_layer.model_resolver import resolve_model`
- [src/core/engine_runner.py:473](src/core/engine_runner.py:473) — `from config_layer.model_resolver import resolve_zone_gate_runtime`
- `src/config_layer/crt_engine_v2.py:2654` — `from config_layer.state_contract_loader import load_and_validate_state_contracts`

These are in-function imports inside the live CRT/engine execution path — the YAML is parsed
during actual engine runs, not only by tests or governance tooling.

**Retrieval/indexing (LLM-context builder, code-driven, does not parse YAML values):**
- `src/retrieval/config.py:128` — listed in `RetrievalConfig.include_patterns` (indexed as text)
- `src/retrieval/truth_tier.py:146` — regex-classified tier `"INTENDED"`, weight 6, for ranking retrieval results

**False positives ruled out** (mention the filename in a docstring/comment only — do not open it):
`src/config_layer/state_identity.py`, `state_topology.py`, `state_contract.py`, `model_paths.py`,
`src/runtime/backtest_v2.py:2503` (an F-058 explanatory code comment, verified — not a load call).

## 2. Test floors (verified to exist)

- `tests/test_active_models_registry.py` — schema_version==2.3 assertion, F-### finding-id cross-check against `docs/current-findings.md`, negative guard against leaked threshold keys
- `tests/test_crt_state_invariants.py` — internal YAML consistency + YAML↔generated-code parity
- `tests/test_crt_state_identity.py`, `test_crt_state_generated_parity.py` — generation-source vs generated-artifact parity
- `tests/test_crt_states_yaml_state_names.py`, `test_crt_states_yaml_transition_parity.py` — drift check vs `configs/formulas/market_crt_states.yaml`
- `tests/test_state_contracts.py`, `test_state_topology_phase.py` — `state_contract_loader` unit/validation tests
- `tests/test_doc_citations.py` — treats it as an in-scope cited doc requiring `path:line · Symbol` citations
- `tests/test_governance_invariant_check.py` — asserts it's in `GOVERNED_FILES`, requires the registry test to run on change
- `tests/test_hypothesis_registry.py`, `test_model_evidence.py`, `test_three_authority_drift_adjudication.py`, `test_who_numeric_dependency_census.py`, `test_reachability_golden.py`, `test_claude_deepseek_pointers.py`, `test_behavioral_constant_authority_trace.py` — cross-checks tying other governance artifacts back to this file

## 3. Documentation citations (cite, don't parse)

CLAUDE.md itself; `docs/governance/config_authority_matrix.md`, `MODEL_INTENT_AUTHORITY_REGISTER.md`,
`model_lineage_rollup.md`; `docs/architecture/model-design-intent.md`; `docs/topics/model-intent-and-feature-ownership.md`;
build-manifest JSONs for edits to it; assorted session-log/implementation-plan narration.

## 4. Tooling that regenerates other artifacts from it

- `scripts/maintenance/gen_crt_state_identity.py` → `src/config_layer/_crt_state_generated.py` (checked-in source, not `data/`/`context/`)
- `scripts/analysis/update_reachability_golden.py` → committed reachability golden fixture
- `scripts/governance/build_msip1_verification_package.py` → copies it + extracts `crt.runtime` into the MSIP-1 package
- `scripts/governance/who_numeric_dependency_census.py`, `behavioral_constant_authority_trace.py`, `three_authority_surplus_census.py` → governance census/report JSON under `docs/governance/`
- `scripts/maintenance/check_governance_invariants.py` → lists it in `GOVERNED_FILES` (Gate-6), gates commits touching it

**Negative finding**: `scripts/context/build_context.py` (the Portable-Mind context compiler) does
**not** reference `active_models.yaml` — it draws only from CLAUDE.md, `docs/current-findings.md`,
and `configs/production/ACTIVE_VERSION`.

## Bottom line

`active_models.yaml` is **not** purely an LLM-context artifact. It is a dual-role file:
1. A **live runtime dependency** — `EngineRunner` and `CRTEngineV2` resolve model identity and
   CRT state contracts through it every run (via `model_resolver.py` / `state_contract_loader.py`).
2. The **code-generation source** for `_crt_state_generated.py` (the actual `CRTState` enum most
   of the codebase imports).
3. A heavily **governance-gated and test-cross-checked** WHO/identity authority document.
4. Also indexed for LLM/Claude-session retrieval per CLAUDE.md's "load first" instruction — but
   that is additive to, not instead of, its runtime role.

This is a report; no files were changed.
