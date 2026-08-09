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
| Semantic OS | Meaning |
| Coverage Dashboard | Measured understanding |

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
| Workbook enrichment | `scripts/governance/enrich_workbooks_with_semantic_identity.py` |
| Tests | `tests/test_semantic_os.py`, `tests/test_semantic_identity.py`, `tests/test_semantic_identity_workbooks.py` |

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

_Charter for Semantic OS v1. Detailed design: SEMANTIC_OS_V1_DESIGN.md._
