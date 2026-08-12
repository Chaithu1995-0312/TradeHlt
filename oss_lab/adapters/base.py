"""Base adapter protocol for OSS Lab engines."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, Sequence, runtime_checkable

from oss_lab.contracts.dataset_manifest import DatasetManifest
from oss_lab.contracts.fill_model import FillModelDeclaration
from oss_lab.contracts.run_manifest import RunManifest
from oss_lab.contracts.trade_record import BenchmarkTradeRecord


@dataclass
class AdapterCapability:
    """What an adapter can actually provide today."""

    oss_id: str
    can_run_backtest: bool = False
    can_emit_trades: bool = False
    can_emit_signals: bool = False
    can_emit_orders: bool = False
    can_emit_fills: bool = False
    can_measure_latency: bool = False
    can_run_lookahead_probe: bool = False
    dependency_installed: bool = False
    notes: list[str] = field(default_factory=list)


@runtime_checkable
class EngineAdapter(Protocol):
    """Thin adapter contract. Implementations must not invent missing fields."""

    oss_id: str

    def capability(self) -> AdapterCapability:
        ...

    def bind_dataset(self, manifest: DatasetManifest) -> None:
        """Fail closed if path/hash do not match lab policy."""
        ...

    def normalize_trades(
        self,
        native_trades: Sequence[dict[str, Any]],
        *,
        run_id: str,
    ) -> list[BenchmarkTradeRecord]:
        ...

    def declare_fill_model(self) -> FillModelDeclaration:
        ...
