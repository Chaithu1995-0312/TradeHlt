# New branch from `patch` + resolve the deferred push

## Context

On 2026-07-02 a live Groq key in `.env` (commits 278d993/eb64269) blocked `git push` via GitHub push-protection. The history was scrubbed via an isolated clone + `filter-branch`, and the **scrubbed line was already pushed** that day (`origin/patch` fast-forwarded `5897209..05d4ad0..e0e7971`). A later session deferred pushing with the note "pushing this branch is a separate, weightier decision given its scrubbed history" — but that caution is now stale: **verified** `origin/patch` and `origin/main` contain zero `.env` history (`git log origin/{patch,main} -- .env` empty; `ls-remote` shows only clean `main`+`patch` on the remote). The only unpushed commit on `patch` is 0c378a9 (docs, truth-layer registry v2.0) — a routine fast-forward.

The old secret survives only in two **local** refs — `backup/pre-env-scrub-20260702` and `claude/elegant-dubinsky-a2b441` (stale `.claude/worktrees/` checkout). **User decision: keep both for now** (key rotation pending; no publication risk since they're local-only).

The working tree holds ~95 modified + 1 deleted tracked files (+1931/−497): F-042/F-043 finding rows, `flow_context/*.json`, `ui_kits/control_plane/*`, broad `src/` edits, doc syncs. User decisions:

- New branch **`feature/truth-registry-v2`** from `patch` @ 0c378a9, checked out.
- **Commit the WIP onto the new branch** (patch stays clean at 0c378a9).
- **Push both**: `patch` (fast-forward to 0c378a9) and the new branch.
- Do **not** delete the secret-bearing local refs.

## Steps

1. **Pre-flight (read-only).** Confirm `patch` @ 0c378a9, `git stash list` untouched, and re-check `git status` for any *untracked* files (first status pass was truncated) — we will commit tracked changes only.
2. **Create + switch:** `git switch -c feature/truth-registry-v2` (from `patch`).
3. **Stage tracked changes only:** `git add -u` — picks up the ~95 modifications + the `.claude/scheduled_tasks.lock` deletion, and cannot add untracked files (`.env` is gitignored+untracked; double-check with `git status --short` that nothing staged is a secret).
4. **Session log (§6 mandate):** append the SESSION LOG ENTRY block to `assistant_project.md` before committing (the pre-commit hook / `test_session_log.py` targets this file), stage it too.
5. **Commit** with a descriptive message (WIP consolidation: F-042/F-043 doc sync, flow_context, control-plane UI kit, src edits) + `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`. Let the pre-commit hook run (~71 tests); if it fails, investigate — never `--no-verify`.
6. **Push:** `git push origin patch feature/truth-registry-v2 -u` — both are plain fast-forwards / new-ref pushes; **no force push anywhere**. LFS size warnings are known-benign.

## Verification

- `git log --oneline -2 feature/truth-registry-v2` shows the WIP commit atop 0c378a9; `git status` clean (apart from intentionally-kept untracked files).
- `git ls-remote origin refs/heads/patch refs/heads/feature/truth-registry-v2` → patch=0c378a9, new branch=new SHA.
- `git show --stat HEAD | grep -i "\.env"` → empty (no secret in the new commit).
- Secret-bearing local refs untouched: `git branch --contains 278d993` still lists only the two kept refs.

## Notes / flags

- The WIP includes edits to `configs/production/v1_multi_2026_03.json` and an archived v2 config — these are the user's own working-tree changes being committed verbatim, not config edits I author; `ACTIVE_VERSION` is untouched (no §6.2 approval gate triggered beyond this user-approved plan).
- Groq key rotation remains the user's out-of-band action; the kept local refs should be deleted once rotated (standing open question in the session log).
