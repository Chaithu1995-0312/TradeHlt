# Plan: List uncommitted files + run test suite, report failures

## Context
User wants two pieces of read-only information before deciding what to commit:
1. Which files are currently modified/untracked (staged and unstaged) in the working tree, so they can decide what to commit.
2. The current state of the test suite — how many test classes/files are failing right now on this branch (`feature/truth-registry-v2`).

This is a diagnostic/reporting task, not a code change — no files will be edited or committed as part of this. Per CLAUDE.md §3.4 and `docs/reference/testing.md`, tests run via `pytest`.

## Steps

1. **List files needing commit**
   - Run `git status` (already have a truncated snapshot from session start showing many `M`/`A`/`AM` files under `configs/`, `docs/`, `.grok/`, etc. — need the full untruncated list since the initial snapshot was cut off at 2k chars).
   - Run `git diff --stat` (unstaged) and `git diff --cached --stat` (staged) to summarize scope of changes per file.
   - Present the full categorized list to the user: staged (A/M in index), modified-unstaged, and untracked.

2. **Run the test suite**
   - Per `docs/reference/testing.md`, run the full suite (likely `python -m pytest tests/` from repo root, using the project's venv if present — e.g. `venv/Scripts/python.exe` per memory note on this repo).
   - Capture full output (this may be large — 51+ test files across 10 domains per CLAUDE.md).
   - Do NOT modify any test files, source files, or config as part of this — purely observe results.

3. **Summarize results**
   - Report: total test files/classes collected, number passed, number failed, and specifically enumerate which test classes/files have failures (name + short reason if available from the traceback summary).
   - Do not attempt to fix failures or interpret them as findings requiring a CLAUDE.md §6.2 doc-drift decision unless the user asks for that follow-up — first turn is just reporting.

## Verification
- `git status` output cross-checked against `git diff --stat` / `git diff --cached --stat` for consistency.
- Pytest run to completion (or clearly report if it times out / needs to run in background given repo size) with a final pass/fail tally matching the printed summary line (`X passed, Y failed, Z error`).

## Out of scope for this turn
- Committing anything.
- Fixing any failing tests.
- Investigating *why* tests fail beyond what pytest's own failure summary shows.
