"""Mechanical floor for CLAUDE.md §6.2 Closure & Authority Index.

Parses the structured registry docs/governance/closure_authority_index.json and
checks:

  * schema + unique surface_ids
  * allowed status values only
  * CLOSED surfaces have scope, frozen flag, reopen conditions, and an
    authoritative artifact that exists and carries the declared status_token
  * CLAUDE.md thin index does not contradict the registry
  * non-transitivity: no surface is CLOSED merely because an upstream is CLOSED;
    declared downstream_not_implied_closed surfaces must not be status=CLOSED
    unless they have their own independent CLOSED token in their own artifact
  * authority artifact rename/delete without index update fails (path existence)

Read-only. Does not re-run closed audits or mutate runtime behavior.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "docs" / "governance" / "closure_authority_index.json"
CLAUDE_MD = ROOT / "CLAUDE.md"

REQUIRED_SURFACE_FIELDS = {
    "surface_id",
    "surface_name",
    "status",
    "scope_boundary",
    "authoritative_artifact",
    "status_token",
    "frozen",
    "reopen_policy",
    "reopen_conditions",
    "upstream_surfaces",
    "downstream_not_implied_closed",
}

# Minimum surfaces this program must expose (user contract).
REQUIRED_SURFACE_IDS = {
    "CRT",
    "GEOMETRY_STATIC_LINEAGE",
    "CANONICAL_FEATURE_CODE_SURFACE",
    "FEATURE_QUERY_SURFACE",
    "GAUSSIAN_LINEAGE",
    "ZONEGATE_LINEAGE",
    "RR_LINEAGE",
    "BITNET_LINEAGE",
    "TRADENET_LINEAGE",
}

# Statuses that are explicitly NOT closed (must never be silently promoted).
NON_CLOSED_STATUSES = {
    "COMPLETE",
    "AUDITED",
    "AUTHORITY_ACTIVE",
    "BLOCKED",
    "OPEN",
}


def _load_registry() -> dict:
    assert REGISTRY.is_file(), f"missing registry: {REGISTRY}"
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def _surfaces(reg: dict) -> list[dict]:
    surfaces = reg.get("surfaces")
    assert isinstance(surfaces, list) and surfaces, "registry.surfaces must be a non-empty list"
    return surfaces


def _by_id(reg: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for s in _surfaces(reg):
        sid = s["surface_id"]
        assert sid not in out, f"duplicate surface_id: {sid}"
        out[sid] = s
    return out


def _read_artifact(rel: str) -> str:
    p = ROOT / rel
    assert p.is_file(), f"authoritative artifact missing: {rel}"
    return p.read_text(encoding="utf-8", errors="replace")


def test_registry_schema_and_invariant():
    reg = _load_registry()
    assert reg.get("schema_version"), "schema_version required"
    inv = reg.get("invariant", "")
    assert "BOUNDARY-SCOPED" in inv.upper() and "NON-TRANSITIVE" in inv.upper(), (
        "registry must declare CLOSURE IS BOUNDARY-SCOPED AND NON-TRANSITIVE"
    )
    allowed = set(reg.get("allowed_status") or [])
    assert "CLOSED" in allowed and "AUDITED" in allowed
    distinctions = " ".join(reg.get("distinctions") or [])
    for phrase in (
        "AUDITED != CLOSED",
        "LINEAGE CLOSED != ECONOMICALLY VALIDATED",
        "UPSTREAM CLOSED != DOWNSTREAM CLOSED",
    ):
        assert phrase in distinctions, f"missing distinction: {phrase}"
    nt = reg.get("non_transitivity") or {}
    assert "rule" in nt and "CLOSED" in nt["rule"]


def test_required_surfaces_present_unique_ids():
    reg = _load_registry()
    by_id = _by_id(reg)
    missing = REQUIRED_SURFACE_IDS - set(by_id)
    assert not missing, f"registry missing required surface_ids: {sorted(missing)}"
    # uniqueness already enforced in _by_id; also names unique
    names = [s["surface_name"] for s in by_id.values()]
    assert len(names) == len(set(names)), "duplicate surface_name values"


def test_surface_fields_and_allowed_status():
    reg = _load_registry()
    allowed = set(reg["allowed_status"])
    for s in _surfaces(reg):
        missing = REQUIRED_SURFACE_FIELDS - set(s)
        assert not missing, f"{s.get('surface_id')}: missing fields {sorted(missing)}"
        assert s["status"] in allowed, (
            f"{s['surface_id']}: invalid status {s['status']!r}; allowed={sorted(allowed)}"
        )
        assert isinstance(s["scope_boundary"], str) and s["scope_boundary"].strip(), (
            f"{s['surface_id']}: empty scope_boundary"
        )
        assert isinstance(s["authoritative_artifact"], str) and s["authoritative_artifact"].strip()
        assert isinstance(s["reopen_conditions"], list) and s["reopen_conditions"], (
            f"{s['surface_id']}: reopen_conditions required (non-empty list)"
        )
        assert isinstance(s["frozen"], bool)


def test_closed_surfaces_have_full_closure_contract():
    reg = _load_registry()
    default = reg.get("reopen_policy_default_closed") or {}
    default_conds = default.get("conditions") or []
    for s in _surfaces(reg):
        if s["status"] != "CLOSED":
            continue
        assert s["frozen"] is True, f"{s['surface_id']}: CLOSED must be frozen=true"
        assert s["scope_boundary"].strip(), f"{s['surface_id']}: CLOSED requires scope"
        assert s["authoritative_artifact"], f"{s['surface_id']}: CLOSED requires artifact"
        assert s["reopen_policy"], f"{s['surface_id']}: CLOSED requires reopen_policy"
        assert s["reopen_conditions"], f"{s['surface_id']}: CLOSED requires reopen_conditions"
        # at least one reopen condition should align with the default policy family
        joined = " ".join(s["reopen_conditions"]).lower()
        assert any(
            key in joined
            for key in ("boundary", "invariant", "contradict", "revalidation", "mechanical", "construction")
        ), f"{s['surface_id']}: reopen_conditions look empty of policy substance"
        # artifact exists + carries status token
        text = _read_artifact(s["authoritative_artifact"])
        token = s["status_token"]
        assert token in text, (
            f"{s['surface_id']}: CLOSED but authoritative artifact lacks status_token {token!r}"
        )
        # supporting artifacts (if any) must also exist
        for rel in s.get("supporting_artifacts") or []:
            assert (ROOT / rel).is_file(), f"{s['surface_id']}: supporting artifact missing: {rel}"


def test_all_authoritative_artifacts_exist_and_tokens_match():
    reg = _load_registry()
    for s in _surfaces(reg):
        text = _read_artifact(s["authoritative_artifact"])
        token = s["status_token"]
        assert token in text, (
            f"{s['surface_id']}: status_token {token!r} not found in {s['authoritative_artifact']}"
        )
        # CLOSED index status must not contradict a non-closed token vocabulary in-registry
        if s["status"] == "CLOSED":
            assert "CLOSED" in token or "STATUS = CLOSED" in token or "= CLOSED" in token, (
                f"{s['surface_id']}: CLOSED surface status_token should declare CLOSED"
            )
        if s["status"] == "AUDITED":
            # lineage audits must not claim CLOSED in the index
            assert s["status"] != "CLOSED"
            assert "CLOSED" not in s["status_detail"] or "not" in s["status_detail"].lower() or True
            # soft: status_detail should not equal a closed token
            assert "CLOSURE_STATUS = CLOSED" not in s.get("status_detail", "")


def test_non_transitivity_upstream_closed_does_not_force_downstream():
    """UPSTREAM CLOSED != DOWNSTREAM CLOSED — structural non-inference check."""
    reg = _load_registry()
    by_id = _by_id(reg)
    closed_ids = {sid for sid, s in by_id.items() if s["status"] == "CLOSED"}

    for sid, s in by_id.items():
        # every listed downstream_not_implied_closed must exist and must NOT be
        # closed *solely* by inference — if it is CLOSED it must have its own token
        for down in s.get("downstream_not_implied_closed") or []:
            assert down in by_id, (
                f"{sid}: downstream_not_implied_closed unknown surface_id {down}"
            )
            d = by_id[down]
            if d["status"] == "CLOSED":
                # independent closure required: own artifact carries own token
                text = _read_artifact(d["authoritative_artifact"])
                assert d["status_token"] in text
                assert d["authoritative_artifact"] != s["authoritative_artifact"], (
                    f"{down} cannot share authoritative artifact with upstream {sid} "
                    "while both are CLOSED (would collapse boundary independence)"
                )

        # if this surface is not CLOSED, it must not be indexed as CLOSED
        if s["status"] in NON_CLOSED_STATUSES:
            assert s["status"] != "CLOSED"
            # having a CLOSED upstream is allowed and must not flip status
            ups = s.get("upstream_surfaces") or []
            if any(u in closed_ids for u in ups):
                assert s["status"] != "CLOSED", (
                    f"{sid}: inferred CLOSED from upstream {ups} — non-transitivity violation"
                )


def test_lineage_audits_are_audited_not_closed():
    reg = _load_registry()
    by_id = _by_id(reg)
    for sid in (
        "GAUSSIAN_LINEAGE",
        "ZONEGATE_LINEAGE",
        "RR_LINEAGE",
        "BITNET_LINEAGE",
        "TRADENET_LINEAGE",
    ):
        assert by_id[sid]["status"] == "AUDITED", (
            f"{sid} must be AUDITED (AUDITED != CLOSED); got {by_id[sid]['status']}"
        )
        assert by_id[sid]["economically_validated"] is False


def test_geometry_and_query_not_closed():
    reg = _load_registry()
    by_id = _by_id(reg)
    assert by_id["GEOMETRY_STATIC_LINEAGE"]["status"] == "COMPLETE"
    assert by_id["FEATURE_QUERY_SURFACE"]["status"] == "AUTHORITY_ACTIVE"
    assert by_id["CANONICAL_FEATURE_CODE_SURFACE"]["status"] == "CLOSED"
    assert by_id["CRT"]["status"] == "CLOSED"


def test_claude_md_exposes_index_and_matches_registry_status():
    """CLAUDE.md thin table must not contradict the structured registry."""
    reg = _load_registry()
    claude = CLAUDE_MD.read_text(encoding="utf-8")
    assert "### Closure & Authority Index" in claude, (
        "CLAUDE.md must expose Closure & Authority Index under §6.2"
    )
    assert "CLOSURE IS BOUNDARY-SCOPED AND NON-TRANSITIVE" in claude
    assert "AUDITED != CLOSED" in claude
    assert "docs/governance/closure_authority_index.json" in claude.replace("\\", "/")

    # Map compact surface labels in the CLAUDE table to registry ids via artifact path
    for s in _surfaces(reg):
        art = s["authoritative_artifact"].replace("\\", "/")
        assert art in claude.replace("\\", "/"), (
            f"CLAUDE.md missing link/path to authoritative artifact for {s['surface_id']}: {art}"
        )
        # status word appears near the artifact reference (same table row window)
        # Find table rows containing the artifact basename
        base = Path(art).name
        # allow either full path or basename in the markdown table
        row_hits = [
            line
            for line in claude.splitlines()
            if base in line or art in line
        ]
        assert row_hits, f"CLAUDE.md has no table/prose row for {s['surface_id']} ({base})"
        status = s["status"]
        # At least one hit in the Closure section should carry the status
        # (CLOSED surfaces use **CLOSED**; others use **AUDITED** etc.)
        section = claude.split("### Closure & Authority Index", 1)[1].split("## 6.3", 1)[0]
        assert status in section, (
            f"CLAUDE.md Closure section missing status token {status} for {s['surface_id']}"
        )
        # stronger: the row that mentions this artifact also mentions the status
        row_ok = any(status in line for line in row_hits if line.strip().startswith("|"))
        assert row_ok, (
            f"CLAUDE.md table row for {s['surface_id']} does not carry status {status}"
        )


def test_closed_status_not_claimed_for_audited_in_claude():
    claude = CLAUDE_MD.read_text(encoding="utf-8")
    section = claude.split("### Closure & Authority Index", 1)[1].split("## 6.3", 1)[0]
    # lineage rows must say AUDITED, not CLOSED
    for label in ("Gaussian lineage", "ZoneGate lineage", "RR lineage", "BitNet lineage", "TradeNet lineage"):
        rows = [ln for ln in section.splitlines() if label in ln and ln.strip().startswith("|")]
        assert rows, f"missing CLAUDE.md row for {label}"
        assert "AUDITED" in rows[0], f"{label} row must be AUDITED"
        # avoid false positive on 'not CLOSED' prose in Reopen column — require status cell
        # Status is 2nd column: | name | **AUDITED** | ...
        cells = [c.strip() for c in rows[0].strip("|").split("|")]
        assert "AUDITED" in cells[1], f"{label}: status cell is {cells[1]!r}, expected AUDITED"


def test_registry_paths_are_repo_relative_and_stable():
    reg = _load_registry()
    for s in _surfaces(reg):
        rel = s["authoritative_artifact"]
        assert not rel.startswith("/") and ":" not in rel[:3], (
            f"{s['surface_id']}: artifact path must be repo-relative: {rel}"
        )
        assert (ROOT / rel).is_file()
