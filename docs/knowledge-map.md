# Knowledge Map — How the Record Systems Connect

> **What this is.** The navigation hub for the repo's *knowledge corpus*: the handful of record
> systems that together answer "what exists, what happened, what was planned, what we proved, and
> why." Read this to know **which doc to open for which question** and **how to traverse between
> them** — without grepping the whole tree. This is an LLM-reference doc; CLAUDE.md only points here.
>
> Created: 2026-06-05 · Updated: 2026-09-03
>
> **See also:** [`timeline.md`](timeline.md) (the date-join) · [`current-findings.md`](current-findings.md) · [`plans/readme.md`](plans/readme.md) · [`analysis/readme.md`](analysis/readme.md) · [`topics/readme.md`](topics/readme.md) · [`architecture/target-strategy-architecture.md`](architecture/target-strategy-architecture.md) (target strategy vs market semantics + not-yet-built checklist)

## The record systems (which doc owns which question)

| System | Entry point | Authoritative for | Open it when you ask… |
|---|---|---|---|
| **SESSION LOG** | [`../assistant_project.md`](../assistant_project.md) | *What was actually done*, dated, append-only (the spine) | "what happened on/around date D?" / "what did we last do?" |
| **Plans** | [`plans/readme.md`](plans/readme.md) | *What was planned/designed* (point-in-time design records, 64 plans) | "was X planned? what was the design / was it shipped or killed?" |
| **Analysis** | [`analysis/readme.md`](analysis/readme.md) | *Point-in-time studies & audits* (evidence; **not** current truth) | "what did the study on X measure?" / "where's the evidence for a finding?" |
| **Findings** | [`current-findings.md`](current-findings.md) | *Current validated conclusions* `F-0xx` + Funding Ledger | "what do we already know about X? what's funded/killed?" |
| **Research candidates (H-*)** | [`../scripts/governance/seed_hypothesis_registry.py`](../scripts/governance/seed_hypothesis_registry.py) (PRIMARY) · generated `data/hypothesis_registry.jsonl` | *Falsifiable statements that must not be forgotten and must not auto-promote.* `authority` is pinned `research`. Status `validated`/`frozen` is **not** a production model. Promotion is only M4 QualificationGate → ConfigValidator → PromotionManager. Schema **rejects** `promotion_requirements` / `min_delta_g001`. | "is this observation a candidate? is it eligible to trade? what is still missing?" |
| **Research families** | [`governance/research_family_registry.json`](governance/research_family_registry.json) | *Which market objects were researched, and which of the six questions L0–L5 was asked of each* — an atlas of **questions and gaps**, explicitly **not** of answers (a cell records that work happened, never that its conclusion holds) | "what has been researched about object X? which layer is unanswered? where are the explicit gaps?" |
| **Codebase structure** | [`architecture/code-map.generated.md`](architecture/code-map.generated.md) (authoritative tree) · [`architecture/codebase-state-map.md`](architecture/codebase-state-map.md) (role per pkg) · [`architecture/entry-exit-map.md`](architecture/entry-exit-map.md) (I/O surface) · [`architecture/model-design-intent.md`](architecture/model-design-intent.md) (why each model exists — design intent, not implementation) | *What packages/modules exist, what each is for, how it's invoked & what it emits* | "where does this change land? what's package Y for? how is the app called / what does it write?" / "why does model X exist?" |
| **Topics** | [`topics/readme.md`](topics/readme.md) | *Concept ↔ code ↔ tests ↔ validations* (per concept) | "give me the grounded picture of concept X" |
| **Timeline** (the join) | [`timeline.md`](timeline.md) | *Date → milestone → SESSION LOG → plan → finding* in one table | "what changed when, and why?" |
| **Research substrates** (frozen datasets) | `../results/research/{bnbusdt,btcusdt,ethusdt,solusdt}_trade_anatomy/README.md` (BNB is the schema reference: [`bnbusdt`](../results/research/bnbusdt_trade_anatomy/README.md)) | *Canonical per-trade datasets for downstream research, one per crypto major* (sha256-pinned, regenerate-don't-edit) | "what's the canonical {coin} trade-behavior dataset (survival/clustering/ML)?" — see F-022/023/024 + `docs/analysis/cross-instrument-anatomy-2026-06-13.md` |
| **Config / registry authorities** | [`governance/config_authority_matrix.md`](governance/config_authority_matrix.md) | *WHO/HOW/WHAT + 14 Sources + field-level authority matrix* (observational; not a fourth peer layer) | "which file owns this threshold / registry active flag / formula? what's descriptive vs executable?" |
| **Target strategy architecture** | [`architecture/target-strategy-architecture.md`](architecture/target-strategy-architecture.md) | *Target framing: market semantics vs strategy knobs, research/live split, BitNet role, Strategy Registry, ledger, not-yet-built checklist* (not runtime authority) | "what is the target strategy system? what is structural vs configurable? what is not built yet?" |
| **Model runtime alignment** | [`governance/model_lineage_rollup.md`](governance/model_lineage_rollup.md) (cross-model rollup) · per-family: [`gaussian`](governance/gaussian_lineage_audit.md) · [`zonegate`](governance/zonegate_lineage_audit.md) · [`rr`](governance/rr_lineage_audit.md) · [`bitnet`](governance/bitnet_lineage_audit.md) · [`tradenet`](governance/tradenet_lineage_audit.md) | *Does the runtime load the artifact the registry declares and the trainer produced* (latest vs active vs loaded, per model) | "is model X's checkpoint stale? what does the spine actually load? should active_models.yaml change?" |
| **Layer identity (L0–L5)** | [`governance/CANONICAL_LAYER_IDENTITY_CONTRACT.md`](governance/CANONICAL_LAYER_IDENTITY_CONTRACT.md) (**Phase 1 CLOSED**, FROZEN v1.0.0, user-accepted 2026-08-23; `CH-occupancy-series-identity` 2026-09-05 names L3 series lineage, PK unchanged) · predecessor census [`analysis/feature_state_lineage_census.md`](analysis/feature_state_lineage_census.md) (what exists today, not identity) | *Equality* of OHLC, Feature Values, Feature States, CRT States, Geometry, Outcome — primary keys, lineage keys, immutability (`RECOMPUTE != RECOVER`), schema versioning, archive. L3 **bar occupancy PK** ≠ **`occupancy_series_identity`** (series lineage: producer + topology + track + corpus_sha256 + run_id; `constructor_id` / `config_hash` are reproducibility lineage, not PK). Not storage. | "are these two records the same object?" / "which occupancy *series* was measured?" |
| **Corpus / Dataset Identity** | [`governance/CORPUS_AUTHORITY.md`](governance/CORPUS_AUTHORITY.md) (`DATASET_IDENTITY_STATUS = FROZEN` v1.0.0) · R3 v1 CH-dataset-identity-r3-v1 · record [`governance/datasets/XAUUSD_MT5_PHASE1_20260521.json`](governance/datasets/XAUUSD_MT5_PHASE1_20260521.json) · CAD-* archive still `SYMBOL_TIMEFRAME` | Dataset Identity is the authority; M15 is the canonical admitted artifact; H1/H4/D1/W1/MN1 are **direct projections** (star). Native HTF CSVs FORENSIC. Parent CRT = `derived_h4`. R3 admission: `dataset_registry.admit_csv_path` (bound datasets); unbound path-passthrough. `BC-1_INFRASTRUCTURE = IMPLEMENTED`; `BC-1_CLOSURE = NOT_GRANTED` (`Construction ≠ Closure`). Not APPROVED. OHLCV still BLOCKED:BC-1..BC-6. | "which file is the truth for XAUUSD M15?" / "is H4 a second corpus?" / "does Parent CRT load XAUUSD_H4.csv?" (no) |
| **Storage preservation (L0–L5)** | [`governance/STORAGE_PRESERVATION_CONTRACT.md`](governance/STORAGE_PRESERVATION_CONTRACT.md) (**Phase 2 CLOSED**, FROZEN v1.0.0, user-accepted 2026-08-23; subordinate to identity) | *What must be preserved so the same object can be recovered* — Store→Load→Identity Check, per-layer persist+validate rules, all-six admissibility, load-time fail-closed, archive preservation, failure modes. Not a store. | "does a proposed store recover exact L0–L5?" |
| **Physical storage architecture** | [`governance/PHYSICAL_STORAGE_ARCHITECTURE.md`](governance/PHYSICAL_STORAGE_ARCHITECTURE.md) (Phase 3 **CLOSED**, Admissibility **PASS**, user-accepted 2026-08-23) | File-backed identity-addressed store in three classes: A declaration snapshots, B identity records, C tracked bindings. Occupancy stored, not folded. Identity Check is the only load. Code: `src/identity/`. Phase 5 query: `IdentityQuery` (PRESERVED-only joins). Executed CRT closes (this corpus/basis): [`governance/xauusd_identity_certification_2y.md`](governance/xauusd_identity_certification_2y.md) — 4-of-4 L5 frozen 2026-08-23; M15 structural tradeability stays F-086. | "does this architecture violate the frozen contracts?" (no) / "can Identity Check load without recompute?" (Phase 4/5 floor: `tests/test_identity_store.py`) / "what CRTEngine actually closed on the 2-year XAUUSD cert?" |
| **Gitignore schema (occupancy vs identity)** | [`governance/GITIGNORE_SCHEMA.md`](governance/GITIGNORE_SCHEMA.md) (`CH-gitignore-schema-v1`) · pin [`../tests/test_gitignore_schema.py`](../tests/test_gitignore_schema.py) · Class C dir [`governance/identity_bindings/`](governance/identity_bindings/) | What git may carry (TRACKED_CODE / TRACKED_MEANING / TRACKED_BINDING) vs local occupancy (LOCAL_BLOB / LOCAL_MODEL / LOCAL_RUN / LOCAL_TELEMETRY / LOCAL_IDENTITY). Operationalizes `RECOMPUTE != RECOVER` at the clone boundary. **Does not** put INV-050…053 lineage in git. MIXED_RESIDUE (`models/` 32 tracked, `reports/` 126 tracked) is named, not silently untracked. | "why doesn't a clone have the OHLC→outcome chain?" / "where do hashes live vs bytes?" / "may I commit `data/` or `logs/`?" (no) |

## How they connect

```
                         assistant_project.md  (SESSION LOG — the spine: every work unit, dated)
                                   │  cites, in its entries:
            ┌──────────────────────┼───────────────────────┬─────────────────────┐
            ▼                      ▼                       ▼                     ▼
      docs/plans/            docs/analysis/         current-findings.md     code/structure
   (the design behind     (the studies a plan      (verdicts; each F-0xx    (what the work
    a session's work)      produced as evidence)    cites analysis as        changed)
            │                      ▲   ▲                Evidence) ───────────────┘
            └── produce ───────────┘   └──── findings cite ──┘
                                   ▲
                         docs/timeline.md  (re-joins SESSION LOG + plans + findings by DATE)
```

- **SESSION LOG is the spine** — but traversal succeeds for a minority of entries, so treat it as the
  first place to look rather than a guaranteed path. An entry is *meant* to be dated and to cite the
  plan it executed, the analysis it produced, and the finding it validated. Measured
  ([`docs/analysis/research-dag-provenance-2026-08-26.md`](analysis/research-dag-provenance-2026-08-26.md)):
  **51% of entries cite no typed ID of any kind**, **63.3%** of session-decision provenance edges are
  UNKNOWN, and **60 entries carry no parseable `Date:`**. To reconstruct a change, start here (or at
  the timeline) and expect to fall back to git history when the citation is absent.
- **`timeline.md` is the temporal join** — the same edges as the spine, but indexed by date for "what
  changed when." It links SESSION LOG ↔ plans ↔ findings (not analysis directly — reach analysis via a
  finding's `Evidence:` field).
- **Findings → Analysis is the evidence edge.** A finding (`current-findings.md`) is a *conclusion*; its
  `Evidence:` field points to the `docs/analysis/` study that proved it. Go finding → analysis for proof.
- **Plans → Analysis/Findings is the causal edge.** A plan proposes work; the SESSION LOG entry that
  executed it records the analysis/finding it produced. Plans don't back-link individually (use the
  timeline row or the SESSION LOG entry for that date to bridge plan ↔ analysis ↔ finding).
- **Structure maps are current truth** for "what exists"; **analysis is history** (point-in-time).

## Traversal recipes

| You want… | Path |
|---|---|
| What changed, when, and why | [`timeline.md`](timeline.md) → pick a date row → follow to its plan / finding |
| Everything we did on a date | [`../assistant_project.md`](../assistant_project.md) (SESSION LOG, newest-first) |
| Why we believe X (with proof) | [`current-findings.md`](current-findings.md) → `F-0xx` → its `Evidence:` → the [`analysis/`](analysis/readme.md) study |
| What was planned for X (shipped?) | [`plans/readme.md`](plans/readme.md) → plan row (Status) → its SESSION LOG date in [`timeline.md`](timeline.md) |
| What a package is for / where code lives | [`architecture/codebase-state-map.md`](architecture/codebase-state-map.md) §1; full tree → [`architecture/code-map.generated.md`](architecture/code-map.generated.md) |
| Grounded picture of a concept | [`topics/readme.md`](topics/readme.md) → the concept's topic doc |
| Is an idea already funded/killed | [`current-findings.md`](current-findings.md) → Funding Ledger |
| Extract Sujan CRT without mutating it | [`governance/SUJAN_CRT_IDENTITY_EXTRACTION_SYSTEM.md`](governance/SUJAN_CRT_IDENTITY_EXTRACTION_SYSTEM.md) → [`.grok/SUJAN_ACCEPTED.md`](../.grok/SUJAN_ACCEPTED.md) (steelman, **not** identity) → transcripts. SEM-031 / F-095 are a projection and its test, not Sujan |

## Visibility coverage (what docs alone give you)

How much of the codebase is recoverable from docs **without reading source**. Two honest halves:
**navigational** visibility (what exists / where / what-for / how it flows) is driven to ~100% and
guarded by tests; **implementation-logic** visibility is intentionally *not* replicated in docs — docs
point to the code that holds it (the anti-rot rule). Last assessed 2026-06-05.

| Dimension | Coverage | Authoritative doc(s) |
|---|---|---|
| Folder / package structure | ~100% | `architecture/code-map.generated.md` (+ `graph.dot`), `codebase-state-map.md` §1 (32/32 pkgs, test-guarded) |
| Module-level roles | **100% (213/213 have docstrings)** | `architecture/module-roles.generated.md` (regenerated from module docstrings) |
| Runtime / decision flow | ~90% | `architecture/signal-flow.md`, `event-taxonomy.md` |
| Data shapes / schemas | ~90% | `reference/schemas.md` (38-dim canonical) |
| Config surface | ~90% | `reference/config-reference.md` |
| Validated truths / economics | ~90% | `current-findings.md` (F-001..F-012 + Funding Ledger) |
| History / "what changed when" | ~90% | `timeline.md`, `plans/readme.md`, SESSION LOG |
| Concept deep-dives (topics) | ~100% of live + key offline | `topics/readme.md` (live spine + Tier-2; Tier-3 flagged DORMANT) |
| Code-location citations | durable where present | `architecture/citation-map.generated.md` (`path:line · Symbol`, test-guarded) |
| **Implementation logic inside functions** | **~30% (by design)** | **read the source the docs point to — not duplicated in docs**; intent-vs-code verdicts: [`analysis/intent-vs-code-reconciliation-2026-06-05.md`](analysis/intent-vs-code-reconciliation-2026-06-05.md) + findings |

Drift is held by tests: `test_codebase_structure_doc.py` (every pkg documented), `test_doc_citations.py`
(every citation resolves), `test_topic_docs.py` (topic floor), `test_current_findings.py` (findings fresh).

## Foundational analysis (historical, partly orphaned)

A few early, **undated** analyses predate the living-doc era and are reachable only via
[`analysis/readme.md`](analysis/readme.md) (treat as history, not current truth):
`codebase-analysis.md` (snapshot 2026-04-22, **stale / pre-migration** — for current structure use the
maps above), `runtime-logic-analysis.md`, `integration-audit.md`, `command-source-audit.md`,
`discovery-funnel-analysis.md`, `performance-improvement-plan.md`. The analysis index is their single
entry point; consult them for original context, not present state.
