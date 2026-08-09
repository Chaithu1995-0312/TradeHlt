# Run backtest_v2 on BNBUSDT + trace in/out (gate-ON)

## Context
The user wants to execute the CRT backtest harness (`src/runtime/backtest_v2.py`) on BNBUSDT and
**trace every trade's entry ("in") and exit ("out")**, delivered two ways (their choices):
1. **Per-trade in/out ledger** — the literal trade-by-trade lifecycle.
2. **Pipeline flow map** — which module emitted each in/out along candle→order.

And the trace must reflect the **gate-ON 4-engine fusion** path (CRT/Gaussian/ZoneGate/RR fusion
vetoes applied — live-equivalent), not the CRT-only research default.

This is an **operational run + report** task — no code changes. It is governed by §4.0
(ORIENT_RUNTIME, done below) and produces artifacts under `results/` + `logs/`.

### Runtime truth (ORIENT_RUNTIME, already resolved)
- `configs/production/ACTIVE_VERSION` → **`v2_multi_2026_04`** (matches F-016; loads on this branch).
- Data file: **`data/BNBUSDT_M15.csv`** (present).
- Engine gate: code default is **ON** (`os.getenv("BACKTEST_ENGINE_GATE", "1")`,
  [backtest_v2.py:1838](src/runtime/backtest_v2.py#L1838)); `.env` forces it to `0` for research
  (F-037). The `.env` loader **does not overwrite an already-set env var**
  ([llm_inference_client.py:61](src/config_layer/llm_inference_client.py#L61)), so a shell-set
  `BACKTEST_ENGINE_GATE=1` wins → gate-ON without editing `.env`.
- Expected volume: ~**11 BNBUSDT trades** gate-ON (vs ~13 gate-OFF), per F-037.
- Note: `BNBUSDT` is absent from `MultiInstrumentRunner.INSTRUMENT_PIP`
  ([backtest_v2.py:2563](src/runtime/backtest_v2.py#L2563)) → `pip_size` defaults to `0.0001`.
  This only scales the *pip* figures; **R-multiples (`pnl_rr_net`) are ratio-based and unaffected** —
  so the in/out ledger uses R, not pips.

## Execution steps

### 1. Run the backtest (gate-ON)
PowerShell (primary shell); set the env var in-session so `.env`'s `0` can't clobber it:
```powershell
$env:BACKTEST_ENGINE_GATE = "1"
python src/runtime/backtest_v2.py --csv data/BNBUSDT_M15.csv --instrument BNBUSDT `
  --output results/backtest/BNBUSDT_gateON_2026_07_04
```
- Keep `--scorer calibrated` (default; phase-5 GaussianNB gate) unless a CRT-pure run is wanted.
- **Confirm gate-ON** by grepping the run log / stdout for:
  `EngineRunner gate wired into backtest path (BACKTEST_ENGINE_GATE=1)`
  ([backtest_v2.py:1847](src/runtime/backtest_v2.py#L1847)). If that line is absent, the run
  silently fell back to CRT-only — stop and fix before reporting.

### 2. Locate artifacts (written by `ResultsWriter.write_all`, [backtest_v2.py:1419](src/runtime/backtest_v2.py#L1419))
Under `results/backtest/BNBUSDT_gateON_2026_07_04/`:
| File | Use in trace |
|---|---|
| `BNBUSDT_events.jsonl` | **primary in/out stream** — CRT state transitions + `TRADE_OPENED`/`TRADE_CLOSED` |
| `BNBUSDT_trades.csv` | **ledger source** — one row per closed trade (entry_raw/fill, sl, tp1/tp2, exit_fill, exit_reason, opened_at/closed_at, pnl_rr_net, state_path, session, live_atr, cached_*) |
| `BNBUSDT_summary.json` | run totals (trades, WR, avg R, PF, DD) for the report header |
| `BNBUSDT_crt_telemetry.jsonl` | CRT funnel counts (context for why N trades) |
| `BNBUSDT_report.txt` | harness' own text summary |
| `logs/backtest_debug.log` | persistent `CLOSE \| ...` lines (survives stdout swallowing) |
| `logs/.../BNBUSDT_fusion.jsonl` | fusion decision per entry (gate-ON only) — confirms fusion actually ran |

### 3. Deliverable A — Per-trade in/out ledger
Parse `BNBUSDT_trades.csv` (+ cross-check `BNBUSDT_events.jsonl`) into one line per trade:
- **IN:** trade_id · opened_at · direction · entry_raw→entry_fill · SL · TP1/TP2 · session ·
  CRT `state_path` (e.g. RANGE→SWEEP→DISPLACEMENT→EXPANSION→RETEST→EXECUTION) · live_atr ·
  bitnet_score_at_entry · shadow_used.
- **OUT:** closed_at · exit_fill · **exit_reason** (TP1/TP2/SL/TTL/gap) · duration_candles ·
  **pnl_rr_net** (the governing R) · capital_after.
- Footer: totals from `summary.json` — approved trades, win rate, avg R, PF, net R, max DD,
  and the fusion-veto count (entries the 4-engine gate rejected vs CRT-only).

### 4. Deliverable B — Pipeline flow map (where each in/out fires)
Annotate the candle→order path with the module/line that emits each in/out
(per `docs/architecture/signal-flow.md`; gate-ON path):
```
CandleLoader.stream()            ── candle IN (CSV → Candle)           backtest_v2.py:704
  → FeaturePipeline.run()        ── 38-dim feature vector             backtest_v2.py:1632
  → CRTEngine.process()          ── state machine → TRADE_OPENED       (EXPANSION→RETEST→EXECUTION)
  → EngineRunner.run() [GATE-ON] ── adapter→fusion→dual→decision veto  backtest_v2.py:2167
  → TradeJournal.on_trade_opened ── "IN": fill+slippage+SL/size        backtest_v2.py:2216 / 858
  → (bars stream; path MFE/MAE)  ── observe_open_bar                   backtest_v2.py:829
  → TradeJournal.on_trade_closed ── "OUT": exit fill, R, capital       backtest_v2.py:938
  → ResultsWriter.write_all      ── events.jsonl + trades.csv          backtest_v2.py:1419
```
Map each ledger trade's IN to the `TRADE_OPENED` event and OUT to `TRADE_CLOSED`, and note any
entries **vetoed by the fusion gate** (`_engine_vetoed`, [backtest_v2.py:2183](src/runtime/backtest_v2.py#L2183))
— those are the gate-ON delta vs the CRT-only spine (the point of running gate-ON).

## Verification
- Gate-ON confirmed via the `BACKTEST_ENGINE_GATE=1` log line **and** presence of a non-empty
  `BNBUSDT_fusion.jsonl`.
- Ledger trade count == `summary.json.approved_trades` == number of `TRADE_CLOSED` events (no
  orphan open trade; the harness force-closes at run end, [backtest_v2.py:2400](src/runtime/backtest_v2.py#L2400)).
- Every ledger row's `pnl_rr_net` and `exit_reason` reconcile with `logs/backtest_debug.log`
  `CLOSE |` lines.
- Sanity vs findings: ~11 trades gate-ON, net expectancy negative/near-zero (BNB has no edge under
  realistic exits — F-025/F-036/F-037); this run is a **trace demonstration**, not an edge claim.

## Out of scope / notes
- No config, `.env`, or code edits — env var is set transiently in the shell for this run only.
- Do **not** register findings; this is operational tracing (Authority Ladder: information only).
- Append the §6 SESSION LOG entry to `assistant_project.md` on completion.
