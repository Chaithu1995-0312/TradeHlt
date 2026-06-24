# Complete the docs/ uppercase→lowercase reorganization (git-stage the prior content migration)

## Context
A prior session reorganized the **entire** `docs/` tree (uppercase flat files → lowercase, foldered:
`reference/`, `architecture/`, `analysis/`, `governance/`, `topics/`, `intent/`, `operations/`,
`plans/`, …), **moved the content**, and **repointed CLAUDE.md** to the new lowercase paths — but
**never git-staged it**. Verified facts (this session, read-only):
- HEAD tracks **38** docs files (the old structure); **289** docs files exist on disk (the new one).
- Working tree: ~**26** old paths show as **deleted (`D`)**, ~**250** new paths are **untracked (`??`)**,
  **3** tracked files **modified (`M`)** (`architecture/codebase-state-map.md`, `flow_context_layer.md`,
  `current-findings.md`).
- Content was genuinely moved: `git show HEAD:docs/CONVENTIONS.md` == on-disk
  `docs/reference/conventions.md` (270 lines, identical). CLAUDE.md already cites the new paths.
- The new structure is internally consistent: **`test_doc_citations` + `test_topic_docs` +
  `test_current_findings` = 13 green** against the on-disk files.

So "finish the migration" = **make git reflect the completed, verified, already-referenced reality.**
This is **unrelated** to the MT5 analytics subsystem (done + committed at `mt5-analytics-v0.3.1`; its
record lives in git, `mt5_analytics/MIGRATIONS.md`, and memory — not lost by replacing this plan).

## Safety doctrine (I did NOT author these docs — §6.2 rule 4 + deletion-safety)
The 26 deletions are safe **only because** the content is preserved in the new lowercase locations.
**Step 1 verifies this for the whole deleted set before anything is committed**; any deleted doc whose
content has **no** new home is surfaced as a `TruthConflict` and **excluded** (never committed as a
silent truth-loss).

## Steps
1. **Verify content moved (no truth lost).** For each `D docs/<OLD>`, confirm a new on-disk file holds
   its content (compare `git show HEAD:docs/<OLD>` to the candidate new path). Script the comparison
   over the full deleted list; CONVENTIONS already spot-verified identical. **Abort + surface** any
   orphan deletion.
2. **Stage the reorg.** `git add -A docs/` (stages ~250 new source files + ~26 deletions + 3 mods) —
   ONLY the `docs/` pathspec, so the many unrelated pre-existing `src/`/config changes stay untouched.
3. **Generated-file hygiene (small, explicit decision).** Default = **commit as-is** (the build
   products are small, CLAUDE.md/tests reference some, e.g. `architecture/citation-map.generated.md`,
   and a faithful snapshot is the goal). The session-log archive `docs/analysis/session-log-archive/`
   is the §6.2-rule-5 history home → **commit** (preserve spilled session logs). Only flag, not act:
   `docs/research-readiness/*-report.json` are pure regenerable data — could be `.gitignore`d in a
   later hygiene pass, not here.
4. **Verify.** Re-run `pytest tests/test_doc_citations.py tests/test_topic_docs.py
   tests/test_current_findings.py` (must stay **13 green**); `git status docs/` clean.
5. **Commit.** `docs: complete uppercase->lowercase reorganization (stage prior content migration)`.
6. **Then the ORIGINAL ask (separate small commit).** Record the new top-level **`mt5_analytics/`**
   package + the **`manual_tools/`** execution-separation exception in `docs/reference/conventions.md`
   (folder-placement table) and `docs/reference/architecture.md` (directory tree). Re-run doc tests;
   commit `docs(reference): record mt5_analytics package + manual_tools placement`.

## Reuse / governance
Reuses the existing doc-governance gates (`tests/test_doc_citations.py` ±30-line window,
`test_topic_docs.py`, `test_current_findings.py`) as the correctness guardrail — no new test
infrastructure. Aligns with §6.2 (existing-doc-first, synchronize, preserve history, minimize doc
count) and the §6.3 Citation Sync Mandate.

## Verification (end-to-end)
- The 3 doc-governance tests stay green before and after staging.
- `git status docs/` is clean (only any intentionally-noted regenerable data remains untracked).
- `git show --stat` of the reorg commit = a coherent docs-only change (no `src/`, config, or
  `mt5_analytics/` paths swept in).
- CLAUDE.md's lowercase citations now resolve to **tracked** files.

## Risks
One large but coherent commit (~280 docs path changes = a single reorganization). Content is
preserved + verified (Step 1) and the governance tests pass, so the risk is git-hygiene, not
truth-loss. It does touch the canonical docs the whole governance layer cites — which is exactly what
the doc tests validate, and they are green.
