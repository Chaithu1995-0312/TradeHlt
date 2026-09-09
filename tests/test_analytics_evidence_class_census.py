from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "analysis"))

import analytics_evidence_class_census as census  # noqa: E402


def _row(field: str, producer: str = "src/emitter.py") -> census.RegistryRow:
    return census.RegistryRow(field, "owner", "events", "EXACT_MATCH", field, "*_events.jsonl", producer)


def test_corpus_observation_wins_over_code(tmp_path: Path) -> None:
    events = tmp_path / "logs" / "run" / "XAUUSD_events.jsonl"
    events.parent.mkdir(parents=True)
    events.write_text(json.dumps({"event": "STATE_TRANSITION", "timestamp": "t"}) + "\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "emitter.py").write_text("event = 'fallback'\n", encoding="utf-8")

    classified = census.classify([_row("event"), _row("timestamp")], tmp_path)

    assert [entry["evidence_class"] for entry in classified] == ["CORPUS_VERIFIED", "CORPUS_VERIFIED"]
    assert all(str(entry["evidence"]).startswith("logs/run/XAUUSD_events.jsonl:") for entry in classified)


def test_foreign_events_are_not_admissible_corpus_proof(tmp_path: Path) -> None:
    foreign = tmp_path / "logs" / "integrity_events.jsonl"
    foreign.parent.mkdir(parents=True)
    foreign.write_text(json.dumps({"event": "SELFTEST"}) + "\n", encoding="utf-8")

    classified = census.classify([_row("event", "UNKNOWN")], tmp_path)

    assert classified[0]["evidence_class"] == "DECLARED_ONLY"


def test_code_then_declared_then_unknown_precedence(tmp_path: Path) -> None:
    producer = tmp_path / "src" / "emitter.py"
    producer.parent.mkdir()
    producer.write_text("payload = {'code_only': 1}\n", encoding="utf-8")
    unknown = census.RegistryRow("missing", "owner", "events", "EXACT_MATCH", "UNKNOWN", "*_events.jsonl", "UNKNOWN")

    classified = census.classify([_row("code_only"), _row("declared_only", "UNKNOWN"), unknown], tmp_path)

    assert [entry["evidence_class"] for entry in classified] == ["CODE_VERIFIED", "DECLARED_ONLY", "UNKNOWN"]
