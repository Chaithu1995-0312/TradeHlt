"""Mechanical floor for the Research Family Registry (Phase A).

Parses docs/governance/research_family_registry.json and checks:

  * schema, invariant, distinctions, closed-set vocabularies
  * all required families present, unique ids, all six L0-L5 cells each
  * evidence_mass <-> cell status coherence (a cell cannot claim historical work
    while declaring zero mass, and cannot claim an answer without a contract)
  * ANSWERED_UNDER_CONTRACT requires a contract_hash that resolves to a real
    contract file — so no cell can claim authority before Phase B exists
  * every finding in the CLAUDE.md 6.2 truths index is either bound to exactly
    one family cell or explicitly listed in excluded_claims (no silent drops)
  * no claim is owned by two families
  * provenance is present and honestly declares filesystem verification state
  * the registry is reachable from docs/knowledge-map.md

Read-only. Asserts nothing about whether any recorded conclusion is TRUE — the
registry records that work happened and what it aimed at, never that it holds.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "docs" / "governance" / "research_family_registry.json"
CLAUDE_MD = ROOT / "CLAUDE.md"
KNOWLEDGE_MAP = ROOT / "docs" / "knowledge-map.md"

LAYERS = ("L0", "L1", "L2", "L3", "L4", "L5")

REQUIRED_FAMILY_FIELDS = {
    "family_id",
    "object",
    "question",
    "canonical_instrument",
    "contract_profile",
    "runner",
    "cells",
    "script_evidence",
    "notes",
}

REQUIRED_FAMILY_IDS = {
    "RF-CRT-STRUCTURE",
    "RF-CRT-PARITY",
    "RF-SESSION-TIME",
    "RF-ZONE-GEOMETRY",
    "RF-GAUSSIAN",
    "RF-RR",
    "RF-NEURAL-CONSUMERS",
    "RF-SHAPES-TRAJECTORIES",
    "RF-REGIME-DYNAMICS",
    "RF-CARRY-BASIS",
    "RF-CROSS-SECTIONAL-PANEL",
    "RF-HTF",
    "RF-WEEKLY-CALENDAR",
    "RF-EXIT-COST-PATH",
    "RF-FEATURE-ONTOLOGY",
    "RF-LABEL-TRUTH",
}

# Which statuses a given evidence_mass may legally carry.
MASS_TO_ALLOWED_STATUS = {
    "high": {"UNVERIFIED_HISTORICAL", "IN_PROGRESS", "ANSWERED_UNDER_CONTRACT"},
    "med": {"UNVERIFIED_HISTORICAL", "IN_PROGRESS", "ANSWERED_UNDER_CONTRACT"},
    "low": {"UNVERIFIED_HISTORICAL", "IN_PROGRESS", "ANSWERED_UNDER_CONTRACT"},
    "none": {"GAP", "IN_PROGRESS", "ANSWERED_UNDER_CONTRACT"},
    "unknown": {"UNTESTED", "IN_PROGRESS", "ANSWERED_UNDER_CONTRACT"},
}


def _load() -> dict:
    assert REGISTRY.is_file(), f"missing registry: {REGISTRY}"
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def _families(reg: dict) -> list[dict]:
    fams = reg.get("families")
    assert isinstance(fams, list) and fams, "registry.families must be a non-empty list"
    return fams


def _by_id(reg: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for f in _families(reg):
        fid = f["family_id"]
        assert fid not in out, f"duplicate family_id: {fid}"
        out[fid] = f
    return out


def _claude_finding_ids() -> set[str]:
    """Finding ids from the CLAUDE.md 6.2 Repository Truths Index table rows."""
    text = CLAUDE_MD.read_text(encoding="utf-8")
    ids = set(re.findall(r"^\|\s*(F-\d{3})\s*\|", text, flags=re.MULTILINE))
    assert ids, "could not parse any F-0NN rows from the CLAUDE.md truths index"
    return ids


def _assigned_claims(reg: dict) -> dict[str, list[str]]:
    """claim_id -> list of 'FAMILY.LAYER' locations it is bound to."""
    out: dict[str, list[str]] = {}
    for f in _families(reg):
        for layer in LAYERS:
            for claim in f["cells"][layer].get("claims") or []:
                out.setdefault(claim, []).append(f"{f['family_id']}.{layer}")
    return out


def test_registry_schema_and_invariant():
    reg = _load()
    assert reg.get("schema_version"), "schema_version required"
    inv = (reg.get("invariant") or "").upper()
    assert "FAMILY IS AN OBJECT" in inv and "LAYER IS A QUESTION" in inv, (
        "registry must declare the object/question invariant"
    )
    assert "EVIDENCE MASS IS NOT AN ANSWER" in inv
    distinctions = " ".join(reg.get("distinctions") or [])
    for phrase in (
        "OBJECT != QUESTION",
        "SCOPE != FAMILY",
        "EVIDENCE MASS != ANSWERED",
        "ANSWERED != ANSWERED UNDER A CONTRACT",
    ):
        assert phrase in distinctions, f"missing distinction: {phrase}"


def test_layer_definitions_complete():
    reg = _load()
    layers = reg.get("layers") or {}
    for layer in LAYERS:
        assert layer in layers, f"missing layer definition: {layer}"
        for field in ("name", "question", "is_not", "atlas_matrix_column"):
            assert layers[layer].get(field), f"{layer}: missing {field}"


def test_execution_order_is_strict_and_records_the_rejected_alternative():
    reg = _load()
    order = reg.get("execution_order") or {}
    rule = (order.get("rule") or "").upper()
    assert "STRICT" in rule
    for layer in LAYERS:
        assert layer in rule, f"execution_order.rule must name {layer}"
    assert order.get("rejected_alternative"), (
        "the pivotality-first alternative was considered and rejected; record it "
        "so the decision is not silently re-litigated"
    )
    assert order.get("consequence"), (
        "strict ordering makes the L0 sufficiency criterion load-bearing; say so"
    )


def test_required_families_present_unique_ids():
    reg = _load()
    by_id = _by_id(reg)
    missing = REQUIRED_FAMILY_IDS - set(by_id)
    assert not missing, f"registry missing required family_ids: {sorted(missing)}"
    extra = set(by_id) - REQUIRED_FAMILY_IDS
    assert not extra, (
        f"unregistered family_ids present: {sorted(extra)} — add them to "
        "REQUIRED_FAMILY_IDS deliberately, never incidentally"
    )
    objects = [f["object"] for f in by_id.values()]
    assert len(objects) == len(set(objects)), "duplicate object names"


def test_family_fields_and_all_six_cells():
    reg = _load()
    for f in _families(reg):
        missing = REQUIRED_FAMILY_FIELDS - set(f)
        assert not missing, f"{f.get('family_id')}: missing fields {sorted(missing)}"
        assert f["question"].strip().endswith("?"), (
            f"{f['family_id']}: question must be an actual question"
        )
        assert isinstance(f["script_evidence"], list) and f["script_evidence"], (
            f"{f['family_id']}: script_evidence required (non-empty)"
        )
        cells = f["cells"]
        assert set(cells) == set(LAYERS), (
            f"{f['family_id']}: cells must be exactly {LAYERS}, got {sorted(cells)}"
        )


def test_cell_vocabularies_are_closed():
    reg = _load()
    allowed_status = set(reg["allowed_cell_status"])
    allowed_mass = set(reg["allowed_evidence_mass"])
    for f in _families(reg):
        for layer in LAYERS:
            cell = f["cells"][layer]
            where = f"{f['family_id']}.{layer}"
            assert cell["status"] in allowed_status, (
                f"{where}: invalid status {cell['status']!r}"
            )
            assert cell["evidence_mass"] in allowed_mass, (
                f"{where}: invalid evidence_mass {cell['evidence_mass']!r}"
            )
            assert isinstance(cell.get("claims"), list), f"{where}: claims must be a list"


def test_mass_and_status_are_coherent():
    """A cell cannot declare zero mass while claiming historical work, or vice versa."""
    reg = _load()
    for f in _families(reg):
        for layer in LAYERS:
            cell = f["cells"][layer]
            where = f"{f['family_id']}.{layer}"
            allowed = MASS_TO_ALLOWED_STATUS[cell["evidence_mass"]]
            assert cell["status"] in allowed, (
                f"{where}: evidence_mass={cell['evidence_mass']!r} is incompatible "
                f"with status={cell['status']!r}; allowed={sorted(allowed)}"
            )


def test_answered_requires_a_resolvable_contract():
    """ANSWERED_UNDER_CONTRACT is the only status carrying authority — it must be earned."""
    reg = _load()
    for f in _families(reg):
        for layer in LAYERS:
            cell = f["cells"][layer]
            if cell["status"] != "ANSWERED_UNDER_CONTRACT":
                assert "contract_hash" not in cell, (
                    f"{f['family_id']}.{layer}: contract_hash on a non-answered cell"
                )
                continue
            where = f"{f['family_id']}.{layer}"
            rel = cell.get("contract_artifact")
            assert cell.get("contract_hash"), f"{where}: ANSWERED requires contract_hash"
            assert rel, f"{where}: ANSWERED requires contract_artifact path"
            assert (ROOT / rel).is_file(), f"{where}: contract artifact missing: {rel}"


def test_no_claim_is_owned_by_two_families():
    reg = _load()
    shared = {c: locs for c, locs in _assigned_claims(reg).items() if len(locs) > 1}
    assert not shared, (
        "each claim must have exactly one owning family cell; shared: "
        + json.dumps(shared, indent=2, sort_keys=True)
    )


def test_every_claim_id_is_well_formed_and_real():
    reg = _load()
    known = _claude_finding_ids()
    for claim, locs in _assigned_claims(reg).items():
        assert re.fullmatch(r"F-\d{3}", claim), f"malformed claim id {claim!r} at {locs}"
        assert claim in known, (
            f"{claim} (at {locs}) is not in the CLAUDE.md truths index"
        )
    for entry in reg.get("excluded_claims") or []:
        assert re.fullmatch(r"F-\d{3}", entry["claim"]), f"malformed: {entry}"
        assert entry.get("reason", "").strip(), f"{entry['claim']}: exclusion needs a reason"


def test_every_indexed_finding_is_bound_or_explicitly_excluded():
    """No silent drops: the registry must account for every live finding."""
    reg = _load()
    known = _claude_finding_ids()
    assigned = set(_assigned_claims(reg))
    excluded = {e["claim"] for e in reg.get("excluded_claims") or []}

    overlap = assigned & excluded
    assert not overlap, f"claims both bound and excluded: {sorted(overlap)}"

    unaccounted = known - assigned - excluded
    assert not unaccounted, (
        f"findings neither bound to a family nor excluded: {sorted(unaccounted)} — "
        "bind them or record an explicit exclusion reason"
    )


def test_provenance_is_present_and_honest():
    reg = _load()
    prov = reg.get("provenance") or {}
    assert prov.get("source"), "provenance.source required"
    assert isinstance(prov.get("verified_against_filesystem"), bool), (
        "provenance.verified_against_filesystem must be an explicit bool"
    )
    if prov["verified_against_filesystem"] is False:
        assert prov.get("verification_blocked_by"), (
            "if unverified, say what blocks verification"
        )
    assert prov.get("cell_values_derived_from"), (
        "record which representation the cell values came from"
    )
    assert prov.get("claim_bindings_derived_from"), (
        "record that family assignment is authored judgement, not machine-derived"
    )


def test_unpartitioned_bundles_are_declared():
    """Families sharing one bundled source row must not read as independently measured."""
    reg = _load()
    bundles = " ".join(reg["provenance"].get("unpartitioned_bundles") or [])
    assert "UNPARTITIONED" in bundles.upper(), (
        "the bundled atlas row must be declared as unpartitioned"
    )
    for fid in ("RF-CARRY-BASIS", "RF-CROSS-SECTIONAL-PANEL", "RF-HTF", "RF-WEEKLY-CALENDAR"):
        note = _by_id(reg)[fid]["notes"].upper()
        assert "UNPARTITIONED" in note, (
            f"{fid}: inherits bundled mass; its notes must say UNPARTITIONED"
        )


def test_excluded_domains_declared():
    reg = _load()
    domains = reg.get("excluded_domains") or []
    assert len(domains) >= 3, "scope, system/governance, and layer-as-family exclusions required"
    for d in domains:
        assert d.get("domain") and d.get("reason"), f"incomplete exclusion: {d}"


def test_registry_is_reachable_from_knowledge_map():
    """An unreachable registry is a private note, not a record system."""
    text = KNOWLEDGE_MAP.read_text(encoding="utf-8").replace("\\", "/")
    assert "governance/research_family_registry.json" in text, (
        "docs/knowledge-map.md must link the research family registry so it is "
        "discoverable from the navigation hub"
    )


def test_seed_state_carries_no_authority():
    """At seed, nothing is answered and nothing is bound to a contract."""
    reg = _load()
    for f in _families(reg):
        assert f["contract_profile"] is None or isinstance(f["contract_profile"], str)
        assert f["canonical_instrument"] is None or isinstance(f["canonical_instrument"], str)
        for layer in LAYERS:
            cell = f["cells"][layer]
            if cell["status"] == "ANSWERED_UNDER_CONTRACT":
                # covered by test_answered_requires_a_resolvable_contract
                continue
            assert cell["status"] in {
                "UNTESTED",
                "UNVERIFIED_HISTORICAL",
                "IN_PROGRESS",
                "GAP",
            }
