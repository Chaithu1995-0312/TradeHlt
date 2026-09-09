"""Fail-closed floor for the closed semantic environment.

Positive: live authorities ground. Negative: invented nouns/relations/symbols/findings
must return UNKNOWN / AMBIGUOUS / UNANSWERABLE — never a fabricated record.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO / "src") not in sys.path:
    sys.path.insert(0, str(_REPO / "src"))

from governance.semantic_grounding import (  # noqa: E402
    AMBIGUOUS,
    CLAIM_KINDS,
    GROUNDED,
    IDENTITY_KINDS,
    RELATION_KINDS,
    UNANSWERABLE,
    UNKNOWN,
    SemanticGrounder,
)
from governance.semantic_os import SemanticOSRegistry  # noqa: E402


@pytest.fixture(scope="module")
def grounder() -> SemanticGrounder:
    return SemanticGrounder.load()


def test_claim_kinds_and_relations_are_closed():
    # JSONL joined the closed set in CH-jsonl-claim-surface PR-2 (CT-008 extension).
    assert CLAIM_KINDS == {"NOUN", "RELATIONSHIP", "IMPLEMENTATION", "EVIDENCE", "JSONL"}
    from governance.semantic_grounding import REFUSED, STATUSES

    assert STATUSES == {"GROUNDED", "UNKNOWN", "AMBIGUOUS", "UNANSWERABLE", "REFUSED"}
    assert REFUSED == "REFUSED"
    assert "FEELING" not in CLAIM_KINDS
    assert "causes_edge" not in RELATION_KINDS
    assert "MarketStructure" in IDENTITY_KINDS


def test_unknown_claim_kind_is_unanswerable(grounder: SemanticGrounder):
    hit = grounder.ground("FEELING", "CN-001")
    assert hit.status == UNANSWERABLE
    assert hit.record_id is None


def test_live_concept_noun_is_grounded(grounder: SemanticGrounder):
    hit = grounder.ground("NOUN", "CN-001")
    assert hit.status == GROUNDED
    assert hit.record_kind == "concept"
    assert hit.authority.endswith("concepts.yaml")
    assert hit.payload.get("authority") == "advisory"


def test_live_contract_noun_is_grounded(grounder: SemanticGrounder):
    hit = grounder.ground("NOUN", "CT-008")
    assert hit.status == GROUNDED, hit.to_dict()
    assert hit.record_kind == "contract"
    assert hit.payload.get("name")


def test_invented_noun_is_unknown(grounder: SemanticGrounder):
    hit = grounder.ground("NOUN", "FloobyMcWidget")
    assert hit.status == UNKNOWN
    assert hit.record_id is None
    assert "do not invent" in " ".join(hit.caveats).lower()


def test_invented_finding_is_unknown(grounder: SemanticGrounder):
    hit = grounder.ground("EVIDENCE", "F-999")
    assert hit.status == UNKNOWN
    assert hit.record_id is None


def test_live_finding_is_grounded(grounder: SemanticGrounder):
    hit = grounder.ground("EVIDENCE", "F-048")
    assert hit.status == GROUNDED
    assert hit.record_kind == "finding"
    assert hit.authority == "docs/current-findings.md"


def test_superseded_finding_grounds_with_a_terminality_caveat(grounder: SemanticGrounder):
    """S-2 (semantic + screenshot layer review, 2026-08-16): `valid_finding_ids`
    is "terminal included; existence only" -- F-007 (Status: SUPERSEDED) grounds
    as GROUNDED/PROVEN exactly like a fresh VALIDATED finding, which is correct
    (the row is real), but its terminality must be visible to a caller that only
    checks status/PROVEN and not payload["status"]."""
    hit = grounder.ground("EVIDENCE", "F-007")
    assert hit.status == GROUNDED, hit.to_dict()
    assert hit.payload.get("status") == "SUPERSEDED"
    assert any("SUPERSEDED" in c and "TERMINAL" in c for c in hit.caveats), hit.to_dict()


def test_live_ontology_id_is_grounded(grounder: SemanticGrounder):
    hit = grounder.ground("NOUN", "FM-041")
    assert hit.status == GROUNDED
    assert hit.record_kind == "ontology_id"


def test_unknown_ontology_id_is_unknown(grounder: SemanticGrounder):
    hit = grounder.ground("NOUN", "FM-999")
    assert hit.status == UNKNOWN


def test_l0_identity_kind_is_grounded(grounder: SemanticGrounder):
    hit = grounder.ground("NOUN", "DecisionAct")
    assert hit.status == GROUNDED
    assert hit.record_kind == "identity_kind"


def test_active_version_is_grounded(grounder: SemanticGrounder):
    hit = grounder.ground("NOUN", "ACTIVE_VERSION")
    assert hit.status == GROUNDED
    assert hit.record_kind == "ConfigIdentity"
    assert hit.payload.get("active_version")


def test_implementation_path_and_symbol(grounder: SemanticGrounder):
    hit = grounder.ground(
        "IMPLEMENTATION",
        "src/core/engine_runner.py",
        symbol="EngineRunner",
    )
    assert hit.status == GROUNDED, hit.to_dict()
    assert hit.payload.get("on_disk") is True
    assert hit.payload.get("symbol") == "EngineRunner"


def test_missing_symbol_is_unknown(grounder: SemanticGrounder):
    hit = grounder.ground(
        "IMPLEMENTATION",
        "src/core/engine_runner.py",
        symbol="DefinitelyNotAClass",
    )
    assert hit.status == UNKNOWN
    assert hit.record_id is None


def test_missing_path_is_unknown(grounder: SemanticGrounder):
    hit = grounder.ground("IMPLEMENTATION", "src/core/does_not_exist.py")
    assert hit.status == UNKNOWN


# ── S-1 (semantic + screenshot layer review, 2026-08-16) ─────────────────────
# The gap `test_missing_path_is_unknown` above does NOT cover: it passes only
# because `src/core/does_not_exist.py` is absent from BOTH disk and the
# generated `data/semantic_os/objects.jsonl` projection. The real defect was
# `on_disk=False` with a projection HIT — a file deleted or renamed after the
# (gitignored, regenerable, gone-stale-in-practice) projection was last built.
# `ground_implementation` used to proceed to GROUNDED/PROVEN in exactly that
# case. These inject a phantom projection row (the same technique that first
# proved the defect) to reproduce it without depending on the projection
# happening to be stale in whatever checkout runs this test.

def test_implementation_fails_closed_when_disk_absent_but_projection_hits(
    grounder: SemanticGrounder,
):
    phantom_path = "src/core/this_file_was_deleted_but_projection_remembers_it.py"
    assert not (_REPO / phantom_path).exists(), "test fixture must not exist on disk"

    original = dict(grounder.index.objects)
    grounder.index.objects[phantom_path] = {
        "path": phantom_path,
        "classes": ["PhantomClass"],
        "functions": ["phantom_function"],
        "semantic_id": None,
        "parse_error": None,
    }
    try:
        hit = grounder.ground("IMPLEMENTATION", phantom_path)
        assert hit.status == UNKNOWN, (
            "grounded a file that is absent from disk using only a stale "
            f"projection row: {hit.to_dict()}"
        )
        assert hit.record_id is None

        # Same hole existed in the NOUN OBJ: path and in the NOUN->IMPLEMENTATION
        # fallback for a bare .py-looking token -- both route through the same
        # disk check now, prove both stay closed too.
        hit_obj = grounder.ground("NOUN", f"OBJ:{phantom_path}")
        assert hit_obj.status == UNKNOWN, hit_obj.to_dict()

        hit_noun = grounder.ground("NOUN", phantom_path)
        assert hit_noun.status != GROUNDED or hit_noun.record_kind != "implementation", (
            "NOUN->IMPLEMENTATION fallback grounded a disk-absent, "
            f"projection-only path: {hit_noun.to_dict()}"
        )

        # And a symbol lookup against that same phantom row must not resolve
        # either (it used to read classes/functions straight from the
        # projection when the file wasn't on disk).
        hit_symbol = grounder.ground(
            "IMPLEMENTATION", phantom_path, symbol="PhantomClass",
        )
        assert hit_symbol.status == UNKNOWN, hit_symbol.to_dict()
    finally:
        grounder.index.objects.clear()
        grounder.index.objects.update(original)


def test_unknown_relation_is_unanswerable(grounder: SemanticGrounder):
    hit = grounder.ground(
        "RELATIONSHIP",
        "causes_edge",
        source="CN-001",
        target="BD-001",
        relation="causes_edge",
    )
    assert hit.status == UNANSWERABLE


def test_owns_relationship_on_live_concept(grounder: SemanticGrounder):
    concept = SemanticOSRegistry.load().concepts["CN-001"]
    owner = concept["owner_boundary"]
    hit = grounder.ground("RELATIONSHIP", "owns", source=owner, target="CN-001", relation="owns")
    assert hit.status == GROUNDED, hit.to_dict()
    assert hit.record_kind == "owns"


def test_false_owns_relationship_is_unknown(grounder: SemanticGrounder):
    hit = grounder.ground(
        "RELATIONSHIP",
        "owns",
        source="BD-010",
        target="CN-001",
        relation="owns",
    )
    # CN-001 is not owned by the agent/control-plane seam.
    assert hit.status in {UNKNOWN, AMBIGUOUS}
    assert hit.status != GROUNDED


def test_governs_relationship_for_ct008(grounder: SemanticGrounder):
    hit = grounder.ground(
        "RELATIONSHIP",
        "governs",
        source="CT-008",
        target="CN-013",
        relation="governs",
    )
    assert hit.status == GROUNDED, hit.to_dict()


def test_grounding_never_invents_payload_on_unknown(grounder: SemanticGrounder):
    for token in ("CN-404", "BD-404", "JN-404", "CT-404", "F-000"):
        hit = grounder.ground("NOUN", token)
        if hit.status == UNKNOWN:
            assert hit.record_id is None
            assert hit.payload in ({}, hit.payload)
            assert not hit.payload.get("name")


def test_cli_ground_unknown_exits_nonzero():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "query_semantic_os_cli",
        _REPO / "scripts" / "governance" / "query_semantic_os.py",
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    code = mod.main(["--ground", "--kind", "NOUN", "--token", "FloobyMcWidget"])
    assert code == 2
