# GROK_BOT_HOOKS_ONEPAGER.md — activate + meaning

> **Owner:** Grok Bot (docs). Hook *logic* owned by Claude / maintenance scripts.  
> **Census:** 2026-09-18 · `D:\Tradelatest\hooks\`  
> **Detail source:** `hooks/README.md` (canonical). This page is the skim sheet.

---

## Activate (once per clone)

```sh
git config core.hooksPath hooks
```

Undo: `git config --unset core.hooksPath`.

**Windows:** hooks call `python` on PATH (Git Bash). If you use `py` only, alias or edit the hook shebang path.

---

## What runs

| Hook file | Stage | Blocks commit? | Script |
|---|---|---|---|
| `hooks/pre-commit` | pre-commit | **Yes** (path-scoped) | `scripts/maintenance/check_governance_invariants.py` |
| `hooks/commit-msg` | commit-msg | **Yes** on governed code | `scripts/maintenance/check_session_log_commit.py` |
| *(same file, 2nd call)* | commit-msg | **Never** | `scripts/maintenance/check_consolidation_due.py` |

Escape hatches:
- Trivial governed-path change: `git commit --no-verify`
- Governed code without a session-log line: put `[nolog]` in the commit message

---

## What they enforce (one line each)

1. **Green floor** — if you touch governed invariant paths, the curated E-001 epistemic tests must stay green. Hook == CI (`--all` in `.github/workflows/governance.yml`).
2. **Session log linkage** — changes under `src/**` or `configs/production/**` need a same-day `SESSION LOG ENTRY` in `assistant_project.md` (or `[nolog]`).
3. **Consolidation nudge** — when findings/memory/log substrate is fat, prints a reminder; does not fail the commit.

---

## Quick verify

```sh
git config core.hooksPath          # expect: hooks
python scripts/maintenance/check_governance_invariants.py --help
python scripts/maintenance/check_session_log_commit.py --help
python scripts/maintenance/check_consolidation_due.py
```

---

## Out of scope for Grok Bot

- Editing hook scripts or GREEN_FLOOR contents → Claude  
- Broadening the floor to whole-suite pytest → **forbidden** (permanently-red gate = decorative; E-001F)
