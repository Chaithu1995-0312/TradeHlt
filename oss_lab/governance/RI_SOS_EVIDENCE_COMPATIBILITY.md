# Gate: RI → Semantic OS Evidence Compatibility Test

| Field | Value |
|---|---|
| Gate id | `RI-SOS-COMPAT-V1` |
| Prerequisite | RI-QA-V1 lab PASS (`RI_QA_V1_MILESTONE_VERDICT.md`) |
| Status | **RUN COMPLETE** — canonical `RI-SOS-20260812T233000Z` → **`COMPAT_USEFUL_READ_ONLY`** (prior `…230000Z` had free-text SOS-id parse under-read) |
| Authority | RESEARCH_LAB_ONLY |
| Semantic OS mutation | **FORBIDDEN** (read-only evidence comparison only) |
| Production wiring | **FORBIDDEN** |

---

## Purpose

Answer one architectural question:

> Can Codebase-Memory supply **structural evidence** that materially improves Semantic OS reasoning **without** becoming a second semantic authority?

```text
             Codebase-Memory
                    │
                    │ structural facts (read-only)
                    ▼
             Evidence package
                    │
                    │ join / compare (no auto-write)
                    ▼
             Semantic OS (existing meaning)
                    │
                    ▼
                 Agent usefulness
```

**Not in scope:** automatic CN/BD/JN/CT/FileIdentity mutation; production MCP defaults; warm-latency optimization.

---

## Roles (frozen for this gate)

| System | Role |
|---|---|
| Codebase-Memory | Structural retrieval / call-import-define evidence |
| Semantic OS | Meaning, ownership, contracts, journeys (advisory) |
| OBJ / disk | Implementation last hop |
| Book / Encyclopedia | Architecture vs file map (context only) |
| Lab metrics | RESEARCH_LAB_ONLY; unsealed until explicitly sealed |

---

## Compatibility rules

1. **Read-only.** No writes under `docs/governance/semantic_os/*.yaml` during the test.  
2. **Evidence, not truth.** CBM outputs become candidate evidence rows, never CN/BD facts by default.  
3. **Fail closed on meaning.** If SOS is silent, answer is UNKNOWN/UNATTRIBUTED — do not invent meaning from structure.  
4. **Dual-direction required.**  
   - SOS → implementation (meaning to path)  
   - Implementation → SOS (path to meaning)  
5. **Negative controls required.** Nonexistent modules must not gain SOS meaning.  
6. **Authority score separate.** A correct structure that claims production authority fails authority correctness.  

---

## Measurement dimensions (score separately)

| Dimension | Question |
|---|---|
| **Structural correctness** | Are paths/symbols/edges real on disk / in index? |
| **Semantic correctness** | Does the *meaning* match SOS / ontology / charter when SOS speaks? |
| **Authority correctness** | Does the answer wrongly claim production/runtime authority? |
| **Negative-control correctness** | Nonexistent targets rejected; no fabricated SOS meaning |
| **Provenance quality** | Are sources (CBM edge, SOS id, OBJ path) explicit and separable? |
| **Retrieval usefulness** | Would an agent spend fewer tool calls / less confusion on the same question? |

**Do not collapse** these into a single “12/12 → integrate” score.

---

## Corpus

Machine corpus: [`../scenarios/ri_sos_compat_corpus_v1.json`](../scenarios/ri_sos_compat_corpus_v1.json)

Categories (at least one item each):

1. File identity  
2. Call / dependency relationship  
3. Journey reconstruction  
4. Boundary membership  
5. Contract implementation coverage  
6. CRT execution tracing  
7. Feature pipeline tracing  
8. Negative / nonexistent target  
9. Semantic OS lookup → implementation  
10. Implementation → Semantic OS meaning  

---

## Method (when executed)

For each corpus item:

```text
1. Query Semantic OS (hand registry + query surface if available)  → SOS_answer
2. Query Codebase-Memory (CLI, same isolation as RI-QA-V1)      → CBM_answer
3. Optionally query OBJ / graph.dot baseline                     → BASE_answer
4. Score six dimensions independently
5. Emit evidence rows (JSONL) — never write SOS YAML
```

Deliverables under `results/oss_lab/repo_intel/runs/RI-SOS-<utc>/`:

- `run_manifest.json`
- `compat_answers.jsonl`
- `dimension_scores.json`
- `report.md`

---

## Pass criteria (lab usefulness — not production authority)

A **useful evidence provider** result requires:

| Criterion | Bar |
|---|---|
| Structural correctness | High on SOS→impl and impl→path items |
| Negative-control correctness | 100% on fabricated targets |
| Authority correctness | 0 false authority claims |
| Semantic correctness | No CBM-invented meaning that contradicts SOS; UNKNOWN when SOS silent is OK |
| Usefulness | At least a qualitative “agent would benefit” judgment on ≥ N items (declare N at run time; default 5) |

**Integration into SOS still requires a separate governed program** (ingestion contract + human authoring of meaning). This gate only decides whether to **design** that contract.

---

## Explicit non-goals

- Warm-daemon latency ranking (defer)  
- Replacing FileIdentity / OBJ generation  
- Auto-authoring CN/BD from call graphs  
- Dual-running Infigraph in the same turn  

---

## Exit states

| State | Meaning |
|---|---|
| `COMPAT_USEFUL_READ_ONLY` | Proceed to design SOS ingestion contract (still no auto-mutate) |
| `COMPAT_STRUCTURAL_ONLY` | Keep as lab structural tool; weak SOS join value |
| `COMPAT_HARMFUL_AUTHORITY` | Do not integrate; authority confusion |
| `COMPAT_INCONCLUSIVE` | Expand corpus / re-run |

---

## Relation to Semantic OS contract

Preserves:

- Implementation last hop  
- Humans write meaning; machines write derived facts  
- Fail closed / UNKNOWN  
- Advisory authority only  

Codebase-Memory, if integrated later, would feed **L4 Evidence** joins — not redefine L1 Concept meaning.
