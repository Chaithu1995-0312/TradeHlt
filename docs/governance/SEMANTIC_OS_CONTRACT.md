# Semantic OS Contract (v1)

**Status:** ACTIVE charter  
**Design:** [`SEMANTIC_OS_V1_DESIGN.md`](SEMANTIC_OS_V1_DESIGN.md)  
**Schema version:** `semantic_os/1.1` (CT-* first-class contracts shipped)  
**Authority:** `advisory` only — never production (§6.5)  
**Code wins** on conflict with this document.

---

## 1. Purpose

The Semantic Operating System is the **meaning interface** between the repository and LLM (or human) reasoning.

It does **not** replace:

- Runtime code or ACTIVE_VERSION config  
- Market ontology (feature mathematics)  
- Findings / promotion / book / encyclopedia  

It **does** provide:

- Concepts (why)  
- Boundaries (who owns which seam)  
- Journeys (what happens)  
- Contracts (what is guaranteed)  
- FileIdentities (what a module is called, rename-stable, and whether its filename still matches)  
- Generated Objects (where code lives)  

---

## 2. Fundamental rules

1. **Foundation-model-first.** Organize as Identity → Concept → Behavior → Relationships → Evidence → Governance → Implementation. Never as folders → files → Python first.  
2. **Implementation is the last hop.**  
3. **Humans write meaning; machines write derived facts.** Hand-authored derived fields are schema violations.  
4. **Fail closed.** Unknown concept/boundary/owner → empty join / UNATTRIBUTED / AMBIGUOUS — never fabricate.  
5. **Minimize entities.** Only CN, BD, JN, CT, FileIdentity, OBJ as first-class. Graphs are views.  
6. **CRT is structural language**, not a strategy. One structure, many consumers. Structural config ≠ consumer config.  
7. **Coverage measures understanding**, not documentation volume.  
8. **Append-only retirement.** SUPERSEDED / RETIRED; never silent delete.  

---

## 3. Entity summary

| Entity | Id | Hand? | Must include |
|---|---|---|---|
| Concept | CN-NNN | Yes | why, non-goals, invariants, failure_modes, evidence FKs |
| Boundary | BD-NNN | Yes | invariant_protected, members globs, owner, consumers |
| Journey | JN-NNN | Yes | ordered steps, concept+boundary per step, failure_mode from concept |
| Contract | CT-NNN | Yes (v1.1) | guarantees, non_guarantees, tests |
| FileIdentity | dotted slug | Tier 1/2 yes, Tier 3 no (v1.1) | semantic_name, physical_path, filename_semantic_status + reason, tier/confidence/provenance |
| Object | OBJ:path | No | Fully generated from disk |

---

## 4. Layer map (L0–L6)

| L | Name | Entity focus |
|---|---|---|
| L0 | Identity | Kind labels (Candle, Feature, Trade, …) |
| L1 | Concept | CN-* |
| L2 | Behavior | JN-* |
| L3 | Relationships | BD-*, CT-*, generated deps |
| L4 | Evidence | Findings, tests, research joins |
| L5 | Governance | Authority doctrine joins |
| L6 | Implementation | OBJ-* |

---

## 5. Documentation vs Semantic OS

| System | Explains |
|---|---|
| Book | Architecture |
| Encyclopedia | Implementation files |
| Semantic OS | Meaning (**repository** — L0–L6) |
| Coverage Dashboard | Measured understanding |

### 5.1 Orthogonal: market-episode reasoning (do not merge)

Semantic OS answers how an agent understands the **repository**.  
A separate ladder answers how an agent understands a **market episode**:

```text
VALUE → STATE → CONTEXT → SHAPE → CRT → TESTIMONY → AGREEMENT
```

That ladder is **not** L0–L6 renamed. CN/BD/JN/CT must not be asked to substitute for continuous STATE bands or a typed AGREEMENT object.

**Locked diagnosis + Phase 2A/2B/2C program:**  
[`EPISODE_SEMANTIC_INTEGRATION_PHASE2.md`](EPISODE_SEMANTIC_INTEGRATION_PHASE2.md)  
(D/L/I meaning grades; cliffs O6/O7/O18 → O11/O12 → O14; no new measurements.)

---

## 6. Scoreboard

Regenerate:

```text
python scripts/governance/coverage_dashboard.py
```

Artifacts:

- `docs/governance/REPOSITORY_COVERAGE_DASHBOARD.md`  
- `docs/governance/repository_coverage_dashboard.LATEST.json`  

Disk object count is always the denominator — never encyclopedia row count.

---

## 7. Enforcement

| Mechanism | Path |
|---|---|
| Hand registry validation | `src/governance/semantic_os.py` |
| Object generation | `src/governance/semantic_objects.py` |
| Tier-3 FileIdentity derivation | `src/governance/semantic_identity.py` |
| Seed projection | `scripts/governance/seed_semantic_os.py` |
| Query | `src/governance/semantic_query.py` |
| Closed claim grounding | `src/governance/semantic_grounding.py` · CLI `scripts/governance/query_semantic_os.py --ground` · agent `truth.ground_claim` |
| Workbook enrichment | `scripts/governance/enrich_workbooks_with_semantic_identity.py` |
| Tests | `tests/test_semantic_os.py`, `tests/test_semantic_identity.py`, `tests/test_semantic_identity_workbooks.py`, `tests/test_semantic_grounding.py`, `tests/test_semantic_query.py` |

---

## 8. Non-goals

- Replacing MIAR, closure index, or market ontology  
- Gating production trades  
- Auto-writing concepts from AST  
- Full knowledge-graph product platform  

---

## 9. Reopen / change

Changes to this contract require:

1. Design note in SEMANTIC_OS_V1_DESIGN (or superseding design)  
2. Validator + test updates  
3. Coverage dashboard re-run  
4. SESSION LOG  

---

## 10. Closed semantic environment (CT-008)

The repository is a **closed semantic environment** for LLM (and human) *repository claims*.

**Free:** reasoning, explanation, planning language, questions, and communication about
already-grounded records.

**Closed:** every repository **noun**, **relationship**, **implementation claim**, and
**evidence claim** must be grounded by a tool that returns an authority record. If the
tool returns `UNKNOWN`, `AMBIGUOUS`, or `UNANSWERABLE`, that is the answer. Do not invent
a CN/BD/JN/CT/FileIdentity/OBJ/FM/F-/H- id, a join, a symbol, or a finding.

| Claim kind | Grounder entry | Authority examples |
|---|---|---|
| NOUN | `SemanticGrounder.ground("NOUN", token)` | Semantic OS YAML, ontology ids, findings, closure surfaces, L0 identity kinds, ACTIVE_VERSION, disk paths |
| RELATIONSHIP | `ground("RELATIONSHIP", rel, source=, target=)` | Closed `RELATION_KINDS` only; both endpoints must already ground |
| IMPLEMENTATION | `ground("IMPLEMENTATION", path, symbol=)` | Disk + AST; FileIdentity / OBJ enrich when present |
| EVIDENCE | `ground("EVIDENCE", token)` | `docs/current-findings.md`, hypothesis JSONL, closure index, `tests/*.py` on disk |
| JSONL | `ground("JSONL", token, relation="CC-*", source=, target=)` | `docs/governance/jsonl_claim_catalog.yaml` — the closed CAN/CANNOT vocabulary |

### 10.1 JSONL claims and the fifth status (`REFUSED`)

A JSONL file existing is not a fact about the market. `kind=JSONL` answers a narrower question —
**may this stream CLOSE this claim?** — and `relation` is **required**: it must name a `CC-*` class
in the claim catalog. A missing relation is `UNANSWERABLE`, because catalog existence is not a
check.

`REFUSED` is the fifth closed status and is **not** a flavour of `UNKNOWN`. "Outside the
vocabulary" and "inside the vocabulary, and forbidden for this claim" are different facts, and
collapsing them would let a caller that checks only `GROUNDED` treat a contaminated stream as
evidence — the F-079 silent-gap class. A `REFUSED` result carries `refusal_class`, the `CC-*` id
that forbids the claim.

Four mechanical rules:

1. **Relation required.** No `CC-*`, no answer (`UNANSWERABLE`).
2. **Join is evaluated first.** Two individually-true lines joined illegally is still a
   hallucination, so a forbidden join refuses *before* any CAN can ground (F-069).
3. **`CANNOT` always refuses** — a stream's `forbidden_cc` list is documentation, not a gate.
4. **A `CAN` aimed at the wrong stream is `UNANSWERABLE`**, never a silent ground.

Cataloguing a stream does **not** identify it: `catalog_stream_status` is the identity-contract
§11 census label and is never an `identity.check` `CheckResult.status` (`PRESERVED` never appears
on this surface). Nothing here stamps the frozen L0–L5 primary keys onto historical JSONL (§12.3).

CLI:

```text
python scripts/governance/query_semantic_os.py --ground --kind NOUN --token CN-001
python scripts/governance/query_semantic_os.py --ground --kind IMPLEMENTATION --token src/core/engine_runner.py --symbol EngineRunner
python scripts/governance/query_semantic_os.py --ground --kind EVIDENCE --token F-048
python scripts/governance/query_semantic_os.py --ground --kind JSONL --token logs/crt_transitions.jsonl --relation CC-L3-GLOBAL-UNIDENTIFIED
python scripts/governance/query_semantic_os.py --ground --kind JSONL --relation CC-FINDING-EXPORT --source producer:engine --dest producer:resolver
```

For `--kind JSONL` the token is passed **as-is** (an omitted `--token` is legal for a join-only
call); every other kind keeps the historical `--token or --relation` coalesce.

Agent tool: `truth.ground_claim` (read-only) — read `grounding_status`, not the envelope `status`,
which is always `"ok"`. Contract: **CT-008**, refined in place. Protocol hook: CLAUDE.md §6.7.
Spec: `docs/governance/JSONL_CLAIM_SURFACE.md`.

This is **not** a semantically-executable trading OS. It does not close inventory gaps by
fabrication. Advisory only (§6.5).

---

_Charter for Semantic OS v1. Detailed design: SEMANTIC_OS_V1_DESIGN.md._
