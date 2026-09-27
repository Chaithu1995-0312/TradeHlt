from pathlib import Path
import re
import py_compile

ROOT = Path(r"D:\Tradelatest")
IMPORT = "from tests.helpers.crt_config import crt_config_for_test"
IMPORT_RE = re.compile(r"^[ \t]*from\s+tests\.helpers\.crt_config\s+import\s+crt_config_for_test[ \t]*\r?\n?", re.M)

def insert_index(lines: list[str]) -> int:
    """After module docstring + __future__, before other imports. Handles CRLF keepends."""
    n = len(lines)
    i = 0
    def body(idx):
        return lines[idx].rstrip("\r\n")

    if i < n and body(i).startswith("#!"):
        i += 1
    if i < n and re.match(r"^#.*coding[:=]", body(i)):
        i += 1
    if i < n and (body(i).lstrip().startswith('"""') or body(i).lstrip().startswith("'''")):
        raw = body(i).lstrip()
        q = '"""' if raw.startswith('"""') else "'''"
        if raw.count(q) >= 2 and raw.endswith(q) and len(raw) > 3:
            i += 1
        else:
            i += 1
            while i < n and q not in body(i):
                i += 1
            if i < n:
                i += 1
    while i < n and (body(i).strip() == "" or body(i).lstrip().startswith("#")):
        i += 1
    last = i
    while i < n:
        s = body(i)
        if s.startswith("from __future__ import") or s.startswith("import __future__"):
            i += 1
            last = i
            continue
        if s.strip() == "":
            i += 1
            continue
        break
    return last

def fix(path: Path, extra_line_fixes=None):
    text = path.read_text(encoding="utf-8")
    # remove every helper import line
    text2, n = IMPORT_RE.subn("", text)
    lines = text2.splitlines(keepends=True)
    idx = insert_index(lines)
    # already have top-level?
    if any(ln.rstrip("\r\n") == IMPORT for ln in lines):
        new = "".join(lines)
        action = f"removed_dup_only n={n}"
    else:
        nl = "\r\n" if any(l.endswith("\r\n") for l in lines[:5]) else "\n"
        lines.insert(idx, IMPORT + nl)
        # blank line after import if next is non-blank non-import? keep minimal — if next is import, no blank needed
        new = "".join(lines)
        action = f"placed_at={idx} removed={n}"
    if extra_line_fixes:
        for a, b in extra_line_fixes:
            if a in new:
                new = new.replace(a, b)
                action += ";str_fix"
            else:
                action += ";str_fix_miss"
    path.write_text(new, encoding="utf-8")
    try:
        py_compile.compile(str(path), doraise=True)
        comp = "OK"
    except Exception as e:
        comp = f"FAIL {e}"
    print(f"{path.relative_to(ROOT)}: {action} compile={comp}")

# mangled assert from earlier CRTConfig rewriter inside a string
auto_fix = [(
    'assert "CRTConfig(" not in source, "Direct CRTConfig(...) instantiation found — FORBIDDEN")ORBIDDEN")ORBIDDEN"',
    'assert "CRTConfig(" not in source, "Direct CRTConfig(...) instantiation found — FORBIDDEN"',
)]
# try alternate mojibake variants
auto_path = ROOT / "tests/test_auto_tuner_multi.py"
raw = auto_path.read_text(encoding="utf-8")
# find the broken line and rewrite surgically
new_lines = []
fixed_assert = False
for ln in raw.splitlines(keepends=True):
    if "FORBIDDEN" in ln and "CRTConfig(" in ln and "assert" in ln:
        # rebuild clean assert line preserving newline
        nl = "\r\n" if ln.endswith("\r\n") else "\n"
        ln = '    assert "CRTConfig(" not in source, "Direct CRTConfig(...) instantiation found — FORBIDDEN"' + nl
        fixed_assert = True
    new_lines.append(ln)
auto_path.write_text("".join(new_lines), encoding="utf-8")
print("auto_tuner assert_fixed=", fixed_assert)

fix(ROOT / "tests/test_auto_tuner_multi.py")
fix(ROOT / "tests/test_crt_config_provenance.py")
fix(ROOT / "tests/Grok/_fixtures.py")

# verify all 17
print("\n=== py_compile all 17 ===")
lst = (ROOT / "multi_llm/parameter_usage_audit/syntax_error_17.txt").read_text().splitlines()
ok = 0
for rel in lst:
    rel = rel.strip()
    if not rel: continue
    p = ROOT / rel
    try:
        py_compile.compile(str(p), doraise=True)
        print("OK", rel)
        ok += 1
    except Exception as e:
        print("FAIL", rel, e)
print(f"compile_ok={ok}/17")
