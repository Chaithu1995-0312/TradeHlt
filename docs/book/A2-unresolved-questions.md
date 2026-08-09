# Appendix A2 — Unresolved Questions (Rollup)

Status of this chapter: Written (updated post-Grok reconciliation pass, 2026-08-07)

## Why this chapter exists

Per this book's own charter: "if understanding is impossible, do not invent." Every chapter that hit
a genuine gap in evidence recorded it locally rather than guessing. This appendix collects those in
one place — and, after the Grok review pass (and a follow-up reconciliation pass that re-verified
several of its claims directly against source), also records what was **closed in the book** and
what was **fixed at the source** without changing production trading-system code.

## What you need to already know

This is a reference appendix, not a narrative chapter — each item links back to the chapter that
owns the full context.

## Fixed at the source (2026-08-07 reconciliation pass)

Unlike the "resolved in the book" items below, these two touched the primary reference docs
themselves, not just book chapters — the exact fix the earlier Grok pass explicitly left out of
scope.

| Item | Resolution | Where |
|---|---|---|
| `docs/reference/schemas.md` §4 stale 38-dim/v3.0 table | **Corrected to 39-dim/v4.0**, matching `src/features/feature_schema.py` field-for-field (macd_hist split 18–19, `candle_range` rename at 28), `SCHEMA_V3_ALIASES` included | `docs/reference/schemas.md` §4; [Ch.07](07-feature-pipeline.md) |
| `docs/reference/testing.md` stale file-count header | **Corrected** from "116 files / 15 dirs (2026-06-12)" to a fresh, exact **411 `.py` files / 415 incl. fixtures, across 25 directories (2026-08-07)** | `docs/reference/testing.md`; [A1](A1-testing.md) |

A byproduct worth recording: this book's own earlier **"~1,200+ files"** estimate for `tests/` (from
the original A1/A2) was itself wrong — traced to a count that included `__pycache__` compiled
bytecode. Corrected in [A1](A1-testing.md).

## Resolved in the book (Grok review pass — no production code changes)

| Item | Resolution | Chapter |
|---|---|---|
| INOUT `src/inout/` vs `archive/inout_legacy/` | **Name collision.** Current `src/inout/` = data fetchers only; archived tree = parallel execution rail retired 2026-05-02 | [Ch.15](15-live-execution-and-inout.md) |
| Program 9 missing from research chapter | **Chaptered from pre-registration** (`docs/research/preregistration-program-9.md`); run verdicts still artifact-bound. A follow-up pass added direct evidence the one attempted Stage-1 run appears **stalled**, not merely unresolved (0-byte log, ~2-min pid window, `H-016` registry still `status: open`) | [Ch.19](19-research-programs.md) |
| ATR / F-057 "flag only" passivity | **Proposed remediation options + trade-offs** added; still OPEN pending owner. A follow-up pass corrected the file citation (the function is `src/core/gate_intelligence.py:24`, not `crt_engine_v2.py`) and found the bug is **narrower than stated**: the backtest path (`crt_engine_v2.py::build_trade`) correctly uses a separate absolute `state.atr_abs` — only the **live path** (`live_engine_hook.py::_build_engine_input`) feeds the relative feature in | [Ch.13](13-execution-planner.md) |
| Measurement Contract gap | **5-step seal path** proposed; still 0 sealed instances in-repo unless registry says otherwise | [Ch.20](20-research-platform.md) |
| MSIP "no treatment" | **Orientation brief** in governance field guide | [Ch.18](18-field-guide-governance.md) |
| Density / meta overwhelm | **Quick Start** chapter added | [Ch.00](00-quick-start.md) |
| 22 un-chaptered packages | **Orientation map** added (not full chapters) | [Ch.04](04-architecture-at-a-glance.md) |

## Still open — book-scope gaps

- **Repository Encyclopedia** — charter in [Chapter 24](24-repository-encyclopedia.md);
  **E0–E6 + E1b + JSONL twin DONE** (`docs/book/encyclopedia/`, including
  `encyclopedia_rows.jsonl`). Optional later: relationship graph edges in JSONL; agent query UI.
- **Repository Semantic Coverage (NOT_YET)** — documentation is STRONG; Semantic OS skeleton only
  (concepts/boundaries/journeys still walking-skeleton; `owner_surface` 100% UNATTRIBUTED).
  **PR-2 CT-*** shipped; **PR-3 JN-001** full 7-step candle journey + CN-003..CN-006 shipped
  (behavior_coverage 7/7 GREEN). Concept/boundary *object* coverage still ~1.3% (RED) until
  more package membership. Measure:
  [`docs/governance/REPOSITORY_COVERAGE_DASHBOARD.md`](../governance/REPOSITORY_COVERAGE_DASHBOARD.md).
  Next: PR-4 concept wave / PR-5 boundary refinement / attribution overlays.
- **Full-depth Part VI–VIII** — chapters 16–23 remain orientation-level relative to their source
  corpora (~250 governance files, ~475 research files). Deepening is expected future book work.
- **Optional MSIP dedicated chapter** — brief exists; full gate-by-gate narrative only if MSIP
  re-enters active execution.
- **Program 9 numeric verdict** — design is chaptered; Stage-1/Stage-2 results must still be read
  from artifacts / findings, not assumed.
- **Program 7 (Open Interest)** — named as out-of-scope for Program 6; status not independently
  verified as run.
- **Deeper Part VIII implementation walk** — agent/control-plane/multi-LLM chapters improved
  slightly but are not full replacements for `docs/reference/agent-reference.md`.

## Still open — real repository issues (code; **not** fixed by this book pass)

> User instruction for this pass: **no trading-system code changes.** These remain tracked, not
> remediated — the two doc-drift items that *were* in this category moved to "Fixed at the source"
> above.

- **ATR unit mismatch, live path only** — `live_engine_hook.py::_build_engine_input` (`:442`) feeds
  `compute_crt_levels` (`src/core/gate_intelligence.py:24`) the close-relative `atr` feature instead
  of an absolute value; confirmed the backtest path (`crt_engine_v2.py::build_trade`) is unaffected
  (uses `state.atr_abs`). Real geometry defect on any live run; options A/B/C in
  [Chapter 13](13-execution-planner.md); awaiting owner decision.
- **F-057 `CRTConfig` programmatic split-brain** — OPEN; options 1/2/3 in Chapter 13; "backtest
  Phase 2."
- **Research Measurement Contract** — schema frozen, 0 sealed `MC-*` (verify registry); path in
  [Chapter 20](20-research-platform.md).

## Verification gaps (assumed from docs; not re-proven this pass)

- Whether Wyckoff / Market Profile / Order Flow interpreters have code beyond scaffolding
  ([Chapter 9](09-interpreters-pattern-contract.md)).
- Whether every tool in `docs/reference/agent-reference.md` is end-to-end reachable
  ([Chapter 21](21-ai-automation-agent.md)).
- Full body of `docs/reference/architecture.md` beyond header/orientation
  ([Chapter 4](04-architecture-at-a-glance.md)).

## Out of scope for this pass (explicit)

- Implementing ATR or F-057 remediations (code + parity + promotion) — options-only per explicit
  user selection; still requires owner decision + construction protocol + parity proof.
- Sealing `MC-*` instances or running Program 9 Stage drivers (resuming or restarting the stalled
  run is a research-execution decision, not a documentation one).
- Adding CLAUDE.md companion-row (already present from an earlier session).

---
**Previous:** [Appendix A1 — Testing the System](A1-testing.md) · **Next:** — (last chapter; return to [the Table of Contents](README.md))
**Related:** every chapter linked above.
**Memory:** none dedicated — this appendix is the book's own open-loop tracker.
