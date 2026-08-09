"""IC-003B pause/resume checkpoint helpers (no full DTW run)."""
from __future__ import annotations

import json
from pathlib import Path

from research.ic003b_sequence_geometry.build_all import (
    inventory_units,
    write_paused_checkpoint,
    _arm_complete,
    _write_arm_artifacts,
)


def test_arm_complete_requires_verdict(tmp_path: Path) -> None:
    sub = tmp_path / "arm_S_N4"
    sub.mkdir()
    (sub / "shapes.json").write_text("{}", encoding="utf-8")
    assert not _arm_complete(tmp_path, "S", 4)

    (sub / "shapes.json").write_text(
        json.dumps({"N": 4, "arm": "S", "verdict": "LIBRARY_OK"}),
        encoding="utf-8",
    )
    assert _arm_complete(tmp_path, "S", 4)


def test_write_paused_lists_completed(tmp_path: Path) -> None:
    res = {
        "N": 4,
        "arm": "S",
        "verdict": "LIBRARY_OK",
        "k_star": 6,
        "gates": {},
        "labels": [0, 1, 0],
    }
    _write_arm_artifacts(tmp_path, "S", 4, res, ["a", "b", "c"], ["TP", "SL", "TP"])
    snap = write_paused_checkpoint(
        tmp_path,
        note="test pause",
        primary_N=(4, 16),
        diagnostic_N=(8,),
    )
    assert snap["status"] == "PAUSED"
    assert "S_N4" in snap["completed"]
    assert "T_N4" in snap["pending"]
    assert "T_N16" in snap["pending"]
    cp = json.loads((tmp_path / "checkpoint.json").read_text(encoding="utf-8"))
    assert cp["status"] == "PAUSED"
    assert cp["next_session_priority"] is True
    assert (tmp_path / "RUN_STATUS.md").is_file()


def test_inventory_empty(tmp_path: Path) -> None:
    completed, pending = inventory_units(tmp_path, primary_N=(4,), diagnostic_N=())
    assert completed == []
    assert pending == ["S_N4", "T_N4", "C_N4"]
