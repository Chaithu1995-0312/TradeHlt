---
name: commit-batch
description: Group uncommitted work into logical batches and commit without touching HEAD or other sessions' files
---

1. `git status --porcelain` — list everything untracked/modified.
2. Group into logical batches (src, tests, docs, governance/findings, data artifacts).
3. Present the batch plan and WAIT for approval. No code changes, no reformatting.
4. Capture the pre-existing test failure baseline; if a batch is gate-blocked by pre-existing
   failures, DEFER it and say so rather than fixing unrelated code.
5. Never switch HEAD. If a parallel session is active, use GIT_INDEX_FILE + commit-tree plumbing.

## Repo-specific

- **NEVER `git add -A` or `git add .`** — roughly 15 concurrent Codex sessions write to this
  working tree. Stage explicit paths only. Unfamiliar new untracked files mid-task are another
  session's work in progress: leave them alone.
- **Baseline command for step 4** is the curated floor, not `pytest` whole (the full suite carries
  ~66 known F-018 reds by design):
  `venv/Scripts/python.exe scripts/maintenance/check_governance_invariants.py --all`
  Record the failed/passed counts BEFORE staging so a pre-existing red is never mistaken for a
  regression. Measured 2026-09-04 on `feature/truth-registry-v2`: 14 failed / 521 passed.
- **The `commit-msg` hook blocks** a commit touching `src/**` or `configs/production/**` unless
  `assistant_project.md` carries a same-day `SESSION LOG ENTRY`, or the message contains `[nolog]`.
  Write the log entry as part of the batch — do not reach for `--no-verify`.
- **The `pre-commit` hook** runs the green floor when a governed path is staged (`src/research/`,
  `src/features/`, `docs/governance/`, `tests/governance/`, `configs/formulas/`,
  `scripts/analysis/`, `docs/current-findings.md`, …). Both hooks are inert until
  `git config core.hooksPath hooks` has been run in this clone — check that first.
- **`.Codex/` is gitignored** (`.gitignore:56`) while `.Codex/settings.local.json` is tracked.
  Config under `.Codex/` needs `git add -f` or it silently does not exist for any other clone —
  that is the F-071 failure class.
- **Never stage** `data/`, `logs/`, `results/`, or `models/` artifacts; `/data/*` and `/results/*`
  are already ignored and the trees are gigabytes.
- Before claiming a batch is complete, re-run the baseline and report the delta, not just "green".
