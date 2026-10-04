"""Archive manifest ledger — every file under ``archive/`` is accounted for, nothing is deleted.

WHY THIS EXISTS
---------------
The research-framework consolidation (plan: shim-in-place, 2026-09-14) shrinks
``scripts/analysis`` + ``scripts/research`` by extracting duplicated helpers into ``src/research``.
Its one hard promise is **zero loss**: before a live file is edited or reduced to a shim, a
byte-exact copy goes to ``archive/<batch>/<original path>`` and a manifest row records its
SHA-256. Before this module, that promise was prose — 26 archived files already had no manifest
row, two manifest schemas coexisted, and nothing checked either. A skipped copy was
indistinguishable from a recorded one (the same silent-gap class as F-079 / F-083).

WHAT IT CHECKS (``verify``)
---------------------------
Violations (fail the floor):
  * a manifest header that is neither the canonical nor the legacy-B schema;
  * an unknown ``action``;
  * a row's archive copy is missing, or its bytes do not hash to the recorded SHA;
  * a live ``original_path`` is missing for any action other than ``moved_to_archive`` /
    ``backfill_archive_copy`` / ``inventory`` (i.e. a delete);
  * a file under ``archive/`` that no archive-copy row (``copied_before_edit`` / ``shimmed`` /
    ``moved_to_archive`` / ``backfill_archive_copy`` / ``inventory``) names — a post-edit row that
    merely points at an archive path does not hash those bytes, so it does not track them;
  * a batch directory (one holding ``MANIFEST.csv``) that ``ARCHIVE_INDEX.md`` never names.

Warnings (reported, never fail): the LATEST post-edit hash recorded for a live path no longer
matches the live file. A later edit by another session does not falsify "this was the hash at
time T", but it is an edit the ledger did not see, so it is surfaced.

SCHEMAS
-------
Canonical (new rows)::

    timestamp_utc,action,original_path,archive_path,sha256_before,reason,sha256_after

Legacy A = canonical minus ``sha256_after``. Legacy B (``utc,action,source,dest,sha256,note``)
is read through ``LEGACY_B_COLUMNS``. Existing files are never rewritten; appends reuse the
file's own header so each file stays internally consistent (§6.2 rule 4, append-discipline).

**Legacy hash semantics.** On legacy ``edited_in_place`` rows the single hash column holds the
POST-edit live hash (the column is misleadingly named ``sha256_before`` in schema A). New rows put
it in ``sha256_after``. ``post_edit_sha()`` hides that difference.

Directories under ``archive/`` that predate the batch convention (no ``MANIFEST.csv``) are
covered by ``archive/LEGACY_INVENTORY.csv`` (action ``inventory``).

Authority: governance hygiene only. Grants no research, promotion, or production authority.
"""
from __future__ import annotations

import csv
import hashlib
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, Optional

_ROOT = Path(__file__).resolve().parents[2]

ARCHIVE_DIRNAME = "archive"
MANIFEST_NAME = "MANIFEST.csv"
MANIFEST_MD_NAME = "MANIFEST.md"
INDEX_NAME = "ARCHIVE_INDEX.md"
LEGACY_INVENTORY_NAME = "LEGACY_INVENTORY.csv"

CANONICAL_COLUMNS: tuple[str, ...] = (
    "timestamp_utc", "action", "original_path", "archive_path", "sha256_before", "reason",
    "sha256_after",
)
LEGACY_A_COLUMNS: tuple[str, ...] = CANONICAL_COLUMNS[:-1]
#: legacy-B header name -> canonical name
LEGACY_B_COLUMNS: dict[str, str] = {
    "utc": "timestamp_utc", "action": "action", "source": "original_path",
    "dest": "archive_path", "sha256": "sha256_before", "note": "reason",
}

# ── action vocabulary ────────────────────────────────────────────────────────────────────────
COPIED_BEFORE_EDIT = "copied_before_edit"      # archive copy of the pre-edit bytes
EDITED_IN_PLACE = "edited_in_place"            # live file changed; post-edit hash recorded
SHIMMED = "shimmed"                            # live file reduced to a thin re-export shim
CREATED = "created"                            # new live file (no archive copy)
MOVED_TO_ARCHIVE = "moved_to_archive"          # live path removed; bytes live in archive only
BACKFILL_ARCHIVE_COPY = "backfill_archive_copy"  # archived file found with no row; hashed later
INVENTORY = "inventory"                        # pre-convention archive content
CORRECTION = "correction"                      # annotates an earlier row; carries no file claim

ACTIONS = frozenset({
    COPIED_BEFORE_EDIT, EDITED_IN_PLACE, SHIMMED, CREATED, MOVED_TO_ARCHIVE,
    BACKFILL_ARCHIVE_COPY, INVENTORY, CORRECTION,
})
#: actions whose row asserts "these archive bytes hash to sha256_before"
ARCHIVE_COPY_ACTIONS = frozenset({
    COPIED_BEFORE_EDIT, SHIMMED, MOVED_TO_ARCHIVE, BACKFILL_ARCHIVE_COPY, INVENTORY,
})
#: actions after which the live original need NOT exist
LIVE_OPTIONAL_ACTIONS = frozenset({MOVED_TO_ARCHIVE, BACKFILL_ARCHIVE_COPY, INVENTORY, CORRECTION})
#: actions that record a post-edit live hash
POST_EDIT_ACTIONS = frozenset({EDITED_IN_PLACE, SHIMMED})

#: never ledger-tracked (interpreter byproducts)
_IGNORED_PARTS = frozenset({"__pycache__"})
_IGNORED_SUFFIXES = frozenset({".pyc", ".pyo"})


# ── rows ─────────────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class ManifestRow:
    manifest: str          # repo-relative posix path of the CSV holding the row
    line: int              # 1-based data-row number within that CSV
    timestamp_utc: str
    action: str
    original_path: str
    archive_path: str
    sha256_before: str
    reason: str
    sha256_after: str = ""
    legacy_schema: bool = False

    def post_edit_sha(self) -> str:
        """Post-edit live hash, hiding the legacy single-column semantics."""
        if self.action not in POST_EDIT_ACTIONS:
            return ""
        if self.sha256_after:
            return self.sha256_after
        return self.sha256_before if (self.legacy_schema and self.action == EDITED_IN_PLACE) else ""


@dataclass
class Report:
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rows: int = 0
    manifests: int = 0
    archive_files: int = 0

    @property
    def ok(self) -> bool:
        return not self.violations

    def as_dict(self) -> dict:
        return {
            "ok": self.ok, "rows": self.rows, "manifests": self.manifests,
            "archive_files": self.archive_files,
            "violations": list(self.violations), "warnings": list(self.warnings),
        }


def sha256_file(path: Path) -> Optional[str]:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _rel(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _header_kind(header: list[str]) -> str:
    cols = tuple(h.strip() for h in header)
    if cols == CANONICAL_COLUMNS:
        return "canonical"
    if cols == LEGACY_A_COLUMNS:
        return "legacy_a"
    if set(cols) == set(LEGACY_B_COLUMNS) and len(cols) == len(LEGACY_B_COLUMNS):
        return "legacy_b"
    return "unknown"


def read_manifest(path: Path, root: Path = _ROOT) -> tuple[str, list[ManifestRow]]:
    """Return ``(header_kind, rows)``. BOM-tolerant. ``header_kind == 'unknown'`` yields no rows."""
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader, [])
        kind = _header_kind(header)
        if kind == "unknown":
            return kind, []
        names = [h.strip() for h in header]
        if kind == "legacy_b":
            names = [LEGACY_B_COLUMNS[n] for n in names]
        rows = []
        for i, values in enumerate(reader, start=1):
            if not any(v.strip() for v in values):
                continue
            rec = dict(zip(names, (v.strip() for v in values)))
            rows.append(ManifestRow(
                manifest=_rel(path, root), line=i,
                timestamp_utc=rec.get("timestamp_utc", ""), action=rec.get("action", ""),
                original_path=rec.get("original_path", ""), archive_path=rec.get("archive_path", ""),
                sha256_before=rec.get("sha256_before", ""), reason=rec.get("reason", ""),
                sha256_after=rec.get("sha256_after", ""), legacy_schema=(kind != "canonical"),
            ))
        return kind, rows


def manifest_paths(root: Path = _ROOT) -> list[Path]:
    archive = root / ARCHIVE_DIRNAME
    found = sorted(archive.glob(f"*/{MANIFEST_NAME}"))
    legacy = archive / LEGACY_INVENTORY_NAME
    if legacy.is_file():
        found.append(legacy)
    return found


def iter_archive_files(root: Path = _ROOT) -> Iterator[Path]:
    """Every file under archive/ that the ledger must account for."""
    archive = root / ARCHIVE_DIRNAME
    top_level_meta = {INDEX_NAME, LEGACY_INVENTORY_NAME}
    for p in sorted(archive.rglob("*")):
        if not p.is_file():
            continue
        rel_parts = p.relative_to(archive).parts
        if len(rel_parts) == 1 and p.name in top_level_meta:
            continue
        if len(rel_parts) == 2 and p.name in (MANIFEST_NAME, MANIFEST_MD_NAME):
            continue
        if _IGNORED_PARTS.intersection(rel_parts) or p.suffix in _IGNORED_SUFFIXES:
            continue
        yield p


# ── verify ───────────────────────────────────────────────────────────────────────────────────
def verify(root: Path = _ROOT) -> Report:
    rep = Report()
    archive = root / ARCHIVE_DIRNAME
    all_rows: list[ManifestRow] = []

    for m in manifest_paths(root):
        rep.manifests += 1
        kind, rows = read_manifest(m, root)
        if kind == "unknown":
            rep.violations.append(f"{_rel(m, root)}: unrecognised manifest header")
            continue
        all_rows.extend(rows)
    rep.rows = len(all_rows)

    covered: set[str] = set()
    latest_post_edit: dict[str, ManifestRow] = {}
    # A legacy copy row that recorded no hash is satisfied by any later row (e.g. a backfill)
    # that hashes the same archive path — history is annotated, never rewritten.
    hashed = {r.archive_path for r in all_rows
              if r.archive_path and r.sha256_before and r.action in ARCHIVE_COPY_ACTIONS}
    for r in all_rows:
        where = f"{r.manifest}:{r.line}"
        if r.action not in ACTIONS:
            rep.violations.append(f"{where}: unknown action {r.action!r}")
            continue
        if r.archive_path and r.action in ARCHIVE_COPY_ACTIONS:
            covered.add(r.archive_path)
        if r.action == CORRECTION:
            continue
        if r.action in ARCHIVE_COPY_ACTIONS:
            a = root / r.archive_path if r.archive_path else None
            got = sha256_file(a) if a else None
            if got is None:
                rep.violations.append(f"{where}: archive copy missing: {r.archive_path or '<empty>'}")
            elif r.sha256_before and got != r.sha256_before:
                rep.violations.append(
                    f"{where}: archive bytes {got[:12]} != recorded sha256_before "
                    f"{r.sha256_before[:12]} ({r.archive_path})")
            elif not r.sha256_before and r.archive_path not in hashed:
                rep.violations.append(f"{where}: {r.action} row carries no sha256_before")
        if r.original_path and r.action not in LIVE_OPTIONAL_ACTIONS:
            if not (root / r.original_path).is_file():
                rep.violations.append(f"{where}: live original missing (delete?): {r.original_path}")
        if r.post_edit_sha() and r.original_path:
            prev = latest_post_edit.get(r.original_path)
            if prev is None or (r.timestamp_utc, r.manifest, r.line) >= (
                    prev.timestamp_utc, prev.manifest, prev.line):
                latest_post_edit[r.original_path] = r

    for path, r in sorted(latest_post_edit.items()):
        live = sha256_file(root / path)
        if live is not None and live != r.post_edit_sha():
            rep.warnings.append(
                f"{r.manifest}:{r.line}: {path} edited after its last recorded post-edit hash "
                f"({r.post_edit_sha()[:12]} -> live {live[:12]})")

    for f in iter_archive_files(root):
        rep.archive_files += 1
        rel = _rel(f, root)
        if rel not in covered:
            rep.violations.append(f"untracked archive file (no manifest row): {rel}")

    index = archive / INDEX_NAME
    index_text = index.read_text(encoding="utf-8") if index.is_file() else ""
    for m in sorted(archive.glob(f"*/{MANIFEST_NAME}")):
        if m.parent.name not in index_text:
            rep.violations.append(f"batch {m.parent.name} not named in {ARCHIVE_DIRNAME}/{INDEX_NAME}")
    return rep


# ── write side (used by consolidation batches) ───────────────────────────────────────────────
def append_rows(manifest: Path, rows: Iterable[dict]) -> int:
    """Append rows (canonical keys) to ``manifest``, keeping that file's own header schema.

    A new file is created with the canonical header. Existing rows are never rewritten.
    """
    rows = list(rows)
    for r in rows:
        if r.get("action") not in ACTIONS:
            raise ValueError(f"unknown action {r.get('action')!r}")
    if manifest.is_file():
        with manifest.open(encoding="utf-8-sig", newline="") as fh:
            header = [h.strip() for h in next(csv.reader(fh), [])]
        kind = _header_kind(header)
        if kind == "unknown":
            raise ValueError(f"{manifest}: unrecognised header, refusing to append")
    else:
        manifest.parent.mkdir(parents=True, exist_ok=True)
        header, kind = list(CANONICAL_COLUMNS), "canonical"
        with manifest.open("w", encoding="utf-8", newline="") as fh:
            csv.writer(fh).writerow(header)
    keys = [LEGACY_B_COLUMNS[name] for name in header] if kind == "legacy_b" else header
    with manifest.open("a", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        for r in rows:
            if kind != "canonical" and r.get("sha256_after"):
                raise ValueError(f"{manifest}: legacy header cannot carry sha256_after")
            w.writerow([r.get(k, "") for k in keys])
    return len(rows)


def snapshot(original: Path, batch_dir: Path, reason: str, root: Path = _ROOT) -> dict:
    """Copy ``original`` byte-exact into ``batch_dir`` (mirroring its repo path); return the row.

    Refuses to overwrite a different existing copy — a batch holds one pre-edit copy per path.
    """
    rel = _rel(original, root)
    dest = batch_dir / rel
    before = sha256_file(original)
    if before is None:
        raise FileNotFoundError(original)
    existing = sha256_file(dest)
    if existing is not None and existing != before:
        raise FileExistsError(f"{dest} already holds different bytes ({existing[:12]})")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if existing is None:
        shutil.copy2(original, dest)
    if sha256_file(dest) != before:
        raise OSError(f"copy of {rel} does not hash-match its source")
    return {
        "timestamp_utc": utc_now(), "action": COPIED_BEFORE_EDIT, "original_path": rel,
        "archive_path": _rel(dest, root), "sha256_before": before, "reason": reason,
        "sha256_after": "",
    }


def backfill_rows(root: Path = _ROOT) -> dict[Path, list[dict]]:
    """Rows that would account for every untracked archive file (dry computation, no writes).

    Files inside a batch dir go to that batch's MANIFEST.csv as ``backfill_archive_copy``; files in
    pre-convention dirs go to ``archive/LEGACY_INVENTORY.csv`` as ``inventory``. The original path
    is inferred only when the file mirrors a repo path that still exists; otherwise left blank.
    """
    archive = root / ARCHIVE_DIRNAME
    covered: set[str] = set()
    for m in manifest_paths(root):
        _, rows = read_manifest(m, root)
        covered.update(r.archive_path for r in rows
                       if r.archive_path and r.sha256_before and r.action in ARCHIVE_COPY_ACTIONS)
    now = utc_now()
    out: dict[Path, list[dict]] = {}
    for f in iter_archive_files(root):
        rel = _rel(f, root)
        if rel in covered:
            continue
        top = f.relative_to(archive).parts[0]
        batch_manifest = archive / top / MANIFEST_NAME
        inside_batch = batch_manifest.is_file()
        mirrored = Path(*f.relative_to(archive / top).parts)
        original = mirrored.as_posix() if (inside_batch and (root / mirrored).is_file()) else ""
        target = batch_manifest if inside_batch else archive / LEGACY_INVENTORY_NAME
        out.setdefault(target, []).append({
            "timestamp_utc": now,
            "action": BACKFILL_ARCHIVE_COPY if inside_batch else INVENTORY,
            "original_path": original, "archive_path": rel, "sha256_before": sha256_file(f),
            "reason": ("backfill: archived without a manifest row; hash taken at backfill time, "
                       "pre-archive provenance unknown") if inside_batch
                      else "inventory: pre-convention archive content; original path unknown",
            "sha256_after": "",
        })
    return out
