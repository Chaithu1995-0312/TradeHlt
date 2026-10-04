from pathlib import Path
import re
import py_compile

ROOT = Path(r"D:\Tradelatest")
files = [ln.strip() for ln in (ROOT / "multi_llm/parameter_usage_audit/syntax_error_17.txt").read_text().splitlines() if ln.strip()]

# Inside a parenthesized import, continuation names should be indented.
# Fix lines that look like "Name," or "Name" right after an open-paren import with no indent.

def fix_import_indents(text: str) -> tuple[str, int]:
    lines = text.splitlines(keepends=True)
    out = []
    in_paren_import = False
    paren_depth = 0
    fixes = 0
    for ln in lines:
        raw = ln.rstrip("\r\n")
        nl = ln[len(raw):]
        stripped = raw.strip()
        # track from X import (
        if not in_paren_import:
            if re.match(r"^(from\s+\S+\s+import\s*\(|import\s+\S+\s*\()", stripped) or (
                re.match(r"^from\s+\S+\s+import\s*$", stripped) is None
                and re.match(r"^from\s+\S+\s+import\s*\(", stripped)
            ):
                if "(" in stripped:
                    in_paren_import = True
                    paren_depth = stripped.count("(") - stripped.count(")")
                    out.append(ln)
                    if paren_depth <= 0:
                        in_paren_import = False
                    continue
            out.append(ln)
            continue
        # in paren import
        paren_depth += stripped.count("(") - stripped.count(")")
        if stripped == "" or stripped.startswith("#"):
            out.append(ln)
        elif raw.startswith(" ") or raw.startswith("\t"):
            out.append(ln)
        elif stripped.startswith(")"):
            out.append(ln)
        else:
            # unindented continuation — restore 4-space indent
            out.append("    " + stripped + nl)
            fixes += 1
        if paren_depth <= 0:
            in_paren_import = False
            paren_depth = 0
    return "".join(out), fixes

total = 0
for rel in files:
    p = ROOT / rel
    text = p.read_text(encoding="utf-8")
    new, n = fix_import_indents(text)
    if n:
        p.write_text(new, encoding="utf-8")
        py_compile.compile(str(p), doraise=True)
        print(f"fixed_indents={n} {rel}")
        total += n
    else:
        py_compile.compile(str(p), doraise=True)
print(f"total_indent_fixes={total}")
