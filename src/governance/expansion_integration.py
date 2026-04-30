# expansion_integration.py — Expansion → Governance Bridge
# Connects ExpansionEngine output to ShadowPromotionGate via:
#   train-data expansion → forward-test validation → viability filter → staging
#
# HARD RULES:
# - No LLM in execution path
# - Does NOT modify orchestrator.py / shadow_promotion_gate.py / promotion_manager.py
# - Deterministic at every step
#
import json
import logging
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    from src.expansion.expansion_engine import ExpansionEngine
except ImportError:  # optional-import guard — module may not exist in all envoys
    ExpansionEngine = None  # type: ignore[assignment,misc]

log = logging.getLogger(__name__)

_HISTORY_LOG = Path("logs/expansion_history.jsonl")

# Viability filter thresholds (hard — cannot be overridden by caller)
_MIN_TRADES = 30
_MAX_DRAWDOWN = 0.25

# Hard assertion multipliers applied vs baseline before staging
_MAX_DD_MULTIPLIER = 1.2


class ViabilityFilter:
    """
    Filters forward-tested configs before governance staging.
    All three conditions must pass:
      1. total_pnl > 0
      2. max_drawdown < _MAX_DRAWDOWN (0.25)
      3. trades >= _MIN_TRADES (30)
    """

    @staticmethod
    def passes(metrics: dict) -> tuple:
        trades = metrics.get("trades", 0)
        pnl = metrics.get("total_pnl", 0.0)
        dd = metrics.get("max_drawdown", 0.0)

        if pnl <= 0:
            return False, "pnl_not_positive ({:.0f})".format(pnl)
        if dd >= _MAX_DRAWDOWN:
            return False, "drawdown_too_high ({:.3f} >= {})".format(dd, _MAX_DRAWDOWN)
        if trades < _MIN_TRADES:
            return False, "insufficient_trades ({} < {})".format(trades, _MIN_TRADES)
        return True, ""

    @staticmethod
    def filter_viable(forward_results: list) -> list:
        viable = []
        for r in forward_results:
            ok, reason = ViabilityFilter.passes(r["forward_metrics"])
            if ok:
                viable.append(r)
            else:
                log.info(
                    "ViabilityFilter: rejected tier=%s reason=%s",
                    r.get("name", "?"), reason,
                )
        return viable


class ExpansionGovernanceBridge:
    """
    Connects ExpansionEngine → forward test → viability filter → ShadowPromotionGate.

    Usage:
        bridge = ExpansionGovernanceBridge()
        result = bridge.run(base_config, expansion_plan, train_csv, forward_csv)

    Output:
        {
          "staged": [{"name": str, "patch": dict, "forward_metrics": dict, "gate_result": dict}],
          "rejected": [{"name": str, "reason": str, ...}],
          "expansion_steps": [...],
          "baseline_metrics": dict,
        }
    """

    def __init__(
        self,
        history_log: Optional[str] = None,
        shadow_gate=None,  # injected in tests; lazy-loads ShadowPromotionGate if None
    ):
        self._history_log = Path(history_log) if history_log else _HISTORY_LOG
        self._shadow_gate = shadow_gate

    # ── Public ─────────────────────────────────────────────────────────────────

    def run(
        self,
        base_config: dict,
        expansion_plan,  # ExpansionPlan dataclass
        train_csv: str,
        forward_csv: str,
    ) -> dict:
        """
        Full pipeline:
          1. Run ExpansionEngine on train_csv → SAFE / BALANCED / AGGRESSIVE configs
          2. Forward-test each tier on forward_csv
          3. Apply viability filter
          4. Hard assertions vs baseline before staging
          5. Stage viable candidates via ShadowPromotionGate.promote_if_superior
          6. Append all outcomes to logs/expansion_history.jsonl
        """
        from src.runtime.backtest_v2 import BacktestRunner

        log.info(
            "ExpansionGovernanceBridge: starting run (train=%s forward=%s)",
            train_csv, forward_csv,
        )

        # ── Step 1: Expand on training data ───────────────────────────────────
        engine = ExpansionEngine()
        expansion_result = engine.run(base_config, expansion_plan, [train_csv])

        baseline_metrics = expansion_result.baseline["metrics"]
        baseline_pnl = baseline_metrics.get("total_pnl", 0.0)
        baseline_dd = baseline_metrics.get("max_drawdown", 0.0)

        log.info(
            "Expansion complete: %d tiers, baseline pnl=%.0f dd=%.3f",
            len(expansion_result.configs), baseline_pnl, baseline_dd,
        )

        # ── Step 2: Forward-test each tier ────────────────────────────────────
        forward_results = self._forward_test_configs(
            expansion_result.configs, forward_csv, BacktestRunner
        )

        # ── Step 3: Viability filter ──────────────────────────────────────────
        viable = ViabilityFilter.filter_viable(forward_results)
        rejected = [r for r in forward_results if r not in viable]

        log.info(
            "Viability: %d viable, %d rejected out of %d",
            len(viable), len(rejected), len(forward_results),
        )

        # ── Step 4 + 5: Hard assertions + staging ─────────────────────────────
        staged = []
        for candidate in viable:
            patch = self._diff_from_base(candidate["config"], base_config)
            fwd_m = candidate["forward_metrics"]

            # Hard assertion: forward pnl must exceed baseline pnl
            if fwd_m["total_pnl"] <= baseline_pnl:
                log.warning(
                    "Hard assertion failed for tier=%s: fwd_pnl=%.0f <= baseline=%.0f",
                    candidate["name"], fwd_m["total_pnl"], baseline_pnl,
                )
                candidate["rejected_reason"] = "hard_assert_pnl"
                rejected.append(candidate)
                continue

            # Hard assertion: forward drawdown <= baseline_dd * 1.2
            if baseline_dd > 0 and fwd_m["max_drawdown"] > baseline_dd * _MAX_DD_MULTIPLIER:
                log.warning(
                    "Hard assertion failed for tier=%s: fwd_dd=%.3f > %.3f",
                    candidate["name"], fwd_m["max_drawdown"],
                    baseline_dd * _MAX_DD_MULTIPLIER,
                )
                candidate["rejected_reason"] = "hard_assert_drawdown"
                rejected.append(candidate)
                continue

            # Stage via ShadowPromotionGate
            gate_result = self._stage_candidate(
                patch=patch,
                forward_metrics=fwd_m,
                baseline_pnl=baseline_pnl,
                n_shadow_trades=fwd_m.get("trades", 0),
            )

            entry = {
                "name": candidate["name"],
                "patch": patch,
                "forward_metrics": fwd_m,
                "gate_result": gate_result,
            }
            staged.append(entry)

            # Persist to expansion history
            self._log_history({
                "ts": datetime.now(timezone.utc).isoformat(),
                "base_config_version": base_config.get("version", "unknown"),
                "tier": candidate["name"],
                "patch": patch,
                "train_metrics": candidate.get("train_metrics", {}),
                "forward_metrics": fwd_m,
                "accepted": True,
                "gate_result": gate_result,
            })

        # Persist rejected entries
        for r in rejected:
            self._log_history({
                "ts": datetime.now(timezone.utc).isoformat(),
                "base_config_version": base_config.get("version", "unknown"),
                "tier": r.get("name", "unknown"),
                "patch": self._diff_from_base(r.get("config", {}), base_config),
                "forward_metrics": r.get("forward_metrics", {}),
                "accepted": False,
                "rejected_reason": r.get("rejected_reason", "viability_filter"),
            })

        log.info(
            "ExpansionGovernanceBridge: staged=%d rejected=%d",
            len(staged), len(rejected),
        )

        return {
            "staged": staged,
            "rejected": rejected,
            "expansion_steps": expansion_result.steps,
            "baseline_metrics": baseline_metrics,
        }

    # ── Private ────────────────────────────────────────────────────────────────

    def _forward_test_configs(
        self, configs: list, forward_csv: str, BacktestRunner
    ) -> list:
        """Run BacktestRunner on forward_csv for each tier config."""
        results = []
        for slot in configs:
            name = slot["name"]
            cfg = slot["config"]
            try:
                runner = BacktestRunner(cfg, csv_path=forward_csv)
                m = runner.run(forward_csv)
                fwd_metrics = {
                    "trades": getattr(m, "trades", 0),
                    "wins": getattr(m, "wins", 0),
                    "losses": getattr(m, "losses", 0),
                    "total_pnl": getattr(m, "total_pnl", 0.0),
                    "max_drawdown": getattr(m, "max_drawdown", 0.0),
                }
                if fwd_metrics["trades"] > 0:
                    fwd_metrics["win_rate"] = fwd_metrics["wins"] / fwd_metrics["trades"]
                else:
                    fwd_metrics["win_rate"] = 0.0
                results.append({
                    "name": name,
                    "config": cfg,
                    "train_metrics": slot.get("metrics", {}),
                    "forward_metrics": fwd_metrics,
                })
                log.info(
                    "ForwardTest tier=%s trades=%d pnl=%.0f dd=%.3f",
                    name, fwd_metrics["trades"], fwd_metrics["total_pnl"],
                    fwd_metrics["max_drawdown"],
                )
            except Exception as exc:
                log.warning("ForwardTest failed for tier=%s: %s", name, exc)
                results.append({
                    "name": name,
                    "config": cfg,
                    "train_metrics": slot.get("metrics", {}),
                    "forward_metrics": {
                        "trades": 0, "total_pnl": 0.0, "max_drawdown": 1.0,
                        "wins": 0, "losses": 0, "win_rate": 0.0,
                    },
                    "rejected_reason": "backtest_exception: {}".format(exc),
                })
        return results

    def _diff_from_base(self, new_config: dict, base_config: dict) -> dict:
        """Generate minimal diff: {param: {old: v, new: v}} for changed keys only."""
        diff = {}
        all_keys = set(new_config.keys()) | set(base_config.keys())
        for k in all_keys:
            old_val = base_config.get(k)
            new_val = new_config.get(k)
            if old_val != new_val:
                diff[k] = {"old": old_val, "new": new_val}
        return diff

    def _stage_candidate(
        self,
        patch: dict,
        forward_metrics: dict,
        baseline_pnl: float,
        n_shadow_trades: int,
    ) -> dict:
        """Stage candidate via ShadowPromotionGate.promote_if_superior."""
        gate = self._get_shadow_gate()
        try:
            result = gate.promote_if_superior(
                baseline_pnl=baseline_pnl,
                shadow_pnl=forward_metrics.get("total_pnl", 0.0),
                n_shadow_trades=n_shadow_trades,
            )
            log.info(
                "ShadowGate: promoted=%s reason=%s",
                result.get("promoted"), result.get("reason"),
            )
            return result
        except Exception as exc:
            log.warning("ShadowGate staging failed: %s", exc)
            return {"promoted": False, "reason": "gate_error: {}".format(exc)}

    def _get_shadow_gate(self):
        """Lazy-load ShadowPromotionGate (avoids import cycle in tests)."""
        if self._shadow_gate is not None:
            return self._shadow_gate
        from src.governance.shadow_promotion_gate import ShadowPromotionGate
        return ShadowPromotionGate()

    def _log_history(self, entry: dict) -> None:
        """Append one entry to logs/expansion_history.jsonl."""
        self._history_log.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self._history_log, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as exc:
            log.warning("History log write failed: %s", exc)