"""Load a sibling .py file as a module (single importlib choke-point)."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

def load_py(path: str | Path, name: str | None = None) -> ModuleType:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    mod_name = name or path.stem
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f'cannot load {path}')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
