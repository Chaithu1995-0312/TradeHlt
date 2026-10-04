import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from governance.bitnet_governance_executor import MetaGovernorExecutor


def test_log_governance_event_writes_jsonl_with_required_fields(tmp_path):
    log_path = tmp_path / "governance_audit.jsonl"
    executor = MetaGovernorExecutor(audit_log_path=str(log_path))

    event = executor.log_governance_event(
        event_type="promote",
        engine_id="rr_engine_v2",
        metrics_snapshot={"win_rate": 0.61, "sharpe": 1.27},
        decision={"action": "promote", "reason": "outperformed baseline"},
    )

    assert log_path.exists()
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1

    row = json.loads(lines[0])
    assert row == event
    assert set(row.keys()) == {
        "timestamp",
        "event_type",
        "engine_id",
        "metrics_snapshot",
        "decision",
    }
    assert row["timestamp"].endswith("Z")
    assert row["event_type"] == "promote"
    assert row["engine_id"] == "rr_engine_v2"
    assert row["metrics_snapshot"]["win_rate"] == pytest.approx(0.61)
    assert row["decision"]["action"] == "promote"


def test_log_governance_event_normalizes_non_dict_payloads(tmp_path):
    log_path = tmp_path / "governance_audit.jsonl"
    executor = MetaGovernorExecutor(audit_log_path=str(log_path))

    row = executor.log_governance_event(
        event_type="no_action",
        engine_id="ml_gaussian",
        metrics_snapshot=0.73,
        decision="hold",
    )

    assert row["metrics_snapshot"] == {"value": 0.73}
    assert row["decision"] == {"summary": "hold"}


@pytest.mark.parametrize(
    "event_type,engine_id",
    [
        ("", "engine_a"),
        ("promote", ""),
    ],
)
def test_log_governance_event_validates_required_fields(tmp_path, event_type, engine_id):
    log_path = tmp_path / "governance_audit.jsonl"
    executor = MetaGovernorExecutor(audit_log_path=str(log_path))

    with pytest.raises(ValueError):
        executor.log_governance_event(
            event_type=event_type,
            engine_id=engine_id,
            metrics_snapshot={"score": 0.4},
            decision={"action": "skip"},
        )
