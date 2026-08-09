"""XAUUSD M15 corpus paths for SECONDLOW research.

Bound to the Phase-1 frozen candidate (scope freeze — not production authority):

  data/mt5/XAUUSD_M15.csv
  sha256 4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56
  range  2024-05-22T01:00:00 .. 2026-05-21T23:45:00

NOT AUTHORITATIVE / NOT VALIDATED / NOT APPROVED / NOT ECONOMICALLY_ADMISSIBLE
until Phase-1 validation closes. Fail-closed verification:
  data_ingestion.xauusd_phase1_candidate.require_phase1_frozen_candidate
"""

from __future__ import annotations

from pathlib import Path

from data_ingestion.xauusd_phase1_candidate import (
    PHASE1_PHYSICAL_PATH,
    PHASE1_SHA256,
    require_phase1_frozen_candidate,
)

# Phase-1 frozen candidate (only allowed XAUUSD M15 for analysis / SECONDLOW).
CANONICAL_XAUUSD_M15 = PHASE1_PHYSICAL_PATH
CANONICAL_CORPUS_SHA256_PREFIX = PHASE1_SHA256[:16]  # 4d73f5cebe33ec91
CANONICAL_CORPUS_SHA256 = PHASE1_SHA256

# Partition invariants on the frozen candidate (recomputed 2026-07-10).
# POST window is empty because the extension after 2026-05-21 is excluded.
CANONICAL_EXPECTED_RAW = 60
CANONICAL_EXPECTED_INDEPENDENT = 36
CANONICAL_EXPECTED_PRE = 21
CANONICAL_EXPECTED_DISCOVERY = 15
CANONICAL_EXPECTED_POST = 0


def resolved_canonical_csv(repo_root: Path | None = None) -> Path:
    """Verify frozen candidate and return absolute path (fail closed)."""
    root = repo_root or Path(__file__).resolve().parents[3]
    b = require_phase1_frozen_candidate(repo_root=root)
    return (root / b.physical_path).resolve()


# Sandbox discovery slice — detector regression fixture ONLY (not economic evidence).
REGRESSION_FIXTURE_XLSX = Path("data/XAUUSD_M15_1year.xlsx")
REGRESSION_FIXTURE_SHA256_PREFIX = "e0bb97d9a5f3bea9"
REGRESSION_EXPECTED_RAW = 16
REGRESSION_EXPECTED_INDEPENDENT = 7

REGRESSION_INDEPENDENT_TIMESTAMPS = (
    "2026-05-15 13:45:00",
    "2026-05-18 00:30:00",
    "2026-05-19 13:15:00",
    "2026-05-19 16:00:00",
    "2026-05-20 01:15:00",
    "2026-05-20 07:15:00",
    "2026-05-20 14:00:00",
)
