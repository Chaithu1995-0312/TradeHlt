"""Script-matrix <-> registry id-set guard (SITS).

Mirrors tests/test_cli_matrix_sync.py. Asserts docs/reference/script-matrix.md lists
exactly the SCR ids present in PRIMARY stubs (or seeded data/). Regenerate:

    python scripts/governance/seed_script_registry.py
    python scripts/analysis/generate_script_matrix.py
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from utils.jsonl_writer import read_jsonl

_REPO = Path(__file__).resolve().parents[1]
_STUBS = _REPO / "docs" / "governance" / "script_registry_stubs.jsonl"
_DATA = _REPO / "data" / "script_registry.jsonl"
_MATRIX = _REPO / "docs" / "reference" / "script-matrix.md"
_SEED = _REPO / "scripts" / "governance" / "seed_script_registry.py"
_GEN = _REPO / "scripts" / "analysis" / "generate_script_matrix.py"

_MATRIX_ID_RE = re.compile(r"^\| `(SCR-\d+)` \|", re.MULTILINE)


def _registry_ids() -> set[str]:
    if _DATA.exists() and _DATA.stat().st_size > 0:
        recs = read_jsonl(_DATA)
    else:
        recs = read_jsonl(_STUBS)
    return {r["id"] for r in recs if r.get("id")}


def _matrix_ids() -> set[str]:
    return set(_MATRIX_ID_RE.findall(_MATRIX.read_text(encoding="utf-8")))


def test_inputs_exist() -> None:
    assert _STUBS.exists(), "script_registry_stubs.jsonl missing — run census --write-stubs"
    assert _MATRIX.exists(), "script-matrix.md missing — run generate_script_matrix.py"


def test_script_matrix_covers_every_registry_id() -> None:
    # Ensure data/ is seeded so matrix generator and id source stay aligned
    subprocess.run(
        [sys.executable, str(_SEED), "--stubs", str(_STUBS), "--out", str(_DATA)],
        check=True,
        cwd=_REPO,
    )
    reg, mat = _registry_ids(), _matrix_ids()
    assert reg, "no SCR ids in registry/stubs"
    missing = reg - mat
    extra = mat - reg
    assert not missing and not extra, (
        "script-matrix.md is out of sync with the script registry — regenerate with:\n"
        "  python scripts/governance/seed_script_registry.py\n"
        "  python scripts/analysis/generate_script_matrix.py\n"
        f"  missing from matrix: {sorted(missing)[:20]}\n"
        f"  stale in matrix:     {sorted(extra)[:20]}"
    )


def test_matrix_regenerates_byte_identical() -> None:
    """Generator output matches committed matrix (no silent doc drift)."""
    subprocess.run(
        [sys.executable, str(_SEED), "--stubs", str(_STUBS), "--out", str(_DATA)],
        check=True,
        cwd=_REPO,
    )
    before = _MATRIX.read_text(encoding="utf-8")
    subprocess.run(
        [sys.executable, str(_GEN), "--out", str(_MATRIX)],
        check=True,
        cwd=_REPO,
    )
    after = _MATRIX.read_text(encoding="utf-8")
    # Re-write is expected to be identical if committed matrix is current
    assert before == after, (
        "script-matrix.md drifted from generator output — commit the regenerated file"
    )
