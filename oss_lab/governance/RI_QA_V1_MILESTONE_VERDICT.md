# Milestone Verdict — REPO-INTEL-QA-V1 (Codebase-Memory)

| Field | Value |
|---|---|
| Status | **SUCCESSFUL RESEARCH-LAB VALIDATION** |
| Not | Semantic OS integration · production finding · semantic authority |
| Run | `RI-RUN-20260812T214500Z` |
| Engine | OSS-CODEBASE-MEMORY v0.10.2 |
| Score | **12 / 12 PASS** · 0 fail · 0 unknown · negative control held |
| Authority | RESEARCH_LAB_ONLY (unsealed) |
| Semantic OS mutated | **NO** |
| Date | 2026-08-12 |

---

## Classification

```text
RI-QA-V1 = first-gate PASS for structural retrieval in the lab
         ≠ Semantic OS integration
         ≠ production wiring
         ≠ second semantic authority
```

**Do not promote the 12/12 score into `docs/current-findings.md` as production-adjacent truth.**  
It is an unsealed lab measurement under the OSS evidence rule.

---

## What this proves

| Claim | Supported? |
|---|---|
| Isolated install + index of Tradelatest is feasible | Yes |
| Structural graph at scale exists (34,572 nodes / 120,458 edges) | Yes |
| Fixed structural Q&A corpus can be answered without empty/unknown | Yes (this corpus) |
| Negative control can reject nonexistent target | Yes (FakeFusionEngineV9) |
| Lab isolation can keep Semantic OS / production untouched | Yes |

Architecture fit:

```text
Book              = architecture narrative
Encyclopedia      = implementation map
Semantic OS       = meaning (advisory)
codebase-memory   = high-resolution structural retrieval (candidate evidence provider)
```

---

## What this does **not** prove

- Semantic correctness beyond the 12 QA cases  
- Authority over repository truth  
- Superiority over OBJ / Semantic OS queries  
- Usefulness for Phase-2 semantic reasoning  
- Production-safe MCP integration  
- Warm-daemon performance  
- Complete repository understanding  
- That automatic Semantic OS mutation is safe or desired  

---

## Architectural boundary (reaffirmed)

```text
Codebase-Memory  →  "What is structurally connected?"
Semantic OS      →  "What does that connection mean?"
Implementation   →  last hop (OBJ:path)
```

Semantic OS remains advisory-only; implementation is the last hop  
([`SEMANTIC_OS_CONTRACT.md`](../../docs/governance/SEMANTIC_OS_CONTRACT.md)).

Ingestion path (if ever authorized) must be:

```text
structural facts  →  evidence layer  →  human/governed SOS interpretation
NOT
structural facts  →  automatic CN/BD/JN truth
```

---

## Next gate (not warm-latency)

**Do not prioritize warm-daemon latency next.**

Prioritize:

> **RI → Semantic OS Evidence Compatibility Test**  
> Can codebase-memory supply structural evidence that **materially improves** Semantic OS reasoning **without** becoming a second semantic authority?

Design: [`RI_SOS_EVIDENCE_COMPATIBILITY.md`](RI_SOS_EVIDENCE_COMPATIBILITY.md)  
Corpus: [`../scenarios/ri_sos_compat_corpus_v1.json`](../scenarios/ri_sos_compat_corpus_v1.json)

---

## Registry implication

| Field | Value |
|---|---|
| Prior | APPROVED_FOR_LAB |
| After this verdict | **BENCHMARKED** (lab) |
| Still forbidden | T4, production MCP default, SOS live YAML mutation |
