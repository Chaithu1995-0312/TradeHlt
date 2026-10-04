from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

CommandMode = Literal["python-file", "module"]
RunStatus = Literal["queued", "running", "succeeded", "failed", "stopped"]
ArgKind = Literal["str", "int", "float", "bool", "list", "choice", "file", "file-multi", "date"]


@dataclass(frozen=True)
class ArgSpec:
    key: str
    flag: str | None = None
    kind: ArgKind = "str"
    required: bool = False
    default: Any = None
    choices: tuple[str, ...] = ()
    help: str = ""
    positional: bool = False
    positional_index: int = 0
    applies_to: tuple[str, ...] = ()
    min_val: float | None = None
    max_val: float | None = None
    file_glob: str = ""
    auto_default: str = ""   # "date_version" → JS pre-fills v5_auto_YYYY_MM
                              # "compressed_from_logs" → JS derives from sibling logs field


@dataclass(frozen=True)
class CommandSpec:
    id: str
    title: str
    description: str
    category: str
    mode: CommandMode
    script: str
    args_schema: tuple[ArgSpec, ...] = ()
    artifacts: tuple[str, ...] = ()
    success_exit_codes: tuple[int, ...] = (0,)
    workflow_stage: str = ""
    quickstart_notes: tuple[str, ...] = ()
    recommended_next_command_ids: tuple[str, ...] = ()


@dataclass
class RunRecord:
    run_id: str
    command_id: str
    args: dict[str, Any]
    command_line: list[str]
    status: RunStatus
    exit_code: int | None = None
    started_at: str | None = None
    ended_at: str | None = None
    log_paths: dict[str, str] = field(default_factory=dict)
    artifact_paths: list[str] = field(default_factory=list)
    pid: int | None = None
    error: str | None = None
    monitor_snapshot: list[dict[str, Any]] = field(default_factory=list)
