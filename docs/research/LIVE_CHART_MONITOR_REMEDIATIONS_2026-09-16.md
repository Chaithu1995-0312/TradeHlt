# Research workflow — Live Chart + State Monitor remediations

| Field | Value |
|---|---|
| **Date** | 2026-09-16 (Asia/Kolkata) |
| **Lane** | Research / design — build on existing schema |
| **Authority** | None. No promotion. `economic_claims_allowed=false` |
| **Parents** | `LIVE_CHART_STATE_MONITOR_ARCHITECTURE_2026-09-16.md` · `cost-model-identity-stamping.md` · `INFRA-CPC-V1` · `live-rail-repair-path.md` · L5 identity contract |

---

## 1. Intent lock (schema first)

| Contract | Intent (one line) |
|---|---|
| **L3 occupancy** | CRT state at bar *t* is a constructor-qualified MeasurementObject — engine ≠ resolver (F-069); never merge ribbons |
| **L4 / L5** | Same geometry under different walk+cost+fill = **different L5 objects**; cost id is identity, not a scalar haircut |
| **Cost stamp** | Additive metadata only: `cost_model_id`, `cost_model_params_hash`, `risk_denominator_id=entry_fill_to_sl__v1` — **zero PnL drift** |
| **INFRA-CPC-V1** | Chart series is audit authority; PNG is a view; missing CRT = `UNAVAILABLE` |
| **F-073 / live rail** | Repair paper path; CRT EXECUTION must not skip EngineRunner; no production live |
| **UI closure** | Dual kit; sole job key = `run_id`; chart view ≠ state monitor |

**Build-on rule:** remediations extend these objects. They do not invent a third CRT, a second sizer, or a merged chart/monitor type.

---

## 2. Current measure (what is already true)

| Fact | Evidence |
|---|---|
| Stamp **code path** exists in `backtest_v2` (fields + CSV columns + summary) | Source constants `BACKTEST_COST_MODEL_ID`, `BACKTEST_RISK_DENOM_ID`; `to_csv_rows` writes ids |
| Stamp **absent** on `run_20260916_101942_XAUUSD/XAUUSD_trades.csv` | Pre-stamp artifact (or run not re-emitted) |
| L5 closed vocab still `{flat_12bps, sem015_component_xauusd, none_gross}` | `src/identity/tokens.py` — **`backtest_g1g2_v2` not member** |
| Paper rail emits fusion audits, not CRT occupancy | `CODEPATH_TRACE.md`; `live_monitor` = `NO_ORDER` only |
| Trade Chart consumes `/api/chart_series` from **backtest** events | `page4_trade_chart.jsx` + INFRA A0 |

---

## 3. Research workflow (order)

```
Step-0  Freeze intent (this brief + architecture §3 forbidden collapses)
Step-1  MEASURE     — provenance / unbound honesty / stamp presence
Step-2  SHADOW      — dual-write or sidecar without switching authority
Step-3  HOLD-OUT    — variance / byte-identical checks before promote
Step-4  PROMOTE     — only with explicit authorization (vocab / wiring)
```

Jarvis: each remediation below ends in a **run** that teaches the next walk.

---

## 4. Hard-blocker remediations

### H1 — Cost identity (ledger nets without certifiable L5)

| ID | Remediation | Extends | Scope | Success measure | Must NOT claim |
|---|---|---|---|---|---|
| **REM-COST-01** | **Re-emit stamp on next backtest** (or config-identical rerun): verify CSV/summary carry `cost_model_id=backtest_g1g2_v2`, `cost_model_params_hash`, `risk_denominator_id=entry_fill_to_sl__v1`; byte-compare `pnl_rr_*` to baseline | Cost stamp plan §5–§8 / CH-cost-model-identity-stamp | Research verify → later authorize if code incomplete | Columns present; hash stable; PnL byte-identical | That SEM-015 or flat-12 is now charged |
| **REM-COST-02** | **Backfill sidecar** for historical `run_20260916_*`: derive ids from knobs into `cost_audit/identity_stamp.json` (do not rewrite trades.csv in place) | Same field names; F-101 content `run_id` | Research-only | Reader reconstructs cost without guessing | Mutating historical ledger authority |
| **REM-COST-03** | **Shadow column** `pnl_rr_net_sem015` beside G1+G2 on n=3 (already replayed) → holdout larger sample; keep `constructor`/`cost` as separate L5 axes in the report | SEM-015 `ComponentCostModel`; L5 “different cost ⇒ different object” | Research shadow | Table + variance; `economic_claims_allowed=false` | Replacing scoreboard or Ultron tax |
| **REM-COST-04** | **L5 vocab extension proposal** (doc-only): add `backtest_g1g2_v2` (+ reserve `backtest_zero_cost`) to `COST_MODEL_IDS` with mapping note vs research set | `tokens.py` / CANONICAL L5 | Governance proposal only | Impact manifest + dual-world note (research vs production path) | Silent merge of `metals_mt5_v1` ↔ `sem015_component_xauusd` without alias table |

**Recommended first on H1:** REM-COST-01 (measure whether stamp already ships) → REM-COST-02 for the named run → REM-COST-03 only as diagnostic.

---

### H2 — Live CRT occupancy missing (chart can’t bind to rail)

| ID | Remediation | Extends | Scope | Success measure | Must NOT claim |
|---|---|---|---|---|---|
| **REM-CRT-01** | **Unbound honesty schema** on `live_monitor/state.json`: `chart_bound=false`, `chart_unbound_reason=rail_skips_process_candle`, `run_id`, `content_run_id` | Architecture §4 / INFRA missing-CRT=`UNAVAILABLE` | Schema/docs + optional state.json shape | Monitor never implies live ribbons | Fake candle colors from fusion scores |
| **REM-CRT-02** | **Dual-write research feeder** (paper): on each closed bar, call `CRTEngine.process_candle` *beside* hook/fusion; write chart-compatible `events.jsonl` / series under `report-dir/crt_occupancy/` with `constructor_id=engine` | L3 constructors; INFRA A0 payload; live-rail repair “no CRT shortcut to orders” | Research / experimental config only | Series openable in Trade Chart under paper `run_id`; fusion audits unchanged | That feeder is the execution authority or closes F-073 |
| **REM-CRT-03** | **Resolver shadow track** on same bars → second ribbon file `constructor_id=resolver`; agreement % logged (F-069 style), never merged | CRT state identity constructors | Research | Dual ribbons + agreement; EXECUTION rarity preserved | Runtime-eligible resolver while `blocking_gaps` non-empty |
| **REM-CRT-04** | **Join probe**: `(instrument, bar_ts)` align occupancy events ↔ `audit.jsonl` decision rows → coverage table | Architecture join contract | Research measure | Coverage %, lag, unbound count | Live PnL / equivalence |

**Recommended first on H2:** REM-CRT-01 (cheap honesty) → REM-CRT-04 measure → REM-CRT-02 only under experimental paper config.

---

## 5. Soft-gap remediations (one row each)

| ID | Gap | Remediation on schema | First run |
|---|---|---|---|
| **REM-SOFT-01** | Ultron gross vs ledger net | Design note: SEM→R tax mapping; keep `spread_pips=0` until authorized; document gate as `cost_model_id=none_gross` at admission | Doc-only compare table |
| **REM-SOFT-02** | Poll-only UI | Keep poll until live bar stream exists; no SSE design debt until REM-CRT-02 produces a series | N/A |
| **REM-SOFT-03** | Watch routine never fired | Dry-run A-setup watch prompt once against PLAYBOOK + latest chart events; log outcome | One manual invoke |
| **REM-SOFT-04** | Paper smells (ZoneGate/`london`, Gaussian EURUSD, INR caps) | Finding tickets only; isolate as infra defects ≠ CRT semantics | Census in paper CODEPATH |
| **REM-SOFT-05** | PLAYBOOK under paper dir but backtest-sourced | Stamp `playbook_source_run_id` in monitor/state | Edit state schema |
| **REM-SOFT-06** | Dual capital / wrong XAU pip | Leave dormant; remediation = declaration in Ultron comment (already) + future instrument pip table | No activate |
| **REM-SOFT-07** | UI RunChip / deep-link incomplete | Follow ui-design-plan U1/U2; bind monitor `?run=` to CP | Design acceptance checklist |

---

## 6. Non-goals

- Merging Control Plane + CRT Dashboard  
- Wiring SEM-015 into Ultron or replacing G1+G2 in production backtest  
- Production broker orders / exit loop  
- Claiming economic edge from shadow nets or costume watches  
- Collapsing engine and resolver occupancy  

---

## 7. Pick-list (next experiment)

| Priority | ID | Why first |
|---|---|---|
| 1 | **REM-COST-01** | Schema already intended; verify stamp on a fresh emit — cheapest hard-blocker close |
| 2 | **REM-CRT-01** | Makes monitor schema-honest before any feeder work |
| 3 | **REM-COST-02** | Unblocks interpreting the named Sept 16 run under identity |
| 4 | **REM-CRT-04** then **REM-CRT-02** | Measure join, then dual-write feeder under paper |
| 5 | **REM-SOFT-03** | Desk loop without architecture risk |

---

## 8. One-line synthesis

**Remediate by naming and dual-writing — not by merging views.** Stamp cost identity (and backfill the historical run), declare chart unbound until a research CRT occupancy feeder sits *beside* the fusion rail, then join on `run_id` + bar_ts under the existing L3/L5 contracts.

---

## 9. Measure log (executed)

### 2026-09-16 — REM-COST-01 + REM-COST-02 + REM-CRT-01

| ID | Result |
|---|---|
| REM-COST-01 | **Code-complete** in acktest_v2 (constants, config fields, CSV/summary writers). Historical XAUUSD_trades.csv still **unstamped** (artifact lag). |
| REM-COST-02 | Sidecar written: 
esults/run_20260916_101942_XAUUSD/cost_audit/identity_stamp.json — cost_model_id=backtest_g1g2_v2, 
isk_denominator_id=entry_fill_to_sl__v1, cost_model_params_hash=8239f7adde53080c, content_run_id=
un_20260916_044942. |
| REM-CRT-01 | ui_kits/live_monitor/state.json + index.html now expose chart_bound=false, chart_unbound_reason=rail_skips_process_candle, playbook source run, cost_model_id=UNSTAMPED. |

Next: REM-CRT-04 join probe or REM-COST-03 larger SEM shadow; L5 vocab (REM-COST-04) remains governance-gated.

### 2026-09-16 — Fresh stamp emit (trust)

| Field | Value |
|---|---|
| Folder | 
esults/run_fresh_stamp_20260916_2250_XAUUSD/run_20260916_225925_XAUUSD |
| content_run_id | 
un_20260916_172925 |
| Stamp on CSV+summary | **YES** — acktest_g1g2_v2 / 8239f7adde53080c / entry_fill_to_sl__v1 |
| n_trades / pnl_rr_net | 3 / **-1.6923** (matches prior economic totals) |
| Verdict | REM-COST-01 **PASS on fresh artifact** — prefer this run over sidecar/old CSV |

### 2026-09-16 — live_chart_bind_v1 applied

| Field | Value |
|---|---|
| Schema | docs/schemas/live_chart_bind_v1.json |
| Canonical run dir | 
esults/run_20260916_225925_XAUUSD (promoted for 
un_*_XAUUSD discovery) |
| API run_id (folder) | 
un_20260916_225925_XAUUSD |
| content run_id | 
un_20260916_172925 |
| chart_payload smoke | **ok=true** — crt_state.engine + 
esolver present |
| Desk chart | **BOUND** via schema |
| Live rail chart | still **UNBOUND** (
ail_skips_process_candle) until REM-CRT-02 |

Open Trade Chart: instrument XAUUSD, run 
un_20260916_225925_XAUUSD.

### 2026-09-16 — live_alert_v1

- Schema: `docs/schemas/live_alert_v1.json`
- Resolver: `scripts/research/live_alert_resolver.py`
- Out: `results/live_alerts_20260916/` (21 A-setup action, 4 EXECUTION, rail unbound blocker open)
- Monitor: `ui_kits/live_monitor/alerts.json`
- Open ledger: `docs/research/LIVE_ALERTS_OPEN_REMEDIATIONS_2026-09-16.md`

### 2026-09-16 - REM-CRT-02 dual-write smoke (research)

| Field | Value |
|---|---|
| Script | `scripts/research/crt_occupancy_feeder_smoke.py` |
| Out dir | `results/live_crt_occupancy_smoke_20260916` |
| Path | BacktestRunner + CandleLoader islice (limit=3000); version v2_htfcrt_2026_08 in-process; BACKTEST_ENGINE_GATE=0 |
| Events | `XAUUSD_events.jsonl` — **485** lines; STATE-ish (STATE_TRANSITION+RESET) = **365** |
| Sample states | DISPLACEMENT, EXECUTION, EXPANSION, RANGE, RETEST, SHADOW_PENDING, SWEEP |
| Meta | `FEEDER_META.json` — constructor_id=engine, remediation=REM-CRT-02, authority=RESEARCH_ONLY, source=dual_write_smoke, parent_schema=live_chart_bind_v1 |
| Verify | `FEEDER_VERIFY.json` — chart_overlay_parseable=true; track_from_events_ok=true (RESOLVED:v2_htfcrt_2026_08) |
| Non-goals held | No ACTIVE_VERSION write; no tokens.py; no Ultron live submit; paper fusion rail unchanged |

Verdict: REM-CRT-02 **smoke PASS** — engine occupancy events are chart_overlay-parseable under a research out-dir. Live rail remains unbound until a paper dual-write wires this feeder beside the fusion path.
