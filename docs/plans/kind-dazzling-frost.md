# Plan — Semantic docs reorg (full reshuffle, kebab-case)

> Created: 2026-05-29 · Updated: 2026-05-29 · Milestone: n/a

## Context

`docs/` is a flat pile of SCREAMING_SNAKE reference docs mixed with ad-hoc subfolders, plus
real defects: a misspelled `HumanLnaguageAnalysis/`, comma-filenames, two colliding
`ARCHITECTURE.md` (`docs/` + `docs/control_plane/`), a loose `architecture-diagram.html`, and
no `docs/` index. The user chose a **full semantic reshuffle** with **kebab-case everywhere**.

This is high-blast-radius: **~86 path references** (CLAUDE.md 33, assistant_project.md 28,
README.md 20, AGENTS.md, memory) + inter-doc links + **4 hardcoded code/hook/test paths**:
`gen_code_map.py` writes `docs/architecture/code-map.generated.md`; `generate_cli_matrix.py`
writes + `test_control_plane_doc_alignment.py` reads `docs/reference/cli-matrix.md`; the Workstream-A
PostToolUse hook copies plans into `docs/implementation_plan/`. All four must move WITH the docs.

**Two scope boundaries (my call, flagged):**
- **Historical text is an audit trail — not rewritten.** `assistant_project.md` SESSION LOG
  entries and the `docs/analysis/` reports describe past work with the paths as they were;
  I only update the **doctrine header** of `assistant_project.md` and make *links* resolve, never
  rewrite historical prose.
- The hook lives in `.claude/settings.local.json`; editing it goes through the **update-config**
  skill (authoritative for hook schema).

## Target taxonomy (kebab files, lowercase folders)

```
docs/
  readme.md                      NEW — docs index + the naming/structure convention
  reference/                     stable "how it works / how to work" + process refs
    architecture.md  conventions.md  schemas.md  config-reference.md  cli-matrix.md*
    testing.md  governance.md  agent-reference.md  example-service.py  control-plane.md
  architecture/                  the "own the codebase" maps / context units
    goal.md  signal-flow.md  codebase-state-map.md  service-boundary-map.md
    event-taxonomy.md  code-map.md  code-map.generated.md*  replay-governance.md
    llm-governance-layer.md  trigger-vocabulary.md  architecture-diagram.html
    services/{_template.md, decision-spine.md}
  analysis/                      historical snapshots (kebab the files) + readme.md
  plans/                         was implementation_plan/*  (hook target → update hook)
  handover/jarvis-crt-handover-v3.md
  human-language-analysis/       was HumanLnaguageAnalysis/ (typo fixed; commas→hyphens)
```
`*` = frozen path consumed by code — its generator/test is updated to the new path (below).

**Rename rule:** `SCREAMING_SNAKE.md` → `kebab-case.md`; folders → `lowercase-kebab`; dates kept
(`system-analysis-report-2026-04-21.md`); `_template.md` → `_template.md`. Collisions resolved by
semantic rename (`control_plane/ARCHITECTURE.md` → `reference/control-plane.md`).

## Execution (scripted, to avoid ~90 hand-edits)

1. **Move/rename** every file with `git mv` (preserves history) per the map above — do moves in a
   throwaway script that records an explicit `old → new` dict (the single source of truth).
2. **Rewrite references** with the same dict, applied across the *living* fileset only:
   `CLAUDE.md`, `README.md`, `AGENTS.md`, the `assistant_project.md` **doctrine header only**, all
   `docs/**/*.md` (inter-doc links), memory `*.md`, and the code files
   (`gen_code_map.py`, `gen_pyan.py`, `generate_cli_matrix.py`, `tests/test_control_plane_doc_alignment.py`).
   Strategy: replace **full relative paths** from the dict first, then a **basename** pass
   (`event-taxonomy.md`→`event-taxonomy.md`) to catch same-dir links; finally fix `../` prefixes for
   the docs that changed folder (the `reference/` group, `signal-flow.md`, `governance.md`).
3. **Frozen paths:** point `gen_code_map.py` `_MERMAID_OUT` → `docs/architecture/code-map.generated.md`;
   `generate_cli_matrix.py` out_path + the test's read path → `docs/reference/cli-matrix.md`; update the
   Workstream-A hook (`docs/implementation_plan/` → `docs/plans/`) via the **update-config** skill.
4. **Add `docs/readme.md`** — the index (mirrors the 4-tier map, now with kebab paths) + the naming
   convention as the standing rule for future docs.
5. **Regenerate** to prove the generators write to the new paths: run `gen_code_map.py` and
   `generate_cli_matrix.py`; confirm output lands at the new locations.

## Out of scope
No `src/` runtime/behavior change. Historical SESSION-LOG / analysis prose not rewritten. Root
operating files (`CLAUDE.md`, `README.md`, `AGENTS.md`, `assistant_project.md`) stay at repo root.

## Verification
- **Link checker (the safety net):** a script walks every `*.md` under repo root + `docs/**`, extracts
  `](path)` links, resolves them relative to the file, and reports any MISS. Must be **zero misses**.
- **No stale paths:** `grep -rn` the repo (excl. venv/worktrees + historical sections) for any
  surviving `docs/reference/architecture.md`, `SCREAMING_SNAKE.md` doc names, `implementation_plan/`,
  `HumanLnaguageAnalysis`, `docs/reference/cli-matrix.md` → expect none in living files.
- **Code/test/hook:** `python scripts/analysis/gen_code_map.py` writes `architecture/code-map.generated.md`;
  `generate_cli_matrix.py` writes `reference/cli-matrix.md`; `pytest tests/test_control_plane_doc_alignment.py`
  passes; a throwaway plan write lands in `docs/plans/` (hook).
- **git status:** all moves show as renames (R); `git ls-files` clean.
- Append a `📝 SESSION LOG ENTRY` to `assistant_project.md`.
```
