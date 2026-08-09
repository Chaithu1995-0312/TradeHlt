"""Validator for corpus authority decision schema + JSONL table (R1).

Rules:
  - every row validates against corpus_authority_decision.schema.json
  - UNRESOLVED rows must not set approved_physical_path / approved_sha256
  - at most one APPROVED row per logical_corpus_id (non-superseded)
  - candidate hashes match fingerprint manifest when path is inventoried
  - status enum closed
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "docs" / "governance" / "corpus_authority_decision.schema.json"
DECISIONS = ROOT / "docs" / "governance" / "corpus_authority_decisions.jsonl"
FINGERPRINT = (
    ROOT / "docs" / "governance" / "ohlcv-corpus-fingerprint-manifest-2026-07-10.json"
)
DOCTRINE = ROOT / "docs" / "governance" / "CORPUS_AUTHORITY.md"
XAUUSD_PKG = (
    ROOT / "docs" / "governance" / "corpus_authority_XAUUSD_M15_adjudication-2026-07-10.md"
)

LEGAL_STATUS = frozenset({
    "APPROVED",
    "REJECTED",
    "QUARANTINED",
    "UNRESOLVED",
    "FROZEN_CANDIDATE_PENDING_PHASE1_VALIDATION",
})
VOLUME = frozenset({
    "BASE_ASSET_VOLUME", "QUOTE_ASSET_VOLUME", "TICK_VOLUME", "LEG_VOLUME",
    "SYNTHETIC_PRICE_RANGE_PROXY", "NONE", "UNDECLARED",
})


def _rows() -> list[dict]:
    assert DECISIONS.is_file(), f"missing decisions: {DECISIONS}"
    out = []
    for i, line in enumerate(DECISIONS.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as e:
            raise AssertionError(f"line {i}: invalid JSON: {e}") from e
    return out


def _schema() -> dict:
    assert SCHEMA.is_file()
    return json.loads(SCHEMA.read_text(encoding="utf-8"))


def _fingerprint_by_path() -> dict[str, str]:
    fp = json.loads(FINGERPRINT.read_text(encoding="utf-8"))
    return {a["physical_path"]: a["sha256"] for a in fp["artifacts"]}


def test_schema_and_doctrine_exist():
    assert SCHEMA.is_file()
    assert DOCTRINE.is_file()
    schema = _schema()
    assert "UNRESOLVED" in json.dumps(schema)
    assert "approved_physical_path" in schema["properties"]
    text = DOCTRINE.read_text(encoding="utf-8")
    assert "cannot enter binding manifest" in text
    assert "synthetic" in text.lower()


def test_seeded_row_count_matches_logical_rollup():
    fp = json.loads(FINGERPRINT.read_text(encoding="utf-8"))
    n_logical = fp["n_logical_corpora"]
    rows = _rows()
    assert len(rows) == n_logical, (
        f"expected {n_logical} decision rows (one per logical corpus), got {len(rows)}"
    )
    ids = [r["logical_corpus_id"] for r in rows]
    assert len(ids) == len(set(ids)), "duplicate logical_corpus_id in decisions"


def test_required_fields_and_status_enum():
    required = set(_schema()["required"])
    for row in _rows():
        missing = required - set(row)
        assert not missing, f"{row.get('decision_id')}: missing {sorted(missing)}"
        assert row["decision_status"] in LEGAL_STATUS
        assert row["volume_semantic"] in VOLUME
        assert row["candidate_physical_artifacts"], "need ≥1 candidate"
        assert row["decision_evidence"], "need evidence refs"


def test_unresolved_and_frozen_cannot_set_approved_authority():
    """APPROVED authority fields are only for decision_status=APPROVED."""
    for row in _rows():
        if row["decision_status"] == "APPROVED":
            continue
        assert row.get("approved_physical_path") in (None, ""), (
            f"{row['decision_id']}: non-APPROVED must not set approved_physical_path"
        )
        assert row.get("approved_sha256") in (None, ""), (
            f"{row['decision_id']}: non-APPROVED must not set approved_sha256"
        )


def test_at_most_one_approved_binding_per_logical_id():
    approved: dict[str, list[str]] = {}
    for row in _rows():
        if row["decision_status"] != "APPROVED":
            continue
        if row.get("superseded_by"):
            continue
        approved.setdefault(row["logical_corpus_id"], []).append(row["decision_id"])
    multi = {k: v for k, v in approved.items() if len(v) > 1}
    assert not multi, f"multiple APPROVED bindings: {multi}"


def test_candidate_hashes_match_fingerprint_when_inventoried():
    by_path = _fingerprint_by_path()
    drifts = []
    for row in _rows():
        for c in row["candidate_physical_artifacts"]:
            path = c.get("physical_path")
            h = c.get("sha256")
            if not path or not h:
                continue
            if path not in by_path:
                continue
            if by_path[path] != h:
                drifts.append(
                    f"{row['logical_corpus_id']} {path}: decision {h[:12]}.. "
                    f"fingerprint {by_path[path][:12]}.."
                )
    assert not drifts, "candidate hash drift vs fingerprint:\n" + "\n".join(drifts)


def test_xauusd_phase1_frozen_candidate_binding():
    assert XAUUSD_PKG.is_file()
    text = XAUUSD_PKG.read_text(encoding="utf-8")
    for token in (
        "C-PINNED-LEGACY",
        "C-ROOT-EXTENDED",
        "FROZEN_CANDIDATE_PENDING_PHASE1_VALIDATION",
        "4d73f5ce",
    ):
        assert token in text, f"XAUUSD package missing {token!r}"

    xau = next(r for r in _rows() if r["logical_corpus_id"] == "XAUUSD_M15")
    assert xau["decision_status"] == "FROZEN_CANDIDATE_PENDING_PHASE1_VALIDATION"
    assert xau.get("approved_physical_path") in (None, "")
    assert xau.get("approved_sha256") in (None, "")
    fc = xau.get("phase1_frozen_candidate") or {}
    assert fc.get("physical_path") == "data/mt5/XAUUSD_M15.csv"
    assert fc.get("content_hash_sha256", "").startswith("4d73f5cebe33ec91")
    assert fc.get("rows") == 47275
    cids = {c.get("candidate_id") for c in xau["candidate_physical_artifacts"]}
    assert {"C-PINNED-LEGACY", "C-ROOT-EXTENDED", "C-QUARANTINE-TWIN", "C-YFINANCE"} <= cids
    by_cid = {c["candidate_id"]: c for c in xau["candidate_physical_artifacts"]}
    assert by_cid["C-ROOT-EXTENDED"]["sha256"] == by_cid["C-QUARANTINE-TWIN"]["sha256"]
    assert by_cid["C-ROOT-EXTENDED"]["sha256"] != by_cid["C-PINNED-LEGACY"]["sha256"]


def test_no_approved_rows_without_phase1_pass():
    """No corpus may be silently APPROVED; XAUUSD is frozen-candidate only."""
    approved = [r for r in _rows() if r["decision_status"] == "APPROVED"]
    assert not approved, (
        "must not auto-APPROVE; found: "
        + ", ".join(r["decision_id"] for r in approved)
    )
