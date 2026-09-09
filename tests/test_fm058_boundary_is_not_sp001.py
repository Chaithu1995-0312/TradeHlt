"""RC-7 — the FM-058 feature family must never be routed through SP-001.

`liquidity_sweep` (FM-058), `sweep_detected` (FM-059) and `double_sweep` (FM-060) are
canonical feature-vector slots. They share the English word "sweep" with SP-001 and share
nothing else:

    SP-001 (decision)          FM-058 (feature)
    founding range h_ref/l_ref  last_swing_high_price.shift(1)   ← different REFERENCE
    strict   close <  ref       inclusive  close <= ref          ← different BOUNDARY
    SweepEvent -> CRT state     int8 -> the 48-dim vector        ← different CONSUMER

The repository already treats them as selectable alternatives:
`configs/formulas/market_crt_states.yaml` `thresholds.sweep_geometry` ∈
{`htf_range`, `pipeline_swing`}.

"Harmonising" them would silently redefine a registered feature and move the feature vector —
so the exclusion is enforced here mechanically instead of living in a docstring. The SK-1
migration deliberately left both producers untouched.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from structure.predicates import swept_high, swept_low

_ROOT = Path(__file__).resolve().parents[1]
_PRODUCERS = (
    _ROOT / "src" / "features" / "feature_pipeline.py",       # batch authority
    _ROOT / "src" / "features" / "causal_structure.py",       # online FeatureStore twin
)


@pytest.mark.parametrize("path", _PRODUCERS, ids=lambda p: p.name)
def test_feature_family_producers_do_not_import_the_decision_kernel(path: Path) -> None:
    """Structural check: neither producer may import `structure.predicates`.

    An import here would be the first step of collapsing two different market objects into
    one. If a future change genuinely needs it, that is a semantic decision requiring its own
    authorization — not a refactor.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("structure"):
            offenders.append(f"line {node.lineno}: from {node.module} import ...")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("structure"):
                    offenders.append(f"line {node.lineno}: import {alias.name}")
    assert not offenders, (
        f"{path.name} imports the SP-001 decision kernel: {offenders}. FM-058 is a DIFFERENT "
        "quantity (swing reference, inclusive boundary); routing it through SP-001 would move "
        "the 48-dim feature vector."
    )


def test_the_two_boundaries_genuinely_disagree() -> None:
    """Proof the distinction is real, not bookkeeping: they differ at `close == ref`.

    If this ever stops being true, the two definitions have converged and the separation
    argument needs re-examining rather than silently maintaining.
    """
    # FM-058's rule, transcribed from feature_pipeline.compute_structure_liquidity:
    #   sweep_high = (high > ref_high) & (close <= ref_high)
    ref = 100.0
    high, low, close = 101.0, 99.0, 100.0        # closed EXACTLY at the reference

    fm058_high = high > ref and close <= ref
    fm058_low = low < ref and close >= ref

    assert fm058_high is True, "FM-058 is inclusive: closing at ref still counts"
    assert swept_high(high, close, ref) is False, "SP-001 is strict: closing at ref does not"
    assert fm058_low is True
    assert swept_low(low, close, ref) is False


def test_resolver_still_exposes_both_families_as_a_config_switch() -> None:
    """`sweep_geometry` is the repo's own record that these are alternatives, not duplicates."""
    src = (_ROOT / "src" / "features" / "crt_state_resolver.py").read_text(encoding="utf-8")
    assert '"htf_range"' in src and '"pipeline_swing"' in src, (
        "the resolver no longer offers both sweep families — if that was deliberate, this "
        "test should be updated with the decision, not deleted"
    )
