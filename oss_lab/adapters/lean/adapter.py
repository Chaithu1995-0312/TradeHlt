"""LEAN adapter STUB — T3 execution/research adapter candidate.

Apache-2.0. Independent mechanics laboratory alongside Nautilus.
Do NOT import LEAN strategy architecture into Tradelatest.
NO lean dependency installed by this module.
"""

from __future__ import annotations

from typing import Any, Sequence

from oss_lab.adapters.base import AdapterCapability
from oss_lab.contracts.dataset_manifest import DatasetManifest
from oss_lab.contracts.fill_model import FillModelDeclaration
from oss_lab.contracts.trade_record import BenchmarkTradeRecord


class LeanAdapter:
    oss_id = "OSS-LEAN"

    def capability(self) -> AdapterCapability:
        return AdapterCapability(
            oss_id=self.oss_id,
            can_run_backtest=False,
            can_emit_trades=False,
            dependency_installed=False,
            notes=[
                "STUB. decision=DISCOVERED.",
                "Three-way execution compare: Tradelatest | Nautilus | LEAN.",
                "Never replace CRT/Fusion/Decision/Planner/Ultron.",
                "Same DatasetManifest + BenchmarkTradeRecord path as Nautilus.",
            ],
        )

    def bind_dataset(self, manifest: DatasetManifest) -> None:
        raise NotImplementedError(
            "LeanAdapter.bind_dataset not implemented — lifecycle DISCOVERED"
        )

    def normalize_trades(
        self,
        native_trades: Sequence[dict[str, Any]],
        *,
        run_id: str,
    ) -> list[BenchmarkTradeRecord]:
        raise NotImplementedError(
            "LeanAdapter.normalize_trades not implemented — lifecycle DISCOVERED"
        )

    def declare_fill_model(self) -> FillModelDeclaration:
        raise NotImplementedError("LEAN fill model not declared — UNKNOWN until designed")
