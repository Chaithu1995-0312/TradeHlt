"""
strategy_orchestrator.py
================================================================================
StrategyOrchestrator — runs all 10 strategies per candle and aggregates signals.

Per-candle flow:
  1. Run every enabled strategy → list[StrategyResult]
  2. Collect actionable results (signal != NO_TRADE)
  3. Completeness gate: require >= min_signal_strategies actionable results
  4. Consensus gate: >= min_agreement_ratio must agree on one direction
  5. Weighted score/confidence from actionable results
  6. Return OrchestratorResult with ensemble metadata + top candidate

Design constraints:
  - Zero changes to existing EngineRunner or FusionEngine.compute() path.
  - Strategy failures are caught individually (fail_open=True): one broken
    strategy never blocks the others.
  - OrchestratorResult.to_engine_dict() emits a format compatible with
    FusionEngine.fuse_strategy_results() for downstream blending.

Config section: strategy_orchestrator in production JSON.
================================================================================
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from config_layer.production_config import get_prod_section   # type: ignore
from strategies.base_strategy import BaseStrategy              # type: ignore
from strategies.strategy_result import StrategyResult          # type: ignore
from strategies.s01_crt_wrapper import S01CRTWrapper           # type: ignore
from strategies.s02_mean_reversion import S02MeanReversion     # type: ignore
from strategies.s03_breakout import S03Breakout                # type: ignore
from strategies.s04_stat_arb import S04StatArb                 # type: ignore
from strategies.s05_grid import S05Grid                        # type: ignore
from strategies.s06_scalping import S06Scalping                # type: ignore
from strategies.s07_news_sentiment import S07NewsSentiment     # type: ignore
from strategies.s08_ml_ensemble import S08MLEnsemble           # type: ignore
from strategies.s09_pattern_recog import S09PatternRecog       # type: ignore
from strategies.s10_trap_strategy import S10TrapStrategy       # type: ignore
from utils.logging_config import get_flow_logger               # type: ignore

logger = get_flow_logger("STRATEGY_ENGINE")

# Ordered registry — instantiated once per pair/timeframe
_STRATEGY_CLASSES: Dict[str, type] = {
    "S1":  S01CRTWrapper,
    "S2":  S02MeanReversion,
    "S3":  S03Breakout,
    "S4":  S04StatArb,
    "S5":  S05Grid,
    "S6":  S06Scalping,
    "S7":  S07NewsSentiment,
    "S8":  S08MLEnsemble,
    "S9":  S09PatternRecog,
    "S10": S10TrapStrategy,
}


def _load_orch_cfg() -> dict:
    try:
        cfg = get_prod_section("strategy_orchestrator") or {}
    except RuntimeError:
        cfg = {}
    if not cfg:
        logger.warning("strategy_orchestrator section missing — using defaults")
    return cfg


_AUDIT_PATH = _ROOT / "logs" / "strategy_audit.jsonl"


def _append_audit(record: dict) -> None:
    try:
        _AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_AUDIT_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except Exception as exc:
        logger.debug("strategy_audit write failed (ignored): %s", exc)


def _build_audit_record(r: "OrchestratorResult") -> dict:
    return {
        "kind":            "STRATEGY_RESULT",
        "ts":              r.ts,
        "pair":            r.pair,
        "timeframe":       r.timeframe,
        "signal":          r.signal,
        "confidence":      round(r.confidence, 4),
        "score":           round(r.score, 4),
        "signal_count":    r.signal_count,
        "agree_count":     r.agree_count,
        "agreement_ratio": round(r.agreement_ratio, 4),
        "gate_reason":     r.gate_reason,
        "elapsed_ms":      round(r.elapsed_ms, 2),
        "strategies": {
            s.strategy_id: {
                "signal":     s.signal,
                "confidence": round(s.confidence, 4),
                "score":      round(s.score, 4),
            }
            for s in r.all_results
        },
    }


# ── Output contract ────────────────────────────────────────────────────────────

@dataclass
class OrchestratorResult:
    """
    Aggregated output from all 10 strategies for a single candle.

    Fields
    ------
    signal          Consensus direction: BUY | SELL | NO_TRADE
    confidence      Weighted-average confidence of agreeing strategies
    score           Weighted-average score of agreeing strategies
    active_count    Total strategies attempted
    signal_count    Strategies that returned an actionable signal
    agree_count     Strategies agreeing with consensus direction
    agreement_ratio agree_count / signal_count
    top_result      Highest-confidence actionable StrategyResult (or None)
    all_results     All 10 StrategyResult objects (including NO_TRADE)
    pair            Instrument symbol
    timeframe       Candle timeframe
    ts              ISO-8601 UTC timestamp
    elapsed_ms      Wall-clock time to run all strategies (milliseconds)
    gate_reason     Why NO_TRADE was returned by the gate (or "")
    """
    signal:          str
    confidence:      float
    score:           float
    active_count:    int
    signal_count:    int
    agree_count:     int
    agreement_ratio: float
    top_result:      Optional[StrategyResult]
    all_results:     List[StrategyResult]
    pair:            str
    timeframe:       str
    ts:              str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    elapsed_ms:      float = 0.0
    gate_reason:     str   = ""

    def is_actionable(self) -> bool:
        return self.signal in ("BUY", "SELL") and self.confidence > 0.0

    def to_engine_dict(self) -> dict:
        """Format compatible with FusionEngine.fuse_strategy_results()."""
        return {
            "signal":          self.signal,
            "confidence":      self.confidence,
            "score":           self.score,
            "signal_count":    self.signal_count,
            "agree_count":     self.agree_count,
            "agreement_ratio": self.agreement_ratio,
            "pair":            self.pair,
            "timeframe":       self.timeframe,
        }

    def to_dict(self) -> dict:
        d = asdict(self)
        d["top_result"] = self.top_result.to_dict() if self.top_result else None
        d["all_results"] = [r.to_dict() for r in self.all_results]
        return d


# ── Orchestrator ───────────────────────────────────────────────────────────────

class StrategyOrchestrator:
    """
    Runs all enabled strategies for a single (pair, timeframe) combination.

    Instantiate once per instrument, then call compute(features, candle)
    on every new candle.

    Parameters
    ----------
    pair        Instrument symbol (e.g. "EURUSD")
    timeframe   Candle timeframe (e.g. "H1")
    config      Optional config override (None → loads from production JSON)
    """

    _orch_cfg: dict = {}

    def __init__(
        self,
        pair: str,
        timeframe: str,
        config: Optional[dict] = None,
    ) -> None:
        self.pair      = pair.upper().replace("/", "")
        self.timeframe = timeframe.upper()
        self._cfg      = config or self._load_cfg()
        self._strategies: Dict[str, BaseStrategy] = self._build_strategies()

        from config_layer.production_config import PROD_VERSION as _pv
        logger.info("Production config version: %s", _pv)

    # ── Public API ─────────────────────────────────────────────────────────────

    def compute(self, features: dict, candle: dict) -> OrchestratorResult:
        """
        Run all enabled strategies on the current candle.

        Returns OrchestratorResult with consensus signal, weighted scores,
        and full per-strategy audit trail.
        """
        t0 = time.perf_counter()
        all_results: List[StrategyResult] = []

        for sid, strategy in self._strategies.items():
            try:
                result = strategy.compute(features, candle)
            except Exception as exc:
                if self._cfg.get("fail_open", True):
                    logger.warning("Strategy %s raised %s — substituting NO_TRADE", sid, exc)
                    result = StrategyResult.no_trade(
                        strategy_id=sid, pair=self.pair, timeframe=self.timeframe
                    )
                else:
                    raise
            all_results.append(result)

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return self._aggregate(all_results, elapsed_ms)

    @property
    def strategy_ids(self) -> List[str]:
        return list(self._strategies.keys())

    # ── Aggregation ────────────────────────────────────────────────────────────

    def _aggregate(
        self,
        all_results: List[StrategyResult],
        elapsed_ms: float,
    ) -> OrchestratorResult:
        cfg = self._cfg
        min_signals: int = int(cfg.get("min_signal_strategies", 2))
        min_agree: float = float(cfg.get("min_agreement_ratio", 0.60))
        weights: dict = cfg.get("weights", {})

        actionable = [r for r in all_results if r.is_actionable()]
        active_count = len(all_results)
        signal_count = len(actionable)

        def _no_trade(reason: str) -> OrchestratorResult:
            return OrchestratorResult(
                signal="NO_TRADE", confidence=0.0, score=0.0,
                active_count=active_count, signal_count=signal_count,
                agree_count=0, agreement_ratio=0.0,
                top_result=None, all_results=all_results,
                pair=self.pair, timeframe=self.timeframe,
                elapsed_ms=elapsed_ms, gate_reason=reason,
            )

        # Completeness gate
        if signal_count < min_signals:
            result = _no_trade(f"completeness_gate: {signal_count}/{min_signals} strategies fired")
            _append_audit(_build_audit_record(result))
            return result

        # Count votes per direction
        buy_results  = [r for r in actionable if r.signal == "BUY"]
        sell_results = [r for r in actionable if r.signal == "SELL"]
        consensus_signal = "BUY" if len(buy_results) >= len(sell_results) else "SELL"
        agree_results = buy_results if consensus_signal == "BUY" else sell_results
        agree_count = len(agree_results)
        agreement_ratio = agree_count / signal_count

        # Consensus gate
        if agreement_ratio < min_agree:
            result = _no_trade(
                f"consensus_gate: {agreement_ratio:.0%} agreement < {min_agree:.0%} required"
            )
            _append_audit(_build_audit_record(result))
            return result

        # Weighted score + confidence over agreeing results
        total_weight = 0.0
        weighted_score = 0.0
        weighted_conf = 0.0
        for r in agree_results:
            w = float(weights.get(r.strategy_id, 1.0 / len(agree_results)))
            weighted_score += r.score * w
            weighted_conf += r.confidence * w
            total_weight += w

        if total_weight > 0.0:
            weighted_score /= total_weight
            weighted_conf /= total_weight

        top_result = max(agree_results, key=lambda r: r.confidence)

        logger.info(
            "Orchestrator %s %s: %s signal_count=%d agree=%d/%d ratio=%.0%% "
            "score=%.3f conf=%.2f elapsed=%.1fms",
            self.pair, self.timeframe, consensus_signal,
            signal_count, agree_count, signal_count,
            agreement_ratio, weighted_score, weighted_conf, elapsed_ms,
        )

        result = OrchestratorResult(
            signal=consensus_signal,
            confidence=min(weighted_conf, 1.0),
            score=min(weighted_score, 1.0),
            active_count=active_count,
            signal_count=signal_count,
            agree_count=agree_count,
            agreement_ratio=agreement_ratio,
            top_result=top_result,
            all_results=all_results,
            pair=self.pair,
            timeframe=self.timeframe,
            elapsed_ms=elapsed_ms,
            gate_reason="",
        )
        _append_audit(_build_audit_record(result))
        return result

    # ── Init helpers ───────────────────────────────────────────────────────────

    def _load_cfg(self) -> dict:
        if not StrategyOrchestrator._orch_cfg:
            StrategyOrchestrator._orch_cfg = _load_orch_cfg()
        return StrategyOrchestrator._orch_cfg

    def _build_strategies(self) -> Dict[str, BaseStrategy]:
        enabled: List[str] = self._cfg.get(
            "enabled_strategies", list(_STRATEGY_CLASSES.keys())
        )
        strategies: Dict[str, BaseStrategy] = {}
        for sid in enabled:
            cls = _STRATEGY_CLASSES.get(sid)
            if cls is None:
                logger.warning("Unknown strategy ID %s — skipped", sid)
                continue
            try:
                strategies[sid] = cls(pair=self.pair, timeframe=self.timeframe)
            except Exception as exc:
                logger.error("Failed to instantiate %s: %s", sid, exc)
                if not self._cfg.get("fail_open", True):
                    raise
        return strategies
