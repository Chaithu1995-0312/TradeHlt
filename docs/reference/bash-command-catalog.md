> Compiled: 2026-06-06 — extracted from session transcripts + codebase docs
> Keep updated: add new commands here as they're used in analysis/planning sessions.
> For the authoritative generated CLI surface (control-plane commands + HTTP routes), see [cli-matrix.md](cli-matrix.md).

# Bash Command Catalog

---

## Common Workflows

Engineers think in goals, not commands. Start here.

### Diagnose low trade count / tune detection

Use when backtest trade count is unexpectedly low or PF has dropped.

1. `backtest_v2.py` — establish baseline trade count and funnel events
2. `funnel_diagnosis.py` — measure which phase transition is the bottleneck
3. `session_sweep.py` — if RETEST→EXECUTION is the bottleneck, test session filter variants
4. `detection_sweep.py` — if DISPLACEMENT→EXPANSION is the bottleneck, sweep detection knobs
5. `pytest tests/ -x --tb=short` — confirm no regressions
6. `promotion_manager.py promote` — promote if ValidationReport passes

### New market data / re-calibrate models

Use when new candle data is available or model scores have drifted.

1. `unified_data_builder.py` — rebuild unified CSV from raw sources
2. `phase5_calibration.py --audit-only` — check current calibration health
3. `phase5_calibration.py --train` — re-calibrate Gaussian/RR models
4. `train_pipeline.py gaussian` — retrain Gaussian model if calibration gate passes
5. `validate-prod` — run config validator across instruments
6. `promotion_manager.py promote` — promote if APPROVE

---

## Top 10 Commands

The 20% of commands that cover 80% of daily usage.

| Command | Purpose | When to use |
|---|---|---|
| `backtest_v2.py` | Run full backtest | After any config or code change |
| `funnel_diagnosis.py` | Measure phase-to-phase drop-off | Trade count unexpectedly low |
| `session_sweep.py` | A/B test session filter variants | Diagnosing RETEST→EXECUTION bottleneck |
| `detection_sweep.py` | Sweep detection knobs across families | Diagnosing DISPLACEMENT→EXPANSION bottleneck |
| `p3b_session_relax_diag.py` | Measure session relaxation impact per instrument | Before changing session config |
| `phase5_calibration.py` | Re-calibrate Gaussian/RR models | New trade outcomes available |
| `train_pipeline.py gaussian` | Retrain Gaussian model | After calibration gate passes |
| `promotion_manager.py promote` | Promote config to production | After ValidationReport APPROVE |
| `_compute_hash.py` | Re-hash config after manual edits | After any config file change |
| `pytest tests/ -x --tb=short` | Run full test suite, stop on first failure | Before every promotion |

---

## Analysis / Sweep Scripts

### backtest_v2 (canonical backtest)

**Purpose:** Run full end-to-end backtest for one instrument.  
**When to use:** After any config or code change to measure impact.  
**Output:** `results/run_<timestamp>_<instrument>/` — summary JSON, events JSONL, trades CSV, report TXT.

```bash
python src/runtime/backtest_v2.py --csv data/BNBUSDT_M15.csv --instrument BNBUSDT
python src/runtime/backtest_v2.py --csv data/BNBUSDT_M15.csv --instrument BNBUSDT --output results/funnel
python src/runtime/backtest_v2.py --csv data/ETHUSDT_M15.csv --instrument ETHUSDT
python src/runtime/backtest_v2.py --csv data/BTCUSDT_M15.csv --instrument BTCUSDT
python src/runtime/backtest_v2.py --csv data/SOLUSDT_M15.csv --instrument SOLUSDT
python src/runtime/backtest_v2.py --csv data/EURUSD_M15.csv --instrument EURUSD
```

### funnel_diagnosis

**Purpose:** Count events at each CRT phase transition to identify the bottleneck stage.  
**When to use:** When trade count is low and you need to know *where* in the funnel trades are being lost.  
**Output:** Console table — event counts per phase + drop-off percentages.

```bash
python scripts/analysis/funnel_diagnosis.py --events results/funnel/run_*/BNBUSDT_events.jsonl --instrument BNBUSDT
```

### session_sweep

**Purpose:** A/B test session filter configuration variants (e.g. relax ASIA, enable OFF_SESSION).  
**When to use:** When `funnel_diagnosis` shows RETEST→EXECUTION as the bottleneck.  
**Output:** Console table — trades/PF/expectancy per session variant.

```bash
python scripts/analysis/session_sweep.py --instrument BNBUSDT --csv data/BNBUSDT_M15.csv
python scripts/analysis/session_sweep.py                      # V0 + all variants
```

### detection_sweep

**Purpose:** Sweep detection knobs (atr_min_distance, conf_body_min, etc.) across families.  
**When to use:** When `funnel_diagnosis` shows DISPLACEMENT→EXPANSION as the bottleneck.  
**Output:** `results/detection_sweep/<instrument>_<family>.json` + console ranked table.

```bash
python scripts/analysis/detection_sweep.py --instrument BNBUSDT --family all
python scripts/analysis/detection_sweep.py --instrument BNBUSDT --family expansion
python scripts/analysis/detection_sweep.py --instrument SOLUSDT --family all
```

### p3b_session_relax_diag

**Purpose:** Measure per-instrument impact of relaxing session filter to specific session combos.  
**When to use:** Before changing `allowed_sessions` config for any instrument.  
**Output:** Console — trades/PF/expectancy per relaxation level.

```bash
python scripts/analysis/p3b_session_relax_diag.py --instrument BNBUSDT
python scripts/analysis/p3b_session_relax_diag.py --instrument BNBUSDT --min-r-exp 0.20
python scripts/analysis/p3b_session_relax_diag.py --instrument BTCUSDT
python scripts/analysis/p3b_session_relax_diag.py --instrument ETHUSDT
python scripts/analysis/p3b_session_relax_diag.py --instrument SOLUSDT
```

### Other CRT-phase diagnostics (reference)

```bash
python scripts/analysis/p1_sweep_memory_diag.py
python scripts/analysis/p2_disp_exemption_diag.py
python scripts/analysis/p3a_zone_attribution_diag.py --instrument BTCUSDT
python scripts/analysis/p3a_zone_attribution_diag.py --instrument ETHUSDT
python scripts/analysis/p3a_zone_attribution_diag.py --instrument SOLUSDT --csv data/SOLUSDT_M15.csv
python scripts/analysis/p3c_zone_relax_diag.py --instrument BTCUSDT
python scripts/analysis/p3c_zone_relax_diag.py --instrument BTCUSDT --zone-relax-pct 0.60
python scripts/analysis/p3c_zone_relax_diag.py --instrument ETHUSDT --zone-relax-pct 0.60
python scripts/analysis/p3c1_build_trade_audit.py --instrument BTCUSDT
python scripts/analysis/p3c1_build_trade_audit.py --instrument ETHUSDT
python scripts/analysis/p4_execution_intent_attribution.py --instrument BNBUSDT
python scripts/analysis/p4_execution_intent_attribution.py --instrument BTCUSDT
python scripts/analysis/p4_execution_intent_attribution.py --instrument ETHUSDT
python scripts/analysis/p3b_gate_expired_counterfactual_rr.py ...
```

### Code map / citation generation

```bash
python scripts/analysis/gen_code_map.py                        # rewrites graph.dot + code-map.generated.md
python scripts/analysis/gen_code_map.py --package core         # print one package's slice
python scripts/analysis/gen_citation_map.py                    # write citation artifact
python scripts/analysis/gen_citation_map.py --check            # print to stdout, write nothing
python scripts/analysis/generate_cli_matrix.py
```

### Early invalidation + pattern library

```bash
python scripts/analysis/early_invalidation_ab.py --instrument ETHUSDT ...
python scripts/analysis/early_invalidation_exectrade_ab.py ...
python scripts/analysis/build_pattern_library.py --instrument ETHUSDT ...
python scripts/analysis/session_cost_audit.py results/roi_baseline/.../BNBUSDT_trades.csv
python scripts/analysis/compress_logs_for_llm.py --logs logs/**/*.jsonl
```

---

## Training Scripts

### phase5_calibration

**Purpose:** Re-calibrate Gaussian and RR model score thresholds against recent trade outcomes.  
**When to use:** After new live/backtest outcomes are available; when `score_outcome_corr` has drifted.  
**Output:** Updated `models/gaussian_*.json` + calibration report.

```bash
python scripts/training/phase5_calibration.py --audit-only          # check health only
python scripts/training/phase5_calibration.py --csv data/ --train   # re-calibrate
python scripts/training/phase5_calibration.py --integrate           # write calibrated scores back
python scripts/training/phase5_calibration.py --synthetic --train   # with synthetic data
```

### train_pipeline

**Purpose:** Retrain a specific model (Gaussian or TradeNet) after calibration gate passes.  
**When to use:** After `phase5_calibration` confirms corr ≥ 0.10 gate.  
**Output:** Updated model artifact in `models/`.

```bash
python scripts/training/train_pipeline.py gaussian
python scripts/training/train_pipeline.py tradenet --data data/training.json --output results/tradenet_result.json
```

### Other training (reference)

```bash
python scripts/training/auto_tuner_multi.py --data-dir data/ --output-dir results/tuner --n-iter 100 --seed 42 --workers 4 --train-split 1.0
python scripts/training/train_rr_model.py
python scripts/training/train_bitnet.py --epochs 300 --lr 0.001 --csv data/EURUSD_M15.csv
python scripts/training/build_stage1_dataset.py --market-scope crypto
python scripts/training/build_stage1_dataset.py --market-scope crypto --strict-layout
python scripts/data/build_rr_dataset.py --output models/rr_dataset.json
python scripts/data/build_tradenet_dataset.py logs/BNBUSDT_fusion.jsonl
```

---

## Governance / Promotion Scripts

### promotion_manager

**Purpose:** Promote a validated config to production; list versions; rollback.  
**When to use:** After `ConfigValidator.validate()` returns APPROVE.  
**Output:** Updated `configs/production/ACTIVE_VERSION` + append to `configs/promotion_log.jsonl`.

```bash
python src/governance/promotion_manager.py list
python src/governance/promotion_manager.py promote \
  --checkpoint results/tuner/checkpoint_multi.json \
  --version v5_multi_2026_06 \
  --data-dir data/
python -m src.governance.promotion_manager list
```

### config_validator (validate-prod)

**Purpose:** Run per-instrument backtest + hard/soft quality gates against current production config.  
**When to use:** Before every promotion; when config has been manually edited.  
**Output:** `results/validation_report.json` with APPROVE / REJECT decision.

```bash
python src/config_layer/config_validator.py validate-prod --data-dir data/
python -m src.config_layer.config_validator validate-prod
python -m src.config_layer.config_validator validate-params --params candidate.json
```

### _compute_hash (rehash)

**Purpose:** Recompute SHA-256 config hash after any manual edit to a production config file.  
**When to use:** Immediately after editing any `configs/production/*.json` by hand.  
**Output:** Updated `config_hash` field in the same JSON file.

```bash
python scripts/maintenance/_compute_hash.py
python scripts/update_config_hash.py "configs/production/v1_multi_2026_03.json"
python scripts/update_config_hash.py "configs/production/v1_multi_2026_03.json" --check
```

---

## Data Fetch / Preparation Scripts

### unified_data_builder

**Purpose:** Rebuild unified M15 CSV files from raw source data.  
**When to use:** When new candle data arrives; before re-calibration or retraining.  
**Output:** `data/<INSTRUMENT>_M15.csv`.

```bash
python scripts/data/unified_data_builder.py                   # all instruments
python scripts/data/unified_data_builder.py BTCUSDT
python scripts/data/unified_data_builder.py --dry-run
python scripts/data/unified_data_builder.py --validate-only
```

### Other data fetching (reference)

```bash
python scripts/data/fetch_crypto_ccxt.py --all
python scripts/data/fetch_crypto_ccxt.py --instrument BTCUSDT --start 2024-05-22 --end 2026-05-22
python scripts/data/fetch_forex_yfinance.py --all
python scripts/data/fetch_forex_yfinance.py --all --append
python scripts/data/fetch_forex_yfinance.py --instrument AUDUSD --start 2025-05-22 --end 2026-05-22
```

---

## pytest Commands

```bash
# Standard runs
pytest                                     # full suite
pytest --tb=no -q                          # silent pass/fail
pytest tests/ -x --tb=short               # stop on first failure
pytest --cov=src --cov-report=term-missing

# Domain-specific
pytest tests/test_engine_runner_*.py
pytest tests/test_ultron_*.py
pytest tests/test_agent_plan_compiler.py -v
pytest tests/test_execution_planner.py
pytest tests/test_shadow_promotion_gate.py
pytest tests/test_fusion_and_validator_regression.py tests/test_schema_contracts.py -v
pytest tests/features/test_feature_schema_registry.py tests/replay/test_replay_memory_engine.py -v
pytest tests/replay/test_timing_reconstructor.py -q
pytest tests/inout/

# Pre-promotion regression pack
python -m pytest tests/test_finalize_survivorship.py tests/test_execution_contract_v1.py tests/test_p4_observability.py -v
```

---

## Maintenance Scripts

```bash
python scripts/maintenance/cleanup_logs.py --days 7 --dry-run
python scripts/maintenance/reorganize_results.py --dry-run
python scripts/validate_integration.py
```

---

## Research Scripts (reference)

```bash
python scripts/research/opportunity_scanner.py --csv data/EURUSD_M15.csv --instrument EURUSD --tp-mult 2.0
python scripts/research/discover_zones.py --opportunities <f> --output models/zone_registry.json --n-clusters 8 --min-samples 15
python scripts/research/discover_zones.py --instrument BNBUSDT --promote
python scripts/research/phase0_economic_edge_diagnosis.py
python scripts/research/feature_region_oos_study.py
python scripts/research/edge_attribution_study.py
python scripts/research/phase6e_shadow_ab.py
python scripts/research/ingest_live_outcomes.py ...
python scripts/research/promotion_dryrun.py
```

---

## src/ Direct Entry Points

```bash
python src/runtime/baseline_capture.py --label phase0 --output-dir results/baseline
python src/runtime/live_engine_hook.py --dry-run
python -m src.agent.cli
python -m src.control_plane.server
```

---

## Groq Bridge / LLM Scripts

```bash
python scripts/groq_bridge/prepare_retrospective.py --source results.csv --last-n 20 --dry-run
python scripts/groq_bridge/prepare_retrospective.py --source results.csv --last-n 50
python scripts/groq_bridge/ingest_response.py --list-sessions
python scripts/groq_bridge/ingest_response.py --session RETRO_... --show
python scripts/groq_bridge/ingest_response.py --session RETRO_... --compare
python scripts/groq_bridge/ingest_response.py --session {session_id} --apply-config
```

---

## Inspection One-Liners

```bash
# Config / version checks
python -c "from config_layer.production_config import PROD_VERSION; print(PROD_VERSION)"
python -c "import json; r=json.load(open('models/gaussian_registry.json')); print(list(r.keys()))"
python -c "import json; print(sum(1 for _ in open('data/master_crypto_training.jsonl')))"
python -c "import csv; r=next(csv.DictReader(open('results/test_plan/EURUSD_trades.csv'))); print(r['config_version'])"
python -c "import json; d=json.load(open('results/test_plan/EURUSD_summary.json')); print(d['config_version'])"

# grep patterns used during sessions
grep -rn "events.jsonl\|def record\|flush\|class EventLog\|write.*event\|json.dump" src/runtime/backtest_v2.py
grep -rln "class .*EventLog\|STATE_TRANSITION" src/
ls -la results/ei_ab_fresh/run_*/
```
