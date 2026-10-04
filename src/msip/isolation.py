"""Import / mutation isolation policy for the MSIP shadow package.

Hard invariant: shadow modules must not call CRT StateMachine mutators or
write EngineState / open trades / write production ACTIVE_VERSION.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

# Modules under src/msip that implement the shadow emit path (scanned by tests).
SHADOW_PACKAGE_ROOT = Path(__file__).resolve().parent

# CRT mutation APIs that shadow code must never invoke.
FORBIDDEN_CALL_NAMES: frozenset[str] = frozenset(
    {
        "try_sweep",
        "try_displacement",
        "try_expansion",
        "try_retest",
        "try_execution",
        "try_resolution",
        "try_expire",
        "try_shadow_pending",
        "open_trade",
        "close_trade",
        "approve",
    }
)

# Import strings that are forbidden on the shadow *write/emit* path.
# Reading CRT state names via a pure observe helper is allowed; mutating is not.
FORBIDDEN_IMPORT_MODULES: frozenset[str] = frozenset(
    {
        "engines.crt_engine",  # wrapper path that can mutate
    }
)

# Features that must come from FeaturePipeline WHAT, never CRT-local live values
# as MSIP source_features until parity + separate migration authority.
CRT_LOCAL_FORBIDDEN_AS_MSIP_SOURCE_UNTIL_PARITY: frozenset[str] = frozenset(
    {
        "crt_local_atr",
        "crt_local_ema_fast",
        "crt_local_ema_slow",
        "crt_local_body_ratio",
        "crt_local_wick_size",
    }
)


def forbidden_calls_in_source(source: str) -> list[str]:
    """Return forbidden call-name substrings present in *source* text."""
    hits: list[str] = []
    for name in FORBIDDEN_CALL_NAMES:
        # Match method-style calls: .try_sweep( or try_sweep(
        if f".{name}(" in source or f"{name}(" in source:
            # Allow comments mentioning the name
            for line in source.splitlines():
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if f".{name}(" in line or (
                    f"{name}(" in line and f"def {name}" not in line
                ):
                    hits.append(name)
                    break
    return sorted(set(hits))


def scan_shadow_emit_modules(paths: Iterable[Path] | None = None) -> dict[str, list[str]]:
    """Scan shadow package .py files for forbidden mutation calls."""
    root = SHADOW_PACKAGE_ROOT
    if paths is None:
        paths = sorted(root.glob("*.py"))
    findings: dict[str, list[str]] = {}
    for path in paths:
        if path.name == "isolation.py":
            continue  # policy definitions only
        text = path.read_text(encoding="utf-8")
        hits = forbidden_calls_in_source(text)
        if hits:
            findings[str(path)] = hits
    return findings
