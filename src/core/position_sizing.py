"""
position_sizing.py
==================
CANONICAL NAMING:
  ``size_trade_lots`` (THIS FILE) = THE SIZING BRIDGE. The ONE place where a risk
  budget expressed in the account's DEPOSIT CURRENCY (INR — user lock 2026-09-30)
  becomes a broker-legal LOT size. Ultron's ``final_position_size``, the live hook's
  ``position_size_hint`` and the backtest ``CapitalCurve`` all call it, so the three
  rails cannot disagree in units.

Why this module exists (D11, verified 2026-09-30)
-------------------------------------------------
Before this module the size was ``risk_usd / |entry - sl|`` — INSTRUMENT UNITS
(ounces for XAUUSD) — and that number was handed to MT5 as ``lot_size`` with no
contract conversion, on an account whose deposit currency is INR:

  * ``src/core/ultron_risk_gate.py`` Check 7 produced it (``final_position_size``),
  * ``src/runtime/live_engine_hook.py:1114`` produced a second copy for
    ``position_size_hint``,
  * ``src/runtime/backtest_v2.py`` ``CapitalCurve`` booked ``price_move × units``
    into an INR-labelled capital curve (implicitly 1 USD = 1 INR).

XAUUSD's broker contract is **100 oz per lot** (measured: the repo's own MT5 cost
calibration records ``contract_size: 100.0``), so every emitted size was ~100x
oversized, and the only thing bounding it was ``MT5Bridge``'s ``lot_max`` clamp.

Contract
--------
``size_trade_lots`` is deliberately arithmetic-only: it takes every broker fact as an
argument and returns ``(lots, None)`` or ``(None, reason)``. It performs NO price
arithmetic (no ``abs(entry - sl)``) and reads NO config — callers resolve the declared
values (instrument spec + USD/INR rate) and pass the stop distance in.

Broker facts are declared in the top-level ``instrument_specs`` config section
(parallel to ``capital_management``); the USD/INR rate is REUSED from the already
declared ``capital_management.usd_to_inr_rate`` — never re-declared here.

Rounding policy: FLOOR, never round. A size below the broker minimum is a REJECT with
reason ``size_below_min_lot`` (user decision 2026-09-30), never a rounded-up risk.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from config_layer.strict_config import ConfigKeyMissingError

__all__ = [
    "INSTRUMENT_SPEC_KEYS",
    "REASON_SIZE_BELOW_MIN_LOT",
    "SPEC_SECTION",
    "USD_INR_RATE_KEY",
    "USD_INR_RATE_SECTION",
    "floor_to_lot_step",
    "has_instrument_spec",
    "instrument_spec",
    "legacy_oz_size_units",
    "size_trade_lots",
    "usd_quote_pnl_inr",
]

#: Reject reason for a risk budget that cannot buy the broker's minimum lot.
REASON_SIZE_BELOW_MIN_LOT = "size_below_min_lot"

#: The four broker facts every instrument spec must declare.
INSTRUMENT_SPEC_KEYS: tuple[str, ...] = (
    "contract_size",   # units (oz for metals, base-currency units for FX) per lot
    "lot_step",        # broker volume step
    "lot_min",         # broker minimum volume
    "lot_max",         # broker maximum volume
)

#: Where the spec lives / where the rate is REUSED from (never re-declared).
SPEC_SECTION = "instrument_specs"
USD_INR_RATE_SECTION = "capital_management"
USD_INR_RATE_KEY = "usd_to_inr_rate"


def floor_to_lot_step(lots: float, lot_step: float) -> float:
    """Largest multiple of ``lot_step`` that does not exceed ``lots``.

    The broker's volume grid is a floor, never a round: 0.0299 lots at a 0.01 step is
    0.02 lots, NOT 0.03. ``math.floor`` (not ``round``) is load-bearing — ``round``
    would round half-away-from-zero and could risk MORE than the budget.
    """
    return math.floor(lots / lot_step) * lot_step


def size_trade_lots(
    risk_capital_inr: float,
    usd_inr_rate: float,
    price_risk_distance: float,
    contract_size: float,
    lot_step: float,
    lot_min: float,
    lot_max: float,
) -> tuple[float | None, str | None]:
    """Convert an INR risk budget into a broker-legal LOT size.

    Parameters
    ----------
    risk_capital_inr : float
        Risk budget in the account's DEPOSIT currency (INR). Callers compute it as
        ``balance_inr × risk_percent / 100`` (Ultron, live hook) or
        ``CapitalCurve.current_risk_amount`` (backtest).
    usd_inr_rate : float
        Declared ``capital_management.usd_to_inr_rate``. XAUUSD is USD-quoted, so the
        risk budget must be converted before it faces a USD price distance.
    price_risk_distance : float
        ``|entry - stop_loss|`` in PRICE units, computed BY THE CALLER (this module
        performs no price arithmetic).
    contract_size : float
        Units of the instrument per 1.00 lot (XAUUSD: 100 oz).
    lot_step, lot_min, lot_max : float
        Broker volume grid, minimum and maximum.

    Returns
    -------
    (lots, None)   on success — ``lots`` is already on the broker's step grid and
                   clamped to ``lot_max``.
    (None, reason) when the risk budget cannot buy ``lot_min``; the caller REJECTS the
                   trade (reason ``size_below_min_lot``). Callers must never substitute
                   a default size.

    Preconditions (owned by the CALLERS' guards)
    -------------------------------------------
    Positive ``usd_inr_rate``, ``price_risk_distance``, ``contract_size`` and
    ``lot_step``. Ultron rejects ``risk_per_unit == 0`` in its Check 6; the live hook
    guards ``risk_dist > 0``; the spec values come from the declared
    ``instrument_specs`` section. Kept out of this function on purpose so that the
    sizing math has exactly two outcomes.
    """
    risk_usd = risk_capital_inr / usd_inr_rate
    size_units = risk_usd / price_risk_distance
    lots = floor_to_lot_step(size_units / contract_size, lot_step)
    if lots < lot_min:
        return (None, REASON_SIZE_BELOW_MIN_LOT)
    return (min(lots, lot_max), None)


def instrument_spec(
    instrument_specs: Mapping | None,
    instrument: str,
    *,
    consumer: str = "position_sizing",
) -> dict[str, Any]:
    """STRICT: the declared broker spec for ``instrument``.

    Raises ``ConfigKeyMissingError`` — naming the exact key — when the section is
    absent, the instrument is undeclared, or one of :data:`INSTRUMENT_SPEC_KEYS` is
    missing. There is no default table and no fallback: an undeclared instrument fails
    closed on the live rail, or takes the explicitly-stamped legacy path on the
    backtest rail.
    """
    if not isinstance(instrument_specs, Mapping) or instrument not in instrument_specs:
        raise ConfigKeyMissingError(
            [instrument or "<instrument>"],
            section=SPEC_SECTION, consumer=consumer,
        )
    spec = instrument_specs[instrument]
    if not isinstance(spec, Mapping):
        raise TypeError(
            f"{SPEC_SECTION}.{instrument} must be a mapping, got {type(spec).__name__}"
        )
    missing = [k for k in INSTRUMENT_SPEC_KEYS if k not in spec]
    if missing:
        raise ConfigKeyMissingError(
            [f"{instrument}.{k}" for k in missing], section=SPEC_SECTION, consumer=consumer,
        )
    return {k: spec[k] for k in INSTRUMENT_SPEC_KEYS}


def has_instrument_spec(instrument_specs: Mapping | None, instrument: str) -> bool:
    """True when a COMPLETE spec is declared for ``instrument``.

    Used by the backtest rail to choose its basis explicitly and loudly: a declared
    instrument sizes in lots on an INR-money curve; an undeclared one keeps the pre-D11
    ounce math and is stamped ``legacy_oz`` (decision 2026-09-30, option B).
    """
    try:
        instrument_spec(instrument_specs, instrument, consumer="has_instrument_spec")
    except (ConfigKeyMissingError, TypeError):
        return False
    return True


def legacy_oz_size_units(risk_capital_inr: float, price_risk_distance: float) -> float:
    """The PRE-D11 sizing math, retained ONLY for the backtest rail.

    ``risk_amount / price_distance`` in instrument units, booked into an INR-labelled
    curve as if 1 USD = 1 INR. This is the defect F-110 describes; it survives here
    only so that instruments with no declared ``instrument_specs`` entry keep producing
    byte-identical ledgers instead of silently changing basis. The backtest stamps
    ``sizing_basis: "legacy_oz"`` on the run and logs a WARNING.

    NEVER call this from the live rail.
    """
    return risk_capital_inr / price_risk_distance


def usd_quote_pnl_inr(
    price_move_usd_per_unit: float,
    contract_size: float,
    lots: float,
    usd_inr_rate: float,
) -> float:
    """INR money from a USD-quoted price move.

    ``USD/unit × units/lot × lots × INR/USD``. One identity, one place: the live rail
    and the backtest rail derive money the same way, so a booked P&L can never again be
    ounces × dollars labelled INR.

    Applies to USD-QUOTED instruments (XAUUSD, and the USD-quoted FX majors). A
    non-USD-quoted pair (USDJPY/USDCHF/USDCAD) would need ITS quote currency's INR rate
    — declared nowhere — so those instruments must not be routed here.
    """
    return price_move_usd_per_unit * contract_size * lots * usd_inr_rate

