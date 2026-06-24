# Plan — Harden CLAUDE.md's doctrine-only mechanisms into test-enforced ones

## Context

Discussion thread (LeCun critique → CLAUDE.md as a "bolt-on world-model/memory" answer)
surfaced two weak links in the prosthesis:

- **#4 prosthetic-grounding fragility** — the SESSION LOG / belief-update / "same-turn"
  mandates are **prose-only**. A single non-compliant turn silently breaks the compounding
  chain. Grounded by Explore agent: ZERO tests touch `assistant_project.md`, the SESSION LOG
  block, the `Belief Update / ROI / Goal` field, or `MEMORY.md`.
- **#3 context-ceiling** — every always-loaded artifact is **append-only, unbounded, no
  rotation/consolidation**. Grounded: `assistant_project.md` = 232 KB / 2,456 lines / 122
  entries (~2 KB/session, no cap); `docs/current-findings.md` = 44 KB / 26 findings (terminal
  F-003/F-007 kept inline forever); CLAUDE.md findings table = 24 always-loaded rows; only
  bounding mechanism is the freshness-CI flag (`test_current_findings.py`), which *flags* but
  never *removes*.

Core realization: the **same technique** (convert a doctrine into a mechanical CI invariant)
hardens #4 AND bounds #3. What it can NEVER do is enforce the *semantics* (truth of a belief,
soundness of ROI) — that residual is irreducible and stays doctrine.

## Scope boundary (the shell vs. the semantics)

| Test-enforceable (the shell — DO) | NOT test-enforceable (the semantics — leave doctrine) |
|---|---|
| SESSION LOG block exists, parses, all 6 fields present | Whether the belief update is *true* |
| `Belief Update` line non-empty; if ≠"none" contains Goal:/Belief:/Action: | Whether the ROI reasoning is *sound* |
| Every finding `Evidence:` pointer resolves to a real file/line | Whether a conflict was *honestly surfaced* vs. silently resolved |
| Flipped finding has a non-empty `Reversal:` field | Whether the *right* finding was updated |
| Artifact size caps (forces consolidation) | — |

## Work items

### A. Harden #4 — convert grounding-shell mandates to tests
1. **`tests/test_session_log.py` (new)** — parse `assistant_project.md` into `📝 SESSION LOG
   ENTRY` blocks; assert each has all 6 fields (Date/Topic/Decision/Belief/Open/Next), Date is
   `YYYY-MM-DD`, and `Belief Update / ROI / Goal` is non-empty (and when ≠ "none" contains the
   `Goal:`…`Belief:`…`Action:` tokens). Mirror the parsing style of `tests/test_current_findings.py`.
2. **Evidence-resolvability** — extend `tests/test_current_findings.py`: every `Evidence:`
   that is a `path:line` or `docs/...` link must resolve (reuse the `_resolve()` helper in
   `tests/test_doc_citations.py`). Closes the gap where Evidence is *present* but dangling.
3. **Reversal-on-flip** — in `tests/test_current_findings.py`, assert any finding whose Status
   moved to SUPERSEDED/RETIRED (detected via `Supersedes:`/`Reversal:` presence) carries a
   non-empty `Reversal:` line.
4. **Commit-linkage hook (CI, not pytest)** — a pre-commit/CI check: if a commit touches
   `src/**` or `configs/production/**`, require a new SESSION LOG entry dated today with a
   non-trivial Decision/Output. Converts "every *response*" (uncheckable — responses aren't
   durable) into "every code-changing *commit*" (checkable). Deliberately ignores pure-discussion
   turns; targets the consequential ones.

### B. Bound #3 — convert "never delete" into "archive past a cap"
5. **Terminal-findings migration** — move SUPERSEDED/RETIRED findings out of
   `docs/current-findings.md` into `docs/analysis/findings-archive.md`, leaving a one-line
   tombstone + pointer in the living doc. Add a test asserting the living doc contains **no**
   terminal-status findings (they must live in the archive). Keeps §6.2 rule-4 history while
   delinting the hot path.
6. **Session-log rotation** — `scripts/maintenance/rotate_session_log.py`: keep the doctrine
   preamble + last ~20 entries in `assistant_project.md`; spill older entries to
   `docs/analysis/session-log-archive/`. Add a test capping `assistant_project.md` line count.
   Safe because durable conclusions are already distilled into findings + memory files (the log
   is forensic-replay redundant for everything else).
7. **Consolidation cadence** — wire the existing (currently-unused) `consolidate-memory` skill
   into the freshness gate: when non-terminal finding count or memory-file count crosses a
   threshold, CI emits a "consolidate" action item.

## Critical files
- `tests/test_current_findings.py` (extend: Evidence-resolve, Reversal-on-flip, no-terminal-in-living, cap)
- `tests/test_doc_citations.py` (reuse `_resolve()`)
- `tests/test_session_log.py` (new)
- `docs/current-findings.md` + new `docs/analysis/findings-archive.md`
- `assistant_project.md` + new `docs/analysis/session-log-archive/`
- `scripts/maintenance/rotate_session_log.py` (new)
- CI config / pre-commit hook for item 4

## Verification
- `pytest tests/test_session_log.py tests/test_current_findings.py tests/test_doc_citations.py -q` green.
- Deliberately corrupt a SESSION LOG block (drop the Belief field) → new test goes red.
- Deliberately leave a SUPERSEDED finding in the living doc → migration test goes red.
- Run `rotate_session_log.py` on a copy → `assistant_project.md` shrinks below cap, archive
  gains the spilled entries, no entry lost (count conserved).
- Confirm determinism per `docs/reference/testing.md` (no flakiness from date-based asserts —
  freeze "today" via a fixture).

## Non-goals / honest limits
- Does NOT make the model's beliefs *correct* — only their *form* checkable. The residual
  prosthetic-grounding fragility (semantics) is irreducible by design and stays doctrine.
- Does NOT change runtime/spine behavior; docs + tests + maintenance scripts only (additive).
