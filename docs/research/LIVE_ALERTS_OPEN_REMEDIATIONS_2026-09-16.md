# Live alerts — open blockers & remediations (2026-09-16)

Authority: RESEARCH_ONLY. Parents: `live_alert_v1`, `live_chart_bind_v1`, LIVE_CHART architecture.

## What now works (measured)

| Surface | Status |
|---|---|
| Desk Trade Chart bind | **BOUND** — `run_20260916_225925_XAUUSD` via `live_chart_bind_v1` |
| Cost stamp on fresh emit | **PASS** — `backtest_g1g2_v2` / `8239f7adde53080c` / `entry_fill_to_sl__v1` |
| Alert resolver | **LIVE** — `scripts/research/live_alert_resolver.py` → `results/live_alerts_20260916/` + `ui_kits/live_monitor/alerts.json` |
| PLAYBOOK A-setup alerts | **21 action** (E≥8→R) + 3 near-miss + 4 EXECUTION + 124 orange-death on bound run |
| Monitor | Shows alerts card + chart bind + rail unbound |

## Open blockers → remediations

| ID | Blocker | Remediation | Status |
|---|---|---|---|
| **REM-CRT-02** | Live rail skips `process_candle` → no live chart colors / no live-stream alerts | Dual-write CRT occupancy feeder beside fusion; chart-compatible `events.jsonl` under paper report-dir | **SIDECAR SMOKE PASS** (paper `--crt-occupancy-sidecar`) - desk alerts may still use backtest events until bind |
| **REM-CRT-04** | No bar_ts join coverage audit between rail audits and CRT events | Join probe once feeder emits occupancy | OPEN |
| **REM-COST-04** | `backtest_g1g2_v2` ∉ L5 `COST_MODEL_IDS` | Governance proposal / vocab extension (doc then authorized PR) | OPEN (alerted as BLOCKER_OPEN) |
| **REM-SOFT-01** | Ultron gross vs ledger net | Design note SEM→R; keep tax dormant until authorized | OPEN (alerted) |
| **REM-SOFT-03** | A-setup watch routine never fired | Point routine at `live_alert_resolver` output / alerts.json | OPEN — next wire |
| **REM-ALERT-01** | Expansion dwell via candle_index can span HTF resets (huge bar counts) | Reset costume on HTF RESET; require continuous EXPANSION occupancy from engine track | OPEN (quality) |
| **REM-ALERT-02** | Alerts are batch-on-run, not streaming | Poll resolver on new events tail when feeder writes live | OPEN |
| **REM-ALERT-03** | No push channel (Telegram/Slack) | Optional later; monitor JSON is source of truth first | DEFERRED |

## Research workflow order (remaining)

1. Land REM-CRT-02 smoke events under `results/live_crt_occupancy_smoke_*`
2. Re-run resolver with `--events` pointing at feeder output (true live-path alerts)
3. REM-ALERT-01 harden costume machine
4. Wire routine `xauusd-trade-chart-a-setup-watch` to call resolver + ping on new `A_SETUP_CANDIDATE` action
5. REM-COST-04 / REM-SOFT-01 stay governance — alert only until authorized

## Non-goals

- Economic claims from alert counts
- Merging engine/resolver for alerts
- Activating Ultron cost tax or production orders

### REM-CRT-02 smoke (2026-09-16 late)

**SMOKE PASS:** results/live_crt_occupancy_smoke_20260916 — 485 events, chart-parseable. Alerts: results/live_alerts_feeder_smoke_20260916. Still OPEN: wire into paper LiveRailOrchestrator.

### 2026-09-16 — continue (alerts harden + routine)

- **REM-ALERT-01 APPLIED:** RESET clears costume; EXPANSION only from S/D; dwell>200 → noncontinuous near-miss. Desk re-resolve: **19 action** A-setups (was 21; 2 discarded as noncontinuous).
- **REM-SOFT-03 APPLIED:** routine `xauusd-trade-chart-a-setup-watch` prompt now runs `live_alert_resolver.py` and pings only on new action/EXECUTION.
- **REM-CRT-02 orchestrator wire:** **DONE** (paper `--crt-occupancy-sidecar` smoke PASS -> `results/live_rail_crt_sidecar_smoke_20260916`).

### 2026-09-16 - REM-CRT-02 paper rail CRT occupancy sidecar (measure)

**WIRED (research, paper-only):** optional `--crt-occupancy-sidecar` on `scripts/live/run_live_rail.py` (requires `--paper` + `--report-dir`). Production path unchanged when flag absent.

| Piece | Path / note |
|---|---|
| Shared helper | `scripts/research/crt_occupancy_lib.py` (BacktestRunner + CandleLoader islice; `BACKTEST_ENGINE_GATE=0` scoped) |
| CLI flag | `--crt-occupancy-sidecar` → `report-dir/crt_occupancy/` + `SIDECAR_META.json` |
| Smoke dir | `results/live_rail_crt_sidecar_smoke_20260916` |
| Rail audit | `audit.jsonl` (2 `NO_ORDER`) — EngineRunner path intact |
| CRT events | `crt_occupancy/XAUUSD_events.jsonl` — **82** events (RESET 35 / STATE_TRANSITION 27 / SWEEP 20); chart_overlay parseable; track_from_events OK |
| Meta | `SIDECAR_META.json` links paper_run_dir + events + `live_chart_bind_v1` / `live_alert_v1` |

**Command:**
```
set PYTHONPATH=src
.venv\Scripts\python.exe scripts\live\run_live_rail.py --paper ^
  --config configs\experimental\spec\live_rail_tickdb_paper_run.json ^
  --arm tickdb --limit 500 ^
  --report-dir results\live_rail_crt_sidecar_smoke_20260916 ^
  --crt-occupancy-sidecar
```

Design preserved: CRT feeder is ADDITIVE occupancy for chart/alerts only; no CRT→broker shortcut; Ultron / orders / ACTIVE_VERSION / tokens.py untouched. Status: REM-CRT-02 **sidecar smoke PASS** — still research-only (not production bind).

### REM-CRT-02 paper side-car (2026-09-16 night)

**SIDECAR SMOKE PASS:** `results/live_rail_crt_sidecar_smoke_20260916`
- Flag: `--crt-occupancy-sidecar` on paper `run_live_rail.py` only
- Rail `audit.jsonl` + `crt_occupancy/XAUUSD_events.jsonl` (82 events, chart-parseable)
- Lib: `scripts/research/crt_occupancy_lib.py`
- Alerts: `results/live_alerts_sidecar_smoke_20260916`
- Still open: larger limit / tickdb hours; REM-COST-04; REM-SOFT-01

### 2026-09-16 — REM-COST-04 + REM-SOFT-01 docs

- Proposal: `docs/research/REM_COST_04_L5_VOCAB_PROPOSAL_2026-09-16.md` (no tokens.py edit)
- Design note: `docs/research/REM_SOFT_01_ULTRON_GROSS_VS_LEDGER_NET_2026-09-16.md` (tax stays dormant)

﻿

﻿### 2026-09-16 - REM-CRT-02 longer paper CRT occupancy sidecar 8k (measure)

**SIDECAR 8k PASS (research-only):** live A-setup density smoke on paper rail + CRT occupancy sidecar.

| Piece | Path / note |
|---|---|
| Report dir | `results/live_rail_crt_sidecar_8k_20260916` |
| Rail audit | `audit.jsonl` (2 `NO_ORDER`) |
| CRT events | `crt_occupancy/XAUUSD_events.jsonl` - **1095** events |
| Alerts | `results/live_alerts_sidecar_8k_20260916` - kinds: A_SETUP 3 (n_action **2**), orange-death **27**, blockers 3 |
| Monitor | `ui_kits/live_monitor/alerts.json` prefers this 8k feeder/live snapshot; desk summary still **19 action** referenced |
| Arm | `tickdb` limit 8000 (no bars fallback needed) |

**Command:**
```
set PYTHONPATH=src
.venv\Scripts\python.exe scripts\live\run_live_rail.py --paper --config configs\experimental\spec\live_rail_tickdb_paper_run.json --arm tickdb --limit 8000 --report-dir results\live_rail_crt_sidecar_8k_20260916 --crt-occupancy-sidecar
```

Resolver: `live_alert_resolver.py` with `--chart-bound --live-rail-bound --stamp-trust FRESH_EMIT_VERIFIED --cost-model-id backtest_g1g2_v2`. No ACTIVE_VERSION / tokens / Ultron config changes. Status: REM-CRT-02 **8k sidecar PASS** - denser than 500-limit smoke; still research-only.

### 2026-09-16 — REM-COST-04 IMPLEMENTED

- `src/identity/tokens.py`: added `backtest_g1g2_v2`, `backtest_zero_cost`
- Tests: `tests/test_cost_model_ids_l5_rem_cost_04.py` (4 passed)
- Manifest: `docs/governance/build_manifests/CH-rem-cost-04-l5-vocab.impact.json`
- Contract 9.2 table updated
- Watch dry-run: `results/live_alerts_watch_dryrun_20260916`

### 2026-09-16 — REM-SOFT-01 shadow measure

- Script `scripts/research/ultron_sem_r_shadow.py`
- On stamped 3 fills: **2/3 admission flips** under SEM→R shadow vs gross `min_rr=1.5`
- Ultron tax still dormant (no config change)

### 2026-09-17 — Telegram link research

See `docs/research/LIVE_ALERT_TELEGRAM_LINK_2026-09-17.md`. REM-TG-01..05 proposed; Telegram execution path exists but does not consume `live_alert_v1`.

### 2026-09-17 — REM-TG-01 dry-run PASS

- Bridge: `scripts/research/live_alert_telegram_bridge.py`
- Verify: `results/live_alert_telegram_dryrun_20260917/REM_TG_01_VERIFY.json` (n_sent_ok=3, force_dry_run=true)
- Routine watch now invokes dry-run bridge after resolver

### 2026-09-17 — REM-TG-05 env wire

- Research bridge prefers `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` (process env or ROOT/.env)
- `TelegramBridge.from_env()` + `from_prod_config()` falls back to those env keys when JSON tokens empty
- `--allow-live-send` refuses unless both env keys set; default remains forced dry_run
