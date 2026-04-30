from __future__ import annotations

import dataclasses
import glob
import json
import os
import subprocess
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.control_plane.monitors import (
    MonitorFieldSpec,
    default_monitors_path,
    extract_fields,
    load_monitor_specs,
)
from src.control_plane.registry import REPO_ROOT, build_command_line, command_map, core_command_specs, merge_command_args
from src.control_plane.types import CommandSpec, RunRecord


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobManager:
    def __init__(
        self,
        specs: tuple[CommandSpec, ...] | None = None,
        state_dir: Path | None = None,
        repo_root: Path | None = None,
        monitors_path: Path | None = None,
    ) -> None:
        self._specs = specs or core_command_specs()
        self._spec_by_id = command_map(self._specs)
        self._repo_root = (repo_root or REPO_ROOT).resolve()
        self._state_dir = (state_dir or (self._repo_root / "logs" / "control_plane")).resolve()
        self._runs_dir = self._state_dir / "runs"
        self._runs_dir.mkdir(parents=True, exist_ok=True)
        self._history_dir = self._state_dir / "monitor_history"
        self._history_dir.mkdir(parents=True, exist_ok=True)
        self._monitors_path = monitors_path or default_monitors_path(self._repo_root)
        try:
            self._monitor_specs: dict[str, tuple[MonitorFieldSpec, ...]] = load_monitor_specs(self._monitors_path)
        except Exception:
            self._monitor_specs = {}
        self._lock = threading.Lock()
        self._records: dict[str, RunRecord] = {}
        self._processes: dict[str, subprocess.Popen[str]] = {}
        self._load_existing()

    def _run_file(self, run_id: str) -> Path:
        return self._runs_dir / f"{run_id}.json"

    def _load_existing(self) -> None:
        known = {f.name for f in dataclasses.fields(RunRecord)}
        for run_file in sorted(self._runs_dir.glob("*.json")):
            try:
                payload = json.loads(run_file.read_text(encoding="utf-8"))
                filtered = {k: v for k, v in payload.items() if k in known}
                record = RunRecord(**filtered)
                self._records[record.run_id] = record
            except Exception:
                continue

    def _persist(self, record: RunRecord) -> None:
        payload = {
            "run_id": record.run_id,
            "command_id": record.command_id,
            "args": record.args,
            "command_line": record.command_line,
            "status": record.status,
            "exit_code": record.exit_code,
            "started_at": record.started_at,
            "ended_at": record.ended_at,
            "log_paths": record.log_paths,
            "artifact_paths": record.artifact_paths,
            "pid": record.pid,
            "error": record.error,
            "monitor_snapshot": record.monitor_snapshot,
        }
        self._run_file(record.run_id).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def list_commands(self) -> tuple[CommandSpec, ...]:
        return self._specs

    def list_runs(self, query: str = "") -> list[RunRecord]:
        with self._lock:
            runs = list(self._records.values())
        runs.sort(key=lambda r: r.started_at or "", reverse=True)
        if not query:
            return runs
        needle = query.lower().strip()
        if not needle:
            return runs
        return [
            r for r in runs
            if needle in r.run_id.lower() or needle in r.command_id.lower() or needle in json.dumps(r.args).lower()
        ]

    def get_run(self, run_id: str) -> RunRecord | None:
        with self._lock:
            return self._records.get(run_id)

    def read_logs(self, run_id: str) -> dict[str, str]:
        record = self.get_run(run_id)
        if not record:
            raise KeyError(f"Run not found: {run_id}")
        out: dict[str, str] = {}
        for key, path in record.log_paths.items():
            p = Path(path)
            out[key] = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
        return out

    def create_run(self, command_id: str, user_args: dict[str, Any] | None = None) -> RunRecord:
        spec = self._spec_by_id.get(command_id)
        if spec is None:
            raise KeyError(f"Unknown command: {command_id}")

        merged_args = merge_command_args(spec, user_args or {})
        command_line = build_command_line(spec, merged_args)
        run_id = uuid.uuid4().hex
        run_dir = self._state_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = run_dir / "stdout.log"
        stderr_path = run_dir / "stderr.log"
        combined_path = run_dir / "combined.log"

        record = RunRecord(
            run_id=run_id,
            command_id=command_id,
            args=merged_args,
            command_line=command_line,
            status="queued",
            started_at=_now_iso(),
            log_paths={
                "stdout": str(stdout_path),
                "stderr": str(stderr_path),
                "combined": str(combined_path),
            },
            artifact_paths=[],
        )
        with self._lock:
            self._records[run_id] = record
            self._persist(record)
        worker = threading.Thread(target=self._execute_run, args=(record.run_id,), daemon=True)
        worker.start()
        return record

    def stop_run(self, run_id: str) -> RunRecord:
        with self._lock:
            record = self._records.get(run_id)
            if record is None:
                raise KeyError(f"Run not found: {run_id}")
            proc = self._processes.get(run_id)
        if proc is None:
            return record
        if proc.poll() is None:
            proc.terminate()
            with self._lock:
                record = self._records[run_id]
                record.status = "stopped"
                record.ended_at = _now_iso()
                self._persist(record)
        return self.get_run(run_id) or record

    def _pump(self, stream: Any, targets: list[Path]) -> None:
        with stream:
            for line in iter(stream.readline, ""):
                for path in targets:
                    with path.open("a", encoding="utf-8") as handle:
                        handle.write(line)

    def _discover_artifacts(self, spec: CommandSpec, args: dict[str, Any]) -> list[str]:
        found: set[str] = set()
        for pattern in spec.artifacts:
            full = str((self._repo_root / pattern).resolve())
            for match in glob.glob(full, recursive=True):
                p = Path(match)
                if p.exists():
                    found.add(str(p.resolve()))

        output_like = ("output", "output_dir", "out", "report", "checkpoint")
        for key in output_like:
            value = args.get(key)
            if not value:
                continue
            p = (self._repo_root / str(value)).resolve()
            if p.is_file():
                found.add(str(p))
            elif p.is_dir():
                for child in p.rglob("*"):
                    if child.is_file():
                        found.add(str(child.resolve()))
        return sorted(found)

    def _execute_run(self, run_id: str) -> None:
        with self._lock:
            record = self._records[run_id]
            record.status = "running"
            self._persist(record)

        stdout_path = Path(record.log_paths["stdout"])
        stderr_path = Path(record.log_paths["stderr"])
        combined_path = Path(record.log_paths["combined"])
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        combined_path.write_text("", encoding="utf-8")

        spec = self._spec_by_id[record.command_id]
        try:
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            proc = subprocess.Popen(
                record.command_line,
                cwd=str(self._repo_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )
            with self._lock:
                self._processes[run_id] = proc
                record.pid = proc.pid
                self._persist(record)

            stdout_thread = threading.Thread(
                target=self._pump, args=(proc.stdout, [stdout_path, combined_path]), daemon=True
            )
            stderr_thread = threading.Thread(
                target=self._pump, args=(proc.stderr, [stderr_path, combined_path]), daemon=True
            )
            stdout_thread.start()
            stderr_thread.start()

            exit_code = proc.wait()
            stdout_thread.join(timeout=2.0)
            stderr_thread.join(timeout=2.0)

            with self._lock:
                record = self._records[run_id]
                record.exit_code = exit_code
                if record.status == "stopped":
                    pass
                elif exit_code in spec.success_exit_codes:
                    record.status = "succeeded"
                else:
                    record.status = "failed"
                record.ended_at = _now_iso()
                record.artifact_paths = self._discover_artifacts(spec, record.args)
                # --- monitor snapshot + rolling history (must not affect run status) ---
                try:
                    mon_specs = self._monitor_specs.get(record.command_id, ())
                    if mon_specs:
                        final = extract_fields(
                            mon_specs, record.args, record.run_id,
                            self._repo_root, self._state_dir,
                        )
                        record.monitor_snapshot = final
                        hist_path = self._history_dir / f"{record.command_id}.jsonl"
                        with hist_path.open("a", encoding="utf-8") as fh:
                            fh.write(json.dumps({
                                "run_id": record.run_id,
                                "command_id": record.command_id,
                                "status": record.status,
                                "started_at": record.started_at,
                                "ended_at": record.ended_at,
                                "fields": final,
                            }) + "\n")
                except Exception as mon_exc:
                    with combined_path.open("a", encoding="utf-8") as handle:
                        handle.write(f"\n[monitor-error] {mon_exc}\n")
                # ---
                self._processes.pop(run_id, None)
                self._persist(record)
        except Exception as exc:
            with self._lock:
                record = self._records[run_id]
                record.status = "failed"
                record.error = str(exc)
                record.ended_at = _now_iso()
                self._processes.pop(run_id, None)
                self._persist(record)
            with combined_path.open("a", encoding="utf-8") as handle:
                handle.write(f"\n[control-plane-error] {exc}\n")

    def snapshot(self, record: RunRecord) -> dict[str, Any]:
        return {
            "run_id": record.run_id,
            "command_id": record.command_id,
            "args": record.args,
            "command_line": record.command_line,
            "status": record.status,
            "exit_code": record.exit_code,
            "started_at": record.started_at,
            "ended_at": record.ended_at,
            "log_paths": record.log_paths,
            "artifact_paths": record.artifact_paths,
            "pid": record.pid,
            "error": record.error,
            "monitor_snapshot": record.monitor_snapshot,
        }

    # ------------------------------------------------------------------
    # Monitor helpers
    # ------------------------------------------------------------------

    def live_monitors(self, run_id: str) -> list[dict[str, Any]]:
        """Return monitor field values for a run.

        For terminal runs (succeeded/failed/stopped), returns the stored
        final snapshot so we don't re-read files that may have rotated.
        For active runs (running/queued), recomputes from live sources.
        """
        record = self.get_run(run_id)
        if record is None:
            raise KeyError(f"Run not found: {run_id}")
        specs = self._monitor_specs.get(record.command_id, ())
        if not specs:
            return []
        if record.status in ("succeeded", "failed", "stopped") and record.monitor_snapshot:
            return record.monitor_snapshot
        return extract_fields(
            specs, record.args, record.run_id, self._repo_root, self._state_dir
        )

    def dashboard_snapshot(self) -> list[dict[str, Any]]:
        """For each monitored command, return its most recent run's field values.

        Returns list of {command_id, run_id, status, started_at, fields}.
        Commands with no runs yet are included with empty fields.
        """
        # Find the most recent run per command_id (list_runs is already sorted desc)
        per_cmd: dict[str, RunRecord] = {}
        for rec in self.list_runs():
            if rec.command_id in self._monitor_specs and rec.command_id not in per_cmd:
                per_cmd[rec.command_id] = rec

        out: list[dict[str, Any]] = []
        for cmd_id, specs in self._monitor_specs.items():
            rec = per_cmd.get(cmd_id)
            if rec is None:
                out.append({
                    "command_id": cmd_id,
                    "run_id": None,
                    "status": None,
                    "started_at": None,
                    "fields": [],
                })
                continue
            if rec.status in ("succeeded", "failed", "stopped") and rec.monitor_snapshot:
                fields = rec.monitor_snapshot
            else:
                try:
                    fields = extract_fields(
                        specs, rec.args, rec.run_id, self._repo_root, self._state_dir
                    )
                except Exception:
                    fields = []
            out.append({
                "command_id": cmd_id,
                "run_id": rec.run_id,
                "status": rec.status,
                "started_at": rec.started_at,
                "fields": fields,
            })
        return out

    def monitor_history(self, command_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Return the last *limit* history entries for a command from its JSONL file."""
        path = self._history_dir / f"{command_id}.jsonl"
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8").splitlines()
        out: list[dict[str, Any]] = []
        for raw in lines[-limit:]:
            raw = raw.strip()
            if not raw:
                continue
            try:
                out.append(json.loads(raw))
            except Exception:
                continue
        return out
