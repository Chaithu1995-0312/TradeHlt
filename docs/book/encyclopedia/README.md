# Repository Encyclopedia

> **Parent charter:** [Chapter 24 — Repository Encyclopedia](../24-repository-encyclopedia.md)  
> **Coverage report:** `grok/Book_PDF_File_Coverage_Grok.xlsx`  
> **Purpose:** File-level purpose, relationships, entry points, and relevance — complementing the architecture book (Ch.00–23), not replacing code.

## Status by phase

| Phase | Scope | Status | Document |
|---|---|---|---|
| **E0** | Charter + Groups A–D vocabulary | **DONE** | [Ch.24](../24-repository-encyclopedia.md) |
| **E1** | Group A spine implementation (`core`, `config_layer`, `runtime`, `execution`, `engines`, `live`, `inout`, `control_plane`) | **DONE** (file map) | [E1-spine-implementation.md](E1-spine-implementation.md) |
| **E1b** | Deep `src/features/` pipeline + registry (28 modules) | **DONE** | [E1b-features-registry.md](E1b-features-registry.md) |
| **E2** | Research utilities (`src/research/` 143 + `scripts/research/` 126) | **DONE** (index) | [E2-research-utilities.md](E2-research-utilities.md) |
| **E3** | Governance tooling (`src/governance` + gov/analysis/maintenance scripts) | **DONE** (index) | [E3-governance-tooling.md](E3-governance-tooling.md) |
| **E4** | Group B sidecars (~100 files: bitnet, utils, training, portfolio, …) | **DONE** | [E4-sidecar-modules.md](E4-sidecar-modules.md) |
| **E5** | Group C dormant / archived (~69 files + archive/) | **DONE** | [E5-dormant-modules.md](E5-dormant-modules.md) |
| **E6** | Remaining operator scripts (~70 outside research/gov/analysis/maintenance) | **DONE** | [E6-remaining-scripts.md](E6-remaining-scripts.md) |
| **JSONL** | Machine twin of all encyclopedia module rows | **GENERATED** | [encyclopedia_rows.jsonl](encyclopedia_rows.jsonl) |

**Series status:** E0–E6 + **E1b** + **JSONL twin** complete.

### Beyond documentation: Semantic Coverage

The encyclopedia answers “is the file indexed?” It does **not** answer “is every executable
behavior semantically covered?” That multi-dimension measurement lives here:

| Artifact | Role |
|---|---|
| [`docs/governance/SEMANTIC_OS_V1_DESIGN.md`](../../governance/SEMANTIC_OS_V1_DESIGN.md) | **Design authority** — FM-first Semantic OS v1 |
| [`docs/governance/SEMANTIC_OS_CONTRACT.md`](../../governance/SEMANTIC_OS_CONTRACT.md) | Charter / rules |
| [`docs/governance/semantic_os/contracts.yaml`](../../governance/semantic_os/contracts.yaml) | First-class **CT-*** contracts (PR-2, schema 1.1) |
| [`docs/governance/REPOSITORY_COVERAGE_DASHBOARD.md`](../../governance/REPOSITORY_COVERAGE_DASHBOARD.md) | Living multi-dimension scores |
| [`docs/governance/repository_coverage_dashboard.LATEST.json`](../../governance/repository_coverage_dashboard.LATEST.json) | Machine twin of the dashboard |
| `python scripts/governance/coverage_dashboard.py` | Regenerate (disk universe = denominator) |

**Dimensions:** physical · book · concept · boundary · journey · **behavior** · contract · authority · evidence · dependency · attribution.

Book explains architecture · Encyclopedia explains implementation · **Semantic OS explains meaning** · Dashboard measures understanding.

### Machine twin (JSONL)

| Item | Value |
|---|---|
| Artifact | [`encyclopedia_rows.jsonl`](encyclopedia_rows.jsonl) (~813 rows) |
| Regenerate | `python grok/build_encyclopedia_jsonl.py` |
| Validate | `python grok/build_encyclopedia_jsonl.py --check` |
| Schema (per line) | `id`, `path`, `kind`, `phase`, `group`, `relevance`, `purpose`, `package`, `classes`, `source_doc`, `book_status`, `bytes`, `generated_at` |

**Do not hand-edit the JSONL as sole truth** — regenerate from the builder (mirrors GENERATED tier discipline). Enrichment lives in the markdown encyclopedias + builder overrides.

## How to read an entry

Each significant file has:

| Field | Meaning |
|---|---|
| **Group** | A (core) · B (sidecar) · C (dormant) · D (scripts) |
| **Relevance** | LIVE · SIDECAR · DORMANT · ARCHIVED · OBSERVE_ONLY · PARTIAL |
| **Book** | CITED · DIR_ORIENTED · NOT_IN_BOOK (from coverage report) |
| **Purpose** | Why it exists |
| **Relationships** | Who calls it / what it calls |
| **Entry points** | CLI / tests / agent / control plane |
| **Chapter** | Architecture chapter if any |

**Code always wins** on conflict with this encyclopedia.

## Inventories used

- `results/analysis/src_business_functionality.xlsx`
- `scripts_business_functionality.xlsx`
- `grok/Book_PDF_File_Coverage_Grok.xlsx` (regenerate: `python grok/book_file_coverage_report.py`)
