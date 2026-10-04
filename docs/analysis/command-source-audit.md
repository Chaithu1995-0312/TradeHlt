# STRICT SOURCE-OF-TRUTH COMMAND ARCHITECTURE AUDIT

Scope: active commands returned by src/control_plane/registry.py::core_command_specs(). No future architecture is described. Unknown items are written as NOT FOUND IN SOURCE.

Source-of-truth registry: src/control_plane/registry.py::core_command_specs().
Dispatcher: src/control_plane/registry.py::build_command_line(), src/control_plane/jobs.py::JobManager.create_run(), and src/control_plane/jobs.py::JobManager._execute_run().

# GLOBAL EXECUTION GRAPH

USER/UI -> src/control_plane/server.py::ControlPlaneAPI.commands_payload()/create_run_payload() -> src/control_plane/registry.py::core_command_specs()/build_command_line() -> src/control_plane/jobs.py::JobManager.create_run() -> src/control_plane/jobs.py::JobManager._execute_run() -> subprocess.Popen(python script or python -m module) -> command entry callable -> downstream functions/classes -> data/logs/results/models/configs outputs proven in command sections.

Control-plane side effects: JobManager.create_run() writes run state under results/{instrument}; JobManager._execute_run() creates stdout/stderr/log files under logs/{instrument} and discovers artifacts after subprocess completion.

# COMMAND DEPENDENCY MATRIX

| Command | Calls | Depends On | Produces |
|---|---|---|---|
| data.prepare_data | Called by control-plane JobManager subprocess; downstream listed in command flow. | Registry script scripts/data/prepare_data.py; CLI/config/model dependencies listed below | M15 CSVs under --output/data from write_csv(); validation messages from validate()/validate_existing(). |
| data.unified_data_builder | Called by control-plane JobManager subprocess; downstream listed in command flow. | Registry script scripts/data/unified_data_builder.py; CLI/config/model dependencies listed below | M15 CSVs under --output-dir from build_instrument(); logs from setup_logging(). |
| tuning.auto_tuner_multi | Called by control-plane JobManager subprocess; downstream listed in command flow. | Registry script scripts/training/auto_tuner_multi.py; CLI/config/model dependencies listed below | results/tuner/live_log_multi.jsonl, checkpoint_multi.json, and run artifacts under --output-dir. |
| tuning.auto_tuner | Called by control-plane JobManager subprocess; downstream listed in command flow. | Registry script scripts/training/auto_tuner.py; CLI/config/model dependencies listed below | results/tuner/live_log.jsonl, checkpoint JSON, and tuner_report.json under --output-dir. |
| validation.config_validator | Called by control-plane JobManager subprocess; downstream listed in command flow. | Registry script src/config_layer/config_validator.py; CLI/config/model dependencies listed below | Optional --output report JSON; temporary BacktestRunner output under results/validation_tmp. |
| promotion.manager | Calls ConfigValidator; called by promotion.promote_v2. | Registry script src/governance/promotion_manager.py; CLI/config/model dependencies listed below | configs/production/{version}.json, configs/production/ACTIVE_VERSION, configs/promotion_log.jsonl, and archived prior configs. |
| governance.orchestrator | Called by control-plane JobManager subprocess; downstream listed in command flow. | Registry script src/governance/orchestrator.py; CLI/config/model dependencies listed below | logs/meta_prompt.txt, logs/governance_audit.jsonl, and possible ShadowPromotionGate promotion side effects. |
| replay.unified | Calls BacktestRunner and backtest_bitnet.run_backtest. | Registry script src/runtime/unified_replay_harness.py; CLI/config/model dependencies listed below | Month-window CSV when requested and alignment summary JSON under results/alignment. |
| backtest.v2 | Downstream of validators, tuners, portfolio validation, SL/TP comparator, unified replay, and control-plane jobs. | Registry script src/runtime/backtest_v2.py; CLI/config/model dependencies listed below | summary.json, trades.csv, events.jsonl, and report.txt under {output}/{run_id}_{instrument}. |
| backtest.bitnet | Called by replay.unified. | Registry script src/runtime/backtest_bitnet.py; CLI/config/model dependencies listed below | logs/backtest_decisions_{symbol}_{timestamp}.jsonl and optional --output CSV or printed JSON. |
| baseline.capture | Called by control-plane JobManager subprocess; downstream listed in command flow. | Registry script src/runtime/baseline_capture.py; CLI/config/model dependencies listed below | results/baseline/{timestamp}_{label}/manifest.json. |
| live.inout_runner | Called by control-plane JobManager subprocess; downstream listed in command flow. | Registry script inout.runner; CLI/config/model dependencies listed below | NOT FOUND IN SOURCE for active command outputs. |
| training.opportunity_scanner | Called by control-plane JobManager subprocess; downstream listed in command flow. | Registry script scripts/research/opportunity_scanner.py; CLI/config/model dependencies listed below | {output_dir}/{instrument}/{run_id}/opportunities.jsonl plus stdout OUTPUT markers. |
| training.phase5_calibration | Called by control-plane JobManager subprocess; downstream listed in command flow. | Registry script scripts/training/phase5_calibration.py; CLI/config/model dependencies listed below | p5_calibration_{version}.json reports, model artifacts under models, and optional model registry updates. |
| training.discover_zones | Called by control-plane JobManager subprocess; downstream listed in command flow. | Registry script scripts/research/discover_zones.py; CLI/config/model dependencies listed below | zone_registry JSON files under models or supplied --output; optional zone gate registry promotion. |
| training.build_rr_dataset | Called by control-plane JobManager subprocess; downstream listed in command flow. | Registry script scripts/data/build_rr_dataset.py; CLI/config/model dependencies listed below | rr_dataset JSON, versioned dataset copies, and RR registry updates. |
| training.train_rr_model | Called by control-plane JobManager subprocess; downstream listed in command flow. | Registry script scripts/training/train_rr_model.py; CLI/config/model dependencies listed below | rr_model_{version}.json, RR registry updates, and canonical models/rr_model.json when promoted. |
| training.train_pipeline | Called by control-plane JobManager subprocess; downstream listed in command flow. | Registry script scripts/training/train_pipeline.py; CLI/config/model dependencies listed below | TradeNet model via save_model() or Gaussian registry/model outputs from run_gaussian_update(). |
| training.auto_train | Calls opportunity_scanner, compress_logs, phase5_calibration, and promote_gaussian via subprocess/function calls. | Registry script scripts/auto_train_from_opportunities.py; CLI/config/model dependencies listed below | Child command opportunities, compressed summaries, phase5 reports/models, and optional Gaussian registry promotion. |
| analysis.compress_logs | Called by control-plane JobManager subprocess; downstream listed in command flow. | Registry script scripts/analysis/compress_logs_for_llm.py; CLI/config/model dependencies listed below | Compressed summary JSON at --output or logs/{instrument}/{run_id}/compressed.json. |
| maintenance.update_config_hash | Called by control-plane JobManager subprocess; downstream listed in command flow. | Registry script scripts/update_config_hash.py; CLI/config/model dependencies listed below | Updated config JSON config_hash unless --check/--dry-run; stdout messages. |
| maintenance.health_checker | Called by control-plane JobManager subprocess; downstream listed in command flow. | Registry script src/monitoring/health_checker.py; CLI/config/model dependencies listed below | HTTP JSON responses for /health and /status; flow logger output. |
| maintenance.build_zone_registry | Called by control-plane JobManager subprocess; downstream listed in command flow. | Registry script scripts/misc/build_zone_registry_from_trades.py; CLI/config/model dependencies listed below | models/bitnet/{instrument}/zone_registry.json or models/zone_registry.json. |
| groq.prepare_retrospective | Called by control-plane JobManager subprocess; downstream listed in command flow. | Registry script scripts/groq_bridge/prepare_retrospective.py; CLI/config/model dependencies listed below | logs/groq_bridge/pending_{session_id}.txt and bridge session/trace files unless dry-run. |
| groq.ingest_response | Can call groq.apply_llm_suggestions via subprocess. | Registry script scripts/groq_bridge/ingest_response.py; CLI/config/model dependencies listed below | logs/groq_bridge/response_{session_id}.txt, insight/session registry updates, and optional child training outputs. |
| groq.apply_llm_suggestions | Calls phase5_calibration, discover_zones, or rr miner subprocess paths based on target model. | Registry script scripts/groq_bridge/apply_llm_suggestions.py; CLI/config/model dependencies listed below | Downstream outputs from phase5_calibration.py or discover_zones.py; rr branch output only if hard-coded miner path exists. |
| analysis.daily_crypto_structure | Called by control-plane JobManager subprocess; downstream listed in command flow. | Registry script scripts/analysis/daily_crypto_structure.py; CLI/config/model dependencies listed below | CSV at --output, default btc_daily_structure.csv. |
| analysis.schema_audit | Called by control-plane JobManager subprocess; downstream listed in command flow. | Registry script scripts/analysis/schema_audit.py; CLI/config/model dependencies listed below | stdout only; no file write found. |
| analysis.sl_tp_comparator | Calls BacktestRunner. | Registry script src/analytics/sl_tp_comparator.py; CLI/config/model dependencies listed below | Comparison JSON, default results/sl_tp_comparison.json. |
| analysis.fusion_shadow | Called by control-plane JobManager subprocess; downstream listed in command flow. | Registry script src/runtime/analyze_fusion_shadow.py; CLI/config/model dependencies listed below | fusion_shadow_analysis_{timestamp}.json under results/validation/automation by default. |
| agent.cli | Called by control-plane JobManager subprocess; downstream listed in command flow. | Registry script src/agent/cli.py; CLI/config/model dependencies listed below | stdout responses, session files under configured session_dir, and audit log through AgentCore/AuditLogger. |
| data.historical_fetcher | Called by control-plane JobManager subprocess; downstream listed in command flow. | Registry script src/data_ingestion/historical_fetcher.py; CLI/config/model dependencies listed below | Rows inserted into configured OHLCV database table; stdout/log output. |
| data.fetch_alphavantage | Called by control-plane JobManager subprocess; downstream listed in command flow. | Registry script scripts/data/fetch_candles_alphavantage.py; CLI/config/model dependencies listed below | CSV under output directory from AlphaVantageCandleFetcher._write_csv(). |
| data.fetch_hummingbot | Called by control-plane JobManager subprocess; downstream listed in command flow. | Registry script scripts/data/fetch_candles_hummingbot.py; CLI/config/model dependencies listed below | CSV under output directory from HummingbotCandleFetcher._write_csv(). |
| tuning.auto_tuner_gemini_gate | Called by control-plane JobManager subprocess; downstream listed in command flow. | Registry script scripts/training/auto_tuner_gemini_gate.py; CLI/config/model dependencies listed below | results/tuner/live_log_gemini_pro.jsonl, results/tuner/runs_gemini_pro, and checkpoint_gemini_pro.json. |
| validation.portfolio | Calls BacktestRunner. | Registry script src/governance/portfolio_validation.py; CLI/config/model dependencies listed below | {output}/portfolio_report.json and printed portfolio report. |
| promotion.promote_v2 | Calls PromotionManager.promote_from_report(). | Registry script scripts/governance/promote_v2.py; CLI/config/model dependencies listed below | results/{version}_{timestamp}.json and production registry writes through PromotionManager when approved. |
| training.train_bitnet | Called by control-plane JobManager subprocess; downstream listed in command flow. | Registry script scripts/training/train_bitnet.py; CLI/config/model dependencies listed below | JSON model at --out, default model.json. |

# COMMAND: data.prepare_data

## 1. Human Purpose
Convert and validate raw source files into normalized M15 outputs. Source: src/control_plane/registry.py::core_command_specs() line 198.

## 2. Entry Point
File: scripts/data/prepare_data.py
Callable: scripts/data/prepare_data.py::main(), process(), validate_existing()
Registry Reference: src/control_plane/registry.py::core_command_specs() line 198; mode python-file.

## 3. CLI Parameters
Registry-declared parameters:
| Parameter | Type/Kind | Default | Required | Source |
|---|---|---|---|---|
| --source | choice | 'standard' | no | src/control_plane/registry.py::core_command_specs() line 198; choices=histdata,binance,standard |
| --files | file-multi | [] | no | src/control_plane/registry.py::core_command_specs() line 198 |
| --instrument | choice | 'EURUSD' | no | src/control_plane/registry.py::core_command_specs() line 198; choices=EURUSD,GBPUSD,AUDUSD,USDJPY,USDCAD,USDCHF,NZDUSD,EURGBP |
| --output | str | 'data' | no | src/control_plane/registry.py::core_command_specs() line 198 |
| --already-m15 | bool | False | no | src/control_plane/registry.py::core_command_specs() line 198 |
| --validate-only | bool | False | no | src/control_plane/registry.py::core_command_specs() line 198 |

Actual argparse parameters found in entry file:
| Parameter | Type | Default | Required | Source |
|---|---|---|---|---|
| --source | str | none | false | scripts/data/prepare_data.py argparse line 484; choices=[histdata, binance, standard] |
| --files | str | [] | false | scripts/data/prepare_data.py argparse line 486; nargs=+ |
| --instrument | str | UNKNOWN | false | scripts/data/prepare_data.py argparse line 488 |
| --output | str | data | false | scripts/data/prepare_data.py argparse line 490 |
| --already-m15 | bool | none | false | scripts/data/prepare_data.py argparse line 492; action=store_true |
| --validate-only | bool | none | false | scripts/data/prepare_data.py argparse line 494; action=store_true |

## 4. Runtime Flow
1. main() dispatches validate_existing() for validate-only or process(); process() selects parse_histdata()/parse_binance()/parse_standard(), resamples with resample_m15(), validates, and writes CSV through write_csv().

## 5. Inputs
- CLI parameters listed above from registry/argparse source.

## 6. Outputs
| Output | Path | Produced By |
|---|---|---|
| M15 CSVs under --output/data from write_csv(); validation messages from validate()/validate_existing(). | see output text | source functions listed in Runtime Flow/Entry Point |

## 7. External Dependencies
NOT FOUND IN SOURCE for API/network calls. Local Python imports and filesystem dependencies are listed in Inputs/Flow.

## 8. Orchestration Relationships
Called by src/control_plane/jobs.py::JobManager._execute_run() as a registered subprocess. Additional downstream calls are in Runtime Flow.

## 9. State Classification
RESEARCH_ONLY - registered command runs offline data, tuning, training, replay, analysis, or maintenance behavior and no live production side effect is proven in this command section.

## 10. Hidden Risks / Important Findings
- Registry --instrument default is EURUSD, actual argparse default is UNKNOWN.

# COMMAND: data.unified_data_builder

## 1. Human Purpose
Build unified multi-instrument data outputs for CRT workflows. Source: src/control_plane/registry.py::core_command_specs() line 219.

## 2. Entry Point
File: scripts/data/unified_data_builder.py
Callable: scripts/data/unified_data_builder.py::main(), run_batch(), build_instrument()
Registry Reference: src/control_plane/registry.py::core_command_specs() line 219; mode python-file.

## 3. CLI Parameters
Registry-declared parameters:
| Parameter | Type/Kind | Default | Required | Source |
|---|---|---|---|---|
| positional instruments | list | [] | no | src/control_plane/registry.py::core_command_specs() line 219 |
| --data-dir | str | 'data' | no | src/control_plane/registry.py::core_command_specs() line 219 |
| --output-dir | str | 'data' | no | src/control_plane/registry.py::core_command_specs() line 219 |
| --validate-only | bool | False | no | src/control_plane/registry.py::core_command_specs() line 219 |
| --dry-run | bool | False | no | src/control_plane/registry.py::core_command_specs() line 219 |

Actual argparse parameters found in entry file:
| Parameter | Type | Default | Required | Source |
|---|---|---|---|---|
| instruments | str | none | positional | scripts/data/unified_data_builder.py argparse line 551; nargs=* |
| --data-dir | str | data | false | scripts/data/unified_data_builder.py argparse line 555 |
| --output-dir | str | data | false | scripts/data/unified_data_builder.py argparse line 559 |
| --validate-only | bool | none | false | scripts/data/unified_data_builder.py argparse line 563; action=store_true |
| --dry-run | bool | none | false | scripts/data/unified_data_builder.py argparse line 567; action=store_true |
| --verbose, -v | bool | none | false | scripts/data/unified_data_builder.py argparse line 571; action=store_true |

## 4. Runtime Flow
1. main() calls setup_logging(), then validate_existing() or run_batch(); run_batch() iterates instruments and build_instrument() detects source layout and writes/validates M15 CSVs.

## 5. Inputs
- CLI parameters listed above from registry/argparse source.

## 6. Outputs
| Output | Path | Produced By |
|---|---|---|
| M15 CSVs under --output-dir from build_instrument(); logs from setup_logging(). | see output text | source functions listed in Runtime Flow/Entry Point |

## 7. External Dependencies
NOT FOUND IN SOURCE for API/network calls. Local Python imports and filesystem dependencies are listed in Inputs/Flow.

## 8. Orchestration Relationships
Called by src/control_plane/jobs.py::JobManager._execute_run() as a registered subprocess. Additional downstream calls are in Runtime Flow.

## 9. State Classification
RESEARCH_ONLY - registered command runs offline data, tuning, training, replay, analysis, or maintenance behavior and no live production side effect is proven in this command section.

## 10. Hidden Risks / Important Findings
- Actual argparse includes --verbose/-v; registry omits it.

# COMMAND: tuning.auto_tuner_multi

## 1. Human Purpose
Run multi-instrument tuner and emit checkpoint artifacts. Source: src/control_plane/registry.py::core_command_specs() line 238.

## 2. Entry Point
File: scripts/training/auto_tuner_multi.py
Callable: scripts/training/auto_tuner_multi.py::main(), AutoTuner, ResultStore
Registry Reference: src/control_plane/registry.py::core_command_specs() line 238; mode python-file.

## 3. CLI Parameters
Registry-declared parameters:
| Parameter | Type/Kind | Default | Required | Source |
|---|---|---|---|---|
| --csv | file | None | no | src/control_plane/registry.py::core_command_specs() line 238 |
| --instrument | choice | 'EURUSD' | no | src/control_plane/registry.py::core_command_specs() line 238; choices=EURUSD,GBPUSD,AUDUSD,USDJPY,USDCAD,USDCHF,NZDUSD,EURGBP |
| --data-dir | str | 'data' | no | src/control_plane/registry.py::core_command_specs() line 238 |
| --instruments | list | [] | no | src/control_plane/registry.py::core_command_specs() line 238 |
| --output-dir | str | 'results/tuner' | no | src/control_plane/registry.py::core_command_specs() line 238 |
| --n-iter | int | 100 | no | src/control_plane/registry.py::core_command_specs() line 238 |
| --seed | int | 42 | no | src/control_plane/registry.py::core_command_specs() line 238 |
| --workers | int | 4 | no | src/control_plane/registry.py::core_command_specs() line 238 |
| --train-split | float | 1.0 | no | src/control_plane/registry.py::core_command_specs() line 238 |
| --no-llm | bool | False | no | src/control_plane/registry.py::core_command_specs() line 238 |

Actual argparse parameters found in entry file:
| Parameter | Type | Default | Required | Source |
|---|---|---|---|---|
| --csv | str | none | false | scripts/training/auto_tuner_multi.py argparse line 871 |
| --instrument | str | none | false | scripts/training/auto_tuner_multi.py argparse line 872 |
| --data-dir | str | data | false | scripts/training/auto_tuner_multi.py argparse line 873 |
| --instruments | str | none | false | scripts/training/auto_tuner_multi.py argparse line 874; nargs=+ |
| --output-dir | str | results/tuner | false | scripts/training/auto_tuner_multi.py argparse line 875 |
| --n-iter | int | 100 | false | scripts/training/auto_tuner_multi.py argparse line 876 |
| --seed | int | 42 | false | scripts/training/auto_tuner_multi.py argparse line 877 |
| --workers | int | os.cpu_count() or 4 | false | scripts/training/auto_tuner_multi.py argparse line 878 |
| --train-split | float | 1.0 | false | scripts/training/auto_tuner_multi.py argparse line 879 |
| --no-llm | bool | none | false | scripts/training/auto_tuner_multi.py argparse line 881; action=store_true |

## 4. Runtime Flow
1. main() builds CSV paths, constructs AutoTuner, and calls AutoTuner.run(); per-instrument runs use CandleLoader and BacktestRunner through _run_single_instrument(); ResultStore writes tuner logs/checkpoints.

## 5. Inputs
- CLI parameters listed above from registry/argparse source.

## 6. Outputs
| Output | Path | Produced By |
|---|---|---|
| results/tuner/live_log_multi.jsonl, checkpoint_multi.json, and run artifacts under --output-dir. | see output text | source functions listed in Runtime Flow/Entry Point |

## 7. External Dependencies
NOT FOUND IN SOURCE for API/network calls. Local Python imports and filesystem dependencies are listed in Inputs/Flow.

## 8. Orchestration Relationships
Called by src/control_plane/jobs.py::JobManager._execute_run() as a registered subprocess. Additional downstream calls are in Runtime Flow.

## 9. State Classification
RESEARCH_ONLY - registered command runs offline data, tuning, training, replay, analysis, or maintenance behavior and no live production side effect is proven in this command section.

## 10. Hidden Risks / Important Findings
- NOT FOUND IN SOURCE

# COMMAND: tuning.auto_tuner

## 1. Human Purpose
Run single/multi instrument tuner for parameter optimization. Source: src/control_plane/registry.py::core_command_specs() line 261.

## 2. Entry Point
File: scripts/training/auto_tuner.py
Callable: scripts/training/auto_tuner.py::main(), AutoTuner, MultiInstrumentTuner
Registry Reference: src/control_plane/registry.py::core_command_specs() line 261; mode python-file.

## 3. CLI Parameters
Registry-declared parameters:
| Parameter | Type/Kind | Default | Required | Source |
|---|---|---|---|---|
| --csv | file | None | no | src/control_plane/registry.py::core_command_specs() line 261 |
| --instrument | choice | 'EURUSD' | no | src/control_plane/registry.py::core_command_specs() line 261; choices=EURUSD,GBPUSD,AUDUSD,USDJPY,USDCAD,USDCHF,NZDUSD,EURGBP |
| --data-dir | str | 'data' | no | src/control_plane/registry.py::core_command_specs() line 261 |
| --instruments | list | [] | no | src/control_plane/registry.py::core_command_specs() line 261 |
| --output-dir | str | 'results/tuner' | no | src/control_plane/registry.py::core_command_specs() line 261 |
| --n-iter | int | 100 | no | src/control_plane/registry.py::core_command_specs() line 261 |
| --seed | int | 42 | no | src/control_plane/registry.py::core_command_specs() line 261 |
| --resume | file | None | no | src/control_plane/registry.py::core_command_specs() line 261 |
| --multi | bool | False | no | src/control_plane/registry.py::core_command_specs() line 261 |
| --verbose | bool | False | no | src/control_plane/registry.py::core_command_specs() line 261 |

Actual argparse parameters found in entry file:
| Parameter | Type | Default | Required | Source |
|---|---|---|---|---|
| --csv | str | none | false | scripts/training/auto_tuner.py argparse line 839 |
| --instrument | str | none | false | scripts/training/auto_tuner.py argparse line 840 |
| --data-dir | str | data | false | scripts/training/auto_tuner.py argparse line 841 |
| --instruments | str | none | false | scripts/training/auto_tuner.py argparse line 842; nargs=+ |
| --output-dir | str | results/tuner | false | scripts/training/auto_tuner.py argparse line 843 |
| --n-iter | int | 100 | false | scripts/training/auto_tuner.py argparse line 844 |
| --seed | int | 42 | false | scripts/training/auto_tuner.py argparse line 845 |
| --resume | str | none | false | scripts/training/auto_tuner.py argparse line 846 |
| --multi | bool | none | false | scripts/training/auto_tuner.py argparse line 847; action=store_true |
| --verbose, -v | bool | none | false | scripts/training/auto_tuner.py argparse line 849; action=store_true |

## 4. Runtime Flow
1. main() selects AutoTuner or MultiInstrumentTuner, optionally resumes from checkpoint, and calls run(); tuner paths execute BacktestRunner and write report/checkpoint artifacts.

## 5. Inputs
- CLI parameters listed above from registry/argparse source.

## 6. Outputs
| Output | Path | Produced By |
|---|---|---|
| results/tuner/live_log.jsonl, checkpoint JSON, and tuner_report.json under --output-dir. | see output text | source functions listed in Runtime Flow/Entry Point |

## 7. External Dependencies
NOT FOUND IN SOURCE for API/network calls. Local Python imports and filesystem dependencies are listed in Inputs/Flow.

## 8. Orchestration Relationships
Called by src/control_plane/jobs.py::JobManager._execute_run() as a registered subprocess. Additional downstream calls are in Runtime Flow.

## 9. State Classification
RESEARCH_ONLY - registered command runs offline data, tuning, training, replay, analysis, or maintenance behavior and no live production side effect is proven in this command section.

## 10. Hidden Risks / Important Findings
- NOT FOUND IN SOURCE

# COMMAND: validation.config_validator

## 1. Human Purpose
Validate production or candidate params with quality gates. Source: src/control_plane/registry.py::core_command_specs() line 286.

## 2. Entry Point
File: src/config_layer/config_validator.py
Callable: src/config_layer/config_validator.py::ConfigValidator.validate(); CLI block
Registry Reference: src/control_plane/registry.py::core_command_specs() line 286; mode python-file.

## 3. CLI Parameters
Registry-declared parameters:
| Parameter | Type/Kind | Default | Required | Source |
|---|---|---|---|---|
| positional subcommand | choice | 'validate-prod' | no | src/control_plane/registry.py::core_command_specs() line 286; choices=validate-prod,validate-params |
| --data-dir | str | 'data' | no | src/control_plane/registry.py::core_command_specs() line 286; applies_to=validate-prod,validate-params |
| --version | str | None | no | src/control_plane/registry.py::core_command_specs() line 286; applies_to=validate-prod |
| --output | str | 'results/validation_report.json' | no | src/control_plane/registry.py::core_command_specs() line 286; applies_to=validate-prod,validate-params |
| --params | file | None | no | src/control_plane/registry.py::core_command_specs() line 286; applies_to=validate-params |
| --config-id | str | 'cli_validation' | no | src/control_plane/registry.py::core_command_specs() line 286; applies_to=validate-params |

Actual argparse parameters found in entry file:
| Parameter | Type | Default | Required | Source |
|---|---|---|---|---|
| --data-dir | str | data | false | src/config_layer/config_validator.py argparse line 524 |
| --version | str | none | false | src/config_layer/config_validator.py argparse line 525 |
| --output | str | none | false | src/config_layer/config_validator.py argparse line 526 |
| --params | str | none | True | src/config_layer/config_validator.py argparse line 530 |
| --data-dir | str | data | false | src/config_layer/config_validator.py argparse line 531 |
| --config-id | str | cli_validation | false | src/config_layer/config_validator.py argparse line 532 |
| --output | str | none | false | src/config_layer/config_validator.py argparse line 533 |

## 4. Runtime Flow
1. CLI subcommands validate-prod/validate-params construct ConfigValidator; ConfigValidator.validate() calls _run_instrument(), _aggregate_metrics(), and _run_quality_gates(); _run_instrument() uses CandleLoader and BacktestRunner.

## 5. Inputs
- CLI parameters listed above from registry/argparse source.
- Production config section config_validator via get_prod_section() and data CSVs from --data-dir.

## 6. Outputs
| Output | Path | Produced By |
|---|---|---|
| Optional --output report JSON; temporary BacktestRunner output under results/validation_tmp. | see output text | source functions listed in Runtime Flow/Entry Point |

## 7. External Dependencies
NOT FOUND IN SOURCE for API/network calls. Local Python imports and filesystem dependencies are listed in Inputs/Flow.

## 8. Orchestration Relationships
Called by src/control_plane/jobs.py::JobManager._execute_run() as a registered subprocess. Additional downstream calls are in Runtime Flow.

## 9. State Classification
LIVE_PRODUCTION - used by PromotionManager and applies production quality gates before config promotion.

## 10. Hidden Risks / Important Findings
- NOT FOUND IN SOURCE

# COMMAND: promotion.manager

## 1. Human Purpose
List and promote validated configs into production registry. Source: src/control_plane/registry.py::core_command_specs() line 309.

## 2. Entry Point
File: src/governance/promotion_manager.py
Callable: src/governance/promotion_manager.py::PromotionManager
Registry Reference: src/control_plane/registry.py::core_command_specs() line 309; mode python-file.

## 3. CLI Parameters
Registry-declared parameters:
| Parameter | Type/Kind | Default | Required | Source |
|---|---|---|---|---|
| positional subcommand | choice | 'list' | no | src/control_plane/registry.py::core_command_specs() line 309; choices=list,promote,from-report |
| --checkpoint | file | None | no | src/control_plane/registry.py::core_command_specs() line 309; applies_to=promote |
| --version | str | None | no | src/control_plane/registry.py::core_command_specs() line 309; applies_to=promote,from-report |
| --data-dir | str | 'data' | no | src/control_plane/registry.py::core_command_specs() line 309; applies_to=promote |
| --instruments | list | [] | no | src/control_plane/registry.py::core_command_specs() line 309; applies_to=promote |
| --notes | str | '' | no | src/control_plane/registry.py::core_command_specs() line 309; applies_to=promote,from-report |
| --no-llm | bool | False | no | src/control_plane/registry.py::core_command_specs() line 309; applies_to=promote |
| --report | file | None | no | src/control_plane/registry.py::core_command_specs() line 309; applies_to=from-report |

Actual argparse parameters found in entry file:
| Parameter | Type | Default | Required | Source |
|---|---|---|---|---|
| --checkpoint | str | none | True | src/governance/promotion_manager.py argparse line 657 |
| --version | str | none | True | src/governance/promotion_manager.py argparse line 659 |
| --data-dir | str | data | false | src/governance/promotion_manager.py argparse line 661 |
| --instruments | str | [EURUSD, GBPUSD, BTCUSDT, XAUUSD] | false | src/governance/promotion_manager.py argparse line 662; nargs=+ |
| --notes | str |  | false | src/governance/promotion_manager.py argparse line 664 |
| --no-llm | bool | none | false | src/governance/promotion_manager.py argparse line 665; action=store_true |
| --report | str | none | True | src/governance/promotion_manager.py argparse line 669 |
| --version | str | none | false | src/governance/promotion_manager.py argparse line 670 |
| --notes | str |  | false | src/governance/promotion_manager.py argparse line 672 |

## 4. Runtime Flow
1. CLI subcommands list/promote/from-report call PromotionManager; promote_from_tuner_checkpoint() validates with ConfigValidator; _execute_promotion(), _write_to_registry(), and _log_event() write production registry and audit state.

## 5. Inputs
- CLI parameters listed above from registry/argparse source.
- Tuner checkpoint/report JSON and configs/production registry files.

## 6. Outputs
| Output | Path | Produced By |
|---|---|---|
| configs/production/{version}.json, configs/production/ACTIVE_VERSION, configs/promotion_log.jsonl, and archived prior configs. | see output text | source functions listed in Runtime Flow/Entry Point |

## 7. External Dependencies
NOT FOUND IN SOURCE for API/network calls. Local Python imports and filesystem dependencies are listed in Inputs/Flow.

## 8. Orchestration Relationships
Calls ConfigValidator; called by promotion.promote_v2.

## 9. State Classification
LIVE_PRODUCTION - writes configs/production ACTIVE_VERSION and promotion audit log.

## 10. Hidden Risks / Important Findings
- NOT FOUND IN SOURCE

# COMMAND: governance.orchestrator

## 1. Human Purpose
Run reflection → meta-governor → shadow gate → promotion loop. Source: src/control_plane/registry.py::core_command_specs() line 337.

## 2. Entry Point
File: src/governance/orchestrator.py
Callable: src/governance/orchestrator.py::GovernanceOrchestrator.run(), main()
Registry Reference: src/control_plane/registry.py::core_command_specs() line 337; mode python-file.

## 3. CLI Parameters
Registry-declared parameters:
| Parameter | Type/Kind | Default | Required | Source |
|---|---|---|---|---|
| --compressed-summary | file | None | no | src/control_plane/registry.py::core_command_specs() line 337 |
| --collector-log | file | None | no | src/control_plane/registry.py::core_command_specs() line 337 |
| --trades-csv | file | None | no | src/control_plane/registry.py::core_command_specs() line 337 |
| --baseline-pnl | float | None | yes | src/control_plane/registry.py::core_command_specs() line 337 |
| --active-config | file | 'configs/production/v2_multi_2026_04.json' | no | src/control_plane/registry.py::core_command_specs() line 337 |
| --bitnet-bin | str | './bitnet/bin/main' | no | src/control_plane/registry.py::core_command_specs() line 337 |
| --model-path | str | './models/bitnet_b1_58_70b.gguf' | no | src/control_plane/registry.py::core_command_specs() line 337 |
| --audit-log | str | 'logs/governance_audit.jsonl' | no | src/control_plane/registry.py::core_command_specs() line 337 |
| --prompt-path | str | 'logs/meta_prompt.txt' | no | src/control_plane/registry.py::core_command_specs() line 337 |

Actual argparse parameters found in entry file:
| Parameter | Type | Default | Required | Source |
|---|---|---|---|---|
| --collector-log | str | none | false | src/governance/orchestrator.py argparse line 228 |
| --trades-csv | str | none | false | src/governance/orchestrator.py argparse line 231 |
| --compressed-summary | str | none | false | src/governance/orchestrator.py argparse line 234 |
| --baseline-pnl | float | none | True | src/governance/orchestrator.py argparse line 238 |
| --active-config | str | configs/production/v1_multi_2026_03.json | false | src/governance/orchestrator.py argparse line 240 |
| --bitnet-bin | str | ./bitnet/bin/main | false | src/governance/orchestrator.py argparse line 243 |
| --model-path | str | ./models/bitnet_b1_58_70b.gguf | false | src/governance/orchestrator.py argparse line 245 |
| --audit-log | str | logs/governance_audit.jsonl | false | src/governance/orchestrator.py argparse line 247 |
| --prompt-path | str | logs/meta_prompt.txt | false | src/governance/orchestrator.py argparse line 249 |

## 4. Runtime Flow
1. main() constructs GovernanceOrchestrator; run() loads compressed or raw collector/trade inputs, writes/uses prompt path, invokes MetaGovernorExecutor, and calls ShadowPromotionGate.promote_if_superior().

## 5. Inputs
- CLI parameters listed above from registry/argparse source.

## 6. Outputs
| Output | Path | Produced By |
|---|---|---|
| logs/meta_prompt.txt, logs/governance_audit.jsonl, and possible ShadowPromotionGate promotion side effects. | see output text | source functions listed in Runtime Flow/Entry Point |

## 7. External Dependencies
NOT FOUND IN SOURCE for API/network calls. Local Python imports and filesystem dependencies are listed in Inputs/Flow.

## 8. Orchestration Relationships
Called by src/control_plane/jobs.py::JobManager._execute_run() as a registered subprocess. Additional downstream calls are in Runtime Flow.

## 9. State Classification
LIVE_PRODUCTION - uses active config and ShadowPromotionGate promotion path.

## 10. Hidden Risks / Important Findings
- NOT FOUND IN SOURCE

# COMMAND: replay.unified

## 1. Human Purpose
Compare v2 execution truth and BitNet gate modes on the same data. Source: src/control_plane/registry.py::core_command_specs() line 366.

## 2. Entry Point
File: src/runtime/unified_replay_harness.py
Callable: src/runtime/unified_replay_harness.py::main(), run_unified_replay()
Registry Reference: src/control_plane/registry.py::core_command_specs() line 366; mode python-file.

## 3. CLI Parameters
Registry-declared parameters:
| Parameter | Type/Kind | Default | Required | Source |
|---|---|---|---|---|
| --config | file | 'configs/production/v2_multi_2026_04.json' | no | src/control_plane/registry.py::core_command_specs() line 366 |
| --data | file | None | yes | src/control_plane/registry.py::core_command_specs() line 366 |
| --months | int | None | no | src/control_plane/registry.py::core_command_specs() line 366 |
| --output-dir | str | 'results/alignment' | no | src/control_plane/registry.py::core_command_specs() line 366 |

Actual argparse parameters found in entry file:
| Parameter | Type | Default | Required | Source |
|---|---|---|---|---|
| --config | str | configs/production/v1_multi_2026_03.json | false | src/runtime/unified_replay_harness.py argparse line 218 |
| --data | str | none | True | src/runtime/unified_replay_harness.py argparse line 219 |
| --months | int | none | false | src/runtime/unified_replay_harness.py argparse line 220 |
| --output-dir | str | results/alignment | false | src/runtime/unified_replay_harness.py argparse line 221 |

## 4. Runtime Flow
1. main() loads config and data file/directory; run_unified_replay() optionally materializes a month-window CSV, runs BacktestRunner and run_backtest_bitnet, then writes alignment summary JSON.

## 5. Inputs
- CLI parameters listed above from registry/argparse source.

## 6. Outputs
| Output | Path | Produced By |
|---|---|---|
| Month-window CSV when requested and alignment summary JSON under results/alignment. | see output text | source functions listed in Runtime Flow/Entry Point |

## 7. External Dependencies
NOT FOUND IN SOURCE for API/network calls. Local Python imports and filesystem dependencies are listed in Inputs/Flow.

## 8. Orchestration Relationships
Calls BacktestRunner and backtest_bitnet.run_backtest.

## 9. State Classification
RESEARCH_ONLY - registered command runs offline data, tuning, training, replay, analysis, or maintenance behavior and no live production side effect is proven in this command section.

## 10. Hidden Risks / Important Findings
- NOT FOUND IN SOURCE

# COMMAND: backtest.v2

## 1. Human Purpose
Run CRT backtest harness with execution-truth outputs. Source: src/control_plane/registry.py::core_command_specs() line 384.

## 2. Entry Point
File: src/runtime/backtest_v2.py
Callable: src/runtime/backtest_v2.py::main(), BacktestRunner, ReportWriter
Registry Reference: src/control_plane/registry.py::core_command_specs() line 384; mode python-file.

## 3. CLI Parameters
Registry-declared parameters:
| Parameter | Type/Kind | Default | Required | Source |
|---|---|---|---|---|
| --csv | file | None | yes | src/control_plane/registry.py::core_command_specs() line 384 |
| --instrument | choice | 'EURUSD' | no | src/control_plane/registry.py::core_command_specs() line 384; choices=EURUSD,GBPUSD,AUDUSD,USDJPY,USDCAD,USDCHF,NZDUSD,EURGBP |
| --output | str | 'results' | no | src/control_plane/registry.py::core_command_specs() line 384 |
| --htf | int | None | no | src/control_plane/registry.py::core_command_specs() line 384 |
| --warmup | int | None | no | src/control_plane/registry.py::core_command_specs() line 384 |
| --capital | float | None | no | src/control_plane/registry.py::core_command_specs() line 384 |
| --risk-pct | float | None | no | src/control_plane/registry.py::core_command_specs() line 384 |
| --spread | float | None | no | src/control_plane/registry.py::core_command_specs() line 384 |
| --no-slip | bool | False | no | src/control_plane/registry.py::core_command_specs() line 384 |
| --no-gap-reset | bool | False | no | src/control_plane/registry.py::core_command_specs() line 384 |
| --sweep-age | int | 20 | no | src/control_plane/registry.py::core_command_specs() line 384 |
| --decay | float | 0.1 | no | src/control_plane/registry.py::core_command_specs() line 384 |
| --threshold | float | 0.75 | no | src/control_plane/registry.py::core_command_specs() line 384 |

Actual argparse parameters found in entry file:
| Parameter | Type | Default | Required | Source |
|---|---|---|---|---|
| --csv | str | none | True | src/runtime/backtest_v2.py argparse line 1944 |
| --instrument | str | AUTO | false | src/runtime/backtest_v2.py argparse line 1945 |
| --output | str | results | false | src/runtime/backtest_v2.py argparse line 1946 |
| --htf | int | none | false | src/runtime/backtest_v2.py argparse line 1948 |
| --warmup | int | none | false | src/runtime/backtest_v2.py argparse line 1949 |
| --capital | float | none | false | src/runtime/backtest_v2.py argparse line 1950 |
| --risk-pct | float | none | false | src/runtime/backtest_v2.py argparse line 1951 |
| --spread | float | none | false | src/runtime/backtest_v2.py argparse line 1952 |
| --no-slip | bool | False | false | src/runtime/backtest_v2.py argparse line 1953; action=store_true |
| --no-gap-reset | bool | False | false | src/runtime/backtest_v2.py argparse line 1954; action=store_true |
| --sweep-age | int | none | false | src/runtime/backtest_v2.py argparse line 1955 |
| --decay | float | none | false | src/runtime/backtest_v2.py argparse line 1956 |
| --threshold | float | none | false | src/runtime/backtest_v2.py argparse line 1957 |
| --config | str | none | false | src/runtime/backtest_v2.py argparse line 1958 |
| --scorer | str | calibrated | false | src/runtime/backtest_v2.py argparse line 1959; choices=[static, calibrated] |

## 4. Runtime Flow
1. main() loads production config via load_prod_config_from_registry(); it calls MultiInstrumentRunner.run_all() for directory/ALL mode or CandleLoader plus BacktestRunner.run() for single CSV; ReportWriter emits summary/trades/events/report.

## 5. Inputs
- CLI parameters listed above from registry/argparse source.
- Production config registry via load_prod_config_from_registry(); OHLCV CSV or directory.

## 6. Outputs
| Output | Path | Produced By |
|---|---|---|
| summary.json, trades.csv, events.jsonl, and report.txt under {output}/{run_id}_{instrument}. | see output text | source functions listed in Runtime Flow/Entry Point |

## 7. External Dependencies
NOT FOUND IN SOURCE for API/network calls. Local Python imports and filesystem dependencies are listed in Inputs/Flow.

## 8. Orchestration Relationships
Downstream of validators, tuners, portfolio validation, SL/TP comparator, unified replay, and control-plane jobs.

## 9. State Classification
RESEARCH_ONLY - registered command runs offline data, tuning, training, replay, analysis, or maintenance behavior and no live production side effect is proven in this command section.

## 10. Hidden Risks / Important Findings
- Actual argparse includes --config and --scorer; registry omits both.
- Source help says --config is not used by CRT backtest.
- Comment marks injected scorer compatibility as deprecated.

# COMMAND: backtest.bitnet

## 1. Human Purpose
Run row-level backtest with BitNet gate modes. Source: src/control_plane/registry.py::core_command_specs() line 410.

## 2. Entry Point
File: src/runtime/backtest_bitnet.py
Callable: src/runtime/backtest_bitnet.py::run_backtest(); CLI block
Registry Reference: src/control_plane/registry.py::core_command_specs() line 410; mode python-file.

## 3. CLI Parameters
Registry-declared parameters:
| Parameter | Type/Kind | Default | Required | Source |
|---|---|---|---|---|
| --config | file | 'configs/production/v2_multi_2026_04.json' | no | src/control_plane/registry.py::core_command_specs() line 410 |
| --data | file | None | no | src/control_plane/registry.py::core_command_specs() line 410 |
| --gate-mode | choice | 'hard_gate' | no | src/control_plane/registry.py::core_command_specs() line 410; choices=hard_gate,score_only_audit,force_accept_baseline |
| --months | int | None | no | src/control_plane/registry.py::core_command_specs() line 410 |
| --output | str | None | no | src/control_plane/registry.py::core_command_specs() line 410 |

Actual argparse parameters found in entry file:
| Parameter | Type | Default | Required | Source |
|---|---|---|---|---|
| --config | str | configs/production/v1_multi_2026_03.json | false | src/runtime/backtest_bitnet.py argparse line 452 |
| --data | str | data.csv | false | src/runtime/backtest_bitnet.py argparse line 453 |
| --gate-mode | str | hard_gate | false | src/runtime/backtest_bitnet.py argparse line 454; choices=[hard_gate, score_only_audit, force_accept_baseline] |
| --months | int | none | false | src/runtime/backtest_bitnet.py argparse line 459 |
| --output | str | none | false | src/runtime/backtest_bitnet.py argparse line 460 |

## 4. Runtime Flow
1. CLI calls run_backtest(); run_backtest() reads config/data, builds canonical features with FeaturePipeline, loads BitNetRunner from config engine_runner.model_path, iterates rows, and logs decisions.

## 5. Inputs
- CLI parameters listed above from registry/argparse source.
- Config JSON, data CSV, gate mode, and BitNet model path from config engine_runner.model_path.

## 6. Outputs
| Output | Path | Produced By |
|---|---|---|
| logs/backtest_decisions_{symbol}_{timestamp}.jsonl and optional --output CSV or printed JSON. | see output text | source functions listed in Runtime Flow/Entry Point |

## 7. External Dependencies
Local BitNetRunner/model path dependency from config engine_runner.model_path.

## 8. Orchestration Relationships
Called by replay.unified.

## 9. State Classification
RESEARCH_ONLY - registered command runs offline data, tuning, training, replay, analysis, or maintenance behavior and no live production side effect is proven in this command section.

## 10. Hidden Risks / Important Findings
- NOT FOUND IN SOURCE

# COMMAND: baseline.capture

## 1. Human Purpose
Capture a baseline manifest for current repo/model/config state. Source: src/control_plane/registry.py::core_command_specs() line 429.

## 2. Entry Point
File: src/runtime/baseline_capture.py
Callable: src/runtime/baseline_capture.py::main(), build_manifest()
Registry Reference: src/control_plane/registry.py::core_command_specs() line 429; mode python-file.

## 3. CLI Parameters
Registry-declared parameters:
| Parameter | Type/Kind | Default | Required | Source |
|---|---|---|---|---|
| --label | str | 'phase0' | no | src/control_plane/registry.py::core_command_specs() line 429 |
| --output-dir | str | 'results/baseline' | no | src/control_plane/registry.py::core_command_specs() line 429 |

Actual argparse parameters found in entry file:
| Parameter | Type | Default | Required | Source |
|---|---|---|---|---|
| --label | str | phase0 | false | src/runtime/baseline_capture.py argparse line 113 |
| --output-dir | str | results/baseline | false | src/runtime/baseline_capture.py argparse line 114 |

## 4. Runtime Flow
1. main() creates a timestamped baseline directory, calls build_manifest(), and writes manifest.json; build_manifest() reads feature schema, model registry, and production config metadata.

## 5. Inputs
- CLI parameters listed above from registry/argparse source.

## 6. Outputs
| Output | Path | Produced By |
|---|---|---|
| results/baseline/{timestamp}_{label}/manifest.json. | see output text | source functions listed in Runtime Flow/Entry Point |

## 7. External Dependencies
NOT FOUND IN SOURCE for API/network calls. Local Python imports and filesystem dependencies are listed in Inputs/Flow.

## 8. Orchestration Relationships
Called by src/control_plane/jobs.py::JobManager._execute_run() as a registered subprocess. Additional downstream calls are in Runtime Flow.

## 9. State Classification
RESEARCH_ONLY - registered command runs offline data, tuning, training, replay, analysis, or maintenance behavior and no live production side effect is proven in this command section.

## 10. Hidden Risks / Important Findings
- NOT FOUND IN SOURCE

# COMMAND: live.inout_runner

## 1. Human Purpose
Run INOUT strategy loop in controlled dry/live mode. Source: src/control_plane/registry.py::core_command_specs() line 442.

## 2. Entry Point
File: inout.runner
Callable: NOT FOUND IN SOURCE for active module; registry target inout.runner
Registry Reference: src/control_plane/registry.py::core_command_specs() line 442; mode module.

## 3. CLI Parameters
Registry-declared parameters:
| Parameter | Type/Kind | Default | Required | Source |
|---|---|---|---|---|
| --cycles | int | 0 | no | src/control_plane/registry.py::core_command_specs() line 442 |
| --config | file | None | no | src/control_plane/registry.py::core_command_specs() line 442 |

Actual argparse parameters found in entry file:
| Parameter | Type | Default | Required | Source |
|---|---|---|---|---|
| NOT FOUND IN SOURCE | NOT FOUND IN SOURCE | NOT FOUND IN SOURCE | NOT FOUND IN SOURCE | active argparse not found or module target missing |

## 4. Runtime Flow
1. Registry declares module inout.runner and build_command_line() would run python -m inout.runner; active module source was not found by importlib resolution, while an archived legacy runner exists under archive/inout_legacy.

## 5. Inputs
- CLI parameters listed above from registry/argparse source.

## 6. Outputs
| Output | Path | Produced By |
|---|---|---|
| NOT FOUND IN SOURCE for active command outputs. | see output text | source functions listed in Runtime Flow/Entry Point |

## 7. External Dependencies
NOT FOUND IN SOURCE for API/network calls. Local Python imports and filesystem dependencies are listed in Inputs/Flow.

## 8. Orchestration Relationships
Called by src/control_plane/jobs.py::JobManager._execute_run() as a registered subprocess. Additional downstream calls are in Runtime Flow.

## 9. State Classification
PARTIALLY_CONNECTED - registered module target inout.runner is missing from active source.

## 10. Hidden Risks / Important Findings
- importlib.util.find_spec("inout.runner") and src.inout.runner returned NOT FOUND in this workspace.
- Archived legacy runner exists under archive/inout_legacy/ARCHIVED_2026_05_02, not active registry path.

# COMMAND: training.opportunity_scanner

## 1. Human Purpose
Generate unbiased opportunity logs for Gaussian/Zone model training (Pipeline B). Source: src/control_plane/registry.py::core_command_specs() line 458.

## 2. Entry Point
File: scripts/research/opportunity_scanner.py
Callable: scripts/research/opportunity_scanner.py::main(), scan()
Registry Reference: src/control_plane/registry.py::core_command_specs() line 458; mode python-file.

## 3. CLI Parameters
Registry-declared parameters:
| Parameter | Type/Kind | Default | Required | Source |
|---|---|---|---|---|
| --csv | file | None | yes | src/control_plane/registry.py::core_command_specs() line 458 |
| --instrument | choice | None | yes | src/control_plane/registry.py::core_command_specs() line 458; choices=EURUSD,GBPUSD,AUDUSD,USDJPY,USDCAD,USDCHF,NZDUSD,EURGBP |
| --tp-atr-mult | float | 2.0 | no | src/control_plane/registry.py::core_command_specs() line 458 |
| --sl-atr-mult | float | 1.0 | no | src/control_plane/registry.py::core_command_specs() line 458 |
| --max-forward-candles | int | 40 | no | src/control_plane/registry.py::core_command_specs() line 458 |
| --warmup-candles | int | 30 | no | src/control_plane/registry.py::core_command_specs() line 458 |
| --output-dir | str | 'logs' | no | src/control_plane/registry.py::core_command_specs() line 458 |

Actual argparse parameters found in entry file:
| Parameter | Type | Default | Required | Source |
|---|---|---|---|---|
| --csv | Path | none | True | scripts/research/opportunity_scanner.py argparse line 243 |
| --instrument | str | none | True | scripts/research/opportunity_scanner.py argparse line 245 |
| --tp-atr-mult | float | 2.0 | false | scripts/research/opportunity_scanner.py argparse line 247 |
| --sl-atr-mult | float | 1.0 | false | scripts/research/opportunity_scanner.py argparse line 248 |
| --max-forward-candles | int | 40 | false | scripts/research/opportunity_scanner.py argparse line 249 |
| --warmup-candles | int | 30 | false | scripts/research/opportunity_scanner.py argparse line 250 |
| --output-dir | Path | Path(...) | false | scripts/research/opportunity_scanner.py argparse line 251 |
| --trail-mult | float | 0.5 | false | scripts/research/opportunity_scanner.py argparse line 252 |
| --run-id | str | none | false | scripts/research/opportunity_scanner.py argparse line 255 |

## 4. Runtime Flow
1. main() parses candle and RR arguments and calls scan(); scan() loads CSV with _load_csv(), runs FeaturePipeline over candles, evaluates forward outcomes, and writes opportunities.jsonl.

## 5. Inputs
- CLI parameters listed above from registry/argparse source.

## 6. Outputs
| Output | Path | Produced By |
|---|---|---|
| {output_dir}/{instrument}/{run_id}/opportunities.jsonl plus stdout OUTPUT markers. | see output text | source functions listed in Runtime Flow/Entry Point |

## 7. External Dependencies
NOT FOUND IN SOURCE for API/network calls. Local Python imports and filesystem dependencies are listed in Inputs/Flow.

## 8. Orchestration Relationships
Called by src/control_plane/jobs.py::JobManager._execute_run() as a registered subprocess. Additional downstream calls are in Runtime Flow.

## 9. State Classification
RESEARCH_ONLY - registered command runs offline data, tuning, training, replay, analysis, or maintenance behavior and no live production side effect is proven in this command section.

## 10. Hidden Risks / Important Findings
- Actual argparse includes --trail-mult and --run-id; registry omits both.

# COMMAND: training.phase5_calibration

## 1. Human Purpose
Train and calibrate the Gaussian model from unbiased opportunity logs. Replaces hardcoded _P5_PARAMS. Source: src/control_plane/registry.py::core_command_specs() line 478.

## 2. Entry Point
File: scripts/training/phase5_calibration.py
Callable: scripts/training/phase5_calibration.py::main()
Registry Reference: src/control_plane/registry.py::core_command_specs() line 478; mode python-file.

## 3. CLI Parameters
Registry-declared parameters:
| Parameter | Type/Kind | Default | Required | Source |
|---|---|---|---|---|
| --opportunities | file | None | yes | src/control_plane/registry.py::core_command_specs() line 478 |
| --version | str | None | yes | src/control_plane/registry.py::core_command_specs() line 478 |
| --train | bool | True | no | src/control_plane/registry.py::core_command_specs() line 478 |
| --force | bool | False | no | src/control_plane/registry.py::core_command_specs() line 478 |
| --promote | bool | False | no | src/control_plane/registry.py::core_command_specs() line 478 |
| --train-ratio | float | 0.7 | no | src/control_plane/registry.py::core_command_specs() line 478 |
| --feature-subset | str | '' | no | src/control_plane/registry.py::core_command_specs() line 478 |
| --class-weights | str | '' | no | src/control_plane/registry.py::core_command_specs() line 478 |
| --rr-buckets | str | '' | no | src/control_plane/registry.py::core_command_specs() line 478 |

Actual argparse parameters found in entry file:
| Parameter | Type | Default | Required | Source |
|---|---|---|---|---|
| --csv | str | none | false | scripts/training/phase5_calibration.py argparse line 1272; nargs=?; const=. |
| --cached | str | none | false | scripts/training/phase5_calibration.py argparse line 1275 |
| --synthetic | bool | none | false | scripts/training/phase5_calibration.py argparse line 1276; action=store_true |
| --opportunities | str | none | false | scripts/training/phase5_calibration.py argparse line 1278 |
| --n-synthetic | int | 500 | false | scripts/training/phase5_calibration.py argparse line 1282 |
| --synthetic-seed | int | 42 | false | scripts/training/phase5_calibration.py argparse line 1284 |
| --audit-only | bool | none | false | scripts/training/phase5_calibration.py argparse line 1286; action=store_true |
| --train | bool | none | false | scripts/training/phase5_calibration.py argparse line 1287; action=store_true |
| --gaussian | bool | none | false | scripts/training/phase5_calibration.py argparse line 1288; action=store_true |
| --tradenet | bool | none | false | scripts/training/phase5_calibration.py argparse line 1291; action=store_true |
| --integrate | bool | none | false | scripts/training/phase5_calibration.py argparse line 1296; action=store_true |
| --promote | bool | none | false | scripts/training/phase5_calibration.py argparse line 1300; action=store_true |
| --export | bool | none | false | scripts/training/phase5_calibration.py argparse line 1301; action=store_true |
| --loo | bool | none | false | scripts/training/phase5_calibration.py argparse line 1302; action=store_true |
| --force | bool | none | false | scripts/training/phase5_calibration.py argparse line 1303; action=store_true |
| --base | str | . | false | scripts/training/phase5_calibration.py argparse line 1304 |
| --train-ratio | float | 0.7 | false | scripts/training/phase5_calibration.py argparse line 1305 |
| --version | str |  | false | scripts/training/phase5_calibration.py argparse line 1306 |
| --results-dirs | str | DEFAULT_RESULTS_DIRS | false | scripts/training/phase5_calibration.py argparse line 1307; nargs=+ |
| --feature-subset | str |  | false | scripts/training/phase5_calibration.py argparse line 1308 |
| --class-weights | str |  | false | scripts/training/phase5_calibration.py argparse line 1311 |
| --rr-buckets | str |  | false | scripts/training/phase5_calibration.py argparse line 1314 |
| --mirror-short-features | bool | True | false | scripts/training/phase5_calibration.py argparse line 1317; action=store_true |
| --no-mirror-short-features | bool | none | false | scripts/training/phase5_calibration.py argparse line 1321; action=store_false; dest=mirror_short_features |
| --instrument | str |  | false | scripts/training/phase5_calibration.py argparse line 1324 |
| --run-id, --run | str | none | false | scripts/training/phase5_calibration.py argparse line 1329; dest=run_id |

## 4. Runtime Flow
1. main() resolves dataset source from opportunities/cached/synthetic/backtest results, can audit only, trains Gaussian via run_calibration()/save_gaussian_model()/register_gaussian()/promote_gaussian(), or trains TradeNet via run_tradenet_training().

## 5. Inputs
- CLI parameters listed above from registry/argparse source.

## 6. Outputs
| Output | Path | Produced By |
|---|---|---|
| p5_calibration_{version}.json reports, model artifacts under models, and optional model registry updates. | see output text | source functions listed in Runtime Flow/Entry Point |

## 7. External Dependencies
NOT FOUND IN SOURCE for API/network calls. Local Python imports and filesystem dependencies are listed in Inputs/Flow.

## 8. Orchestration Relationships
Called by src/control_plane/jobs.py::JobManager._execute_run() as a registered subprocess. Additional downstream calls are in Runtime Flow.

## 9. State Classification
RESEARCH_ONLY - registered command runs offline data, tuning, training, replay, analysis, or maintenance behavior and no live production side effect is proven in this command section.

## 10. Hidden Risks / Important Findings
- Actual argparse contains many source/train flags omitted by registry, including --csv, --cached, --synthetic, --gaussian, --tradenet, --integrate, --instrument, --run-id.
- --integrate is deprecated/no-op in source.

# COMMAND: training.discover_zones

## 1. Human Purpose
Cluster opportunity logs into zone registry for the Zone Gate engine via KMeans. Each run saves a versioned file and registers in zone_gate_registry.json. Source: src/control_plane/registry.py::core_command_specs() line 498.

## 2. Entry Point
File: scripts/research/discover_zones.py
Callable: scripts/research/discover_zones.py::main(), discover()
Registry Reference: src/control_plane/registry.py::core_command_specs() line 498; mode python-file.

## 3. CLI Parameters
Registry-declared parameters:
| Parameter | Type/Kind | Default | Required | Source |
|---|---|---|---|---|
| --opportunities | file-multi | None | yes | src/control_plane/registry.py::core_command_specs() line 498 |
| --output | str | 'models/zone_registry.json' | no | src/control_plane/registry.py::core_command_specs() line 498 |
| --version | str | None | no | src/control_plane/registry.py::core_command_specs() line 498 |
| --n-clusters | int | 8 | no | src/control_plane/registry.py::core_command_specs() line 498 |
| --min-samples | int | 15 | no | src/control_plane/registry.py::core_command_specs() line 498 |
| --feature-weights | str | '' | no | src/control_plane/registry.py::core_command_specs() line 498 |

Actual argparse parameters found in entry file:
| Parameter | Type | Default | Required | Source |
|---|---|---|---|---|
| --opportunities | str | none | False | scripts/research/discover_zones.py argparse line 183; nargs=+ |
| --output | Path | none | False | scripts/research/discover_zones.py argparse line 188 |
| --n-clusters | int | 8 | false | scripts/research/discover_zones.py argparse line 193 |
| --min-samples | int | 15 | false | scripts/research/discover_zones.py argparse line 194 |
| --feature-weights | str |  | false | scripts/research/discover_zones.py argparse line 195 |
| --version | str | none | false | scripts/research/discover_zones.py argparse line 198 |
| --subsample | int | 1 | false | scripts/research/discover_zones.py argparse line 201 |
| --no-promote | bool | True | false | scripts/research/discover_zones.py argparse line 204; action=store_false; dest=promote |
| --instrument | str |  | false | scripts/research/discover_zones.py argparse line 206 |
| --run-id, --run | str | none | false | scripts/research/discover_zones.py argparse line 210; dest=run_id |

## 4. Runtime Flow
1. main() resolves opportunity paths/output defaults, calls discover() to cluster records, writes versioned/canonical zone registry JSON, and calls register_zone_gate()/promote_zone_gate() unless disabled.

## 5. Inputs
- CLI parameters listed above from registry/argparse source.

## 6. Outputs
| Output | Path | Produced By |
|---|---|---|
| zone_registry JSON files under models or supplied --output; optional zone gate registry promotion. | see output text | source functions listed in Runtime Flow/Entry Point |

## 7. External Dependencies
NOT FOUND IN SOURCE for API/network calls. Local Python imports and filesystem dependencies are listed in Inputs/Flow.

## 8. Orchestration Relationships
Called by src/control_plane/jobs.py::JobManager._execute_run() as a registered subprocess. Additional downstream calls are in Runtime Flow.

## 9. State Classification
RESEARCH_ONLY - registered command runs offline data, tuning, training, replay, analysis, or maintenance behavior and no live production side effect is proven in this command section.

## 10. Hidden Risks / Important Findings
- Actual argparse includes --subsample, --no-promote, --instrument, --run-id; registry omits them.

# COMMAND: training.build_rr_dataset

## 1. Human Purpose
Build RR training dataset from opportunity scanner JSONL (unbiased) or legacy trades CSVs. Each run saves a versioned dataset file and registers in rr_registry.json. Source: src/control_plane/registry.py::core_command_specs() line 515.

## 2. Entry Point
File: scripts/data/build_rr_dataset.py
Callable: scripts/data/build_rr_dataset.py::main(), _build_from_opportunities(), _register_dataset()
Registry Reference: src/control_plane/registry.py::core_command_specs() line 515; mode python-file.

## 3. CLI Parameters
Registry-declared parameters:
| Parameter | Type/Kind | Default | Required | Source |
|---|---|---|---|---|
| --opportunities | file-multi | None | no | src/control_plane/registry.py::core_command_specs() line 515 |
| --csv | file | None | no | src/control_plane/registry.py::core_command_specs() line 515 |
| --dir | str | None | no | src/control_plane/registry.py::core_command_specs() line 515 |
| --output | str | 'models/rr_dataset.json' | no | src/control_plane/registry.py::core_command_specs() line 515 |
| --version | str | None | no | src/control_plane/registry.py::core_command_specs() line 515 |

Actual argparse parameters found in entry file:
| Parameter | Type | Default | Required | Source |
|---|---|---|---|---|
| --opportunities | str | none | false | scripts/data/build_rr_dataset.py argparse line 203; nargs=+ |
| --csv | str | none | false | scripts/data/build_rr_dataset.py argparse line 209 |
| --dir | str | none | false | scripts/data/build_rr_dataset.py argparse line 210 |
| --glob | str | none | false | scripts/data/build_rr_dataset.py argparse line 211 |
| --output | str | none | false | scripts/data/build_rr_dataset.py argparse line 213 |
| --version | str | none | false | scripts/data/build_rr_dataset.py argparse line 220 |
| --no-register | bool | True | false | scripts/data/build_rr_dataset.py argparse line 224; action=store_false; dest=register |
| --instrument | str |  | false | scripts/data/build_rr_dataset.py argparse line 228 |
| --run-id, --run | str | none | false | scripts/data/build_rr_dataset.py argparse line 233; dest=run_id |

## 4. Runtime Flow
1. main() prefers _build_from_opportunities() and falls back to legacy CSV collection; it saves dataset JSON and _register_dataset() updates RR dataset registry unless disabled.

## 5. Inputs
- CLI parameters listed above from registry/argparse source.

## 6. Outputs
| Output | Path | Produced By |
|---|---|---|
| rr_dataset JSON, versioned dataset copies, and RR registry updates. | see output text | source functions listed in Runtime Flow/Entry Point |

## 7. External Dependencies
NOT FOUND IN SOURCE for API/network calls. Local Python imports and filesystem dependencies are listed in Inputs/Flow.

## 8. Orchestration Relationships
Called by src/control_plane/jobs.py::JobManager._execute_run() as a registered subprocess. Additional downstream calls are in Runtime Flow.

## 9. State Classification
RESEARCH_ONLY - registered command runs offline data, tuning, training, replay, analysis, or maintenance behavior and no live production side effect is proven in this command section.

## 10. Hidden Risks / Important Findings
- Actual argparse includes --glob, --no-register, --instrument, --run-id; registry omits them.

# COMMAND: training.train_rr_model

## 1. Human Purpose
Train the RR Pattern Miner from a versioned RR dataset. Saves a uniquely-versioned model file and registers in rr_registry.json. Source: src/control_plane/registry.py::core_command_specs() line 540.

## 2. Entry Point
File: scripts/training/train_rr_model.py
Callable: scripts/training/train_rr_model.py::main(), RRPatternTrainer.train()
Registry Reference: src/control_plane/registry.py::core_command_specs() line 540; mode python-file.

## 3. CLI Parameters
Registry-declared parameters:
| Parameter | Type/Kind | Default | Required | Source |
|---|---|---|---|---|
| --dataset | file | None | no | src/control_plane/registry.py::core_command_specs() line 540 |
| --version | str | None | no | src/control_plane/registry.py::core_command_specs() line 540 |
| --output | str | None | no | src/control_plane/registry.py::core_command_specs() line 540 |
| --promote | bool | False | no | src/control_plane/registry.py::core_command_specs() line 540 |

Actual argparse parameters found in entry file:
| Parameter | Type | Default | Required | Source |
|---|---|---|---|---|
| --dataset | str | none | false | scripts/training/train_rr_model.py argparse line 60 |
| --version | str | none | false | scripts/training/train_rr_model.py argparse line 64 |
| --output | str | none | false | scripts/training/train_rr_model.py argparse line 68 |
| --promote | bool | False | false | scripts/training/train_rr_model.py argparse line 72; action=store_true |
| --zero-price-features | bool | False | false | scripts/training/train_rr_model.py argparse line 76; action=store_true |
| --instrument | str |  | false | scripts/training/train_rr_model.py argparse line 85 |
| --run-id, --run | str | none | false | scripts/training/train_rr_model.py argparse line 90; dest=run_id |

## 4. Runtime Flow
1. main() resolves dataset from CLI/run-scoped/active registry/canonical path, loads it, trains RRPatternTrainer, writes rr_model JSON, registers it, and optionally promotes/copies canonical model.

## 5. Inputs
- CLI parameters listed above from registry/argparse source.

## 6. Outputs
| Output | Path | Produced By |
|---|---|---|
| rr_model_{version}.json, RR registry updates, and canonical models/rr_model.json when promoted. | see output text | source functions listed in Runtime Flow/Entry Point |

## 7. External Dependencies
NOT FOUND IN SOURCE for API/network calls. Local Python imports and filesystem dependencies are listed in Inputs/Flow.

## 8. Orchestration Relationships
Called by src/control_plane/jobs.py::JobManager._execute_run() as a registered subprocess. Additional downstream calls are in Runtime Flow.

## 9. State Classification
RESEARCH_ONLY - registered command runs offline data, tuning, training, replay, analysis, or maintenance behavior and no live production side effect is proven in this command section.

## 10. Hidden Risks / Important Findings
- Actual argparse includes --zero-price-features, --instrument, --run-id; registry omits them.

# COMMAND: training.train_pipeline

## 1. Human Purpose
Run TradeNet binary classifier training or Gaussian registry update from fusion logs. Source: src/control_plane/registry.py::core_command_specs() line 562.

## 2. Entry Point
File: scripts/training/train_pipeline.py
Callable: scripts/training/train_pipeline.py::_cli(), _real_tradenet_fn()
Registry Reference: src/control_plane/registry.py::core_command_specs() line 562; mode python-file.

## 3. CLI Parameters
Registry-declared parameters:
| Parameter | Type/Kind | Default | Required | Source |
|---|---|---|---|---|
| positional subcommand | choice | 'gaussian' | no | src/control_plane/registry.py::core_command_specs() line 562; choices=tradenet,gaussian |
| --data | file | None | no | src/control_plane/registry.py::core_command_specs() line 562; applies_to=tradenet |
| --output | str | 'results/training_result.json' | no | src/control_plane/registry.py::core_command_specs() line 562; applies_to=tradenet |
| --logs | file-multi | [] | no | src/control_plane/registry.py::core_command_specs() line 562; applies_to=gaussian |
| --version | str | None | no | src/control_plane/registry.py::core_command_specs() line 562; applies_to=gaussian |
| --no-promote | bool | False | no | src/control_plane/registry.py::core_command_specs() line 562; applies_to=gaussian |
| --force-promote | bool | False | no | src/control_plane/registry.py::core_command_specs() line 562; applies_to=gaussian |

Actual argparse parameters found in entry file:
| Parameter | Type | Default | Required | Source |
|---|---|---|---|---|
| --data | str | none | True | scripts/training/train_pipeline.py argparse line 52 |
| --output | str | none | false | scripts/training/train_pipeline.py argparse line 53 |
| --logs | str | none | True | scripts/training/train_pipeline.py argparse line 57; nargs=+ |
| --version | str | none | True | scripts/training/train_pipeline.py argparse line 61 |
| --no-promote | bool | none | false | scripts/training/train_pipeline.py argparse line 62; action=store_true |
| --force-promote | bool | none | false | scripts/training/train_pipeline.py argparse line 66; action=store_true |

## 4. Runtime Flow
1. _cli() uses subparsers; tradenet calls run_training_pipeline() with _real_tradenet_fn(); gaussian calls run_gaussian_update() with logs/version/promotion flags.

## 5. Inputs
- CLI parameters listed above from registry/argparse source.

## 6. Outputs
| Output | Path | Produced By |
|---|---|---|
| TradeNet model via save_model() or Gaussian registry/model outputs from run_gaussian_update(). | see output text | source functions listed in Runtime Flow/Entry Point |

## 7. External Dependencies
NOT FOUND IN SOURCE for API/network calls. Local Python imports and filesystem dependencies are listed in Inputs/Flow.

## 8. Orchestration Relationships
Called by src/control_plane/jobs.py::JobManager._execute_run() as a registered subprocess. Additional downstream calls are in Runtime Flow.

## 9. State Classification
RESEARCH_ONLY - registered command runs offline data, tuning, training, replay, analysis, or maintenance behavior and no live production side effect is proven in this command section.

## 10. Hidden Risks / Important Findings
- NOT FOUND IN SOURCE

# COMMAND: training.auto_train

## 1. Human Purpose
Full Pipeline-B nightly loop: scan opportunities → compress → Gaussian training → optional promotion. Source: src/control_plane/registry.py::core_command_specs() line 587.

## 2. Entry Point
File: scripts/auto_train_from_opportunities.py
Callable: scripts/auto_train_from_opportunities.py::main(), _run()
Registry Reference: src/control_plane/registry.py::core_command_specs() line 587; mode python-file.

## 3. CLI Parameters
Registry-declared parameters:
| Parameter | Type/Kind | Default | Required | Source |
|---|---|---|---|---|
| --data-dir | str | 'data' | no | src/control_plane/registry.py::core_command_specs() line 587 |
| --instruments | list | [] | no | src/control_plane/registry.py::core_command_specs() line 587 |
| --model-version | str | None | no | src/control_plane/registry.py::core_command_specs() line 587 |
| --max-forward-candles | int | 40 | no | src/control_plane/registry.py::core_command_specs() line 587 |
| --no-promote | bool | False | no | src/control_plane/registry.py::core_command_specs() line 587 |
| --promote-if-approved | bool | False | no | src/control_plane/registry.py::core_command_specs() line 587 |

Actual argparse parameters found in entry file:
| Parameter | Type | Default | Required | Source |
|---|---|---|---|---|
| --data-dir | Path | Path(...) | false | scripts/auto_train_from_opportunities.py argparse line 131 |
| --instruments | str | [EURUSD, GBPUSD, AUDUSD, USDJPY, EURCAD, XAUUSD, BTCUSDT, ETHUSDT] | false | scripts/auto_train_from_opportunities.py argparse line 132; nargs=+ |
| --output-logs | Path | Path(...) | false | scripts/auto_train_from_opportunities.py argparse line 135 |
| --results-dir | Path | Path(...) | false | scripts/auto_train_from_opportunities.py argparse line 136 |
| --model-version | str | none | false | scripts/auto_train_from_opportunities.py argparse line 139 |
| --max-forward-candles | int | 40 | false | scripts/auto_train_from_opportunities.py argparse line 141 |
| --warmup-candles | int | 30 | false | scripts/auto_train_from_opportunities.py argparse line 142 |
| --trail-mult | float | 0.5 | false | scripts/auto_train_from_opportunities.py argparse line 143 |
| --per-instrument | str | True | false | scripts/auto_train_from_opportunities.py argparse line 146; action=argparse.BooleanOptionalAction |
| --promote-if-approved | bool | none | false | scripts/auto_train_from_opportunities.py argparse line 151; action=store_true |
| --no-promote | bool | none | false | scripts/auto_train_from_opportunities.py argparse line 153; action=store_true |
| --phase5-extra | str | [] | false | scripts/auto_train_from_opportunities.py argparse line 155; nargs=* |
| --run-id | str | none | false | scripts/auto_train_from_opportunities.py argparse line 158 |

## 4. Runtime Flow
1. main() orchestrates subprocess calls through _run(): opportunity_scanner.py, compress_logs_for_llm.py, and phase5_calibration.py; it can call promote_gaussian after approved training.

## 5. Inputs
- CLI parameters listed above from registry/argparse source.

## 6. Outputs
| Output | Path | Produced By |
|---|---|---|
| Child command opportunities, compressed summaries, phase5 reports/models, and optional Gaussian registry promotion. | see output text | source functions listed in Runtime Flow/Entry Point |

## 7. External Dependencies
NOT FOUND IN SOURCE for API/network calls. Local Python imports and filesystem dependencies are listed in Inputs/Flow.

## 8. Orchestration Relationships
Calls opportunity_scanner, compress_logs, phase5_calibration, and promote_gaussian via subprocess/function calls.

## 9. State Classification
PARTIALLY_CONNECTED - subprocess orchestration exists, but source docstring says optional LLM hypertuning is stubbed/manual.

## 10. Hidden Risks / Important Findings
- Actual argparse includes output/results/warmup/trail/per-instrument/phase5-extra/run-id options omitted by registry.
- Docstring says optional LLM hypertuning is currently stubbed and wired only manually through groq_bridge.

# COMMAND: analysis.compress_logs

## 1. Human Purpose
Stream opportunity JSONL logs into a token-efficient JSON summary for LLM governance. Source: src/control_plane/registry.py::core_command_specs() line 606.

## 2. Entry Point
File: scripts/analysis/compress_logs_for_llm.py
Callable: scripts/analysis/compress_logs_for_llm.py::main(), compress()
Registry Reference: src/control_plane/registry.py::core_command_specs() line 606; mode python-file.

## 3. CLI Parameters
Registry-declared parameters:
| Parameter | Type/Kind | Default | Required | Source |
|---|---|---|---|---|
| --logs | file-multi | None | yes | src/control_plane/registry.py::core_command_specs() line 606 |
| --output | str | 'logs/compressed_summary.json' | yes | src/control_plane/registry.py::core_command_specs() line 606 |
| --top-n-features | int | 8 | no | src/control_plane/registry.py::core_command_specs() line 606 |

Actual argparse parameters found in entry file:
| Parameter | Type | Default | Required | Source |
|---|---|---|---|---|
| --logs | str | none | True | scripts/analysis/compress_logs_for_llm.py argparse line 229; nargs=+ |
| --output | Path | none | false | scripts/analysis/compress_logs_for_llm.py argparse line 231 |
| --instrument | str |  | false | scripts/analysis/compress_logs_for_llm.py argparse line 233 |
| --run-id | str | none | false | scripts/analysis/compress_logs_for_llm.py argparse line 237 |
| --top-n-features | int | 8 | false | scripts/analysis/compress_logs_for_llm.py argparse line 240 |

## 4. Runtime Flow
1. main() parses log paths and calls compress(); compress() expands JSONL globs, aggregates outcomes/features/anomalies, and main() writes compressed JSON.

## 5. Inputs
- CLI parameters listed above from registry/argparse source.

## 6. Outputs
| Output | Path | Produced By |
|---|---|---|
| Compressed summary JSON at --output or logs/{instrument}/{run_id}/compressed.json. | see output text | source functions listed in Runtime Flow/Entry Point |

## 7. External Dependencies
NOT FOUND IN SOURCE for API/network calls. Local Python imports and filesystem dependencies are listed in Inputs/Flow.

## 8. Orchestration Relationships
Called by src/control_plane/jobs.py::JobManager._execute_run() as a registered subprocess. Additional downstream calls are in Runtime Flow.

## 9. State Classification
RESEARCH_ONLY - registered command runs offline data, tuning, training, replay, analysis, or maintenance behavior and no live production side effect is proven in this command section.

## 10. Hidden Risks / Important Findings
- Actual argparse includes --instrument and --run-id; registry omits them.

# COMMAND: maintenance.update_config_hash

## 1. Human Purpose
Recompute and write the SHA-256 hash for a production config JSON. Run after any manual config edit. Source: src/control_plane/registry.py::core_command_specs() line 621.

## 2. Entry Point
File: scripts/update_config_hash.py
Callable: scripts/update_config_hash.py::compute_hash(), update_hash(), check_hash(); CLI block
Registry Reference: src/control_plane/registry.py::core_command_specs() line 621; mode python-file.

## 3. CLI Parameters
Registry-declared parameters:
| Parameter | Type/Kind | Default | Required | Source |
|---|---|---|---|---|
| positional config_file | file | None | yes | src/control_plane/registry.py::core_command_specs() line 621 |
| --check | bool | False | no | src/control_plane/registry.py::core_command_specs() line 621 |
| --dry-run | bool | False | no | src/control_plane/registry.py::core_command_specs() line 621 |

Actual argparse parameters found in entry file:
| Parameter | Type | Default | Required | Source |
|---|---|---|---|---|
| config_file | str | none | positional | scripts/update_config_hash.py argparse line 50 |
| --check | bool | none | false | scripts/update_config_hash.py argparse line 51; action=store_true |
| --dry-run | bool | none | false | scripts/update_config_hash.py argparse line 52; action=store_true |

## 4. Runtime Flow
1. CLI calls check_hash() for --check or update_hash() otherwise; compute_hash() loads JSON params and update_hash() writes config_hash unless dry-run.

## 5. Inputs
- CLI parameters listed above from registry/argparse source.

## 6. Outputs
| Output | Path | Produced By |
|---|---|---|
| Updated config JSON config_hash unless --check/--dry-run; stdout messages. | see output text | source functions listed in Runtime Flow/Entry Point |

## 7. External Dependencies
NOT FOUND IN SOURCE for API/network calls. Local Python imports and filesystem dependencies are listed in Inputs/Flow.

## 8. Orchestration Relationships
Called by src/control_plane/jobs.py::JobManager._execute_run() as a registered subprocess. Additional downstream calls are in Runtime Flow.

## 9. State Classification
RESEARCH_ONLY - registered command runs offline data, tuning, training, replay, analysis, or maintenance behavior and no live production side effect is proven in this command section.

## 10. Hidden Risks / Important Findings
- NOT FOUND IN SOURCE

# COMMAND: maintenance.health_checker

## 1. Human Purpose
Run system health checks and expose a status endpoint. Source: src/control_plane/registry.py::core_command_specs() line 636.

## 2. Entry Point
File: src/monitoring/health_checker.py
Callable: src/monitoring/health_checker.py::main(), HealthChecker, _Handler
Registry Reference: src/control_plane/registry.py::core_command_specs() line 636; mode python-file.

## 3. CLI Parameters
Registry-declared parameters:
| Parameter | Type/Kind | Default | Required | Source |
|---|---|---|---|---|
| --port | int | 8788 | no | src/control_plane/registry.py::core_command_specs() line 636 |

Actual argparse parameters found in entry file:
| Parameter | Type | Default | Required | Source |
|---|---|---|---|---|
| --port | int | _DEFAULT_PORT | false | src/monitoring/health_checker.py argparse line 182 |

## 4. Runtime Flow
1. main() parses --port, starts HTTPServer with _Handler, and serves /health and /status; HealthChecker collects production config, kill switch, strategy, telegram, and MT5 component statuses.

## 5. Inputs
- CLI parameters listed above from registry/argparse source.

## 6. Outputs
| Output | Path | Produced By |
|---|---|---|
| HTTP JSON responses for /health and /status; flow logger output. | see output text | source functions listed in Runtime Flow/Entry Point |

## 7. External Dependencies
Local HTTP server on 0.0.0.0; component checks import Telegram/MT5 bridge modules.

## 8. Orchestration Relationships
Called by src/control_plane/jobs.py::JobManager._execute_run() as a registered subprocess. Additional downstream calls are in Runtime Flow.

## 9. State Classification
LIVE_PRODUCTION - serves live health/readiness HTTP endpoints.

## 10. Hidden Risks / Important Findings
- NOT FOUND IN SOURCE

# COMMAND: maintenance.build_zone_registry

## 1. Human Purpose
Rebuild per-instrument zone registry JSON files from *_trades.csv output. Source: src/control_plane/registry.py::core_command_specs() line 648.

## 2. Entry Point
File: scripts/misc/build_zone_registry_from_trades.py
Callable: scripts/misc/build_zone_registry_from_trades.py::main()
Registry Reference: src/control_plane/registry.py::core_command_specs() line 648; mode python-file.

## 3. CLI Parameters
Registry-declared parameters:
| Parameter | Type/Kind | Default | Required | Source |
|---|---|---|---|---|
| --csv | file | None | no | src/control_plane/registry.py::core_command_specs() line 648 |
| --dir | str | None | no | src/control_plane/registry.py::core_command_specs() line 648 |
| --glob | str | None | no | src/control_plane/registry.py::core_command_specs() line 648 |
| --output-root | str | 'models/bitnet' | no | src/control_plane/registry.py::core_command_specs() line 648 |
| --global-registry | bool | False | no | src/control_plane/registry.py::core_command_specs() line 648 |

Actual argparse parameters found in entry file:
| Parameter | Type | Default | Required | Source |
|---|---|---|---|---|
| --csv | str | none | false | scripts/misc/build_zone_registry_from_trades.py argparse line 58 |
| --dir | str | none | false | scripts/misc/build_zone_registry_from_trades.py argparse line 59 |
| --glob | str | none | false | scripts/misc/build_zone_registry_from_trades.py argparse line 60 |
| --output-root | str | models/bitnet | false | scripts/misc/build_zone_registry_from_trades.py argparse line 61 |
| --global-registry | bool | none | false | scripts/misc/build_zone_registry_from_trades.py argparse line 63; action=store_true |

## 4. Runtime Flow
1. main() collects trades CSVs from --csv/--dir/--glob, adapts schema with pandas, calls run_bitnet_search(), and writes per-instrument or global zone registry output.

## 5. Inputs
- CLI parameters listed above from registry/argparse source.

## 6. Outputs
| Output | Path | Produced By |
|---|---|---|
| models/bitnet/{instrument}/zone_registry.json or models/zone_registry.json. | see output text | source functions listed in Runtime Flow/Entry Point |

## 7. External Dependencies
NOT FOUND IN SOURCE for API/network calls. Local Python imports and filesystem dependencies are listed in Inputs/Flow.

## 8. Orchestration Relationships
Called by src/control_plane/jobs.py::JobManager._execute_run() as a registered subprocess. Additional downstream calls are in Runtime Flow.

## 9. State Classification
PARTIALLY_CONNECTED - source imports run_bitnet_search from unqualified train_pipeline; resolution under control-plane cwd is not proven in this file.

## 10. Hidden Risks / Important Findings
- NOT FOUND IN SOURCE

# COMMAND: groq.prepare_retrospective

## 1. Human Purpose
Phase-1 Groq Bridge: prepare a retrospective prompt from trades/opportunities for LLM review. Source: src/control_plane/registry.py::core_command_specs() line 666.

## 2. Entry Point
File: scripts/groq_bridge/prepare_retrospective.py
Callable: scripts/groq_bridge/prepare_retrospective.py::main()
Registry Reference: src/control_plane/registry.py::core_command_specs() line 666; mode python-file.

## 3. CLI Parameters
Registry-declared parameters:
| Parameter | Type/Kind | Default | Required | Source |
|---|---|---|---|---|
| --source | file | None | no | src/control_plane/registry.py::core_command_specs() line 666 |
| --compressed-summary | file | None | no | src/control_plane/registry.py::core_command_specs() line 666 |
| --target-model | str | None | no | src/control_plane/registry.py::core_command_specs() line 666 |
| --output | str | None | no | src/control_plane/registry.py::core_command_specs() line 666 |
| --summary | file | None | no | src/control_plane/registry.py::core_command_specs() line 666 |
| --last-n | int | 200 | no | src/control_plane/registry.py::core_command_specs() line 666 |
| --instrument | str | 'UNKNOWN' | no | src/control_plane/registry.py::core_command_specs() line 666 |
| --dry-run | bool | False | no | src/control_plane/registry.py::core_command_specs() line 666 |

Actual argparse parameters found in entry file:
| Parameter | Type | Default | Required | Source |
|---|---|---|---|---|
| --source | str | none | false | scripts/groq_bridge/prepare_retrospective.py argparse line 619 |
| --compressed-summary | str | none | false | scripts/groq_bridge/prepare_retrospective.py argparse line 628 |
| --target-model | str | none | false | scripts/groq_bridge/prepare_retrospective.py argparse line 637; choices=[gaussian, zone, rr] |
| --output | str | none | false | scripts/groq_bridge/prepare_retrospective.py argparse line 646 |
| --summary | str | none | false | scripts/groq_bridge/prepare_retrospective.py argparse line 652 |
| --last-n | int | 200 | false | scripts/groq_bridge/prepare_retrospective.py argparse line 657 |
| --instrument | str | UNKNOWN | false | scripts/groq_bridge/prepare_retrospective.py argparse line 663 |
| --dry-run | bool | none | false | scripts/groq_bridge/prepare_retrospective.py argparse line 668; action=store_true |

## 4. Runtime Flow
1. main() reads source CSV/JSON/JSONL or compressed summary, builds a prompt, and unless dry-run writes pending prompt plus bridge session/trace records; no Groq API call is present in this command.

## 5. Inputs
- CLI parameters listed above from registry/argparse source.

## 6. Outputs
| Output | Path | Produced By |
|---|---|---|
| logs/groq_bridge/pending_{session_id}.txt and bridge session/trace files unless dry-run. | see output text | source functions listed in Runtime Flow/Entry Point |

## 7. External Dependencies
NOT FOUND IN SOURCE for Groq API/network call; command writes a prompt for manual console use.

## 8. Orchestration Relationships
Called by src/control_plane/jobs.py::JobManager._execute_run() as a registered subprocess. Additional downstream calls are in Runtime Flow.

## 9. State Classification
EXPERIMENTAL - manual Groq bridge prompt/session workflow.

## 10. Hidden Risks / Important Findings
- NOT FOUND IN SOURCE

# COMMAND: groq.ingest_response

## 1. Human Purpose
Phase-1 Groq Bridge: ingest LLM JSON response and optionally apply config/training suggestions. Source: src/control_plane/registry.py::core_command_specs() line 688.

## 2. Entry Point
File: scripts/groq_bridge/ingest_response.py
Callable: scripts/groq_bridge/ingest_response.py::main()
Registry Reference: src/control_plane/registry.py::core_command_specs() line 688; mode python-file.

## 3. CLI Parameters
Registry-declared parameters:
| Parameter | Type/Kind | Default | Required | Source |
|---|---|---|---|---|
| --session | str | None | no | src/control_plane/registry.py::core_command_specs() line 688 |
| --response-file | file | None | no | src/control_plane/registry.py::core_command_specs() line 688 |
| --list-sessions | bool | False | no | src/control_plane/registry.py::core_command_specs() line 688 |
| --show | bool | False | no | src/control_plane/registry.py::core_command_specs() line 688 |
| --record-score | float | None | no | src/control_plane/registry.py::core_command_specs() line 688 |
| --apply-config | bool | False | no | src/control_plane/registry.py::core_command_specs() line 688 |
| --apply-to-training | bool | False | no | src/control_plane/registry.py::core_command_specs() line 688 |
| --target-model | str | None | no | src/control_plane/registry.py::core_command_specs() line 688 |
| --opportunities | file | None | no | src/control_plane/registry.py::core_command_specs() line 688 |
| --version | str | None | no | src/control_plane/registry.py::core_command_specs() line 688 |
| --groq-model | str | 'llama-3.3-70b-versatile' | no | src/control_plane/registry.py::core_command_specs() line 688 |

Actual argparse parameters found in entry file:
| Parameter | Type | Default | Required | Source |
|---|---|---|---|---|
| --session | str | none | false | scripts/groq_bridge/ingest_response.py argparse line 339 |
| --response-file | str | none | false | scripts/groq_bridge/ingest_response.py argparse line 340 |
| --list-sessions | bool | none | false | scripts/groq_bridge/ingest_response.py argparse line 341; action=store_true |
| --show | bool | none | false | scripts/groq_bridge/ingest_response.py argparse line 342; action=store_true |
| --record-score | float | none | false | scripts/groq_bridge/ingest_response.py argparse line 343 |
| --apply-config | bool | none | false | scripts/groq_bridge/ingest_response.py argparse line 349; action=store_true |
| --apply-to-training | bool | none | false | scripts/groq_bridge/ingest_response.py argparse line 354; action=store_true |
| --target-model | str | none | false | scripts/groq_bridge/ingest_response.py argparse line 364; choices=[gaussian, zone, rr] |
| --opportunities | str | none | false | scripts/groq_bridge/ingest_response.py argparse line 370 |
| --version | str | none | false | scripts/groq_bridge/ingest_response.py argparse line 376 |
| --groq-model | str | llama-3.3-70b-versatile | false | scripts/groq_bridge/ingest_response.py argparse line 381 |

## 4. Runtime Flow
1. main() lists/shows sessions, records scores, or ingests a local response file; it saves response/insight state and can call apply_llm_suggestions.py through subprocess.

## 5. Inputs
- CLI parameters listed above from registry/argparse source.

## 6. Outputs
| Output | Path | Produced By |
|---|---|---|
| logs/groq_bridge/response_{session_id}.txt, insight/session registry updates, and optional child training outputs. | see output text | source functions listed in Runtime Flow/Entry Point |

## 7. External Dependencies
NOT FOUND IN SOURCE for Groq API/network call; response is read from local file.

## 8. Orchestration Relationships
Can call groq.apply_llm_suggestions via subprocess.

## 9. State Classification
EXPERIMENTAL - manual Groq response ingestion/forwarder.

## 10. Hidden Risks / Important Findings
- NOT FOUND IN SOURCE

# COMMAND: groq.apply_llm_suggestions

## 1. Human Purpose
Phase-1 Groq Bridge: apply LLM hyperparameter suggestions from a JSON response file to re-train a model. Source: src/control_plane/registry.py::core_command_specs() line 712.

## 2. Entry Point
File: scripts/groq_bridge/apply_llm_suggestions.py
Callable: scripts/groq_bridge/apply_llm_suggestions.py::main()
Registry Reference: src/control_plane/registry.py::core_command_specs() line 712; mode python-file.

## 3. CLI Parameters
Registry-declared parameters:
| Parameter | Type/Kind | Default | Required | Source |
|---|---|---|---|---|
| --target-model | str | None | yes | src/control_plane/registry.py::core_command_specs() line 712 |
| --suggestions-file | file | None | yes | src/control_plane/registry.py::core_command_specs() line 712 |
| --opportunities | file | None | yes | src/control_plane/registry.py::core_command_specs() line 712 |
| --version | str | None | yes | src/control_plane/registry.py::core_command_specs() line 712 |

Actual argparse parameters found in entry file:
| Parameter | Type | Default | Required | Source |
|---|---|---|---|---|
| --target-model | str | none | True | scripts/groq_bridge/apply_llm_suggestions.py argparse line 131; choices=[gaussian, zone, rr] |
| --suggestions-file | Path | none | True | scripts/groq_bridge/apply_llm_suggestions.py argparse line 132 |
| --opportunities | str | none | True | scripts/groq_bridge/apply_llm_suggestions.py argparse line 134 |
| --version | str | none | True | scripts/groq_bridge/apply_llm_suggestions.py argparse line 136 |

## 4. Runtime Flow
1. main() loads a JSON-ish suggestions file and dispatches local subprocesses: gaussian to phase5_calibration.py, zone to discover_zones.py, and rr to hard-coded rr_pattern_miner.py locations.

## 5. Inputs
- CLI parameters listed above from registry/argparse source.

## 6. Outputs
| Output | Path | Produced By |
|---|---|---|
| Downstream outputs from phase5_calibration.py or discover_zones.py; rr branch output only if hard-coded miner path exists. | see output text | source functions listed in Runtime Flow/Entry Point |

## 7. External Dependencies
NOT FOUND IN SOURCE for API/network calls. Local Python imports and filesystem dependencies are listed in Inputs/Flow.

## 8. Orchestration Relationships
Calls phase5_calibration, discover_zones, or rr miner subprocess paths based on target model.

## 9. State Classification
PARTIALLY_CONNECTED - gaussian and zone paths dispatch real scripts, rr branch searches paths that do not match active RR trainer import.

## 10. Hidden Risks / Important Findings
- RR branch searches src/training/rr_pattern_miner.py and scripts/training/rr_pattern_miner.py, while active RR trainer imports config_layer.rr.rr_pattern_miner.

# COMMAND: analysis.daily_crypto_structure

## 1. Human Purpose
Extract daily market structure from BTC/crypto JSONL collector logs into a CSV report. Source: src/control_plane/registry.py::core_command_specs() line 730.

## 2. Entry Point
File: scripts/analysis/daily_crypto_structure.py
Callable: scripts/analysis/daily_crypto_structure.py::load_opportunities(), analyse_daily(); CLI block
Registry Reference: src/control_plane/registry.py::core_command_specs() line 730; mode python-file.

## 3. CLI Parameters
Registry-declared parameters:
| Parameter | Type/Kind | Default | Required | Source |
|---|---|---|---|---|
| --log | file | None | yes | src/control_plane/registry.py::core_command_specs() line 730 |
| --output | str | 'btc_daily_structure.csv' | no | src/control_plane/registry.py::core_command_specs() line 730 |

Actual argparse parameters found in entry file:
| Parameter | Type | Default | Required | Source |
|---|---|---|---|---|
| --log | str | none | True | scripts/analysis/daily_crypto_structure.py argparse line 101 |
| --output | str | btc_daily_structure.csv | false | scripts/analysis/daily_crypto_structure.py argparse line 102 |

## 4. Runtime Flow
1. CLI loads opportunity JSONL through load_opportunities(), analyse_daily() groups daily structure, and pandas writes output CSV.

## 5. Inputs
- CLI parameters listed above from registry/argparse source.

## 6. Outputs
| Output | Path | Produced By |
|---|---|---|
| CSV at --output, default btc_daily_structure.csv. | see output text | source functions listed in Runtime Flow/Entry Point |

## 7. External Dependencies
NOT FOUND IN SOURCE for API/network calls. Local Python imports and filesystem dependencies are listed in Inputs/Flow.

## 8. Orchestration Relationships
Called by src/control_plane/jobs.py::JobManager._execute_run() as a registered subprocess. Additional downstream calls are in Runtime Flow.

## 9. State Classification
RESEARCH_ONLY - registered command runs offline data, tuning, training, replay, analysis, or maintenance behavior and no live production side effect is proven in this command section.

## 10. Hidden Risks / Important Findings
- NOT FOUND IN SOURCE

# COMMAND: analysis.schema_audit

## 1. Human Purpose
Audit trades CSV files for schema consistency against CANONICAL_FEATURES. Source: src/control_plane/registry.py::core_command_specs() line 743.

## 2. Entry Point
File: scripts/analysis/schema_audit.py
Callable: scripts/analysis/schema_audit.py::main()
Registry Reference: src/control_plane/registry.py::core_command_specs() line 743; mode python-file.

## 3. CLI Parameters
Registry-declared parameters:
| Parameter | Type/Kind | Default | Required | Source |
|---|---|---|---|---|
| --root | str | None | no | src/control_plane/registry.py::core_command_specs() line 743 |
| --csv | file | None | no | src/control_plane/registry.py::core_command_specs() line 743 |

Actual argparse parameters found in entry file:
| Parameter | Type | Default | Required | Source |
|---|---|---|---|---|
| --root | str | none | false | scripts/analysis/schema_audit.py argparse line 59 |
| --csv | str | none | false | scripts/analysis/schema_audit.py argparse line 60 |

## 4. Runtime Flow
1. main() reads --root or --csv, _audit_csvs() scans *_trades.csv, _read_csv_schema() samples headers, and the command prints schema distribution.

## 5. Inputs
- CLI parameters listed above from registry/argparse source.

## 6. Outputs
| Output | Path | Produced By |
|---|---|---|
| stdout only; no file write found. | see output text | source functions listed in Runtime Flow/Entry Point |

## 7. External Dependencies
NOT FOUND IN SOURCE for API/network calls. Local Python imports and filesystem dependencies are listed in Inputs/Flow.

## 8. Orchestration Relationships
Called by src/control_plane/jobs.py::JobManager._execute_run() as a registered subprocess. Additional downstream calls are in Runtime Flow.

## 9. State Classification
RESEARCH_ONLY - registered command runs offline data, tuning, training, replay, analysis, or maintenance behavior and no live production side effect is proven in this command section.

## 10. Hidden Risks / Important Findings
- NOT FOUND IN SOURCE

# COMMAND: analysis.sl_tp_comparator

## 1. Human Purpose
Run dual SL/TP strategy comparison on an M15 CSV and report optimal settings. Source: src/control_plane/registry.py::core_command_specs() line 756.

## 2. Entry Point
File: src/analytics/sl_tp_comparator.py
Callable: src/analytics/sl_tp_comparator.py::_cli(), run_comparison_from_backtest()
Registry Reference: src/control_plane/registry.py::core_command_specs() line 756; mode python-file.

## 3. CLI Parameters
Registry-declared parameters:
| Parameter | Type/Kind | Default | Required | Source |
|---|---|---|---|---|
| --csv | file | None | yes | src/control_plane/registry.py::core_command_specs() line 756 |
| --instrument | choice | 'UNKNOWN' | no | src/control_plane/registry.py::core_command_specs() line 756; choices=EURUSD,GBPUSD,AUDUSD,USDJPY,USDCAD,USDCHF,NZDUSD,EURGBP |
| --output | str | None | no | src/control_plane/registry.py::core_command_specs() line 756 |
| --metric | str | None | no | src/control_plane/registry.py::core_command_specs() line 756 |

Actual argparse parameters found in entry file:
| Parameter | Type | Default | Required | Source |
|---|---|---|---|---|
| --csv | str | none | True | src/analytics/sl_tp_comparator.py argparse line 648 |
| --instrument | str | UNKNOWN | false | src/analytics/sl_tp_comparator.py argparse line 649 |
| --output | str | none | false | src/analytics/sl_tp_comparator.py argparse line 650 |
| --metric | str | none | false | src/analytics/sl_tp_comparator.py argparse line 651 |

## 4. Runtime Flow
1. _cli() calls run_comparison_from_backtest(); that runs BacktestRunner, reads generated trades CSV, compares SL/TP methods, and ComparisonReport.save_json() writes report.

## 5. Inputs
- CLI parameters listed above from registry/argparse source.

## 6. Outputs
| Output | Path | Produced By |
|---|---|---|
| Comparison JSON, default results/sl_tp_comparison.json. | see output text | source functions listed in Runtime Flow/Entry Point |

## 7. External Dependencies
NOT FOUND IN SOURCE for API/network calls. Local Python imports and filesystem dependencies are listed in Inputs/Flow.

## 8. Orchestration Relationships
Calls BacktestRunner.

## 9. State Classification
RESEARCH_ONLY - registered command runs offline data, tuning, training, replay, analysis, or maintenance behavior and no live production side effect is proven in this command section.

## 10. Hidden Risks / Important Findings
- NOT FOUND IN SOURCE

# COMMAND: analysis.fusion_shadow

## 1. Human Purpose
Analyse EngineRunner fusion decisions from flow_collector.log — compares shadow vs live gate outputs. Source: src/control_plane/registry.py::core_command_specs() line 771.

## 2. Entry Point
File: src/runtime/analyze_fusion_shadow.py
Callable: src/runtime/analyze_fusion_shadow.py::main(), analyze_log()
Registry Reference: src/control_plane/registry.py::core_command_specs() line 771; mode python-file.

## 3. CLI Parameters
Registry-declared parameters:
| Parameter | Type/Kind | Default | Required | Source |
|---|---|---|---|---|
| --log-path | str | 'logs/flow_collector.log' | no | src/control_plane/registry.py::core_command_specs() line 771 |
| --output-dir | str | 'results/validation/automation' | no | src/control_plane/registry.py::core_command_specs() line 771 |

Actual argparse parameters found in entry file:
| Parameter | Type | Default | Required | Source |
|---|---|---|---|---|
| --log-path | str | logs/flow_collector.log | false | src/runtime/analyze_fusion_shadow.py argparse line 115 |
| --output-dir | str | results/validation/automation | false | src/runtime/analyze_fusion_shadow.py argparse line 120 |

## 4. Runtime Flow
1. main() calls analyze_log() for flow_collector JSON payloads and writes timestamped fusion_shadow_analysis JSON under output-dir.

## 5. Inputs
- CLI parameters listed above from registry/argparse source.

## 6. Outputs
| Output | Path | Produced By |
|---|---|---|
| fusion_shadow_analysis_{timestamp}.json under results/validation/automation by default. | see output text | source functions listed in Runtime Flow/Entry Point |

## 7. External Dependencies
NOT FOUND IN SOURCE for API/network calls. Local Python imports and filesystem dependencies are listed in Inputs/Flow.

## 8. Orchestration Relationships
Called by src/control_plane/jobs.py::JobManager._execute_run() as a registered subprocess. Additional downstream calls are in Runtime Flow.

## 9. State Classification
RESEARCH_ONLY - registered command runs offline data, tuning, training, replay, analysis, or maintenance behavior and no live production side effect is proven in this command section.

## 10. Hidden Risks / Important Findings
- NOT FOUND IN SOURCE

# COMMAND: agent.cli

## 1. Human Purpose
Launch the CRT Trading Agent REPL for natural-language pipeline control. Source: src/control_plane/registry.py::core_command_specs() line 785.

## 2. Entry Point
File: src/agent/cli.py
Callable: src/agent/cli.py::main(), _load_config(), AgentCore
Registry Reference: src/control_plane/registry.py::core_command_specs() line 785; mode python-file.

## 3. CLI Parameters
Registry-declared parameters:
| Parameter | Type/Kind | Default | Required | Source |
|---|---|---|---|---|
| --resume | str | None | no | src/control_plane/registry.py::core_command_specs() line 785 |

Actual argparse parameters found in entry file:
| Parameter | Type | Default | Required | Source |
|---|---|---|---|---|
| --resume | str | none | false | src/agent/cli.py argparse line 51 |

## 4. Runtime Flow
1. main() imports agent modes, loads production agent config or fallback via _load_config(), constructs AgentCore, optionally resumes AgentState, loops stdin through AgentCore.turn(), then saves state.

## 5. Inputs
- CLI parameters listed above from registry/argparse source.
- agent config section or fallback config from src/agent/cli.py::_load_config(); stdin user text.

## 6. Outputs
| Output | Path | Produced By |
|---|---|---|
| stdout responses, session files under configured session_dir, and audit log through AgentCore/AuditLogger. | see output text | source functions listed in Runtime Flow/Entry Point |

## 7. External Dependencies
Fallback config contains model_endpoint http://127.0.0.1:8080/completion; network call is not in cli.py itself.

## 8. Orchestration Relationships
Called by src/control_plane/jobs.py::JobManager._execute_run() as a registered subprocess. Additional downstream calls are in Runtime Flow.

## 9. State Classification
EXPERIMENTAL - interactive agent CLI registered as command, not a training/backtest/promotion pipeline.

## 10. Hidden Risks / Important Findings
- NOT FOUND IN SOURCE

# COMMAND: data.historical_fetcher

## 1. Human Purpose
Fetch multi-pair historical OHLCV data from exchange APIs into data/ directory. Source: src/control_plane/registry.py::core_command_specs() line 798.

## 2. Entry Point
File: src/data_ingestion/historical_fetcher.py
Callable: src/data_ingestion/historical_fetcher.py::_main(), HistoricalFetcher.fetch_and_store()
Registry Reference: src/control_plane/registry.py::core_command_specs() line 798; mode python-file.

## 3. CLI Parameters
Registry-declared parameters:
| Parameter | Type/Kind | Default | Required | Source |
|---|---|---|---|---|
| --pair | str | None | no | src/control_plane/registry.py::core_command_specs() line 798 |
| --timeframe | str | 'M15' | no | src/control_plane/registry.py::core_command_specs() line 798 |
| --start | str | None | no | src/control_plane/registry.py::core_command_specs() line 798 |
| --end | str | None | no | src/control_plane/registry.py::core_command_specs() line 798 |
| --all-pairs | bool | False | no | src/control_plane/registry.py::core_command_specs() line 798 |

Actual argparse parameters found in entry file:
| Parameter | Type | Default | Required | Source |
|---|---|---|---|---|
| --pair | str | none | True | src/data_ingestion/historical_fetcher.py argparse line 576 |
| --timeframe | str | none | True | src/data_ingestion/historical_fetcher.py argparse line 577 |
| --start | str | none | True | src/data_ingestion/historical_fetcher.py argparse line 578 |
| --end | str | none | True | src/data_ingestion/historical_fetcher.py argparse line 579 |
| --all-pairs | bool | none | false | src/data_ingestion/historical_fetcher.py argparse line 580; action=store_true |

## 4. Runtime Flow
1. _main() parses pair/timeframe/date args, constructs HistoricalFetcher, and fetch_and_store() checks DB ranges, fetches missing data from configured sources, and inserts rows.

## 5. Inputs
- CLI parameters listed above from registry/argparse source.
- data_ingestion config section: db_url, schema, ohlcv_table, pairs, timeframes, mt5_enabled, csv_fallback_dir, batch_size, connection_timeout_sec.

## 6. Outputs
| Output | Path | Produced By |
|---|---|---|
| Rows inserted into configured OHLCV database table; stdout/log output. | see output text | source functions listed in Runtime Flow/Entry Point |

## 7. External Dependencies
Timescale/Postgres through psycopg2, optional MetaTrader5, and CSV fallback directory.

## 8. Orchestration Relationships
Called by src/control_plane/jobs.py::JobManager._execute_run() as a registered subprocess. Additional downstream calls are in Runtime Flow.

## 9. State Classification
PARTIALLY_CONNECTED - real fetcher exists, but registry optional/default params conflict with required argparse flags.

## 10. Hidden Risks / Important Findings
- Registry marks pair/timeframe/start/end with defaults, but actual argparse requires all four.

# COMMAND: data.fetch_alphavantage

## 1. Human Purpose
Download M15 forex OHLCV candles from Alpha Vantage FX_INTRADAY API into data/. Source: src/control_plane/registry.py::core_command_specs() line 814.

## 2. Entry Point
File: scripts/data/fetch_candles_alphavantage.py
Callable: scripts/data/fetch_candles_alphavantage.py::main(), AlphaVantageCandleFetcher
Registry Reference: src/control_plane/registry.py::core_command_specs() line 814; mode python-file.

## 3. CLI Parameters
Registry-declared parameters:
| Parameter | Type/Kind | Default | Required | Source |
|---|---|---|---|---|
| --pair | choice | None | yes | src/control_plane/registry.py::core_command_specs() line 814; choices=EURUSD,GBPUSD,AUDUSD,USDJPY,USDCHF,USDCAD,NZDUSD,EURCAD |
| --start | date | None | yes | src/control_plane/registry.py::core_command_specs() line 814 |
| --end | date | None | yes | src/control_plane/registry.py::core_command_specs() line 814 |
| --interval | choice | '15min' | no | src/control_plane/registry.py::core_command_specs() line 814; choices=1min,5min,15min,30min,60min |
| --api-key | str | None | no | src/control_plane/registry.py::core_command_specs() line 814 |
| --out | str | 'data' | no | src/control_plane/registry.py::core_command_specs() line 814 |
| --config | file | 'configs/production/v1_multi_2026_03.json' | no | src/control_plane/registry.py::core_command_specs() line 814 |

Actual argparse parameters found in entry file:
| Parameter | Type | Default | Required | Source |
|---|---|---|---|---|
| --pair | str | none | false | scripts/data/fetch_candles_alphavantage.py argparse line 58 |
| --interval | str | none | false | scripts/data/fetch_candles_alphavantage.py argparse line 62 |
| --start | str | none | True | scripts/data/fetch_candles_alphavantage.py argparse line 66 |
| --end | str | none | True | scripts/data/fetch_candles_alphavantage.py argparse line 67 |
| --api-key | str | none | false | scripts/data/fetch_candles_alphavantage.py argparse line 68; dest=api_key |
| --out | str | none | false | scripts/data/fetch_candles_alphavantage.py argparse line 72 |
| --config | str | configs/production/v1_multi_2026_03.json | false | scripts/data/fetch_candles_alphavantage.py argparse line 73 |

## 4. Runtime Flow
1. main() loads config and API key from CLI/env, constructs AlphaVantageCandleFetcher, fetches monthly API slices through urllib.request.urlopen, and _write_csv() writes candle CSV.

## 5. Inputs
- CLI parameters listed above from registry/argparse source.
- Config JSON plus AV_API_KEY environment variable or --api-key.

## 6. Outputs
| Output | Path | Produced By |
|---|---|---|
| CSV under output directory from AlphaVantageCandleFetcher._write_csv(). | see output text | source functions listed in Runtime Flow/Entry Point |

## 7. External Dependencies
Alpha Vantage HTTPS API at https://www.alphavantage.co/query via urllib.request.urlopen; AV_API_KEY env fallback.

## 8. Orchestration Relationships
Called by src/control_plane/jobs.py::JobManager._execute_run() as a registered subprocess. Additional downstream calls are in Runtime Flow.

## 9. State Classification
RESEARCH_ONLY - registered command runs offline data, tuning, training, replay, analysis, or maintenance behavior and no live production side effect is proven in this command section.

## 10. Hidden Risks / Important Findings
- NOT FOUND IN SOURCE

# COMMAND: data.fetch_hummingbot

## 1. Human Purpose
Download M15 crypto OHLCV candles from exchange via Hummingbot connector into data/. Source: src/control_plane/registry.py::core_command_specs() line 843.

## 2. Entry Point
File: scripts/data/fetch_candles_hummingbot.py
Callable: scripts/data/fetch_candles_hummingbot.py::main(), HummingbotCandleFetcher
Registry Reference: src/control_plane/registry.py::core_command_specs() line 843; mode python-file.

## 3. CLI Parameters
Registry-declared parameters:
| Parameter | Type/Kind | Default | Required | Source |
|---|---|---|---|---|
| --pair | choice | None | yes | src/control_plane/registry.py::core_command_specs() line 843; choices=BTCUSDT,ETHUSDT,XAUUSD |
| --exchange | choice | 'binance' | no | src/control_plane/registry.py::core_command_specs() line 843; choices=binance,bybit,okx,kucoin,kraken |
| --start | date | None | yes | src/control_plane/registry.py::core_command_specs() line 843 |
| --end | date | None | yes | src/control_plane/registry.py::core_command_specs() line 843 |
| --interval | choice | '15m' | no | src/control_plane/registry.py::core_command_specs() line 843; choices=1m,5m,15m,30m,1h,4h,1d |
| --out | str | 'data' | no | src/control_plane/registry.py::core_command_specs() line 843 |
| --config | file | 'configs/production/v1_multi_2026_03.json' | no | src/control_plane/registry.py::core_command_specs() line 843 |

Actual argparse parameters found in entry file:
| Parameter | Type | Default | Required | Source |
|---|---|---|---|---|
| --exchange | str | none | false | scripts/data/fetch_candles_hummingbot.py argparse line 57 |
| --pair | str | none | false | scripts/data/fetch_candles_hummingbot.py argparse line 58 |
| --interval | str | none | false | scripts/data/fetch_candles_hummingbot.py argparse line 59 |
| --start | str | none | True | scripts/data/fetch_candles_hummingbot.py argparse line 60 |
| --end | str | none | True | scripts/data/fetch_candles_hummingbot.py argparse line 61 |
| --out | str | none | false | scripts/data/fetch_candles_hummingbot.py argparse line 62 |
| --all-instruments | bool | none | false | scripts/data/fetch_candles_hummingbot.py argparse line 63; action=store_true |
| --config | str | configs/production/v1_multi_2026_03.json | false | scripts/data/fetch_candles_hummingbot.py argparse line 64 |

## 4. Runtime Flow
1. main() loads config, constructs HummingbotCandleFetcher, calls fetch() or fetch_all_instruments(), and _write_csv() writes public exchange candle CSVs.

## 5. Inputs
- CLI parameters listed above from registry/argparse source.

## 6. Outputs
| Output | Path | Produced By |
|---|---|---|
| CSV under output directory from HummingbotCandleFetcher._write_csv(). | see output text | source functions listed in Runtime Flow/Entry Point |

## 7. External Dependencies
Hummingbot connectors and public exchange candle sources through CandlesFactory.

## 8. Orchestration Relationships
Called by src/control_plane/jobs.py::JobManager._execute_run() as a registered subprocess. Additional downstream calls are in Runtime Flow.

## 9. State Classification
RESEARCH_ONLY - registered command runs offline data, tuning, training, replay, analysis, or maintenance behavior and no live production side effect is proven in this command section.

## 10. Hidden Risks / Important Findings
- Actual argparse includes --all-instruments; registry omits it.

# COMMAND: tuning.auto_tuner_gemini_gate

## 1. Human Purpose
CRT Engine auto-tuner with Gemini gate variant — multi-instrument Bayesian optimisation. Source: src/control_plane/registry.py::core_command_specs() line 874.

## 2. Entry Point
File: scripts/training/auto_tuner_gemini_gate.py
Callable: scripts/training/auto_tuner_gemini_gate.py::main(), run_backtest()
Registry Reference: src/control_plane/registry.py::core_command_specs() line 874; mode python-file.

## 3. CLI Parameters
Registry-declared parameters:
| Parameter | Type/Kind | Default | Required | Source |
|---|---|---|---|---|
| --csv | file | None | no | src/control_plane/registry.py::core_command_specs() line 874 |
| --instrument | choice | None | no | src/control_plane/registry.py::core_command_specs() line 874; choices=EURUSD,GBPUSD,AUDUSD,USDJPY,USDCAD,USDCHF,NZDUSD,EURGBP |
| --data-dir | str | 'data' | no | src/control_plane/registry.py::core_command_specs() line 874 |
| --instruments | list | [] | no | src/control_plane/registry.py::core_command_specs() line 874 |
| --output-dir | str | 'results/tuner' | no | src/control_plane/registry.py::core_command_specs() line 874 |
| --n-iter | int | 100 | no | src/control_plane/registry.py::core_command_specs() line 874 |
| --seed | int | 42 | no | src/control_plane/registry.py::core_command_specs() line 874 |
| --workers | int | None | no | src/control_plane/registry.py::core_command_specs() line 874 |
| --train-split | float | 1.0 | no | src/control_plane/registry.py::core_command_specs() line 874 |

Actual argparse parameters found in entry file:
| Parameter | Type | Default | Required | Source |
|---|---|---|---|---|
| --csv | str | none | false | scripts/training/auto_tuner_gemini_gate.py argparse line 524 |
| --instrument | str | none | false | scripts/training/auto_tuner_gemini_gate.py argparse line 525 |
| --data-dir | str | data | false | scripts/training/auto_tuner_gemini_gate.py argparse line 526 |
| --instruments | str | none | false | scripts/training/auto_tuner_gemini_gate.py argparse line 527; nargs=+ |
| --output-dir | str | results/tuner | false | scripts/training/auto_tuner_gemini_gate.py argparse line 528 |
| --n-iter | int | 100 | false | scripts/training/auto_tuner_gemini_gate.py argparse line 529 |
| --seed | int | 42 | false | scripts/training/auto_tuner_gemini_gate.py argparse line 530 |
| --workers | int | os.cpu_count() or 4 | false | scripts/training/auto_tuner_gemini_gate.py argparse line 531 |
| --train-split | float | 1.0 | false | scripts/training/auto_tuner_gemini_gate.py argparse line 532 |

## 4. Runtime Flow
1. main() constructs the tuner and calls run_backtest(); the script imports config_layer.llm_scorer.llm_score and writes Gemini-named tuner logs/checkpoints.

## 5. Inputs
- CLI parameters listed above from registry/argparse source.

## 6. Outputs
| Output | Path | Produced By |
|---|---|---|
| results/tuner/live_log_gemini_pro.jsonl, results/tuner/runs_gemini_pro, and checkpoint_gemini_pro.json. | see output text | source functions listed in Runtime Flow/Entry Point |

## 7. External Dependencies
config_layer.llm_scorer.llm_score imported; direct Gemini API call NOT FOUND IN SOURCE in this script.

## 8. Orchestration Relationships
Called by src/control_plane/jobs.py::JobManager._execute_run() as a registered subprocess. Additional downstream calls are in Runtime Flow.

## 9. State Classification
EXPERIMENTAL - separate LLM-gated tuner variant.

## 10. Hidden Risks / Important Findings
- NOT FOUND IN SOURCE

# COMMAND: validation.portfolio

## 1. Human Purpose
Run portfolio-level validation across all instruments and emit a consolidated report. Source: src/control_plane/registry.py::core_command_specs() line 895.

## 2. Entry Point
File: src/governance/portfolio_validation.py
Callable: src/governance/portfolio_validation.py::main(), run_portfolio(), PortfolioAnalytics
Registry Reference: src/control_plane/registry.py::core_command_specs() line 895; mode python-file.

## 3. CLI Parameters
Registry-declared parameters:
| Parameter | Type/Kind | Default | Required | Source |
|---|---|---|---|---|
| --output | str | 'results/portfolio' | no | src/control_plane/registry.py::core_command_specs() line 895 |
| --capital | float | 100000.0 | no | src/control_plane/registry.py::core_command_specs() line 895 |

Actual argparse parameters found in entry file:
| Parameter | Type | Default | Required | Source |
|---|---|---|---|---|
| --output | str | _DEFAULT_OUTPUT_DIR | false | src/governance/portfolio_validation.py argparse line 563 |
| --capital | float | _DEFAULT_INITIAL_CAPITAL | false | src/governance/portfolio_validation.py argparse line 564 |

## 4. Runtime Flow
1. main() calls run_portfolio(); run_portfolio() iterates hard-coded INSTRUMENTS, runs BacktestRunner, aggregates PortfolioAnalytics metrics, and writes portfolio_report.json.

## 5. Inputs
- CLI parameters listed above from registry/argparse source.

## 6. Outputs
| Output | Path | Produced By |
|---|---|---|
| {output}/portfolio_report.json and printed portfolio report. | see output text | source functions listed in Runtime Flow/Entry Point |

## 7. External Dependencies
NOT FOUND IN SOURCE for API/network calls. Local Python imports and filesystem dependencies are listed in Inputs/Flow.

## 8. Orchestration Relationships
Calls BacktestRunner.

## 9. State Classification
LIVE_PRODUCTION - validates portfolio behavior using production defaults.

## 10. Hidden Risks / Important Findings
- NOT FOUND IN SOURCE

# COMMAND: promotion.promote_v2

## 1. Human Purpose
Thin wrapper for v2 multi-instrument promotion — validate and write production config. Source: src/control_plane/registry.py::core_command_specs() line 908.

## 2. Entry Point
File: scripts/governance/promote_v2.py
Callable: scripts/governance/promote_v2.py::main()
Registry Reference: src/control_plane/registry.py::core_command_specs() line 908; mode python-file.

## 3. CLI Parameters
Registry-declared parameters:
| Parameter | Type/Kind | Default | Required | Source |
|---|---|---|---|---|
| --version | str | 'v2_multi_2026_04' | no | src/control_plane/registry.py::core_command_specs() line 908 |
| --dry-run | bool | False | no | src/control_plane/registry.py::core_command_specs() line 908 |
| --config-id | str | 'multi_strategy_v2_2026_05' | no | src/control_plane/registry.py::core_command_specs() line 908 |

Actual argparse parameters found in entry file:
| Parameter | Type | Default | Required | Source |
|---|---|---|---|---|
| --version | str | v2_multi_2026_04 | false | scripts/governance/promote_v2.py argparse line 39 |
| --dry-run | bool | none | false | scripts/governance/promote_v2.py argparse line 41; action=store_true |
| --config-id | str | multi_strategy_v2_2026_05 | false | scripts/governance/promote_v2.py argparse line 43 |

## 4. Runtime Flow
1. main() validates hard-coded CSV paths through MultiStrategyValidator, writes a validation report, and if approved and not dry-run calls PromotionManager.promote_from_report().

## 5. Inputs
- CLI parameters listed above from registry/argparse source.

## 6. Outputs
| Output | Path | Produced By |
|---|---|---|
| results/{version}_{timestamp}.json and production registry writes through PromotionManager when approved. | see output text | source functions listed in Runtime Flow/Entry Point |

## 7. External Dependencies
NOT FOUND IN SOURCE for API/network calls. Local Python imports and filesystem dependencies are listed in Inputs/Flow.

## 8. Orchestration Relationships
Calls PromotionManager.promote_from_report().

## 9. State Classification
LIVE_PRODUCTION - can call PromotionManager to write production registry.

## 10. Hidden Risks / Important Findings
- Call to PromotionManager.promote_from_report() does not pass csv_paths, so PromotionManager stale-report revalidation is skipped.

# COMMAND: training.train_bitnet

## 1. Human Purpose
Train legacy BitNet ternary model from M15 CSV data. Source: src/control_plane/registry.py::core_command_specs() line 923.

## 2. Entry Point
File: scripts/training/train_bitnet.py
Callable: scripts/training/train_bitnet.py::main(), build_dataset(), train()
Registry Reference: src/control_plane/registry.py::core_command_specs() line 923; mode python-file.

## 3. CLI Parameters
Registry-declared parameters:
| Parameter | Type/Kind | Default | Required | Source |
|---|---|---|---|---|
| --csv | list | [] | no | src/control_plane/registry.py::core_command_specs() line 923 |
| --epochs | int | 300 | no | src/control_plane/registry.py::core_command_specs() line 923 |
| --lr | float | 0.001 | no | src/control_plane/registry.py::core_command_specs() line 923 |
| --out | str | 'model.json' | no | src/control_plane/registry.py::core_command_specs() line 923 |

Actual argparse parameters found in entry file:
| Parameter | Type | Default | Required | Source |
|---|---|---|---|---|
| --csv | str | [data/EURUSD_M15.csv, data/GBPUSD_M15.csv, data/AUDUSD_M15.csv] | false | scripts/training/train_bitnet.py argparse line 242; nargs=+ |
| --epochs | int | 300 | false | scripts/training/train_bitnet.py argparse line 246 |
| --lr | float | 0.001 | false | scripts/training/train_bitnet.py argparse line 247 |
| --out | str | model.json | false | scripts/training/train_bitnet.py argparse line 248 |

## 4. Runtime Flow
1. main() calls build_dataset() on CSVs, train() on numeric features, and writes a JSON model to --out; no registry update is present in this command.

## 5. Inputs
- CLI parameters listed above from registry/argparse source.

## 6. Outputs
| Output | Path | Produced By |
|---|---|---|
| JSON model at --out, default model.json. | see output text | source functions listed in Runtime Flow/Entry Point |

## 7. External Dependencies
NOT FOUND IN SOURCE for API/network calls. Local Python imports and filesystem dependencies are listed in Inputs/Flow.

## 8. Orchestration Relationships
Called by src/control_plane/jobs.py::JobManager._execute_run() as a registered subprocess. Additional downstream calls are in Runtime Flow.

## 9. State Classification
RESEARCH_ONLY - registered command runs offline data, tuning, training, replay, analysis, or maintenance behavior and no live production side effect is proven in this command section.

## 10. Hidden Risks / Important Findings
- No model registry update found in scripts/training/train_bitnet.py::main().

# DEAD / UNUSED COMPONENTS

- archive/dead_code/ui/dashboard.py, archive/dead_code/journal/trade_logger.py, archive/dead_code/journal/schema.py, archive/dead_code/features/bitnet_feature_builder.py, archive/dead_code/config_layer/insight_reporter.py, and archive/dead_code/bitnet/_smoke_test.py are explicitly marked ARCHIVED 2026-04-28 - Dead Code Pass at file line 1.
- archive/inout_legacy/ARCHIVED_2026_05_02/README.md marks legacy src/inout as archived. The active registered command live.inout_runner targets inout.runner, but importlib resolution found no active module.
- ui_kits/control_plane/mockApi.js is stale relative to src/control_plane/registry.py::core_command_specs(); active registry has 38 commands while the mock source text reflects a smaller generated set.
- scripts/auto_train_from_opportunities.py docstring states optional LLM hypertuning is currently stubbed and wired only manually through groq_bridge.
- scripts/training/phase5_calibration.py defines --integrate as deprecated/no-op; src/runtime/backtest_v2.py comments mark injected scorer compatibility code as deprecated.
- scripts/groq_bridge/apply_llm_suggestions.py RR branch searches src/training/rr_pattern_miner.py and scripts/training/rr_pattern_miner.py; registered RR trainer imports config_layer.rr.rr_pattern_miner.
- Registry/actual CLI drift is documented in each affected command section above.

# FINAL RULE

If this report says NOT FOUND IN SOURCE, the audited source did not prove the requested item for that command.
