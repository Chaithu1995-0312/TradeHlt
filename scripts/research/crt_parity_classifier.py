"""
CRT Semantic Parity — Mismatch Classifier (pure, F-069 program)
=================================================================
READ-ONLY / PURE. No repository imports, no file I/O, no network. Every
function here is a deterministic transform over its arguments only, so it can
be driven with synthetic inputs in tests (E-001: a test that cannot fail is
not enforcement) and reused unchanged by the Phase-2 vision root-cause
classifier (same taxonomy shape, different category codes).

WHY THIS EXISTS
----------------
Pre-registration: docs/research/preregistration-crt-semantic-parity.md
The CRT Semantic Parity program (CRTStateResolver vs BacktestRunner, config
tuning only) must classify every residual mismatch — never report a bare
"mismatch". Each rule below is grounded in a specific, cited code fact, not a
guess:

  * EXECUTION fails closed for lack of a `score`/`risk_score`/`crt_score`
    feature (src/features/crt_state_resolver.py, `_continuous_gates_pass`
    EXECUTION branch) — none of those keys exist in `CANONICAL_FEATURES`
    (src/features/feature_schema.py), so no resolver config can ever produce
    an EXECUTION bar on a real 39-dim vector.
  * RESOLUTION / EXPIRED are declared `when: {}` in
    configs/formulas/market_crt_states.yaml (trade-state / TTL-only) — not
    reachable via any predicate threshold.
  * MIN_CELL_N=15 mirrors the established under-power discipline
    (scripts/analysis/blind_label_score.py) — a cell below this floor is
    reported INSUFFICIENT, never promoted to a causal (A/B/C) verdict
    (tests/governance/test_epistemic_invariants.py::test_qualification_insufficient_guard).

AUTHORITY
---------
Research only. Classifying a mismatch grants no promotion/production
authority (§6.5). `aggregate_categories` never returns a determination
stronger than the weakest evidence present (E-001E: parent ≤ children).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Mapping, Sequence

CERT_VERSION = "1.0.0"

MIN_CELL_N = 15
TAU_MARGINAL = 0.15   # |resolver_n - engine_n| / engine_n, "marginals agree" threshold
TAU_RECALL = 0.60     # recall at/below which a marginal-agreeing cell is a phase error

# engine_state -> (rationale, evidence file:line-ish citation). Structural facts,
# verified by reading source — NOT a statistical claim, so classified even when
# engine_n < MIN_CELL_N (e.g. EXECUTION at n=5).
STRUCTURALLY_UNREACHABLE_STATES: dict[str, str] = {
    "EXECUTION": (
        "_continuous_gates_pass fails EXECUTION closed when "
        "raw.get('score'/'risk_score'/'crt_score') is None; none of those "
        "three keys exist in CANONICAL_FEATURES, so the gate is "
        "unconditionally closed on any real 39-dim vector."
    ),
    "RESOLUTION": (
        "Declared `when: {}` in configs/formulas/market_crt_states.yaml "
        "(trade-state-only; no predicate can enter it)."
    ),
    "EXPIRED": (
        "Declared `when: {}` in configs/formulas/market_crt_states.yaml "
        "(TTL-only; no predicate can enter it)."
    ),
}

STRUCTURAL_EVIDENCE: dict[str, str] = {
    "EXECUTION": "src/features/crt_state_resolver.py::_continuous_gates_pass",
    "RESOLUTION": "configs/formulas/market_crt_states.yaml (states.RESOLUTION.when)",
    "EXPIRED": "configs/formulas/market_crt_states.yaml (states.EXPIRED.when)",
}

# Threshold names that exist by the same name on both the resolver YAML and
# CRTConfig — a value delta here is direct, checkable Category-A evidence.
SHARED_THRESHOLD_NAMES: tuple[str, ...] = (
    "body_ratio_min",
    "atr_multiplier_min",
    "atr_min_displacement",
    "max_sweep_age_candles",
    "max_displacement_age_candles",
    "expansion_atr_min_distance",
    "retest_depth_max",
    "retest_atr_depth_fraction",
    "max_expansion_age_candles",
    "score_threshold",
    "pending_displacement_ttl_candles",
)

CATEGORY_PRECEDENCE: tuple[str, ...] = (
    "B-UNREACHABLE-STATE",
    "INSUFFICIENT",
    "B-NO-COUNTERPART",
    "A-THRESHOLD-DELTA",
    "A-SWEEP-REACHABLE",
    "C-PHASE-ERROR",
    "C-GEOMETRY",
    "D-UNKNOWN",
)


@dataclass(frozen=True)
class MismatchContext:
    """Everything a classification decision may reference. Immutable —
    callers build a fresh context per sweep-report evaluation.
    """

    resolver_thresholds: Mapping[str, float] = field(default_factory=dict)
    engine_thresholds: Mapping[str, float] = field(default_factory=dict)
    # state -> (engine_n, resolver_n, true_positive_n)
    state_marginals: Mapping[str, tuple[int, int, int]] = field(default_factory=dict)
    # (engine_state, resolver_state) pairs a sweep candidate demonstrably shrank
    cells_improved_by_sweep: frozenset[tuple[str, str]] = frozenset()
    # (engine_state, resolver_state) pairs known to derive from structurally
    # different geometry despite a shared name (e.g. pipeline last-swing
    # liquidity_sweep vs engine RangeDetector.detect_sweep over a frozen HTF range)
    known_geometry_divergent_pairs: frozenset[tuple[str, str]] = frozenset()
    # Threshold names that exist ONLY on the engine side (no resolver
    # counterpart) — a transition reason naming one of these cannot be
    # closed by any resolver config.
    engine_only_threshold_names: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Classification:
    category: str          # "A" | "B" | "C" | "D" | "INSUFFICIENT"
    code: str               # one of CATEGORY_PRECEDENCE
    summary: str
    rationale: str
    evidence_ref: str
    payload: Mapping[str, object] = field(default_factory=dict)


def classify_mismatch(
    engine_state: str,
    resolver_state: str,
    episode: Mapping[str, object],
    ctx: MismatchContext,
) -> Classification:
    """Classify one engine/resolver mismatch cell. Pure — no I/O, no mutation.

    `episode` is expected to optionally carry `engine_transition_reason`
    (str | None) — the engine STATE_TRANSITION `reason` text associated with
    entries into `engine_state`, used only for the B-NO-COUNTERPART check.
    Absent/empty is handled gracefully (that check is simply skipped).
    """
    # 1. Structural unreachability — deductive fact from source, Certain even
    #    at low n (this is why it precedes the power gate).
    if engine_state in STRUCTURALLY_UNREACHABLE_STATES:
        return Classification(
            category="B",
            code="B-UNREACHABLE-STATE",
            summary=f"{engine_state} cannot be reproduced by any resolver configuration.",
            rationale=STRUCTURALLY_UNREACHABLE_STATES[engine_state],
            evidence_ref=STRUCTURAL_EVIDENCE[engine_state],
            payload={"engine_state": engine_state, "resolver_state": resolver_state},
        )

    eng_n, res_n, tp = ctx.state_marginals.get(engine_state, (0, 0, 0))

    # 2. Power gate — statistical (not deductive) claims require MIN_CELL_N.
    if eng_n < MIN_CELL_N:
        return Classification(
            category="INSUFFICIENT",
            code="INSUFFICIENT",
            summary=f"{engine_state}: engine_n={eng_n} below the power floor.",
            rationale=(
                f"engine_n={eng_n} < MIN_CELL_N={MIN_CELL_N}; a causal "
                "classification would overclaim precision the sample can't support."
            ),
            evidence_ref="scripts/analysis/blind_label_score.py (MIN_CELL_N precedent)",
            payload={"engine_n": eng_n, "resolver_n": res_n, "tp": tp},
        )

    # 3. No-counterpart — the engine transition reason names a gate with no
    #    resolver-side counterpart.
    reason = str(episode.get("engine_transition_reason") or "").lower()
    no_counterpart_hit = next(
        (name for name in sorted(ctx.engine_only_threshold_names) if name.lower() in reason),
        None,
    )
    if no_counterpart_hit:
        return Classification(
            category="B",
            code="B-NO-COUNTERPART",
            summary=f"{engine_state}->{resolver_state}: engine gate has no resolver counterpart.",
            rationale=(
                f"Engine transition reason references '{no_counterpart_hit}', which has no "
                "key in the resolver's threshold config — not tunable from the resolver side."
            ),
            evidence_ref="configs/formulas/market_crt_states.yaml (thresholds:)",
            payload={"engine_state": engine_state, "resolver_state": resolver_state,
                      "matched_threshold": no_counterpart_hit},
        )

    # 4. Threshold-delta — a shared-name threshold differs between the two configs.
    delta_names = sorted(
        name for name in SHARED_THRESHOLD_NAMES
        if name in ctx.resolver_thresholds and name in ctx.engine_thresholds
        and ctx.resolver_thresholds[name] != ctx.engine_thresholds[name]
    )
    if delta_names:
        return Classification(
            category="A",
            code="A-THRESHOLD-DELTA",
            summary=f"{engine_state}->{resolver_state}: shared threshold(s) diverge.",
            rationale=(
                f"Threshold(s) {delta_names} exist by the same name on both sides with "
                "different values — a direct, tunable configuration lever."
            ),
            evidence_ref="configs/formulas/market_crt_states.yaml vs "
                         "src/config_layer/state_identity.py (CRTConfig)",
            payload={"engine_state": engine_state, "resolver_state": resolver_state,
                      "delta_names": delta_names},
        )

    # 5. Sweep-reachable — a candidate demonstrably shrank this exact cell.
    if (engine_state, resolver_state) in ctx.cells_improved_by_sweep:
        return Classification(
            category="A",
            code="A-SWEEP-REACHABLE",
            summary=f"{engine_state}->{resolver_state}: shrunk by a swept candidate.",
            rationale="A candidate in the swept parameter range demonstrably reduced this cell.",
            evidence_ref="results/analysis/crt_parity_sweep/ledger.jsonl",
            payload={"engine_state": engine_state, "resolver_state": resolver_state},
        )

    # 6. Phase error — marginals agree but positions don't.
    recall = tp / eng_n if eng_n else 0.0
    marginal_delta = abs(res_n - eng_n) / eng_n if eng_n else 1.0
    if marginal_delta <= TAU_MARGINAL and recall <= TAU_RECALL:
        return Classification(
            category="C",
            code="C-PHASE-ERROR",
            summary=f"{engine_state}: right count, wrong bars (recall={recall:.2f}).",
            rationale=(
                f"Resolver emits a similar TOTAL count of {engine_state} "
                f"(res_n={res_n} vs eng_n={eng_n}, delta={marginal_delta:.2%}) but recall is "
                f"only {recall:.2%} — the state fires on the wrong bars, not the wrong count. "
                "Timing/lifecycle defect, not a volume defect."
            ),
            evidence_ref="results/analysis/crt_parity_sweep/ (per-state marginals)",
            payload={"engine_state": engine_state, "eng_n": eng_n, "res_n": res_n,
                      "recall": recall, "marginal_delta": marginal_delta},
        )

    # 7. Geometry — same-named quantity, structurally different derivation.
    if (engine_state, resolver_state) in ctx.known_geometry_divergent_pairs:
        return Classification(
            category="C",
            code="C-GEOMETRY",
            summary=f"{engine_state}->{resolver_state}: divergent detector geometry.",
            rationale=(
                "The two sides compute a same-named quantity from structurally different "
                "inputs (e.g. pipeline last-swing detection vs engine frozen-HTF-range "
                "detection) — not a threshold value, a different construction."
            ),
            evidence_ref="src/features/crt_state_resolver.py vs "
                         "src/config_layer/crt_engine_v2.py (RangeDetector)",
            payload={"engine_state": engine_state, "resolver_state": resolver_state},
        )

    # 8. Fallthrough — investigated, never left silently unlabeled.
    return Classification(
        category="D",
        code="D-UNKNOWN",
        summary=f"{engine_state}->{resolver_state}: no rule matched.",
        rationale="None of the B/A/C rules applied; requires manual investigation.",
        evidence_ref="",
        payload={"engine_state": engine_state, "resolver_state": resolver_state},
    )


def aggregate_categories(classifications: Sequence[Classification]) -> dict:
    """Pure rollup. Never returns a determination stronger than the weakest
    evidence present (E-001E: parent verdict <= children).
    """
    total = len(classifications)
    by_category = Counter(c.category for c in classifications)
    by_code = Counter(c.code for c in classifications)

    if total == 0:
        determination = "Inconclusive"
    elif by_category.get("D", 0) > 0:
        determination = "Inconclusive"
    else:
        has_a = by_category.get("A", 0) > 0
        has_b = by_category.get("B", 0) > 0
        has_c = by_category.get("C", 0) > 0
        n_causal_kinds = sum([has_a, has_b, has_c])
        if n_causal_kinds == 0:
            # Only INSUFFICIENT (and/or nothing) present — no causal claim earned.
            determination = "Inconclusive"
        elif n_causal_kinds == 1:
            determination = "Configuration" if has_a else (
                "Implementation" if has_b else "Implementation"
            )
        else:
            determination = "Mixed"

    return {
        "cert_version": CERT_VERSION,
        "total": total,
        "by_category": dict(by_category),
        "by_code": dict(by_code),
        "determination": determination,
    }
