# Live Chart View + State Monitoring — elevated architecture

| Field | Value |
|---|---|
| **Date** | 2026-09-16 (Asia/Kolkata) |
| **Status** | Design / analysis only — no promotion, no live money, no L5 vocabulary change |
| **Lane** | Architecture elevation on existing schema + UI kits + paper rail |
| **ACTIVE_VERSION** | `v2_htfcrt_2026_08` |
| **Stance** | Jarvis: **run before walk** — small runs already taught the gaps; this doc walks them into one spine |

---

## 0. One-line thesis

The codebase is already **schema-designed**. Live trading does not need a new stack.
It needs a **join contract** between three surfaces that today look related but must stay distinct:

1. **Schema / identity** — what a state, cost, run, and measurement *are*
2. **Trade Chart view** — CRTEngine occupancy painted on candles (desk eyes)
3. **State monitoring** — live-rail / Ultron / planner audits (ops eyes)

Collapsing (2) and (3) into one “live chart” is how F-069 / F-073 get papered over.
Joining them on **`run_id` + `(instrument, bar_ts)`** is the walk.

---

## 1. What we already ran (evidence, not aspiration)

| Run | Artifact | What it proved |
|---|---|---|
| Paper live rail | `results/live_rail_paper_20260916_212321/` + `CODEPATH_TRACE.md` | F-073 repair path is callable in paper; path is Orchestrator → feeder → HookedLiveEngine → EngineRunner; **does not** call `CRTEngine.process_candle` |
| Live monitor kit | `ui_kits/live_monitor/` (`index.html` + `state.json`) | Ops snapshot of paper audits works as a thin HTML consumer of control-plane URLs |
| Playwright closure | `…/playwright_validate/` (6/6) | Control Plane / flows / node context links are real |
| Trade Chart desk | `ui_kits/crt_dashboard/page4_trade_chart.jsx` | Engine vs Resolver are **two ribbons** (F-069); candle color = engine `CRT_HEX`, not OHLC direction |
| Trader grading | `…/trader_read/PLAYBOOK.md` | Costume S→D→E(≥8)→R is a watch filter; A+ costume ≠ edge; MFE/MAE≥2 |
| Cost audit | `results/run_20260916_101942_XAUUSD/cost_audit/` | Ledger G1+G2 ≠ SEM-015 ≠ Ultron dormant tax; identities must not be mixed |
| Hourly watch routine | `xauusd-trade-chart-a-setup-watch` | Standing “desk ping” intent exists; never run yet |

These runs are the **denominator** for the walk. Do not redesign them away.

---

## 2. Locked decisions (inherit — do not reopen)

From existing plans (cite, do not re-argue):

| Source | Lock |
|---|---|
| `live-rail-repair-path.md` | TickDB/paper first; **repair** F-073 (do not retire hook); CRT EXECUTION must **not** skip EngineRunner |
| `crt-state-identity-ontology-2026-09.md` | Engine vs Resolver = constructors on one identity; Resolver not runtime-eligible while `blocking_gaps` non-empty |
| `ui-design-plan-closure-runid-2026-09-14.md` | Dual kit (Control Plane + CRT Dashboard); sole job key = **`run_id`**; no new SPA toolchain |
| `we-have-states-defined-whimsical-penguin.md` | One structural kernel arithmetic; founding ontology stays pluggable |
| Cost audit 2026-09-16 | Gate may stay gross while ledger nets; stamp cost identity before shadow SEM |
| User prefs | Identity-before-attribution; measure-before-promote; Variable ≠ Producer; formula/word parity |

---

## 3. Layer stack (schema → live eyes)

Elevate, don’t replace. Each layer has one job and one forbidden collapse.

```
L0  Ontology / formulas
    market_ontology.yaml · crt_state_identity.yaml · MeasurementObject registry
         │
L1  Identity tokens (closed vocab)
    CRTState · COST_MODEL_IDS · fill_model_id · walk_kernel · run_id mint rules (F-101)
         │
L2  Constructors (HOW)
    engine (runtime_eligible) · resolver (diagnostic) · research founders (visual/weekly)
         │
L3  Analysis tools (consume L0–L2 — no rival CRT)
    mother_range / sujan / oracle labeler / mt5_cost_calibration / trader grading / AST+schema probes
         │
L4  Run closure (job truth)
    Control Plane /runs/{id} · artifacts · monitors · CODEBASE_SEMANTIC_NAMES · UI_LLM_NAVIGATION
         │
L5a Trade Chart VIEW (desk)          L5b State MONITOR (ops)
    page4_trade_chart.jsx                 live_monitor + Runtime flow context
    engine ribbon + resolver ribbon       paper audit.jsonl · Ultron · NO_ORDER
    PLAYBOOK watch rules                  live.inout_runner node context
         │                                         │
         └──────── join: run_id + (instrument, bar_ts) ────────┘
         │
L6  Live rail (paper → later authorized)
    LiveRailOrchestrator · feeder · HookedLiveEngine · UltronLiveAdapter · OrderManager(paper)
```

### Forbidden collapses

| Collapse | Why forbidden |
|---|---|
| Chart color = OHLC direction | Candle color is **engine state**, not bull/bear body |
| Engine ribbon = Resolver ribbon | F-069 divergent construction |
| Live monitor = Trade Chart | Rail does not drive `process_candle`; chart without engine events is a different object |
| Ultron pip tax = G1+G2 ledger = SEM-015 | Three cost surfaces; L5 IDs differ; `backtest_g1g2_v2` not even in L5 vocab yet |
| Paper rail = production live | F-073; dry_run / AUTO_EXECUTE / experimental config |

---

## 4. Join contract (the small design that scales)

### 4.1 Keys

| Key | Owns | Used by |
|---|---|---|
| `run_id` | Job / closure | Control Plane, Dashboard RunChip, live_monitor `paper_run_dir` linkage |
| `(instrument, bar_ts)` | Bar alignment | Chart series, engine events, resolver track, audit rows |
| `cost_model_id` (+ params hash) | Net interpretation | Scoreboard, future shadow SEM column — **stamp before compare** |
| `constructor_id` | `engine` \| `resolver` | Chart ribbons, never merged occupancy |

### 4.2 Event vocabulary (pins / costume)

Already on Trade Chart: pin letter = **event first letter** (`S`=SWEEP, `R`=RESET), not S/R levels.
Desk costume (PLAYBOOK): **S → D → E(≥8) → R → (X)**.
Monitor vocabulary stays audit kinds (`NO_ORDER`, planner skip reasons) — do not rename audits into CRT states.

### 4.3 Dual panel product shape (v1 — no kit merge)

```
┌─ Control Plane ──────────────────┐  ┌─ CRT Dashboard ─────────────────────┐
│ Runs / Workflow / Closure        │  │ RunChip bar (bound run_id)          │
│ live.inout_runner node context   │  │ Trade Chart (L5a)                   │
│ → deep-link live_monitor         │  │ Trades Trace / Replay (scaffold→)   │
└──────────────────────────────────┘  └─────────────────────────────────────┘
         ▲                                         ▲
         │         ui_kits/live_monitor            │
         └──── state.json polls paper audit ───────┘
               + architecture URL pills (already)
```

Acceptance for “live chart + state monitoring” in v1:

1. Bound `run_id` visible in both shells  
2. Chart shows engine ribbon for that run (resolver optional second)  
3. Monitor shows rail audits for the **same** paper/backtest job or explicitly `UNBOUND`  
4. PLAYBOOK rules readable as watch chips (not hardcoded KPIs)  
5. Cost identity stamped or badge `UNSTAMPED` (today’s CSV state)

---

## 5. Analysis-tool posture (use infra, don’t fork)

All analysis stays **consumers** of L0–L2:

| Tool class | Role in this architecture |
|---|---|
| Schema / FM catalogs / identity check | Gate promotions; never invent sibling CRT enums |
| Cost calibration + cost_audit replay | Shadow nets beside ledger; no silent Ultron wire |
| Trader grading / PLAYBOOK | Feed watch routine + chart overlays (costume markers) |
| AST / workflow context / sealed mc_kit | Explain codepath in monitor; design_only sealed contracts stay sealed |
| Paper live rail CLI | The **only** authorized “run” of L6 until F-073 repair PRs land |

Research founding independence (visual / weekly pools) stays pluggable.
Arithmetic independence (six sweep copies) stays on the Structural Kernel kill-list — out of scope for this UI elevation except as a dependency note.

---

## 6. Walk plan (phased — measure-before-promote)

Jarvis order: each phase ends with a **run** that teaches the next walk.

### Phase A — Contract freeze (docs only) ✅ this document
- Freeze dual-view + join keys above  
- Point to existing plans; no new stack  

### Phase B — Stamp & bind (small code, later authorized)
- Stamp `cost_model_id` / params hash on trade ledger writes  
- `live_monitor.state.json` gains explicit `run_id` + `chart_url` deep link  
- Dashboard RunChip binds Trade Chart ↔ monitor  

### Phase C — Chart←rail shadow (paper only)
- Optional sidecar: bar_ts stream from paper rail audits aligned to nearest engine event log **if** same corpus/run  
- If no engine events (current paper path): monitor shows `CHART_UNBOUND_REASON=rail_skips_process_candle` — honest, not fake candles  

### Phase D — Watch loop
- Arm / verify `XAUUSD Trade Chart A-setup watch` against PLAYBOOK  
- Emit only A/A+ or orange-death-before-X; no economic claims  

### Phase E — Live rail repair PRs (from `live-rail-repair-path.md`)
- Only after PR-4a XOR/DM-001 landmines; still paper  
- Still no CRT-only shortcut  

### Non-goals (v1)
- Merging Control Plane + CRT Dashboard shells  
- Wiring SEM-015 into Ultron pip tax  
- Adding `backtest_g1g2_v2` to L5 without governance PR  
- Production broker orders  

---

## 7. Gap ledger (open, ordered)

| ID | Gap | Blocks | Next measure |
|---|---|---|---|
| G-LC-01 | Paper rail ↛ `CRTEngine.process_candle` | Live chart colors from rail | Document unbound; or authorized dual-feed experiment |
| G-LC-02 | Trades CSV unstamped cost identity | Fair net compare | Stamp-only write |
| G-LC-03 | Ultron gross vs ledger net | Live RR honesty | Design note SEM→R; no silent activate |
| G-LC-04 | `backtest_g1g2_v2` ∉ L5 vocab | Certify ledger outcomes | Governance add after stamp |
| G-LC-05 | Dashboard System/Intelligence/Replay scaffold | “Live” chrome trust | UNBOUND badges (UI plan U2) |
| G-LC-06 | Watch routine never fired | Desk automation | First scheduled run / dry ping |
| G-LC-07 | Dual capital / pip_size XAU wrong | Future Ultron tax | Keep dormant until mapping authorized |

---

## 8. “Run before walk” operating rule

When unsure whether the architecture is right:

1. **Run** a paper or analysis probe that touches one join key (`run_id` or bar_ts or cost_model_id)  
2. Write the result under `results/…` with CODEPATH or audit MD  
3. **Walk** only the contract that the run falsified or confirmed  
4. Refuse walks that invent a third CRT, a second sizer, or a merged chart/monitor object  

That is how the small designs we already did (monitor HTML, paper rail, PLAYBOOK, cost audit) stay load-bearing instead of disposable demos.

---

## 9. Immediate next ask (user pick)

1. **Phase B stamp/bind design detail** (field list + deep-link URL shapes) — still analysis  
2. **Phase C unbound honesty** — wire `CHART_UNBOUND_REASON` into `live_monitor/state.json` schema only  
3. **Phase D** — dry-run the A-setup watch prompt once (no schedule change)  
4. Stop at this elevation doc  

Primary artifacts this elevation rests on:

- `docs/implementation_plan/live-rail-repair-path.md`  
- `docs/implementation_plan/ui-design-plan-closure-runid-2026-09-14.md`  
- `docs/implementation_plan/crt-state-identity-ontology-2026-09.md`  
- `docs/UI_DESIGN_GAP_FROM_LIVE.md`  
- `ui_kits/live_monitor/` · `ui_kits/crt_dashboard/page4_trade_chart.jsx`  
- `results/…/cost_audit/COST_AUDIT_REVIEW.md` · `…/trader_read/PLAYBOOK.md`

---

## 10. Inventory cross-check (2026-09-16 evening)

Full surface census (analysis-only, no file mods in that pass) confirms and sharpens §3–§7:

### Confirmed
- UI transport is **HTTP poll only** (CP ~2s, live_monitor 4s, chart on tab open). No SSE/WS chart stream in `src/charts` / `ui_kits` (Binance WS is data-venue, not UI).
- Trade Chart authority path is live: `src/charts/chart_series.py` + `/api/chart_series` + `page4_trade_chart.jsx`.
- Cost stamp plan exists (`docs/implementation_plan/cost-model-identity-stamping.md` + impact JSON) but **`backtest_v2` still lacks stamped fields** on disk.
- Companion freeze: `docs/governance/INFRA_CHART_PAPER_COMPARE_V1.md` (chart⊕paper⊕broker; A0 series builder live).

### Sharp blocker (restated)
**Schema/identity + backtest Trade Chart are mature; paper live rail + `live_monitor` are a decision/audit side-car.**

Connecting schema → analysis → live chart + state monitor is blocked primarily by:

1. **Missing CRT occupancy producer on the live path** (`process_candle` / resolver) — fusion-only audits do not feed chart ribbons.
2. **L5 cost identity** — G1+G2 not stamped; `backtest_g1g2_v2` not in closed `COST_MODEL_IDS`.

Bridging requires a **second producer** (or dual-write): closed-bar CRTEngine (and/or resolver) **plus** the fusion decision rail — not a merge of the two views.

### Enrichment targets for `live_monitor/state.json` (schema only until authorized)
Beyond today’s `audit_kinds` / `last3` / architecture URLs:
- `run_id` (content mint, F-101-aware) + `paper_run_dir`
- `chart_bound: bool` + `chart_unbound_reason` (e.g. `rail_skips_process_candle`)
- optional L3: `last_engine_state` / costume phase when a CRT feeder exists
- `cost_model_id` when ledger-bound; else `UNSTAMPED`

PLAYBOOK under the paper run folder is **descriptive backtest-sourced** (`run_20260916_101942_XAUUSD`) — not live-generated; keep that provenance explicit in monitor chips.
