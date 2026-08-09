"""Floor for the IC-003B derived-information driver (scripts/research/ic003b_derive_information.py).

Confirms the derivation is deterministic and stays descriptive (no authority). The heavy artifact under
results/ is gitignored, so the artifact-dependent checks skip when it is absent. Governance-doc/logic floor.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

_ROOT = Path(__file__).resolve().parents[2]
_DRIVER = _ROOT / "scripts" / "research" / "ic003b_derive_information.py"
_ARTIFACT = _ROOT / "results" / "research" / "ic_003b" / "DERIVED_INFORMATION.json"
_MD = _ROOT / "results" / "research" / "ic_003b" / "DERIVED_INFORMATION.md"

pytestmark = pytest.mark.research_integrity


def _load_driver():
    spec = importlib.util.spec_from_file_location("ic003b_derive_information", _DRIVER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_driver_imports_and_helpers_deterministic():
    """Pure helpers must be deterministic + correct (no market data, fast)."""
    m = _load_driver()
    # Wilson CI is a fixed formula; BH is order-deterministic; Spearman on a monotone pair == 1
    lo, hi = m._wilson(47, 100)
    assert 0.0 <= lo < 0.47 < hi <= 1.0
    assert m._bh([0.001, 0.9, 0.9, 0.9]) == [True, False, False, False]
    assert abs(m._spearman([1, 2, 3, 4], [1, 2, 3, 4]) - 1.0) < 1e-9
    # Cramer's V of an independent table is ~0; of a perfectly-separating table is ~1
    lab = np.array([0, 0, 1, 1]); ind = np.array(["a", "b", "a", "b"]); sep = np.array(["a", "a", "b", "b"])
    assert m._cramers_v(lab, ind) < 1e-9
    assert m._cramers_v(lab, sep) > 0.99


@pytest.mark.skipif(not _ARTIFACT.exists(), reason="DERIVED_INFORMATION.json absent (gitignored results)")
def test_artifact_descriptive_and_shaped():
    d = json.loads(_ARTIFACT.read_text(encoding="utf-8"))
    assert "information-only" in d["authority"] and "NO edge" in d["authority"].replace("no ", "NO ")
    assert set(["D1_information_content", "D2_cross_representation_concordance",
                "D3_path_morphology_arm_S_N4", "D4_shape_as_conditional_signal_arm_S_N4"]) <= set(d)
    # D4 must never silently assert authority: it reports a boolean, not a promotion
    assert isinstance(d["D4_shape_as_conditional_signal_arm_S_N4"]["any_bh_significant"], bool)
    if _MD.exists():
        assert "Authority: NONE" in _MD.read_text(encoding="utf-8")
