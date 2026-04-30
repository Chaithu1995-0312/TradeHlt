from __future__ import annotations

from dataclasses import replace
import json
import shlex
import sys
from pathlib import Path
from typing import Any

from src.control_plane.types import ArgSpec, CommandSpec

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_STAGE_ORDER: tuple[str, ...] = (
    "Data Prep",
    "Tuning",
    "Validation & Promotion",
    "Replay & Backtest",
    "Live Runner",
)

_WORKFLOW_STAGE_BY_COMMAND: dict[str, str] = {
    "data.prepare_data": "Data Prep",
    "data.unified_data_builder": "Data Prep",
    "tuning.auto_tuner_multi": "Tuning",
    "tuning.auto_tuner": "Tuning",
    "validation.config_validator": "Validation & Promotion",
    "promotion.manager": "Validation & Promotion",
    "governance.orchestrator": "Validation & Promotion",
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
    "tuning.auto_tuner_multi": ("validation.config_validator",),
    "tuning.auto_tuner": ("validation.config_validator",),
    "validation.config_validator": ("promotion.manager", "replay.unified"),
    "promotion.manager": ("baseline.capture", "live.inout_runner"),
    "governance.orchestrator": ("promotion.manager",),
    "replay.unified": ("backtest.v2", "backtest.bitnet"),
    "backtest.v2": ("validation.config_validator",),
    "backtest.bitnet": ("replay.unified",),
    "baseline.capture": ("tuning.auto_tuner_multi",),
    "live.inout_runner": ("replay.unified",),
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
                ArgSpec("files", flag="--files", kind="list", default=[]),
                ArgSpec("instrument", flag="--instrument", kind="str", default="UNKNOWN"),
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
                ArgSpec("csv", flag="--csv", kind="str", default=None),
                ArgSpec("instrument", flag="--instrument", kind="str", default=None),
                ArgSpec("data_dir", flag="--data-dir", kind="str", default="data"),
                ArgSpec("instruments", flag="--instruments", kind="list", default=[]),
                ArgSpec("output_dir", flag="--output-dir", kind="str", default="results/tuner"),
                ArgSpec("n_iter", flag="--n-iter", kind="int", default=100),
                ArgSpec("seed", flag="--seed", kind="int", default=42),
                ArgSpec("workers", flag="--workers", kind="int", default=4),
                ArgSpec("train_split", flag="--train-split", kind="float", default=1.0),
                ArgSpec("no_llm", flag="--no-llm", kind="bool", default=False),
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
                ArgSpec("csv", flag="--csv", kind="str", default=None),
                ArgSpec("instrument", flag="--instrument", kind="str", default=None),
                ArgSpec("data_dir", flag="--data-dir", kind="str", default="data"),
                ArgSpec("instruments", flag="--instruments", kind="list", default=[]),
                ArgSpec("output_dir", flag="--output-dir", kind="str", default="results/tuner"),
                ArgSpec("n_iter", flag="--n-iter", kind="int", default=100),
                ArgSpec("seed", flag="--seed", kind="int", default=42),
                ArgSpec("resume", flag="--resume", kind="str", default=None),
                ArgSpec("multi", flag="--multi", kind="bool", default=False),
                ArgSpec("verbose", flag="--verbose", kind="bool", default=False),
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
                ArgSpec("output", flag="--output", kind="str", default=None, applies_to=("validate-prod", "validate-params")),
                ArgSpec("params", flag="--params", kind="str", default=None, applies_to=("validate-params",)),
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
                ArgSpec("checkpoint", flag="--checkpoint", kind="str", default=None, applies_to=("promote",)),
                ArgSpec("version", flag="--version", kind="str", default=None, applies_to=("promote", "from-report")),
                ArgSpec("data_dir", flag="--data-dir", kind="str", default="data", applies_to=("promote",)),
                ArgSpec("instruments", flag="--instruments", kind="list", default=[], applies_to=("promote",)),
                ArgSpec("notes", flag="--notes", kind="str", default="", applies_to=("promote", "from-report")),
                ArgSpec("no_llm", flag="--no-llm", kind="bool", default=False, applies_to=("promote",)),
                ArgSpec("report", flag="--report", kind="str", default=None, applies_to=("from-report",)),
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
                ArgSpec("collector_log", flag="--collector-log", kind="str", required=True),
                ArgSpec("trades_csv", flag="--trades-csv", kind="str", required=True),
                ArgSpec("baseline_pnl", flag="--baseline-pnl", kind="float", required=True),
                ArgSpec("active_config", flag="--active-config", kind="str", default="configs/production/v1_multi_2026_03.json"),
                ArgSpec("bitnet_bin", flag="--bitnet-bin", kind="str", default="./bitnet/bin/main"),
                ArgSpec("model_path", flag="--model-path", kind="str", default="./models/bitnet_b1_58_70b.gguf"),
                ArgSpec("audit_log", flag="--audit-log", kind="str", default="logs/governance_audit.jsonl"),
                ArgSpec("prompt_path", flag="--prompt-path", kind="str", default="logs/meta_prompt.txt"),
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
                ArgSpec("config", flag="--config", kind="str", default="configs/production/v1_multi_2026_03.json"),
                ArgSpec("data", flag="--data", kind="str", required=True),
                ArgSpec("months", flag="--months", kind="int", default=None),
                ArgSpec("output_dir", flag="--output-dir", kind="str", default="results/alignment"),
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
                ArgSpec("csv", flag="--csv", kind="str", required=True),
                ArgSpec("instrument", flag="--instrument", kind="str", default="AUTO"),
                ArgSpec("output", flag="--output", kind="str", default="results"),
                ArgSpec("htf", flag="--htf", kind="int", default=None),
                ArgSpec("warmup", flag="--warmup", kind="int", default=None),
                ArgSpec("capital", flag="--capital", kind="float", default=None),
                ArgSpec("risk_pct", flag="--risk-pct", kind="float", default=None),
                ArgSpec("spread", flag="--spread", kind="float", default=None),
                ArgSpec("no_slip", flag="--no-slip", kind="bool", default=False),
                ArgSpec("no_gap_reset", flag="--no-gap-reset", kind="bool", default=False),
                ArgSpec("sweep_age", flag="--sweep-age", kind="int", default=20),
                ArgSpec("decay", flag="--decay", kind="float", default=0.10),
                ArgSpec("threshold", flag="--threshold", kind="float", default=0.75),
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
                ArgSpec("config", flag="--config", kind="str", default="configs/production/v1_multi_2026_03.json"),
                ArgSpec("data", flag="--data", kind="str", default="data.csv"),
                ArgSpec("gate_mode", flag="--gate-mode", kind="choice", default="hard_gate", choices=("hard_gate", "score_only_audit", "force_accept_baseline")),
                ArgSpec("months", flag="--months", kind="int", default=None),
                ArgSpec("output", flag="--output", kind="str", default=None),
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
                ArgSpec("cycles", flag="--cycles", kind="int", default=0),
                ArgSpec("config", flag="--config", kind="str", default=None),
            ),
            artifacts=("logs/inout_runner.log", "logs/inout_heartbeat.jsonl", "logs/inout_audit.jsonl"),
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
    if kind == "list":
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
        if arg.kind == "list":
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
        preview = shell_preview(render_command(spec, seed_args))
        artifacts = ", ".join(spec.artifacts) if spec.artifacts else "-"
        suggested = ", ".join(spec.recommended_next_command_ids) if spec.recommended_next_command_ids else "-"
        lines.append(f"| `{spec.id}` | {spec.category} | `{preview}` | `{artifacts}` | `{suggested}` |")
    return "\n".join(lines) + "\n"


def dump_specs_json(specs: tuple[CommandSpec, ...] | None = None) -> str:
    payload = [command_spec_to_json(spec) for spec in (specs or core_command_specs())]
    return json.dumps(payload, indent=2)
