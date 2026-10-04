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
