# RI → Semantic OS Evidence Compatibility Report

| Field | Value |
|---|---|
| Report id | `RI-SOS-<run_id>` |
| Corpus | `RI-SOS-COMPAT-V1` |
| Prerequisite | RI-QA-V1 PASS |
| Authority | RESEARCH_LAB_ONLY |
| Semantic OS mutated? | **NO** (required) |
| Status | NOT_RUN / MEASURED / … |

---

## Six dimension scores (do not collapse)

| Dimension | Pass rate | Notes |
|---|---|---|
| structural_correctness | | |
| semantic_correctness | | |
| authority_correctness | | |
| negative_control_correctness | | |
| provenance_quality | | |
| retrieval_usefulness | | |

---

## Per-item matrix

| qa_id | category | structural | semantic | authority | negative | provenance | usefulness | notes |
|---|---|---|---|---|---|---|---|---|
| RI-SOS-001 | file_identity | | | | | | | |
| … | | | | | | | | |

---

## Exit state

| State | Chosen? |
|---|---|
| COMPAT_USEFUL_READ_ONLY | |
| COMPAT_STRUCTURAL_ONLY | |
| COMPAT_HARMFUL_AUTHORITY | |
| COMPAT_INCONCLUSIVE | |

---

## Explicit non-claims

- Not a production finding  
- Not permission to auto-mutate Semantic OS  
- Not permission to wire production MCP defaults  
- RI-QA-V1 12/12 does not substitute for this gate  
