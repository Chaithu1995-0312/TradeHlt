"""
run_identity.py — the canonical Run-Identity authority (EFAP Stage 0/2).

The single source of truth for a run's identity record and for the join gate
that prevents Run A + Run B artifacts from being treated as one object.

Identity record (written as ``run_identity.json`` inside every run dir and carried
on every derived report):

    run_id:             <run_YYYYMMDD_HHMMSS_INSTRUMENT>  — minted once per run
    config_version:     <ACTIVE_VERSION>                   — human config version
    config_hash:        <sha256 from config registry meta>
    dataset_hash:       <sha256 of the consumed CSV/candle range (registered formula,
                        never inlined / never invented)>
    artifact_timestamp: <UTC ISO8601>
    identity_status:    VERIFIED | UNVERIFIED

VERIFIED  ⇔ all five data fields present and non-empty.
UNVERIFIED ⇔ any field missing/unprovable (e.g. historic pre-2026-09-16 runs that
             never recorded hashes). RECOMPUTE != RECOVER: an UNVERIFIED record is
             never silently upgraded, and UNVERIFIED inherits down to every derived
             report built on it.

The join gate (Stage 2) is::

    def can_join(a, b):                    # a, b → RunIdentity records
        if a.identity_status != "VERIFIED": return False
        if b.identity_status != "VERIFIED": return False
        if a.run_id      != b.run_id:         return False
        if a.config_hash != b.config_hash:    return False
        return True

Pure functions + a CLI audit. No side effects on import.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

VERIFIED = "VERIFIED"
UNVERIFIED = "UNVERIFIED"

# Canonical machine-readable join-gate reason codes (CI-greppable, archived with evidence).
DENY_UNVERIFIED_OPERAND = "UNVERIFIED_OPERAND"
DENY_RUN_ID_MISMATCH = "RUN_ID_MISMATCH"
DENY_CONFIG_HASH_MISMATCH = "CONFIG_HASH_MISMATCH"
ALLOW_REASON_CODE = "JOIN_ALLOWED"

_IDENTITY_FIELDS = (
    "run_id",
    "config_version",
    "config_hash",
    "dataset_hash",
    "artifact_timestamp",
    "identity_status",
)


def dataset_hash(filepath: "str | Path") -> str:
    """SHA-256 of a data file's bytes (registered formula — the one place dataset
    hashing is defined). Deterministic: same bytes → same digest."""
    return hashlib.sha256(Path(filepath).read_bytes()).hexdigest()


def _verified(*values: object) -> bool:
    return all(v is not None and str(v).strip() != "" for v in values)


@dataclass(frozen=True)
class RunIdentity:
    """Frozen identity record for one run. All string fields."""

    run_id: str = ""
    config_version: str = ""
    config_hash: str = ""
    dataset_hash: str = ""
    artifact_timestamp: str = ""
    identity_status: str = UNVERIFIED

    @property
    def is_verified(self) -> bool:
        return self.identity_status == VERIFIED

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in _IDENTITY_FIELDS}

    @classmethod
    def from_dict(cls, d: dict) -> "RunIdentity":
        return cls(
            run_id=str(d.get("run_id") or ""),
            config_version=str(d.get("config_version") or ""),
            config_hash=str(d.get("config_hash") or ""),
            dataset_hash=str(d.get("dataset_hash") or ""),
            artifact_timestamp=str(d.get("artifact_timestamp") or ""),
            identity_status=str(d.get("identity_status") or UNVERIFIED),
        )

    @classmethod
    def from_json_file(cls, path: "str | Path") -> "RunIdentity":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def can_join(a: RunIdentity, b: RunIdentity) -> tuple[bool, str]:
    """EFAP Stage-2 join gate. Returns (allowed, reason).

    Deny order is load-bearing: any UNVERIFIED operand denies FIRST (closes the
    historical-run loophole), then run identity, then config identity. Each deny
    reason carries a canonical machine-readable code after ``[CODE]``.
    """
    if a.identity_status != VERIFIED:
        return False, (
            f"JOIN DENIED [{DENY_UNVERIFIED_OPERAND}]: "
            f"left artifact identity_status={a.identity_status} (not VERIFIED)"
        )
    if b.identity_status != VERIFIED:
        return False, (
            f"JOIN DENIED [{DENY_UNVERIFIED_OPERAND}]: "
            f"right artifact identity_status={b.identity_status} (not VERIFIED)"
        )
    if a.run_id != b.run_id:
        return False, (
            f"JOIN DENIED [{DENY_RUN_ID_MISMATCH}]: "
            f"cross-run join {a.run_id!r} != {b.run_id!r}"
        )
    if a.config_hash != b.config_hash:
        return False, (
            f"JOIN DENIED [{DENY_CONFIG_HASH_MISMATCH}]: "
            f"config_hash mismatch {a.config_hash[:8]} != {b.config_hash[:8]}"
        )
    return True, f"JOIN ALLOWED [{ALLOW_REASON_CODE}]: {a.run_id}"


def validate_join_artifacts(left_path: "str | Path", right_path: "str | Path") -> tuple[bool, str]:
    """Convenience: can_join() over two on-disk ``run_identity.json`` records."""
    return can_join(
        RunIdentity.from_json_file(left_path),
        RunIdentity.from_json_file(right_path),
    )


def _main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="run_identity", description="EFAP run-identity gate")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pj = sub.add_parser("validate-join", help="deny/allow a join between two run_identity.json records")
    pj.add_argument("left", help="path to a run_identity.json")
    pj.add_argument("right", help="path to a run_identity.json")

    pm = sub.add_parser("show", help="print one run_identity.json record")
    pm.add_argument("path", help="path to a run_identity.json")

    args = ap.parse_args(argv)
    if args.cmd == "validate-join":
        ok, reason = validate_join_artifacts(args.left, args.right)
        print(reason)
        return 0 if ok else 1
    if args.cmd == "show":
        r = RunIdentity.from_json_file(args.path)
        print(json.dumps(r.to_dict(), indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(_main())
def build_identity(
    run_id: str,
    config_version: str,
    config_hash: str,
    dataset_hash: str,
    artifact_timestamp: str | None = None,
) -> RunIdentity:
    """Construct an identity record, computing ``identity_status``.

    VERIFIED requires every data field present AND non-empty. Any missing/unprovable
    field ⇒ UNVERIFIED (never fabricated — RECOMPUTE != RECOVER)."""
    ts = artifact_timestamp or datetime.now(timezone.utc).isoformat()
    status = (
        VERIFIED
        if _verified(run_id, config_version, config_hash, dataset_hash, ts)
        else UNVERIFIED
    )
    return RunIdentity(
        run_id=run_id,
        config_version=config_version,
        config_hash=config_hash,
        dataset_hash=dataset_hash,
        artifact_timestamp=ts,
        identity_status=status,
    )