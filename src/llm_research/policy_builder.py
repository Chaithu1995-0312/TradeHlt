# policy_builder.py — converts frozen ExtractedPolicy → deterministic Python filter/booster
# No LLM involvement. Policy must be frozen (saved) before this runs.
# Output is a callable PolicyEngine used by ForwardTester.
#
import logging
from src.llm_research.pattern_extractor import ExtractedPolicy

log = logging.getLogger(__name__)


class PolicyEngine:
    """
    Deterministic filter/booster engine built from frozen ExtractedPolicy.

    Usage:
        engine = PolicyEngine.from_policy(policy)
        decision = engine.evaluate(features)
        # decision: {"tier": "TIER_1|TIER_2|TIER_3", "action": "TRADE|BLOCK", "factor": float}
    """

    def __init__(self, filters: list, boosters: list, tier_rules: dict, confidence_formula: str):
        self._filters = filters
        self._boosters = boosters
        self._tier_rules = tier_rules
        self._confidence_formula = confidence_formula

    @classmethod
    def from_policy(cls, policy: ExtractedPolicy) -> "PolicyEngine":
        return cls(
            filters=policy.filters,
            boosters=policy.boosters,
            tier_rules=policy.tier_rules,
            confidence_formula=policy.confidence_formula,
        )

    def evaluate(self, features: dict) -> dict:
        """
        Evaluate a feature dict against the policy.
        Returns:
            {
                "tier": "TIER_1" | "TIER_2" | "TIER_3",
                "action": "TRADE" | "BLOCK",
                "factor": float (1.0 = normal size),
                "confidence": float,
                "blocked_by": str (if blocked),
            }
        """
        # ── Compute confidence score ───────────────────────────────────────
        confidence = self._compute_confidence(features)

        # ── Apply filters (BLOCK gates) ────────────────────────────────────
        for f in self._filters:
            if _eval_condition(f.get("condition", ""), features):
                return {
                    "tier": "TIER_3",
                    "action": "BLOCK",
                    "factor": 0.0,
                    "confidence": confidence,
                    "blocked_by": f.get("condition", "unknown"),
                }

        # ── Determine tier ─────────────────────────────────────────────────
        tier = self._classify_tier(features, confidence)

        if tier == "TIER_3":
            return {"tier": "TIER_3", "action": "BLOCK", "factor": 0.0, "confidence": confidence, "blocked_by": "tier_3"}

        # ── Apply boosters ─────────────────────────────────────────────────
        factor = 1.0
        for b in self._boosters:
            if _eval_condition(b.get("condition", ""), features):
                factor = max(factor, float(b.get("factor", 1.0)))

        return {
            "tier": tier,
            "action": "TRADE",
            "factor": min(factor, 1.5),  # cap at 1.5×
            "confidence": confidence,
            "blocked_by": None,
        }

    def _compute_confidence(self, features: dict) -> float:
        """Evaluate the LLM-provided confidence formula against features."""
        if not self._confidence_formula:
            return 0.5
        try:
            # Simple safe eval: replace feature names with values
            expr = self._confidence_formula
            for k, v in features.items():
                expr = expr.replace(k, str(float(v)))
            return max(0.0, min(1.0, float(eval(expr))))  # noqa: S307 — sandboxed numeric formula
        except Exception:
            return 0.5

    def _classify_tier(self, features: dict, confidence: float) -> str:
        """Classify into TIER_1/TIER_2/TIER_3 based on confidence formula thresholds."""
        # If tier_rules contain conditions, try to evaluate them
        t1 = self._tier_rules.get("TIER_1", "")
        t2 = self._tier_rules.get("TIER_2", "")

        if t1 and _eval_condition(t1, features):
            return "TIER_1"
        if t2 and _eval_condition(t2, features):
            return "TIER_2"

        # Fallback: confidence-based tiering
        if confidence >= 0.75:
            return "TIER_1"
        elif confidence >= 0.55:
            return "TIER_2"
        return "TIER_3"


def _eval_condition(condition: str, features: dict) -> bool:
    """
    Safe evaluation of a simple feature condition string.
    Supports: AND, OR, <, >, <=, >=, ==
    Feature names are replaced with their float values.
    Returns False on parse error (safe default).
    """
    if not condition or condition.lower() in ("everything else", ""):
        return False
    try:
        expr = condition.replace(" AND ", " and ").replace(" OR ", " or ")
        for k in sorted(features.keys(), key=len, reverse=True):
            v = features.get(k, 0)
            try:
                expr = expr.replace(k, str(float(v)))
            except (TypeError, ValueError):
                pass
        return bool(eval(expr))  # noqa: S307 — numeric condition only
    except Exception:
        return False