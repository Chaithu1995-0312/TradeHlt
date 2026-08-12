"""MetricCell — one cell in the comparison matrix.

Never fill missing cells with assumptions. Status is load-bearing.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Optional


class MetricStatus(str, Enum):
    VERIFIED = "VERIFIED"
    MEASURED = "MEASURED"
    REPRODUCED = "REPRODUCED"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    FAILED = "FAILED"
    NOT_RUN = "NOT_RUN"


@dataclass
class MetricCell:
    metric: str
    engine: str
    value: Any  # number | str | None
    unit: str
    definition: str
    source_artifact: str
    run_id: str
    status: MetricStatus
    confidence_note: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value if isinstance(self.status, MetricStatus) else self.status
        return d
