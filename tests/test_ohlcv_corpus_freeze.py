"""R0 mechanical freeze: pinned canonical corpus bytes must not drift.

Drift is permitted only when a non-UNRESOLVED corpus authority decision for the
same logical_corpus_id lists the new hash (approved_sha256 or a candidate hash).

This is NOT CandleLoader admission (R3).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FREEZE_PIN = ROOT / "docs" / "governance" / "ohlcv-corpus-freeze-pin-2026-07-10.json"
FREEZE_POLICY = ROOT / "docs" / "governance" / "ohlcv-corpus-mutation-freeze-2026-07-10.md"
DECISIONS = ROOT / "docs" / "governance" / "corpus_authority_decisions.jsonl"

# Statuses that may authorize intentional pin drift (not Phase-1 freeze alone —
# FROZEN_CANDIDATE is a scope pin, not a mutation waiver for other corpora).
TERMINAL = frozenset({"APPROVED", "REJECTED", "QUARANTINED"})


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_pin() -> dict:
    assert FREEZE_PIN.is_file(), f"missing freeze pin: {FREEZE_PIN}"
    return json.loads(FREEZE_PIN.read_text(encoding="utf-8"))


def _decisions() -> list[dict]:
    if not DECISIONS.is_file():
        return []
    rows = []
    for line in DECISIONS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _hashes_authorized_for(logical_id: str | None) -> set[str]:
    """Hashes a terminal decision may authorize as intentional mutation targets."""
    if not logical_id:
        return set()
    out: set[str] = set()
    for row in _decisions():
        if row.get("logical_corpus_id") != logical_id:
            continue
        if row.get("decision_status") not in TERMINAL:
            continue
        if row.get("approved_sha256"):
            out.add(row["approved_sha256"])
        for h in row.get("candidate_hashes") or []:
            out.add(h)
        for c in row.get("candidate_physical_artifacts") or []:
            if c.get("sha256"):
                out.add(c["sha256"])
    return out


def test_freeze_policy_exists():
    assert FREEZE_POLICY.is_file()
    text = FREEZE_POLICY.read_text(encoding="utf-8")
    assert "OHLCV-CORPUS-FREEZE-2026-07-10" in text
    assert "Canonical corpus replacement" in text or "canonical corpus replacement" in text.lower()
    assert "quarantine" in text.lower()
    assert "HANDOFF" in text
    assert "corpus.py" in text


def test_freeze_pin_schema():
    pin = _load_pin()
    assert pin.get("freeze_id") == "OHLCV-CORPUS-FREEZE-2026-07-10"
    assert pin.get("schema_version") == "1.0.0"
    pins = pin.get("pins")
    assert isinstance(pins, list) and len(pins) >= 1
    paths = []
    for entry in pins:
        assert "path" in entry and "sha256" in entry
        assert len(entry["sha256"]) == 64
        paths.append(entry["path"])
    assert "data/XAUUSD_M15.csv" in paths


def test_freeze_pins_match_on_disk_or_authorized_decision():
    pin = _load_pin()
    failures = []
    for entry in pin["pins"]:
        rel = entry["path"]
        p = ROOT / rel
        if not p.is_file():
            failures.append(f"missing pinned file: {rel}")
            continue
        actual = _sha256(p)
        expected = entry["sha256"]
        if actual == expected:
            continue
        authorized = _hashes_authorized_for(entry.get("logical_corpus_id"))
        if actual in authorized:
            continue
        failures.append(
            f"freeze drift on {rel}: pinned {expected[:16]}.. on-disk {actual[:16]}.. "
            f"(no terminal authority decision covering the new hash)"
        )
    assert not failures, "\n".join(failures)
