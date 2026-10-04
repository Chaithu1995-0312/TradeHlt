"""semantic_identity — Tier-3 derivation for the Semantic File Identity Layer.

Pure, dependency-light module. Computes the machine-derived (Tier 3, LOW confidence) slice of
``file_identity`` records for every code-universe path NOT already claimed by a curated (Tier 1/2)
record in ``docs/governance/semantic_os/file_identities.yaml``.

Why Tier 3 is generated here rather than materialized in the YAML: a Tier-3 row asserts nothing a
human decided — it is a pure path transform. Writing ~700+ of them into a tracked, hand-authored
file is exactly the "generated content in a hand-authored source" anti-pattern
``SemanticOSRegistry.validate_no_derived_in_source`` exists to prevent; a deleted file would leave
a dangling ``physical_path`` if materialized; and ``git diff`` on the curated YAML then shows only
human decisions. See ``docs/governance/SEMANTIC_FILE_IDENTITY_REPORT.md`` §3.

Importable only by ``governance.semantic_os`` and ``governance.semantic_objects`` — this module is
never on the runtime spine (enforced by ``tests/test_semantic_identity.py::
test_identity_layer_touches_no_runtime_module``).
"""
from __future__ import annotations

import re
from typing import Iterable

#: Bumped whenever the derivation algorithm changes. Recorded verbatim in every Tier-3 record's
#: ``derivation`` field, so a machine-made row is unambiguous and its provenance is traceable.
DERIVATION_VERSION = "path_slug/v1"

_DEDUP_SUFFIX_RE = re.compile(r"__\d+$")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def _normalize_segment(raw: str) -> str:
    """Lowercase; non-alphanumeric runs -> single ``_``; strip edges; guard empty/leading-digit."""
    s = _NON_ALNUM_RE.sub("_", raw.lower()).strip("_")
    s = re.sub(r"_+", "_", s)
    if not s:
        return "x"
    if s[0].isdigit():
        s = "x_" + s
    return s


def derive_slug(rel_path: str) -> str:
    """Deterministic, pure function of a repo-relative path -> a dotted lowercase slug.

    ``src/config_layer/crt_engine_v2.py``      -> ``config_layer.crt_engine_v2``
    ``scripts/governance/seed_semantic_os.py`` -> ``scripts.governance.seed_semantic_os``
    ``_scripts_functionality_export.py``       -> ``root.scripts_functionality_export``

    Always at least 2 segments (the id regex requires >=1 dot — see ``semantic_os._ID_RE``),
    which is what guarantees disjointness from single-token MIAR entry ids like ``crt``.
    """
    posix = rel_path.replace("\\", "/")
    trimmed = posix[: -len(".py")] if posix.endswith(".py") else posix
    if trimmed.endswith("/__init__"):
        trimmed = trimmed[: -len("/__init__")]
    if trimmed in ("", "__init__"):
        trimmed = "init"

    if trimmed.startswith("src/"):
        segments = trimmed[len("src/"):].split("/")
    elif trimmed.startswith("scripts/"):
        segments = ["scripts"] + trimmed[len("scripts/"):].split("/")
    else:
        segments = ["root"] + trimmed.split("/")

    segments = [_normalize_segment(s) for s in segments if s]
    if not segments:
        segments = ["root", "unknown"]
    if len(segments) == 1:
        prefix = "src" if posix.startswith("src/") else ("scripts" if posix.startswith("scripts/") else "root")
        segments = [prefix, segments[0]]
    if len(segments) > 5:
        # Deterministic elision: keep the top-level package plus the last two segments — enough
        # to stay readable and to keep the id a pure function of the path.
        segments = [segments[0]] + segments[-2:]

    return ".".join(segments)


def derive_semantic_name(rid: str) -> str:
    """Title-cased display name from the id's last segment (dedup suffix stripped)."""
    slug_part = rid.rsplit(".", 1)[-1]
    base = _DEDUP_SUFFIX_RE.sub("", slug_part)
    words = [w for w in base.split("_") if w]
    return " ".join(w.capitalize() for w in words) or slug_part


def _tier3_record(rid: str, path: str, derivation: str) -> dict:
    return {
        "id": rid,
        "kind": "file_identity",
        "semantic_name": derive_semantic_name(rid),
        "physical_path": path,
        "status": "ACTIVE",
        "authority": "advisory",
        "tier": 3,
        "confidence": "LOW",
        "provenance": "DERIVED",
        "derivation": derivation,
        "canonical": True,
        "role": "UNKNOWN",
        "semantic_layer": "UNCLASSIFIED",
        "filename_semantic_status": "UNKNOWN",
        "filename_status_reason": (
            f"Not reviewed. Slug derived from path by {derivation} — no human has read this "
            "file's source."
        ),
        "aliases": [],
        "concept_ids": [],
        "miar_entry": None,
        "summary_50": "",
        "why_this_identity": "",
        "evidence": [],
        "supersedes": None,
        "superseded_by": None,
    }


def derive_tier3_identities(paths: Iterable[str], curated: dict[str, dict]) -> list[dict]:
    """Machine-derived identities for every path in ``paths`` not already claimed by ``curated``.

    Deterministic AND order-invariant: the result is a pure function of the *set* of remaining
    paths, computed by sorting before grouping and before assigning dedup suffixes — calling this
    twice, or once on a shuffled input, produces byte-identical output (required for
    ``tests/test_semantic_os.py::test_seed_runs_and_is_byte_identical_on_rerun``).

    Collision handling: multiple paths that normalize to the same slug are grouped, sorted by
    path, and every member after the first gets a visible ``__2``, ``__3``... suffix recorded in
    ``derivation`` as ``path_slug/v1#dedup2`` — never silently renamed.
    """
    curated_paths = {
        str(r.get("physical_path") or "").replace("\\", "/") for r in curated.values()
    }
    remaining = sorted({p.replace("\\", "/") for p in paths} - curated_paths)

    by_slug: dict[str, list[str]] = {}
    for path in remaining:
        by_slug.setdefault(derive_slug(path), []).append(path)

    records: list[dict] = []
    for slug, group_paths in sorted(by_slug.items()):
        group_paths = sorted(group_paths)
        for idx, path in enumerate(group_paths):
            if idx == 0:
                rid, derivation = slug, DERIVATION_VERSION
            else:
                rid = f"{slug}__{idx + 1}"
                derivation = f"{DERIVATION_VERSION}#dedup{idx + 1}"
            records.append(_tier3_record(rid, path, derivation))
    return records


def resolve_identity_index(curated: dict[str, dict], derived: Iterable[dict]) -> dict[str, dict]:
    """``physical_path -> canonical file_identity record``. The single join point for OBJ + Excel.

    Curated always wins on a path collision (there should never be one — ``derive_tier3_identities``
    already skips curated paths — but this keeps the join defensive rather than order-dependent).
    """
    out: dict[str, dict] = {}
    for rid, record in sorted(curated.items()):
        if record.get("canonical") is not True:
            continue
        path = str(record.get("physical_path") or "").replace("\\", "/")
        if path:
            out[path] = record
    for record in sorted(derived, key=lambda r: r["id"]):
        path = record.get("physical_path")
        if path and path not in out:
            out[path] = record
    return out


def validate_projection(
    curated: dict[str, dict], derived: list[dict], paths: Iterable[str]
) -> list[str]:
    """Projection-level invariants the per-record schema validator cannot see on its own.

    (a) no derived id collides with a curated id (would silently shadow a human decision);
    (b) derived ids are unique among themselves;
    (c) curated ∪ derived paths == the full path universe (total coverage, no gaps, no strays).
    """
    errors: list[str] = []
    curated_ids = set(curated)
    derived_ids = [r["id"] for r in derived]

    dup_curated = sorted(set(derived_ids) & curated_ids)
    if dup_curated:
        errors.append(f"derived id(s) collide with curated id(s): {dup_curated}")

    seen: dict[str, int] = {}
    for rid in derived_ids:
        seen[rid] = seen.get(rid, 0) + 1
    dup_within = sorted(r for r, n in seen.items() if n > 1)
    if dup_within:
        errors.append(f"derived id(s) collide with each other: {dup_within}")

    curated_paths = {
        str(r.get("physical_path") or "").replace("\\", "/") for r in curated.values()
    }
    derived_paths = {r["physical_path"] for r in derived}
    universe = {p.replace("\\", "/") for p in paths}
    covered = curated_paths | derived_paths

    missing = sorted(universe - covered)
    if missing:
        errors.append(f"{len(missing)} path(s) have no file_identity at all (sample {missing[:5]})")
    extra = sorted(covered - universe)
    if extra:
        errors.append(f"file_identity references path(s) outside the universe (sample {extra[:5]})")

    return errors
