# PRE-REMEDIATION BASELINE

**Status:** FROZEN observational baseline (no remediation, no tuning)  
**Date (UTC):** 2026-07-09T07:29:48Z  
**Branch:** `feature/truth-registry-v2`  
**Purpose:** Reproducible behavioral snapshot of the repository **before Gate 6 remediation**.

---

## 1. Entry point & production-path fidelity

### BASELINE_ENTRY_POINT

```text
python src/runtime/backtest_v2.py --csv data/BNBUSDT_M15.csv --instrument BNBUSDT --output results/baseline
```

Canonical harness: `src/runtime/backtest_v2.py` → `BacktestRunner.run()` → CRT state machine + optional EngineRunner gate.

### PRODUCTION_PATH_FIDELITY

| Aspect | Assessment |
|---|---|
| Config | Loads active production config via `ACTIVE_VERSION` → `v2_multi_2026_04` |
| CRT engine | Same `CRTEngine.process_candle()` spine as live |
| Features | Batch `FeaturePipeline` 38-dim vectors, timestamp-keyed |
| Exit model | `intrabar_touch` from `crt_engine.exit_model` |
| Slippage / spread | Production `backtest` section (seeded slip + 2 bps spread) |
| EngineRunner fusion gate | **Must be forced ON** for live-equivalent fusion (see caveat) |

**Critical env caveat (observed):** importing the backtest stack loads `.env` and sets `BACKTEST_ENGINE_GATE=0` (F-037 research isolation). The **bare** CLI command therefore runs **CRT-only** (13 BNB trades, 0 EngineRunner rejections).

**Official baseline command (production-fidelity, gate ON):**

```powershell
$env:PYTHONPATH = "D:\Tradelatest\src"
$env:BACKTEST_ENGINE_GATE = "1"
python src/runtime/backtest_v2.py --csv data/BNBUSDT_M15.csv --instrument BNBUSDT --output results/baseline
```

Python used: `venv\Scripts\python.exe` (3.14.3).  
`BACKTEST_BYPASS_ZONE_INVALID` left at code default `"1"` (zone_gate_invalid bypass in backtest only).

---

## 2. Pinned identities

| Pin | Value |
|---|---|
| **PINNED_COMMIT** | `ed1e418e47489dc8d76a2f7cc4e0cd340348b661` |
| **WORKTREE_STATE** | **DIRTY** (~358 porcelain lines; not clean). Runtime-affecting dirty paths include `src/core/engine_runner.py`, `src/config_layer/crt_engine_v2.py`, `src/features/*`, `configs/production/v2_multi_2026_04.json`, `models/zone_gate_registry.json` |
| **CONFIG** | `v2_multi_2026_04` (`configs/production/ACTIVE_VERSION`) |
| **Config file** | `configs/production/v2_multi_2026_04.json` |
| **Config SHA-256** | `8f45c66c1175cf87c3a1ddd2c01c715d84e14f7b3ab1fdb4dd31f9dc58e778ae` |
| **Embedded config_hash** | `7de09f6233b712f0136fc1bf1d2a51322b5b7c65395c75b035d0f96db689d613` |
| **CORPUS** | `data/BNBUSDT_M15.csv` |
| **Corpus SHA-256** | `083f2bdf32b917648f36bd7596c97c0b5702c06aebef7b80df80219618bcddce` |
| **DATA_RANGE** | `2024-05-22 00:00:00` → `2026-05-21 23:45:00` (70,080 rows; pipeline keep 70,002 after 78 drop) |
| **Random seed** | `slippage_seed=42` (production `backtest` section) |
| **Run artifact dirs** | `results/baseline/run1/` · `results/baseline/run2/` (byte-identical) · diagnostic gate-OFF: `results/baseline/gate_off_bare_command/` |

### MODEL_ARTIFACTS

| Artifact | Path | Active on this path? | SHA-256 |
|---|---|---|---|
| Zone registry | `models/zone_registry.json` | Yes (`zone_mode=hard`, 8 zones loaded) | `e73e08934add02c98aa6ab19e70230af09368a19af601de9d852dc1e3639eda3` |
| Zone gate manifest | `models/zone_gate_registry.json` | Manifest only (runtime loads zone_registry) | `e6d36474edce31a7d6b99cdcd5ffb683186f055d2dacf398606f4068b4387c09` |
| RR model | `models/rr_model.json` | No (`rr_fusion.enabled=false`) | `6ed92d26ff612538a590813af417d2c9380b340cd39a1485aa69f46564c9cd66` |
| Gaussian | Heuristic 3-feature (`gaussian_impl=heuristic`) | Yes | code-path (registry note: `p5_20260524T120449`) |
| BitNet | — | No (`use_bitnet=false`) | n/a |
| Calibrated CRT scorer | ModelRegistry | NoOpScorer (“no active gaussian registered”) | n/a |

### EXECUTION_SEMANTICS

| Knob | Value |
|---|---|
| Exit model | `intrabar_touch` (intrabar SL/TP touch; **not** close-only) |
| Slippage | ON · Uniform adverse · `slippage_atr_fraction=0.1` · seed `42` |
| Spread | `simulated_spread_pct=0.0002` (2 bps) |
| Capital | `100000` · risk `1%` · compounding ON |
| Gap reset | ON · 120 minutes |
| HTF / warmup | `htf_candles_per_range=4` · `warmup_candles=30` |
| Ultron risk gate (EngineRunner) | `ultron_gate_enabled=false` (legacy dual-engine pass-through still active) |
| DecisionEngine | `score_threshold=0.45` · `rr_threshold=1.5` · `p_win_threshold=0.4` |

---

## 3. Runtime rejection funnel (actual ordering)

Discovered from `BacktestRunner.run()` + `EngineRunner.run()` (not assumed):

```text
candle stream
  → CRT internal filters (session / score / inverted-SL / etc.)
  → CRT state machine:
       RANGE → SWEEP → DISPLACEMENT → EXPANSION → RETEST → EXECUTION
       (+ SHADOW_PENDING, EXPIRED branches)
  → on TRADE_OPENED action only:
       → drift_cooldown (if paused)
       → Phase-5 scorer gate (p_win < 0.35)   [NoOpScorer here → inert]
       → FeatureMonitor hard_drift_veto
       → EngineRunner gate (when BACKTEST_ENGINE_GATE=1):
            adapter → engines(CRT/Gaussian/Zone/RR) → fusion
            → dual/ultron-legacy → DecisionEngine → (return)
       → if not vetoed: journal.on_trade_opened() → later exit (intrabar_touch)
```

**Note:** EngineRunner is a **post-CRT veto** on candidates, not a per-candle sole decision authority in this harness.

---

## 4. Run results (official = gate ON)

### RUN_1_RESULT / RUN_2_RESULT

Both runs (gate ON, same command):

| Metric | Value | Classification |
|---|---|---|
| Total candles | 70,080 | measured |
| Feature rows after pipeline | 70,002 | measured |
| CRT state visits (funnel_counts) | see below | measured |
| CRT `TRADE_OPENED` events | 13 | measured (events.jsonl) |
| **Candidates into post-CRT gates** | **13** | measured |
| Phase-5 rejects | 0 | measured (NoOpScorer) |
| Drift cooldown / hard veto | 0 | measured |
| EngineRunner journal rejects | **2** | measured |
| **Journal approved trades (TRADE_COUNT)** | **11** | measured |
| Wins / losses | 3 / 8 | measured |
| Win rate | 27.27% | measured |
| Avg RR net (expectancy) | **−0.3865 R** | measured |
| Total PnL raw / net | −2.633 R / **−4.251 R** | measured |
| Profit factor | **0.509** | measured |
| Gross win / gross loss | +4.4065 R / −8.6575 R | measured |
| Avg win / avg loss | +1.4688 R / −1.0822 R | measured |
| Max drawdown (R) | 5.7318 R | measured |
| Max drawdown (% equity) | 5.63% | measured |
| Trades per month | 0.4583 | measured |
| Avg trade duration | 3.4 candles | measured |
| Exit reasons | STOPPED 9 · TP2 2 | measured |
| Score→outcome corr | 0.5922 | measured |
| Goal report (G001) | FAIL | measured (measure-only) |
| Final capital | 95,758.16 | measured |
| Total return | −4.24% | measured |

### CRT funnel / state distribution

| State | Count |
|---|---:|
| RANGE | 49,274 |
| SWEEP | 9,179 |
| DISPLACEMENT | 460 |
| SHADOW_PENDING | 54 |
| EXPANSION | 10,977 |
| RETEST | 47 |
| EXECUTION | 43 |
| EXPIRED | 16 |

CRT selection attrition (illustrative ratios on counts):  
RETEST 47 / SWEEP 9,179 ≈ 0.5%; EXECUTION visits 43; journaled trades 11.

### Rejection counts & rates (post-CRT journal)

| Reason | Count | Rate of 13 candidates |
|---|---:|---:|
| `engine_runner:adapter:invalid_session:0.0` | 2 | 15.4% |
| `P5_SCORE_LOW:*` | 0 | 0% |
| `drift_cooldown` / `hard_drift_veto` | 0 | 0% |
| `engine_runner:*:low_rr` | **0** | 0% (not observed in journal) |

CRT-internal (log-only, **not** in `rejection_reasons`): inverted-SL rejects observed **3×** in console (`Trade REJECTED: inverted SL`).

### Decision distribution

| Layer | Observation |
|---|---|
| Journal approve / reject | 11 / 2 (approval rate 84.6% of CRT candidates) |
| Session of trades | all session code `1.0` (LONDON/NEWYORK mapping in report: LONDON 7 / NEWYORK 6) |
| Direction | LONG 7 · SHORT 4 |
| EngineRunner `decision==execute` aggregate | **MISSING** — summary does not expose ER decision histogram |
| Inferred non-vetoed CRT candidates | 11 (journal opens) |

### Score distributions (where available)

| Score | n | min | max | mean |
|---|---:|---:|---:|---:|
| `risk_score` (trade CSV) | 11 | 0.3712 | 0.5710 | 0.4761 |
| `bitnet_score_at_entry` | 11 | 0.0 | 0.0 | 0.0 (BitNet off) |
| Fusion/engine score histogram over all candles | — | — | — | **MISSING** (not in summary; only per-reject console samples) |

### EXECUTE_COUNT

| Definition | Value | Notes |
|---|---|---|
| Journal trades opened after all gates | **11** | this is the operational trade admit count |
| EngineRunner `decision=="execute"` count | **MISSING** | infrastructure does not aggregate this in `*_summary.json` |
| Zero-trade path | n/a | trades **did** occur → trade metrics are computable |

Because `trade_count > 0`, profitability metrics are reported as measured values (negative expectancy). This is a **baseline observation**, not a promotion claim.

---

## 5. Dominant rejection / absorbing stages

1. **CRT structural funnel (pre-candidate):** vast majority of candles never reach RETEST/EXECUTION (RANGE/SWEEP/EXPANSION dominate). Primary throughput bottleneck is CRT selection, not EngineRunner.
2. **Among CRT TRADE_OPENED candidates (n=13):**
   - Dominant **journaled** EngineRunner reject: **`adapter:invalid_session`** (2/13).
   - Dominant **admit** path: 11/13 journaled after EngineRunner (no `low_rr` in journal).
3. **CRT-internal inverted SL** (3 log events) aborts some EXECUTION attempts before journal.

---

## 6. F-048 reproduction

| Check | Result |
|---|---|
| Isolated `DecisionEngine.evaluate` with polarity `rr∈(0,1]` vs `rr_threshold=1.5` | **Rejects `low_rr`** (source-confirmed this session) |
| This baseline’s journal `engine_runner:*:low_rr` count | **0** |
| Journal trades after EngineRunner gate | **11** |
| Per-candle `EngineRunner.run()` over full corpus (F-048’s 0/70,002 frame) | **NOT run** |

**F048_REPRODUCED = NO** for the plan’s expected baseline signature (`execute_count==0` / trade-blocking under gate-ON CRT candidates).

**Nuance (not a finding flip):** F-048’s **mechanism** (polarity vs `rr_threshold=1.5`) remains source-true in isolation. This harness did **not** surface `low_rr` as the absorbing journal reason; observed ER absorbs were `invalid_session`. Whether the 11 admits are true `execute` returns vs fail-soft exception-allow is **MISSING** from exported metrics (would need instrumented decision logging). **No finding update** — evidence is harness-scoped, not a clean F-048 reversal (E-001).

Consistent with **F-037**: gate OFF → 13 trades; gate ON → 11 trades (Δ = −2, matching the two `invalid_session` rejects).

---

## 7. Deterministic equality

| Artifact | Run1 SHA-256 | Run2 equal? |
|---|---|---|
| `BNBUSDT_summary.json` | `d32c75e2de63ea3afd29e60d8392e1424a27ed6d4a3ac3d7c8ed1e0ef07d3bd1` | **YES** |
| `BNBUSDT_trades.csv` | `aab9783b0e78be6303695b31b61f75b388d98d11d9adfdd0654f955251fac1f3` | **YES** |
| `BNBUSDT_report.txt` | equal | **YES** |
| `BNBUSDT_events.jsonl` | equal | **YES** |
| Summary key-walk diff count | 0 | **YES** |

**DETERMINISTIC_EQUALITY = YES** (decisions + report metrics byte-identical across two identical commands).

---

## 8. Diagnostic: bare command (gate OFF via .env)

Not the official baseline; recorded for fidelity honesty:

| Metric | Gate OFF (bare) | Gate ON (official) |
|---|---:|---:|
| Trades | 13 | 11 |
| PnL net | −4.646 R | −4.251 R |
| ER rejects | 0 | 2 |
| WR | 30.8% | 27.3% |

Artifacts: `results/baseline/gate_off_bare_command/`.

---

## 9. Exact reproducibility command

```powershell
cd D:\Tradelatest
$env:PYTHONPATH = "D:\Tradelatest\src"
$env:BACKTEST_ENGINE_GATE = "1"
# optional pin: ensure no other BACKTEST_* overrides
venv\Scripts\python.exe src\runtime\backtest_v2.py --csv data\BNBUSDT_M15.csv --instrument BNBUSDT --output results\baseline
```

**Expected (this worktree):** 11 trades · WR 27.3% · AvgRR −0.39R · PnL net −4.25R · MaxDD 5.6% · 2× `engine_runner:adapter:invalid_session:0.0`.

**Reproducibility warning:** worktree is dirty relative to `ed1e418e`; re-running on a clean checkout may differ if dirty paths affect scoring/gates.

---

## 10. Files produced / changed

| Path | Role |
|---|---|
| `reports/PRE_REMEDIATION_BASELINE.md` | This durable report |
| `results/baseline/run1/*` | Official run 1 artifacts |
| `results/baseline/run2/*` | Official run 2 artifacts (equal) |
| `results/baseline/run_*_BNBUSDT/*` | Timestamped harness outputs |
| `results/baseline/gate_off_bare_command/*` | Diagnostic bare-command artifacts |
| `results/baseline/*_console.log` | Console captures |
| **Production code / configs / models / datasets** | **NOT modified by this task** |

---

## 11. Findings / tests / unknowns

| Item | Value |
|---|---|
| **TESTS_RUN** | none (observational baseline only) |
| **NEW_FINDINGS** | **none** (F-037 reconfirmed; F-048 not cleanly re-proven/reversed at journal level — no mandate trigger) |
| **REMAINING_UNKNOWNS** | (1) Whether 11 admits are true DE `execute` vs fail-soft exception-allow; (2) full per-stage ER decision histogram; (3) clean-checkout byte equality given dirty worktree; (4) live_engine_hook path not exercised here |

---

## 12. COMPLETION_STATUS

**COMPLETE** — one representative corpus (BNBUSDT), production-fidelity gate-ON baseline run twice, deterministic equality verified, durable report written, no remediation performed, stop.
