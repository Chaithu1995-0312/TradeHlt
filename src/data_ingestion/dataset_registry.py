"""R3 Dataset Identity registry + load-time admission.

Dataset Identity is the authority. One canonical admitted artifact per bound
dataset; coarser frames are direct ParentCandleBuilder projections (star).
This module does not grant APPROVED / AUTHORITATIVE / ECONOMICALLY_ADMISSIBLE
and does not close OHLCV.

Bound XAUUSD M15 loads reuse ``xauusd_phase1_candidate`` for hash/range.
Unbound instruments path-passthrough (R3 v1 scope). Native HTF CSVs listed
as FORENSIC on a bound dataset cannot enter CandleLoader as a corpus.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

import jsonschema

from data_ingestion.xauusd_phase1_candidate import (
    PHASE1_PHYSICAL_PATH,
    PHASE1_SHA256,
    Phase1CandidateError,
    _sha256_file,
    guard_xauusd_csv_path,
    is_xauusd_m15_request,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = _REPO_ROOT / "docs" / "governance" / "dataset_identity_registry.json"
SCHEMA_PATH = _REPO_ROOT / "docs" / "governance" / "dataset_identity.schema.json"
PRODUCER_ID = "features.parent_candle.ParentCandleBuilder"
PROJECTION_RULES = ("H1", "H4", "D1", "W1", "MN1")
_NATIVE_TF_TOKENS = ("_M1", "_M5", "_H1", "_H4", "_D1", "_W1", "_MN1")

logger = logging.getLogger("CRT.DatasetRegistry")


class DatasetAdmissionError(RuntimeError):
    """Fail-closed corpus admission (R3)."""


@dataclass(frozen=True)
class ProjectionSpec:
    dataset_id: str
    rule: str
    producer: str
    parent: str
    parent_sha256: str
    derivation: str


@dataclass(frozen=True)
class Admission:
    filepath: str
    dataset_id: Optional[str]
    bound: bool
    rewritten: bool


def _posix(path: Path | str) -> str:
    return str(path).replace("\\", "/")


def _rel_posix(path: Path | str, repo_root: Path) -> str:
    p = Path(path)
    try:
        if p.is_absolute():
            return p.resolve().relative_to(repo_root.resolve()).as_posix()
    except (OSError, ValueError):
        pass
    return Path(_posix(path).replace("\\", "/")).as_posix().lstrip("./")


def load_registry_index(path: Optional[Path] = None) -> dict:
    p = path or REGISTRY_PATH
    if not p.is_file():
        raise DatasetAdmissionError(f"dataset identity registry missing: {p}")
    raw = json.loads(p.read_text(encoding="utf-8"))
    if raw.get("unbound_load_policy") != "path_passthrough":
        raise DatasetAdmissionError(
            f"unbound_load_policy {raw.get('unbound_load_policy')!r} "
            "!= path_passthrough (R3 v1)"
        )
    return raw


def load_dataset_record(record_rel: str, *, repo_root: Optional[Path] = None) -> dict:
    root = repo_root or _REPO_ROOT
    p = root / record_rel
    if not p.is_file():
        raise DatasetAdmissionError(f"dataset record missing: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _load_schema(schema_path: Optional[Path] = None) -> dict:
    """SCHEMA_PATH was dead code (assigned, never read) until 2026-09-03 -- BC-4a wiring.

    docs/governance/dataset_identity.schema.json already defines a closed enum for
    volume_semantic (TICK_VOLUME / BASE_ASSET_VOLUME / ... / UNDECLARED) and clock_basis;
    nothing validated against it. _validate_record below hand-rolled a PRESENCE check
    only -- the declared VALUE was never read. Verified before wiring: the one existing
    record (XAUUSD_MT5_PHASE1_20260521) validates cleanly against this schema as-is, so
    turning this on is additive, not a behavior break.
    """
    p = schema_path or SCHEMA_PATH
    if not p.is_file():
        raise DatasetAdmissionError(f"dataset identity schema missing: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def _validate_against_schema(raw: dict, *, schema_path: Optional[Path] = None) -> None:
    """Fail-closed schema validation -- makes the declared vocabulary load-bearing."""
    schema = _load_schema(schema_path)
    try:
        jsonschema.validate(raw, schema)
    except jsonschema.ValidationError as exc:
        raise DatasetAdmissionError(
            f"{raw.get('dataset_id', '<unknown>')}: schema validation failed at "
            f"{'/'.join(str(p) for p in exc.path) or '<root>'}: {exc.message}"
        ) from exc


def _verify_artifact_hash(art: dict, *, root: Path, context: str) -> str:
    """Recompute sha256 of a declared canonical_artifact path and compare -- fail-closed.

    Generalizes the Phase-1 hardcoded-constant check (kept verbatim for
    XAUUSD_MT5_PHASE1_20260521) to any other bound record: a non-Phase-1 record's
    admitted:true claim is only load-bearing if the declared sha256 matches the bytes
    actually on disk, not a self-declared string. Returns the recomputed hash.
    """
    art_path = root / art["path"]
    if not art_path.is_file():
        raise DatasetAdmissionError(f"{context}: canonical_artifact.path missing on disk: {art['path']}")
    recomputed = _sha256_file(art_path)
    if recomputed != art.get("sha256"):
        raise DatasetAdmissionError(
            f"{context}: declared sha256 {art.get('sha256')} != recomputed {recomputed} "
            f"for {art['path']}"
        )
    return recomputed


def _validate_record(raw: dict, *, root: Path) -> None:
    _validate_against_schema(raw)
    required = (
        "dataset_id",
        "symbol",
        "source_family",
        "clock_basis",
        "volume_semantic",
        "decision_status",
        "canonical_artifact",
        "timeframes",
        "load_policy",
        "explicitly_not",
    )
    missing = [k for k in required if k not in raw]
    if missing:
        raise DatasetAdmissionError(f"dataset record missing {missing}")
    if raw["decision_status"] == "APPROVED":
        raise DatasetAdmissionError(
            "R3 v1 forbids APPROVED dataset records; XAUUSD stays "
            "FROZEN_CANDIDATE_PENDING_PHASE1_VALIDATION"
        )
    bans = set(raw.get("explicitly_not") or ())
    need = {"AUTHORITATIVE", "VALIDATED", "ECONOMICALLY_ADMISSIBLE", "APPROVED"}
    if need - bans:
        raise DatasetAdmissionError(
            f"dataset {raw['dataset_id']} must explicitly_not {sorted(need)}"
        )
    art = raw["canonical_artifact"]
    if art.get("timeframe") != "M15" or not art.get("admitted"):
        raise DatasetAdmissionError(
            f"{raw['dataset_id']}: canonical_artifact must be admitted M15"
        )
    if raw["dataset_id"] == "XAUUSD_MT5_PHASE1_20260521":
        # Verbatim pre-multi-dataset check: this one record stays pinned to the exact
        # frozen constants, never to a recomputed hash (the file must literally be the
        # Phase-1 bytes, matching xauusd_phase1_candidate's own hardcoded mirror).
        if art.get("sha256") != PHASE1_SHA256:
            raise DatasetAdmissionError(
                f"{raw['dataset_id']}: canonical sha256 != Phase-1 XAUUSD pin"
            )
        if art.get("path") != PHASE1_PHYSICAL_PATH.as_posix():
            raise DatasetAdmissionError(
                f"{raw['dataset_id']}: canonical path != {PHASE1_PHYSICAL_PATH.as_posix()}"
            )
    else:
        # Any other bound record (R3 multi-dataset): the declared sha256 must match the
        # recomputed hash of the declared path -- fail-closed, not a self-declared string.
        _verify_artifact_hash(art, root=root, context=raw["dataset_id"])
    tfs = raw["timeframes"]
    m15 = tfs.get("M15") or {}
    if m15.get("role") != "canonical_artifact" or not m15.get("admitted"):
        raise DatasetAdmissionError(f"{raw['dataset_id']}: M15 must be canonical_artifact")
    parent_hash = art["sha256"]
    for rule in PROJECTION_RULES:
        slot = tfs.get(rule)
        if not slot:
            raise DatasetAdmissionError(f"{raw['dataset_id']}: missing projection slot {rule}")
        if slot.get("role") != "projection":
            raise DatasetAdmissionError(f"{raw['dataset_id']}: {rule} role must be projection")
        if slot.get("derivation") != "direct":
            raise DatasetAdmissionError(f"{raw['dataset_id']}: {rule} must be derivation: direct")
        if slot.get("parent") != "M15":
            raise DatasetAdmissionError(f"{raw['dataset_id']}: {rule} parent must be M15")
        if slot.get("parent_sha256") != parent_hash:
            raise DatasetAdmissionError(f"{raw['dataset_id']}: {rule} parent_sha256 drift")
        if slot.get("producer") != PRODUCER_ID:
            raise DatasetAdmissionError(
                f"{raw['dataset_id']}: {rule} producer must be {PRODUCER_ID}"
            )
        if slot.get("path"):
            raise DatasetAdmissionError(
                f"{raw['dataset_id']}: projection {rule} must not have a file path"
            )
        if slot.get("admitted"):
            raise DatasetAdmissionError(
                f"{raw['dataset_id']}: projection {rule} must not be admitted as a file"
            )
        if rule == "MN1" and slot.get("parent") == "W1":
            raise DatasetAdmissionError("W1 forbidden as parent of MN1")
    policy = raw["load_policy"]
    if not policy.get("require_hash_match"):
        raise DatasetAdmissionError("load_policy.require_hash_match must be true")
    if not policy.get("reject_forensic_as_canonical"):
        raise DatasetAdmissionError("load_policy.reject_forensic_as_canonical must be true")


def load_bound_datasets(*, repo_root: Optional[Path] = None) -> dict[str, dict]:
    root = repo_root or _REPO_ROOT
    index = load_registry_index(root / "docs" / "governance" / "dataset_identity_registry.json")
    out: dict[str, dict] = {}
    for row in index.get("datasets") or []:
        rec = load_dataset_record(row["record"], repo_root=root)
        if rec.get("dataset_id") != row.get("dataset_id"):
            raise DatasetAdmissionError(
                f"registry dataset_id {row.get('dataset_id')!r} != record {rec.get('dataset_id')!r}"
            )
        _validate_record(rec, root=root)
        out[rec["dataset_id"]] = rec
    # R3 multi-dataset: at most one bound record may claim the legacy bare-XAUUSD_M15*
    # rewrite target. Two claimants is ambiguity that must fail closed at load time,
    # not be silently resolved by iteration order inside admit_csv_path.
    legacy = [ds_id for ds_id, rec in out.items() if rec.get("legacy_rewrite_target")]
    if len(legacy) > 1:
        raise DatasetAdmissionError(
            f"ambiguous legacy_rewrite_target: {len(legacy)} bound records claim it {legacy}; "
            "exactly one is required"
        )
    return out


def projection_spec(dataset_id: str, rule: str, *, repo_root: Optional[Path] = None) -> ProjectionSpec:
    datasets = load_bound_datasets(repo_root=repo_root)
    rec = datasets.get(dataset_id)
    if rec is None:
        raise DatasetAdmissionError(f"unbound dataset_id: {dataset_id}")
    if rule not in PROJECTION_RULES:
        raise DatasetAdmissionError(
            f"{rule} is not a projection of {dataset_id} "
            f"(canonical is {rec['canonical_artifact']['timeframe']}; "
            f"projections={list(PROJECTION_RULES)})"
        )
    slot = rec["timeframes"][rule]
    return ProjectionSpec(
        dataset_id=dataset_id,
        rule=rule,
        producer=str(slot["producer"]),
        parent=str(slot["parent"]),
        parent_sha256=str(slot["parent_sha256"]),
        derivation=str(slot["derivation"]),
    )


def resolve_canonical(dataset_id: str, *, repo_root: Optional[Path] = None) -> Path:
    """Return the admitted canonical CSV after fail-closed hash/range verify.

    XAUUSD_MT5_PHASE1_20260521 keeps its dedicated enforcer (guard_xauusd_csv_path,
    which also checks row count and start/end range, not just the hash). Any other
    bound record is verified generically: recomputed sha256 must match the declared
    one (the same check load_bound_datasets already ran at load time, re-run here so
    a caller resolving long after load still gets a fresh guarantee).
    """
    root = repo_root or _REPO_ROOT
    datasets = load_bound_datasets(repo_root=root)
    rec = datasets.get(dataset_id)
    if rec is None:
        raise DatasetAdmissionError(f"unbound dataset_id: {dataset_id}")
    art = rec["canonical_artifact"]
    if dataset_id == "XAUUSD_MT5_PHASE1_20260521":
        guarded = guard_xauusd_csv_path(art["path"], rec["symbol"], repo_root=root)
        return Path(guarded)
    _verify_artifact_hash(art, root=root, context=dataset_id)
    return root / art["path"]


def _is_forensic_request(filepath: str | Path, instrument: str, rec: dict, repo_root: Path) -> bool:
    rel = _rel_posix(filepath, repo_root)
    forensic = {_posix(p) for p in rec.get("forensic_paths") or []}
    if rel in forensic:
        return True
    name = Path(filepath).name.upper()
    inst = (instrument or rec.get("symbol") or "").upper()
    if inst != rec["symbol"].upper():
        return False
    if is_xauusd_m15_request(filepath, instrument):
        return False
    return any(tok in name for tok in _NATIVE_TF_TOKENS)


def admit_csv_path(
    filepath: str | Path,
    instrument: str = "",
    *,
    repo_root: Optional[Path] = None,
) -> Admission:
    """R3 admission for CandleLoader (multi-dataset).

    Resolution order (fail-closed at every step, never a silent pick):
      1. Path exactly matches a bound record's canonical_artifact.path -> admit that
         record directly. This lets a NEW dataset be addressed by its own explicit path
         even when its filename would otherwise trip the legacy XAUUSD_M15* heuristic.
      2. is_xauusd_m15_request AND exactly one bound record carries
         legacy_rewrite_target:true -> rewrite to that record's canonical artifact
         (preserves the pre-multi-dataset behaviour verbatim: any XAUUSD_M15* request,
         including one that also happens to be a forensic_paths entry, silently
         resolves to the legacy target). Zero legacy targets -> falls through.
      3. Path is a declared forensic_paths entry (or matches the native-HTF-token
         heuristic) of ANY bound record -> reject.
      4. Otherwise unbound passthrough.
    """
    root = repo_root or _REPO_ROOT
    original = str(filepath)
    try:
        datasets = load_bound_datasets(repo_root=root)
    except DatasetAdmissionError:
        raise
    except Phase1CandidateError as exc:
        raise DatasetAdmissionError(str(exc)) from exc

    rel = _rel_posix(filepath, root)

    # Step 1: exact canonical-artifact-path match wins over every heuristic below --
    # this is what lets a NEW dataset be addressed by its own explicit path even when
    # its filename would otherwise trip the legacy XAUUSD_M15* heuristic in step 2.
    for rec in datasets.values():
        if rel == _posix(rec["canonical_artifact"]["path"]):
            return Admission(
                filepath=str(root / rec["canonical_artifact"]["path"]),
                dataset_id=rec["dataset_id"],
                bound=True,
                rewritten=False,
            )

    # Step 2: legacy bare-XAUUSD_M15* rewrite -- exactly one legacy_rewrite_target.
    # load_bound_datasets already fails closed if more than one record claims it.
    # MUST run before step 3 (forensic): the pre-multi-dataset behaviour rewrote ANY
    # XAUUSD_M15*-named request unconditionally, including ones that also appear in
    # some record's forensic_paths (e.g. data/XAUUSD_M15.csv is both) -- preserved
    # verbatim rather than newly forensic-rejected.
    if is_xauusd_m15_request(filepath, instrument):
        legacy = next((r for r in datasets.values() if r.get("legacy_rewrite_target")), None)
        if legacy is not None:
            try:
                guarded = guard_xauusd_csv_path(filepath, instrument or "XAUUSD", repo_root=root)
            except Phase1CandidateError as exc:
                raise DatasetAdmissionError(
                    f"{legacy['dataset_id']} canonical M15 admission failed: {exc}"
                ) from exc
            return Admission(
                filepath=str(guarded),
                dataset_id=legacy["dataset_id"],
                bound=True,
                rewritten=_posix(guarded) != _posix(original)
                and Path(guarded).resolve() != Path(original).resolve()
                if Path(original).exists() or Path(original).is_absolute()
                else _posix(guarded) != _posix(original),
            )

    # Step 3: FORENSIC rejection against every bound record, not just one.
    for rec in datasets.values():
        if _is_forensic_request(filepath, instrument, rec, root):
            raise DatasetAdmissionError(
                f"{rec['dataset_id']}: {filepath} is FORENSIC / NOT_ADMITTED. "
                f"H1/H4/D1/W1/MN1 are direct ParentCandleBuilder projections of admitted M15 "
                f"(parent_timeframe_source={rec.get('parent_timeframe_source')}). "
                f"Do not load native HTF CSVs as corpus authority."
            )

    # Step 4: unbound passthrough.
    return Admission(
        filepath=original,
        dataset_id=None,
        bound=False,
        rewritten=False,
    )
