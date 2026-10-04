"""Floor for the parent-CRT pivotality probe (F-089).

Unit-level: the probe's own run does two full spine passes (minutes), so these exercise
the pure comparison/gate functions on synthetic streams instead.

The load-bearing test here is `test_outcome_difference_classifies_pivotal` and its
siblings — per the E-001 lesson that *a test that cannot fail is not enforcement*, the
probe must be demonstrably able to return PIVOTAL and VACUOUS, not only the verdict that
happens to be true today.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_SRC = _REPO / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

_PROBE_PATH = _REPO / "scripts" / "research" / "parent_crt_pivotality_probe.py"


def _load_probe():
    spec = importlib.util.spec_from_file_location("parent_crt_pivotality_probe", _PROBE_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


probe = _load_probe()


# ── fixtures ───────────────────────────────────────────────────────────────────
def _cfg(enabled: bool) -> dict:
    return {
        "params": {"a": 1, "b": 2},
        "config_hash": "deadbeef",
        "parent_crt": {"enabled": enabled, "timeframe": "H4"},
        "crt_engine": {"use_bitnet": False},
    }


def _events(rejections: dict[str, str], *, states=None, trades=None) -> list[dict]:
    states = states if states is not None else [
        ("STATE_TRANSITION", "2024-05-23T02:00:00", "RANGE", "SWEEP"),
        ("RESET", "2024-05-23T03:00:00", "SWEEP", "RANGE"),
    ]
    out = [{"event": e, "timestamp": t, "state_from": a, "state_to": b}
           for e, t, a, b in states]
    out += [{"event": "FILTER_REJECTED", "timestamp": t, "reason": r}
            for t, r in rejections.items()]
    for kind, n in (trades or {"TRADE_OPENED": 3}).items():
        out += [{"event": kind, "timestamp": f"2025-01-0{i+1}T00:00:00"} for i in range(n)]
    return out


def _write(tmp_path: Path, name: str, rows: list[dict]) -> Path:
    p = tmp_path / name
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return p


_BIAS_LONG = "Against parent-timeframe bias (LONG)"
_OFF_SESSION = "off_session:OFF_SESSION"


# ── validity gate 1: the A/B must isolate exactly one knob ─────────────────────
def test_config_ab_valid_when_only_parent_crt_enabled_differs():
    ab = probe.compare_configs(_cfg(True), _cfg(False))
    assert ab["valid"] is True
    assert ab["config_hash_equal"] is True
    assert ab["params_diff"] == []


def test_config_ab_invalid_when_params_differ():
    """A confounded pair must be refused, not silently compared."""
    on, off = _cfg(True), _cfg(False)
    off["params"]["a"] = 99
    ab = probe.compare_configs(on, off)
    assert ab["valid"] is False
    assert ab["params_diff"] == ["a"]


def test_config_ab_invalid_when_config_hash_differs():
    on, off = _cfg(True), _cfg(False)
    off["config_hash"] = "cafebabe"
    assert probe.compare_configs(on, off)["valid"] is False


def test_config_ab_invalid_when_another_behavioural_section_differs():
    """Any unexplained behavioural difference means the arms differ elsewhere too."""
    on, off = _cfg(True), _cfg(False)
    off["crt_engine"]["use_bitnet"] = True
    ab = probe.compare_configs(on, off)
    assert ab["valid"] is False
    assert ab["unexplained_behavioural_diffs"] == ["crt_engine.use_bitnet"]


def test_config_ab_ignores_metadata_and_comment_differences():
    """Provenance fields and comments differ on every promoted config and are inert."""
    on, off = _cfg(True), _cfg(False)
    on["config_id"] = "x_promote";        off["config_id"] = "y_candidate"
    on["created_at"] = "2026-08-15";      off["created_at"] = "2026-05-06"
    on["notes"] = "one";                  off["notes"] = "two"
    on["version"] = "v_on";               off["version"] = "v_off"
    on["validation_summary"] = {"a": 1};  off["validation_summary"] = {"a": 2}
    on["_comment_parent_crt"] = "armed";  off["_comment_parent_crt"] = "not armed"
    on["crt_engine"]["note"] = "n1";      off["crt_engine"]["note"] = "n2"
    ab = probe.compare_configs(on, off)
    assert ab["valid"] is True, ab["unexplained_behavioural_diffs"]


def test_config_ab_accepts_the_adjudicated_inert_ultron_keys():
    """The 4 F-082 cost-tax keys are declared-at-default on ON, absent on OFF."""
    on, off = _cfg(True), _cfg(False)
    on["ultron_risk_gate"] = {"spread_pips": 0.0, "slippage_pips": 0.0,
                              "pip_size": 0.0001, "min_sl_pips": 0.0}
    off["ultron_risk_gate"] = {}
    assert probe.compare_configs(on, off)["valid"] is True


def test_config_ab_rejects_a_NON_default_ultron_value():
    """Adjudicated-inert covers the key, NOT any value. A live tax must invalidate."""
    on, off = _cfg(True), _cfg(False)
    on["ultron_risk_gate"] = {"spread_pips": 1.5}     # a real tax -> behaviour differs
    off["ultron_risk_gate"] = {}
    ab = probe.compare_configs(on, off)
    assert ab["valid"] is False
    assert ab["unexplained_behavioural_diffs"] == ["ultron_risk_gate.spread_pips"]


def test_config_ab_invalid_when_gate_is_not_actually_on_and_off():
    """Both arms enabled is not an A/B at all."""
    assert probe.compare_configs(_cfg(True), _cfg(True))["valid"] is False


def test_config_ab_invalid_on_extra_behavioural_top_level_key():
    on, off = _cfg(True), _cfg(False)
    on["extra_section"] = {"x": 1}
    ab = probe.compare_configs(on, off)
    assert ab["valid"] is False
    assert "extra_section" in ab["unexplained_behavioural_diffs"]


# ── verdicts ───────────────────────────────────────────────────────────────────
def test_reason_only_difference_classifies_decision_neutral(tmp_path):
    """The measured XAUUSD shape: same candidates die, the recorded reason differs."""
    on = probe.load_profile(_write(tmp_path, "on.jsonl", _events(
        {"2025-01-31T21:00:00": _BIAS_LONG, "2025-02-01T21:00:00": _OFF_SESSION})))
    off = probe.load_profile(_write(tmp_path, "off.jsonl", _events(
        {"2025-01-31T21:00:00": _OFF_SESSION, "2025-02-01T21:00:00": _OFF_SESSION})))
    r = probe.classify(on, off)
    assert r["verdict"] == probe.VERDICT_NEUTRAL
    assert r["gate_fired"] == 1
    assert r["reasons_changed"] == 1
    assert r["outcomes_changed"] == 0
    assert r["state_sequence_equal"] is True
    assert r["reasons_changed_detail"][0]["gate_off"] == _OFF_SESSION
    assert r["reasons_changed_detail"][0]["gate_on"] == _BIAS_LONG


def test_extra_rejection_in_gate_on_classifies_pivotal(tmp_path):
    """A candidate the gate kills that the OFF arm let through IS an outcome change."""
    on = probe.load_profile(_write(tmp_path, "on.jsonl", _events(
        {"2025-01-31T21:00:00": _BIAS_LONG})))
    off = probe.load_profile(_write(tmp_path, "off.jsonl", _events({})))
    r = probe.classify(on, off)
    assert r["verdict"] == probe.VERDICT_PIVOTAL
    assert r["rejections_only_in_gate_on"] == ["2025-01-31T21:00:00"]
    assert r["outcomes_changed"] >= 1


def test_state_sequence_difference_classifies_pivotal(tmp_path):
    """A perturbed state machine is pivotal even if the rejection set matches."""
    rej = {"2025-01-31T21:00:00": _BIAS_LONG}
    on = probe.load_profile(_write(tmp_path, "on.jsonl", _events(rej)))
    off = probe.load_profile(_write(tmp_path, "off.jsonl", _events(
        {"2025-01-31T21:00:00": _OFF_SESSION},
        states=[("STATE_TRANSITION", "2024-05-23T02:00:00", "RANGE", "SWEEP")])))
    r = probe.classify(on, off)
    assert r["verdict"] == probe.VERDICT_PIVOTAL
    assert r["state_sequence_equal"] is False


def test_trade_count_difference_classifies_pivotal(tmp_path):
    rej = {"2025-01-31T21:00:00": _BIAS_LONG}
    on = probe.load_profile(_write(tmp_path, "on.jsonl",
                                   _events(rej, trades={"TRADE_OPENED": 3})))
    off = probe.load_profile(_write(tmp_path, "off.jsonl",
                                    _events({"2025-01-31T21:00:00": _OFF_SESSION},
                                            trades={"TRADE_OPENED": 5})))
    r = probe.classify(on, off)
    assert r["verdict"] == probe.VERDICT_PIVOTAL
    assert r["trades_equal"] is False


def test_gate_that_never_fires_is_vacuous_not_neutral(tmp_path):
    """A gate with nothing to veto is UNTESTED. It must not be reported as neutral."""
    ident = {"2025-01-31T21:00:00": _OFF_SESSION}
    on = probe.load_profile(_write(tmp_path, "on.jsonl", _events(ident)))
    off = probe.load_profile(_write(tmp_path, "off.jsonl", _events(ident)))
    r = probe.classify(on, off)
    assert r["verdict"] == probe.VERDICT_VACUOUS
    assert r["gate_fired"] == 0
    assert r["outcomes_changed"] == 0      # identical, yet still NOT "neutral"


# ── profile parsing ────────────────────────────────────────────────────────────
def test_profile_counts_state_events_and_separates_rejections(tmp_path):
    p = probe.load_profile(_write(tmp_path, "e.jsonl", _events(
        {"2025-01-31T21:00:00": _BIAS_LONG})))
    assert p["state_events"] == 2                      # STATE_TRANSITION + RESET
    assert p["rejections"] == {"2025-01-31T21:00:00": _BIAS_LONG}
    assert p["trades"]["TRADE_OPENED"] == 3


def test_profile_state_sha_is_order_sensitive(tmp_path):
    """RESET-before-TRANSITION on one bar is a different machine; the sha must see it."""
    a = [("STATE_TRANSITION", "t1", "RANGE", "SWEEP"), ("RESET", "t1", "SWEEP", "RANGE")]
    b = list(reversed(a))
    pa = probe.load_profile(_write(tmp_path, "a.jsonl", _events({}, states=a)))
    pb = probe.load_profile(_write(tmp_path, "b.jsonl", _events({}, states=b)))
    assert pa["state_seq_sha256"] != pb["state_seq_sha256"]


def test_profile_tolerates_a_corrupt_line(tmp_path):
    p = tmp_path / "e.jsonl"
    rows = [json.dumps(r) for r in _events({})]
    rows.insert(1, "{not json")
    p.write_text("\n".join(rows) + "\n", encoding="utf-8")
    assert probe.load_profile(p)["state_events"] == 2


# ── validity gate 3: corpus identity ───────────────────────────────────────────
def test_corpus_identity_fails_closed_on_wrong_bytes(tmp_path):
    bad = tmp_path / "XAUUSD_M15.csv"
    bad.write_text("timestamp,open,high,low,close,volume\n", encoding="utf-8")
    r = probe.verify_corpus(bad)
    assert r["ok"] is False
    assert r["got"] != r["expected"]


@pytest.mark.skipif(not (_REPO / "data" / "mt5" / "XAUUSD_M15.csv").is_file(),
                    reason="XAUUSD corpus not present")
def test_corpus_identity_passes_on_the_frozen_candidate():
    from data_ingestion.xauusd_phase1_candidate import PHASE1_SHA256
    r = probe.verify_corpus(_REPO / "data" / "mt5" / "XAUUSD_M15.csv")
    assert r["ok"] is True and r["got"] == PHASE1_SHA256


# ── the real configs still form a valid A/B ────────────────────────────────────
def test_the_two_real_registry_configs_isolate_parent_crt():
    """If a future edit breaks the isolation, this fails BEFORE F-089 is re-cited."""
    cfgs = _REPO / "configs" / "production"
    on_p = cfgs / f"{probe.GATE_ON_VERSION}.json"
    off_p = cfgs / f"{probe.GATE_OFF_VERSION}.json"
    if not (on_p.is_file() and off_p.is_file()):
        pytest.skip("registry configs not present")
    ab = probe.compare_configs(
        json.loads(on_p.read_text(encoding="utf-8")),
        json.loads(off_p.read_text(encoding="utf-8")),
    )
    assert ab["valid"] is True, (
        "the F-089 A/B no longer isolates parent_crt.enabled: " + json.dumps(ab, indent=2))
    assert ab["parent_crt_enabled_on"] is True
    assert ab["parent_crt_enabled_off"] is False
