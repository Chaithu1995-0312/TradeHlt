#!/usr/bin/env python3
"""
RR L1 Freeze Certificate — validate, hash, assert-signed.

Centerpiece: docs/governance/rr_l1_freeze/RR_L1_FREEZE_CERTIFICATE.json

protocol_hash = sha256(canonical JSON of certificate["contract"] only).
L2/L3/L4/epoch must call assert-signed (exit 0) before claiming this freeze.

Usage (repo root):
  python scripts/governance/rr_l1_freeze_certificate.py status
  python scripts/governance/rr_l1_freeze_certificate.py validate
  python scripts/governance/rr_l1_freeze_certificate.py hash [--write]
  python scripts/governance/rr_l1_freeze_certificate.py assert-signed
  python scripts/governance/rr_l1_freeze_certificate.py print-contract-hash
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CERT = (
    REPO_ROOT
    / "docs"
    / "governance"
    / "rr_l1_freeze"
    / "RR_L1_FREEZE_CERTIFICATE.json"
)
UNSET = "__UNSET__"
SCHEMA_ID = "RR_L1_FREEZE_CERTIFICATE_V1"
SIGNED_STATUSES = {"SIGNED"}
BLOCKING_STATUSES_FOR_CONSUMERS = {"UNSIGNED_DRAFT", "READY_FOR_SIGNATURE", "SUPERSEDED"}


def _load(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"certificate not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_contract_bytes(contract: dict) -> bytes:
    """Stable JSON for hashing: sorted keys, no whitespace variance, UTF-8."""
    return json.dumps(
        contract,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def compute_protocol_hash(contract: dict) -> str:
    return hashlib.sha256(_canonical_contract_bytes(contract)).hexdigest()


def _walk_unset(obj: Any, path: str = "contract") -> List[str]:
    found: List[str] = []
    if obj == UNSET:
        found.append(path)
        return found
    if isinstance(obj, dict):
        for k, v in obj.items():
            found.extend(_walk_unset(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            found.extend(_walk_unset(v, f"{path}[{i}]"))
    return found


def _require_keys(d: dict, keys: Iterable[str], where: str) -> List[str]:
    return [f"{where}.{k} missing" for k in keys if k not in d]


def validate(cert: dict, *, require_ready: bool = False) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    if cert.get("schema_id") != SCHEMA_ID:
        errors.append(f"schema_id must be {SCHEMA_ID}")
    for k in (
        "certificate_id",
        "status",
        "contract",
        "protocol_hash",
        "signature",
        "consumption",
        "rc_ids_closed_by_this_certificate",
    ):
        if k not in cert:
            errors.append(f"root missing key: {k}")

    contract = cert.get("contract")
    if not isinstance(contract, dict):
        errors.append("contract must be object")
        return False, errors

    errors.extend(
        _require_keys(
            contract,
            [
                "meta",
                "instrument_universe",
                "sampling",
                "measure_regime",
                "target_definition",
                "structure_mask_policy",
                "feature_list",
                "governing_exit",
                "success_failure_rules",
                "hard_flags",
            ],
            "contract",
        )
    )

    unset_paths = _walk_unset(contract)
    if unset_paths:
        errors.append(f"unset fields ({len(unset_paths)}): " + ", ".join(unset_paths[:20]))
        if len(unset_paths) > 20:
            errors.append(f"... and {len(unset_paths) - 20} more __UNSET__ paths")

    fl = contract.get("feature_list") or {}
    if isinstance(fl, dict):
        names = fl.get("names")
        if not isinstance(names, list) or len(names) < 1:
            errors.append("contract.feature_list.names must be non-empty list")
        if fl.get("names_frozen") is not True and (
            require_ready or cert.get("status") in SIGNED_STATUSES | {"READY_FOR_SIGNATURE"}
        ):
            errors.append("contract.feature_list.names_frozen must be true before READY/SIGNED")

    hf = contract.get("hard_flags") or {}
    if isinstance(hf, dict):
        if hf.get("RR_FUSION_REENABLE") is True:
            errors.append("hard_flags.RR_FUSION_REENABLE must be false for L1 clean-B freeze")
        if hf.get("USE_LEGACY_F022_LABELS_AS_PRIMARY_Y") is True:
            errors.append("hard_flags.USE_LEGACY_F022_LABELS_AS_PRIMARY_Y must be false")
        if hf.get("AUTO_PROMOTE_CONFIG") is True:
            errors.append("hard_flags.AUTO_PROMOTE_CONFIG must be false")

    expected = {"RR-FEAT-005", "RR-LAB-003", "RR-GOV-008", "RR-GOV-004"}
    closed = set(cert.get("rc_ids_closed_by_this_certificate") or [])
    if not expected.issubset(closed):
        errors.append(f"rc_ids_closed_by_this_certificate must include {sorted(expected)}")

    status = cert.get("status")
    ph = cert.get("protocol_hash")
    recomputed = compute_protocol_hash(contract)

    if status in SIGNED_STATUSES | {"READY_FOR_SIGNATURE"}:
        if not unset_paths and fl.get("names_frozen") is True:
            if not ph:
                errors.append("protocol_hash required when READY_FOR_SIGNATURE or SIGNED")
            elif ph != recomputed:
                errors.append(
                    f"protocol_hash mismatch: stored={ph[:16]}… recomputed={recomputed[:16]}…"
                )

    sig = cert.get("signature") or {}
    if status in SIGNED_STATUSES:
        if not sig.get("signed"):
            errors.append("status=SIGNED requires signature.signed=true")
        if not sig.get("signed_by"):
            errors.append("status=SIGNED requires signature.signed_by")
        if not sig.get("signed_at_utc"):
            errors.append("status=SIGNED requires signature.signed_at_utc")
        if not ph or ph != recomputed:
            errors.append("status=SIGNED requires valid protocol_hash matching contract")

    if require_ready and (unset_paths or fl.get("names_frozen") is not True):
        errors.append("not ready: unset fields or names_frozen!=true")

    ok = len(errors) == 0
    return ok, errors


def cmd_status(path: Path) -> int:
    cert = _load(path)
    contract = cert.get("contract") or {}
    unset = _walk_unset(contract) if isinstance(contract, dict) else ["contract invalid"]
    recomputed = (
        compute_protocol_hash(contract) if isinstance(contract, dict) else None
    )
    ph = cert.get("protocol_hash")
    print(f"path:              {path}")
    print(f"certificate_id:    {cert.get('certificate_id')}")
    print(f"status:            {cert.get('status')}")
    print(f"unset_count:       {len(unset)}")
    print(f"names_frozen:      {(contract.get('feature_list') or {}).get('names_frozen')}")
    print(f"protocol_hash:     {ph}")
    print(f"recomputed_hash:   {recomputed}")
    print(f"hash_match:        {ph == recomputed if ph and recomputed else False}")
    print(f"signature.signed:  {(cert.get('signature') or {}).get('signed')}")
    print(f"L2+_allowed:       {cert.get('status') in SIGNED_STATUSES and not unset and ph == recomputed}")
    return 0


def cmd_validate(path: Path) -> int:
    cert = _load(path)
    ok, errors = validate(cert)
    if ok:
        print("VALIDATE: PASS")
        return 0
    print("VALIDATE: FAIL")
    for e in errors:
        print(f"  - {e}")
    return 1


def cmd_hash(path: Path, write: bool) -> int:
    cert = _load(path)
    contract = cert.get("contract")
    if not isinstance(contract, dict):
        print("FAIL: contract missing", file=sys.stderr)
        return 1
    h = compute_protocol_hash(contract)
    print(h)
    if write:
        cert["protocol_hash"] = h
        # Promote draft → ready only when clean
        ok, errors = validate(cert, require_ready=False)
        unset = _walk_unset(contract)
        fl = contract.get("feature_list") or {}
        if not unset and fl.get("names_frozen") is True and cert.get("status") == "UNSIGNED_DRAFT":
            cert["status"] = "READY_FOR_SIGNATURE"
        path.write_text(json.dumps(cert, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote protocol_hash -> {path}", file=sys.stderr)
        if not ok:
            print("note: hash written but validate still FAIL:", file=sys.stderr)
            for e in errors:
                print(f"  - {e}", file=sys.stderr)
    return 0


def cmd_assert_signed(path: Path) -> int:
    """Exit 0 only if consumers may proceed (SIGNED + valid hash + no unset)."""
    cert = _load(path)
    status = cert.get("status")
    if status not in SIGNED_STATUSES:
        print(
            f"ASSERT-SIGNED: FAIL status={status!r} (need SIGNED). "
            f"L2/L3/L4/epoch blocked.",
            file=sys.stderr,
        )
        return 2
    ok, errors = validate(cert)
    if not ok:
        print("ASSERT-SIGNED: FAIL validation", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(
        f"ASSERT-SIGNED: PASS certificate_id={cert.get('certificate_id')} "
        f"protocol_hash={cert.get('protocol_hash')}"
    )
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--cert",
        type=Path,
        default=DEFAULT_CERT,
        help="path to RR_L1_FREEZE_CERTIFICATE.json",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="print freeze status summary")
    sub.add_parser("validate", help="validate structure / unset / hash rules")
    h = sub.add_parser("hash", help="compute protocol_hash from contract")
    h.add_argument(
        "--write",
        action="store_true",
        help="write protocol_hash into the JSON (and promote to READY if clean)",
    )
    sub.add_parser("print-contract-hash", help="alias of hash without write")
    sub.add_parser(
        "assert-signed",
        help="exit 0 only if SIGNED and valid — for L2/L3/L4 consumers",
    )

    args = p.parse_args(argv)
    path = args.cert
    if not path.is_absolute():
        path = (REPO_ROOT / path).resolve()

    if args.cmd == "status":
        return cmd_status(path)
    if args.cmd == "validate":
        return cmd_validate(path)
    if args.cmd in ("hash", "print-contract-hash"):
        write = bool(getattr(args, "write", False))
        return cmd_hash(path, write=write)
    if args.cmd == "assert-signed":
        return cmd_assert_signed(path)
    p.error(f"unknown cmd {args.cmd}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
