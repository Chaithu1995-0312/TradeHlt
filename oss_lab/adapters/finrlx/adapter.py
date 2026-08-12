"""FinRL-X adapter STUB — T2 research / portfolio / RL candidate.

Published paper-trading returns are not Tradelatest evidence.
NO FinRL dependency is imported or installed by this module.
"""

from __future__ import annotations

from typing import Any, Sequence

from oss_lab.adapters.base import AdapterCapability
from oss_lab.contracts.dataset_manifest import DatasetManifest
from oss_lab.contracts.fill_model import FillModelDeclaration
from oss_lab.contracts.trade_record import BenchmarkTradeRecord


class FinRLXAdapter:
    oss_id = "OSS-FINRLX"

    def capability(self) -> AdapterCapability:
        return AdapterCapability(
            oss_id=self.oss_id,
            can_run_backtest=False,
            can_emit_trades=False,
            dependency_installed=False,
            notes=[
                "STUB only. decision=DISCOVERED.",
                "Separate observed return from annualized return.",
                "License must be verified before use.",
            ],
        )

    def bind_dataset(self, manifest: DatasetManifest) -> None:
        raise NotImplementedError(
            "FinRLXAdapter.bind_dataset not implemented — lifecycle DISCOVERED"
        )

    def normalize_trades(
        self,
        native_trades: Sequence[dict[str, Any]],
        *,
        run_id: str,
    ) -> list[BenchmarkTradeRecord]:
        raise NotImplementedError(
            "FinRLXAdapter.normalize_trades not implemented — lifecycle DISCOVERED"
        )

    def declare_fill_model(self) -> FillModelDeclaration:
        raise NotImplementedError(
            "FinRL fill model not declared — UNKNOWN until designed"
        )
