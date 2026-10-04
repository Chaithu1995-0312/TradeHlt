"""live_rail config. Nested ``_require`` — no silent defaults. Not on ACTIVE_VERSION."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config_layer.production_config import get_prod_section
from inout.live_rail.types import ClockBasis, DataVenue, OrderVenue

_TF_SECONDS = {
    "M1": 60,
    "M5": 300,
    "M15": 900,
    "M30": 1800,
    "H1": 3600,
    "H4": 14400,
    "D1": 86400,
}

_VOLUME_MODES = frozenset({"sum_size", "tick_count"})


def _require(cfg: dict, key: str, *, where: str = "live_rail") -> Any:
    if key not in cfg:
        raise KeyError(
            f"Required config key '{key}' missing from {where}. "
            "Add it to the production JSON live_rail section (no silent default)."
        )
    return cfg[key]


def _tf_seconds(timeframe: str) -> int:
    if timeframe not in _TF_SECONDS:
        raise KeyError(f"live_rail.timeframe={timeframe!r} is not in {_TF_SECONDS}")
    return _TF_SECONDS[timeframe]


@dataclass(frozen=True)
class TickDBCfg:
    path: str
    speed_mult: float
    require_clock_record: bool

    @classmethod
    def from_dict(cls, d: dict) -> "TickDBCfg":
        w = "live_rail.tickdb"
        return cls(
            path=str(_require(d, "path", where=w)),
            speed_mult=float(_require(d, "speed_mult", where=w)),
            require_clock_record=bool(_require(d, "require_clock_record", where=w)),
        )


@dataclass(frozen=True)
class BinanceCfg:
    ws_base: str
    streams: list[str]
    max_quote_age_ms: int
    heartbeat_s: float

    @classmethod
    def from_dict(cls, d: dict) -> "BinanceCfg":
        w = "live_rail.binance"
        return cls(
            ws_base=str(_require(d, "ws_base", where=w)),
            streams=list(_require(d, "streams", where=w)),
            max_quote_age_ms=int(_require(d, "max_quote_age_ms", where=w)),
            heartbeat_s=float(_require(d, "heartbeat_s", where=w)),
        )


@dataclass(frozen=True)
class BarBuilderCfg:
    emit_incomplete_on_stop: bool
    volume_mode: str

    @classmethod
    def from_dict(cls, d: dict) -> "BarBuilderCfg":
        w = "live_rail.bar_builder"
        flag = bool(_require(d, "emit_incomplete_on_stop", where=w))
        if flag:
            raise ValueError("bar_builder.emit_incomplete_on_stop must be false")
        if "timeframe_seconds" in d:
            raise KeyError(
                "live_rail.bar_builder.timeframe_seconds is derived from live_rail.timeframe "
                "— do not declare it independently (disagreement is a split-brain)."
            )
        mode = str(_require(d, "volume_mode", where=w))
        if mode not in _VOLUME_MODES:
            raise ValueError(f"live_rail.bar_builder.volume_mode={mode!r} not in {_VOLUME_MODES}")
        return cls(emit_incomplete_on_stop=flag, volume_mode=mode)


@dataclass(frozen=True)
class ReconnectCfg:
    base_delay_s: float
    max_delay_s: float
    max_attempts: int
    fail_count_disable: int

    @classmethod
    def from_dict(cls, d: dict) -> "ReconnectCfg":
        w = "live_rail.reconnect"
        return cls(
            base_delay_s=float(_require(d, "base_delay_s", where=w)),
            max_delay_s=float(_require(d, "max_delay_s", where=w)),
            max_attempts=int(_require(d, "max_attempts", where=w)),
            fail_count_disable=int(_require(d, "fail_count_disable", where=w)),
        )


@dataclass(frozen=True)
class OrderManagerCfg:
    enabled: bool
    default_order_type: str
    fill_timeout_s: float
    allow_partial: bool
    allow_lot_clamp: bool

    @classmethod
    def from_dict(cls, d: dict) -> "OrderManagerCfg":
        w = "live_rail.order_manager"
        return cls(
            enabled=bool(_require(d, "enabled", where=w)),
            default_order_type=str(_require(d, "default_order_type", where=w)),
            fill_timeout_s=float(_require(d, "fill_timeout_s", where=w)),
            allow_partial=bool(_require(d, "allow_partial", where=w)),
            allow_lot_clamp=bool(_require(d, "allow_lot_clamp", where=w)),
        )


@dataclass(frozen=True)
class PortfolioCfg:
    paper_balance: float

    @classmethod
    def from_dict(cls, d: dict) -> "PortfolioCfg":
        return cls(paper_balance=float(_require(d, "paper_balance", where="live_rail.portfolio")))


@dataclass(frozen=True)
class QueuesCfg:
    tick_maxsize: int
    bar_maxsize: int

    @classmethod
    def from_dict(cls, d: dict) -> "QueuesCfg":
        w = "live_rail.queues"
        if "report_maxsize" in d:
            raise KeyError("live_rail.queues.report_maxsize removed — no report_queue")
        return cls(
            tick_maxsize=int(_require(d, "tick_maxsize", where=w)),
            bar_maxsize=int(_require(d, "bar_maxsize", where=w)),
        )


@dataclass(frozen=True)
class LiveRailConfig:
    enabled: bool
    dry_run: bool
    auto_execute: bool
    data_venue: DataVenue
    order_venue: OrderVenue
    symbol: str
    timeframe: str
    timeframe_seconds: int
    clock_basis: ClockBasis
    hook_submit_orders: bool
    account_balance_source: str
    tickdb: TickDBCfg
    binance: BinanceCfg
    bar_builder: BarBuilderCfg
    reconnect: ReconnectCfg
    order_manager: OrderManagerCfg
    portfolio: PortfolioCfg
    queues: QueuesCfg
    longport_enabled: bool

    @classmethod
    def from_prod_config(cls, prod_cfg: dict | None = None) -> "LiveRailConfig":
        section = prod_cfg if prod_cfg is not None else get_prod_section("live_rail")
        if not isinstance(section, dict) or not section:
            raise RuntimeError("live_rail section missing — refuse to start (fail-fast).")
        tf = str(_require(section, "timeframe"))
        return cls(
            enabled=bool(_require(section, "enabled")),
            dry_run=bool(_require(section, "dry_run")),
            auto_execute=bool(_require(section, "auto_execute")),
            data_venue=DataVenue(str(_require(section, "data_venue"))),
            order_venue=OrderVenue(str(_require(section, "order_venue"))),
            symbol=str(_require(section, "symbol")),
            timeframe=tf,
            timeframe_seconds=_tf_seconds(tf),
            clock_basis=ClockBasis(str(_require(section, "clock_basis"))),
            hook_submit_orders=bool(_require(section, "hook_submit_orders")),
            account_balance_source=str(_require(section, "account_balance_source")),
            tickdb=TickDBCfg.from_dict(dict(_require(section, "tickdb"))),
            binance=BinanceCfg.from_dict(dict(_require(section, "binance"))),
            bar_builder=BarBuilderCfg.from_dict(dict(_require(section, "bar_builder"))),
            reconnect=ReconnectCfg.from_dict(dict(_require(section, "reconnect"))),
            order_manager=OrderManagerCfg.from_dict(dict(_require(section, "order_manager"))),
            portfolio=PortfolioCfg.from_dict(dict(_require(section, "portfolio"))),
            queues=QueuesCfg.from_dict(dict(_require(section, "queues"))),
            longport_enabled=bool(
                _require(
                    dict(_require(section, "longport")),
                    "enabled",
                    where="live_rail.longport",
                )
            ),
        )

    def assert_safe_to_start(self) -> None:
        if self.data_venue is DataVenue.LONGPORT or self.longport_enabled:
            raise RuntimeError("LongPort adapter is a stub — refuse to start")
        if self.data_venue is DataVenue.BINANCE and self.symbol.upper() == "XAUUSD":
            raise RuntimeError(
                "Binance data_venue cannot feed XAUUSD. Use tickdb or mt5_candles."
            )
        if self.hook_submit_orders and self.order_manager.enabled:
            raise RuntimeError(
                "XOR violated: hook_submit_orders and order_manager.enabled both true"
            )
        if not self.dry_run and self.auto_execute:
            raise RuntimeError("Refusing live auto-execute at config load.")
        if self.order_venue is OrderVenue.MT5:
            raise RuntimeError(
                "order_venue=mt5 is factory-unreachable in this design. "
                "MT5VenueExecutor is isolation-tested only (PR-3). "
                "A later authorized turn may open the factory."
            )
        if self.account_balance_source != "paper":
            raise RuntimeError(
                "account_balance_source must be 'paper' in this design "
                "(broker-balance source is unauthorized)."
            )
