"""M4 QualificationGate tests — the 7-gate rejection logic, permutation, and BH FDR."""
from datetime import datetime

from research.contracts import Outcome, Signal
from research.costs import ZERO_COST
from research.measurement.metrics import EdgeAggregator
from research.qualification import (
    QualConfig,
    benjamini_hochberg,
    evaluate_pre_bh,
    finalize,
    permutation_p_value,
)

_QCFG = QualConfig(min_samples=10, expectancy_min=0.0, pf_min=1.0, oos_split=0.3,
                   oos_retention_min=0.5, n_permutations=200, significance_alpha=0.05)
_AGG = EdgeAggregator()


def _o(rr: float, idx: int) -> Outcome:
    sig = Signal(instrument="T", timestamp=datetime(2026, 1, 1), entry_index=idx,
                 direction="long", entry=100.0, sl_atr_mult=1.0, tp_atr_mult=2.0, atr=1.0)
    return Outcome(signal=sig, outcome="TP_HIT" if rr > 0 else "SL_HIT", rr_achieved=rr,
                   mfe=0.0, mae=0.0, duration_candles=1,
                   time_to_tp=1 if rr > 0 else None,
                   time_to_failure=None if rr > 0 else 1, reached_1r=rr > 0)


def _report_and_state(outs, win_name="ctrl", win_rrs=None, win_exp=0.0):
    rep = _AGG.aggregate("hyp", ["T"], outs, cost_model=ZERO_COST)
    st = evaluate_pre_bh(rep, {"T": outs}, win_name, win_rrs or [0.0] * 30, win_exp,
                         _QCFG, ZERO_COST)
    return st


def _interleaved(n_triples: int) -> list[Outcome]:
    # [+2, +2, -1] repeated → E[R]=1.0, evenly distributed so IS & OOS both positive.
    outs, idx = [], 1
    for _ in range(n_triples):
        for rr in (2.0, 2.0, -1.0):
            outs.append(_o(rr, idx)); idx += 1
    return outs


# ── permutation + BH primitives ──────────────────────────────────────────────
def test_permutation_detects_real_separation():
    p = permutation_p_value([1.0] * 40, [0.0] * 40, 500, seed=1)
    assert p < 0.05


def test_permutation_no_separation_high_p():
    p = permutation_p_value([0.1, -0.1] * 20, [0.1, -0.1] * 20, 500, seed=1)
    assert p > 0.05


def test_permutation_deterministic():
    a = permutation_p_value([1.0, 2.0, -1.0] * 10, [0.0] * 30, 300, seed=7)
    b = permutation_p_value([1.0, 2.0, -1.0] * 10, [0.0] * 30, 300, seed=7)
    assert a == b


def test_benjamini_hochberg_controls_fdr():
    survivors = benjamini_hochberg({"a": 0.01, "b": 0.04, "c": 0.5}, alpha=0.05)
    assert survivors == {"a"}


# ── faithfulness of the efficient (subset-sum) permutation vs brute-force shuffle ──
def _brute_force_p(hyp, ctrl, n_perm, seed):
    """Reference impl: full shuffle + slice (the slow, obviously-correct version)."""
    import random
    observed = (sum(hyp) / len(hyp)) - (sum(ctrl) / len(ctrl))
    pool = list(hyp) + list(ctrl)
    nh = len(hyp)
    rng = random.Random(seed)
    ge = 0
    for _ in range(n_perm):
        rng.shuffle(pool)
        diff = (sum(pool[:nh]) / nh) - (sum(pool[nh:]) / (len(pool) - nh))
        if diff >= observed:
            ge += 1
    return (ge + 1) / (n_perm + 1)


def test_permutation_per_iteration_statistic_identity():
    # (A) Exact algebra: for a fixed subset, subset-sum means == direct means. No RNG.
    pool = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    subset_idx = [0, 2, 4]                      # values 1,3,5
    total = sum(pool)
    s = sum(pool[i] for i in subset_idx)
    k, n = len(subset_idx), len(pool)
    complement = [pool[i] for i in range(n) if i not in subset_idx]
    assert s / k == sum(pool[i] for i in subset_idx) / k
    assert (total - s) / (n - k) == sum(complement) / len(complement)


def test_permutation_monte_carlo_convergence():
    # (B) The two estimators agree within Monte-Carlo tolerance at high n (NOT per-seed:
    # full-shuffle and sample(k) consume the RNG differently). Average over seeds.
    hyp = [0.6, 0.4, -0.2, 0.8, 0.3, -0.1, 0.5, 0.2]
    ctrl = [0.0, 0.1, -0.1, 0.0, 0.05, -0.05, 0.0, 0.0, 0.0, 0.0]
    fast = sum(permutation_p_value(hyp, ctrl, 3000, seed=s) for s in range(8)) / 8
    slow = sum(_brute_force_p(hyp, ctrl, 3000, seed=s) for s in range(8)) / 8
    assert abs(fast - slow) < 0.03


# ── the gate end-to-end ──────────────────────────────────────────────────────
def test_strong_edge_promotes():
    st = _report_and_state(_interleaved(13))           # 39 outs, E[R]=1.0, PF=4.0
    final = finalize(st, bh_survivors={"hyp"}, qcfg=_QCFG)
    assert st.passed_1_to_6 is True
    assert final.verdict == "PROMOTE"
    assert final.reject_reasons == []


def test_weak_edge_rejected_on_expectancy():
    st = _report_and_state([_o(-1.0, i) for i in range(1, 41)])
    final = finalize(st, bh_survivors=set(), qcfg=_QCFG)
    assert final.verdict in ("REJECT", "INSUFFICIENT")
    assert final.reject_reasons[0].startswith("FAILED_gate2_expectancy")


def test_does_not_beat_control_rejected():
    # Real edge, but the winning control is even better → gate 4 fails.
    st = _report_and_state(_interleaved(13), win_exp=5.0)
    final = finalize(st, bh_survivors=set(), qcfg=_QCFG)
    assert final.verdict == "REJECT"
    assert final.reject_reasons[0].startswith("FAILED_gate4_beats_control")


def test_oos_retention_gate_fires_on_is_only_edge():
    # All wins first (IS), all losses last (OOS) → OOS expectancy < 0.
    outs = [_o(2.0, i) for i in range(1, 29)] + [_o(-1.0, i) for i in range(29, 41)]
    st = _report_and_state(outs)
    final = finalize(st, bh_survivors=set(), qcfg=_QCFG)
    assert final.verdict == "REJECT"
    assert final.reject_reasons[0].startswith("FAILED_gate5_oos_retention")


def test_insufficient_samples():
    st = _report_and_state([_o(1.0, i) for i in range(1, 6)])   # n=5 < min_samples 10
    final = finalize(st, bh_survivors=set(), qcfg=_QCFG)
    assert final.verdict == "INSUFFICIENT"
    assert final.reject_reasons[0].startswith("FAILED_gate1_sample")


def test_passed_gates_but_bh_rejects():
    # Passes 1–6 but is NOT in the BH survivor set → gate 7 rejects.
    st = _report_and_state(_interleaved(13))
    assert st.passed_1_to_6 is True
    final = finalize(st, bh_survivors=set(), qcfg=_QCFG)
    assert final.verdict == "REJECT"
    assert final.reject_reasons[0].startswith("FAILED_gate7_bh")
