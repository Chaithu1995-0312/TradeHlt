"""Qlib adapter STUB — T2 research engine candidate.

NO qlib dependency is imported or installed by this module.
When/if APPROVED_FOR_LAB + version pin lands, implementation lives only here.
"""

from __future__ import annotations

from typing import Any, Sequence

from oss_lab.adapters.base import AdapterCapability
from oss_lab.contracts.dataset_manifest import DatasetManifest
from oss_lab.contracts.fill_model import FillModelDeclaration
from oss_lab.contracts.trade_record import BenchmarkTradeRecord


class QlibAdapter:
    oss_id = "OSS-QLIB"

    def capability(self) -> AdapterCapability:
        return AdapterCapability(
            oss_id=self.oss_id,
            can_run_backtest=False,
            can_emit_trades=False,
            dependency_installed=False,
            notes=[
                "STUB only. decision=DISCOVERED.",
                "Do not pip install until APPROVED_FOR_LAB + pin + supply-chain check.",
                "Published Qlib examples are PUBLISHED RESULT, not Tradelatest evidence.",
            ],
        )

    def bind_dataset(self, manifest: DatasetManifest) -> None:
        raise NotImplementedError(
            "QlibAdapter.bind_dataset not implemented — lifecycle DISCOVERED"
        )

    def normalize_trades(
        self,
        native_trades: Sequence[dict[str, Any]],
        *,
        run_id: str,
    ) -> list[BenchmarkTradeRecord]:
        raise NotImplementedError(
            "QlibAdapter.normalize_trades not implemented — lifecycle DISCOVERED"
        )

    def declare_fill_model(self) -> FillModelDeclaration:
        raise NotImplementedError("Qlib fill model not declared — UNKNOWN until designed")
