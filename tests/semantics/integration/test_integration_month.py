"""Real-corpus Semantic OS integration run on the one-month XAUUSD slice (owner-run).

Skipped unless --run-measurement: it runs the backtest twice on gitignored data/ and writes results/.
"""

from __future__ import annotations

import json

import pytest

from semantics.integration.observe import MONTH_SLICE

pytestmark = pytest.mark.measurement


def test_month_slice_replay_is_faithful_and_every_reset_maps(tmp_path):
    if not MONTH_SLICE.is_file():
        pytest.skip(f"corpus slice missing: {MONTH_SLICE}")
    import importlib.util
    from pathlib import Path

    script = Path(__file__).resolve().parents[3] / "scripts" / "governance" / "semantic_os_integration.py"
    spec = importlib.util.spec_from_file_location("semantic_os_integration", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.main(["--out", str(tmp_path)]) == 0
    run = next(p for p in tmp_path.iterdir() if p.is_dir())
    summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    assert summary["replay_gate"]["status"] == "PASS"
    assert "UNEXPLAINED" not in summary["per_check_concept"].get("C1 MKT-P01", {})
    assert {row["concept_id"] for row in summary["d_level_table"]} >= {"MKT-E01", "TRS-03", "DEX-05"}
