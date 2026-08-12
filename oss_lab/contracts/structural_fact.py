"""StructuralFactRecord — common output for repository-intelligence tools.

Separate from BenchmarkTradeRecord (execution track).

Doctrine:
  Codebase-Memory / Infigraph / pyan → STRUCTURAL facts
  Semantic OS → MEANING / authority / relationships

Never promote a structural edge into semantic truth without Semantic OS ingestion
+ human/governance interpretation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from oss_lab.contracts.presence import Presence
from oss_lab.contracts.trade_record import FieldProvenance


@dataclass
class StructuralFactRecord:
    """One normalized structural fact from a repo-intelligence engine."""

    run_id: str
    engine: str  # e.g. codebase_memory | infigraph | pyan_baseline
    fact_type: str  # CALLS | IMPORTS | DEFINES | INHERITS | ROUTES | OTHER
    source_symbol: Optional[str] = None
    target_symbol: Optional[str] = None
    source_path: Optional[str] = None
    target_path: Optional[str] = None
    language: Optional[str] = None
    confidence: Optional[float] = None
    evidence_span: Optional[str] = None  # file:line range if available
    raw_ref: Optional[str] = None  # native id/hash
    field_provenance: dict[str, FieldProvenance] = field(default_factory=dict)
    adapter_meta: dict[str, Any] = field(default_factory=dict)

    def mark(
        self,
        field_name: str,
        presence: Presence,
        reason: str = "",
        native_field: Optional[str] = None,
        source_adapter: Optional[str] = None,
    ) -> None:
        self.field_provenance[field_name] = FieldProvenance(
            presence=presence,
            reason=reason,
            native_field=native_field,
            source_adapter=source_adapter,
        )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["field_provenance"] = {
            k: (v.to_dict() if isinstance(v, FieldProvenance) else v)
            for k, v in self.field_provenance.items()
        }
        return d
