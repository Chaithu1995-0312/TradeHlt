"""
crt_sweep_taxonomy.py
═══════════════════════════════════════════════════════════════════════════════
Pure-function geometric classifier for CRT sweep candles.

Source of truth: Jarvis_CRT_Handover.docx §5.3 (Patch v3, BTCUSDT M15, 2024-01-01)

Classifies a candle's wick/body geometry into one of four sweep archetypes,
or returns None if no archetype matches. Used as ADDITIVE METADATA on existing
SweepEvents — does NOT influence sweep detection or scoring decisions.

This module deliberately:
  - has zero dependency on the production scoring stack
  - is side-effect free (no logging, no global state)
  - uses no random jitter (deterministic by construction)

Consumers:
  1. config_layer/crt_engine_v2.py::RangeDetector.detect_sweep
       → annotates SweepEvent.sweep_type / sweep_label for diagnostics.
  2. tools/btcusdt_crt_v3_replay.py
       → reference harness reproducing the handover doc's worked examples.
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

from typing import Optional, Tuple

# ─────────────────────────────────────────────────────────────────
# CONSTANTS — verbatim from §5.3 / §7.2 of the handover doc
# ─────────────────────────────────────────────────────────────────

WICK_BONUS_FACTOR: float = 0.35

# (sweep_type, sweep_label, predicate(uw, lw, br, bearish) -> bool)
# Order matters: first match wins.
_SWEEP_RULES = (
    ("TYPE-A", "PINBAR BEAR",
        lambda uw, lw, br, bearish: uw < 0.02 and lw > 0.35 and br > 0.40 and bearish),
    ("TYPE-B", "SHOOTING STAR",
        lambda uw, lw, br, bearish: uw > 0.40 and lw < 0.12 and br > 0.30 and bearish),
    ("TYPE-C", "HAMMER",
        lambda uw, lw, br, bearish: lw > 0.40 and uw < 0.12 and br > 0.30 and not bearish),
    ("TYPE-D", "PINBAR BULL",
        lambda uw, lw, br, bearish: lw < 0.02 and uw > 0.35 and br > 0.40 and not bearish),
)


# ─────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────

def classify_sweep(
    upper_wick: float,
    lower_wick: float,
    body_ratio: float,
    bearish: bool,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Classify a candle's geometry per Section 5.3 of the handover doc.

    Parameters
    ----------
    upper_wick : float in [0, 1]
        (high - max(open, close)) / full_range
    lower_wick : float in [0, 1]
        (min(open, close) - low) / full_range
    body_ratio : float in [0, 1]
        |close - open| / full_range
    bearish    : bool
        True if close < open

    Returns
    -------
    (sweep_type, sweep_label) : tuple of two Optional[str]
        ('TYPE-A', 'PINBAR BEAR')   for upper<0.02, lower>0.35, body>0.40, bearish
        ('TYPE-B', 'SHOOTING STAR') for upper>0.40, lower<0.12, body>0.30, bearish
        ('TYPE-C', 'HAMMER')        for lower>0.40, upper<0.12, body>0.30, bullish
        ('TYPE-D', 'PINBAR BULL')   for lower<0.02, upper>0.35, body>0.40, bullish
        (None, None)                otherwise
    """
    for sweep_type, sweep_label, predicate in _SWEEP_RULES:
        if predicate(upper_wick, lower_wick, body_ratio, bearish):
            return sweep_type, sweep_label
    return None, None


def wick_bonus(
    sweep_type: Optional[str],
    upper_wick: float,
    lower_wick: float,
) -> float:
    """
    Compute the wick_bonus scalar used by the doc's 4-head scoring (§7.2).

    Bonus formula (§7.2 / Table 9):
        TYPE-A PINBAR BEAR    → lower_wick * 0.35
        TYPE-B SHOOTING STAR  → upper_wick * 0.35
        TYPE-C HAMMER         → lower_wick * 0.35
        TYPE-D PINBAR BULL    → upper_wick * 0.35
        None                  → 0.0
    """
    if sweep_type in ("TYPE-A", "TYPE-C"):
        return lower_wick * WICK_BONUS_FACTOR
    if sweep_type in ("TYPE-B", "TYPE-D"):
        return upper_wick * WICK_BONUS_FACTOR
    return 0.0


def candle_geometry(
    open_: float,
    high: float,
    low: float,
    close: float,
) -> dict:
    """
    Compute the per-candle geometry used by the taxonomy and the doc's scoring.
    Matches Table 3 of the handover doc exactly.

    Returns dict with keys: full_range, body, body_ratio, upper_wick, lower_wick, bearish
    """
    full_range = max(high - low, 0.001)  # floor per Table 3
    body = abs(close - open_)
    upper_wick = (high - max(open_, close)) / full_range
    lower_wick = (min(open_, close) - low) / full_range
    return {
        "full_range": full_range,
        "body":       body,
        "body_ratio": body / full_range,
        "upper_wick": upper_wick,
        "lower_wick": lower_wick,
        "bearish":    close < open_,
    }
