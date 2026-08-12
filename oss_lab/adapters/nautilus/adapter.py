"""NautilusTrader adapter STUB — T3 runtime/execution/replay candidate.

LGPL-3.0 obligations require legal review before any non-lab integration.
NO nautilus_trader dependency is imported or installed by this module.
"""

from __future__ import annotations

from typing import Any, Sequence

from oss_lab.adapters.base import AdapterCapability
from oss_lab.contracts.dataset_manifest import DatasetManifest
from oss_lab.contracts.fill_model import FillModelDeclaration
from oss_lab.contracts.trade_record import BenchmarkTradeRecord


class NautilusAdapter:
    oss_id = "OSS-NAUTILUS"

    def capability(self) -> AdapterCapability:
        return AdapterCapability(
            oss_id=self.oss_id,
            can_run_backtest=False,
            can_emit_trades=False,
            dependency_installed=False,
            notes=[
                "STUB only. decision=DISCOVERED.",
                "LGPL-3.0 LEGAL_REVIEW_REQUIRED before APPROVED_FOR_INTEGRATION.",
                "Must never replace CRT/Fusion/Decision/ExecutionPlanner/Ultron.",
            ],
        )

    def bind_dataset(self, manifest: DatasetManifest) -> None:
        raise NotImplementedError(
            "NautilusAdapter.bind_dataset not implemented — lifecycle DISCOVERED"
        )

    def normalize_trades(
        self,
        native_trades: Sequence[dict[str, Any]],
        *,
        run_id: str,
    ) -> list[BenchmarkTradeRecord]:
        raise NotImplementedError(
            "NautilusAdapter.normalize_trades not implemented — lifecycle DISCOVERED"
        )

    def declare_fill_model(self) -> FillModelDeclaration:
        raise NotImplementedError(
            "Nautilus fill model not declared — UNKNOWN until designed"
        )
