"""regime_conditioning.py — Program 4 conditioning harness (the only new measurement).

Tests whether a NON-DIRECTIONAL target (volatility regime) carries economic value by
**conditioning a directional consumer** on the regime label at its entry bar, and asking
whether any regime cell clears the UNCHANGED M4 gate while beating the pre-registered
controls. It adds NO new oracle: it partitions a consumer's `forward_walk` Outcomes and
runs each cell through `research.qualification` (evaluate_pre_bh / benjamini_hochberg /
finalize) VERBATIM — i.e. Program 4 competes in Program 1's court.

The regime claim's significance is a LABEL-PERMUTATION test (not a point comparison): the
statistic is `S = max over regimes of (cell_E − unconditioned_E)` (the best concentration of
edge into a regime), and the null is `S` recomputed over many seeded random/shuffled
relabelings. This honestly handles "one of three cells might get lucky" — the null maxes over
regimes too — and prevents a consumer's unconditioned edge from masquerading as a regime edge.
The lagged-regime control separates persistence from forecast skill (REGIME_REDUNDANT).

See docs/research-readiness/program-4-nondirectional-preregistration.md. Grants no authority
(§6.5): a positive result is information → shadow, never production weight.

PROGRAM 4B EXTENSION (additive, backward-compatible): `evaluate_scope()` accepts an optional
trailing `current_level_series` argument (default `None`, preserving Program 4's original
behavior byte-for-byte at every existing call site — see
`test_evaluate_scope_without_current_level_series_matches_pre_4b_behavior` in
`tests/test_regime_conditioning.py`). When supplied, `label_series` is understood to carry a
PREDICTED regime (e.g. `interpreters.regime_observer.MarkovRegimeForecaster.forecast_series`)
rather than the contemporaneous one, and a 5th control — `_within_tercile_relabeler` — is
activated: it shuffles the predicted label only WITHIN each CURRENT-level bucket, isolating
whether an apparent uplift is really just the (already-falsified, F-030) level signal
reappearing under the predicted label's name. See
docs/research-readiness/program-4b-transition-preregistration.md §3.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from research.contracts import Outcome
from research.costs import CostModel
from research.measurement.metrics import EdgeAggregator
from research.qualification import (
    QualConfig,
    _net_rrs,
    _seed_for,
    benjamini_hochberg,
    evaluate_pre_bh,
    finalize,
)

CONDITIONING_VERSION = "1.2"

# Canonical regime order — mirrors interpreters.regime_observer.REGIMES. Defined locally
# to keep the research layer isolated (no interpreters/config_layer import). The guard test
# tests/test_regime_conditioning.py pins them equal so they cannot drift.
REGIMES: tuple[str, str, str] = ("C", "N", "E")

_NEG_INF = float("-inf")


# ── config (the `regime` block; hash-neutral to ResearchConfig) ───────────────
@dataclass(frozen=True)
class RegimeConfig:
    atr_period: int
    tercile_window: int
    lag_k: int
    min_cell_samples: int
    harmful_margin: float
    redundant_tol: float
    null_relabelings: int     # # of random + # of shuffled relabelings in the null

    @classmethod
    def from_dict(cls, d: dict) -> "RegimeConfig":
        r = d.get("regime", {})
        return cls(
            atr_period=int(r.get("atr_period", 14)),
            tercile_window=int(r.get("tercile_window", 480)),
            lag_k=int(r.get("lag_k", 50)),
            min_cell_samples=int(r.get("min_cell_samples", 30)),
            harmful_margin=float(r.get("harmful_margin", 0.05)),
            redundant_tol=float(r.get("redundant_tol", 0.05)),
            null_relabelings=int(r.get("null_relabelings", 200)),
        )

    @classmethod
    def from_file(cls, path: str | Path) -> "RegimeConfig":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


# ── pure helpers ──────────────────────────────────────────────────────────────
def _expectancy(outcomes: Sequence[Outcome], cost: CostModel) -> float:
    rrs = _net_rrs(list(outcomes), cost)
    return sum(rrs) / len(rrs) if rrs else 0.0


def _labeled_universe(
    per_instrument: dict[str, list[Outcome]],
    label_series: dict[str, list[str | None]],
) -> dict[str, list[tuple[Outcome, str]]]:
    """Per instrument, the (outcome, real_label) pairs whose entry-bar regime is defined.
    This labeled subset is the apples-to-apples universe — cells AND the unconditioned
    baseline are computed over it; unlabeled-warmup bars are excluded from both."""
    out: dict[str, list[tuple[Outcome, str]]] = {}
    for inst in sorted(per_instrument):
        series = label_series.get(inst, [])
        pairs: list[tuple[Outcome, str]] = []
        for o in per_instrument[inst]:
            idx = o.signal.entry_index
            lab = series[idx] if 0 <= idx < len(series) else None
            if lab is not None:
                pairs.append((o, lab))
        out[inst] = pairs
    return out


def _cells(universe: dict[str, list[tuple[Outcome, str]]],
           label_of: Callable[[str, int, Outcome, str], str | None]) -> dict[str, dict[str, list[Outcome]]]:
    """Partition the labeled universe into {regime: {instrument: [outcomes]}} via a relabel
    function. Outcomes whose relabel is None are dropped (used by the lagged control)."""
    cells: dict[str, dict[str, list[Outcome]]] = {g: {} for g in REGIMES}
    for inst in sorted(universe):
        for pos, (o, real) in enumerate(universe[inst]):
            g = label_of(inst, pos, o, real)
            if g in cells:
                cells[g].setdefault(inst, []).append(o)
    return cells


def _uncond_E(universe: dict[str, list[tuple[Outcome, str]]], cost: CostModel) -> float:
    flat = [o for inst in sorted(universe) for (o, _l) in universe[inst]]
    return _expectancy(flat, cost)


def _best_concentration(cells: dict[str, dict[str, list[Outcome]]], baseline_E: float,
                        cost: CostModel, min_n: int) -> tuple[str | None, float]:
    """Statistic S = max over regimes of (cell_E − baseline_E), over cells with >= min_n
    samples. Returns (argmax_regime, S); (None, -inf) if no cell qualifies."""
    best_g, best = None, _NEG_INF
    for g in REGIMES:
        flat = [o for outs in cells[g].values() for o in outs]
        if len(flat) < min_n:
            continue
        uplift = _expectancy(flat, cost) - baseline_E
        if uplift > best:
            best_g, best = g, uplift
    return best_g, best


# ── relabeling schemes (deterministic) ────────────────────────────────────────
def _real_label_of(inst, pos, o, real):
    return real


def _random_relabeler(universe, tag: str):
    """iid draw from each instrument's empirical regime marginal (seeded by `tag`)."""
    import random
    plans: dict[str, list[str]] = {}
    for inst in sorted(universe):
        labels = [real for _o, real in universe[inst]]
        n = len(labels)
        counts = [labels.count(g) for g in REGIMES]
        rng = random.Random(_seed_for(f"{tag}:{inst}:random"))
        draws: list[str] = []
        for _ in range(n):
            x = rng.random() * (n if n else 1)
            acc, pick = 0, REGIMES[-1]
            for g, c in zip(REGIMES, counts):
                acc += c
                if x < acc:
                    pick = g
                    break
            draws.append(pick)
        plans[inst] = draws
    return lambda inst, pos, o, real: plans[inst][pos]


def _shuffled_relabeler(universe, tag: str):
    """Seeded permutation of each instrument's real labels (exact marginal counts kept)."""
    import random
    plans: dict[str, list[str]] = {}
    for inst in sorted(universe):
        labels = [real for _o, real in universe[inst]]
        rng = random.Random(_seed_for(f"{tag}:{inst}:shuffled"))
        rng.shuffle(labels)
        plans[inst] = labels
    return lambda inst, pos, o, real: plans[inst][pos]


def _lagged_relabeler(label_series: dict[str, list[str | None]], lag_k: int):
    """Regime at entry_index − lag_k (None if out of range / unlabeled)."""
    def label_of(inst, pos, o, real):
        series = label_series.get(inst, [])
        j = o.signal.entry_index - lag_k
        return series[j] if 0 <= j < len(series) else None
    return label_of


def _within_tercile_relabeler(
    universe: dict[str, list[tuple[Outcome, str]]],
    current_level_series: dict[str, list[str | None]],
    tag: str,
):
    """Program 4b's 5th control (stratified shuffle). Groups each instrument's entries by
    their CURRENT vol-tercile level at entry_index (from `current_level_series` — e.g.
    RegimeLabeler's contemporaneous S_t, NOT the predicted label under test), then
    seeded-shuffles the label under test only WITHIN each current-level group. This
    preserves the current-level marginal exactly while destroying any genuine
    transition-forecast information — isolating whether an apparent uplift is really just
    the (already-falsified, F-030) LEVEL signal reappearing under the predicted label's name."""
    import random
    plans: dict[str, list[str]] = {}
    for inst in sorted(universe):
        pairs = universe[inst]                       # [(outcome, label_under_test), ...]
        series = current_level_series.get(inst, [])
        labels = [lab for _o, lab in pairs]
        out: list[str] = [None] * len(labels)         # type: ignore[list-item]

        buckets: dict[str | None, list[int]] = {g: [] for g in REGIMES}
        buckets[None] = []
        for pos, (o, _lab) in enumerate(pairs):
            idx = o.signal.entry_index
            cur = series[idx] if 0 <= idx < len(series) else None
            buckets[cur].append(pos)

        rng = random.Random(_seed_for(f"{tag}:{inst}:within_tercile"))
        for cur in list(REGIMES) + [None]:
            positions = buckets[cur]
            bucket_labels = [labels[p] for p in positions]
            rng.shuffle(bucket_labels)
            for p, lab in zip(positions, bucket_labels):
                out[p] = lab
        plans[inst] = out
    return lambda inst, pos, o, real: plans[inst][pos]


def _label_permutation_p(universe, uncond_E: float, S_real: float, cost: CostModel,
                         rcfg: RegimeConfig, consumer: str) -> tuple[float, float]:
    """Label-permutation test: P(S_null >= S_real) where the null draws random + shuffled
    relabelings. Returns (p_value, null_p95). p=1.0 if S_real is -inf (no qualifying cell)."""
    if S_real == _NEG_INF:
        return 1.0, 0.0
    nulls: list[float] = []
    for b in range(rcfg.null_relabelings):
        for scheme in (_random_relabeler, _shuffled_relabeler):
            cells = _cells(universe, scheme(universe, f"{consumer}:{b}"))
            nulls.append(_best_concentration(cells, uncond_E, cost, rcfg.min_cell_samples)[1])
    finite = [s for s in nulls if s != _NEG_INF]
    ge = sum(1 for s in nulls if s >= S_real)
    p = (ge + 1) / (len(nulls) + 1)
    if finite:
        k = max(0, min(len(finite) - 1, int(round(0.95 * (len(finite) - 1)))))
        null_p95 = sorted(finite)[k]
    else:
        null_p95 = 0.0
    return p, null_p95


def _consumer_verdict(
    *,
    has_exploitable: bool,
    all_insufficient: bool,
    redundant: bool,
    n_harmful: int,
    n_beneficial: int,
) -> str:
    """Roll a consumer's per-cell results up to a single verdict (E-001E invariant).

    Pure function of the rollup inputs so the precedence can be tested behaviorally
    (see tests/governance/test_epistemic_invariants.py). The `all_insufficient` guard
    MUST precede the harmful check: a consumer whose every cell failed the sample gate
    is UNDERPOWERED, so its sign-counts are noise and must report REGIME_INSUFFICIENT,
    never REGIME_HARMFUL/INFORMATIONAL (the spine-throughput case, F-019/F-022). This is
    the v1.1->v1.2 fix that closed F-030 — removing the guard re-opens the overclaim.
    """
    if has_exploitable:
        return "REGIME_EXPLOITABLE"
    if all_insufficient:
        return "REGIME_INSUFFICIENT"
    if redundant:
        return "REGIME_REDUNDANT"
    if n_harmful > n_beneficial and n_harmful > 0:
        return "REGIME_HARMFUL"
    return "REGIME_INFORMATIONAL"


# ── the scope evaluation ───────────────────────────────────────────────────────
def evaluate_scope(
    consumers: dict[str, dict[str, list[Outcome]]],
    controls: dict[str, dict[str, list[Outcome]]],
    label_series: dict[str, list[str | None]],
    qcfg: QualConfig,
    cost: CostModel,
    rcfg: RegimeConfig,
    scope_instruments: list[str],
    current_level_series: dict[str, list[str | None]] | None = None,
) -> dict:
    """Run the full 3×3 cross-matrix (consumers × regimes) for one scope, single pass.
    M4 gate verdicts use cohort BH across all real cells; the *regime* significance is the
    label-permutation test. Returns a deterministic, byte-comparable dict (no wall-clock).

    `current_level_series` (Program 4b only, default None): when supplied, activates the
    within-tercile-shuffle 5th control (see module docstring) — omitting it reproduces
    Program 4's original behavior exactly."""
    agg = EdgeAggregator()

    # Winning directional control over this scope (== qualify_majors semantics) — reused
    # for gate-4 (beats-control) and gate-6 (permutation).
    win_name, win_rrs, win_exp = "none", [], _NEG_INF
    for name in sorted(controls):
        per = {i: controls[name].get(i, []) for i in scope_instruments}
        rrs: list[float] = []
        for outs in per.values():
            rrs.extend(_net_rrs(outs, cost))
        rep = agg.aggregate(name, sorted(scope_instruments),
                            [o for outs in per.values() for o in outs], cost_model=cost)
        if rep.expectancy_rr > win_exp:
            win_name, win_rrs, win_exp = name, rrs, rep.expectancy_rr
    if win_exp == _NEG_INF:
        win_name, win_rrs, win_exp = "none", [], 0.0

    pre: dict[str, dict] = {}
    bh_inputs: dict[str, float] = {}

    for consumer in sorted(consumers):
        per_inst = {i: consumers[consumer].get(i, []) for i in scope_instruments}
        universe = _labeled_universe(per_inst, label_series)
        uncond_E = _uncond_E(universe, cost)

        real_cells = _cells(universe, _real_label_of)
        real_arg, S_real = _best_concentration(real_cells, uncond_E, cost, rcfg.min_cell_samples)
        p_label, null_p95 = _label_permutation_p(universe, uncond_E, S_real, cost, rcfg, consumer)

        # Lagged control: best concentration under a STALE regime, own baseline.
        lag_cells = _cells(universe, _lagged_relabeler(label_series, rcfg.lag_k))
        lag_flat = [o for g in REGIMES for outs in lag_cells[g].values() for o in outs]
        lag_uncond_E = _expectancy(lag_flat, cost)
        _lag_arg, S_lagged = _best_concentration(lag_cells, lag_uncond_E, cost, rcfg.min_cell_samples)

        # Within-tercile-shuffle control (Program 4b's 5th control, only when a current-level
        # series is supplied — None here reproduces Program 4's original behavior exactly).
        S_within_tercile = None
        if current_level_series is not None:
            wt_cells = _cells(universe, _within_tercile_relabeler(universe, current_level_series, consumer))
            wt_flat = [o for g in REGIMES for outs in wt_cells[g].values() for o in outs]
            wt_uncond_E = _expectancy(wt_flat, cost)
            _wt_arg, S_within_tercile = _best_concentration(wt_cells, wt_uncond_E, cost, rcfg.min_cell_samples)

        # M4 gate per real cell (cohort BH applied after, across all cells in the scope).
        states, cell_E = {}, {}
        for g in REGIMES:
            per_g = {i: real_cells[g].get(i, []) for i in scope_instruments}
            flat = [o for outs in per_g.values() for o in outs]
            rep = agg.aggregate(f"{consumer}|{g}", sorted(scope_instruments), flat, cost_model=cost)
            st = evaluate_pre_bh(rep, per_g, win_name, win_rrs, win_exp, qcfg, cost)
            states[g] = st
            cell_E[g] = _expectancy(flat, cost)
            if st.passed_1_to_6:
                bh_inputs[f"{consumer}|{g}"] = st.p_value

        pre[consumer] = {
            "states": states, "cell_E": cell_E, "uncond_E": uncond_E,
            "real_arg": real_arg, "S_real": S_real, "p_label": p_label,
            "null_p95": null_p95, "S_lagged": S_lagged, "lag_uncond_E": lag_uncond_E,
            "S_within_tercile": S_within_tercile,
        }

    bh_survivors = benjamini_hochberg(bh_inputs, qcfg.significance_alpha)

    consumers_out: dict[str, dict] = {}
    scope_exploitable = False
    for consumer in sorted(pre):
        p = pre[consumer]
        uncond_E = p["uncond_E"]
        S_real = p["S_real"]
        # Regime significance + persistence guard (consumer-level).
        beats_nulls = (S_real != _NEG_INF and S_real > 0.0
                       and p["p_label"] <= qcfg.significance_alpha)
        redundant_lagged = beats_nulls and (p["S_lagged"] >= S_real - rcfg.redundant_tol)
        s_wt = p.get("S_within_tercile")
        redundant_within_tercile = bool(
            beats_nulls and s_wt is not None and s_wt != _NEG_INF
            and s_wt >= S_real - rcfg.redundant_tol
        )
        # Combined: an edge redundant with EITHER a stale regime (persistence, F-030's
        # lagged check) OR the current vol level (Program 4b's within-tercile check) is not
        # genuine transition-forecast skill. Old callers (current_level_series=None) get
        # redundant == redundant_lagged exactly, i.e. byte-identical to pre-4b behavior.
        redundant = redundant_lagged or redundant_within_tercile

        cells_out = {}
        n_harmful = n_beneficial = 0
        for g in REGIMES:
            final = finalize(p["states"][g], bh_survivors, qcfg)
            cell_E_g = p["cell_E"][g]
            uplift = cell_E_g - uncond_E
            harmful = cell_E_g < (uncond_E - rcfg.harmful_margin)
            beneficial = uplift > 0.0
            if harmful:
                n_harmful += 1
            if beneficial and final.n >= rcfg.min_cell_samples:
                n_beneficial += 1
            # A cell is exploitable iff it is the best real cell AND it clears M4 AND the
            # regime labeling beats the null distribution AND it isn't mere persistence.
            exploitable = (g == p["real_arg"] and final.verdict == "PROMOTE"
                           and beats_nulls and not redundant)
            if exploitable:
                scope_exploitable = True
            cells_out[g] = {
                "n": final.n,
                "expectancy_rr": final.expectancy_rr,
                "profit_factor": final.profit_factor,
                "p_value": final.p_value,
                "gate_verdict": final.verdict,
                "reject_reasons": final.reject_reasons,
                "uplift_real": round(uplift, 6),
                "harmful": harmful,
                "is_best_cell": g == p["real_arg"],
                "cell_verdict": "REGIME_EXPLOITABLE" if exploitable else (
                    "REGIME_INSUFFICIENT" if final.verdict == "INSUFFICIENT" else (
                        "REGIME_HARMFUL" if harmful else "REGIME_INFORMATIONAL")),
            }

        # Roll the per-cell results up to a consumer verdict. The all_insufficient guard
        # (underpowered consumer -> REGIME_INSUFFICIENT, not HARMFUL) lives inside the pure
        # _consumer_verdict helper so the E-001E invariant is behaviorally testable. F-019/F-022.
        all_insufficient = all(cells_out[g]["gate_verdict"] == "INSUFFICIENT" for g in REGIMES)
        verdict = _consumer_verdict(
            has_exploitable=any(
                c["cell_verdict"] == "REGIME_EXPLOITABLE" for c in cells_out.values()
            ),
            all_insufficient=all_insufficient,
            redundant=redundant,
            n_harmful=n_harmful,
            n_beneficial=n_beneficial,
        )

        consumer_out = {
            "verdict": verdict,
            "unconditioned_E": round(uncond_E, 6),
            "best_regime": p["real_arg"],
            "S_real": None if S_real == _NEG_INF else round(S_real, 6),
            "p_label": round(p["p_label"], 6),
            "null_p95": round(p["null_p95"], 6),
            "S_lagged": None if p["S_lagged"] == _NEG_INF else round(p["S_lagged"], 6),
            "beats_nulls": beats_nulls,
            "redundant": redundant,
            "cells": cells_out,
        }
        # Program 4b fields are only ADDED to the dict when the extension is active, so a
        # call without current_level_series (every existing Program 4 call site) produces a
        # JSON body with the exact same key set as before this change — byte-identical,
        # protecting F-030's already-registered artifact reproducibility.
        if current_level_series is not None:
            consumer_out["S_within_tercile"] = (
                None if s_wt is None or s_wt == _NEG_INF else round(s_wt, 6)
            )
            consumer_out["redundant_lagged"] = redundant_lagged
            consumer_out["redundant_within_tercile"] = redundant_within_tercile
        consumers_out[consumer] = consumer_out

    if scope_exploitable:
        scope_verdict = "REGIME_EXPLOITABLE"
    else:
        verdicts = {c["verdict"] for c in consumers_out.values()}
        # Precedence: an informative verdict dominates INSUFFICIENT (an underpowered consumer
        # shouldn't mask a real signal from another consumer in the same scope).
        scope_verdict = next(
            (v for v in ("REGIME_HARMFUL", "REGIME_REDUNDANT", "REGIME_INFORMATIONAL",
                         "REGIME_INSUFFICIENT") if v in verdicts),
            "REGIME_INFORMATIONAL")

    return {
        "conditioning_version": CONDITIONING_VERSION,
        "winning_control": win_name,
        "winning_control_exp": round(win_exp, 6),
        "lag_k": rcfg.lag_k,
        "null_relabelings": rcfg.null_relabelings,
        "scope_verdict": scope_verdict,
        "consumers": consumers_out,
    }
