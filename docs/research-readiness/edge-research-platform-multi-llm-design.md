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
