"""Formula registry parity floor — the WHAT authority (market_ontology.yaml) and its code
executor (formula_registry.FORMULA_REGISTRY) must agree, and formulas are never eval'd.

Enforces:
  - every ontology primitive resolves to a real callable; compositions resolve to primitives,
  - the executed body_ratio composition == the canonical candle_math.body_ratio (the wick_size
    reconciliation stays locked: active denominator is candle_range, bounded [0,1]),
  - no eval/exec in the executor (CONFIG-DECLARED, CODE-EXECUTED, never CONFIG-EVAL'd).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from features import candle_math as cm
from features import formula_registry as fr

_REPO = Path(__file__).resolve().parents[1]
_WORKED = dict(open_=100.0, high=110.0, low=95.0, close=108.0)


def test_ontology_file_exists_and_declares_authority():
    ont = fr.load_ontology()
    assert ont["authority"] == "user_approved"
    assert ont["primitives"] and ont["feature_compositions"]


def test_registry_and_ontology_agree():
    assert fr.validate_registry() == [], "ontology ↔ FORMULA_REGISTRY inconsistency"


def test_body_ratio_composition_is_canonical_body_over_range():
    """The active body_ratio denominator is candle_range (NOT total_wick) — the wick_size lock."""
    ont = fr.load_ontology()
    comp = ont["feature_compositions"]["body_ratio"]
    assert comp["numerator"] == "body_size"
    assert comp["denominator"] == "candle_range"
    assert comp["active"] is True
    assert comp["bounded"] == [0, 1]


def test_composition_matches_candle_math_on_battery():
    # Worked example first: 8/15 = 0.5333, NOT 8/7.
    assert fr.compute_composition("body_ratio", **_WORKED) == pytest.approx(8.0 / 15.0)
    rng = np.random.default_rng(3)
    for _ in range(1000):
        o, c = rng.uniform(1, 100), rng.uniform(1, 100)
        lo = min(o, c) - rng.uniform(0, 10)
        hi = max(o, c) + rng.uniform(0, 10)
        assert fr.compute_composition("body_ratio", o, hi, lo, c) == pytest.approx(
            cm.body_ratio(o, hi, lo, c)
        )


def test_registry_primitives_equal_candle_math():
    assert fr.FORMULA_REGISTRY["candle_math.body_size"](100.0, 108.0) == cm.body_size(100.0, 108.0)
    assert fr.FORMULA_REGISTRY["candle_math.candle_range"](110.0, 95.0) == cm.candle_range(110.0, 95.0)
    assert fr.FORMULA_REGISTRY["candle_math.total_wick"](100.0, 110.0, 95.0, 108.0) == cm.total_wick(
        100.0, 110.0, 95.0, 108.0
    )


def test_no_eval_in_executor():
    """CONFIG-DECLARED, CODE-EXECUTED — NO module in the registry package (or the facade / the
    scalar impl layers) may ever eval/exec a formula string."""
    feats = _REPO / "src" / "features"
    targets = [
        feats / "formula_registry.py",   # facade
        feats / "candle_math.py",
        feats / "derived_math.py",
        *sorted((feats / "registry").glob("*.py")),
    ]
    for p in targets:
        src = p.read_text(encoding="utf-8")
        assert "eval(" not in src and "exec(" not in src, f"{p.name}: formulas must never be eval/exec'd"


def test_facade_reexports_stable_api():
    """The back-compat facade must expose the full stable surface (internal splits stay behind it)."""
    for sym in ("FORMULA_REGISTRY", "compute_composition", "compute_derived",
                "validate_registry", "build_lineage_graph", "load_ontology"):
        assert hasattr(fr, sym), f"formula_registry facade missing {sym}"


def test_compute_derived_matches_scalar():
    from features import derived_math as dm
    assert fr.compute_derived("disp_strength", body_size=1.0, atr=0.01, close=100.0) == pytest.approx(
        dm.disp_strength(1.0, 0.01, 100.0))
    assert fr.compute_derived("volatility_ratio", high=110.0, low=95.0, atr=0.01, close=100.0) == pytest.approx(
        dm.volatility_ratio(110.0, 95.0, 0.01, 100.0))
