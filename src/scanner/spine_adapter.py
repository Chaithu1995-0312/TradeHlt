"""
scanner/spine_adapter.py
Adapts MultiSymbolScanner output to EngineRunner.run() — the ONLY path from
scanner signals to a trade decision.

Usage (inject into MultiSymbolScanner):

    from scanner.spine_adapter import SpineAdapter
    adapter = SpineAdapter(engine_runner=engine_runner_instance, timeframe="M15")
    scanner = MultiSymbolScanner(
        universe=universe,
        engine_runner=adapter.evaluate,
        data_fetcher=...,
    )

Contract:
    Input:  (symbol: str, data: dict)
        data must contain 35 canonical features (validated by FeatureStore).
    Output: dict compatible with MultiSymbolScanner signal format
        AND with EngineRunnerOutput from core.types.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_SENTINEL = "scanner"


class SpineAdapter:
    """
    Wraps EngineRunner.run() as the (symbol, data) callable that
    MultiSymbolScanner.engine_runner expects.

    All scanner signals MUST pass through this adapter — there is no other
    legal path from a scanned candle to a trade decision.
    """

    def __init__(
        self,
        engine_runner: Any,        # EngineRunner instance
        timeframe: str = "M15",
        session: str = "london",
    ):
        self._runner = engine_runner
        self._timeframe = timeframe
        self._session = session

    def evaluate(self, symbol: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Adapter callable for MultiSymbolScanner.engine_runner.

        Runs the canonical spine (EngineRunner.run) and maps the output to
        the action/confidence/rr format the scanner expects.

        Args:
            symbol: instrument identifier, e.g. "EURUSD"
            data:   feature dict — must satisfy CANONICAL_FEATURES schema

        Returns:
            dict with at minimum: action, confidence, rr, decision, final_score
        """
        context: Dict[str, Any] = {
            "symbol":    symbol,
            "timeframe": self._timeframe,
            "session":   self._session,
            "candle_idx": data.get("candle_idx", 0),
        }

        try:
            result = self._runner.run(input_data=data, context=context)
        except Exception as exc:
            logger.warning("SpineAdapter[%s]: EngineRunner.run failed: %s", symbol, exc)
            return {"action": "NO_SIGNAL", "confidence": 0.0, "rr": 0.0,
                    "decision": "reject", "reason": str(exc)}

        decision = str(result.get("decision", "reject")).lower()
        final_score = float(result.get("final_score", 0.0))
        direction = result.get("selected_direction", 0)

        if decision != "execute":
            return {
                "action":     "NO_SIGNAL",
                "confidence": final_score,
                "rr":         0.0,
                "decision":   decision,
                "reason":     result.get("reason", result.get("reject_stage", "")),
                **result,
            }

        action = "BUY" if direction >= 0 else "SELL"
        rr = float(result.get("engine_scores", {}).get("rr", 0.0))

        return {
            "action":     action,
            "confidence": final_score,
            "rr":         rr,
            "decision":   "execute",
            "final_score": final_score,
            "regime":     result.get("regime", ""),
            "engine_scores": result.get("engine_scores", {}),
            "fusion":     result.get("fusion", {}),
            **result,
        }
