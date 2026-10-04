from __future__ import annotations

import time
from pathlib import Path

from src.control_plane.jobs import JobManager
from src.control_plane.cp_types import ArgSpec, CommandSpec


def _wait_for_terminal(manager: JobManager, run_id: str, timeout: float = 10.0) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        run = manager.get_run(run_id)
        if run and run.status in {"succeeded", "failed", "stopped"}:
            return run.status
        time.sleep(0.1)
    raise TimeoutError(f"Run did not finish in {timeout}s: {run_id}")


def test_job_manager_executes_and_collects_artifacts(tmp_path: Path) -> None:
    script_path = tmp_path / "emit_artifact.py"
    artifact = tmp_path / "artifact.txt"
    script_path.write_text(
        "from pathlib import Path\n"
        f"Path(r'{artifact}').write_text('ok', encoding='utf-8')\n"
        "print('done')\n",
        encoding="utf-8",
    )
    spec = CommandSpec(
        id="test.emit",
        title="Emit",
        description="test",
        category="Test",
        mode="python-file",
        script=str(script_path),
        args_schema=(),
        artifacts=("artifact.txt",),
    )
    manager = JobManager(specs=(spec,), state_dir=tmp_path / "state", repo_root=tmp_path)
    run = manager.create_run("test.emit", {})
    status = _wait_for_terminal(manager, run.run_id)
    assert status == "succeeded"
    snap = manager.snapshot(manager.get_run(run.run_id))
    assert snap["exit_code"] == 0
    assert Path(snap["log_paths"]["stdout"]).exists()
    assert any(str(artifact) == path for path in snap["artifact_paths"])


def test_job_manager_persists_run_records(tmp_path: Path) -> None:
    script_path = tmp_path / "noop.py"
    script_path.write_text("print('ok')\n", encoding="utf-8")
    spec = CommandSpec(
        id="test.noop",
        title="Noop",
        description="test",
        category="Test",
        mode="python-file",
        script=str(script_path),
    )
    state_dir = tmp_path / "state"
    manager = JobManager(specs=(spec,), state_dir=state_dir, repo_root=tmp_path)
    run = manager.create_run("test.noop", {})
    _wait_for_terminal(manager, run.run_id)

    restored = JobManager(specs=(spec,), state_dir=state_dir, repo_root=tmp_path)
    loaded = restored.get_run(run.run_id)
    assert loaded is not None
    assert loaded.command_id == "test.noop"

