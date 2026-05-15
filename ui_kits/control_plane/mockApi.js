// Mock backend matching shapes from src/control_plane/server.py + registry.py.
// Generated from registry.py core_command_specs() — 12 commands, 5 workflow stages.

const COMMANDS = [
  {
    id: "data.prepare_data", title: "Prepare Data",
    description: "Convert and validate raw source files into normalized M15 outputs.",
    category: "Data Prep", workflow_stage: "Data Prep", mode: "python-file",
    script: "scripts/data/prepare_data.py",
    args_schema: [
      { key: "source", flag: "--source", kind: "choice", default: "standard", choices: ["histdata","binance","standard"] },
      { key: "files", flag: "--files", kind: "list", default: [] },
      { key: "instrument", flag: "--instrument", kind: "str", default: "UNKNOWN" },
      { key: "output", flag: "--output", kind: "str", default: "data" },
      { key: "already_m15", flag: "--already-m15", kind: "bool", default: false },
      { key: "validate_only", flag: "--validate-only", kind: "bool", default: false },
    ],
    artifacts: ["data/*.csv"],
    quickstart_notes: [
      "Start here when converting raw source files to normalized M15 CSV outputs.",
      "Use --validate-only first when ingesting a new provider format.",
      "Verify generated files in data/ before moving to tuning.",
    ],
    recommended_next_command_ids: ["data.unified_data_builder","tuning.auto_tuner_multi"],
  },
  {
    id: "data.unified_data_builder", title: "Unified Data Builder",
    description: "Build unified multi-instrument data outputs for CRT workflows.",
    category: "Data Prep", workflow_stage: "Data Prep", mode: "python-file",
    script: "scripts/data/unified_data_builder.py",
    args_schema: [],
    artifacts: ["data/*.csv","results/**/*.json"],
    quickstart_notes: [
      "Use for batch multi-instrument build when data arrives in mixed layouts.",
      "Run before tuner so instruments are aligned in one build cycle.",
      "Inspect output CSV timestamps for alignment sanity.",
    ],
    recommended_next_command_ids: ["tuning.auto_tuner_multi"],
  },
  {
    id: "tuning.auto_tuner_multi", title: "Auto Tuner (Multi)",
    description: "Run multi-instrument tuner and emit checkpoint artifacts.",
    category: "Tuning", workflow_stage: "Tuning", mode: "python-file",
    script: "scripts/training/auto_tuner_multi.py",
    args_schema: [
      { key: "csv", flag: "--csv", kind: "str", default: null },
      { key: "instrument", flag: "--instrument", kind: "str", default: null },
      { key: "data_dir", flag: "--data-dir", kind: "str", default: "data" },
      { key: "instruments", flag: "--instruments", kind: "list", default: [] },
      { key: "output_dir", flag: "--output-dir", kind: "str", default: "results/tuner" },
      { key: "n_iter", flag: "--n-iter", kind: "int", default: 100 },
      { key: "seed", flag: "--seed", kind: "int", default: 42 },
      { key: "workers", flag: "--workers", kind: "int", default: 4 },
      { key: "train_split", flag: "--train-split", kind: "float", default: 1.0 },
      { key: "no_llm", flag: "--no-llm", kind: "bool", default: false },
    ],
    artifacts: ["results/tuner/**/*.json","results/tuner/**/*.csv"],
    quickstart_notes: [
      "Primary optimizer for multi-instrument calibration.",
      "Set --instruments and --output-dir to isolate each campaign.",
      "Track checkpoint JSON in results/tuner before validation.",
    ],
    recommended_next_command_ids: ["validation.config_validator"],
  },
  {
    id: "tuning.auto_tuner", title: "Auto Tuner",
    description: "Run single/multi instrument tuner for parameter optimization.",
    category: "Tuning", workflow_stage: "Tuning", mode: "python-file",
    script: "scripts/training/auto_tuner.py",
    args_schema: [
      { key: "csv", flag: "--csv", kind: "str", default: null },
      { key: "instrument", flag: "--instrument", kind: "str", default: null },
      { key: "data_dir", flag: "--data-dir", kind: "str", default: "data" },
      { key: "instruments", flag: "--instruments", kind: "list", default: [] },
      { key: "output_dir", flag: "--output-dir", kind: "str", default: "results/tuner" },
      { key: "n_iter", flag: "--n-iter", kind: "int", default: 100 },
      { key: "seed", flag: "--seed", kind: "int", default: 42 },
      { key: "resume", flag: "--resume", kind: "str", default: null },
      { key: "multi", flag: "--multi", kind: "bool", default: false },
      { key: "verbose", flag: "--verbose", kind: "bool", default: false },
    ],
    artifacts: ["results/tuner/**/*.json","results/tuner/**/*.csv"],
    quickstart_notes: [
      "Use for single-instrument or ad hoc experiments.",
      "Resume prior runs with --resume to avoid losing search state.",
      "Promote only after validator approval.",
    ],
    recommended_next_command_ids: ["validation.config_validator"],
  },
  {
    id: "validation.config_validator", title: "Config Validator",
    description: "Validate production or candidate params with quality gates.",
    category: "Validation & Promotion", workflow_stage: "Validation & Promotion", mode: "python-file",
    script: "src/config_layer/config_validator.py",
    args_schema: [
      { key: "subcommand", positional: true, positional_index: 0, kind: "choice", default: "validate-prod", choices: ["validate-prod","validate-params"] },
      { key: "data_dir", flag: "--data-dir", kind: "str", default: "data", applies_to: ["validate-prod","validate-params"] },
      { key: "version", flag: "--version", kind: "str", default: null, applies_to: ["validate-prod"] },
      { key: "output", flag: "--output", kind: "str", default: null, applies_to: ["validate-prod","validate-params"] },
      { key: "params", flag: "--params", kind: "str", default: null, applies_to: ["validate-params"] },
      { key: "config_id", flag: "--config-id", kind: "str", default: "cli_validation", applies_to: ["validate-params"] },
    ],
    artifacts: ["results/validation/**/*.json","results/validation/**/*.csv"],
    quickstart_notes: [
      "Gate candidate params with hard and soft quality checks.",
      "Use validate-prod for regression baselines, validate-params for candidates.",
      "Review warnings and hard_failures before promotion.",
    ],
    recommended_next_command_ids: ["promotion.manager","replay.unified"],
  },
  {
    id: "promotion.manager", title: "Promotion Manager",
    description: "List and promote validated configs into production registry.",
    category: "Validation & Promotion", workflow_stage: "Validation & Promotion", mode: "python-file",
    script: "src/governance/promotion_manager.py",
    args_schema: [
      { key: "subcommand", positional: true, positional_index: 0, kind: "choice", default: "list", choices: ["list","promote","from-report"] },
      { key: "checkpoint", flag: "--checkpoint", kind: "str", default: null, applies_to: ["promote"] },
      { key: "version", flag: "--version", kind: "str", default: null, applies_to: ["promote","from-report"] },
      { key: "data_dir", flag: "--data-dir", kind: "str", default: "data", applies_to: ["promote"] },
      { key: "instruments", flag: "--instruments", kind: "list", default: [], applies_to: ["promote"] },
      { key: "notes", flag: "--notes", kind: "str", default: "", applies_to: ["promote","from-report"] },
      { key: "no_llm", flag: "--no-llm", kind: "bool", default: false, applies_to: ["promote"] },
      { key: "report", flag: "--report", kind: "str", default: null, applies_to: ["from-report"] },
    ],
    artifacts: ["configs/production/*.json","configs/promotion_log.jsonl","results/validation/**/*.json"],
    quickstart_notes: [
      "Moves approved configs into configs/production with audit trail.",
      "Use list to inspect versions, promote/from-report for controlled release.",
      "Confirm promotion log and registry artifacts after run.",
    ],
    recommended_next_command_ids: ["baseline.capture","live.inout_runner"],
  },
  {
    id: "governance.orchestrator", title: "Governance Orchestrator",
    description: "Run reflection → meta-governor → shadow gate → promotion loop.",
    category: "Validation & Promotion", workflow_stage: "Validation & Promotion", mode: "python-file",
    script: "src/governance/orchestrator.py",
    args_schema: [
      { key: "collector_log", flag: "--collector-log", kind: "str", required: true, default: null },
      { key: "trades_csv", flag: "--trades-csv", kind: "str", required: true, default: null },
      { key: "baseline_pnl", flag: "--baseline-pnl", kind: "float", required: true, default: null },
      { key: "active_config", flag: "--active-config", kind: "str", default: "configs/production/v1_multi_2026_03.json" },
      { key: "bitnet_bin", flag: "--bitnet-bin", kind: "str", default: "./bitnet/bin/main" },
      { key: "model_path", flag: "--model-path", kind: "str", default: "./models/bitnet_b1_58_70b.gguf" },
      { key: "audit_log", flag: "--audit-log", kind: "str", default: "logs/governance_audit.jsonl" },
      { key: "prompt_path", flag: "--prompt-path", kind: "str", default: "logs/meta_prompt.txt" },
    ],
    artifacts: ["logs/governance_audit.jsonl","logs/meta_prompt.txt","configs/production/*.json"],
    quickstart_notes: [
      "Runs full governance loop: reflection to promotion decision.",
      "Provide collector log, trades CSV, and baseline PnL from same dataset.",
      "Use for governance-driven iteration, not first-pass tuning.",
    ],
    recommended_next_command_ids: ["promotion.manager"],
  },
  {
    id: "replay.unified", title: "Unified Replay Harness",
    description: "Compare v2 execution truth and BitNet gate modes on the same data.",
    category: "Replay & Backtest", workflow_stage: "Replay & Backtest", mode: "python-file",
    script: "src/runtime/unified_replay_harness.py",
    args_schema: [
      { key: "config", flag: "--config", kind: "str", default: "configs/production/v1_multi_2026_03.json" },
      { key: "data", flag: "--data", kind: "str", required: true, default: null },
      { key: "months", flag: "--months", kind: "int", default: null },
      { key: "output_dir", flag: "--output-dir", kind: "str", default: "results/alignment" },
    ],
    artifacts: ["results/alignment/**/*.json","results/alignment/**/*.csv"],
    quickstart_notes: [
      "Compares v2 execution truth and BitNet gate behaviors.",
      "Use before promotion to inspect alignment drift and gating impact.",
      "Review unified report JSON in results/alignment.",
    ],
    recommended_next_command_ids: ["backtest.v2","backtest.bitnet"],
  },
  {
    id: "backtest.v2", title: "Backtest v2",
    description: "Run CRT backtest harness with execution-truth outputs.",
    category: "Replay & Backtest", workflow_stage: "Replay & Backtest", mode: "python-file",
    script: "src/runtime/backtest_v2.py",
    args_schema: [
      { key: "csv", flag: "--csv", kind: "str", required: true, default: null },
      { key: "instrument", flag: "--instrument", kind: "str", default: "AUTO" },
      { key: "output", flag: "--output", kind: "str", default: "results" },
      { key: "htf", flag: "--htf", kind: "int", default: null },
      { key: "warmup", flag: "--warmup", kind: "int", default: null },
      { key: "capital", flag: "--capital", kind: "float", default: null },
      { key: "risk_pct", flag: "--risk-pct", kind: "float", default: null },
      { key: "spread", flag: "--spread", kind: "float", default: null },
      { key: "no_slip", flag: "--no-slip", kind: "bool", default: false },
      { key: "no_gap_reset", flag: "--no-gap-reset", kind: "bool", default: false },
      { key: "sweep_age", flag: "--sweep-age", kind: "int", default: 20 },
      { key: "decay", flag: "--decay", kind: "float", default: 0.10 },
      { key: "threshold", flag: "--threshold", kind: "float", default: 0.75 },
    ],
    artifacts: ["results/**/*.json","results/**/*_trades.csv","results/**/*_summary.csv"],
    quickstart_notes: [
      "Execution-truth backtest with detailed metrics and trade outputs.",
      "Use single CSV first, then directory/ALL mode for portfolio view.",
      "Check summary and trades outputs before validation.",
    ],
    recommended_next_command_ids: ["validation.config_validator"],
  },
  {
    id: "backtest.bitnet", title: "Backtest BitNet Gate",
    description: "Run row-level backtest with BitNet gate modes.",
    category: "Replay & Backtest", workflow_stage: "Replay & Backtest", mode: "python-file",
    script: "src/runtime/backtest_bitnet.py",
    args_schema: [
      { key: "config", flag: "--config", kind: "str", default: "configs/production/v1_multi_2026_03.json" },
      { key: "data", flag: "--data", kind: "str", default: "data.csv" },
      { key: "gate_mode", flag: "--gate-mode", kind: "choice", default: "hard_gate", choices: ["hard_gate","score_only_audit","force_accept_baseline"] },
      { key: "months", flag: "--months", kind: "int", default: null },
      { key: "output", flag: "--output", kind: "str", default: null },
    ],
    artifacts: ["logs/backtest_decisions_*.jsonl","results/**/*.csv","results/**/*.json"],
    quickstart_notes: [
      "Backtest with explicit BitNet gate modes for audit and diagnostics.",
      "Use score_only_audit to compare gate effect without hard blocking.",
      "Inspect decision logs in logs/backtest_decisions_*.jsonl.",
    ],
    recommended_next_command_ids: ["replay.unified"],
  },
  {
    id: "baseline.capture", title: "Baseline Capture",
    description: "Capture a baseline manifest for current repo/model/config state.",
    category: "Replay & Backtest", workflow_stage: "Replay & Backtest", mode: "python-file",
    script: "src/runtime/baseline_capture.py",
    args_schema: [
      { key: "label", flag: "--label", kind: "str", default: "phase0" },
      { key: "output_dir", flag: "--output-dir", kind: "str", default: "results/baseline" },
    ],
    artifacts: ["results/baseline/**/manifest.json"],
    quickstart_notes: [
      "Capture reproducible state snapshot before major workflow runs.",
      "Use a label tied to experiment phase for traceability.",
      "Store manifest path with run notes for rollback context.",
    ],
    recommended_next_command_ids: ["tuning.auto_tuner_multi"],
  },
  {
    id: "live.inout_runner", title: "INOUT Live Runner",
    description: "Run INOUT strategy loop in controlled dry/live mode.",
    category: "Live Runner", workflow_stage: "Live Runner", mode: "module",
    script: "inout.runner",
    args_schema: [
      { key: "cycles", flag: "--cycles", kind: "int", default: 0 },
      { key: "config", flag: "--config", kind: "str", default: null },
    ],
    artifacts: ["logs/inout_runner.log","logs/inout_heartbeat.jsonl","logs/inout_audit.jsonl"],
    quickstart_notes: [
      "Runs INOUT loop for controlled live/dry execution monitoring.",
      "Start with finite --cycles in new environments.",
      "Watch heartbeat and audit logs continuously during execution.",
    ],
    recommended_next_command_ids: ["replay.unified"],
  },
];

const WORKFLOW_STAGES = [
  "Data Prep", "Tuning", "Validation & Promotion", "Replay & Backtest", "Live Runner",
];

const SEED_RUNS = [
  { run_id: "a4f9c2b1c3804f70a221d99e", command_id: "tuning.auto_tuner_multi", status: "running", exit_code: null,
    started_at: "2026-05-13T09:21:54Z", ended_at: null,
    args: { instruments: ["EURUSD","AUDUSD","GBPUSD"], output_dir: "results/tuner", n_iter: 100, workers: 4 },
    cmdline: "python scripts/training/auto_tuner_multi.py --instruments EURUSD AUDUSD GBPUSD --output-dir results/tuner --n-iter 100 --workers 4",
    artifact_paths: ["results/tuner/checkpoint_multi.json", "results/tuner/summary.csv"],
    fields: [
      { label: "Current Iter", value: 47, format: "int", unit: "" },
      { label: "Iters Logged", value: 47, format: "int", unit: "" },
      { label: "Best Fitness", value: 0.6303, format: "float", unit: "" },
      { label: "Elapsed", value: 872, format: "duration", unit: "" },
    ],
    field_history: {
      "Current Iter":  [{t:0,v:5},{t:1,v:12},{t:2,v:19},{t:3,v:25},{t:4,v:31},{t:5,v:37},{t:6,v:42},{t:7,v:47}],
      "Best Fitness":  [{t:0,v:0.4810},{t:1,v:0.5202},{t:2,v:0.5587},{t:3,v:0.5894},{t:4,v:0.6011},{t:5,v:0.6184},{t:6,v:0.6253},{t:7,v:0.6303}],
    },
    timeline: [
      { ts: "2026-05-13T09:21:54Z", event: "created", note: "queued via web UI" },
      { ts: "2026-05-13T09:21:54Z", event: "started", note: "PID 48211" },
      { ts: "2026-05-13T09:22:39Z", event: "checkpoint", note: "iter 10 best=0.5587" },
      { ts: "2026-05-13T09:25:11Z", event: "checkpoint", note: "iter 25 best=0.6011" },
      { ts: "2026-05-13T09:33:42Z", event: "checkpoint", note: "iter 47 best=0.6303" },
    ],
    stdout: "[INFO] tuning.auto_tuner_multi started\n[INFO] instruments=EURUSD,AUDUSD,GBPUSD n_iter=100 workers=4\n[INFO] iter 47/100 best_score=0.6303 fitness=0.6125\n[INFO]   per-instrument: EURUSD=0.612 AUDUSD=0.598 GBPUSD=0.628\n[INFO] checkpoint written: results/tuner/checkpoint_multi.json\n",
    stderr: "",
  },
  { run_id: "3d11e0f4ab9249a78c01b8e2", command_id: "validation.config_validator", status: "succeeded", exit_code: 0,
    started_at: "2026-05-13T08:42:11Z", ended_at: "2026-05-13T08:48:03Z",
    args: { subcommand: "validate-params", params: "results/tuner/candidate_07.json", data_dir: "data", config_id: "candidate_07" },
    cmdline: "python src/config_layer/config_validator.py validate-params --data-dir data --params results/tuner/candidate_07.json --config-id candidate_07",
    artifact_paths: ["results/validation/report.json"],
    fields: [
      { label: "Gate Decision", value: "APPROVE", format: "str", unit: "" },
      { label: "Final Score", value: 0.6438, format: "float", unit: "" },
      { label: "Trades", value: 312, format: "int", unit: "" },
      { label: "Max DD", value: 18.4, format: "float", unit: "%" },
      { label: "Hard Failures", value: 0, format: "int", unit: "" },
    ],
    field_history: {
      "Final Score": [{t:0,v:0.6438}],
      "Trades":      [{t:0,v:312}],
      "Max DD":      [{t:0,v:18.4}],
    },
    timeline: [
      { ts: "2026-05-13T08:42:11Z", event: "created", note: "queued via web UI" },
      { ts: "2026-05-13T08:42:11Z", event: "started", note: "PID 48133" },
      { ts: "2026-05-13T08:44:02Z", event: "stage", note: "per-instrument backtests complete" },
      { ts: "2026-05-13T08:47:55Z", event: "stage", note: "soft gate warning: win_rate=52.1% < 55%" },
      { ts: "2026-05-13T08:48:03Z", event: "succeeded", note: "decision=APPROVE final_score=0.6438" },
    ],
    stdout: "[INFO] validation.config_validator validate-params\n[INFO] params=results/tuner/candidate_07.json\n[INFO] HARD gates: PASS · SOFT warnings: 1 (win_rate < 55%)\n[INFO] decision: APPROVE\n",
    stderr: "",
  },
  { run_id: "9b23a8c0e9dd4a1b86f2c742", command_id: "backtest.v2", status: "succeeded", exit_code: 0,
    started_at: "2026-05-13T07:14:09Z", ended_at: "2026-05-13T07:17:44Z",
    args: { csv: "data/EURUSD_M15.csv", instrument: "EURUSD", output: "results", threshold: 0.75 },
    cmdline: "python src/runtime/backtest_v2.py --csv data/EURUSD_M15.csv --instrument EURUSD --output results --threshold 0.75",
    artifact_paths: ["results/EURUSD_2024_summary.csv","results/EURUSD_2024_trades.csv","results/EURUSD_2024_summary.json"],
    fields: [
      { label: "Summary Size", value: 14823, format: "int", unit: "bytes" },
      { label: "Summary Updated", value: "2026-05-13T07:17:44Z", format: "timestamp", unit: "" },
      { label: "Trade Count", value: 312, format: "int", unit: "" },
      { label: "PnL (RR)", value: 47.18, format: "float", unit: "R" },
      { label: "Win Rate", value: 53.5, format: "float", unit: "%" },
      { label: "Max DD", value: 21.7, format: "float", unit: "%" },
    ],
    field_history: {
      "Trade Count": [{t:0,v:48},{t:1,v:104},{t:2,v:163},{t:3,v:221},{t:4,v:278},{t:5,v:312}],
      "PnL (RR)":    [{t:0,v:6.2},{t:1,v:14.8},{t:2,v:23.1},{t:3,v:31.4},{t:4,v:42.7},{t:5,v:47.18}],
      "Win Rate":    [{t:0,v:50.0},{t:1,v:51.9},{t:2,v:52.7},{t:3,v:53.2},{t:4,v:53.6},{t:5,v:53.5}],
      "Max DD":      [{t:0,v:8.4},{t:1,v:11.9},{t:2,v:16.2},{t:3,v:19.5},{t:4,v:21.7},{t:5,v:21.7}],
    },
    timeline: [
      { ts: "2026-05-13T07:14:09Z", event: "created", note: "queued via web UI" },
      { ts: "2026-05-13T07:14:09Z", event: "started", note: "PID 47921" },
      { ts: "2026-05-13T07:15:31Z", event: "drift", note: "FeatureMonitor Z=2.71 SOFT" },
      { ts: "2026-05-13T07:17:44Z", event: "succeeded", note: "312 trades · PnL=+47.18R" },
    ],
    stdout: "[INFO] backtest.v2 started\n[INFO] streaming data/EURUSD_M15.csv (35,040 bars)\n[WARN] FeatureMonitor drift Z=2.71 SOFT threshold\n[INFO] 312 trades WR=53.5% PnL(net)=+47.18R MaxDD=21.7%\n",
    stderr: "[WARN] 1 drift warning during run\n",
  },
  { run_id: "f7e1d9aa6c50450ab2ee0001", command_id: "backtest.bitnet", status: "failed", exit_code: 2,
    started_at: "2026-05-12T22:08:04Z", ended_at: "2026-05-12T22:08:31Z",
    args: { config: "configs/production/v1_multi_2026_03.json", data: "data.csv", gate_mode: "score_only_audit" },
    cmdline: "python src/runtime/backtest_bitnet.py --config configs/production/v1_multi_2026_03.json --data data.csv --gate-mode score_only_audit",
    artifact_paths: ["logs/backtest_decisions_20260512.jsonl"],
    fields: [],
    field_history: {},
    timeline: [
      { ts: "2026-05-12T22:08:04Z", event: "created", note: "queued via web UI" },
      { ts: "2026-05-12T22:08:04Z", event: "started", note: "PID 47012" },
      { ts: "2026-05-12T22:08:31Z", event: "failed", note: "FileNotFoundError: data.csv (exit=2)" },
    ],
    stdout: "[INFO] backtest.bitnet started gate_mode=score_only_audit\n[ERROR] data file not found: data.csv\n",
    stderr: "[ERROR] FileNotFoundError: data.csv\n",
  },
  { run_id: "2c8b4e30d8a14a83a55cae09", command_id: "live.inout_runner", status: "queued", exit_code: null,
    started_at: null, ended_at: null,
    args: { cycles: 10, config: "configs/production/v1_multi_2026_03.json" },
    cmdline: "python -m inout.runner --cycles 10 --config configs/production/v1_multi_2026_03.json",
    artifact_paths: [],
    fields: [],
    field_history: {},
    timeline: [
      { ts: "2026-05-13T09:30:00Z", event: "created", note: "queued via web UI" },
    ],
    stdout: "",
    stderr: "",
  },
];

const DASHBOARD_COMMAND_IDS = [
  "live.inout_runner","tuning.auto_tuner_multi","validation.config_validator","backtest.v2",
];

class MockApi {
  constructor() {
    this.runs = [...SEED_RUNS];
    this.subscribers = new Set();
  }
  subscribe(fn) { this.subscribers.add(fn); return () => this.subscribers.delete(fn); }
  emit() { this.subscribers.forEach(fn => fn()); }

  commands() { return { commands: COMMANDS, categories: [...new Set(COMMANDS.map(c => c.category))].sort(), workflow_stages: WORKFLOW_STAGES }; }
  listRuns(query = "") {
    if (!query) return { runs: this.runs };
    const q = query.toLowerCase();
    return { runs: this.runs.filter(r =>
      r.run_id.includes(q) || r.command_id.toLowerCase().includes(q) || JSON.stringify(r.args).toLowerCase().includes(q)
    )};
  }
  getRun(id) { return { run: this.runs.find(r => r.run_id === id) }; }
  logs(id) { const r = this.runs.find(x => x.run_id === id); return { run_id: id, logs: { stdout: r?.stdout || "", stderr: r?.stderr || "" } }; }
  artifacts(id) {
    const r = this.runs.find(x => x.run_id === id);
    return { run_id: id, artifacts: (r?.artifact_paths || []).map(p => ({ path: p, exists: r?.status !== "failed", size: r?.status === "succeeded" ? 14823 : null })) };
  }
  monitors(id) {
    const r = this.runs.find(x => x.run_id === id);
    return { run_id: id, command_id: r?.command_id, status: r?.status, fields: r?.fields || [] };
  }
  dashboard() {
    const out = DASHBOARD_COMMAND_IDS.map(cid => {
      const latest = this.runs.find(r => r.command_id === cid);
      return {
        command_id: cid,
        run_id: latest?.run_id || null,
        status: latest?.status || null,
        started_at: latest?.started_at || null,
        fields: latest?.fields || [],
      };
    });
    return { commands: out };
  }
  createRun(commandId, args, cmdline = null) {
    const run_id = "r" + Math.random().toString(36).slice(2, 12).padEnd(11, "0") + Date.now().toString(36).slice(-2);
    const cmd = COMMANDS.find(c => c.id === commandId);
    const nowIso = new Date().toISOString();
    const newRun = {
      run_id, command_id: commandId, status: "queued", exit_code: null,
      started_at: nowIso, ended_at: null,
      args,
      cmdline: cmdline || `python ${cmd?.mode === "module" ? "-m " : ""}${cmd?.script || commandId}`,
      artifact_paths: cmd?.artifacts || [], fields: [], field_history: {},
      timeline: [
        { ts: nowIso, event: "created", note: "queued via web UI" },
      ],
      stdout: `[INFO] ${commandId} started\n[INFO] args=${JSON.stringify(args)}\n`,
      stderr: "",
    };
    this.runs = [newRun, ...this.runs];
    this.emit();
    setTimeout(() => {
      newRun.status = "running";
      newRun.fields = [{ label: "Current Iter", value: 1, format: "int", unit: "" }];
      newRun.field_history = { "Current Iter": [{ t: 0, v: 1 }] };
      newRun.timeline.push({ ts: new Date().toISOString(), event: "started", note: `PID ${Math.floor(40000 + Math.random() * 9999)}` });
      this.emit();
    }, 800);
    setTimeout(() => {
      newRun.status = "succeeded"; newRun.exit_code = 0; newRun.ended_at = new Date().toISOString();
      newRun.stdout += "[INFO] complete\n";
      newRun.fields = [
        { label: "Current Iter", value: 100, format: "int", unit: "" },
        { label: "Best Fitness", value: 0.6280, format: "float", unit: "" },
        { label: "Elapsed", value: 1842, format: "duration", unit: "" },
      ];
      newRun.field_history = {
        "Current Iter": [{t:0,v:1},{t:1,v:25},{t:2,v:50},{t:3,v:75},{t:4,v:100}],
        "Best Fitness": [{t:0,v:0.41},{t:1,v:0.52},{t:2,v:0.58},{t:3,v:0.61},{t:4,v:0.628}],
      };
      newRun.timeline.push({ ts: newRun.ended_at, event: "succeeded", note: "exit=0" });
      this.emit();
    }, 3200);
    return { run: newRun };
  }
  stop(id) {
    const r = this.runs.find(x => x.run_id === id);
    if (r && (r.status === "running" || r.status === "queued")) {
      r.status = "stopped"; r.ended_at = new Date().toISOString();
      r.stderr += "[WARN] stopped via API\n";
      r.timeline = r.timeline || [];
      r.timeline.push({ ts: r.ended_at, event: "stopped", note: "stopped via API" });
    }
    this.emit();
    return { run: r };
  }
}

window.mockApi = new MockApi();

// Mock filesystem catalog — mirrors what would come from a `/catalog` endpoint
// listing data/ and configs/production/. Used by ComboBox to restrict inputs.
window.CATALOG = {
  data_csv: [
    "data/AUDUSD_M15.csv",
    "data/BTCUSDT_M15.csv",
    "data/ETHUSDT_M15.csv",
    "data/EURCAD_M15.csv",
    "data/EURUSD_M15.csv",
    "data/GBPUSD_M15.csv",
    "data/USDJPY_M15.csv",
    "data/XAUUSD_M15.csv",
  ],
  data_all: [
    "data/AUDUSD_M15.csv",
    "data/BTCUSDT_M15.csv",
    "data/ETHUSDT_M15.csv",
    "data/EURCAD_M15.csv",
    "data/EURUSD_M15.csv",
    "data/GBPUSD_M15.csv",
    "data/USDJPY_M15.csv",
    "data/XAUUSD_M15.csv",
    "data/training.json",
  ],
  instruments: ["AUDUSD", "BTCUSDT", "ETHUSDT", "EURCAD", "EURUSD", "GBPUSD", "USDJPY", "XAUUSD"],
  prod_configs: [
    "configs/production/v1_multi_2026_03.json",
    "configs/production/v1_multi_2026_03_force_accept.json",
    "configs/production/v2_multi_2026_04.json",
    "configs/production/v2_test.json",
    "configs/production/regime_map.json",
  ],
  prod_versions: [
    "v1_multi_2026_03",
    "v1_multi_2026_03_force_accept",
    "v2_multi_2026_04",
    "v2_test",
  ],
  gate_modes: ["hard_gate", "score_only_audit", "force_accept_baseline"],
};
