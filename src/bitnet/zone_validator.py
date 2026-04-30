"""
bitnet/zone_validator.py
=========================
Validates candidate zones against minimum quality criteria.

Rejects zones that are:
  - Too small (insufficient sample size)
  - Unprofitable (avg_rr too low)
  - High drawdown
  - Below minimum winrate

This is the primary guard against weak / garbage zones entering the registry.
"""

from __future__ import annotations
from typing import Tuple


class ZoneValidator:
    """
    Validates a zone candidate's aggregate metrics.

    Acceptance criteria (class-level constants, override via subclass or instance):
      MIN_TRADES    : minimum trade count inside zone
      MIN_AVG_RR    : minimum average RR required
      MAX_DRAWDOWN  : maximum allowable sequential drawdown
      MIN_WINRATE   : minimum win rate

    Usage
    -----
        ok, reason = ZoneValidator.check(metrics)
        if not ok:
            log.warning(f"Zone rejected: {reason}")
    """

    MIN_TRADES   = 100
    MIN_AVG_RR   = 0.30
    MAX_DRAWDOWN = 0.25
    MIN_WINRATE  = 0.40

    @classmethod
    def check(cls, metrics: dict) -> Tuple[bool, str]:
        """
        Check if zone metrics meet acceptance criteria.

        Parameters
        ----------
        metrics : dict with keys: trade_count, avg_rr, max_drawdown, winrate

        Returns
        -------
        (accepted: bool, reason: str)
        """
        n       = metrics.get("trade_count", 0)
        avg_rr  = metrics.get("avg_rr",      0.0)
        max_dd  = metrics.get("max_drawdown", 1.0)
        winrate = metrics.get("winrate",      0.0)

        if n < cls.MIN_TRADES:
            return False, f"insufficient_trades ({n} < {cls.MIN_TRADES})"

        if avg_rr <= cls.MIN_AVG_RR:
            return False, f"low_avg_rr ({avg_rr:.4f} <= {cls.MIN_AVG_RR})"

        if max_dd > cls.MAX_DRAWDOWN:
            return False, f"high_drawdown ({max_dd:.4f} > {cls.MAX_DRAWDOWN})"

        if winrate < cls.MIN_WINRATE:
            return False, f"low_winrate ({winrate:.4f} < {cls.MIN_WINRATE})"

        return True, "accepted"

    @classmethod
    def is_valid(cls, metrics: dict) -> bool:
        """Convenience method — returns bool only."""
        ok, _ = cls.check(metrics)
        return ok

    @classmethod
    def with_thresholds(
        cls,
        min_trades:   int   = 100,
        min_avg_rr:   float = 0.30,
        max_drawdown: float = 0.25,
        min_winrate:  float = 0.40,
    ) -> "type[ZoneValidator]":
        """
        Factory: create a ZoneValidator subclass with custom thresholds.

        Example
        -------
            StrictValidator = ZoneValidator.with_thresholds(min_trades=200, min_avg_rr=0.50)
            ok, reason = StrictValidator.check(metrics)
        """
        return type(
            "CustomZoneValidator",
            (cls,),
            {
                "MIN_TRADES":   min_trades,
                "MIN_AVG_RR":   min_avg_rr,
                "MAX_DRAWDOWN": max_drawdown,
                "MIN_WINRATE":  min_winrate,
            },
        )