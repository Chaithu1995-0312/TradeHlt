from __future__ import annotations
import argparse
import json
from pathlib import Path
from .core import inventory, load_manifest, validate_manifest, build_plan, write_json, render_report


def main() -> None:
    parser = argparse.ArgumentParser(prog="research-ssot", description="Intent-driven research inventory and planning MVP")
    sub = parser.add_subparsers(dest="command", required=True)
    p_inv = sub.add_parser("inventory", help="Statically inventory repository Python scripts")
    p_inv.add_argument("--root", required=True)
    p_inv.add_argument("--out", required=True)
    p_inv.add_argument("--include", nargs="*", default=["scripts/analysis", "scripts/research"])
    p_val = sub.add_parser("validate", help="Validate the intent/node manifest")
    p_val.add_argument("--manifest", required=True)
    p_val.add_argument("--out")
    p_plan = sub.add_parser("plan", help="Build deterministic DAG for one intent")
    p_plan.add_argument("--manifest", required=True)
    p_plan.add_argument("--intent", required=True)
    p_plan.add_argument("--out", required=True)
    p_rep = sub.add_parser("report", help="Assemble one final plan report")
    p_rep.add_argument("--plan", required=True)
    p_rep.add_argument("--inventory")
    p_rep.add_argument("--out", required=True)
    args = parser.parse_args()

    if args.command == "inventory":
        data = inventory(args.root, tuple(args.include))
        write_json(args.out, data)
        print(f"Inventory written: {args.out} ({data['script_count']} scripts; static only)")
    elif args.command == "validate":
        manifest = load_manifest(args.manifest)
        issues = validate_manifest(manifest)
        result = {"valid": not any(i["severity"] == "ERROR" for i in issues), "issues": issues}
        if args.out:
            write_json(args.out, result)
        print(json.dumps(result, indent=2))
        if not result["valid"]:
            raise SystemExit(2)
    elif args.command == "plan":
        plan = build_plan(load_manifest(args.manifest), args.intent)
        write_json(args.out, plan)
        print(f"Plan written: {args.out} ({len(plan['ordered_nodes'])} nodes; not executed)")
    elif args.command == "report":
        plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
        inv = json.loads(Path(args.inventory).read_text(encoding="utf-8")) if args.inventory else None
        target = Path(args.out); target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_report(plan, inv), encoding="utf-8")
        print(f"Final report written: {args.out}")

if __name__ == "__main__":
    main()
