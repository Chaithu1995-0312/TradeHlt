"""Program 10 D3 — the measurement-only firewall.

The resolved/estimated intrabar order is a REPORT. If it ever flows back into a Signal, an
Outcome, or a hypothesis, the measurement becomes a label and every downstream economic claim
inherits an inference as if it were an observation. This test is the structural floor that makes
that impossible to do by accident.

Behavioral, not decorative: it fails if any consumer module gains an import of `research.path`.
"""

import ast
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[3] / "src"

# Packages that must never consume the path layer. `research.path` itself and its tests are
# obviously exempt; so is any driver script under scripts/ (they orchestrate, they don't measure).
_FORBIDDEN_CONSUMERS = (
    _SRC / "research" / "hypotheses",
    _SRC / "research" / "measurement",
    _SRC / "core",
    _SRC / "engines",
    _SRC / "config_layer",
    _SRC / "interpreters",
)


def _imported_modules(py: Path) -> set[str]:
    try:
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
    except (SyntaxError, UnicodeDecodeError):  # pragma: no cover - not our concern here
        return set()
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def _offenders() -> list[str]:
    bad: list[str] = []
    for root in _FORBIDDEN_CONSUMERS:
        if not root.exists():
            continue
        pys = [root] if root.is_file() else sorted(root.rglob("*.py"))
        for py in pys:
            for mod in _imported_modules(py):
                if mod == "research.path" or mod.startswith("research.path."):
                    bad.append(f"{py.relative_to(_SRC)} imports {mod}")
    return bad


def test_no_consumer_imports_the_path_layer():
    offenders = _offenders()
    assert offenders == [], (
        "research.path is MEASURE-ONLY (Program 10 D3) — the resolved intrabar order must never "
        "reach a Signal/Outcome/hypothesis. Offending imports:\n  " + "\n  ".join(offenders))


def test_firewall_scanner_actually_detects_an_import(tmp_path):
    """Red-green proof: the scanner must catch a planted violation, or it enforces nothing.

    Guards against the E-001F 'decorative wiring' failure class — a test that can never fail.
    """
    planted = tmp_path / "planted.py"
    planted.write_text("from research.path import ambiguity_census\n", encoding="utf-8")
    assert "research.path" in _imported_modules(planted)

    planted_alias = tmp_path / "planted2.py"
    planted_alias.write_text("import research.path.ambiguity_census as x\n", encoding="utf-8")
    assert any(m.startswith("research.path") for m in _imported_modules(planted_alias))


def test_path_package_declares_measure_only():
    """The package docstring carries the contract; a silent removal is a governance regression."""
    init = _SRC / "research" / "path" / "__init__.py"
    text = init.read_text(encoding="utf-8")
    assert "MEASURE-ONLY" in text
    assert "preregistration-program-10" in text


@pytest.mark.parametrize("root", [p for p in _FORBIDDEN_CONSUMERS])
def test_forbidden_consumer_roots_exist(root):
    """If a guarded package is renamed the firewall would silently guard nothing."""
    assert root.exists(), f"guarded package missing: {root} — update _FORBIDDEN_CONSUMERS"
