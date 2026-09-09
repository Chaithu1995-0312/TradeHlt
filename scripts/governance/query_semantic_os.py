#!/usr/bin/env python3
"""query_semantic_os.py — closed Semantic OS ask + ground CLI.

Thin wrapper. All resolution lives in src/governance/semantic_query.py and
src/governance/semantic_grounding.py.

Usage:
    python scripts/governance/query_semantic_os.py --validate
    python scripts/governance/query_semantic_os.py --summary
    python scripts/governance/query_semantic_os.py --ask authoritative --target CN-001
    python scripts/governance/query_semantic_os.py --ground --kind NOUN --token CN-001
    python scripts/governance/query_semantic_os.py --ground --kind IMPLEMENTATION --token src/core/engine_runner.py --symbol EngineRunner
    python scripts/governance/query_semantic_os.py --ground --kind EVIDENCE --token F-048
    python scripts/governance/query_semantic_os.py --ground --kind RELATIONSHIP --relation owns --source CN-001 --target BD-001
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
for _p in (_ROOT / "src",):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _print(payload: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
        return
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Semantic OS query + closed claim grounding")
    ap.add_argument("--validate", action="store_true", help="validate hand-authored YAML only")
    ap.add_argument("--summary", action="store_true", help="registry + object counts")
    ap.add_argument("--ask", metavar="QUESTION", help="closed question slug (authoritative/owner/...)")
    ap.add_argument("--target", default="", help="question target (id, alias, or path)")
    ap.add_argument("--ground", action="store_true", help="ground a typed claim")
    ap.add_argument(
        "--kind",
        default="NOUN",
        help="NOUN | RELATIONSHIP | IMPLEMENTATION | EVIDENCE | JSONL",
    )
    ap.add_argument(
        "--token",
        default="",
        help="noun / path / evidence id / relation label; JSONL: stream path or "
             "STR-* id (may be empty for a join-only call)",
    )
    ap.add_argument(
        "--relation",
        default="",
        help="closed relation kind when --kind RELATIONSHIP; REQUIRED CC-* id when "
             "--kind JSONL",
    )
    ap.add_argument("--source", default="", help="relationship source")
    ap.add_argument("--dest", dest="target_rel", default="", help="relationship target")
    ap.add_argument("--symbol", default="", help="optional implementation symbol")
    ap.add_argument("--json", action="store_true", help="JSON output (default is also JSON)")
    args = ap.parse_args(argv)

    if args.validate:
        from governance.semantic_os import SemanticOSRegistry

        errors = SemanticOSRegistry.load().validate_all()
        payload = {"ok": not errors, "error_count": len(errors), "errors": [str(e) for e in errors[:50]]}
        _print(payload, True)
        return 0 if not errors else 1

    if args.summary:
        from governance.semantic_query import SemanticIndex

        idx = SemanticIndex.load()
        _print(idx.summary(), True)
        return 0

    if args.ask:
        from governance.semantic_query import SemanticIndex

        idx = SemanticIndex.load()
        answer = idx.answer(args.ask, args.target)
        _print(answer.to_dict(), True)
        return 0 if answer.verdict != "UNANSWERABLE" else 2

    if args.ground:
        from governance.semantic_grounding import SemanticGrounder

        grounder = SemanticGrounder.load()
        # kind=JSONL passes --token AS-IS: an omitted token is legal for a join-only call, and
        # coalescing it to the CC id (as the other kinds do) would silently break that path.
        jsonl = str(args.kind or "").strip().upper() == "JSONL"
        hit = grounder.ground(
            args.kind,
            args.token if jsonl else (args.token or args.relation),
            source=args.source,
            target=args.target_rel or args.target,
            symbol=args.symbol,
            relation=args.relation,
        )
        _print(hit.to_dict(), True)
        return 0 if hit.status == "GROUNDED" else 2

    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
