"""Sujan manipulation detection, Phase 1 (SEM-033). Research only.

Detects one thing and emits one alert: a later candle that purges an externally supplied
parent bulk candle's full wick-to-wick range and closes back inside it.

No entries. No targets. No HTF analysis. No OB/FVG. No CRT state machine. No C1/C2/C3.
No distribution. No expansion. No repository CRT substitutions. No economic claim.

BULK_CANDLE_SELECTOR is APPROVED_PROXY_UNVALIDATED — SEM-034 shortlists candidates for the
human bridge to confirm. It does not define what a bulk candle is; UNK-007 stays OPEN.

Spec:      docs/research/sujan_manipulation_object.md
Identity:  docs/governance/SUJAN_CRT_IDENTITY_EXTRACTION_SYSTEM.md
Drift log: docs/research/sujan_identity_drift_log.md (Record 5)

This is NOT SEM-031 (src/research/sujan_crt/) and imports nothing from it. F-095 attaches
to SEM-031 and does not travel here; nothing here travels to "Sujan CRT" either.
"""
from research.sujan_manipulation.bulk_proxy import (
    FROZEN_TOP_N,
    PROXY_ID,
    PROXY_STATUS,
    RankedCandidate,
    TopNBodySelector,
    TopNRangeSelector,
    build_selectors,
    overlap_indices,
)
from research.sujan_manipulation.geometry import (
    ALERT_KIND,
    ManipulationEvent,
    ManipulationSide,
    detect_manipulation,
)
from research.sujan_manipulation.parent import (
    BULK_CANDLE_EVIDENCE,
    BULK_CANDLE_SELECTOR,
    Bar,
    ExplicitTimestampSelector,
    ParentBulkCandle,
    ParentRange,
    ParentSelector,
    load_parent_timestamps,
    parent_range,
)
from research.sujan_manipulation.state import (
    PHASE1_PATH,
    ManipulationRunner,
    ParentMonitor,
    Phase1State,
    StateTransition,
)

__all__ = [
    "ALERT_KIND",
    "FROZEN_TOP_N",
    "PROXY_ID",
    "PROXY_STATUS",
    "BULK_CANDLE_EVIDENCE",
    "BULK_CANDLE_SELECTOR",
    "PHASE1_PATH",
    "Bar",
    "ExplicitTimestampSelector",
    "ManipulationEvent",
    "ManipulationRunner",
    "ManipulationSide",
    "ParentBulkCandle",
    "ParentMonitor",
    "ParentRange",
    "ParentSelector",
    "RankedCandidate",
    "TopNBodySelector",
    "TopNRangeSelector",
    "Phase1State",
    "StateTransition",
    "build_selectors",
    "detect_manipulation",
    "load_parent_timestamps",
    "overlap_indices",
    "parent_range",
]
