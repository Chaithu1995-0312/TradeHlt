"""Provenance Spine floor (MPA v1).

Enforces the three §C invariants, the backfill's one absolute rule (never EXPLICIT), and the
separation that keeps the 2026-08-26 research-DAG audit uncontaminated.

Every invariant here is proved by PLANTING the defect and asserting red — E-001: a test that cannot
fail is not enforcement. Several existing floors in this repository asserted a snapshot of the
pre-fix world and silently went red the moment someone fixed it; these assert invariants instead.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_SRC = _REPO / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from governance import provenance_derivation as D  # noqa: E402
from governance import provenance_resolver as R  # noqa: E402
from governance.provenance_record import (  # noqa: E402
    ATTESTED,
    DERIVATION_RULES,
    DERIVED,
    EXPLICIT,
    LEDGER,
    META_LINE,
    RESOLUTION_ORDER,
    SLOTS,
    SUBJECT_TYPES,
    ProvenanceError,
    _validate_line,
    build_binding,
    build_record,
    classify_chain,
    iter_records,
    tracked_paths,
)

_AUDIT_ARTIFACT = _REPO / "docs" / "governance" / "research_dag_provenance-2026-08-26.json"


def _explicit_contract(target: str = "MC-X-V1") -> dict:
    return build_binding(slot="contract", target_id=target, resolution=EXPLICIT, resolves=True,
                         witness=f"- Contract: {target}")


def _record(**over) -> dict:
    kwargs = dict(
        timestamp="2026-08-26T12:00:00+00:00",
        subject_type="FINDING",
        subject_id="F-999",
        source_path="docs/current-findings.md",
        slots={"contract": _explicit_contract()},
    )
    kwargs.update(over)
    return build_record(**kwargs)


# --- invariant 1: DERIVED requires a registered, versioned rule ---------------------------------


def test_derived_without_a_derivation_block_is_rejected() -> None:
    with pytest.raises(ProvenanceError, match="requires a derivation block"):
        build_binding(slot="contract", target_id="MC-X-V1", resolution=DERIVED, resolves=True)


def test_derived_naming_an_unregistered_rule_is_rejected() -> None:
    with pytest.raises(ProvenanceError, match="not a registered rule"):
        build_binding(slot="contract", target_id="MC-X-V1", resolution=DERIVED, resolves=True,
                      derivation={"rule_id": "D99_INVENTED", "rule_version": "1.0.0"})


def test_derived_with_a_wrong_rule_version_is_rejected() -> None:
    with pytest.raises(ProvenanceError, match="rule_version"):
        build_binding(slot="contract", target_id="MC-X-V1", resolution=DERIVED, resolves=True,
                      derivation={"rule_id": "D1_CONTRACT_CONTENT_HASH", "rule_version": "9.9.9"})


# --- invariant 2: ATTESTED requires who / when / basis / authority -------------------------------


@pytest.mark.parametrize("blank", ["by", "utc", "basis", "authority"])
def test_attested_with_any_empty_field_is_rejected(blank: str) -> None:
    attestation = {"by": "claude", "utc": "2026-08-26", "basis": "b", "authority": "user"}
    attestation[blank] = ""
    with pytest.raises(ProvenanceError, match="attestation missing"):
        build_binding(slot="evidence", target_id="docs/analysis/x.md", resolution=ATTESTED,
                      resolves=True, attestation=attestation)


def test_attestation_without_the_attested_class_is_rejected() -> None:
    """A binding cannot carry an attestation while claiming a stronger class."""
    with pytest.raises(ProvenanceError, match="attestation present"):
        build_binding(slot="evidence", target_id="docs/analysis/x.md", resolution=EXPLICIT,
                      resolves=True,
                      attestation={"by": "a", "utc": "b", "basis": "c", "authority": "d"})


# --- invariant 3: chain_class / chain_complete are DERIVED ---------------------------------------


@pytest.mark.parametrize("field,value", [("chain_class", "ATTESTED"), ("chain_complete", True)])
def test_caller_supplied_classification_is_rejected(field: str, value) -> None:
    tampered = dict(_record())
    tampered[field] = value
    with pytest.raises(ProvenanceError, match="disagrees with the bindings"):
        _validate_line(tampered)


def test_weakest_class_wins() -> None:
    """One ATTESTED slot makes an ATTESTED chain however many EXPLICIT slots sit beside it."""
    attested = build_binding(
        slot="evidence", target_id="docs/analysis/x.md", resolution=ATTESTED, resolves=True,
        attestation={"by": "c", "utc": "u", "basis": "b", "authority": "a"})
    rec = _record(slots={"contract": _explicit_contract(), "evidence": [attested]})
    assert rec["chain_class"] == ATTESTED, "an ATTESTED binding must drag the chain down"


def test_a_dangling_binding_does_not_complete_the_chain() -> None:
    """Recorded so the dangling citation stays visible — but it resolves nothing."""
    dangling = build_binding(slot="contract", target_id="MC-GHOST", resolution=EXPLICIT,
                             resolves=False, witness="- Contract: MC-GHOST")
    rec = _record(slots={"contract": dangling})
    assert rec["chain_class"] == "UNKNOWN" and rec["chain_complete"] is False


def test_unknown_is_recorded_by_omission_never_asserted() -> None:
    assert "UNKNOWN" not in RESOLUTION_ORDER
    with pytest.raises(ProvenanceError, match="recorded by OMITTING"):
        build_binding(slot="contract", target_id="x", resolution="UNKNOWN", resolves=False)


def test_grants_authority_is_pinned_false() -> None:
    """Mirrors economic_claims_allowed in measurement_result_log — provenance is not authority."""
    tampered = dict(_record())
    tampered["grants_authority"] = True
    with pytest.raises(ProvenanceError, match="grants_authority is const false"):
        _validate_line(tampered)


def test_session_log_is_not_a_subject_type() -> None:
    """1,052 of the audit's 1,170 decisions are session entries; admitting them would rebuild the
    audit's denominator problem inside the ledger."""
    assert "SESSION" not in SUBJECT_TYPES
    assert SUBJECT_TYPES == {"FINDING", "DECISION", "PROMOTION", "CLOSURE"}


# --- the backfill's absolute rule -----------------------------------------------------------------


def test_no_derivation_rule_can_emit_explicit() -> None:
    """The single most important assertion in this file.

    Backfill writes DERIVED or ATTESTED. If a rule could emit EXPLICIT, a reconstruction would be
    indistinguishable from a link the original record actually carried.
    """
    for kind, sid in R.all_subjects():
        for slot, value in D.derive(kind, sid).items():
            for b in (value if isinstance(value, list) else [value]):
                assert b["resolution"] != EXPLICIT, (
                    f"{kind}:{sid}.{slot} was backfilled as EXPLICIT by "
                    f"{(b.get('derivation') or {}).get('rule_id')}"
                )
                assert b["resolution"] in (DERIVED, ATTESTED)


def test_derivation_never_overwrites_an_explicit_binding() -> None:
    for kind, sid in R.all_subjects():
        chain = R.resolve(kind, sid)
        for slot in D.derive(kind, sid, chain):
            assert not chain.slots[slot].bindings, (
                f"{kind}:{sid}.{slot} already had an EXPLICIT binding and was still derived"
            )


def test_promotion_evidence_is_never_derived() -> None:
    """A promotion line carries nothing to derive FROM; deriving by date proximity would be the
    audit's own weakest inference (I3_DATE_COLOCATION). ATTESTED is the only honest path."""
    for kind, sid in R.all_subjects():
        if kind != "PROMOTION":
            continue
        assert "evidence" not in D.derive(kind, sid), f"PROMOTION:{sid} evidence was derived"


def test_every_registered_rule_is_implemented() -> None:
    implemented = {rid for _, rid, _ in D.SINGLE_RULES} | {rid for _, rid, _ in D.LIST_RULES}
    implemented.add("D2_EXECUTION_BY_CONTRACT")  # sequenced explicitly after D1
    assert implemented == set(DERIVATION_RULES), (
        "registry and implementations diverged: "
        f"{implemented.symmetric_difference(set(DERIVATION_RULES))}"
    )


def test_d1_content_hash_rule_stays_reachable(tmp_path: Path, monkeypatch) -> None:
    """D1 fires ZERO times on today's corpus — the six bare-sha256 Contract fields were rebound to
    ids on 2026-08-26. Kept reachable by fixture so it cannot rot into dead code, the same
    treatment the audit gives its own unexercised rule I4.
    """
    body = {"contract_id": "MC-FIXTURE-V1", "schema_version": "1.0.0"}
    raw = json.dumps(body, indent=2).encode("utf-8")
    inst = tmp_path / "MC-FIXTURE-V1.json"
    inst.write_bytes(raw)
    import hashlib
    digest = hashlib.sha256(raw).hexdigest()

    monkeypatch.setattr(R, "MC_DIR", tmp_path)
    chain = R.ChainResult(
        subject_type="FINDING", subject_id="F-FIX", source_path="x", source_sha256=None,
        slots={s: R.SlotResult(s, "UNRESOLVED", "") for s in SLOTS},
        chain_class="UNKNOWN", chain_complete=False,
    )
    chain.slots["contract"].details = {"sha256": digest}

    binding = D.d1_contract_content_hash("FINDING", "F-FIX", chain)
    assert binding is not None and binding["target_id"] == "MC-FIXTURE-V1"
    assert binding["resolution"] == DERIVED
    assert binding["derivation"]["rule_id"] == "D1_CONTRACT_CONTENT_HASH"

    chain.slots["contract"].details = {"sha256": "0" * 64}
    assert D.d1_contract_content_hash("FINDING", "F-FIX", chain) is None, \
        "a non-matching hash must resolve to nothing"


# --- the separation that protects the audit -------------------------------------------------------


def test_audit_extractor_does_not_read_the_ledger() -> None:
    """Structural guarantee, not a promise in prose.

    The audit classifies from the ORIGINAL artifacts. If it ever read this ledger, a backfilled
    DERIVED link would start moving the audit's UNKNOWN percentages and the cardinal rule
    ("GAPS ARE THE RESULT") would be silently broken.
    """
    src = (_REPO / "scripts" / "analysis" / "research_dag_provenance.py").read_text(
        encoding="utf-8")
    for token in ("provenance_ledger", "provenance_record", "provenance_derivation"):
        assert token not in src, (
            f"research_dag_provenance.py references {token!r} — the audit must classify from the "
            f"original artifacts only"
        )


def test_audit_artifact_carries_no_ledger_derived_numbers() -> None:
    """The audit's payload must contain nothing sourced from this ledger.

    Deliberately NOT a byte-comparison against the committed artifact: that would pin a SNAPSHOT
    and go red on ordinary corpus drift (a new manifest, a new SESSION LOG entry) while saying
    nothing about contamination. The invariant is that the audit's payload never carries a
    ledger-derived key. Byte-level determinism of the audit is owned by
    tests/test_research_dag_provenance.py::test_determinism_two_runs_are_byte_identical, and the
    structural guarantee is the test above.
    """
    if not _AUDIT_ARTIFACT.is_file():
        pytest.skip("audit artifact not present")
    payload = json.loads(_AUDIT_ARTIFACT.read_text(encoding="utf-8"))

    # Scope is the audit's COMPUTED output, not the whole file. The ledger's path legitimately
    # appears elsewhere in the payload as a declared file of the manifest that introduced it — the
    # audit measures this change like any other decision, and that is not contamination.
    computed = json.dumps({k: payload[k] for k in ("rollup",) if k in payload})
    for token in ("provenance_ledger", "chain_class", "PV-2026", "ATTESTED", "DERIVED"):
        assert token not in computed, (
            f"the audit's rollup contains {token!r} — its numbers must derive from the ORIGINAL "
            f"records, never from the provenance ledger"
        )

    # And its own class vocabulary is unchanged: EXPLICIT / INFERRED / UNKNOWN, never the ledger's.
    classes = set(payload["rollup"]["overall"]) if "overall" in payload.get("rollup", {}) else set()
    assert not (classes & {"DERIVED", "ATTESTED"}), (
        f"the audit adopted ledger classes {classes & {'DERIVED', 'ATTESTED'}} — the two "
        f"instruments must keep separate vocabularies"
    )


# --- resolution semantics ---------------------------------------------------------------------


def test_evidence_resolution_is_tracked_only() -> None:
    """An untracked path is RECORDED (so the dangling citation stays visible) but never resolves."""
    tracked = tracked_paths()
    assert tracked, "git ls-files returned nothing — the tracked-path instrument is broken"
    result = R._resolve_evidence("", ["docs/analysis/definitely-not-a-real-file.md"], tracked)
    assert result.bindings and result.bindings[0]["resolves"] is False
    assert result.status == "DANGLING"


def test_tracked_paths_fails_closed(monkeypatch) -> None:
    """With no git, NOTHING resolves — never everything."""
    def _boom(*a, **k):
        raise OSError("no git here")
    monkeypatch.setattr(subprocess, "run", _boom)
    assert tracked_paths() == frozenset()


def test_contract_resolution_is_tracked_only() -> None:
    """A contract must be GIT-TRACKED to resolve, exactly as an evidence path must.

    2026-08-27: until this fix the contract slot used a filesystem glob while the evidence slot
    used `git ls-files`, so an untracked instance resolved on the author's machine and vanished in
    every other clone. MC-ASYM (F-091) and MC-MRPRIOR (F-094) were in that state — two of the
    repository's four provenance-complete chains were complete on one disk only, and the resolver
    could not warn about the very gap it exists to surface. Same instrument as
    measurement_result_log.scanned_instance_paths, which was already git-ls-files-based.
    """
    ids = {"MC-GHOST-V1": "configs/research/measurement_contracts/instances/MC-GHOST-V1.json"}
    result = R._resolve_contract("MC-GHOST-V1", ids, frozenset())
    assert result.bindings and result.bindings[0]["resolves"] is False
    assert result.status == "DANGLING"
    assert any("UNTRACKED" in b for b in result.blockers)

    tracked = frozenset(ids.values())
    assert R._resolve_contract("MC-GHOST-V1", ids, tracked).bindings[0]["resolves"] is True


def test_every_cited_contract_is_tracked() -> None:
    """No finding may cite a contract that another clone cannot see.

    This is the check that would have caught MC-ASYM and MC-MRPRIOR before they reached a
    published finding. It is the F-071 class, which this repository keeps re-encountering.

    Scoped to CITED contracts, not every file on disk: `drafts/` is out of the sealed-instance
    universe by the same construction `measurement_result_log.scanned_instance_paths` already uses,
    and an unsealed draft nobody cites is free to be untracked. (One such draft exists today —
    `drafts/MC-SUJAN-XAUUSD-M15-V1.json`, which no finding cites and whose own test floor looks for
    it under `instances/`. Reported, not adopted.)
    """
    ids, _ = R.contract_ids_and_hashes()
    tracked = tracked_paths()

    cited = set()
    for block in R.finding_blocks().values():
        for name, value in R._FIELD_RE.findall(block):
            if name == "Contract" and value.strip().startswith(("MC-", "MP-")):
                cited.add(value.strip())

    assert cited, "no finding cites a contract — the parse is broken, not the repository"
    untracked = sorted(c for c in cited if ids.get(c) and ids[c] not in tracked)
    missing = sorted(c for c in cited if c not in ids)
    assert not untracked, (
        "findings cite measurement contracts that exist on disk but are UNTRACKED, so those "
        f"chains resolve to nothing from any other clone: {untracked}"
    )
    assert not missing, f"findings cite contracts that do not exist at all: {missing}"


def test_a_bare_sha256_contract_is_never_explicit() -> None:
    """Content-hash resolution is rule D1 (DERIVED). Shape is not a record."""
    result = R._resolve_contract("a" * 64, {})
    assert result.status == "UNRESOLVED" and not result.bindings
    assert result.details.get("sha256") == "a" * 64


def test_declared_but_unexecuted_is_a_first_class_state() -> None:
    """The contract/execution split is the architecture's central correction: the audit's single
    measurement-basis slot could not tell naming a contract from running it."""
    contract = R.SlotResult("contract", "RESOLVED", "names MC-NOPE",
                            bindings=[_explicit_contract("MC-NOPE")])
    result = R._resolve_execution(contract, {})
    assert result.status == "UNRESOLVED"
    assert "declared but has NO result line" in result.summary
    assert result.blockers and "measurement_result_log" in result.blockers[0]


def test_every_subject_type_resolves_without_raising() -> None:
    seen = set()
    for kind, sid in R.all_subjects():
        if kind in seen:
            continue
        seen.add(kind)
        chain = R.resolve(kind, sid)
        assert set(chain.slots) == set(SLOTS)
    assert seen == SUBJECT_TYPES, f"subject types not exercised: {SUBJECT_TYPES - seen}"


# --- ledger integrity ------------------------------------------------------------------------


def test_ledger_lines_all_validate() -> None:
    if not LEDGER.is_file():
        pytest.skip("ledger not created yet")
    for record in iter_records():
        _validate_line(record)


def test_ledger_meta_line_declares_the_contract() -> None:
    if not LEDGER.is_file():
        pytest.skip("ledger not created yet")
    first = json.loads(LEDGER.read_text(encoding="utf-8").splitlines()[0])
    assert first["kind"] == "meta" and first["grants_authority"] is False
    assert first["schema"] == META_LINE["schema"]


def test_ledger_holds_no_explicit_backfill() -> None:
    """Whole-ledger version of the backfill rule: a binding carrying a derivation or an attestation
    can never also claim EXPLICIT."""
    if not LEDGER.is_file():
        pytest.skip("ledger not created yet")
    for record in iter_records():
        for slot in SLOTS:
            value = record["slots"].get(slot)
            for b in (value if isinstance(value, list) else ([value] if value else [])):
                if b.get("derivation") or b.get("attestation"):
                    assert b["resolution"] != EXPLICIT, f"{record['record_id']}.{slot}"


_SCHEMA = _REPO / "configs" / "research" / "provenance" / "provenance_record.schema.json"


def test_schema_files_parse_and_are_frozen() -> None:
    """Both schemas exist, parse, and pin their version with a `const` — the frozen-schema pattern
    tests/test_measurement_contract.py already enforces for MC-*."""
    record_schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    assert record_schema["properties"]["schema"]["const"] == "provenance_ledger/1"
    assert record_schema["properties"]["grants_authority"]["const"] is False

    mx = json.loads((_SCHEMA.parent / "measurement_execution.schema.json").read_text("utf-8"))
    assert mx["properties"]["economic_claims_allowed"]["const"] is False


def test_ledger_conforms_to_the_frozen_schema() -> None:
    """Optional-import: `jsonschema` is not installed in this environment (the same reason
    test_measurement_contract's schema test is red). The Python validator in provenance_record
    is the always-on floor; this is the belt-and-braces check when the library is available."""
    jsonschema = pytest.importorskip("jsonschema")
    if not LEDGER.is_file():
        pytest.skip("ledger not created yet")
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    for record in iter_records():
        jsonschema.validate(record, schema)


def test_schema_rule_enum_matches_the_code_registry() -> None:
    """A rule addable in code but not in the schema (or vice versa) is a silent divergence."""
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    enum = set(
        schema["definitions"]["slotBinding"]["properties"]["derivation"]
        ["oneOf"][0]["properties"]["rule_id"]["enum"]
    )
    assert enum == set(DERIVATION_RULES), (
        f"schema rule enum and DERIVATION_RULES diverged: "
        f"{enum.symmetric_difference(set(DERIVATION_RULES))}"
    )


def test_classify_chain_is_pure() -> None:
    slots = {"contract": _explicit_contract()}
    assert classify_chain(slots) == classify_chain(slots)
    assert classify_chain({}) == ("UNKNOWN", False)
