"""Static isolation: shadow package must not call CRT try_* mutators."""

from __future__ import annotations

from pathlib import Path

from msip.isolation import SHADOW_PACKAGE_ROOT, scan_shadow_emit_modules


def test_no_forbidden_mutation_calls_in_shadow_package():
    findings = scan_shadow_emit_modules()
    assert findings == {}, f"forbidden CRT mutation calls found: {findings}"


def test_shadow_emitter_source_has_no_try_star():
    path = SHADOW_PACKAGE_ROOT / "shadow_emitter.py"
    text = path.read_text(encoding="utf-8")
    for name in (
        "try_sweep",
        "try_displacement",
        "try_expansion",
        "try_retest",
        "try_execution",
        "open_trade",
    ):
        assert f".{name}(" not in text
        # allow mention in comments only — enforce no live call
        for line in text.splitlines():
            if line.strip().startswith("#"):
                continue
            assert f"{name}(" not in line or f"def {name}" in line


def test_package_files_exist():
    expected = [
        "__init__.py",
        "market_state_vector.py",
        "interpretation_config.py",
        "shadow_emitter.py",
        "disagreement.py",
        "isolation.py",
    ]
    for name in expected:
        assert (SHADOW_PACKAGE_ROOT / name).is_file()
