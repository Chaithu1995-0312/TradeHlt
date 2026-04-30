from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

from src.control_plane.jobs import JobManager
from src.control_plane.server import ControlPlaneServer, find_free_port
from src.control_plane.types import ArgSpec, CommandSpec


def _get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _post_json(url: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def test_api_run_lifecycle_and_artifacts(tmp_path: Path) -> None:
    script_path = tmp_path / "emit.py"
    artifact = tmp_path / "api_artifact.txt"
    script_path.write_text(
        "from pathlib import Path\n"
        f"Path(r'{artifact}').write_text('artifact', encoding='utf-8')\n"
        "print('api ok')\n",
        encoding="utf-8",
    )
    spec = CommandSpec(
        id="test.api_emit",
        title="API Emit",
        description="api",
        category="Test",
        mode="python-file",
        script=str(script_path),
        args_schema=(ArgSpec("dummy", flag="--dummy", kind="str", default=None),),
        artifacts=("api_artifact.txt",),
    )
    manager = JobManager(specs=(spec,), state_dir=tmp_path / "state", repo_root=tmp_path)
    port = find_free_port()
    server = ControlPlaneServer(host="127.0.0.1", port=port, manager=manager)
    server.start()
    try:
        base = server.base_url
        commands = _get_json(base + "/commands")
        assert commands["commands"][0]["id"] == "test.api_emit"
        assert "workflow_stages" in commands
        assert "workflow_stage" in commands["commands"][0]
        assert "quickstart_notes" in commands["commands"][0]
        assert "recommended_next_command_ids" in commands["commands"][0]

        create = _post_json(base + "/commands/test.api_emit/runs", {"args": {}})
        run_id = create["run"]["run_id"]

        deadline = time.time() + 10
        status = "queued"
        while time.time() < deadline:
            run_payload = _get_json(base + f"/runs/{run_id}")
            status = run_payload["run"]["status"]
            if status in {"succeeded", "failed", "stopped"}:
                break
            time.sleep(0.1)
        assert status == "succeeded"

        logs = _get_json(base + f"/runs/{run_id}/logs")
        assert "api ok" in logs["logs"]["stdout"]

        artifacts = _get_json(base + f"/runs/{run_id}/artifacts")
        assert artifacts["artifacts"]
        assert artifacts["artifacts"][0]["exists"] is True
    finally:
        server.stop()


def test_ui_route_returns_html(tmp_path: Path) -> None:
    spec = CommandSpec(
        id="test.noop",
        title="Noop",
        description="noop",
        category="Test",
        mode="module",
        script="inout.runner",
    )
    manager = JobManager(specs=(spec,), state_dir=tmp_path / "state", repo_root=tmp_path)
    port = find_free_port()
    server = ControlPlaneServer(host="127.0.0.1", port=port, manager=manager)
    server.start()
    try:
        with urllib.request.urlopen(server.base_url + "/", timeout=10) as resp:
            html = resp.read().decode("utf-8")
        assert "CRT Web Control Plane" in html
        assert "Run History" in html
        assert "playbookPanel" in html
        assert "helpBtn" in html
        assert "tourOverlay" in html
    finally:
        server.stop()
