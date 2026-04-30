"""
tool_registry.py
─────────────────────────────────────────────────────────────────────────────
Central registry for all agent tools.

ToolSpec — metadata for one tool (description, args schema, handler, write flag).
REGISTRY  — global dict[name → ToolSpec].
@register_tool — decorator to register a handler.
get_schema_text() — generates the {TOOL_SCHEMA} text injected into LLM prompts.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger("ToolRegistry")


@dataclass
class ToolSpec:
    name: str
    description: str
    args_schema: dict          # {param: {"type": str, "required": bool, "desc": str}}
    handler: Callable
    write: bool = False        # True → requires per-call y/N confirmation
    allowlist: bool = True     # False → must appear in config.write_tools_enabled


REGISTRY: Dict[str, ToolSpec] = {}


def register_tool(
    name: str,
    description: str = "",
    write: bool = False,
    args_schema: Optional[dict] = None,
    allowlist: bool = True,
) -> Callable:
    """Decorator to register a function as an agent tool."""
    def decorator(fn: Callable) -> Callable:
        if name in REGISTRY:
            raise ValueError(f"Tool '{name}' already registered")
        REGISTRY[name] = ToolSpec(
            name=name,
            description=description or (fn.__doc__ or "").split("\n")[0].strip(),
            args_schema=args_schema or {},
            handler=fn,
            write=write,
            allowlist=allowlist,
        )
        return fn
    return decorator


def get_tool(name: str) -> ToolSpec:
    if name not in REGISTRY:
        raise KeyError(f"Tool '{name}' not in registry. Available: {list(REGISTRY.keys())}")
    return REGISTRY[name]


def get_schema_text(mode: Optional[str] = None) -> str:
    """
    Generate tool schema text for injection into LLM prompts.
    If mode given, only include tools relevant to that mode.
    """
    lines = []
    for spec in REGISTRY.values():
        args = ", ".join(
            f"{k}:{v.get('type', 'any')}{'*' if v.get('required') else ''}"
            for k, v in spec.args_schema.items()
        )
        write_tag = " [WRITE — requires confirm]" if spec.write else ""
        lines.append(f"- {spec.name}({args}){write_tag}: {spec.description}")
    return "\n".join(lines)
