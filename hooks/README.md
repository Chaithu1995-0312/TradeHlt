# Git hooks (tracked) — CLAUDE.md §6 enforcement

These hooks are version-controlled so they are reviewable and shared, unlike `.git/hooks/`.

## Activate (one-time, per clone)

```sh
git config core.hooksPath hooks
```

Deactivate with `git config --unset core.hooksPath`.

## Hooks

| Hook | Behaviour | Logic |
|---|---|---|
| `pre-commit` (blocking) | A commit touching governed-invariant paths (`src/research/**`, `docs/governance/**`, `tests/governance/**`, `docs/current-findings.md`, `docs/operations/KNOWN_ILLUSIONS.md`) must keep the **curated green floor** green — the Program E-001 behavioral epistemic invariants + coupled tests. Path-scoped (docs-only edits skip the pytest cost); bypass a trivial change with `git commit --no-verify`. | [`scripts/maintenance/check_governance_invariants.py`](../scripts/maintenance/check_governance_invariants.py) |
| `commit-msg` (blocking) | A commit touching `src/**` or `configs/production/**` must ship a same-day `📝 SESSION LOG ENTRY` (CLAUDE.md §6/§7.4), or carry `[nolog]` in the message for a trivial refactor. | [`scripts/maintenance/check_session_log_commit.py`](../scripts/maintenance/check_session_log_commit.py) |
| `commit-msg` (advisory, **never blocks**) | Prints a "consolidation due" nudge when the findings/memory/log/archive substrate grows past a soft threshold (CLAUDE.md #3 context-ceiling). | [`scripts/maintenance/check_consolidation_due.py`](../scripts/maintenance/check_consolidation_due.py) |

The `pre-commit` gate is the **continuous** half of Program E-001 (`docs/governance/EPISTEMIC_INTEGRITY.md`):
the behavioral red→green invariant proven in `tests/governance/test_epistemic_invariants.py` runs on every
governed commit, and the **same script** (`--all`) is the CI gate ([`.github/workflows/governance.yml`](../.github/workflows/governance.yml)),
so hook == CI by construction. It runs a **curated green floor**, never `pytest` whole — a permanently-red
gate enforces nothing (decorative wiring, E-001F). The floor (`GREEN_FLOOR`) grows monotonically as the
F-018 split-brain reds are resolved.

This is the **forward** half of the Persistent Logging Mandate (a missing log on a real change);
the **timeless** half (a malformed log) is enforced by `tests/test_session_log.py`. Neither checks
whether the recorded belief is *true* — that residual stays doctrine (CLAUDE.md §6.1).

The consolidation advisory is the **volume** analogue of the **time**-based freshness gate
(`test_current_findings.py::test_nonterminal_findings_are_fresh`): both nudge you to keep the
always-loaded substrate lean. It is advisory-only here; run it with `--strict` in a CI step (exit 1
when due) if you want a hard gate.

**Windows note:** the hook calls `python` on PATH; if your Python launcher is `py`, edit the hook
or alias accordingly. Git for Windows runs the `sh` shebang via its bundled shell.
