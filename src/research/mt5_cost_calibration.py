"""
mt5_cost_calibration
================================================================================
READ-ONLY MT5 broker cost extraction for XAUUSD (ZONE-X programme, item O-1).

ZONE-X (external spec, `ZONE-X-SPEC-v0.8.md`, not part of the Tradelatest governed
pipeline) assumed a round-trip trading cost of `c = 0.07 ATR/side` ($0.51/oz/side
at the spec's own test-year median ATR) and flagged that number as NEVER VERIFIED
and now BLOCKING (spec §8). This module pulls the four real components from a
locally running MT5 terminal so `c` stops being an estimate:

  1. spread (ask - bid), tick-level, aggregated by hour-of-day (UTC)
  2. commission per lot per side, from real historical deal records
  3. slippage (requested vs filled price), split by order type -- STOP orders
     are the metric that matters here, since every ZONE-X barrier is a stop
     order and the spec measured 29% of bars gapping from the prior close
  4. swap/rollover, from the symbol's contract spec

Authority: RESEARCH_ONLY. Standalone diagnostic -- does not touch production
config, ACTIVE_VERSION, the promotion pipeline, or any governed engine.

Never fabricates a number: every quantity carries an explicit `Status` --
MEASURED / INSUFFICIENT_DATA / UNKNOWN. Commission and stop-order slippage need
real trade history the account may not have yet; those degrade honestly instead
of silently defaulting to 0. See `docs/governance/EPISTEMIC_INTEGRITY.md`'s
"write UNKNOWN, never invent" doctrine (this module is outside that governance
tree but follows the same discipline by request).

Never persists account identity/balance. `account_info()` is read transiently
only, to check the account's profit currency for the swap $-conversion --
matches the `FORBIDDEN_KEYS = ("balance","equity","margin","login","server")`
no-persist rule enforced by `tests/manual/live_smoke.py`.

Requirements:
  * `pip install MetaTrader5` (Windows-only; not installed in venv/.venv as of
    this module's authoring -- confirmed via a site-packages check).
  * The MT5 desktop terminal RUNNING and LOGGED IN (the API attaches over IPC).
  * For items 2/3 (commission, stop slippage): the account needs real trade
    history. A fresh demo has none -- see `extract_commission`/`extract_slippage`
    docstrings for the minimal-effort manual path to populate it.

This module never places or modifies orders -- strictly read-only, same
posture as `mt5_analytics/core/mt5_adapter.py`, which it reuses (via
composition, not modification) for the MT5 connection lifecycle and the
broker-server-clock-to-UTC offset correction.

CLI entry point: scripts/research/xauusd_mt5_cost_calibration.py
================================================================================
"""
from __future__ import annotations

# ── 1. Standard library ───────────────────────────────────────────────────────
import datetime as _dt
import logging
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

# ── 2. Path bootstrap (when run as a script / imported standalone) ────────────
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ── 3. Logger ─────────────────────────────────────────────────────────────────
logger = logging.getLogger("mt5_cost_calibration")

# ── 4. Optional dependencies (fail-soft import; fail-fast at use) ─────────────
try:
    import MetaTrader5 as mt5  # type: ignore
    _MT5_AVAILABLE = True
except Exception:  # pragma: no cover - exercised only when the wheel is absent
    mt5 = None  # type: ignore
    _MT5_AVAILABLE = False

try:
    import numpy as np
    import pandas as pd
    _PANDAS_AVAILABLE = True
except Exception:  # pragma: no cover
    np = None  # type: ignore
    pd = None  # type: ignore
    _PANDAS_AVAILABLE = False

from mt5_analytics.core.mt5_adapter import MT5Adapter  # noqa: E402


def _require_mt5() -> None:
    if not _MT5_AVAILABLE or mt5 is None:
        raise RuntimeError(
            "MetaTrader5 package not installed. Run: pip install MetaTrader5"
        )


# ── 5. Status enum (never-fabricate contract) ──────────────────────────────────

class Status(str, Enum):
    """Every extracted quantity carries one of these -- never a silently
    invented number. Severity for `compute_c_per_side`'s worst-of: MEASURED <
    INSUFFICIENT_DATA < UNKNOWN."""

    MEASURED = "MEASURED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    UNKNOWN = "UNKNOWN"


_SEVERITY = {Status.MEASURED: 0, Status.INSUFFICIENT_DATA: 1, Status.UNKNOWN: 2}


def _worst(*statuses: Status) -> Status:
    return max(statuses, key=lambda s: _SEVERITY[s])


# ── 6. Config dataclass ─────────────────────────────────────────────────────────

@dataclass
class CostCalibrationConfig:
    """Value object for a cost-calibration run. No silent defaults on anything
    that changes the economic answer -- only operational knobs get defaults."""

    symbol: str = "XAUUSD"
    tick_lookback_days: int = 14
    history_lookback_days: int = 90
    tick_chunk_days: int = 1
    min_stop_fills_for_confidence: int = 5   # reporting hint only -- NEVER a silent gate
    out_dir: Path = field(
        default_factory=lambda: _ROOT / "results" / "research" / "xauusd_mt5_cost_calibration"
    )
    server_utc_offset_hours: Optional[float] = None


# ── 7. MT5CostReader -- composition sibling to MT5Adapter ─────────────────────
#
# MT5Adapter (mt5_analytics/core/mt5_adapter.py) exposes exactly five read
# calls by design -- it is the frozen read-surface of an audited kernel with
# its own migration log. Rather than widen that contract for an unrelated,
# one-off research need, MT5CostReader wraps an already-`__enter__`-ed
# MT5Adapter and reads its PUBLIC `server_utc_offset` attribute to add the two
# calls cost calibration needs: copy_ticks_range and symbol_info. This reuses
# the hard part (offset detection) with zero duplication and zero risk to the
# adapter -- `mt5a._shift` (protected) is never touched.

class MT5CostReader:
    """Read-only wrapper adding `copy_ticks_range_chunked` + `symbol_info` on
    top of an already-connected `MT5Adapter`. Composition, not subclassing --
    `mt5_analytics/core/mt5_adapter.py` is never modified."""

    def __init__(self, mt5a: MT5Adapter) -> None:
        _require_mt5()
        self._mt5a = mt5a

    def _shift(self, d: _dt.datetime) -> _dt.datetime:
        """UTC datetime -> server-time datetime, mirroring MT5Adapter._shift
        via the adapter's public `server_utc_offset` (seconds)."""
        return d + _dt.timedelta(seconds=self._mt5a.server_utc_offset)

    def copy_ticks_range_chunked(
        self,
        symbol: str,
        date_from: _dt.datetime,
        date_to: _dt.datetime,
        *,
        chunk_days: int = 1,
    ) -> list[dict]:
        """Tick history for UTC [date_from, date_to), chunked by `chunk_days`
        to bound per-call IPC/memory cost. Keeps only valid quote ticks
        (bid > 0 and ask > 0 and ask >= bid) -- filtering on raw field values
        rather than TICK_FLAG bits, since MT5 always carries the current
        bid/ask pair on every tick even when only one side just changed;
        flag-bit filtering would systematically undercount valid ticks.
        `time` is normalized to true UTC via the adapter's offset. A chunk
        returning None/empty (weekend, market closed) is skipped, not an
        error -- only a fully empty window escalates to INSUFFICIENT_DATA at
        the caller."""
        off = self._mt5a.server_utc_offset
        out: list[dict] = []
        cursor = date_from
        step = _dt.timedelta(days=max(1, chunk_days))
        while cursor < date_to:
            chunk_end = min(cursor + step, date_to)
            raw = mt5.copy_ticks_range(
                symbol, self._shift(cursor), self._shift(chunk_end), mt5.COPY_TICKS_ALL
            )
            if raw is not None and len(raw):
                for t in raw:
                    bid = float(t["bid"])
                    ask = float(t["ask"])
                    if bid > 0 and ask > 0 and ask >= bid:
                        out.append(
                            {
                                "time": int(t["time"]) - off,
                                "bid": bid,
                                "ask": ask,
                            }
                        )
            cursor = chunk_end
        return out

    def symbol_info(self, symbol: str) -> dict:
        """Contract-spec fields for `symbol` (swap, contract size, point, ...)
        as a plain dict. `{}` if the broker doesn't know the symbol."""
        info = mt5.symbol_info(symbol)
        if info is None:
            return {}
        return dict(info._asdict())


# ── 8. Result dataclasses (each carries a `status`) ────────────────────────────

@dataclass
class SpreadResult:
    status: Status
    hourly: Any                       # pandas.DataFrame: hour_utc,n_ticks,median,p90,mean (or None)
    overall_median_usd: Optional[float]
    overall_p90_usd: Optional[float]
    n_ticks_total: int
    window: tuple[str, str]
    note: str = ""


@dataclass
class CommissionResult:
    status: Status
    per_lot_per_side_usd: dict            # _stats()-shaped: n/mean/p50/p10/p90
    per_oz_usd: dict                      # same, divided by contract_size
    n_positions: int
    n_positions_with_commission: int
    commission_form_observed: Optional[str]   # "case_b_separate" | "case_c_folded" | "mixed" | None
    window: tuple[str, str]
    note: str = ""


@dataclass
class SlippageResult:
    status: Status
    by_order_type: dict                   # {"MARKET": {...}, "STOP": {...}, "LIMIT": {...}, "STOP_LIMIT": {...}}
    stop_slippage_median_usd: Optional[float]
    stop_status: Status = Status.UNKNOWN
    n_orders_joined: int = 0
    n_orders_unmatched: int = 0
    window: tuple[str, str] = ("", "")
    note: str = ""


@dataclass
class SwapResult:
    status: Status
    swap_mode_name: str
    swap_long_usd_per_oz: Optional[float]
    swap_short_usd_per_oz: Optional[float]
    contract_size: float
    point: float
    rollover3days_weekday: Optional[str]
    raw: dict
    note: str = ""


# ── 9. Small stats helper (mirrors scripts/research/xauusd_price_cost_trace.py::_stats) ──

def _stats(xs: list[float]) -> dict:
    if not _PANDAS_AVAILABLE:
        raise RuntimeError("pandas/numpy required for _stats()")
    a = np.asarray(xs, dtype=float)
    if a.size == 0:
        return {"n": 0}
    return {
        "n": int(a.size),
        "mean": float(a.mean()),
        "p50": float(np.median(a)),
        "p10": float(np.percentile(a, 10)),
        "p90": float(np.percentile(a, 90)),
        "min": float(a.min()),
        "max": float(a.max()),
    }


# ── 10. Extraction routines ─────────────────────────────────────────────────────

def extract_spread_by_hour(
    reader: MT5CostReader,
    symbol: str,
    date_from: _dt.datetime,
    date_to: _dt.datetime,
    *,
    chunk_days: int = 1,
) -> SpreadResult:
    """Ask-bid spread grouped by hour-of-day (UTC), median AND p90 per hour --
    the tail matters because that is where stop-order fills happen, not the
    advertised/mean figure. Needs no trade history -- ticks only."""
    _require_mt5()
    window = (date_from.isoformat(), date_to.isoformat())
    ticks = reader.copy_ticks_range_chunked(symbol, date_from, date_to, chunk_days=chunk_days)
    if not ticks:
        return SpreadResult(
            status=Status.INSUFFICIENT_DATA,
            hourly=None,
            overall_median_usd=None,
            overall_p90_usd=None,
            n_ticks_total=0,
            window=window,
            note=f"copy_ticks_range returned 0 valid quote ticks for {symbol} over the requested window.",
        )
    df = pd.DataFrame(ticks)
    df["spread"] = df["ask"] - df["bid"]
    df["hour_utc"] = pd.to_datetime(df["time"], unit="s", utc=True).dt.hour

    grouped = df.groupby("hour_utc")["spread"].agg(
        n_ticks="count", median_spread_usd="median", mean_spread_usd="mean",
        p90_spread_usd=lambda s: float(np.percentile(s, 90)),
    )
    hourly = grouped.reindex(range(24)).reset_index().rename(columns={"index": "hour_utc"})
    hourly["n_ticks"] = hourly["n_ticks"].fillna(0).astype(int)

    return SpreadResult(
        status=Status.MEASURED,
        hourly=hourly,
        overall_median_usd=float(df["spread"].median()),
        overall_p90_usd=float(np.percentile(df["spread"], 90)),
        n_ticks_total=int(len(df)),
        window=window,
    )


def extract_commission(
    mt5a: MT5Adapter,
    symbol: str,
    date_from: _dt.datetime,
    date_to: _dt.datetime,
) -> CommissionResult:
    """Commission per lot per side, from real historical deal records.

    Handles both broker forms observed in this repo's history
    (mt5_analytics/MIGRATIONS.md, 2026-06-26): commission folded onto each
    trade leg's own deal ("Case C", e.g. IC Markets Raw) and commission as a
    separate zero-volume deal ("Case B", documented but never yet observed
    live) -- summing `commission` across every deal in a position_id is
    correct under either form.

    `status = UNKNOWN` (not INSUFFICIENT_DATA) if the account has zero trade
    history, or every trade deal in the window shows commission == 0.0 --
    that is genuinely ambiguous (a real zero-commission account type, or a
    broker that just doesn't populate the field) and must not be reported as
    a confident $0.00.

    If this comes back UNKNOWN/INSUFFICIENT_DATA on a fresh demo: place a
    handful of small trades (any order type) and let them close, then rerun.
    """
    _require_mt5()
    window = (date_from.isoformat(), date_to.isoformat())
    deals = mt5a.history_deals_get(date_from, date_to)
    deals = [d for d in deals if d.get("symbol") == symbol]

    if not deals:
        return CommissionResult(
            status=Status.UNKNOWN,
            per_lot_per_side_usd={"n": 0},
            per_oz_usd={"n": 0},
            n_positions=0,
            n_positions_with_commission=0,
            commission_form_observed=None,
            window=window,
            note=f"No historical deals found for {symbol} in the requested window -- "
                 "account has no trade history yet for this symbol.",
        )

    by_position: dict[int, list[dict]] = {}
    for d in deals:
        by_position.setdefault(int(d.get("position_id", 0)), []).append(d)

    per_side_vals: list[float] = []
    per_lot_side_vals: list[float] = []
    n_with_commission = 0
    saw_case_b = False   # separate zero-volume commission deal
    saw_case_c = False   # commission folded onto a volume>0 leg

    for pid, pdeals in by_position.items():
        total_commission = sum(float(d.get("commission", 0.0)) for d in pdeals)
        n_sides = sum(1 for d in pdeals if float(d.get("volume", 0.0)) > 0)
        entry_volume = sum(
            float(d.get("volume", 0.0))
            for d in pdeals
            if d.get("entry") == mt5.DEAL_ENTRY_IN
        )
        for d in pdeals:
            comm = float(d.get("commission", 0.0))
            vol = float(d.get("volume", 0.0))
            if comm != 0.0:
                if vol == 0.0:
                    saw_case_b = True
                else:
                    saw_case_c = True
        if total_commission == 0.0:
            continue
        n_with_commission += 1
        if n_sides > 0:
            per_side_vals.append(total_commission / n_sides)
        if entry_volume > 0:
            per_lot_side_vals.append(total_commission / (2.0 * entry_volume))

    if n_with_commission == 0:
        return CommissionResult(
            status=Status.UNKNOWN,
            per_lot_per_side_usd={"n": 0},
            per_oz_usd={"n": 0},
            n_positions=len(by_position),
            n_positions_with_commission=0,
            commission_form_observed=None,
            window=window,
            note=f"{len(by_position)} closed position(s) found for {symbol}, but every deal shows "
                 "commission == 0.0. Could be a genuine zero-commission account, or the broker "
                 "simply doesn't populate this field -- treat as UNKNOWN, not $0.00. Cross-check "
                 "against the broker's contract-spec page.",
        )

    info = mt5.symbol_info(symbol)
    contract_size = float(info.trade_contract_size) if info is not None else 100.0

    per_lot_stats = _stats(per_lot_side_vals) if per_lot_side_vals else {"n": 0}
    per_oz_stats = (
        {k: (v / contract_size if k not in ("n",) else v) for k, v in per_lot_stats.items()}
        if per_lot_stats.get("n", 0) > 0
        else {"n": 0}
    )

    form = "mixed" if (saw_case_b and saw_case_c) else (
        "case_b_separate" if saw_case_b else ("case_c_folded" if saw_case_c else None)
    )

    return CommissionResult(
        status=Status.MEASURED,
        per_lot_per_side_usd=per_lot_stats,
        per_oz_usd=per_oz_stats,
        n_positions=len(by_position),
        n_positions_with_commission=n_with_commission,
        commission_form_observed=form,
        window=window,
    )


_MARKET_TYPE_NAMES = ("ORDER_TYPE_BUY", "ORDER_TYPE_SELL")
_STOP_TYPE_NAMES = ("ORDER_TYPE_BUY_STOP", "ORDER_TYPE_SELL_STOP")
_LIMIT_TYPE_NAMES = ("ORDER_TYPE_BUY_LIMIT", "ORDER_TYPE_SELL_LIMIT")
_STOP_LIMIT_TYPE_NAMES = ("ORDER_TYPE_BUY_STOP_LIMIT", "ORDER_TYPE_SELL_STOP_LIMIT")
_BUY_FAMILY_NAMES = ("ORDER_TYPE_BUY", "ORDER_TYPE_BUY_STOP", "ORDER_TYPE_BUY_LIMIT", "ORDER_TYPE_BUY_STOP_LIMIT")


def _order_type_classes() -> dict[str, set]:
    """Build the type-classification sets from LIVE mt5.ORDER_TYPE_* constants
    (never hardcoded ints -- exact enum values are broker/build sensitive)."""
    return {
        "MARKET": {getattr(mt5, n) for n in _MARKET_TYPE_NAMES},
        "STOP": {getattr(mt5, n) for n in _STOP_TYPE_NAMES},
        "LIMIT": {getattr(mt5, n) for n in _LIMIT_TYPE_NAMES},
        "STOP_LIMIT": {getattr(mt5, n) for n in _STOP_LIMIT_TYPE_NAMES},
    }


def extract_slippage(
    mt5a: MT5Adapter,
    symbol: str,
    date_from: _dt.datetime,
    date_to: _dt.datetime,
) -> SlippageResult:
    """Requested (order.price_open) vs filled (deal.price) price, split by
    order type. STOP is the metric ZONE-X actually needs: every barrier in
    that design is a stop order, and the spec measured 29% of bars gapping
    from the prior close -- so stops get jumped, not touched, and
    market-order slippage is the WRONG number for that use.

    `stop_status` is tracked separately from the overall `status` and goes
    INSUFFICIENT_DATA whenever zero STOP-order fills exist in the window,
    independent of whether market/limit slippage was measurable.

    A known unresolved ambiguity: some brokers rewrite a triggered
    STOP_LIMIT order's `type` field to the resulting LIMIT type once
    triggered, which would misclassify it out of the STOP-adjacent bucket.
    Not resolvable in the abstract -- can only be confirmed against this
    account's own triggered stop-limit records if/when any occur.

    If stop_status comes back INSUFFICIENT_DATA on a fresh demo: manually
    place ~8-12 small (0.01 lot) STOP orders in the terminal, staggered
    across a few trigger distances (e.g. 0.25x/0.5x/1.0x/2.0x current ATR),
    half BUY_STOP above market and half SELL_STOP below, and let natural
    volatility trigger a subset over a few days. Re-run with --skip-ticks to
    check accumulation cheaply. Caveat: near-market stops trigger faster but
    likely UNDERSTATE true gap-driven slippage relative to ZONE-X's actual
    wide, volatility-triggered barriers.
    """
    _require_mt5()
    window = (date_from.isoformat(), date_to.isoformat())
    orders = mt5a.history_orders_get(date_from, date_to)
    order_map = {int(o["ticket"]): o for o in orders if o.get("symbol") == symbol and "ticket" in o}
    deals = mt5a.history_deals_get(date_from, date_to)
    deals = [d for d in deals if d.get("symbol") == symbol]

    classes = _order_type_classes()
    buy_family = {getattr(mt5, n) for n in _BUY_FAMILY_NAMES}
    by_class: dict[str, list[float]] = {k: [] for k in classes}
    n_joined = 0
    n_unmatched = 0

    for d in deals:
        if d.get("entry") not in (mt5.DEAL_ENTRY_IN, mt5.DEAL_ENTRY_INOUT):
            continue
        order_ticket = int(d.get("order", 0))
        order = order_map.get(order_ticket)
        if order is None:
            n_unmatched += 1
            continue
        order_type = order.get("type")
        price_open = float(order.get("price_open", 0.0))
        deal_price = float(d.get("price", 0.0))
        if price_open <= 0 or deal_price <= 0:
            continue
        adverse = (deal_price - price_open) if order_type in buy_family else (price_open - deal_price)
        n_joined += 1
        for class_name, type_set in classes.items():
            if order_type in type_set:
                by_class[class_name].append(adverse)
                break

    by_order_type = {}
    for class_name, vals in by_class.items():
        s = _stats(vals) if vals else {"n": 0}
        by_order_type[class_name] = {
            "status": (Status.MEASURED if s.get("n", 0) > 0 else Status.INSUFFICIENT_DATA).value,
            **s,
        }

    n_stop = by_order_type["STOP"]["n"]
    stop_status = Status.MEASURED if n_stop > 0 else Status.INSUFFICIENT_DATA
    stop_median = by_order_type["STOP"].get("p50") if stop_status == Status.MEASURED else None

    overall_status = Status.MEASURED if n_joined > 0 else Status.INSUFFICIENT_DATA
    note = ""
    if stop_status != Status.MEASURED:
        note = (
            "Zero STOP-order fills in this window -- stop_slippage_median_usd is unavailable. "
            "Market/limit slippage above is NOT a substitute (ZONE-X's barriers are all stops, "
            "which get jumped on the 29% of bars that gap, unlike market fills)."
        )

    return SlippageResult(
        status=overall_status,
        by_order_type=by_order_type,
        stop_slippage_median_usd=stop_median,
        stop_status=stop_status,
        n_orders_joined=n_joined,
        n_orders_unmatched=n_unmatched,
        window=window,
        note=note,
    )


def extract_swap(reader: MT5CostReader, symbol: str, mt5a: MT5Adapter) -> SwapResult:
    """Swap/rollover per oz per night, long and short separately, from the
    symbol's contract spec (`symbol_info`). Needs no trade history.

    `swap_mode` is read live from mt5.SYMBOL_SWAP_MODE_* (never hardcoded --
    exact enum values are broker/build sensitive). POINTS and CURRENCY_SYMBOL
    modes are converted to $/oz/night, assuming the account's profit currency
    is USD (checked transiently via account_info()['currency'], never
    persisted). Percent/interest-based modes, or a non-USD account currency,
    go UNKNOWN with the raw fields dumped for manual conversion.
    """
    _require_mt5()
    info = reader.symbol_info(symbol)
    if not info:
        return SwapResult(
            status=Status.UNKNOWN,
            swap_mode_name="UNKNOWN",
            swap_long_usd_per_oz=None,
            swap_short_usd_per_oz=None,
            contract_size=0.0,
            point=0.0,
            rollover3days_weekday=None,
            raw={},
            note=f"mt5.symbol_info('{symbol}') returned None -- symbol not known to this broker "
                 "(check --symbol; broker gold naming varies, e.g. 'GOLD', 'XAUUSD.a').",
        )

    contract_size = float(info.get("trade_contract_size", 100.0))
    point = float(info.get("point", 0.0))
    swap_mode = info.get("swap_mode")
    swap_long_raw = float(info.get("swap_long", 0.0))
    swap_short_raw = float(info.get("swap_short", 0.0))

    weekday_names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    r3d = info.get("swap_rollover3days")
    rollover_name = weekday_names[int(r3d)] if isinstance(r3d, int) and 0 <= r3d <= 6 else None

    account = mt5a.account_info()   # transient only -- currency check, never persisted
    account_currency = account.get("currency")
    mode_name = "UNKNOWN"
    for name in (
        "SYMBOL_SWAP_MODE_DISABLED", "SYMBOL_SWAP_MODE_POINTS", "SYMBOL_SWAP_MODE_CURRENCY_SYMBOL",
        "SYMBOL_SWAP_MODE_CURRENCY_MARGIN", "SYMBOL_SWAP_MODE_CURRENCY_DEPOSIT",
        "SYMBOL_SWAP_MODE_INTEREST_CURRENT", "SYMBOL_SWAP_MODE_INTEREST_OPEN",
        "SYMBOL_SWAP_MODE_REOPEN_CURRENT", "SYMBOL_SWAP_MODE_REOPEN_BID",
    ):
        if hasattr(mt5, name) and swap_mode == getattr(mt5, name):
            mode_name = name
            break

    usd_ok = account_currency == "USD"
    long_oz = short_oz = None
    status = Status.UNKNOWN
    note = ""

    if mode_name == "SYMBOL_SWAP_MODE_POINTS" and usd_ok and point > 0:
        # swap_usd_per_lot_per_day = swap_points * point * contract_size;
        # per-oz divides by contract_size again -> contract_size cancels.
        long_oz = swap_long_raw * point
        short_oz = swap_short_raw * point
        status = Status.MEASURED
    elif mode_name == "SYMBOL_SWAP_MODE_CURRENCY_SYMBOL" and usd_ok and contract_size > 0:
        long_oz = swap_long_raw / contract_size
        short_oz = swap_short_raw / contract_size
        status = Status.MEASURED
    else:
        note = (
            f"swap_mode={mode_name!r} (or account currency {account_currency!r} != USD) is not a "
            "flat $/oz conversion this module handles -- raw fields dumped below for manual "
            "conversion per the broker's contract-spec page."
        )

    return SwapResult(
        status=status,
        swap_mode_name=mode_name,
        swap_long_usd_per_oz=long_oz,
        swap_short_usd_per_oz=short_oz,
        contract_size=contract_size,
        point=point,
        rollover3days_weekday=rollover_name,
        raw={"swap_long": swap_long_raw, "swap_short": swap_short_raw, "swap_mode": swap_mode},
        note=note,
    )


# ── 11. Combined c_per_side ─────────────────────────────────────────────────────

def compute_c_per_side(
    spread: SpreadResult, commission: CommissionResult, slippage: SlippageResult
) -> dict:
    """c_per_side = spread_median/2 + commission_per_oz(median) + stop_slippage_median.

    Status is the WORST of the three inputs -- never silently substitutes 0
    for a missing term. Uses slippage.stop_status (not the overall slippage
    status) since stop-order slippage is the quantity that matters here.
    """
    status = _worst(spread.status, commission.status, slippage.stop_status)
    if status != Status.MEASURED:
        blocked_by = []
        if spread.status != Status.MEASURED:
            blocked_by.append("spread")
        if commission.status != Status.MEASURED:
            blocked_by.append("commission")
        if slippage.stop_status != Status.MEASURED:
            blocked_by.append("stop_slippage")
        return {
            "status": status.value,
            "c_per_side_usd": None,
            "note": f"blocked: {', '.join(blocked_by)}",
        }

    # MT5 deal.commission is a signed cashflow (negative = debit/paid). Economic
    # cost per side is the absolute magnitude — never add the signed debit raw
    # or a -$0.04 commission would *reduce* reported c.
    commission_per_oz_median = float(commission.per_oz_usd.get("p50", 0.0) or 0.0)
    commission_cost = abs(commission_per_oz_median)
    half_spread = float(spread.overall_median_usd) / 2.0
    stop_slip = float(slippage.stop_slippage_median_usd)
    c = half_spread + commission_cost + stop_slip
    return {
        "status": Status.MEASURED.value,
        "c_per_side_usd": float(c),
        "components": {
            "half_spread_usd": half_spread,
            "commission_per_oz_usd": commission_cost,
            "commission_raw_signed_p50": commission_per_oz_median,
            "stop_slippage_usd": stop_slip,
        },
    }


# ── 12. ZONE-X spec citation constants (frozen, cited not recomputed) ───────────
# ZONE-X-SPEC-v0.8.md §3.2 -- MEASURED, test-year ATR14. Cited here so this
# module's $->ATR conversion never silently drifts from the frozen spec value;
# if the spec is ever re-cut/re-windowed, this citation is the thing to re-check.
ZONE_X_ATR14_MEDIAN_USD = 7.342
ZONE_X_ATR14_P10_USD = 3.467
ZONE_X_ATR14_P90_USD = 15.489
ZONE_X_SPEC_CITATION = "ZONE-X-SPEC-v0.8.md §3.2, frozen"
ZONE_X_C_007_USD_PER_SIDE = 0.51   # spec §8.1: c=0.07 ATR -> $/side at median ATR
ZONE_X_C_003_USD_PER_SIDE = 0.22   # spec §8.1: c=0.03 ATR -> $/side at median ATR
XAU_PROTOCOL_V1_USD_ROUND_TRIP = 0.40   # configs/research/xau_metals_protocol_v1.json, ~0.20/side


# ── 13. Output writers ──────────────────────────────────────────────────────────

def write_spread_csv(result: SpreadResult, out_dir: Path, ts: str) -> Optional[Path]:
    if result.hourly is None:
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"spread_by_hour_{ts}.csv"
    result.hourly.to_csv(path, index=False)
    (out_dir / "spread_by_hour_LATEST.csv").write_text(
        path.read_text(encoding="utf-8"), encoding="utf-8"
    )
    return path


def write_commission_json(result: CommissionResult, out_dir: Path, ts: str) -> Path:
    import json
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": result.status.value,
        "per_lot_per_side_usd": result.per_lot_per_side_usd,
        "per_oz_usd": result.per_oz_usd,
        "n_positions": result.n_positions,
        "n_positions_with_commission": result.n_positions_with_commission,
        "commission_form_observed": result.commission_form_observed,
        "window": result.window,
        "note": result.note,
    }
    path = out_dir / f"commission_{ts}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (out_dir / "commission_LATEST.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    return path


def write_slippage_csv(result: SlippageResult, out_dir: Path, ts: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for class_name, stats in result.by_order_type.items():
        rows.append({
            "order_type_class": class_name,
            "n_fills": stats.get("n", 0),
            "median_slippage_usd": stats.get("p50"),
            "p90_slippage_usd": stats.get("p90"),
            "status": stats.get("status"),
        })
    df = pd.DataFrame(rows)
    path = out_dir / f"slippage_by_order_type_{ts}.csv"
    df.to_csv(path, index=False)
    (out_dir / "slippage_by_order_type_LATEST.csv").write_text(
        path.read_text(encoding="utf-8"), encoding="utf-8"
    )
    return path


def write_swap_json(result: SwapResult, out_dir: Path, ts: str) -> Path:
    import json
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": result.status.value,
        "swap_mode_name": result.swap_mode_name,
        "swap_long_usd_per_oz": result.swap_long_usd_per_oz,
        "swap_short_usd_per_oz": result.swap_short_usd_per_oz,
        "contract_size": result.contract_size,
        "point": result.point,
        "rollover3days_weekday": result.rollover3days_weekday,
        "raw": result.raw,
        "note": result.note,
    }
    path = out_dir / f"swap_{ts}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (out_dir / "swap_LATEST.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def render_summary_md(
    spread: SpreadResult,
    commission: CommissionResult,
    slippage: SlippageResult,
    swap: SwapResult,
    c_per_side: dict,
    cfg: CostCalibrationConfig,
    ts: str,
) -> str:
    """Human summary mirroring scripts/research/xauusd_price_cost_trace.py's
    PRICE_COST_TRACE.md convention. Never prints a numeric headline for a
    quantity whose status != MEASURED -- prints the status literal instead."""

    def _fmt(val: Optional[float], status: Status, unit: str = "") -> str:
        if status != Status.MEASURED or val is None:
            return f"**{status.value}**"
        return f"**{val:.4f}{unit}**"

    lines = [
        "# XAUUSD MT5 Cost Calibration -- ZONE-X O-1",
        "",
        f"**Generated:** {ts}",
        f"**Symbol:** {cfg.symbol}",
        "**Authority:** RESEARCH_ONLY -- standalone diagnostic; grants no economic "
        "authority, does not touch production config or the promotion pipeline.",
        "",
        "## Four quantities",
        "",
        "| Quantity | Status | Value |",
        "|---|---|---|",
        f"| Spread (median, $/oz) | {spread.status.value} | "
        f"{_fmt(spread.overall_median_usd, spread.status)} |",
        f"| Spread (p90, $/oz) | {spread.status.value} | "
        f"{_fmt(spread.overall_p90_usd, spread.status)} |",
        f"| Commission ($/oz/side, median cost) | {commission.status.value} | "
        f"{_fmt(abs(commission.per_oz_usd['p50']) if commission.per_oz_usd.get('p50') is not None else None, commission.status)} |",
        f"| Stop-order slippage ($/oz, median) | {slippage.stop_status.value} | "
        f"{_fmt(slippage.stop_slippage_median_usd, slippage.stop_status)} |",
        f"| Swap long ($/oz/night) | {swap.status.value} | "
        f"{_fmt(swap.swap_long_usd_per_oz, swap.status)} |",
        f"| Swap short ($/oz/night) | {swap.status.value} | "
        f"{_fmt(swap.swap_short_usd_per_oz, swap.status)} |",
        "",
        "See `spread_by_hour_LATEST.csv` for the full 24-hour breakdown "
        "(median/p90/mean per UTC hour) and `slippage_by_order_type_LATEST.csv` "
        "for the MARKET/STOP/LIMIT/STOP_LIMIT breakdown.",
        "",
        "## c_per_side",
        "",
        "```",
        "c_per_side = spread_median/2 + commission_per_oz(median) + stop_slippage_median",
        "```",
        "",
    ]

    if c_per_side["status"] == Status.MEASURED.value:
        c = c_per_side["c_per_side_usd"]
        atr_median = c / ZONE_X_ATR14_MEDIAN_USD
        atr_p10 = c / ZONE_X_ATR14_P10_USD
        atr_p90 = c / ZONE_X_ATR14_P90_USD
        lines += [
            f"**c_per_side = ${c:.4f}/oz**",
            "",
            f"In ATR units (citing {ZONE_X_SPEC_CITATION}, not recomputed):",
            "",
            f"- at median ATR (${ZONE_X_ATR14_MEDIAN_USD}): **{atr_median:.4f} ATR**",
            f"- at p10 ATR (${ZONE_X_ATR14_P10_USD}, quiet): **{atr_p10:.4f} ATR**",
            f"- at p90 ATR (${ZONE_X_ATR14_P90_USD}, volatile): **{atr_p90:.4f} ATR**",
            "",
            "### vs the repo's own prior",
            "",
            f"`configs/research/xau_metals_protocol_v1.json` pre-registers "
            f"`usd_round_trip = {XAU_PROTOCOL_V1_USD_ROUND_TRIP}` "
            f"(~${XAU_PROTOCOL_V1_USD_ROUND_TRIP / 2:.2f}/side). Measured "
            f"${c:.4f}/side round-trips to **${2 * c:.4f}/oz** -- "
            + (
                "this validates the 0.40 prior (within a reasonable band)."
                if abs(2 * c - XAU_PROTOCOL_V1_USD_ROUND_TRIP) < 0.15
                else (
                    "the 0.40 prior looks TOO CONSERVATIVE (measured cost is higher)."
                    if 2 * c > XAU_PROTOCOL_V1_USD_ROUND_TRIP
                    else "the 0.40 prior looks TOO GENEROUS (measured cost is lower)."
                )
            ),
            "",
            "### vs ZONE-X §8.1's own thresholds",
            "",
            f"- ZONE-X assumed `c=0.07 ATR/side` = ${ZONE_X_C_007_USD_PER_SIDE}/side at median ATR.",
            f"- The alternative `c=0.03 ATR/side` = ${ZONE_X_C_003_USD_PER_SIDE}/side would cut the "
            "required directional edge fourfold (2.1pp -> 0.5pp).",
            f"- **Measured: ${c:.4f}/side** -- "
            + (
                f"closer to the c=0.03 case (directional gap ~0.5pp, programme should CONTINUE)."
                if c <= (ZONE_X_C_003_USD_PER_SIDE + ZONE_X_C_007_USD_PER_SIDE) / 2
                else f"closer to or above the c=0.07 case (directional gap ~2.1pp+, weak case to CONTINUE)."
            ),
            "",
        ]
    else:
        lines += [
            f"**c_per_side: {c_per_side['status']}** ({c_per_side.get('note', '')})",
            "",
        ]

    lines += [
        "## What's still unresolved and why",
        "",
    ]
    for name, res, extra in (
        ("Spread", spread, spread.note),
        ("Commission", commission, commission.note),
        ("Stop-order slippage", slippage, slippage.note),
        ("Swap", swap, swap.note),
    ):
        status_val = res.stop_status.value if name == "Stop-order slippage" else res.status.value
        if status_val != Status.MEASURED.value and extra:
            lines.append(f"- **{name}** ({status_val}): {extra}")
    if all(
        s == Status.MEASURED.value
        for s in (spread.status.value, commission.status.value, slippage.stop_status.value, swap.status.value)
    ):
        lines.append("- Nothing outstanding -- all four quantities MEASURED.")
    lines.append("")

    return "\n".join(lines)
