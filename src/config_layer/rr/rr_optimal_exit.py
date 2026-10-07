"""
rr_optimal_exit.py
==================
Post-entry optimal-exit labeller (hindsight — TRAINING / ANALYSIS ONLY).

Given a filled entry, walk the next N bars and find the *maximum* take-profit
price the market reached before the stop-loss was touched.

Rules
-----
1. SL is anchored to the entry range (CRT range / entry candle):
       LONG  → sl = range_low  - sl_range_buffer_frac * range_height
       SHORT → sl = range_high + sl_range_buffer_frac * range_height
2. TP = maximum favourable excursion (MFE) reached strictly AFTER the entry
   bar and BEFORE the SL is hit, within `max_forward_bars`.
3. Round-trip cost on the invested amount:
       entry leg = investment * (fee + slippage) + investment * spread
       exit  leg = qty * exit_price * (fee + slippage)
   Trade is APPROVED only if
       net_profit(tp_max) > investment * min_net_return_pct
   i.e. the profit at max TP still beats the investment after a round trip.
   The minimum qualifying TP price is closed-form:
       LONG  tp_min = E * (1 + c + s + m) / (1 - c)
       SHORT tp_min = E * (1 - c - s - m) / (1 + c)
   with c = fee+slippage per side, s = spread, m = min_net_return_pct.

Same-bar ambiguity (bar touches both SL and a new high/low): resolved by
`same_bar_policy` — "sl_first" (pessimistic, default) ignores that bar's
excursion; "tp_first" counts it, then stops.

WARNING: uses future bars by design. Never call from BacktestRunner /
EngineRunner / live paths — it produces labels, not signals (no-lookahead rule,
CLAUDE.md §4).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from config_layer.production_config import get_prod_section          # type: ignore
from utils.logging_config import get_flow_logger                      # type: ignore


logger = get_flow_logger("EXECUTION_PLANNER")

_SECTION = "rr_optimal_exit"
_SAME_BAR_POLICIES = ("sl_first", "tp_first")


# ============================================================================
# CONFIG LOAD — fail-fast at module import
# ============================================================================

def _load_optimal_exit_cfg() -> dict:
    cfg = get_prod_section(_SECTION)
    if not cfg:
        raise RuntimeError(
            f"{_SECTION} section missing from production config JSON. "
            "Add it to configs/production/v1_multi_2026_03.json."
        )
    return cfg


def _require(cfg: dict, key: str) -> object:
    if key not in cfg:
        raise KeyError(
            f"Required config key '{key}' missing from {_SECTION} section. "
            f"Add it to configs/production/v1_multi_2026_03.json."
        )
    return cfg[key]


_CFG = _load_optimal_exit_cfg()


# ============================================================================
# DATA MODEL
# ============================================================================

@dataclass
class OptimalExitConfig:
    max_forward_bars:      int
    fee_pct_per_side:      float
    slippage_pct_per_side: float
    spread_pct:            float
    sl_range_buffer_frac:  float
    min_net_return_pct:    float
    same_bar_policy:       str

    @classmethod
    def from_prod_config(cls, prod_cfg: dict) -> "OptimalExitConfig":
        policy = str(_require(prod_cfg, "same_bar_policy"))
        if policy not in _SAME_BAR_POLICIES:
            raise ValueError(f"same_bar_policy={policy!r} not in {_SAME_BAR_POLICIES}")
        return cls(
            max_forward_bars      = int(_require(prod_cfg, "max_forward_bars")),
            fee_pct_per_side      = float(_require(prod_cfg, "fee_pct_per_side")),
            slippage_pct_per_side = float(_require(prod_cfg, "slippage_pct_per_side")),
            spread_pct            = float(_require(prod_cfg, "spread_pct")),
            sl_range_buffer_frac  = float(_require(prod_cfg, "sl_range_buffer_frac")),
            min_net_return_pct    = float(_require(prod_cfg, "min_net_return_pct")),
            same_bar_policy       = policy,
        )


# ============================================================================
# PUBLIC API
# ============================================================================

class OptimalExitLabeler:
    """Find SL (entry-range anchored) and max reachable TP after an entry."""

    def __init__(self, config: Optional[OptimalExitConfig] = None) -> None:
        self._cfg = config or OptimalExitConfig.from_prod_config(_CFG)

    # ── Public ────────────────────────────────────────────────────────────

    def stop_loss(self, direction: str, range_high: float, range_low: float) -> float:
        """SL just beyond the opposite side of the entry range."""
        buffer = self._cfg.sl_range_buffer_frac * (range_high - range_low)
        return range_low - buffer if direction == "LONG" else range_high + buffer

    def min_profitable_tp(self, direction: str, entry_price: float) -> float:
        """Lowest (LONG) / highest (SHORT) exit price whose net PnL beats the threshold."""
        c = self._cfg.fee_pct_per_side + self._cfg.slippage_pct_per_side
        s = self._cfg.spread_pct
        m = self._cfg.min_net_return_pct
        if direction == "LONG":
            return entry_price * (1.0 + c + s + m) / (1.0 - c)
        return entry_price * (1.0 - c - s - m) / (1.0 + c)

    def net_profit(
        self, direction: str, entry_price: float, exit_price: float, investment: float,
    ) -> float:
        """Net PnL in account currency after round-trip fees, slippage and spread."""
        c = self._cfg.fee_pct_per_side + self._cfg.slippage_pct_per_side
        qty = investment / entry_price
        sign = 1.0 if direction == "LONG" else -1.0
        gross = sign * qty * (exit_price - entry_price)
        cost = investment * (c + self._cfg.spread_pct) + qty * exit_price * c
        return gross - cost

    def label(
        self,
        *,
        direction: str,
        entry_price: float,
        entry_idx: int,
        highs: Sequence[float],
        lows: Sequence[float],
        range_high: float,
        range_low: float,
        investment: float,
        entity_id: str = "unnamed",
    ) -> Dict[str, Any]:
        """Scan bars (entry_idx, entry_idx + max_forward_bars] for max TP before SL."""
        direction = direction.upper()
        failures = self._validate_inputs(
            direction, entry_price, entry_idx, highs, lows, range_high, range_low, investment,
        )
        if failures:
            return self._report("REJECT", entity_id, {}, failures)

        sl = self.stop_loss(direction, range_high, range_low)
        if (direction == "LONG" and sl >= entry_price) or (direction == "SHORT" and sl <= entry_price):
            return self._report(
                "REJECT", entity_id, {"sl": sl},
                [f"SL {sl} not on loss side of entry {entry_price} for {direction}"],
            )

        tp_max, bars_to_tp, sl_hit_bar, bars_scanned = self._scan(
            direction, entry_price, entry_idx, highs, lows, sl,
        )
        tp_min = self.min_profitable_tp(direction, entry_price)
        risk = abs(entry_price - sl)
        reward = abs(tp_max - entry_price)
        net = self.net_profit(direction, entry_price, tp_max, investment)

        metrics = {
            "direction":        direction,
            "entry_price":      entry_price,
            "sl":               sl,
            "tp_max":           tp_max,
            "tp_min_required":  tp_min,
            "rr":               reward / risk,
            "net_profit":       net,
            "net_return_pct":   net / investment,
            "net_loss_at_sl":   self.net_profit(direction, entry_price, sl, investment),
            "bars_to_tp":       bars_to_tp,
            "sl_hit_bar":       sl_hit_bar,
            "bars_scanned":     bars_scanned,
        }
        warnings: List[str] = []
        if bars_scanned < self._cfg.max_forward_bars and sl_hit_bar is None:
            warnings.append(f"Only {bars_scanned}/{self._cfg.max_forward_bars} forward bars available")

        reached = tp_max >= tp_min if direction == "LONG" else tp_max <= tp_min
        min_net = investment * self._cfg.min_net_return_pct
        if not reached or net <= min_net:
            return self._report(
                "REJECT", entity_id, metrics,
                [f"net_profit={net:.6f} at tp_max={tp_max} <= required {min_net:.6f} "
                 f"after round trip (tp_min={tp_min})"],
                warnings,
            )
        return self._report("APPROVE", entity_id, metrics, [], warnings)

    # ── Private ───────────────────────────────────────────────────────────

    def _scan(self, direction, entry_price, entry_idx, highs, lows, sl):
        """Return (tp_max, bars_to_tp, sl_hit_bar, bars_scanned)."""
        is_long = direction == "LONG"
        tp_max, bars_to_tp, sl_hit_bar = entry_price, None, None
        end = min(len(highs), entry_idx + 1 + self._cfg.max_forward_bars)
        bars_scanned = 0
        for i in range(entry_idx + 1, end):
            bars_scanned += 1
            k = i - entry_idx
            sl_hit = lows[i] <= sl if is_long else highs[i] >= sl
            if sl_hit and self._cfg.same_bar_policy == "sl_first":
                sl_hit_bar = k
                break
            extreme = highs[i] if is_long else lows[i]
            if (is_long and extreme > tp_max) or (not is_long and extreme < tp_max):
                tp_max, bars_to_tp = extreme, k
            if sl_hit:
                sl_hit_bar = k
                break
        return tp_max, bars_to_tp, sl_hit_bar, bars_scanned

    @staticmethod
    def _validate_inputs(direction, entry_price, entry_idx, highs, lows,
                         range_high, range_low, investment) -> List[str]:
        failures: List[str] = []
        if direction not in ("LONG", "SHORT"):
            failures.append(f"direction={direction!r} not in ('LONG', 'SHORT')")
        if entry_price <= 0 or investment <= 0:
            failures.append("entry_price and investment must be > 0")
        if range_high <= range_low:
            failures.append(f"range_high={range_high} <= range_low={range_low}")
        if len(highs) != len(lows):
            failures.append("highs and lows length mismatch")
        elif not 0 <= entry_idx < len(highs) - 1:
            failures.append(f"entry_idx={entry_idx} leaves no forward bars")
        return failures

    @staticmethod
    def _report(decision, entity_id, metrics, hard_failures, warnings=None) -> Dict[str, Any]:
        if decision == "REJECT":
            logger.debug("OptimalExit REJECT %s: %s", entity_id, hard_failures)
        return {
            "decision":      decision,
            "entity_id":     entity_id,
            "evaluated_at":  datetime.now(timezone.utc).isoformat(),
            "metrics":       metrics,
            "hard_failures": list(hard_failures),
            "warnings":      list(warnings or []),
        }
