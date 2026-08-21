"""
clock_registry.py — declared, human-reviewed clock provenance for OHLCV corpora.

WHY THIS EXISTS (evidence, not assertion)
------------------------------------------
`inout/mt5_candle_fetcher.py:186` does `datetime.fromtimestamp(r["time"], tz=timezone.utc)` on
MT5's server-time epoch, so every `data/mt5/*` corpus carries a `timestamp` column LABELED UTC
while actually holding broker-server local time (F-066). The mislabel is invisible at read time:
nothing in the file says which clock it is on, so every downstream consumer silently guesses.

The CRT episode trace (`results/crt_episode_trace/20260813T124158Z/`) showed the cost — FOUR
independent surfaces answer "what session is it?" and they disagree at the same instant:

  1. `RiskScore.time_score`     crt_engine_v2.py:1837-1844  raw `timestamp.time()`  -> 0.0
  2. session GATE               crt_engine_v2.py:3106-3116  basis-aware             -> OFF_SESSION
  3. FM-052 `session` feature   feature_pipeline.py:716     basis-aware             -> 2
  4. `active_range.session`     crt_engine_v2.py:116        never assigned          -> UNKNOWN

WHAT THIS MODULE DOES — AND DELIBERATELY DOES NOT DO
-----------------------------------------------------
It records, per corpus, WHICH CLOCK the timestamps are on, and whether a human has REVIEWED that
declaration. It is a provenance gate, not a converter.

It does **NOT** convert or re-label any timestamp. `broker_clock.py:80-82` is explicit that the
MT5->UTC conversion is "for deriving session/hour-of-day semantics only, never for re-labeling the
corpus's own timestamp column," and F-066 deliberately parked the session FILTER on broker time
because it was empirically tuned there. Re-labeling at ingestion would silently move a tuned
trading filter; refusing to run on an undeclared clock does not.

FAIL-CLOSED
-----------
`require_reviewed_clock()` raises unless a record exists, its SHA-256 matches the file on disk, and
`user_reviewed` is true. There is no TTY branch and no environment escape hatch — an escape hatch
is exactly the silent-default class F-058 and the CLAUDE.md 6.5 "no silent config defaults" rule
were written to close. A re-fetched corpus changes SHA, which invalidates the record and correctly
re-opens review.

The registry lives under `configs/` (versioned), never under `data/` (gitignored), so a review is
auditable and shared rather than local to one machine.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from data_ingestion.ohlcv_schema import ClockProvenanceError

# Repo root: src/data_ingestion/clock_registry.py -> parents[2]
_REPO_ROOT = Path(__file__).resolve().parents[2]

REGISTRY_RELPATH = "configs/data_provenance/ohlcv_clock_registry.json"
REGISTRY_SCHEMA_VERSION = "1.0.0"

# ── Legal declared clocks ──────────────────────────────────────────────────────
# Two named kinds plus any IANA zone. `UNKNOWN` is deliberately NOT legal for a REVIEWED record:
# "reviewed" means a human declared which clock this is. An undecided corpus stays unreviewed.
TZ_UTC = "UTC"
TZ_MT5_SERVER_NY_DST = "MT5_SERVER_NY_DST"
_NAMED_TIMEZONE_KINDS = (TZ_UTC, TZ_MT5_SERVER_NY_DST)

# Basis values from `feature_pipeline.session_timestamp_basis`.
BASIS_BROKER_LOCAL = "broker_local"
BASIS_UTC_CORRECTED = "utc_corrected"

_SHA_CHUNK = 1 << 20  # 1 MiB


def repo_root() -> Path:
    return _REPO_ROOT


def registry_path() -> Path:
    return _REPO_ROOT / REGISTRY_RELPATH


def normalize_key(path: str | os.PathLike) -> str:
    """Registry key: repo-relative POSIX path, case-preserved.

    Absolute paths inside the repo are relativized so a record written on one machine resolves on
    another. A path outside the repo keeps its absolute POSIX form (still keyed, still gated).
    """
    p = Path(path)
    try:
        resolved = p.resolve()
    except OSError:                                   # broken symlink / missing parent
        resolved = p.absolute()
    try:
        return resolved.relative_to(_REPO_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def sha256_file(path: str | os.PathLike) -> str:
    """Streaming SHA-256 — corpora reach hundreds of MB, so never read whole-file."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(_SHA_CHUNK):
            h.update(chunk)
    return h.hexdigest()


def validate_timezone_value(tz: str) -> None:
    """Raise ValueError unless `tz` is a named kind or a resolvable IANA zone."""
    if tz in _NAMED_TIMEZONE_KINDS:
        return
    try:
        ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError, KeyError) as exc:
        raise ValueError(
            f"timezone={tz!r} is not legal. Use one of {_NAMED_TIMEZONE_KINDS} "
            f"or a valid IANA zone name (e.g. 'Europe/Athens')."
        ) from exc


@dataclass(frozen=True)
class ClockRecord:
    """One corpus's declared clock. `user_reviewed` is set ONLY by a human via the review CLI."""
    path: str
    sha256: str
    timezone: str
    user_reviewed: bool
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    detector: Optional[dict] = None
    notes: str = ""

    def __post_init__(self) -> None:
        if self.user_reviewed:
            # A reviewed record must carry a legal declaration and an attributable reviewer.
            validate_timezone_value(self.timezone)
            if not self.reviewed_by:
                raise ValueError(
                    f"{self.path}: user_reviewed=true requires a non-empty 'reviewed_by'. "
                    "An unattributable review is not a review."
                )

    def to_json(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_json(obj: dict) -> "ClockRecord":
        missing = {"path", "sha256", "timezone", "user_reviewed"} - set(obj)
        if missing:
            raise ValueError(
                f"{REGISTRY_RELPATH}: record missing required field(s): "
                + ", ".join(sorted(missing))
            )
        if not isinstance(obj["user_reviewed"], bool):
            raise ValueError(
                f"{REGISTRY_RELPATH}: record {obj.get('path')!r} has non-boolean "
                f"user_reviewed={obj['user_reviewed']!r}. Use true/false, never a truthy string."
            )
        return ClockRecord(
            path=str(obj["path"]),
            sha256=str(obj["sha256"]),
            timezone=str(obj["timezone"]),
            user_reviewed=obj["user_reviewed"],
            reviewed_by=obj.get("reviewed_by"),
            reviewed_at=obj.get("reviewed_at"),
            detector=obj.get("detector"),
            notes=str(obj.get("notes", "")),
        )


def load_registry(registry: Optional[Path] = None) -> dict[str, ClockRecord]:
    """Load the registry into {normalized_key: ClockRecord}.

    A MISSING registry file is not an error here — it yields an empty mapping, and the gate then
    reports "no record" for every corpus (still fail-closed). A registry that EXISTS but is corrupt
    IS an error: silently treating malformed governance state as absent is how a gate stops gating.
    """
    reg_path = registry or registry_path()
    if not reg_path.exists():
        return {}
    try:
        raw = json.loads(reg_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ClockProvenanceError(f"{reg_path} is not valid JSON: {exc}") from exc

    if not isinstance(raw, dict) or "records" not in raw:
        raise ClockProvenanceError(
            f"{reg_path} must be an object with a 'records' array (schema_version "
            f"{REGISTRY_SCHEMA_VERSION})."
        )

    out: dict[str, ClockRecord] = {}
    for obj in raw["records"]:
        rec = ClockRecord.from_json(obj)
        key = normalize_key(rec.path)
        if key in out:
            raise ClockProvenanceError(
                f"{reg_path}: duplicate record for {key!r}. One corpus, one record."
            )
        out[key] = rec
    return out


def save_registry(records: dict[str, ClockRecord], registry: Optional[Path] = None) -> Path:
    """Atomic write, records sorted by path so diffs stay reviewable."""
    reg_path = registry or registry_path()
    reg_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "records": [records[k].to_json() for k in sorted(records)],
    }
    tmp = reg_path.with_suffix(reg_path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, reg_path)
    return reg_path


def lookup(path: str | os.PathLike, registry: Optional[Path] = None) -> Optional[ClockRecord]:
    return load_registry(registry).get(normalize_key(path))


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


# ── In-process declarations (constructed data, never corpora of record) ────────
# A corpus that ARRIVES from outside needs human review because nobody knows its clock. A file
# the running process just WROTE has a clock by construction — a test fixture or a synthetic
# generator already knows what it stamped. Requiring a human to review a tmp_path file that is
# created and deleted inside one test would be theatre, not governance.
#
# This is deliberately NOT an environment variable or a config flag: it is a CALL, so it appears
# in source, in review, and in grep. `tests/test_ohlcv_clock_provenance.py` pins the rule that no
# module under `src/` may invoke it — production code has no constructed corpora, so a call there
# would be a bypass, and the floor test fails the build if one appears.
_IN_PROCESS: dict[str, tuple[str, str]] = {}      # key -> (timezone, reason)
_IN_PROCESS_TREES: list[tuple[Path, str, str]] = []


def declare_in_process(path: str | os.PathLike, timezone: str, *, reason: str) -> None:
    """Declare one process-local file's clock. Never persisted to the registry."""
    validate_timezone_value(timezone)
    _IN_PROCESS[normalize_key(path)] = (timezone, reason)


def declare_tree_in_process(root: str | os.PathLike, timezone: str, *, reason: str) -> None:
    """Declare every file under `root` (e.g. a pytest tmp factory). Never persisted."""
    validate_timezone_value(timezone)
    _IN_PROCESS_TREES.append((Path(root).resolve(), timezone, reason))


def clear_in_process_declarations() -> None:
    _IN_PROCESS.clear()
    _IN_PROCESS_TREES.clear()


def _in_process_record(path: str | os.PathLike, key: str) -> Optional[ClockRecord]:
    hit = _IN_PROCESS.get(key)
    if hit is None:
        try:
            resolved = Path(path).resolve()
        except OSError:
            resolved = Path(path).absolute()
        for root, tz, reason in _IN_PROCESS_TREES:
            if resolved == root or root in resolved.parents:
                hit = (tz, reason)
                break
    if hit is None:
        return None
    tz, reason = hit
    return ClockRecord(path=key, sha256="<in-process>", timezone=tz, user_reviewed=True,
                       reviewed_by="in-process declaration", reviewed_at=utcnow_iso(),
                       notes=reason)


# ── Phase 3 gate ───────────────────────────────────────────────────────────────
def require_reviewed_clock(
    path: str | os.PathLike,
    *,
    basis: Optional[str] = None,
    registry: Optional[Path] = None,
) -> ClockRecord:
    """Raise `ClockProvenanceError` unless this corpus has a reviewed, SHA-matching clock record.

    `basis` — when the caller knows the active `feature_pipeline.session_timestamp_basis`, pass it
    and the double-conversion guard runs (a corpus already on true UTC must never be pushed through
    the MT5->UTC conversion again). Callers that do not resolve a basis omit it; the review gate
    itself still applies.
    """
    key = normalize_key(path)
    if not Path(path).exists():
        raise FileNotFoundError(f"OHLCV corpus not found: {path}")

    in_proc = _in_process_record(path, key)
    if in_proc is not None:
        if basis is not None:
            require_basis_compatible(in_proc, basis)
        return in_proc

    rec = load_registry(registry).get(key)
    if rec is None:
        raise ClockProvenanceError(_unreviewed_message(key, path, reason="no record"))

    actual_sha = sha256_file(path)
    if actual_sha != rec.sha256:
        raise ClockProvenanceError(
            f"Clock provenance STALE for {key}.\n"
            f"  recorded sha256 : {rec.sha256}\n"
            f"  actual   sha256 : {actual_sha}\n"
            f"The file changed since it was reviewed, so its recorded clock no longer applies.\n"
            f"Re-review it:\n"
            f"  python scripts/governance/review_ohlcv_clocks.py --review {key}"
        )

    if not rec.user_reviewed:
        raise ClockProvenanceError(_unreviewed_message(key, path, reason="user_reviewed=false",
                                                      detector=rec.detector))

    if basis is not None:
        require_basis_compatible(rec, basis)
    return rec


def require_basis_compatible(rec: ClockRecord, basis: str) -> None:
    """Double-conversion guard.

    `utc_corrected` routes timestamps through `broker_clock.mt5_server_to_utc*`, which subtracts the
    broker's 2h/3h seasonal offset. Applying that to a corpus whose stamps are ALREADY true UTC
    silently shifts it into a wrong clock — the same class of defect this registry exists to catch,
    arriving from the opposite direction.
    """
    if basis not in (BASIS_BROKER_LOCAL, BASIS_UTC_CORRECTED):
        raise ClockProvenanceError(
            f"feature_pipeline.session_timestamp_basis={basis!r} is not one of "
            f"({BASIS_BROKER_LOCAL!r}, {BASIS_UTC_CORRECTED!r})."
        )
    if basis == BASIS_UTC_CORRECTED and rec.timezone == TZ_UTC:
        raise ClockProvenanceError(
            f"DOUBLE CONVERSION refused for {rec.path}.\n"
            f"  declared clock : {TZ_UTC} (already true UTC)\n"
            f"  active basis   : {BASIS_UTC_CORRECTED} (applies the MT5 server->UTC offset)\n"
            f"broker_clock.py's SCOPE section: Binance-sourced corpora use genuinely UTC epoch\n"
            f"timestamps and must NEVER be passed through this conversion. Either read this corpus\n"
            f"under basis '{BASIS_BROKER_LOCAL}', or correct the declaration if it is not UTC."
        )


def _unreviewed_message(key: str, path: Any, *, reason: str,
                        detector: Optional[dict] = None) -> str:
    guess = ""
    if detector:
        guess = (f"\n  detector guess : {detector.get('verdict', 'n/a')} "
                 f"(confidence {detector.get('confidence', 'n/a')}) - ADVISORY ONLY")
    return (
        f"Clock provenance UNREVIEWED for {key} ({reason}).\n"
        f"  file           : {path}{guess}\n"
        f"This corpus's timestamps have no human-reviewed timezone declaration, so the session\n"
        f"filter, time_score and hour-of-day features would run on an assumed clock (see F-066).\n"
        f"Execution stops here by design.\n"
        f"Review it:\n"
        f"  python scripts/governance/review_ohlcv_clocks.py --review {key}"
    )
