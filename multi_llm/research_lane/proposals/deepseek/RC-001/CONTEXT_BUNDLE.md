# CONTEXT_BUNDLE

Generated: 2026-07-14T14:43:57Z

Use ONLY this bundle + PROMPT. Do not invent repo files not listed.


========================================================================
# SOURCE: docs/research-readiness/erp-decision-board-and-story-authority.md
# ROLE: decisions_and_story_authority
========================================================================

# Edge Research Platform — Decision Board + Synth Story Authority (Read This First)

> **One document for humans.** Grok’s tracked decisions + reverse-engineering of the scripted  
> 4h story: *if we change the script, do we need code changes, or only WHAT / WHO / HOW?*  
>  
> **Date:** 2026-07-14 · **Program:** `EDGE_RESEARCH_PLATFORM`  
> **Authority:** design / governance explanation only — no production authority.

---

# PART A — SHOUT-OUT: DECISIONS IN FORCE

These are **locked program decisions** unless you explicitly reverse them.

## A1. What this project is

| # | Decision | Status |
|---|---|---|
| **D-01** | Project = **research / verification platform**, not “I already have a profitable strategy.” | LOCKED |
| **D-02** | Goal = maximize P(find cost-surviving edge **or** clean null) per unit time/risk. | LOCKED |
| **D-03** | Production authority only from **surviving evidence** + gates — not model existence. | LOCKED |

## A2. Trust & evidence

| # | Decision | Status |
|---|---|---|
| **D-04** | Backtest / tool numbers start **`UNTRUSTED_RAW`** until validation flow is reviewed and matches **intended implementation**. | LOCKED |
| **D-05** | LLM chat prose = **NON_EVIDENCE**. Tool invent / misread / wrong-path = H1 / H2 / H3. | LOCKED |
| **D-06** | LLM may propose **H_tool / H_market** only; never set FLOW_MATCHES_INTENT or capital alone. | LOCKED |
| **D-07** | Only four control-plane artifact kinds: **PROPOSAL · CRITIQUE · EXECUTION_EVIDENCE · DECISION**. | LOCKED (design) |
| **D-08** | **No multi-model voting.** Agreement is not evidence. | LOCKED |

## A3. Research spine (how the system is supposed to work)

| # | Decision | Status |
|---|---|---|
| **D-09** | Canonical loop = data → features → events → opportunity → multi-engine evidence → store → honest outcomes → demote zero-Δ → policy from survivors → OOS/costs → shadow → small capital → monitor. | LOCKED (intent) |
| **D-10** | Always **name the validation lens** (CRT-only gate-OFF vs fusion gate-ON). Research default is often CRT-only (F-037). | LOCKED |
| **D-11** | RREngine in pitch = **candle polarity**, not true payoff RR (F-048 class). | LOCKED (accuracy) |
| **D-12** | BitNet / TradeNet = no authority until measured Δ (F-004 / F-005). | LOCKED |

## A4. Priority stack

| # | Decision | Status |
|---|---|---|
| **D-13** | Rank 0: **WS-TEST-HARNESS** (H1–H3 + real outlets). | LOCKED (design order) |
| **D-14** | Rank 0b: **WS-MLLM-RCP** thin protocol only (parallel, not instead of factory). | LOCKED (design order) |
| **D-15** | Rank 1: **WS-OUTCOME-FACTORY** (honest labels). | LOCKED (design order) |
| **D-16** | Do **not** fund first: CRT knob archaeology, session-as-alpha, zone knobs-as-edge, same OHLCV directional toys, carry reopen without new thesis, wire TradeNet/BitNet “because built.” | LOCKED |
| **D-17** | Unknowns workshop **PARKED** until full implementation plan. | LOCKED |

## A5. Multi-LLM (design, not role-card rewrite yet)

| # | Decision | Status |
|---|---|---|
| **D-18** | Dual-lane until AMB-01 frozen: **research lane** (architect / diversity / critic / Claude) vs **implementation lane** (`multi_llm/` as today). | RECOMMENDED DEFAULT |
| **D-19** | Measure Grok/DeepSeek marginal value over controlled cycles; drop if zero Δ. | LOCKED (principle) |
| **D-20** | You = capital + final risk authority always. | LOCKED |

## A6. Synth pack

| # | Decision | Status |
|---|---|---|
| **D-21** | Synth 4h pack is **intentional geometry**, not random; intended vs produced must match. | LOCKED |
| **D-22** | Engines on pack use **design feature contract + real engine callables** (not invented scores). | LOCKED |
| **D-23** | **Story numbers today live in CODE** (the generator script). Changing the story is **not** fully manageable by WHAT/WHO/HOW alone — see Part B. | LOCKED (finding) |
| **D-24** | Active build sequence = **phased plan P0–P7** in [`edge-research-platform-phased-plan.md`](edge-research-platform-phased-plan.md). Next grant: **P0 freeze → Implement P1**. | LOCKED (plan) |
| **D-25** | **No false wealth promise** stands; design also **moves toward earned promise** via Promise Ladder PL-0…PL-5 + Track II search pressure. See [`edge-research-platform-promise-ladder.md`](edge-research-platform-promise-ladder.md). | LOCKED (design law) |
| **D-26** | After P2 (PL-1), open P4 wealth-search within agreed window or document deferral (PR-02). Integrity-only forever is **not** success. | LOCKED (intent) |
| **D-27** | Multi-LLM **Research Lane initiated** (thin dual-lane HOW). Packages = PROPOSAL/CRITIQUE/EXECUTION_EVIDENCE/DECISION only. Implementation Lane unchanged until AMB-01 supersede. | LOCKED (initiated) |

### Owner still must choose (open)

| AMB | Topic | Options |
|---|---|---|
| AMB-01 | Role map vs `multi_llm/` | A supersede / B dual-lane / C hybrid |
| AMB-02 | Who freezes + reviews | Architect+You / +Critic |
| AMB-04 | RCP vs factory priority | C thin parallel (default) |
| AMB-10 | First 10 cycles population | 3 H_tool synth first (default) |

---

# PART B — SCRIPTED STORY (REVERSE ENGINEER)

## B1. The story you locked

```text
range
  → SWEEP low = 98.50
  → displacement up
  → expansion near 104
  → retest low = 101.40  (above SL 101)
  → LONG entry = 102.00
  → mild adverse 101.20  (not SL)
  → TP touch high ≥ 104
  → TP_HIT  R = 2.0
```

| Design level | Value |
|---|---|
| ATR | 1.0 |
| SL | 101.0 (= entry − 1×ATR) |
| TP | 104.0 (= entry + 2×ATR) |
| Entry index | **41** (= 32 warmup + 9 event-relative) |
| Instrument | SYNTHUSDT · M15 |

**Reproduce:**

```bash
PYTHONPATH=src python scripts/research/erp_synth_4h_trace.py
```

**Artifacts:** `data/synthetic/erp_4h_m15/`  
**Last critical compare:** PASS (outcome + engines match intended).

---

## B2. What each layer means in *this repo*

| Layer | Meaning (three-authority model) | Examples |
|---|---|---|
| **WHAT** | Mathematical identity — *what quantity is* | `body_ratio = body/range` (FM), `compute_scores` formulas, soft-zone formula |
| **WHO** | Contracts / topology / roles of quantities in state graphs | CRT state transitions, state contracts, “who owns which field” |
| **HOW** | Behavioral knobs when production-loaded | Weights `(0.35,0.25,0.20,0.20)`, thresholds in prod config / CRTConfig |
| **CODE** | Executable procedures, generators, wiring | `erp_synth_4h_trace.py` bar plan, `forward_walk`, `RREngine.compute` |

**Rule of thumb:**

- Change **meaning of a formula** → WHAT (+ CODE that implements it).  
- Change **thresholds / weights** on live path → HOW (config).  
- Change **legal state graph** → WHO (+ CODE seed).  
- Change **this synthetic candle movie** → today almost entirely **CODE** (and data files it writes).

---

## B3. Reverse-engineer: who owns each piece of the story?

| Story element | Current owner | Layer | Change only WHAT/WHO/HOW? |
|---|---|---|---|
| Warmup length 32, event 16 bars | Python constants | **CODE** | **No** — edit script (or future story YAML + generator) |
| Prices: 98.50, 101.40, 102, 104, … | Python constants + bar plan | **CODE** | **No** |
| Phase sequence (range→sweep→…) | Hardcoded `plan.append(...)` order | **CODE** | **No** — structure of generator |
| Entry index 41 | Derived: `WARMUP + REL_ENTRY` | **CODE** | **No** (follows constants) |
| SL/TP absolute 101 / 104 | `ENTRY ± ATR×mult` | **CODE** design + Signal fields | Mults could later be HOW; prices still from story |
| `forward_walk` exit rule (intrabar SL/TP, SL-first tie) | `src/research/measurement/forward_walk.py` | **CODE** (structural) | **No** for rule change; params only if API extended |
| CRT score formula pieces | `scoring_engine.compute_scores` | **WHAT** math in CODE | Formula identity = WHAT; weights = **HOW** |
| CRT weights 0.35/0.25/0.20/0.20 | Script constant (mirrors HOW default) | **HOW-shaped** but **copied in CODE** | Live path: HOW. Pack: edit script **or** load prod HOW |
| `body_ratio` definition | `candle_math` / FM | **WHAT** | Changing formula = WHAT+CODE; story OHLC still CODE |
| RR polarity on entry bar | `RREngine` | **WHAT** in CODE | Same |
| Soft zone score formula | `_compute_soft_zone_score` | **WHAT** in CODE | Inputs (distance/freshness) = design seeds in **CODE** today |
| Gaussian μ,σ and EMA seeds | Script design seeds | **CODE** (pack determinism) | Live gaussian μ/σ may come registry/HOW; pack is fixed CODE |
| Intended vs produced compare | Script asserts | **CODE** | Always re-run generator after story edit |
| CSV / intended_spec / produced | Generated files | **DATA** | Regenerated; do not hand-edit as truth |

### Bottom line (answer to your question)

```text
TODAY (as implemented):

  Change the scripted STORY (prices, phases, bar counts, entry index)
      → REQUIRES CODE change in scripts/research/erp_synth_4h_trace.py
         (and re-run to refresh data/synthetic/erp_4h_m15/*)

  WHAT / WHO / HOW alone CANNOT retarget this story
      because the story is not loaded from ontology, state contracts, or prod config.

  Change HOW engine weights / thresholds on the LIVE trading path
      → often config-only (HOW), no story script change.

  Change WHAT formulas (e.g. body_ratio definition)
      → ontology/registry + CODE; then re-run pack to see intended vs produced break.
```

---

## B4. What *is* manageable without touching the story generator?

| You want to change… | Via WHAT/WHO/HOW? | Notes |
|---|---|---|
| Production fusion weights, dual_engine thresholds | **HOW** (prod config + rehash if needed) | Does not rewrite synth CSV |
| CRT `score_component_weights` on live | **HOW** | Pack still uses its own tuple unless wired to config |
| Legal CRT transitions | **WHO** (+ CODE seed) | Unrelated to synth bar movie |
| Formula identity of body_ratio / disp | **WHAT** | After change, **re-run synth** to refresh intended body_ratio / CRT |
| Forward-walk cost model for real research | research config / call args | Separate from this pack’s fixed R=2 design |
| Zone hard registry zones | models + config | Pack uses **soft_designed**, not registry |

---

## B5. If you change the story — checklist

Suppose you edit: `SWEEP_LOW = 97.0`, or entry = 103, or force SL_HIT instead of TP.

| Step | Action |
|---|---|
| 1 | Edit constants / bar `plan` in **CODE** (`erp_synth_4h_trace.py`) |
| 2 | Recompute design SL/TP/entry index consistency by hand or script asserts |
| 3 | Re-run generator → new CSV + intended_spec + produced_compare |
| 4 | Expect **new** engine scores (body_ratio, RR polarity, CRT components may move) |
| 5 | **No** prod config rehash required (pack is offline research fixture) |
| 6 | **No** WHO state-graph edit required for price-only changes |
| 7 | If you only change numbers but keep TP_HIT design, keep path constraints: adverse low **> SL**, some high **≥ TP** after entry |

**Code change required?**  
- **Yes, today** — the generator script (or a new story file if you later externalize it).  
- **Not** required: CRT ontology, production JSON, WHO contracts — for pure story retargeting.

---

## B6. Path to “story managed like HOW” (optional future — not done)

To make story **data-driven** (closer to config-first):

```text
story_spec.yaml          ← research HOW-like (geometry only)
        ↓
generic bar synthesizer  ← CODE once (structure)
        ↓
CSV + intended_spec
        ↓
same engine callables    ← WHAT formulas unchanged
```

That still needs **one** CODE project (parser + synthesizer). After that, most story edits = edit YAML only (not WHAT/WHO, and not prod HOW).

Until then: **story = CODE**.

---

## B7. Trace of current story through layers (intended)

```text
CODE story constants
    → CODE builds OHLCV bars
    → DATA: SYNTH_4H_M15.csv
    → WHAT: body_ratio, CRT score math, RR polarity, soft zone, gaussian kernel
    → HOW-shaped seeds: weights (0.35…), gauss μ/σ (pack-fixed in CODE)
    → CODE: forward_walk → TP_HIT R=2
    → DATA: intended_spec.json vs produced_compare.json
    → WHO: not used for this pack (no CRT state-machine detect claimed)
```

---

# PART C — ONE-PAGE SUMMARY

| Question | Answer |
|---|---|
| Can I retarget the scripted story only via WHAT/WHO/HOW? | **No — not today.** Story is **CODE** in `erp_synth_4h_trace.py`. |
| Do I need engine formula changes to change 98.50 → 97.00? | **No.** Edit story constants + re-run. |
| Do I need production config changes to retarget the story? | **No.** |
| Will engine scores stay 0.8227 / 0.9432 / … if story prices change? | **Usually no** — re-compute intended vs produced. |
| What stays stable if only prices change? | WHAT definitions; WHO topology; live HOW config; compare *framework*. |
| What is the shout-out decision on authority? | **D-23:** story geometry is CODE-owned until externalized. |

---

# PART D — WHERE EVERYTHING LIVES

| Doc / path | Role |
|---|---|
| **This file** | Decision board + story authority (read first) |
| `edge-research-platform-program.md` | Full program tracker |
| `edge-research-platform-multi-llm-design.md` | Multi-LLM + research loop + AMB-* |
| `edge-research-platform-io-map.md` | Topic inputs/outputs |
| `edge-research-platform-testing-plan.md` | H1–H3 test pyramid |
| `erp-synthetic-4h-trace.md` | Auto narrative of last run |
| `scripts/research/erp_synth_4h_trace.py` | **Story CODE** |
| `data/synthetic/erp_4h_m15/*` | Generated fixtures |

---

*End of document. Decisions above are the tracked shout-out list; reverse-engineering answer is Part B.*


========================================================================
# SOURCE: docs/research-readiness/edge-research-platform-phased-plan.md
# ROLE: phased_plan_p0_p7
========================================================================

# Edge Research Platform — Phased Design Plan

> **Status:** DESIGN PLAN (ready for owner freeze → implement grants per phase)  
> **Date:** 2026-07-14 · **Program:** `EDGE_RESEARCH_PLATFORM`  
> **Read first:** [`erp-decision-board-and-story-authority.md`](erp-decision-board-and-story-authority.md)  
> **Authority:** none until you grant each phase; no capital / promotion by default.

This plan is built from **what we already have** (decisions, I/O map, testing design, multi-LLM design, synth 4h pack) and sequences **what to build next** without LLM theater or production overclaim.

---

## 0. North star (two clauses — both required)

```text
(1) Maximize P(find cost-surviving deployable edges that can support
    a *conditional* wealth promise)
        OR cleanly prove the information set cannot — then stop or expand data.

(2) Never issue a wealth promise without the Promise Ladder rung earned
    (see edge-research-platform-promise-ladder.md).
```

| Forbidden | Required |
|---|---|
| False promise (“will make money” with no PL-3+) | Path **toward** promise (Track II search + PL ladder) |
| Integrity-only forever with no search pressure | Integrity **first**, then forced new-info / demotion / shadow / micro capital |

**Not:** maximize models, governance pages, or multi-LLM tokens.  
**Yes:** raise **P(durable wealth)** via earned rungs PL-0→PL-5.

**Parallel design:** [Promise Ladder + Track I ∥ Track II](edge-research-platform-promise-ladder.md).

---

## 1. What already exists (do not rebuild)

| Asset | Path / note | Phase use |
|---|---|---|
| Decision board D-01…D-23 | `erp-decision-board-and-story-authority.md` | All phases |
| Program tracker | `edge-research-platform-program.md` + `.json` | All phases |
| I/O map | `edge-research-platform-io-map.md` | Contracts |
| Testing design L0–L8 | `edge-research-platform-testing-plan.md` | P1 |
| Multi-LLM design + AMB-* | `edge-research-platform-multi-llm-design.md` | P0 / P2 |
| Synth 4h story + engines + compare | `scripts/research/erp_synth_4h_trace.py`, `data/synthetic/erp_4h_m15/` | P1 golden |
| Outcome measurement | `src/research/measurement/forward_walk.py`, `qualification.py` | P2 |
| Engines | `engines/*`, `engine_runner.py` | P3 |
| Live/MT5 dry-run surfaces | `live/mt5_bridge.py`, `tests/mt5_analytics`, `live_smoke` | P5 |
| Multi-LLM protocol (impl lane) | `multi_llm/` | Dual-lane with research RCP |
| Findings / registries | `docs/current-findings.md`, hypothesis registry seed | Truth |

---

## 2. Phase map (overview)

```text
P0  FREEZE & PROTOCOL          (docs / decisions only)
P1  TEST HARNESS + SYNTH GOLDEN (H1–H3 floors)
P2  OUTCOME FACTORY             (honest labels + population)
P3  ENGINE EVIDENCE + DEMOTION  (incremental value)
P4  NEW INFORMATION FAMILY      (OI / path / abstain)
P5  SHADOW / EXEC REALISM       (no capital by default)
P6  MULTI-LLM RCP CYCLES        (measure model Δ; thin→measured)
P7  CAPITAL MICRO               (owner dual-ack only)
```

| Phase | Name | Depends on | Default grant |
|---|---|---|---|
| **P0** | Freeze protocol | — | Owner stamp |
| **P1** | Harness + synth golden | P0 | Implement |
| **P2** | Outcome factory | P1 | Implement after design freeze |
| **P3** | Engine demotion | P2 | Implement |
| **P4** | New info (OI/path) | P2 | Design → data → implement |
| **P5** | Shadow realism | P2 + survivor or dry path | Owner |
| **P6** | MLLM 10 cycles | P0 + P1 (H_tool); P2 for H_market | Parallel thin from P0 |
| **P7** | Capital micro | P5 + Stage-3 survivor | Explicit only |

**Parallel allowed:**

- P6 thin protocol docs/JSONL from day one **with** P1–P2 (D-14 / AMB-04).  
- **Track I ∥ Track II** after P2: P3 demotion **and** P4 new-info design/data spike.  
- P5 dry-path build while hunting PL-3 candidates.

**Forbidden parallel:**

- P7 with anything without **PL-4** (shadow promise).  
- P4 heavy automation before P2.  
- Wealth language at PL-0/1.

**Promise rungs (earn, don’t assume):**

| After phase exit | Max rung available |
|---|---|
| P1 | PL-0 (instrument parts) |
| P2 | **PL-1** measurement promise |
| P3 Stage-1 info | **PL-2** |
| P3/P4 economic candidate | **PL-3** |
| P5 shadow match | **PL-4** |
| P7 dual-ack | **PL-5** micro capital promise |

---

## 3. Phase detail

### P0 — Freeze & protocol (docs only)

**Goal:** Lock defaults so implementers do not thrash.

| Deliverable | Done when |
|---|---|
| Owner accepts decision board D-01…D-23 | Written DECISION in program log |
| AMB-01 default = dual-lane (or explicit other) | Checklist filled in multi-llm design §7 |
| AMB-04 = thin RCP parallel factory | Same |
| AMB-10 = first 3 cycles H_tool on synth | Same |
| This phased plan referenced as active plan | Program pointer updated |

**In:** decision board, multi-llm design, this plan.  
**Out:** frozen AMB choices; **no code required**.  
**Exit:** Owner says “P0 frozen” → grant P1 (and optional P6 thin).

---

### P1 — Test harness + synth golden (WS-TEST-HARNESS)

**Goal:** Make H1/H2/H3 *mechanically hard*; keep synth story as golden intended-vs-produced.

#### P1.0 Already done (baseline)

- Synth generator + TP_HIT R=2 path  
- Engine feature contract + CRT/Gaussian/Zone-soft/RR match  
- Narrative + intended_spec / produced_compare  

#### P1.1 Implement (T0 from testing plan)

| Work item | Output |
|---|---|
| pytest markers in `pyproject.toml` | unit / contract / research_integrity / market_network / … |
| `tests/support/run_manifest.py` | write/read/hash manifest |
| `assert_summary_matches_manifest` | H2 guard |
| AH-01…AH-05 fixture tests | invent/misread/missing manifest fail |
| VP-01…VP-04 intent-contract fixtures | wrong lens/labels fail |
| Wire synth pack as **golden test** | `pytest` runs compare CRITICAL_PASS |
| Default CI excludes network/broker/ui | documented command |

#### P1.2 Optional same phase (if time)

| Work item | Output |
|---|---|
| Story externalization design only | `story_spec` schema sketch (D-23 follow-on) — **no must-ship** |
| Binance public L3 (T1) | BN-SCHEMA/PIT/FAIL — nightly/manual |

**In:** synth pack, testing plan T0–T1.  
**Out:** CI-green AH/VP + synth golden; manifests under `results/test_runs/` for new runs.  
**Exit:** `pytest` selected markers green; synth CRITICAL_PASS in CI.  
**Trust:** still no market edge claim.

---

### P2 — Outcome factory (WS-OUTCOME-FACTORY)

**Goal:** Neutral opportunity population + honest outcomes (anti F-022).

| Work item | Output |
|---|---|
| DESIGN freeze: seed definition, join keys, exit_model, cost bps, horizon | Intent contract YAML/JSON |
| Re-derive path using `forward_walk(intrabar_fixed)` | Population table / JSONL |
| Audit sample: opportunity-stream labels vs re-derive | Contamination report |
| Factory CLI thin wrapper under `scripts/research/` | Reproducible run + run_manifest |
| Floor tests: schema + determinism of factory on synth + 1 real instrument slice | pytest |
| Document validation lens per run | D-10 |

**In:** `forward_walk`, qualification patterns, synth as unit fixture, real `data/*_M15.csv` for scale later.  
**Out:** versioned opportunity+outcome artifact; `label_source=forward_walk` default for research.  
**Exit:** DESIGN frozen + one full re-derive run with manifest + floor tests green.  
**Blocker for:** P3 economic demotion, P4 market H, P6 H_market cycles.

---

### P3 — Engine evidence + demotion (WS-ENGINE-DEMOTION)

**Goal:** Measure incremental value; demote zero-Δ engines (Authority Ladder).

| Work item | Output |
|---|---|
| Extend synth pattern to factory population | Per-opportunity engine score table |
| Ablations: alone / leave-one-out / combinations | Δ table under fixed costs |
| Dual-lens policy: gate-OFF vs gate-ON declared | Explicit columns, not mixed |
| Demotion ledger (describe vs decide) | JSONL or findings draft |
| No auto re-enable of rr_fusion / BitNet / TradeNet | Config stays disabled unless ΔG001 |

**In:** P2 population; engines; synth engine contract as template.  
**Out:** keep/demote recommendations (research authority only).  
**Exit:** At least one instrument (or synth-scaled multi-opp if real N insufficient) with documented Δ; engines without Δ marked describe-only.

---

### P4 — New information family (WS-OI-PATH-ABSTAIN) — **primary wealth-search phase**

**Goal:** Expand search space off exhausted OHLCV-direction toys (D-16).  
**Promise-track:** This is where **P(wealth)** is supposed to move after integrity — not more CRT knobs.

| Work item | Output |
|---|---|
| Data spike: OI / positioning / liq feasibility | Acquisition report or BLOCKED |
| If unblocked: PIT join to opportunity seeds | Joined feature table |
| Targets: path quality / abstain / P(hit TP before SL) — not only up/down | Prereg H_market |
| Incremental vs OHLCV-only baseline | Stage-1/2 gates |
| STOP if Stage-1 fails | No model zoo |

**In:** P2 factory; `data/perp/*` funding/basis already exist (carry nulls scoped).  
**Out:** PROMOTE/REJECT/INSUFFICIENT under frozen gate.  
**Exit:** One prereg closed; data corpus retained even if null.

---

### P5 — Shadow / execution realism (WS-SHADOW-LIVE)

**Goal:** Close F-010-class gap without capital.

| Work item | Output |
|---|---|
| Dry-run path: decision → planner → MT5 dry_run | Structured log + manifest |
| Optional: Playwright control-plane job truth (L6) | UI-H2 |
| MT5 RO pre-release smoke (existing live_smoke) | L4 collectable or documented SKIP |
| Structural review notes for F-048 decision path | Doc only unless grant |

**In:** live_engine_hook, mt5_bridge dry_run, tests.  
**Out:** shadow bundle UNTRUSTED_RAW until flow review.  
**Exit:** Dry path runs end-to-end on one instrument; no real orders.

---

### P6 — Multi-LLM Research Control Plane (WS-MLLM-RCP)

**Goal:** Anti echo-chamber; measure model value (D-07, D-18, D-19).

#### P6.A Thin (can start after P0, parallel P1)

| Work item | Output |
|---|---|
| Package schema for 4 kinds | JSON schema |
| `research_cycle_ledger.jsonl` (append-only) | Path under `multi_llm/` or `docs/governance/` |
| Cycle scorecard template | Metrics table (diversity, defects, cost, survivors) |
| 3 H_tool cycles on **synth pack** | PROPOSAL→CRITIQUE→EXECUTION_EVIDENCE→DECISION |

#### P6.B Measured (after P2)

| Work item | Output |
|---|---|
| 7 more cycles (H_tool and/or H_market on factory) | Ledger rows |
| Marginal contribution of Grok / DeepSeek | Keep or drop roles |
| Dual-lane handoff pack (research vs `multi_llm/` impl) | One-page operator guide |

**Exit P6.A:** 3 completed H_tool cycles with artifacts.  
**Exit P6.B:** 10 cycles + keep/drop decision for extra models.

---

### P7 — Capital micro = **first wealth promise (PL-5)** (only if survivor)

**Goal:** Tiny real risk only after Stage-3 economic survivor + flow match + You dual-ack.  
**Language:** Only here may you say a **conditional micro capital promise** — still not “scaled wealth.”

| Work item | Output |
|---|---|
| Checklist + env gates (`RUN_CAPITAL_MICRO`, `OWNER_CAPITAL_ACK`) | Never CI |
| Kill switch armed; max notional / trade count | Config HOW |
| Live monitor vs research edge decay | Alerts |

**Exit:** Explicit owner run log; or phase remains **NOT STARTED**.

---

## 4. Cross-phase rules (always on)

1. **D-04:** every economic number = UNTRUSTED_RAW until validation-flow review.  
2. **D-10:** name lens on every research claim.  
3. **D-23:** story geometry changes = edit generator CODE + re-run (until externalized).  
4. **No** multi-model vote (D-08).  
5. **No** findings Validated flip without DECISION package (AMB-12 default).  
6. Construction protocol for governed code changes.  
7. SESSION LOG on every implementing turn.

---

## 5. Suggested calendar (indicative, not commitment)

| Phase | Effort band | Notes |
|---|---|---|
| P0 | 0.5 day | Owner decisions |
| P1 | 2–5 days | T0 harness + golden; T1 optional |
| P2 | 1–2 weeks | Design freeze is the hard part |
| P3 | 1 week | After P2 |
| P4 | 1–3 weeks | Data-blocked risk |
| P5 | 3–7 days | Dry only |
| P6.A | 2–4 days | Parallel early |
| P6.B | ongoing | With research cycles |
| P7 | TBD | Only if survivor |

---

## 6. Success metrics per phase

| Phase | Success = |
|---|---|
| P0 | AMB checklist filled; plan active |
| P1 | AH/VP + synth golden green in CI |
| P2 | Factory artifact + floors; contamination report |
| P3 | Demotion ledger with measured Δ (or power-aware INSUFFICIENT) |
| P4 | Closed prereg (null OK if honest) |
| P5 | Dry shadow path + manifest |
| P6 | 10 cycles; model keep/drop data |
| P7 | Dual-ack live micro with kill switch |

**Program-level success (6–12 months):** either Stage-3 survivor under costs **or** multi-axis clean null with redirected effort — not “more architecture.”

---

## 7. Grant sequence (how to start work)

```text
You: "P0 frozen" + optional AMB choices
You: "Implement P1"
     → harness + golden
You: "Design freeze P2" then "Implement P2"
     → factory
You: "Implement P3" / "Design P4" / "Implement P6.A" as needed
You: never "Implement P7" without survivor evidence package
```

---

## 8. Document map

| Doc | Role |
|---|---|
| **This plan** | Phased design → implement sequence |
| Decision board | Locked D-* and story authority |
| Program md/json | Living status / conversation log |
| Testing plan | L0–L8 detail for P1/P5 |
| Multi-LLM design | RCP + AMB detail for P6 |
| I/O map | Per-topic contracts |
| Synth trace | Golden narrative |

---

## 9. Immediate next step (default)

1. **You freeze P0** (or say “accept all recommended AMB defaults”).  
2. **Grant Implement P1** (pytest markers + run_manifest + synth golden in CI).  
3. Keep **P6.A** as optional parallel docs-only until you want ledger code.

---

*End of phased plan. No phase implies edge existence. Null results are success when honest.*


========================================================================
# SOURCE: docs/research-readiness/edge-research-platform-promise-ladder.md
# ROLE: promise_ladder
========================================================================

# Parallel Design: Move *Toward* a Promise of Wealth (Without Lying)

> **Status:** DESIGN · 2026-07-14 · Program `EDGE_RESEARCH_PLATFORM`  
> **Companion plans:** [phased plan P0–P7](edge-research-platform-phased-plan.md) · [before/after](edge-research-platform-before-after.md) · [decision board](erp-decision-board-and-story-authority.md)

---

## 0. The tension (resolved)

| Stance | Meaning |
|---|---|
| **No false promise** | We never say “this will make money” without staged evidence. That stays permanent. |
| **Design moves toward promise** | The system is **not** optimized for eternal null reports. It is optimized to **raise P(durable wealth)** by finding, proving, and scaling real edge — or stopping when the information set cannot. |

```text
FALSE PROMISE (forbidden)
  "Sophisticated system" → assume profit → capital

PATH TO PROMISE (this design)
  integrity → honest search → survivor → shadow → micro capital
  → only then language upgrades: "we have a conditional promise"
```

**Promise** here means: *a time-bound, evidence-scoped economic commitment you may act on* — not marketing, not LLM consensus.

---

## 1. Two parallel tracks (run together)

```text
TRACK I — INTEGRITY & ORGANIZATION (P0–P2, P6 thin)
  "Don't lie to yourself"
  Harness · factory · manifests · multi-LLM non-echo

TRACK II — PATH TO PROMISE (P3–P5, P4 search, P6 H_market, P7)
  "Earn the right to claim and risk capital"
  Demotion · new info · survivors · shadow · micro capital · scale gate
```

| | Track I | Track II |
|---|---|---|
| **Primary output** | Trustworthy measurement | Economic survivors |
| **Success if null** | Still success (clamps work) | Success only if *search was real* and null is decisive |
| **Wealth language** | Forbidden | Allowed **only** after PL-3+ (see ladder) |
| **Blocks Track II if missing** | Yes — dirty labels / H1 theater kill promise | — |

**Rule:** Track II never outruns Track I.  
**Rule:** Track I alone is not the goal — **P(wealth)** must keep rising via Track II search quality.

---

## 2. Promise Ladder (PL-0 → PL-5)

Language and capital rights **upgrade only** when the rung is earned.

| Rung | Name | What you may say | Capital | Maps to phases |
|---|---|---|---|---|
| **PL-0** | **No promise** | “We are building a research platform.” | None | Now / P0–P1 |
| **PL-1** | **Measurement promise** | “Our numbers mean what we claim (path + labels).” | None | P1–P2 exit |
| **PL-2** | **Information promise** | “This channel has incremental predictive content (L1/L2).” | None | P3 / early P4 Stage-1 |
| **PL-3** | **Economic candidate** | “After costs + OOS + controls, E>0 candidate (research).” | None / paper only | P3–P4 Stage-2–3, P5 design |
| **PL-4** | **Shadow promise** | “Live-equivalent path reproduces research edge in shadow.” | Paper / dry | P5 complete |
| **PL-5** | **Capital promise (micro)** | “We risk tiny capital under kill-switch; edge held in sample.” | Micro only | P7 |
| **PL-5+** | **Scale promise** | “Increase size only while live edge and risk gates hold.” | Scaled | Beyond P7; new plan |

### Mandatory phrase by rung

| Rung | Allowed one-liner |
|---|---|
| PL-0 | “No edge claimed.” |
| PL-1 | “Instrument is honest; edge still unproven.” |
| PL-2 | “Information exists; money not yet.” |
| PL-3 | “Candidate economic edge under frozen gate — not live.” |
| PL-4 | “Shadow-consistent candidate — capital not yet.” |
| PL-5 | “Micro capital authorized under checklist — not scaled.” |
| PL-5+ | “Scale only while live metrics hold.” |

**Demotion:** Any rung can fall to lower PL if replication fails, live decay, or contamination found. Promise is **revocable**.

---

## 3. How Track II *moves toward* wealth (design intent)

Integrity is necessary but not sufficient. Track II forces **search pressure**:

| Pressure | Design rule |
|---|---|
| **Kill dead alpha sources** | P3 demotion freezes budget on CRT-as-alpha, zone knobs, etc. (D-16) |
| **Expand information set** | P4 is not optional forever — after factory, **must** open new families (OI/path/flow) or declare information-set exhaustion |
| **Time-box nulls** | Each H_market prereg has **stop date / max cycles**; no infinite parameter archaeology |
| **Throughput metric** | Scorecard: falsifications/month + survivors/quarter — not docs/month |
| **Capital as teacher** | P7 micro capital is not “victory lap”; it is **live falsifier** (F-010 close) |
| **Promise clock** | Owner reviews every N cycles: stay PL-k or **exit thesis** (change markets / stop program) |

### Promise-oriented KPI (parallel to integrity KPI)

| KPI | Track | Target direction |
|---|---|---|
| Manifest coverage of research runs | I | → 100% |
| Factory label contamination rate | I | → 0 material |
| Distinct info families tested / year | II | ↑ |
| Hypotheses killed pre-capital | II | ↑ (good) |
| PL-3 candidates produced / year | II | ↑ (quality-gated) |
| Time PL-3 → PL-4 | II | ↓ if candidates exist |
| Live micro expectancy (if PL-5) | II | ≥ research bound − slippage budget |
| Docs without DECISION package | I | → 0 |

---

## 4. Parallel schedule (integrity ∥ promise)

```text
TIME →

P0 ████
P1 ████████
P2     ████████████
P3           ████████
P4           ░░░░████████████   (starts after P2; may overlap P3)
P5                 ████████     (dry always; PL-4 only if PL-3)
P6 thin ████████████████████    (∥ always)
P6 H_mkt       ████████████     (after P2)
P7                       ██     (only PL-3+PL-4)

Promise ladder:
PL-0 ████
PL-1       ████ (at P2 exit)
PL-2             ████ (P3/P4 stage1)
PL-3                   ████ (economic candidate)
PL-4                         ████ (shadow)
PL-5                               ██ (micro)
```

**Parallel rules (updated):**

| Allowed in parallel | Forbidden |
|---|---|
| P1 ∥ P6 thin | P7 ∥ anything without PL-4 |
| P3 ∥ P4 design/data spike | P4 “sweep knobs” without factory |
| P5 dry path build ∥ P3 | Calling PL-3 without OOS+costs |
| Multiple H_market preregs after P2 | Multi-LLM vote as promise |

---

## 5. Gate from “no wealth language” → “conditional promise”

```text
PL-0/1  integrity only
    │
    ▼
PL-2  Stage-1 information (beats nulls; may still E≤0)
    │
    ▼
PL-3  Stage-2/3 economic candidate
      • frozen prereg
      • costs + OOS + controls
      • FLOW_MATCHES_INTENT
      • replication plan named
    │
    ▼
PL-4  Shadow: same lens, live-equivalent path, slippage model
    │
    ▼
PL-5  You dual-ack micro capital + kill switch
    │
    ▼
PL-5+ Scale only if live metrics hold (separate plan)
```

**ChatGPT / Grok / Claude may never announce PL-3+ alone.**  
**DECISION package + You** required for PL-5.

---

## 6. What “design moves toward promise” changes in the phased plan

| Phase | Integrity goal (old emphasis) | **Promise-track emphasis (new)** |
|---|---|---|
| P0 | Freeze AMB | Freeze also: **promise KPI review cadence** (e.g. every 30 days) |
| P1 | Don’t lie | Unblocks *trust* required for any later promise |
| P2 | Honest labels | Unblocks *economic truth* — without this, no PL-2+ |
| P3 | Demote engines | **Free capacity** toward channels that can become PL-3 |
| P4 | New info | **Primary wealth search** after integrity |
| P5 | Dry realism | **Bridge to capital promise** (PL-4) |
| P6 | Anti echo | Cycles biased to **H_market after P2**, not only H_tool |
| P7 | Optional | **First real wealth promise** (micro, revocable) |

---

## 7. Before / after *promise language*

| | **Before** | **After integrity-only** | **After path-to-promise (PL-3+)** |
|---|---|---|---|
| Pitch | “System will make money” (false) | “Research platform; no edge claimed” (true, incomplete goal) | “We hold a **conditional** edge under X gate; capital only at PL-5” |
| Risk | Overpromise | Under-aiming (lab forever) | Balanced: claim only what is earned |
| Capital | Ambiguous | Blocked | Micro then scale rules |

---

## 8. Failure modes on the promise track

| Failure | Symptom | Response |
|---|---|---|
| **Integrity theater** | P1–P2 perfect, no P4 search | Force P4 time-box after P2 |
| **Search theater** | Many H_market, dirty factory | Block PL-2+ |
| **Promise inflation** | PL-3 language without OOS | Auto demote to PL-1 |
| **Null addiction** | Celebrate only kills | Require ≥1 new family test per review window |
| **Capital leap** | Skip shadow | Deny P7 |

---

## 9. Owner decisions to freeze (promise track)

| ID | Decision | Default recommendation |
|---|---|---|
| **PR-01** | Promise ladder PL-0…PL-5 is the only wealth-language scale | Accept |
| **PR-02** | After P2 exit, open P4 within 30 days or document deferral | Accept |
| **PR-03** | Promise KPI review every 30 days | Accept |
| **PR-04** | PL-5 requires You + kill switch + max notional | Accept |
| **PR-05** | Multi-LLM never raises PL alone | Accept |

---

## 10. One-sentence design law

> **Never promise wealth without evidence; never design so that wealth cannot be promised even when evidence arrives.**

Integrity clamps stop lies.  
The Promise Ladder + Track II search make **earned promise** the destination.

---

*Parallel to P0–P7. Does not grant capital. Upgrades speech and risk rights only at earned rungs.*


========================================================================
# SOURCE: docs/research-readiness/edge-research-platform-mllm-how.md
# ROLE: mllm_how
========================================================================

# Multi-LLM Architecture — HOW Layer Design + Initiation

> **Status:** HOW design **initiated** (thin dual-lane) · 2026-07-14  
> **Program:** `EDGE_RESEARCH_PLATFORM` · Phase **P0/P6.A**  
> **Authority:** orchestration only — grants **no** production, promotion, or capital authority  
> **Runtime lane:** file packages under [`multi_llm/research_lane/`](../../multi_llm/research_lane/README.md)

---

## 1. Is multi-LLM architecture required?

| Question | Answer |
|---|---|
| Required for P1 harness code? | **No** — Claude + You can implement P1 |
| Required for anti-echo + promise-track research? | **Yes (thin)** — asymmetric roles + 4 artifact kinds |
| Full auto multi-agent mesh? | **No** — premature (D-bridge: You still bridge) |
| Rewrite existing `multi_llm/` impl pipeline? | **No** — **dual-lane** (AMB-01 default B) |

**Decision (HOW):** **Initiate Research Lane now** (packages + ledger + roles).  
Keep **Implementation Lane** (`MULTI_LLM_PROTOCOL.md` as today) unchanged until AMB-01 supersede.

---

## 2. HOW vs WHAT vs WHO vs CODE (this architecture)

| Layer | Owns |
|---|---|
| **WHAT** | Market math / features / outcomes (unchanged by multi-LLM) |
| **WHO** | CRT topology / contracts (unchanged) |
| **HOW** | *This doc + research_lane configs*: roles, cycle steps, package schema, stop rules, promise rung speech, scorecard knobs |
| **CODE** | Claude-only execution; optional later ledger validators |

Changing who reviews whom or package fields = **HOW** (edit protocol/schema).  
Changing CRT score formula = **WHAT**.  
Changing bar story synth = **CODE** (D-23).

---

## 3. Dual-lane HOW map

```text
                    YOU (HOW: capital + grants + bridge)
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
   LANE R — RESEARCH                    LANE I — IMPLEMENT
   multi_llm/research_lane/             multi_llm/ (existing)
   ERP P0–P7 · Promise Ladder           code epics · build_queue
              │                               │
   PROPOSAL → CRITIQUE → freeze               DeepSeek plan → …
   → Claude EXECUTION_EVIDENCE                → Claude EXECUTOR
   → DECISION (PL rung / next phase)          → tests + SESSION LOG
              │                               │
              └─────────── REPO TRUTH ─────────┘
                 findings · manifests · code
```

| Knob (HOW) | Default |
|---|---|
| `lane_default` | Dual-lane |
| `research_artifact_kinds` | PROPOSAL, CRITIQUE, EXECUTION_EVIDENCE, DECISION |
| `impl_handoff_block` | Existing §3 block in MULTI_LLM_PROTOCOL |
| `no_voting` | true |
| `claude_only_code` | true |
| `promise_rung_current` | PL-0 |
| `pl_upgrade_requires` | DECISION + You for PL-5; evidence for PL-3/4 |

---

## 4. Research-lane roles (HOW assignment)

| Role | Default model | Never does |
|---|---|---|
| **Principal** | You | Let LLM set capital |
| **Architect** | ChatGPT (or You) | Execute code; sole-sign PL-5 |
| **Hypothesis diversity** | Grok | Approve own ideas; write prod code |
| **Technical critic** | DeepSeek | Execute unfrozen experiments |
| **Executor** | Claude | Raise PL alone; skip factory for H_market |
| **Impl navigator** (Lane I only) | Gemini | Own research DECISION |

Gemini stays **Lane I** unless a research cycle explicitly invites quant critique as CRITIQUE.

---

## 5. Cycle HOW (8 steps — operational)

| Step | Actor | Writes kind | HOW stop |
|---|---|---|---|
| 1 | Architect | PROPOSAL | Unbound H rejected |
| 2 | Diversity (opt) | PROPOSAL counters | — |
| 3 | Critic | CRITIQUE | Blocking defects → no freeze |
| 4 | Architect + You | DECISION freeze | No RUN without freeze |
| 5 | Claude | EXECUTION_EVIDENCE | Must include run_manifest path when tools ran |
| 6 | Critic or Architect ≠ executor | CRITIQUE/DECISION review | H2 quote-check |
| 7 | Architect | DECISION branch | RETIRE/REPAIR/REPLICATE/EXPAND/PL |
| 8 | You | DECISION grant | P1…P7 / capital |

---

## 6. Package schema (HOW contract)

Machine schema: [`multi_llm/research_lane/package_schema.json`](../../multi_llm/research_lane/package_schema.json)

Minimum fields every package:

```text
package_id, kind, cycle_id, created_at, author_role, author_model,
claim_type (H_tool|H_market|process),
summary,
binds (entrypoint, lens, ACTIVE_VERSION, instruments) when applicable,
falsifier,
promise_rung_max_claim (≤ current unless DECISION upgrades),
artifact_paths[],
status (PROPOSED|ACCEPTED|REJECTED|SUPERSEDED)
```

Ledger: append-only [`research_cycle_ledger.jsonl`](../../multi_llm/research_lane/research_cycle_ledger.jsonl)

---

## 7. Initiation status (done this turn)

| Item | Status |
|---|---|
| HOW design doc (this file) | **INITIATED** |
| `multi_llm/research_lane/` tree | **INITIATED** |
| package_schema.json | **INITIATED** |
| research_cycle_ledger.jsonl seed (cycle RC-000) | **INITIATED** |
| Operator README + templates | **INITIATED** |
| Scorecard template | **INITIATED** |
| Lane I protocol rewrite | **NOT** done (by design) |
| Auto agent orchestration | **NOT** done |
| P1 harness code | **NOT** done (needs Implement P1 grant) |

---

## 8. How to run one research cycle (operator HOW)

### 8.1 Initiate plan command (model-separated)

```bash
PYTHONPATH=src python scripts/multi_llm/initiate_plan.py --model grok --cycle RC-001 --focus "..."
PYTHONPATH=src python scripts/multi_llm/initiate_plan.py --model deepseek --cycle RC-001
# shortcuts: scripts/multi_llm/{grok,deepseek,gemini,claude,chatgpt}.ps1
# control plane: research.initiate_plan
```

Writes under `proposals/<model>/<cycle>/`:

| File | Purpose |
|---|---|
| `CONTEXT_BUNDLE.md` | Curated ERP docs only (`context_manifest.json`) |
| `PROMPT_FOR_<MODEL>.md` | Plan design prompt for that model |
| `PROPOSAL.md` | **Model-separated** proposal stub → paste model reply here |

**No full-repo scan. No LLM API.** You paste PROMPT+BUNDLE into the model.

### 8.2 After models return plans

```text
1. Overwrite each model's PROPOSAL.md with filled content
2. Optional DeepSeek CRITIQUE (template or critic initiate)
3. You: freeze DECISION
4. Claude: execute only if granted → EXECUTION_EVIDENCE
5. Ledger append (initiate_plan already logs INIT PROPOSED)
```

First cycle **RC-000** is process-only (architecture initiation). **RC-001** smoke packages may exist from initiate_plan.

---

## 9. Relation to Promise Ladder

| Package claim | Max PL speech without DECISION upgrade |
|---|---|
| H_tool integrity | PL-0 … PL-1 |
| H_market Stage-1 | PL-2 |
| Economic candidate | PL-3 only after DECISION |
| Capital | PL-5 only You |

---

## 10. Next HOW knobs (not initiated)

- Validator script `scripts/context/validate_research_ledger.py`  
- Nightly scorecard rollup  
- AMB-01 role-card merge into `roles/ROLE_*.md`  
- Wire packages to `docs/current-findings.md` gate  

---

*HOW owns the multi-LLM process. Reality owns truth. You own capital.*


========================================================================
# SOURCE: docs/research-readiness/edge-research-platform-before-after.md
# ROLE: before_after
========================================================================

# Edge Research Platform — Before vs After Full Design Implementation

> **Purpose:** One clear picture of **what changes** when the entire phased plan (P0–P7) is done.  
> **Baseline (“Before”):** repository + program state as of design freeze 2026-07-14.  
> **After:** intended end-state if P0–P7 complete successfully — **not a claim that edge exists**.  
> **Plan:** [`edge-research-platform-phased-plan.md`](edge-research-platform-phased-plan.md)

---

## One-sentence contrast

| | |
|---|---|
| **Before** | A rich trading **codebase** with engines, governance, and many null research results — but weak guarantees that numbers are trustworthy, opportunities are honest, multi-LLM work is non-echoing, or capital is gated by survivors. Easy to **falsely** promise wealth; hard to **earn** one. |
| **After** | A **closed-loop research organization** that both (1) refuses false promises and (2) **moves toward an earned wealth promise**: integrity → search new info → PL-3 candidates → shadow (PL-4) → micro capital (PL-5) → scale only if live holds. Null is allowed; **lab-forever without search pressure is not the goal**. |

---

## 1. What the project *is*

| Dimension | **Before** | **After (full design implemented)** |
|---|---|---|
| Identity | “Sophisticated multi-engine trading system” (easy to oversell) | Research platform **aiming to earn** a conditional wealth promise (D-01 + Promise Ladder) |
| Success definition | Better backtests / more modules | Raise **P(durable wealth)** via earned PL rungs; clean null only after real search (D-02) |
| Authority | Often confused with “model exists / tests green” | Only **surviving evidence** after gates (D-03); PL-5 for micro capital speech |
| Trader pitch | Risk of “it will make money” | “No promise until PL-3+; path designed **toward** promise, not away from it” |

---

## 2. Trust in numbers and tools

| Dimension | **Before** | **After** |
|---|---|---|
| Backtest / PF / E / WR | Often treated as truth when a run “looked right” | Default **`UNTRUSTED_RAW`** until validation flow reviewed vs intent (D-04) |
| LLM statements | Easy to treat as evidence | **NON_EVIDENCE** until artifact + quote-check (D-05) |
| Failure modes | Informal | Named **H1 invent / H2 misread / H3 wrong path** with tests |
| Run identity | Command may be forgotten | Every serious run has **`run_manifest`** (path, flags, ACTIVE_VERSION, lens, costs, labels) |
| Lens | Easy to mix CRT-only research with “full fusion” claims | Every claim **names lens** (gate-OFF vs gate-ON) (D-10) |

---

## 3. Research spine (candle → decision → learning)

| Step | **Before** | **After** |
|---|---|---|
| Data | CSV / fetchers exist; L3 integrity uneven | Still file-backed; **network/MT5 checks** optional but defined (L3/L4) |
| Features | Ontology / certification in progress | Same WHAT layer; pack and factory use **declared** features |
| Events / opportunities | CRT + opportunity streams; **F-022** contamination risk | **Outcome factory**: neutral seeds + **forward_walk** honest labels |
| Multi-engine scores | Engines exist; research often CRT-only; some inert (BitNet/TradeNet) | Same opportunity → **evidence channels**; zero-Δ **demoted**; inert stay off until Δ |
| Store disagreement | Partial logs / fusion meta | Structured opportunity + engine score table + disagreement retained |
| Predict vs outcome | Qualification exists but label hygiene uneven | Systematic **intended vs produced** + M4-style economic gates |
| Demotion | Ad hoc / findings prose | **Demotion ledger** (describe vs decide) from measured Δ |
| Decision policy | Full stack in code; live structural issues (F-048 class) | Policy only from **survivors**; non-survivors cannot buy authority |
| OOS / costs / regimes | Used in many programs; not one factory standard | Standard factory + costs + dual-lens discipline |
| Shadow / capital | Live path incomplete / PnL unverified (F-010) | **Dry shadow** path proven; capital only P7 + dual-ack |
| Monitor edge decay | Weak closed loop | Continuous monitor only after capital path exists |

### Visual

```text
BEFORE (typical path risk)
  data → features → CRT/entries → pretty backtest → hope
  (labels?, lens?, LLM summary?, model “exists”?)

AFTER (designed path)
  data → verified features → events → opportunity population
       → engines evidence (stored)
       → honest outcomes (factory)
       → incremental value / demote
       → survivors only → policy
       → OOS/costs → shadow → small capital → monitor
       (every step: manifest + trust token)
```

---

## 4. Synthetic fixture (story you locked)

| Dimension | **Before design work** | **After full design** |
|---|---|---|
| Intentional 4h geometry | Did not exist as golden | Exists: sweep 98.5 → … → TP_HIT R=2, entry idx 41 |
| Engine scores on pack | N/A or invented | **Real callables**, intended = produced (CRT/G/Z/RR) |
| Story edit | N/A | Still **CODE** in generator unless later externalized (D-23) |
| CI | No synth golden | **P1:** pytest golden CRITICAL_PASS |

---

## 5. Multi-LLM / research organization

| Dimension | **Before** | **After** |
|---|---|---|
| Multi-model use | You copy-paste; risk of **echo chamber** | Asymmetric roles + **no voting** (D-08) |
| Output types | Free chat + SESSION LOG + turn_ledger | Only **PROPOSAL / CRITIQUE / EXECUTION_EVIDENCE / DECISION** |
| Implementation lane | `multi_llm/` (DeepSeek plan → … → Claude) | **Kept** (dual-lane) unless AMB-01 supersedes |
| Research lane | Informal | Architect / diversity / critic / Claude executor + You capital |
| Model value | Assumed useful | **Measured** over 10 cycles; drop Grok/DeepSeek if zero Δ (D-19) |
| Bridge cost | High manual paste | Packages on disk; You still own capital |

---

## 6. Workstreams & phases (what “implemented” means)

| Phase | Before | After complete |
|---|---|---|
| **P0** | AMB open, plan draft | Defaults frozen; grant path clear |
| **P1** | Testing **design** only; synth manual | Markers, manifests, AH/VP tests, synth **CI golden** |
| **P2** | `forward_walk` exists; no program factory | Versioned opportunity+outcome factory + floors |
| **P3** | Engines run; demotion informal | Ablation Δ table + demotion ledger |
| **P4** | OI deferred; OHLCV nulls many | At least one **new-info** prereg closed (null OK) |
| **P5** | dry_run pieces / live_smoke exist | End-to-end **shadow dry** + manifest |
| **P6** | multi_llm for code delivery | Research cycle ledger + scorecard + keep/drop |
| **P7** | No governed micro-capital ritual | Dual-ack capital path **or** explicitly never opened |

---

## 7. Artifacts: before vs after

| Kind | **Before** | **After** |
|---|---|---|
| Program docs | Scattered session insight | Decision board + phased plan + I/O + testing + multi-LLM design |
| Run truth | Chat + ad hoc results folders | `run_manifest` + assertions + hash |
| Synth | — | `data/synthetic/erp_4h_m15/*` + generator |
| Factory | Opportunities / mixed labels | Clean population + re-derived outcomes |
| Findings | Living `current-findings.md` | Same **plus** DECISION co-sign before Validated flips |
| Research cycles | Chat threads | `research_cycle_ledger.jsonl` (4 kinds) |
| Capital | Informal / blocked | Checklist + env dual-ack only |

---

## 8. What does **not** automatically change (even after full implement)

These stay true unless **evidence** overturns them:

| Item | Note |
|---|---|
| **No guaranteed profit** | Design never promises edge (D-01) |
| Prior nulls (F-019 family, carry, etc.) | Still valid under their scopes until reopened with new ontology/data |
| BitNet/TradeNet | Stay off until ΔG001 |
| RR polarity ≠ true RR | Naming honesty remains (D-11) |
| You as capital owner | Never automated away (D-20) |
| File-backed, no DB | Unchanged stack choice |
| WHAT/WHO/HOW live spine | Still the production authority model; synth story is separate CODE until externalized |

**After implementation success can look like either:**

```text
A) One or more small, cost-surviving, replicated edges → shadow → micro capital
B) Honest multi-axis nulls + demoted dead models + faster kill of bad ideas
```

Both are **wins**. Only (A) allows P7.

---

## 9. Operator experience: before vs after

### Before

```text
Idea → ask LLM → run a script → read summary → maybe promote hope
You paste between Grok / ChatGPT / Claude / DeepSeek
Hard to know: wrong lens? bad labels? invented metric?
```

### After

```text
PROPOSAL (frozen H_tool or H_market)
  → CRITIQUE
  → freeze prereg
  → Claude EXECUTION_EVIDENCE (manifest + compare)
  → DECISION (retire / repair / replicate / next gate)
  → You authorize only expensive / capital steps
```

---

## 10. Risk profile

| Risk | **Before** | **After** |
|---|---|---|
| Self-deception via backtests | High | Lower (trust gate + factory) |
| LLM echo chamber | High | Lower if RCP used + measured |
| Years of infra without alpha | High | Still real — mitigated by demotion + new-info phase + stop rules |
| Premature capital | Possible | Structurally blocked until P7 gates |
| LLM theater (tokens without falsification rate) | High | Measured in P6 scorecard |

---

## 11. Checklist: “entire design implemented”

Tick only when true:

- [ ] P0 frozen (AMB defaults written)  
- [ ] P1 CI: AH/VP + synth golden green  
- [ ] P2 factory artifact + floors + contamination report  
- [ ] P3 demotion ledger from measured Δ  
- [ ] P4 at least one new-info prereg closed  
- [ ] P5 dry shadow path with manifest  
- [ ] P6 ten cycles + model keep/drop recorded  
- [ ] P7 either dual-ack micro run **or** explicit “not opened” DECISION  
- [ ] No production authority granted without Stage-3-class survivor  
- [ ] Decision board still matches reality (update if reversed)

---

## 12. Where to read next

| Doc | Role |
|---|---|
| This file | Before / after narrative |
| [Phased plan](edge-research-platform-phased-plan.md) | How to get from before → after |
| [Decision board](erp-decision-board-and-story-authority.md) | Locked D-* |
| [Program](edge-research-platform-program.md) | Living status |

---

*Before = capable lab with weak epistemic clamps.  
After = same lab with clamps, factory, demotion, and capital only for survivors — still no promise of wealth.*


========================================================================
# SOURCE: docs/research-readiness/edge-research-platform-io-map.md
# ROLE: io_map
========================================================================

# Edge Research Platform — Topic Input / Output Map

> **Purpose:** For each program topic, state **inputs** and **outputs** as per the plan and
> **existing codebase surfaces**.  
> **Unknowns:** parked — discuss **after full implementation plan** (see program §12; do not block on U-*).  
> **Status:** DESIGN reference · 2026-07-14 · Program `EDGE_RESEARCH_PLATFORM`  
> **Authority:** none (mapping only).  
> Companions: [program](edge-research-platform-program.md) · [testing plan](edge-research-platform-testing-plan.md)

**Trust default for every output row:** `UNTRUSTED_RAW` until validation-flow review (§2).

---

## 0. End-to-end spine (intent)

```text
INPUTS                          CODE / DATA                         OUTPUTS
─────────────────────────────────────────────────────────────────────────────
Market feeds / CSV     →   loaders / fetchers              →  OHLCV (+ optional perp)
OHLCV                  →   feature_pipeline + registry     →  verified feature vector
Features + bars        →   CRT / events                    →  opportunity seeds
Opportunity            →   engines (score evidence)        →  structured scores
Scores                 →   fusion + decision (live path)   →  approve / veto
Approve                →   planner + Ultron                →  order intent
Order intent           →   MT5 dry_run / live              →  ticket / skip
Path after entry       →   forward_walk / backtest exits   →  honest outcome labels
Labels + scores        →   qualification / demotion        →  keep / kill / authority
```

---

## 1. Workstream topics

### 1.1 WS-TEST-HARNESS (rank 0)

| | |
|---|---|
| **Plan role** | H1–H3 resistance; real-market outlets; pytest pyramid L0–L8 |
| **Inputs** | Test code; optional live network; optional MT5 terminal; control-plane process; fixtures under `tests/fixtures/`, `tests/golden/` |
| **Primary code (today)** | `tests/**`, `tests/conftest.py`, `tests/manual/live_smoke.py`, `tests/mt5_analytics/*`, `tests/test_live_integration.py`, `pyproject.toml` `[tool.pytest.ini_options]` |
| **To add (plan T0+)** | `tests/support/run_manifest.py`, markers, `results/test_runs/<run_id>/` |
| **Outputs** | JUnit/pytest status; `run_manifest.json`; `assertions.json`; `RUN_SHA256.txt`; SKIP if no broker |
| **Not an output** | Economic edge claim; production authority |

---

### 1.2 WS-OUTCOME-FACTORY (rank 1)

| | |
|---|---|
| **Plan role** | Neutral opportunities + honest future outcomes (anti F-022 contamination) |
| **Inputs** | OHLCV series; opportunity / signal seed (time, side, entry, SL/TP or rules); exit model name; cost bps; max horizon |
| **Primary code (today)** | `src/research/measurement/forward_walk.py` · `src/research/qualification.py` · `src/research/runner.py` · `src/research/zone_label_audit.py` (re-derive pattern) · `src/runtime/backtest_v2.py` (hot-loop exits aligned to forward_walk) · opportunity JSONL under research/results paths · `data/*_M15.csv` |
| **Outputs** | Per-opportunity outcome record: hit SL/TP, R multiple, path stats (MFE/MAE if computed), label_source=`forward_walk`, exit_model, costs; population table / JSONL; optional audit report (stream label vs re-derive) |
| **Not an output** | Trained model weights; live orders |

---

### 1.3 WS-OI-PATH-ABSTAIN (rank 2)

| | |
|---|---|
| **Plan role** | New info (OI/positioning/liq) as incremental path / abstain evidence |
| **Inputs** | Opportunity population (from factory); OI / funding / basis / future liq feeds; OHLCV baseline features |
| **Primary code (today)** | `src/inout/perp_funding_fetcher.py` · `data/perp/*` (funding/basis) · `src/research/cross_sectional.py` / carry programs (pattern only; carry *signal* already null under scope) · OI still **data-blocked** historically |
| **Outputs** | Joined opportunity×positioning features (PIT); path/abstain scores; incremental Δ vs OHLCV-only; M4-style qualify artifact if run |
| **Not an output** | Automatic fusion weight; production gate |

---

### 1.4 WS-ENGINE-DEMOTION (rank 3)

| | |
|---|---|
| **Plan role** | Measure incremental value; demote zero-Δ engines |
| **Inputs** | Same opportunity set; per-engine scores; honest outcomes from factory; cost model; optional gate-ON/OFF lens |
| **Primary code (today)** | `src/core/engine_runner.py` · `src/core/fusion_engine.py` · `src/core/decision_engine.py` · `src/engines/crt_engine.py` · `src/engines/*gaussian*` · `src/engines/zone_gate_engine.py` · `src/engines/rr_engine.py` · `src/engines/tradenet_meta_engine.py` · `src/config_layer/crt_engine_v2.py` · active config `configs/production/` + `ACTIVE_VERSION` |
| **Outputs** | Per-engine / ablation table: alone vs combinations; ΔE/ΔPF/ΔG001; demote/keep/describe decision; trust token on run |
| **Not an output** | Forced re-enable of rr_fusion/BitNet/TradeNet without Δ proof |

---

### 1.5 WS-NEW-INFO-SEARCH (rank 4) — blocked on factory

| | |
|---|---|
| **Plan role** | Automated hypothesis generation/falsification on non-dead families |
| **Inputs** | Clean opportunity+outcome factory; allowed feature families; pre-registered search space; multiplicity controls |
| **Primary code (today)** | `src/research/hypotheses/*` · `src/research/runner.py` · `src/research/qualification.py` · `src/interpreters/*` + adapter → forward_walk chain · `scripts/research/*` |
| **Outputs** | Hypothesis registry rows; PROMOTE/REJECT/INSUFFICIENT verdicts; frozen prereg artifacts under `docs/research-readiness/` / `results/research/` |
| **Not an output** | Production config change without promotion_manager |

---

### 1.6 WS-SHADOW-LIVE (rank 5) — blocked on survivor

| | |
|---|---|
| **Plan role** | Real path shadow / micro capital after survivor |
| **Inputs** | Live or replay candles; prod config; dry_run flags; kill switch state |
| **Primary code (today)** | `src/runtime/live_engine_hook.py` · `src/live/mt5_bridge.py` · `src/live/telegram_bridge.py` · `src/uat/kill_switch.py` · `src/core/ultron_risk_gate.py` · `src/config_layer/execution_planner.py` · `tests/test_live_integration.py` |
| **Outputs** | Shadow decision log; planned entry/SL/TP; dry_run ticket sentinel or real ticket (L8 only); PnL only if capital path; kill-switch events |
| **Not an output** | CI-green live profit claim (F-010) |

---

## 2. Pipeline stage topics (codebase spine)

### 2.1 Market data collect

| Direction | Artifact |
|---|---|
| **IN** | Exchange/broker API or local file path; symbol; timeframe; date range |
| **Code** | `src/inout/hummingbot_candle_fetcher.py` · `src/inout/mt5_candle_fetcher.py` · `src/inout/perp_funding_fetcher.py` · `src/data_ingestion/historical_fetcher.py` · control-plane fetch commands in `src/control_plane/registry.py` |
| **OUT** | `data/*_M15.csv`, `data/mt5/*`, `data/perp/*`, `data/binance/*` (as present) |
| **Test outlets** | L3 Binance public · L4 MT5 bars |

### 2.2 Verified features

| Direction | Artifact |
|---|---|
| **IN** | OHLCV bars; ontology / formula registry; window params from config |
| **Code** | `src/features/feature_pipeline.py` · `src/features/feature_schema.py` · `src/features/candle_math.py` · `src/features/registry/*` · `configs/formulas/` (if present) · `src/features/dataset_validator.py` |
| **OUT** | 38-dim (or declared) feature dict/vector; validation errors; certification ledger events (governance scripts) |
| **Trust note** | PIT/certification gaps are work-item scope, not free pass |

### 2.3 Events / opportunity seeds

| Direction | Artifact |
|---|---|
| **IN** | Features + bars; CRT config (`params` / engine sections) |
| **Code** | `src/config_layer/crt_engine_v2.py` · CRT path in backtest / live · opportunity JSONL writers used by research/training |
| **OUT** | State transitions; opportunity / TRADE_OPENED-like seeds; detection stream (≠ trade ledger — F-022) |

### 2.4 Multi-engine evidence

| Direction | Artifact |
|---|---|
| **IN** | Opportunity context + feature vector + config weights |
| **Code** | `src/core/engine_runner.py` · engines under `src/engines/*` · optional BitNet/TradeNet paths when enabled |
| **OUT** | `score_dict` / engine scores + metadata; fusion input |
| **Synth pack design** | `data/synthetic/erp_4h_m15/intended_spec.json` → `engines_feature_contract` + `engines_intended`; produced via `scripts/research/erp_synth_4h_trace.py` (CRT 0.8227 / Gaussian 0.9432 / Zone-soft 0.882419 / RR 0.6429) |

### 2.5 Fusion + decision

| Direction | Artifact |
|---|---|
| **IN** | Engine scores; fusion weights; thresholds; `BACKTEST_ENGINE_GATE` env for research |
| **Code** | `src/core/fusion_engine.py` · `src/core/decision_engine.py` · `src/runtime/backtest_v2.py` (gate flag) |
| **OUT** | execute / reject + reason codes; fusion audit lines |
| **Lens** | Research often CRT-only (gate off); live uses hook path — always name lens in outputs |

### 2.6 Plan + risk

| Direction | Artifact |
|---|---|
| **IN** | Approved signal; ATR/session; planner + ultron config sections |
| **Code** | `src/config_layer/execution_planner.py` · `src/core/ultron_risk_gate.py` |
| **OUT** | Entry/SL/TP/RR/TTL/size intent; APPROVE/REJECT risk |

### 2.7 Execution

| Direction | Artifact |
|---|---|
| **IN** | Order intent; `dry_run`; MT5 connection |
| **Code** | `src/live/mt5_bridge.py` · `src/runtime/live_engine_hook.py` · `mt5_analytics/*` (post-trade truth) |
| **OUT** | `mt5_ticket` (or dry-run sentinel); alerts via `telegram_bridge`; analytics episodes |

### 2.8 Outcome measurement

| Direction | Artifact |
|---|---|
| **IN** | Signal + future bars; exit_model; costs |
| **Code** | `src/research/measurement/forward_walk.py` · backtest exit tracking in `backtest_v2.py` · `src/research/qualification.py` |
| **OUT** | R, win/loss, path metrics; qualification verdict JSON under `results/research/` |

### 2.9 Governance / promotion

| Direction | Artifact |
|---|---|
| **IN** | ValidationReport; config; checkpoint |
| **Code** | `src/config_layer/config_validator.py` · `src/governance/promotion_manager.py` · `configs/promotion_log.jsonl` |
| **OUT** | PROMOTED / FAILED log line; archived config; **not** automatic from research nulls |

### 2.10 Control plane (operator)

| Direction | Artifact |
|---|---|
| **IN** | HTTP request / UI action; command name + params |
| **Code** | `src/control_plane/server.py` · `registry.py` · `jobs.py` · `dashboard_api.py` |
| **OUT** | Job id/status; logs; paths to result files |
| **Test** | Playwright L6 on `localhost:8787` |

---

## 3. Testing plan topics (I/O by layer)

| Layer | Topic | Inputs | Outputs |
|---|---|---|---|
| **L0** | Unit | Fixtures, pure functions | Pass/fail only |
| **L1** | Contract/golden | Frozen vectors, schemas | Pass/fail; drift alarms |
| **L2** | Research integrity / VP-* | Intent contract JSON; run under test | Manifest + path match/fail |
| **L3** | Binance public | Symbol, interval, public REST | Schema/PIT/gap/parity artifacts |
| **L4** | MT5 read-only | Running terminal (or SKIP) | Bars, episodes, verify report |
| **L5** | Exec dry-run | Intent + dry_run bridge | Sentinel ticket; no real order |
| **L6** | Playwright UI | Local control plane | UI status vs job argv/artifact |
| **L7** | Shadow economic | Frozen pop + engines + outcomes | Shadow bundle; still untrusted until review |
| **L8** | Capital micro | Dual env ack + checklist | Real fills/PnL (owner only) |

**Artifact shape (L2+):**

```text
IN:  command argv + ACTIVE_VERSION + intent contract
OUT: results/test_runs/<run_id>/{run_manifest.json, assertions.json, RUN_SHA256.txt}
```

---

## 4. Lifecycle topics (process I/O)

| Phase | Inputs | Outputs |
|---|---|---|
| **DESIGN** | Goal, workstream, unknowns parked | Prereg / intent contract / this I/O map row frozen |
| **IMPLEMENTATION** | Design freeze + owner grant | Code/config diff; construction protocol if required |
| **REVIEW** | Diff + intended path | PASS/FAIL; `FLOW_REVIEWED` |
| **TESTING** | Markers L0–L6 as applicable | pytest + manifests |
| **VALIDATION** | Frozen protocol + data | Verdict JSON; trust token; **no auto promote** |

---

## 5. Config / runtime identity (always declare)

| Direction | Artifact |
|---|---|
| **IN** | `configs/production/ACTIVE_VERSION` → active JSON via `get_prod_config()` / `get_prod_section()` |
| **Code** | `src/config_layer/production_config.py` (and related) |
| **OUT** | Version string + section dicts consumed by engines/live/backtest — must appear in every run_manifest |

---

## 6. Quick matrix (topic → one-line I/O)

| Topic | Main input | Main output |
|---|---|---|
| Test harness | Code + optional live feeds | Manifested test artifacts |
| Outcome factory | Seeds + future OHLCV | Honest labels / population |
| OI path/abstain | Population + positioning data | Incremental path/abstain evidence |
| Engine demotion | Scores + honest labels | Keep/demote table |
| New-info search | Clean factory + search space | Qualify verdicts |
| Shadow/live | Candles + config + bridges | Decision/order log (dry or real) |
| Features | OHLCV | Feature vector |
| CRT/events | Features + bars | Opportunity seeds |
| Engines | Opportunity + features | Evidence scores |
| Fusion/decision | Scores + gates | execute/reject |
| Planner/risk | Signal | Order intent / risk reject |
| MT5 | Intent | Ticket / dry sentinel |
| forward_walk | Signal + future bars | Outcome R / path |
| Qualification | Outcomes + controls | PROMOTE/REJECT/… |
| Promotion | ValidationReport | Config archive + log |
| Control plane | Command request | Job + result paths |
| Binance L3 | Public API | Live schema/parity report |
| Playwright L6 | Browser + UI | Operator path truth |

---

## 7. Parked for later (do not discuss now)

- Full **unknowns** debate (program §12 U-001…U-016) → **after full implementation plan**
- Assumption deep-dive (§13) → same
- Trader objections classification → when available

---

## 8. How to use this file

1. When writing the **full implementation plan**, each work package cites a **topic row** here.  
2. Implementation must not invent new I/O without updating this map.  
3. Validation claims must name the **output artifact path** from this map.  
4. Unknowns stay parked until implementation plan is complete.


========================================================================
# SOURCE: docs/research-readiness/edge-research-platform-testing-plan.md
# ROLE: testing_plan
========================================================================

# Edge Research Platform — Strong Testing Plan (H1–H3 + Real Market Outlets)

> **Status:** DESIGN (not implemented). Companion to  
> [`edge-research-platform-program.md`](edge-research-platform-program.md).  
> **Authority:** testing/process design only — grants **no** production or capital authority.  
> **Opened:** 2026-07-14 · **Program:** `EDGE_RESEARCH_PLATFORM`

---

## 0. Why this plan exists

Unit tests prove code branches. They do **not** prove:

- the agent reported a real run (H1),
- the agent interpreted the run correctly (H2),
- the run was the **intended** validation path with honest labels/costs (H3),
- research numbers survive **real market data / broker reality**.

This plan binds **pytest + real outlets** (Binance public API, MT5, control-plane UI via Playwright) into one trust ladder.

```text
Code unit tests (always CI)
        ↓
Contract / golden / determinism (CI)
        ↓
Network read-only market data (opt-in CI / nightly)
        ↓
Broker dry-run / analytics smoke (manual or gated)
        ↓
Shadow / paper path (owner grant)
        ↓
Tiny capital (only after FLOW_MATCHES_INTENT + economic survivor)
```

**Hard rules (inherit program §2 + §14):**

1. Every economic number starts as `UNTRUSTED_RAW`.
2. No finding upgrade from chat alone.
3. Real-market tests produce **on-disk artifacts** with provenance, not console-only claims.
4. Live order placement defaults **OFF** (`dry_run=true`); mutation tests are separate and owner-gated.
5. Never read or print `.env` secrets into logs/docs.

---

## 1. Threat model → test objectives

| Mode | Attack / failure | Test objective |
|---|---|---|
| **H1** | LLM invents “pytest green” / PF / trade counts | Every claim requires **artifact path + command provenance**; CI job publishes JUnit + hashed result bundle |
| **H2** | LLM misreads flags, instrument, gate-ON/OFF | Artifacts embed **machine-readable run manifest** (flags, ACTIVE_VERSION, instrument, lens); assertion helpers compare summary vs manifest |
| **H3** | Real run, wrong path / labels / costs | **Validation-path identity tests**: named entrypoint + config + label source must match work-item intent contract |
| **Market drift** | CSV corpus ≠ live feed schema/timezone | **Live feed vs frozen corpus schema/PIT gates** on Binance/MT5 pulls |
| **Execution gap** | Backtest fills ≠ broker | **Shadow / dry-run order intent vs MT5 state** (no size until grant) |
| **UI lie** | Control plane shows stale job status | **Playwright E2E** job submit → status → artifact link |

---

## 2. Test layers (pyramid)

| Layer | ID | Runs where | Real market? | Catches |
|---|---|---|---|---|
| **L0 Unit / pure** | `unit` | Every PR / CI | No (fixtures) | Logic bugs |
| **L1 Contract / golden** | `contract` | Every PR / CI | No (frozen vectors) | Schema, determinism, registry, formula parity |
| **L2 Research integrity** | `research_integrity` | Every PR + nightly | Frozen on-disk OHLCV/perp | Label/path identity, gate flags, no-lookahead |
| **L3 Network market-in** | `market_network` | Nightly / manual | **Yes — read-only** Binance/public REST (and optional exchange CCXT) | Feed shape, clock, gaps, symbol map |
| **L4 Broker analytics** | `broker_mt5_ro` | Manual / pre-release | **Yes — MT5 read-only** | Candle provider, deal reconstruct, verify reconcile |
| **L5 Execution dry-run** | `exec_dry_run` | Manual / owner | MT5 dry_run / paper | Order intent shape, clamp, kill-switch; **no real fills** |
| **L6 Control-plane UI** | `ui_playwright` | Nightly / manual | Localhost + optional job that hits read-only data | H2 on UI: wrong job, wrong command, stale status |
| **L7 Shadow economic** | `shadow_economic` | Owner grant only | Real data in, **no or micro risk** | Full path: opportunity → decision → planned order → outcome re-derive |
| **L8 Tiny capital** | `capital_micro` | Explicit owner + checklist | Real | Only after L7 survivor + `FLOW_MATCHES_INTENT` |

**CI default:** L0–L2 always.  
**Never in default CI:** L5 mutation, L7 economic promote, L8 capital.  
**Secrets:** L3 may use public endpoints only in CI; authenticated Binance/MT5 stay out of PR CI unless a locked runner exists.

---

## 3. pytest architecture (implementation target)

### 3.1 Markers (add to `pyproject.toml`)

```toml
[tool.pytest.ini_options]
markers = [
  "unit: pure logic, no network",
  "contract: golden/schema/determinism",
  "research_integrity: validation-path and label integrity",
  "market_network: read-only live market HTTP",
  "broker_mt5_ro: requires running MT5 terminal, read-only",
  "exec_dry_run: MT5/Telegram dry_run paths",
  "ui_playwright: control plane browser E2E",
  "shadow_economic: owner-gated shadow measurement",
  "capital_micro: owner-gated real capital — never default",
  "slow: long-running",
]
```

### 3.2 Selection recipes

```bash
# PR / local default (no network, no broker)
pytest -m "not market_network and not broker_mt5_ro and not exec_dry_run and not ui_playwright and not shadow_economic and not capital_micro"

# Nightly market-in (public)
pytest -m "market_network" --maxfail=5

# Pre-release broker truth
pytest -m "broker_mt5_ro"   # or: python tests/manual/live_smoke.py

# UI
pytest -m "ui_playwright" --browser chromium

# Forbidden unless owner env set
# RUN_CAPITAL_MICRO=1 pytest -m capital_micro
```

### 3.3 Artifact contract (every L2+)

Each non-unit test that produces economic or market claims writes:

```text
results/test_runs/<run_id>/
  run_manifest.json      # provenance
  assertions.json        # machine outcomes
  raw/                   # optional feed samples (redacted)
  RUN_SHA256.txt         # hash of manifest+assertions
```

**`run_manifest.json` minimum fields**

| Field | Purpose (H1/H2/H3) |
|---|---|
| `run_id`, `timestamp_utc` | Identity |
| `command`, `argv`, `cwd` | H1: real invocation |
| `git_sha`, `branch` | Reproducibility |
| `ACTIVE_VERSION`, `config_hash` | H3: config identity |
| `validation_lens` | e.g. `crt_only_gate_off` \| `fusion_gate_on` |
| `exit_model`, `cost_model_bps` | H3: economic identity |
| `label_source` | e.g. `forward_walk_intrabar_fixed` \| `opportunity_stream` |
| `instruments`, `timeframe`, `data_source` | H2: no instrument swap |
| `network` | `none` \| `binance_public` \| `mt5` \| `mixed` |
| `dry_run` | must be `true` unless L8 |
| `intended_work_item_id` | links to program WI |
| `validation_flow_review` | starts `UNTRUSTED_RAW` |

**Assertion helper (anti-H2):**  
`assert_summary_matches_manifest(summary_dict, manifest)` — fails if instrument/lens/cost in prose-facing summary ≠ manifest.

---

## 4. Real market outlets — what to test

### 4.1 Binance (and public crypto) — L3 `market_network`

**Existing surfaces to wrap (do not reinvent first):**

- Control-plane / fetcher paths using `exchange=binance` (registry already exposes binance/bybit/…)
- `src/inout/perp_funding_fetcher.py` / funding+basis corpus patterns
- Historical candle fetch used by research scripts

**Test packs**

| Test ID | Behavior | Pass criteria |
|---|---|---|
| **BN-SCHEMA-01** | Public klines for `BNBUSDT` M15 (last N bars) | Columns + dtypes match OHLCV contract; timestamps UTC monotonic |
| **BN-PIT-01** | Fetch “as of” boundary | No bar with open time > request watermark |
| **BN-GAP-01** | Gap/missing bar report | Missing ratio logged; hard fail only if policy threshold exceeded |
| **BN-PARITY-01** | Live pull vs on-disk `data/*_M15.csv` overlap window | Overlap equality within declared tolerance (float/ts) |
| **BN-FUND-01** | Funding/premium endpoints (if used) | Schema + no-lookahead join key to spot bars |
| **BN-FAIL-01** | Force bad symbol / timeout | Fail-closed; no invented bars; artifact records ERROR |

**Auth:** PR CI uses **public** endpoints only. Private account endpoints (if ever) = separate marker + secret store, not this program’s first ship.

**H3 guard:** BN-* tests assert `data_source=binance_public` in manifest and **never** claim “backtest edge.”

---

### 4.2 MT5 — L4 `broker_mt5_ro` + L5 `exec_dry_run`

**Existing assets (reuse):**

| Asset | Role |
|---|---|
| `tests/mt5_analytics/*` | Fixture + reconstruct + verify reconcile |
| `tests/manual/live_smoke.py` | Real terminal smoke (not collected by default) |
| `src/live/mt5_bridge.py` | Orders; dry_run sentinel already tested unit-side |
| `src/runtime/live_engine_hook.py` | Live spine consumer |
| `src/data_ingestion/historical_fetcher.py` | MT5 candle path when enabled |
| `tests/test_live_integration.py` | dry_run / disabled bridges (no terminal) |

**Read-only pack (L4)**

| Test ID | Behavior | Pass criteria |
|---|---|---|
| **MT5-CONN-01** | `initialize` + account metadata **redacted** | Connect or clean SKIP if no terminal (exit 0 for smoke) |
| **MT5-BARS-01** | Candle provider returns M15 for configured symbol | Schema + monotonic ts; count > 0 |
| **MT5-DEAL-01** | Reconstruct closed positions (N days) | Episodes valid under position schema |
| **MT5-VERIFY-01** | Reconcile MT5 truth ↔ analytics artifacts | Diff within policy; report written |
| **MT5-NO-MUTATE-01** | Introspect: execution mutation attrs not called | Same spirit as `live_smoke` check (6) |
| **MT5-FX-CSV-01** | Optional: live M15 vs `data/mt5/*` sample | Overlap parity / schema |

**Dry-run execution pack (L5)** — still **no real orders**

| Test ID | Behavior | Pass criteria |
|---|---|---|
| **MT5-DRY-01** | `MT5Bridge(dry_run=True).send_order(...)` | Sentinel ticket; no `order_send` to terminal |
| **MT5-DRY-02** | Lot clamp min/max | Out-of-range clamped |
| **MT5-HOOK-01** | `live_engine_hook` path with dry_run bridges | Structured result keys present; `mt5_ticket` dry-run consistent |
| **MT5-KILL-01** | Kill switch trips on large loss register | No further orders |

**Capital micro (L8)** — **not designed as automated green-path**

- Explicit checklist doc + human confirm
- Hard env: `RUN_CAPITAL_MICRO=1` AND `OWNER_CAPITAL_ACK=1`
- Max notional / max trades / time box in config
- Kill switch armed; Telegram alert required if enabled

---

### 4.3 Playwright — control plane UI (L6)

**Why Playwright (not “more unit tests”):**  
H2 often happens at the **operator surface** — wrong command selected, wrong params, job shows SUCCESS while artifact is empty.

**Scope:** `localhost:8787` control plane only (stdlib HTTP UI). No external trading website automation in v1 (Binance website scraping is out of scope; use REST).

| Test ID | Flow | Pass criteria |
|---|---|---|
| **UI-BOOT-01** | Open control plane root | UI loads; command catalog non-empty |
| **UI-CATALOG-01** | Catalog vs `registry.py` sample commands | Critical commands present (backtest, validate, fetch) |
| **UI-JOB-01** | Submit **read-only** / safe command (e.g. list commands / dry health) | Job id returned; status terminal SUCCESS/FAILED recorded |
| **UI-ARTIFACT-01** | Job that writes a known path | UI/API exposes path; file exists; manifest hash check |
| **UI-PARAM-01** | Invalid param rejected | Client-side or API error; no silent default that changes instrument |
| **UI-H2-01** | Deliberate mismatch: display instrument vs job argv | Test **fails** if UI summary ≠ argv (guardrail for future bugs) |

**Stack suggestion:** `pytest-playwright` (or Playwright Python) behind `ui_playwright` marker; start control plane as session fixture or require pre-started server.

**Security:** tests bind `127.0.0.1` only; no tunnel.

---

### 4.4 Optional later outlets (design placeholders)

| Outlet | Use | Priority |
|---|---|---|
| Bybit / OKX public REST | Cross-check crypto OHLCV | After BN pack stable |
| Binance WebSocket book ticker | Microstructure research only | After WS-OI design |
| Telegram dry_run | Alert path L5 | Already partial unit coverage |
| Paper account MT5 | L7 shadow | Owner |

---

## 5. Validation-path identity framework (core H3 harness)

### 5.1 Intent contract file (per work item)

```json
{
  "work_item_id": "WI-00N",
  "intended_entrypoint": "src/runtime/backtest_v2.py",
  "required_env": {"BACKTEST_ENGINE_GATE": "0"},
  "forbidden_env": {},
  "validation_lens": "crt_only_gate_off",
  "exit_model": "intrabar_fixed",
  "cost_model_bps": 12,
  "label_source": "forward_walk",
  "instruments": ["BNBUSDT"],
  "allow_network": false,
  "allow_broker": false
}
```

### 5.2 Tests

| Test ID | Asserts |
|---|---|
| **VP-01** | Runner records env/lens into `run_manifest.json` |
| **VP-02** | If actual lens ≠ intent contract → **FAIL** (H3) |
| **VP-03** | If `label_source=opportunity_stream` while intent says `forward_walk` → **FAIL** |
| **VP-04** | Economic assertions refuse to run unless manifest present |
| **VP-05** | Agent-facing “summary.md” must be generated **from** assertions.json (not free text) to reduce H2 |

### 5.3 Relation to program trust tokens

```text
L0–L1 green     → code health only
L2 VP-* green   → FLOW_REVIEWED possible
L2 + reviewed intent match → FLOW_MATCHES_INTENT (research evidence only)
L7 survivor     → AUTHORITY_ELIGIBLE candidate (still not auto-promote)
```

---

## 6. Anti-hallucination test pack (H1/H2 directly)

| Test ID | Idea |
|---|---|
| **AH-01** | Fixture: fake LLM summary with wrong PF; `assert_summary_matches_manifest` must fail |
| **AH-02** | Fixture: missing `run_manifest` → economic claim helper raises |
| **AH-03** | Fixture: tool timeout / empty stdout → status ERROR, no default success |
| **AH-04** | Session log / program JSON must not gain fabricated metrics without artifact path (doc test optional) |
| **AH-05** | Golden: known command produces known manifest fields for BNBUSDT dry backtest (small fixture CSV) |

These are **pure CI** tests — no network.

---

## 7. Mapping to workstreams

| Workstream | Required layers before “validated” |
|---|---|
| **WS-OUTCOME-FACTORY** | L0–L2 + VP-* + AH-*; BN-PARITY on any live refresh of corpus |
| **WS-OI-PATH-ABSTAIN** | L3 for OI/funding feeds; L2 path identity; no L8 |
| **WS-ENGINE-DEMOTION** | L1–L2 incremental-value harness; dual-lens explicit (gate on/off) |
| **WS-SHADOW-LIVE** | L4 + L5 + L7; UI optional; L8 only after grant |
| **Control plane ops** | L6 Playwright for operator truth |

---

## 8. Implementation phases (design → build order)

### Phase T0 — Scaffold (no network)

1. Add pytest markers to `pyproject.toml`.
2. Add `tests/support/run_manifest.py` (write/read/hash manifest).
3. Add `tests/support/assert_summary_matches_manifest.py`.
4. Add AH-01..05 + VP-01..04 against fixtures.
5. Wire default CI exclude list for network/broker/ui markers.

**Exit:** PR CI green; inventing metrics without manifest is hard-fail in helpers.

### Phase T1 — Market network (Binance public)

1. `tests/market_network/test_binance_klines_schema.py` etc.
2. Nightly workflow (or documented manual command).
3. Optional: reuse existing fetch scripts behind thin test wrappers.

**Exit:** BN-SCHEMA/PIT/GAP/FAIL green on nightly; artifacts under `results/test_runs/`.

### Phase T2 — MT5 promote smoke into markers

1. Wrap or twin `tests/manual/live_smoke.py` checks as `broker_mt5_ro` tests with SKIP if no terminal.
2. Keep mutation impossible by default.
3. Document pre-release: `pytest -m broker_mt5_ro` + live_smoke.

**Exit:** Same guarantees as live_smoke, collectable, artifacted.

### Phase T3 — Playwright control plane

1. Add dev optional dep `playwright` / `pytest-playwright` (optional extra, not hard prod dep).
2. UI-BOOT, UI-JOB, UI-ARTIFACT against localhost.
3. Nightly or manual.

**Exit:** Operator cannot be shown SUCCESS without artifact existence check.

### Phase T4 — Shadow economic harness (owner)

1. Single scripted path: frozen opportunities → engines → dry plan → forward_walk outcomes.
2. Full manifest + dual-lens options.
3. Still `UNTRUSTED_RAW` until human sets `FLOW_MATCHES_INTENT`.

**Exit:** Reproducible shadow bundle; no capital.

### Phase T5 — Capital micro (checklist only until needed)

Do **not** automate green CI. Checklist in program work item when a survivor exists.

---

## 9. CI / scheduling matrix

| Pipeline | Markers | Frequency |
|---|---|---|
| PR | `unit`, `contract`, `research_integrity`, `AH-*`, `VP-*` (fixture) | Every push |
| Nightly | + `market_network` | Daily |
| Pre-release human | + `broker_mt5_ro`, `exec_dry_run`, `ui_playwright` | Before any live claim |
| Owner only | `shadow_economic` | After design freeze |
| Never auto | `capital_micro` | Explicit dual env ack |

---

## 10. What this plan deliberately does **not** do

- Does not claim Playwright on binance.com (fragile, ToS risk) — use **API**.
- Does not enable live orders in CI.
- Does not treat L0–L2 green as economic edge.
- Does not replace M4 / qualification science — it **certifies the instrument**.
- Does not trust backtests until validation path matches intent (program §2).

---

## 11. Success criteria for “strong testing” (program-level)

| Criterion | Met when |
|---|---|
| H1 resisted | No economic claim accepted without `run_manifest` + artifact hash |
| H2 resisted | Summary≠manifest fails tests; UI argv≠display fails UI-H2 |
| H3 resisted | VP-* fails on lens/label/cost mismatch |
| Real market-in | Nightly BN-* or documented manual green within SLA |
| Broker truth | Pre-release MT5-RO green or explicit SKIP with reason |
| Capital safety | L8 impossible without dual env + owner checklist |

---

## 12. Open design choices (owner)

1. Nightly runner host (local Windows with MT5 vs Linux CI without MT5)?
2. Playwright as optional extra vs separate package?
3. Should BN-PARITY hard-fail on any drift or WARN + ticket?
4. Who signs `FLOW_MATCHES_INTENT` on shadow bundles (U-013)?

---

## 13. Next implementation grant (suggested)

**Minimal first ship (T0 only)** after owner says implement:

- markers + run_manifest helpers + AH/VP fixture tests  
- no Binance/MT5/Playwright code yet  

Then T1 (Binance public) as first **real market-out** proof.

---

## 14. Traceability

| Program concept | This plan |
|---|---|
| TP-BACKTEST-VALIDATION-GATE | VP-*, L2, manifests |
| TP-TOOL-HALLUCINATION H1/H2/H3 | AH-*, UI-H2, artifact hash |
| WS-OUTCOME-FACTORY | T0 + T1 + VP label_source |
| WS-SHADOW-LIVE | T2 + T4 + T5 |
| F-010 / F-037 / F-022 | Lenses + label_source + live gap tests |


========================================================================
# SOURCE: docs/research-readiness/edge-research-platform-multi-llm-design.md
# ROLE: mllm_design_amb
========================================================================

# Edge Research Platform — Integrated Design (Research Loop + Multi-LLM Control Plane)

> **Status:** DESIGN incorporated into program · 2026-07-14  
> **Program:** `EDGE_RESEARCH_PLATFORM`  
> **Authority:** design only — grants no production / capital authority  
> **Companions:** [program](edge-research-platform-program.md) · [I/O map](edge-research-platform-io-map.md) · [testing plan](edge-research-platform-testing-plan.md) · [§16 model/tool hypotheses](edge-research-platform-program.md) · existing [`multi_llm/`](../../multi_llm/README.md)

This file **folds two owner-facing designs into the current program**:

1. **Research platform loop** — how the trading research system is supposed to work (trader-friend narrative).  
2. **Multi-LLM Research Control Plane** — how multiple models work without becoming an echo chamber.

It also lists **ambiguities** that must be resolved before implementation (not silently assumed).

---

## 1. What is already true in the current program

| Existing piece | Where | Maps to |
|---|---|---|
| Trust: backtest untrusted until validation flow matches intent | program §2 | Steps 7–10 honesty |
| H1/H2/H3 tool-output policy | program §14–§16 | No free-form tool truth |
| Lifecycle DESIGN→…→VALIDATION | program §3 | Prereg → execute → review |
| Workstreams (test harness, outcome factory, OI, demotion, shadow) | program §4 | Steps 1–13 priorities |
| I/O map topic contracts | io-map | Every step’s inputs/outputs |
| Synth 4h pack intended vs produced | `data/synthetic/erp_4h_m15/` | Engine evidence + outcome factory template |
| Multi-LLM protocol (existing) | `multi_llm/`, CLAUDE.md §13 | Partial overlap — **role map differs** (see §5) |
| Living findings + reversals | `docs/current-findings.md` | Maintained truth |
| Hypothesis registry artifact | `data/hypothesis_registry.jsonl` (generated) | Seed for control plane |

**Hard rule preserved:** models (market or LLM) never earn authority by fluency or consensus.

---

## 2. Research platform loop (incorporated)

### 2.1 What the project is *not*

```text
Find a strategy → backtest until pretty → trade it
```

### 2.2 Canonical progression (steps 1–13)

Aligned to program goal + I/O map:

```text
 1. COLLECT MARKET DATA
 2. CALCULATE VERIFIED MARKET FEATURES
 3. DETECT INTERESTING MARKET EVENTS
 4. CREATE AN OPPORTUNITY
 5. MULTIPLE ENGINES ANALYZE THE SAME OPPORTUNITY
 6. STORE ALL EVIDENCE + DISAGREEMENT
 7. TEST WHETHER ANY EVIDENCE PREDICTS FUTURE OUTCOMES
 8. REMOVE MODELS / FEATURES THAT ADD NO VALUE
 9. BUILD DECISION POLICY FROM ONLY SURVIVING EVIDENCE
10. TEST OOS + COSTS + SLIPPAGE + REGIMES
11. PAPER / SHADOW DEPLOYMENT
12. SMALL CAPITAL
13. CONTINUOUSLY MONITOR WHETHER EDGE STILL EXISTS
```

### 2.3 Parallel “factory” view

```text
RAW MARKET INFORMATION
  → POINT-IN-TIME EVENTS
  → OPPORTUNITY POPULATION
  → HONEST FUTURE OUTCOMES
  → FEATURES + MODELS + HYPOTHESES
  → MEASURE INCREMENTAL VALUE
  → FALSIFY WEAK IDEAS
  → REPLICATE SURVIVORS
  → DECISION POLICY
  → REALISTIC EXECUTION TESTING
  → SHADOW → SMALL CAPITAL → SCALE IF LIVE EDGE HOLDS
```

### 2.4 Mapping steps → current workstreams / code

| Steps | Workstream / surface | Code / artifact anchors |
|---|---|---|
| 1 | Market data | `src/inout/*`, `data/*`, L3 Binance / L4 MT5 tests |
| 2 | Features | `feature_pipeline`, ontology/registry, certification |
| 3–4 | Events / opportunities | CRT/`crt_engine_v2`, opportunity streams; **factory** must clean labels (F-022) |
| 5–6 | Engines + store | `engine_runner`, engines; synth pack engines design |
| 7 | Outcomes | `forward_walk`, qualification |
| 8 | Demotion | WS-ENGINE-DEMOTION; Authority Ladder |
| 9–10 | Policy + OOS | decision/fusion only from survivors; M4-style gates |
| 11–13 | Shadow/live | `live_engine_hook`, MT5 dry_run → capital only after grant |

### 2.5 Accuracy notes for the trader pitch (do not overclaim)

| Pitch line | Repo accuracy note |
|---|---|
| “Multiple engines analyze every opportunity” | **Target architecture.** Research default often CRT-only (F-037 / gate-OFF). Live fusion path differs. Always name the lens. |
| “RR evaluates payoff distribution” | **Aspirational naming.** RREngine is candle polarity (F-048 class), not true forward RR. Ultron/planner own true RR. |
| “BitNet / TradeNet contribute” | Built / available; **inert or unwired** on active path (F-004 / F-005) until ΔG001. |
| “After thousands of opportunities…” | Measurement ambition; many cells still underpowered or null under M4. |
| Order flow / OI examples | Valid **next information families**; OI historically data-blocked — design, not proven. |

**North-star sentence (keep):**  
*Infrastructure to answer which information, if any, has repeatable decision value after costs — not “CRT knows how to make money.”*

---

## 3. Multi-LLM Research Control Plane (incorporated)

### 3.1 Problem being solved

Multiple capable LLMs **≠** a research system. Without roles, frozen specs, evidence handoffs, and single repo truth, you get a **multi-LLM echo chamber**.

### 3.2 Target organization (design intent)

```text
                    YOU
          OBJECTIVE + CAPITAL OWNER
             FINAL RISK AUTHORITY
                     │
                     ▼
         RESEARCH CONTROL PLANE
    (packages: PROPOSAL | CRITIQUE |
     EXECUTION_EVIDENCE | DECISION)
                     │
       ┌─────────────┼─────────────┐
       ▼             ▼             ▼
   HYPOTHESIS     TECHNICAL      ARCHITECT
   DIVERSITY      CRITIC         + REVIEWER
   (Grok*)        (DeepSeek*)    (ChatGPT*)
       │             │             │
       └─────────────┼─────────────┘
                     ▼
                   CLAUDE
            CODEBASE EXECUTOR
     inspect → implement → test → record
                     │
                     ▼
            REPOSITORY EVIDENCE
                     │
                     ▼
              INDEPENDENT REVIEW
                     │
              RETIRE | REPAIR | REPLICATE | PROMOTE GATE
                     │
                     ▼
              MAINTAINED TRUTH
              (findings / registries)
```

\*Role labels are **design targets** — conflict with current `multi_llm/` role cards is §5 AMB-01.

### 3.3 Four legal artifact kinds (only)

| Kind | Meaning | May become repo truth? |
|---|---|---|
| **PROPOSAL** | H_tool / H_market / experiment sketch | No — status PROPOSED |
| **CRITIQUE** | Attack on design, leakage, stats, path | No — may force redesign |
| **EXECUTION_EVIDENCE** | Machine-readable run + manifest + compare | Research record after §2 |
| **DECISION** | RETIRE / REPAIR / REPLICATE / EXPAND / next gate | Yes if signed + evidence-bound |

**Rules:**

- No free-form chat conclusion becomes truth.  
- No model approves its own work.  
- No experiment changes after results are observed (prereg freeze).  
- No LLM vote substitutes for empirical evidence.  
- Capital / production: **You only**.

### 3.4 Operating loop (8 steps — design)

| Step | Actor (design) | Output kind |
|---|---|---|
| 1 Define question | Architect | PROPOSAL (hypothesis + gates + stop) |
| 2 Outside-view challenges | Hypothesis diversity agent | PROPOSAL (counter-H) |
| 3 Attack design | Technical critic | CRITIQUE |
| 4 Synthesize + freeze prereg | Architect | DECISION (freeze) + frozen spec |
| 5 Execute in codebase | Claude | EXECUTION_EVIDENCE |
| 6 Review actual evidence | Architect (≠ executor) | CRITIQUE or DECISION |
| 7 Branch | Architect + evidence | RETIRE / REPAIR / REPLICATE / EXPAND |
| 8 Authorize expensive next | **You** | DECISION (budget/capital) |

### 3.5 Long-term: reduce manual copy-paste bridge

**Near term (honest):** You remain bridge (copy packages between chats).  
**Target:** Research Control Plane reads/writes:

- hypothesis registry (seed exists: `data/hypothesis_registry.jsonl` — generated)  
- experiment registry (partially: research-readiness preregs + MSIP/PREP patterns)  
- evidence manifests (`run_manifest`, `produced_compare`, `results/research/*`)  
- findings (`docs/current-findings.md`)  
- decision ledger (to define; promotion_log is production-only)

Packages are **file-backed**, not chat memory.

### 3.6 Measure whether extra LLMs earn their seat

Do **not** assume Grok/DeepSeek permanent value. Track per cycle:

| Metric | Intent |
|---|---|
| Unique accepted hypotheses per model | Diversity |
| Defects caught pre-execution by critic | Quality |
| Spec changes from valid critique | Signal |
| Cost (tokens/time) per falsified H | Efficiency |
| Surviving effects per cycle | Research ROI |

If marginal contribution ≈ 0 → **remove from loop** (same Authority Ladder spirit as demoting engines).

### 3.7 Highest-leverage next project (design ranking)

**Not** another trading model first.

> **Governed Multi-LLM Research Control Plane on existing repo truth**  
> + **10 controlled research cycles** measuring each model’s incremental value.

Still **after / alongside** integrity (outcome factory + test harness) so cycles are not theater on dirty labels.

Suggested workstream id: **WS-MLLM-RCP** (see program priority update).

---

## 4. How the two designs join (one system)

```text
MULTI-LLM CONTROL PLANE          RESEARCH PLATFORM SPINE
(how intelligence is organized)  (what is being researched)
───────────────────────────────  ────────────────────────────
PROPOSAL H_market / H_tool   →   steps 3–7 design
CRITIQUE                     →   prereg freeze quality
Claude EXECUTION_EVIDENCE    →   steps 1–8 / 11 instrumentation
DECISION RETIRE/REPLICATE    →   step 8 demotion / step 9 survivors
You capital authorize        →   steps 12–13 only
```

**LLMs accelerate falsification and design.**  
**Engines/features/data produce economic evidence.**  
**You own risk.**

---

## 5. Ambiguities (discuss / resolve before implement)

Each item: **AMBIGUITY · options · recommendation**.

### AMB-01 — Role map vs existing `multi_llm/`

| | |
|---|---|
| **Conflict** | Today (CLAUDE.md §13 / `multi_llm/`): DeepSeek=**Planner**, Gemini Think=Quant, Gemini Pro=Optimizer, ChatGPT=**Interpreter** (never executes), Claude=**Executor**, Grok=**Synthesizer**. Proposed design: ChatGPT=**Architect+Reviewer**, Grok=**Hypothesis diversity**, DeepSeek=**Critic**, Claude=Executor, Gemini **absent**. |
| **Options** | (A) Supersede multi_llm role cards with this design. (B) Keep multi_llm for *code delivery*; use this design only for *research science cycles*. (C) Hybrid: research cycles use Grok/DeepSeek/ChatGPT/Claude; implementation epics keep Gemini + old DeepSeek-plan. |
| **Recommendation** | **(B) then evolve to (C):** two lanes — **Research lane** (this doc) vs **Implementation lane** (`multi_llm/`). Shared: four artifact kinds + repo truth. Avoid one vote across all models. |

### AMB-02 — Who freezes prereg and who reviews Claude

| | |
|---|---|
| **Conflict** | Same model as architect and post-hoc reviewer can rubber-stamp. |
| **Options** | (A) ChatGPT freezes; DeepSeek reviews evidence. (B) ChatGPT freezes; second ChatGPT session / You review. (C) You always co-sign freezes. |
| **Recommendation** | Freeze = Architect + **You** for any RUN/spend; evidence review = **Critic or You**, not the executor; architect may draft review but not sole sign FLOW_MATCHES_INTENT (U-013). |

### AMB-03 — Automation level of the “bridge”

| | |
|---|---|
| **Conflict** | “Stop being copy-paste bridge” vs capital authority and tool access still human. |
| **Options** | (A) File packages only (manual paste). (B) Shared JSONL APIs + one inbox. (C) Full agent orchestration (high risk). |
| **Recommendation** | **(A)→(B):** define package schema first; no autonomous multi-agent write to findings without You. |

### AMB-04 — Control plane vs outcome factory priority

| | |
|---|---|
| **Conflict** | “Highest leverage = Multi-LLM RCP” vs program rank-1 outcome factory / rank-0 test harness. |
| **Options** | (A) RCP first. (B) Factory+harness first. (C) Thin RCP protocol (docs+JSONL) **in parallel** with factory; no heavy automation until factory exists. |
| **Recommendation** | **(C):** write protocol + 4 artifact kinds + 10-cycle scorecard **now** (cheap); **do not** delay factory; avoid LLM theater on contaminated labels. |

### AMB-05 — Four artifact kinds vs SESSION LOG / turn_ledger / findings

| | |
|---|---|
| **Conflict** | Multiple logs already exist (`assistant_project.md`, `llm_project_assistant.md`, `multi_llm/turn_ledger.jsonl`, findings). |
| **Options** | (A) New registries only. (B) Map four kinds onto existing files. (C) Single `research_cycle_ledger.jsonl`. |
| **Recommendation** | **(C) + (B):** one append-only `research_cycle_ledger.jsonl` with `kind ∈ {PROPOSAL,CRITIQUE,EXECUTION_EVIDENCE,DECISION}`; SESSION LOG remains engineering ritual; findings only for economic/architectural conclusions. |

### AMB-06 — Grok permanent role value

| | |
|---|---|
| **Conflict** | Design assumes Grok diversity; unknown if it beats ChatGPT solo. |
| **Options** | Measure 10 cycles vs remove. |
| **Recommendation** | **Measure; no permanent seat without metric.** Same for DeepSeek critic. |

### AMB-07 — “No voting” vs multi-model agreement language

| | |
|---|---|
| **Conflict** | Humans still say “models agree.” |
| **Options** | Ban consensus language; require disagreement log. |
| **Recommendation** | Agreement is **non-evidence**. Only EXECUTION_EVIDENCE + gates matter. |

### AMB-08 — Research spine multi-engine narrative vs CRT-only measurement

| | |
|---|---|
| **Conflict** | Pitch step 5 vs F-037 gate-OFF. |
| **Options** | (A) Change default research to gate-ON. (B) Dual-lens always. (C) Pitch only as target state. |
| **Recommendation** | **(B)+(C):** every H_market names lens; demotion workstream uses explicit dual-lens. |

### AMB-09 — RR / BitNet / TradeNet in the friend pitch

| | |
|---|---|
| **Conflict** | Example dialogue overstates engine roles. |
| **Options** | Soften pitch; or keep as *intended* with footnotes. |
| **Recommendation** | Pitch uses **roles as intent**; footnotes: polarity vs RR, inert flags, Authority Ladder. |

### AMB-10 — Scope of “10 controlled research cycles”

| | |
|---|---|
| **Conflict** | Cycles on what population? Toy synth only? Live majors? |
| **Options** | (A) Synth + one H_tool only. (B) One real H_market on factory. (C) Mix. |
| **Recommendation** | **First 3 cycles H_tool-only** (path/engine/manifest) on synth pack; **next 7** only after outcome factory design freeze — prevents theater. |

### AMB-11 — Interaction with parked unknowns / MSIP PREP

| | |
|---|---|
| **Conflict** | MSIP whole-representation prereg parked; unknowns parked until full impl plan. |
| **Options** | Fold MSIP into RCP cycles; or keep separate science track. |
| **Recommendation** | Separate science tracks OK; **same four artifact kinds + freeze rules** for all. |

### AMB-12 — Who may write `docs/current-findings.md`

| | |
|---|---|
| **Conflict** | Claude historically writes findings; design says independent review first. |
| **Options** | Claude drafts; review DECISION required before Validated flip. |
| **Recommendation** | Claude may draft; **Validated/Reversal only after DECISION package** co-signed by You (and preferably critic). |

---

## 6. Proposed priority stack adjustment (design only)

| Rank | Workstream | Note |
|---|---|---|
| 0 | WS-TEST-HARNESS | Unchanged — anti theater |
| 0b | **WS-MLLM-RCP** (thin) | Protocol + 4 kinds + cycle scorecard + package schema — **docs/JSONL first** |
| 1 | WS-OUTCOME-FACTORY | Unchanged — dirty labels kill science |
| 2+ | as before | |

**Do not** reorder factory behind full multi-agent automation.

---

## 7. Ambiguity resolution checklist (owner)

When you want to freeze this design, pick:

| ID | Your choice (fill) |
|---|---|
| AMB-01 | A / B / C / other: ___ |
| AMB-02 | A / B / C / other: ___ |
| AMB-03 | A / B / C / other: ___ |
| AMB-04 | A / B / C / other: ___ |
| AMB-05 | A / B / C / other: ___ |
| AMB-06 | measure / always-on / drop: ___ |
| AMB-08 | A / B / C: ___ |
| AMB-10 | A / B / C: ___ |
| AMB-12 | policy: ___ |

Until filled, implementers must treat multi-LLM RCP as **protocol design**, not role-card rewrite of `multi_llm/`.

---

## 8. What we know / think / don’t know (on this incorporation)

| | |
|---|---|
| **Know** | Research loop + adversarial multi-LLM design match program goal; repo already has findings, preregs, registries, Claude executor discipline. |
| **Think** | Thin RCP + factory + harness beats new models; measure Grok/DeepSeek. |
| **Don’t know** | Whether multi-LLM diversity pays for itself; whether You will accept dual-lane (research vs implement). |
| **Failure mode** | LLM theater without higher falsification rate. |
| **Next** | Owner resolve AMB table **or** authorize thin package schema only. |


========================================================================
# SOURCE: docs/research-readiness/edge-research-platform-program.md
# ROLE: program_tracker
========================================================================

# Edge Research Platform Program

> **Living program control surface** (human). Machine twin:
> [`edge-research-platform-program.json`](edge-research-platform-program.json).
> Update **both** in the same turn when status, decisions, or conversation log change.
>
> **Authority:** tracking + research planning only. Grants **no** production, promotion,
> or capital authority (CLAUDE.md §6.5 Authority Ladder).

| Field | Value |
|---|---|
| **Program ID** | `EDGE_RESEARCH_PLATFORM` |
| **Status** | `ACTIVE` |
| **Opened** | 2026-07-14 |
| **Updated** | 2026-07-14 |
| **Branch scope** | `feature/truth-registry-v2` (statements are branch-scoped) |
| **ACTIVE_VERSION at open** | `v2_multi_2026_04` |
| **Testing plan (DESIGN)** | [`edge-research-platform-testing-plan.md`](edge-research-platform-testing-plan.md) |
| **I/O map (DESIGN)** | [`edge-research-platform-io-map.md`](edge-research-platform-io-map.md) |
| **Synthetic 4h OHLCV trace** | [`erp-synthetic-4h-trace.md`](erp-synthetic-4h-trace.md) + `data/synthetic/erp_4h_m15/` |
| **Integrated research + multi-LLM design** | [`edge-research-platform-multi-llm-design.md`](edge-research-platform-multi-llm-design.md) |
| **Decision board + story authority (READ FIRST)** | [`erp-decision-board-and-story-authority.md`](erp-decision-board-and-story-authority.md) |
| **Phased design plan (ACTIVE)** | [`edge-research-platform-phased-plan.md`](edge-research-platform-phased-plan.md) |
| **Before / after full implement** | [`edge-research-platform-before-after.md`](edge-research-platform-before-after.md) |
| **Promise ladder (path to wealth language)** | [`edge-research-platform-promise-ladder.md`](edge-research-platform-promise-ladder.md) |
| **Multi-LLM HOW (initiated)** | [`edge-research-platform-mllm-how.md`](edge-research-platform-mllm-how.md) + [`multi_llm/research_lane/`](../../multi_llm/research_lane/README.md) |
| **Unknowns discussion** | **PARKED** until full implementation plan is written — *phased plan now exists; unknowns stay parked until P0 freeze if desired* |

**Read order for planning turns:** §2 Trust → **I/O map** → **multi-LLM integrated design** → **testing plan** → §4 Priority stack.  
(§12 Unknowns / §13 Assumptions: reference only — **discuss after full implementation plan**.)

---

## 1. Goal

**Primary goal**

Maximize the probability of either:

1. finding a **small number** of edges that survive costs, OOS, regime splits, and realistic execution, **or**
2. proving cleanly that the **current information set cannot produce** such edges —

**per unit of calendar time and capital risk.**

**Not goals**

- Maximize architecture elegance or model count
- Treat CRT / Gaussian / Zone / RR / BitNet / TradeNet existence as edge
- Optimize a backtest until it looks profitable
- **Trust raw backtest numbers before validation-flow review** (see §2)

**The bet**

A rigorous research system (honest costs, no lookahead, controls, OOS, demotion of weak ideas)
beats hand-tuning indicators until a ledger looks good — *without claiming a profitable strategy
already exists.*

---

## 2. Trust policy (HARD) — do not skip

### TP-BACKTEST-VALIDATION-GATE

> **Do NOT trust backtest data, ledgers, PF / expectancy / win-rate numbers, or qualification
> verdicts until the validation flow that consumed them has been reviewed and confirmed to
> match the intended implementation.**

| Default trust on any new result | `UNTRUSTED_RAW` |
|---|---|
| Severity | **HARD** — no decision, finding upgrade, or “it works” claim on unreviewed flow |

**Applies to**

- `backtest_v2` outputs and golden ledgers used as economic evidence
- Spine / research qualification results
- Opportunity-stream derived labels (F-022 contamination class)
- M4 / `forward_walk` results when used for edge claims
- Any PF, E[R], WR, or trade-count used for ranking ideas

**Required before trust**

1. Name the **exact validation path consumed** (e.g. CRT-only gate-OFF research spine vs fusion gate-ON; which exit model; cost model; label source).
2. Review that path against **intended implementation** (code + config + `ACTIVE_VERSION`).
3. Confirm no lookahead, wrong exit model, wrong cost model, or contaminated labels for the claim being made.
4. Set the work item’s `validation_flow_review` status (see tokens below) **before** treating numbers as research evidence.

**Status tokens**

| Token | Meaning |
|---|---|
| `UNTRUSTED_RAW` | Artifacts exist; validation flow not reviewed |
| `FLOW_REVIEWED` | Consumed path inspected and documented |
| `FLOW_MATCHES_INTENT` | Path matches intended implementation; numbers may be used as **research evidence only** |
| `AUTHORITY_ELIGIBLE` | Survived qualification + Authority Ladder; still not automatic production authority |

**Related repo evidence (why this rule exists)**

- F-022 — opportunity stream ≠ trade ledger; labels can lie
- F-037 — research spine often CRT-only (`BACKTEST_ENGINE_GATE=0`); fusion path differs
- F-010 — live PnL unverified
- F-041B / F-045 — contaminated or indeterminate economic labels
- F-048 — live decision path structural issues

---

## 3. Lifecycle (how we work this program)

Every work item moves through:

```text
DESIGN → IMPLEMENTATION → REVIEW → TESTING → VALIDATION
```

| Phase | Purpose | Typical exit |
|---|---|---|
| **DESIGN** | Pre-register hypothesis, population, targets, controls, kill criteria | Design freeze or owner grant |
| **IMPLEMENTATION** | Surgical code / config / data plumbing | Diff + construction protocol if code |
| **REVIEW** | Design and/or implementation vs intent; **includes validation-flow review** | Review PASS / FAIL |
| **TESTING** | Unit / integration / determinism / parity floors | Tests green (not economic truth) |
| **VALIDATION** | Frozen scientific/economic protocol | Verdict + trust token (never skip §2) |

**Rule:** `TESTING` green ≠ edge. `VALIDATION` numbers ≠ trusted evidence until §2 is satisfied.

---

## 4. Priority stack (default until owner revises)

| Rank | Workstream | Status | Phase | Why first |
|---|---|---|---|---|
| 0 | **WS-TEST-HARNESS** — H1–H3 + real-market test pyramid (Binance/MT5/Playwright) | PLANNED | DESIGN | Without harness, every later validation is chat-vulnerable; see [testing plan](edge-research-platform-testing-plan.md) |
| 0b | **WS-MLLM-RCP** — thin Multi-LLM Research Control Plane (4 artifact kinds + cycle scorecard) | PLANNED | DESIGN | Anti echo-chamber; **parallel thin protocol only** — does not jump factory (AMB-04); see [integrated design](edge-research-platform-multi-llm-design.md) |
| 1 | **WS-OUTCOME-FACTORY** — honest opportunity population + outcome factory | PLANNED | DESIGN | Contaminated labels poison everything (F-022 class) |
| 2 | **WS-OI-PATH-ABSTAIN** — OI / positioning / liquidation as incremental path + abstain evidence | PLANNED | DESIGN | OHLCV direction exhausted; OI open/deferred (Program 7 class) |
| 3 | **WS-ENGINE-DEMOTION** — incremental-value audit; demote zero-Δ engines | PLANNED | DESIGN | Existence ≠ authority |
| 4 | **WS-NEW-INFO-SEARCH** — automated search over non-dead families | BLOCKED | DESIGN | Needs clean factory |
| 5 | **WS-SHADOW-LIVE** — shadow / small capital for survivors only | BLOCKED | VALIDATION | F-010 / F-048 |

### Do not fund first

- CRT geometry / threshold archaeology  
- Session as “new alpha” (F-017)  
- Zone knobs as edge (F-036 / F-041B)  
- Same M15 OHLCV directional toys (F-019 family)  
- Carry spot-dispersion / simple harvest reopen without a new structural thesis (F-033 / F-034)  
- Wire TradeNet / BitNet because they exist (F-005 / F-004)

---

## 5. Target architecture (intent — not current proven edge)

```text
Market data
  → verified features / events
  → neutral opportunity population
  → models add evidence (not free BUY/SELL votes)
  → structured opportunity record
  → decision policy from survivors only
  → risk → execution
  → honest outcome measurement
  → research feedback / demotion
```

Models contribute **different evidence** (structure, region, statistical, payoff, sequence).  
Authority is earned only by **measured incremental value** after costs and honest outcomes.

---

## 6. Work items

> Append rows; do not delete. Close with `CLOSED` / `KILLED` + reason.

| ID | Workstream | Title | Phase | Status | validation_flow_review | Notes |
|---|---|---|---|---|---|---|
| — | — | *(none opened yet)* | — | — | — | Next: open WS-OUTCOME-FACTORY design package |

**Work item template (copy when opening)**

```text
ID: WI-00N
Workstream: WS-...
Title:
Phase: DESIGN | IMPLEMENTATION | REVIEW | TESTING | VALIDATION
Status: PLANNED | IN_PROGRESS | BLOCKED | REVIEW | DONE | KILLED
validation_flow_review: UNTRUSTED_RAW | FLOW_REVIEWED | FLOW_MATCHES_INTENT | AUTHORITY_ELIGIBLE | N/A
Validation path consumed: (name entrypoint, gate flags, exit model, costs, labels)
Intent match evidence: (file:line / config keys / ACTIVE_VERSION)
Owner grant: yes/no
```

---

## 7. Conversation log

### CL-001 — 2026-07-14 — Trader-friend project narrative

- Project = **research/verification platform**, not a proven money printer.
- Bet = process quality vs manual indicator optimization.
- Risk = years of governance/features without economically valuable information.
- Action proposed: show trader the honest pitch; collect 5–10 objections; classify  
  `already-falsified | unresolved assumption | testable hypothesis`.

### CL-002 — 2026-07-14 — What to test first + goal

- Goal locked as §1.
- First scientific priority: outcome factory, then OI/path/abstain, parallel demotion.
- Explicit non-reopen of killed OHLCV directional families.

### CL-003 — 2026-07-14 — Program tracker created

- Owner asked to track this conversation in MD + JSON for  
  **design → implementation → review → testing → validation**.
- **Trust rule formalized:** do not trust backtest data until validation flow consumed is
  reviewed and matches intended implementation (§2 / `TP-BACKTEST-VALIDATION-GATE`).
- These two files are the continue-from surface for this program.

### CL-004 — 2026-07-14 — Unknowns, assumptions, tool-hallucination policy

- Owner asked to define unknowns in the plan, explain assumptions, and handle
  **hallucinated tool output**.
- Added §12 Unknowns, §13 Assumptions, §14 Tool-output hallucination policy
  (and matching JSON blocks). No new market claim; no code.

### CL-005 — 2026-07-14 — Strong testing plan (H1–H3 + real market outlets)

- Owner asked for a strong testing plan using real market outputs and frameworks
  (Playwright, Binance API, MT5, etc.) aligned to H1/H2/H3.
- Added DESIGN doc [`edge-research-platform-testing-plan.md`](edge-research-platform-testing-plan.md):
  layers L0–L8, pytest markers, run_manifest anti-hallucination, BN/MT5/Playwright packs,
  validation-path identity (VP-*), phases T0–T5. **Implementation not started.**
- Workstream: **WS-TEST-HARNESS** registered (PLANNED / DESIGN).

### CL-006 — 2026-07-14 — I/O map; unknowns parked

- Owner: save unknowns; discuss after full implementation plan; deliver **each topic input and output**
  per plan + codebase.
- Added [`edge-research-platform-io-map.md`](edge-research-platform-io-map.md).
- §12 unknowns marked PARKED (inventory only).

### CL-007 — 2026-07-14 — Synthetic 4h OHLCV intentional pack + trace

- Owner: 4h synthetic OHLCV (not random); trace through topics; intended vs produced.
- Generator: `scripts/research/erp_synth_4h_trace.py`
- Artifacts: `data/synthetic/erp_4h_m15/` (CSV, intended_spec, produced_compare, TRACE)
- Doc: [`erp-synthetic-4h-trace.md`](erp-synthetic-4h-trace.md)
- CRITICAL_COMPARE=PASS (TP_HIT, rr=2.0, tp_offset=4, sweep low, schema)

### CL-008 — 2026-07-14 — Engines topic designed (intended feature contract + real engines)

- Owner: design engines scores as per intended (not NOT_RUN / not invented).
- Added `engines_feature_contract` + `engines_intended` from story geometry.
- Produced via `crt_engine.compute`, `HeuristicGaussianEngine`, soft zone, `RREngine`.
- Scores: CRT 0.8227 · Gaussian 0.9432 · Zone 0.882419 · RR 0.6429 — **all match**.
- Fusion still NOT_RUN (isolation).

---

## 8. Open questions

1. Trader friend’s strongest 5–10 objections (pending).
2. Is OI history acquisition feasible for Program-7-class tests?
3. Is a non-spot instrument available if vol-info needs long-vol expression (F-040)?
4. Owner authorize **WS-OUTCOME-FACTORY** design package next?
5. Which concrete code paths + scripts constitute the “intended” outcome factory for WS-OUTCOME-FACTORY? (U-002)
6. Who performs independent review of validation-flow matches (owner / second model / checklist only)?
7. Nightly runner: Windows+MT5 vs Linux CI public-only? (testing plan §12)
8. Owner authorize **T0 scaffold** (markers + run_manifest + AH/VP fixtures) implement?

---

## 9. Next actions

| ID | Action | Status |
|---|---|---|
| NA-001 | Treat this MD+JSON pair as the program control surface | DONE |
| NA-002 | Draft WS-OUTCOME-FACTORY design (population, re-derive, trust checklist) — design only unless owner grants implement | PENDING |
| NA-003 | Ingest trader objections when available; classify each | PENDING |
| NA-004 | Keep §12–§14 current whenever a workstream design freezes | PENDING |
| NA-005 | Testing plan DESIGN published; await owner grant for Phase T0 implement | PENDING |
| NA-006 | I/O map published; unknowns parked until full implementation plan | DONE |
| NA-007 | Write **full implementation plan** (work packages citing I/O map rows) | DONE → see phased plan |
| NA-008 | Owner freeze P0 + grant Implement P1 (default next) | PENDING |

---

## 10. How to continue (for any session / model)

1. Read this file + the JSON twin (especially §12–§14).
2. Run ORIENT_RUNTIME (`ACTIVE_VERSION`) before any config/runtime claim.
3. Do not promote backtest numbers past `UNTRUSTED_RAW` without §2.
4. Treat LLM prose and un-audited tool summaries as **non-evidence** until §14 checks pass.
5. Append conversation log + update JSON `conversation_log` / `next_actions` same turn.
6. Open work items under §6; never skip DESIGN for economic claims.
7. Code changes still go through construction protocol + SESSION LOG (`assistant_project.md`).

---

## 11. Evidence anchors (thin)

Full text in [`docs/current-findings.md`](../current-findings.md):  
F-001, F-005, F-010, F-019, F-022, F-025, F-036, F-037, F-038, F-040, F-048.

---

## 12. Unknowns (plan-level)

> **PARKED FOR DISCUSSION:** Owner directive 2026-07-14 — **do not workshop unknowns now**;
> revisit **after the full implementation plan** is complete. List retained as inventory only.
>
> **Unknown** = something the plan needs but we do **not** currently know with evidence.
> Unknowns are not bugs; leaving them unlisted is. Status: `OPEN` | `NARROWED` | `RESOLVED` | `ACCEPTED_RISK`.

### 12.1 Economic / scientific unknowns

| ID | Unknown | Why it blocks or shapes the plan | Status | How it gets resolved |
|---|---|---|---|---|
| **U-001** | Does **any** durable edge exist in reachable data after costs and realistic execution? | Core outcome of the whole program; not assumed true | OPEN | Survive Stage-3 validation under §2, or multi-axis clean null |
| **U-002** | What is the **canonical honest opportunity + outcome** definition for this program? | WS-OUTCOME-FACTORY has no frozen population/label contract yet | OPEN | DESIGN freeze: seed events, join keys, `forward_walk` params, cost model |
| **U-003** | Are opportunity-stream labels (F-022 class) still contaminating any path we might reuse? | Determines how much of existing JSONL is unusable | OPEN | Census of label sources + re-derive sample vs stream |
| **U-004** | Can **OI / positioning / liquidations** be acquired at history depth and PIT quality sufficient for incremental tests? | WS-OI-PATH-ABSTAIN may be data-blocked (Program 7 prior) | OPEN | Data acquisition spike + coverage/PIT audit |
| **U-005** | If vol/path info is real but not spot-expressible (F-040 class), do we have **any instrument/payoff** that can express it? | Else vol-info may stay research-only forever | OPEN | Owner: options/perp/vol product scope or accept abstain-only consumer |
| **U-006** | Will **incremental** model value (Δ over OHLCV baseline) ever clear costs, or only Level-1 information? | Demotion vs promotion of engines | OPEN | WS-ENGINE-DEMOTION protocol after factory exists |
| **U-007** | Can the **live path** ever admit and measure trades as research intends (F-010 / F-048 class)? | Shadow/live step may be structurally blocked | OPEN | Structural review of DecisionEngine / planner / risk gate before capital |
| **U-008** | Is the binding constraint **missing information**, **wrong execution model**, or **efficient markets at our horizon**? | Changes whether to buy data vs redesign payoff vs stop | OPEN | Sequence of nulls + one new-info family; do not decide early |

### 12.2 Engineering / measurement unknowns

| ID | Unknown | Why it matters | Status | How it gets resolved |
|---|---|---|---|---|
| **U-009** | Exact **validation path map**: which scripts, flags (`BACKTEST_ENGINE_GATE`, fusion on/off), exit models, and cost models each workstream will consume | §2 trust requires naming the path; not yet frozen per workstream | OPEN | Per-WI “validation path consumed” field at DESIGN freeze |
| **U-010** | Parity between **research spine** and **live-equivalent** measurement for any claim we care about | F-037: CRT-only research ≠ full fusion live | OPEN | Explicit dual-lens policy or single declared lens per claim |
| **U-011** | Completeness of **feature/formula identity** for any feature used in new tests (PIT, registry, GD residual) | Wrong inputs → false edges or false nulls | OPEN | Only consume certified/promoted or explicitly scoped experimental features |
| **U-012** | Multiplicity / repeated-experiment debt when many hypotheses share the same opportunity set | False discovery risk | OPEN | Pre-registration + family-wise controls in DESIGN |
| **U-013** | Owner review bandwidth and **who signs** `FLOW_MATCHES_INTENT` | Trust tokens without an owner are theater | OPEN | Owner names reviewer role |

### 12.3 Process / external unknowns

| ID | Unknown | Why it matters | Status | How it gets resolved |
|---|---|---|---|---|
| **U-014** | Trader-friend objections (content unknown) | May reorder priority stack or kill assumptions | OPEN | Collect verbatim; classify |
| **U-015** | Time/capital budget for infrastructure vs discovery | Failure mode = perfect lab, no alpha | OPEN | Owner budget rule (e.g. max design weeks before new-info RUN) |
| **U-016** | Whether LLM agents will **accelerate falsification** more than they inject false claims | §14 risk | OPEN | Hallucination policy + mechanical floors; measure correction rate |

### 12.4 Explicitly *not* unknown (do not re-open as mystery)

These are **known nulls / constraints under their stated scopes** (see findings). Reopening requires new ontology/data/domain, not hope:

- Global M15 OHLCV directional toys failing M4-style gates (F-019 family, scoped)
- Session-as-improvable lever under tested conditions (F-017)
- Zone knob ΔG001 ≡ 0 under tested conditions (F-036)
- Carry signal / simple harvest as tested (F-033 / F-034)
- TradeNet unwired / BitNet inert on active patch (F-005 / F-004)

---

## 13. Assumptions (plan-level)

> **Assumption** = a belief the plan relies on that is **not fully proven**.
> Each must be: stated, classed, and either tested, replaced, or accepted as risk.
> Class: `STRUCTURAL` (how the lab works) · `ECONOMIC` (markets) · `OPERATIONAL` (how we work) · `DATA`.

| ID | Assumption | Class | Confidence | If false, what breaks | Disposition |
|---|---|---|---|---|---|
| **A-001** | A rigorous research process **raises** P(find or cleanly reject edge) vs unaudited backtest-fitting | ECONOMIC / OPERATIONAL | Likely | Program ROI thesis fails; still may retain hygiene value | **Working thesis** — not proven; measure by time-to-kill bad ideas |
| **A-002** | Honest opportunity + outcome factory is **buildable** from existing stack (`forward_walk`, qualification, loaders) without a full rewrite | STRUCTURAL | Likely | WS-1 balloons; plan must shrink scope | Test in DESIGN spike; stop if scope explodes |
| **A-003** | Contaminated / stream labels are a **first-order** risk for any learning or engine retrain | STRUCTURAL | Certain *(mechanism documented; extent of live reuse still U-003)* | Wasted if we only ever use clean re-derive and never touch stream labels | Keep factory first |
| **A-004** | **New information families** (OI/positioning/etc.) are higher EV than more OHLCV directional geometry | ECONOMIC | Likely *(prior from F-019…F-040 arc)* | Priority stack wrong; still need factory | Reorder only with evidence or strong trader objection |
| **A-005** | Path / abstain / P(hit TP before SL) targets are more decision-relevant than raw up/down after prior nulls | ECONOMIC | Possible–Likely | Wrong targets; change prediction objects | Freeze targets in WS design |
| **A-006** | Models should earn **incremental** authority only; presence in code grants none | STRUCTURAL | Certain *(repo doctrine §6.5)* | Reverts to “sophisticated system = edge” fallacy | Enforce demotion workstream |
| **A-007** | Research default CRT-only spine (F-037 class) is an **intended isolation lens**, not automatically the live decision lens | STRUCTURAL | Certain for mechanism; intent user-classified historically | Claims mislabeled as “full system” | Every claim names lens |
| **A-008** | 12 bps (or declared cost) is an acceptable **research cost prior** for crypto majors qualification | DATA / ECONOMIC | Possible | Cost-dominated nulls or false promotes | Sensitivity only after Stage-1 info; not first knob |
| **A-009** | Feature/formula governance reduces false results enough to justify sequencing integrity before discovery | OPERATIONAL | Likely | Over-invest in lab; under-invest in info | Cap integrity work; don’t block all discovery forever |
| **A-010** | Owner will not risk meaningful capital until shadow + flow review | OPERATIONAL | Likely *(stated intent)* | Live loss / unmeasured path | Hard gate on WS-SHADOW-LIVE |
| **A-011** | LLM/tool outputs are **advisory** and can be wrong even when fluent | OPERATIONAL | Certain | False findings re-propagate (E-001 class) | §14 policy |
| **A-012** | “Kill failed hypotheses and keep infrastructure” is preferable to forcing models into production | ECONOMIC | Likely | Capital and reputation risk | Explicit non-goal: force CRT profitable |

**Assumption hygiene rules**

1. New workstream DESIGN must list which A-ids it depends on.
2. Do not silently upgrade `Possible` → `Certain` without artifact evidence.
3. If an assumption is load-bearing and untested, the work item stays DESIGN or ACCEPTED_RISK with owner sign-off.

---

## 14. Tool-output hallucination policy

### 14.1 What “hallucinated tool output” means here

Three failure modes (all in scope):

| Mode | Definition | Example |
|---|---|---|
| **H1 — LLM invents a tool result** | Model states numbers, paths, or “pytest green” **without** a real tool return in-session | “BNBUSDT PF=1.4” with no run |
| **H2 — LLM misreads a real tool result** | Tool returned truth; model **wrongly summarizes** or swaps instruments/flags | Gate-OFF ledger described as fusion gate-ON |
| **H3 — Tool/script output is real but mis-specified** | Command ran; **wrong flow / labels / config** so the artifact is not the intended experiment | Valid JSON from contaminated opportunity labels (F-022 class) |

§2 primarily catches **H3**. §14 catches **H1–H2** and forces H3 into explicit review.

### 14.2 Default trust for agent/tool claims

| Source | Default | May become evidence only if |
|---|---|---|
| LLM chat prose | **NON_EVIDENCE** | N/A (never sole basis for findings) |
| LLM “remembered” past run | **NON_EVIDENCE** | Re-run or open on-disk artifact + hash |
| Shell / pytest / script stdout in-session | **UNTRUSTED_RAW** | Path reviewed (§2) + summary checked against artifact |
| On-disk JSON/JSONL under `results/` | **UNTRUSTED_RAW** | Same + provenance (command, config, version) recorded |
| Finding already in `docs/current-findings.md` | **RESEARCH_RECORD** | Still scope-bound; not production authority |
| `ACTIVE_VERSION` + loaded config | **RUNTIME_TIER0** | Fail-fast if mismatch |

### 14.3 Mandatory anti-hallucination checks (before using a number)

1. **Provenance:** command (or script entrypoint), cwd, key flags, `ACTIVE_VERSION`, instrument, date.
2. **Artifact:** path to file on disk when claim matters beyond chat; prefer hash or byte size.
3. **Flow name:** which validation lens (CRT-only vs fusion; exit model; cost; label source).
4. **Intent match:** does that flow match the **intended** implementation for this work item? (§2)
5. **No silent fill:** if tool failed, timed out, or returned empty — say so; **do not invent** success.
6. **UNKNOWN tag:** if unsure, write `UNKNOWN:` / leave status OPEN — never invent a PF/E/path.
7. **Correction rule:** if a false claim was written into MD/JSON/findings, fix the **source** same turn (E-001 / §6.2).

### 14.4 Phrases that are automatic red flags

Treat as **H1-suspect** until proven:

- “Tests all passed” / “backtest shows edge” without command output citation
- “Live would do X” without live-path evidence (F-010 / F-048)
- “All engines agree” without per-engine scores on a named opportunity id
- Rounded “nice” metrics with no artifact path
- Cross-session memory of ledgers without re-read of files

### 14.5 Allowed use of tools under this program

| Allowed | Not allowed |
|---|---|
| Run scripts to **create** artifacts | Cite chat-only metrics as validation |
| Quote tool output **with path** | Upgrade `UNTRUSTED_RAW` without review |
| Mark `UNKNOWN` / fail-closed | Invent missing JSON fields or trade counts |
| Compare two on-disk artifacts | Treat LLM rewrite of JSON as the artifact |

### 14.6 Relation to program phases

```text
Tool run
  → artifact (UNTRUSTED_RAW)
  → REVIEW: did we run the intended flow? (H3 + §2)
  → REVIEW: did the agent report the artifact correctly? (H1/H2)
  → only then: research evidence (FLOW_MATCHES_INTENT)
  → never automatic: production authority
```

---

## 15. Quick reference — unknowns vs assumptions vs hallucinations

| Kind | Question it answers | Failure if ignored |
|---|---|---|
| **Unknown** | What do we not know yet? | Plan pretends certainty |
| **Assumption** | What are we relying on without full proof? | Silent dependency; wrong priority |
| **Hallucinated / mis-specified tool output** | Is this number even real and on the right path? | False edge or false kill enters the ledger |

**Operator slogan:** *Unknowns listed · Assumptions labeled · Tool numbers untrusted until flow + quote check.*

---

## 16. Utilizing models for tool-output hypotheses

> **Purpose:** Models help *propose and stress-test* claims about tool outputs.
> They do **not** create market edge and do **not** upgrade `UNTRUSTED_RAW` by fluency.
> Full authority still: artifact → validation-flow review → Authority Ladder.

### 16.1 Two different “models” (do not mix)

| Kind | Examples in this repo | Job re: tool output |
|---|---|---|
| **A. Market engines / research models** | CRT scorer, Gaussian, Zone, RR, BitNet, TradeNet, interpreters | Emit **evidence scores** on an opportunity; subject to incremental-value tests |
| **B. LLM / agent models** | Multi-LLM pipeline, agent tools, chat assistants | Propose **hypotheses about what a tool run means**, draft tests, spot H1–H3 failures |

Both feed **tool-output hypotheses** — statements of the form:

```text
H_tool: "If we run <entrypoint> with <args/lens>, we expect <observable artifact fields>
         because <mechanism>. Falsify if <counter-evidence>."
```

That is **not** the same as:

```text
H_market: "This structure predicts positive expectancy after costs."
```

### 16.2 What a tool-output hypothesis is allowed to claim

| Allowed claim class | Example | Becomes evidence only after |
|---|---|---|
| **Path identity** | “Gate-OFF backtest uses CRT-only entries” | Manifest + code/env check (H3) |
| **Artifact shape** | “forward_walk returns TP_HIT on synth pack” | Re-run + intended_spec compare |
| **Engine contract** | “With feature contract X, CRT score ≈ 0.8227” | Real `crt_compute` vs closed form |
| **Delta / ablation** | “Turning zone weight to 0 does not change entries” | Byte-identical ledgers or scored Δ |
| **Failure mode** | “Empty stdout must not be summarized as SUCCESS” | AH-* tests |

| Forbidden upgrade | Why |
|---|---|
| Chat: “PF=1.4 so edge exists” | H1 + economic claim without flow review |
| Engine score alone → production authority | Existence ≠ Authority Ladder |
| LLM rewrite of JSON as the artifact | Replaces tool truth |

### 16.3 How to use **LLM/agent models** (B)

**Role:** hypothesis *generator*, *adversary*, and *checklist writer* — never sole validator.

| Step | LLM does | System / human does |
|---|---|---|
| 1 Propose | Draft `H_tool` from code/docs/logs | Store as claim with status `PROPOSED` |
| 2 Bind | Name entrypoint, flags, ACTIVE_VERSION, instrument | Reject unbound claims |
| 3 Predict | Expected artifact fields (outcome, scores, keys) | Write `intended_*` before run when possible |
| 4 Attack | List H1/H2/H3 ways the claim could be fake | Prefer worst-case first |
| 5 Design test | Suggest pytest / synth pack / dual-lens | Owner grants implement |
| 6 Interpret | Explain *after* artifact exists | Quote-check vs `run_manifest` (H2) |
| 7 Demote | Suggest kill/reopen conditions | Record in findings only if gates pass |

**Prompt contract for agents (copy into handoffs):**

```text
You may only emit H_tool claims.
Each claim must include: entrypoint, args/env, expected artifact path fields,
falsifier, H1/H2/H3 risk.
You must not state PF/E/WR as fact without an on-disk artifact path.
If no tool ran this turn, every numeric market result is NON_EVIDENCE.
```

### 16.4 How to use **market engines / models** (A)

**Role:** produce **structured evidence** on a fixed opportunity population — inputs to *market* hypotheses, and also to *tool* hypotheses (“did the engine path fire?”).

| Pattern | How |
|---|---|
| **Same opportunity, four evidence channels** | Synth pack pattern: design feature contract → CRT/Gaussian/Zone/RR scores → compare intended vs produced |
| **Incremental value H_tool** | “Removing engine E does not change outcome distribution under lens L” → ablation artifact |
| **Abstain evidence** | Model score as *filter*, not as direction vote; test Δ after costs |
| **Shadow only** | BitNet/TradeNet: log scores; no fusion authority until ΔG001 measured |
| **Never** | Treat engine score as fill/PnL proof |

### 16.5 Combined loop (recommended)

```text
          ┌─────────────────────────────┐
          │ LLM proposes H_tool / H_mkt │
          │ (PROPOSED, NON_EVIDENCE)    │
          └─────────────┬───────────────┘
                        ▼
          ┌─────────────────────────────┐
          │ Bind path + intended fields │
          │ (intended_spec / contract)  │
          └─────────────┬───────────────┘
                        ▼
          ┌─────────────────────────────┐
          │ Real tool run               │
          │ engines / backtest / MT5…   │
          │ → artifact + run_manifest   │
          └─────────────┬───────────────┘
                        ▼
          ┌─────────────────────────────┐
          │ Compare intended vs produced│
          │ (AH/VP/synth pack style)    │
          └─────────────┬───────────────┘
                        ▼
              match? ──no──► H_tool FAIL / fix path
                │
               yes
                ▼
          FLOW_REVIEWED → (optional) market H_mkt under M4
                ▼
          only survivors: decision authority
```

**Worked example already in-repo:**  
`scripts/research/erp_synth_4h_trace.py` — OHLCV design → engines feature contract → intended scores → real engines → `produced_compare.json`. That is the template for “models help tool-output hypotheses” without H1 invention.

### 16.6 Which model for which tool-output job

| Job | Prefer | Avoid |
|---|---|---|
| “Did validation path match intent?” | Deterministic VP/manifest + code | LLM alone |
| “What might be wrong with this log?” | LLM adversary (propose) + re-run | Accepting LLM diagnosis as truth |
| “What score should CRT emit on this contract?” | Closed-form + `crt_compute` | Hand-waved “high CRT” |
| “Does gaussian add Δ?” | Ablation on factory population | Single pretty chart |
| “New market idea?” | LLM/interpreter for *search*; M4 for *verdict* | Promoting chat ideas live |
| “UI showed SUCCESS” | Playwright + artifact exists | Trusting UI copy |

### 16.7 Authority boundary (hard)

```text
Model output (A or B)
  → may create H_tool / H_mkt (PROPOSED)
  → may never set FLOW_MATCHES_INTENT alone
  → may never set production / capital authority
  → may only assist after artifact+review into RESEARCH_RECORD or AUTHORITY_ELIGIBLE
```

### 16.8 Practical utilization checklist (operator)

1. Decide claim type: **tool-path** vs **market-edge** (never one label for both).  
2. If tool-path: write intended fields **before** or immediately with the run.  
3. Run real tool; store path + hash.  
4. Use LLM only to *diff* narrative vs artifact (H2 check).  
5. Use engines only as *named evidence channels* on a frozen population.  
6. Promote nothing that skipped §2 / §14.  

### CL-009 — 2026-07-14 — Model use for tool-output hypotheses

- Owner asked how to utilize models that help tool-output hypotheses.
- Added §16: split market engines (A) vs LLM agents (B); H_tool contract;
  combined loop; authority boundary; synth pack as worked example.

### CL-010 — 2026-07-14 — Incorporate research loop + multi-LLM RCP design; ambiguities

- Owner provided trader-facing research steps 1–13 + multi-LLM control plane design;
  asked to incorporate into current design and discuss ambiguity.
- Added [`edge-research-platform-multi-llm-design.md`](edge-research-platform-multi-llm-design.md):
  spine mapping, four artifact kinds, 8-step loop, WS-MLLM-RCP (thin), AMB-01…AMB-12.
- **Key ambiguity:** proposed roles ≠ existing `multi_llm/` role cards → dual-lane recommended until owner freezes AMB-01.
- Pitch accuracy footnotes: F-037 lens, F-048 RR, F-004/F-005 inert models.

### CL-011 — 2026-07-14 — Decision board MD + story authority reverse-engineer

- Owner: keep decisions tracked/shout-out; single easy MD; reverse-engineer scripted story vs WHAT/WHO/HOW.
- Added [`erp-decision-board-and-story-authority.md`](erp-decision-board-and-story-authority.md)
  (D-01…D-23 + Part B reverse-engineer).
- **Finding D-23:** changing story prices/phases **requires CODE** in `erp_synth_4h_trace.py` today;
  NOT manageable by WHAT/WHO/HOW alone. HOW still owns live knobs; WHAT owns formulas;
  re-run pack after any story edit.

### CL-012 — 2026-07-14 — Phased design plan P0–P7

- Owner: with data and design, produce design plan in phases.
- Added [`edge-research-platform-phased-plan.md`](edge-research-platform-phased-plan.md):
  P0 freeze → P1 harness/golden → P2 factory → P3 demotion → P4 OI/path → P5 shadow →
  P6 MLLM cycles → P7 capital micro. Parallel rules, exits, grant sequence.
- NA-007 closed; next = owner P0 freeze + Implement P1.

### CL-013 — 2026-07-14 — Before/after full design description

- Owner: describe before and after entire design implemented.
- Added [`edge-research-platform-before-after.md`](edge-research-platform-before-after.md):
  identity, trust, spine, synth, multi-LLM, phases, artifacts, non-goals, checklist.

### CL-014 — 2026-07-14 — Parallel path toward earned wealth promise

- Owner: parallel design still not a false promise of wealth; design must **move toward** promise.
- Added [`edge-research-platform-promise-ladder.md`](edge-research-platform-promise-ladder.md):
  Track I integrity ∥ Track II path-to-promise; PL-0…PL-5; KPIs; PR-01…PR-05.
- D-25/D-26: no false promise + forced search after factory; lab-forever without P4 pressure ≠ success.
- Phased plan north star + parallel rules updated.

### CL-015 — 2026-07-14 — Multi-LLM HOW design + Research Lane initiated

- Owner: design HOW for plan; initiate multi-LLM architecture if required.
- **Required thin:** dual-lane Research Lane initiated under `multi_llm/research_lane/`.
- HOW doc: [`edge-research-platform-mllm-how.md`](edge-research-platform-mllm-how.md).
- Artifacts: package_schema.json, research_cycle_ledger.jsonl (RC-000), roles, templates, scorecard.
- Lane I (`MULTI_LLM_PROTOCOL`) **not** rewritten. Promise rung still PL-0.
- Next: owner phase grant Implement P1; optional RC-001 H_tool after P1.


========================================================================
# SOURCE: docs/research-readiness/erp-synthetic-4h-trace.md
# ROLE: synth_trace
========================================================================

# Synthetic 4h OHLCV — Transformation Trace (Intended vs Produced)

> Generated by `scripts/research/erp_synth_4h_trace.py`.  
> Instrument `SYNTHUSDT` · M15 · event window **4.0 hours** (16 bars)  
> Warmup 32 bars (indicator window only).  
> Critical compare: **PASS**

## Design principle

This series is **not random**. Every bar phase is scripted so that:
1. A liquidity **sweep** prints a known low.
2. **Displacement / expansion** create upside structure.
3. A **retest** holds above the design SL.
4. A design-injected LONG signal has a path that **hits TP before SL** under `forward_walk(intrabar_fixed)`.

That lets us compare **intended_spec.json** vs **produced_compare.json** without market noise.

## Files

| File | Role |
|---|---|
| `SYNTH_4H_M15.csv` | OHLCV input artifact |
| `intended_spec.json` | Ground-truth design |
| `produced_compare.json` | What code actually produced |
| `TRACE_NARRATIVE.md` | This narration |

## Bar phases (event window only)

| Abs idx | Time | Phase | Note |
|---|---|---|---|
| 32 | 2024-06-01 08:00:00 | `event_range` | range hold pre-sweep |
| 33 | 2024-06-01 08:15:00 | `event_range` | range hold |
| 34 | 2024-06-01 08:30:00 | `event_range` | range hold |
| 35 | 2024-06-01 08:45:00 | `sweep` | liquidity sweep below range, close reclaimed |
| 36 | 2024-06-01 09:00:00 | `displacement` | impulsive bullish displacement bar 1 |
| 37 | 2024-06-01 09:15:00 | `displacement` | impulsive bullish displacement bar 2 |
| 38 | 2024-06-01 09:30:00 | `expansion` | expansion print toward design TP zone |
| 39 | 2024-06-01 09:45:00 | `expansion` | hold near highs |
| 40 | 2024-06-01 10:00:00 | `retest` | retest pullback above design SL=101 |
| 41 | 2024-06-01 10:15:00 | `entry` | reclaim / designed LONG entry bar |
| 42 | 2024-06-01 10:30:00 | `path` | adverse excursion short of SL |
| 43 | 2024-06-01 10:45:00 | `path` | recovery |
| 44 | 2024-06-01 11:00:00 | `path` | grind higher |
| 45 | 2024-06-01 11:15:00 | `path_tp` | designed TP touch high>=104 |
| 46 | 2024-06-01 11:30:00 | `post` | post-outcome residual bar |
| 47 | 2024-06-01 11:45:00 | `post` | post-outcome residual bar |

## Topic-by-topic transformation

### 1. Market data collect

| | |
|---|---|
| **Transform** | Generator constants → CSV rows |
| **Intended out** | n=48 rows written |
| **Produced out** | `row_count ok=True` |

### 2. Schema validation

| | |
|---|---|
| **Transform** | CSV frame → `validate_ohlcv_frame` |
| **Intended out** | PASS (six columns, monotonic ts, OHLC consistency) |
| **Produced out** | `schema ok=True` |

### 3. Features (candle math sample)

| | |
|---|---|
| **Transform** | Entry bar OHLC → body/range |
| **Intended out** | body_ratio in [0,1] from designed open/close/range |
| **Produced out** | `{"body": 0.3500000000000085, "body_ratio_manual_body_over_range": 0.5000000000000101, "body_ratio_match": true, "body_ratio_module": 0.5000000000000101, "entry_index": 41, "range": 0.7000000000000028}` |

### 4. Events / opportunity seed

| | |
|---|---|
| **Transform** | Scripted phases → design Signal (injected; CRT not required) |
| **Intended out** | LONG entry_index=41 entry=102.0 |
| **Produced out** | `{"signal": {"atr": 1.0, "direction": "long", "entry": 102.0, "entry_index": 41, "instrument": "SYNTHUSDT", "sl_atr_mult": 1.0, "tp_atr_mult": 2.0}}` |

### 5. Engines evidence

| | |
|---|---|
| **Transform** | Design feature contract → CRT/Gaussian/Zone soft/RR engines |
| **Intended out** | {"crt": 0.8227, "gaussian": 0.9432, "rr": 0.6429, "zone_gate": 0.882419} |
| **Produced out** | `{"match": {"crt": true, "gaussian": true, "rr": true, "zone_gate": true}, "scores": {"crt": 0.8227, "gaussian": 0.9432, "rr": 0.6429, "zone_gate": 0.882419}, "status": "RUN"}` |

### 6. Fusion / decision

| | |
|---|---|
| **Transform** | Scores → execute/reject |
| **Intended out** | NOT IN THIS PACK |
| **Produced out** | `NOT_RUN` |

### 7. Plan + risk levels

| | |
|---|---|
| **Transform** | ATR mults → absolute SL/TP |
| **Intended out** | SL=101.0 TP=104.0 |
| **Produced out** | `{"sl_price": 101.0, "tp_price": 104.0}` |

### 8. Execution (MT5)

| | |
|---|---|
| **Transform** | Order intent → ticket |
| **Intended out** | NOT IN THIS PACK |
| **Produced out** | `NOT_RUN` |

### 9. Outcome factory (`forward_walk`)

| | |
|---|---|
| **Transform** | Signal + future bars → Outcome |
| **Intended out** | TP_HIT rr≥1.999999 |
| **Produced out** | `{"duration_candles": 4, "mae": -0.8, "mfe": 2.25, "outcome": "TP_HIT", "reached_1r": true, "rr_achieved": 2.0, "time_to_failure": null, "time_to_tp": 4}` |

### 10. Test harness compare

| | |
|---|---|
| **Transform** | intended_spec vs produced_compare |
| **Intended out** | all_critical_pass=true |
| **Produced out** | `all_critical_pass=True` |

## Critical comparison table

| Check | Intended | Produced | Match |
|---|---|---|---|
| Schema | PASS | True | True |
| Row count | 48 | 48 | True |
| Sweep low | 98.5 | 98.5 | True |
| Outcome | TP_HIT | TP_HIT | True |
| TP offset (bars after entry) | 4 | 4 | True |
| RR ≥ 2 | ≥2 | 2.0 | True |
| SL not first | true | True | True |
| Engines all match | true | True | True |
| CRT score | 0.8227 | 0.8227 | True |
| Gaussian score | 0.9432 | 0.9432 | True |
| Zone soft score | 0.882419 | 0.882419 | True |
| RR polarity | 0.6429 | 0.6429 | True |

**Overall critical: PASS**

## Engines design (topic 5)

Features at entry are **not random scores** — they are a design contract from the story:

- `sweep_detected=True` (sweep bar exists); `double_sweep=False`
- `body_ratio` from entry OHLC via `candle_math`
- `disp_strength = DISP_CLOSE_2 - SWEEP_LOW` (thrust magnitude)
- `retest_depth=0.5` (CRT retest component peak by design)
- EMA/momentum seeds for bullish heuristic gaussian (fixed mu/sigma for pack)
- Soft zone distance/freshness/strength near retest structure

Produced via real callables: `crt_engine.compute`, `HeuristicGaussianEngine`,
`_compute_soft_zone_score`, `RREngine.compute` — intended closed-form must match.

## Narration of the 4-hour path

1. **Warmup (prior 8h):** price oscillates in a ±0.30 band around 100 so later ATR-style
   windows see a calm regime (features may still use longer windows elsewhere).
2. **Event +0:00–0:45:** three range bars — market still balanced.
3. **Sweep:** one bar prints low **98.5** then closes back up — designed liquidity grab.
4. **Displacement:** two strong up bars into the 102–103 area.
5. **Expansion:** highs probe the **104** region (design TP neighborhood).
6. **Retest:** pullback low **101.4** stays **above** design SL **101.0**.
7. **Entry:** designed long at **102.0** (index 41).
8. **Path:** one mild adverse bar (low 101.20) that **must not** hit SL 101.00,
   then grind higher until a bar high **≥ 104.00** → **TP_HIT** under intrabar_fixed.
9. **Post bars:** residual after outcome (should not change forward_walk result).

## What this does *not* claim

- Not a CRT engine detection proof (seed is design-injected).
- Not fusion/live/MT5/Binance proof.
- Not economic edge — only that the **measurement path** matches geometry we built.
- Outputs remain research fixtures; trust token still starts `UNTRUSTED_RAW` until flow review.

## Reproduce

```bash
PYTHONPATH=src python scripts/research/erp_synth_4h_trace.py
```


========================================================================
# SOURCE: multi_llm/research_lane/README.md
# ROLE: research_lane_ops
========================================================================

# Research Lane (Multi-LLM HOW) — Initiated

> **Lane R** of the dual-lane architecture.  
> **Lane I** (implementation) stays at [`../MULTI_LLM_PROTOCOL.md`](../MULTI_LLM_PROTOCOL.md).  
> **HOW design:** [`docs/research-readiness/edge-research-platform-mllm-how.md`](../../docs/research-readiness/edge-research-platform-mllm-how.md)

## Why this exists

Stop multi-LLM **echo chamber**. Every research output is one of:

| kind | meaning |
|---|---|
| `PROPOSAL` | Hypothesis or experiment sketch |
| `CRITIQUE` | Attack on design / evidence |
| `EXECUTION_EVIDENCE` | Real tool run + paths |
| `DECISION` | Freeze / retire / next grant / PL rung |

**No voting. No free-form truth. No capital without You.**

## Files

| File | Role |
|---|---|
| `package_schema.json` | HOW contract for packages |
| `research_cycle_ledger.jsonl` | Append-only ledger |
| `RESEARCH_ROLES.md` | Role → model map |
| `scorecard.md` | Marginal value metrics |
| `templates/` | Copy-paste package shells |
| `cycles/` | Optional per-cycle notes |

## Quick start (one cycle)

1. Open a template under `templates/`.  
2. Fill fields; keep `promise_rung_max_claim` ≤ current PL (now **PL-0**).  
3. Append one JSON object line to `research_cycle_ledger.jsonl` (Claude can do this when recording).  
4. Hand package text to the next role (You bridge).  
5. Claude only executes after a **DECISION** freeze for RUN work.

## Current state

| Item | Value |
|---|---|
| Initiated | **yes** (RC-000) |
| Current promise rung | **PL-0** |
| Next recommended grant | P0 freeze + **Implement P1** |
| Lane I rewrite | **no** |

## Authority

Reality > tests/findings > repo > You (what to do) > LLMs.  
Claude writes code. Packages do not promote configs.


========================================================================
# SOURCE: multi_llm/research_lane/RESEARCH_ROLES.md
# ROLE: research_roles
========================================================================

# Research Lane — Role HOW Map

> Dual-lane default (AMB-01 B). Does **not** replace `multi_llm/roles/ROLE_*.md` for Implementation Lane.

| Role | Default model | Lane | Writes | Never |
|---|---|---|---|---|
| **Principal** | You | Both | DECISION (capital, phase grants) | Delegate capital to LLM |
| **Architect** | ChatGPT | Research | PROPOSAL, DECISION (freeze/branch drafts) | Sole-sign PL-5; write prod code |
| **Hypothesis diversity** | Grok | Research | PROPOSAL (counters, new families) | Approve own H; execute |
| **Technical critic** | DeepSeek | Research | CRITIQUE | Execute unfrozen RUN |
| **Executor** | Claude | Both | EXECUTION_EVIDENCE; code/tests | Raise PL alone; invent metrics |
| **Impl planner** | DeepSeek | Implementation | plan handoffs | Own ERP DECISION |
| **Impl navigator** | Gemini | Implementation | gaps/next | Own ERP DECISION |
| **Impl interpreter** | ChatGPT | Implementation | explain/expand | Execute code |

## Handoff rule

```text
Same problem → different roles → different package kinds
Never: four models answer same prompt and vote
```

## Speech rule

| Role output | Max wealth language |
|---|---|
| Any PROPOSAL/CRITIQUE | PL-0 wording unless package binds higher *after* DECISION |
| DECISION upgrading PL | Must cite EXECUTION_EVIDENCE package_ids |


========================================================================
# SOURCE: multi_llm/research_lane/package_schema.json
# ROLE: package_schema
========================================================================

{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "tradelatest.multi_llm.research_lane.package.v1",
  "title": "ResearchLanePackage",
  "type": "object",
  "required": [
    "package_id",
    "kind",
    "cycle_id",
    "created_at",
    "author_role",
    "summary",
    "status"
  ],
  "properties": {
    "schema_version": { "type": "string", "const": "1.0" },
    "package_id": { "type": "string", "minLength": 3 },
    "kind": {
      "type": "string",
      "enum": ["PROPOSAL", "CRITIQUE", "EXECUTION_EVIDENCE", "DECISION"]
    },
    "cycle_id": { "type": "string", "pattern": "^RC-[0-9]{3,}$" },
    "created_at": { "type": "string" },
    "author_role": {
      "type": "string",
      "enum": [
        "principal",
        "architect",
        "hypothesis_diversity",
        "technical_critic",
        "executor",
        "system"
      ]
    },
    "author_model": {
      "type": "string",
      "description": "e.g. grok, chatgpt, deepseek, claude, human"
    },
    "claim_type": {
      "type": "string",
      "enum": ["H_tool", "H_market", "process", "none"]
    },
    "summary": { "type": "string", "minLength": 1 },
    "binds": {
      "type": "object",
      "properties": {
        "entrypoint": { "type": "string" },
        "lens": { "type": "string" },
        "active_version": { "type": "string" },
        "instruments": { "type": "array", "items": { "type": "string" } },
        "phase": { "type": "string" },
        "promise_rung_max_claim": {
          "type": "string",
          "enum": ["PL-0", "PL-1", "PL-2", "PL-3", "PL-4", "PL-5", "PL-5+"]
        }
      }
    },
    "falsifier": { "type": "string" },
    "h1_h2_h3_risks": {
      "type": "array",
      "items": { "type": "string" }
    },
    "artifact_paths": {
      "type": "array",
      "items": { "type": "string" }
    },
    "related_package_ids": {
      "type": "array",
      "items": { "type": "string" }
    },
    "status": {
      "type": "string",
      "enum": ["PROPOSED", "ACCEPTED", "REJECTED", "SUPERSEDED", "BLOCKED"]
    },
    "notes": { "type": "string" }
  },
  "additionalProperties": true
}
