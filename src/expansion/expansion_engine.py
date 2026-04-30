# expansion_engine.py — deterministic stepwise expansion loop
# LLM has ZERO role here. LLM only suggests directions (in llm_pattern_extractor.py).
# All decisions are made by Evaluator against hard guardrails.
#
import json
import logging
from copy import deepcopy
from pathlib import Path
from datetime import datetime, timezone

from src.expansion.policy_schema import (
    ExpansionPlan, ExpansionStep, ExpansionResult,
    MAX_STEPS_PER_PARAM,
)
from src.expansion.config_mutator import ConfigMutator
from src.expansion.evaluator import Evaluator

log = logging.getLogger(__name__)

_TRACE_LOG = Path("logs/expansion_trace.jsonl")
_REJECTION_LOG = Path("logs/expansion_rejected.jsonl")


class ExpansionEngine:
    """
    Controlled edge expansion: systematically relaxes ONE parameter per step,
    runs backtest, evaluates, and stops when guardrails are breached or
    target trade count is reached.

    Output:
    - Best config by score
    - Ranked config variants: SAFE / BALANCED / AGGRESSIVE
    - Full trace log (expansion_trace.jsonl)
    - Rejection log (expansion_rejected.jsonl)
    """

    def __init__(self, config: dict = None, target_multiplier: float = 2.0):
        self.config = config or {}
        self.target_multiplier = target_multiplier

    def run(
        self,
        base_config: dict,
        expansion_plan: ExpansionPlan,
        csv_paths: list[str],
    ) -> ExpansionResult:
        """
        Args:
            base_config: production config dict (not mutated)
            expansion_plan: LLM-suggested or fallback expansion plan
            csv_paths: list of instrument CSV paths for backtest
        Returns:
            ExpansionResult with ranked configs and full trace
        """
        from src.runtime.backtest_v2 import BacktestRunner

        # ── Baseline ──────────────────────────────────────────────────────────
        baseline_metrics = self._run_backtest(BacktestRunner, base_config, csv_paths)
        baseline_score = Evaluator.score(baseline_metrics, baseline_metrics)
        target_trades = int(baseline_metrics.get("trades", 0) * self.target_multiplier)

        log.info(
            "ExpansionEngine: baseline trades=%d pnl=%.0f drawdown=%.3f target_trades=%d",
            baseline_metrics.get("trades", 0), baseline_metrics.get("total_pnl", 0),
            baseline_metrics.get("max_drawdown", 0), target_trades,
        )

        accepted: list[tuple[dict, dict, float, str]] = []  # (config, metrics, score, tier)
        all_steps: list[ExpansionStep] = []
        current_config = deepcopy(base_config)
        step_counter = 0

        # ── Stepwise expansion ────────────────────────────────────────────────
        for candidate in sorted(expansion_plan.candidates, key=lambda c: c.priority):
            baseline_value = ConfigMutator.get_value(base_config, candidate.param)

            for _ in range(MAX_STEPS_PER_PARAM):
                step_counter += 1
                old_val = ConfigMutator.get_value(current_config, candidate.param)

                try:
                    new_config = ConfigMutator.mutate(
                        current_config,
                        candidate.param,
                        candidate.direction,
                        candidate.step,
                        baseline_value=baseline_value,
                    )
                except ValueError as e:
                    log.warning("ConfigMutator: %s — skipping", e)
                    break

                new_val = ConfigMutator.get_value(new_config, candidate.param)
                if abs(new_val - old_val) < 1e-6:
                    log.info("Param %s hit bound — stopping this candidate", candidate.param)
                    break

                metrics = self._run_backtest(BacktestRunner, new_config, csv_paths)
                score = Evaluator.score(metrics, baseline_metrics)
                passes, reason = Evaluator.passes_guardrails(metrics, baseline_metrics)

                if not passes:
                    step = ExpansionStep(
                        step=step_counter,
                        param=candidate.param,
                        old_value=old_val,
                        new_value=new_val,
                        trades=metrics.get("trades", 0),
                        pnl=metrics.get("total_pnl", 0.0),
                        drawdown=metrics.get("max_drawdown", 0.0),
                        score=score,
                        status=f"rejected_{reason.split('(')[0].rstrip()}",
                        reason=reason,
                    )
                    all_steps.append(step)
                    self._log_rejection(step, new_config, metrics)
                    log.info("Step %d REJECTED: %s", step_counter, reason)
                    break  # stop expanding this param

                tier = Evaluator.classify_config(
                    score, baseline_score,
                    metrics.get("trades", 0), baseline_metrics.get("trades", 0)
                )

                step = ExpansionStep(
                    step=step_counter,
                    param=candidate.param,
                    old_value=old_val,
                    new_value=new_val,
                    trades=metrics.get("trades", 0),
                    pnl=metrics.get("total_pnl", 0.0),
                    drawdown=metrics.get("max_drawdown", 0.0),
                    score=score,
                    status="accepted",
                    reason=tier,
                )
                all_steps.append(step)
                self._log_trace(step)
                accepted.append((new_config, metrics, score, tier))
                current_config = new_config

                log.info(
                    "Step %d ACCEPTED: param=%s %.4f→%.4f trades=%d pnl=%.0f score=%.2f [%s]",
                    step_counter, candidate.param, old_val, new_val,
                    metrics.get("trades", 0), metrics.get("total_pnl", 0), score, tier
                )

                if metrics.get("trades", 0) >= target_trades:
                    log.info("Target trades=%d reached — stopping expansion", target_trades)
                    step.status = "target_reached"
                    break

        # ── Build output ──────────────────────────────────────────────────────
        ranked_configs = self._build_ranked_configs(
            base_config, baseline_metrics, accepted
        )

        best_config = base_config
        best_metrics = baseline_metrics
        if accepted:
            best = max(accepted, key=lambda x: x[2])
            best_config, best_metrics = best[0], best[1]

        return ExpansionResult(
            baseline={"config": base_config, "metrics": baseline_metrics},
            configs=ranked_configs,
            steps=all_steps,
            best_config=best_config,
            best_metrics=best_metrics,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _run_backtest(self, BacktestRunner, config: dict, csv_paths: list[str]) -> dict:
        """Run BacktestRunner across all csv_paths; aggregate metrics."""
        total = {"trades": 0, "wins": 0, "losses": 0, "total_pnl": 0.0, "max_drawdown": 0.0}
        runner = BacktestRunner(config)
        for csv_path in csv_paths:
            try:
                m = runner.run(csv_path)
                total["trades"] += m.trades
                total["wins"] += m.wins
                total["losses"] += m.losses
                total["total_pnl"] += m.total_pnl
                total["max_drawdown"] = max(total["max_drawdown"], m.max_drawdown)
            except Exception as exc:
                log.warning("Backtest failed for %s: %s", csv_path, exc)
        if total["trades"] > 0:
            total["win_rate"] = total["wins"] / total["trades"]
            total["expectancy"] = total["total_pnl"] / total["trades"]
            total["fitness"] = total["win_rate"] * total["expectancy"]
        return total

    def _build_ranked_configs(
        self,
        base_config: dict,
        baseline_metrics: dict,
        accepted: list,
    ) -> list[dict]:
        """Build SAFE / BALANCED / AGGRESSIVE config slots."""
        tiers = {"SAFE": None, "BALANCED": None, "AGGRESSIVE": None}

        # Always include baseline as SAFE fallback
        tiers["SAFE"] = {
            "name": "SAFE",
            "config": base_config,
            "metrics": baseline_metrics,
            "trades": baseline_metrics.get("trades", 0),
            "pnl": baseline_metrics.get("total_pnl", 0.0),
        }

        for cfg, metrics, score, tier in accepted:
            slot = {
                "name": tier,
                "config": cfg,
                "metrics": metrics,
                "trades": metrics.get("trades", 0),
                "pnl": metrics.get("total_pnl", 0.0),
            }
            # Keep best score per tier
            if tiers[tier] is None or score > tiers[tier].get("_score", -999):
                slot["_score"] = score
                tiers[tier] = slot

        return [v for v in tiers.values() if v is not None]

    def _log_trace(self, step: ExpansionStep):
        _TRACE_LOG.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            **step.__dict__,
        }
        try:
            with open(_TRACE_LOG, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as exc:
            log.warning("Trace log write failed: %s", exc)

    def _log_rejection(self, step: ExpansionStep, config: dict, metrics: dict):
        _REJECTION_LOG.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "step": step.step,
            "param": step.param,
            "reason": step.reason,
            "config": {k: v for k, v in config.items() if isinstance(v, (int, float, str, bool))},
            "metrics": metrics,
        }
        try:
            with open(_REJECTION_LOG, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as exc:
            log.warning("Rejection log write failed: %s", exc)


def save_expansion_configs(result: ExpansionResult, output_dir: str = "results/expansion"):
    """
    Persist ranked configs to disk with version suffix.
    E.g.: results/expansion/v1_multi_2026_03_BALANCED.json
    """
    import os
    os.makedirs(output_dir, exist_ok=True)

    base_version = result.baseline["config"].get("version", "unknown")
    saved = []

    for slot in result.configs:
        name = slot["name"]
        cfg = deepcopy(slot["config"])
        cfg["version"] = f"{base_version}_{name.lower()}"
        cfg["_expansion_metrics"] = slot["metrics"]

        path = Path(output_dir) / f"{cfg['version']}.json"
        with open(path, "w") as f:
            json.dump(cfg, f, indent=2)
        saved.append(str(path))
        log.info("Saved %s config: %s (trades=%d pnl=%.0f)",
                 name, path, slot["trades"], slot["pnl"])

    return saved