"""VectorBT adapter STUB — T2 research, DEFERRED pending Commons Clause legal review.

Do not install until LEGAL_REVIEW_REQUIRED is cleared.
"""

from __future__ import annotations

from typing import Any, Sequence

from oss_lab.adapters.base import AdapterCapability
from oss_lab.contracts.dataset_manifest import DatasetManifest
from oss_lab.contracts.fill_model import FillModelDeclaration
from oss_lab.contracts.trade_record import BenchmarkTradeRecord


class VectorBTAdapter:
    oss_id = "OSS-VECTORBT"

    def capability(self) -> AdapterCapability:
        return AdapterCapability(
            oss_id=self.oss_id,
            can_run_backtest=False,
            can_emit_trades=False,
            dependency_installed=False,
            notes=[
                "STUB. decision=DEFERRED.",
                "Apache-2.0 + Commons Clause — legal review before dependency.",
                "Not on this-week critical path.",
            ],
        )

    def bind_dataset(self, manifest: DatasetManifest) -> None:
        raise NotImplementedError(
            "VectorBTAdapter blocked — lifecycle DEFERRED (legal review)"
        )

    def normalize_trades(
        self,
        native_trades: Sequence[dict[str, Any]],
        *,
        run_id: str,
    ) -> list[BenchmarkTradeRecord]:
        raise NotImplementedError(
            "VectorBTAdapter blocked — lifecycle DEFERRED (legal review)"
        )

    def declare_fill_model(self) -> FillModelDeclaration:
        raise NotImplementedError("VectorBT fill model not declared — DEFERRED")
