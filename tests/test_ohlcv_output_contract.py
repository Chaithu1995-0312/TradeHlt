"""Validator for docs/governance/ohlcv-output-contract-2026-07-10.json (PASS B).

Enforces the contract's anti-aspiration invariants (C3):

  1. schema shape — required top-level blocks and per-guarantee fields;
  2. NO guarantee may be PROVEN on narrative evidence alone;
  3. NO guarantee may be PROVEN with runtime_enforcer 'none' unless it carries
     executable evidence (data-truth without an enforcer is at best measured,
     never guaranteed by machinery — the census IS executable evidence, but a
     status_note or the closure report must carry the caveat);
  4. fail-closed consistency — if ANY handoff-required guarantee is not PROVEN,
     the layer-audit manifest's closure_verdict MUST be BLOCKED:* (never CLOSED,
     never null once PASS B has run);
  5. the trust_status matrix keeps mutation REGISTRATION separate from
     DETECTION coverage (mutation_score may not silently read as complete).

Read-only; guards against silent hand-edits drifting the contract into
aspirational documentation.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = ROOT / "docs" / "governance" / "ohlcv-output-contract-2026-07-10.json"
MANIFEST = ROOT / "docs" / "governance" / "layer-audit-manifest.json"

REQUIRED_TOP = {
    "schema_version", "contract_id", "created_utc", "repository_commit",
    "guarantees", "handoff_required_guarantees", "handoff_gate_rule",
    "corpus_families", "forbidden_substitutions", "trust_status",
}
REQUIRED_GUARANTEE_FIELDS = {
    "id", "statement", "scope", "authoritative_producer", "runtime_enforcer",
    "evidence", "contradiction_refs", "guarantee_status",
}
LEGAL_STATUSES = {"PROVEN", "UNPROVEN", "CONTRADICTED"}
NON_NARRATIVE = {"executable", "static", "reproducible"}


def _contract() -> dict:
    assert CONTRACT.is_file(), f"missing contract: {CONTRACT}"
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_contract_schema_shape():
    c = _contract()
    missing = REQUIRED_TOP - set(c)
    assert not missing, f"contract missing top-level blocks: {sorted(missing)}"
    ids = set()
    for g in c["guarantees"]:
        gmissing = REQUIRED_GUARANTEE_FIELDS - set(g)
        assert not gmissing, f"{g.get('id')} missing fields: {sorted(gmissing)}"
        assert g["guarantee_status"] in LEGAL_STATUSES
        assert g["evidence"], f"{g['id']} has no evidence entries"
        ids.add(g["id"])
    dangling = set(c["handoff_required_guarantees"]) - ids
    assert not dangling, f"handoff-required ids not defined: {sorted(dangling)}"


def test_proven_requires_non_narrative_evidence():
    for g in _contract()["guarantees"]:
        if g["guarantee_status"] != "PROVEN":
            continue
        types = {e["type"] for e in g["evidence"]}
        assert types & NON_NARRATIVE, (
            f"{g['id']} is PROVEN on narrative evidence alone — forbidden (C3)"
        )


def test_proven_without_enforcer_needs_executable_evidence():
    for g in _contract()["guarantees"]:
        if g["guarantee_status"] != "PROVEN":
            continue
        enforcer = str(g["runtime_enforcer"]).strip().lower()
        if enforcer.startswith("none"):
            types = {e["type"] for e in g["evidence"]}
            assert "executable" in types, (
                f"{g['id']} PROVEN with no runtime enforcer requires "
                "executable evidence"
            )


def test_fail_closed_verdict_consistency():
    c = _contract()
    by_id = {g["id"]: g for g in c["guarantees"]}
    non_proven = [
        gid for gid in c["handoff_required_guarantees"]
        if by_id[gid]["guarantee_status"] != "PROVEN"
    ]
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    ohlcv = next(l for l in m["layers"] if l["layer_id"] == "OHLCV")
    verdict = ohlcv["closure_verdict"]
    if non_proven:
        assert isinstance(verdict, str) and verdict.startswith("BLOCKED:"), (
            f"handoff-required guarantees {non_proven} are not PROVEN but the "
            f"manifest verdict is {verdict!r} — fail-closed violation"
        )
    # contract's own verdict echo must agree with the manifest
    assert c["verdict_echo"].endswith(verdict), (
        "contract verdict_echo and manifest closure_verdict diverged"
    )


def test_mutation_registration_not_conflated_with_detection():
    ts = _contract()["trust_status"]
    for key in ("failure_classes_registered", "canonical_seeds_defined",
                "detectors_implemented", "clean_path_probes_green",
                "mutants_killed", "mutation_score"):
        assert key in ts, f"trust_status missing {key}"
    # registration complete does NOT imply detection complete
    if ts["detectors_implemented"] < ts["failure_classes_registered"]:
        assert ts["mutation_score"] == "NOT_MEASURED", (
            "detector gaps exist but mutation_score claims a measurement — "
            "registration is being conflated with detection coverage"
        )
