"""
goal_validator.py
================================================================================
Layer 0 — the GOAL validator. Compares measured metrics against the frozen
`GoalSpec` (goal_schema.py) and returns a structured `GoalReport`.

Two consumers, one validator:
  1. Backtest telemetry (measure-only) — backtest_v2.py attaches the report to
     `BacktestMetrics.distribution["goal_report"]`, the same additive pattern as
     the ROI block / feature_drift. NEVER gates anything.
  2. Promotion enforcement (dormant) — when `GoalSpec.enforce` is True, the
     promotion authority folds FAIL criteria into its hard-failures. Default
     enforce=False ⇒ zero behaviour change.

Determinism: `evaluate()` is a PURE function of the metrics it is handed (no I/O,
no clock, no RNG), so it cannot perturb replay / golden determinism. The report
is a stable, sorted structure.

Skip semantics: a criterion whose actual value is NOT supplied is reported with
`status="SKIP"` and does NOT count toward FAIL. This lets the same validator
serve a full backtest metrics set and the narrower per-instrument set that
config_validator has, without inventing missing numbers.
================================================================================
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

# -- Path setup --------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config_layer.goal_schema import GoalSpec, load_goal_spec   # type: ignore

logger = logging.getLogger("CRT.Goal")

# Metric keys the validator understands. The caller supplies whatever it has.
_METRIC_TRADES_PER_MONTH = "trades_per_month"
_METRIC_AVG_RR           = "avg_rr"
_METRIC_WIN_RATE         = "win_rate"
_METRIC_MAX_DD_PCT       = "max_drawdown_pct"
_METRIC_EXPECTANCY_R     = "expectancy_r"


@dataclass(frozen=True)
class GoalReport:
    """Structured comparison of measured metrics vs the GoalSpec.

    decision: "PASS" | "FAIL"  (a disabled or fully-skipped spec ⇒ "PASS")
    enabled:  whether a goal was actually configured
    enforced: whether the goal would hard-block promotion (GoalSpec.enforce)
    criteria: one row per evaluated bound; status ∈ {PASS, FAIL, SKIP}
    """

    enabled:  bool             = False
    enforced: bool             = False
    goal_id:  str              = "UNSET"
    decision: str              = "PASS"
    criteria: List[dict]       = field(default_factory=list)

    @property
    def failed_criteria(self) -> List[str]:
        return [c["name"] for c in self.criteria if c["status"] == "FAIL"]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled":  self.enabled,
            "enforced": self.enforced,
            "goal_id":  self.goal_id,
            "decision": self.decision,
            "criteria": list(self.criteria),
        }


def _row(name: str, comparator: str, target: Optional[float],
         actual: Optional[float]) -> Optional[dict]:
    """Build one criterion row. Returns None when the goal does not declare this
    bound (so it is not even reported). SKIP when the bound is declared but the
    metric was not supplied. comparator ∈ {">=", "<="}."""
    if target is None:
        return None
    if actual is None:
        return {"name": name, "comparator": comparator, "target": target,
                "actual": None, "gap": None, "status": "SKIP"}
    if comparator == ">=":
        passed = actual >= target
        gap = round(actual - target, 6)     # positive ⇒ satisfied with margin
    else:  # "<="
        passed = actual <= target
        gap = round(target - actual, 6)     # positive ⇒ satisfied with margin
    return {"name": name, "comparator": comparator, "target": target,
            "actual": round(actual, 6), "gap": gap,
            "status": "PASS" if passed else "FAIL"}


class GoalValidator:
    """Stateless goal-vs-metrics comparator. All methods static."""

    @staticmethod
    def evaluate(metrics: Mapping[str, float],
                 spec: Optional[GoalSpec] = None) -> GoalReport:
        """Compare `metrics` against `spec` (defaults to the active goal). Pure;
        no I/O beyond the optional one-time spec load.

        `metrics` keys understood: trades_per_month, avg_rr, win_rate,
        max_drawdown_pct, expectancy_r. Missing keys ⇒ SKIP (not FAIL).
        """
        if spec is None:
            spec = load_goal_spec()

        if not spec.enabled:
            return GoalReport(enabled=False, enforced=False, goal_id=spec.goal_id,
                              decision="PASS", criteria=[])

        def g(key: str) -> Optional[float]:
            v = metrics.get(key)
            return None if v is None else float(v)

        rows: List[Optional[dict]] = [
            _row("trades_per_month_min", ">=", spec.trades_per_month_min, g(_METRIC_TRADES_PER_MONTH)),
            _row("trades_per_month_max", "<=", spec.trades_per_month_max, g(_METRIC_TRADES_PER_MONTH)),
            _row("avg_rr_min",           ">=", spec.avg_rr_min,           g(_METRIC_AVG_RR)),
            _row("win_rate_min",         ">=", spec.win_rate_min,         g(_METRIC_WIN_RATE)),
            _row("max_drawdown_pct_max", "<=", spec.max_drawdown_pct_max, g(_METRIC_MAX_DD_PCT)),
            _row("expectancy_r_min",     ">=", spec.expectancy_r_min,     g(_METRIC_EXPECTANCY_R)),
        ]
        criteria = [r for r in rows if r is not None]
        decision = "FAIL" if any(c["status"] == "FAIL" for c in criteria) else "PASS"
        return GoalReport(
            enabled=True, enforced=bool(spec.enforce), goal_id=spec.goal_id,
            decision=decision, criteria=criteria,
        )
