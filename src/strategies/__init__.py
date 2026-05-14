"""
strategies package — all 10 strategy modules (S1..S10) + orchestrator.

Sprint 1: StrategyResult contract + BaseStrategy ABC
Sprint 2: S1 CRT, S2 MeanRev, S3 Breakout, S9 Pattern, S10 Trap
Sprint 3: S4 StatArb, S5 Grid, S6 Scalping, S7 News, S8 ML Ensemble
Sprint 4: StrategyOrchestrator + FusionEngine.fuse_strategy_results()
"""

from strategies.strategy_result import StrategyResult
from strategies.base_strategy import BaseStrategy
from strategies.s01_crt_wrapper import S01CRTWrapper
from strategies.s02_mean_reversion import S02MeanReversion
from strategies.s03_breakout import S03Breakout
from strategies.s04_stat_arb import S04StatArb
from strategies.s05_grid import S05Grid
from strategies.s06_scalping import S06Scalping
from strategies.s07_news_sentiment import S07NewsSentiment
from strategies.s08_ml_ensemble import S08MLEnsemble
from strategies.s09_pattern_recog import S09PatternRecog
from strategies.s10_trap_strategy import S10TrapStrategy
from strategies.strategy_orchestrator import StrategyOrchestrator, OrchestratorResult

__all__ = [
    "StrategyResult",
    "BaseStrategy",
    "S01CRTWrapper",
    "S02MeanReversion",
    "S03Breakout",
    "S04StatArb",
    "S05Grid",
    "S06Scalping",
    "S07NewsSentiment",
    "S08MLEnsemble",
    "S09PatternRecog",
    "S10TrapStrategy",
    "StrategyOrchestrator",
    "OrchestratorResult",
]
