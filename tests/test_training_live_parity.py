"""Smoke tests for the read-only parity probe (scripts/analysis/training_live_parity.py)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "analysis"))
import training_live_parity as tlp  # noqa: E402
from features.feature_schema import CANONICAL_FEATURES  # noqa: E402


def test_compare_flags_only_changed_feature():
    b = pd.DataFrame({k: np.arange(5, dtype=float) for k in CANONICAL_FEATURES})
    l = b.copy()
    l["atr"] = l["atr"] + 1.0
    res = {r["feature"]: r for r in tlp.compare(b, l)}
    assert res["atr"]["mismatch_rows"] == 5
    assert res["rsi_14"]["mismatch_rows"] == 0


def test_rr_warmup_is_monotonic_and_empty_for_short_lists():
    out = tlp.rr_warmup(sizes=(50, 300, 400))
    assert out[50] == 0
    assert out[50] <= out[300] <= out[400]
