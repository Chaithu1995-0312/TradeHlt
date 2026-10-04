"""PIT prefix-invariance floor — the durable gate that no future dependence silently
re-enters the production FeaturePipeline (PIT Phase C, 2026-07-11).

Contract: for EVERY canonical column, running the pipeline on a strict prefix must
produce values IDENTICAL to the full-corpus run on all shared timestamps — with ZERO
tail exclusion. Bar t may use only information ≤ t (FC1-A causal-delayed structure,
FC1-D rolling-causal volregime, trailing indicators everywhere else).

Evidence twin: docs/governance/pit_phaseC_feature_certification-2026-07-11.{json,md}
(real-corpus arm). This floor runs the synthetic arm on every pytest invocation.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_PROBE = _REPO / "scripts" / "analysis" / "pit_phaseC_feature_certification.py"


def _load_probe():
    spec = importlib.util.spec_from_file_location("pit_phaseC_feature_certification", _PROBE)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["pit_phaseC_feature_certification"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def probe():
    if not _PROBE.exists():
        pytest.skip("phase C probe not present")
    return _load_probe()


def test_all_canonical_production_columns_prefix_invariant(probe):
    raw = probe._synthetic(n=900, seed=23)
    arm = probe.prefix_invariance(raw, cuts=[0.5, 0.8], corpus_label="floor_synthetic")
    assert arm["all_prefix_invariant"], (
        "PREFIX-INVARIANCE BROKEN — future dependence re-entered the production pipeline. "
        f"Variant columns: {arm['variant_features']}. "
        "This is a PIT Phase-C stop condition: adjudicate before any remediation "
        "(see docs/governance/pit_phaseC_feature_certification-2026-07-11.md)."
    )
    # the harness itself must have compared a meaningful interior
    assert all(c["shared_rows"] > 100 for c in arm["cuts"])


def test_no_unwindowed_rank_feeds_production(probe):
    """Full-frame rank/quantile may exist ONLY for research-only columns; the empirical
    prefix floor above is the ground truth, this localizes regressions early."""
    scan = probe.global_fit_scan()
    # exactly the known research-only global rank (volatility_regime_global_batch)
    assert len(scan["unwindowed_sites"]) <= 1, (
        f"new full-frame rank/quantile sites appeared: {scan['unwindowed_sites']}"
    )
