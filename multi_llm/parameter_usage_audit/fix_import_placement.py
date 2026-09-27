from __future__ import annotations

from pathlib import Path
import re
import py_compile
import traceback

ROOT = Path(r"D:\Tradelatest")
LIST = ROOT / "multi_llm" / "parameter_usage_audit" / "syntax_error_17.txt"
IMPORT_LINE = "from tests.helpers.crt_config import crt_config_for_test"
IMPORT_RE = re.compile(
    r"^\s*from\s+tests\.helpers\.crt_config\s+import\s+crt_config_for_test\s*$",
    re.M,
)
# also catch mid-block insertion without leading newline cleanliness
INLINE_IMPORT_RE = re.compile(
    r"^[ \t]*from\s+tests\.helpers\.crt_config\s+import\s+crt_config_for_test\s*\n?",
    re.M,
)

def has_future(lines: list[str]) -> int:
    """Return index after last consecutive __future__ import block (0 if none)."""
    i = 0
    # skip shebang, encoding, docstring, comments blank
    n = len(lines)
    # shebang
    if i < n and lines[i].startswith("#!"):
        i += 1
    # encoding comment
    if i < n and re.match(r"^#.*coding[:=]", lines[i]):
        i += 1
    # module docstring
    if i < n and (lines[i].lstrip().startswith('"""') or lines[i].lstrip().startswith("'''")):
        q = '"""' if '"""' in lines[i] else "'''"
        if lines[i].count(q) >= 2 and lines[i].lstrip().endswith(q) and len(lines[i].strip()) > 3:
            i += 1
        else:
            i += 1
            while i < n and q not in lines[i]:
                i += 1
            if i < n:
                i += 1
    # skip blanks and pure comments
    while i < n and (lines[i].strip() == "" or lines[i].lstrip().startswith("#")):
        i += 1
    # consume __future__ imports
    last = i
    while i < n:
        s = lines[i]
        if s.startswith("from __future__ import") or s.startswith("import __future__"):
            i += 1
            last = i
            # continuation unlikely for future
            continue
        if s.strip() == "":
            i += 1
            continue
        break
    return last

def find_insert_index(lines: list[str]) -> int:
    """After __future__ (and following blanks), before rest. Prefer after existing import block start position: right after futures/docstring — do NOT reorder other imports; place immediately after futures or at first import region start."""
    # Per scope: leave existing ordering alone — insert as a new top-level line after __future__/docstring/shebang, before other imports is OK as long as we don't reorder them. Actually "Preserve all existing imports" + "leave file's existing ordering alone" means: insert without moving other imports. Best: insert just before the first non-future import that was broken, OR after all leading future/docstring, at the position where we remove the bad one if it was at top... 
    # Safest: insert immediately AFTER the __future__ block (or module header), before the first remaining import — that adds one line without reordering existing ones relative to each other.
    return has_future(lines)

def is_lazy_import_file(text: str) -> bool:
    """True if ONLY uses of crt_config_for_test appear inside functions/classes AND there was intentional local import.
    We check: after removing bad module-level insert, whether original design had import inside def.
    For our 17, the insert was mid multi-line import at module level — not lazy.
    Heuristic: if 'def ' appears before the bad import line and the import is indented — lazy.
    """
    for m in INLINE_IMPORT_RE.finditer(text):
        # check indentation
        line_start = text.rfind("\n", 0, m.start()) + 1
        indent = m.start() - line_start
        # count preceding context: if we're inside a def/class by indent > 0
        if indent > 0:
            return True
    return False

def fix_file(path: Path) -> dict:
    original = path.read_text(encoding="utf-8")
    text = original
    info = {"file": str(path.relative_to(ROOT)).replace("\\", "/"), "lazy": False, "had_toplevel": False, "action": ""}

    if is_lazy_import_file(text):
        info["lazy"] = True
        info["action"] = "SKIP_LAZY"
        return info

    # Count existing correct top-level imports (column 0)
    toplevel_count = 0
    for line in text.splitlines():
        if line.startswith("from tests.helpers.crt_config import crt_config_for_test"):
            toplevel_count += 1
    info["had_toplevel"] = toplevel_count > 0

    # Remove ALL occurrences of the helper import line (including indented/broken mid-block)
    text2, n_removed = INLINE_IMPORT_RE.subn("", text)
    if n_removed == 0:
        info["action"] = "NO_IMPORT_FOUND"
        return info

    lines = text2.splitlines(keepends=True)
    # Normalize: ensure we don't leave empty issues inside paren imports — removing mid-block line should restore validity
    insert_at = find_insert_index(lines)

    # Duplicate guard: if a proper top-level import already remains, don't insert
    remaining_toplevel = any(
        ln.startswith("from tests.helpers.crt_config import crt_config_for_test")
        for ln in lines
    )
    if remaining_toplevel:
        new_text = "".join(lines)
        info["action"] = f"REMOVED_BAD_ONLY n={n_removed}"
    else:
        # Insert after futures
        # Use newline form matching file
        nl = "\n"
        if lines and lines[0].endswith("\r\n"):
            nl = "\r\n"
        elif any(l.endswith("\r\n") for l in lines[:5]):
            nl = "\r\n"
        insert_line = IMPORT_LINE + nl
        # If insert point is mid-file and previous line isn't blank, OK; don't reorder
        lines.insert(insert_at, insert_line)
        new_text = "".join(lines)
        info["action"] = f"MOVED n_removed={n_removed} insert_at={insert_at}"

    if new_text == original:
        info["action"] = "NO_CHANGE"
        return info

    path.write_text(new_text, encoding="utf-8")
    try:
        py_compile.compile(str(path), doraise=True)
        info["compile"] = "OK"
    except Exception as e:
        info["compile"] = f"FAIL: {e}"
    return info

results = []
for line in LIST.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line:
        continue
    p = ROOT / line
    results.append(fix_file(p))

for r in results:
    print(f"{r['file']}: {r['action']} compile={r.get('compile','n/a')} lazy={r['lazy']}")

ok = sum(1 for r in results if r.get("compile") == "OK")
print(f"SUMMARY compile_ok={ok}/{len(results)} lazy_skips={sum(1 for r in results if r['lazy'])}")
