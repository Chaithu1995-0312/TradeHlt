"""
mt5_analytics.analytics — the post-trade INTELLIGENCE read model (v0.6.0).

The first economically-meaningful consumer of the validated truth engine: it turns
persisted PositionEpisodes + FeatureRecords into a sufficiency-honest InsightReport.

DOCTRINE — this subpackage is a PURE READ MODEL. It composes
`analytics.metrics_oracle` primitives for a HUMAN to read; it never creates truth and
never feeds the trading spine. The only flow is:

    MT5 -> truth engine -> features -> insight -> HUMAN

NEVER `insight -> decisions`. Do NOT add a `recommendation_engine` / `optimization` /
`auto_tuning` module here — that would cross the §6.5 information-not-authority boundary.
"""
from .insight_report import (  # noqa: F401
    DEFAULT_MIN_N,
    SufficiencyStatus,
    AttributionBucket,
    AttributionReport,
    AdverseEfficiency,
    ConcentrationReport,
    CostDrag,
    ExitEfficiency,
    InsightReport,
    RiskAdjusted,
    build_insight,
)
