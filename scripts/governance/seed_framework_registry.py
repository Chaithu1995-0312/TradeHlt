"""Seed data/framework_registry.jsonl from the curated codebase classification.

One-time / regenerable map of existing code against the 6-level hierarchy
(001_FRAMEWORK_REGISTRY.md §M1). Thin wrapper: builds the curated records, validates each via
``FrameworkRegistry.validate_record``, writes deterministically (sorted, pinned timestamps) so
reruns are byte-identical.

Statuses are CODE-VERIFIED, not copied from the framework docs (CLAUDE.md §6.2 — code wins):
  - UltronRiskGate is ``extant`` + WIRED (active config disabled=false; live_engine_hook.py),
    NOT the docs' "disabled".
  - config_integrity / portfolio are ``orphaned`` (F-006 / F-013).
  - Domain CryptoSpot/Forex are ``implicit`` (no Domain class). CryptoFutures/Equities/Futures/
    Options are ABSENT and get no record.

Run:  python scripts/governance/seed_framework_registry.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
for _p in (_ROOT / "src", _ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from governance.framework_registry import FrameworkRegistry  # noqa: E402

OUT = _ROOT / "data" / "framework_registry.jsonl"
_TS = "2026-06-16T00:00:00Z"  # pinned for byte-stable reruns


def _ev(path: str, etype: str, symbol: str | None = None, line: int | None = None) -> dict:
    return {"path": path, "line": line, "symbol": symbol, "type": etype}


def _rec(
    rid: str, rtype: str, level: int, name: str, *,
    parent: str | None = None, children: list[str] | None = None,
    evidence: list[dict] | None = None, findings: list[str] | None = None,
    tests: list[str] | None = None, status: str, notes: str = "",
) -> dict:
    return {
        "id": rid, "type": rtype, "level": level, "name": name,
        "parent": parent, "children": children or [],
        "evidence": evidence or [], "findings": findings or [], "tests": tests or [],
        "status": status, "created": _TS, "last_validated": _TS, "notes": notes,
    }


def build_records() -> list[dict]:
    R: list[dict] = []

    # ---- L0 Kernel (domain-independent plumbing) -------------------------------
    R.append(_rec("KERNEL-001", "kernel", 0, "EngineRunner",
                  children=["IMPL-002", "IMPL-003", "IMPL-004", "IMPL-005"],
                  evidence=[_ev("src/core/engine_runner.py", "code", "EXPECTED_ENGINES", 52)],
                  status="extant", notes="Orchestrator; fuses the 4 mandatory engines."))
    R.append(_rec("KERNEL-002", "kernel", 0, "FusionEngine",
                  evidence=[_ev("src/core/fusion_engine.py", "code", "FusionEngine")],
                  findings=["F-005"], status="extant",
                  notes="Weighted-completeness fusion; TradeNet v2 slot is a permanent stub (F-005)."))
    R.append(_rec("KERNEL-003", "kernel", 0, "DecisionEngine",
                  evidence=[_ev("src/core/decision_engine.py", "code", "DecisionEngine")],
                  status="extant"))
    R.append(_rec("KERNEL-004", "kernel", 0, "FeaturePipeline",
                  evidence=[_ev("src/features/feature_pipeline.py", "code", "FeaturePipeline")],
                  findings=["F-029"], status="extant",
                  notes="38-dim CANONICAL_FEATURES; center=True/global-rank benign (F-029)."))
    R.append(_rec("KERNEL-005", "kernel", 0, "BacktestRunner",
                  evidence=[_ev("src/runtime/backtest_v2.py", "code", "BacktestRunner")],
                  findings=["F-010"], status="extant",
                  notes="Candle-by-candle, no lookahead; headline ROI is backtest-only (F-010)."))
    R.append(_rec("KERNEL-006", "kernel", 0, "Collector",
                  evidence=[_ev("src/core/collector.py", "code", "Collector")],
                  findings=["F-022"], status="extant",
                  notes="opportunities.jsonl is a detection stream, not a trade ledger (F-022)."))

    # ---- L1 Domain (implicit — no Domain class) --------------------------------
    R.append(_rec("DOMAIN-001", "domain", 1, "CryptoSpot",
                  children=["STYLE-001", "STYLE-002", "STYLE-003", "STYLE-004",
                            "STYLE-005", "STYLE-006", "STYLE-007", "STYLE-008"],
                  evidence=[_ev("scripts/data/fetch_crypto_ccxt.py", "code", "fetch"),
                            _ev("configs/production/v2_multi_2026_04.json", "config", "session_calendar")],
                  findings=["F-016", "F-019"], status="implicit",
                  notes="No Domain class; calendar/cost/leverage implicit in config + data scripts. "
                        "Active config v2_multi_2026_04 (F-016)."))
    R.append(_rec("DOMAIN-002", "domain", 1, "Forex",
                  evidence=[_ev("scripts/data/fetch_forex_yfinance.py", "code", "fetch")],
                  findings=["F-029"], status="implicit",
                  notes="Dormant data pipeline only; 0 trades on active config (F-029 cross-asset OPEN)."))

    # ---- L2 Style (no style class yet) -----------------------------------------
    styles = [
        ("STYLE-001", "ReactionBased", ["STRAT-001", "STRAT-007", "STRAT-010"],
         "src/strategies/s01_crt_wrapper.py", "Strategy", ["F-021"],
         "3 strategies (CRT/News/Trap); CRT empirically null beyond session (F-021)."),
        ("STYLE-002", "MeanReversion", ["STRAT-002"], "src/strategies/s02_mean_reversion.py", "Strategy", [], ""),
        ("STYLE-003", "Breakout", ["STRAT-003"], "src/strategies/s03_breakout.py", "Strategy", [], ""),
        ("STYLE-004", "StatArb", ["STRAT-004"], "src/strategies/s04_stat_arb.py", "Strategy", [], ""),
        ("STYLE-005", "Grid", ["STRAT-005"], "src/strategies/s05_grid.py", "Strategy", [], ""),
        ("STYLE-006", "Momentum", ["STRAT-006"], "src/strategies/s06_scalping.py", "Strategy", [], ""),
        ("STYLE-007", "Pattern", ["STRAT-009"], "src/strategies/s09_pattern_recog.py", "Strategy", ["F-028"],
         "P&F PNF-v1 double-top/bottom carries no standalone edge (F-028)."),
        ("STYLE-008", "MLHybrid", ["STRAT-008"], "src/strategies/s08_ml_ensemble.py", "Strategy", [], ""),
    ]
    for sid, name, kids, path, sym, finds, note in styles:
        R.append(_rec(sid, "style", 2, name, parent="DOMAIN-001", children=kids,
                      evidence=[_ev(path, "code", sym)], findings=finds, status="extant",
                      notes=note or "No style class; strategy is flat under the kernel."))

    # ---- L3 Strategy ------------------------------------------------------------
    strats = [
        ("STRAT-001", "CRT", "STYLE-001", "src/strategies/s01_crt_wrapper.py", ["IMPL-001"],
         ["F-021"], "Wired as a MANDATORY engine (not a plugin); de-privileging is downstream (F-021)."),
        ("STRAT-002", "RSI_BB", "STYLE-002", "src/strategies/s02_mean_reversion.py", [], [], ""),
        ("STRAT-003", "BOS_Volume", "STYLE-003", "src/strategies/s03_breakout.py", [], [], ""),
        ("STRAT-004", "ZScore", "STYLE-004", "src/strategies/s04_stat_arb.py", [], [], ""),
        ("STRAT-005", "ATRGrid", "STYLE-005", "src/strategies/s05_grid.py", [], [], ""),
        ("STRAT-006", "MACD", "STYLE-006", "src/strategies/s06_scalping.py", [], [], ""),
        ("STRAT-007", "NewsSentiment", "STYLE-001", "src/strategies/s07_news_sentiment.py", [], [], ""),
        ("STRAT-008", "MLEnsemble", "STYLE-008", "src/strategies/s08_ml_ensemble.py", [], [], ""),
        ("STRAT-009", "Candlestick", "STYLE-007", "src/strategies/s09_pattern_recog.py", [], [], ""),
        ("STRAT-010", "LiquiditySweep", "STYLE-001", "src/strategies/s10_trap_strategy.py", [], ["F-026"],
         "Trap/sweep continuation adds no forward asymmetry (Program 2/E1, F-026)."),
    ]
    for tid, name, parent, path, kids, finds, note in strats:
        R.append(_rec(tid, "strategy", 3, name, parent=parent, children=kids,
                      evidence=[_ev(path, "code", "Strategy")], findings=finds, status="extant",
                      notes=note))

    # ---- L4 Implementation / Intelligence --------------------------------------
    R.append(_rec("IMPL-001", "implementation", 4, "CRTEngine", parent="STRAT-001",
                  evidence=[_ev("src/engines/crt_engine.py", "code", "CRTEngine")],
                  status="extant", notes="Concrete CRT scoring implementation."))
    R.append(_rec("IMPL-002", "implementation", 4, "HeuristicGaussianEngine", parent="KERNEL-001",
                  evidence=[_ev("src/engines/heuristic_gaussian_engine.py", "code", "Engine")],
                  status="extant", notes="Fused at kernel (1 of 4 mandatory engines)."))
    R.append(_rec("IMPL-003", "implementation", 4, "MLGaussianEngine", parent="KERNEL-001",
                  evidence=[_ev("src/engines/ml_gaussian_engine.py", "code", "Engine")],
                  status="extant", notes="Fused at kernel."))
    R.append(_rec("IMPL-004", "implementation", 4, "ZoneGateEngine", parent="KERNEL-001",
                  evidence=[_ev("src/engines/zone_gate_engine.py", "code", "Engine")],
                  findings=["F-021"], status="extant", notes="Fused at kernel; 0 ZONE rejects on RETEST (F-021)."))
    R.append(_rec("IMPL-005", "implementation", 4, "RREngine", parent="KERNEL-001",
                  evidence=[_ev("src/engines/rr_engine.py", "code", "Engine")],
                  status="extant", notes="Fused at kernel."))
    R.append(_rec("IMPL-006", "implementation", 4, "AutomationAgent",
                  evidence=[_ev("src/agent/agent_core.py", "code", "Agent")],
                  status="extant", notes="REPL + deterministic PLAN_REGISTRY; advisory."))
    R.append(_rec("IMPL-007", "implementation", 4, "BitNetInference",
                  evidence=[_ev("src/bitnet/bitnet_inference.py", "code", "BitNet")],
                  findings=["F-004"], status="extant",
                  notes="LIVE hard-reject gate (score<0.55), persisted; only adaptive threshold dormant (F-004)."))
    R.append(_rec("IMPL-008", "implementation", 4, "RegimeClassifier",
                  evidence=[_ev("src/cognitive/cognitive_bus.py", "code", "Bus")],
                  findings=["F-012"], status="dormant",
                  notes="cognitive/ is sidecar-only, zero spine consumption (F-012)."))
    R.append(_rec("IMPL-009", "implementation", 4, "DriftDetector",
                  evidence=[_ev("src/features/feature_monitor.py", "code", "FeatureMonitor")],
                  findings=["F-008"], status="extant",
                  notes="Drift DETECTED but not acted on — no block/size-down (F-008)."))

    # ---- L5 Risk ----------------------------------------------------------------
    R.append(_rec("RISK-001", "risk", 5, "UltronRiskGate",
                  evidence=[_ev("src/core/ultron_risk_gate.py", "code", "disabled", 48),
                            _ev("src/runtime/live_engine_hook.py", "code", "UltronRiskGate")],
                  findings=["F-010"], status="extant",
                  notes="CODE-VERIFIED: disabled=false in active config, wired in live_engine_hook. "
                        "Framework doc's 'disabled' claim is DOC_DRIFT (corrected)."))
    R.append(_rec("RISK-002", "risk", 5, "PortfolioAllocator",
                  evidence=[_ev("src/portfolio/allocator.py", "code", "PortfolioAllocator")],
                  findings=["F-013"], status="orphaned",
                  notes="Built but zero runtime callers (F-013); CapitalPolicy/exposure/correlation siblings."))

    # ---- L6 Execution -----------------------------------------------------------
    R.append(_rec("EXEC-001", "execution", 6, "ExecutionPlannerV1_2",
                  evidence=[_ev("src/config_layer/execution_planner.py", "code", "ExecutionPlanner")],
                  status="extant", notes="Derives entry/SL/TP/RR/TTL from accepted signals."))
    R.append(_rec("EXEC-002", "execution", 6, "LiveEngine",
                  evidence=[_ev("src/engines/live_engine.py", "code", "LiveEngine")],
                  findings=["F-010"], status="stub",
                  notes="Live path unverified (F-010); no slippage model (fixed 12bps). "
                        "001's src/inout/executor.py does NOT exist — DOC_DRIFT."))

    # ---- Governance / meta (intent, not in the hierarchy) ----------------------
    R.append(_rec("INTENT-001", "intent", 0, "PromotionManager",
                  evidence=[_ev("src/governance/promotion_manager.py", "code", "PromotionManager")],
                  status="extant", notes="The only path to production; requires APPROVE ValidationReport."))
    R.append(_rec("INTENT-002", "intent", 0, "ConfigIntegrity",
                  evidence=[_ev("src/governance/config_integrity.py", "code", "audit")],
                  findings=["F-006"], status="orphaned",
                  notes="Real check but ORPHANED — gates nothing at runtime, CLI-only (F-006)."))
    return R


def main() -> int:
    records = build_records()
    n = FrameworkRegistry.dump(OUT, records)
    print(f"seeded {n} records -> {OUT.relative_to(_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
