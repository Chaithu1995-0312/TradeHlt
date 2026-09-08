"""Floor test for the FALSIFY <-> registry binding declared in SCHEMAS_README.

`docs/research/reports/SCHEMAS_README.md` ("How schemas bind to FALSIFY records") declares five
binding rules, and `registry_shape_references.json` states flatly: "FALSIFY records reference
MeasurementObject.object_id, Population.population_id, and JointStateSpace StateIDs."

Nothing checked that. When measured (2026-09-08) rules 1-2 were violated by 4 of 4 records:
`MeasurementObject` was an ad-hoc dict carrying four DIFFERENT key shapes across four records
with `object_id` never present as a key, and `Population` was prose fusing the id, n and
base-rate into one unparseable string. A declared linkage that nothing verifies is
indistinguishable from an enforced one -- the same silent-gap class as F-079 / F-083 / F-085 /
F-056.

This test makes those five rules mechanical. It is ENFORCEMENT, not promotion: it checks the
records against the registries as they already stand and elevates nothing. Registry entries keep
status REGISTERED_IDENTITY (identity, not edge). Grants no authority (CLAUDE.md 6.5).

Authority: governance/hygiene only.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]

_PACK = _REPO / "docs" / "research" / "reports" / "l003_jse_falsify_evidence_pack-2026-09-08.json"
_FALSIFY_SCHEMA = _REPO / "docs" / "research" / "reports" / "schemas" / "falsify_record.schema.json"
_MOR = _REPO / "docs" / "governance" / "measurement_object_registry.json"
_POP_REG = _REPO / "docs" / "governance" / "population_registry.json"
_L003L = _REPO / "docs" / "governance" / "analytics_joint_state_space_l003l-2026-09-07.json"


def _load(path: Path) -> dict:
    assert path.is_file(), f"missing (tracked?) artifact: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def records() -> list[dict]:
    return _load(_PACK)["falsify_records"]


@pytest.fixture(scope="module")
def registered_object_ids() -> set[str]:
    return {o["object_id"] for o in _load(_MOR)["objects"]}


@pytest.fixture(scope="module")
def registered_population_ids() -> set[str]:
    return {p["population_id"] for p in _load(_POP_REG)["populations"]}


@pytest.fixture(scope="module")
def state_ids() -> set[str]:
    return {s["state_id"] for s in _load(_L003L)["omega_joint"]["states"]}


def test_every_artifact_is_git_tracked():
    """provenance_record.schema.json defines `resolves` as git-tracked, NOT merely on disk:
    'an untracked path points at nothing from any other clone'. This test would pass on a
    developer's disk while the whole substrate was invisible to CI, so assert tracking."""
    import subprocess

    for path in (_PACK, _FALSIFY_SCHEMA, _MOR, _POP_REG, _L003L):
        rel = path.relative_to(_REPO).as_posix()
        out = subprocess.run(
            ["git", "ls-files", "--error-unmatch", rel],
            cwd=_REPO, capture_output=True, text=True, check=False,
        )
        assert out.returncode == 0, (
            f"{rel} is NOT git-tracked -- it resolves on this disk only (F-071 class). "
            "Track it before relying on any binding to it."
        )


# ---- SCHEMAS_README rule 1 -------------------------------------------------

def test_rule1_measurement_object_cites_registered_id_or_declares_absence(
    records, registered_object_ids
):
    """object_id is either a registered MOR id, or null WITH a declared reason.

    Null-with-reason is deliberate: records 3-4 target path-geometry buckets that have no
    registered MeasurementObject, and inventing an id would be fabrication (CLAUDE.md 6.6).
    A bare missing key, however, is the silent gap this test exists to forbid."""
    for rec in records:
        rid = rec["record_id"]
        mo = rec["MeasurementObject"]
        assert "object_id" in mo, (
            f"{rid}: MeasurementObject has no `object_id` key (SCHEMAS_README rule 1). "
            f"Keys present: {sorted(mo)}"
        )
        obj_id = mo["object_id"]
        if obj_id is None:
            reason = mo.get("object_id_absent_reason")
            assert reason and reason.strip(), (
                f"{rid}: object_id is null but no `object_id_absent_reason` given. "
                "An absent id must be declared, never silent."
            )
        else:
            assert obj_id in registered_object_ids, (
                f"{rid}: object_id {obj_id!r} is not in measurement_object_registry.json "
                f"(registered: {sorted(registered_object_ids)})"
            )


# ---- SCHEMAS_README rule 2 -------------------------------------------------

def test_rule2_population_id_is_registered(records, registered_population_ids):
    for rec in records:
        rid = rec["record_id"]
        assert "population_id" in rec, (
            f"{rid}: no `population_id` (SCHEMAS_README rule 2). The prose `Population` "
            "string is not a reference."
        )
        pop_id = rec["population_id"]
        assert pop_id in registered_population_ids, (
            f"{rid}: population_id {pop_id!r} not in population_registry.json "
            f"(registered: {sorted(registered_population_ids)})"
        )


def test_rule2_population_prose_stays_consistent_with_the_id(records):
    """The verbatim prose string is preserved (6.2 rule 4); it must still agree with the id
    it was split from, or the two have drifted apart."""
    for rec in records:
        rid = rec["record_id"]
        prose = rec["Population"]
        assert isinstance(prose, str), (
            f"{rid}: `Population` must stay a string -- falsify_record.schema.json types it "
            '{"type": "string"}; making it an object breaks rule-4 validation.'
        )
        assert prose.startswith(rec["population_id"]), (
            f"{rid}: population_id {rec['population_id']!r} is not the prefix of the "
            f"Population prose {prose!r} -- id and prose have drifted."
        )


# ---- SCHEMAS_README rule 3 -------------------------------------------------

def test_rule3_joint_coordinates_are_members_of_S(records, state_ids):
    """"Targets that are joint coordinates MUST be members of S." Passing today; pinned so it
    stays passing."""
    assert len(state_ids) == 9, f"S should have 9 members (L x L), got {len(state_ids)}"
    seen = 0
    for rec in records:
        coord = rec["MeasurementObject"].get("target_coordinate")
        if coord is None:
            continue
        seen += 1
        assert coord in state_ids, (
            f"{rec['record_id']}: target_coordinate {coord!r} is not a member of S "
            f"({sorted(state_ids)})"
        )
    assert seen > 0, "no target_coordinate found -- rule 3 would be vacuous"


# ---- SCHEMAS_README rule 4 -------------------------------------------------

def test_rule4_records_validate_against_falsify_schema(records):
    """Structural validation. jsonschema is not installed in this venv, so enforce the
    schema's own `required` list and declared primitive types directly rather than skipping
    (a skipped check is the very gap this file exists to close)."""
    schema = _load(_FALSIFY_SCHEMA)
    required = schema["required"]
    props = schema["properties"]
    type_map = {"string": str, "object": dict, "array": list}

    for rec in records:
        rid = rec.get("record_id", "<no id>")
        missing = [k for k in required if k not in rec]
        assert not missing, f"{rid}: missing required field(s) {missing}"
        for key, spec in props.items():
            if key not in rec or "type" not in spec:
                continue
            expected = type_map.get(spec["type"])
            if expected is not None:
                assert isinstance(rec[key], expected), (
                    f"{rid}: field {key!r} should be {spec['type']}, "
                    f"got {type(rec[key]).__name__}"
                )
        if "status" in rec:
            assert rec["status"] in props["status"]["enum"], (
                f"{rid}: status {rec['status']!r} not in {props['status']['enum']}"
            )


# ---- SCHEMAS_README rule 5 -------------------------------------------------

def test_rule5_every_measurement_object_declares_formula_map_notation():
    """"Producer refs alone are insufficient; formula_map.notation must appear on Y_* registry
    entries." Passing today; pinned."""
    objects = _load(_MOR)["objects"]
    assert objects, "MeasurementObject registry is empty"
    for obj in objects:
        oid = obj.get("object_id")
        fm = obj.get("formula_map")
        assert isinstance(fm, dict), f"{oid}: no formula_map"
        for field in ("domain", "codomain", "notation"):
            assert fm.get(field), f"{oid}: formula_map.{field} missing or empty"
