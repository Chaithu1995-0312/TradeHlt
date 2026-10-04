# Live-alert spine ↔ Telegram alerts (codebase link research)

| Field | Value |
|---|---|
| **Date** | 2026-09-17 (Asia/Kolkata) |
| **Authority** | RESEARCH_ONLY — no sends activated, no secrets transcribed |
| **Parents** | `live_alert_v1` · `TelegramBridge` · `HookedLiveEngine` · LIVE_ALERTS_OPEN_REMEDIATIONS |

---

## 1. Inventory — Telegram / alert surfaces in-repo

| Path | Role | Trigger today | Status |
|---|---|---|---|
| `src/live/telegram_bridge.py` | Canonical Bot API sender | `send_signal_alert` / `send_kill_switch` / `send_daily_summary` | **live module** (fail-open; dry_run supported) |
| `src/runtime/live_engine_hook.py` | Hook wires TelegramBridge | Kill-switch trip → `send_kill_switch`; approve+`hook_submit_orders=True` → `send_signal_alert` (+ MT5) | **wired**; default **`hook_submit_orders=False`** (XOR — no Telegram-as-order) |
| `src/runtime/live_rail_orchestrator.py` | Paper/production rail builds hook | Passes `hook_submit_orders=cfg.hook_submit_orders` | Paper experimental config keeps submit **off** |
| `src/engines/live_engine.py` | Older “Live trading decision + Telegram alert system” | Pipeline step sends via `send_telegram_alert`; training-trigger throttle; `simulate_*` blanks token | **parallel stack** (env `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`) — not the CRT costume spine |
| `src/execution/alert_manager.py` | Generic notifier | `external_hook` injectable (Telegram optional) | **stub/extensible**; not bound to live_alert_v1 |
| `src/.../health_checker.py` | Health path imports TelegramBridge | Probe / notify via `from_prod_config()` | **ops side** |
| `configs/production/... live_integration.telegram` | bot_token, chat_id, enabled, timeout_s, dry_run | Loaded by `TelegramBridge.from_prod_config` | **config** (values not logged here) |
| `scripts/research/live_alert_resolver.py` | `live_alert_v1` producer | Writes JSONL / monitor snapshot — **no Telegram** | **research spine** |
| `ui_kits/live_monitor/alerts.json` | Monitor consumer | Poll display | **UI only** |
| Routine `xauusd-trade-chart-a-setup-watch` | Hourly resolver | Notify user via Grok Bot chat on action/EXECUTION | **not Telegram** |

### Config posture (keys only)

Production `live_integration.telegram`: `bot_token`, `chat_id`, `enabled`, `timeout_s`, `dry_run` (via `TelegramBridge.from_prod_config`).  
Legacy engine also reads **env** `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`.

Paper rail: `hook_submit_orders=false` → HookedLiveEngine stays decision-only; **no signal Telegram** on the F-073 paper path we smoke-tested.

---

## 2. Current send path (as-built)

```
                    ┌─────────────────────────────┐
                    │ live_alert_v1 resolver       │
                    │ (CRT costume / blockers)     │
                    │ → alerts.jsonl / monitor     │
                    │ → Grok watch routine         │
                    └─────────────┬───────────────┘
                                  │  NO Telegram today
                                  ▼
                             (gap)

Ultron APPROVE + hook_submit_orders=True
        │
        ▼
HookedLiveEngine._emit_live_io
        │
        ├─ TelegramBridge.send_signal_alert  (BUY/SELL + SL/TP/RR)
        └─ MT5Bridge send_order

KillSwitch.register_trade → trip
        │
        └─ TelegramBridge.send_kill_switch

engines/live_engine.py (legacy)
        │
        └─ send_telegram_alert (env token)  ← parallel, not CRT A-setup
```

---

## 3. Gap vs `live_alert_v1`

| live_alert_v1 kind | On Telegram today? |
|---|---|
| `A_SETUP_CANDIDATE` (action) | **No** |
| `EXPANSION_ORANGE_DEATH` | **No** |
| `EXECUTION_RARE` | **No** (hook Telegram is fusion/Ultron signal, not CRT state EXECUTION) |
| `CHART_UNBOUND` / `BLOCKER_OPEN` | **No** |
| `STAMP_TRUST_OK` | **No** (and should stay quiet) |
| Ultron approve signal | **Yes** — only if `hook_submit_orders=True` |
| Kill switch | **Yes** — on trip via hook |

**Spine split:**  
- **Desk/research alerts** = constructor-qualified CRT occupancy → `live_alert_v1`.  
- **Telegram in codebase** = execution-adjacent notifications (signal / kill / legacy engine).  

They share a transport (`TelegramBridge`) but **not an event vocabulary**. REM-ALERT-03 correctly deferred “push channel” until this join is designed.

---

## 4. Recommended join remediations (research → later authorize)

| ID | Remediation | Extends | Must NOT |
|---|---|---|---|
| **REM-TG-01** | Add `scripts/research/live_alert_telegram_bridge.py`: map `severity=action` (+ optional EXECUTION) → `TelegramBridge.send_*` or a new `send_research_alert(text)` using **dry_run=True** by default; read alerts.jsonl delta | `TelegramBridge` + `live_alert_v1` | Enable on paper rail without `--paper` gate; paste tokens into docs |
| **REM-TG-02** | Format contract: prefix `LIVE_ALERT_V1 \| {kind} \| {instrument}` + bar_ts + expansion_bars + api_run_id + constructor=engine; never claim economic edge | Schema `live_alert_v1` | Reuse `send_signal_alert` BUY/SELL wording for A-setups (wrong ontology) |
| **REM-TG-03** | Wire watch routine: after resolver, if new action alerts and `live_integration.telegram.dry_run` or explicit research flag, call REM-TG-01; else Grok Bot only | Routine prompt | Flip `hook_submit_orders` to True to “get Telegram” |
| **REM-TG-04** | Deduplicate: fingerprint `(kind, bar_ts, api_run_id)` so hourly watch doesn’t re-blast | alerts snapshot | Spam on orange-death (watch severity → digest only) |
| **REM-TG-05** | Unify config: prefer `live_integration.telegram` over legacy env for any new path; document dual stacks (hook vs engines/live_engine) | config | Store bot_token in git |

**Suggested first implement:** REM-TG-01 + REM-TG-02 with **forced dry_run**, measure one dry log line from an `A_SETUP_CANDIDATE` action alert — no HTTP.

---

## 5. Non-goals

- Activating `hook_submit_orders` or AUTO_EXECUTE  
- Sending real Telegram traffic from this research turn  
- Publishing bot_token / chat_id values  
- Collapsing CRT A-setup into Ultron SIGNAL alerts  
- Replacing monitor JSON as source of truth  

---

## 6. One-line synthesis

**Telegram is already incorporated for execution/kill notifications via `TelegramBridge` + HookedLiveEngine (submit XOR off on paper). The live-alert spine is a separate CRT research channel that stops at JSON/monitor/Grok — joining them needs a dry-run research bridge (REM-TG-01..04), not flipping the order XOR.**

---

## 7. REM-TG-01 implemented (2026-09-17)

- `TelegramBridge.send_research_alert(text)` — free-form research path (not BUY/SELL)
- `scripts/research/live_alert_telegram_bridge.py` — forced dry_run by default; TG-02 format; TG-04 fingerprints
- Smoke: `results/live_alert_telegram_dryrun_20260917/` — 3 dry messages OK, 0 HTTP
- Watch routine updated to call dry-run bridge (REM-TG-03 light)
- Still open: authorize live send (`--allow-live-send` only with tokens + explicit yes)

### 2026-09-17 — REM-TG-05 env wire

- Research bridge prefers `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` (process env or ROOT/.env)
- `TelegramBridge.from_env()` + `from_prod_config()` falls back to those env keys when JSON tokens empty
- `--allow-live-send` refuses unless both env keys set; default remains forced dry_run
