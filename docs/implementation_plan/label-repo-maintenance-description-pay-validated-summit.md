# Repo Maintenance — Session Log Rotation, Findings Consolidation, Memory Consolidation

## Context

Three advisory hygiene signals have accumulated past their thresholds and need paying down before
any new research track starts: the SESSION LOG (`assistant_project.md`, 31 entries vs the 25-keep
norm), `docs/current-findings.md` (39 findings, 2 of them already-SUPERSEDED but mis-filed in the
"non-terminal" section, leaving 37 genuinely-tracked findings vs a ~30 target), and the memory
index (51 files vs a 45 target). None of this is a code change — it's pure doc/memory bookkeeping
governed by CLAUDE.md §6 (session log), §6.2 (truth maintenance, "never delete, mark
SUPERSEDED/RETIRED, append-discipline"), and the repo's own `consolidate-memory` skill. The goal is
to clear these signals without inventing new conclusions or silently overclaiming closure — every
move is either purely mechanical (rotation, re-filing already-decided statuses) or a citation-based
supersession of findings that are *already* documented as closed/killed in memory (Program 1,
Program 5/6/6b).

## 1. Session log rotation (mechanical, scripted)

Run the existing tool, nothing new to build:

```
python scripts/maintenance/rotate_session_log.py --keep 25 --dry-run   # verify split first
python scripts/maintenance/rotate_session_log.py --keep 25             # apply
```

This spills the oldest 6 entries from [assistant_project.md](assistant_project.md) into
`docs/analysis/session-log-archive/session-log-<oldest-date>_to_<newest-spilled-date>.md` (the
existing archive folder — [scripts/maintenance/rotate_session_log.py](scripts/maintenance/rotate_session_log.py) already names files by
date range, so no new naming scheme is needed; this **is** the "single folder + timestamp
differentiation" pattern the task asks for, already in place). Conservation guard in the script
aborts before writing if entry count doesn't match markers — trust it.

## 2. Findings consolidation in `docs/current-findings.md`

**Step A — re-file already-decided statuses (no new judgment).** F-003 and F-007 are already
marked `Status: SUPERSEDED` but sit in the `## Findings (non-terminal)` section instead of
`## Terminal (SUPERSEDED / RETIRED) — kept for replay` (currently a placeholder, "_(none yet...)_").
Cut their blocks and paste them under Terminal, replacing the placeholder line. No status or
content changes — purely fixing a stale section placement.

**Step B — consolidate the two closed-program clusters into superseding findings**, per
§6.2 rule 4 (preserve history, mark SUPERSEDED, never delete) and rule 5 (minimize doc count):

- **New finding `F-040 · Program 1 (next-bar directional ontology) closed after four
  falsifications`** — consolidates F-019 (qualify-majors null), F-020 (conditional entropy null),
  F-021 (selection-is-session-only), F-025 (exit/cost grid null), F-026 (structural asymmetry
  null/underpowered). Cite [docs/analysis/program-1-closure-2026-06-13.md](docs/analysis/program-1-closure-2026-06-13.md) (already exists per
  memory `project_program1_closure.md`) as the evidence anchor. Status: `VALIDATED`.
- Flip F-019, F-020, F-021, F-025, F-026 to `Status: SUPERSEDED` with a one-line
  `Superseded-by: F-040` note, and move all five blocks to the Terminal section (content
  untouched otherwise — this is re-filing + a status flip, not a rewrite of their evidence).
- **New finding `F-041 · Cross-sectional / carry program (5, 6, 6b) closed — no monetizable
  signal on crypto-major dispersion or carry`** — consolidates F-032 (panel dispersion null),
  F-033 (carry/basis signal null), F-034 (carry harvest null). Cite the three existing memory
  files (`project_cross_sectional_program5.md`, `project_carry_basis_program6.md`,
  `project_carry_harvest_program6b.md`) as evidence anchors. Status: `VALIDATED`.
- Flip F-032, F-033, F-034 to `Status: SUPERSEDED` (`Superseded-by: F-041`), move to Terminal.

**Net effect:** non-terminal findings 39 → 39 (no deletions) but *tracked-as-open* count
37 → 31 (37 minus the 6 superseded, plus the 2 new consolidated rows F-040/F-041 = 31). This is the
"Recommended" option the user selected — close to the 30 target without forcing artificial RETIRED
verdicts on findings whose null results are durable knowledge, not failures.

**Step C — sync the Repository Truths Index table** in [CLAUDE.md](CLAUDE.md) §6.2: add rows for
F-040/F-041, and either remove or mark the now-superseded F-019/020/021/025/026/032/033/034 rows
(the table is enforced 1:1 against non-terminal findings by `tests/test_current_findings.py` — run
it after the edit to confirm sync, per the Findings Mandate).

**Step D — run the test floor:** `pytest tests/test_current_findings.py -q` must pass before
calling this step done (it enforces the index↔doc 1:1 invariant).

## 3. Memory consolidation (51 → 45 files)

Invoke the existing skill rather than hand-rolling logic:

```
/consolidate-memory   (anthropic-skills:consolidate-memory)
```

This is the purpose-built tool for "merge duplicates, fix stale facts, prune the index" — point it
at `C:\Users\Hi\.claude\projects\D--Tradelatest\memory\`. Likely merge candidates based on the
current `MEMORY.md` index: the Program-1 family (`project_program1_closure.md`,
`project_qualify_majors_findings.md`, `project_phase_b_conditional_entropy.md`,
`project_phase_s_selection_effect.md`, `project_phase_d_exit_grid.md`,
`project_phase_e_structural_asymmetry.md` — 6 files describing one closed program) and the
cross-sectional/carry family (`project_cross_sectional_program5.md`,
`project_carry_basis_program6.md`, `project_carry_harvest_program6b.md` — 3 files, same program
that's now also being consolidated in `current-findings.md` Step B). Merging each family into one
memory file (mirroring the F-040/F-041 consolidation above so doc and memory tell the same
compressed story) would bring 51 → ~43, past the 45 target. Let the skill decide exact grouping —
this list is a steer for it, not a hard prescription.

## Verification

- `git diff --stat` shows only `assistant_project.md`, `docs/current-findings.md`, `CLAUDE.md`,
  new file under `docs/analysis/session-log-archive/`, and memory files under
  `C:\Users\Hi\.claude\projects\D--Tradelatest\memory\` — no `src/` changes.
- `pytest tests/test_current_findings.py tests/test_session_log.py -q` green.
- `grep -c "^### F-" docs/current-findings.md` and a manual scan of `## Findings (non-terminal)`
  confirm 31 tracked + the rest under Terminal.
- Session log entry count in `assistant_project.md` == 25 + this response's own new entry (§6
  mandate — this maintenance turn itself still ends with a SESSION LOG block, appended after
  rotation).
