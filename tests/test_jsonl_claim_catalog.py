"""JSONL claim catalog contract — the CAN/CANNOT vocabulary is closed, self-consistent, faithful.

GREEN_FLOOR member. Mirrors tests/test_findings_export.py (PRIMARY -> GENERATED derived view,
build-twice determinism, hand-edit guard) for docs/governance/jsonl_claim_catalog.yaml.

The load-bearing tests here are the NEGATIVE ones: a catalog that admits a CANNOT class, globs a
committed registry, or overlaps two refusal ids on one join pair must FAIL. A validator that only
accepts good input is not enforcement (E-001).

Spec: docs/governance/JSONL_CLAIM_SURFACE.md. Schema: docs/reference/schemas.md §9.15.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
import yaml

from governance.jsonl_claim_catalog import (
    ADMITTED,
    CATALOG_STREAM_STATUSES,
    FAMILIES,
    GLOB_FAMILIES,
    INVENTORY_NOT_MARKET,
    META_LINE,
    NOT_ADMITTED,
    REFUSED,
    SCHEMA_VERSION,
    UNKNOWN_CLASS,
    UNKNOWN_STREAM,
    Catalog,
    CatalogError,
    export,
    load_catalog,
    render,
)

_REPO = Path(__file__).resolve().parents[1]
_CATALOG_YAML = _REPO / "docs" / "governance" / "jsonl_claim_catalog.yaml"
_EXPORT_PATH = _REPO / "data" / "jsonl_claim_catalog.jsonl"


@pytest.fixture(scope="module")
def raw() -> dict:
    return yaml.safe_load(_CATALOG_YAML.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def catalog() -> Catalog:
    return load_catalog(_CATALOG_YAML)


@pytest.fixture(scope="module", autouse=True)
def _ensure_exported(catalog: Catalog) -> None:
    """data/ is gitignored — a fresh checkout has no projection; regenerate deterministically."""
    if not _EXPORT_PATH.exists():
        export(_EXPORT_PATH, catalog)
    assert _EXPORT_PATH.exists(), f"export failed to produce {_EXPORT_PATH}"


def _mutate(raw: dict, fn) -> dict:
    """Deep-copy the real catalog, apply a planted defect, return it."""
    data = copy.deepcopy(raw)
    fn(data)
    return data


# --- shape ------------------------------------------------------------------------------------


def test_primary_catalog_loads_and_is_advisory(catalog: Catalog) -> None:
    assert catalog.schema_version == SCHEMA_VERSION
    # PINNED: this surface never grants G001 / promotion / production authority (CLAUDE.md §6.5).
    assert catalog.authority == "advisory"
    assert catalog.streams and catalog.claim_classes and catalog.forbidden_joins


def test_no_g001_or_promotion_keys_anywhere(raw: dict) -> None:
    """A refusal surface must not smuggle in economic authority."""
    text = json.dumps(raw).lower()
    for forbidden in ("economic_claims_allowed: true", "g001_improvement", "promote:"):
        assert forbidden not in text, f"catalog must not carry {forbidden!r}"


def test_ids_are_unique_and_namespaced(catalog: Catalog) -> None:
    stream_ids = [s["id"] for s in catalog.streams]
    cc_ids = [c["id"] for c in catalog.claim_classes]
    assert len(set(stream_ids)) == len(stream_ids)
    assert len(set(cc_ids)) == len(cc_ids)
    assert all(i.startswith("STR-") for i in stream_ids)
    assert all(i.startswith("CC-") for i in cc_ids)


def test_closed_enums_hold(catalog: Catalog) -> None:
    for row in catalog.streams:
        assert row["family"] in FAMILIES
        assert row["catalog_stream_status"] in CATALOG_STREAM_STATUSES
    for row in catalog.claim_classes:
        assert row["polarity"] in {"CAN", "CANNOT"}


def test_catalog_status_vocabulary_is_named_apart_from_checkresult(catalog: Catalog) -> None:
    """§11 census labels are NOT identity.check statuses. PRESERVED must never appear here."""
    assert "PRESERVED" not in CATALOG_STREAM_STATUSES
    assert "CONTAMINATED" in CATALOG_STREAM_STATUSES  # legal here, illegal on a CheckResult
    for row in catalog.streams:
        assert row["catalog_stream_status"] != "PRESERVED"


def test_glob_rules_by_family(catalog: Catalog) -> None:
    """A registry is exactly one file; only runtime/parquet trees may glob."""
    for row in catalog.streams:
        has_glob = any(ch in row["path"] for ch in "*?[")
        if has_glob:
            assert row["family"] in GLOB_FAMILIES, f"{row['id']}: {row['family']} may not glob"


def test_both_polarities_present_and_seed_classes_exist(catalog: Catalog) -> None:
    """The P-FLOW-15 seed — every CANNOT the LLM actually trips over must be nameable."""
    ids = {c["id"] for c in catalog.claim_classes}
    for required in (
        "CC-F022-CONTAMINATED",
        "CC-L3-GLOBAL-UNIDENTIFIED",
        "CC-L1-UNIDENTIFIED",
        "CC-L3-FORBIDDEN-JOIN",
        "CC-PARQUET-PROJECTION",
        "CC-PRESENCE-NOT-G001",
        "CC-TV-NOT-IN-STREAM",
        "CC-ULTRON-NOT-IN-BACKTEST",
        "CC-MEANING-NOT-LOG",
        "CC-ILLEGAL-JOIN",
        "CC-MC-DECLARED-UNEXECUTED",
        "CC-L5-UNIDENTIFIED",
        "CC-FINDING-EXPORT",
        "CC-HYPOTHESIS-REGISTRY",
        "CC-SEMANTIC-OS",
        "CC-SCRIPT-REGISTRY",
        "CC-PROMOTION-LOG",
        "CC-ENVELOPE-SHAPE",
        "CC-AGENT-AUDIT-RAN",
        "CC-MC-SCHEMA-SHAPE",
        "CC-MC-RESULT-BINDING",
    ):
        assert required in ids, f"seed class missing from the catalog: {required}"


def test_stream_cc_references_resolve(catalog: Catalog) -> None:
    known = {c["id"] for c in catalog.claim_classes}
    for row in catalog.streams:
        assert set(row["allowed_cc"]) <= known, row["id"]
        assert set(row["forbidden_cc"]) <= known, row["id"]


def test_forbidden_cc_is_subset_of_cannot_and_allowed_cc_is_disjoint(catalog: Catalog) -> None:
    cannot = {c["id"] for c in catalog.claim_classes if c["polarity"] == "CANNOT"}
    for row in catalog.streams:
        assert set(row["forbidden_cc"]) <= cannot, f"{row['id']}: forbidden_cc must all be CANNOT"
        assert not (set(row["allowed_cc"]) & cannot), f"{row['id']}: a CANNOT cannot be admitted"


def test_meaning_authority_is_sentinel_or_a_real_id(catalog: Catalog) -> None:
    """No invented SEM/CN/FM ids. Every pointer must ground as a NOUN (CLAUDE.md §6.7)."""
    from governance.semantic_grounding import SemanticGrounder

    grounder = SemanticGrounder.load()
    rows = list(catalog.streams) + list(catalog.claim_classes)
    for row in rows:
        value = row["meaning_authority"]
        if value == INVENTORY_NOT_MARKET:
            continue
        assert isinstance(value, list), f"{row['id']}: meaning_authority must be the sentinel or a list"
        for ident in value:
            hit = grounder.ground("NOUN", ident)
            assert hit.status == "GROUNDED", f"{row['id']}: meaning_authority {ident} is {hit.status}"


def test_join_endpoints_are_in_the_closed_grammar(catalog: Catalog) -> None:
    stream_ids = {s["id"] for s in catalog.streams}
    for row in catalog.forbidden_joins:
        for endpoint in (row["source_str"], row["target_str"]):
            assert (
                endpoint in {"producer:engine", "producer:resolver"}
                or endpoint in stream_ids
                or (endpoint.startswith("family:") and endpoint.split(":", 1)[1] in FAMILIES)
            ), endpoint


# --- behaviour --------------------------------------------------------------------------------


def test_stream_for_path_resolves_every_form(catalog: Catalog) -> None:
    assert catalog.stream_for_path("logs/XAUUSD/r1/opportunities.jsonl")["id"] == "STR-F022-OPPORTUNITIES"
    assert catalog.stream_for_path("configs/promotion_log.jsonl")["id"] == "STR-PROMOTION-LOG"
    assert catalog.stream_for_path("STR-PROMOTION-LOG")["id"] == "STR-PROMOTION-LOG"
    # PRIMARY source of a generated registry resolves to that registry's row.
    assert catalog.stream_for_path("docs/current-findings.md")["id"] == "STR-FINDINGS-EXPORT"
    # Windows separators normalize.
    assert catalog.stream_for_path(r"logs\XAUUSD\r1\opportunities.jsonl")["id"] == "STR-F022-OPPORTUNITIES"
    # Fail closed on anything uncatalogued.
    assert catalog.stream_for_path("logs/not_a_catalogued_stream.jsonl") is None
    assert catalog.stream_for_path("") is None


def test_exact_match_wins_over_glob(catalog: Catalog) -> None:
    """A committed registry must never be captured by a '**' runtime pattern."""
    hit = catalog.stream_for_path("configs/promotion_log.jsonl")
    assert hit["family"] == "committed_audit"


def test_join_cc_is_order_insensitive_and_fails_closed(catalog: Catalog) -> None:
    assert catalog.join_cc("producer:engine", "producer:resolver") == "CC-L3-FORBIDDEN-JOIN"
    assert catalog.join_cc("producer:resolver", "producer:engine") == "CC-L3-FORBIDDEN-JOIN"
    assert catalog.join_cc("STR-F022-OPPORTUNITIES", "STR-BACKTEST-TRADES") == "CC-ILLEGAL-JOIN"
    assert catalog.join_cc("producer:engine", "") is None
    assert catalog.join_cc("", "") is None
    assert catalog.join_cc("STR-PROMOTION-LOG", "STR-FINDINGS-EXPORT") is None


def test_admissibility_matrix(catalog: Catalog) -> None:
    opp = catalog.stream_for_path("logs/x/opportunities.jsonl")
    findings = catalog.stream_for_path("data/findings.jsonl")
    # CANNOT is always REFUSED — even on a stream that omits it from forbidden_cc.
    assert catalog.admissibility(opp, "CC-F022-CONTAMINATED") == REFUSED
    assert catalog.admissibility(findings, "CC-F022-CONTAMINATED") == REFUSED
    assert catalog.admissibility(None, "CC-F022-CONTAMINATED") == REFUSED
    # CAN in allowed_cc -> ADMITTED (which is NOT grounded).
    assert catalog.admissibility(opp, "CC-ENVELOPE-SHAPE") == ADMITTED
    # CAN listed on a DIFFERENT stream -> NOT_ADMITTED, not GROUNDED and not REFUSED.
    assert catalog.admissibility(opp, "CC-FINDING-EXPORT") == NOT_ADMITTED
    # Invented class -> UNKNOWN_CLASS. Unknown stream on a CAN -> UNKNOWN_STREAM.
    assert catalog.admissibility(opp, "CC-TOTALLY-INVENTED") == UNKNOWN_CLASS
    assert catalog.admissibility(None, "CC-FINDING-EXPORT") == UNKNOWN_STREAM


# --- GENERATED projection ---------------------------------------------------------------------


def test_render_is_deterministic(catalog: Catalog) -> None:
    assert render(catalog) == render(catalog)


def test_meta_line_identifies_the_generator(catalog: Catalog) -> None:
    first = json.loads(render(catalog).splitlines()[0])
    assert first == META_LINE
    assert first["kind"] == "meta"
    assert first["generated_by"].startswith("src/governance/jsonl_claim_catalog.py")
    assert first["authority"] == "advisory"


def test_primary_yaml_carries_no_generated_by(raw: dict) -> None:
    """generated_by lives ONLY on the GENERATED meta line — the PRIMARY is hand-authored."""
    assert "generated_by" not in raw


def test_every_record_is_projected_exactly_once(catalog: Catalog) -> None:
    lines = render(catalog).splitlines()[1:]
    recs = [json.loads(line) for line in lines]
    assert len(recs) == len(catalog.streams) + len(catalog.claim_classes) + len(catalog.forbidden_joins)
    kinds = {r["record_kind"] for r in recs}
    assert kinds == {"stream", "claim_class", "forbidden_join"}


def test_on_disk_export_is_not_hand_edited(catalog: Catalog) -> None:
    """The GENERATED guard: the on-disk projection equals a fresh render of the PRIMARY."""
    assert _EXPORT_PATH.read_text(encoding="utf-8") == render(catalog), (
        "data/jsonl_claim_catalog.jsonl differs from a fresh render — it was hand-edited or is "
        "stale; regenerate via: python -m governance.jsonl_claim_catalog (§6.2: never hand-edit)"
    )


# --- planted defects (the load-bearing half) ----------------------------------------------------


def test_rejects_cannot_class_in_allowed_cc(raw: dict) -> None:
    """The invariant the whole surface rests on: a refusal can never be admitted."""
    def plant(d: dict) -> None:
        d["streams"][0]["allowed_cc"].append("CC-F022-CONTAMINATED")

    with pytest.raises(CatalogError, match="allowed_cc lists CANNOT"):
        load_catalog_from(_mutate(raw, plant))


def test_rejects_glob_on_a_committed_registry(raw: dict) -> None:
    def plant(d: dict) -> None:
        for row in d["streams"]:
            if row["family"] == "committed_audit":
                row["path"] = "configs/**/*.jsonl"
                return
        raise AssertionError("fixture drift: no committed_audit stream to mutate")

    with pytest.raises(CatalogError, match="requires an exact path"):
        load_catalog_from(_mutate(raw, plant))


def test_rejects_can_class_in_forbidden_cc(raw: dict) -> None:
    def plant(d: dict) -> None:
        d["streams"][0]["forbidden_cc"].append("CC-PROMOTION-LOG")

    with pytest.raises(CatalogError, match="subset of CANNOT"):
        load_catalog_from(_mutate(raw, plant))


def test_rejects_unknown_family(raw: dict) -> None:
    def plant(d: dict) -> None:
        d["streams"][0]["family"] = "some_new_family"

    with pytest.raises(CatalogError, match="unknown family"):
        load_catalog_from(_mutate(raw, plant))


def test_rejects_duplicate_ids(raw: dict) -> None:
    def plant(d: dict) -> None:
        d["claim_classes"].append(copy.deepcopy(d["claim_classes"][0]))

    with pytest.raises(CatalogError, match="duplicate claim_class"):
        load_catalog_from(_mutate(raw, plant))


def test_rejects_join_endpoint_outside_the_grammar(raw: dict) -> None:
    def plant(d: dict) -> None:
        d["forbidden_joins"][0]["source_str"] = "producer:vibes"

    with pytest.raises(CatalogError, match="closed grammar"):
        load_catalog_from(_mutate(raw, plant))


def test_rejects_overlapping_join_rows(raw: dict) -> None:
    """The specialized engine x resolver row must not also resolve to the generic id."""
    def plant(d: dict) -> None:
        d["forbidden_joins"].append(
            {"source_str": "producer:resolver", "target_str": "producer:engine", "cc_id": "CC-ILLEGAL-JOIN"}
        )

    with pytest.raises(CatalogError, match="overlapping forbidden_joins"):
        load_catalog_from(_mutate(raw, plant))


def test_rejects_non_advisory_authority(raw: dict) -> None:
    def plant(d: dict) -> None:
        d["authority"] = "production"

    with pytest.raises(CatalogError, match="PINNED to 'advisory'"):
        load_catalog_from(_mutate(raw, plant))


def test_rejects_generated_by_on_primary(raw: dict) -> None:
    def plant(d: dict) -> None:
        d["generated_by"] = "somebody"

    with pytest.raises(CatalogError, match="generated_by belongs on the GENERATED"):
        load_catalog_from(_mutate(raw, plant))


def test_rejects_missing_required_stream_key(raw: dict) -> None:
    def plant(d: dict) -> None:
        del d["streams"][0]["identity_notes"]

    with pytest.raises(CatalogError, match="missing keys"):
        load_catalog_from(_mutate(raw, plant))


def load_catalog_from(data: dict, tmp: Path | None = None) -> Catalog:
    """Validate an in-memory catalog through the real loader path (no partial-validation bypass)."""
    import tempfile

    target = tmp or Path(tempfile.mkdtemp()) / "jsonl_claim_catalog.yaml"
    target.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return load_catalog(target)
