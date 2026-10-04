"""Measurement result log — the committed record that a sealed MC-* contract actually EXECUTED.

Closes the F-083 silent gap: a `measurement_contract.schema.json` instance can declare an
`evidence_artifacts` map and a `trust_status.mt00` of `PASS` while the run never happened, and
nothing in the repository could tell the two apart. `tests/test_measurement_contract.py` validates
contract SHAPE; it never compares an instance to the artifacts its run produced.

This module adds the missing half: an append-only committed log (sibling of
`configs/promotion_log.jsonl`) binding a `contract_id` to artifact SHA-256 hashes and an optional
run-level basis declaration. A scanned instance whose `mt00` is not `UNRUN` must have a line here.

**A result line is NOT an L5 object.** Do not call `identity_check("L5", line["l5_basis"])` —
`identity.check._check_l5` requires a full L4 parent plus the L5 payload (`y_R_gross`, `mfe`,
`mae`, `duration_bars`, `exit_reason`), which do not exist at run grain. Calling it would mark
every line `UNIDENTIFIED` and `CC-MC-RESULT-BINDING` could never ground. `basis_status` is
`UNIDENTIFIED | BASIS_DECLARED | N_A` and is never `PRESERVED`.

**Import discipline (AST-pinned by tests/test_measurement_result_log.py):** import
`identity.tokens` DIRECTLY. Never `import identity` — `identity/__init__.py` re-exports
`identity_check`, and pulling the check machinery in here is the grain error this module exists to
avoid. Never import a walk / cost / fill kernel.

Authority: research only. `economic_claims_allowed` is const `False` on every line — a result line
proves a run EXECUTED, never that it passed or that its result is economic (CLAUDE.md §6.5).

Schema doc: `docs/reference/schemas.md` §9.16. Spec: `docs/governance/JSONL_CLAIM_SURFACE.md` §8.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Iterator, Mapping, Optional

from identity.tokens import (
    COST_MODEL_IDS,
    FILL_MODEL_IDS,
    GEOMETRY_KINDS,
    GEOMETRY_SCHEMAS,
    TIMEFRAMES,
    WALK_KERNELS,
)

_ROOT = Path(__file__).resolve().parents[2]

RESULT_LOG = _ROOT / "configs" / "research" / "measurement_result_log.jsonl"
INSTANCE_DIR = _ROOT / "configs" / "research" / "measurement_contracts" / "instances"

KIND = "MEASUREMENT_RESULT"

#: Honest trust tokens. Names mirror the frozen contract schema EXACTLY: the second key is
#: `mt01_matrix_coverage`, not `mt01` — `trust_status` is `additionalProperties: false`.
MT00_VALUES = frozenset({"UNRUN", "PASS", "FAIL", "PARTIAL"})
MT01_VALUES = frozenset({"UNRUN", "COMPLETE", "INCOMPLETE"})

#: Run-level basis classification. NEVER `PRESERVED` — that is an identity CheckResult status.
UNIDENTIFIED, BASIS_DECLARED, N_A = "UNIDENTIFIED", "BASIS_DECLARED", "N_A"
BASIS_STATUSES = frozenset({UNIDENTIFIED, BASIS_DECLARED, N_A})

#: Shrink-only. A scanned instance may be pinned here ONLY with an explicit adjudication.
#: Empty at ship — every instance in the scan universe is honestly UNRUN.
_F083_GRANDFATHER: frozenset[str] = frozenset()

META_LINE = {
    "kind": "meta",
    "schema": "measurement_result_log/1",
    "authority": "research",
    "scan_universe": "configs/research/measurement_contracts/instances/MC-*.json (git-tracked only)",
    "sealed_pass_bound": 0,
    "note": (
        "Append-only. A correction is a NEW line, never an overwrite. A line proves a run "
        "EXECUTED, never that it passed and never that its result is economic."
    ),
}

#: Five keys against five frozensets. Do NOT iterate `identity.tokens.L5_BASIS` — that tuple is
#: ("walk_kernel", "cost_model_id", "fill_model_id") only; geometry lives on L4. An implementer who
#: loops over it will classify an incomplete basis as BASIS_DECLARED.
_L5_BASIS_REQUIRED: tuple[tuple[str, frozenset], ...] = (
    ("walk_kernel", WALK_KERNELS),
    ("cost_model_id", COST_MODEL_IDS),
    ("fill_model_id", FILL_MODEL_IDS),
    ("geometry_kind", GEOMETRY_KINDS),      # L4 vocabulary; absent from L5_BASIS
    ("geometry_schema", GEOMETRY_SCHEMAS),  # L4 vocabulary; absent from L5_BASIS
)


class ResultLogError(ValueError):
    """A result line violates the append-only / honest-token contract."""


def classify_l5_basis(basis: Optional[Mapping[str, Any]]) -> str:
    """Classify a RUN-LEVEL basis declaration. Never calls identity_check, never PRESERVED."""
    if basis is None:
        return N_A
    if not isinstance(basis, Mapping):
        return UNIDENTIFIED
    for key, vocab in _L5_BASIS_REQUIRED:
        value = basis.get(key)
        if value in (None, "") or value not in vocab:
            return UNIDENTIFIED
    timeframe = basis.get("timeframe")
    if timeframe not in (None, "") and timeframe not in TIMEFRAMES:
        return UNIDENTIFIED
    return BASIS_DECLARED


def sha256_file(path: Path) -> Optional[str]:
    """SHA-256 of a file, or None when it is unreadable. Never raises."""
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _validate_line(line: Mapping[str, Any]) -> None:
    if line.get("kind") != KIND:
        raise ResultLogError(f"kind must be {KIND!r}")
    for key in ("timestamp", "contract_id", "run_id"):
        if not str(line.get(key) or "").strip():
            raise ResultLogError(f"{key} is required")
    if line.get("trust_mt00") not in MT00_VALUES:
        raise ResultLogError(f"trust_mt00 must be one of {sorted(MT00_VALUES)}")
    if line.get("trust_mt01_matrix_coverage") not in MT01_VALUES:
        raise ResultLogError(f"trust_mt01_matrix_coverage must be one of {sorted(MT01_VALUES)}")
    # PINNED: this surface never grants economic authority (CLAUDE.md §6.5).
    if line.get("economic_claims_allowed") is not False:
        raise ResultLogError("economic_claims_allowed is const false on a result line")
    if line.get("authority") != "research":
        raise ResultLogError("authority is const 'research' on a result line")
    basis_status = line.get("basis_status")
    if basis_status not in BASIS_STATUSES:
        raise ResultLogError(f"basis_status must be one of {sorted(BASIS_STATUSES)}")
    if basis_status == "PRESERVED":  # defensive; PRESERVED is not in BASIS_STATUSES
        raise ResultLogError("PRESERVED is an identity CheckResult status, never a basis_status")
    expected = classify_l5_basis(line.get("l5_basis"))
    if basis_status != expected:
        raise ResultLogError(f"basis_status {basis_status!r} disagrees with the basis ({expected!r})")
    hashes = line.get("artifact_hashes")
    if not isinstance(hashes, dict):
        raise ResultLogError("artifact_hashes must be a dict of repo-relative path -> sha256")
    for path, digest in hashes.items():
        if not isinstance(digest, str) or len(digest) != 64:
            raise ResultLogError(f"artifact_hashes[{path!r}] is not a sha256 hex digest")


def build_result_line(
    *,
    timestamp: str,
    contract_id: str,
    run_id: str,
    trust_mt00: str,
    trust_mt01_matrix_coverage: str,
    artifact_hashes: Mapping[str, str],
    declared_artifacts_exist: bool,
    l5_basis: Optional[Mapping[str, Any]] = None,
    ontology_ids: Optional[list[str]] = None,
    notes: str = "",
) -> dict:
    """Assemble a validated result line. `basis_status` is derived, never caller-supplied."""
    line = {
        "timestamp": timestamp,
        "kind": KIND,
        "contract_id": contract_id,
        "run_id": run_id,
        "trust_mt00": trust_mt00,
        "trust_mt01_matrix_coverage": trust_mt01_matrix_coverage,
        "economic_claims_allowed": False,
        "authority": "research",
        "ontology_ids": list(ontology_ids or []),
        "artifact_hashes": dict(artifact_hashes),
        "declared_artifacts_exist": bool(declared_artifacts_exist),
        "l5_basis": dict(l5_basis) if l5_basis is not None else None,
        "basis_status": classify_l5_basis(l5_basis),
        "notes": notes,
    }
    _validate_line(line)
    return line


def append_measurement_result(line: Mapping[str, Any], path: Optional[Path] = None) -> None:
    """Append one validated line. Append-only — a correction is a NEW line, never an overwrite."""
    path = RESULT_LOG if path is None else path
    _validate_line(line)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps(META_LINE, ensure_ascii=False, sort_keys=True) + "\n",
                        encoding="utf-8")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(line), ensure_ascii=False, sort_keys=True) + "\n")


def iter_result_lines(path: Optional[Path] = None) -> Iterator[dict]:
    """Yield non-meta result records. Missing file yields nothing."""
    path = RESULT_LOG if path is None else path
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            record = json.loads(raw)
        except ValueError:
            continue
        if isinstance(record, dict) and record.get("kind") == KIND:
            yield record


def lines_for_contract(contract_id: str, path: Optional[Path] = None) -> list[dict]:
    """Every result line for a contract, in append order (last is the current correction).

    ``path`` resolves at CALL time so the log location stays overridable (module-level default
    arguments would freeze it at import).
    """
    return [r for r in iter_result_lines(path) if r.get("contract_id") == contract_id]


# --- the F-083 scan ----------------------------------------------------------------------------


def scanned_instance_paths(root: Path = _ROOT) -> list[Path]:
    """TRACKED `instances/MC-*.json` only.

    Deliberately `git ls-files`, not a filesystem glob: three instances are untracked today and one
    of them backs a published finding, so a disk-based universe gives a different verdict in every
    clone — the F-071 class this surface exists to prevent. Same instrument as
    `tests/test_current_findings.py`'s evidence-resolvability gate.

    Out of scan by construction: `drafts/`, the MP-* profiles, and the parent-directory
    `MC-CPR-L0-XAUUSD-M15-UTC-V1.json` (`mt00: PARTIAL`), which is not rewritten.
    """
    rel = "configs/research/measurement_contracts/instances"
    try:
        out = subprocess.run(
            ["git", "ls-files", f"{rel}/MC-*.json"],
            capture_output=True, text=True, timeout=60, check=False, cwd=root,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    paths = []
    for name in out.splitlines():
        name = name.strip()
        if name:
            paths.append(root / name)
    return sorted(paths)


def audit_instance(path: Path, root: Path = _ROOT, log: Optional[Path] = None) -> dict:
    """F-083 verdict for one instance: is a non-UNRUN claim backed by a real result line?

    Returns ``{contract_id, mt00, ok, problems}``. ``mt00 == UNRUN`` is always ``ok`` — UNRUN is
    honest and needs no result line. There is no "not applicable" status.
    """
    problems: list[str] = []
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"contract_id": path.stem, "mt00": None, "ok": False,
                "problems": [f"unreadable instance: {exc}"]}

    contract_id = doc.get("contract_id") or path.stem
    mt00 = (doc.get("trust_status") or {}).get("mt00")

    if mt00 == "UNRUN":
        return {"contract_id": contract_id, "mt00": mt00, "ok": True, "problems": []}
    if contract_id in _F083_GRANDFATHER:
        return {"contract_id": contract_id, "mt00": mt00, "ok": True,
                "problems": ["grandfathered (shrink-only pin)"]}

    lines = lines_for_contract(contract_id, log)
    if not lines:
        problems.append(
            f"trust_status.mt00={mt00!r} but no result line in {RESULT_LOG.name} — F-083: "
            "declared-but-unexecuted is indistinguishable from executed"
        )
        return {"contract_id": contract_id, "mt00": mt00, "ok": False, "problems": problems}

    line = lines[-1]
    if not line.get("declared_artifacts_exist"):
        problems.append("result line reports declared_artifacts_exist=false")
    hashes = line.get("artifact_hashes") or {}
    for key, declared in (doc.get("evidence_artifacts") or {}).items():
        if not declared:
            continue
        if declared not in hashes:
            problems.append(f"evidence_artifacts.{key} ({declared}) has no artifact_hashes entry")
            continue
        actual = sha256_file(root / declared)
        if actual is None:
            problems.append(f"evidence_artifacts.{key} ({declared}) is not readable")
        elif actual != hashes[declared]:
            problems.append(f"evidence_artifacts.{key} ({declared}) hash mismatch")
    return {"contract_id": contract_id, "mt00": mt00, "ok": not problems, "problems": problems}


def audit_all(root: Path = _ROOT, log: Optional[Path] = None) -> list[dict]:
    """F-083 audit over the whole tracked scan universe."""
    return [audit_instance(p, root, log) for p in scanned_instance_paths(root)]
