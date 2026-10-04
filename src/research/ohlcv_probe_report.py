"""Shared emission contract for OHLCV corpus-authority probes (BC-2, BC-4, ...).

Extracted from src/research/ohlcv_open_close_label.py after that scorer's emission-layer
hardening (2026-09-03 prereg amendment section 9). ohlcv_open_close_label.py is left
byte-identical -- its F-098 evidence artifact must stay reproducible -- so this module
duplicates rather than imports from it. A later, separately-authorized turn may migrate
BC-2 onto this shared module.

Contract this module provides, proven by the BC-2 probe:
  - one report shape from every exit path (_base_report)
  - fail-closed snapshot provenance: only a live capture may claim source=live_mt5
  - a checked (not merely asserted) admitted-artifact hash binding
  - a one-directional staleness guard (can only downgrade a result, never manufacture one)
  - terminal provenance recorded WITHOUT the account login
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]

ADMITTED_SHA256 = (
    "4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56"
)
ADMITTED_PATH = "data/mt5/XAUUSD_M15.csv"
DATASET_ID = "XAUUSD_MT5_PHASE1_20260521"

# Same rationale as BC-2 (prereg amendment 9.1): MT5 server time runs ~UTC+2/+3 (F-066), so a
# HEALTHY terminal shows a legitimate multi-hour skew. 6h clears any plausible broker offset
# while still catching a weeks-stale terminal.
STALE_THRESHOLD_SECONDS = 6 * 3600

CLOCK_BASIS = "broker_local"
SOURCE_LIVE = "live_mt5"
SOURCE_SYNTHETIC = "synthetic"


class ProbeError(RuntimeError):
    pass


def aware_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


@lru_cache(maxsize=4)
def _sha256_of(path: str) -> Optional[str]:
    p = Path(path)
    if not p.is_file():
        return None
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_admitted_artifact(
    repo_root: Optional[Path] = None,
) -> tuple[bool, Optional[bool]]:
    """Hash the admitted canonical CSV. Returns (present, match); match is None if absent."""
    root = repo_root or REPO_ROOT
    digest = _sha256_of(str(root / ADMITTED_PATH))
    if digest is None:
        return False, None
    return True, digest == ADMITTED_SHA256


@dataclass(frozen=True)
class ProbeSnapshot:
    """A single MT5 capture, or a synthetic stand-in for it.

    source defaults to SOURCE_SYNTHETIC (fail-closed): only a real capture function may
    construct one with source=SOURCE_LIVE.
    """

    fetched_at: datetime
    symbol: str
    source: str = SOURCE_SYNTHETIC
    clock_basis: str = CLOCK_BASIS
    terminal: Optional[dict] = None
    # Measured AT CAPTURE TIME and stored. Re-scoring later must not re-measure against the
    # scoring-time clock.
    wall_clock_skew_seconds: Optional[float] = None
    # Free-form payload for the probe-specific data (bars, tick counts, ...).
    payload: dict = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.payload is None:
            object.__setattr__(self, "payload", {})


def staleness_reason(snap: ProbeSnapshot, which: str) -> Optional[str]:
    """One-directional: may only downgrade a result to INSUFFICIENT, never manufacture one."""
    if snap.source != SOURCE_LIVE:
        return None  # synthetic fixtures carry no wall clock
    if snap.wall_clock_skew_seconds is None:
        return f"stale_feed_unmeasured_{which}"
    if abs(float(snap.wall_clock_skew_seconds)) > STALE_THRESHOLD_SECONDS:
        return f"stale_feed_{which}"
    return None


def terminal_provenance(mt5module) -> dict:
    """Terminal identity WITHOUT the account login -- nothing in these probes needs it."""
    ti = mt5module.terminal_info()
    ai = mt5module.account_info()
    return {
        "company": getattr(ti, "company", None) if ti else None,
        "name": getattr(ti, "name", None) if ti else None,
        "build": getattr(ti, "build", None) if ti else None,
        "connected": getattr(ti, "connected", None) if ti else None,
        "server": getattr(ai, "server", None) if ai else None,
    }


def base_report(
    probe_id: str,
    *,
    snap_a: Optional[ProbeSnapshot] = None,
    snap_b: Optional[ProbeSnapshot] = None,
    prereg: str,
    repo_root: Optional[Path] = None,
    verify_admitted: bool = True,
) -> dict[str, Any]:
    """The ONE report shape every exit path returns, shared across BC probes."""
    if verify_admitted:
        present, match = verify_admitted_artifact(repo_root)
    else:
        present, match = False, None
    return {
        "probe_id": probe_id,
        "dataset_id": DATASET_ID,
        "admitted_sha256": ADMITTED_SHA256,
        "admitted_path": ADMITTED_PATH,
        "admitted_artifact_present": present,
        "admitted_sha256_match": match,
        "prereg": prereg,
        "clock_basis": snap_a.clock_basis if snap_a else CLOCK_BASIS,
        "source_a": snap_a.source if snap_a else None,
        "source_b": snap_b.source if snap_b else None,
        "wall_clock_skew_seconds_a": snap_a.wall_clock_skew_seconds if snap_a else None,
        "wall_clock_skew_seconds_b": snap_b.wall_clock_skew_seconds if snap_b else None,
        "stale_threshold_seconds": STALE_THRESHOLD_SECONDS,
        "terminal_a": snap_a.terminal if snap_a else None,
        "terminal_b": snap_b.terminal if snap_b else None,
        # The frozen dataset record carries no terminal identity, so a family match cannot
        # be VERIFIED -- only recorded for a future comparison.
        "producer_family_match": "UNVERIFIED_NO_RECORDED_TERMINAL",
        "ohlcv_closure": "UNCHANGED",
    }
