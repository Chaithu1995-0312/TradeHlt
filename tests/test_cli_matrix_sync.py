"""CLI-matrix <-> registry command-set guard.

Mirrors tests/test_codebase_structure_doc.py (pure-text read-and-assert, no imports of the
control_plane package). Asserts that the generated `docs/reference/cli-matrix.md` lists exactly the
set of `CommandSpec` ids declared in `src/control_plane/registry.py`. A new or removed command fails
this test until the matrix is regenerated:

    PYTHONPATH=. python scripts/analysis/generate_cli_matrix.py

It guards the command SET only (add/remove drift). Per-command argv/default drift is cured by the same
regeneration — the generator is the single source.
"""
from __future__ import annotations

import re
from pathlib import Path

_REGISTRY = Path("src/control_plane/registry.py")
_MATRIX = Path("docs/reference/cli-matrix.md")

_REG_ID_RE = re.compile(r'id="([^"]+)"')
_MATRIX_ID_RE = re.compile(r"^\| `([a-z][\w.]+)` \|", re.MULTILINE)


def _registry_ids() -> set[str]:
    return set(_REG_ID_RE.findall(_REGISTRY.read_text(encoding="utf-8")))


def _matrix_ids() -> set[str]:
    return set(_MATRIX_ID_RE.findall(_MATRIX.read_text(encoding="utf-8")))


def test_inputs_exist() -> None:
    assert _REGISTRY.exists(), "src/control_plane/registry.py missing"
    assert _MATRIX.exists(), "docs/reference/cli-matrix.md missing"


def test_cli_matrix_covers_every_registry_command() -> None:
    reg, mat = _registry_ids(), _matrix_ids()
    assert reg, "no CommandSpec ids found in registry.py (regex drift?)"
    missing = reg - mat   # in registry, absent from the doc
    extra = mat - reg     # in the doc, no longer in registry
    assert not missing and not extra, (
        "cli-matrix.md is out of sync with registry.py — regenerate with "
        "`PYTHONPATH=. python scripts/analysis/generate_cli_matrix.py`.\n"
        f"  missing from matrix: {sorted(missing)}\n"
        f"  stale in matrix:     {sorted(extra)}"
    )
