"""RC-6 — the shape-based structural copy check.

The name-based ownership lint can only see a re-derivation that BINDS A REGISTERED NAME.
Two of the nine sweep copies SK-1 migrated were inline `if high > ref and close < ref:`
conditions with no assignment target — structurally invisible to it. Measured 2026-08-19:
against a synthetic inline copy the name check scored 0 hits and the shape check scored 1.

This module pins three things:
  1. the repository is currently free of shape copies (the floor);
  2. the detector actually fires on a new copy (a check that cannot fail is decoration);
  3. it does NOT fire on the lone compares that appear all over the repo (`close > open`),
     which is the false-positive risk the pair requirement exists to control.
"""
from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))


def _lint():
    spec = importlib.util.spec_from_file_location(
        "_fml_shape", _ROOT / "scripts" / "analysis" / "feature_math_lint.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_fml_shape"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def lint():
    return _lint()


def _shapes_in(lint, src: str) -> list[dict]:
    """Run the shape matcher over a source string by reusing the module's own AST helpers."""
    tree = ast.parse(src)
    found: list[dict] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.BoolOp) and isinstance(node.op, ast.And)):
            continue
        parts = [lint._simple_compare(v) for v in node.values]
        pairs = [p for p in parts if p]
        if len(pairs) < 2:
            continue
        for i in range(len(pairs)):
            for j in range(len(pairs)):
                if i == j:
                    continue
                (d1, l1, r1), (d2, l2, r2) = pairs[i], pairs[j]
                lf1, lf2 = lint._leaf(l1), lint._leaf(l2)
                if lf1 in lint._EXTREMES and d1 == lint._EXTREMES[lf1] and lf2 == "close" and r1 == r2 and d2 != d1:
                    found.append({"kind": "sweep_shape", "line": node.lineno})
                if lf1 == "close" and lf2 == "close" and d1 == d2 and lint._leaf(r1) == "open" and lint._leaf(r2) != "open":
                    found.append({"kind": "f074_core_shape", "line": node.lineno})
    return found


def test_repository_has_no_structural_shape_copies(lint) -> None:
    """The floor. Legitimate producers are allowlisted; a new copy is not."""
    report = lint.build_report()
    violations = report["structural_shape"]["violations"]
    assert violations == [], (
        "structural shape copies found — route them through structure.predicates:\n"
        + "\n".join(f"  {v['module']}:{v['line']} {v['kind']} — {v['detail']}" for v in violations)
    )


# ── The detector must actually fire (this is the part that makes it a gate) ──

@pytest.mark.parametrize(
    "src,kind",
    [
        ("if candle.high > rng.h_ref and candle.close < rng.h_ref:\n    pass",
         "sweep_shape"),
        ("if bar.low < pool.price and bar.close > pool.price:\n    pass",
         "sweep_shape"),
        ("x = float(b.high) > wr.h_ref and float(b.close) < wr.h_ref",
         "sweep_shape"),
        # inclusive form (FM-058's boundary) is also a copy when it appears outside the
        # allowlisted producers — reported so the author has to say which quantity they mean
        ("if h > ref and c <= ref:\n    pass".replace("h >", "high >").replace(" c ", " close "),
         "sweep_shape"),
        ("ok = candle.close > candle.open and candle.close > sweep.price",
         "f074_core_shape"),
        ("ok = c.close < c.open and c.close < sweep.sweep_price",
         "f074_core_shape"),
    ],
)
def test_detector_fires_on_a_new_copy(lint, src, kind) -> None:
    hits = _shapes_in(lint, src)
    assert any(h["kind"] == kind for h in hits), f"detector missed a {kind} copy:\n{src}"


# ── False-positive control: the PAIR is required ──

@pytest.mark.parametrize(
    "src",
    [
        "if candle.close > candle.open:\n    pass",                 # lone body-sign compare
        "if candle.high > rng.h_ref:\n    pass",                    # lone pierce
        "if a > b and c > d:\n    pass",                            # unrelated pair
        "if candle.high > rng.h_ref and candle.close < other.h_ref:\n    pass",  # DIFFERENT refs
        "if candle.high > rng.h_ref and candle.close > rng.h_ref:\n    pass",    # break, not sweep
        "if x.close > x.open and y.close > y.open:\n    pass",       # two body-signs, no level
    ],
    ids=["lone-body", "lone-pierce", "unrelated", "different-refs", "break-not-sweep", "two-bodies"],
)
def test_detector_does_not_fire_on_innocent_compares(lint, src) -> None:
    assert _shapes_in(lint, src) == [], f"false positive on:\n{src}"


def test_legitimate_producers_stay_allowlisted(lint) -> None:
    """The kernel and the FM-058 producers define this math; they must not be flagged."""
    for rel in ("structure/predicates.py", "features/feature_pipeline.py",
                "features/causal_structure.py"):
        assert lint._is_allowlisted(rel), f"{rel} must remain allowlisted"
