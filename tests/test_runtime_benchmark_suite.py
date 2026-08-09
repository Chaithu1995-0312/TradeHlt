"""Floor for RUNTIME-BENCHMARK-SUITE-2026-07-20 (separate from feature freeze).

Asserts authority separation, RB1 XAUUSD primary provenance/coverage/acceptance,
and that full-corpus BNB is not required as the primary iteration benchmark.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POLICY = ROOT / "docs" / "governance" / "runtime-benchmark-suite-2026-07-20.md"
PIN = ROOT / "docs" / "governance" / "runtime-benchmark-suite-pin-2026-07-20.json"
FEATURE_PIN = ROOT / "docs" / "governance" / "feature-layer-freeze-pin-2026-07-20.json"

SUITE_ID = "RUNTIME-BENCHMARK-SUITE-2026-07-20"
STATUS_TOKEN = "RUNTIME_BENCHMARK_SUITE = AUTHORITY_ACTIVE"


def _load_pin() -> dict:
    assert PIN.is_file(), f"missing suite pin: {PIN}"
    return json.loads(PIN.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def test_policy_and_token():
    assert POLICY.is_file()
    text = POLICY.read_text(encoding="utf-8")
    assert SUITE_ID in text
    assert STATUS_TOKEN in text
    assert "Separate authority" in text or "separate authority" in text.lower()
    assert "XAUUSD 2-month" in text or "XAUUSD 2-month window" in text
    assert "RB-HEAVY" in text or "RB1-HEAVY" in text or "optional" in text.lower()


def test_pin_authority_separation_from_feature_freeze():
    pin = _load_pin()
    assert pin.get("suite_id") == SUITE_ID
    assert pin.get("status_token") == STATUS_TOKEN
    assert pin.get("feature_freeze_pin")
    assert FEATURE_PIN.is_file()
    sep = pin.get("authority_separation") or {}
    assert "feature" in json.dumps(sep).lower()
    assert "runtime" in json.dumps(sep).lower()
    # Must not use feature-matrix vector SHA as a suite pass gate
    blob = json.dumps(pin)
    assert "adad1a0ba6b42c4549c85f8152e4bcb560c07d7e94f8e910ec6622003d484c0b" not in blob
    rb1 = pin["benchmarks"]["RB1_XAUUSD_W2M"]
    assert rb1.get("role") == "PRIMARY_ITERATION_BENCHMARK"
    assert rb1.get("status") == "ACCEPTED_PRIMARY"


def test_rb1_gate_pair_provenance():
    pin = _load_pin()
    rb1 = pin["benchmarks"]["RB1_XAUUSD_W2M"]
    assert rb1["csv_path"] == "data/XAUUSD_W2026-03-23-to-2026-05-21.csv"
    csv = ROOT / rb1["csv_path"]
    assert csv.is_file()
    assert _sha256(csv) == rb1["csv_sha256"]
    arms = rb1["arms"]
    assert arms["gate_off"]["backtest_engine_gate"] == "0"
    assert arms["gate_on"]["backtest_engine_gate"] == "1"
    assert arms["gate_off"]["process_env"]["BACKTEST_ENGINE_GATE"] == "0"
    assert arms["gate_on"]["process_env"]["BACKTEST_ENGINE_GATE"] == "1"
    assert arms["gate_off"]["active_config_version"] == pin["active_config_version"]
    assert arms["gate_on"]["active_config_version"] == pin["active_config_version"]
    for side in ("gate_off", "gate_on"):
        a = arms[side]
        assert a["artifact_hashes"]["summary_json"]
        assert a["artifact_hashes"]["events_jsonl"]
        cov = a["coverage"]
        assert cov["benchmark_class"] == "RUNTIME_BACKTEST"
        assert cov["backtest_engine_gate"] == a["backtest_engine_gate"]
        assert "exercises" in cov
        assert cov["exercises"]["backtest_v2"] is True
        assert cov["exercises"]["crt_state_machine"] is True
        assert "filter_reject_reasons" in cov
        assert "trade_count" in cov
        assert a.get("metrics_authority") == "DESCRIPTIVE_ONLY_NOT_PROMOTION"


def test_rb1_artifacts_rehash_when_retained():
    pin = _load_pin()
    rb1 = pin["benchmarks"]["RB1_XAUUSD_W2M"]
    if not pin.get("acceptance_criteria", {}).get("B5_artifacts_retained"):
        return
    for side in ("gate_off", "gate_on"):
        a = rb1["arms"][side]
        run_dir = ROOT / a["run_dir"]
        # run_dir may be absolute or relative
        if not run_dir.is_dir():
            run_dir = Path(a["run_dir"])
        assert run_dir.is_dir(), a["run_dir"]
        inst = a["instrument"]
        summ = run_dir / f"{inst}_summary.json"
        events = run_dir / f"{inst}_events.jsonl"
        assert summ.is_file() and events.is_file()
        assert _sha256(summ) == a["artifact_hashes"]["summary_json"]
        assert _sha256(events) == a["artifact_hashes"]["events_jsonl"]


def test_acceptance_criteria_all_true():
    pin = _load_pin()
    ac = pin["acceptance_criteria"]
    for k, v in ac.items():
        assert v is True, f"acceptance criterion {k} not true"


def test_bnb_is_not_primary():
    pin = _load_pin()
    heavy = pin["benchmarks"].get("RB1_HEAVY_BNB_FULL") or {}
    # Primary must be XAUUSD
    assert "RB1_XAUUSD_W2M" in pin["benchmarks"]
    assert pin["benchmarks"]["RB1_XAUUSD_W2M"]["role"] == "PRIMARY_ITERATION_BENCHMARK"
    # Heavy BNB must not be ACCEPTED_PRIMARY
    assert heavy.get("status") != "ACCEPTED_PRIMARY"
