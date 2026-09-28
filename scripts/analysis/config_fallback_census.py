#!/usr/bin/env python
"""config_fallback_census.py -- EPIC-84 F2: every silent default / fallback in src/ (read-only).

User rule 2026-09-28: no defaults, no fallbacks; a missing config key fails closed.
This census lists every site where a value can come from a code literal instead of a
loaded config, so each EPIC-84 lane has an exact work list, and (Wave 2) a blocking
ratchet can refuse new ones.

Patterns (AST, not regex):
  GET_DEFAULT     x.get("key", <default>)            default is not None
  GETATTR_DEFAULT getattr(x, "key", <default>)       default is not None
  DEFAULT_MERGE   {**DEFAULT_*} / dict(DEFAULT_*)    a whole default dict under the config
  OR_LITERAL      <read> or <literal>                read = .get / subscript / attribute
  FIELD_DEFAULT   dataclass field default in a class named *Config/*Params/*Settings/*Policy
  ENV_DEFAULT     os.environ.get("X", <default>) / os.getenv("X", <default>)

Class (who must act):
  CONFIG      receiver looks like a config object (cfg/config/section/params/settings...)
              or the default is a DEFAULT_* merge -> must become a strict read
  PARAM_DEFAULT  config-dataclass field default -> must be removed
  ENV         environment fallback -> must become declared config or fail closed
  DATA        receiver looks like a data record (row/trade/bar/event/payload...) -> review;
              a per-trade VALUE (risk_percent, direction...) read from a payload is still a
              fallback and becomes a trade REJECT (D7), so DATA is not automatically exempt
  UNCLASSIFIED   neither -> the lane classifies by reading the site

USAGE
    python scripts/analysis/config_fallback_census.py            # write docs/research-readiness/config-fallback-census.{json,md}
    python scripts/analysis/config_fallback_census.py --package core --print
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "src"
OUT_DIR = REPO / "docs" / "research-readiness"

CONFIG_RX = re.compile(
    r"(^|_)(cfg|conf|config|configs|settings|section|sec|params|param|prod|options|opts|"
    r"policy|thresholds|spec|contract|profile|knobs)($|_)|_cfg$|^cfg|config$",
    re.IGNORECASE,
)
DATA_RX = re.compile(
    r"(^|_)(row|rows|rec|record|records|trade|trades|bar|bars|candle|candles|event|events|"
    r"evt|ev|payload|data|item|items|entry|msg|message|resp|response|result|results|obj|"
    r"meta|metadata|summary|stats|out|output|line|doc|node|state|info|ctx|context|pos|"
    r"position|order|signal|sig|features|feat|feature|label|labels|report|verdict|manifest|"
    r"kwargs|headers|js|j|payloads|snapshot|detail|details|m|d|e|r|t|x|s|o|p|c|b|a|v|f|g)$",
    re.IGNORECASE,
)
CLASS_RX = re.compile(r"(Config|Params|Settings|Policy|Knobs)$")


def _text(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:  # noqa: BLE001
        return "?"


def _leaf_name(node: ast.AST) -> str:
    """Rightmost identifier of a receiver: self.cfg -> cfg, get_prod_section('x') -> get_prod_section."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Call):
        return _leaf_name(node.func)
    if isinstance(node, ast.Subscript):
        # cfg["section"] -> treat the subscripted object as the receiver
        return _leaf_name(node.value)
    return ""


def _is_none(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value is None


def _is_literal(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return node.value is not None
    if isinstance(node, (ast.List, ast.Tuple, ast.Dict, ast.Set)):
        return True
    if isinstance(node, ast.UnaryOp) and isinstance(node.operand, ast.Constant):
        return True
    if isinstance(node, ast.Name) and node.id.isupper():
        return True  # module constant
    if isinstance(node, ast.Attribute) and node.attr.isupper():
        return True
    return False


def _classify_receiver(recv: ast.AST) -> str:
    name = _leaf_name(recv)
    full = _text(recv)
    if name in {"get_prod_section", "get_prod_config", "load_prod_config", "_section"}:
        return "CONFIG"
    if name.upper().startswith("DEFAULT"):
        return "CONFIG"
    if CONFIG_RX.search(name) or re.search(r"(cfg|config|section|params|settings)", full, re.I):
        return "CONFIG"
    if DATA_RX.search(name):
        return "DATA"
    return "UNCLASSIFIED"


def _is_environ(node: ast.AST) -> bool:
    t = _text(node)
    return t in {"os.environ", "environ"}


class _Visitor(ast.NodeVisitor):
    def __init__(self, rel: str):
        self.rel = rel
        self.hits: list[dict] = []
        self._class_stack: list[str] = []
        self._func_stack: list[str] = []

    def _add(self, node, pattern, cls, key, default, receiver):
        self.hits.append({
            "file": self.rel,
            "line": node.lineno,
            "pattern": pattern,
            "class": cls,
            "key": key,
            "default": default[:60],
            "receiver": receiver[:60],
            "scope": ".".join(self._class_stack + self._func_stack) or "<module>",
        })

    def visit_ClassDef(self, node: ast.ClassDef):
        self._class_stack.append(node.name)
        is_dc = any("dataclass" in _text(d) for d in node.decorator_list)
        if is_dc and CLASS_RX.search(node.name):
            for stmt in node.body:
                if isinstance(stmt, ast.AnnAssign) and stmt.value is not None \
                        and isinstance(stmt.target, ast.Name):
                    val = stmt.value
                    if isinstance(val, ast.Call) and _leaf_name(val.func) == "field":
                        kws = {k.arg: k.value for k in val.keywords}
                        if "default" in kws:
                            val = kws["default"]
                        elif "default_factory" in kws:
                            val = kws["default_factory"]
                        else:
                            continue
                    self._add(stmt, "FIELD_DEFAULT", "PARAM_DEFAULT", stmt.target.id,
                              _text(val), node.name)
        self.generic_visit(node)
        self._class_stack.pop()

    def visit_FunctionDef(self, node):
        self._func_stack.append(node.name)
        self.generic_visit(node)
        self._func_stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node: ast.Call):
        f = node.func
        # x.get("k", default)
        if isinstance(f, ast.Attribute) and f.attr == "get" and len(node.args) >= 2 \
                and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str) \
                and not _is_none(node.args[1]):
            key = node.args[0].value
            if _is_environ(f.value):
                self._add(node, "ENV_DEFAULT", "ENV", key, _text(node.args[1]), _text(f.value))
            else:
                self._add(node, "GET_DEFAULT", _classify_receiver(f.value), key,
                          _text(node.args[1]), _text(f.value))
        # os.getenv("X", default)
        elif _text(f) in {"os.getenv", "getenv"} and len(node.args) >= 2 \
                and not _is_none(node.args[1]):
            key = node.args[0].value if isinstance(node.args[0], ast.Constant) else _text(node.args[0])
            self._add(node, "ENV_DEFAULT", "ENV", str(key), _text(node.args[1]), "os.getenv")
        # getattr(x, "k", default)
        elif isinstance(f, ast.Name) and f.id == "getattr" and len(node.args) == 3 \
                and isinstance(node.args[1], ast.Constant) and not _is_none(node.args[2]):
            self._add(node, "GETATTR_DEFAULT", _classify_receiver(node.args[0]),
                      str(node.args[1].value), _text(node.args[2]), _text(node.args[0]))
        # dict(DEFAULT_*)
        elif isinstance(f, ast.Name) and f.id == "dict" and node.args \
                and _leaf_name(node.args[0]).upper().startswith("DEFAULT"):
            self._add(node, "DEFAULT_MERGE", "CONFIG", "*", _text(node.args[0]), "dict()")
        self.generic_visit(node)

    def visit_Dict(self, node: ast.Dict):
        for k, v in zip(node.keys, node.values):
            if k is None and _leaf_name(v).upper().startswith("DEFAULT"):
                self._add(node, "DEFAULT_MERGE", "CONFIG", "*", _text(v), "{**}")
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp):
        if isinstance(node.op, ast.Or) and len(node.values) >= 2 and _is_literal(node.values[-1]):
            left = node.values[0]
            if isinstance(left, (ast.Call, ast.Subscript, ast.Attribute)):
                recv = left.func.value if (isinstance(left, ast.Call)
                                           and isinstance(left.func, ast.Attribute)) else left
                key = ""
                if isinstance(left, ast.Call) and left.args and isinstance(left.args[0], ast.Constant):
                    key = str(left.args[0].value)
                elif isinstance(left, ast.Subscript) and isinstance(left.slice, ast.Constant):
                    key = str(left.slice.value)
                elif isinstance(left, ast.Attribute):
                    key = left.attr
                self._add(node, "OR_LITERAL", _classify_receiver(recv), key,
                          _text(node.values[-1]), _text(left))
        self.generic_visit(node)


def scan(package: str | None = None) -> list[dict]:
    root = SRC / package if package else SRC
    hits: list[dict] = []
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(REPO).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        except (SyntaxError, UnicodeDecodeError) as exc:
            hits.append({"file": rel, "line": 0, "pattern": "PARSE_ERROR", "class": "UNCLASSIFIED",
                         "key": "", "default": str(exc)[:60], "receiver": "", "scope": ""})
            continue
        v = _Visitor(rel)
        v.visit(tree)
        hits.extend(v.hits)
    for h in hits:
        parts = h["file"].split("/")
        h["package"] = parts[1] if len(parts) > 2 else "<root>"
    return hits


def summarize(hits: list[dict]) -> dict:
    by_pkg: dict[str, Counter] = defaultdict(Counter)
    for h in hits:
        by_pkg[h["package"]][h["class"]] += 1
    return {
        "total": len(hits),
        "by_class": dict(Counter(h["class"] for h in hits)),
        "by_pattern": dict(Counter(h["pattern"] for h in hits)),
        "by_package": {k: dict(v) for k, v in sorted(by_pkg.items())},
    }


def to_markdown(summary: dict) -> str:
    classes = ["CONFIG", "PARAM_DEFAULT", "ENV", "DATA", "UNCLASSIFIED"]
    lines = [
        "# Config fallback census (EPIC-84 F2, generated)",
        "",
        "Generated by `scripts/analysis/config_fallback_census.py`. Every site where a value can",
        "come from a code literal instead of a loaded config. Rule (user 2026-09-28): no defaults,",
        "no fallbacks; a missing key fails closed. Full rows: `config-fallback-census.json`.",
        "",
        f"Total sites: **{summary['total']}**",
        "",
        "| Package | " + " | ".join(classes) + " | Total |",
        "|---|" + "---:|" * (len(classes) + 1),
    ]
    for pkg, c in summary["by_package"].items():
        lines.append(f"| {pkg} | " + " | ".join(str(c.get(k, 0)) for k in classes)
                     + f" | {sum(c.values())} |")
    lines += ["", "Patterns: " + ", ".join(f"{k} {v}" for k, v in sorted(summary["by_pattern"].items())), ""]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--package", default=None, help="limit to src/<package>")
    ap.add_argument("--print", action="store_true", help="print rows instead of writing files")
    args = ap.parse_args()
    hits = scan(args.package)
    summary = summarize(hits)
    if args.print:
        for h in hits:
            print(f"{h['file']}:{h['line']}  {h['pattern']:<15} {h['class']:<13} "
                  f"{h['key']!s:<28} default={h['default']}  recv={h['receiver']}")
        print(json.dumps(summary, indent=1))
        return 0
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "config-fallback-census.json").write_text(
        json.dumps({"summary": summary, "sites": hits}, indent=1) + "\n", encoding="utf-8")
    (OUT_DIR / "config-fallback-census.md").write_text(to_markdown(summary) + "\n", encoding="utf-8")
    print(json.dumps(summary["by_class"]), f"total={summary['total']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
