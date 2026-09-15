"""Load a sibling .py file as a module (single importlib choke-point)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def load_py(path: str | Path, name: str | None = None) -> ModuleType:
    """Load ``path`` as module ``name`` (default: stem).

    Registers in ``sys.modules`` *before* ``exec_module`` so ``@dataclass``
    (and similar) work on Python 3.12+. Returns a cached module if ``name``
    is already present.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    mod_name = name or path.stem
    existing = sys.modules.get(mod_name)
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    try:
        spec.loader.exec_module(mod)
    except BaseException:
        sys.modules.pop(mod_name, None)
        raise
    return mod
