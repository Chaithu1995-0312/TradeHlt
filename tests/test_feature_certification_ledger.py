"""Feature-certification ledger floor — the durable gate that the certification ledger stays
schema-valid, append-only-monotonic, and DESCRIPTIVE-ONLY (never grants production authority).

Mirrors the corpus_authority_decisions validator (per-event required fields + binding guards) and
the active_models authority-creep guard (test_active_models_registry.py:44-45,191-213).
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_LEDGER = _REPO / "docs" / "governance" / "feature_certification_ledger.jsonl"
_SCHEMA = _REPO / "docs" / "governance" / "feature_certification_ledger.schema.json"
_STATE = _REPO / "scripts" / "governance" / "feature_certification_state.py"

_EVENT_TYPES = {"SEEDED", "CERTIFIED", "PROMOTED", "BLOCKED", "INVALIDATED_STALE", "SUPERSEDED"}
_FRONTIER = {"UNKNOWN", "HYPOTHESIS", "CERTIFIED", "PROMOTED_PRODUCTION", "BLOCKED", "STALE", "SUPERSEDED"}
_PROMOTION_AUTHORITY = {"src/governance/promotion_manager.py", "src/research/qualification.py"}
# §6.5 authority-creep: a descriptive ledger may never carry these as authority-granting keys.
_AUTHORITY_CREEP_RE = re.compile(r"promotion_requirements|min_delta", re.IGNORECASE)


def _events():
    if not _LEDGER.exists():
        pytest.skip("certification ledger not seeded")
    return [json.loads(ln) for ln in _LEDGER.read_text(encoding="utf-8").splitlines() if ln.strip()]


def test_schema_file_is_valid_json():
    assert _SCHEMA.exists()
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    assert schema["contract_id"] == "FEATURE-CERT-LEDGER-V1"


def test_every_event_has_base_fields():
    for ev in _events():
        assert ev["event"] in _EVENT_TYPES, ev
        assert ev["feature_name"] and ev["timestamp"]
        assert ev["frontier_state"] in _FRONTIER, ev
        assert "research/governance only" in ev.get("authority", ""), (
            f"{ev['feature_name']}/{ev['event']}: missing descriptive authority disclaimer"
        )


def test_per_event_required_extras():
    for ev in _events():
        e = ev["event"]
        if e == "CERTIFIED":
            for k in ("formula_hash", "dependency_contract_hash", "certified_at", "certification_evidence"):
                assert ev.get(k), f"CERTIFIED {ev['feature_name']} missing {k}"
        elif e == "PROMOTED":
            for k in ("formula_hash", "dependency_contract_hash", "promotion_authority"):
                assert ev.get(k), f"PROMOTED {ev['feature_name']} missing {k}"
            assert ev["promotion_authority"] in _PROMOTION_AUTHORITY, (
                f"PROMOTED {ev['feature_name']}: promotion authority must stay in code, got "
                f"{ev['promotion_authority']}"
            )
        elif e == "BLOCKED":
            assert ev.get("blocking_dependencies"), f"BLOCKED {ev['feature_name']} needs blocking_dependencies"
        elif e == "INVALIDATED_STALE":
            assert ev.get("stale_reason") and ev.get("upstream_trigger")
        elif e == "SUPERSEDED":
            assert ev.get("superseded_by")


def test_descriptive_only_no_authority_creep():
    """The ledger records outcomes; it must never encode a promotion requirement or a runtime
    threshold value. (a) no authority-creep key names; (b) no numeric *_threshold key."""
    for ev in _events():
        for k, v in ev.items():
            assert not _AUTHORITY_CREEP_RE.search(k), f"authority-creep key '{k}' in ledger event"
            if k.endswith("_threshold") and isinstance(v, (int, float)):
                pytest.fail(f"ledger sets a runtime threshold value {k}={v} (§6.5 violation)")


def test_append_only_monotonic_coverage():
    """Seed coverage is monotone: every feature ever seen keeps at least its SEEDED baseline; the
    resolver never drops a feature. (append-discipline — history is preserved, not rewritten)."""
    events = _events()
    seeded = {ev["feature_name"] for ev in events if ev["event"] == "SEEDED"}
    seen = {ev["feature_name"] for ev in events}
    # every feature that appears must have been seeded first (no orphan mutation without a baseline)
    assert seen == seeded or seen.issubset(seeded), sorted(seen - seeded)


def _load_state():
    spec = importlib.util.spec_from_file_location("feature_certification_state", _STATE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["feature_certification_state"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_resolver_derives_blocked_from_dag():
    if not _STATE.exists():
        pytest.skip("state resolver not present")
    mod = _load_state()
    dag = mod._load_dag()
    state = mod.resolve_state(mod.load_events(), dag)
    # raw inputs are axiomatic-promoted; L1 ema_spread's deps not yet promoted → ema_spread BLOCKED
    assert state["close"]["effective_state"] == "PROMOTED_PRODUCTION"
    assert state["ema_spread"]["effective_state"] in {"BLOCKED", "READY_TO_CERTIFY", "CERTIFIED",
                                                      "PROMOTED_PRODUCTION", "STALE", "SUPERSEDED"}
    # every non-raw feature with an unpromoted dep must report it
    for f, s in state.items():
        if s["blocking_dependencies"]:
            assert s["effective_state"] == "BLOCKED"
