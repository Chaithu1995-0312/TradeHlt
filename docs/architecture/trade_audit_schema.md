# Canonical Trade Audit Schema

> **Status:** authoritative reference for mapping every per-trade / per-event / per-run
> column on disk to its source `file:line`, plus real worked rows for the Grok handoff.
> This document is a *pointer* and a *mapping*, not an implementation of feature math —
> the canonical formulas live in the code paths it cites. When code drifts, update the
> citations here, never re-derive local math.

**Verification stamp:** all `file:line` citations below were read directly from the repo at
branch `grokbotchanges` (HEAD `c27d69e`). Line numbers are for that snapshot.

---

## 1. Scope — the three lanes that reach disk

There are three distinct write-lanes. Column-truth differs per lane; mixing them is the #1
source of wrong claims.

| Lane | Writer (file:line) | Artifacts | Writes exits? |
|---|---|---|---|
| **Backtest ledger** | `src/runtime/backtest_v2.py` — `TradeJournal` (1077), `to_csv_rows()` (1298), `_write_trades` (1802) | `{SYM}_trades.csv`, `{SYM}_events.jsonl`, `{SYM}_summary.json`, `{SYM}_report.txt` | **YES** — full realized PnL/R, exit reason+time+price |
| **CRT telemetry** | `crt_engine_v2.py` state machine + `crt_telemetry.jsonl` | `{SYM}_crt_telemetry.jsonl` | State/transition counts; carries `crt_state`, `resolution` |
| **Live hook** | `src/runtime/live_engine_hook.py` (1033-1125) | logs only — **no trade journal, no exit ledger** | **NO** for exits/R; plan-time fields yes |

**Consequence (correction to the prior draft):** "no exit / no realized R / no cost model /
no aggregation" is **only true for the live path**. All four exist and land on disk for the
backtest. The genuinely missing piece is a **live `TradeJournal`**.

---

## 2. Canonical trade identity — three ID systems coexist

| System | Format | Producer | Where it lives |
|---|---|---|---|
| `EX_…` | md5-derived execution id | ExecutionPlannerV1_2 `plan()` | live planner / gate output — **not on the trades.csv row** |
| `CRT-####` / uuid4-hex | `TradeRecord.trade_id` via `TradeIdentityV1` (`src/journal/trade_identity_v1_0.py`) | backtest runner open | **trades.csv `trade_id`** (e.g. `CRT-0001`) |
| `_spine_entries` parquet keys | spine-entry trade keys | `results/research/_spine_entries/*.parquet` | research lane only |

**Rule for any report:** pick **one** canonical id and join through the events/telemetry lane.
The on-disk ledger id (`CRT-####`) is the only one on the financial row. The draft used the
`EX_` id as "trade_id" — that differs from the ledger id.

---

## 3. Column → source map for `XAUUSD_trades.csv`

Writer: `TradeJournal.to_csv_rows()` (`src/runtime/backtest_v2.py:1298-1371`), header derived
from `rows[0].keys()` (`_write_trades`, :1802-1815). Values originate in the `TradeRecord`
dataclass (`:376+`) and are filled at close (`_close_trade`, ~:1230-1289).

### 3.1 Core financial row (cols 1-28)

| CSV column | TradeRecord field | Source file:line | Derivation / notes |
|---|---|---|---|
| `trade_id` | `trade_id` | to_csv_rows:1302; field :377 | canonical id (see §2) |
| `instrument` | `instrument` | :1303; :378 | symbol, e.g. `XAUUSD` |
| `direction` | `direction` | :1304; :379 | `LONG`/`SHORT` |
| `entry_raw` | `entry_price_raw` | :1305; :381 | engine entry, no costs |
| `entry_fill` | `entry_price_fill` | :1306; :386 | `entry_raw + e_slip + spread_half` — `SlippageModel.compute_fill_prices` :587 |
| `sl` | `sl_price` | :1307; :383 | stop level |
| `tp1` | `tp1_price` | :1308; :384 | take-profit 1 |
| `tp2` | `tp2_price` | :1309; :385 | take-profit 2 |
| `exit_fill` | `exit_price_fill` | :1310; :387 | `exit_raw + x_slip − spread_half` — :588 |
| `exit_reason` | `exit_reason` | :1311; :388 | resolved by `_resolve_exit` :1498-1550 (see §3.3) |
| `opened_at` / `closed_at` | `opened_at`/`closed_at` | :1312-1313; :389-390 | ISO timestamps |
| `duration_candles` | `duration_candles` | :1314 | bars open→close |
| `pnl_pips_raw` | `pnl_pips_raw` | :1315; :1244 | `price_move_raw / pip_size`; `price_move_raw` :1239-1240 |
| `pnl_pips_net` | `pnl_pips_net` | :1316; :1245 | `price_move_net / pip_size`; `price_move_net` :1241-1242 |
| `pnl_rr_raw` | `pnl_rr_raw` | :1317; :1248 | `pnl_pips_raw / risk_pips` |
| `pnl_rr_net` | `pnl_rr_net` | :1318; :1249 | **the number to use.** `pnl_pips_net / risk_pips` |
| `slippage_pips` | `slippage_pips` | :1319; :1252-1253 | `\|entry_fill−entry_raw−spread_half\| + \|x_slip\|` over pip |
| `spread_pips` | `spread_pips` | :1320; :1254 | round-trip `2×spread_half` over pip |
| `capital_before` / `capital_after` | same | :1321-1322; :1277-1278 | capital curve around the trade |
| `position_size` | `position_size` | :1323 | final units (gate output on live path; see §5) |
| `risk_score` | `risk_score` | :1324 | gate/risk score at open |
| `session`, `day_of_week`, `hour_of_day` | same | :1325-1327 | session bucket (NEWYORK/LONDON…), DOW, UTC hour |
| `htf_id` | `htf_id` | :1328 | HTF range id (e.g. `XAUUSD-HTF-000714`) |
| `candle_idx` | `candle_open` | :1329 | open candle index |

### 3.2 Feature batch + audit (cols 29-end)

| CSV column group | Source file:line | Notes |
|---|---|---|
| 48 canonical features | `row.update(r.features)` :1332 | timestamp-keyed batch feature vector. **On this artifact 46 columns** appear verbatim: `open,high,low,close,volume,volume_ratio,double_sweep,ema_fast,ema_slow,ema_spread,trend_bias,trend_strength,momentum_score,atr,volatility_ratio,rsi_14,macd_line,macd_signal,macd_hist_raw,macd_hist_z,sweep_detected,liquidity_sweep,break_of_structure,swing_high,swing_low,higher_high,lower_low,body_size,candle_range,body_ratio,volatility_regime,disp_strength,retest_depth,candles_since_retest,liquidity_distance,liquidity_pressure_score,volume_spike,order_block_distance,fvg_distance,breaker_distance,mitigation_block_distance,pdh_distance,pdl_distance,eqh_distance,eql_distance,change_of_character` |
| `live_atr` … `live_ema_slow` | :1354-1356 | engine-live metrics (non-zero when trade fires) |
| `cached_retest_depth` … `cached_double_sweep` | :1357-1361 | cached CRT state at entry |
| `bitnet_score_at_entry` / `bitnet_decision_at_entry` | :1363-1364 | adaptive threshold audit |
| `config_version` | :1365 | e.g. `v2_htfcrt_2026_08` |
| `shadow_used` | :1366 | shadow/REM flag int |

> **Discrepancy worth flagging to Grok:** current `to_csv_rows` also appends
> `cost_model_id`, `cost_model_params_hash`, `risk_denominator_id` (:1367-1369) to each row.
> The **Sep-09-2026 on-disk header ends at `shadow_used`** — it was written before (or by a
> variant without) those identity columns. Do not claim those three columns exist in that
> specific artifact.

### 3.3 Exit-reason resolution (backtest)

`_resolve_exit(action, t, trade_status, candle, …)` — `backtest_v2.py:1498-1550`.

| Action when closed | Result `exit_reason` | Book price |
|---|---|---|
| TP1 | `TP1` | `tp1_price` |
| TP2 (runner) | `TP2` | `tp2_price` |
| `TRADE_TP2_*` while already `TP1` | `TP1_TP2` | `f·tp1 + (1−f)·tp2` |
| `…_STOPPED` after TP1 | `TP1_BE_STOP` | `f·tp1 + (1−f)·be` |
| STOPPED (SL) | `STOPPED` | `sl_price` |
| `TRADE_STOPPED_STRUCTURAL` after TP1 | `TP1_STRUCTURAL_STOP` | `f·tp1 + (1−f)·close` |
| structural kill otherwise | `STOPPED_STRUCTURAL` | `candle.close` |

Lifecycle source (CRT executor, `src/config_layer/crt_engine_v2.py`):
`open_trade` :2466-2469; `update_trade` :2471-2530 (priority **TP2 > SL > TP1**, partial-close
at 50%, semi-trail `entry + 0.5·(TP1−entry)` at :2524, breakeven runner after TP1); `close_structural`
:2532-2551 (books at **bar close**, never displacement origin — SEM-021).

---

## 4. Events + telemetry lanes

### 4.1 `{SYM}_events.jsonl` — `_write_events` (`backtest_v2.py:1817-1825`)
Records from the CRT state machine (`crt_engine_v2.py`). Observed schema:
`event, timestamp, candle_index, state_from, state_to, direction, price, reason, metadata`.
Seen kinds include `RESET` (HTF change / gap — `GapDetector` :598), `SWEEP`, plus trade open/close events.

### 4.2 `{SYM}_crt_telemetry.jsonl`
State/expansion telemetry. Observed kinds: `TRANSITION_COUNTER`, `EXPANSION_RETRACE_CHECK`, …
`state_entry_counts` here is where `crt_state`/`RESOLUTION` funnel lives — **not** on the
trades.csv row (see §6).

### 4.3 `{SYM}_summary.json` / `{SYM}_report.txt`
Written by `_write_summary` (:1786-1800) / `_write_report` (:1827). Aggregation by
`MetricsEngine.compute` (`backtest_v2.py:1573-1615`): wins/losses, `tp1_hits`/`tp2_hits`,
`total_pnl_rr_raw/net`, `avg_trade_duration`, `max_drawdown_rr`, streaks, `monthly_pnl`,
---

## 5. Live-path sizing / RR — not "inferred," but sourced in code

| Quantity | Source file:line | Formula |
|---|---|---|
| `position_size_hint` | `live_engine_hook.py:1090-1095` | `round((balance×risk_percent/100)/risk_dist, 4)` |
| `rr_ratio` / `rr_ratio_tp2` | `live_engine_hook.py:1077-1088` | from SL/TP geometry, `rr_source="sl_tp_geometry"` |
| SL/TP levels | `live_engine_hook.py:1055-1073` | per-intent `tp1_*` (breakout 1.5 / liq_sweep 1.2 / pullback 0.8 / reversal 1.0), `tp2=2.0`; `_atr_abs = atr×close` :1059 → `compute_crt_levels` :1060 |
| `final_position_size` | `ultron_risk_gate.py:326-344` (evaluate at :160) | `allowed_risk=min(risk_percent, max_risk_per_trade_pct)` :293-295; `risk_usd = balance×allowed/100`; `final=min(hint, risk_usd/\|entry−sl\|)` |
| account_balance | threaded: `live_engine_hook.py:1017-1022` | present in context + portfolio_state; **not echoed by `plan()`** (cosmetic, TRUE) |
| cost model inside gate | `ultron_risk_gate.py:233-249` | `rr_ratio −= (spread+slippage)·pip_size / sl_distance`; backtest default 0.0 |

**Gate wrapper:** `ultron_risk_gate_wrapper.py` (SR-1) pre-scales `risk_percent` by regime
factor (trend 1.0 / range 0.8 / neutral 0.6 / uncertain 0.5) then **always** delegates to the
real gate (invoked from `live_engine_hook.py:1168`).

---

## 6. Genuinely unreportable from disk today (live-path gaps)

| Missing on disk | Where it should come from | Status |
|---|---|---|
| `execution_id` / `trade_intent` / gate component scores on the per-trade row | planner+gate (live) | absent from trades.csv |
| `crt_state` entry state + `resolution_site` on the row | CRT resolver / telemetry | in `crt_telemetry.jsonl`, not the row |
| live-path exit + realized R | a live `TradeJournal` (**does not exist**) | live is log-only |
| `account_balance` echo / risk-$ in dollars | context | absent from trades.csv (only `risk_score` + `position_size` + capital) |

---

## 7. Real worked rows (Grok handoff block)

Source artifact (verbatim): `logs/dual_construction_f069_remeasure_20260909/scratch_roots/arm_a_v2_baseline/results/run_20260909_182035_XAUUSD/XAUUSD_trades.csv`

**Header (on disk, ends at `shadow_used`):**
```
trade_id,instrument,direction,entry_raw,entry_fill,sl,tp1,tp2,exit_fill,exit_reason,opened_at,closed_at,duration_candles,pnl_pips_raw,pnl_pips_net,pnl_rr_raw,pnl_rr_net,slippage_pips,spread_pips,capital_before,capital_after,position_size,risk_score,session,day_of_week,hour_of_day,htf_id,candle_idx,<46 canonical features>,live_atr,live_ema_fast,live_ema_slow,cached_retest_depth,cached_body_ratio,cached_disp_strength,cached_session,cached_double_sweep,bitnet_score_at_entry,bitnet_decision_at_entry,config_version,shadow_used
```

### Worked row CRT-0001 (STOPPED, annotated)
```
trade_id=CRT-0001  instrument=XAUUSD  direction=LONG
entry_raw=2614.46  entry_fill=2615.082684588  sl=2610.047571429
tp1=2618.872428571  tp2=2623.284857143
exit_fill=2609.772004593  exit_reason=STOPPED
opened_at=2024-11-12T15:30:00  closed_at=2024-11-12T15:45:00  duration_candles=1
pnl_pips_raw=-441.2  pnl_pips_net=-531.1  pnl_rr_raw=-0.8763  pnl_rr_net=-1.0547
slippage_pips=37.59  spread_pips=52.23
capital_before=100000.0  capital_after=98945.27  position_size=198.61  risk_score=0.5728
session=3.0  day_of_week=1  hour_of_day=15.0  htf_id=XAUUSD-HTF-000714  candle_idx=11427
config_version=v2_htfcrt_2026_08  shadow_used=0
```
**Footed math** (pip = 0.01 for XAUUSD):
- `price_move_net = exit_fill − entry_fill = −5.31068` → `pnl_pips_net = −5.31068 / 0.01 = −531.1` ✓
- `price_move_raw = sl − entry_raw = −4.41243` → `pnl_pips_raw = −441.2` ✓
- **R denominator = `\|entry_fill − sl\| / pip = 5.03511 / 0.01 = 503.5 pips`** (NOT `\|entry_raw−sl\|`)
- `pnl_rr_net = −531.1 / 503.5 = −1.0547` ✓ · `pnl_rr_raw = −441.2 / 503.5 = −0.8763` ✓
- Capital: `Δ = position_size × pnl_per_unit = 198.61 × −5.31068 = −1054.6` → `98945.27` ✓

### Row CRT-0002 (STOPPED)
```
CRT-0002,XAUUSD,LONG,2565.48,2565.795144948,2564.559857143,2566.860214286,2567.320285714,2564.250491678,STOPPED,2024-11-15T07:45:00,2024-11-15T08:00:00,1,-92.0,-154.5,-0.7449,-1.2504,11.3,51.15,98945.27,97708.02,800.99,0.4871,1.0,4,7.0,XAUUSD-HTF-000729,11672,<46 feats…>
```

### Row CRT-0003 (TP2 winner)
```
CRT-0003,XAUUSD,LONG,2934.39,2935.02626272,2933.209857143,2936.160214286,2936.750285714,2936.139410026,TP2,2025-02-25T15:45:00,2025-02-25T16:15:00,2,236.0,111.3,1.2994,0.6128,65.86,58.86,97708.02,98306.8,537.92,0.5649,3.0,1,15.0,XAUUSD-HTF-001130,18092,<46 feats…>
```

**Corroborating aggregate (summary.json):** approved=3, wins=1 (33.3%),
`total_pnl_rr_net=-1.6923`, `avg_rr_net=-0.5641`, `max_drawdown_rr=2.3052`, `tp1_hits=1`,
`tp2_hits=1`, capital 100000 → 98306.8 (−1.69%). `cost_analysis`: total_slippage_pips=114.75,
total_spread_pips=162.24, avg_cost_per_trade=92.33, raw-vs-net R delta=+1.3706.

---

## 8. Grok verification checklist (do all before claiming)

1. [ ] Read `TradeRecord` (`backtest_v2.py:376+`) and `to_csv_rows` (:1298-1371).
2. [ ] Confirm **R denominator = `\|entry_fill − sl\|/pip`** (:1247-1249), not `\|entry_raw−sl\|`.
3. [ ] Confirm same-run `_events.jsonl` + `_crt_telemetry.jsonl` + `_summary.json` exist (they do), and that the `trades.csv` header here **lacks** `cost_model_id` etc.
4. [ ] Grep for a **live** `TradeJournal` — none exists; live path is log-only.
5. [ ] Do **not** relabel `CRT-####` with the `EX_` planner id.