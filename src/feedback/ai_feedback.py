# ai_feedback.py — Offline LLM feedback on trade journal analytics
#
# HARD RULES:
# - LLM suggestions ONLY — never auto-apply
# - Minimum 30 trades before feedback runs
# - Suggestions feed ExpansionEngine as starting point
# - Human approval required before any param change
#
import json
import logging
from typing import Optional

log = logging.getLogger(__name__)

_MIN_TRADES = 30

_PROMPT_TEMPLATE = """You are a trading system analyst. Review the following performance analytics and suggest parameter improvements.

Performance Summary:
{summary}

Loss Clusters:
{clusters}

Output JSON only (no prose):
{{
  "insights": ["insight 1", "insight 2"],
  "suggestions": [
    {{"param": "param_name", "change": "+0.05", "reason": "reason"}}
  ]
}}
"""


class AIFeedback:
    """
    Generates offline LLM suggestions based on trade analytics.

    NOT used in live execution. Runs offline after sufficient trades accumulate.

    Usage:
        feedback = AIFeedback(llm_fn=my_llm_call)
        result = feedback.generate(analytics_summary, loss_clusters, trade_count)
        # → {"insights": [...], "suggestions": [...]}
    """

    def __init__(self, llm_fn=None, min_trades: int = _MIN_TRADES):
        """
        Args:
            llm_fn: callable(prompt: str) → str (JSON response)
                    If None, returns empty suggestions (no LLM available).
            min_trades: minimum trade count before feedback is generated.
        """
        self._llm_fn = llm_fn
        self.min_trades = min_trades

    def generate(
        self,
        analytics_summary: dict,
        loss_clusters: dict,
        trade_count: int,
    ) -> dict:
        """
        Generate feedback suggestions from analytics.

        Args:
            analytics_summary: dict from PerformanceAnalyzer.compute()
            loss_clusters: dict from TradeClustering.cluster_losses()
            trade_count: total number of trades

        Returns:
            {"insights": [...], "suggestions": [...], "skipped": bool}
        """
        if trade_count < self.min_trades:
            log.info(
                "AIFeedback: skipping — insufficient trades (%d < %d)",
                trade_count, self.min_trades,
            )
            return {"insights": [], "suggestions": [], "skipped": True, "reason": "insufficient_trades"}

        if self._llm_fn is None:
            log.info("AIFeedback: no LLM available — returning rule-based suggestions")
            return self._rule_based_feedback(analytics_summary, loss_clusters)

        prompt = _PROMPT_TEMPLATE.format(
            summary=json.dumps(analytics_summary, indent=2),
            clusters=json.dumps({k: len(v) for k, v in loss_clusters.items()}, indent=2),
        )

        try:
            raw = self._llm_fn(prompt)
            result = json.loads(raw)
            log.info(
                "AIFeedback: generated %d insights, %d suggestions",
                len(result.get("insights", [])), len(result.get("suggestions", [])),
            )
            result["skipped"] = False
            return result
        except Exception as exc:
            log.warning("AIFeedback: LLM call failed (%s) — falling back to rule-based", exc)
            return self._rule_based_feedback(analytics_summary, loss_clusters)

    def _rule_based_feedback(self, summary: dict, clusters: dict) -> dict:
        """Deterministic rule-based fallback when LLM unavailable."""
        insights = []
        suggestions = []

        win_rate = summary.get("win_rate", 0.0)
        expectancy = summary.get("expectancy", 0.0)

        if win_rate < 0.40:
            insights.append("Win rate below 40% — consider tightening entry filters")
            suggestions.append({"param": "fusion_min_score", "change": "+0.05", "reason": "low win rate"})

        if expectancy < 0:
            insights.append("Negative expectancy — review RR ratio targets")
            suggestions.append({"param": "min_rr_ratio", "change": "+0.2", "reason": "negative expectancy"})

        if "low_zone" in clusters:
            insights.append("Losses concentrated in low zone quality trades")
            suggestions.append({"param": "zone_gate_threshold", "change": "+0.05", "reason": "high loss rate in low zone"})

        if "low_rr" in clusters:
            insights.append("Low RR trades underperform — raise minimum RR")
            suggestions.append({"param": "min_rr_ratio", "change": "+0.2", "reason": "high loss rate in low RR trades"})

        return {"insights": insights, "suggestions": suggestions, "skipped": False}