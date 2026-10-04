"""Evidence records — measurements, not predictions."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

CONFIDENCE_LEVELS = ("INSUFFICIENT", "POSSIBLE", "LIKELY", "CERTAIN")
AUTHORITY = "RESEARCH_ONLY"

# Always attached so a consumer cannot quote a number without the grain.
DEFAULT_CAVEATS = (
    "Grain is bar×direction on the 94k ledger, or a later CRT spine run on events/telemetry — never both as one lifecycle.",
    "Governing y is clean_labels path labels, never opportunities.outcome (F-022).",
    "y_R_net uses protocol 12bps; F-082 measured XAUUSD broker cost is ~11x smaller. Net is diagnostic.",
    "Stored features are PIT_UNCLEAN (F-051). Does not reverse F-086. No G001.",
)


@dataclass
class EvidenceRecord:
    question: str
    surface: str
    n: int
    effect_name: str
    effect_size: float | None
    confidence: str
    candidate_finding: str
    caveats: list[str] = field(default_factory=list)
    authority: str = AUTHORITY
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.confidence not in CONFIDENCE_LEVELS:
            raise ValueError(f"confidence must be one of {CONFIDENCE_LEVELS}")
        if self.authority != AUTHORITY:
            raise ValueError("evidence records cannot grant production authority")
        merged = list(DEFAULT_CAVEATS)
        for c in self.caveats:
            if c not in merged:
                merged.append(c)
        self.caveats = merged

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def descriptive_confidence(n: int) -> str:
    """Counts of what the file contains. Not an economic claim."""
    if n < 30:
        return "INSUFFICIENT"
    return "CERTAIN"


def contrast_confidence(n: int, abs_delta: float, floor: float = 0.02) -> str:
    """Rate/mean contrast. Never CERTAIN — that band is reserved for file counts."""
    if n < 30:
        return "INSUFFICIENT"
    if abs_delta < floor:
        return "POSSIBLE"
    if n >= 1000 and abs_delta >= 0.05:
        return "LIKELY"
    return "POSSIBLE"
