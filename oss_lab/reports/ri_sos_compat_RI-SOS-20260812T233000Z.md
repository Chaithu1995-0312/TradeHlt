# RI → Semantic OS Evidence Compatibility Report — RI-SOS-20260812T233000Z

| Field | Value |
|---|---|
| Corpus | RI-SOS-COMPAT-V1 |
| Exit state | **COMPAT_USEFUL_READ_ONLY** |
| Authority | RESEARCH_LAB_ONLY (unsealed) |
| Semantic OS mutated | **NO** |
| CBM | v0.10.2 project=tradelatest |
| git_commit | `84fff5176f5753eb7a12a0e74f8cb857f86ff877` |
| Usefulness PASS count | 15 |

## Six dimension scores (not collapsed)

| Dimension | n | pass | fail | unknown | pass_rate |
|---|---|---|---|---|---|
| structural_correctness | 15 | 15 | 0 | 0 | 1.0 |
| semantic_correctness | 15 | 13 | 0 | 2 | 0.8667 |
| authority_correctness | 15 | 15 | 0 | 0 | 1.0 |
| negative_control_correctness | 1 | 1 | 0 | 0 | 1.0 |
| provenance_quality | 15 | 14 | 0 | 1 | 0.9333 |
| retrieval_usefulness | 15 | 15 | 0 | 0 | 1.0 |

## Per-item

| qa_id | category | structural | semantic | authority | negative | provenance | usefulness | notes |
|---|---|---|---|---|---|---|---|---|
| RI-SOS-001 | file_identity | PASS | PASS | PASS | N/A | PASS | PASS | dual channel: SOS meaning + CBM structure |
| RI-SOS-002 | call_dependency | PASS | PASS | PASS | N/A | PASS | PASS | dual channel: SOS meaning + CBM structure |
| RI-SOS-003 | journey_reconstruction | PASS | PASS | PASS | N/A | PASS | PASS | dual channel: SOS meaning + CBM structure |
| RI-SOS-004 | boundary_membership | PASS | PASS | PASS | N/A | PASS | PASS | dual channel: SOS meaning + CBM structure |
| RI-SOS-005 | contract_coverage | PASS | PASS | PASS | N/A | PASS | PASS | dual channel: SOS meaning + CBM structure |
| RI-SOS-006 | crt_execution_trace | PASS | PASS | PASS | N/A | PASS | PASS | dual channel: SOS meaning + CBM structure |
| RI-SOS-007 | feature_pipeline_trace | PASS | PASS | PASS | N/A | PASS | PASS | dual channel: SOS meaning + CBM structure |
| RI-SOS-008 | negative_nonexistent | PASS | PASS | PASS | PASS | UNKNOWN | PASS | negative: no fabricated implementation path |
| RI-SOS-009 | sos_to_implementation | PASS | PASS | PASS | N/A | PASS | PASS | dual channel: SOS meaning + CBM structure |
| RI-SOS-010 | implementation_to_sos | PASS | PASS | PASS | N/A | PASS | PASS | SOS silent → UNKNOWN meaning is fail-closed OK; partial dual provenanc |
| RI-SOS-011 | file_identity | PASS | PASS | PASS | N/A | PASS | PASS | dual channel: SOS meaning + CBM structure |
| RI-SOS-012 | call_dependency | PASS | UNKNOWN | PASS | N/A | PASS | PASS | SOS silent on item; economic RR remains Ultron (F-048); structure sepa |
| RI-SOS-013 | journey_reconstruction | PASS | UNKNOWN | PASS | N/A | PASS | PASS | SOS silent on item; partial dual provenance; CBM structure useful wher |
| RI-SOS-014 | boundary_membership | PASS | PASS | PASS | N/A | PASS | PASS | oss_lab not in production BD membership; dual channel: SOS meaning + C |
| RI-SOS-015 | contract_coverage | PASS | PASS | PASS | N/A | PASS | PASS | SOS remains advisory; CBM not elevated to production authority; dual c |

## Interpretation

Codebase-Memory appears **useful as a read-only structural evidence provider** beneath Semantic OS. Proceed only to **design** an L4 evidence ingestion contract; **do not** auto-mutate CN/BD/JN and **do not** grant production authority.

## Explicit non-claims

- Not a production finding
- Not permission to auto-mutate Semantic OS YAML
- Not permission to wire production MCP defaults
- RI-QA-V1 12/12 does not substitute for this gate

Artifacts: `D:/Tradelatest/results/oss_lab/repo_intel/runs/RI-SOS-20260812T233000Z`
