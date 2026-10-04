"""
base_strategy.py
================================================================================
BaseStrategy — abstract base class for all 10 strategy modules (S1..S10).

Every concrete strategy:
  1. Subclasses BaseStrategy.
  2. Implements compute(features, candle) -> StrategyResult.
  3. Calls inherited helpers (_get_lot_size, _calc_sl_inr, _calc_tp_inr,
     _no_trade) instead of reimplementing INR risk math.
  4. Loads tunable params via from_prod_config() — no magic numbers.

Config section: "capital_management" in production JSON.
================================================================================
"""

from __future__ import annotations

import math
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Optional

# ── Path bootstrap (only needed when run as script) ──────────────────────────
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config_layer.production_config import get_prod_section   # type: ignore
from core.position_sizing import (                              # type: ignore
    SPEC_SECTION,
    has_instrument_spec,
    instrument_spec,
    size_trade_lots,
    usd_quote_pnl_inr,
)
from strategies.strategy_result import StrategyResult          # type: ignore
from utils.logging_config import get_flow_logger               # type: ignore

logger = get_flow_logger("STRATEGY_ENGINE")


# ── Config load ──────────────────────────────────────────────────────────────

def _load_capital_cfg() -> dict:
    cfg = get_prod_section("capital_management")
    if not cfg:
        raise RuntimeError(
            "capital_management section missing from production config. "
            "Add it to configs/production/v1_multi_2026_03.json."
        )
    return cfg


from config_layer.strict_config import require as _strict_require


def _require(cfg: dict, key: str) -> object:
    if key not in cfg:
        raise KeyError(
            f"Required key '{key}' missing from capital_management config section."
        )
    return cfg[key]


_CAPITAL_CFG = _load_capital_cfg()

_TOTAL_CAPITAL_INR: float   = float(_require(_CAPITAL_CFG, "total_capital_inr"))
_MAX_RISK_PER_TRADE: float  = float(_require(_CAPITAL_CFG, "max_risk_per_trade_inr"))
_PIP_VALUE_PER_LOT: dict    = dict(_require(_CAPITAL_CFG, "pip_value_per_lot"))
_USD_TO_INR_RATE: float     = float(_require(_CAPITAL_CFG, "usd_to_inr_rate"))
# F-115: broker contract facts (top-level section, declared per instrument). Optional as a
# whole: an instrument with no entry keeps the legacy FX pip path below.
_INSTRUMENT_SPECS: dict     = dict(get_prod_section(SPEC_SECTION) or {})


# ── BaseStrategy ─────────────────────────────────────────────────────────────

class BaseStrategy(ABC):
    """
    Abstract base for all 10 strategy modules.

    Parameters
    ----------
    pair        Instrument symbol (e.g. "EURUSD").
    timeframe   Candle timeframe string (e.g. "H1").
    config      Optional config override; if None, loads from production JSON.
    capital_inr Total capital in INR; defaults to production config value.
    """

    def __init__(
        self,
        pair: str,
        timeframe: str,
        config: Optional[dict] = None,
        capital_inr: float = _TOTAL_CAPITAL_INR,
    ) -> None:
        self.pair        = pair.upper().replace("/", "")  # normalise EUR/USD → EURUSD
        self.timeframe   = timeframe.upper()
        self.capital_inr = capital_inr
        self._cfg        = config or _CAPITAL_CFG
        self._pip_value  = self._resolve_pip_value(self.pair)
        # F-115: a declared broker spec sizes through core.position_sizing (the one
        # INR->lots bridge Ultron and CapitalCurve already use); None keeps legacy FX pip math.
        self._spec = (
            instrument_spec(_INSTRUMENT_SPECS, self.pair, consumer="BaseStrategy")
            if has_instrument_spec(_INSTRUMENT_SPECS, self.pair) else None
        )

    # ── Abstract interface ────────────────────────────────────────────────────

    @abstractmethod
    def compute(self, features: dict, candle: dict) -> StrategyResult:
        """
        Evaluate the current candle + feature vector and return a StrategyResult.

        Parameters
        ----------
        features  35-dim canonical feature dict from FeaturePipeline.
        candle    Raw OHLCV dict: {open, high, low, close, volume, timestamp}.

        Returns
        -------
        StrategyResult — always (use self._no_trade() when conditions not met).
        """

    @property
    @abstractmethod
    def strategy_id(self) -> str:
        """Return strategy code: "S1" .. "S10"."""

    # ── Shared calculation helpers (inherited by all strategies) ─────────────

    def _get_lot_size(self, sl_pips: float) -> float:
        """
        ATR-based position sizing: maximum lots before sl_inr exceeds cap.

        lot_size = max_risk_inr / (sl_pips × pip_value_usd × usd_to_inr)

        Returns 0.0 if sl_pips is zero or negative (safe default).
        """
        if sl_pips <= 0.0:
            return 0.0
        if self._spec is not None:
            # sl_pips == |entry - sl| * _pips_per_unit(); invert back to the price distance.
            lots, reason = size_trade_lots(
                _MAX_RISK_PER_TRADE, _USD_TO_INR_RATE,
                sl_pips / self._pips_per_unit(), **self._spec,
            )
            if lots is None:
                logger.debug("%s %s sizing rejected: %s", self.strategy_id, self.pair, reason)
                return 0.0
            return lots
        lot_size = _MAX_RISK_PER_TRADE / (sl_pips * self._pip_value * _USD_TO_INR_RATE)
        # FLOOR to the 0.01 step, never round-to-nearest: rounding up could risk MORE than
        # the cap (sl_inr > max -> StrategyResult.validate raised on ~half of signals).
        # Same policy as core.position_sizing.floor_to_lot_step. Epsilon guards exact steps.
        lot_size = math.floor(lot_size * 100.0 + 1e-9) / 100.0
        # Cap at 100 lots — sanity guard; realistic retail max is ~10 lots
        return min(lot_size, 100.0)

    def _calc_sl_inr(self, entry: float, sl: float, lot_size: float) -> float:
        """INR loss if SL is hit."""
        if self._spec is not None:
            return round(usd_quote_pnl_inr(
                abs(entry - sl), self._spec["contract_size"], lot_size, _USD_TO_INR_RATE), 2)
        sl_pips = abs(entry - sl) * self._pips_per_unit()
        return round(sl_pips * lot_size * self._pip_value * _USD_TO_INR_RATE, 2)

    def _calc_tp_inr(self, entry: float, tp: float, lot_size: float) -> float:
        """INR gain if TP is hit."""
        if self._spec is not None:
            return round(usd_quote_pnl_inr(
                abs(tp - entry), self._spec["contract_size"], lot_size, _USD_TO_INR_RATE), 2)
        tp_pips = abs(tp - entry) * self._pips_per_unit()
        return round(tp_pips * lot_size * self._pip_value * _USD_TO_INR_RATE, 2)

    def _calc_roi(self, entry: float, tp: float, fill_fraction: float = 1.0) -> float:
        """
        Expected ROI as a percentage of capital deployed.

        fill_fraction: 0.4 = conservative (40% of TP distance), 1.0 = full TP.
        """
        if entry <= 0.0:
            return 0.0
        move = abs(tp - entry) * fill_fraction
        return round((move / entry) * 100.0, 2)

    def _no_trade(self, regime: str = "UNKNOWN") -> StrategyResult:
        """Standard NO_TRADE return — call when conditions are not met."""
        return StrategyResult.no_trade(
            strategy_id=self.strategy_id,
            pair=self.pair,
            timeframe=self.timeframe,
            regime=regime,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _resolve_pip_value(self, pair: str) -> float:
        """USD pip value per standard lot for the given pair."""
        value = _PIP_VALUE_PER_LOT.get(pair)
        if value is None:
            return float(_strict_require(
                _CAPITAL_CFG, "unknown_pair_pip_value",
                section_name="capital_management", consumer="BaseStrategy",
            ))
        return float(value)

    def _pips_per_unit(self) -> float:
        """
        Converts price unit to pips.
        JPY pairs: 1 pip = 0.01 price unit → multiply price diff by 100.
        All others: 1 pip = 0.0001 price unit → multiply price diff by 10,000.
        """
        return 100.0 if self.pair.endswith("JPY") else 10_000.0

    @staticmethod
    def _atr_price(features: dict, close: float) -> float:
        """ATR in PRICE units, for SL/TP/range distances.

        The canonical ``atr`` feature (FM-041) is CLOSE-RELATIVE (atr_14_raw / close);
        a price distance needs FM-074 ``atr_absolute`` = ``atr * close`` -- the same
        recovery ``execution_planner`` and ``gate_intelligence`` already use (F-072/F-109).
        Using the relative value as a distance put a gold stop ~$0.0007 from entry (F-115).
        Ratio denominators against other canonical features must keep the relative ``atr``.
        """
        return float(features.get("atr", 0.0)) * close

    def _sl_pips(self, entry: float, sl: float) -> float:
        return abs(entry - sl) * self._pips_per_unit()

    def _tp_pips(self, entry: float, tp: float) -> float:
        return abs(tp - entry) * self._pips_per_unit()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.strategy_id} | {self.pair} {self.timeframe})"
