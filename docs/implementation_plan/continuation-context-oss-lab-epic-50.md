# Continuation — Epic 50 OSS Integration Benchmark Lab

| Field | Value |
|---|---|
| **Stories** | STORY-50.1, STORY-50.2 |
| **Status** | `in_progress` (claimed 2026-09-18; census not started) |
| **Assignee** | Grok |
| **Queue** | `multi_llm/build_queue.jsonl` |
| **Lane** | measurement / evidence (census). Not economic qualification. Not live wiring. |
| **Task class** | `OBSERVATION_ONLY` for the census. README rewrite is a separate `DOCUMENTATION_ONLY` gate. |
| **Authority** | none. `oss_lab` is RESEARCH_LAB_ONLY. T4 production authority forbidden. |
| **Log** | `assistant_project.md` (codebase log) |

Resume here. Do not re-pick a story type. Do not re-derive the claim.

## What is claimed

| Id | Title | `depends_on` |
|---|---|---|
| STORY-50.1 | Census `oss_lab/` (claimed 73 files) against README “LAB ONLY — blocked on Codebase-Memory pin/security gate before first real benchmark” — confirm the gate is still blocking | STORY-41.27, STORY-41.28 (both still `pending` — **not** census blockers) |
| STORY-50.2 | If 50.1 finds the gate **cleared**, file the first real benchmark run as its own follow-up story (**do not run one here**) | STORY-50.1 |

`out_of_scope` on both records: implementation execution, code changes, deep analysis.

`creator` stays `Claude` (who filed). Assignee is Grok.

## Already read (do not treat as the census)

README banner (`oss_lab/README.md` line 5) still says the pin/security gate **blocks** the first real benchmark.

Sibling lab docs already say that gate **passed on 2026-08-12**:

- `oss_lab/governance/codebase_memory_gate.md` — G1–G6 → `APPROVED_FOR_LAB`; pin `v0.10.2` @ `b377c62a…`
- `oss_lab/governance/evaluation_queue.md` — first lab run `RI-RUN-20260812T214500Z` REPO-INTEL-QA-V1 **12/12**; registry lifecycle `BENCHMARKED` (LAB_ONLY)
- `oss_lab/governance/ARCHITECTURE_APPROVAL.md` — remaining block is optional **L4 evidence-ingestion design**, not pin/security; SOS mutation still forbidden

**Open TruthConflict (DOC_DRIFT candidate):** README vs gate docs. Do **not** silently rewrite the README. Present it; user approves any doc sync.

Split “first real benchmark” before answering 50.2:

| Track | What | Status (from those docs, unsealed — re-verify) |
|---|---|---|
| B — repo intel | REPO-INTEL-QA-V1 | Already ran 2026-08-12 |
| A — execution | XAUUSD three-way (Tradelatest / Nautilus / LEAN) | Not that QA run; likely still unrun |

50.2 files a follow-up story for the **unrun** track. It does not re-run RI-QA-V1. It does not execute a benchmark.

## Exact next step (STORY-50.1)

1. Count tracked files under `oss_lab/` (`git ls-files oss_lab/`). Compare to the story’s “73 files”. Exclude `__pycache__`.
2. Module map: `registry/`, `contracts/`, `adapters/` (tradelatest, qlib, nautilus, finrlx, lean, vectorbt, infigraph, codebase_memory), `runners/`, `metrics/`, `scenarios/`, `governance/`, `reports/`, `evidence/`.
3. Grep `src/` for `from oss_lab` / `import oss_lab` — spine must not import the lab.
4. Gate checklist against disk, not README: pin tree `tools/oss_lab/codebase-memory/v0.10.2/`, registry `decision` for `OSS-CODEBASE-MEMORY`, G1–G6 evidence JSON, RI-QA report.
5. Answer the story’s literal question: “is the **Codebase-Memory pin/security gate** still blocking?” Then separately name remaining blocks (L4 SOS ingest vs EXECUTION-track deps).
6. Then STORY-50.2: follow-up story **or** recorded no-op. Never run the benchmark in that story.

Do **not** `pip install` OSS. Do **not** run `oss_lab/runners/`. Do **not** mutate Semantic OS. Do **not** touch `ACTIVE_VERSION`. Do **not** start Epic 62 ownership stubs or STORY-41.27.

## Non-goals (still)

- Registering RI-QA 12/12 as a finding (verdict doc forbids it)
- Enabling BitNet / live rail / spine import
- Marking either story `done` until 50.1 verdict + 50.2 follow-up-or-noop exist

## Where this session left off

2026-09-18 later: **`tools/oss_lab/` census done** (user prompt `oss_tools`). 50.1/50.2 still `in_progress`. README not rewritten. No benchmark run. STORY-50.3 not filed yet.

## `tools/oss_lab/` (oss_tools) — measured 2026-09-18

There is **no** path named `oss_tools`. The pin tree is **`tools/oss_lab/`**, gitignored, distinct from committed **`oss_lab/`**.

| Check | Result |
|---|---|
| Disk | yes — `tools/oss_lab/codebase-memory/v0.10.2/` |
| `git ls-files tools/oss_lab/` | **empty** (untracked by design) |
| `.gitignore` | line 60 `tools/oss_lab/` under `LOCAL_CACHE / vendored` |
| `GITIGNORE_SCHEMA.md` path table | **does not name** `tools/oss_lab/` (gitignore has it; schema table omits it) |
| Files | 5: `codebase-memory-mcp.exe` **296,090,624 B** (~283 MB — matches old inventory “283 MB vendored”), `install.ps1` 15 KB, `LICENSE`, `README.md`, `THIRD_PARTY_NOTICES.md` 573 KB. Total **296,680,095 B** |
| Pin zip | `results/oss_lab/repo_intel/codebase_memory_v0.10.2/codebase-memory-mcp-windows-amd64.zip` exists, **39,152,379 B** (matches G1 evidence `windows_amd64_bytes`) |
| Extract vs `install.ps1` | Extracted CLI tree is present. Isolation policy still says prefer `--skip-config` / do not run installer if it cannot skip. 2026-08-12 session: extract + CLI, **no** `install.ps1`. |
| `INSTALL_ISOLATION.md` line 6 | still says “binary **not yet activated**; extract only” — **stale vs disk** (exe is extracted). Activation ≠ extract. |
| Registry `OSS-CODEBASE-MEMORY` | `decision=BENCHMARKED`, `lifecycle_status=BENCHMARKED`, `certification_status=LAB_ONLY`, pin `v0.10.2@b377c62a…`, `security_status=ASSESSED_RISK`, T1. `allowed_surfaces` lists adapters/evidence/`results/oss_lab` — **not** `tools/oss_lab` (G4 evidence names the tools path as install isolation only). |
| G1–G3 / G4–G6 JSON | both present under `oss_lab/evidence/repo_intel/codebase_memory_v0.10.2/` |
| RI-QA report + run dir | `oss_lab/reports/repo_intel_RI-RUN-20260812T214500Z.md` + `results/oss_lab/repo_intel/runs/RI-RUN-20260812T214500Z/` exist |
| `oss_lab/` file count | **73** disk files (no `__pycache__`) — matches the story’s “73 files” |
| Spine import | **0** `from oss_lab` / `import oss_lab` under `src/`. Tests import the lab. |

### STORY-50.1 literal question

**Is the Codebase-Memory pin/security gate still blocking?** **No.** G1–G6 recorded PASS / PASS_WITH_RESIDUALS → `APPROVED_FOR_LAB`; registry is `BENCHMARKED`; pin zip + extracted exe are on this machine.

Still blocked (different gates, do not collapse into pin/security):

- SLSA/cosign residual (`ATTEMPTED_TOOLS_ABSENT`)
- L4 read-only SOS evidence-ingestion **design** (ARCHITECTURE_APPROVAL current gate)
- Semantic OS mutation still forbidden
- Track A execution three-way (XAUUSD / Nautilus / LEAN) **unrun**
- `oss_lab/README.md` banner still says the pin/security gate blocks — **DOC_DRIFT**, do not silent-fix

50.2 implication (not executed): pin/security **cleared** → file a follow-up for **Track A**, do **not** re-run RI-QA-V1, do **not** run a benchmark in 50.2.
