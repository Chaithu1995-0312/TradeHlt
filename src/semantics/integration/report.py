"""Integration report: verdict counts per concept, every UNEXPLAINED row, and the D-level table (C8).

D-levels (how far Semantic OS can detect a semantic defect for a concept, in THIS run):
  D1  named only: a concept contract, no representation
  D2  mapped: representations exist, so registry checks (V-6..V-12) apply
  D4  run-witnessed: a comparator produced at least one decidable row on the real corpus
  (D3, a synthetic behaviour comparator, is not enumerated here; a D4 concept has one by construction)
No P&L, expectancy or win rate is computed or written.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

from semantics.integration.checks import AGREE, EXPECTED_DIVERGENCE, NOT_CHECKABLE, UNEXPLAINED, VERDICTS, Row

_MAX_LISTED = 200   # UNEXPLAINED rows written individually to report.md; all are in rows.jsonl


def d_levels(concepts: dict, shards: dict, rows: Iterable[Row]) -> list[dict]:
    reps: dict = defaultdict(int)
    for shard in shards.values():
        for rep in (shard.get("representations") or {}).values():
            if isinstance(rep, dict) and rep.get("concept_id"):
                reps[rep["concept_id"]] += 1
    decided: dict = defaultdict(int)
    for row in rows:
        if row.verdict != NOT_CHECKABLE:
            decided[row.concept_id] += 1
    table = []
    for cid, rec in concepts.items():
        if decided.get(cid):
            level, missing = "D4", ""
        elif reps.get(cid):
            level, missing = "D2", "comparator"
        else:
            level, missing = "D1", "mapping (representation)"
        table.append({"concept_id": cid, "name": rec.get("canonical_name"), "layer": rec.get("layer"),
                      "status": rec.get("status"), "level": level, "representations": reps.get(cid, 0),
                      "decided_rows": decided.get(cid, 0), "missing": missing})
    return table


def inventory(rows: Iterable[Row]) -> list[dict]:
    """Every disagreement (EXPECTED_DIVERGENCE + UNEXPLAINED) grouped by check, concept, slot,
    mechanism note and recorded divergence: the mismatch inventory a fix program starts from."""
    groups: dict = defaultdict(list)
    for row in rows:
        if row.verdict not in (EXPECTED_DIVERGENCE, UNEXPLAINED):
            continue
        slot = row.engine.get("slot") if isinstance(row.engine, dict) else None
        groups[(row.verdict, row.check, row.concept_id, slot, row.note, row.divergence_ref)].append(row.bar)
    return [{"verdict": v, "check": c, "concept_id": cid, "slot": slot, "mechanism": note,
             "divergence_ref": ref, "count": len(bars), "first_bars": bars[:5]}
            for (v, c, cid, slot, note, ref), bars in sorted(groups.items(), key=lambda kv: (kv[0][0], -len(kv[1])))]


def summarize(rows: list[Row], identity: dict, gate: dict, levels: list[dict]) -> dict:
    per: dict = defaultdict(Counter)
    for row in rows:
        per[f"{row.check} {row.concept_id}"][row.verdict] += 1
    return {
        "identity": identity,
        "replay_gate": gate,
        "verdicts": dict(Counter(r.verdict for r in rows)),
        "per_check_concept": {k: {v: c[v] for v in VERDICTS if c[v]} for k, c in sorted(per.items())},
        "d_levels": dict(Counter(item["level"] for item in levels)),
        "note": "Integration test of meaning, not a performance run: no P&L, expectancy or win rate.",
    }


def write_report(out: Path, rows: list[Row], identity: dict, gate: dict, levels: list[dict]) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    with (out / "rows.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row.to_dict(), default=str) + "\n")
    summary = summarize(rows, identity, gate, levels)
    inv = inventory(rows)
    (out / "summary.json").write_text(json.dumps({**summary, "d_level_table": levels, "inventory": inv},
                                                 indent=2, default=str), encoding="utf-8")
    lines = [
        "# Semantic OS integration run", "",
        f"- corpus: `{identity.get('corpus')}` (sha256 `{identity.get('corpus_sha256')}`)",
        f"- config: `{identity.get('config_version')}` hash `{identity.get('config_hash')}`",
        f"- code: `{identity.get('code_sha')}` (dirty: {identity.get('tree_dirty')})",
        f"- replay gate: **{gate.get('status')}** ({gate.get('events', gate.get('observed'))} events)",
        f"- **{summary['verdicts'].get(UNEXPLAINED, 0)} unexplained disagreements among the semantic claims "
        f"exercised by this corpus**; {summary['verdicts'].get(NOT_CHECKABLE, 0)} claims were NOT_CHECKABLE "
        "and say nothing either way",
        f"- verdicts: {summary['verdicts']}", "",
        "Not a performance run: no P&L, expectancy or win rate.", "",
        "## Verdicts per check and concept", "",
        "| check concept | AGREE | EXPECTED_DIVERGENCE | UNEXPLAINED | NOT_CHECKABLE |", "|---|---|---|---|---|",
    ]
    for key, counts in summary["per_check_concept"].items():
        lines.append(f"| {key} | {counts.get(AGREE, 0)} | {counts.get(EXPECTED_DIVERGENCE, 0)} | "
                     f"{counts.get(UNEXPLAINED, 0)} | {counts.get(NOT_CHECKABLE, 0)} |")
    lines += ["", "## Inventory (every disagreement, grouped by mechanism)", "",
              "| verdict | check | concept | slot | mechanism | recorded divergence | count | first bars |",
              "|---|---|---|---|---|---|---|---|"]
    for g in inv:
        lines.append(f"| {g['verdict']} | {g['check']} | {g['concept_id']} | {g['slot'] or ''} | {g['mechanism']} | "
                     f"{g['divergence_ref'] or ''} | {g['count']} | {g['first_bars']} |")
    lines += ["", "## UNEXPLAINED rows (candidate semantic defects)", "",
              "| check | concept | bar | engine | contract | note |", "|---|---|---|---|---|---|"]
    unexplained = [row for row in rows if row.verdict == UNEXPLAINED]
    for row in unexplained[:_MAX_LISTED]:
        lines.append(f"| {row.check} | {row.concept_id} | {row.bar} | `{row.engine}` | `{row.contract}` | {row.note} |")
    if len(unexplained) > _MAX_LISTED:
        lines.append(f"\n{len(unexplained) - _MAX_LISTED} more UNEXPLAINED rows in rows.jsonl (counts in Inventory).")
    lines += ["", "## Detection level per concept (C8)", "",
              f"{summary['d_levels']}", "",
              "| concept | name | layer | status | level | reps | decided rows | missing |", "|---|---|---|---|---|---|---|---|"]
    for item in levels:
        lines.append(f"| {item['concept_id']} | {item['name']} | {item['layer']} | {item['status']} | "
                     f"{item['level']} | {item['representations']} | {item['decided_rows']} | {item['missing']} |")
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary
