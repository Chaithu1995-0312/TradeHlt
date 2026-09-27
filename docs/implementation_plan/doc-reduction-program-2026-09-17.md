# Documentation reduction program (lossless) — program spec

| Field | Value |
|---|---|
| **Date** | 2026-09-17 |
| **Status** | Layer 0 COMPLETE (baseline + tracking). Layers 1–4 PENDING. |
| **Task class** | `OBSERVATION_ONLY` — documentation only, **no code or config changes** |
| **Baseline commit** | `c27d69e` (branch `grokbotchanges`) |
| **Workflow** | [`Claude-deepseek.md`](../../Claude-deepseek.md) S4 P0–P8 (P8 = documentation result, never promotion) |
| **Tracking (single source)** | [`docs/governance/DOC_TRACKING_INDEX.xlsx`](../governance/DOC_TRACKING_INDEX.xlsx) — `Master_Index`, `Conversion_Ledger`, `Story_Detail` |
| **Task queue (Jira model)** | [`multi_llm/build_queue.jsonl`](../../multi_llm/build_queue.jsonl) epics 11–13, per [`ISSUE_TRACKING_PLAYBOOK.md`](../../multi_llm/ISSUE_TRACKING_PLAYBOOK.md) |
| **Backup mechanism** | `archive/` ledger ([`archive/ARCHIVE_INDEX.md`](../../archive/ARCHIVE_INDEX.md) rules, verifier `scripts/maintenance/verify_archive_manifests.py`) + git history |
| **Authority** | Information only (CLAUDE.md §6.5). Grants no production authority. |

This document follows the same eight-section shape it asks every converted subsystem doc to use.

---

## 1. Functional overview

**Problem.** The repo holds **1,200 tracked Markdown docs (22.07 MB)** written by several models over five
months. Knowledge about one subsystem is spread over plans, analyses, remediation notes, and
concatenated exports; some docs are byte-identical copies; some status tables contradict their own
logs. Finding "what is true now, what is done, what is left" costs a full reread.

**Goal.** Fewer, precise documents — one per subsystem — each carrying its own functional overview,
technical overview, implementation spec, schema, workflows, open work, defects, and out-of-scope
items, **with zero loss of information**: every fact, ID, citation, and decision in a source doc is
either present in the target doc or preserved byte-for-byte in `archive/` with a pointer.

**Who uses it.** The user (plain-language entry per subsystem), every model in the multi-LLM workflow
(smaller boot + retrieval surface), and the governance floors (fewer stale citations).

**Non-goals.** Deleting history; rewriting conclusions; changing any finding's status; touching code,
config, tests, or `ACTIVE_VERSION`.

---

## 2. Technical overview

### 2.1 Measured inventory (Layer 0, baseline `c27d69e`, 2026-09-17)

| Layer | Rule (first match wins) | Docs | Bytes |
|---|---|---|---|
| `EXCLUDED_SESSION_LOG` | `assistant_project.md`, `llm_project_assistant.md`, `docs/analysis/session-log-archive/` | 41 | 3,187,751 |
| `EXCLUDED_PINNED` | path referenced by a test / `scripts/maintenance` / `scripts/governance` file, or `docs/topics/`, `CLAUDE.md`, `Claude-deepseek.md`, `HANDOFF.md` | 141 | 2,563,151 |
| `L1_EXACT_DUPLICATE` | SHA-256 shared with another tracked doc | 16 | 248,565 |
| `L2_DERIVED` | `grokconcatedplans/`, `grokconcatedimplplans/`, `*.generated.*`, `*.LATEST.*` | 28 | 3,853,611 |
| `L3_POINT_IN_TIME` | `docs/implementation_plan/`, `docs/plans/`, `docs/analysis/`, `docs/research-readiness/`, `reports/`, `multi_llm/research_lane/` | 534 | 7,529,264 |
| `L4_LIVING` | everything else | 440 | 4,692,480 |
| **Total** | | **1,200** | **22,074,822** |

Other facts: 12 exact-duplicate groups; 119 docs pinned by exact path in tests/governance scripts;
4 `.generated.md` files (279 KB). The per-doc numbers live in `Master_Index` (one row per doc).

### 2.2 Reused assets (no parallel systems)

| Need | Reused asset | How |
|---|---|---|
| Doc inventory + tracking | `DOC_TRACKING_INDEX.xlsx` (built 2026-08-06, 652 rows) | Extended **in place**: 548 rows added, 16 baseline columns, `Conversion_Ledger` + `Story_Detail` sheets. Cell-by-cell check vs backup: **0 original cells lost or changed**. |
| Topic classification | `scripts/governance/_build_doc_tracking_index.py::infer_topic` | Imported read-only for the 548 new rows. **Never re-run the builder** (defect DOC-BUG-03). |
| Task tracking | `multi_llm/build_queue.jsonl` (one-queue rule) | Epics 11–13 appended in the existing schema; rich Jira fields (checklist, traceability, audit, labels) in `Story_Detail`, keyed by story id. |
| Backup | `archive/` + MANIFEST.csv + `verify_archive_manifests.py` | Every source removed from its live path is first copied to `archive/doc_reduction_<batch>/` with a canonical manifest row. |
| Workflow | `Claude-deepseek.md` P0–P8 | Each conversion batch = one cycle (§5). |

---

## 3. Implementation spec

### 3.1 Target document template (every subsystem doc)

```
# <Subsystem> — <one-line purpose>
| Field | Value |  (date, status, owners, source docs count, Conversion batch id, authority)
## 1. Functional overview        what it does, for whom, why (user language)
## 2. Technical overview         modules, data flow, entry points (path:line citations)
## 3. Implementation spec        behaviour, config keys, invariants, verified numbers
## 4. Schema                     records, fields, vocabularies (link, don't copy, if a schema doc owns it)
## 5. Workflows                  how it is run / operated / verified
## 6. Yet to do                  open items → STORY ids
## 7. Bugs / defects             DOC-BUG / G-* / F-ids with status
## 8. Out of scope               explicit non-goals
## Appendix A. Source map        every source doc → target section(s) → archive path + sha256
## Appendix B. History           dated decisions carried verbatim (never summarised away)
```

### 3.2 Lossless rule (the definition of "no loss")

A source doc may leave its live path only when **all** hold:

1. **Hash recorded** — `SHA256_Baseline` in `Master_Index` matches the bytes being archived.
2. **Archived first** — byte copy under `archive/doc_reduction_<batch>/<original path>`, manifest row
   `timestamp_utc,action,original_path,archive_path,sha256_before,reason,sha256_after`, verifier green.
3. **Coverage check PASS** against the target doc (recorded in `Conversion_Ledger`):
   - every **identifier** in the source (`F-\d+`, `SEM-\d+`, `CH-*`, `MC-*`, `STORY-*`, `REM-*`, `G-*`, `FM-\d+`, `RC-\d+`) appears in the target or in Appendix A;
   - every **`path:line` / file-path citation** appears in the target;
   - every **number with a unit or percent** in a table or verdict line appears in the target, or the source section is linked from Appendix A as "verbatim in archive";
   - every **heading** maps to a target section (recorded in `Headings_Mapped`).
4. **Pointer stub left** at the original path if `Inbound_Refs > 0`: a short Markdown file naming the
   target doc + section and the archive path + sha256 — so links, citations, and retrieval still resolve.
5. **Pins untouched** — docs in `EXCLUDED_PINNED` never move until the pinning test/script is updated
   in its own authorized change.

Numbers or text that cannot be placed in the target stay in Appendix B verbatim. Nothing is paraphrased
out of existence.

### 3.3 Per-layer actions

| Layer | Action | Coverage check |
|---|---|---|
| L1 exact duplicate | keep the copy with the most inbound refs as canonical; archive the rest; pointer stub | trivial (identical sha) |
| L2 derived | prove the concatenation is byte-reconstructable from its `SOURCE_FILE` blocks; then either archive (sources remain) or mark `GENERATED` and keep | reconstruction sha equality per block |
| L3 point-in-time | group by subsystem (`Topic` + `User_Topic_Track`) → one subsystem doc per §3.1 | full §3.2 check |
| L4 living | only via the Documentation Drift Protocol (CLAUDE.md §6.2); merge when two docs own one topic | full §3.2 check + drift classification |
| Excluded | no action in this program | — |

---

## 4. Schema

### 4.1 `Master_Index` added columns

| Column | Meaning |
|---|---|
| `Present`, `Tracked` | on disk / in `git ls-files` |
| `Baseline_Commit`, `Baseline_UTC` | when the hash was taken |
| `SHA256_Baseline`, `Bytes`, `Lines`, `Headings` | the lossless reference |
| `Last_Commit_Date` | last commit touching the path |
| `Inbound_Refs` | tracked text files naming this path |
| `Pinned_By` | tests / governance scripts naming this path |
| `Dup_Group_Size` | docs sharing this sha |
| `Layer` | §2.1 |
| `Conversion_Status` | `UNCONVERTED → PLANNED → CONVERTED → VERIFIED → ARCHIVED` |
| `Target_Doc`, `Story_ID` | where its content went; which story did it |

### 4.2 `Conversion_Ledger` (one row per action)

`Seq, Timestamp_UTC, Story_ID, Layer, Action, Source_Path, SHA256_Before, Target_Doc, Target_Section,
Archive_Path, SHA256_Archive, Coverage_Check, Headings_Mapped, IDs_Mapped, Citations_Mapped,
Pointer_Stub, Reviewer, Notes`

### 4.3 `Story_Detail` (Jira fields not in the thin queue)

`Story_ID, Type (Task|Bug|Decision), Checklist, Traceability, Requester, Date_Identified, Source,
Labels, Evidence, Verification_Status`

Status of record stays in `build_queue.jsonl` (`pending` / `in_progress` / `testing` / `done`);
`Story_Detail` never repeats it. `testing` was added 2026-09-18 (first use: STORY-13.20) for work
that is implemented and unit-verified but not yet signed off. `in_progress` was added 2026-09-18
(first use: STORY-50.1 / STORY-50.2) for claimed work that has an `assignee` and a linked
`continuation` note but is not yet implemented. Only `pending` feeds `NEXT_10_STEPS`
(`scripts/context/build_context.py:134`), so `in_progress` and `testing` both leave the next-up
list without being claimed done. Per-story stage transitions are appended to the record's own
`lifecycle` array. Assignee for reporting is `build_queue.jsonl` `assignee` plus
`Story_Detail.Assignee`.

---

## 5. Workflows

### 5.1 One conversion batch = one P0–P8 cycle

| Phase | Doc-reduction meaning |
|---|---|
| P0 Boot | `Claude-deepseek.md`, this doc, `ACTIVE_VERSION` |
| P1 Orient | `git status --porcelain` (concurrent sessions); pick batch from `Master_Index` by layer + topic |
| P2 Frame | name the story id, source docs, target doc |
| P3 Retrieve | read every source doc fully (flip `Read_Status`) |
| P4 Plan | `Conversion_Status=PLANNED`; draft Appendix A source map |
| P5 Execute | write target doc; archive sources with manifest; pointer stubs |
| P6 Verify | §3.2 coverage check; `verify_archive_manifests.py`; `tests/test_doc_citations.py`; green-floor delta vs baseline |
| P7 Record | `Conversion_Ledger` rows; `Conversion_Status=ARCHIVED`; story → `done`; SESSION LOG |
| P8 Activate | documentation result only |

### 5.2 Order of layers

Layer 0 (done) → L1 duplicates → L2 derived → L3 pilot (live chart/monitor, 7 docs from 2026-09-16/17)
→ L3 rollout by topic → L4 living via Drift Protocol. Each layer closes before the next opens.

---

## 6. Yet to do

| Story | Item |
|---|---|
| STORY-11.8 | L1 exact duplicates (unpinned) |
| STORY-11.9 | L2 derived: prove `grokconcated*` reconstructable, then decide |
| STORY-11.10 | Validate the §3.1 template + §3.2 check on the pilot |
| STORY-11.11 | L3 pilot: live chart / state monitor subsystem |
| STORY-11.12 | L3 rollout by topic (534 docs) |
| STORY-11.13 | L4 living docs via Drift Protocol (440 docs) |
| STORY-11.14 | Pinned docs: plan pin updates before any move (141 docs) |

Epic 12 (run/trace coverage spine) and epic 13 (Grok live chart/monitor remediations) are tracked in the
same queue; their docs become subsystem docs during L3.

---

## 7. Bugs / defects

| Story | Defect | Evidence |
|---|---|---|
| STORY-11.4 | `docs/analysis/current-findings-index.md` is byte-identical to `docs/analysis/feature_identities_v6.md` (misnamed; the real index is `docs/current-findings-index.md`) | shared sha `Master_Index`; added in `1890785` |
| STORY-11.5 | `DOC_TRACKING_INDEX.xlsx` stored twice (repo root + `docs/governance/`) | identical sha `7d9dc260…` at baseline |
| STORY-11.6 | `_build_doc_tracking_index.py` rebuilds the workbook from scratch — a re-run wipes hand sheets and baseline columns | builds a fresh `Workbook()` |
| STORY-11.7 | `build_queue.jsonl` STORY-10.3 `files` lists placeholders (`path/to/file.py`, `server.py`, `query_registry.py`) | queue line 44 |
| STORY-13.19 | `LIVE_ALERTS_OPEN_REMEDIATIONS_2026-09-16.md` status table says OPEN for items its own log marks APPLIED/IMPLEMENTED | table lines 19–26 vs log §2026-09-16 |

---

## 8. Out of scope

- Any code, config, test, or `ACTIVE_VERSION` change (including REM-COST-04's uncommitted code).
- Rotating session logs (memory warning: `rotate_session_log.py` fuses bare-marker entries).
- Changing a finding's status or wording in `docs/current-findings.md`.
- Moving any `EXCLUDED_PINNED` doc before its pin is updated in a separate authorized change.
- Non-Markdown docs (`.docx`, `.xlsx`, `.html`) — inventoried later if requested.
- The `tools/tv_forensic/capture_tv.py` automation-evasion edit (user decision 2026-09-17).

---

## Appendix A. Source map

Layer 0 converted nothing, so no sources are mapped yet. Rows are added by each batch.

## Appendix B. History

- 2026-09-17 — Program opened. Layer 0: baseline of 1,200 tracked docs at `c27d69e` into
  `DOC_TRACKING_INDEX.xlsx` (652 existing rows preserved, 548 added, 0 cells lost); epics 11–13 filed.
