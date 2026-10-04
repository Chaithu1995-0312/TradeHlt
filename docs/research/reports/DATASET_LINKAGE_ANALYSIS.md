# BG-006 Dataset Linkage Prevalence

**Status:** OBSERVATION ONLY · READ-ONLY · NO AUTHORITY · NO PROMOTION  
**Date:** 2026-09-09  
**Commit:** `b5d06a2`  
**Question:** do contracts reference a dataset by *any* means, and does that reference resolve to a registered `DatasetIdentity`?

---

## 1. Scope

| Path | Read |
|---|---|
| `configs/research/measurement_contracts/` | 18 contract documents |
| `docs/governance/datasets/` | 2 DatasetIdentity records |
| `docs/governance/dataset_identity_registry.json` | the index (2 entries) |

**Location correction:** the episode proposal guessed DatasetIdentity instances lived under `configs/research/datasets/`. That directory holds **0 files**. The records are in `docs/governance/datasets/`, indexed by `dataset_identity_registry.json`.

## 2. Method

Pure read; one file written. Three resolution channels measured **separately**, because they answer different questions:

| Channel | What it looks for |
|---|---|
| **C1 typed key** | a declared field naming a dataset (`dataset_id`, `dataset_identity`, `dataset_ids`, `corpus_id`, `logical_corpus_id`, `dataset_ref`), searched recursively at any depth |
| **C2 content hash** | any 64-hex sha256 appearing anywhere in the document |
| **C3 path string** | any `data/…` or `results/…` `.csv` path |

C2/C3 occurrences are classified by the JSON field they sit in, because **not every hash in a contract is a dataset reference, and not every dataset reference is an inclusion**:

| Role | Field | Meaning |
|---|---|---|
| `CORPUS_INCLUSION` | `population.inclusion_rule` | the measured corpus |
| `CORPUS_EXCLUSION` | `population.exclusion_rule` | explicitly **not** the population |
| `NON_DATASET_ARTIFACT` | anywhere else | e.g. a cost-calibration manifest |

Without that classification a naive matcher would count an *exclusion* pin and a cost-manifest pin as dataset linkage. Both occur in this corpus.

## 3. Counts

**N = 18 contract documents.**

| Measure | Count | % of N |
|---|---|---|
| C1 — carries a typed dataset field | 0 | 0.0% |
| Carries any dataset reference (C2/C3) | 12 | 66.7% |
| — of which the **inclusion** corpus resolves to a registered DatasetIdentity | 9 | 50.0% |
| Reference present but resolves to nothing | 0 | 0.0% |
| No dataset reference at all | 6 | 33.3% |

**C1 = 0/18** — confirms BG-001's key-based result independently.

**C2 = 9/18** contracts pin a corpus sha256 that matches a registered DatasetIdentity. The linkage BG-001 reported as absent **exists de facto by content hash** — it is absent *de jure* (no typed field), not absent in fact.

### Reference strength

References are not equivalent. Graded by how much of the reference is load-bearing:

| Tier | Meaning | Count | % of N |
|---|---|---|---|
| **T1 hash-in-inclusion** | sha256 inside `population.inclusion_rule` resolving to a DatasetIdentity — content-addressed and part of the population definition | 9 | 50.0% |
| **T2 path-only** | the canonical path appears and resolves, but no resolving hash sits in `inclusion_rule` — names the file, does not pin its content | 3 | 16.7% |
| **T3 none** | no dataset reference of any kind | 6 | 33.3% |

T2 members: `MC-SUJAN-XAUUSD-M15-V1` (`drafts/`), `MC-SUJAN-XAUUSD-M15-V1` (`instances/`), `MC-CPR-L0-XAUUSD-M15-UTC-V1` (`measurement_contracts/`) — these name `data/mt5/XAUUSD_M15.csv` outside the population block, so the file is identified but its content is not pinned by the contract.

_Note: `MC-SUJAN-XAUUSD-M15-V1` exists in both `drafts/` and `instances/` and is counted once per file, so N counts documents, not distinct contract ids (17 distinct ids across 18 documents)._

T3 members: 6 documents — the 3 MP-* profiles (which carry no population block at all, per BG-001) plus 3 MC-* contracts.

## 4. Resolution matrix

### 4a. Hash inventory (contract side)

| sha256 | occurrences | roles | resolves to |
|---|---|---|---|
| `4d73f5cebe33ec91…` | 13 | CORPUS_INCLUSION×9, NON_DATASET_ARTIFACT×4 | `XAUUSD_MT5_PHASE1_20260521` |
| `478b075150935c95…` | 3 | CORPUS_EXCLUSION×2, NON_DATASET_ARTIFACT×1 | **unregistered** |
| `6ce4abf5cd76e37e…` | 2 | NON_DATASET_ARTIFACT×2 | **unregistered** |

### 4b. DatasetIdentity side

| dataset_id | canonical path | rows | decision_status | referenced by contracts |
|---|---|---|---|---|
| `XAUUSD_MT5_PHASE1_20260521` | `data/mt5/XAUUSD_M15.csv` | 47,275 | `FROZEN_CANDIDATE_PENDING_PHASE1_VALIDATION` | 13 |
| `XAUUSD_MT5_TVWINDOW_20260706_20260807` | `data/mt5/XAUUSD_W2026-07-06-to-2026-08-07.csv` | 2,300 | `UNRESOLVED` | 0 |

**Registered but referenced by no contract:** `XAUUSD_MT5_TVWINDOW_20260706_20260807`.

### 4c. The status of what resolves

- `XAUUSD_MT5_PHASE1_20260521` — `decision_status: FROZEN_CANDIDATE_PENDING_PHASE1_VALIDATION`.

The corpus the contracts actually pin is **not APPROVED**. Per `CORPUS_AUTHORITY.md`, `FROZEN_CANDIDATE_PENDING_PHASE1_VALIDATION` is a *scope freeze only* — it permits Phase-1 validation probes against the frozen object and explicitly does **not** grant AUTHORITATIVE / VALIDATED / ECONOMICALLY_ADMISSIBLE / APPROVED status. So the de-facto linkage resolves to a corpus that carries no corpus authority. This is an observation about status, not a defect claim: the contracts are research instruments and no APPROVED XAUUSD corpus exists to pin instead.

## 5. Non-claims

This analysis does **not** determine:

- that a hash match constitutes a *governed* reference — it is a content coincidence that happens to be load-bearing, not a declared, validated linkage;
- that the contracts intended to reference the DatasetIdentity record (the records were created independently; no contract names one);
- whether a typed `dataset_id` field ought to be added, or where;
- whether pinning a `FROZEN_CANDIDATE` corpus is correct or incorrect for research use;
- anything about the crypto corpora, which have no DatasetIdentity record at all;
- anything economic, or anything about `src/`, production config, or the live path.

No contract, registry, dataset record or schema was modified. No sidecar instance was created. Grants no authority (§6.5).

## 6. Recommended next observations

Observation proposals only; no architectural change is proposed.

1. **Hash-pin coverage across the whole research corpus.** The same content-hash channel that revealed this linkage could be run over `docs/current-findings.md` evidence paths and the MPA ledger, measuring how much of the repository's provenance is carried by hashes in prose rather than typed fields.
2. **Crypto corpus registration gap.** 4 anatomy instruments (BNB/BTC/ETH/SOL) underpin the entire L-003 package and have **no** DatasetIdentity record. Measuring what would be required to describe them is a bounded observation.
3. **Re-run after any new sealed contract or dataset record.** Both sides are moving denominators.

---

_Read-only. Contracts scanned: 18. DatasetIdentity records: 2. Distinct sha256 pins found in contracts: 3. No file other than this report was written._
