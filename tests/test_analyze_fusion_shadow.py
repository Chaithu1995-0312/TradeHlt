import json
from pathlib import Path

from runtime.analyze_fusion_shadow import analyze_log


def test_analyze_log_reads_prefixed_json_lines(tmp_path: Path):
    log_path = tmp_path / "flow_collector.log"
    line_with_shadow = {
        "id": "a1",
        "fusion": {
            "final_score": 0.9,
            "evaluate_shadow": {"final_score": 0.6},
        },
    }
    line_without_shadow = {"id": "a2", "fusion": {"final_score": 0.5}}
    non_json_line = "[2026-04-11T00:00:00Z] [FLOW:COLLECTOR] [INFO] plain text"

    content = "\n".join(
        [
            f'[ts] [FLOW:COLLECTOR] [INFO] {json.dumps(line_with_shadow)}',
            f'[ts] [FLOW:COLLECTOR] [INFO] {json.dumps(line_without_shadow)}',
            non_json_line,
        ]
    )
    log_path.write_text(content, encoding="utf-8")

    summary = analyze_log(log_path)

    assert summary["records_total"] == 2
    assert summary["records_with_fusion"] == 2
    assert summary["records_with_shadow"] == 1
    assert summary["records_missing_shadow"] == 1
    assert summary["delta_summary"]["count"] == 1
    assert abs(summary["delta_summary"]["avg_delta_shadow_minus_compute"] - (-0.3)) < 1e-9
    assert summary["sample_trade_ids"] == ["a1"]


def test_analyze_log_handles_empty_input(tmp_path: Path):
    log_path = tmp_path / "empty.log"
    log_path.write_text("", encoding="utf-8")

    summary = analyze_log(log_path)

    assert summary["records_total"] == 0
    assert summary["records_with_shadow"] == 0
    assert summary["delta_summary"]["count"] == 0
    assert summary["delta_summary"]["avg_abs_delta"] == 0.0
