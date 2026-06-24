# Plan — Frozen-Sentence TruthConflict + Honest Self-Report Metrics Layer

## Context
A proposal (routed through the multi-LLM pipeline) suggested automating extraction of "7 empirical
observation metrics" from existing logs, to be used (in part) to settle a documentation
`TruthConflict`. Read-only investigation surfaced three facts that reshape the work:

1. **The 7 metrics are not a canonical artifact** — the fields (GP/Act/Rec/Find/Ent/NS/KROI) and the
   term "Metrics Block" appear nowhere in `docs/`, `CLAUDE.md`, or `assistant_project.md`. They are
   introduced for the first time in the proposal.
2. **No existing log contains a Metrics Block** — `grep 'GP:1' assistant_project.md` → 0. Any
   extractor is therefore *prospective only*; "works on current free-text logs" is false. (The
   proposal's `artifacts/assistant_project.md` path is also wrong; the file is at repo root.)
3. **The `TruthConflict` is the frozen-sentence DOC_DRIFT** between `CLAUDE.md` §6.1 (fuller wording,
   includes the goal-probability clause) and `docs/architecture/intelligence-compounding.md:11-13`
   (shorter variant, confirmed live). Per §6.2 rule 3 this is a *user decision*, not something a
   multi-session self-report study should "prove."

**User decisions (this session):** (a) do **Both** — resolve the conflict *and* build the metrics
layer; (b) frame the metrics strictly as **honest self-report / compliance telemetry with zero
authority**; (c) keep the two efforts **independent** — the metrics never settle the TruthConflict.

**Epistemic guardrail (binds the whole plan, per §6.5 Authority Ladder + E-001):** the 7 metrics are
self-rated grades. Automating their extraction tabulates self-report; it does not make them
empirical. They may inform personal/session hygiene; they may **never** gate behavior, settle a
TruthConflict, or "prove" a wording variant superior.

---

## Workstream A — Resolve the frozen-sentence TruthConflict (1-line doc edit)

**Winner (user choice):** §6.1's fuller wording, with the goal-probability clause.

**Edit:** `docs/architecture/intelligence-compounding.md` lines 11-13 — replace the blockquote's
final clause so it reads the §6.1 variant:
> …because intelligence is an ROI-weighted belief change **that increases the probability of
> achieving the user's long-term objectives** — not accumulated data.

**Sync / safety:**
- No test pins this text (verified: `grep` over `tests/` → no match) → no test change.
- §6.2 rule 4 (preserve history): leave the panda report
  [`docs/implementation_plan/c-users-hi-downloads-...-imperative-panda.md`](docs/implementation_plan/c-users-hi-downloads-intelligence-compo-imperative-panda.md)
  as-is — it documents the drift and its resolution.
- Optional one-line note in that report's verdict marking the conflict `RESOLVED` (date + winner),
  append-discipline only.
- Hash-neutral (doc-only). No `_compute_hash.py` run needed.

---

## Workstream B — Metrics Block as optional honest self-report telemetry (independent of A)

### B1 — Define the 7 metrics canonically (do this first; they don't exist yet)
Extend the existing owner of the operational hook rather than creating a new doc
(§6.2 existing-doc-first + minimize-doc-count):
- Add a **"Metrics Block (optional self-report telemetry)"** subsection to
  `docs/architecture/intelligence-compounding.md` (it already owns the operational hook + evolution
  path). Include: the field legend (stable order GP|Act|Rec|Find|Ent|NS|KROI), the one-line format,
  and an explicit **epistemic-status caveat** encoding decision (b)/(c) above — self-report, zero
  authority, never settles a TruthConflict or gates behavior.
- Annotate each field's epistemic tier so honesty is visible:
  - **Has an objective proxy (prefer the proxy over self-report):** `Find` (already enforced by
    `test_current_findings.py`), `Ent` (MEMORY.md / log byte-size vs limit — the system already
    flags MEMORY.md 24.9KB > 24.4KB), `NS` (detectable: did the turn reference the frozen sentence).
  - **Genuinely self-report:** `GP`, `Act`, `Rec`, `KROI`.
- Add a thin pointer in `CLAUDE.md` §7.4 (one line: "optionally append a `**Metrics**` block — see
  intelligence-compounding.md; self-report only, no authority"). Keep it **optional** — do not make
  it a §6 mandate.

### B2 — Prospective extractor (small, read-only, stdlib)
- `scripts/metrics/extract_metrics.py` — thin parser (no trading/production logic; sibling of
  `scripts/analysis/*`). Reads repo-root `assistant_project.md` (correct path), regex-matches
  `**Metrics**\nGP:...|...` blocks, emits structured dicts / JSON. Robust to absent blocks (returns
  `[]`, prints a notice that the convention is prospective).
- `argparse` CLI: `--file` (default repo-root log), `--json` (machine output), `--since <ISO date>`.
- Reuse the existing console-safe path (`src/utils/console_safe.py`) for any non-ASCII output
  (Windows cp1252 constraint, CLAUDE.md §4).

### B3 — Minimal test (per the doctrine-test-enforcement pattern)
- `tests/test_extract_metrics.py` — feed a sample log string with one Metrics Block, assert the
  parser returns the expected dict (stable field order, correct splitting). Assert empty input →
  `[]`. Shell is testable; the self-ratings' *meaning* stays doctrine (mirrors how
  `test_session_log.py` tests structure, not soundness).

### B4 — (Optional, note only — not v1) Reality cross-check
Where an objective proxy exists (B1), the extractor *could* later flag divergence between a
self-reported field and its proxy (e.g. self-reported `Ent:L` while MEMORY.md is over limit). This
is a genuine honesty mechanism but is deferred — keep v1 to pure extraction (no premature framework).

---

## Sequencing
1. Workstream A (1-line edit + optional RESOLVED note) — independent, ship first, trivial.
2. B1 (canonical definition + caveat + §7.4 pointer).
3. B2 (extractor) ‖ B3 (test).
4. B4 deferred.

A and B share no code path and no decision dependency (per user instruction (c)).

## Verification
- **A:** re-read `intelligence-compounding.md:11-13`; confirm byte-match with CLAUDE.md §6.1's
  sentence. Run `pytest tests/test_session_log.py tests/test_current_findings.py` (should stay green
  — no enforced text changed).
- **B:** `pytest tests/test_extract_metrics.py`. Run `python scripts/metrics/extract_metrics.py`
  against the live log → expect `[]` + the prospective-convention notice today; add one Metrics Block
  to a future SESSION LOG entry and confirm it now extracts to a correct dict.
- **Doctrine:** confirm `pytest tests/test_session_log.py` still passes (optional block is
  non-mandatory by design — `test_session_log.py:11` does not require even the Belief Update field).

## Out of scope / explicitly NOT doing
- Not making the Metrics Block mandatory (no change to `test_session_log.py`'s required fields).
- Not using any metric to settle the frozen-sentence conflict or gate behavior (decision (b)/(c)).
- Not building Stage-2 `intent.json` / `decision.json` / `invariant.json` artifacts (premature).
