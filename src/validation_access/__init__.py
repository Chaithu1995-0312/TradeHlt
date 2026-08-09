"""Validation Access (VA-XAUUSD-M15) — dual-surface sequential ladder S→I→F→E.

Access / packaging only. Grants no runtime, fusion, sizing, or promotion authority.
Design freeze: docs/governance/VALIDATION_ACCESS_VA_XAUUSD_M15.md
"""
from __future__ import annotations

from validation_access.ladder import LadderResult, run_ladder

__all__ = ["LadderResult", "run_ladder"]
