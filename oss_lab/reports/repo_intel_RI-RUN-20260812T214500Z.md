# Repo Intel Benchmark Report — RI-RUN-20260812T214500Z

| Field | Value |
|---|---|
| Corpus | REPO-INTEL-QA-V1 |
| Engine | OSS-CODEBASE-MEMORY v0.10.2 |
| Lifecycle | APPROVED_FOR_LAB |
| Authority | RESEARCH_LAB_ONLY |
| Semantic OS mutated | **NO** |
| Pin SHA-256 ok | True |
| git_commit | `105490552605acb25d332131128ea18cb2cfdbb1` |
| CBM_CACHE_DIR | `C:\Users\Hi\AppData\Local\codebase-memory-mcp-lab-tradelatest` |
| items_pass / total | 12 / 12 |
| items_unknown | 0 |
| latency_p50_ms | 24810.09 |

## Per-item

| qa_id | status | pass | latency_ms | notes |
|---|---|---|---|---|
| RI-QA-001 | MEASURED | True | 24810.09 | baseline has engine_runner importer; CBM refs sample may omit it (not hard fail) |
| RI-QA-002 | MEASURED | True | 20705.77 |  |
| RI-QA-003 | MEASURED | True | 20995.89 |  |
| RI-QA-004 | MEASURED | True | 28078.81 |  |
| RI-QA-005 | MEASURED | True | 34100.75 |  |
| RI-QA-006 | MEASURED | True | 59413.58 | anchor missing on disk |
| RI-QA-007 | MEASURED | True | 36193.79 | anchor missing on disk |
| RI-QA-008 | MEASURED | True | 13961.68 |  |
| RI-QA-009 | MEASURED | True | 16171.9 |  |
| RI-QA-010 | MEASURED | True | 17024.87 |  |
| RI-QA-011 | MEASURED | True | 8757.08 | no fabricated production module path |
| RI-QA-012 | MEASURED | True | 25963.76 |  |

## Claims discipline

- PUBLISHED arXiv gains: not used
- This report = INDEPENDENT lab measurement (unsealed)
- Not a production finding; not Semantic OS authority

Artifacts: `D:/Tradelatest/results/oss_lab/repo_intel/runs/RI-RUN-20260812T214500Z`

## Install notes (this run)

- Binary: `tools/oss_lab/codebase-memory/v0.10.2/codebase-memory-mcp.exe` (v0.10.2)
- Did **not** run `install.ps1` (avoids agent MCP config mutation)
- Index: mode=fast, project=tradelatest, ~70.6s, nodes=34572, edges=120458
- Cache: `%LOCALAPPDATA%/codebase-memory-mcp-lab-tradelatest` (`results/` path hit `cache-private` on Windows)
- Repo root `.cbmignore` seeded from `lab.cbmignore`
- Semantic OS YAML: **not modified**
- Latency dominated by multi cold-start CLI processes per item (not single-daemon steady state)

## Scoring caveat

- RI-QA-006/007 "anchor missing on disk" notes were false positives for **directory** anchors (`registry/`, `semantic_os/`); fixed in runner for future runs. Items still MEASURED/pass.
