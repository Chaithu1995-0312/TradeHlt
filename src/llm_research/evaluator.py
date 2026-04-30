# evaluator.py — generalization, overfitting, and contribution analysis
# Runs AFTER forward test. Determines if LLM policy generalizes.
#
import json
import logging
from pathlib import Path
from src.llm_research.forward_tester import ForwardTestReport, ModeResult

log = logging.getLogger(__name__)


class ResearchEvaluator:
    """
    Post-forward-test analysis:
    1. Generalization: did rules work on unseen data?
    2. Overfitting check: train performance vs forward performance
    3. Contribution: where did LLM add/subtract edge?
    """

    @staticmethod
    def evaluate(report: ForwardTestReport, train_metrics: dict = None) -> dict:
        """
        Args:
            report: ForwardTestReport from forward_tester
            train_metrics: optional baseline metrics from training period (for overfitting check)
        Returns:
            evaluation dict with verdict and breakdown
        """
        baseline = report.baseline
        hybrid = report.hybrid
        policy = report.policy

        # ── Generalization ────────────────────────────────────────────────────
        generalization = {
            "hybrid_vs_baseline_pnl_delta": hybrid.total_pnl - baseline.total_pnl,
            "hybrid_vs_baseline_winrate_delta": hybrid.win_rate - baseline.win_rate,
            "hybrid_vs_baseline_trades_delta": hybrid.trades - baseline.trades,
            "verdict": "GENERALIZES" if hybrid.total_pnl > baseline.total_pnl else "DOES_NOT_GENERALIZE",
        }

        # ── Overfitting check ─────────────────────────────────────────────────
        overfitting = {"verdict": "UNKNOWN"}
        if train_metrics:
            train_winrate = train_metrics.get("win_rate", 0.0)
            fwd_winrate = hybrid.win_rate
            winrate_drop = train_winrate - fwd_winrate
            overfitting = {
                "train_win_rate": train_winrate,
                "forward_win_rate": fwd_winrate,
                "win_rate_drop": winrate_drop,
                "verdict": "OVERFIT" if winrate_drop > 0.10 else "CLEAN",
                "note": "Drop > 10pp = overfitting signal",
            }

        # ── Contribution analysis ─────────────────────────────────────────────
        engine_only_trades = baseline.trades - hybrid.trades
        engine_only_wins = _estimate_wins_in_filtered(baseline, hybrid)
        filter_quality = _filter_quality_score(baseline, hybrid, engine_only_trades, engine_only_wins)

        exploratory_trades = max(0, policy.trades - baseline.trades)

        contribution = {
            "filter_contribution": {
                "trades_removed_by_policy": engine_only_trades,
                "estimated_bad_trades_removed": engine_only_wins,
                "filter_quality_score": filter_quality,
                "verdict": "POSITIVE" if filter_quality > 0.5 else "NEGATIVE",
            },
            "frequency_contribution": {
                "exploratory_trades_added": exploratory_trades,
                "tier1_trades": policy.tier1_trades,
                "tier2_trades": policy.tier2_trades,
                "verdict": "POSITIVE" if exploratory_trades > 0 and policy.total_pnl > 0 else "NEUTRAL",
            },
            "sizing_contribution": {
                "boosted_trades": hybrid.boosted_trades,
                "verdict": "ACTIVE" if hybrid.boosted_trades > 0 else "INACTIVE",
            },
        }

        # ── Overall verdict ───────────────────────────────────────────────────
        keep_policy = (
            generalization["verdict"] == "GENERALIZES"
            and overfitting.get("verdict") != "OVERFIT"
        )

        recommendation = {
            "keep_policy": keep_policy,
            "preferred_mode": _best_mode(baseline, policy, hybrid),
            "next_step": (
                "Deploy hybrid mode to production shadow test"
                if keep_policy else
                "Discard policy — retrain with more data or different features"
            ),
        }

        return {
            "summary": {
                "baseline_pnl": baseline.total_pnl,
                "policy_pnl": policy.total_pnl,
                "hybrid_pnl": hybrid.total_pnl,
                "baseline_trades": baseline.trades,
                "policy_trades": policy.trades,
                "hybrid_trades": hybrid.trades,
            },
            "generalization": generalization,
            "overfitting": overfitting,
            "contribution": contribution,
            "recommendation": recommendation,
        }


def save_evaluation(evaluation: dict, path: str = "results/llm_research/evaluation.json"):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(evaluation, f, indent=2)
    log.info("Evaluation saved: %s", path)
    _print_summary(evaluation)


def _filter_quality_score(baseline: ModeResult, hybrid: ModeResult,
                           removed: int, removed_wins: int) -> float:
    """Score 0–1: 1.0 = only losers removed, 0.0 = only winners removed."""
    if removed == 0:
        return 1.0
    # If hybrid win_rate > baseline win_rate, filter is removing losers
    if hybrid.win_rate >= baseline.win_rate:
        return 1.0
    return max(0.0, hybrid.win_rate / max(baseline.win_rate, 0.01))


def _estimate_wins_in_filtered(baseline: ModeResult, hybrid: ModeResult) -> int:
    """Rough estimate of bad trades removed (losers in filtered-out set)."""
    removed = baseline.trades - hybrid.trades
    if removed <= 0:
        return 0
    # assume filtered trades have baseline win rate (conservative estimate)
    return int(removed * baseline.win_rate)


def _best_mode(baseline: ModeResult, policy: ModeResult, hybrid: ModeResult) -> str:
    best = max(
        [("BASELINE", baseline.total_pnl),
         ("POLICY", policy.total_pnl),
         ("HYBRID", hybrid.total_pnl)],
        key=lambda x: x[1]
    )
    return best[0]


def _print_summary(evaluation: dict):
    s = evaluation.get("summary", {})
    rec = evaluation.get("recommendation", {})
    log.info("=" * 60)
    log.info("FORWARD TEST EVALUATION SUMMARY")
    log.info("  Baseline: trades=%d pnl=%.0f", s.get("baseline_trades", 0), s.get("baseline_pnl", 0))
    log.info("  Policy:   trades=%d pnl=%.0f", s.get("policy_trades", 0), s.get("policy_pnl", 0))
    log.info("  Hybrid:   trades=%d pnl=%.0f", s.get("hybrid_trades", 0), s.get("hybrid_pnl", 0))
    log.info("  Verdict: keep_policy=%s preferred=%s", rec.get("keep_policy"), rec.get("preferred_mode"))
    log.info("  Next: %s", rec.get("next_step"))
    log.info("=" * 60)