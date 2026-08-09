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

#### P1.3 Story ontology + multi-story golden library — **IMPLEMENTED 2026-07-16** (WI-002)

> Owner-approved slice covering P1.1 golden + P1.2 story externalization. **Descriptive-only** — the
> executable substrate (9 CRT states, 38-dim vector, `configs/formulas/market_ontology.yaml`) is
> UNCHANGED; story geometry stays in CODE (D-23). Grants no runtime/promotion authority (§6.5).

| Artifact | What |
|---|---|
| `configs/research/market_story_ontology.yaml` | 8 semantic layers · 12 families (4 active) · 38 market states · engine bands (descriptive) |
| `src/research/synthetic/` | reusable story engine (`story_spec`, `story_builder`, `ontology`, `story_registry`, `stories/`) |
| `scripts/research/story_library_build.py` | driver → `data/synthetic/stories/<id>/` + `INDEX.json` |
| `tests/research/test_story_library_golden.py`, `test_story_ontology.py` | six-layer + anti-drift floors (38 tests green) |

**Six-layer per-story validation:** family → market-states → CRT-path → feature-signature →
engine-signature → outcome. **12/12 stories pass**; the anchor reproduces the `erp_4h_m15` pack;
outcome coverage includes TP_HIT / SL_HIT / TIMEOUT.

**Roadmap:** Phase A = 4 families / ~12 stories (done) · Phase B = 8 families / ~40 stories · Phase C
= 12 families / 80–120 stories (then consider promoting a semantic layer to executable — evidence-first).

**Pending owner:** a Decision-Board note (proposed **D-2N**) locking "semantic story ontology =
descriptive/validation only." Remaining P1 (pytest markers + `run_manifest` + AH/VP fixtures) still PLANNED.

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
