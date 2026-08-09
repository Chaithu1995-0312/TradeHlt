"""Mechanical floor for the asset-class measurement PROFILES (MEASUREMENT_CONTRACT.md section 9).

A profile supplies reusable per-asset-class defaults for the surface fields of a sealed MC-*
MeasurementContract instance. It is subordinate: it must never impersonate a contract instance,
never set trust_status, and never grant economic admissibility.

Checks:
  * profile schema, MP-* id namespace (never MC-*), lifecycle gating
  * SUBORDINATION IS MECHANICAL — every enumerated value in a profile is asserted to be a member
    of the FROZEN measurement_contract.schema.json enum for that field. A profile cannot drift
    away from the charter's vocabulary without going red.
  * profile_hash is recomputed here, never trusted as written
  * the `labels` surface is byte-identical across every profile (cross-asset-class comparability)
  * unresolved_terms cite real findings
  * the charter carries the additive sections that authorize this layer

Read-only. Asserts nothing about whether any measurement is CORRECT — only that the profile
declares its basis in the charter's own vocabulary.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE_DIR = ROOT / "configs" / "research" / "measurement_contracts"
SCHEMA = ROOT / "docs" / "governance" / "measurement_contract.schema.json"
CHARTER = ROOT / "docs" / "governance" / "MEASUREMENT_CONTRACT.md"
CLAUDE_MD = ROOT / "CLAUDE.md"

REQUIRED_PROFILE_IDS = {"MP-CRYPTO-MAJORS", "MP-FX-MAJORS", "MP-METALS-MT5"}

REQUIRED_TOP_FIELDS = {
    "schema_version",
    "profile_id",
    "version",
    "lifecycle",
    "profile_hash",
    "created_utc",
    "subordinate_to",
    "profile",
    "surface_defaults",
    "unresolved_terms",
}

# Fields a profile must NOT carry — they belong to a sealed contract instance only.
FORBIDDEN_TOP_FIELDS = {
    "experiment_id",
    "contract_id",
    "trust_status",
    "authority",
    "evidence_artifacts",
}

ALLOWED_LIFECYCLE = {"DRAFT", "CALIBRATED", "FROZEN"}

# (surface, field) -> dotted path into the frozen schema's properties tree.
ENUM_BINDINGS = {
    ("population", "unit_of_analysis"): "population.unit_of_analysis",
    ("population", "detection_vs_trade"): "population.detection_vs_trade",
    ("features", "formula_authority"): "features.formula_authority",
    ("labels", "label_family"): "labels.label_family",
    ("labels", "derivation_authority"): "labels.derivation_authority",
    ("costs", "success_gate_uses"): "costs.success_gate_uses",
    ("exits", "exit_family"): "exits.exit_family",
    ("splits", "scheme"): "splits.scheme",
    ("splits", "overlap_policy"): "splits.overlap_policy",
    ("pipeline_identity", "engine_gate_mode"): "pipeline_identity.engine_gate_mode",
    ("pipeline_identity", "dataset_integrity_level"): "pipeline_identity.dataset_integrity_level",
}


def _profiles() -> dict[str, dict]:
    assert PROFILE_DIR.is_dir(), f"missing profile dir: {PROFILE_DIR}"
    out: dict[str, dict] = {}
    for p in sorted(PROFILE_DIR.glob("*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        pid = data.get("profile_id")
        assert pid, f"{p.name}: profile_id required"
        assert pid not in out, f"duplicate profile_id {pid}"
        out[pid] = data
    assert out, "no profiles found"
    return out


def _schema() -> dict:
    assert SCHEMA.is_file(), f"frozen schema missing: {SCHEMA}"
    return json.loads(SCHEMA.read_text(encoding="utf-8"))


def _schema_enum(schema: dict, dotted: str) -> list[str]:
    """Resolve 'surface.field' to that field's enum in the frozen schema."""
    surface, field = dotted.split(".")
    node = schema["properties"][surface]["properties"][field]
    enum = node.get("enum")
    assert enum, f"frozen schema has no enum at {dotted}"
    return enum


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _claude_finding_ids() -> set[str]:
    text = CLAUDE_MD.read_text(encoding="utf-8")
    return set(re.findall(r"^\|\s*(F-\d{3})\s*\|", text, flags=re.MULTILINE))


def test_required_profiles_present():
    got = set(_profiles())
    missing = REQUIRED_PROFILE_IDS - got
    assert not missing, f"missing profiles: {sorted(missing)}"
    extra = got - REQUIRED_PROFILE_IDS
    assert not extra, f"unregistered profiles: {sorted(extra)}"


def test_profile_shape_and_id_namespace():
    for pid, prof in _profiles().items():
        missing = REQUIRED_TOP_FIELDS - set(prof)
        assert not missing, f"{pid}: missing fields {sorted(missing)}"
        assert re.fullmatch(r"MP-[A-Z0-9][A-Z0-9_-]+", pid), (
            f"{pid}: profile ids use the MP-* namespace"
        )
        assert not pid.startswith("MC-"), (
            f"{pid}: must not occupy the MC-* sealed-contract namespace"
        )
        forbidden = FORBIDDEN_TOP_FIELDS & set(prof)
        assert not forbidden, (
            f"{pid}: carries contract-instance fields {sorted(forbidden)} — a profile "
            "must not impersonate a sealed contract or claim admissibility"
        )


def test_subordination_is_declared_and_points_at_the_frozen_schema():
    schema = _schema()
    for pid, prof in _profiles().items():
        sub = prof["subordinate_to"]
        assert sub["schema"] == "docs/governance/measurement_contract.schema.json", (
            f"{pid}: must subordinate to the frozen schema"
        )
        assert sub["charter"] == "docs/governance/MEASUREMENT_CONTRACT.md"
        assert sub["schema_version"] == schema["properties"]["schema_version"]["const"], (
            f"{pid}: declared schema_version does not match the frozen schema const"
        )
        rel = sub["relationship"].lower()
        assert "never" in rel, f"{pid}: relationship must state what a profile may NOT do"


def test_relationship_declares_mc_instance_override_precedence():
    """2026-08-06 (engine_gate discussion): profiles keep their full term set, but on any field
    the frozen schema scopes per-experiment (engine_gate_mode, dataset_integrity_level, splits,
    metrics.multiplicity) a sealed MC-* instance must be documented as authoritative over the
    profile default. This is what stops 'wider scope' from silently becoming 'ownership'."""
    experiment_scoped_terms = (
        "pipeline_identity.engine_gate_mode",
        "pipeline_identity.dataset_integrity_level",
        "splits",
        "metrics.multiplicity",
    )
    for pid, prof in _profiles().items():
        rel = prof["subordinate_to"]["relationship"]
        assert "always wins" in rel.lower() or "always win" in rel.lower(), (
            f"{pid}: relationship must state MC-* override precedence explicitly"
        )
        for term in experiment_scoped_terms:
            assert term in rel, (
                f"{pid}: relationship must name {term!r} as an experiment-scoped field an "
                "MC-* instance overrides"
            )


def test_profile_enum_values_are_members_of_the_frozen_schema_enums():
    """The mechanical subordination check — vocabulary cannot drift from the charter."""
    schema = _schema()
    problems: list[str] = []
    for pid, prof in _profiles().items():
        for (surface, field), dotted in ENUM_BINDINGS.items():
            value = (prof["surface_defaults"].get(surface) or {}).get(field, None)
            if value is None:
                continue  # unresolved terms are allowed to be null while DRAFT
            allowed = _schema_enum(schema, dotted)
            if value not in allowed:
                problems.append(
                    f"{pid}.{surface}.{field}={value!r} not in frozen enum {allowed}"
                )
        promotable = (
            (prof["surface_defaults"].get("costs") or {}).get("gross_vs_net") or {}
        ).get("promotable")
        if promotable is not None:
            allowed = schema["properties"]["costs"]["properties"]["gross_vs_net"][
                "properties"
            ]["promotable"]["enum"]
            if promotable not in allowed:
                problems.append(f"{pid}.costs.promotable={promotable!r} not in {allowed}")
    assert not problems, "profile vocabulary drifted from the frozen schema:\n" + "\n".join(problems)


def test_lifecycle_gating():
    for pid, prof in _profiles().items():
        lc = prof["lifecycle"]
        assert lc in ALLOWED_LIFECYCLE, f"{pid}: bad lifecycle {lc!r}"
        unresolved = prof["unresolved_terms"]
        if lc == "DRAFT":
            assert prof["profile_hash"] is None, f"{pid}: DRAFT must not carry a hash"
            assert unresolved, f"{pid}: DRAFT must enumerate what blocks its freeze"
        elif lc == "CALIBRATED":
            assert prof["profile_hash"] is None, f"{pid}: CALIBRATED must not carry a hash"
            assert not unresolved, f"{pid}: CALIBRATED requires unresolved_terms empty"
        else:  # FROZEN
            assert not unresolved, f"{pid}: FROZEN requires unresolved_terms empty"
            assert prof["profile_hash"], f"{pid}: FROZEN requires a profile_hash"


def test_profile_hash_is_recomputed_never_trusted():
    for pid, prof in _profiles().items():
        if prof["lifecycle"] != "FROZEN":
            continue
        expected = hashlib.sha256(
            _canonical(prof["surface_defaults"]).encode("utf-8")
        ).hexdigest()
        assert prof["profile_hash"] == expected, (
            f"{pid}: stored profile_hash does not match recomputation over surface_defaults "
            f"(expected {expected})"
        )


def test_label_surface_is_identical_across_profiles():
    """The one surface that must NOT vary by asset class (F-035 generalization claims)."""
    labels = {pid: prof["surface_defaults"]["labels"] for pid, prof in _profiles().items()}
    canon = {pid: _canonical(v) for pid, v in labels.items()}
    distinct = set(canon.values())
    if len(distinct) > 1:
        # `note` may legitimately differ in wording; the decisive fields must not.
        decisive = {
            pid: _canonical(
                {
                    k: v[k]
                    for k in (
                        "label_family",
                        "derivation_authority",
                        "stream_fields_banned_for_economic_claims",
                    )
                }
            )
            for pid, v in labels.items()
        }
        assert len(set(decisive.values())) == 1, (
            "label derivation differs across asset classes — cross-class generalization "
            "claims become uninterpretable:\n" + json.dumps(decisive, indent=2)
        )


def test_costs_are_derived_not_a_shared_constant():
    """The F-025/F-035 lesson, enforced: cost must be per-instrument, not a flat bps."""
    for pid, prof in _profiles().items():
        costs = prof["surface_defaults"]["costs"]
        assert costs["cost_model_id"].startswith("derived_per_instrument"), (
            f"{pid}: cost_model_id must be a derived per-instrument model"
        )
        formulas = " ".join(c["bps_or_formula"] for c in costs["components"])
        assert "DERIVED" in formulas, (
            f"{pid}: at least one cost component must be DERIVED from instrument bar statistics"
        )
        assert costs["gross_vs_net"]["promotable"] == "net_only", (
            f"{pid}: gross results are diagnostic and never promotable"
        )


def test_unresolved_terms_cite_real_findings():
    known = _claude_finding_ids()
    for pid, prof in _profiles().items():
        for entry in prof["unresolved_terms"]:
            assert entry.get("term"), f"{pid}: unresolved entry needs a term"
            assert entry.get("blocks_freeze") is True, (
                f"{pid}.{entry.get('term')}: unresolved terms block the freeze"
            )
            for ref in entry.get("refs") or []:
                assert ref in known, f"{pid}.{entry['term']}: unknown finding ref {ref}"


def test_charter_authorizes_the_profile_layer():
    text = CHARTER.read_text(encoding="utf-8")
    assert "## 9. Asset-class profiles" in text, (
        "MEASUREMENT_CONTRACT.md must carry the section that authorizes profiles"
    )
    assert "## 10. L0 sufficiency criterion" in text
    assert "configs/research/measurement_contracts/" in text.replace("\\", "/")
    # the freeze must not be silently overwritten
    assert "FROZEN v1.0.0" in text, "the original freeze marker must survive amendment"
    assert "amended additively" in text, (
        "an amendment to a frozen charter must say so in the header"
    )


def test_profiles_grant_no_admissibility():
    """A profile may never be the thing that makes an economic claim admissible."""
    for pid, prof in _profiles().items():
        blob = _canonical(prof).lower()
        assert "economic_admissible" not in blob, (
            f"{pid}: profiles must not carry the admissibility flag"
        )
        assert "not an admissibility seal" in prof["_doc"].lower(), (
            f"{pid}: _doc must state the profile is not an admissibility seal"
        )
