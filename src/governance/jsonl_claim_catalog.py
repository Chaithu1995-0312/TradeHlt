"""JSONL claim catalog — loader + admissibility over the PRIMARY CAN/CANNOT vocabulary.

Reads ``docs/governance/jsonl_claim_catalog.yaml`` (PRIMARY, hand-authored) and renders the
GENERATED projection ``data/jsonl_claim_catalog.jsonl``. Same PRIMARY -> GENERATED discipline as
``governance.findings_export`` (CLAUDE.md machine-readable truth table): the YAML is the authority,
the JSONL is regenerated and never hand-edited, and rendering twice is byte-identical.

This module answers *admissibility* only — "may this stream close this claim class?" It is
deliberately NOT the grounder: ``ADMITTED`` is not ``GROUNDED``. ``SemanticGrounder.ground_jsonl``
(PR-2) layers the per-class extra checks on top and owns the final status.

SCOPE (CLAUDE.md §6.5): advisory. Cataloguing a stream neither identifies it nor grants it
authority. ``catalog_stream_status`` is the identity-contract §11 census label and is NEVER an
``identity.check.CheckResult.status`` — the two vocabularies are named apart on purpose.

Schema doc: ``docs/reference/schemas.md`` §9.15. Spec: ``docs/governance/JSONL_CLAIM_SURFACE.md``.
"""
from __future__ import annotations

import json
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Optional

_ROOT = Path(__file__).resolve().parents[2]
_CATALOG_YAML = _ROOT / "docs" / "governance" / "jsonl_claim_catalog.yaml"

DEFAULT_OUT = _ROOT / "data" / "jsonl_claim_catalog.jsonl"

SCHEMA_VERSION = "jsonl_claim_catalog/1"

META_LINE = {
    "kind": "meta",
    "schema": SCHEMA_VERSION,
    "source": "docs/governance/jsonl_claim_catalog.yaml",
    "generated_by": "src/governance/jsonl_claim_catalog.py (render)",
    "authority": "advisory",
}

# --- closed vocabularies ----------------------------------------------------------------------

FAMILIES = frozenset({
    "generated_registry",
    "committed_audit",
    "runtime_untracked",
    "parquet_projection",
})

#: Families whose ``path`` may contain a glob. A registry is exactly one file; a runtime tree is not.
GLOB_FAMILIES = frozenset({"runtime_untracked", "parquet_projection"})

POLARITIES = frozenset({"CAN", "CANNOT"})

#: Catalog census labels (identity contract §11). NEVER a CheckResult.status.
CATALOG_STREAM_STATUSES = frozenset({
    "IDENTIFIED",
    "UNIDENTIFIED",
    "CONTAMINATED",
    "UNJOINABLE",
    "N_A",
})

#: Sentinel for a stream that inventories the repository rather than describing the market.
INVENTORY_NOT_MARKET = "INVENTORY_NOT_MARKET"

#: Closed join-endpoint grammar.
PRODUCER_ENDPOINTS = frozenset({"producer:engine", "producer:resolver"})

# admissibility() results — none of these is a grounding status.
ADMITTED, NOT_ADMITTED, UNKNOWN_CLASS, UNKNOWN_STREAM = (
    "ADMITTED", "NOT_ADMITTED", "UNKNOWN_CLASS", "UNKNOWN_STREAM",
)
REFUSED = "REFUSED"

_REQUIRED_STREAM_KEYS = (
    "id", "path", "family", "layer", "catalog_stream_status", "allowed_cc", "forbidden_cc",
    "meaning_authority", "identity_notes", "findings", "primary_source",
)
_REQUIRED_CLASS_KEYS = (
    "id", "polarity", "llm_claim", "against", "why", "catalog_stream_status", "findings",
    "meaning_authority",
)
_REQUIRED_JOIN_KEYS = ("source_str", "target_str", "cc_id")


class CatalogError(ValueError):
    """The PRIMARY catalog is malformed. Fail closed — never fall back to a permissive default."""


# --- loading ----------------------------------------------------------------------------------


def _norm_path(raw: str) -> str:
    """Slash-normalize and strip a leading './'. Does not resolve, does not open."""
    text = str(raw or "").strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text


class Catalog:
    """In-memory view of the PRIMARY catalog. Immutable by convention — do not mutate rows."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.schema_version: str = data["schema_version"]
        self.authority: str = data["authority"]
        self.streams: list[dict] = list(data["streams"])
        self.claim_classes: list[dict] = list(data["claim_classes"])
        self.forbidden_joins: list[dict] = list(data["forbidden_joins"])
        self._by_stream_id = {s["id"]: s for s in self.streams}
        self._by_cc_id = {c["id"]: c for c in self.claim_classes}

    # -- lookups --

    def claim_class(self, cc_id: str) -> Optional[dict]:
        """The CC-* row, or None when the id is outside the closed vocabulary."""
        return self._by_cc_id.get(str(cc_id or "").strip())

    def stream(self, stream_id: str) -> Optional[dict]:
        return self._by_stream_id.get(str(stream_id or "").strip())

    def stream_for_path(self, raw: str) -> Optional[dict]:
        """Resolve a token to its stream row: STR-* id, exact path, glob, or a primary_source.

        Never opens the token. Exact and primary-source matches win over globs so that a
        committed registry is never captured by a ``**`` runtime pattern.
        """
        token = _norm_path(raw)
        if not token:
            return None
        direct = self._by_stream_id.get(token.strip())
        if direct is not None:
            return direct
        for row in self.streams:
            if _norm_path(row["path"]) == token:
                return row
        for row in self.streams:
            primary = row.get("primary_source")
            if primary and _norm_path(primary) == token:
                return row
        for row in self.streams:
            if row["family"] in GLOB_FAMILIES and fnmatch(token, _norm_path(row["path"])):
                return row
        return None

    def join_cc(self, source_str: str, target_str: str) -> Optional[str]:
        """The CC-* refusal id for a forbidden join, else None. Order-insensitive."""
        src, dst = str(source_str or "").strip(), str(target_str or "").strip()
        if not src or not dst:
            return None
        for row in self.forbidden_joins:
            a, b = row["source_str"], row["target_str"]
            if (src == a and dst == b) or (src == b and dst == a):
                return row["cc_id"]
        return None

    def admissibility(self, stream: Optional[dict], cc_id: str) -> str:
        """May this stream close this claim class? ``ADMITTED`` is NOT ``GROUNDED``.

        CANNOT is always REFUSED — a stream that omits it from ``forbidden_cc`` does not soften
        it (``forbidden_cc`` is documentation). A CAN outside the stream's ``allowed_cc`` is
        NOT_ADMITTED: that stream does not close that claim.
        """
        row = self.claim_class(cc_id)
        if row is None:
            return UNKNOWN_CLASS
        if row["polarity"] == "CANNOT":
            return REFUSED
        if stream is None:
            return UNKNOWN_STREAM
        return ADMITTED if row["id"] in stream["allowed_cc"] else NOT_ADMITTED

    # -- projection --

    def records(self) -> list[dict]:
        """Flat GENERATED records in a stable order: streams, then classes, then joins."""
        out: list[dict] = []
        out.extend({"record_kind": "stream", **row} for row in self.streams)
        out.extend({"record_kind": "claim_class", **row} for row in self.claim_classes)
        out.extend({"record_kind": "forbidden_join", **row} for row in self.forbidden_joins)
        return out


def _validate(data: dict[str, Any]) -> None:
    """Structural gate. Raises CatalogError — the loader never returns a partial catalog."""
    if data.get("schema_version") != SCHEMA_VERSION:
        raise CatalogError(f"schema_version must be {SCHEMA_VERSION!r}, got {data.get('schema_version')!r}")
    if data.get("authority") != "advisory":
        raise CatalogError("authority is PINNED to 'advisory' — this surface never grants G001")
    for section in ("streams", "claim_classes", "forbidden_joins"):
        if not isinstance(data.get(section), list) or not data[section]:
            raise CatalogError(f"section {section!r} must be a non-empty list")
    if "generated_by" in data:
        raise CatalogError("generated_by belongs on the GENERATED meta line, not the PRIMARY YAML")

    classes: dict[str, dict] = {}
    for row in data["claim_classes"]:
        missing = [k for k in _REQUIRED_CLASS_KEYS if k not in row]
        if missing:
            raise CatalogError(f"claim_class {row.get('id')!r} missing keys: {missing}")
        cc_id = row["id"]
        if not cc_id.startswith("CC-"):
            raise CatalogError(f"claim_class id must start with 'CC-': {cc_id!r}")
        if cc_id in classes:
            raise CatalogError(f"duplicate claim_class id {cc_id!r}")
        if row["polarity"] not in POLARITIES:
            raise CatalogError(f"{cc_id}: polarity must be CAN|CANNOT, got {row['polarity']!r}")
        if row["catalog_stream_status"] not in CATALOG_STREAM_STATUSES:
            raise CatalogError(f"{cc_id}: bad catalog_stream_status {row['catalog_stream_status']!r}")
        classes[cc_id] = row
    cannot_ids = {i for i, r in classes.items() if r["polarity"] == "CANNOT"}

    seen_streams: set[str] = set()
    for row in data["streams"]:
        missing = [k for k in _REQUIRED_STREAM_KEYS if k not in row]
        if missing:
            raise CatalogError(f"stream {row.get('id')!r} missing keys: {missing}")
        sid = row["id"]
        if not sid.startswith("STR-"):
            raise CatalogError(f"stream id must start with 'STR-': {sid!r}")
        if sid in seen_streams:
            raise CatalogError(f"duplicate stream id {sid!r}")
        seen_streams.add(sid)
        if row["family"] not in FAMILIES:
            raise CatalogError(f"{sid}: unknown family {row['family']!r}")
        if row["catalog_stream_status"] not in CATALOG_STREAM_STATUSES:
            raise CatalogError(f"{sid}: bad catalog_stream_status {row['catalog_stream_status']!r}")
        path = _norm_path(row["path"])
        has_glob = any(ch in path for ch in "*?[")
        if has_glob and row["family"] not in GLOB_FAMILIES:
            raise CatalogError(
                f"{sid}: family {row['family']!r} requires an exact path, got glob {path!r}"
            )
        for key in ("allowed_cc", "forbidden_cc"):
            unknown = [c for c in row[key] if c not in classes]
            if unknown:
                raise CatalogError(f"{sid}: {key} references unknown class(es) {unknown}")
        # The load-bearing invariant: a CANNOT can never be admitted by a stream.
        illegal = sorted(set(row["allowed_cc"]) & cannot_ids)
        if illegal:
            raise CatalogError(
                f"{sid}: allowed_cc lists CANNOT class(es) {illegal} — a refusal cannot be admitted"
            )
        stray = sorted(set(row["forbidden_cc"]) - cannot_ids)
        if stray:
            raise CatalogError(
                f"{sid}: forbidden_cc must be a subset of CANNOT ids, got {stray}"
            )

    for row in data["forbidden_joins"]:
        missing = [k for k in _REQUIRED_JOIN_KEYS if k not in row]
        if missing:
            raise CatalogError(f"forbidden_join {row} missing keys: {missing}")
        if row["cc_id"] not in classes:
            raise CatalogError(f"forbidden_join references unknown class {row['cc_id']!r}")
        if classes[row["cc_id"]]["polarity"] != "CANNOT":
            raise CatalogError(f"forbidden_join {row['cc_id']!r} must be a CANNOT class")
        for endpoint in (row["source_str"], row["target_str"]):
            legal = (
                endpoint in PRODUCER_ENDPOINTS
                or endpoint in seen_streams
                or (endpoint.startswith("family:") and endpoint.split(":", 1)[1] in FAMILIES)
            )
            if not legal:
                raise CatalogError(f"forbidden_join endpoint outside the closed grammar: {endpoint!r}")

    # A pair must resolve to exactly one refusal id (no specialized/generic overlap).
    pairs: dict[frozenset[str], str] = {}
    for row in data["forbidden_joins"]:
        key = frozenset({row["source_str"], row["target_str"]})
        if key in pairs and pairs[key] != row["cc_id"]:
            raise CatalogError(
                f"overlapping forbidden_joins for {sorted(key)}: {pairs[key]} vs {row['cc_id']}"
            )
        pairs[key] = row["cc_id"]


def load_catalog(path: Path = _CATALOG_YAML) -> Catalog:
    """Load + validate the PRIMARY YAML. Raises CatalogError on any structural defect."""
    import yaml  # lazy: keeps importers PyYAML-free until the catalog is actually needed

    if not path.exists():
        raise CatalogError(f"PRIMARY catalog missing: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    _validate(data)
    return Catalog(data)


# --- GENERATED projection ---------------------------------------------------------------------


def render(catalog: Optional[Catalog] = None) -> str:
    """Meta line + one line per record. Deterministic: no timestamps, sorted keys."""
    cat = catalog if catalog is not None else load_catalog()
    lines = [json.dumps(META_LINE, ensure_ascii=False, sort_keys=True)]
    lines.extend(json.dumps(rec, ensure_ascii=False, sort_keys=True) for rec in cat.records())
    return "\n".join(lines) + "\n"


def export(out: Path = DEFAULT_OUT, catalog: Optional[Catalog] = None) -> int:
    """Write the derived view. Returns the record count (excluding the meta line)."""
    cat = catalog if catalog is not None else load_catalog()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(cat), encoding="utf-8")
    return len(cat.records())


if __name__ == "__main__":  # pragma: no cover - convenience only; the floor calls export()
    print(f"wrote {export()} records to {DEFAULT_OUT}")
