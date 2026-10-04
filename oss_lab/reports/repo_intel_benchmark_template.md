# Repository Intelligence Benchmark Report

| Field | Value |
|---|---|
| Report id | `RI-BENCH-<run_id>` |
| Corpus | `REPO-INTEL-QA-V1` |
| Engine under test | `OSS-CODEBASE-MEMORY` (or `OSS-INFIGRAPH`) |
| Engine version/pin | **UNKNOWN until G2 pin** |
| Local baselines | `graph.dot`, `gen_pyan.py`, `dot_graph_context.py` |
| Authority | RESEARCH_LAB_ONLY |
| Semantic OS mutated? | **NO** (required) |
| Lifecycle | DISCOVERED → (after gate) APPROVED_FOR_LAB benchmark |

---

## Run provenance

| Field | Value |
|---|---|
| git_commit | |
| tool_version | |
| tool_commit_or_tag | |
| install_path | (must not be production venv) |
| command | |
| os_runtime | |
| started_utc | |
| finished_utc | |
| evidence_dir | `results/oss_lab/repo_intel/<run_id>/` |

---

## Gate status

| Gate | Result |
|---|---|
| G1 License | OPEN / PASS / FAIL |
| G2 Version pin | OPEN / PASS / FAIL |
| G3 Security/install | OPEN / PASS / FAIL |
| G4 Architecture boundary | OPEN / PASS / FAIL |
| G5 Benchmark readiness | OPEN / PASS / FAIL |
| G6 Lifecycle update | OPEN / PASS / FAIL |

If any critical gate is FAIL/OPEN, mark entire report **INADMISSIBLE**.

---

## Aggregate scores

| Metric | Value | Unit | Status |
|---|---|---|---|
| items_total | 12 | count | |
| items_measured | | count | |
| items_pass | | count | |
| items_fail | | count | |
| items_unknown | | count | |
| index_wall_clock | | s | NOT_RUN |
| query_latency_p50 | | ms | NOT_RUN |
| query_latency_p95 | | ms | NOT_RUN |
| triple_run_repro | | PASS/FAIL/VAR | NOT_RUN |

---

## Per-item results

| qa_id | status | latency_ms | matches_baseline? | answer_summary | notes |
|---|---|---|---|---|---|
| RI-QA-001 | NOT_RUN | | | | |
| RI-QA-002 | NOT_RUN | | | | |
| RI-QA-003 | NOT_RUN | | | | |
| RI-QA-004 | NOT_RUN | | | | |
| RI-QA-005 | NOT_RUN | | | | |
| RI-QA-006 | NOT_RUN | | | | |
| RI-QA-007 | NOT_RUN | | | | |
| RI-QA-008 | NOT_RUN | | | | |
| RI-QA-009 | NOT_RUN | | | | |
| RI-QA-010 | NOT_RUN | | | | |
| RI-QA-011 | NOT_RUN | | | | |
| RI-QA-012 | NOT_RUN | | | | |

---

## StructuralFactRecord emission

| Field | Value |
|---|---|
| facts_emitted | 0 / N |
| mapping_notes | |
| fields_UNKNOWN | |

---

## Claims discipline

| Claim class | Allowed? |
|---|---|
| PUBLISHED RESULT (arXiv/blog) | Cite only; not Tradelatest evidence |
| INDEPENDENT REPRODUCTION (this report) | Yes, if gates PASS and methods recorded |
| TRADLATEST RESULT / production finding | **No** without separate governance path |
| Semantic OS meaning update | **No** from this report alone |

---

## Decision

| Option | Chosen? |
|---|---|
| Continue iteration (fix tool config / pin) | |
| APPROVED_FOR_LAB remains; more runs needed | |
| Design Semantic OS **ingestion contract** (separate program) | only if useful + reproducible |
| DEFER / REJECT candidate | |

**Explicit:** This report does not mutate `docs/governance/semantic_os/*.yaml`.
