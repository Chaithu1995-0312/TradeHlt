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
| **D-16** | Do **not** fund first: CRT knob archaeology, session-as-alpha, zone knobs-as-edge, same OHLCV directional toys, carry reopen without new thesis, wire TradeNet/BitNet “because built.” | LOCKED · **the F-019/F-036 anchors are `PROVISIONAL pending E4`** ([revalidation gate](findings-revalidation-gate-e4-preregistration.md), WI-001, frozen 2026-07-16) |
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
| `erp-design-essay-reconciliation.md` | Reconciles a pasted multi-model design essay vs repo (already-built / locked / parked / genuinely-new) |

---

*End of document. Decisions above are the tracked shout-out list; reverse-engineering answer is Part B.*
