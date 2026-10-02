"""Derived consumers of v2 concepts (I-14, spec §15 G-4). Evidence class HEURISTIC, never PROVEN.

A module under src/ (outside src/semantics/) consumes a concept when its AST reads one of the
concept's representations:

  feature slot (producer feature_pipeline)   a string constant equal to the slot name
  `Owner.MEMBER` with an upper-case member   the attribute access Owner.MEMBER
  `Owner.attr` with a capitalised owner      an access .attr in a module that also names Owner
  `lower.KIND` (e.g. events.RESET)           a string constant equal to KIND
  bare `Owner`                               the name Owner

A homonym (another class's .status, a string "atr" meaning something else) can produce a false
consumer. That is why the result is HEURISTIC: it lists where to look, not what is proven.
"""

from __future__ import annotations

import ast
from functools import lru_cache
from pathlib import Path
from typing import Mapping, Optional

ROOT = Path(__file__).resolve().parents[2]
_SRC = ROOT / "src"
_EXCLUDED = _SRC / "semantics"


class _ModuleFacts:
    __slots__ = ("names", "attrs", "pairs", "strings")

    def __init__(self) -> None:
        self.names: set[str] = set()
        self.attrs: set[str] = set()
        self.pairs: set[tuple[str, str]] = set()
        self.strings: set[str] = set()


def _facts(tree: ast.AST) -> _ModuleFacts:
    facts = _ModuleFacts()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            facts.names.add(node.id)
        elif isinstance(node, ast.Attribute):
            facts.attrs.add(node.attr)
            if isinstance(node.value, ast.Name):
                facts.pairs.add((node.value.id, node.attr))
        elif isinstance(node, ast.alias):
            facts.names.add((node.asname or node.name).split(".")[-1])
            facts.names.add(node.name.split(".")[-1])
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            facts.strings.add(node.value)
    return facts


@lru_cache(maxsize=1)
def _scan() -> tuple:
    rows = []
    for path in sorted(_SRC.rglob("*.py")):
        if _EXCLUDED in path.parents or "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        rows.append((path.relative_to(ROOT).as_posix(), _facts(tree)))
    return tuple(rows)


def _matches(producer: str, key: str, facts: _ModuleFacts) -> bool:
    base = key.split("[", 1)[0]
    if producer == "feature_pipeline":
        return base in facts.strings
    if "." not in base:
        return base in facts.names or base in facts.attrs
    owner, attr = base.split(".", 1)
    if "." in attr:
        return False
    if not owner[:1].isupper():
        return attr in facts.strings
    if attr.isupper():
        return (owner, attr) in facts.pairs
    named = owner in facts.names or owner in facts.attrs
    return named and attr in facts.attrs


def representation_consumers(producer: str, key: str) -> list[str]:
    """Modules that read this representation (HEURISTIC)."""
    return [module for module, facts in _scan() if _matches(producer, key, facts)]


def consumers_by_concept(shards: Optional[Mapping[str, dict]] = None) -> dict[str, list[str]]:
    """concept_id -> sorted modules reading any of its representations (HEURISTIC)."""
    if shards is None:
        from semantics.registry import load_representation_shards
        shards = load_representation_shards()
    found: dict[str, set[str]] = {}
    for shard in shards.values():
        producer = str(shard.get("producer_id"))
        for key, rep in (shard.get("representations") or {}).items():
            if not isinstance(rep, dict) or not rep.get("concept_id"):
                continue
            found.setdefault(rep["concept_id"], set()).update(representation_consumers(producer, key))
    return {cid: sorted(mods) for cid, mods in found.items()}
