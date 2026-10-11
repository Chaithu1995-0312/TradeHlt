"""Detector tests for scripts/analysis/pnp_bar_census.py (causal streaming P->N->P state machine)."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "analysis"))
import pnp_bar_census as pc  # noqa: E402


def run(sign, a=1, gaps=None, **kw):
    s = np.array(sign); g = np.zeros(len(s), bool)
    for i in gaps or []:
        g[i] = True
    return pc.detect(s, g, a, **kw)


def test_basic_pnp_event_on_second_bar_of_final_run():
    ev = run([1, 1, -1, -1, 1, 1, 1])
    assert [e["confirm_idx"] for e in ev] == [5] and ev[0]["n_len"] == 2 and ev[0]["p1_len"] == 2


def test_mirror_npn_uses_a_minus_one():
    assert [e["confirm_idx"] for e in run([-1, -1, 1, 1, -1, -1], a=-1)] == [5]
    assert run([-1, -1, 1, 1, -1, -1], a=1) == []


def test_single_bar_runs_do_not_count():
    assert run([1, 1, -1, 1, 1, 1]) == []          # 1-bar middle
    assert run([1, -1, -1, 1, 1]) == []             # 1-bar first run


def test_zero_bars_are_skipped_and_gaps_reset_state():
    assert [e["confirm_idx"] for e in run([1, 1, 0, -1, -1, 0, 1, 1])] == [7]
    assert run([1, 1, -1, -1, 1, 1], gaps=[4]) == []


def test_refractory_collapses_chained_detections():
    seq = [1, 1, -1, -1, 1, 1, -1, -1, 1, 1]       # second event 4 bars later -> suppressed by refractory=8
    assert len(run(seq)) == 1
    assert len(run(seq, refractory=2)) == 2


def test_middle_run_length_cap():
    assert run([1, 1] + [-1] * 11 + [1, 1]) == []


def test_detection_is_causal_prefix_invariant():
    rng = np.random.default_rng(3)
    s = rng.choice([-1, 1], 300)
    full = [e["confirm_idx"] for e in run(s)]
    for cut in (60, 150, 299):
        part = [e["confirm_idx"] for e in run(s[:cut])]
        assert part == [i for i in full if i < cut]
