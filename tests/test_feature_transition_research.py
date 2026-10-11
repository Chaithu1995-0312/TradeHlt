"""Unit tests for transition detection and stats helpers in feature_transition_research."""
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "analysis"))
import feature_transition_research as ftr  # noqa: E402


def test_npn_detected_with_transition_offset():
    s = [-1, -1, 1, 1, -1, -1]
    r = ftr.detect_patterns(s)
    assert r["NPN"] == 4 and r["PNP"] is None and r["PN"] == 4


def test_pnp_and_np_and_pn():
    assert ftr.detect_patterns([1, 1, -1, -1, 1, 1])["PNP"] == 4
    assert ftr.detect_patterns([-1, -1, 1, 1])["NP"] == 2
    assert ftr.detect_patterns([1, 1, -1, -1])["PN"] == 2


def test_single_bar_flicker_is_ignored_and_zeros_dropped():
    assert ftr.detect_patterns([-1, -1, 1, -1, -1])["NPN"] is None  # 1-bar run removed -> one merged '-' run
    assert ftr.detect_patterns([-1, -1, 0, 0, 1, 1, 0, -1, -1])["NPN"] is not None


def test_no_pattern_in_constant_sequence():
    assert all(v is None for v in ftr.detect_patterns([1] * 8).values())


def test_fisher_matches_known_value_and_symmetry():
    # Tea-tasting table [[3,1],[1,3]] two-sided p = 0.4857
    assert abs(ftr.fisher_exact_p(3, 1, 1, 3) - 0.4857) < 1e-3
    assert abs(ftr.fisher_exact_p(3, 1, 1, 3) - ftr.fisher_exact_p(1, 3, 3, 1)) < 1e-12


def test_binomial_and_bh():
    assert abs(ftr.binom_two_sided(5, 10, 0.5) - 1.0) < 1e-9
    q = ftr.bh_q([0.01, 0.04, 0.03, float("nan")])
    assert math.isnan(q[3]) and q[0] <= q[2] <= q[1] + 1e-12 and max(q[:3]) <= 1.0


def test_permutation_p_in_unit_interval_and_small_groups_nan():
    import numpy as np
    rng = np.random.default_rng(1)
    assert math.isnan(ftr.perm_p(np.array([1.0]), np.array([0.0, 1.0]), rng))
    p = ftr.perm_p(np.array([1.0, 2.0, 3.0]), np.array([-1.0, -2.0, -3.0]), rng, n=500)
    assert 0 < p <= 1
