"""
test_provenance_remediation.py — M6R regression test for empty-hash provenance.

Invariant:
  A certification event with empty evidence SHA-256 is not considered fully
  provenance-complete unless a valid append-only PROVENANCE_REMEDIATION event
  resolves it.

This test enforces that the ledger's provenance model is self-consistent:
  - Every CERTIFIED event with empty sha256 must have a corresponding
    PROVENANCE_REMEDIATION event that references it by event_identity_hash.
  - The remediation event must be append-only (no rewriting of history).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LEDGER = REPO_ROOT / "docs" / "governance" / "feature_certification_ledger.jsonl"


def _load_ledger() -> list[dict]:
    """Load all events from the ledger JSONL file."""
    events: list[dict] = []
    for line in LEDGER.read_text("utf-8").strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def _event_identity_hash(event: dict) -> str:
    """Compute the SHA-256 of the event's JSON line (as it appears in the ledger)."""
    # Re-serialize to match the original line format
    line = json.dumps(event, ensure_ascii=False, sort_keys=False)
    return hashlib.sha256(line.encode("utf-8")).hexdigest()


class TestProvenanceRemediation:
    """M6R: empty-hash certification events must be remediated."""

    @pytest.fixture(scope="class")
    def ledger_events(self) -> list[dict]:
        return _load_ledger()

    def test_ledger_exists(self):
        """The certification ledger must exist."""
        assert LEDGER.exists(), f"Ledger not found at {LEDGER}"

    def test_all_empty_hash_events_have_remediation(self, ledger_events):
        """Every CERTIFIED event with empty sha256 must have a corresponding
        PROVENANCE_REMEDIATION event that references it by event_identity_hash."""
        # Collect all CERTIFIED events with empty sha256
        empty_hash_events: list[dict] = []
        for ev in ledger_events:
            if ev.get("event") != "CERTIFIED":
                continue
            evidence = ev.get("certification_evidence") or {}
            if evidence.get("sha256", "") == "":
                empty_hash_events.append(ev)

        # Collect all PROVENANCE_REMEDIATION events
        remediation_events: list[dict] = [
            ev for ev in ledger_events
            if ev.get("event") == "PROVENANCE_REMEDIATION"
        ]

        # Build a set of remediated event hashes
        remediated_hashes: set[str] = set()
        for rev in remediation_events:
            h = rev.get("original_event_identity_hash")
            if h:
                remediated_hashes.add(h)

        # Check each empty-hash event has a remediation
        unremediated: list[str] = []
        for ev in empty_hash_events:
            eh = _event_identity_hash(ev)
            if eh not in remediated_hashes:
                feature = ev.get("feature_name", "?")
                formula = ev.get("formula_id", "?")
                unremediated.append(
                    f"{feature} ({formula}): event hash {eh[:16]}..."
                )

        assert not unremediated, (
            f"{len(unremediated)} CERTIFIED event(s) with empty evidence SHA-256 "
            f"have no PROVENANCE_REMEDIATION event:\n" + "\n".join(unremediated)
        )

    def test_remediation_does_not_rewrite_history(self, ledger_events):
        """PROVENANCE_REMEDIATION events must be append-only — they must not
        modify or replace the original CERTIFIED event."""
        certified_events: dict[str, dict] = {}
        remediation_events: list[dict] = []

        for ev in ledger_events:
            if ev.get("event") == "CERTIFIED":
                eh = _event_identity_hash(ev)
                certified_events[eh] = ev
            elif ev.get("event") == "PROVENANCE_REMEDIATION":
                remediation_events.append(ev)

        for rev in remediation_events:
            original_hash = rev.get("original_event_identity_hash")
            if original_hash and original_hash in certified_events:
                original = certified_events[original_hash]
                # Verify the original event still has empty sha256 (not rewritten)
                evidence = original.get("certification_evidence") or {}
                assert evidence.get("sha256", "") == "", (
                    f"Original CERTIFIED event for {original.get('feature_name')} "
                    f"was rewritten — sha256 is no longer empty. "
                    f"Remediation must be append-only."
                )

    def test_remediation_marks_provenance_status(self, ledger_events):
        """Every PROVENANCE_REMEDIATION event must declare a provenance_status."""
        remediation_events = [
            ev for ev in ledger_events
            if ev.get("event") == "PROVENANCE_REMEDIATION"
        ]
        for rev in remediation_events:
            status = rev.get("provenance_status")
            assert status is not None, (
                f"PROVENANCE_REMEDIATION event for {rev.get('target_feature')} "
                f"missing provenance_status"
            )
            assert status in ("RESOLVED", "UNRESOLVED"), (
                f"provenance_status must be RESOLVED or UNRESOLVED, got {status!r}"
            )

    def test_remediation_declares_no_behavior_change(self, ledger_events):
        """PROVENANCE_REMEDIATION must declare certification_identity_changed=NO
        and production_behavior_changed=NO."""
        remediation_events = [
            ev for ev in ledger_events
            if ev.get("event") == "PROVENANCE_REMEDIATION"
        ]
        for rev in remediation_events:
            assert rev.get("certification_identity_changed") == "NO", (
                f"Remediation for {rev.get('target_feature')}: "
                f"certification_identity_changed must be NO"
            )
            assert rev.get("production_behavior_changed") == "NO", (
                f"Remediation for {rev.get('target_feature')}: "
                f"production_behavior_changed must be NO"
            )