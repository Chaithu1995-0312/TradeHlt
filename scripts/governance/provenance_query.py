"""provenance_query.py — read/record CLI over the Provenance Spine (MPA v1).

The ONLY write path into `configs/research/provenance_ledger.jsonl`. Never hand-edit the ledger:
`chain_class` and `chain_complete` are derived, and a hand-written line will disagree with its own
bindings and be rejected on read.

    # read
    python scripts/governance/provenance_query.py --subject FINDING:F-092
    python scripts/governance/provenance_query.py --coverage
    python scripts/governance/provenance_query.py --unresolved --by FINDING

    # write
    python scripts/governance/provenance_query.py --record FINDING:F-092 [--derive]
    python scripts/governance/provenance_query.py --backfill [--dry-run]
    python scripts/governance/provenance_query.py --attest PROMOTION:<ts> --slot evidence \\
        --target docs/analysis/x.md --basis "..." --authority "user 2026-08-26"

Authority: reporting only. A provenance record grants nothing (CLAUDE.md §6.5).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from governance import provenance_derivation as D  # noqa: E402
from governance import provenance_resolver as R  # noqa: E402
from governance.provenance_record import (  # noqa: E402
    LEDGER,
    SLOTS,
    UNKNOWN,
    append_record,
    build_record,
    current_record,
    iter_records,
)

_STATUS_MARK = {"RESOLVED": "OK ", "DANGLING": "?? ", "UNRESOLVED": "-- "}


def _split(token: str) -> tuple[str, str]:
    if ":" not in token:
        raise SystemExit(f"expected SUBJECT_TYPE:ID, got {token!r}")
    kind, _, sid = token.partition(":")
    return kind.strip().upper(), sid.strip()


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _print_chain(chain: R.ChainResult, derived: dict | None = None) -> None:
    print(f"{chain.subject_type} {chain.subject_id}")
    print(f"  source      {chain.source_path}")
    for slot in SLOTS:
        r = chain.slots[slot]
        mark = _STATUS_MARK.get(r.status, "?  ")
        extra = ""
        if derived and slot in derived:
            v = derived[slot]
            b = v[0] if isinstance(v, list) else v
            extra = f"  [+DERIVED {b['derivation']['rule_id']}]"
        print(f"  {mark}{slot:<10} {r.summary}{extra}")
        for blocker in r.blockers:
            print(f"       ! {blocker}")
    print(f"  chain_class {chain.chain_class}   complete={chain.chain_complete}")
    print(f"  NOTE        {chain.authority_note}")


def cmd_subject(token: str, derive: bool) -> int:
    kind, sid = _split(token)
    chain = R.resolve(kind, sid)
    derived = D.derive(kind, sid, chain) if derive else None
    _print_chain(chain, derived)
    existing = current_record(kind, sid)
    print(f"  ledger      {'recorded ' + existing['record_id'] if existing else 'no record yet'}")
    return 0


def cmd_coverage(by: str | None) -> int:
    """Class histogram, never a single percentage — see MPA §H tension 3."""
    from collections import Counter

    per_slot: dict[str, Counter] = {s: Counter() for s in SLOTS}
    chains: Counter = Counter()
    total = 0
    for kind, sid in R.all_subjects():
        if by and kind != by.upper():
            continue
        total += 1
        chain = R.resolve(kind, sid)
        for slot in SLOTS:
            per_slot[slot][chain.slots[slot].status] += 1
        chains[chain.chain_class] += 1

    scope = by.upper() if by else "ALL"
    print(f"provenance coverage — {scope} ({total} subjects)")
    print(f"  {'slot':<12}{'RESOLVED':>10}{'DANGLING':>10}{'UNRESOLVED':>12}")
    for slot in SLOTS:
        c = per_slot[slot]
        print(f"  {slot:<12}{c['RESOLVED']:>10}{c['DANGLING']:>10}{c['UNRESOLVED']:>12}")
    print("  chain_class histogram: " + ", ".join(
        f"{k}={v}" for k, v in sorted(chains.items())) or "  (none)")
    print("  NOTE: a class histogram, deliberately not one percentage — ATTESTED is the weakest "
          "non-UNKNOWN class and propagates, so coverage cannot be inflated by attesting.")
    return 0


def cmd_unresolved(by: str | None) -> int:
    rows = []
    for kind, sid in R.all_subjects():
        if by and kind != by.upper():
            continue
        chain = R.resolve(kind, sid)
        missing = [s for s in SLOTS if chain.slots[s].status == "UNRESOLVED"]
        if missing:
            rows.append((kind, sid, missing))
    print(f"{len(rows)} subject(s) with an unresolved slot — the gap list IS the result")
    for kind, sid, missing in rows[:200]:
        print(f"  {kind:<10} {sid:<52} missing: {','.join(missing)}")
    if len(rows) > 200:
        print(f"  ... {len(rows) - 200} more")
    return 0


def _record_one(kind: str, sid: str, *, derive: bool, notes: str, dry_run: bool) -> str:
    chain = R.resolve(kind, sid)
    slots = chain.bindings_by_slot()
    if derive:
        slots = D.merged_slots(chain, D.derive(kind, sid, chain))
    record = build_record(
        timestamp=_utc(), subject_type=kind, subject_id=sid,
        source_path=chain.source_path, source_sha256=chain.source_sha256,
        slots=slots, notes=notes,
    )
    if not dry_run:
        append_record(record)
    return f"{record['record_id']}  chain_class={record['chain_class']} " \
           f"complete={record['chain_complete']}"


def cmd_record(token: str, derive: bool, notes: str, dry_run: bool) -> int:
    kind, sid = _split(token)
    print(_record_one(kind, sid, derive=derive, notes=notes, dry_run=dry_run))
    if dry_run:
        print("  [DRY-RUN] nothing appended")
    return 0


def cmd_backfill(dry_run: bool, by: str | None) -> int:
    """One record per subject that has at least one binding. Idempotent by construction.

    A subject already carrying an identical chain is SKIPPED rather than re-appended: append-only
    means a second run must be a no-op, not a duplicate.
    """
    written = skipped = empty = 0
    for kind, sid in R.all_subjects():
        if by and kind != by.upper():
            continue
        chain = R.resolve(kind, sid)
        slots = D.merged_slots(chain, D.derive(kind, sid, chain))
        if not any(slots.get(s) for s in SLOTS):
            empty += 1
            continue
        candidate = build_record(
            timestamp=_utc(), subject_type=kind, subject_id=sid,
            source_path=chain.source_path, source_sha256=chain.source_sha256,
            slots=slots,
            notes="MPA v1 backfill: EXPLICIT from the record itself, DERIVED by named rule. "
                  "Never EXPLICIT-by-backfill.",
        )
        existing = current_record(kind, sid)
        if existing and existing.get("slots") == candidate["slots"]:
            skipped += 1
            continue
        if not dry_run:
            append_record(candidate)
        written += 1
    verb = "would append" if dry_run else "appended"
    print(f"backfill: {verb} {written}, skipped {skipped} unchanged, "
          f"{empty} subject(s) with nothing to bind (recorded as UNKNOWN by omission)")
    if dry_run:
        print("  [DRY-RUN] ledger untouched")
    return 0


def cmd_attest(token: str, slot: str, target: str, basis: str, authority: str,
               by_whom: str, dry_run: bool) -> int:
    kind, sid = _split(token)
    if slot not in SLOTS:
        raise SystemExit(f"--slot must be one of {list(SLOTS)}")
    chain = R.resolve(kind, sid)
    binding = D.attestation_binding(
        slot=slot, target_id=target, by=by_whom, utc=_utc(),
        basis=basis, authority=authority,
    )
    slots = chain.bindings_by_slot()
    slots[slot] = [binding] if slot == "evidence" else binding
    record = build_record(
        timestamp=_utc(), subject_type=kind, subject_id=sid,
        source_path=chain.source_path, source_sha256=chain.source_sha256,
        slots=slots,
        notes=f"ATTESTED binding on {slot} — a claim someone stands behind, not a derivation.",
    )
    if not dry_run:
        append_record(record)
    print(f"{record['record_id']}  chain_class={record['chain_class']} (ATTESTED propagates)")
    if dry_run:
        print("  [DRY-RUN] nothing appended")
    return 0


def cmd_ledger() -> int:
    rows = list(iter_records())
    print(f"{LEDGER.relative_to(_ROOT)}: {len(rows)} record(s)")
    from collections import Counter
    print("  chain_class: " + ", ".join(
        f"{k}={v}" for k, v in sorted(Counter(r["chain_class"] for r in rows).items())))
    print("  complete:    " + ", ".join(
        f"{k}={v}" for k, v in sorted(Counter(str(r["chain_complete"]) for r in rows).items())))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--subject", help="SUBJECT_TYPE:ID, e.g. FINDING:F-092")
    ap.add_argument("--coverage", action="store_true")
    ap.add_argument("--unresolved", action="store_true")
    ap.add_argument("--ledger", action="store_true")
    ap.add_argument("--record", help="SUBJECT_TYPE:ID — append one record")
    ap.add_argument("--backfill", action="store_true")
    ap.add_argument("--attest", help="SUBJECT_TYPE:ID — append one ATTESTED binding")
    ap.add_argument("--slot", choices=list(SLOTS))
    ap.add_argument("--target")
    ap.add_argument("--basis", default="")
    ap.add_argument("--authority", default="")
    ap.add_argument("--by", help="attestor for --attest, or subject-type filter for reads")
    ap.add_argument("--derive", action="store_true", help="include DERIVED bindings")
    ap.add_argument("--notes", default="")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    if args.subject:
        return cmd_subject(args.subject, args.derive)
    if args.coverage:
        return cmd_coverage(args.by)
    if args.unresolved:
        return cmd_unresolved(args.by)
    if args.ledger:
        return cmd_ledger()
    if args.record:
        return cmd_record(args.record, args.derive, args.notes, args.dry_run)
    if args.backfill:
        return cmd_backfill(args.dry_run, args.by)
    if args.attest:
        for required in ("slot", "target", "basis", "authority", "by"):
            if not getattr(args, required):
                raise SystemExit(
                    f"--attest requires --{required} — an attestation records who, when, on what "
                    f"basis, and under whose authority"
                )
        return cmd_attest(args.attest, args.slot, args.target, args.basis,
                          args.authority, args.by, args.dry_run)
    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
