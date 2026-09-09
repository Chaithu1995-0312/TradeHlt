"""Measurement result log contract — F-083 made mechanical.

GREEN_FLOOR member. Proves that a sealed MC-* instance claiming a non-UNRUN `mt00` cannot stay
green without a committed result line binding its artifacts, and that a run-level basis is never
mistaken for an L5 object.

The load-bearing tests are the negatives: a PASS with no result line, a PASS with an unbound
artifact, an `economic_claims_allowed: true` line, and the `L5_BASIS` trap (three keys, no
geometry) must all FAIL.

Spec: docs/governance/JSONL_CLAIM_SURFACE.md §8. Schema: docs/reference/schemas.md §9.16.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest

from governance.measurement_result_log import (
    BASIS_DECLARED,
    BASIS_STATUSES,
    META_LINE,
    MT00_VALUES,
    MT01_VALUES,
    N_A,
    RESULT_LOG,
    UNIDENTIFIED,
    ResultLogError,
    _F083_GRANDFATHER,
    append_measurement_result,
    audit_all,
    build_result_line,
    classify_l5_basis,
    lines_for_contract,
    scanned_instance_paths,
    sha256_file,
)

_REPO = Path(__file__).resolve().parents[1]
_MODULE = _REPO / "src" / "governance" / "measurement_result_log.py"
_INSTANCES = _REPO / "configs" / "research" / "measurement_contracts" / "instances"

_GOOD_BASIS = {
    "walk_kernel": "multi_tp_walk",
    "cost_model_id": "flat_12bps",
    "fill_model_id": "touch_exact",
    "geometry_kind": "engine_trade",
    "geometry_schema": "dual_tp_partial",
    "instrument": "XAUUSD",
    "timeframe": "M15",
    "corpus_sha256": None,
}


# --- classify_l5_basis: the five-key rule ----------------------------------------------------


def test_none_basis_is_n_a() -> None:
    assert classify_l5_basis(None) == N_A


def test_complete_basis_is_declared() -> None:
    assert classify_l5_basis(_GOOD_BASIS) == BASIS_DECLARED


@pytest.mark.parametrize(
    "missing", ["walk_kernel", "cost_model_id", "fill_model_id", "geometry_kind", "geometry_schema"]
)
def test_every_one_of_the_five_keys_is_required(missing: str) -> None:
    """The L5_BASIS trap: that tuple has THREE keys and no geometry.

    An implementer who iterates `identity.tokens.L5_BASIS` instead of the local five-key table
    would classify a basis missing `geometry_kind` / `geometry_schema` as BASIS_DECLARED, and
    CC-MC-RESULT-BINDING would ground on an incomplete basis.
    """
    basis = {k: v for k, v in _GOOD_BASIS.items() if k != missing}
    assert classify_l5_basis(basis) == UNIDENTIFIED, missing


def test_l5_basis_tuple_really_is_three_keys_without_geometry() -> None:
    """Pins the upstream fact the five-key rule exists to work around."""
    from identity.tokens import L5_BASIS

    assert L5_BASIS == ("walk_kernel", "cost_model_id", "fill_model_id")
    assert "geometry_kind" not in L5_BASIS and "geometry_schema" not in L5_BASIS


@pytest.mark.parametrize(
    "key,bad",
    [
        ("walk_kernel", "made_up_kernel"),
        ("cost_model_id", "free"),
        ("fill_model_id", "optimistic"),
        ("geometry_kind", "vibes"),
        ("geometry_schema", "triple_tp"),
        ("timeframe", "M7"),
    ],
)
def test_out_of_vocabulary_tokens_are_unidentified(key: str, bad: str) -> None:
    assert classify_l5_basis({**_GOOD_BASIS, key: bad}) == UNIDENTIFIED


def test_basis_status_is_never_preserved() -> None:
    """PRESERVED is an identity CheckResult status; a run-level basis must never claim it."""
    assert "PRESERVED" not in BASIS_STATUSES
    assert BASIS_STATUSES == {"UNIDENTIFIED", "BASIS_DECLARED", "N_A"}


def test_non_mapping_basis_is_unidentified() -> None:
    assert classify_l5_basis("multi_tp_walk") == UNIDENTIFIED  # type: ignore[arg-type]


# --- line validation ---------------------------------------------------------------------------


def _line(**over):
    base = dict(
        timestamp="2026-08-25T00:00:00Z",
        contract_id="MC-FIXTURE-V1",
        run_id="run-1",
        trust_mt00="FAIL",
        trust_mt01_matrix_coverage="UNRUN",
        artifact_hashes={},
        declared_artifacts_exist=True,
        l5_basis=None,
    )
    base.update(over)
    return build_result_line(**base)


def test_honest_line_builds() -> None:
    line = _line()
    assert line["basis_status"] == N_A
    assert line["economic_claims_allowed"] is False
    assert line["authority"] == "research"


def test_trust_token_names_match_the_frozen_contract_schema() -> None:
    """The contract key is `mt01_matrix_coverage` — `trust_status` is additionalProperties:false,
    so a result line calling it `mt01` would describe a field that cannot exist."""
    schema = json.loads(
        (_REPO / "docs" / "governance" / "measurement_contract.schema.json").read_text(encoding="utf-8")
    )
    trust = schema["properties"]["trust_status"]
    assert trust.get("additionalProperties") is False
    assert "mt01_matrix_coverage" in trust["properties"]
    assert "mt01" not in trust["properties"]
    assert set(trust["properties"]["mt00"]["enum"]) == MT00_VALUES
    assert set(trust["properties"]["mt01_matrix_coverage"]["enum"]) == MT01_VALUES
    assert "trust_mt01_matrix_coverage" in _line()


def test_economic_claims_allowed_cannot_be_true() -> None:
    with pytest.raises(ResultLogError, match="economic_claims_allowed"):
        append_measurement_result({**_line(), "economic_claims_allowed": True})


def test_authority_cannot_be_upgraded() -> None:
    with pytest.raises(ResultLogError, match="authority"):
        append_measurement_result({**_line(), "authority": "production"})


def test_basis_status_must_agree_with_the_basis() -> None:
    forged = {**_line(), "l5_basis": {"walk_kernel": "multi_tp_walk"}, "basis_status": BASIS_DECLARED}
    with pytest.raises(ResultLogError, match="disagrees with the basis"):
        append_measurement_result(forged)


@pytest.mark.parametrize("token", ["PASSED", "unrun", "", None])
def test_dishonest_mt00_tokens_are_rejected(token) -> None:
    with pytest.raises(ResultLogError):
        append_measurement_result({**_line(), "trust_mt00": token})


def test_short_hash_is_rejected() -> None:
    with pytest.raises(ResultLogError, match="sha256"):
        append_measurement_result({**_line(), "artifact_hashes": {"a.json": "deadbeef"}})


# --- the committed log -----------------------------------------------------------------------


def test_committed_log_exists_and_starts_with_the_meta_line() -> None:
    assert RESULT_LOG.exists(), "the result log is committed, not gitignored"
    first = json.loads(RESULT_LOG.read_text(encoding="utf-8").splitlines()[0])
    assert first == META_LINE
    assert first["authority"] == "research"


def test_every_committed_line_is_honest() -> None:
    for line in lines_for_contract("", RESULT_LOG) or []:  # no-op guard
        pass
    from governance.measurement_result_log import iter_result_lines, _validate_line

    for record in iter_result_lines(RESULT_LOG):
        _validate_line(record)  # raises on any dishonest committed line


def test_append_is_append_only(tmp_path: Path) -> None:
    log = tmp_path / "log.jsonl"
    append_measurement_result(_line(run_id="a"), log)
    append_measurement_result(_line(run_id="b"), log)
    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3  # meta + 2
    assert lines_for_contract("MC-FIXTURE-V1", log)[-1]["run_id"] == "b"  # correction is a new line


# --- the F-083 scan ------------------------------------------------------------------------------


def test_scan_universe_is_tracked_only_and_deterministic() -> None:
    """`git ls-files`, not a disk glob — an untracked instance must not change the verdict."""
    import subprocess

    paths = scanned_instance_paths()
    assert paths, "expected at least one tracked MC-* instance"
    tracked = subprocess.run(
        ["git", "ls-files", "configs/research/measurement_contracts/instances/MC-*.json"],
        capture_output=True, text=True, cwd=_REPO, check=False,
    ).stdout.split()
    assert len(paths) == len(tracked)
    on_disk = list(_INSTANCES.glob("MC-*.json"))
    assert len(on_disk) >= len(paths), "a disk glob should be a superset of the tracked scan"


def test_drafts_and_profiles_and_cpr_are_out_of_scan() -> None:
    """MC-CPR-L0 (mt00=PARTIAL) lives at the parent dir and is NOT rewritten into the scan."""
    names = {p.name for p in scanned_instance_paths()}
    assert "MC-CPR-L0-XAUUSD-M15-UTC-V1.json" not in names
    assert not any(n.endswith(".v1.json") for n in names)  # MP-* profiles
    assert not any("drafts" in str(p) for p in scanned_instance_paths())
    cpr = _INSTANCES.parent / "MC-CPR-L0-XAUUSD-M15-UTC-V1.json"
    if cpr.exists():  # fixture guard: it is out of scan, and we did not rewrite it
        assert json.loads(cpr.read_text(encoding="utf-8"))["trust_status"]["mt00"] == "PARTIAL"


def test_grandfather_pin_is_empty_and_shrink_only() -> None:
    assert _F083_GRANDFATHER == frozenset(), (
        "the F-083 grandfather pin is shrink-only and ships empty — every scanned instance is "
        "honestly UNRUN"
    )


def test_every_scanned_instance_is_f083_honest() -> None:
    """The floor itself. No longer vacuous: MC-MAGPRIOR-XAUUSD-M15-V1 executed E-MT-00 on
    2026-08-26 and is backed by a real result line, so this now exercises the bound path."""
    failures = [r for r in audit_all() if not r["ok"]]
    assert not failures, f"F-083 violations: {failures}"


def test_unrun_needs_no_result_line() -> None:
    """UNRUN is honest and needs no line; anything else must be backed by one.

    2026-08-26 (CH-measurement-provenance-boundary): this previously asserted that EVERY instance
    is UNRUN — a snapshot of the pre-execution world that had to go red the first time the
    measurement layer actually ran. The invariant it meant to protect is the one asserted here,
    and it is the one `audit_instance` encodes.
    """
    results = audit_all()
    assert results, "scan produced nothing"
    assert all(r["ok"] for r in results)

    unrun = [r for r in results if r["mt00"] == "UNRUN"]
    executed = [r for r in results if r["mt00"] != "UNRUN"]
    assert unrun, "every instance executed — this test's UNRUN arm is no longer exercised"
    for r in executed:
        assert lines_for_contract(r["contract_id"]), (
            f"{r['contract_id']} claims mt00={r['mt00']!r} with no result line — the F-083 shape"
        )


def test_non_unrun_without_a_result_line_fails(tmp_path: Path, monkeypatch) -> None:
    """Planted defect: the exact F-083 shape."""
    from governance import measurement_result_log as mod

    inst = tmp_path / "MC-PLANTED-V1.json"
    inst.write_text(json.dumps({
        "schema_version": "1.0.0",
        "contract_id": "MC-PLANTED-V1",
        "evidence_artifacts": {"contract_path": "MC-PLANTED-V1.json"},
        "trust_status": {"mt00": "PASS", "mt01_matrix_coverage": "COMPLETE",
                         "economic_claims_allowed": False},
    }), encoding="utf-8")
    verdict = mod.audit_instance(inst, tmp_path, tmp_path / "empty.jsonl")
    assert verdict["ok"] is False
    assert "no result line" in " ".join(verdict["problems"])


def test_pass_with_unbound_artifact_fails(tmp_path: Path, monkeypatch) -> None:
    from governance import measurement_result_log as mod

    artifact = tmp_path / "report.json"
    artifact.write_text("{}", encoding="utf-8")
    inst = tmp_path / "MC-PLANTED2-V1.json"
    inst.write_text(json.dumps({
        "schema_version": "1.0.0",
        "contract_id": "MC-PLANTED2-V1",
        "evidence_artifacts": {"mt00_report_path": "report.json"},
        "trust_status": {"mt00": "PASS", "mt01_matrix_coverage": "COMPLETE",
                         "economic_claims_allowed": False},
    }), encoding="utf-8")
    log = tmp_path / "log.jsonl"
    append_measurement_result(
        _line(contract_id="MC-PLANTED2-V1", trust_mt00="PASS",
              trust_mt01_matrix_coverage="COMPLETE", artifact_hashes={}), log
    )
    verdict = mod.audit_instance(inst, tmp_path, log)
    assert verdict["ok"] is False
    assert "no artifact_hashes entry" in " ".join(verdict["problems"])


def test_hash_mismatch_fails(tmp_path: Path, monkeypatch) -> None:
    from governance import measurement_result_log as mod

    artifact = tmp_path / "report.json"
    artifact.write_text("{}", encoding="utf-8")
    inst = tmp_path / "MC-PLANTED3-V1.json"
    inst.write_text(json.dumps({
        "schema_version": "1.0.0",
        "contract_id": "MC-PLANTED3-V1",
        "evidence_artifacts": {"mt00_report_path": "report.json"},
        "trust_status": {"mt00": "PASS", "mt01_matrix_coverage": "COMPLETE",
                         "economic_claims_allowed": False},
    }), encoding="utf-8")
    log = tmp_path / "log.jsonl"
    append_measurement_result(
        _line(contract_id="MC-PLANTED3-V1", trust_mt00="PASS",
              trust_mt01_matrix_coverage="COMPLETE",
              artifact_hashes={"report.json": "0" * 64}), log
    )
    verdict = mod.audit_instance(inst, tmp_path, log)
    assert verdict["ok"] is False
    assert "hash mismatch" in " ".join(verdict["problems"])


# --- grounding ------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def grounder():
    from governance.semantic_grounding import SemanticGrounder

    return SemanticGrounder.load()


def test_unrun_instance_grounds_on_shape(grounder) -> None:
    hit = grounder.ground("JSONL", "MC-VCRT-XAUUSD-M15-V2", relation="CC-MC-SCHEMA-SHAPE")
    assert hit.status == "GROUNDED"
    assert hit.payload["trust_mt00"] == "UNRUN"
    assert "never ran" in hit.payload["does_not_prove"] or "ever ran" in hit.payload["does_not_prove"]


def test_unrun_instance_refuses_result_binding(grounder) -> None:
    hit = grounder.ground("JSONL", "MC-VCRT-XAUUSD-M15-V2", relation="CC-MC-RESULT-BINDING")
    assert hit.status == "REFUSED"
    assert hit.refusal_class == "CC-MC-DECLARED-UNEXECUTED"


def test_result_binding_grounds_on_an_executed_fail_run(tmp_path: Path, monkeypatch, grounder) -> None:
    """The success pin: EXECUTED is not PASSED.

    A synthetic FAIL run with an honest result line must GROUND — otherwise the CAN half of F-083
    is unreachable and only refusals would ever be observable. The fixture never enters the real
    `instances/` tree.
    """
    from governance import measurement_result_log as mod

    artifact = tmp_path / "mt00_report.json"
    artifact.write_text('{"verdict": "FAIL"}', encoding="utf-8")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()

    inst_dir = tmp_path / "instances"
    inst_dir.mkdir()
    (inst_dir / "MC-JSONL-CLAIM-FIXTURE-V1.json").write_text(json.dumps({
        "schema_version": "1.0.0",
        "contract_id": "MC-JSONL-CLAIM-FIXTURE-V1",
        "evidence_artifacts": {"mt00_report_path": "mt00_report.json"},
        "trust_status": {"mt00": "FAIL", "mt01_matrix_coverage": "COMPLETE",
                         "economic_claims_allowed": False},
    }), encoding="utf-8")

    log = tmp_path / "log.jsonl"
    append_measurement_result(
        _line(contract_id="MC-JSONL-CLAIM-FIXTURE-V1", trust_mt00="FAIL",
              trust_mt01_matrix_coverage="COMPLETE",
              artifact_hashes={"mt00_report.json": digest}), log
    )

    monkeypatch.setattr(mod, "INSTANCE_DIR", inst_dir)
    monkeypatch.setattr(mod, "RESULT_LOG", log)
    monkeypatch.setattr("governance.semantic_grounding._ROOT", tmp_path)

    hit = grounder.ground("JSONL", "MC-JSONL-CLAIM-FIXTURE-V1", relation="CC-MC-RESULT-BINDING")
    assert hit.status == "GROUNDED", hit.ungrounded_reason
    assert hit.payload["trust_mt00"] == "FAIL"          # GROUNDED != passed
    assert hit.payload["basis_status"] == N_A
    assert hit.payload["authority"] == "research"
    assert hit.record_kind != "PRESERVED"


def test_bad_mc_token_grammar_is_unanswerable(grounder) -> None:
    hit = grounder.ground("JSONL", "logs/x/opportunities.jsonl", relation="CC-MC-SCHEMA-SHAPE")
    assert hit.status == "UNANSWERABLE"


# --- import discipline (AST) --------------------------------------------------------------------


def test_module_imports_identity_tokens_directly_and_nothing_else_from_identity() -> None:
    """`identity/__init__.py` re-exports identity_check; pulling it in here is the grain error
    this module exists to avoid. Also bans walk / cost / fill kernels."""
    tree = ast.parse(_MODULE.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    identity_imports = [m for m in imported if m == "identity" or m.startswith("identity.")]
    assert identity_imports == ["identity.tokens"], identity_imports

    for banned in ("identity.check", "features.feature_pipeline", "config_layer.crt_engine_v2",
                   "runtime.backtest_v2", "research.forward_walk", "research.costs"):
        assert not any(m == banned or m.startswith(banned + ".") for m in imported), banned


def test_module_never_calls_identity_check() -> None:
    """AST, not grep: the module's own docstring names the function it must never CALL."""
    tree = ast.parse(_MODULE.read_text(encoding="utf-8"))
    called = {
        node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    assert "identity_check" not in called, (
        "a measurement RUN is not one trade - _check_l5 requires a full L4 parent plus the L5 "
        "payload, so calling it here would mark every line UNIDENTIFIED"
    )
    assert "identity_check" not in {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}


def test_sha256_file_is_none_on_missing(tmp_path: Path) -> None:
    assert sha256_file(tmp_path / "nope.json") is None
