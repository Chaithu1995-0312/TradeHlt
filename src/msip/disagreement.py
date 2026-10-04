"""Optional shadow vs CRT observation disagreement taxonomy (telemetry only)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from msip.market_state_vector import MarketStateVector

# Taxonomy from SHADOW_COMPARISON_AND_DISAGREEMENT_SPEC_V1
DISAGREEMENT_CLASSES = (
    "D-OBS-ABSENT",
    "D-SCALE-MISMATCH",
    "D-LABEL-POLICY",
    "D-STRUCTURE-VS-SWEEP",
    "D-SESSION-ENCODING",
    "D-LIFECYCLE-ONLY",
)


@dataclass(frozen=True)
class DisagreementRecord:
    class_id: str
    symbol: str
    timeframe: str
    bar_timestamp: str
    bar_index: int | None
    detail: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "class": self.class_id,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "bar_timestamp": self.bar_timestamp,
            "bar_index": self.bar_index,
            "detail": dict(self.detail),
        }


def classify_disagreements(
    vector: MarketStateVector,
    *,
    crt_used_local_math: bool = False,
    crt_state: str | None = None,
) -> list[DisagreementRecord]:
    """Emit zero or more disagreement records for one bar (no CRT mutation)."""
    out: list[DisagreementRecord] = []
    dims = vector.dimensions
    ts = vector.bar_timestamp
    base = dict(
        symbol=vector.symbol,
        timeframe=vector.timeframe,
        bar_timestamp=ts,
        bar_index=vector.bar_index,
    )

    # D-OBS-ABSENT: dimension null while CRT used related local math
    if crt_used_local_math:
        vol = dims.get("volatility_state") or {}
        if vol.get("atr") is None:
            out.append(
                DisagreementRecord(
                    class_id="D-OBS-ABSENT",
                    detail={"field": "atr", "reason": "null_while_crt_local_math"},
                    **base,
                )
            )

    # D-STRUCTURE-VS-SWEEP: pipeline liquidity_sweep present note vs lifecycle
    structure = dims.get("structure_state") or {}
    sweep = structure.get("liquidity_sweep")
    if crt_state is not None and crt_state not in ("RANGE", None):
        if sweep is None:
            out.append(
                DisagreementRecord(
                    class_id="D-STRUCTURE-VS-SWEEP",
                    detail={
                        "pipeline_liquidity_sweep": sweep,
                        "crt_state": crt_state,
                        "note": "join_only_not_identity",
                    },
                    **base,
                )
            )

    # D-LIFECYCLE-ONLY: CRT private lifecycle with no continuous analogue
    if crt_state in (
        "SHADOW_PENDING",
        "EXPANSION",
        "RETEST",
        "EXECUTION",
        "RESOLUTION",
        "EXPIRED",
    ):
        out.append(
            DisagreementRecord(
                class_id="D-LIFECYCLE-ONLY",
                detail={"crt_state": crt_state, "expected": True},
                **base,
            )
        )

    # D-LABEL-POLICY: HOW labels present (informational — expected divergence class)
    if vector.has_how_labels():
        out.append(
            DisagreementRecord(
                class_id="D-LABEL-POLICY",
                detail={"note": "how_labels_present_not_a_bug"},
                **base,
            )
        )

    return out


def emit_disagreement_jsonl(path: Path, records: list[DisagreementRecord]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        for rec in records:
            fh.write(
                json.dumps(rec.to_dict(), sort_keys=True, separators=(",", ":")) + "\n"
            )
