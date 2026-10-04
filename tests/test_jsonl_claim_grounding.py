"""JSONL claim grounding contract — the refusal surface fails closed.

GREEN_FLOOR member. CT-008 extension: `kind=JSONL` answers whether a JSONL stream may CLOSE a
claim, and returns a NAMED refusal (`REFUSED` + `CC-*`) rather than a plausible `GROUNDED`.

Structured as a PER-CC expected-status fixture, deliberately NOT `for cc in CAN: assert GROUNDED`
— a loop like that passes whenever the grounder is uniformly permissive, which is the failure it
is supposed to catch. Every CANNOT row must REFUSE; the CAN rows are asserted individually.

Spec: docs/governance/JSONL_CLAIM_SURFACE.md §6 (the normative 7-step algorithm).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from governance.jsonl_claim_catalog import load_catalog
from governance.semantic_grounding import (
    CLAIM_KINDS,
    REFUSED,
    STATUSES,
    SemanticGrounder,
    _contained_repo_path,
)

_REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def grounder() -> SemanticGrounder:
    return SemanticGrounder.load()


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


# --- closed vocabularies ------------------------------------------------------------------------


def test_jsonl_is_a_claim_kind_and_refused_is_a_status() -> None:
    assert "JSONL" in CLAIM_KINDS
    assert REFUSED in STATUSES
    # REFUSED must be its OWN status: collapsing it into UNANSWERABLE would erase the difference
    # between "outside the vocabulary" and "forbidden for this claim".
    assert REFUSED not in {"UNKNOWN", "UNANSWERABLE", "GROUNDED", "AMBIGUOUS"}


def test_unknown_claim_kind_still_unanswerable(grounder: SemanticGrounder) -> None:
    assert grounder.ground("FEELING", "x").status == "UNANSWERABLE"


def test_grounding_to_dict_carries_the_new_keys_on_every_kind(grounder: SemanticGrounder) -> None:
    old = grounder.ground("EVIDENCE", "F-048").to_dict()
    assert old["refusal_class"] is None and old["catalog_stream_status"] is None
    new = grounder.ground(
        "JSONL", "logs/crt_transitions.jsonl", relation="CC-L3-GLOBAL-UNIDENTIFIED"
    ).to_dict()
    assert new["refusal_class"] == "CC-L3-GLOBAL-UNIDENTIFIED"


# --- step 1/2: relation is required, and the vocabulary is closed --------------------------------


@pytest.mark.parametrize("relation", ["", "   ", "owns", "CC", "F-022", "cc-f022-contaminated"])
def test_missing_or_non_cc_relation_is_unanswerable(grounder: SemanticGrounder, relation: str) -> None:
    """Catalog existence is not a check — a bare stream token must never ground."""
    hit = grounder.ground("JSONL", "logs/crt_transitions.jsonl", relation=relation)
    assert hit.status == "UNANSWERABLE", relation


def test_invented_cc_id_is_unanswerable(grounder: SemanticGrounder) -> None:
    hit = grounder.ground("JSONL", "logs/x/opportunities.jsonl", relation="CC-TOTALLY-INVENTED")
    assert hit.status == "UNANSWERABLE"
    assert hit.record_id is None  # never invent a record id on a non-GROUNDED result


# --- step 3: join first --------------------------------------------------------------------------


def test_forbidden_join_refuses_even_when_the_relation_is_a_can(grounder: SemanticGrounder) -> None:
    """Two individually-true lines joined illegally is still a hallucination (F-069)."""
    hit = grounder.ground(
        "JSONL",
        "docs/current-findings.md",
        relation="CC-FINDING-EXPORT",  # a CAN that would otherwise GROUND
        source="producer:engine",
        target="producer:resolver",
    )
    assert hit.status == REFUSED
    assert hit.refusal_class == "CC-L3-FORBIDDEN-JOIN"


def test_join_only_call_with_empty_token_is_legal(grounder: SemanticGrounder) -> None:
    hit = grounder.ground(
        "JSONL", "", relation="CC-ENVELOPE-SHAPE", source="producer:engine", target="producer:resolver"
    )
    assert hit.status == REFUSED
    assert hit.refusal_class == "CC-L3-FORBIDDEN-JOIN"


def test_join_is_order_insensitive(grounder: SemanticGrounder) -> None:
    hit = grounder.ground(
        "JSONL", "", relation="CC-ENVELOPE-SHAPE", source="producer:resolver", target="producer:engine"
    )
    assert hit.refusal_class == "CC-L3-FORBIDDEN-JOIN"


def test_parquet_over_jsonl_join_refuses(grounder: SemanticGrounder) -> None:
    hit = grounder.ground(
        "JSONL",
        "",
        relation="CC-ENVELOPE-SHAPE",
        source="family:parquet_projection",
        target="family:runtime_untracked",
    )
    assert hit.refusal_class == "CC-PARQUET-PROJECTION"


def test_legal_pair_does_not_refuse(grounder: SemanticGrounder) -> None:
    """Non-vacuity: join_cc must not refuse everything."""
    hit = grounder.ground(
        "JSONL",
        "docs/current-findings.md",
        relation="CC-FINDING-EXPORT",
        source="STR-PROMOTION-LOG",
        target="STR-FINDINGS-EXPORT",
    )
    assert hit.status == "GROUNDED"


# --- step 4: every CANNOT refuses ----------------------------------------------------------------


def test_every_cannot_class_refuses(grounder: SemanticGrounder, catalog) -> None:
    """Exhaustive over the catalog — a new CANNOT row cannot be added without a refusal path."""
    cannots = [c["id"] for c in catalog.claim_classes if c["polarity"] == "CANNOT"]
    assert len(cannots) >= 12, "the P-FLOW-15 seed should carry at least 12 CANNOT classes"
    for cc_id in cannots:
        hit = grounder.ground("JSONL", "logs/crt_transitions.jsonl", relation=cc_id)
        assert hit.status == REFUSED, f"{cc_id} did not refuse"
        assert hit.refusal_class == cc_id
        assert hit.evidence_class != "PROVEN", f"{cc_id}: a refusal is never PROVEN evidence"


def test_cannot_refuses_even_on_an_uncatalogued_stream(grounder: SemanticGrounder) -> None:
    """A CANNOT is a property of the CLAIM, not of the stream it is aimed at."""
    hit = grounder.ground("JSONL", "logs/never_seen.jsonl", relation="CC-F022-CONTAMINATED")
    assert hit.status == REFUSED


def test_cannot_refuses_even_when_absent_from_that_streams_forbidden_cc(
    grounder: SemanticGrounder, catalog
) -> None:
    """`forbidden_cc` is documentation; omitting a CANNOT there must not soften it."""
    stream = catalog.stream_for_path("configs/promotion_log.jsonl")
    assert "CC-F022-CONTAMINATED" not in stream["forbidden_cc"]  # fixture guard
    hit = grounder.ground("JSONL", "configs/promotion_log.jsonl", relation="CC-F022-CONTAMINATED")
    assert hit.status == REFUSED


# --- step 6: a CAN on the wrong stream ------------------------------------------------------------


def test_can_not_in_allowed_cc_is_unanswerable(grounder: SemanticGrounder) -> None:
    """opportunities.jsonl does not close CC-FINDING-EXPORT — and must not REFUSE either."""
    hit = grounder.ground("JSONL", "logs/x/opportunities.jsonl", relation="CC-FINDING-EXPORT")
    assert hit.status == "UNANSWERABLE"
    assert hit.refusal_class is None


def test_uncatalogued_stream_on_a_can_is_unknown(grounder: SemanticGrounder) -> None:
    hit = grounder.ground("JSONL", "logs/not_catalogued.jsonl", relation="CC-ENVELOPE-SHAPE")
    assert hit.status == "UNKNOWN"


# --- step 7: the clone-visible CANs ----------------------------------------------------------------


def test_finding_export_grounds_from_primary_markdown(grounder: SemanticGrounder) -> None:
    """Must NOT require gitignored data/findings.jsonl — a fresh clone has to pass this."""
    hit = grounder.ground("JSONL", "docs/current-findings.md", relation="CC-FINDING-EXPORT")
    assert hit.status == "GROUNDED"
    assert hit.authority == "docs/current-findings.md"
    assert "data/findings.jsonl" not in hit.artifacts
    assert hit.payload["finding_count"] > 0
    assert "does_not_prove" in hit.payload  # the bound is stated in the payload


def test_finding_export_accepts_the_str_id(grounder: SemanticGrounder) -> None:
    assert grounder.ground("JSONL", "STR-FINDINGS-EXPORT", relation="CC-FINDING-EXPORT").status == "GROUNDED"


def test_finding_export_rejects_a_foreign_token(grounder: SemanticGrounder) -> None:
    assert grounder.ground("JSONL", "configs/promotion_log.jsonl", relation="CC-FINDING-EXPORT").status == "UNANSWERABLE"


def test_envelope_shape_grounds_without_the_gitignored_file(grounder: SemanticGrounder) -> None:
    """Shape of the contract, proved from committed sources; occupancy stays refused."""
    hit = grounder.ground("JSONL", "STR-F022-OPPORTUNITIES", relation="CC-ENVELOPE-SHAPE")
    assert hit.status == "GROUNDED"
    assert "src/events/event_fabric.py" in hit.artifacts
    assert "occupancy" in hit.payload["does_not_prove"]
    # the same stream still cannot close the economic claim
    assert grounder.ground(
        "JSONL", "STR-F022-OPPORTUNITIES", relation="CC-F022-CONTAMINATED"
    ).status == REFUSED


def test_promotion_log_grounds_and_states_its_bound(grounder: SemanticGrounder) -> None:
    hit = grounder.ground("JSONL", "configs/promotion_log.jsonl", relation="CC-PROMOTION-LOG")
    assert hit.status == "GROUNDED"
    assert hit.payload["record_count"] > 0
    assert "profitable" in hit.payload["does_not_prove"]


# --- CC-AGENT-AUDIT-RAN --------------------------------------------------------------------------


def test_agent_audit_requires_the_tool_name_as_source(grounder: SemanticGrounder) -> None:
    hit = grounder.ground("JSONL", "logs/agent_audit.jsonl", relation="CC-AGENT-AUDIT-RAN")
    assert hit.status == "UNANSWERABLE"


def test_agent_audit_absent_or_missing_line_is_unknown_never_refused(grounder: SemanticGrounder) -> None:
    """Absence is not a CANNOT class — a gitignored stream is UNKNOWN (F-071)."""
    hit = grounder.ground(
        "JSONL", "logs/agent_audit.jsonl", relation="CC-AGENT-AUDIT-RAN", source="tool.that.never.ran"
    )
    assert hit.status == "UNKNOWN"
    assert hit.refusal_class is None


def test_agent_audit_rejects_a_target(grounder: SemanticGrounder) -> None:
    hit = grounder.ground(
        "JSONL",
        "logs/agent_audit.jsonl",
        relation="CC-AGENT-AUDIT-RAN",
        source="truth.ground_claim",
        target="STR-PROMOTION-LOG",
    )
    assert hit.status in {"UNANSWERABLE", REFUSED}


# --- CC-MC-*: shape is not execution (F-083). Depth lives in test_measurement_result_log.py ---------


def test_mc_schema_shape_grounds_on_an_unrun_instance(grounder: SemanticGrounder) -> None:
    """UNRUN is a legal, honest SHAPE — declaring a contract is not running it."""
    hit = grounder.ground("JSONL", "MC-VCRT-XAUUSD-M15-V2", relation="CC-MC-SCHEMA-SHAPE")
    assert hit.status == "GROUNDED"
    assert hit.payload["trust_mt00"] == "UNRUN"


def test_mc_result_binding_refuses_an_unrun_instance(grounder: SemanticGrounder) -> None:
    """The same document that GROUNDS on shape must REFUSE on execution."""
    hit = grounder.ground("JSONL", "MC-VCRT-XAUUSD-M15-V2", relation="CC-MC-RESULT-BINDING")
    assert hit.status == REFUSED
    assert hit.refusal_class == "CC-MC-DECLARED-UNEXECUTED"


def test_mc_declared_unexecuted_is_a_cannot(grounder: SemanticGrounder) -> None:
    hit = grounder.ground("JSONL", "MC-VCRT-XAUUSD-M15-V2", relation="CC-MC-DECLARED-UNEXECUTED")
    assert hit.status == REFUSED


def test_mc_token_grammar_rejects_a_stream_path(grounder: SemanticGrounder) -> None:
    """The three CC-MC-* classes take an MC-* id or an instances/ path, never a JSONL stream."""
    assert grounder.ground(
        "JSONL", "logs/x/opportunities.jsonl", relation="CC-MC-SCHEMA-SHAPE"
    ).status == "UNANSWERABLE"


# --- PR-4: meaning is the ontology, never a log line ----------------------------------------------------


@pytest.mark.parametrize(
    "token",
    [
        "logs/crt_transitions.jsonl",   # an occupancy stream
        "data/findings.jsonl",          # a generated registry
        "configs/promotion_log.jsonl",  # a committed audit
        "logs/x/opportunities.jsonl",   # a contaminated detection stream
        "logs/never_catalogued.jsonl",  # not even in the catalog
    ],
)
def test_what_range_means_is_refused_against_every_jsonl(grounder: SemanticGrounder, token: str) -> None:
    """No JSONL defines a market state — meaning is the ontology (CLAUDE.md 6.6).

    Deliberately spans all four stream families plus an uncatalogued path: CC-MEANING-NOT-LOG is a
    property of the CLAIM, so no stream may soften it.
    """
    hit = grounder.ground("JSONL", token, relation="CC-MEANING-NOT-LOG")
    assert hit.status == REFUSED, token
    assert hit.refusal_class == "CC-MEANING-NOT-LOG"


def test_meaning_refusal_points_at_the_real_authority(grounder: SemanticGrounder, catalog) -> None:
    """The refusal is only useful if it names where meaning actually lives."""
    row = catalog.claim_class("CC-MEANING-NOT-LOG")
    assert row["meaning_authority"], "CC-MEANING-NOT-LOG must point at an ontology id"
    for ident in row["meaning_authority"]:
        assert grounder.ground("NOUN", ident).status == "GROUNDED", ident


def test_the_ontology_still_answers_what_a_state_means(grounder: SemanticGrounder) -> None:
    """Non-vacuity: the refusal redirects to a path that WORKS, it is not a dead end."""
    assert grounder.ground("NOUN", "SEM-011").status == "GROUNDED"


def test_every_stream_declares_a_meaning_authority(catalog) -> None:
    """No stream may be silent about where its meaning comes from."""
    for row in catalog.streams:
        value = row["meaning_authority"]
        assert value == "INVENTORY_NOT_MARKET" or (isinstance(value, list) and value), row["id"]


# --- path containment -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "token",
    [
        r"C:\Windows\System32\config",
        "C:/Windows/System32/config",
        "../../secret",
        "../../../etc/passwd",
        "/etc/passwd",
    ],
)
def test_path_escape_tokens_are_unknown_and_never_opened(grounder: SemanticGrounder, token: str) -> None:
    hit = grounder.ground("JSONL", token, relation="CC-ENVELOPE-SHAPE")
    assert hit.status in {"UNKNOWN", "UNANSWERABLE"}, token
    assert hit.status != "GROUNDED"


def test_contained_repo_path_rejects_escapes() -> None:
    assert _contained_repo_path("docs/current-findings.md") is not None
    assert _contained_repo_path("C:/Windows/System32/config") is None
    assert _contained_repo_path("../../secret") is None
    assert _contained_repo_path("") is None
    assert _contained_repo_path("a" + chr(0) + "b") is None


# --- the four original kinds are untouched -------------------------------------------------------------


@pytest.mark.parametrize(
    "kind,token,kwargs",
    [
        ("NOUN", "CN-001", {}),
        ("NOUN", "CT-008", {}),
        ("EVIDENCE", "F-048", {}),
        ("IMPLEMENTATION", "src/core/engine_runner.py", {"symbol": "EngineRunner"}),
    ],
)
def test_existing_claim_kinds_still_ground(grounder: SemanticGrounder, kind, token, kwargs) -> None:
    """Regression: adding a fifth status must not perturb the four original kinds."""
    assert grounder.ground(kind, token, **kwargs).status == "GROUNDED"


# --- agent envelope --------------------------------------------------------------------------------


def test_agent_tool_preserves_grounding_status_before_the_envelope_clobber() -> None:
    """The F-079 guard: `status` becomes "ok", so REFUSED must survive in `grounding_status`."""
    from agent.modes.truth_mode import _ground_claim

    out = _ground_claim(
        kind="JSONL", token="logs/crt_transitions.jsonl", relation="CC-L3-GLOBAL-UNIDENTIFIED"
    )
    assert out["grounding_status"] == "REFUSED"
    assert out["refusal_class"] == "CC-L3-GLOBAL-UNIDENTIFIED"
    assert out["passed"] is False
    assert out["status"] == "ok"  # envelope contract unchanged for existing consumers


def test_agent_tool_grounded_path_also_reports_grounding_status() -> None:
    from agent.modes.truth_mode import _ground_claim

    out = _ground_claim(kind="JSONL", token="docs/current-findings.md", relation="CC-FINDING-EXPORT")
    assert out["grounding_status"] == "GROUNDED"
    assert out["passed"] is True


def test_agent_tool_join_only_passes_empty_token_through() -> None:
    from agent.modes.truth_mode import _ground_claim

    out = _ground_claim(
        kind="JSONL", relation="CC-FINDING-EXPORT", source="producer:engine", target="producer:resolver"
    )
    assert out["grounding_status"] == "REFUSED"
    assert out["token"] == ""  # not coalesced to the CC id


def test_agent_tool_kind_desc_advertises_jsonl() -> None:
    import agent.modes.truth_mode  # noqa: F401 - registers the tool
    from agent.tool_registry import get_tool

    desc = get_tool("truth.ground_claim").args_schema["kind"]["desc"]
    assert "JSONL" in desc


# --- CLI -----------------------------------------------------------------------------------------------


def test_cli_join_only_without_token_reaches_the_grounder() -> None:
    """Pin for the `args.token or args.relation` coalesce that would break join-only calls."""
    import sys

    sys.path.insert(0, str(_REPO / "scripts" / "governance"))
    from importlib import util

    spec = util.spec_from_file_location(
        "_qsos", _REPO / "scripts" / "governance" / "query_semantic_os.py"
    )
    mod = util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rc = mod.main(
        [
            "--ground",
            "--kind",
            "JSONL",
            "--relation",
            "CC-FINDING-EXPORT",
            "--source",
            "producer:engine",
            "--dest",
            "producer:resolver",
        ]
    )
    assert rc == 2  # REFUSED is a non-zero exit


def test_cli_exit_zero_only_on_grounded() -> None:
    from importlib import util

    spec = util.spec_from_file_location(
        "_qsos2", _REPO / "scripts" / "governance" / "query_semantic_os.py"
    )
    mod = util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.main(
        ["--ground", "--kind", "JSONL", "--token", "docs/current-findings.md",
         "--relation", "CC-FINDING-EXPORT"]
    ) == 0
    assert mod.main(
        ["--ground", "--kind", "JSONL", "--token", "logs/crt_transitions.jsonl",
         "--relation", "CC-L3-GLOBAL-UNIDENTIFIED"]
    ) == 2
