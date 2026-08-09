"""CommandSpec registry: the catalog of control-plane commands."""

from __future__ import annotations

from dataclasses import replace
import json
import shlex
import sys
from pathlib import Path
from typing import Any

from src.control_plane.cp_types import ArgSpec, CommandSpec

REPO_ROOT = Path(__file__).resolve().parents[2]

_KNOWN_INSTRUMENTS: tuple[str, ...] = (
    "EURUSD", "GBPUSD", "AUDUSD", "USDJPY",
    "USDCAD", "USDCHF", "NZDUSD", "EURGBP",
)
WORKFLOW_STAGE_ORDER: tuple[str, ...] = (
    "Data Prep",
    "Tuning",
    "Model Training",
    "Validation & Promotion",
    "Replay & Backtest",
    "Live Runner",
)

_WORKFLOW_STAGE_BY_COMMAND: dict[str, str] = {
    "data.prepare_data": "Data Prep",
    "data.unified_data_builder": "Data Prep",
    "data.fetch_alphavantage": "Data Prep",
    "data.fetch_hummingbot": "Data Prep",
    "tuning.auto_tuner_multi": "Tuning",
    "tuning.auto_tuner": "Tuning",
    "training.opportunity_scanner": "Model Training",
    "training.phase5_calibration": "Model Training",
    "training.discover_zones": "Model Training",
    "training.build_rr_dataset": "Model Training",
    "training.train_rr_model": "Model Training",
    "training.train_pipeline": "Model Training",
    "training.auto_train": "Model Training",
    "analysis.compress_logs": "Model Training",
    "validation.config_validator": "Validation & Promotion",
    "promotion.manager": "Validation & Promotion",
    "governance.orchestrator": "Validation & Promotion",
    "governance.script_census": "Validation & Promotion",
    "governance.seed_script_registry": "Validation & Promotion",
    "governance.query_scripts": "Validation & Promotion",
    "replay.unified": "Replay & Backtest",
    "backtest.v2": "Replay & Backtest",
    "backtest.bitnet": "Replay & Backtest",
    "baseline.capture": "Replay & Backtest",
    "live.inout_runner": "Live Runner",
}

_QUICKSTART_NOTES_BY_COMMAND: dict[str, tuple[str, ...]] = {
    "data.prepare_data": (
        "Start here when converting raw source files to normalized M15 CSV outputs.",
        "Use --validate-only first when ingesting a new provider format.",
        "Verify generated files in data/ before moving to tuning.",
    ),
    "data.unified_data_builder": (
        "Use for batch multi-instrument build when data arrives in mixed layouts.",
        "Run before tuner so instruments are aligned in one build cycle.",
        "Inspect output CSV timestamps for alignment sanity.",
    ),
    "tuning.auto_tuner_multi": (
        "Primary optimizer for multi-instrument calibration.",
        "Set --instruments and --output-dir to isolate each campaign.",
        "Track checkpoint JSON in results/tuner before validation.",
    ),
    "tuning.auto_tuner": (
        "Use for single-instrument or ad hoc experiments.",
        "Resume prior runs with --resume to avoid losing search state.",
        "Promote only after validator approval.",
    ),
    "training.opportunity_scanner": (
        "Run after data prep — generates unbiased JSONL training data for all ML models.",
        "Set --tp-atr-mult 2.0 --sl-atr-mult 1.0 to match the production 2R target.",
        "Output: logs/opportunities_{instrument}.jsonl — feed this into Phase 5 and Discover Zones.",
        "Run once per instrument (e.g. 8 runs for 8 instruments). Multi-select all resulting JSONL files when feeding Phase-5 Calibration and Discover Zones.",
    ),
    "training.phase5_calibration": (
        "Run after Opportunity Scanner — trains the Gaussian model on unbiased historical data.",
        "Use --force to save a MARGINAL model (corr below 0.05 gate) for testing.",
        "Check results/p5_calibration_{version}.json for corr_expected_rr and calibration_error.",
        "Accepts multiple --opportunities files — pass ALL per-instrument JSONL outputs from Opportunity Scanner for a merged shared model.",
    ),
    "training.discover_zones": (
        "Run after Opportunity Scanner — clusters candle contexts into zone registry for Zone Gate.",
        "Start with --n-clusters 8 and increase if zone coverage is low.",
        "Output: models/zone_registry_kmeans.json — loaded by the Zone Gate engine at runtime.",
        "Accepts multiple --opportunities files — pass ALL per-instrument JSONL outputs from Opportunity Scanner for a merged shared registry.",
    ),
    "training.build_rr_dataset": (
        "Preferred: use --opportunities (unbiased JSONL). Legacy: --csv / --dir for trades CSVs.",
        "Each run saves a versioned models/rr_dataset_{version}.json + updates rr_registry.json.",
        "Follow with 'Train RR Model' to train the model from the saved dataset.",
        "Accepts multiple --opportunities files — pass ALL per-instrument JSONL outputs from Opportunity Scanner for a merged shared dataset.",
    ),
    "training.train_rr_model": (
        "Trains RR Pattern Miner from the active (or specified) rr_registry dataset.",
        "Each run saves a versioned models/rr_model_{version}.json + updates rr_registry.json.",
        "Use --promote to set as active and update canonical models/rr_model.json for the runtime.",
    ),
    "training.train_pipeline": (
        "Use 'gaussian' subcommand to update the Gaussian registry from fusion JSONL logs.",
        "Use 'tradenet' subcommand to train the binary trade classifier from labeled data.",
        "Supply --version to track model versions across runs.",
    ),
    "training.auto_train": (
        "Nightly orchestrator — runs scan → compress → Gaussian training → optional promotion.",
        "Use --no-promote for dry runs; add --promote-if-approved for automated nightly jobs.",
        "Check logs/opportunities_*.jsonl and results/p5_calibration_*.json after the run.",
    ),
    "analysis.compress_logs": (
        "Run after Opportunity Scanner to prepare logs for LLM governance review.",
        "Pass logs/opportunities_*.jsonl (or fusion JSONL) as --logs input.",
        "Output: compact JSON with summary/data/anomalies — feed to Governance Orchestrator.",
    ),
    "data.fetch_alphavantage": (
        "Requires a free Alpha Vantage API key — set AV_API_KEY environment variable or pass --api-key.",
        "Free tier: 25 requests/day. Fetching 1 year of M15 data = 12 monthly API calls per pair.",
        "Output lands in data/ as {PAIR}_M15.csv — feed directly into Prepare Data (validate-only) next.",
    ),
    "data.fetch_hummingbot": (
        "Fetches from Binance/Bybit/OKX via Hummingbot connectors — no API key required for public candles.",
        "Output lands in data/ as {PAIR}_M15.csv — feed directly into Prepare Data (validate-only) next.",
        "Use 'binance' exchange for BTCUSDT/ETHUSDT. Use 'bybit' for XAUUSD (spot).",
    ),
    "validation.config_validator": (
        "Gate candidate params with hard and soft quality checks.",
        "Use validate-prod for regression baselines, validate-params for candidates.",
        "Review warnings and hard_failures before promotion.",
    ),
    "promotion.manager": (
        "Moves approved configs into configs/production with audit trail.",
        "Use list to inspect versions, promote/from-report for controlled release.",
        "Confirm promotion log and registry artifacts after run.",
    ),
    "governance.orchestrator": (
        "Runs full governance loop: reflection to promotion decision.",
        "Provide collector log, trades CSV, and baseline PnL from same dataset.",
        "Use for governance-driven iteration, not first-pass tuning.",
    ),
    "replay.unified": (
        "Compares v2 execution truth and BitNet gate behaviors.",
        "Use before promotion to inspect alignment drift and gating impact.",
        "Review unified report JSON in results/alignment.",
    ),
    "backtest.v2": (
        "Execution-truth backtest with detailed metrics and trade outputs.",
        "Use single CSV first, then directory/ALL mode for portfolio view.",
        "Check summary and trades outputs before validation.",
    ),
    "backtest.bitnet": (
        "Backtest with explicit BitNet gate modes for audit and diagnostics.",
        "Use score_only_audit to compare gate effect without hard blocking.",
        "Inspect decision logs in logs/backtest_decisions_*.jsonl.",
    ),
    "baseline.capture": (
        "Capture reproducible state snapshot before major workflow runs.",
        "Use a label tied to experiment phase for traceability.",
        "Store manifest path with run notes for rollback context.",
    ),
    "live.inout_runner": (
        "Runs INOUT loop for controlled live/dry execution monitoring.",
        "Start with finite --cycles in new environments.",
        "Watch heartbeat and audit logs continuously during execution.",
    ),
}

_RECOMMENDED_NEXT_BY_COMMAND: dict[str, tuple[str, ...]] = {
    "data.prepare_data": ("data.unified_data_builder", "tuning.auto_tuner_multi"),
    "data.unified_data_builder": ("tuning.auto_tuner_multi",),
    "data.fetch_alphavantage": ("data.prepare_data",),
    "data.fetch_hummingbot": ("data.prepare_data",),
    "tuning.auto_tuner_multi": ("training.opportunity_scanner", "validation.config_validator"),
    "tuning.auto_tuner": ("training.opportunity_scanner", "validation.config_validator"),
    "training.opportunity_scanner": ("training.phase5_calibration", "training.discover_zones"),
    "training.phase5_calibration": ("training.discover_zones", "validation.config_validator"),
    "training.discover_zones": ("training.build_rr_dataset", "validation.config_validator"),
    "training.build_rr_dataset": ("training.train_rr_model", "validation.config_validator"),
    "training.train_rr_model": ("validation.config_validator",),
    "training.train_pipeline": ("validation.config_validator",),
    "training.auto_train": ("validation.config_validator",),
    "analysis.compress_logs": ("governance.orchestrator",),
    "validation.config_validator": ("promotion.manager", "replay.unified"),
    "promotion.manager": ("baseline.capture", "live.inout_runner"),
    "governance.orchestrator": ("live.inout_runner",),
    "replay.unified": ("backtest.v2", "backtest.bitnet"),
    "backtest.v2": ("validation.config_validator",),
    "backtest.bitnet": ("replay.unified",),
    "baseline.capture": ("tuning.auto_tuner_multi",),
    "live.inout_runner": ("replay.unified", "governance.orchestrator"),
}


def core_command_specs() -> tuple[CommandSpec, ...]:
    specs = (
        CommandSpec(
            id="data.prepare_data",
            title="Prepare Data",
            description="Convert and validate raw source files into normalized M15 outputs.",
            category="Data Prep",
            mode="python-file",
            script="scripts/data/prepare_data.py",
            args_schema=(
                ArgSpec("source", flag="--source", kind="choice", default="standard", choices=("histdata", "binance", "standard")),
                ArgSpec("files", flag="--files", kind="file-multi", default=[],
                        file_glob="data/*",
                        help="Source files to import (leave empty for auto-discover)"),
                ArgSpec("instrument", flag="--instrument", kind="choice",
                        default="EURUSD", choices=_KNOWN_INSTRUMENTS,
                        help="Target instrument symbol"),
                ArgSpec("output", flag="--output", kind="str", default="data"),
                ArgSpec("already_m15", flag="--already-m15", kind="bool", default=False),
                ArgSpec("validate_only", flag="--validate-only", kind="bool", default=False),
            ),
            artifacts=("data/*.csv",),
        ),
        CommandSpec(
            id="data.unified_data_builder",
            title="Unified Data Builder",
            description="Build unified multi-instrument data outputs for CRT workflows.",
            category="Data Prep",
            mode="python-file",
            script="scripts/data/unified_data_builder.py",
            quickstart_notes=("Use for batch multi-instrument build when data arrives in mixed layouts.",),
            args_schema=(
                ArgSpec("instruments", flag=None, kind="list", default=[],
                        positional=True, positional_index=0,
                        help="Instruments to build (empty = all configured). e.g. EURUSD GBPUSD"),
                ArgSpec("data_dir",      flag="--data-dir",      kind="str",  default="data",  help="Directory with raw M1 CSVs"),
                ArgSpec("output_dir",    flag="--output-dir",    kind="str",  default="data",  help="Directory to write M15 CSVs"),
                ArgSpec("validate_only", flag="--validate-only", kind="bool", default=False,   help="Validate existing M15 files only, no building"),
                ArgSpec("dry_run",       flag="--dry-run",       kind="bool", default=False,   help="Preview what would be built, no output"),
            ),
            artifacts=("data/*.csv", "results/**/*.json"),
        ),
        CommandSpec(
            id="tuning.auto_tuner_multi",
            title="Auto Tuner (Multi)",
            description="Run multi-instrument tuner and emit checkpoint artifacts.",
            category="Tuning",
            mode="python-file",
            script="scripts/training/auto_tuner_multi.py",
            args_schema=(
                ArgSpec("csv", flag="--csv", kind="file", default=None, file_glob="data/*.csv", help="Single CSV file — overrides data_dir"),
                ArgSpec("instrument", flag="--instrument", kind="choice",
                        default="EURUSD", choices=_KNOWN_INSTRUMENTS,
                        help="Single instrument override (empty = all in data_dir)"),
                ArgSpec("data_dir", flag="--data-dir", kind="str", default="data", help="Directory containing per-instrument CSV files"),
                ArgSpec("instruments", flag="--instruments", kind="list", default=[], help="Comma-separated instrument list to tune (empty=all in data_dir)"),
                ArgSpec("output_dir", flag="--output-dir", kind="str", default="results/tuner", help="Directory for checkpoint and results output"),
                ArgSpec("n_iter", flag="--n-iter", kind="int", default=100, min_val=1, max_val=10000, help="Number of Bayesian search iterations (1–10000)"),
                ArgSpec("seed", flag="--seed", kind="int", default=42, min_val=0, max_val=2147483647, help="Random seed for reproducibility"),
                ArgSpec("workers", flag="--workers", kind="int", default=4, min_val=1, max_val=64, help="Parallel worker processes (1–64)"),
                ArgSpec("train_split", flag="--train-split", kind="float", default=1.0, min_val=0.1, max_val=1.0, help="Fraction of data used for training (0.1–1.0)"),
                ArgSpec("no_llm", flag="--no-llm", kind="bool", default=False, help="Disable LLM-assisted tuning hints"),
            ),
            artifacts=("results/tuner/**/*.json", "results/tuner/**/*.csv"),
        ),
        CommandSpec(
            id="tuning.auto_tuner",
            title="Auto Tuner",
            description="Run single/multi instrument tuner for parameter optimization.",
            category="Tuning",
            mode="python-file",
            script="scripts/training/auto_tuner.py",
            args_schema=(
                ArgSpec("csv", flag="--csv", kind="file", default=None, file_glob="data/*.csv", help="Single CSV file"),
                ArgSpec("instrument", flag="--instrument", kind="choice",
                        default="EURUSD", choices=_KNOWN_INSTRUMENTS,
                        help="Single instrument override (empty = all in data_dir)"),
                ArgSpec("data_dir", flag="--data-dir", kind="str", default="data", help="Directory containing per-instrument CSV files"),
                ArgSpec("instruments", flag="--instruments", kind="list", default=[], help="Comma-separated instrument list (empty=all)"),
                ArgSpec("output_dir", flag="--output-dir", kind="str", default="results/tuner", help="Directory for checkpoint and results output"),
                ArgSpec("n_iter", flag="--n-iter", kind="int", default=100, min_val=1, max_val=10000, help="Number of Bayesian search iterations (1–10000)"),
                ArgSpec("seed", flag="--seed", kind="int", default=42, min_val=0, max_val=2147483647, help="Random seed for reproducibility"),
                ArgSpec("resume", flag="--resume", kind="file", default=None,
                        file_glob="results/tuner/*.json",
                        help="Resume from existing checkpoint JSON"),
                ArgSpec("multi", flag="--multi", kind="bool", default=False, help="Enable multi-instrument mode"),
                ArgSpec("verbose", flag="--verbose", kind="bool", default=False, help="Enable verbose logging"),
            ),
            artifacts=("results/tuner/**/*.json", "results/tuner/**/*.csv"),
        ),
        CommandSpec(
            id="validation.config_validator",
            title="Config Validator",
            description="Validate production or candidate params with quality gates.",
            category="Validation & Promotion",
            mode="python-file",
            script="src/config_layer/config_validator.py",
            args_schema=(
                ArgSpec("subcommand", positional=True, positional_index=0, kind="choice", default="validate-prod", choices=("validate-prod", "validate-params")),
                ArgSpec("data_dir", flag="--data-dir", kind="str", default="data", applies_to=("validate-prod", "validate-params")),
                ArgSpec("version", flag="--version", kind="str", default=None, applies_to=("validate-prod",)),
                ArgSpec("output", flag="--output", kind="str",
                        default="results/validation_report.json",
                        applies_to=("validate-prod", "validate-params"),
                        help="Output ValidationReport JSON path"),
                ArgSpec("params", flag="--params", kind="file", default=None,
                        file_glob="configs/production/*.json",
                        applies_to=("validate-params",),
                        help="Config JSON to validate"),
                ArgSpec("config_id", flag="--config-id", kind="str", default="cli_validation", applies_to=("validate-params",)),
            ),
            artifacts=("results/validation/**/*.json", "results/validation/**/*.csv"),
        ),
        CommandSpec(
            id="promotion.manager",
            title="Promotion Manager",
            description="List and promote validated configs into production registry.",
            category="Validation & Promotion",
            mode="python-file",
            script="src/governance/promotion_manager.py",
            args_schema=(
                ArgSpec("subcommand", positional=True, positional_index=0, kind="choice", default="list", choices=("list", "promote", "from-report")),
                ArgSpec("checkpoint", flag="--checkpoint", kind="file", default=None,
                        file_glob="results/tuner/*.json",
                        applies_to=("promote",),
                        help="Tuner checkpoint JSON from auto_tuner_multi"),
                ArgSpec("version", flag="--version", kind="str", default=None,
                        auto_default="date_version",
                        applies_to=("promote", "from-report"),
                        help="Version label — auto-filled as v5_auto_YYYY_MM"),
                ArgSpec("data_dir", flag="--data-dir", kind="str", default="data", applies_to=("promote",)),
                ArgSpec("instruments", flag="--instruments", kind="list", default=["EURUSD", "GBPUSD", "BTCUSDT", "XAUUSD"], applies_to=("promote",)),
                ArgSpec("notes", flag="--notes", kind="str", default="", applies_to=("promote", "from-report")),
                ArgSpec("no_llm", flag="--no-llm", kind="bool", default=False, applies_to=("promote",)),
                ArgSpec("report", flag="--report", kind="file", default=None,
                        file_glob="results/**/*.json",
                        applies_to=("from-report",),
                        help="ValidationReport JSON from config_validator"),
            ),
            artifacts=("configs/production/*.json", "configs/promotion_log.jsonl", "results/validation/**/*.json"),
        ),
        CommandSpec(
            id="governance.orchestrator",
            title="Governance Orchestrator",
            description="Run reflection → meta-governor → shadow gate → promotion loop.",
            category="Validation & Promotion",
            mode="python-file",
            script="src/governance/orchestrator.py",
            args_schema=(
                ArgSpec("compressed_summary", flag="--compressed-summary", kind="file", required=False,
                        file_glob="logs/compressed_*.json",
                        help="Pre-computed compressed summary JSON from compress_logs (mutually exclusive with --collector-log/--trades-csv)"),
                ArgSpec("collector_log", flag="--collector-log", kind="file", required=False,
                        file_glob="logs/**/*.jsonl",
                        help="Live collector JSONL log file (mutually exclusive with --compressed-summary)"),
                ArgSpec("trades_csv", flag="--trades-csv", kind="file", required=False,
                        file_glob="results/**/*_trades.csv",
                        help="Trades CSV from live runner or backtest (mutually exclusive with --compressed-summary)"),
                ArgSpec("baseline_pnl", flag="--baseline-pnl", kind="float", required=True, min_val=-10000000.0, max_val=10000000.0, help="Baseline PnL from same dataset for comparison"),
                ArgSpec("active_config", flag="--active-config", kind="file",
                        default="configs/production/v2_multi_2026_04.json",
                        file_glob="configs/production/*.json",
                        help="Production config JSON to govern against"),
                ArgSpec("bitnet_bin", flag="--bitnet-bin", kind="str", default="./bitnet/bin/main", help="Path to BitNet binary"),
                ArgSpec("model_path", flag="--model-path", kind="str", default="./models/bitnet_b1_58_70b.gguf", help="Path to BitNet GGUF model file"),
                ArgSpec("audit_log", flag="--audit-log", kind="str", default="logs/governance_audit.jsonl", help="Path for governance audit log output"),
                ArgSpec("prompt_path", flag="--prompt-path", kind="str", default="logs/meta_prompt.txt", help="Path for meta-governor prompt output"),
            ),
            artifacts=("logs/governance_audit.jsonl", "logs/meta_prompt.txt", "configs/production/*.json"),
        ),
        CommandSpec(
            id="replay.unified",
            title="Unified Replay Harness",
            description="Compare v2 execution truth and BitNet gate modes on the same data.",
            category="Replay & Backtest",
            mode="python-file",
            script="src/runtime/unified_replay_harness.py",
            args_schema=(
                ArgSpec("config", flag="--config", kind="file",
                        default="configs/production/v2_multi_2026_04.json",
                        file_glob="configs/production/*.json",
                        help="Production config JSON to replay"),
                ArgSpec("data", flag="--data", kind="file", required=True, file_glob="data/*.csv", help="CSV data file for replay"),
                ArgSpec("months", flag="--months", kind="int", default=None, min_val=1, max_val=60, help="Months of data to include (1–60; empty=all)"),
                ArgSpec("output_dir", flag="--output-dir", kind="str", default="results/alignment", help="Directory for alignment report outputs"),
            ),
            artifacts=("results/alignment/**/*.json", "results/alignment/**/*.csv"),
        ),
        CommandSpec(
            id="backtest.v2",
            title="Backtest v2",
            description="Run CRT backtest harness with execution-truth outputs.",
            category="Replay & Backtest",
            mode="python-file",
            script="src/runtime/backtest_v2.py",
            args_schema=(
                ArgSpec("csv", flag="--csv", kind="file", required=True, file_glob="data/*.csv", help="M15 OHLCV CSV file from data folder"),
                ArgSpec("instrument", flag="--instrument", kind="choice",
                        default="AUTO", choices=_KNOWN_INSTRUMENTS + ("AUTO",),
                        help="Instrument — used for output naming and session detection. AUTO = detect from CSV filename"),
                ArgSpec("output", flag="--output", kind="str", default="results", help="Directory for backtest result outputs"),
                ArgSpec("htf", flag="--htf", kind="int", default=None, min_val=1, max_val=100, help="Higher-timeframe lookback candles (1–100)"),
                ArgSpec("warmup", flag="--warmup", kind="int", default=None, min_val=10, max_val=1000, help="Candles to warm up indicators before scoring (10–1000)"),
                ArgSpec("capital", flag="--capital", kind="float", default=None, min_val=1000.0, max_val=10000000.0, help="Starting capital for simulation (1000–10000000)"),
                ArgSpec("risk_pct", flag="--risk-pct", kind="float", default=None, min_val=0.01, max_val=5.0, help="Risk per trade as % of capital (0.01–5.0)"),
                ArgSpec("spread", flag="--spread", kind="float", default=None, min_val=0.0, max_val=0.1, help="Simulated spread cost (0.0–0.1)"),
                ArgSpec("no_slip", flag="--no-slip", kind="bool", default=False, help="Disable slippage simulation"),
                ArgSpec("no_gap_reset", flag="--no-gap-reset", kind="bool", default=False, help="Disable gap-based state reset"),
                ArgSpec("sweep_age", flag="--sweep-age", kind="int", default=20, min_val=5, max_val=100, help="Candles before sweep signal expires (5–100)"),
                ArgSpec("decay", flag="--decay", kind="float", default=0.10, min_val=0.0, max_val=0.5, help="Score decay lambda per candle since retest (0.0–0.5)"),
                ArgSpec("threshold", flag="--threshold", kind="float", default=0.75, min_val=0.0, max_val=1.0, help="Minimum fusion score to open trade (0.0–1.0)"),
            ),
            artifacts=("results/**/*.json", "results/**/*_trades.csv", "results/**/*_summary.csv"),
        ),
        CommandSpec(
            id="backtest.bitnet",
            title="Backtest BitNet Gate",
            description="Run row-level backtest with BitNet gate modes.",
            category="Replay & Backtest",
            mode="python-file",
            script="src/runtime/backtest_bitnet.py",
            args_schema=(
                ArgSpec("config", flag="--config", kind="file",
                        default="configs/production/v2_multi_2026_04.json",
                        file_glob="configs/production/*.json",
                        help="Production config JSON"),
                ArgSpec("data", flag="--data", kind="file", default=None, file_glob="data/*.csv", help="M15 OHLCV CSV file from data folder"),
                ArgSpec("gate_mode", flag="--gate-mode", kind="choice", default="hard_gate", choices=("hard_gate", "score_only_audit", "force_accept_baseline"), help="BitNet gate behaviour: hard_gate blocks trades, score_only_audit logs without blocking, force_accept_baseline bypasses gate"),
                ArgSpec("months", flag="--months", kind="int", default=None, min_val=1, max_val=60, help="Months of data to include (1–60; empty=all)"),
                ArgSpec("output", flag="--output", kind="str", default=None, help="Output path for decision log (default=auto)"),
            ),
            artifacts=("logs/backtest_decisions_*.jsonl", "results/**/*.csv", "results/**/*.json"),
        ),
        CommandSpec(
            id="baseline.capture",
            title="Baseline Capture",
            description="Capture a baseline manifest for current repo/model/config state.",
            category="Replay & Backtest",
            mode="python-file",
            script="src/runtime/baseline_capture.py",
            args_schema=(
                ArgSpec("label", flag="--label", kind="str", default="phase0"),
                ArgSpec("output_dir", flag="--output-dir", kind="str", default="results/baseline"),
            ),
            artifacts=("results/baseline/**/manifest.json",),
        ),
        CommandSpec(
            id="live.inout_runner",
            title="INOUT Live Runner",
            description="Run INOUT strategy loop in controlled dry/live mode.",
            category="Live Runner",
            mode="module",
            script="inout.runner",
            args_schema=(
                ArgSpec("cycles", flag="--cycles", kind="int", default=0, min_val=0, max_val=100000, help="Max cycles to run (0=unlimited, 1–100000 for finite run)"),
                ArgSpec("config", flag="--config", kind="file", default=None,
                        file_glob="configs/production/*.json",
                        help="Production config JSON — must be promoted version"),
            ),
            artifacts=("logs/inout_runner.log", "logs/inout_heartbeat.jsonl", "logs/inout_audit.jsonl"),
        ),
        # ── Model Training ────────────────────────────────────────────────────
        CommandSpec(
            id="training.opportunity_scanner",
            title="Opportunity Scanner",
            description="Generate unbiased opportunity logs for Gaussian/Zone model training (Pipeline B).",
            category="Model Training",
            mode="python-file",
            script="scripts/research/opportunity_scanner.py",
            args_schema=(
                ArgSpec("csv",               flag="--csv",               kind="file",  required=True,  file_glob="data/*.csv", help="M15 OHLCV CSV file"),
                ArgSpec("instrument",        flag="--instrument",        kind="choice", required=True,
                        choices=_KNOWN_INSTRUMENTS,
                        help="Instrument symbol — embedded in output filename"),
                ArgSpec("tp_atr_mult",       flag="--tp-atr-mult",       kind="float", default=2.0,    min_val=0.5, max_val=10.0, help="TP = this × ATR (0.5–10)"),
                ArgSpec("sl_atr_mult",       flag="--sl-atr-mult",       kind="float", default=1.0,    min_val=0.1, max_val=5.0,  help="SL = this × ATR (0.1–5)"),
                ArgSpec("max_forward_candles", flag="--max-forward-candles", kind="int", default=40,   min_val=5,   max_val=200,  help="Max bars for forward simulation (5–200)"),
                ArgSpec("warmup_candles",    flag="--warmup-candles",    kind="int",   default=30,     min_val=10,  max_val=500,  help="Warm-up bars before recording (10–500)"),
                ArgSpec("output_dir",        flag="--output-dir",        kind="str",   default="logs", help="Output directory for JSONL files"),
            ),
            artifacts=("logs/opportunities_*.jsonl",),
        ),
        CommandSpec(
            id="training.phase5_calibration",
            title="Gaussian Model Training (Phase 5)",
            description="Train and calibrate the Gaussian model from unbiased opportunity logs. Replaces hardcoded _P5_PARAMS.",
            category="Model Training",
            mode="python-file",
            script="scripts/training/phase5_calibration.py",
            args_schema=(
                ArgSpec("opportunities",  flag="--opportunities",  kind="file",  required=True,  file_glob="logs/opportunities_*.jsonl", help="Select opportunity JSONL from Opportunity Scanner"),
                ArgSpec("version",        flag="--version",        kind="str",   required=True,  auto_default="date_version", help="Version key — auto-filled as v5_auto_YYYY_MM"),
                ArgSpec("train",          flag="--train",          kind="bool",  default=True,   help="Run training (required to produce model file)"),
                ArgSpec("force",          flag="--force",          kind="bool",  default=False,  help="Save even if corr gate fails (MARGINAL models)"),
                ArgSpec("promote",        flag="--promote",        kind="bool",  default=False,  help="Auto-promote to registry if Phase-5 gates pass"),
                ArgSpec("train_ratio",    flag="--train-ratio",    kind="float", default=0.70,   min_val=0.1, max_val=1.0, help="Train/validation split ratio (0.1–1.0)"),
                ArgSpec("feature_subset", flag="--feature-subset", kind="str",   default="",    help="Comma-separated CANONICAL_FEATURE names to keep (others zeroed)"),
                ArgSpec("class_weights",  flag="--class-weights",  kind="str",   default="",    help="Comma-separated priors override (length = n_classes)"),
                ArgSpec("rr_buckets",     flag="--rr-buckets",     kind="str",   default="",    help="Comma-separated RR class upper-bound edges (default: 0.0,1.0,2.0)"),
            ),
            artifacts=("models/gaussian_*.json", "results/p5_calibration_*.json"),
        ),
        CommandSpec(
            id="training.discover_zones",
            title="Zone Gate Training (Discover Zones)",
            description="Cluster opportunity logs into zone registry for the Zone Gate engine via KMeans. Each run saves a versioned file and registers in zone_gate_registry.json.",
            category="Model Training",
            mode="python-file",
            script="scripts/research/discover_zones.py",
            args_schema=(
                ArgSpec("opportunities",   flag="--opportunities",   kind="file-multi", required=True, file_glob="logs/opportunities_*.jsonl", help="Select one or more opportunity JSONLs (Ctrl/⌘ for multiple)"),
                ArgSpec("output",          flag="--output",          kind="str",   default="models/zone_registry.json", help="Canonical output path (also updated when --promote, which is default)"),
                ArgSpec("version",         flag="--version",         kind="str",   default=None, auto_default="date_version", help="Version key for zone_gate_registry — auto-filled as YYYYMM_v1"),
                ArgSpec("n_clusters",      flag="--n-clusters",      kind="int",   default=8,      min_val=2, max_val=64,   help="Number of zone clusters (2–64)"),
                ArgSpec("min_samples",     flag="--min-samples",     kind="int",   default=15,     min_val=1, max_val=1000, help="Drop clusters with fewer samples (1–1000)"),
                ArgSpec("feature_weights", flag="--feature-weights", kind="str",   default="",    help="Comma-separated weights per CANONICAL_FEATURE_ORDER (35 values)"),
            ),
            artifacts=("models/zone_registry_*.json", "models/zone_gate_registry.json"),
        ),
        CommandSpec(
            id="training.build_rr_dataset",
            title="Build RR Dataset",
            description="Build RR training dataset from opportunity scanner JSONL (unbiased) or legacy trades CSVs. Each run saves a versioned dataset file and registers in rr_registry.json.",
            category="Model Training",
            mode="python-file",
            script="scripts/data/build_rr_dataset.py",
            args_schema=(
                ArgSpec("opportunities", flag="--opportunities", kind="file-multi",
                        default=None, file_glob="logs/opportunities_*.jsonl",
                        help="Opportunity JSONL files from scanner (unbiased — recommended)"),
                ArgSpec("csv",    flag="--csv",    kind="file", default=None,
                        file_glob="results/**/*_trades.csv",
                        help="Single *_trades.csv (legacy biased source)"),
                ArgSpec("dir",    flag="--dir",    kind="str",  default=None,
                        help="Directory to scan recursively for *_trades.csv (legacy)"),
                ArgSpec("output", flag="--output", kind="str",
                        default="models/rr_dataset.json",
                        help="Canonical output dataset path"),
                ArgSpec("version", flag="--version", kind="str",
                        default=None, auto_default="date_version",
                        help="Version key for rr_registry — auto-filled as YYYYMM_v1"),
            ),
            artifacts=("models/rr_dataset_*.json", "models/rr_registry.json"),
        ),
        CommandSpec(
            id="training.train_rr_model",
            title="Train RR Model",
            description="Train the RR Pattern Miner from a versioned RR dataset. Saves a uniquely-versioned model file and registers in rr_registry.json.",
            category="Model Training",
            mode="python-file",
            script="scripts/training/train_rr_model.py",
            args_schema=(
                ArgSpec("dataset", flag="--dataset", kind="file",
                        default=None, file_glob="models/rr_dataset_*.json",
                        help="RR dataset JSON (default: active version from rr_registry)"),
                ArgSpec("version", flag="--version", kind="str",
                        default=None, auto_default="date_version",
                        help="Version key for rr_registry — auto-filled as YYYYMM_v1"),
                ArgSpec("output", flag="--output", kind="str",
                        default=None,
                        help="Output model path (default: models/rr_model_{version}.json)"),
                ArgSpec("promote", flag="--promote", kind="bool", default=False,
                        help="Set as active version after training (also writes canonical rr_model.json)"),
            ),
            artifacts=("models/rr_model_*.json", "models/rr_registry.json"),
        ),
        CommandSpec(
            id="training.train_pipeline",
            title="Train Pipeline (TradeNet / Gaussian)",
            description="Run TradeNet binary classifier training or Gaussian registry update from fusion logs.",
            category="Model Training",
            mode="python-file",
            script="scripts/training/train_pipeline.py",
            args_schema=(
                ArgSpec("subcommand",    positional=True, positional_index=0, kind="choice", default="gaussian", choices=("tradenet", "gaussian")),
                ArgSpec("data",          flag="--data",          kind="file",  default=None,
                        file_glob="results/**/*.json",
                        applies_to=("tradenet",), help="Training data JSON (tradenet only)"),
                ArgSpec("output",        flag="--output",        kind="str",  default="results/training_result.json",
                        applies_to=("tradenet",), help="Results JSON output path (tradenet only)"),
                ArgSpec("logs",          flag="--logs",          kind="file-multi", default=[],
                        file_glob="logs/**/*_fusion.jsonl",
                        applies_to=("gaussian",), help="One or more *_fusion.jsonl paths (gaussian only)"),
                ArgSpec("version",       flag="--version",       kind="str",  default=None,
                        auto_default="date_version",
                        applies_to=("gaussian",), help="Registry version key — auto-filled as v5_auto_YYYY_MM"),
                ArgSpec("no_promote",    flag="--no-promote",    kind="bool", default=False, applies_to=("gaussian",), help="Register but skip auto-promotion"),
                ArgSpec("force_promote", flag="--force-promote", kind="bool", default=False, applies_to=("gaussian",), help="Bypass regression guard in promote_gaussian()"),
            ),
            artifacts=("models/gaussian_*.json", "results/training_result.json"),
        ),
        CommandSpec(
            id="training.auto_train",
            title="Auto-Train Pipeline (Nightly)",
            description="Full Pipeline-B nightly loop: scan opportunities → compress → Gaussian training → optional promotion.",
            category="Model Training",
            mode="python-file",
            script="scripts/auto_train_from_opportunities.py",
            args_schema=(
                ArgSpec("data_dir",            flag="--data-dir",            kind="str",  default="data",  help="Directory containing M15 CSV files"),
                ArgSpec("instruments",         flag="--instruments",         kind="list", default=[],      help="Instruments to process (empty = all 8 standard)"),
                ArgSpec("model_version",       flag="--model-version",       kind="str",  default=None,
                        auto_default="date_version",
                        help="Version key — auto-filled as v5_auto_YYYY_MM"),
                ArgSpec("max_forward_candles", flag="--max-forward-candles", kind="int",  default=40,      min_val=5, max_val=200, help="Forward simulation depth (5–200)"),
                ArgSpec("no_promote",          flag="--no-promote",          kind="bool", default=False,   help="Force promotion off even with --promote-if-approved"),
                ArgSpec("promote_if_approved", flag="--promote-if-approved", kind="bool", default=False,   help="Auto-promote if Phase-5 gates pass"),
            ),
            artifacts=("logs/opportunities_*.jsonl", "models/gaussian_*.json", "results/p5_calibration_*.json"),
        ),
        CommandSpec(
            id="analysis.compress_logs",
            title="Compress Logs for LLM",
            description="Stream opportunity JSONL logs into a token-efficient JSON summary for LLM governance.",
            category="Model Training",
            mode="python-file",
            script="scripts/analysis/compress_logs_for_llm.py",
            args_schema=(
                ArgSpec("logs",           flag="--logs",           kind="file-multi", required=True, file_glob="logs/opportunities_*.jsonl", help="Select opportunity JSONLs to compress (Ctrl/⌘ for multiple)"),
                ArgSpec("output",         flag="--output",         kind="str",  required=True, default="logs/compressed_summary.json", auto_default="compressed_from_logs", help="Output path — auto-derived from selected log filename"),
                ArgSpec("top_n_features", flag="--top-n-features", kind="int",  default=8,     min_val=1, max_val=35, help="Top N features in correlation summary (1–35)"),
            ),
            artifacts=("logs/compressed_*.json",),
        ),
        # ── Maintenance ───────────────────────────────────────────────────────
        CommandSpec(
            id="maintenance.update_config_hash",
            title="Update Config Hash",
            description="Recompute and write the SHA-256 hash for a production config JSON. Run after any manual config edit.",
            category="Maintenance",
            mode="python-file",
            script="scripts/update_config_hash.py",
            args_schema=(
                ArgSpec("config_file", flag=None, kind="file", required=True, positional=True, positional_index=0,
                        file_glob="configs/production/*.json", help="Production config JSON to hash"),
                ArgSpec("check",   flag="--check",   kind="bool", default=False, help="Only verify hash — do not update"),
                ArgSpec("dry_run", flag="--dry-run", kind="bool", default=False, help="Show what would change without writing"),
            ),
            artifacts=("configs/production/*.json",),
        ),
        CommandSpec(
            id="maintenance.health_checker",
            title="Health Checker",
            description="Run system health checks and expose a status endpoint.",
            category="Maintenance",
            mode="python-file",
            script="src/monitoring/health_checker.py",
            args_schema=(
                ArgSpec("port", flag="--port", kind="int", default=8788, min_val=1024, max_val=65535, help="HTTP port for health endpoint (1024-65535)"),
            ),
            artifacts=("logs/health_checker.log",),
        ),
        CommandSpec(
            id="maintenance.build_zone_registry",
            title="Build Zone Registry from Trades",
            description="Rebuild per-instrument zone registry JSON files from *_trades.csv output.",
            category="Maintenance",
            mode="python-file",
            script="scripts/misc/build_zone_registry_from_trades.py",
            args_schema=(
                ArgSpec("csv",             flag="--csv",             kind="file", default=None,
                        file_glob="results/**/*_trades.csv", help="Single *_trades.csv to process"),
                ArgSpec("dir",             flag="--dir",             kind="str",  default=None, help="Directory to scan for *_trades.csv"),
                ArgSpec("glob",            flag="--glob",            kind="str",  default=None, help="Glob pattern for trades CSVs"),
                ArgSpec("output_root",     flag="--output-root",     kind="str",  default="models/bitnet", help="Base output dir for per-instrument registries"),
                ArgSpec("global_registry", flag="--global-registry", kind="bool", default=False, help="Write to models/zone_registry.json"),
            ),
            artifacts=("models/bitnet/**/*.json", "models/zone_registry.json"),
        ),
        # ── Groq Bridge ───────────────────────────────────────────────────────
        CommandSpec(
            id="groq.prepare_retrospective",
            title="Prepare Retrospective",
            description="Phase-1 Groq Bridge: prepare a retrospective prompt from trades/opportunities for LLM review.",
            category="Groq Bridge",
            mode="python-file",
            script="scripts/groq_bridge/prepare_retrospective.py",
            args_schema=(
                ArgSpec("source",             flag="--source",             kind="file",  default=None,
                        file_glob="logs/*.jsonl", help="Source file (trades CSV or opportunities JSONL)"),
                ArgSpec("compressed_summary", flag="--compressed-summary", kind="file",  default=None,
                        file_glob="logs/compressed_*.json", help="Pre-computed compressed summary JSON"),
                ArgSpec("target_model",       flag="--target-model",       kind="str",   default=None, help="Target model type (gaussian/zone_gate/rr)"),
                ArgSpec("output",             flag="--output",             kind="str",   default=None, help="Output path for prompt file"),
                ArgSpec("summary",            flag="--summary",            kind="file",  default=None,
                        file_glob="logs/*_summary.json", help="Optional pre-computed summary JSON"),
                ArgSpec("last_n",             flag="--last-n",             kind="int",   default=200, min_val=10, max_val=5000, help="Max recent rows to include (10-5000)"),
                ArgSpec("instrument",         flag="--instrument",         kind="str",   default="UNKNOWN", help="Instrument label for session ID"),
                ArgSpec("dry_run",            flag="--dry-run",            kind="bool",  default=False, help="Preview prompt without writing"),
            ),
            artifacts=("logs/groq_sessions/*/prompt.txt",),
        ),
        CommandSpec(
            id="groq.ingest_response",
            title="Ingest Groq Response",
            description="Phase-1 Groq Bridge: ingest LLM JSON response and optionally apply config/training suggestions.",
            category="Groq Bridge",
            mode="python-file",
            script="scripts/groq_bridge/ingest_response.py",
            args_schema=(
                ArgSpec("session",            flag="--session",            kind="str",   default=None, help="Session ID (RETRO_...)"),
                ArgSpec("response_file",      flag="--response-file",      kind="file",  default=None,
                        file_glob="logs/groq_sessions/**/*.json", help="Path to file with Groq JSON response"),
                ArgSpec("list_sessions",      flag="--list-sessions",      kind="bool",  default=False, help="List all sessions"),
                ArgSpec("show",               flag="--show",               kind="bool",  default=False, help="Show insights for a session"),
                ArgSpec("record_score",       flag="--record-score",       kind="float", default=None, help="Record post-backtest validation score"),
                ArgSpec("apply_config",       flag="--apply-config",       kind="bool",  default=False, help="Apply config changes from session"),
                ArgSpec("apply_to_training",  flag="--apply-to-training",  kind="bool",  default=False, help="Treat response as LLM hypertuning suggestions"),
                ArgSpec("target_model",       flag="--target-model",       kind="str",   default=None, help="Target model for --apply-to-training"),
                ArgSpec("opportunities",      flag="--opportunities",      kind="file",  default=None,
                        file_glob="logs/opportunities_*.jsonl", help="Opportunity log to forward"),
                ArgSpec("version",            flag="--version",            kind="str",   default=None, auto_default="date_version", help="Model version label"),
                ArgSpec("groq_model",         flag="--groq-model",         kind="str",   default="llama-3.3-70b-versatile", help="Groq model name for logging"),
            ),
            artifacts=("logs/groq_sessions/**/insights.json",),
        ),
        CommandSpec(
            id="groq.apply_llm_suggestions",
            title="Apply LLM Suggestions",
            description="Phase-1 Groq Bridge: apply LLM hyperparameter suggestions from a JSON response file to re-train a model.",
            category="Groq Bridge",
            mode="python-file",
            script="scripts/groq_bridge/apply_llm_suggestions.py",
            args_schema=(
                ArgSpec("target_model",    flag="--target-model",    kind="str",  required=True, help="Target model type (gaussian/zone_gate/rr)"),
                ArgSpec("suggestions_file",flag="--suggestions-file",kind="file", required=True,
                        file_glob="logs/groq_sessions/**/*.json", help="LLM JSON response file"),
                ArgSpec("opportunities",   flag="--opportunities",   kind="file", required=True,
                        file_glob="logs/opportunities_*.jsonl", help="Opportunity JSONL used for training"),
                ArgSpec("version",         flag="--version",         kind="str",  required=True, auto_default="date_version", help="Version label for trained model"),
            ),
            artifacts=("models/gaussian_*.json", "models/zone_registry_*.json"),
        ),
        # ── Analysis ──────────────────────────────────────────────────────────
        CommandSpec(
            id="analysis.daily_crypto_structure",
            title="Daily Crypto Structure",
            description="Extract daily market structure from BTC/crypto JSONL collector logs into a CSV report.",
            category="Analysis",
            mode="python-file",
            script="scripts/analysis/daily_crypto_structure.py",
            args_schema=(
                ArgSpec("log",    flag="--log",    kind="file",  required=True, file_glob="logs/*.log", help="Collector log file"),
                ArgSpec("output", flag="--output", kind="str",   default="btc_daily_structure.csv", help="Output CSV path"),
            ),
            artifacts=("btc_daily_structure.csv",),
        ),
        CommandSpec(
            id="analysis.schema_audit",
            title="Schema Audit",
            description="Audit trades CSV files for schema consistency against CANONICAL_FEATURES.",
            category="Analysis",
            mode="python-file",
            script="scripts/analysis/schema_audit.py",
            args_schema=(
                ArgSpec("root", flag="--root", kind="str",  default=None, help="Root dir to scan for *_trades.csv"),
                ArgSpec("csv",  flag="--csv",  kind="file", default=None, file_glob="results/**/*_trades.csv", help="Single trades CSV to check"),
            ),
            artifacts=(),
        ),
        CommandSpec(
            id="analysis.sl_tp_comparator",
            title="SL/TP Comparator",
            description="Run dual SL/TP strategy comparison on an M15 CSV and report optimal settings.",
            category="Analysis",
            mode="python-file",
            script="src/analytics/sl_tp_comparator.py",
            args_schema=(
                ArgSpec("csv",        flag="--csv",        kind="file",   required=True, file_glob="data/*.csv", help="M15 OHLCV CSV file"),
                ArgSpec("instrument", flag="--instrument", kind="choice", default="UNKNOWN", choices=_KNOWN_INSTRUMENTS, help="Instrument symbol"),
                ArgSpec("output",     flag="--output",     kind="str",    default=None, help="Output JSON path"),
                ArgSpec("metric",     flag="--metric",     kind="str",    default=None, help="Primary comparison metric override"),
            ),
            artifacts=("results/sl_tp_comparison_*.json",),
        ),
        CommandSpec(
            id="analysis.fusion_shadow",
            title="Fusion Shadow Analysis",
            description="Analyse EngineRunner fusion decisions from flow_collector.log — compares shadow vs live gate outputs.",
            category="Analysis",
            mode="python-file",
            script="src/runtime/analyze_fusion_shadow.py",
            args_schema=(
                ArgSpec("log_path",   flag="--log-path",   kind="str", default="logs/flow_collector.log", help="Collector log file path"),
                ArgSpec("output_dir", flag="--output-dir", kind="str", default="results/validation/automation", help="Output directory for analysis JSON"),
            ),
            artifacts=("results/validation/automation/*.json",),
        ),
        # ── Agent ─────────────────────────────────────────────────────────────
        CommandSpec(
            id="agent.cli",
            title="Agent REPL",
            description="Launch the CRT Trading Agent REPL for natural-language pipeline control.",
            category="Agent",
            mode="python-file",
            script="src/agent/cli.py",
            args_schema=(
                ArgSpec("resume", flag="--resume", kind="str", default=None, help="Resume a prior agent session by ID"),
            ),
            artifacts=("logs/agent_audit.jsonl", "logs/agent_intent_log.jsonl"),
        ),
        # ── Additional Data Prep ───────────────────────────────────────────────
        CommandSpec(
            id="data.historical_fetcher",
            title="Historical Data Fetcher",
            description="Fetch multi-pair historical OHLCV data from exchange APIs into data/ directory.",
            category="Data Prep",
            mode="python-file",
            script="src/data_ingestion/historical_fetcher.py",
            args_schema=(
                ArgSpec("pair",      flag="--pair",      kind="str",  default=None, help="Trading pair (e.g. EURUSD)"),
                ArgSpec("timeframe", flag="--timeframe", kind="str",  default="M15", help="Timeframe (e.g. M15, H1)"),
                ArgSpec("start",     flag="--start",     kind="str",  default=None, help="Start date YYYY-MM-DD"),
                ArgSpec("end",       flag="--end",       kind="str",  default=None, help="End date YYYY-MM-DD"),
                ArgSpec("all_pairs", flag="--all-pairs", kind="bool", default=False, help="Fetch all configured pairs"),
            ),
            artifacts=("data/*.csv",),
        ),
        CommandSpec(
            id="data.fetch_alphavantage",
            title="Fetch Forex Data (AlphaVantage)",
            description="Download M15 forex OHLCV candles from Alpha Vantage FX_INTRADAY API into data/.",
            category="Data Prep",
            mode="python-file",
            script="scripts/data/fetch_candles_alphavantage.py",
            args_schema=(
                ArgSpec("pair", flag="--pair", kind="choice", required=True,
                        choices=("EURUSD", "GBPUSD", "AUDUSD", "USDJPY", "USDCHF", "USDCAD", "NZDUSD", "EURCAD"),
                        help="Forex pair to fetch"),
                ArgSpec("start", flag="--start", kind="date", required=True,
                        help="Start date inclusive (YYYY-MM-DD)"),
                ArgSpec("end",   flag="--end",   kind="date", required=True,
                        help="End date exclusive (YYYY-MM-DD)"),
                ArgSpec("interval", flag="--interval", kind="choice", default="15min",
                        choices=("1min", "5min", "15min", "30min", "60min"),
                        help="Candle interval (default 15min)"),
                ArgSpec("api_key", flag="--api-key", kind="str", default=None,
                        help="Alpha Vantage API key (falls back to AV_API_KEY env var then config)"),
                ArgSpec("out", flag="--out", kind="str", default="data",
                        help="Output directory (default: data/)"),
                ArgSpec("config", flag="--config", kind="file",
                        default="configs/production/v1_multi_2026_03.json",
                        file_glob="configs/production/*.json",
                        help="Production config JSON (provides api_key and defaults)"),
            ),
            artifacts=("data/*.csv",),
        ),
        CommandSpec(
            id="data.fetch_hummingbot",
            title="Fetch Crypto Data (Hummingbot)",
            description="Download M15 crypto OHLCV candles from exchange via Hummingbot connector into data/.",
            category="Data Prep",
            mode="python-file",
            script="scripts/data/fetch_candles_hummingbot.py",
            args_schema=(
                ArgSpec("pair", flag="--pair", kind="choice", required=True,
                        choices=("BTCUSDT", "ETHUSDT", "XAUUSD"),
                        help="Crypto pair to fetch"),
                ArgSpec("exchange", flag="--exchange", kind="choice", default="binance",
                        choices=("binance", "bybit", "okx", "kucoin", "kraken"),
                        help="Exchange connector (default: binance)"),
                ArgSpec("start", flag="--start", kind="date", required=True,
                        help="Start date inclusive (YYYY-MM-DD)"),
                ArgSpec("end",   flag="--end",   kind="date", required=True,
                        help="End date exclusive (YYYY-MM-DD)"),
                ArgSpec("interval", flag="--interval", kind="choice", default="15m",
                        choices=("1m", "5m", "15m", "30m", "1h", "4h", "1d"),
                        help="Candle interval (default 15m)"),
                ArgSpec("out", flag="--out", kind="str", default="data",
                        help="Output directory (default: data/)"),
                ArgSpec("config", flag="--config", kind="file",
                        default="configs/production/v1_multi_2026_03.json",
                        file_glob="configs/production/*.json",
                        help="Production config JSON (provides exchange/interval defaults)"),
            ),
            artifacts=("data/*.csv",),
        ),
        # ── Additional Tuning ─────────────────────────────────────────────────
        CommandSpec(
            id="tuning.auto_tuner_gemini_gate",
            title="Auto Tuner (Gemini Gate)",
            description="CRT Engine auto-tuner with Gemini gate variant — multi-instrument Bayesian optimisation.",
            category="Tuning",
            mode="python-file",
            script="scripts/training/auto_tuner_gemini_gate.py",
            args_schema=(
                ArgSpec("csv",         flag="--csv",         kind="file",  default=None, file_glob="data/*.csv", help="Single M15 CSV path"),
                ArgSpec("instrument",  flag="--instrument",  kind="choice", default=None, choices=_KNOWN_INSTRUMENTS, help="Instrument symbol"),
                ArgSpec("data_dir",    flag="--data-dir",    kind="str",   default="data", help="Directory with M15 CSVs"),
                ArgSpec("instruments", flag="--instruments", kind="list",  default=[], help="Instruments for multi-instrument mode"),
                ArgSpec("output_dir",  flag="--output-dir",  kind="str",   default="results/tuner", help="Tuner output directory"),
                ArgSpec("n_iter",      flag="--n-iter",      kind="int",   default=100, min_val=1, max_val=1000, help="Bayesian optimisation iterations"),
                ArgSpec("seed",        flag="--seed",        kind="int",   default=42, help="Random seed"),
                ArgSpec("workers",     flag="--workers",     kind="int",   default=None, help="CPU workers (None=auto)"),
                ArgSpec("train_split", flag="--train-split", kind="float", default=1.0, min_val=0.1, max_val=1.0, help="Train split fraction"),
            ),
            artifacts=("results/tuner/checkpoint_*.json",),
        ),
        # ── Additional Validation & Promotion ────────────────────────────────
        CommandSpec(
            id="validation.portfolio",
            title="Portfolio Validation",
            description="Run portfolio-level validation across all instruments and emit a consolidated report.",
            category="Validation & Promotion",
            mode="python-file",
            script="src/governance/portfolio_validation.py",
            args_schema=(
                ArgSpec("output",  flag="--output",  kind="str",   default="results/portfolio", help="Output directory for validation reports"),
                ArgSpec("capital", flag="--capital", kind="float", default=100000.0, min_val=1000.0, help="Starting capital for portfolio simulation"),
            ),
            artifacts=("results/portfolio/*.json",),
        ),
        CommandSpec(
            id="promotion.promote_v2",
            title="Promote v2",
            description="Thin wrapper for v2 multi-instrument promotion — validate and write production config.",
            category="Validation & Promotion",
            mode="python-file",
            script="scripts/governance/promote_v2.py",
            args_schema=(
                ArgSpec("version",   flag="--version",   kind="str",  default="v2_multi_2026_04", help="Production version label"),
                ArgSpec("dry_run",   flag="--dry-run",   kind="bool", default=False, help="Validate only — do not write"),
                ArgSpec("config_id", flag="--config-id", kind="str",  default="multi_strategy_v2_2026_05", help="Config ID label for validation report"),
            ),
            artifacts=("configs/production/*.json", "configs/promotion_log.jsonl"),
        ),
        # ── Model Training (additional) ───────────────────────────────────────
        CommandSpec(
            id="training.train_bitnet",
            title="Train BitNet",
            description="Train legacy BitNet ternary model from M15 CSV data.",
            category="Model Training",
            mode="python-file",
            script="scripts/training/train_bitnet.py",
            args_schema=(
                ArgSpec("csv",    flag="--csv",    kind="list",  default=[], help="M15 CSV paths (space-separated)"),
                ArgSpec("epochs", flag="--epochs", kind="int",   default=300, min_val=1, max_val=5000, help="Training epochs"),
                ArgSpec("lr",     flag="--lr",     kind="float", default=0.001, min_val=1e-6, max_val=1.0, help="Learning rate"),
                ArgSpec("out",    flag="--out",    kind="str",   default="model.json", help="Output model JSON path"),
            ),
            artifacts=("model.json", "models/bitnet/**/*.json"),
        ),
        # ── Multi-LLM Research Lane (plan initiation — no API call) ─────────
        CommandSpec(
            id="research.initiate_plan",
            title="Initiate Multi-LLM Research Plan",
            description=(
                "Prepare model-separated PROPOSAL + plan-design PROMPT + curated CONTEXT_BUNDLE "
                "(ERP docs only; no full-repo scan). Paste into grok/deepseek/gemini/claude/chatgpt. "
                "Does not call LLM APIs."
            ),
            category="Validation & Promotion",
            mode="python-file",
            script="scripts/multi_llm/initiate_plan.py",
            args_schema=(
                ArgSpec(
                    "model",
                    flag="--model",
                    kind="choice",
                    default="grok",
                    choices=("deepseek", "grok", "gemini", "claude", "chatgpt", "all"),
                    help="Target LLM for plan initiation",
                ),
                ArgSpec("cycle", flag="--cycle", kind="str", default="", help="Cycle id (empty=auto RC-timestamp)"),
                ArgSpec("focus", flag="--focus", kind="str", default="", help="Optional plan focus"),
                ArgSpec("no_ledger", flag="--no-ledger", kind="bool", default=False, help="Skip ledger append"),
            ),
            artifacts=(
                "multi_llm/research_lane/proposals/**/PROPOSAL.md",
                "multi_llm/research_lane/proposals/**/PROMPT_FOR_*.md",
                "multi_llm/research_lane/proposals/**/CONTEXT_BUNDLE.md",
                "multi_llm/research_lane/research_cycle_ledger.jsonl",
            ),
        ),
        # ── SITS (Script & Implementation Traceability) operator CLIs ───────
        CommandSpec(
            id="governance.script_census",
            title="Script Census (SITS)",
            description=(
                "Discover scripts/** + root *.py and optionally merge path-stable SCR stubs "
                "(inventory observe layer; no trading behavior)."
            ),
            category="Validation & Promotion",
            mode="python-file",
            script="scripts/analysis/script_census.py",
            args_schema=(
                ArgSpec(
                    "write_stubs",
                    flag="--write-stubs",
                    kind="str",
                    default="",
                    help="If set, merge stubs to this path (e.g. docs/governance/script_registry_stubs.jsonl)",
                ),
                ArgSpec(
                    "json",
                    flag="--json",
                    kind="str",
                    default="",
                    help="Optional census summary JSON output path",
                ),
            ),
            artifacts=(
                "docs/governance/script_registry_stubs.jsonl",
                "reports/script_census.LATEST.json",
            ),
        ),
        CommandSpec(
            id="governance.seed_script_registry",
            title="Seed Script Registry (SITS)",
            description=(
                "Project stubs + overlays + CommandSpec reverse-map into data/script_registry.jsonl "
                "(GENERATED; inventory authority only)."
            ),
            category="Validation & Promotion",
            mode="python-file",
            script="scripts/governance/seed_script_registry.py",
            args_schema=(
                ArgSpec(
                    "stubs",
                    flag="--stubs",
                    kind="str",
                    default="docs/governance/script_registry_stubs.jsonl",
                    help="PRIMARY stubs JSONL path",
                ),
                ArgSpec(
                    "out",
                    flag="--out",
                    kind="str",
                    default="data/script_registry.jsonl",
                    help="Generated registry JSONL path",
                ),
            ),
            artifacts=("data/script_registry.jsonl",),
        ),
        CommandSpec(
            id="governance.query_scripts",
            title="Query Script Registry (SITS)",
            description=(
                "Query/filter the script inventory; --validate runs schema + path checks; "
                "--canonical-gap lists ACTIVE CANONICAL_CLI missing CommandSpec linkage."
            ),
            category="Validation & Promotion",
            mode="python-file",
            script="scripts/governance/query_scripts.py",
            args_schema=(
                ArgSpec("summary", flag="--summary", kind="bool", default=True, help="Print summary JSON"),
                ArgSpec("validate", flag="--validate", kind="bool", default=False, help="Schema/path validation"),
                ArgSpec(
                    "canonical_gap",
                    flag="--canonical-gap",
                    kind="bool",
                    default=False,
                    help="ACTIVE CANONICAL_CLI without control_plane_id / allowlist",
                ),
                ArgSpec(
                    "missing_impl",
                    flag="--missing-impl",
                    kind="bool",
                    default=False,
                    help="logic_in_script without valid promotion plan",
                ),
            ),
            artifacts=("data/script_registry.jsonl",),
        ),
    )
    enriched: list[CommandSpec] = []
    for spec in specs:
        enriched.append(
            replace(
                spec,
                workflow_stage=_WORKFLOW_STAGE_BY_COMMAND.get(spec.id, spec.category),
                quickstart_notes=_QUICKSTART_NOTES_BY_COMMAND.get(spec.id, ()),
                recommended_next_command_ids=_RECOMMENDED_NEXT_BY_COMMAND.get(spec.id, ()),
            )
        )
    return tuple(enriched)


def command_map(specs: tuple[CommandSpec, ...] | None = None) -> dict[str, CommandSpec]:
    chosen = specs or core_command_specs()
    return {spec.id: spec for spec in chosen}


def command_categories(specs: tuple[CommandSpec, ...] | None = None) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for spec in (specs or core_command_specs()):
        if spec.category not in seen:
            seen.add(spec.category)
            out.append(spec.category)
    return out


def workflow_stage_order() -> tuple[str, ...]:
    return WORKFLOW_STAGE_ORDER


def _coerce(kind: str, value: Any) -> Any:
    if kind == "int":
        return int(value)
    if kind == "float":
        return float(value)
    if kind == "bool":
        return bool(value)
    if kind in ("list", "file-multi"):
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            return [v.strip() for v in value.split(",") if v.strip()]
        raise ValueError(f"Expected list-compatible value, got {type(value)}")
    return value


def merge_command_args(spec: CommandSpec, user_args: dict[str, Any] | None) -> dict[str, Any]:
    user_args = user_args or {}
    merged: dict[str, Any] = {}
    selected_subcommand: str | None = None
    for arg in spec.args_schema:
        if arg.key == "subcommand":
            selected_subcommand = user_args.get(arg.key, arg.default)
            break
    for arg in spec.args_schema:
        if arg.applies_to and selected_subcommand not in arg.applies_to:
            merged[arg.key] = None
            continue
        value = user_args.get(arg.key, arg.default)
        if value is None and arg.required:
            raise ValueError(f"Missing required argument: {arg.key}")
        if value is not None:
            value = _coerce(arg.kind, value)
        if arg.kind == "choice" and value is not None and arg.choices and value not in arg.choices:
            raise ValueError(f"Invalid value for {arg.key}: {value}. Choices={arg.choices}")
        if arg.kind in ("int", "float") and value is not None:
            if arg.min_val is not None and value < arg.min_val:
                raise ValueError(f"{arg.key} must be >= {arg.min_val}, got {value}")
            if arg.max_val is not None and value > arg.max_val:
                raise ValueError(f"{arg.key} must be <= {arg.max_val}, got {value}")
        merged[arg.key] = value
    return merged


def build_command_line(spec: CommandSpec, merged_args: dict[str, Any]) -> list[str]:
    if spec.mode == "python-file":
        command = [sys.executable, str(REPO_ROOT / spec.script)]
    else:
        command = [sys.executable, "-m", spec.script]

    positionals = [a for a in spec.args_schema if a.positional]
    positionals.sort(key=lambda a: a.positional_index)
    for arg in positionals:
        value = merged_args.get(arg.key)
        if value is None:
            continue
        if arg.kind in ("list", "file-multi"):
            for item in list(value):
                command.append(str(item))
        else:
            command.append(str(value))

    for arg in spec.args_schema:
        if arg.positional:
            continue
        value = merged_args.get(arg.key)
        if value is None:
            continue
        if arg.kind == "bool":
            if value:
                command.append(arg.flag or "")
            continue
        if arg.kind in ("list", "file-multi"):
            values = list(value)
            if not values:
                continue
            command.append(arg.flag or "")
            for item in values:
                command.append(str(item))
            continue
        if not arg.flag:
            continue
        command.extend([arg.flag, str(value)])

    return [part for part in command if part]


def render_command(spec: CommandSpec, user_args: dict[str, Any] | None = None) -> list[str]:
    merged = merge_command_args(spec, user_args)
    return build_command_line(spec, merged)


def shell_preview(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def command_spec_to_json(spec: CommandSpec) -> dict[str, Any]:
    return {
        "id": spec.id,
        "title": spec.title,
        "description": spec.description,
        "category": spec.category,
        "mode": spec.mode,
        "script": spec.script,
        "args_schema": [
            {
                "key": a.key,
                "flag": a.flag,
                "kind": a.kind,
                "required": a.required,
                "default": a.default,
                "choices": list(a.choices),
                "help": a.help,
                "positional": a.positional,
                "positional_index": a.positional_index,
                "applies_to": list(a.applies_to),
                "min_val": a.min_val,
                "max_val": a.max_val,
                "file_glob": a.file_glob,
                "auto_default": a.auto_default,
            }
            for a in spec.args_schema
        ],
        "artifacts": list(spec.artifacts),
        "success_exit_codes": list(spec.success_exit_codes),
        "workflow_stage": spec.workflow_stage or spec.category,
        "quickstart_notes": list(spec.quickstart_notes),
        "recommended_next_command_ids": list(spec.recommended_next_command_ids),
    }


def generate_cli_matrix_markdown(specs: tuple[CommandSpec, ...] | None = None) -> str:
    lines: list[str] = []
    chosen = specs or core_command_specs()
    lines.append("# CLI Matrix (Generated)\n")
    lines.append("Generated from `src/control_plane/registry.py`.\n")
    lines.append("| ID | Category | Invocation | Artifacts | Suggested Next |")
    lines.append("|---|---|---|---|---|")
    for spec in chosen:
        seed_args: dict[str, Any] = {}
        for arg in spec.args_schema:
            # Seed required args with no default
            if arg.required and arg.default is None:
                if arg.kind == "int":
                    seed_args[arg.key] = 1
                elif arg.kind == "float":
                    seed_args[arg.key] = 1.0
                elif arg.kind == "list":
                    seed_args[arg.key] = ["VALUE"]
                elif arg.kind == "choice" and arg.choices:
                    seed_args[arg.key] = arg.choices[0]
                else:
                    seed_args[arg.key] = f"<{arg.key}>"
            # Also fix optional choice args whose default is not in choices
            elif (arg.kind == "choice" and arg.choices and arg.default is not None
                  and arg.default not in arg.choices):
                seed_args[arg.key] = arg.choices[0]
        try:
            preview = shell_preview(render_command(spec, seed_args))
        except (ValueError, KeyError):
            preview = f"python -m {spec.script} ..."
        artifacts = ", ".join(spec.artifacts) if spec.artifacts else "-"
        suggested = ", ".join(spec.recommended_next_command_ids) if spec.recommended_next_command_ids else "-"
        lines.append(f"| `{spec.id}` | {spec.category} | `{preview}` | `{artifacts}` | `{suggested}` |")
    return "\n".join(lines) + "\n"


def dump_specs_json(specs: tuple[CommandSpec, ...] | None = None) -> str:
    payload = [command_spec_to_json(spec) for spec in (specs or core_command_specs())]
    return json.dumps(payload, indent=2)
