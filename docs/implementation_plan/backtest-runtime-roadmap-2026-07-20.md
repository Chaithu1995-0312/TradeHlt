# Backtest / Runtime Roadmap (opened 2026-07-20)

**Status:** **ACTIVE engineering focus** after
[`FEATURE_LAYER_MUTATION_FREEZE = ACTIVE`](../governance/feature-layer-mutation-freeze-2026-07-20.md).

**Scope note:** this is a working roadmap. It does not grant promotion authority, economic
claims, or permission to unfreeze the feature layer. Authority still follows CLAUDE.md §4.0
(runtime truth) and §6.5 (Authority Ladder).

---

## 0. Why the focus shifted

| Layer | State | Implication |
|---|---|---|
| Feature identity | Exhausted + **governance** mutation-frozen | Stop free-form feature work (science remains extensible via waivers) |
| Feature regression pin | XAUUSD matrix + schema + source SHAs only | Not a multi-instrument runtime suite |
| Feature completion (M16) | Parked under accepted future programs | Resume only by named program |
| Binding constraint (findings) | Entry-info null F-019…; process/throughput/governance (F-001) | Edge is not “one more FM” |
| Unverified live path | F-010 OPEN; F-048 candidate | Runtime/backtest honesty > new features |

**Milestone split (2026-07-20b):**

| Milestone | Status |
|---|---|
| Feature Layer Freeze (governance) | ✅ ACTIVE |
| Feature Regression Benchmark (XAUUSD only) | ✅ Pinned |
| Runtime Benchmarks (BNB gate ON/OFF, multi-instrument, ledger) | ⏳ Opens with R-1 / R-2 |

**Default for new sessions:** work this roadmap, keep
`tests/test_feature_layer_freeze.py` green, do not open a parallel feature tracker.
Do not put BNB vector hashes back into the *feature* freeze pin — put them in a runtime
benchmark manifest when R-1/R-2 runs.

---

## 1. North-star questions (runtime truth first)

Before any backtest or live reasoning, `ORIENT_RUNTIME`:

1. `configs/production/ACTIVE_VERSION` → currently **`v2_multi_2026_04`**
2. Load via `get_prod_config()` — schema must accept keys
3. Record gate mode: `BACKTEST_ENGINE_GATE` effective value (F-037: research often off)
4. Record instrument + CSV path + whether corpus guards rewrote the path

A run without those four facts is not evidence.

---

## 2. Workstreams (priority order)

### R-1 — Measurement honesty (foundational)

| ID | Item | Why | Exit |
|---|---|---|---|
| R-1.1 | Always log **gate ON vs OFF** in run artifacts / notes | F-037: spine research ≠ live fusion | Every backtest note states effective gate |
| R-1.2 | Path / corpus-guard transparency | SF-001: silent corpus substitution | Declared windows stay declared; no silent rewrite without log+finding |
| R-1.3 | Single-pass or cached CSV load (optional hygiene) | SF-004: four reads per backtest | Reduce waste without changing ledger |
| R-1.4 | Keep feature freeze pin green while changing runtime | Freeze contract | `tests/test_feature_layer_freeze.py` pass |

### R-2 — Runtime benchmark suite (separate from feature freeze pin)

> **Do not merge these into the feature-layer freeze pin.** Feature parity ≠ execution
> coverage. Runtime manifests should carry their own coverage metadata (filters, planner,
> partial TP, gate mode, trade counts).

| ID | Item | Why | Exit |
|---|---|---|---|
| R-2.1 | Reuse XAUUSD 2-month run as **fixture reference** (do not re-run casually) | `results/XAUUSD/backtests/run_20260719_021925_XAUUSD/` — 0 trades, session-filter bottleneck | Documented path + transition counts in notes |
| R-2.2 | **Runtime Benchmark 1 — XAUUSD 2-month Gate ON/OFF** on `data/XAUUSD_W2026-03-23-to-2026-05-21.csv` | Fast primary runtime reference (~4k bars, not a feature SHA) | Manifest with n_trades, events hash, gate mode, coverage metadata |
| R-2.2b | **RB1-HEAVY (optional)** — BNB full corpus Gate ON/OFF | Multi-year generality only; **not** default | Same schema; run only when user asks |
| R-2.3 | Runtime Benchmark 2 — multi-instrument (ETH/BTC/SOL as needed) | Comparability | Table instrument×gate |
| R-2.4 | Runtime Benchmark 3 — trade ledger parity / determinism (2× byte-identical events) | Replay doctrine | Pass/fail recorded |
| R-2.5 | Coverage metadata on every runtime run | Anti false-green | `exercised_filters`, `partial_tp`, `planner`, `trade_count`, `gate` fields present |

### R-3 — Admission / filter stack (runtime correctness)

| ID | Item | Why | Exit |
|---|---|---|---|
| R-3.1 | Map filter stack: CRT session → fusion (if gate ON) → DecisionEngine → planner → Ultron | Know where candidates die | One diagram + counters from real runs |
| R-3.2 | **F-048 intent decision** (user): mis-wire vs dormant-by-design | `run()==execute` structurally zero if polarity vs rr_threshold=1.5 | Written verdict + either fix plan or explicit dormant acceptance |
| R-3.3 | Session filter vs FM-052 collision (when consumer phase opens) | XAUUSD: 3/3 retests killed by session | Deferred with M16 P1; do not “fix” session in feature layer |

### R-4 — Live path readiness (no paper claims)

| ID | Item | Why | Exit |
|---|---|---|---|
| R-4.1 | Live ingress already fail-closed (T-11 partial) | Silent defaults removed | Keep; no new soft defaults |
| R-4.2 | Feeder handshake design (T-11 residual) | Batch/live period asymmetry | Design note + external EA coordination; not unilateral |
| R-4.3 | Shadow / paper path inventory | F-010 live PnL unverified | List what can run without secrets; what is blocked |

### R-5 — Consumer-alignment phase (explicit future; not now)

Only when user opens **live_engine_hook phase**:

- M16-WU-SESSION-ENCODING  
- M16-WU-TREND-STRENGTH-COLLISION  
- M16-WU-VOLREGIME-S05  

These remain `BLOCKS_ACTIVATION: true`. Deferral is accepted; do not start under “small cleanup.”

### R-6 — Explicitly out of scope (until re-authorized)

- L6 feature activation / FM-030/031 vector swap without migration plan  
- New feature math, new FM production registrations outside accepted programs  
- Economic “edge found” claims from underpowered runs (n≪30)  
- MT5 automation / paper-trade integration (user parked)  

---

## 3. Suggested first three steps (execute next)

1. **R-1.1 + R-2.2 (XAUUSD 2-month gate-ON/OFF pair)** — fast default; capture summary +
   events hash + coverage; no config promotion. **Do not default to full-year BNB.**
2. **R-3.1 filter-stack map** from the XAUUSD pair (read-only).
3. **R-3.2 F-048 adjudication packet** for user decision (code cites + options; no silent fix).

---

## 4. Definition of done for this roadmap (phase exit)

This roadmap phase is **not** “find edge.” Exit when:

- [ ] Gate mode is always explicit on stored runs  
- [ ] Multi-instrument gate-ON/OFF baselines exist and are determinism-checked  
- [ ] Filter-stack map is current vs code  
- [ ] F-048 has a user-recorded intent decision  
- [ ] Feature freeze pin still green  
- [ ] Next phase chosen: consumer-alignment (M16 P1–P3) **or** execution/risk deep-dive **or** stop  

---

## 5. Cross-links

| Artifact | Role |
|---|---|
| [`feature-layer-mutation-freeze-2026-07-20.md`](../governance/feature-layer-mutation-freeze-2026-07-20.md) | Freeze policy |
| [`feature-layer-freeze-pin-2026-07-20.json`](../governance/feature-layer-freeze-pin-2026-07-20.json) | Regression pin |
| [`feature-layer-tracking-2026-07-19.md`](feature-layer-tracking-2026-07-19.md) | Closed feature queue (historical) |
| [`docs/architecture/signal-flow.md`](../architecture/signal-flow.md) | Candle→order spine |
| [`docs/architecture/roadmap.md`](../architecture/roadmap.md) | Gov vs Trd tracks (M labels) |
| F-010 / F-037 / F-048 / F-017 | Findings that bound this work |

---

## 6. Standing caveat

F-019…F-025 entry-information null bounds expected economic value of micro-optimizations.
Runtime work is justified as **correctness, measurability, and honest admission**, not as an
implied path to positive expectancy.
