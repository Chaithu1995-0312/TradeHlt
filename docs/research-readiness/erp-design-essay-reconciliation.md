# ERP Design-Essay Reconciliation — where a pasted multi-model design lands vs the repo

> **Date:** 2026-07-16 · **Program:** `EDGE_RESEARCH_PLATFORM`
> **Read first:** [`erp-decision-board-and-story-authority.md`](erp-decision-board-and-story-authority.md)
> **Authority:** reconciliation / design-explanation only — **no** production, fusion, sizing,
> or promotion authority. Grants nothing; classifies only.

A long multi-model design discussion was proposed (expectancy math → goal-driven "work
backward from capital" architecture → multi-LLM tournament → story ontology → "invert:
discover the mathematical factor that explains profitability, then label it a story" → an
11-phase autonomous research platform). This doc maps each fragment onto what the repo already
**locked / built / investigated**, so the small genuinely-new surface is visible and no locked
decision is silently re-derived.

**Anchor caveat (non-optional):** the F-019 / F-036 null anchors cited below are
`PROVISIONAL pending E4` — the null is *pending revalidation* (see D-16's note and
[`findings-revalidation-gate-e4-preregistration.md`](findings-revalidation-gate-e4-preregistration.md)),
**not** eternally settled.

---

## One-line verdict

The essay is **~85–90% a re-derivation** of the existing `EDGE_RESEARCH_PLATFORM` program
(same north star, same frozen research spine, same story ontology, same multi-LLM research
lane). The **~10–15% that is genuinely additive is all descriptive / measurement** — none of
it earns runtime authority. One fragment ("invert to math-first factor discovery") re-enters a
**narrowly-scoped** question the repo already investigated and parked; the correct wording for
that is precise (see the guardrail) and must **not** be over-generalized to "all mathematical
discovery is falsified."

---

## Reconciliation table

| Essay fragment | Verdict | Repo anchor |
|---|---|---|
| Expectancy / compounding / "positive EV, repeat, compound" | ALREADY-LOCKED | D-02, [`goal.md`](../architecture/goal.md), G001 goal layer |
| Goal-driven "work backward" arch + frozen research spine | ALREADY-LOCKED | D-09 canonical loop, [`goal.md`](../architecture/goal.md) |
| "Research / verification platform, not a finished strategy" | ALREADY-LOCKED | D-01 |
| Per-module "each answers one question" table | ALREADY-BUILT (descriptive) | [`service-boundary-map.md`](../architecture/service-boundary-map.md) |
| Multi-LLM: same package, **score not vote**, leaderboard | ALREADY-DESIGNED | D-08, D-18/D-27, [`edge-research-platform-multi-llm-design.md`](edge-research-platform-multi-llm-design.md), `multi_llm/` |
| Promise ladder / research progression | ALREADY-DESIGNED | [`edge-research-platform-promise-ladder.md`](edge-research-platform-promise-ladder.md), D-25/D-26 |
| Story ontology · 8 layers · 12 families (4 active) · ~38 states | ALREADY-BUILT | [`market_story_ontology.yaml`](../../configs/research/market_story_ontology.yaml), [`src/research/synthetic/`](../../src/research/synthetic/story_builder.py) |
| Claim-extraction → hypothesis registry → evidence tests | ALREADY-BUILT | `data/hypothesis_registry.jsonl`, E-001 pre-registration ritual |
| **Mathematical discovery from existing OHLCV features → predict profitable entries** | **INVESTIGATED & PARKED (narrow)** | F-019…F-035 (crypto+FX), Program 1 CLOSED, **D-16** — *anchors PROVISIONAL pending E4* |
| Strategy factory + adaptive portfolio allocation | BUILT-BUT-ORPHANED | F-013 (scan→allocate + PortfolioAllocator built, unwired) |
| Proposed `research/ontology/...` repo layout | ALREADY-BUILT (would duplicate) | [`src/research/`](../../src/research/__init__.py) tree |
| Externalize story geometry to `story_spec.yaml` (essay §B6) | GENUINELY-NEW | D-23 (`story = CODE` today), board §B6 |
| Per-story mathematical **trace corpus** (data capture only) | GENUINELY-NEW (measurement) | no `trace_vector` code exists |
| `evidence_level` tags (Measured / Inferred / Speculative) | GENUINELY-NEW (light) | maps onto §6.5 Authority Ladder |
| model×story performance leaderboard | GENUINELY-NEW (measurement) — gated by D-19 / AMB-01 | — |
| Daily chart-snapshot research-trace ritual | GENUINELY-NEW (operational, image-based) — Level-3 narrative risk | closest is synthetic `scripts/research/erp_synth_4h_trace.py` |

---

## The precise guardrail (do not over-generalize)

The essay's headline recommendation — *"make the mathematics the source of authority: discover
the feature-combination that precedes positive R, then label it a story"* — must be classified
with the **narrow, defensible** statement, not a blanket one:

> The specific program of searching for profitable **entry** factors by sweeping combinations
> of **OHLCV-derived** features has already been extensively investigated under the documented
> scopes and is currently parked by **D-16**. This does **not** preclude future mathematical
> research over genuinely new information domains or ontologies.

The distinction the essay blurs:

- **Parked (D-16):** the OHLCV-feature→entry sweep — "same OHLCV directional toys." Reopening it
  by a parameter pass over the same features is *archaeology* (Program 1 closure), not a thesis.
- **Not parked:** "mathematical discovery" as a *category*. The ERP's own next phase is
  **P4 — NEW INFORMATION FAMILY (OI / path / abstain)** ([`edge-research-platform-phased-plan.md`](edge-research-platform-phased-plan.md)):
  new information domains and new ontologies are the sanctioned way forward.

Two further points the essay itself gets right and the repo already holds:

- The essay's "invert to a frozen research spine" is **not new** — the ERP already froze
  `Data → Verified Features → Events → Opportunity → Engine Evidence → Honest Outcomes →
  Demote Zero-Δ → Policy` (**D-09**). The essay rephrases it.
- Authority discipline (§6.5): **information ≠ value ≠ authority.** A detectable factor is
  *information*; only demonstrated ΔG001 earns fusion / sizing / production weight.

---

## Frontiers correction (companion "repo-state analysis")

The companion pasted repo-state analysis recommends *"begin implementing the H1/H4 Timeframe
Resampler (Program 3) … build a deterministic resampler."* That recommendation is **stale /
CODE_DRIFT**:

- [`src/research/resample.py`](../../src/research/resample.py) and
  [`scripts/research/qualify_htf.py`](../../scripts/research/qualify_htf.py) **already exist**.
- **F-027** already recorded: *"coarser timeframes (H1/H4) do NOT rescue the directional edge —
  0 PROMOTE at H1/H4."*

So H1/H4 is **already built and closed** — not a new frontier; re-running it is exactly the
archaeology D-16 parks. By contrast an **Asset Class Ontology** (equities / futures: overnight
& borrow costs, funding rates, session / weekend-gap handling) *is* consistent with the
corrected wording — a genuinely new information domain, aligned with phased-plan **P4**. But
**building it is a separate funded decision, out of scope for this read-only reconciliation.**

---

## Genuinely-new shortlist (the ~10–15%)

All five are **descriptive / measurement only**; none earns fusion / sizing / production weight
without measured ΔG001 (§6.5 Authority Ladder):

1. **Per-story mathematical trace corpus** — a data-capture artifact (story → feature/engine
   vector → honest outcome). Measurement asset; its *consumer* (ranking a "profit variable")
   is the parked class unless fed a new information domain (P4).
2. **`evidence_level` tags** (Measured / Inferred / Speculative) on ontology states — light
   metadata that maps onto the Authority Ladder; keeps Level-3 narratives ("institutions sold")
   labelled as speculation, not measured fact.
3. **model×story performance leaderboard** — new measurement; gated by D-19 (measure marginal
   value; drop at zero Δ) and AMB-01.
4. **Story geometry externalized to YAML (essay §B6)** — the decision board itself flags this as
   future work (D-23: `story = CODE` today); needs one code project (parser + synthesizer).
5. **Daily chart-snapshot research ritual** — operational workflow over chart images; carries
   Level-3 narrative risk (image interpretation is harder to validate than deterministic
   features) and is not part of the OHLCV pipeline.

---

*End of reconciliation. This document classifies a design proposal against existing program
state; it changes no finding, config, or runtime truth.*
