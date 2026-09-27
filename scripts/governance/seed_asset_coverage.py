"""PRIMARY seed for asset_coverage_v1 (STORY-12.3).

Hand-curated rows RTC-001..RTC-008 from
docs/implementation_plan/run-trace-coverage-schema-2026-09-17.md section 5.B.
Writes generated data/asset_coverage.jsonl. Do not hand-edit that file.

    python scripts/governance/seed_asset_coverage.py
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "asset_coverage.jsonl"
TODAY = "2026-09-18"

ROWS = [
    {
        "id": "RTC-001",
        "module": "runtime.layer_trace",
        "writer_symbol": "_write",
        "package": "runtime",
        "rail": "backtest",
        "family": "layer_trace",
        "path_pattern": "results/layer_trace/*_layer_trace.jsonl",
        "format": "jsonl",
        "grain": "bar_layer",
        "run_key": {"field": "run_id", "id_kind": "run_canonical", "clock_basis": "utc"},
        "bar_key": {"field": "bar_ts", "basis": "bar_open_ts", "clock_basis": "broker_local"},
        "trace_key": {"field": "trace_id"},
        "layer_ns": "walk",
        "layers": ["L0", "L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8", "L9"],
        "join_status": "JOINABLE_RECORDED",
        "gaps": ["MULTI_RUN_FILE", "NO_EMIT_SITE", "SILENT_CONDITIONAL"],
        "findings": ["F-058", "F-101"],
        "evidence": [{"path": "src/runtime/layer_trace.py", "line": 0, "symbol": "_write"}],
    },
    {
        "id": "RTC-002",
        "module": "runtime.backtest_v2",
        "writer_symbol": "_write_events",
        "package": "runtime",
        "rail": "backtest",
        "family": "events",
        "path_pattern": "results/**/*_events.jsonl",
        "format": "jsonl",
        "grain": "event",
        "run_key": {"field": "run_id", "id_kind": "run_content", "clock_basis": "utc"},
        "bar_key": {"field": "timestamp", "basis": "bar_open_ts", "clock_basis": "broker_local"},
        "trace_key": None,
        "layer_ns": "walk",
        "layers": [],
        "join_status": "JOINABLE_DERIVED",
        "gaps": ["INDEX_OFFSET"],
        "findings": ["F-101"],
        "evidence": [{"path": "src/runtime/backtest_v2.py", "line": 0, "symbol": "_write_events"}],
    },
    {
        "id": "RTC-003",
        "module": "runtime.backtest_v2",
        "writer_symbol": "_write_trades",
        "package": "runtime",
        "rail": "backtest",
        "family": "trades",
        "path_pattern": "results/**/*_trades.csv",
        "format": "csv",
        "grain": "trade",
        "run_key": {"field": "run_id", "id_kind": "run_content", "clock_basis": "utc"},
        "bar_key": {"field": "opened_at", "basis": "bar_open_ts", "clock_basis": "broker_local"},
        "trace_key": None,
        "layer_ns": "walk",
        "layers": [],
        "join_status": "JOINABLE_DERIVED",
        "gaps": ["INDEX_OFFSET"],
        "findings": ["F-101"],
        "evidence": [{"path": "src/runtime/backtest_v2.py", "line": 0, "symbol": "_write_trades"}],
    },
    {
        "id": "RTC-004",
        "module": "runtime.backtest_v2",
        "writer_symbol": "_write_summary",
        "package": "runtime",
        "rail": "backtest",
        "family": "summary",
        "path_pattern": "results/**/*_summary.json",
        "format": "json",
        "grain": "run",
        "run_key": {"field": "run_id", "id_kind": "run_content", "clock_basis": "utc"},
        "bar_key": None,
        "trace_key": None,
        "layer_ns": "walk",
        "layers": [],
        "join_status": "RUN_ONLY",
        "gaps": [],
        "findings": ["F-101"],
        "evidence": [{"path": "src/runtime/backtest_v2.py", "line": 0, "symbol": "_write_summary"}],
    },
    {
        "id": "RTC-005",
        "module": "runtime.backtest_v2",
        "writer_symbol": "__init__",
        "package": "runtime",
        "rail": "backtest",
        "family": "results_folder",
        "path_pattern": "results/run_*",
        "format": "json",
        "grain": "run",
        "run_key": {"field": "folder_name", "id_kind": "run_folder", "clock_basis": "naive_local"},
        "bar_key": None,
        "trace_key": None,
        "layer_ns": "walk",
        "layers": [],
        "join_status": "RUN_ONLY",
        "gaps": ["LOCAL_CLOCK_ID"],
        "findings": ["F-101"],
        "evidence": [{"path": "src/runtime/backtest_v2.py", "line": 0, "symbol": "ReportWriter"}],
    },
    {
        "id": "RTC-006",
        "module": "runtime.live_rail_orchestrator",
        "writer_symbol": "_audit",
        "package": "runtime",
        "rail": "paper_live",
        "family": "rail_audit",
        "path_pattern": "results/**/audit.jsonl",
        "format": "jsonl",
        "grain": "event",
        "run_key": None,
        "bar_key": {"field": "ts", "basis": "wall_clock", "clock_basis": "wall_utc"},
        "trace_key": None,
        "layer_ns": "walk",
        "layers": [],
        "join_status": "UNJOINABLE",
        "gaps": ["NO_RUN_ID", "NO_BAR_TS", "WALL_CLOCK_NOT_BAR_TS"],
        "findings": ["F-103"],
        "evidence": [{"path": "src/runtime/live_rail_orchestrator.py", "line": 0, "symbol": "_audit"}],
    },
    {
        "id": "RTC-007",
        "module": "control_plane.jobs",
        "writer_symbol": "create_run",
        "package": "control_plane",
        "rail": "control_plane",
        "family": "job_state",
        "path_pattern": "logs/jobs/**/*.json",
        "format": "json",
        "grain": "job",
        "run_key": {"field": "run_id", "id_kind": "job", "clock_basis": "utc"},
        "bar_key": None,
        "trace_key": None,
        "layer_ns": None,
        "layers": [],
        "join_status": "RUN_ONLY",
        "gaps": [],
        "findings": ["F-101"],
        "evidence": [{"path": "src/control_plane/jobs.py", "line": 0, "symbol": "create_run"}],
    },
    {
        "id": "RTC-008",
        "module": "interpreters.contract",
        "writer_symbol": "InterpreterReading",
        "package": "interpreters",
        "rail": "research",
        "family": "interpreter_reading",
        "path_pattern": "",
        "format": "json",
        "grain": "bar",
        "run_key": None,
        "bar_key": {"field": "observation_time", "basis": "bar_open_ts", "clock_basis": "broker_local"},
        "trace_key": {"field": "trace_id"},
        "layer_ns": "walk",
        "layers": [],
        "join_status": "JOINABLE_DERIVED",
        "gaps": ["HOMONYM"],
        "findings": [],
        "evidence": [{"path": "src/interpreters/contract.py", "line": 0, "symbol": "InterpreterReading"}],
    },
]


def _fill_lines(rows: list[dict]) -> None:
    import ast
    for row in rows:
        ev = row["evidence"][0]
        path = ROOT / ev["path"]
        tree = ast.parse(path.read_text(encoding="utf-8"))
        want = ev["symbol"]
        line = 1
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == want:
                line = node.lineno
                break
        ev["line"] = line
        row["last_validated"] = TODAY


def main() -> None:
    rows = json.loads(json.dumps(ROWS))
    _fill_lines(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    text = chr(10).join(json.dumps(r, ensure_ascii=False) for r in rows) + chr(10)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {len(rows)} -> {OUT}")


if __name__ == "__main__":
    main()
