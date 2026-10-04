"""Trading layer (Semantic OS v2 slice 2): thesis, roles, plan, cost, outcome.

Roles name a market level. They do not change it (I-10). Fills, position lifecycle,
sizing, approval, and the exit schedule are slice 3 and are not built here.
"""

from semantics.trading.cost import COST, Cost, component_cost, flat_cost
from semantics.trading.entry import ENTRY, Entry, legacy_entry, resting_entry
from semantics.trading.outcome import OUTCOME, Outcome, measure_outcome
from semantics.trading.plan import TradePlan, trade_plan
from semantics.trading.roles import INVALIDATION, OBJECTIVE, Invalidation, Objective, make_invalidation, objective_role
from semantics.trading.stop import STOP, Stop, place_stop
from semantics.trading.target import TARGET, Target, derive_intent, fixed_r_target, intent_r_multiple, structural_tp2_target
from semantics.trading.thesis import THESIS, Thesis, form_thesis, mark_expired, mark_failed, mark_spent

__all__ = [
    "COST", "Cost", "component_cost", "flat_cost",
    "ENTRY", "Entry", "legacy_entry", "resting_entry",
    "OUTCOME", "Outcome", "measure_outcome",
    "TradePlan", "trade_plan",
    "INVALIDATION", "OBJECTIVE", "Invalidation", "Objective", "make_invalidation", "objective_role",
    "STOP", "Stop", "place_stop",
    "TARGET", "Target", "derive_intent", "fixed_r_target", "intent_r_multiple", "structural_tp2_target",
    "THESIS", "Thesis", "form_thesis", "mark_expired", "mark_failed", "mark_spent",
]
