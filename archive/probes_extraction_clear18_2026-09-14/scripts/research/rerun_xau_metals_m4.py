#!/usr/bin/env python3
"""Re-run M4 only for xau_metals_protocol_v1 from frozen units_scored.jsonl."""
from __future__ import annotations

import importlib.util
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _load_runner():
    path = ROOT / "scripts/research/run_xau_metals_protocol_v1.py"
    name = "run_xau_metals_v1"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    # Py3.14 dataclasses require module registered before @dataclass executes
    sys.modules[name] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    n_perm = 2000
    if len(sys.argv) > 1:
        n_perm = int(sys.argv[1])

    mod = _load_runner()
    from research.xau_metals_protocol import (
        assert_control_acceptance,
        load_protocol,
        protocol_sha256,
    )

    protocol = load_protocol()
    psha = protocol_sha256()
    out_dir = ROOT / protocol["outputs"]["dir"]
    units_path = out_dir / "units_scored.jsonl"
    if not units_path.exists():
        print(f"ERROR: missing {units_path}", file=sys.stderr)
        return 2

    units = [
        json.loads(line)
        for line in units_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    arms: dict[str, list[int]] = defaultdict(list)
    for i, u in enumerate(units):
        for a in u.get("arms") or []:
            arms[a].append(i)
    arms = dict(arms)

    in_top = ["nb_top_decile" in (u.get("arms") or []) for u in units]
    in_rand = ["random_match_n" in (u.get("arms") or []) for u in units]
    splits = [str(u["split"]) for u in units]
    assert_control_acceptance(in_top=in_top, in_random=in_rand, splits=splits)

    print(f"[M4-rerun] units={len(units)} n_permutations={n_perm}")
    print(f"[M4-rerun] arms={{k: len(v) for k,v in arms.items()}}".replace(
        "{k: len(v) for k,v in arms.items()}",
        str({k: len(v) for k, v in arms.items()}),
    ))

    m4 = mod.run_m4(units, arms, protocol, n_permutations=n_perm)
    for name, r in m4["results"].items():
        reasons = (r.get("reject_reasons") or [])[:1]
        print(
            f"  {name:18s} {r['verdict']:14s} "
            f"E={r.get('expectancy_rr')} PF={r.get('profit_factor')} "
            f"p={r.get('p_value')} reasons={reasons}"
        )
    print(
        f"primary={m4['primary_verdict']} any_PROMOTE={m4['cohort']['any_promote']} "
        f"economic_authority=false"
    )

    run_ts = mod._utc()
    e1 = json.loads((out_dir / "e1_manifest.json").read_text(encoding="utf-8"))
    ledger_path = out_dir / "ledger.jsonl"
    cand_out = out_dir / "candidates.jsonl"
    journals = sorted(out_dir.glob("journal_*.jsonl"), key=lambda p: p.stat().st_mtime)
    journal = journals[-1] if journals else out_dir / "journal_missing.jsonl"

    e2_manifest = {
        "phase": "E2_M4",
        "protocol_id": protocol["protocol_id"],
        "protocol_sha256": psha,
        "run_id": f"xau_metals_v1_m4_{run_ts}",
        "timestamp_utc": run_ts,
        "authority": mod.AUTHORITY,
        "smoke": False,
        "m4_rerun_from_units": True,
        "n_permutations_requested": n_perm,
        "prior_run_n_permutations_note": "units built under 200-perm execute; M4 re-run independent",
        **m4,
        "inputs": {
            "units_scored": str(units_path).replace("\\", "/"),
            "units_sha256": mod._sha256_file(units_path),
            "ledger": str(ledger_path).replace("\\", "/"),
            "ledger_sha256": mod._sha256_file(ledger_path),
            "candidates": str(cand_out).replace("\\", "/"),
            "journal": str(journal).replace("\\", "/"),
            "model": protocol["model"]["path"],
            "model_version": protocol["model"]["version"],
        },
        "e1_kill_context": e1.get("kill"),
        "economic_authority_granted": False,
    }
    e2_path = out_dir / "e2_m4_manifest.json"
    payload = json.dumps(e2_manifest, indent=2, default=str)
    e2_path.write_text(payload, encoding="utf-8")
    (out_dir / f"e2_m4_manifest_{run_ts}.json").write_text(payload, encoding="utf-8")

    exec_path = out_dir / "EXECUTION_RECORD.json"
    rec = json.loads(exec_path.read_text(encoding="utf-8"))
    rec["m4_formal_n_permutations"] = n_perm
    rec["m4_rerun_ts"] = run_ts
    rec["primary_verdict"] = m4["primary_verdict"]
    rec["any_promote"] = m4["cohort"]["any_promote"]
    rec["m4_verdict_counts"] = m4["cohort"]["verdict_counts"]
    rec["e3_allowed"] = m4["cohort"].get("e3_allowed", False)
    rec["economic_authority_granted"] = False
    exec_path.write_text(json.dumps(rec, indent=2, default=str), encoding="utf-8")

    n_train = sum(1 for u in units if u["split"] == "train")
    n_oos = sum(1 for u in units if u["split"] == "oos")
    lines = [
        "# xau_metals_protocol_v1 — execution result",
        "",
        "**Run (units):** 20260722T211010Z",
        f"**M4 formal re-run:** {run_ts} · **n_permutations={n_perm}** (protocol default)",
        f"**protocol_sha256:** `{psha}`",
        "**Authority:** RESEARCH_ONLY · `economic_authority_granted=false`",
        "",
        "## Population",
        "",
        f"- RETEST candidates scored: **{len(units)}** (train {n_train} / oos {n_oos})",
        "- Control acceptance: **PASS**",
        "",
        "## E1 kills (unchanged from unit build)",
        "",
        f"- kills: {e1.get('kill', {}).get('kills_fired')}",
        f"- relative: {e1.get('kill', {}).get('E1_relative', {}).get('verdict')}",
        f"- absolute: {e1.get('kill', {}).get('E1_absolute', {}).get('verdict')}",
        "",
        f"## M4 (n_permutations={n_perm})",
        "",
        "| Hypothesis | Verdict | E[R] | PF | p | reject |",
        "|---|---|---:|---:|---:|---|",
    ]
    for name, r in m4["results"].items():
        reasons = r.get("reject_reasons") or []
        lines.append(
            f"| {name} | {r['verdict']} | {r.get('expectancy_rr')} | "
            f"{r.get('profit_factor')} | {r.get('p_value')} | {reasons[:1]} |"
        )
    lines += [
        "",
        f"**Primary (`nb_top_decile`):** `{m4['primary_verdict']}`",
        f"**any_PROMOTE:** {m4['cohort']['any_promote']}",
        f"**E3 allowed:** {m4['cohort'].get('e3_allowed')}",
        "",
        "## Note",
        "",
        "M4 re-run reused frozen `units_scored.jsonl` from the execute path "
        "(same P1–P5). Gate1 sample and gate2 expectancy do not depend on "
        "permutation count; p-values/BH may differ vs the 200-perm run.",
        "",
    ]
    (out_dir / "PROTOCOL_V1_RESULT.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {e2_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
