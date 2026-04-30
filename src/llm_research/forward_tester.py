# forward_tester.py — 3-mode forward test on unseen data
# Modes: BASELINE (engine only) | POLICY (LLM rules) | HYBRID (engine AND policy)
# LLM is NOT used here. PolicyEngine is deterministic (frozen policy).
#
import csv
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

TRAIN_SPLIT = 0.70      # 70% training, 30% forward test (default auto-split)


@dataclass
class ModeResult:
    mode: str
    trades: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0
    max_drawdown: float = 0.0
    filtered_by_policy: int = 0    # trades blocked by policy
    boosted_trades: int = 0        # trades with factor > 1.0
    tier1_trades: int = 0
    tier2_trades: int = 0

    @property
    def win_rate(self) -> float:
        return self.wins / self.trades if self.trades else 0.0

    @property
    def expectancy(self) -> float:
        return self.total_pnl / self.trades if self.trades else 0.0

    @property
    def profit_density(self) -> float:
        """PnL per risk unit (proxy for edge quality)."""
        return self.total_pnl / max(self.trades, 1)


@dataclass
class ForwardTestReport:
    """Full 3-mode comparison."""
    baseline: ModeResult
    policy: ModeResult
    hybrid: ModeResult
    forward_rows: int = 0
    train_rows: int = 0
    policy_source: str = ""

    def to_dict(self) -> dict:
        return {
            "forward_rows": self.forward_rows,
            "train_rows": self.train_rows,
            "policy_source": self.policy_source,
            "modes": {
                "BASELINE": self.baseline.__dict__,
                "POLICY": self.policy.__dict__,
                "HYBRID": self.hybrid.__dict__,
            },
            "analysis": self._analyze(),
        }

    def _analyze(self) -> dict:
        """Generalization + overfitting + contribution analysis."""
        return {
            "llm_improves_winrate": self.hybrid.win_rate > self.baseline.win_rate,
            "llm_improves_pnl": self.hybrid.total_pnl > self.baseline.total_pnl,
            "llm_adds_trades": self.policy.trades > self.baseline.trades,
            "hybrid_best_pnl": max(
                self.baseline.total_pnl, self.policy.total_pnl, self.hybrid.total_pnl
            ) == self.hybrid.total_pnl,
            "filter_quality": {
                "engine_buys_llm_blocks": self.baseline.trades - self.hybrid.trades,
                "description": "Trades engine accepted but hybrid filtered (policy veto)"
            },
            "missed_opportunity": {
                "llm_adds_engine_skips": max(0, self.policy.trades - self.baseline.trades),
                "description": "Trades LLM took that engine skipped (exploratory)"
            },
        }


def run_forward_test(
    data_csv: str,
    config: dict,
    policy,
    forward_csv: str = None,
) -> ForwardTestReport:
    """
    Run 3-mode forward test.

    Args:
        data_csv: main historical data CSV
        config: production config for BacktestRunner
        policy: frozen PolicyEngine instance
        forward_csv: if provided, use as forward set; else auto-split data_csv
    Returns:
        ForwardTestReport with all 3 mode results
    """
    from src.core.engine_runner import EngineRunner
    from src.config_layer.execution_planner import ExecutionPlannerV1_2

    # ── Load data ─────────────────────────────────────────────────────────────
    if forward_csv:
        train_rows, forward_rows = _load_explicit_split(data_csv, forward_csv)
    else:
        train_rows, forward_rows = _auto_split(data_csv, TRAIN_SPLIT)

    log.info(
        "ForwardTester: train=%d rows, forward=%d rows (source: %s)",
        len(train_rows), len(forward_rows),
        "explicit" if forward_csv else "auto-split"
    )

    engine = EngineRunner(config)
    planner = ExecutionPlannerV1_2(config)

    baseline = ModeResult(mode="BASELINE")
    pol = ModeResult(mode="POLICY")
    hybrid = ModeResult(mode="HYBRID")

    peak_baseline = peak_policy = peak_hybrid = 0.0

    for row in forward_rows:
        features = {k: float(v) for k, v in row.items() if _is_numeric(v)}
        if not features:
            continue

        # ── Engine decision ───────────────────────────────────────────────────
        engine_result = engine.run(features, {})
        engine_fires = engine_result.get("event") == "TRADE_OPENED"

        # ── Policy decision ───────────────────────────────────────────────────
        pol_decision = policy.evaluate(features)
        policy_fires = pol_decision["action"] == "TRADE"
        policy_tier = pol_decision["tier"]

        # ── PnL from planner (both modes use same planner) ────────────────────
        pnl = 0.0
        if engine_fires or policy_fires:
            try:
                plan = planner.plan(engine_result if engine_fires else {"event": "TRADE_OPENED", **features})
                pnl = plan.get("expected_pnl", 0.0)
            except Exception:
                pnl = 0.0

        # ── BASELINE: engine only ─────────────────────────────────────────────
        if engine_fires:
            _record_trade(baseline, pnl)
            peak_baseline = max(peak_baseline, baseline.total_pnl)
            if peak_baseline > 0:
                baseline.max_drawdown = max(baseline.max_drawdown,
                                            (peak_baseline - baseline.total_pnl) / peak_baseline)

        # ── POLICY: LLM rules only ────────────────────────────────────────────
        if policy_fires:
            factor = pol_decision.get("factor", 1.0)
            adjusted_pnl = pnl * factor
            _record_trade(pol, adjusted_pnl)
            if policy_tier == "TIER_1":
                pol.tier1_trades += 1
            elif policy_tier == "TIER_2":
                pol.tier2_trades += 1
            if factor > 1.0:
                pol.boosted_trades += 1
            peak_policy = max(peak_policy, pol.total_pnl)
            if peak_policy > 0:
                pol.max_drawdown = max(pol.max_drawdown,
                                       (peak_policy - pol.total_pnl) / peak_policy)
        else:
            pol.filtered_by_policy += 1

        # ── HYBRID: engine AND policy must agree ─────────────────────────────
        if engine_fires and policy_fires:
            factor = pol_decision.get("factor", 1.0)
            adjusted_pnl = pnl * factor
            _record_trade(hybrid, adjusted_pnl)
            if factor > 1.0:
                hybrid.boosted_trades += 1
            peak_hybrid = max(peak_hybrid, hybrid.total_pnl)
            if peak_hybrid > 0:
                hybrid.max_drawdown = max(hybrid.max_drawdown,
                                          (peak_hybrid - hybrid.total_pnl) / peak_hybrid)
        elif engine_fires and not policy_fires:
            hybrid.filtered_by_policy += 1

    return ForwardTestReport(
        baseline=baseline,
        policy=pol,
        hybrid=hybrid,
        forward_rows=len(forward_rows),
        train_rows=len(train_rows),
        policy_source=getattr(policy, "_source", "unknown"),
    )


def save_report(report: ForwardTestReport, path: str = "results/llm_research/forward_test_report.json"):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(report.to_dict(), f, indent=2)
    log.info("Forward test report saved: %s", path)


# ── Private helpers ───────────────────────────────────────────────────────────

def _auto_split(csv_path: str, train_ratio: float) -> tuple[list, list]:
    rows = _read_csv(csv_path)
    split = int(len(rows) * train_ratio)
    return rows[:split], rows[split:]


def _load_explicit_split(train_csv: str, forward_csv: str) -> tuple[list, list]:
    return _read_csv(train_csv), _read_csv(forward_csv)


def _read_csv(path: str) -> list[dict]:
    rows = []
    try:
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(dict(row))
    except FileNotFoundError:
        log.error("CSV not found: %s", path)
    return rows


def _is_numeric(v) -> bool:
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False


def _record_trade(result: ModeResult, pnl: float):
    result.trades += 1
    result.total_pnl += pnl
    if pnl > 0:
        result.wins += 1
    else:
        result.losses += 1