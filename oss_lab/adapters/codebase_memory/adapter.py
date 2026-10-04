"""Codebase-Memory MCP adapter STUB — T1 repo-intelligence candidate.

NO external binary/dependency is installed or invoked by this module.
Structural facts only; never Semantic OS authority.
"""

from __future__ import annotations

from typing import Any, Sequence

from oss_lab.adapters.base import AdapterCapability
from oss_lab.contracts.structural_fact import StructuralFactRecord


class CodebaseMemoryAdapter:
    oss_id = "OSS-CODEBASE-MEMORY"

    def capability(self) -> AdapterCapability:
        return AdapterCapability(
            oss_id=self.oss_id,
            can_run_backtest=False,
            can_emit_trades=False,
            dependency_installed=False,
            notes=[
                "STUB normalize path. decision=APPROVED_FOR_LAB (G1–G6 2026-08-12).",
                "Do not replace Semantic OS. Structural facts → future ingestion only.",
                "Install only under INSTALL_ISOLATION.md; prefer --skip-config.",
                "SLSA residual: run gh/cosign when tools available before first execute.",
                "Published token/tool reductions = claims to reproduce, not evidence.",
            ],
        )

    def normalize_facts(
        self,
        native_facts: Sequence[dict[str, Any]],
        *,
        run_id: str,
    ) -> list[StructuralFactRecord]:
        raise NotImplementedError(
            "CodebaseMemoryAdapter.normalize_facts not implemented — "
            "lifecycle APPROVED_FOR_LAB (install/benchmark next; mapping still stub)"
        )
