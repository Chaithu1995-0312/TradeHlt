"""charts — INFRA-CPC-V1 Workstream A0: own OHLC charts from the corpus we consume.

Design authority: docs/governance/INFRA_CHART_PAPER_COMPARE_V1.md (`INFRA-CPC-V1`,
frozen 2026-08-06). This package implements **A0 only** — Layer V0 (bars) + Layer V1
(CRTState colour) + the §3.3 export pack. A1 (8-layer story tags), A2 (FM panel),
B (paper trades) and C (broker compare) are out of scope and deliberately absent.

Z-AC1: no ZONE-X module may be imported from this package.
"""
