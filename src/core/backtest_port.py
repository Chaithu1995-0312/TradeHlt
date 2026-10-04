"""
backtest_port.py — Trd-M4 dependency-inversion port.

Neutral abstraction so governance / analytics / agent code can depend on a
backtest *contract* instead of importing the concrete
``runtime.backtest_v2.BacktestRunner`` at module level — inverting the previous
upward ``governance → runtime`` import edge.

``runtime.backtest_v2.BacktestRunner`` structurally satisfies ``BacktestPort`` and
its ``run()`` return value (``BacktestMetrics``) structurally satisfies
``BacktestResult`` — **no inheritance required** (these are ``typing.Protocol``
structural contracts, mirroring the only other abstract contract in the codebase,
``strategies/base_strategy.py``, but without forcing a base class on the runner).

Consumers receive a ``BacktestFactory`` (default: ``default_backtest_factory``,
which lazily imports ``BacktestRunner`` inside the call) so neither this module nor
any consumer that types against it pulls ``runtime.backtest_v2`` at import time.
"""
from __future__ import annotations

from typing import Any, Callable, Iterator, Protocol, runtime_checkable


@runtime_checkable
class BacktestResult(Protocol):
    """Metrics contract consumers read off a completed backtest run.

    Matches the fields/properties of ``runtime.backtest_v2.BacktestMetrics``.
    """
    approved_trades:       int
    wins:                  int
    losses:                int
    max_drawdown_pct:      float
    total_pnl_rr_net:      float
    total_return_pct:      float
    annualized_return_pct: float
    profit_factor:         float
    return_to_max_dd:      float
    capital_curve:         dict

    @property
    def win_rate(self) -> float: ...

    @property
    def avg_rr_net(self) -> float: ...

    def to_dict(self) -> dict: ...


@runtime_checkable
class BacktestPort(Protocol):
    """Runner contract consumers invoke — matches ``BacktestRunner.run``."""

    def run(
        self,
        candle_source: Iterator[Any],
        total_candles: int,
        output_dir: str = "results",
    ) -> BacktestResult: ...


# A factory is any callable (bt_config, csv_path=..., **kwargs) -> BacktestPort.
BacktestFactory = Callable[..., BacktestPort]


def default_backtest_factory(
    bt_config: Any,
    csv_path: str | None = None,
    **kwargs: Any,
) -> BacktestPort:
    """Default factory: lazily resolve the concrete runtime implementation.

    The import lives **inside** the call so that importing this module (or any
    consumer that injects this default) never triggers a ``runtime.backtest_v2``
    import — that is the dependency inversion.
    """
    from runtime.backtest_v2 import BacktestRunner  # lazy: breaks module-level upward edge
    return BacktestRunner(bt_config, csv_path=csv_path, **kwargs)
