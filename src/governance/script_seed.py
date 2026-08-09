"""SITS seed pipeline core (PR-6 extract from scripts/governance/seed_script_registry.py).

Applies curated overlays + control-plane reverse-map. Overlay *lists* remain PRIMARY in
the seed CLI (hand-maintained); this module is the pure merge engine.

Inventory authority only — never import from trading spine.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

from governance.script_registry import (
    TERMINAL_LIFECYCLES,
    command_specs_by_script,
    normalize_posix,
)
from utils.jsonl_writer import read_jsonl


def apply_overlays(stubs: list[dict], overlays: list[dict]) -> list[dict]:
    """Match overlays by path or id; overlay fields win (except id)."""
    by_path: dict[str, dict] = {normalize_posix(r["path"]): dict(r) for r in stubs}
    by_id: dict[str, dict] = {r["id"]: by_path[normalize_posix(r["path"])] for r in stubs}

    for ov in overlays:
        target: dict | None = None
        if "id" in ov and ov["id"] in by_id:
            target = by_id[ov["id"]]
        elif "path" in ov:
            p = normalize_posix(ov["path"])
            target = by_path.get(p)
        if target is None:
            key = ov.get("id") or ov.get("path")
            print(f"WARNING: overlay target not found in stubs: {key}", file=sys.stderr)
            continue
        for k, v in ov.items():
            if k == "id":
                continue
            target[k] = v
        by_path[normalize_posix(target["path"])] = target
        by_id[target["id"]] = target

    return list({r["id"]: r for r in by_path.values()}.values())


def apply_control_plane_links(
    records: list[dict],
    *,
    command_by_script: Optional[dict[str, str]] = None,
    descriptions: Optional[dict[str, str]] = None,
    quiet: bool = False,
) -> list[dict]:
    """Mark paths that already have a CommandSpec as ACTIVE CANONICAL_CLI (PR-4)."""
    if command_by_script is None:
        command_by_script = command_specs_by_script()
    descriptions = descriptions or {}

    out: list[dict] = []
    linked = 0
    for rec in records:
        r = dict(rec)
        path = normalize_posix(r.get("path", ""))
        life = r.get("lifecycle")
        if life in TERMINAL_LIFECYCLES:
            out.append(r)
            continue
        cid = command_by_script.get(path)
        if not cid:
            out.append(r)
            continue
        r["category"] = "CANONICAL_CLI"
        r["control_plane_id"] = cid
        if r.get("lifecycle") not in ("ACTIVE", "EPHEMERAL"):
            r["lifecycle"] = "ACTIVE"
        if r.get("lifecycle") == "EPHEMERAL" and not path.startswith("scripts/probes/"):
            r["lifecycle"] = "ACTIVE"
        if (r.get("purpose") or "").strip() in ("", "GRANDFATHER_UNCLASSIFIED"):
            desc = descriptions.get(cid) or f"Control-plane operator command `{cid}`."
            r["purpose"] = desc
        if not r.get("notes"):
            r["notes"] = f"SITS PR-4: linked from CommandSpec {cid}"
        linked += 1
        out.append(r)
    if linked and not quiet:
        print(f"Control-plane reverse-map: linked {linked} CANONICAL_CLI rows", file=sys.stderr)
    return out


def command_descriptions() -> dict[str, str]:
    try:
        from governance.script_registry import _load_core_command_specs

        core_command_specs = _load_core_command_specs()
    except Exception:  # noqa: BLE001
        return {}
    return {s.id: (s.description or s.title or s.id) for s in core_command_specs()}


def build_records(
    stubs_path: Path,
    overlays: list[dict[str, Any]],
    *,
    link_control_plane: bool = True,
) -> list[dict]:
    """Load stubs → overlays → optional CommandSpec reverse-map."""
    if not stubs_path.exists():
        return []
    stubs = read_jsonl(stubs_path)
    records = apply_overlays(stubs, overlays)
    if link_control_plane:
        records = apply_control_plane_links(
            records,
            command_by_script=command_specs_by_script(),
            descriptions=command_descriptions(),
        )
    return records
