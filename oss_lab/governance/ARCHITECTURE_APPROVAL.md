# OSS Lab — Architecture Approval

| Field | Value |
|---|---|
| Status | **ARCHITECTURALLY APPROVED** |
| Implementation | **Safely staged** (scaffold + registry + stubs) |
| Blocked on | Optional next: SLSA tool residual; **ingestion contract design** only after usefulness review (first run complete) |
| Authority | RESEARCH_LAB_ONLY — no production authority |
| Approved | 2026-08-12 (design consensus) |
| Semantic OS mutation | **FORBIDDEN** until post-benchmark ingestion design |

---

## Approved architecture

```text
                         oss_lab/
                            │
              ┌─────────────┴─────────────┐
              │                           │
       TRACK A — EXECUTION         TRACK B — REPO INTEL
              │                           │
       XAUUSD M15                    repository
              │                           │
       engine adapters              OSS adapters
              │                           │
 BenchmarkTradeRecord          StructuralFactRecord
              │                           │
       CanonicalMetrics          structural facts
              │                           │
              ▼                           ▼
        Evidence layer        (future) Semantic OS ingestion
```

### Semantic boundary (load-bearing)

```text
Codebase-Memory / Infigraph
        ↓
"What is structurally connected?"

Semantic OS
        ↓
"What does that connection mean?"
```

**External measurement can inform the system; it cannot silently become system truth.**

---

## Approved decisions (frozen for this initiative)

| # | Decision | Rationale |
|---|---|---|
| 1 | One `oss_lab/`, two evidence tracks | No second lab package |
| 2 | `StructuralFactRecord` separate from `BenchmarkTradeRecord` | Repo intel is not trading-specific |
| 3 | No live Semantic OS YAML writes during evaluation | Evidence first; ingestion is a separate governed step |
| 4 | Codebase-Memory first; Infigraph H2H only | Avoid dual overlapping graph systems |
| 5 | LEAN = independent execution laboratory | Mechanics only; not semantic spine |
| 6 | VectorBT deferred | Commons Clause is a legal/governance gate |
| 7 | RIG = methodology, not dependency | Published gains ≠ Tradelatest evidence |
| 8 | T4 external authority forbidden by default | Preserve ontology/CRT/Fusion/Decision/Ultron/governance |

Tradelatest authorities preserved: ontology, CRT, Fusion, Decision, Ultron, governance, ACTIVE_VERSION.

---

## Current gate (narrow)

```text
Codebase-Memory
      ↓
G1–G6                            ✓ APPROVED_FOR_LAB
      ↓
isolated extract (CLI)           ✓ tools/oss_lab/codebase-memory/v0.10.2/
      ↓
REPO-INTEL-QA-V1                 ✓ RI-RUN-20260812T214500Z (12/12)
      ↓
StructuralFactRecord artifacts   ✓ runs/.../structural_facts.jsonl
      ↓
benchmark report                 ✓ report.md (unsealed RESEARCH_LAB_ONLY)
      ↓
(only then) design Semantic OS ingestion contract  ← optional next
```

Checklist: [`codebase_memory_gate.md`](codebase_memory_gate.md)  
Q&A corpus: [`../scenarios/repo_intel_qa_corpus_v1.json`](../scenarios/repo_intel_qa_corpus_v1.json)  
Report template: [`../reports/repo_intel_benchmark_template.md`](../reports/repo_intel_benchmark_template.md)

---

## Explicit non-goals until gate clears

- No binary/package install into production venv
- No Semantic OS live YAML mutation
- No dual Codebase-Memory + Infigraph deploy
- No LEAN/Nautilus strategy import into spine
- No findings registration from unpublished local benchmarks without measurement discipline
