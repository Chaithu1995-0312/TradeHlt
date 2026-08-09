# Chapter 18 — A Field Guide to docs/governance/

**Part VI — Governance**
Status of this chapter: Orientation-level

## Why this chapter exists

`docs/governance/` has roughly 250 files — by far the largest single documentation subtree in the
repository. Chapters 16 and 17 already gave you the *doctrine* (Config-First, Truth Maintenance,
Closure & Authority). This chapter is different in kind: it's a map of the directory itself, so that
when you land in it — chasing a citation from another chapter, or investigating a specific
subsystem's audit trail — you know which cluster you're in and what kind of document to expect.

## What problem it solves

Without a map, `docs/governance/` reads as an undifferentiated pile of dated JSON+MD pairs. It
isn't — it's several distinct evidence ledgers, each with its own internal logic, that happen to
share a directory.

## What you need to already know

[Chapter 17](17-truth-maintenance.md) — nearly everything in this directory is either a closure
artifact, a lineage audit, or a certification record in that chapter's sense.

## The idea

### This is mostly an evidence ledger, not narrative documentation

The distinction from [Chapter 3](03-how-this-book-fits.md) matters most here: most of
`docs/governance/` is machine-oriented certification/evidence material — dated, often paired
JSON+MD, produced by a specific audit or census run — not curated prose meant to be read start to
finish. Treat this chapter as a directory of *drawers*, not a table of contents to read in order.

### The clusters

- **Promotion / production lifecycle.** The mechanics are [Chapter 16](16-config-first-and-promotion.md)'s
  territory; this directory holds supporting evidence like `IMPLEMENTATION_VALIDATION_V1.md`.
- **Closure reports.** End-of-thread declarations for a specific boundary — `crt_closure_report.md`
  ([Chapter 8](08-crt-state-machine.md)'s primary source), `canonical_feature_code_surface_closure-2026-07-11.md`,
  various `feature_pipeline_*_closure_manifest` and `feature_surface_closure_audit` pairs.
- **Lineage audits.** Does the runtime actually load the artifact its registry claims to, and did
  the trainer actually produce it honestly — one file per model family:
  `gaussian_lineage_audit.md`, `zonegate_lineage_audit.md`, `rr_lineage_audit.md`,
  `bitnet_lineage_audit.md`, `tradenet_lineage_audit.md`, plus a cross-model `model_lineage_rollup.md`.
  These are [Chapter 10](10-four-scoring-engines.md) and [Chapter 11](11-fusion.md)'s primary evidence.
- **Epistemic integrity / adjudication.** `EPISTEMIC_INTEGRITY.md` ([Chapter 17](17-truth-maintenance.md)'s
  primary source) plus dated adjudication records where two or more authorities disagreed and the
  disagreement had to be formally resolved (e.g. `three_authority_drift_adjudication-2026-07-11.md`,
  `geometry_semantic_adjudication.jsonl`).
- **Ontology / market-ontology contracts.** `MARKET_ONTOLOGY_EVOLUTION_CONTRACT.md`
  ([Chapter 6](06-market-ontology.md)'s primary source), plus formula- and geometry-specific
  contracts (`crt_formula_contract.md/json`, `geometry_family_registry.json`).
- **Measurement contract.** `MEASUREMENT_CONTRACT.md` and its schema — a frozen, not-yet-implemented
  program for making research claims formally comparable (see [Chapter 19](19-research-programs.md)).
- **Feature-DAG / FM certification.** A large cluster tracking the certification status of
  individual feature-math (`FM-0NN`) nodes as they climb the ontology's refinement ladder
  ([Chapter 6](06-market-ontology.md)) — `feature_dag_layers-*`, `feature_certification_ledger.jsonl`,
  per-feature certification files.
- **CRT-specific census/diagnostic artifacts.** `crt_executable_surface.md/json`,
  `crt_executable_state_graph.md/json`, `CRT_CONFIG_CONSTRUCTION_PROTOCOL.md`, and dated funnel/
  fail-reason diagnostics — deep supporting evidence for [Chapter 8](08-crt-state-machine.md).
- **OHLCV corpus authority.** A dated 2026-07-10 cluster establishing exactly what the raw candle
  corpus is, its lineage, and its temporal semantics — `CORPUS_AUTHORITY.md` plus census/closure/
  contradiction/fingerprint artifacts. Supporting evidence for [Chapter 5](05-data-ingestion-no-lookahead.md).
- **MSIP (Market State Interpretation Platform).** See the dedicated brief below (Grok review pass).
- **Script inventory / authority.** `script_canonical_allowlist.json`,
  `MODEL_INTENT_AUTHORITY_REGISTER.md` — governs which scripts are recognized, registered surfaces
  (referenced by `CLAUDE.md` §3.1's SITS registration requirement).
- **Documentation governance itself.** `DOCUMENTATION_DRIFT_PROTOCOL.md` ([Chapter 17](17-truth-maintenance.md)'s
  primary source), plus `finding_dependency_audit.md` and `user-progress-registry.md`.
- **Ten packaged decision-bundle subdirectories** (`build_manifests/`, `crt_architecture_adjudication_v1/`,
  `msip_shadow_design_v1/`, `rr_l1_freeze/`, `xauusd_crt_baseline_trace/`, and others) — self-contained
  evidence packages for a specific past decision, not meant to be browsed loose.

### MSIP brief — Market State Interpretation Platform (Grok review pass)

MSIP is large enough that earlier drafts deferred it to A2. It does **not** replace CRT; it is a
**shadow / observational** representation layer for continuous market state, designed to answer
whether state vectors carry information *beyond* CRT lifecycle labels — without earning production
cutover by existing.

| Piece | Role |
|---|---|
| Design contract | `docs/governance/MSIP_SHADOW_DESIGN_CONTRACT_V1.md` (+ packaged bundle under `msip_shadow_design_v1/`) |
| Implementation plan | Shadow plan reviewed under G-PLAN-01; implementation only after explicit G-IMPL-01 owner OPEN |
| Code surface | `src/msip/` — `market_state_vector.py`, `interpretation_config.py`, `shadow_emitter.py`, `disagreement.py`, `isolation.py` |
| Shadow driver | Research scripts such as `run_msip_shadow.py` (observational; CRT path untouched when shadow off) |
| Hypotheses | H-MSIP-001 / H-017 (micro matched-subpopulation SUPPORTIVE, research-only); H-MSIP-002 / H-018 (MATCHING_DEPENDENT robustness) |
| Whole-representation prereg | `MSIP_WHOLE` series — design/prereg work has been **parked** pending owner un-park; no production authority |

**Status vocabulary (honest):** infrastructure for shadow observation is **implemented**; several
gates (e.g. G-SHADOW-01) have been declared on specified XAUUSD populations; **threshold change,
migration, concurrency, and production cutover remain NOT_AUTHORIZED**. Findings from MSIP
hypotheses are research-only micro effects or matching-dependent results — they do **not** reopen
CRT's CLOSED mechanism boundary and do **not** grant fusion weight ([Chapter 16](16-config-first-and-promotion.md)
Authority Ladder).

A full MSIP chapter (hypothesis ladder, gate names, evidence packages) remains optional future book
work; this brief is enough to stop treating MSIP as an undocumented mystery.

### How to actually use this directory

Don't browse it top-down. Arrive with a specific question — "is Gaussian's model artifact actually
loaded correctly," "what does the CRT closure boundary formally cover," "why is `rr_fusion`
disabled" — and use [Chapter 17](17-truth-maintenance.md)'s Closure & Authority Index or
`docs/current-findings.md`'s `Evidence:` fields to find the specific file. This directory rewards
targeted lookup, not linear reading.

## Classification

| Concept | Status |
|---|---|
| `docs/governance/` as a whole | Production evidence ledger — actively maintained, test-guarded per-cluster |
| Individual clusters | Mixed — closure reports and lineage audits are authoritative for their narrow boundary; census/diagnostic artifacts are point-in-time evidence, not living truth |

## Authoritative sources

- The clusters listed above, by name, are the entry points — there is no single index file for this
  directory beyond `docs/current-findings.md`'s `Evidence:` cross-references and the Closure &
  Authority Index in [Chapter 17](17-truth-maintenance.md).

## Unresolved questions

- **MSIP full chapter (optional)** — the brief above covers design posture and authority bounds; a
  deeper chapter (every gate id, every H-MSIP run artifact) remains future book work only if MSIP
  re-enters active execution. Tracked in [A2](A2-unresolved-questions.md).
- This chapter's cluster list is a first-pass grouping, not an exhaustive index of all ~250 files —
  a future deepening pass could build a proper searchable index if that turns out to be worth the
  maintenance cost (weighed against `CLAUDE.md` §6.2 rule 5's "minimize doc count").

---
**Previous:** [Chapter 17 — Truth Maintenance](17-truth-maintenance.md) · **Next:** [Chapter 19 — The Research Programs](19-research-programs.md)
**Related:** [Chapter 06](06-market-ontology.md), [Chapter 08](08-crt-state-machine.md), [Chapter 10](10-four-scoring-engines.md) (the chapters whose primary evidence lives in this directory)
**Memory:** `docs/memory/governance-memory.md`.
