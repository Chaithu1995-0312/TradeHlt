"""Infigraph adapter STUB — T1 repo-intelligence candidate.

Head-to-head with Codebase-Memory before any dual adoption.
NO external dependency installed by this module.
"""

from __future__ import annotations

from typing import Any, Sequence

from oss_lab.adapters.base import AdapterCapability
from oss_lab.contracts.structural_fact import StructuralFactRecord


class InfigraphAdapter:
    oss_id = "OSS-INFIGRAPH"

    def capability(self) -> AdapterCapability:
        return AdapterCapability(
            oss_id=self.oss_id,
            can_run_backtest=False,
            can_emit_trades=False,
            dependency_installed=False,
            notes=[
                "STUB. decision=DISCOVERED.",
                "Head-to-head vs OSS-CODEBASE-MEMORY required before adoption.",
                "Local-first / no API key claimed — favorable offline posture.",
            ],
        )

    def normalize_facts(
        self,
        native_facts: Sequence[dict[str, Any]],
        *,
        run_id: str,
    ) -> list[StructuralFactRecord]:
        raise NotImplementedError(
            "InfigraphAdapter.normalize_facts not implemented — lifecycle DISCOVERED"
        )
