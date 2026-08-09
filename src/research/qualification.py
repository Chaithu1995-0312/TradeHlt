"""qualification.py — M4 QualificationGate for the Edge Discovery Program.

The rejection gate. A hypothesis is PROMOTE only if it clears **seven ordered gates**:

  1. sample size        — n >= min_samples              (else INSUFFICIENT)
  2. expectancy (NET)    — E[R] >= expectancy_min
  3. profit factor (NET) — PF   >= pf_min
  4. beats control       — E[R] > the WINNING control's E[R]  (baseline_delta > 0)
  5. OOS retention       — IS & OOS both E[R] > 0 AND oos/is >= oos_retention_min
  6. permutation sig.    — one-sided two-sample permutation p (vs winning control) <= alpha
  7. Benjamini-Hochberg  — survives FDR correction across all hypotheses in the cohort

Gates 1–6 are per-hypothesis and short-circuit (the first failure is `reject_reasons[0]`,
i.e. the nearest failure gate). Gate 7 is a cohort-level multiple-comparison correction —
**the single most important defense against a broad search becoming a false-discovery
engine.** Everything is NET of costs (EdgeAggregator already nets).

ISOLATION: pure stdlib + research-internal imports only — never the live spine.
DETERMINISM: the permutation RNG is seeded from the hypothesis name, so verdicts are
byte-reproducible.

A clean PROMOTE: none across all hypotheses is a SUCCESSFUL experiment — it means no
evidence of edge under the unified intrabar truth standard.
"""

from __future__ import annotations

import dataclasses
import hashlib
from dataclasses import dataclass

from research.contracts import EdgeReport, Outcome
from research.costs import CostModel
from research.measurement.metrics import EdgeAggregator

# Governance versions — the statistical method IS governance. Bump when the gate
# sequence / permutation algorithm / FDR implementation changes, so stored verdicts
# stay interpretable. Stamped into every qualification report.
QUALIFICATION_VERSION = "1.0"
PERMUTATION_METHOD_VERSION = "1.0"
BH_METHOD_VERSION = "1.0"


@dataclass(frozen=True)
class QualConfig:
    min_samples: int
    expectancy_min: float
    pf_min: float
    oos_split: float           # fraction held out as OOS (chronological, per-instrument)
    oos_retention_min: float
    n_permutations: int
    significance_alpha: float

    @classmethod
    def from_research_config(cls, rc) -> "QualConfig":
        return cls(
            min_samples=rc.q_min_samples,
            expectancy_min=rc.q_expectancy_min,
            pf_min=rc.q_pf_min,
            oos_split=rc.q_oos_split,
            oos_retention_min=rc.q_oos_retention_min,
            n_permutations=rc.q_n_permutations,
            significance_alpha=rc.q_significance_alpha,
        )


# ── numeric helpers (pure) ───────────────────────────────────────────────────
def _net_rrs(outcomes: list[Outcome], cost: CostModel) -> list[float]:
    return [
        cost.net_rr(o.rr_achieved, o.signal.entry, o.signal.sl_atr_mult * o.signal.atr)
        for o in outcomes
    ]


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _split_is_oos(
    per_instrument: dict[str, list[Outcome]], oos_split: float
) -> tuple[list[Outcome], list[Outcome]]:
    """Chronological per-instrument split (outcomes are already in detection order):
    first (1-oos_split) → IS, last oos_split → OOS, then pooled across instruments."""
    is_outs: list[Outcome] = []
    oos_outs: list[Outcome] = []
    for instrument in sorted(per_instrument):
        outs = per_instrument[instrument]
        cut = int(round(len(outs) * (1.0 - oos_split)))
        is_outs.extend(outs[:cut])
        oos_outs.extend(outs[cut:])
    return is_outs, oos_outs


def permutation_p_value(
    hyp_rrs: list[float], ctrl_rrs: list[float], n_permutations: int, seed: int
) -> float:
    """One-sided two-sample permutation test: P(perm mean-diff >= observed) under the
    null that hypothesis and control samples are exchangeable. Deterministic (seeded).
    Returns 1.0 when either sample is empty or n_permutations <= 0 (cannot reject).

    PERMUTATION_METHOD_VERSION 1.0 — exact two-sample permutation, computed by sampling
    only the SMALLER group's sum each iteration (the other group's mean follows from
    total - s). This is the identical statistic to shuffle-and-split, at
    O(n_permutations * min(nh, nc)) instead of O(n_permutations * (nh + nc)) — so a
    346k-sample control no longer blows up the cost when the hypothesis is sparse."""
    import random

    nh, nc = len(hyp_rrs), len(ctrl_rrs)
    if nh == 0 or nc == 0 or n_permutations <= 0:
        return 1.0
    observed = _mean(hyp_rrs) - _mean(ctrl_rrs)
    pool = list(hyp_rrs) + list(ctrl_rrs)
    total = sum(pool)
    n = nh + nc
    k = min(nh, nc)                     # sample the smaller side
    rng = random.Random(seed)
    ge = 0
    for _ in range(n_permutations):
        s = 0.0
        for i in rng.sample(range(n), k):
            s += pool[i]
        if k == nh:                     # sampled group == hypothesis
            diff = (s / nh) - ((total - s) / nc)
        else:                           # sampled group == control
            diff = ((total - s) / nh) - (s / nc)
        if diff >= observed:
            ge += 1
    return (ge + 1) / (n_permutations + 1)   # add-one ⇒ never reports p=0


def benjamini_hochberg(pvalues: dict[str, float], alpha: float) -> set[str]:
    """Return the set of names whose p-values survive BH FDR control at `alpha`."""
    if not pvalues:
        return set()
    items = sorted(pvalues.items(), key=lambda kv: kv[1])
    m = len(items)
    max_k = 0
    for i, (_name, p) in enumerate(items, start=1):
        if p <= (i / m) * alpha:
            max_k = i
    return {items[i][0] for i in range(max_k)}


def _seed_for(name: str) -> int:
    return int(hashlib.sha256(name.encode("utf-8")).hexdigest()[:8], 16)


def _summary(report: EdgeReport) -> dict:
    return {"n": report.n, "profit_factor": report.profit_factor,
            "expectancy_rr": report.expectancy_rr, "win_rate": report.win_rate}


# ── the gate ─────────────────────────────────────────────────────────────────
@dataclass
class _GateState:
    """Per-hypothesis result of gates 1–6, before the cohort BH step (gate 7)."""
    report: EdgeReport
    is_report: EdgeReport
    oos_report: EdgeReport
    baseline_name: str
    baseline_delta: float
    oos_retention: float
    p_value: float
    reject_reasons: list[str]      # ordered; [0] = nearest failure gate
    passed_1_to_6: bool
    insufficient: bool


def evaluate_pre_bh(
    report: EdgeReport,
    per_instrument: dict[str, list[Outcome]],
    winning_control_name: str,
    winning_control_rrs: list[float],
    winning_control_exp: float,
    qcfg: QualConfig,
    cost: CostModel,
) -> _GateState:
    """Run gates 1–6 for one hypothesis (short-circuit on first failure)."""
    agg = EdgeAggregator()
    is_outs, oos_outs = _split_is_oos(per_instrument, qcfg.oos_split)
    is_report = agg.aggregate(report.hypothesis, report.instruments, is_outs, cost_model=cost)
    oos_report = agg.aggregate(report.hypothesis, report.instruments, oos_outs, cost_model=cost)
    oos_retention = (oos_report.expectancy_rr / is_report.expectancy_rr
                     if is_report.expectancy_rr > 0 else 0.0)
    baseline_delta = report.expectancy_rr - winning_control_exp

    rr = []
    for outs in per_instrument.values():
        rr.extend(_net_rrs(outs, cost))
    p_value = permutation_p_value(rr, winning_control_rrs, qcfg.n_permutations,
                                  _seed_for(report.hypothesis))

    reasons: list[str] = []
    insufficient = False

    def fail(gate: str, msg: str):
        reasons.append(f"FAILED_{gate}: {msg}")

    # 1 sample
    if report.n < qcfg.min_samples:
        fail("gate1_sample", f"n={report.n} < min_samples={qcfg.min_samples}")
        insufficient = True
    # 2 expectancy
    elif report.expectancy_rr < qcfg.expectancy_min:
        fail("gate2_expectancy", f"E[R]={report.expectancy_rr} < {qcfg.expectancy_min}")
    # 3 profit factor
    elif report.profit_factor < qcfg.pf_min:
        fail("gate3_profit_factor", f"PF={report.profit_factor} < {qcfg.pf_min}")
    # 4 beats winning control
    elif baseline_delta <= 0:
        fail("gate4_beats_control",
             f"E[R]={report.expectancy_rr} <= {winning_control_name} E[R]={winning_control_exp}")
    # 5 OOS retention
    elif not (is_report.expectancy_rr > 0 and oos_report.expectancy_rr > 0
              and oos_retention >= qcfg.oos_retention_min):
        fail("gate5_oos_retention",
             f"is_E={is_report.expectancy_rr} oos_E={oos_report.expectancy_rr} "
             f"retention={round(oos_retention, 4)} < {qcfg.oos_retention_min}")
    # 6 permutation significance
    elif p_value > qcfg.significance_alpha:
        fail("gate6_permutation", f"p={round(p_value, 4)} > alpha={qcfg.significance_alpha}")

    passed_1_to_6 = not reasons
    return _GateState(report, is_report, oos_report, winning_control_name, baseline_delta,
                      oos_retention, p_value, reasons, passed_1_to_6, insufficient)


def finalize(state: _GateState, bh_survivors: set[str], qcfg: QualConfig) -> EdgeReport:
    """Apply gate 7 (cohort BH) and produce the verdict-filled EdgeReport."""
    reasons = list(state.reject_reasons)
    if state.passed_1_to_6 and state.report.hypothesis not in bh_survivors:
        reasons.append(
            f"FAILED_gate7_bh: p={round(state.p_value, 4)} not significant after "
            f"Benjamini-Hochberg FDR={qcfg.significance_alpha}")

    if state.insufficient:
        verdict = "INSUFFICIENT"
    elif reasons:
        verdict = "REJECT"
    else:
        verdict = "PROMOTE"

    return dataclasses.replace(
        state.report,
        is_metrics=_summary(state.is_report),
        oos_metrics=_summary(state.oos_report),
        oos_retention=round(state.oos_retention, 4),
        baseline_name=state.baseline_name,
        baseline_delta=round(state.baseline_delta, 4),
        p_value=round(state.p_value, 6),
        verdict=verdict,
        reject_reasons=reasons,
    )
