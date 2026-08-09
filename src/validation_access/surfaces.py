"""Dual surfaces for VA-XAUUSD-M15: Surface A (CLI) and Surface B (evidence pack).

Separated by design — never merge pack JSON into CLI narrative or vice versa.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from validation_access.ladder import LadderResult, RungResult, RUNG_ORDER

PACK_REL_ROOT = "results/validation_access/xauusd_m15"


def _rung_dict(r: RungResult) -> dict[str, Any]:
    return {
        "code": r.code,
        "name": r.name,
        "status": r.status,
        "summary": r.summary,
        "details": r.details,
        "blockers": r.blockers,
        "evidence_paths": r.evidence_paths,
    }


# ── Surface A: human CLI ─────────────────────────────────────────────────────

def format_cli_report(result: LadderResult) -> str:
    lines = [
        f"=== VALIDATION ACCESS {result.design_id} ===",
        f"instrument={result.instrument}  tf={result.timeframe}  run_id={result.run_id}",
        f"ACTIVE_VERSION={result.active_version}",
        f"started={result.started_utc}  finished={result.finished_utc}",
        f"overall={result.overall_status}",
        f"authority: {result.authority_note}",
        "",
        f"{'Rung':<4} {'Status':<22} {'Name':<32} Summary",
        "-" * 100,
    ]
    for code in RUNG_ORDER:
        r = result.rungs[code]
        lines.append(
            f"{code:<4} {r.status:<22} {r.name:<32} {r.summary}"
        )
    lines += [
        "",
        "Sequence: S → I → F → E (gating).",
        "Surface A = this CLI report only.",
        "Surface B = evidence pack under results/validation_access/xauusd_m15/<run_id>/",
        "",
    ]
    # Compact I modes if present
    i = result.rungs.get("I")
    if i and isinstance(i.details.get("failure_mode_summary"), dict):
        lines.append("I failure modes:")
        for k, v in i.details["failure_mode_summary"].items():
            lines.append(f"  - {k}: {v}")
        lines.append("")
    e = result.rungs.get("E")
    if e and e.status == "OPEN":
        lines.append(
            "E=OPEN is expected until a sealed MC-* exists. "
            "Does not invalidate S/I/F access."
        )
        lines.append("")
    return "\n".join(lines)


def write_cli_summary_md(result: LadderResult, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = [
        f"# Validation Access CLI — {result.design_id}",
        "",
        f"- run_id: `{result.run_id}`",
        f"- instrument: `{result.instrument}` `{result.timeframe}`",
        f"- overall: **{result.overall_status}**",
        f"- ACTIVE_VERSION: `{result.active_version}`",
        "",
        "| Rung | Status | Summary |",
        "|---|---|---|",
    ]
    for code in RUNG_ORDER:
        r = result.rungs[code]
        body.append(f"| {code} | {r.status} | {r.summary} |")
    body += [
        "",
        "> Surface A only. Evidence pack is Surface B (separate files).",
        "",
        format_cli_report(result),
        "",
    ]
    path.write_text("\n".join(body), encoding="utf-8")
    return path


# ── Surface B: LLM evidence pack ─────────────────────────────────────────────

def write_evidence_pack(result: LadderResult, root: Path) -> Path:
    """Write separated evidence pack. Returns pack directory."""
    pack_dir = root / PACK_REL_ROOT / result.run_id
    pack_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "design_id": result.design_id,
        "run_id": result.run_id,
        "instrument": result.instrument,
        "timeframe": result.timeframe,
        "started_utc": result.started_utc,
        "finished_utc": result.finished_utc,
        "active_version": result.active_version,
        "overall_status": result.overall_status,
        "authority_note": result.authority_note,
        "options": result.options,
        "llm_instruction": (
            "Descriptive evidence pack only. Do not promote, size, or claim edge. "
            "Authority ladder §6.5. E=OPEN means no sealed measurement contract."
        ),
        "surfaces": {
            "A": "CLI ladder (ladder_cli.md / stdout) — human",
            "B": "this pack — LLM/archive",
        },
    }
    (pack_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    ladder = {
        "run_id": result.run_id,
        "overall_status": result.overall_status,
        "rung_order": list(RUNG_ORDER),
        "rungs": {code: _rung_dict(result.rungs[code]) for code in RUNG_ORDER},
    }
    (pack_dir / "ladder.json").write_text(
        json.dumps(ladder, indent=2), encoding="utf-8"
    )

    # Per-rung slim files
    s_dir = pack_dir / "S_story"
    s_dir.mkdir(exist_ok=True)
    (s_dir / "golden_summary.json").write_text(
        json.dumps(_rung_dict(result.rungs["S"]), indent=2), encoding="utf-8"
    )

    i_dir = pack_dir / "I_impl"
    i_dir.mkdir(exist_ok=True)
    (i_dir / "harness_summary.json").write_text(
        json.dumps(_rung_dict(result.rungs["I"]), indent=2), encoding="utf-8"
    )

    f_dir = pack_dir / "F_feature"
    f_dir.mkdir(exist_ok=True)
    (f_dir / "surface_summary.json").write_text(
        json.dumps(_rung_dict(result.rungs["F"]), indent=2), encoding="utf-8"
    )

    e_dir = pack_dir / "E_economic"
    e_dir.mkdir(exist_ok=True)
    (e_dir / "measurement_status.json").write_text(
        json.dumps(_rung_dict(result.rungs["E"]), indent=2), encoding="utf-8"
    )

    index_md = [
        f"# Evidence Pack INDEX — {result.design_id}",
        "",
        f"**run_id:** `{result.run_id}`  ",
        f"**overall:** `{result.overall_status}`  ",
        f"**ACTIVE_VERSION:** `{result.active_version}`",
        "",
        "## Files",
        "",
        "| File | Content |",
        "|---|---|",
        "| `manifest.json` | run identity + authority note |",
        "| `ladder.json` | full S→I→F→E machine status |",
        "| `S_story/golden_summary.json` | story six-layer |",
        "| `I_impl/harness_summary.json` | implementation harness |",
        "| `F_feature/surface_summary.json` | feature surface cert |",
        "| `E_economic/measurement_status.json` | measurement contract status |",
        "",
        "## Rung snapshot",
        "",
        "| Rung | Status | Summary |",
        "|---|---|---|",
    ]
    for code in RUNG_ORDER:
        r = result.rungs[code]
        index_md.append(f"| {code} | {r.status} | {r.summary} |")
    index_md += [
        "",
        "> Surface B only. Do not treat this as the human CLI surface.",
        f"> {result.authority_note}",
        "",
    ]
    (pack_dir / "INDEX.md").write_text("\n".join(index_md), encoding="utf-8")

    # Also write Surface A summary beside pack (linked, not merged)
    write_cli_summary_md(result, pack_dir / "ladder_cli.md")

    # Stable LATEST pointer (copy of ladder.json path only)
    latest = root / PACK_REL_ROOT / "LATEST"
    latest.mkdir(parents=True, exist_ok=True)
    (latest / "run_id.txt").write_text(result.run_id + "\n", encoding="utf-8")
    (latest / "ladder.json").write_text(
        json.dumps(ladder, indent=2), encoding="utf-8"
    )
    (latest / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    return pack_dir
