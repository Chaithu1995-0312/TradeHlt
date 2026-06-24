# Collaboration Workflow — Tracking & Replay Setup

> Created: 2026-05-29 · Updated: 2026-05-29 · Milestone: n/a

## Context (why we're doing this)

You asked two things: *how does Claude reference the docs (the "soft waterfall")* and *is every plan/change tracked with a timestamp?* Investigating both surfaced the real need:

- The repo already has rich machinery for tracking and verifying changes — **but it's written for the LLM, not for you**, and it's spread across `CLAUDE.md`, `README.md`, `trigger-vocabulary.md`, the `assistant_project.md` doctrine header, and `replay-governance.md`. There is **no single plain-language place** that says: *here is how we work together, here is how I track every change, here is how you replay/verify it.*
- **Session logs are always timestamped** (mandatory `Date:` field, 81 entries) but **plans in `docs/plans/` are not** (kebab-case filenames, dates only sometimes appear in the body). The tracking trail therefore has a hole at the planning layer.

**Outcome:** one readable collaboration-workflow doc that ties the existing layers into a loop you can follow, **plus** closing the plan-timestamp gap so every plan is dated like every session-log entry. This is docs + a light enforcement test — **no `src/` or runtime change**, no new abstractions.

## What already exists (reuse, do not reinvent)

| Concern | Existing asset — point at it, don't rebuild |
|---|---|
| Turn ritual | `CLAUDE.md` §7 `ORIENT → PROBE → IMPLEMENT → SELF-DOCUMENT` |
| Change journal | `assistant_project.md` SESSION LOG blocks (Date/Topic/Decision/Open Questions/Next Step), mandated by `CLAUDE.md` §6 |
| Workflow loop | `docs/architecture/trigger-vocabulary.md` triggers + compositions (`Continue = Orient → Map → Next step → Validate → Log`) |
| SDLC roadmap | `assistant_project.md` doctrine header (M0–M5 milestones, standing rules) |
| Verify/replay gate | `docs/architecture/replay-governance.md` §6 (6-step byte-identical determinism gate) |
| Baseline before/after | `src/runtime/baseline_capture.py` → `results/baseline/{ts}_{label}/manifest.json` |
| Replay validator | `scripts/misc/trade_replay_validator.py` (deterministic per-candle RR recompute, `MAX_RR_DELTA=0.05`) |
| Audit trail | `configs/promotion_log.jsonl` (append-only PROMOTED / PROMOTION_FAILED) |
| Five Governance Questions | `assistant_project.md` doctrine header |
| Act-vs-involve + plain-language rule | memory `feedback_collaboration_protocol.md` |
| Doc-alignment test pattern | `tests/test_control_plane_doc_alignment.py` |

## Recommended approach

### 1. New doc — `docs/architecture/collaboration-workflow.md` (user-facing, plain language)
A single short doc written *for the user*, not the LLM. Sections:
- **How we work together** — the act-vs-involve rule (act at ~100% confidence on reversible work; involve you on ambiguous/judgment parts; keep momentum) and plain-language communication, lifted from `feedback_collaboration_protocol.md`.
- **The turn loop** — `ORIENT → PROBE → IMPLEMENT → SELF-DOCUMENT` restated in everyday words (state scope → ask sharp questions → do it → log it).
- **How I track every change (3 layers)** — Plan (`docs/plans/`, *what we'll do*) → Git commit (*the code change*, `feat/fix/test` scopes) → SESSION LOG (`assistant_project.md`, *the dated journal*). One diagram/line showing plan → implement → log, all timestamped.
- **The "explain every change" contract** — each implemented change is explained as: *what changed · why · blast radius · how to replay/verify*, then logged.
- **How you replay & verify a change** — the plain recipe: `baseline_capture.py` (snapshot) → implement → re-run same CSV + `slippage_seed` → assert byte-identical trade ledger → score the Five Questions. Link `replay-governance.md` §6 for the authoritative gate.
- **Quick reference** — the trigger words in one table (`Continue / Next step / Next plan / Validate / Implement / Orient / Map / Audit / Plan / Log`) pointing to `trigger-vocabulary.md` for detail.

Keep it scannable (one screen of headings); deep detail stays in the linked authoritative docs.

### 2. Close the plan-timestamp gap (make plans "covered" like sessions)
- Adopt a standard plan header on every `docs/plans/*.md`:
  `> Created: YYYY-MM-DD · Updated: YYYY-MM-DD · Milestone: M<n> (or n/a)`
- Backfill the two existing plans (`claude-architecture-migration-eager-wreath.md`, `kind-dazzling-frost.md`) with their dates (recover from body/git).
- Add the rule to the **Plan** trigger in `CLAUDE.md` §12 and `docs/architecture/trigger-vocabulary.md` (one line: every plan carries a Created/Updated date — mirrors the §6 SESSION LOG mandate).

### 3. Make the new doc discoverable in the "soft waterfall"
- Add a row to the `CLAUDE.md` §2 companion-docs table and a bullet in §3.4 "Key files."
- Add it to the `README.md` docs map under the operating-rules tier.

### 4. Light enforcement test (so the gap stays closed)
Extend `tests/test_control_plane_doc_alignment.py` (or a sibling `tests/test_plan_timestamps.py`) with a test asserting **every `docs/plans/*.md` contains a `Created:` date matching `\d{4}-\d{2}-\d{2}`** — the enforceable analogue of the session-log Date mandate. Follows the existing read-a-doc-and-assert pattern.

## Files to create / modify
- **Create:** `docs/architecture/collaboration-workflow.md`
- **Modify:** `CLAUDE.md` (§2 table row, §3.4 bullet, §12 Plan-trigger timestamp rule)
- **Modify:** `README.md` (docs-map entry)
- **Modify:** `docs/architecture/trigger-vocabulary.md` (Plan-trigger timestamp rule)
- **Modify:** the two existing `docs/plans/*.md` (add dated header)
- **Modify/Create:** `tests/test_control_plane_doc_alignment.py` (or `tests/test_plan_timestamps.py`) — plan-timestamp assertion

## Verification (end-to-end)
1. **Read test:** open `docs/architecture/collaboration-workflow.md` — does it explain, in plain language, how we work + how to track + how to replay, on roughly one screen?
2. **Timestamp coverage:** both existing plan files now show a `Created:` date header.
3. **Discoverability:** the new doc is linked from `CLAUDE.md` §2/§3.4 and `README.md`.
4. **Tests:** `python -m pytest tests/test_control_plane_doc_alignment.py -q` (and the new plan-timestamp test) → all pass.
5. **Replay sanity (optional, proves the recipe):** run `python src/runtime/baseline_capture.py --label collab-setup` and confirm a manifest lands in `results/baseline/` — demonstrates the before/after snapshot step the doc describes.

## Out of scope
- No change to `src/`, the engines, the replay engine, or runtime behavior.
- No new automation/hooks beyond the one alignment test.
- Not rewriting `trigger-vocabulary.md` — only adding the one timestamp rule and cross-linking.
