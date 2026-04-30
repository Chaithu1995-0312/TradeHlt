# policy_schema.py — dataclasses for expansion plan and results
#
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ExpansionCandidate:
    """A single parameter expansion suggestion from LLM or fallback."""
    param: str                  # e.g. "fusion_min_score"
    direction: str              # "increase" | "decrease"
    step: float                 # per-iteration delta e.g. 0.05
    priority: int               # lower = try first
    floor: float = 0.0          # hard lower bound (safety)
    ceiling: float = 1.0        # hard upper bound (safety)


@dataclass
class ExpansionPlan:
    """Full expansion plan: base metrics + ordered candidates."""
    base_metrics: dict          # {"trades": 42, "pnl": 25000, "drawdown": 0.18}
    candidates: list[ExpansionCandidate] = field(default_factory=list)
    target_multiplier: float = 2.0   # desired trade count multiplier


@dataclass
class ExpansionStep:
    """
    One step in the expansion loop — persisted to expansion_trace.jsonl.
    This is the rejection log + trace log combined.
    """
    step: int
    param: str
    old_value: float
    new_value: float
    trades: int
    pnl: float
    drawdown: float
    score: float
    status: str                 # "accepted" | "rejected_pnl" | "rejected_drawdown" | "target_reached"
    reason: str = ""


@dataclass
class ExpansionResult:
    """Final output of ExpansionEngine.run()."""
    baseline: dict              # original config + metrics
    configs: list[dict]         # ranked configs: SAFE, BALANCED, AGGRESSIVE
    steps: list[ExpansionStep]  # full trace (accepted + rejected)
    best_config: dict           # the single best config by score
    best_metrics: dict


# ── Expandable parameter bounds (safety) ─────────────────────────────────────
# LLM suggestions are clipped to these ranges.
PARAM_BOUNDS: dict[str, tuple[float, float]] = {
    "fusion_min_score":    (0.40, 0.85),
    "zone_gate_threshold": (0.40, 0.80),
    "body_ratio_min":      (0.45, 0.85),
    "min_rr_ratio":        (1.50, 3.00),
    "fusion_weight_crt":       (0.20, 0.60),
    "fusion_weight_gaussian":  (0.15, 0.50),
    "fusion_weight_zone":      (0.10, 0.40),
    "fusion_weight_rr":        (0.05, 0.25),
    "bitnet_threshold":        (0.30, 0.70),
}

# Hard guardrails applied in ExpansionEngine (cannot be overridden)
MAX_PARAM_CHANGE = 0.15     # total drift allowed per param from baseline
MAX_STEPS_PER_PARAM = 3     # max iterations per candidate
MIN_PNL_RATIO = 0.90        # pnl must stay >= 90% of baseline
MAX_DRAWDOWN_RATIO = 1.50   # drawdown must stay <= 150% of baseline


@dataclass(frozen=True)
class RegimeWeightCandidate:
    regime: str                    # RANGING | TRENDING | HIGH_VOLATILITY
    fusion_weights: dict           # {"crt": float, "gaussian": float, "zone": float, "rr": float}
    bitnet_threshold: float        # 0.30 - 0.70
    rationale: str                 # LLM explanation, stored for audit
    source: str                    # "llm_suggested" | "deterministic_fallback"


@dataclass(frozen=True)
class RegimeSearchResult:
    regime: str
    best_candidate: RegimeWeightCandidate
    baseline_score: float
    best_score: float
    improvement_pct: float
    candidates_tested: int
    candidates_accepted: int
    insights: str                  # LLM pattern analysis
    timestamp: str
