"""Semantic OS integration run: the real backtest observed bar by bar, compared with the v2
concept contracts (observe -> checks -> report). Observation only; nothing is edited or wired.

Run: scripts/governance/semantic_os_integration.py
"""

from semantics.integration.checks import (
    AGREE, EXPECTED_DIVERGENCE, NOT_CHECKABLE, UNEXPLAINED, VERDICTS, CheckContext, Row, run_checks,
)
from semantics.integration.report import d_levels, write_report

__all__ = [
    "AGREE", "EXPECTED_DIVERGENCE", "NOT_CHECKABLE", "UNEXPLAINED", "VERDICTS", "CheckContext", "Row",
    "run_checks", "d_levels", "write_report",
]
