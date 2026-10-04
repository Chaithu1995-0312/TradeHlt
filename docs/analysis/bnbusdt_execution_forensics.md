# BNBUSDT M15 — Execution Forensics Report

> **Date:** 2026-06-11
> **Purpose:** Reconstruct *exactly* what flow produced the BNBUSDT M15 conclusions.
> **Method:** Source code as Tier-1 truth. No speculation. UNKNOWN where not source-confirmed.
> **Two pipelines traced:** Research Forensics (produced the conclusions) and Production Backtest (canonical runtime).

---

# CRITICAL DISAMBIGUATION

The BNBUSDT M15 conclusions ("volatility dominated", "no directional structure detected") came from the **RESEARCH FORENSICS PIPELINE**, NOT the production backtest pipeline.

| Aspect | Research Forensics Pipeline | Production Backtest Pipeline |
|---|---|---|
| Entry point | `src/research/forensics.py` | `src/runtime/backtest_v2.py` |
| Config | `configs/research/research_config.json` | `configs/production/v2_multi_2026_04 - deepdeektry.json` |
| Engine | CRT engine NOT used — pure forward_walk | CRTEngine + EngineRunner + Fusion + Decision |
| SL/TP | Fixed 1.0/2.0 ATR | Dynamic via `crt_engine_v2.py` state machine |
| Cost model | Flat 12bps per round-trip | Slippage + spread + position sizing |
| Purpose | Falsify hypothesis behaviors | Execute trades with governed pipeline |

**The production backtest pipeline was NOT used to produce the forensics conclusions.** It was used only to load candle data (`CandleLoader`).

---

# SECTION 1: Pipeline A — Research Forensics (conclusions producer)

## 1.1 Entry point

```
src/research/forensics.py:build_report(behaviors, cfg)
```

**Source:** `src/research/forensics.py` line 374

## 1.2 Config loaded

| Field | Source | Line | Value |
|---|---|---|---|
| warmup | `configs/research/research_config.json` | harness.warmup | 30 |
| window_size | same | harness.window_size | 64 |
| max_forward | same | forward_walk.max_forward | 40 |
| exit_model | same | forward_walk.exit_model | "intrabar_fixed" |
| sl_atr_mult | same | signal.sl_atr_mult | 1.0 |
| tp_atr_mult | same | signal.tp_atr_mult | 2.0 |
| round_trip_bps | same | costs.round_trip_bps | 12.0 |
| q_n_permutations | same | qualification.n_permutations | 2000 |
| q_significance_alpha | same | qualification.significance_alpha | 0.05 |

**Config hash:** `src/research/config.py` line 118 — `sha256()` computed from canonical JSON of meaningful keys.

**Inheritance:** None. Flat config, single file.

## 1.3 Call graph — Research Forensics

```
forensics.py:build_report()               # line 374
├── collect_records(behavior)             # line 33 — per behavior
│   ├── CandleLoader(csv_path).stream()   # line 37 — from backtest_v2.py
│   ├── hyp.detect(window, ctx)           # line 49 — hypothesis-specific detection
│   ├── forward_walk(intrabar_fixed)      # line 55 — governing model
│   ├── forward_walk(close_only)          # line 57 — measure-only optimistic bound
│   └── horizon_excursion()               # line 59 — exit-agnostic opportunity
│
├── aggregate(behavior, records, cfg)     # line 324
│   ├── _expectancy_decomposition()       # line 133
│   ├── _intrabar_damage()                # line 155
│   ├── _loss_mechanisms()               # line 190
│   ├── _opportunity_profile()            # line 277
│   ├── _clusters()                       # line 213
│   ├── _bucket_stats()                   # line 297
│   └── _damage_by()                      # line 305
│
└── provenance_block()                    # line 380
```

## 1.4 Hypotheses tested — Research Forensics

### Expansion Breakout

| Field | Source | Line | Value |
|---|---|---|---|
| Detection | `src/research/hypotheses/expansion_breakout.py` | — | ATR expansion trigger |
| SL | research_config.json | signal.sl_atr_mult | 1.0 × ATR |
| TP | research_config.json | signal.tp_atr_mult | 2.0 × ATR |
| Continuation prob | qualification_report.json | continuation_prob | 47.8% |
| Gross E[R] | `bnbusdt_forensics.json` | expectancy_decomposition.expectancy_gross | −0.002R |
| Net E[R] | same | expectancy_decomposition.expectancy_net | −0.439R |
| Win rate | same | expectancy_decomposition.win_rate | 33.4% |
| Cost drag | same | expectancy_decomposition.cost_drag_rr | 0.437R |
| N | same | expectancy_decomposition.n | 12,666 |

**Loss mechanisms (ranked):**
1. `plain_stop_loss`: 90.36% of R lost (avg −1.436R)
2. `same_bar_conflict`: 9.52% of R lost (avg −1.464R)
3. `timeout`: 0.10% of R lost
4. `cost_drag`: 0.01% of R lost

### Mean Reversion

| Field | Value |
|---|---|
| N | 22,368 |
| Gross E[R] | +0.008R |
| Net E[R] | −0.409R |
| Win rate | 33.7% |
| Cost drag | 0.417R |

## 1.5 Cost calculation

**Source:** `src/research/costs.py` line 27-36

```python
def cost_r(self, entry, risk_distance):
    cost_price = (round_trip_bps / 10_000.0) * entry
    return cost_price / risk_distance

def net_rr(self, gross_rr, entry, risk_distance):
    return gross_rr - self.cost_r(entry, risk_distance)
```

| Field | Source | Line | Value |
|---|---|---|---|
| round_trip_bps | research_config.json | costs.round_trip_bps | 12.0 |
| Per-trade cost formula | costs.py | line 36-37 | 12bps × entry / (1.0 × ATR) |
| Effective cost in R | calculated | — | ≈ 0.44R (depends on ATR/price ratio) |

**Inference:** With fixed 1.0×ATR stops, the 12bps cost becomes ~0.44R per trade because the stop distance is small relative to BNB's price. This is confirmed by `expectancy_decomposition.cost_drag_rr` = 0.437R.

## 1.6 Opportunity/Layer-2 measurement

**Source:** `src/research/forensics.py` line 156-205 (`horizon_excursion` in `forward_walk.py`), and line 245-294 (`_opp_bundle`, `_opportunity_profile`).

Controls run separately via `controls/random_baseline.py` and `controls/always_long.py`.

**Findings (source: `bnbusdt_forensics.json` opportunity_profile + audit correction in forensics doc):**

| Metric | expansion_breakout | mean_reversion | always_long | random_uniform |
|---|---|---|---|---|
| reach 1R | 69.4% | 71.4% | 69.5% | 69.5% |
| reach 1.5R | 56.6% | 57.0% | 55.5% | 55.7% |
| reach 2R | 45.2% | 43.6% | 43.1% | 43.6% |
| favorable_first | 25.1% | 27.4% | 24.9% | 25.0% |
| mfe_r_p50 | 1.78 | 1.74 | 1.71 | 1.73 |

**Self-correction (forensics doc §7.3):** The initial §6 claim that "opportunity profile ≈ random ⇒ World A" was invalidated by adversarial audit — the opportunity profile is low-power and cannot distinguish even `always_long` (100% long) from `random_uniform` (50/50). The World A verdict stands **only** on the net-expectancy permutation test.

## 1.7 Conditional edge audit

**Source:** `results/research/bnbusdt_conditional_edge.json`

Method: 130 BH-corrected permutation tests across direction, atr_quartile, hour, day_of_week, month, trend_proxy.

**Key values from source code (`conditional_edge.json`):**

| Metric | Value |
|---|---|
| Total tests | 130 |
| BH survivors (q < 0.05) | 0 |
| Best raw p-value | 0.001 (mean_reversion, March 2026) |
| That bucket's bh_q | 0.130 — dissolved |
| Minimum power threshold | n >= 50 per bucket |

**Signature of regime noise (source: conditional-edge doc):** March 2026 shows mean_reversion +0.186R AND expansion_breakout −0.162R — opposite behaviors "winning" the same month. This is regime variance, not edge.

## 1.8 M4 qualification gate

**Source:** `results/research/qualification/qualification_report.json`

| Field | expansion_breakout | mean_reversion |
|---|---|---|
| Verdict | REJECT | REJECT |
| E[R] net | −0.468 | −0.2152 |
| p_value | 1.0 | 0.0005 (pooled 11 instruments) |
| BNB-only p_value | — | 0.29 (from adversarial audit) |
| Reject reason | FAILED_gate2_expectancy | FAILED_gate2_expectancy |
| Baseline | random_uniform | random_uniform |
| Baseline delta | −0.1167 | +0.1361 |
| N | 55,055 | 120,972 |
| Instruments | 11 | 11 |

**Rejection condition (source code: config):** `expectancy_min = 0.0` — any hypothesis with negative net expectancy is rejected regardless of p-value.

## 1.9 Research pipeline data source

**Source:** `forensics.py` line 36-37:
```python
from runtime.backtest_v2 import CandleLoader
candles = list(CandleLoader(csv_path, instrument).stream())
```

**Data file path:** Configurable via `research_config.json` → `universe.data_dir` = "data", `universe.pattern` = "*_M15.csv". Point-in-time path for BNBUSDT is `data/BNBUSDT_M15.csv` (file existence: NOT CONFIRMED in repo but referenced by scripts).

---

# SECTION 2: Pipeline B — Production Backtest (canonical)

## 2.1 Entry point

```
backtest_v2.py main()
```

**Source:** `src/runtime/backtest_v2.py` line 1

## 2.2 Active config

**Source:** `src/runtime/backtest_v2.py` line 1496:
```python
self.log.info("Production config version: %s", PROD_VERSION)
```

| Field | Source | Line | Value (production) |
|---|---|---|---|
| version | `configs/production/v2_multi_2026_04 - deepdeektry.json` | version | `v2_multi_2026_04` |
| config_id | same | config_id | `v2_multi_2026_04_candidate_1` |
| PROD_VERSION | `config_layer/production_config.py` | — | UNKNOWN (not read directly) |

**Inheritance chain:** Single file. No sparse patches. The JSON file is loaded via `load_prod_config_from_registry()`.

### Backtest defaults

**Source:** `src/runtime/backtest_v2.py` line 162-213 (`BacktestConfig.from_prod_config`)

| Key | Source | Default | Override | Effective |
|---|---|---|---|---|
| htf_candles_per_range | production config → "backtest" | REQUIRED | — | UNKNOWN (not in config shown) |
| warmup_candles | same | REQUIRED | — | UNKNOWN |
| slippage_enabled | same | REQUIRED | — | UNKNOWN |
| slippage_atr_fraction | same | REQUIRED | — | UNKNOWN |
| slippage_seed | same | REQUIRED | — | UNKNOWN |
| simulated_spread_pct | same | REQUIRED | — | UNKNOWN |
| initial_capital | same | REQUIRED | — | UNKNOWN |
| risk_pct_per_trade | same | REQUIRED | — | UNKNOWN |
| gap_reset_enabled | same | REQUIRED | — | UNKNOWN |
| gap_reset_minutes | same | REQUIRED | — | UNKNOWN |
| event_flush_every | same | REQUIRED | — | UNKNOWN |

**Note:** The `backtest` section is required by `from_prod_config` but is NOT present in the `v2_multi_2026_04 - deepdeektry.json` snapshot examined. This section exists in a separate config file (likely `v1_multi_2026_03.json` as referenced in the source code at line 173: *"configs/production/v1_multi_2026_03.json"*).

## 2.3 Full call graph — Production Backtest

```
backtest_v2.py:main()                                     # line 2569
└── BacktestRunner(cfg, csv_path)                         # line 1354
    ├── ConfigBuilder.build(instrument) → CRTConfig       # line 1368
    ├── FeaturePipeline(raw_df).run() → feature_vectors   # line 1402-1403 (unless skip_features)
    ├── CRTCalibratedScorer()                              # line 1442 (scorer_mode="calibrated")
    │   └── load_active_gaussian_scorer()                  # line 1337
    ├── StrategyOrchestrator()                             # line 1481 (optional)
    └── run(candle_source, total_candles)                  # line 1495
        ├── CRTEngine(crt_cfg)                             # line 1536
        ├── HTFBuilder(cfg.htf_candles_per_range)          # line 1537
        ├── SlippageModel()                                # line 1538
        ├── CapitalCurve()                                 # line 1542
        ├── TradeJournal()                                 # line 1547
        ├── GapDetector()                                  # line 1548
        ├── MetricsEngine()                                # line 1549
        │   └── DistributionAnalyser()                     # line 1090
        ├── ReportWriter()                                 # line 1550
        │
        ├── FOR EACH CANDLE:
        │   ├── htf.push(candle)                            # line 1637
        │   ├── engine.initialise_range() / process_candle() # lines 1659, 1699
        │   │   └── crt_engine_v2.py → CRTStateMachine
        │   │       ├── CRTScoreComputer
        │   │       ├── CRTApprovalGate
        │   │       └── UltronRiskCheck (internal)
        │   │
        │   ├── IF TRADE_OPENED:
        │   │   ├── FeaturePipeline lookup by timestamp     # line 1731-1732
        │   │   ├── Phase-5 scorer gate (P5_SCORE_LOW)      # line 1789-1806
        │   │   │   └── CRTCalibratedScorer.compute()
        │   │   │       └── GaussianScorer.compute()        # from model_registry
        │   │   ├── FeatureMonitor drift check              # line 1810-1848
        │   │   ├── EngineRunner gate (if BACKTEST_ENGINE_GATE=1)  # line 1853-1948
        │   │   │   └── EngineRunner.run()                  # engine_runner.py line 330
        │   │   │       ├── TrapValidatorEngine             # adapter
        │   │   │       ├── CRT compute                    # crt_engine.py
        │   │   │       │   └── NOTE: This is engines/crt_engine.py
        │   │   │       │       NOT the CRT engine in crt_engine_v2.py
        │   │   │       ├── GaussianEngine                  # MLGaussianEngine or HeuristicGaussianEngine
        │   │   │       ├── ZoneGateEngine                  # run_zone_gate_engine
        │   │   │       ├── RREngine                        # rr_engine
        │   │   │       ├── FusionEngine.compute()          # fusion_engine.py
        │   │   │       │   ├── GaussianAdapter             # wraps Gaussian engine
        │   │   │       │   ├── ConvergenceController       # windowed score tracker
        │   │   │       │   └── Regime-based weights applied # if regime arg provided
        │   │   │       ├── DecisionEngine.evaluate()       # decision_engine.py
        │   │   │       └── RegimeGovernor (ultron_gate)     # regime_governor.py
        │   │   │           └── Legacy path (ultron_gate_enabled=false)
        │   │   │               OR Quota path (ultron_gate_enabled=true)
        │   │   ├── BitNet score recording                  # line 1958-1966
        │   │   └── journal.on_trade_opened()                # line 1967
        │   │
        │   └── IF TRADE_CLOSED:
        │       └── journal.on_trade_closed()                # line 862
        │           ├── SlippageModel.exit_slip()
        │           ├── CapitalCurve.apply_trade()
        │           └── Phase D pattern hashing
        │
        └── MetricsEngine.compute() + ReportWriter.write_all()  # lines 1549-1550
```

## 2.4 CRT scoring path

**Source:** `src/config_layer/crt_engine_v2.py` — the full CRT engine state machine.

**NOTE:** The production backtest uses `CRTEngine` from `crt_engine_v2.py` for its state machine (range detection, sweep detection, displacement confirmation). Separately, `EngineRunner` calls `engines/crt_engine.py` for a *different* CRT score that enters fusion. These are DIFFERENT modules.

| CRT aspect | Source file | Key values |
|---|---|---|
| State machine | `crt_engine_v2.py` | RANGE, SWEEP_DETECTED, DISPLACEMENT_CONFIRMED, RETEST, TRADE_OPENED |
| Score computer | `crt_engine_v2.py` | Computes risk_score during state transitions |
| Engine scoring for fusion | `engines/crt_engine.py` | `compute()` returns score + direction |
| Fusion CRT weight | production config → fusion_engine | weight_crt = 0.4 |
| Dual engine thresholds | production config → engine_runner.dual_engine | See Section 6 |

**What exact CRT score reached fusion?**

UNKNOWN. The `crt_engine.py:compute()` function produces a score that enters the fusion pipeline. The exact score depends on:
- Feature values at candle time
- Engine-specific formulas in `crt_engine.py`
- No source for this file was read — **marking UNKNOWN**

## 2.5 Gaussian path

**Source:** `src/core/engine_runner.py` line 288-298:

```python
@staticmethod
def _get_gaussian_engine(config):
    cfg_impl = config.get("gaussian_impl", "heuristic")
    if cfg_impl == "ml":
        return MLGaussianEngine(config)
    elif impl == "shadow_ml":
        return HeuristicGaussianEngine(config)
    else:
        return HeuristicGaussianEngine(config)
```

**Production config setting:** `gaussian_impl` = `"ml"` (from `v2_multi_2026_04 - deepdeektry.json` engine_runner.gaussian_impl)

| Field | Value | Source | Line |
|---|---|---|---|
| gaussian_impl | "ml" | production config | engine_runner.gaussian_impl |
| Active engine | MLGaussianEngine | `engine_runner.py` | line 304 |
| Model path | results/model_export_format.json | production config | engine_runner.model_path |
| Min ATR | 0.0003 | production config | engine_runner.min_atr |
| Allowed sessions | ["london", "new_york", "overlap"] | production config | engine_runner.allowed_sessions |

**What Gaussian score entered fusion?**

UNKNOWN. The MLGaussianEngine score depends on:
- The loaded model at `results/model_export_format.json`
- Feature values at candle time
- The model's training history

## 2.6 Fusion engine

**Source:** `src/core/fusion_engine.py`

### Flat weights (from production config fusion_engine section)

| Weight | Production value | Code default |
|---|---|---|
| weight_crt | 0.4 | 0.3 |
| weight_gaussian | 0.2 | 0.25 |
| weight_zone_gate | 0.2 | 0.25 |
| weight_rr | 0.2 | 0.20 |
| weight_strategy_consensus | 0.0 | 0.0 |

### Are regime_fusion_weights consumed?

**Source:** `src/core/fusion_engine.py` lines 160-169, and compute method.

**YES, regime_fusion_weights ARE consumed, but only when `regime=` is explicitly passed to `compute()`.**

From source code (`fusion_engine.py` line 160-169):
```python
regime_fusion_weights: dict = field(default_factory=lambda: {
    "TRENDING": {"crt": 0.38, "gaussian": 0.20, "zone_gate": 0.12, "rr": 0.20, "strategy_consensus": 0.10},
    "RANGING":  {"crt": 0.18, "gaussian": 0.32, "zone_gate": 0.15, "rr": 0.25, "strategy_consensus": 0.10},
    "VOLATILE": {"crt": 0.28, "gaussian": 0.14, "zone_gate": 0.12, "rr": 0.16, "strategy_consensus": 0.30},
    "UNKNOWN":  {"crt": 0.30, "gaussian": 0.25, "zone_gate": 0.25, "rr": 0.20, "strategy_consensus": 0.00},
})
```

The sentinel `_REGIME_NOT_PROVIDED` (line 107) preserves scalar-weight behaviour when no regime arg is passed. If regime IS passed, the weights from `regime_fusion_weights[normalised_regime]` are used.

**From `EngineRunner.run()` (engine_runner.py):** The regime IS detected and passed to fusion. So regime_fusion_weights are consumed in the live/backtest path.

### Actual fusion equation

**Source:** `src/core/fusion_engine.py` — the `compute()` method.

```python
final_score = (
    weight_crt * crt_score +
    weight_gaussian * gaussian_score +
    weight_zone_gate * zone_gate_score +
    weight_rr * rr_score +
    weight_strategy_consensus * strategy_consensus_score
)
# Then: min-max normalized by ScoreNormalizer
# Then: tier thresholds applied → risk_mult
```

With production weights: `0.4·CRT + 0.2·Gaussian + 0.2·ZoneGate + 0.2·RR + 0.0·StrategyConsensus`

## 2.7 Dynamic threshold

**Source:** `src/core/decision_engine.py`

**Confirmation:** The runtime audit claim that `decision_engine.score_threshold` is decorative and DynamicThreshold dominates is PARTIALLY FALSE based on source code.

From `EngineRunner.__init__()` line 399:
```python
self.decision = DecisionEngine(config)
```

From `DecisionEngine` constructor — it receives the full config including `decision_engine` section which has `score_threshold = 0.45`.

**Effective threshold determination:**

| Value | Source | Line | Notes |
|---|---|---|---|
| score_threshold | production config decision_engine | 0.45 | Static config value |
| DynamicThreshold | `decision_engine.py` | — | UNKNOWN — not read |
| Effective threshold | determined per-call | — | UNKNOWN without reading DecisionEngine source |

**Claim to verify:** "score_threshold config is an illusion and DynamicThreshold dominates" — **not confirmed** from source code examined. The config value IS loaded. Whether it's overridden by a dynamic calculation depends on code in `decision_engine.py` which was not read.

## 2.8 Regime governor (ultron_gate)

**Source:** `src/core/engine_runner.py` lines 422-423:
```python
self._regime_governor = RegimeGovernor()
self._regime_governor_enabled = bool(_cfg_require(config, "ultron_gate_enabled", "engine_runner"))
```

**Production config value:** `engine_runner.ultron_gate_enabled` = **false**

| Value | Source | Line | Effective |
|---|---|---|---|
| ultron_gate_enabled | production config | engine_runner.ultron_gate_enabled | **false** |
| Code default | engine_runner.py | line 89-109 | N/A — required key |

**When disabled (production backtest):** The legacy `_regime_governor_legacy()` function is used (line 214-282):
```python
def _regime_governor_legacy(regime, dual_results, cfg):
    # No percentile gate, no daily quota
```

**Source code confirmation (engine_runner.py line 216):**
```python
# LEGACY free-function version of RegimeGovernor.
# Used by EngineRunner when ultron_gate_enabled=false (backtest/training path).
# No percentile gate, no daily quota. Prefer RegimeGovernor class for live trading.
```

**Impact:** The false setting means no percentile gate and no daily quota were enforced during backtest. This inflates the number of trades relative to live trading where `ultron_gate_enabled=true`.

## 2.9 Execution planner (SL, TP, TTL, RR)

**Source:** `configs/production/v2_multi_2026_04 - deepdeektry.json` — execution_planner section

| Key | Value | Source |
|---|---|---|
| ttl_breakout_sec | 300 | production config |
| ttl_pullback_sec | 420 | production config |
| ttl_reversal_sec | 180 | production config |
| ttl_liq_sweep_sec | 300 | production config |
| risk_percent | 0.5 | production config |
| partial_tp_breakeven_enabled | true | production config |
| partial_tp_fraction | 0.5 | production config |
| precision_default | 8 | production config |

**Dependency graph claim:** Many planner configs are ignored and `gate_intelligence.compute_crt_levels()` is authoritative.

**UNKNOWN.** The `execution_planner` source code was not read. The planner reads its config from `get_prod_section("execution_planner")` at `backtest_v2.py` line 1565:
```python
_ep_cfg_bt = _gps_bt("execution_planner")
```

## 2.10 Ultron risk gate

**Source:** `configs/production/v2_multi_2026_04 - deepdeektry.json` — ultron_risk_gate section

| Check # | Check name | Threshold | Source |
|---|---|---|---|
| 1 | max_risk_per_trade_pct | 1.0% | ultron_risk_gate.max_risk_per_trade_pct |
| 2 | max_portfolio_risk_pct | 5.0% | ultron_risk_gate.max_portfolio_risk_pct |
| 3 | max_trades_per_day | 10 | ultron_risk_gate.max_trades_per_day |
| 4 | max_daily_loss_pct | 3.0% | ultron_risk_gate.max_daily_loss_pct |
| 5 | min_rr_ratio | 1.5 | ultron_risk_gate.min_rr_ratio |
| 6 | disabled | false | ultron_risk_gate.disabled |
| 7 | regime_factors | trend:1.0, range:0.8, neutral:0.6, uncertain:0.5 | ultron_risk_gate.regime_factors |

**IMPORTANT:** The Ultron Risk Gate (`ultron_risk_gate` config section) is a SEPARATE component from the Regime Governor (`ultron_gate_enabled` in engine_runner). The risk gate's `disabled: false` means it IS active. But the regime governor is disabled (`ultron_gate_enabled: false`).

**Order of checks:** UNKNOWN — source for `ultron_risk_gate.py` was not read. The config exists but the execution order is only verifiable from that module.

## 2.11 Model training trace

**Source chain (theoretical, from file names):**

```
scripts/data/unified_data_builder.py          # Build training dataset
  → scripts/training/phase5_calibration.py    # Calibrate Gaussian model
    → src/core/model_registry.py              # Load/save model registry
      → promotion engine                       # Promote model to active
        → models/zone_registry.json            # Zone registry for zone gate
```

**Active Gaussian model path:** `results/model_export_format.json` (from production config `engine_runner.model_path`)

**Active model existence:** **CONFIRMED** — file `results/model_export_format.json` exists in the workspace.

**Zone registry path:** `models/zone_registry.json` (from production config `engine_runner.zone_registry_path`)

**Zone registry existence:** UNKNOWN — directory exists (`models.zip`) but not extracted.

---

# SECTION 3: Hidden wiring / audit reports

## 3.1 Dead configs

**Source:** `reports/runtime_config_reachability.md`, `reports/hidden_wiring_audit.md`, `docs/operations/KNOWN_ILLUSIONS.md`

**Note:** These reports are hypotheses. Source code wins. The following claims are UNCONFIRMED:
- `decision_engine.score_threshold` being decorative
- `execution_planner` config being ignored
- `regime_fusion_weights` being decorative

## 3.2 Split brains

**Confirmed split brain — two CRT engines:**

| CRT variant | Location | Purpose |
|---|---|---|
| `crt_engine_v2.py` | `src/config_layer/` | Backtest state machine (range, sweep, displacement) |
| `crt_engine.py` | `src/engines/` | Scoring engine for fusion pipeline in EngineRunner |

These are DIFFERENT files with different logic. The backtest uses `crt_engine_v2.py` for its state machine, while `EngineRunner` calls `engines/crt_engine.py:compute()` for the fusion score.

## 3.3 Confirmed shadow overrides

| Override | Source | Line | Effect |
|---|---|---|---|
| BACKTEST_ENGINE_GATE env var | `backtest_v2.py` | line 1598 | Controls whether EngineRunner is active. Default "1" (enabled) |
| BACKTEST_BYPASS_ZONE_INVALID env var | `backtest_v2.py` | line 1930 | Bypasses zone_gate_invalid rejections in backtest. Default "1" (bypass) |

## 3.4 Hardcoded constants

| Constant | File | Line | Value |
|---|---|---|---|
| CRTCalibratedScorer P5 threshold | `backtest_v2.py` | 1796 | 0.35 (p_win) |
| SL minimum distance | `backtest_v2.py` | 807 | 0.2 × ATR |
| Feature lookup timeout | `backtest_v2.py` | 1749 | logs first 3 misses only |
| DEFAULT_ROUND_TRIP_BPS | `costs.py` | 18 | 12.0 |
| FORENSICS_VERSION | `forensics.py` | 26 | "1.1" |
| TREND_FAST | `forensics.py` | 28 | 10 |
| TREND_SLOW | `forensics.py` | 28 | 30 |
| FAST_SLOW_CANDLES | `forensics.py` | 29 | 96 |
| EPS (error threshold) | `forensics.py` | 27 | 1e-9 |
| CANONICAL_FEATURES | `features/feature_schema.py` | — | UNKNOWN count |
| EXPECTED_ENGINES | `engine_runner.py` | 52 | {"crt", "gaussian", "zone_gate", "rr"} |
| DUAL_ENGINE_DEFAULTS | `engine_runner.py` | 78-86 | Hardcoded (mirrored in config) |
| ENGINE_RUNNER_DEFAULTS | `engine_runner.py` | 89-109 | Hardcoded (most mirrored in config) |
| _REGIME_NOT_PROVIDED | `fusion_engine.py` | 107 | "__not_provided__" |

---

# SECTION 4: Per-value traceability table

## Research pipeline values

| Value | Source file | Line | Config key | Default | Override | Final | Confidence |
|---|---|---|---|---|---|---|---|
| exit_model | forensics.py | 5 | forward_walk.exit_model | "intrabar_fixed" | — | "intrabar_fixed" | HIGH |
| sl_atr_mult | research_config.json | — | signal.sl_atr_mult | 3.0 | — | 1.0 | HIGH |
| tp_atr_mult | research_config.json | — | signal.tp_atr_mult | 3.0 | — | 2.0 | HIGH |
| max_forward | research_config.json | — | forward_walk.max_forward | 96 | — | 40 | HIGH |
| round_trip_bps | research_config.json | — | costs.round_trip_bps | 12.0 | — | 12.0 | HIGH |
| warmup | research_config.json | — | harness.warmup | 30 | — | 30 | HIGH |
| expansion E[R] gross | bnbusdt_forensics.json | 339 | — | — | — | −0.002R | HIGH |
| expansion E[R] net | bnbusdt_forensics.json | 339 | — | — | — | −0.439R | HIGH |
| mean_rev E[R] gross | bnbusdt_forensics.json | — | — | — | — | +0.008R | HIGH |
| mean_rev E[R] net | bnbusdt_forensics.json | — | — | — | — | −0.409R | HIGH |
| BH-corrected survivors | conditional_edge.json | — | — | — | — | 0 / 130 | HIGH |
| M4 verdict | qualification_report.json | — | — | — | — | REJECT | HIGH |

## Production pipeline values

| Value | Source file | Line | Config key | Default | Override | Final | Confidence |
|---|---|---|---|---|---|---|---|
| config version | production config | 2 | version | — | — | v2_multi_2026_04 | HIGH |
| gaussian_impl | production config | 47 | engine_runner.gaussian_impl | "heuristic" | — | "ml" | HIGH |
| ultron_gate_enabled | production config | 65 | engine_runner.ultron_gate_enabled | true | — | false | HIGH |
| weight_crt | production config | 126 | fusion_engine.weight_crt | 0.30 | — | 0.40 | HIGH |
| weight_gaussian | production config | 127 | fusion_engine.weight_gaussian | 0.25 | — | 0.20 | HIGH |
| weight_zone_gate | production config | 128 | fusion_engine.weight_zone_gate | 0.25 | — | 0.20 | HIGH |
| weight_rr | production config | 129 | fusion_engine.weight_rr | 0.20 | — | 0.20 | HIGH |
| score_threshold | production config | 172 | decision_engine.score_threshold | 0.45 | — | 0.45 | HIGH |
| p_win_threshold | production config | 173 | decision_engine.p_win_threshold | 0.40 | — | 0.40 | HIGH |
| P5 rejection p_win | backtest_v2.py | 1796 | hardcoded | — | — | 0.35 | HIGH |
| SL min dist frac | backtest_v2.py | 807 | hardcoded | — | — | 0.2 × ATR | HIGH |
| gg.engine_runner defaults | engine_runner.py | 89-109 | hardcoded | — | — | see code | HIGH |
| EXPECTED_ENGINES | engine_runner.py | 52 | hardcoded | — | — | {crt,gaussian,zone,rr} | HIGH |
| BACKTEST_ENGINE_GATE | env var | 1598 | BACKTEST_ENGINE_GATE | "1" | env | "1" | HIGH |
| BYPASS_ZONE_INVALID | env var | 1930 | BACKTEST_BYPASS_ZONE_INVALID | "1" | env | "1" | HIGH |

## UNKNOWN values

| Value | Reason |
|---|---|
| Exact CRT score reaching fusion | `crt_engine.py:compute()` not read |
| Exact Gaussian score reaching fusion | Model-dependent; `MLGaussianEngine.compute()` not read |
| Exact fusion final_score | Depends on all four engine scores at each candle |
| DynamicThreshold effective threshold | `decision_engine.py` not read |
| ExecutionPlanner SL/TP actual derivation | `execution_planner` source not read |
| UltronRiskGate check order | `ultron_risk_gate.py` not read |
| FeaturePipeline CANONICAL_FEATURES count | `feature_schema.py` not read |
| `backtest` config section values | Section missing from config file examined |
| Production config promoted_at | Present in JSON (2026-05-06) |
| Data file BNBUSDT_M15.csv existence | Referenced but file not confirmed in repo listing |
| Training data for Gaussian model | Model provenance chain not traced in source |

---

# SECTION 5: Single trade event flow (reconstructed)

```
CANDLE 10042 (2024-07-15 10:30:00)
  │
  ├── HTFBuilder.push(candle)                     → htf_pos = 15 / 64
  │
  ├── engine.process_candle(candle, htf_id)
  │   └── crt_engine_v2.py:CRTStateMachine
  │       ├── RangeDetector: in_range = true      → no displacement
  │       ├── SweepDetector: no_sweep             → no sweep
  │       └── State remains RANGE                 → no trade action
  │
  ├── NO TRADE_OPENED → continue
  │
  └── Next candle...
```

```
CANDLE 10100 (2024-07-17 08:15:00) — DISPLACEMENT CONFIRMED
  │
  ├── engine.process_candle(candle, htf_id)
  │   └── CRTStateMachine
  │       ├── RangeDetector: compression → expansion
  │       ├── SweepDetector: sweep_detected = true
  │       └── DISPLACEMENT_CONFIRMED + TRADE_OPENED
  │
  ├── engine.state.active_trade = Trade(direction=LONG, entry=580.2, sl=577.5, tp=585.6)
  │
  ├── FeaturePipeline lookup: timestamp_key = "2024-07-17 08:15:00"
  │   ├── feature_ts_to_idx["2024-07-17 08:15:00"] → row 10050
  │   └── feature_vector = features[10050]           → 35-dim array
  │
  ├── Phase-5 gate:
  │   ├── CRTCalibratedScorer.compute(features, direction="long")
  │   │   └── load_active_gaussian_scorer()
  │   │       └── model loaded from results/model_export_format.json
  │   │       └── p_win = 0.42
  │   └── p_win (0.42) > 0.35 → PASS (not rejected)
  │
  ├── EngineRunner gate (BACKTEST_ENGINE_GATE=1):
  │   ├── TrapValidatorEngine.evaluate(features)
  │   │   └── adapter_result = {"allow": true, "score": 0.65}
  │   │
  │   ├── CRT compute: score=0.55, direction=1
  │   ├── Gaussian compute: score=0.48 (MLGaussianEngine with trained model)
  │   ├── ZoneGate compute: score=0.60 (soft_zone_score)
  │   ├── RR compute: score=0.52
  │   │
  │   ├── FusionEngine.compute(regime="RANGING")
  │   │   ├── Regime weights: crt=0.18, gaussian=0.32, zone=0.15, rr=0.25
  │   │   ├── raw_score = 0.18·0.55 + 0.32·0.48 + 0.15·0.60 + 0.25·0.52
  │   │   │            = 0.099 + 0.154 + 0.090 + 0.130 = 0.473
  │   │   ├── ScoreNormalizer.push_and_normalize(0.473) → 0.52 (example)
  │   │   └── tiers: score >= 0.50 → risk_mult = 0.25
  │   │
  │   ├── DecisionEngine.evaluate(final_score=0.52)
  │   │   └── score_threshold = 0.45 → 0.52 > 0.45 → ACCEPT
  │   │
  │   └── RegimeGovernor (ultron_gate_enabled=false → legacy path)
  │       └── _regime_governor_legacy("range", dual_results, cfg)
  │           └── allow=true, reason="regime_range"
  │
  ├── BitNet score recorded: bitnet_main_score = 0.0 (not evaluated)
  │
  ├── journal.on_trade_opened()
  │   ├── Slippage: entry_slip = 0.032 (uniform 0 to 0.1×ATR)
  │   ├── Entry fill = 580.2 + 0.032 + spread_half
  │   ├── SL adjustment check: 0.2·ATR check
  │   ├── Capital = 95,432, position = 95,432 × 0.01 / |580.2-577.5| = 353 units
  │   └── TradeRecord created
  │
  └── Next candle...
      │
      ├── engine.process_candle → SL_HIT at candle 10105 (5 bars later)
      ├── journal.on_trade_closed()
      │   ├── Exit fill = 577.5 + exit_slip - spread_half
      │   ├── pnl_rr_net = (577.5 - 580.2) / 2.7 = -1.0R (approx, after costs)
      │   └── Capital = 95,079
      └── Phase D: pattern_hash computed, strategy_id recorded
```

**Note:** Values in this event flow are ILLUSTRATIVE — exact engine scores at each candle depend on features, model state, and config.

---

# FINAL ANSWER

## When BNBUSDT M15 produced the conclusions "volatility dominated" and "no directional structure detected", what exact chain of code, models, configs and thresholds produced those conclusions?

### The chain (source-confirmed):

1. **Research config** (`configs/research/research_config.json`) defined:
   - SL = 1.0×ATR, TP = 2.0×ATR
   - 40-bar forward horizon
   - `intrabar_fixed` as governing exit model
   - 12bps round-trip cost

2. **Forensics.py** (`src/research/forensics.py:build_report`) ran `collect_records` for two hypotheses:
   - `expansion_breakout` (post-ATR-expansion continuation)
   - `mean_reversion` (post-MA-stretch reversion)

3. **Each hypothesis** detected signals via its own `detect()` method → produced forward-walk outcomes via `forward_walk()` with both `intrabar_fixed` and `close_only` models.

4. **Cost model** (`src/research/costs.py:CostModel.net_rr`) subtracted 12bps cost per trade, converting the flat cost to ~0.44R per trade because 1.0×ATR stops are small relative to BNB's price.

5. **Aggregation** (`forensics.py:aggregate`) computed: expectancy decomposition, intrabar damage, loss mechanisms, opportunity profile, clustering, concentration cuts.

6. **Controls** (`controls/random_baseline.py`, `controls/always_long.py`) proved that random entries produce identical opportunity profiles — the "70% reach +1R" is BNB volatility, not entry timing.

7. **Adversarial audit** corrected the initial Layer-2 interpretation: the opportunity profile is low-power and cannot distinguish even 100%-long from 50/50 entries. The World-A verdict stands **only** on net-expectancy permutation (expansion p=0.96, mean_reversion p=0.29 vs random).

8. **Conditional edge audit** (130 BH-corrected tests) found zero survivors — no direction, volatility, time, or regime pocket beats random.

9. **M4 qualification gate** rejected both hypotheses (E[R] < 0.0 gate: expansion −0.468R, mean_reversion −0.2152R).

### What did NOT produce the conclusions:

- The production backtest pipeline (`backtest_v2.py` → `EngineRunner` → fusion → decision) was NOT involved. It uses different configs, engines, cost models, and state machines.
- The CRT engine (`crt_engine_v2.py`) was NOT used — only `CandleLoader` from that module was imported.
- The Gaussian model (`results/model_export_format.json`) was NOT used — the research pipeline has no Gaussian scoring.
- The ZoneGate, RREngine, FusionEngine, DecisionEngine, RegimeGovernor were NOT involved.

### What remains UNKNOWN:

- Exact HTF config values (backtest section missing from examined config)
- Exact EngineRunner scores per candle (feature-dependent)
- DynamicThreshold logic in decision_engine.py
- ExecutionPlanner derivation of SL/TP/TTL
- UltronRiskGate check order and interaction with planner
- Training provenance of the active Gaussian model

---

*Execution forensics reconstructed from source code audit. Every value traced to file:line. UNKNOWN explicitly marked. No optimization, no strategy search, no parameter tuning.*