"""CH-timeframe-ssot-v1 — one candle-merging authority, ratcheted.

Candle aggregation (M15 -> H1/H4/D1/W1) has ONE authority pair:
  * batch     : `research.resample.resample` (+ `bucket_floor`)
  * streaming : `features.parent_candle.ParentCandleBuilder`
both on the `features.calendar_periods` grids with the corpus calendar (`corpus.calendar`, the gold market day
starting 17:00 New York). A hand-rolled `df.resample("4h")`, `dt.floor("h")`, `pd.Grouper(freq=...)` or a
`groupby(...dt.date)` buckets on naive UTC midnight, usually keeps the trailing partial bucket, and silently
disagrees with every calendar-aware consumer.

This test is a shrink-only ratchet over `src/`, `scripts/` and `tools/` (not `tests/`, not `archive/`):
  * a NEW hand-rolled merge in those trees fails the test;
  * an allowlisted entry whose count no longer matches the live count must be updated, so the list only shrinks;
  * the scanner is proven able to fail on a planted violation.
Allowlist: `docs/governance/aggregation_authority_allowlist.json` (path + kind + count + reason).
"""
from __future__ import annotations

import ast
import json
import re
import warnings
from collections import Counter
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_ALLOWLIST = _REPO / "docs" / "governance" / "aggregation_authority_allowlist.json"
_TREES = ("src", "scripts", "tools")
_SKIP_PARTS = {"archive", "__pycache__", ".git", "venv", ".venv", "node_modules"}
# A pandas offset alias used as a bucket rule: "h", "4h", "1H", "D", "W", "15min", "30T", "ME"...
_RULE = re.compile(r"^\s*\d*\s*(h|H|d|D|w|W|min|MIN|T|M|ME|MS)\s*$")


def _is_rule_literal(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return bool(_RULE.match(node.value))
    if isinstance(node, ast.JoinedStr) and node.values:          # f"{n}h", f"{hours}H"
        tail = node.values[-1]
        return isinstance(tail, ast.Constant) and isinstance(tail.value, str) and bool(_RULE.match("1" + tail.value))
    return False


def _day_key(node: ast.AST) -> bool:
    """`x.dt.date`, `x.dt.normalize()` or `x.dt.floor('D')`-like day keys used as a groupby key."""
    if isinstance(node, ast.Attribute) and node.attr == "date" and isinstance(node.value, ast.Attribute) and node.value.attr == "dt":
        return True
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr == "normalize" and isinstance(node.func.value, ast.Attribute) and node.func.value.attr == "dt":
            return True
    return False


def scan_source(source: str) -> list[str]:
    """Kinds of hand-rolled candle merging found in one module's source ([] if none / unparsable)."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")           # unrelated scripts carry invalid-escape SyntaxWarnings
            tree = ast.parse(source)
    except SyntaxError:
        return []
    kinds: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = fn.attr if isinstance(fn, ast.Attribute) else (fn.id if isinstance(fn, ast.Name) else "")
        first = node.args[0] if node.args else None
        if name == "resample" and isinstance(fn, ast.Attribute) and first is not None and _is_rule_literal(first):
            kinds.append("pandas_resample")
        elif name == "floor" and isinstance(fn, ast.Attribute) and first is not None and _is_rule_literal(first):
            kinds.append("dt_floor")
        elif name == "Grouper" and any(k.arg == "freq" for k in node.keywords):
            kinds.append("pd_Grouper_freq")
        elif name == "groupby" and isinstance(fn, ast.Attribute) and any(_day_key(a) for a in node.args):
            kinds.append("groupby_day")
    return kinds


def scan_repo(root: Path = _REPO) -> Counter:
    found: Counter = Counter()
    for tree_name in _TREES:
        base = root / tree_name
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            if _SKIP_PARTS & set(path.relative_to(root).parts):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            rel = path.relative_to(root).as_posix()
            for kind in scan_source(text):
                found[(rel, kind)] += 1
    return found


def _allowlist() -> dict:
    return json.loads(_ALLOWLIST.read_text(encoding="utf-8"))


def _allowed(data: dict) -> Counter:
    return Counter({(e["path"], e["kind"]): int(e["count"]) for e in data["entries"]})


# ── the scanner can fail ──────────────────────────────────────────────────────────────────────

def test_scanner_flags_each_hand_rolled_pattern():
    assert scan_source("df.set_index('t').resample('4h').agg({})") == ["pandas_resample"]
    assert scan_source("x = df['t'].dt.floor('h')") == ["dt_floor"]
    assert scan_source("df.groupby(pd.Grouper(key='t', freq='D'))") == ["pd_Grouper_freq"]
    assert scan_source("df.groupby(df['t'].dt.date).first()") == ["groupby_day"]
    assert scan_source("df.groupby(df['t'].dt.normalize())") == ["groupby_day"]


def test_scanner_ignores_non_merging_calls():
    assert scan_source("rng.resample(bl)\nlabel.floor(3.5)\ndf.groupby('hour')\nx.dt.hour // 4") == []
    assert scan_source("def broken(:") == []


# ── the ratchet ───────────────────────────────────────────────────────────────────────────────

def test_allowlist_is_well_formed():
    data = _allowlist()
    assert data["authority"]["batch"] == "research.resample.resample"
    assert data["authority"]["streaming"] == "features.parent_candle.ParentCandleBuilder"
    keys = [(e["path"], e["kind"]) for e in data["entries"]]
    assert len(keys) == len(set(keys)), "duplicate (path, kind) in the allowlist"
    assert all(e["reason"].strip() and int(e["count"]) > 0 for e in data["entries"])
    assert data["entry_count"] == len(data["entries"])


def test_no_new_hand_rolled_candle_merging():
    live, allowed = scan_repo(), _allowed(_allowlist())
    new = {k: n - allowed.get(k, 0) for k, n in live.items() if n > allowed.get(k, 0)}
    assert not new, (
        "new hand-rolled candle merging outside the authority (research.resample.resample / "
        "features.parent_candle.ParentCandleBuilder on the corpus calendar):\n  "
        + "\n  ".join(f"{p} [{kind}] +{n}" for (p, kind), n in sorted(new.items()))
        + "\nCall the authority instead. Only if the code is provably not OHLC merging, add it to "
          "docs/governance/aggregation_authority_allowlist.json with a reason."
    )


def test_allowlist_only_shrinks():
    live, allowed = scan_repo(), _allowed(_allowlist())
    stale = {k: (n, live.get(k, 0)) for k, n in allowed.items() if live.get(k, 0) < n}
    assert not stale, (
        "allowlisted merging was removed or migrated; lower or delete these entries so the list only shrinks:\n  "
        + "\n  ".join(f"{p} [{kind}] allowed {a}, live {b}" for (p, kind), (a, b) in sorted(stale.items()))
    )


def test_the_ratchet_catches_a_planted_violation(tmp_path):
    planted = tmp_path / "scripts"
    planted.mkdir()
    (planted / "planted.py").write_text("import pandas as pd\nh4 = df.resample('4h').last()\n", encoding="utf-8")
    found = scan_repo(tmp_path)
    assert found[("scripts/planted.py", "pandas_resample")] == 1
    assert found[("scripts/planted.py", "pandas_resample")] > _allowed(_allowlist()).get(("scripts/planted.py", "pandas_resample"), 0)
