"""SECONDLOW-v1 detector — canonical MT5 corpus + xlsx regression fixture."""

from research.secondlow_v1.corpus import (
    CANONICAL_CORPUS_SHA256_PREFIX,
    CANONICAL_XAUUSD_M15,
    REGRESSION_FIXTURE_SHA256_PREFIX,
    REGRESSION_FIXTURE_XLSX,
    REGRESSION_INDEPENDENT_TIMESTAMPS,
)
from research.secondlow_v1.detector import (
    DISCOVERY_END,
    DISCOVERY_START,
    MIN_EVENT_SPACING_MIN,
    SecondLowEvent,
    classify_exposure,
    detect_independent_events,
    load_ohlcv,
    partition_event_times,
)

__all__ = [
    "CANONICAL_CORPUS_SHA256_PREFIX",
    "CANONICAL_XAUUSD_M15",
    "DISCOVERY_END",
    "DISCOVERY_START",
    "MIN_EVENT_SPACING_MIN",
    "REGRESSION_FIXTURE_SHA256_PREFIX",
    "REGRESSION_FIXTURE_XLSX",
    "REGRESSION_INDEPENDENT_TIMESTAMPS",
    "SecondLowEvent",
    "classify_exposure",
    "detect_independent_events",
    "load_ohlcv",
    "partition_event_times",
]