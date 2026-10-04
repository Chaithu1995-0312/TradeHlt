# GCMC v3 — close the coverage denominator

## Context

`.grok/infra_architecture_link.xlsx` reports **100.0% coverage** and the workbook is internally
honest about it: `Gaps` is empty, `Unreferenced_spine` is empty, `on_disk_not_in_excel = 0`,
`in_excel_not_on_disk = 0`, and `sweep_kind` is labelled `name_census_not_source_read`.

The problem is the **denominator**, not the arithmetic. The sweep declares six trees
(`src` 592, `scripts` 408, `tests` 531, `mt5_analytics` 45, `oss_lab` 37, `tools` 17 = **1,630**)
and reports 1,630/1,630. On disk there are **1,831** `.py` files once scratch-worktree copies are
set aside — so real coverage is **89.0%**, and **201 files** sit outside the sweep entirely,
**101 of them git-tracked**:

| Outside the sweep | Files | Tracked |
|---|---:|---:|
| repo-root `*.py` (`audit.py`, `run_*.py`, `_m8_*.py`, `build_zone_registry_*.py`, …) | 23 | 23 |
| `results/` | 50 | 0 |
| `copiedSrcFiles/` | 32 | 0 |
| `msip_1_verification_package/` | 31 | 31 |
| `archive/` (dead_code, inout_legacy, ui_legacy) | 19 | 19 |
| `H-SECONDLOW-002_Complete_Package/` | 19 | 19 |
| `.grok/` (incl. the linker producing this analysis) | 8 | 0 |
| `terminals/` | 6 | 0 |
| `grok/` | 4 | 4 |
| `exec_telemetry/` | 4 | 4 |
| `docs/` (incl. `docs/reference/example-service.py`) | 3 | 1 |
| `reports/`, `manual_tools/` | 2 | 2 |

Repo-root `*.py` is the substantive miss: CLAUDE.md §3.1b (SITS) treats those as governed,
registerable surfaces. `.grok/` is the self-reference miss: the linker is not counted by its own
sweep.

Two secondary defects to fix in the same pass:

- `PATH_RE` (`_link_infra_architecture.py:55`) hardcodes the six tree names, so a citation to
  `archive/…` or `audit.py` is **invisible to the join** even where one already exists.
- `excel_rows_updated_tests_functionality: 643` vs `excel_tests_functionality: 531` — the former
  counts sheet *rows* (per-test), not files. Reads as a coverage figure and is not one.

**Outcome:** a v3 sweep whose universe is every `.py` on disk except whole-repo scratch copies,
with the exclusions named and counted rather than implicit, and with non-live code (archived,
frozen verification copies) cited under owner labels that say so. Still a name census — this plan
adds no behavior claim, no G001, no CRT closure.

## Decisions taken

- **Universe = everything on disk** (1,831), minus `logs/` (2,997 `.py`) and `.claude/`
  (2,277 `.py`). Both are whole-repo scratch-worktree copies with **0 tracked files** — counting
  them would double-count `src/` and `scripts/` many times over. They go on an `Excluded` sheet
  with that reason, not silently dropped.
- **Non-live code gets distinct owner labels** in `infra_file_citations.md` — an archived or
  frozen-copy file counts as cited, but the label itself says it is not the running system.

## Changes

### 1. `.grok/_link_infra_architecture.py`

**Roots.** Add a `GCMC_V3` spec beside `GCMC_V1`/`GCMC_V2`:

```python
GCMC_V3_DIRS = ("archive", "grok", "exec_telemetry", "manual_tools", "reports", "docs",
                "msip_1_verification_package", "H-SECONDLOW-002_Complete_Package",
                ".grok", "results", "copiedSrcFiles", "terminals")
GCMC_V3_ROOT_FILES = True          # repo-root *.py, non-recursive
EXCLUDED_TREES = {"logs": "whole-repo scratch-worktree copies, 0 tracked",
                  ".claude": "agent worktree copies, 0 tracked"}
```

Reuse `walk_py()` for the directory roots; add a `walk_py_root()` for the 23 non-recursive
repo-root files. Add `logs` to `SKIP_DIR` (`:25`) so `.claude` and `logs` are excluded by one rule.

**Citation matching (`PATH_RE`, `:55`).** Widen the alternation to include the v3 directory roots.
For repo-root files do **not** widen the regex — a bare `\w+\.py` pattern false-positives on every
`src/`-relative path docs write without the prefix (`core/engine_runner.py`, `bitnet/…`). Instead
match root filenames by **exact token membership** against the known 23-name set, via a second
small matcher in `extract_citations()`.

**Rooms (`_ROOM_RULES`, `:61`).** Append v3 prefixes ahead of the fallback. Suggested rooms, all
`sidecar`, so they cannot enter the `Unreferenced_spine` debt sheet:

| Prefix | Room | Allowance |
|---|---|---|
| `archive/` | `archived_dead_code` | `NOT_LIVE` |
| `msip_1_verification_package/`, `H-SECONDLOW-002_Complete_Package/` | `frozen_package` | `NOT_LIVE` |
| `.grok/`, `grok/` | `self_tooling` | `ALLOWED_SIDELINE` |
| `results/`, `copiedSrcFiles/`, `terminals/` | `untracked_scratch` | `ALLOWED_SIDELINE` |
| `exec_telemetry/`, `manual_tools/`, `reports/` | `measurement` | `MEASUREMENT_ONLY` |
| `docs/` | `tooling_scripts` | `ALLOWED_SIDELINE` |
| repo-root `*.py` | `root_scripts` | `ALLOWED_SIDELINE` |

**New column.** Add `Git tracked` to `LINK_HEADERS` (`:36`), sourced once from
`git ls-files '*.py'` — this is what makes the tracked/untracked split auditable per row rather
than only in the summary.

**New sheets** in `write_join_book()`:
- `GCMC_v3_disk` — same 14+1 columns as the v1/v2 sheets. These files are in no source inventory
  workbook, so `Excel listed` will read `NO` throughout; that is correct, not a gap.
- `Excluded` — `Tree · Reason · .py count · Tracked count`, one row per excluded tree plus the
  `SKIP_DIR` members. This sheet plus the three disk sheets must sum to the full walk.

**Coverage JSON.** Add `disk_gcmc_v3`, `disk_total_py`, `tracked_total_py`, `pct_of_disk`,
`pct_of_tracked`, `excluded_counts`. Rename `excel_rows_updated_*` → `excel_rows_written_*` and
add a `note` field stating they are sheet rows, not file counts.

### 2. `.grok/_cite_remainder.py`

- Extend the disk walk (`:128`) to include the v3 roots.
- Extend `_OWNERS` (`:20`) with the v3 prefixes. Distinct labels for the non-live buckets so the
  citation itself carries the liveness signal:
  - `archive/` → `INFRA.md (archived — not live)`
  - `msip_1_verification_package/` → `INFRA.md (frozen verification copy)`
  - `H-SECONDLOW-002_Complete_Package/` → `INFRA.md (frozen research package)`
  - `.grok/`, `grok/` → `INFRA.md (self-tooling)`
  - `results/`, `copiedSrcFiles/`, `terminals/` → `INFRA.md (untracked scratch)`
  - `exec_telemetry/` → `live-execution.md`; `manual_tools/`, `reports/` →
    `research-measurement-contract.md`; `docs/reference/example-service.py` →
    `INFRA.md (reference template)`
  - repo-root fallback → `INFRA.md (root scripts)`
- Update the header lines (`:147`) so the stated denominator matches the new universe.

### 3. Run order

`_cite_remainder.py` writes the file the linker then joins against, and imports the linker for
`walk_py`/`load_doc_citations`. So: **edit the linker first**, then `_cite_remainder.py`, then run

```bash
python .grok/_cite_remainder.py && python .grok/_link_infra_architecture.py
```

Note `_link_infra_architecture.py` writes into four **existing** workbooks
(`results/analysis/src_business_functionality.xlsx`, `scripts_business_functionality.xlsx`,
`docs/analysis/tests_functionality_inventory.xlsx` — tracked and already dirty in git —
`.grok/gcmc_v2_inventory.xlsx`). v3 adds no new source workbook; the v3 rows live only in the
link workbook.

## Verification

Re-run the two scripts, then assert against `.grok/infra_architecture_link_coverage.json`:

- `disk_gcmc_v1 == 1531`, `disk_gcmc_v2 == 99`, `disk_gcmc_v3 == 201`, `disk_total_py == 1831`
- `pct_of_disk == 100.0` and `disk_all_referenced_in_infra_docs == 1831`
- `tracked_total_py == 1496`; `Git tracked = YES` row count across the three disk sheets == 1496
- `Gaps` sheet still header-only; `Unreferenced_spine` still header-only (v3 rows are all
  `sidecar`, so a regression here means a room rule leaked `spine`)
- `Excluded` sheet: `logs` 2997 / 0 tracked, `.claude` 2277 / 0 tracked; excluded + covered ==
  the unfiltered disk walk

Independent cross-check, not reading the script's own output:

```bash
find . -name '*.py' -not -path './.git/*' -not -path './venv/*' -not -path './.venv/*' \
  -not -path './node_modules/*' -not -path './__pycache__/*' \
  -not -path './.claude/*' -not -path './logs/*' | wc -l    # expect 1831
```

Spot-check three rows by hand in `GCMC_v3_disk`: `audit.py` (root, tracked),
`archive/dead_code/journal/schema.py` (`archived_dead_code`, `NOT_LIVE`),
`.grok/_link_infra_architecture.py` (`self_tooling`, and now cited by its own sweep).

Confirm `.grok/infra_file_citations.md` gained the new owner sections and that the archived /
frozen-copy paths appear **only** under their `NOT_LIVE`-labelled headings.

## Scope guard

This stays a **name census**. `sweep_kind` remains `name_census_not_source_read`. 100% of the new
denominator will still mean *every `.py` on disk has a named home* — not that any file was read,
not that CRT is CLOSED, not that an edge exists. No `src/` edit, no config change, no promotion,
no G001.
