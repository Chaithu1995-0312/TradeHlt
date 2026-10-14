# Bring program12 + navigator work into semanticos_impl; resolver TTL as a divergence-page branch

## Context
A scan of past Grok sessions found product code that only exists, uncommitted, in two other worktrees of
this repo (verified with `git status` in each):
- `D:\Tradelatest-program12` (branch `grok/program12-slice1`, 10 commits not in semanticos_impl + 28 uncommitted
  paths): timeframe-ladder package, CLI, parity script, tests, ladder configs, `MC-LADDER-XAUUSD-HTF-V1`,
  program-12 manifests/docs, and a finding written as **F-114** (collides with semanticos_impl's F-114).
  Its commit `63a6a1d` changes `src/features/crt_state_resolver.py::_check_expired` from `age >= max` to
  `age > max` (engine parity), plus `tests/test_crt_state_resolver_ttl_boundary.py`.
- `D:\Tradelatest-wt-navigator` (branch `lane/research-navigator`, 1 commit `3b5af83` SITS grandfather resync +
  uncommitted `nav_reconcile.py`, its test, `ui_kits/research_navigator/`, manifests, registry edits).

User decisions: bring both into semanticos_impl; renumber the ladder finding **F-114 → F-121**; keep
the resolver trunk at `>=` and instead show the `>` change as an **implementation branch on the Divergence
Branches page** (tools/feature_audit, published artifact AZnzfViBRctbrFARiCdBrt) for the user to pick there;
leave navigator scratch (`_my*.txt`, `_wt*.txt`, `_verify_experiment*`, two mangled-name PS files) untracked.

## Steps
1. **Commit in place, program12 worktree** (`git -C D:/Tradelatest-program12`): stage the uncommitted ladder
   set explicitly (src/research/timeframe_ladder/*, scripts/research/timeframe_ladder.py,
   program12_parity_one_month.py, tests/research/test_timeframe_ladder.py + test_program12_parity_one_month.py,
   configs/research/ladder_h1.json, ladder_h4.json, MC-LADDER instance, CH-program12-* manifests,
   docs/research/program12-slice2-*.md, ladder_clone_diff.md, preregistration doc, CLAUDE.md,
   docs/current-findings.md, research_family_registry.json, stubs, matrix, seed_script_registry.py,
   assistant_project.md). `--no-verify` (shared hooks; floor already red). No push of that branch.
2. **Commit in place, navigator worktree**: stage nav_reconcile.py, tests/test_nav_reconcile.py,
   ui_kits/research_navigator/, CH-research-navigator-reconcile-v1 manifests, grandfather json, stubs, matrix,
   seed, ic-003-shape-narratives.md, assistant_project.md. Junk stays untracked. `--no-verify`.
3. **Merge `grok/program12-slice1` into semanticos_impl** (`--no-commit`), resolve with a scratchpad script in
   the style of `resolve_merge.py`:
   - assistant_project.md: ours + incoming entries appended.
   - stubs / script-matrix / seed_script_registry.py: incoming new scripts get the next free SCR ids
     (SCR-512+; overlays are keyed by path), Records count updated.
   - F-114 → F-121 in incoming text only (current-findings section, CLAUDE.md Truths row,
     research_family_registry, program-12 manifests/docs that name it) + a "written as F-114 on
     grok/program12-slice1" note; existing F-114 untouched.
   - `src/features/crt_state_resolver.py`: restore ours (`git checkout --ours` hunk → keep `>=`);
     leave `tests/test_crt_state_resolver_ttl_boundary.py` out of the merge (it asserts `>`; stays on the
     grok branch).
   - Run `tests/research/test_timeframe_ladder.py`, `test_program12_parity_one_month.py`,
     `tests/test_current_findings.py`, `tests/test_closure_authority_index.py`. If ladder code breaks on the
     F-119 corpus_store API, report it rather than silently rewriting it.
4. **Merge `lane/research-navigator`**: same resolver for session log, stubs/matrix/seed/grandfather
   (nav_reconcile.py gets the next free SCR id). Run `tests/test_nav_reconcile.py`, `tests/test_script_registry.py`.
5. **Divergence-page branch for the resolver TTL** (trunk unchanged):
   - New `tools/feature_audit/resolver_ttl_data.py`: load H4 via `h4_loader.py`, run the active-config
     `CRTStateResolver` (construction as in `scripts/research/crt_state_confusion_matrix.py:331-360`) twice —
     trunk as-is, branch = subclass overriding `_check_expired` with strict `>` (no src edit). Count bars whose
     resolved state differs; write a `crt_state_resolved` entry (group `crt`) into `results/divergence_h4.json`
     with one `implementation` branch `resolver-expansion-ttl-strict` (formula `age > max_expansion_age_*`,
     note citing engine `_ttl_exceeded` and commit 63a6a1d; open only if ≥1 bar differs, else closed with numbers).
     State is categorical → chart as state ordinal or omit the window chart (`window` absent).
   - `render_divergence.py`: add the `crt` group to `GROUPS`; README rebuild table gets step 8c.
   - Rebuild (steps 1–9 + new step), copy `results/branch_mockup_rsi.html` →
     `docs/artifacts/2026-10-14_divergence-branches.html`, republish to the same artifact URL (keeps db picks).
   - SITS: if `tools/` is census-scoped, register the new script; otherwise note it.
6. Session log entries (assistant_project.md), commit the two merges + the page work separately,
   `--no-verify` (floor red), push semanticos_impl only.

## Verification
- Ladder, parity, nav_reconcile, state-entry tests pass (or failures reported with cause).
- `git grep -n "F-114"` shows only the original finding + the renumbering note; `git grep "F-121"` resolves.
- `git show HEAD:src/features/crt_state_resolver.py | grep "age >= max_candles"` still present.
- Governance floor re-run: report failed/passed vs the 13/866 baseline (navigator's grandfather resync may
  turn some script-registry reds green; new ids must not add reds).
- Republished page shows the new CRT section with the branch's bar count and a decision panel.
