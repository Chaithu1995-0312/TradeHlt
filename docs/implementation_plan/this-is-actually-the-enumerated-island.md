# Plan — Reconcile the multi-model design essay against the repo

## Context

You pasted a long multi-model design discussion (expectancy math → goal-driven "work
backward from capital" architecture → multi-LLM tournament → story ontology → "invert:
discover the mathematical factor that explains profitability, then label it a story" → an
11-phase autonomous research platform). There is no code request in it.

The problem this plan solves: **most of that design is already built or already decided in
this repo, and one part of it re-enters a narrowly-scoped question your evidence has already
investigated and parked.** Left unreconciled, the essay reads as a fresh mandate to build an
11-phase platform — re-deriving locked decisions (D-01…D-27) and re-funding the
OHLCV-feature→entry sweep that decision **D-16** parks.

You chose **Reconcile vs repo** (read-only, no code). Deliverable: **one new doc** mapping
every essay fragment to a verdict, with the falsification claim scoped **precisely** (see the
correction below) so it does not over-generalize beyond what the repo documents.

## Correction folded in (from your review)

Do **not** write "math-first is falsified." Write the narrow, defensible statement:

> The specific program of searching for profitable **entry** factors by sweeping combinations
> of **OHLCV-derived** features has already been extensively investigated under the documented
> scopes and is currently parked by **D-16**. This does **not** preclude future mathematical
> research over genuinely new information domains or ontologies.

Also: the essay's "invert to a frozen research spine" is **not new** — the ERP already froze
`Data → Verified Features → Events → Opportunity → Engine Evidence → Honest Outcomes →
Demote Zero-Δ → Policy` (D-09). The essay rephrases it; it does not introduce it.

## Deliverable

Create **`docs/research-readiness/erp-design-essay-reconciliation.md`** (new; matches the
`erp-*` / `edge-research-platform-*` doc family). Doc-only, additive, zero code/config,
hash-neutral. Link it from the "read first" board
[`erp-decision-board-and-story-authority.md`](docs/research-readiness/erp-decision-board-and-story-authority.md)
Part D table (one row) so it is not orphaned (rule 1, existing-doc-first).

## Doc structure

1. **Header** — date, `Authority: reconciliation / design-explanation only — no production
   authority`, purpose, and the caveat: the F-019/F-036 anchors are `PROVISIONAL pending E4`
   (D-16 note + the E4 revalidation gate) — the null is *pending revalidation*, not eternally
   settled.

2. **One-line verdict** — the essay is ~85–90% a re-derivation of the `EDGE_RESEARCH_PLATFORM`
   program; ~10–15% is genuinely additive and all of it is descriptive/measurement.

3. **Reconciliation table** (uses your corrected classification):

   | Essay fragment | Verdict | Repo anchor |
   |---|---|---|
   | Expectancy / compounding / "positive EV, repeat, compound" | ALREADY-LOCKED | D-02, `goal.md`, G001 |
   | Goal-driven "work backward" arch + frozen research spine | ALREADY-LOCKED | D-09 canonical loop, `goal.md` |
   | Research platform (not "I have a strategy") | ALREADY-LOCKED | D-01 |
   | Per-module "each answers one question" table | ALREADY-BUILT (descriptive) | `service-boundary-map.md` |
   | Multi-LLM: same package, score-not-vote, leaderboard | ALREADY-DESIGNED | D-08, D-18/D-27, `edge-research-platform-multi-llm-design.md`, `multi_llm/` |
   | Promise ladder / research progression | ALREADY-DESIGNED | `edge-research-platform-promise-ladder.md`, D-25/D-26 |
   | Story ontology · 8 layers · 12 families (4 active) · ~38 states | ALREADY-BUILT | `configs/research/market_story_ontology.yaml`, `src/research/synthetic/` |
   | Claim-extraction → hypothesis registry → evidence tests | ALREADY-BUILT | `data/hypothesis_registry.jsonl`, E-001 ritual |
   | **Mathematical discovery from existing OHLCV features → predict profitable entries** | **INVESTIGATED & PARKED (narrow)** | F-019…F-035 (crypto+FX), Program 1 CLOSED, **D-16** — *anchors PROVISIONAL pending E4* |
   | Strategy factory + adaptive portfolio allocation | BUILT-BUT-ORPHANED | F-013 |
   | Proposed `research/ontology/...` repo layout | ALREADY-BUILT (would duplicate) | `src/research/` tree |
   | Externalize story geometry to `story_spec.yaml` (essay B6) | GENUINELY-NEW | D-23 (`story = CODE` today), board §B6 |
   | Per-story mathematical **trace corpus** (data capture only) | GENUINELY-NEW (measurement) | no `trace_vector` code exists |
   | `evidence_level` tags (Measured / Inferred / Speculative) | GENUINELY-NEW (light) | maps onto §6.5 Authority Ladder |
   | model×story performance leaderboard | GENUINELY-NEW (measurement) — gated by D-19 / AMB-01 | — |
   | Daily chart-snapshot research-trace ritual | GENUINELY-NEW (operational, image-based) — Level-3 narrative risk | closest is synthetic `erp_synth_4h_trace.py` |

4. **The precise guardrail** — reproduce the narrow-scope wording verbatim (above). State the
   distinction the essay blurs: *OHLCV-feature→entry sweep is parked (D-16); "mathematical
   discovery" as a category is not.* A genuinely new information domain or ontology is the
   sanctioned way to reopen — a parameter pass over the same features is "archaeology"
   (Program 1 closure). Anchor it in §6.5: **information ≠ value ≠ authority.**

5. **Frontiers correction** (small, high-value) — the companion pasted "repo-state analysis"
   recommends *building the H1/H4 resampler (Program 3)*; that is **stale / CODE_DRIFT**:
   `src/research/resample.py` + `qualify_htf.py` already exist and **F-027** already closed
   H1/H4 (0 PROMOTE). So H1/H4 is **not** a new frontier. An **Asset Class Ontology**
   (equities/futures: overnight/borrow costs, session/gap handling) *is* consistent with the
   corrected wording (new information domain, not an OHLCV re-sweep) — but **building it is a
   separate funded decision, out of scope for this read-only reconciliation.**

6. **Genuinely-new shortlist** (your five) — trace corpus · `evidence_level` tags · model×story
   leaderboard · story-geometry-to-YAML (B6) · daily chart-snapshot ritual. Each carries an
   authority note: descriptive/measurement only; none earns fusion/sizing/production weight
   without measured ΔG001.

## Files referenced (read-only, for citation accuracy)

- [`erp-decision-board-and-story-authority.md`](docs/research-readiness/erp-decision-board-and-story-authority.md) — D-01…D-27, story authority, Part D links (row to add).
- [`market_story_ontology.yaml`](configs/research/market_story_ontology.yaml) — 8 layers / 38 states / 12 families.
- [`edge-research-platform-phased-plan.md`](docs/research-readiness/edge-research-platform-phased-plan.md) + `promise-ladder` + `multi-llm-design` — confirm essay phases ≈ these.
- `CLAUDE.md` Truths Index — F-013, F-019…F-027…F-035, D-16 anchor caveat.
- [`resample.py`](src/research/resample.py) + `qualify_htf.py` — evidence H1/H4 is already built (F-027).

## Verification (read-only)

- Every table anchor resolves: each `F-0xx` exists in the CLAUDE.md Truths Index; each `D-xx`
  in the decision board; each path exists.
- The falsification row uses the **narrow** wording (OHLCV-feature→entry sweep), never "all
  math-first," and tags the anchors PROVISIONAL pending E4.
- No new `F-id`, no finding flip, no config/hash touch — reconciliation is not a conclusion, so
  it adds **no** row to `docs/current-findings.md` and triggers no rehash.
- The board's Part D gains exactly one link row; the new doc's internal links all resolve.
- Close with the §7.4 SESSION LOG block appended to `assistant_project.md`.
