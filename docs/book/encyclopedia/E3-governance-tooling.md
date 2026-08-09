# Encyclopedia E3 — Governance Tooling

**Phase:** E3  
**Status:** DONE (library + CLI index — not every analysis probe essay)  
**Date:** 2026-08-07  
**Parent:** [Chapter 24](../24-repository-encyclopedia.md) · [Encyclopedia index](README.md)  
**Architecture narrative:** [Chapter 16](../16-config-first-and-promotion.md) · [Chapter 17](../17-truth-maintenance.md) · [Chapter 18](../18-field-guide-governance.md)

## Scope

| Tree | `.py` files | Role |
|---|---:|---|
| `src/governance/` | **19** | Promotion, registries, validators, SITS cores — importable |
| `scripts/governance/` | **31** | Construction protocol, seeds, queries, feature-DAG, promote CLIs |
| `scripts/analysis/` | **115** | Census, probes, generators, instrument forensics (OBSERVE-heavy) |
| `scripts/maintenance/` | **9** | Hash, session-log rotation, hygiene (adjacent ops) |
| **Total E3 surface** | **~174** | Governance / truth / map tooling |

**E3 design rule:** index by **job type** (promote, seed registry, certify features, generate maps, probe drift) — not 174 narratives. Deep doctrine stays in Ch.16–18 and `docs/governance/*`.

**Group:** governance libraries = **A-adjacent (ops authority)**; most analysis scripts = **D (operators)** or **OBSERVE_ONLY**.  
**Relevance:** can **write** promotion logs, registries under `data/`, governance artifacts — treat write paths as gated.

---

## How to use this index

| If you need to… | Start here |
|---|---|
| Promote a config | `PromotionManager` + `scripts/governance/promote_v2.py` · Ch.16 |
| Enforce construction protocol | `scripts/governance/construction_protocol.py` |
| Query hypotheses / frameworks / scripts | `query_hypotheses.py` / `query_registry.py` / `query_scripts.py` |
| Seed registries | `seed_*_registry.py` (PRIMARY in seeds, GENERATED in `data/`) |
| Feature certification / DAG | `feature_dag_certify.py`, `feature_certification_state.py`, `feature_surface_query.py` |
| Findings machine export | `export_findings.py` → `data/findings.jsonl` |
| Config reachability / behavior census | `scripts/analysis/config_reachability.py`, `behavior_census.py` |
| Regenerate architecture maps | `gen_code_map.py`, `gen_pyan.py`, `generate_cli_matrix.py`, … |

---

## 1. Job map (primary navigation)

| Job | Library (`src/governance`) | CLI / script | Writes | Chapter |
|---|---|---|---|---|
| **Promote production config** | `promotion_manager.py` | `scripts/governance/promote_v2.py` | `configs/production/*`, `promotion_log.jsonl` | Ch.16 |
| **Shadow promotion gate** | `shadow_promotion_gate.py` | (via manager / dedicated flows) | shadow reports | Ch.16 |
| **Config integrity check** | `config_integrity.py` | analysis / preflight | usually none | Ch.16; F-006 class |
| **Portfolio validation** | `portfolio_validation.py` | multi-market validation paths | validation reports | Ch.16 |
| **Multi-strategy validation** | `multi_strategy_validator.py`, `strategy_backtest.py` | promote_v2 / validators | ValidationReport | Ch.16 |
| **Governance loop orchestrator** | `orchestrator.py` | control-plane / CLI wrappers | audit trails | Ch.16 adjacent |
| **Findings → JSONL** | `findings_export.py` | `export_findings.py` | `data/findings.jsonl` (GENERATED) | Ch.17 |
| **Hypothesis registry** | `hypothesis_registry.py` | `seed_hypothesis_registry.py`, `query_hypotheses.py` | `data/hypothesis_registry.jsonl` | Ch.17 / E2 |
| **Framework registry** | `framework_registry.py` | `seed_framework_registry.py`, `query_registry.py`, `update_registry.py` | `data/framework_registry.jsonl` | Ch.17 |
| **Script registry (SITS)** | `script_registry.py`, `script_census.py`, `script_seed.py` | `seed_script_registry.py`, `query_scripts.py`, `scripts/analysis/script_census.py` | stubs + `data/script_registry.jsonl` | CLAUDE §3.1 |
| **Module attribution census** | `module_census.py`, `module_attribution.py` | module census CLI under analysis | module registry artifacts | Ch.04 adjacent |
| **Construction protocol** | — | `construction_protocol.py` | completion validation | Gate 6 protocol |
| **Feature DAG certify** | — | `feature_dag_certify.py`, `feature_certification_state.py` | certification ledger | Ch.06–07 / F-054 |
| **Feature surface query** | — | `feature_surface_query.py` | read-only | Ch.07 query surface |
| **BitNet governance executor** | `bitnet_governance_executor.py` | bitnet governance flows | gated | Ch.10 BitNet |
| **Meta governor executor** | (if present as meta path) | meta-governor flows | gated | Ch.16 |
| **Expansion integration** | `expansion_integration.py` | expansion ops | research/ops | sidecar |
| **Reflection buffer** | `reflection_buffer_advanced.py` | advanced reflection | sidecar | low priority |
| **Runtime import boundary scan** | — | `scan_runtime_boundary.py` | report | hygiene |
| **Model path literal scan** | — | `scan_model_paths_literals.py` | report | ModelPaths boundary |
| **Three-authority surplus census** | — | `three_authority_surplus_census.py` | census artifacts | Ch.17 / WHO-WHAT-HOW |
| **CRT config construction census** | — | `crt_config_construction_census.py` | census (F-057 class) | Ch.13 |
| **Validation access pack** | — | `validation_access_cli.py` | `results/validation_access/**` | research access |
| **Session log / hash hygiene** | — | `scripts/maintenance/*` | logs, hashes | CLAUDE §6 |

---

## 2. `src/governance/` — library encyclopedia (19 files)

### Promotion & validation (LIVE ops)

### `promotion_manager.py`
- **Relevance:** LIVE · **Purpose:** Only path to production promotion — requires APPROVE ValidationReport, SHA-256, append-only `promotion_log.jsonl`.
- **Entry:** `python …/promotion_manager.py` or `promote_v2.py`; never bypass.
- **Chapter:** Ch.16.

### `shadow_promotion_gate.py`
- **Relevance:** LIVE · **Purpose:** Two-gate shadow promotion before full promote.
- **Chapter:** Ch.16.

### `config_integrity.py`
- **Relevance:** LIVE (often under-consumed) · **Purpose:** Config lineage / integrity guards (F-006: real check historically orphaned from hot path — still hygiene-critical).
- **Chapter:** Ch.16; findings F-006.

### `portfolio_validation.py`
- **Relevance:** LIVE-research/ops · **Purpose:** Multi-market edge universality validation for portfolios.
- **Chapter:** Ch.16 adjacent; F-013 class (allocator orphaned from live single-candle spine).

### `multi_strategy_validator.py` / `strategy_backtest.py`
- **Relevance:** PARTIAL · **Purpose:** ValidationReport across strategy modules + per-strategy backtest measurement.
- **Note:** Strategy modules largely DORMANT (Group C) — validators exist for multi-strategy governance path.
- **Chapter:** Ch.16; E5 for strategies themselves.

### `orchestrator.py`
- **Relevance:** LIVE-ops · **Purpose:** GovernanceOrchestrator — multi-step governance loop coordination.
- **Chapter:** Ch.16.

### Registries & generated truth (LIVE meta)

### `findings_export.py`
- **Relevance:** LIVE · **Purpose:** Parse `docs/current-findings.md` → `data/findings.jsonl` (GENERATED; never hand-edit).
- **CLI:** `scripts/governance/export_findings.py`
- **Chapter:** Ch.17.

### `hypothesis_registry.py`
- **Relevance:** LIVE · **Purpose:** H-id registry schema/validation; authority locked to research.
- **Seed/query:** `seed_hypothesis_registry.py`, `query_hypotheses.py`
- **Chapter:** Ch.17 / E2.

### `framework_registry.py`
- **Relevance:** LIVE · **Purpose:** Architecture component map (kernel/domain/style/…) as JSONL registry.
- **Seed/query/update:** `seed_framework_registry.py`, `query_registry.py`, `update_registry.py`
- **Chapter:** Ch.17.

### `script_registry.py` / `script_census.py` / `script_seed.py`
- **Relevance:** LIVE · **Purpose:** SITS — discover scripts, merge stubs/overlays, materialize `data/script_registry.jsonl`.
- **CLI:** `seed_script_registry.py`, `query_scripts.py`, `scripts/analysis/script_census.py` (+ matrix generators).
- **Chapter:** CLAUDE.md §3.1; conventions.

### `module_census.py` / `module_attribution.py`
- **Relevance:** LIVE · **Purpose:** Same idea as SITS for every `src/**/*.py` — ownership / attribution surface.
- **Chapter:** Ch.04 adjacent.

### Specialist / sidecar

| File | Relevance | Purpose |
|---|---|---|
| `bitnet_governance_executor.py` | SPECIALIST | BitNet-specific governance execution path |
| `expansion_integration.py` | SIDECAR | Wire expansion engine into governance loops |
| `reflection_buffer_advanced.py` | SIDECAR | Advanced reflection buffer for governance agents |
| `__init__.py` | LIVE | Package marker |

---

## 3. `scripts/governance/` — CLI encyclopedia (31 files)

### 3.1 Construction & promotion

| Script | Purpose | Danger |
|---|---|---|
| `construction_protocol.py` | Gate-6 BUILD_IMPACT_MANIFEST / validate-completion / check | WRITE policy enforcement |
| `promote_v2.py` | Thin multi-strategy promote CLI | **WRITES production configs** |
| `crt_config_construction_census.py` | ConfigBuilder / CRTConfig construction sites (F-057 observe) | READ-ONLY census |
| `behavioral_constant_authority_trace.py` | Behavioral constants on decision spine | READ-ONLY |

### 3.2 Registry seeds & queries

| Script | Purpose |
|---|---|
| `seed_hypothesis_registry.py` | Seed H-ids from curated ledger |
| `seed_framework_registry.py` | Seed framework registry |
| `seed_script_registry.py` | SITS seed + PRIMARY overlays |
| `export_findings.py` | Regenerate findings JSONL |
| `query_hypotheses.py` / `query_registry.py` / `query_scripts.py` | Read-only queries |
| `update_registry.py` | Append-only framework registry update |
| `framework_registry_report.py` / `framework_gap_audit.py` | Markdown reports from registry |

### 3.3 Feature DAG / FM governance

| Script | Purpose |
|---|---|
| `feature_certification_state.py` | Per-feature certification ledger seed/resolver |
| `feature_dag_certify.py` | Certify / promote / STALE cascade mutations |
| `feature_surface_query.py` | Read-only join API over feature surface artifacts |
| `build_fm_ownership_matrix.py` | FM ownership / consumer matrix generator |

### 3.4 Authority censuses & boundary scans

| Script | Purpose |
|---|---|
| `three_authority_surplus_census.py` | WHO/WHAT/HOW declaration surplus |
| `who_numeric_dependency_census.py` | WHO numeric threshold dependency census |
| `scan_runtime_boundary.py` | Kernel ↔ research import direction + promotion boundary |
| `scan_model_paths_literals.py` | Unauthorized `models/` path literals |
| `build_g001_consumer_attribution.py` | G001 consumer attribution package |

### 3.5 Decision packages / MSIP / RR freeze / zone remap

| Script | Purpose | Class |
|---|---|---|
| `build_crt_architecture_adjudication_v1.py` | CRT architecture adjudication package | OBSERVE package |
| `build_msip_shadow_design_contract_v1.py` | MSIP shadow design freeze package | design only |
| `build_msip1_verification_package.py` | MSIP-1 verification pack | OBSERVE |
| `patch_msip_shadow_design_consistency_v1.py` | Consistency patch for MSIP design pack | OBSERVE |
| `rr_l1_freeze_certificate.py` | RR L1 freeze certificate hash/assert | certificate |
| `remap_zone_registry_v4.py` | Zone registry schema v3→v4 remap | **WRITES model JSON** (one-shot) |
| `validation_access_cli.py` | VA-XAUUSD-M15 dual-surface access ladder | writes results packs |
| `_build_doc_tracking_index.py` | DOC_TRACKING_INDEX.xlsx metadata inventory | Excel write |

---

## 4. `scripts/analysis/` — census & probe clusters (115 files)

**Default stance:** OBSERVE_ONLY / diagnostic. Prefer governance feature-DAG tools for **mutations**; analysis scripts for **measurement**.

| Cluster | ~Count | Examples | Use when |
|---|---:|---|---|
| **Feature DAG / FM certification** | 15 | `feature_dag_layers.py`, `feature_math_lint.py`, `b2a_feature_candidate_certification.py`, FM drift/decision-flip probes | Feature surface hygiene, F-053/F-054 class |
| **CRT / state / parity** | 14 | funnel diagnostics, guard ablations, transition audits, soft-conf / shadow probes | CRT CLOSED boundary forensics |
| **RR / Gaussian / Zone / BitNet probes** | 10 | `rr_confidence_probe.py`, zone parity, gaussian/bitnet runners | Engine AUDITED lineage evidence |
| **XAUUSD / instrument forensics** | 9 | trade anatomy, timestamp gaps, phase1 validation | Instrument-specific audits |
| **Code map / wiring / matrices** | 7 | `gen_code_map.py`, `gen_pyan.py`, `generate_cli_matrix.py`, `generate_script_matrix.py`, `script_census.py` | Regenerate architecture/CLI maps |
| **Session / clock / normalization** | 5 | session certification, cost audit, override scoping | F-066 / session policy class |
| **Config / behavior census** | 2 | `config_reachability.py`, `behavior_census.py` | Config-first maturity (§6.5) |
| **Blind label / epistemic** | 2 | blind label sample/score | Epistemic / labeling studies |
| **Geometry census** | 1+ | `geometry_census.py` | Geometry family registry inputs |
| **Other / residual** | ~50 | pattern library, consensus sweeps, log compress, early invalidation A/B, detection sweeps, … | Read docstring; classify before reuse |

**Regenerate maps (safe, high-ROI):**

```text
scripts/analysis/gen_code_map.py
scripts/analysis/gen_pyan.py
scripts/analysis/generate_cli_matrix.py
scripts/analysis/generate_script_matrix.py
scripts/analysis/script_census.py   # often with --write-stubs for SITS
```

---

## 5. `scripts/maintenance/` — adjacent hygiene (9 files)

| Script | Purpose |
|---|---|
| `_compute_hash.py` | Recompute production config hash after `params` edits |
| `rotate_session_log.py` | Rotate `assistant_project.md` / workflow log |
| `check_session_log_commit.py` | Commit-hook session log presence |
| `check_governance_invariants.py` | Governance invariant checker |
| `check_consolidation_due.py` | Consolidation due probe |
| `cleanup_logs.py` / `reorganize_results.py` | Log/results hygiene |
| `fix_bom.py` | BOM fixes |
| `_promote_v4_bnb_cutover.py` | Historical cutover helper (danger: version-specific) |

---

## 6. Evidence ledger home (docs, not scripts)

E3 tools **read/write into** the evidence directory mapped in Ch.18:

| Cluster | Examples |
|---|---|
| Closure reports | `crt_closure_report.md`, feature surface closures |
| Lineage audits | `*_lineage_audit.md` |
| Certification ledgers | `feature_certification_ledger.jsonl`, DAG LATEST JSON |
| Measurement contract | `MEASUREMENT_CONTRACT.md` (still OPEN seals) |
| Construction protocol | `REPOSITORY_CONSTRUCTION_PROTOCOL.md`, `change_contracts.json` |
| MIAR | `MODEL_INTENT_AUTHORITY_REGISTER.md` |

---

## 7. Danger / authority flags

| Flag | Meaning |
|---|---|
| **PROMOTION_WRITE** | Can change active production config — human confirm required |
| **GENERATED_ONLY** | `data/*.jsonl` — regenerate from seeds/docs; never hand-edit as truth |
| **APPEND_ONLY** | Registries / promotion_log / certification ledger — no silent rewrite |
| **OBSERVE_ONLY** | Analysis probes must not change production behavior |
| **ONE_SHOT_MUTATION** | e.g. zone registry remap — archive + hash after |
| **ORPHANED_CHECK** | e.g. config_integrity may not gate runtime — still run in hygiene |

---

## E3 exit criterion

| Criterion | Status |
|---|---|
| Every `src/governance` module has a purpose row | **Met** (§2) |
| All `scripts/governance` listed by job cluster | **Met** (§3) |
| `scripts/analysis` clustered with regenerate shortlist | **Met** (§4) |
| Maintenance adjacency noted | **Met** (§5) |
| Per-file essay for all 115 analysis scripts | **Out of scope** (cluster index) |

---

## Next

- **E4** — Group B sidecars (`bitnet`, `utils`, `training`, `portfolio`, `replay`, …)  
- **E5** — Group C dormant one-liners  
- **E6** — Remaining non-research / non-governance scripts catalog  

---
**Related:** [Ch.16](../16-config-first-and-promotion.md) · [Ch.17](../17-truth-maintenance.md) · [Ch.18](../18-field-guide-governance.md) · [E1](E1-spine-implementation.md) · [E2](E2-research-utilities.md) · [Ch.24](../24-repository-encyclopedia.md)
