"""
goal_schema.py
================================================================================
Layer 0 — the GOAL (economic-objective) schema.

The `goal` config section is the single, machine-readable statement of what the
system is *trying to achieve in business terms* (trades/month, RR, drawdown,
expectancy). It is the economic-objective dimension that sits ALONGSIDE — never
above — the `goal.md` invariant ordering (replay correctness > explainability >
telemetry continuity > advisory-AI). See docs/architecture/goal.md.

Authority model (decided with the owner):
  • Telemetry NOW — `GoalValidator` (goal_validator.py) compares each backtest's
    metrics against this spec and emits an additive, measure-only `goal_report`.
  • A dormant `enforce` flag (default False) lets the goal later become a HARD
    promotion gate, without changing any behaviour until it is flipped on.

Fail-soft contract (F-018): the active `patch` config can lag HEAD code, so a
*missing* `goal` section MUST NOT break loading — `load_goal_spec()` returns a
DISABLED spec (advisory off) when the section is absent. A section that is
*present but malformed* fails-fast via `_require` (a real misconfiguration).

This file follows the golden template in docs/reference/example-service.py:
`_require` strict accessor, `from_prod_config` factory, named flow logger,
zero magic numbers (every target flows from the production JSON).
================================================================================
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Tuple

# -- Path setup --------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

logger = logging.getLogger("CRT.Goal")


def _require(cfg: dict, key: str) -> object:
    """Strict accessor — raises if `key` is missing from a PRESENT goal section.

    Mirrors `_validator_require` in config_validator.py. Only called once the
    section is known to exist, so a KeyError here means a real misconfiguration
    (not the lagging-config fail-soft path, which is handled in `load_goal_spec`).
    """
    if key not in cfg:
        raise KeyError(
            f"Required config key '{key}' missing from the 'goal' section. "
            f"Add it to the active production config JSON."
        )
    return cfg[key]


def _bound(cfg: dict, key: str, sub: str) -> Optional[float]:
    """Read a nested range bound, e.g. goal['avg_rr']['min'].

    Returns None when the whole range key is absent (a partially-specified goal is
    allowed) OR when this particular sub-bound is not declared (e.g. an optional
    'target' on a min/max range). Fails-fast only when the range key is present but
    MALFORMED — not a dict, or an empty dict declaring no bounds at all."""
    if key not in cfg:
        return None
    block = cfg[key]
    if not isinstance(block, dict) or not block:
        raise KeyError(
            f"goal['{key}'] is present but malformed (expected a non-empty object "
            f"of bounds, e.g. \"{key}\": {{\"{sub}\": <number>}})."
        )
    return float(block[sub]) if sub in block else None


@dataclass(frozen=True)
class GoalSpec:
    """The frozen economic objective. `enabled=False` ⇒ advisory no-op (no goal
    section configured). All numeric targets are Optional: a partially-specified
    goal only constrains the bounds it actually declares."""

    enabled:               bool                 = False
    goal_id:               str                  = "UNSET"
    enforce:               bool                 = False
    trades_per_month_min:  Optional[float]      = None
    trades_per_month_max:  Optional[float]      = None
    trades_per_month_target: Optional[float]    = None
    avg_rr_min:            Optional[float]      = None
    win_rate_min:          Optional[float]      = None
    max_drawdown_pct_max:  Optional[float]      = None
    risk_per_trade_target: Optional[float]      = None
    expectancy_r_min:      Optional[float]      = None
    timeframe_execution:   Optional[str]        = None
    timeframe_structure:   Optional[str]        = None
    instruments:           Tuple[str, ...]      = field(default_factory=tuple)
    reaction_only:         Optional[bool]       = None
    human_execution:       Optional[bool]       = None
    no_prediction:         Optional[bool]       = None

    @classmethod
    def disabled(cls) -> "GoalSpec":
        """Advisory-off spec used when no `goal` section is configured (F-018)."""
        return cls(enabled=False, goal_id="UNSET", enforce=False)

    @classmethod
    def from_prod_config(cls, cfg: dict) -> "GoalSpec":
        """Build a GoalSpec from a PRESENT `goal` section dict. Fails-fast (via
        `_require`) on a malformed section. `goal_id` + `enforce` are mandatory;
        every target is optional (declare only the bounds you want to track)."""
        tf = cfg.get("timeframe", {}) or {}
        cons = cfg.get("constraints", {}) or {}
        instruments = tuple(str(s) for s in (cfg.get("instruments") or []))
        return cls(
            enabled               = True,
            goal_id               = str(_require(cfg, "goal_id")),
            enforce               = bool(_require(cfg, "enforce")),
            trades_per_month_min    = _bound(cfg, "trades_per_month", "min"),
            trades_per_month_max    = _bound(cfg, "trades_per_month", "max"),
            trades_per_month_target = _bound(cfg, "trades_per_month", "target"),
            avg_rr_min            = _bound(cfg, "avg_rr", "min"),
            win_rate_min          = _bound(cfg, "win_rate", "min"),
            max_drawdown_pct_max  = _bound(cfg, "max_drawdown_pct", "max"),
            risk_per_trade_target = _bound(cfg, "risk_per_trade", "target"),
            expectancy_r_min      = _bound(cfg, "expectancy_r", "min"),
            timeframe_execution   = tf.get("execution"),
            timeframe_structure   = tf.get("structure"),
            instruments           = instruments,
            reaction_only         = cons.get("reaction_only"),
            human_execution       = cons.get("human_execution"),
            no_prediction         = cons.get("no_prediction"),
        )


def load_goal_spec(version: Optional[str] = None) -> GoalSpec:
    """Load the active `goal` spec. FAIL-SOFT: a missing section returns a
    disabled spec (advisory off) so lagging configs keep loading (F-018). A
    present-but-malformed section still fails-fast inside `from_prod_config`."""
    try:
        from config_layer.production_config import get_prod_section
        section = get_prod_section("goal", version=version)
    except RuntimeError:
        # Section (or registry) absent — advisory off, never block.
        logger.info("No 'goal' section in active config — Goal Layer advisory disabled.")
        return GoalSpec.disabled()
    except ImportError as exc:
        logger.warning("Could not import production_config for goal load: %s", exc)
        return GoalSpec.disabled()
    if not section:
        return GoalSpec.disabled()
    return GoalSpec.from_prod_config(section)
