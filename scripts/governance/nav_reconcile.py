#!/usr/bin/env python
"""Research Navigator — Phase 1 source reconciliation (READ-ONLY indexer).

Research Navigator UI Specification v0.1 §11 Phase 1 + the Research SSOT Framework
v0.1 ARCHITECTURE.md "read-only overlap map" phase.

This script READS the declared research/documentation source inventories and emits a
DERIVED index (artifacts + relationships) plus a machine-readable reconciliation report.
It is deliberately read-only and non-authoritative:

  * it mutates no source workbook, document, config, or registry;
  * it executes no other repository script;
  * it makes no economic/trading claim and no G001 assertion;
  * it NEVER treats a matching filename or semantic label as artifact identity.

Identity rule (spec §9 / §10): two records are joined ONLY when their normalized full
POSIX paths are equal (a mechanically observed match). A bare-basename or semantic-label
similarity is emitted as an *inferred candidate* with confidence "inferred_candidate",
never as a verified connection. Conflicting identities are preserved, never merged.

Outputs (all under data/, which is gitignored and not a governed surface):
  data/nav_index/artifacts.jsonl      one Artifact per line
  data/nav_index/relationships.jsonl  one ArtifactRelationship per line
  data/nav_index/reconciliation.json  SourceSnapshot + coverage + conflicts + exclusions
  data/nav_index/index.html           self-contained read-only page (embedded payload)

Usage:
  python scripts/governance/nav_reconcile.py [--root PATH] [--out-dir PATH]
                                            [--ssot-inventory PATH]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    import openpyxl
except Exception:  # pragma: no cover - openpyxl is a repo dependency
    openpyxl = None  # type: ignore

# Declared source inventories (relative to --root). Identity semantics differ per source;
# the Navigator preserves those distinctions rather than flattening them (spec §2).
SRC_DOC_TRACKING = "DOC_TRACKING_INDEX.xlsx"
SRC_INTENT_CSV = "docs/research/RESEARCH_SCRIPTS_INTENT_TRACKER.csv"
SRC_BUSINESS = "scripts_business_functionality.xlsx"
SRC_INFRA = "Infrastructure Inventory.xlsx"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256_file(path: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def _norm_posix(p: Any) -> str | None:
    """Normalize a path to POSIX form; return None for empty/non-path values."""
    if p is None:
        return None
    s = str(p).strip().replace("\\", "/")
    if not s:
        return None
    while s.startswith("./"):
        s = s[2:]
    return s


def _clean(v: Any) -> Any:
    """Trim strings; pass through None; stringify other scalars safely."""
    if v is None:
        return None
    if isinstance(v, str):
        v = v.strip()
        return v if v else None
    return v


def _jsonable(v: Any) -> Any:
    """Make a cell safe for the derived JSON index. Datetimes become text."""
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    return str(v)


def _intent_confidence(declared: Any) -> str:
    """Declared only when the source cell has purpose text. Never default to declared."""
    if declared is None:
        return "intent_unstated"
    if isinstance(declared, str) and not declared.strip():
        return "intent_unstated"
    return "declared"


def _row_get(row: dict, *names: str) -> Any:
    """Fetch a cell by exact header, then by case-insensitive header."""
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
    folded = {str(k).casefold(): k for k in row}
    for name in names:
        key = folded.get(name.casefold())
        if key is not None and row[key] not in (None, ""):
            return row[key]
    return None


def _iter_sheet(path: Path, sheet: str) -> Iterable[dict[str, Any]]:
    """Yield each data row of `sheet` as a header-keyed dict (header normalized)."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        if sheet not in wb.sheetnames:
            return
        rows = wb[sheet].iter_rows(values_only=True)
        header = next(rows, None)
        if header is None:
            return
        keys = [(str(h).strip() if h is not None else "") for h in header]
        for r in rows:
            if r is None or all(c is None for c in r):
                continue
            yield {keys[i] if i < len(keys) else "col%d" % i: _clean(r[i])
                   for i in range(len(keys))}
    finally:
        wb.close()



def _read_csv(path: Path) -> Iterable[dict[str, Any]]:
    """Read a CSV into header-keyed dicts (utf-8-sig tolerant, BOM-safe)."""
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            yield {(k.strip() if k else k): _clean(v) for k, v in row.items()}


def _first_present_sheet(path: Path, candidates: tuple[str, ...]) -> str | None:
    """Return the first sheet name among `candidates` present in the workbook."""
    if openpyxl is None:
        return None
    try:
        wb = openpyxl.load_workbook(path, read_only=True)
    except Exception:
        return None
    try:
        names = set(wb.sheetnames)
        for c in candidates:
            if c in names:
                return c
    finally:
        wb.close()
    return None


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


_HTML_TEMPLATE = (
    Path(__file__).resolve().parents[2] / "ui_kits" / "research_navigator" / "template.html"
)
_HTML_MARKER = "__NAV_PAYLOAD__"


def write_html(out_dir: Path, artifacts: list[dict], relationships: list[dict],
               reconciliation: dict) -> Path:
    """Fill the tracked template. The page embeds the payload so file:// can open it.

    It is a view of the derived index. It does not write decisions back and it does
    not reclassify an inferred candidate as a verified join.
    """
    template = _HTML_TEMPLATE.read_text(encoding="utf-8")
    if template.count(_HTML_MARKER) != 1:
        raise RuntimeError("navigator template must contain %s exactly once" % _HTML_MARKER)
    blob = json.dumps(
        {"artifacts": artifacts, "relationships": relationships, "reconciliation": reconciliation},
        ensure_ascii=False, separators=(",", ":"))
    blob = (blob.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))
    dest = out_dir / "index.html"
    dest.write_text(template.replace(_HTML_MARKER, blob, 1), encoding="utf-8")
    return dest


def _freshness_to_lifecycle(fresh: Any) -> str:
    """Map a document Freshness token to a lifecycle observation (still AWAITING confirmation)."""
    s = (str(fresh) or "").strip().lower()
    if s in ("current", "fresh", "active"):
        return "active_observed"
    if s in ("stale", "outdated"):
        return "stale_observed"
    if s in ("historical", "archived", "superseded"):
        return s
    return "unknown"


def _artifact(*, artifact_id: str, artifact_type: str, original_path: str | None,
              source_inventory: str, source_version: str | None, declared_intent: Any,
              intent_confidence: str, classification_basis: str, authority_role: Any = None,
              lifecycle_observed: Any = None, content_hash: Any = None,
              provenance: dict | None = None) -> dict:
    """Build one Artifact record (spec §9). All lifecycle_confirmed default to AWAITING_CONFIRMATION."""
    return {
        "artifact_id": artifact_id, "type": artifact_type, "original_path": original_path,
        "source_inventory": source_inventory, "source_version": source_version,
        "content_hash": content_hash, "declared_intent": declared_intent,
        "authority_role": authority_role, "lifecycle_observed": lifecycle_observed,
        "lifecycle_confirmed": "AWAITING_CONFIRMATION", "intent_confidence": intent_confidence,
        "classification_basis": classification_basis, "provenance": provenance or {},
    }

def _read_doc_tracking(path: Path) -> tuple[list[dict], dict]:
    """Read DOC_TRACKING_INDEX.xlsx / Master_Index. Key = Rel_Path. Preserves authority/freshness."""
    version = _sha256_file(path) or "unknown"
    arts: list[dict] = []
    meta = {"present": True, "file": path.name, "sha256": version, "rows": 0,
            "ambiguity_flagged": 0, "dup_group_gt1": 0, "key": "Rel_Path"}
    sheet = _first_present_sheet(path, ("Master_Index", "Documents", "Sheet1"))
    if sheet is None:
        meta["sheet_found"] = None
        return arts, meta
    meta["sheet"] = sheet
    n = 0
    for r in _iter_sheet(path, sheet):
        n += 1
        rel = _norm_posix(r.get("Rel_Path")) or f"doc_row_{n}"
        if r.get("Ambiguity_Flag"):
            meta["ambiguity_flagged"] += 1
        dg = r.get("Dup_Group_Size")
        if isinstance(dg, (int, float)) and dg > 1:
            meta["dup_group_gt1"] += 1
        declared = bool(r.get("Topic") or r.get("Doc_Type"))
        arts.append(_artifact(
            artifact_id="NAV-DOC:" + rel, artifact_type="document", original_path=rel,
            source_inventory=SRC_DOC_TRACKING, source_version=version,
            declared_intent=r.get("Topic"), authority_role=r.get("Authority_Tier"),
            lifecycle_observed=_freshness_to_lifecycle(r.get("Freshness")),
            content_hash=r.get("SHA256_Baseline"),
            intent_confidence="declared" if declared else "intent_unstated",
            classification_basis=("Master_Index Topic/Doc_Type" if declared else "no Topic/Doc_Type"),
            provenance={"doc_type": r.get("Doc_Type"), "freshness": r.get("Freshness"),
                        "latest_in_family": r.get("Latest_In_Family"),
                        "conversion_status": r.get("Conversion_Status"),
                        "story_ids": r.get("Story_IDs"), "ambiguity_flag": r.get("Ambiguity_Flag"),
                        "dup_group_size": dg}))
    meta["rows"] = n
    return arts, meta


def _read_intent_tracker(path: Path) -> tuple[list[dict], dict]:
    """Read RESEARCH_SCRIPTS_INTENT_TRACKER.csv. Key = script_path (POSIX). INTENT_UNSTATED honored."""
    version = _sha256_file(path) or "unknown"
    arts: list[dict] = []
    meta = {"present": True, "file": path.name, "sha256": version, "rows": 0, "key": "script_path"}
    for i, r in enumerate(_read_csv(path), start=1):
        sp = _norm_posix(r.get("script_path")) or f"script_row_{i}"
        unstated = (str(r.get("status_hints") or "").strip().upper() == "INTENT_UNSTATED")
        arts.append(_artifact(
            artifact_id="NAV-SCRIPT:" + sp, artifact_type="script", original_path=sp,
            source_inventory=SRC_INTENT_CSV, source_version=version,
            declared_intent=r.get("intent"), lifecycle_observed=r.get("status_hints"),
            intent_confidence="intent_unstated" if unstated else "declared",
            classification_basis=("INTENT_UNSTATED marker" if unstated else "author-declared intent"),
            provenance={"primary_inputs": r.get("primary_inputs"),
                        "primary_outputs": r.get("primary_outputs"),
                        "related_id": r.get("related_episode_or_id"),
                        "status_hints": r.get("status_hints")}))
    meta["rows"] = len(arts)
    return arts, meta


def _read_business(path: Path) -> tuple[list[dict], dict, dict]:
    """Read scripts_business_functionality.xlsx. File Name may be a bare basename -> flagged.

    Returns (artifacts, meta, by_full_path). We build a full POSIX path but FLAG rows whose
    File Name lacks a slash so their downstream joins remain inferred (spec §10).
    """
    version = _sha256_file(path) or "unknown"
    arts: list[dict] = []
    by_path: dict[str, dict] = {}
    meta = {"present": True, "file": path.name, "sha256": version, "rows": 0,
            "key": "File Name", "basename_only": 0}
    sheet = _first_present_sheet(path, ("Scripts Analysis", "Scripts", "Sheet1"))
    if sheet is None:
        meta["sheet_found"] = None
        return arts, meta, by_path
    meta["sheet"] = sheet
    n = 0
    for r in _iter_sheet(path, sheet):
        raw = _norm_posix(r.get("File Name"))
        if raw is None:
            continue
        n += 1
        is_bare = "/" not in raw
        full = raw if raw.startswith("scripts/") else "scripts/" + raw.lstrip("/")
        if is_bare:
            meta["basename_only"] += 1
        declared = _row_get(r, "Summary of functionality", "Business Functionality", "Purpose")
        disk = _row_get(r, "Disk present")
        tracked = _row_get(r, "Git tracked")
        observed = None
        if disk or tracked:
            observed = "disk_present=%s;git_tracked=%s" % (disk, tracked)
        art = _artifact(
            artifact_id="NAV-BIZ:" + full, artifact_type="script", original_path=full,
            source_inventory=SRC_BUSINESS, source_version=version,
            declared_intent=declared if _intent_confidence(declared) == "declared" else None,
            lifecycle_observed=observed,
            intent_confidence=_intent_confidence(declared),
            classification_basis=("Summary of functionality" if _intent_confidence(declared) == "declared"
                                  else "no Summary of functionality"),
            provenance={"referred_files": _row_get(r, "Referred files", "Referred Files"),
                        "raw_file_name": r.get("File Name"), "basename_only": is_bare,
                        "semantic_id": _row_get(r, "Semantic ID"),
                        "semantic_name": _row_get(r, "Semantic Name"),
                        "filename_semantic_status": _row_get(r, "Filename Semantic Status"),
                        "identity_tier": _jsonable(_row_get(r, "Identity Tier")),
                        "identity_provenance": _row_get(r, "Identity Provenance"),
                        "disk_present": disk, "git_tracked": tracked})
        arts.append(art)
        by_path.setdefault(full, art)
    meta["rows"] = n
    return arts, meta, by_path


def _asset_lookups(assets: list[dict]) -> tuple[dict, dict, dict]:
    """Exact endpoint keys only: asset id, asset name, and '{id} {name}'."""
    by_id: dict[str, str] = {}
    by_name: dict[str, str] = {}
    by_composed: dict[str, str] = {}
    for art in assets:
        prov = art.get("provenance") or {}
        aid = prov.get("asset_id")
        name = prov.get("name")
        if aid:
            by_id[str(aid)] = art["artifact_id"]
        if name:
            by_name[str(name)] = art["artifact_id"]
        if aid and name:
            by_composed["%s %s" % (aid, name)] = art["artifact_id"]
    return by_id, by_name, by_composed


def _resolve_asset_endpoint(raw: Any, by_id: dict, by_name: dict, by_composed: dict) -> tuple[str | None, str]:
    """Resolve a relationship endpoint only on exact key equality."""
    if raw is None:
        return None, "missing"
    text = str(raw).strip()
    if not text or text in {"—", "-"}:
        return None, "missing"
    if text in by_id:
        return by_id[text], "exact_id"
    if text in by_name:
        return by_name[text], "exact_name"
    if text in by_composed:
        return by_composed[text], "exact_id_name"
    return None, "unresolved"


def _read_infrastructure(path: Path) -> tuple[list[dict], list[dict], dict]:
    """Read Infrastructure Inventory.xlsx (Assets + Relationships). Subsystem-level scope."""
    version = _sha256_file(path) or "unknown"
    assets: list[dict] = []
    rels: list[dict] = []
    meta = {"present": True, "file": path.name, "sha256": version, "assets": 0,
            "relationships": 0,
            "scope": "subsystem-level (Location is a directory, not a file census)"}
    asheet = _first_present_sheet(path, ("Assets", "Subsystems", "Sheet1"))
    if asheet:
        n = 0
        for r in _iter_sheet(path, asheet):
            n += 1
            aid = r.get("ID") or f"INV_{n}"
            assets.append(_artifact(
                artifact_id="NAV-SUBSYS:" + str(aid), artifact_type="subsystem",
                original_path=_norm_posix(r.get("Location")),
                source_inventory=SRC_INFRA, source_version=version,
                declared_intent=r.get("Purpose"), authority_role=r.get("Authority"),
                lifecycle_observed=r.get("Status"),
                intent_confidence="declared" if r.get("Purpose") else "intent_unstated",
                classification_basis="subsystem inventory purpose",
                provenance={"asset_id": _jsonable(aid), "name": _jsonable(r.get("Name")),
                            "location_is_directory": True, "inputs": _jsonable(r.get("Inputs")),
                            "outputs": _jsonable(r.get("Outputs")),
                            "dependencies": _jsonable(r.get("Dependencies")),
                            "used_by": _jsonable(r.get("Used By")),
                            "evidence": _jsonable(r.get("Evidence")),
                            "architecture_layer": _jsonable(r.get("Architecture Layer")),
                            "confidence": _jsonable(r.get("Confidence"))}))
        meta["assets"] = n
    by_id, by_name, by_composed = _asset_lookups(assets)
    rsheet = _first_present_sheet(path, ("Relationships", "Dependencies", "Sheet2"))
    if rsheet:
        m = 0
        for r in _iter_sheet(path, rsheet):
            m += 1
            verb = _row_get(r, "Relationship", "Type")
            src_raw = _row_get(r, "Source")
            tgt_raw = _row_get(r, "Target")
            src_id, src_how = _resolve_asset_endpoint(src_raw, by_id, by_name, by_composed)
            tgt_id, tgt_how = _resolve_asset_endpoint(tgt_raw, by_id, by_name, by_composed)
            both = src_id is not None and tgt_id is not None
            rels.append({
                "source": src_id, "target": tgt_id,
                "source_raw": _jsonable(src_raw), "target_raw": _jsonable(tgt_raw),
                "relationship_type": str(verb).strip() if verb else "unknown",
                "evidence": _jsonable(_row_get(r, "Evidence"))
                or "Infrastructure Inventory Relationships sheet",
                "confidence": "mechanically_observed",
                "endpoint_resolution": "exact" if both else "unresolved",
                "source_resolution": src_how, "target_resolution": tgt_how,
                "source_inventory": SRC_INFRA,
            })
        meta["relationships"] = m
        meta["relationships_endpoints_exact"] = sum(
            1 for rel in rels if rel.get("endpoint_resolution") == "exact")
    return assets, rels, meta


def _read_ssot_inventory(ssot: Path | None) -> tuple[list[dict], dict]:
    """Read an OPTIONAL Research SSOT framework inventory.jsonl (untracked prototype).

    Absent by default because researcharctitecuredocs/ is gitignored; only read when the user
    passes --ssot-inventory explicitly.
    """
    if ssot is None:
        return [], {"present": False,
                    "note": "not supplied (researcharctitecuredocs is gitignored)"}
    if not ssot.exists():
        return [], {"present": False, "note": f"supplied path absent: {ssot}"}
    version = _sha256_file(ssot) or "unknown"
    arts: list[dict] = []
    for line in ssot.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        p = _norm_posix(rec.get("path") or rec.get("id"))
        if p is None:
            continue
        arts.append(_artifact(
            artifact_id="NAV-SSOT:" + p, artifact_type="artifact", original_path=p,
            source_inventory="research_ssot_framework", source_version=version,
            declared_intent=rec.get("kind"), content_hash=rec.get("hash"),
            intent_confidence="declared" if rec.get("kind") else "intent_unstated",
            classification_basis="SSOT inventory record", provenance={"ssot": rec}))
    return arts, {"present": True, "file": str(ssot), "sha256": version, "rows": len(arts),
                  "note": "untracked prototype; supplied explicitly via --ssot-inventory"}


# Sheets that are legends or rollups. Every other sheet is row-preserved or typed-indexed.
_EXCLUDED_SHEETS = {
    ("DOC_TRACKING_INDEX.xlsx", "Legend"): "token legend, not an artifact inventory",
    ("DOC_TRACKING_INDEX.xlsx", "Role_Protocol"): "field protocol legend, not an artifact inventory",
    ("DOC_TRACKING_INDEX.xlsx", "Repo_Coverage_Summary"): "banner row, not an artifact inventory",
    ("scripts_business_functionality.xlsx", "Counts"): "metric rollup of Scripts Analysis",
    ("scripts_business_functionality.xlsx", "README"): "workbook readme, not an artifact row",
}
_PATH_KEYS = ("Rel_Path", "LATEST_Path", "Source_Path", "Uncovered_File",
              "Wired_Module_File", "Path", "Target_Doc", "Archive_Path")
_INTENT_KEYS = ("Summary of functionality", "Purpose", "Intent", "Topic", "Role",
                "User_Intent_Slice", "Why_Hot", "Turn_Summary", "Decision", "Notes")
_NONE_REF = {"(none / stdlib-only)", "none", "n/a", "na", "-", "—"}


def _workbook_sheetnames(path: Path) -> list[str]:
    if openpyxl is None or not path.exists():
        return []
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        return list(wb.sheetnames)
    finally:
        wb.close()


def _preserve_sheet(path: Path, sheet: str, source_inventory: str, version: str,
                    id_prefix: str) -> list[dict]:
    """Keep every data row. Domain type stays unknown until a person confirms it."""
    arts: list[dict] = []
    for n, row in enumerate(_iter_sheet(path, sheet), start=1):
        raw_path = None
        for key in _PATH_KEYS:
            raw_path = _norm_posix(_row_get(row, key))
            if raw_path:
                break
        declared = None
        for key in _INTENT_KEYS:
            declared = _row_get(row, key)
            if _intent_confidence(declared) == "declared":
                break
            declared = None
        prov = {k: _jsonable(v) for k, v in row.items() if k}
        prov["sheet"] = sheet
        prov["workbook"] = path.name
        arts.append(_artifact(
            artifact_id="%s:%s:%d" % (id_prefix, sheet, n),
            artifact_type="unknown",
            original_path=raw_path,
            source_inventory=source_inventory,
            source_version=version,
            declared_intent=declared,
            intent_confidence=_intent_confidence(declared),
            classification_basis="row preserved from %s/%s; domain type not confirmed" % (path.name, sheet),
            lifecycle_observed=_jsonable(_row_get(row, "Status", "Freshness")),
            provenance=prov,
        ))
    return arts


def _attach_confidence(path: Path, assets: list[dict]) -> tuple[list[dict], dict]:
    """Join the Confidence sheet only on exact id, name, or '{id} {name}'."""
    unmatched: list[dict] = []
    meta = {"sheet": None, "rows": 0, "exact_matched": 0, "unmatched": 0}
    sheet = _first_present_sheet(path, ("Confidence",))
    if sheet is None:
        return unmatched, meta
    meta["sheet"] = sheet
    by_id, by_name, by_composed = _asset_lookups(assets)
    by_art = {a["artifact_id"]: a for a in assets}
    version = _sha256_file(path) or "unknown"
    n = 0
    for row in _iter_sheet(path, sheet):
        n += 1
        key = str(_row_get(row, "Asset") or "").strip()
        hit = by_id.get(key) or by_name.get(key) or by_composed.get(key)
        if hit and hit in by_art:
            meta["exact_matched"] += 1
            by_art[hit]["provenance"]["confidence_sheet"] = _jsonable(_row_get(row, "Confidence"))
            by_art[hit]["provenance"]["confidence_reason"] = _jsonable(_row_get(row, "Reason"))
            by_art[hit]["provenance"]["confidence_match"] = key
        else:
            meta["unmatched"] += 1
            unmatched.extend(_preserve_sheet_row(path, sheet, row, n, version))
    meta["rows"] = n
    return unmatched, meta


def _preserve_sheet_row(path: Path, sheet: str, row: dict, n: int, version: str) -> list[dict]:
    """One unmatched sheet row, same shape as `_preserve_sheet`."""
    declared = _row_get(row, "Reason", "Notes")
    prov = {k: _jsonable(v) for k, v in row.items() if k}
    prov["sheet"] = sheet
    prov["workbook"] = path.name
    return [_artifact(
        artifact_id="NAV-ROW:INFRA:%s:%d" % (sheet, n),
        artifact_type="unknown",
        original_path=None,
        source_inventory=SRC_INFRA,
        source_version=version,
        declared_intent=declared if _intent_confidence(declared) == "declared" else None,
        intent_confidence=_intent_confidence(declared),
        classification_basis="Confidence row did not exact-match an asset id or name",
        provenance=prov,
    )]


def _read_crt_constructors(path: Path) -> tuple[list[dict], dict]:
    """CRT Constructors rows are path records. They are not joined to other artifacts here."""
    meta = {"sheet": None, "rows": 0}
    sheet = _first_present_sheet(path, ("CRT Constructors",))
    if sheet is None:
        return [], meta
    meta["sheet"] = sheet
    version = _sha256_file(path) or "unknown"
    arts: list[dict] = []
    for n, row in enumerate(_iter_sheet(path, sheet), start=1):
        raw = _norm_posix(_row_get(row, "Path"))
        role = _row_get(row, "Role")
        arts.append(_artifact(
            artifact_id="NAV-CRTCTOR:" + (raw or "row_%d" % n),
            artifact_type="code_module" if raw else "unknown",
            original_path=raw,
            source_inventory=SRC_INFRA,
            source_version=version,
            declared_intent=role if _intent_confidence(role) == "declared" else None,
            authority_role=_row_get(row, "CRT Constructor Architecture"),
            intent_confidence=_intent_confidence(role),
            classification_basis="CRT Constructors Path cell",
            provenance={k: _jsonable(v) for k, v in row.items() if k},
        ))
    meta["rows"] = len(arts)
    return arts, meta


def _referred_tokens(cell: Any) -> list[str]:
    if cell is None:
        return []
    text = str(cell).strip()
    if text.casefold() in _NONE_REF:
        return []
    out: list[str] = []
    for chunk in text.replace("\n", ";").split(";"):
        tok = chunk.strip().strip(",")
        if tok and tok.casefold() not in _NONE_REF:
            out.append(tok)
    return out


def _compare_intent_xlsx(root: Path, intent: list[dict]) -> tuple[list[dict], dict]:
    """The xlsx is a second snapshot. Equal path sets are not indexed twice."""
    path = root / "docs" / "research" / "RESEARCH_SCRIPTS_INTENT_TRACKER.xlsx"
    meta: dict[str, Any] = {"present": path.exists(), "path": str(path)}
    if not path.exists():
        meta["note"] = "xlsx snapshot absent"
        return [], meta
    meta["sha256"] = _sha256_file(path)
    xlsx_intent: dict[str, Any] = {}
    sheet = _first_present_sheet(path, ("research_scripts", "Sheet1"))
    meta["sheet"] = sheet
    if sheet:
        for row in _iter_sheet(path, sheet):
            sp = _norm_posix(_row_get(row, "script_path"))
            if sp:
                xlsx_intent[sp] = row.get("intent")
    csv_intent = {a["original_path"]: a for a in intent if a.get("original_path")}
    only_xlsx = sorted(set(xlsx_intent) - set(csv_intent))
    only_csv = sorted(set(csv_intent) - set(xlsx_intent))
    disagree = []
    for sp, xintent in xlsx_intent.items():
        art = csv_intent.get(sp)
        if art is None:
            continue
        if (art.get("declared_intent") or None) != (xintent or None):
            disagree.append(sp)
            art["provenance"]["intent_xlsx"] = _jsonable(xintent)
            art["provenance"]["intent_disagrees_with_xlsx"] = True
    meta["rows"] = len(xlsx_intent)
    meta["only_xlsx"] = len(only_xlsx)
    meta["only_csv"] = len(only_csv)
    meta["intent_text_disagreements"] = len(disagree)
    meta["disagreement_paths"] = disagree[:20]
    extras: list[dict] = []
    version = meta.get("sha256") or "unknown"
    for sp in only_xlsx:
        extras.append(_artifact(
            artifact_id="NAV-SCRIPTXLSX:" + sp, artifact_type="script", original_path=sp,
            source_inventory="RESEARCH_SCRIPTS_INTENT_TRACKER.xlsx", source_version=version,
            declared_intent=xlsx_intent.get(sp),
            intent_confidence=_intent_confidence(xlsx_intent.get(sp)),
            classification_basis="xlsx path absent from the csv snapshot",
            provenance={"script_path": sp},
        ))
    return extras, meta


def build_index(root: Path, out_dir: Path, ssot_inventory: Path | None) -> dict:
    """Read all declared sources, reconcile identities, and write the derived index + report."""
    ts = _utcnow()
    doc_path = root / SRC_DOC_TRACKING
    intent_path = root / SRC_INTENT_CSV
    biz_path = root / SRC_BUSINESS
    infra_path = root / SRC_INFRA

    missing_sources: list[str] = []
    docs, doc_meta = ([], {"present": False})
    if doc_path.exists():
        docs, doc_meta = _read_doc_tracking(doc_path)
    else:
        missing_sources.append(SRC_DOC_TRACKING)

    intent, intent_meta = ([], {"present": False})
    if intent_path.exists():
        intent, intent_meta = _read_intent_tracker(intent_path)
    else:
        missing_sources.append(SRC_INTENT_CSV)

    biz, biz_meta, biz_by_path = ([], {"present": False}, {})
    if biz_path.exists():
        biz, biz_meta, biz_by_path = _read_business(biz_path)
    else:
        missing_sources.append(SRC_BUSINESS)

    infra_assets, infra_rels, infra_meta = ([], [], {"present": False})
    if infra_path.exists():
        infra_assets, infra_rels, infra_meta = _read_infrastructure(infra_path)
    else:
        missing_sources.append(SRC_INFRA)

    ssot_arts, ssot_meta = _read_ssot_inventory(ssot_inventory)

    preserved: list[dict] = []
    sheet_census: list[dict] = []
    exclusions: list[dict] = [{
        "item": "researcharctitecuredocs/ (SSOT framework)",
        "reason": "gitignored local prototype, not a tracked source; read only "
                  "when --ssot-inventory is explicitly supplied",
    }]
    excluded_rows = 0

    def _note(workbook: str, sheet: str, rows: int, disposition: str, reason: str) -> None:
        sheet_census.append({"workbook": workbook, "sheet": sheet, "rows": rows,
                             "disposition": disposition, "reason": reason})

    def _walk(path: Path, source: str, id_prefix: str, already: dict[str, tuple[int, str]]) -> None:
        nonlocal excluded_rows
        if not path.exists():
            return
        version = _sha256_file(path) or "unknown"
        for sheet in _workbook_sheetnames(path):
            if sheet in already:
                rows, reason = already[sheet]
                _note(path.name, sheet, rows, "indexed", reason)
                continue
            reason = _EXCLUDED_SHEETS.get((path.name, sheet))
            if reason:
                n = sum(1 for _ in _iter_sheet(path, sheet))
                excluded_rows += n
                _note(path.name, sheet, n, "excluded", reason)
                exclusions.append({"item": "%s / %s" % (path.name, sheet), "reason": reason, "rows": n})
                continue
            rows = _preserve_sheet(path, sheet, source, version, id_prefix)
            preserved.extend(rows)
            _note(path.name, sheet, len(rows), "row_preserved",
                  "domain type not confirmed; each row kept as type unknown")

    if doc_path.exists():
        _walk(doc_path, SRC_DOC_TRACKING, "NAV-ROW:DOC", {
            doc_meta.get("sheet") or "Master_Index": (len(docs), "Master_Index document rows"),
        })
    if biz_path.exists():
        _walk(biz_path, SRC_BUSINESS, "NAV-ROW:BIZ", {
            biz_meta.get("sheet") or "Scripts Analysis": (len(biz), "Scripts Analysis rows"),
        })
    confidence_meta = {"rows": 0, "exact_matched": 0, "unmatched": 0}
    crt_arts: list[dict] = []
    crt_meta = {"rows": 0}
    if infra_path.exists():
        unmatched, confidence_meta = _attach_confidence(infra_path, infra_assets)
        preserved.extend(unmatched)
        crt_arts, crt_meta = _read_crt_constructors(infra_path)
        _walk(infra_path, SRC_INFRA, "NAV-ROW:INFRA", {
            "Assets": (infra_meta.get("assets", 0), "subsystem asset rows"),
            "Relationships": (infra_meta.get("relationships", 0), "relationship rows, not artifacts"),
            "Confidence": (confidence_meta.get("rows", 0),
                           "annotation; exact id/name match only, unmatched rows preserved"),
            "CRT Constructors": (crt_meta.get("rows", 0), "code-path rows"),
        })
    xlsx_extras, xlsx_meta = _compare_intent_xlsx(root, intent)
    if xlsx_meta.get("present") and xlsx_meta.get("only_xlsx", 0) == 0 and xlsx_meta.get("only_csv", 0) == 0:
        _note("RESEARCH_SCRIPTS_INTENT_TRACKER.xlsx", xlsx_meta.get("sheet") or "research_scripts",
              xlsx_meta.get("rows", 0), "duplicate_snapshot",
              "path set equals the csv; not indexed a second time")
        exclusions.append({
            "item": "docs/research/RESEARCH_SCRIPTS_INTENT_TRACKER.xlsx",
            "reason": "duplicate snapshot of RESEARCH_SCRIPTS_INTENT_TRACKER.csv "
                      "(path sets equal; intent-text disagreements stay on the csv record)",
            "rows": xlsx_meta.get("rows", 0),
            "intent_text_disagreements": xlsx_meta.get("intent_text_disagreements", 0),
        })
    elif xlsx_meta.get("present"):
        _note("RESEARCH_SCRIPTS_INTENT_TRACKER.xlsx", xlsx_meta.get("sheet") or "research_scripts",
              len(xlsx_extras), "indexed", "paths absent from the csv snapshot")

    # ---- Identity reconciliation: the ONLY verified join is equal normalized full path. ----
    verified_matches: list[dict] = []
    inferred_candidates: list[dict] = []
    intent_by_path = {a["original_path"]: a for a in intent}
    # Only business rows whose File Name carried a slash are path-verified. Basename-only
    # rows have an INFERRED scripts/<name> path and must NEVER verified-join (spec §10).
    biz_by_verified_path = {a["original_path"]: a for a in biz
                            if not a["provenance"].get("basename_only")}
    biz_basenames: dict[str, list[str]] = {}
    for a in biz:
        biz_basenames.setdefault(str(a["original_path"]).rsplit("/", 1)[-1], []).append(
            a["original_path"])
    # (a) Every basename-only business row is itself an unresolved identity candidate.
    for a in biz:
        if a["provenance"].get("basename_only"):
            inferred_candidates.append({
                "kind": "script_identity", "confidence": "inferred_candidate",
                "business_path": a["original_path"],
                "raw_file_name": a["provenance"].get("raw_file_name"),
                "reason": "business File Name is a bare basename; the scripts/ prefix is "
                          "INFERRED — path unverified, NOT joined"})
    # (b) Join intent<->business ONLY on verified full paths.
    for p, iart in intent_by_path.items():
        bart = biz_by_verified_path.get(p)
        if bart is not None:
            verified_matches.append({"key": p, "kind": "script_identity",
                                     "intent_id": iart["artifact_id"],
                                     "business_id": bart["artifact_id"],
                                     "rule": "full normalized POSIX path equality "
                                             "(business File Name carried a slash)"})
        else:
            cands = biz_basenames.get(str(p).rsplit("/", 1)[-1], [])
            if cands:
                inferred_candidates.append({
                    "kind": "script_identity", "confidence": "inferred_candidate",
                    "intent_path": p, "business_candidates": cands,
                    "reason": "basename match only; verified full paths differ — NOT joined"})



    # ---- Relationships -------------------------------------------------------------
    relationships: list[dict] = list(infra_rels)  # observed infra edges (mechanically observed)
    # A script's related_id resolves to a document-family token -> inferred evidence link.
    known_tokens: set[str] = set()
    for a in docs:
        for key in ("latest_in_family", "story_ids"):
            v = a["provenance"].get(key)
            if isinstance(v, str):
                for tok in v.replace(";", ",").split(","):
                    tok = tok.strip()
                    if tok:
                        known_tokens.add(tok)
    for a in intent:
        rid = a["provenance"].get("related_id")
        if isinstance(rid, str) and rid.strip():
            token = rid.strip().split(",")[0].strip()
            if token and token in known_tokens:
                relationships.append({"source": a["artifact_id"], "target": token,
                                      "relationship_type": "provides_evidence_for",
                                      "evidence": "related_id token matched a document-family token",
                                      "confidence": "inferred_candidate",
                                      "source_inventory": SRC_INTENT_CSV})

    all_arts = docs + intent + biz + infra_assets + crt_arts + preserved + xlsx_extras + ssot_arts
    known_paths = {a["original_path"] for a in all_arts
                   if a.get("original_path") and not (a.get("provenance") or {}).get("basename_only")}
    for art in biz:
        for tok in _referred_tokens((art.get("provenance") or {}).get("referred_files")):
            norm = _norm_posix(tok)
            path_shaped = bool(norm and ("/" in norm or norm.endswith(".py")))
            resolved = bool(path_shaped and norm in known_paths)
            relationships.append({
                "source": art["artifact_id"],
                "target": norm if resolved else None,
                "target_raw": tok,
                "relationship_type": "references",
                "evidence": "scripts_business_functionality.xlsx Referred files cell",
                "confidence": "mechanically_observed",
                "endpoint_resolution": "exact_path" if resolved else "unresolved",
                "path_shaped": path_shaped,
                "source_inventory": SRC_BUSINESS,
            })
    by_path: dict[str, list[dict]] = {}
    for art in all_arts:
        opath = art.get("original_path")
        if not opath or (art.get("provenance") or {}).get("basename_only"):
            continue
        by_path.setdefault(opath, []).append(art)
    for opath, group in by_path.items():
        if len(group) < 2:
            continue
        anchor = min(group, key=lambda a: a["artifact_id"])
        for other in group:
            if other["artifact_id"] == anchor["artifact_id"]:
                continue
            relationships.append({
                "source": other["artifact_id"], "target": anchor["artifact_id"],
                "target_raw": opath, "relationship_type": "references",
                "evidence": "equal normalized full POSIX path; records kept separate",
                "confidence": "mechanically_observed", "endpoint_resolution": "exact_path",
                "source_inventory": other.get("source_inventory"),
            })

    total = len(all_arts)
    classified_intent = sum(1 for a in all_arts if a["intent_confidence"] == "declared")
    awaiting = sum(1 for a in all_arts if a["lifecycle_confirmed"] == "AWAITING_CONFIRMATION")
    verified_rels = sum(1 for r in relationships if r.get("endpoint_resolution") in ("exact", "exact_path"))
    unresolved_rels = sum(1 for r in relationships if r.get("endpoint_resolution") == "unresolved")
    inferred_rels = sum(1 for r in relationships if r.get("confidence") == "inferred_candidate")
    indexed_or_preserved = sum(c["rows"] for c in sheet_census if c["disposition"] != "excluded"
                               and c["disposition"] != "duplicate_snapshot")
    discovered_rows = indexed_or_preserved + excluded_rows
    accounted_rows = indexed_or_preserved
    if intent_meta.get("present"):
        # The csv is not a workbook sheet. Count it once in both sides.
        csv_rows = len(intent)
        discovered_rows += csv_rows
        accounted_rows += csv_rows
        _note("RESEARCH_SCRIPTS_INTENT_TRACKER.csv", "csv", csv_rows, "indexed",
              "script intent rows")
    if ssot_meta.get("present"):
        discovered_rows += len(ssot_arts)
        accounted_rows += len(ssot_arts)

    coverage = {
        "inventory": {
            "accounted_for": accounted_rows,
            "discovered_data_rows": discovered_rows,
            "explicitly_excluded_rows": excluded_rows,
            "artifact_rows_with_identity": total,
            "ratio": round(accounted_rows / discovered_rows, 4) if discovered_rows else None,
            "note": "Excluded legend/rollup rows stay in the denominator. "
                    "Duplicate intent xlsx rows are census-only and are not counted twice.",
        },
        "intent": {"with_declared_or_confirmed": classified_intent, "requiring_intent": total,
                   "ratio": round(classified_intent / total, 4) if total else None},
        "lifecycle": {"with_explicit_disposition": 0, "in_scope": total,
                      "awaiting_confirmation": awaiting, "ratio": 0.0},
        "relationship": {"verified_endpoints": verified_rels, "inferred": inferred_rels,
                         "unresolved_endpoints": unresolved_rels,
                         "unresolved_identity_candidates": len(inferred_candidates)},
    }

    reconciliation = {
        "navigator": "Research Navigator", "spec_version": "v0.1", "generated_utc": ts,
        "root": str(root), "authority": "derived_index_not_authority",
        "identity_rule": ("join ONLY on equal normalized full POSIX path; basename/semantic "
                          "similarity = inferred_candidate, never verified"),
        "scope_note": ("Read-only derived index; not an authority registry. Conflicting "
                       "identities are preserved, never merged."),
        "sources": {"doc_tracking": doc_meta, "intent_tracker": intent_meta,
                    "intent_tracker_xlsx": xlsx_meta,
                    "business_functionality": biz_meta, "infrastructure": infra_meta,
                    "confidence_sheet": confidence_meta, "crt_constructors": crt_meta,
                    "ssot_inventory": ssot_meta},
        "counts": {"artifacts_total": total, "documents": len(docs),
                   "scripts_intent": len(intent), "scripts_business": len(biz),
                   "subsystems": len(infra_assets), "crt_constructors": len(crt_arts),
                   "preserved_rows": len(preserved), "ssot_artifacts": len(ssot_arts),
                   "relationships": len(relationships)},
        "verified_identity_matches": verified_matches,
        "inferred_identity_candidates": inferred_candidates,
        "conflicts": {"basename_only_business_rows": biz_meta.get("basename_only", 0),
                      "ambiguity_flagged_documents": doc_meta.get("ambiguity_flagged", 0),
                      "dup_group_gt1_documents": doc_meta.get("dup_group_gt1", 0),
                      "intent_xlsx_text_disagreements": xlsx_meta.get("intent_text_disagreements", 0)},
        "coverage": coverage,
        "sheet_census": sheet_census,
        "awaiting_confirmation": inferred_candidates,
        "missing_sources": missing_sources,
        "exclusions": exclusions,
        "outputs": {
            "artifacts": "artifacts.jsonl",
            "relationships": "relationships.jsonl",
            "reconciliation": "reconciliation.json",
            "html": "index.html",
            "html_note": (
                "Self-contained read-only page. The payload is embedded so the file "
                "opens from disk. The page does not record decisions."
            ),
        },
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(out_dir / "artifacts.jsonl", all_arts)
    _write_jsonl(out_dir / "relationships.jsonl", relationships)
    (out_dir / "reconciliation.json").write_text(
        json.dumps(reconciliation, ensure_ascii=False, indent=2), encoding="utf-8")
    write_html(out_dir, all_arts, relationships, reconciliation)
    return reconciliation


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Research Navigator Phase-1 reconciler (read-only)")
    ap.add_argument("--root", default=None, help="repo root (default: this file's parents[2])")
    ap.add_argument("--out-dir", default=None, help="output dir (default: <root>/data/nav_index)")
    ap.add_argument("--ssot-inventory", default=None,
                    help="optional path to research_ssot_framework inventory.jsonl")
    args = ap.parse_args(argv)

    if openpyxl is None:
        print("FATAL: openpyxl is required to read the workbook sources", file=sys.stderr)
        return 3
    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parents[2]
    out_dir = (Path(args.out_dir).resolve() if args.out_dir
               else root / "data" / "nav_index")
    ssot = Path(args.ssot_inventory).resolve() if args.ssot_inventory else None

    rec = build_index(root, out_dir, ssot)
    c = rec["counts"]
    print("Research Navigator — Phase 1 reconciliation (read-only) -> %s" % out_dir)
    print("  artifacts: %d (docs=%d scripts_intent=%d scripts_biz=%d subsystems=%d ssot=%d)"
          % (c["artifacts_total"], c["documents"], c["scripts_intent"], c["scripts_business"],
             c["subsystems"], c["ssot_artifacts"]))
    print("  verified identity matches: %d | inferred candidates: %d | relationships: %d"
          % (len(rec["verified_identity_matches"]), len(rec["inferred_identity_candidates"]),
             c["relationships"]))
    print("  conflicts: basename_only_business=%d ambiguity_flagged_docs=%d dup_group_gt1_docs=%d"
          % (rec["conflicts"]["basename_only_business_rows"],
             rec["conflicts"]["ambiguity_flagged_documents"],
             rec["conflicts"]["dup_group_gt1_documents"]))
    if rec["missing_sources"]:
        print("  MISSING SOURCES: %s" % ", ".join(rec["missing_sources"]))
    print("  wrote: %s" % (out_dir / "artifacts.jsonl"))
    print("  wrote: %s" % (out_dir / "relationships.jsonl"))
    print("  wrote: %s" % (out_dir / "reconciliation.json"))
    print("  wrote: %s" % (out_dir / "index.html"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

