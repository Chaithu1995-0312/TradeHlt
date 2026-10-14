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

from data_ingestion.clock_contract import ClockDef, parse_clock_defs, require_exact_identity
from data_ingestion.ohlcv_schema import ClockProvenanceError

# Repo root: src/data_ingestion/clock_registry.py -> parents[2]
_REPO_ROOT = Path(__file__).resolve().parents[2]

REGISTRY_RELPATH = "configs/data_provenance/ohlcv_clock_registry.json"
# 2.0.0 (CH-corpus-clock-contract-v1): adds the top-level `clocks` table (configured clock
# definitions) and record-level provider/broker/clock_id. 1.0.0 files still load (no clocks).
REGISTRY_SCHEMA_VERSION = "2.0.0"

# ── Legacy declared-clock LABELS ───────────────────────────────────────────────
# Pre-2.0 records carry a free `timezone` label. It is HISTORY: conversion never reads it (the
# mapping comes from the configured clock named by `clock_id`). Kept so old records still load and
# so the review CLI can still show what a reviewer once wrote. `UNKNOWN` is not legal for a
# REVIEWED legacy record.
TZ_UTC = "UTC"
TZ_MT5_SERVER_NY_DST = "MT5_SERVER_NY_DST"
_NAMED_TIMEZONE_KINDS = (TZ_UTC, TZ_MT5_SERVER_NY_DST)

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
    """One corpus artifact's declared clock identity. `user_reviewed` is set ONLY by a human via
    the review CLI. `provider`/`broker`/`clock_id` name the configured clock (the `clocks` table);
    `timezone` is the legacy free label (history only, never read by conversion)."""
    path: str
    sha256: str
    timezone: str
    user_reviewed: bool
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    detector: Optional[dict] = None
    notes: str = ""
    provider: Optional[str] = None
    broker: Optional[str] = None
    clock_id: Optional[str] = None

    def __post_init__(self) -> None:
        if self.user_reviewed:
            # A reviewed record must carry an attributable reviewer and either a configured clock
            # identity (2.0) or a legal legacy label (1.0 history).
            if not self.clock_id:
                validate_timezone_value(self.timezone)
            if not self.reviewed_by:
                raise ValueError(
                    f"{self.path}: user_reviewed=true requires a non-empty 'reviewed_by'. "
                    "An unattributable review is not a review."
                )

    def to_json(self) -> dict:
        d = asdict(self)
        for k in ("provider", "broker", "clock_id"):
            if d.get(k) is None:
                d.pop(k)
        return d

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
            provider=obj.get("provider"),
            broker=obj.get("broker"),
            clock_id=obj.get("clock_id"),
        )


def _read_raw(reg_path: Path) -> dict:
    try:
        raw = json.loads(reg_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ClockProvenanceError(f"{reg_path} is not valid JSON: {exc}") from exc
    if not isinstance(raw, dict) or "records" not in raw:
        raise ClockProvenanceError(
            f"{reg_path} must be an object with a 'records' array (schema_version "
            f"{REGISTRY_SCHEMA_VERSION})."
        )
    return raw


def load_registry(registry: Optional[Path] = None) -> dict[str, ClockRecord]:
    """Load the registry into {normalized_key: ClockRecord}.

    A MISSING registry file is not an error here — it yields an empty mapping, and the gate then
    reports "no record" for every corpus (still fail-closed). A registry that EXISTS but is corrupt
    IS an error: silently treating malformed governance state as absent is how a gate stops gating.
    """
    reg_path = registry or registry_path()
    if not reg_path.exists():
        return {}
    raw = _read_raw(reg_path)
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


def load_clocks(registry: Optional[Path] = None) -> dict[str, ClockDef]:
    """The configured clock definitions (`clocks` table). Missing table -> no clocks (all corpora
    are then refused at admission). Offset-valued fields are refused by `parse_clock_defs`."""
    reg_path = registry or registry_path()
    if not reg_path.exists():
        return {}
    return parse_clock_defs(_read_raw(reg_path).get("clocks", {}))


def save_registry(records: dict[str, ClockRecord], registry: Optional[Path] = None) -> Path:
    """Atomic write, records sorted by path so diffs stay reviewable. The `clocks` table is
    preserved verbatim (this function never edits clock definitions)."""
    reg_path = registry or registry_path()
    reg_path.parent.mkdir(parents=True, exist_ok=True)
    clocks = _read_raw(reg_path).get("clocks", {}) if reg_path.exists() else {}
    payload = {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "clocks": clocks,
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
_IN_PROCESS: dict[str, tuple[str, str]] = {}      # key -> (clock_id, reason)
_IN_PROCESS_TREES: list[tuple[Path, str, str]] = []


def declare_in_process(path: str | os.PathLike, clock_id: str, *, reason: str) -> None:
    """Declare one process-local file's configured clock. Never persisted to the registry."""
    _IN_PROCESS[normalize_key(path)] = (clock_id, reason)


def declare_tree_in_process(root: str | os.PathLike, clock_id: str, *, reason: str) -> None:
    """Declare every file under `root` (e.g. a pytest tmp factory). Never persisted."""
    _IN_PROCESS_TREES.append((Path(root).resolve(), clock_id, reason))


def clear_in_process_declarations() -> None:
    _IN_PROCESS.clear()
    _IN_PROCESS_TREES.clear()


def _in_process_decl(path: str | os.PathLike, key: str) -> Optional[tuple[str, str]]:
    hit = _IN_PROCESS.get(key)
    if hit is None:
        try:
            resolved = Path(path).resolve()
        except OSError:
            resolved = Path(path).absolute()
        for root, cid, reason in _IN_PROCESS_TREES:
            if resolved == root or root in resolved.parents:
                hit = (cid, reason)
                break
    return hit


# ── Admission: the clock identity of a corpus ──────────────────────────────────
@dataclass(frozen=True)
class ResolvedClock:
    """The admitted clock identity of one corpus file: the configured definition plus the
    declaration that selected it. `origin` is where the declaration came from."""
    clock: ClockDef
    record: ClockRecord
    origin: str                      # registry | in_process | inherited_parent


def _sidecar_path(path: str | os.PathLike) -> Path:
    return Path(path).with_suffix(".parent.json")


def _inherit_from_parent(path: str | os.PathLike, registry: Optional[Path],
                         _depth: int = 0) -> Optional[ResolvedClock]:
    """Derived-window lineage (contract §13): a window written by the replay harness names its
    parent in a `.parent.json` sidecar bound to THIS file's sha. The window inherits the parent's
    DECLARED clock through that explicit lineage — nothing is inferred from the bytes."""
    sc = _sidecar_path(path)
    if _depth > 4 or not sc.exists():
        return None
    try:
        meta = json.loads(sc.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    src = meta.get("derived_from") or {}
    bound = meta.get("derived_corpus_sha256")
    parent_path, parent_sha = src.get("corpus_path"), src.get("corpus_sha256")
    if not (bound and parent_path and parent_sha):
        return None
    if bound != sha256_file(path):
        raise ClockProvenanceError(
            f"{path}: derived-window sidecar {sc.name} is bound to a different file sha "
            f"({str(bound)[:12]}.. != actual); a window must be re-derived, its clock is not inherited.")
    pp = Path(parent_path)
    pp = pp if pp.is_absolute() else _REPO_ROOT / pp
    if not pp.exists() or sha256_file(pp) != parent_sha:
        raise ClockProvenanceError(
            f"{path}: parent corpus {parent_path} is missing or its sha changed; the window's "
            f"clock lineage is broken.")
    parent = resolve_clock(pp, registry=registry, _depth=_depth + 1)
    rec = ClockRecord(path=normalize_key(path), sha256=bound, timezone="", user_reviewed=True,
                      reviewed_by=f"inherited from {parent.record.path}", reviewed_at=utcnow_iso(),
                      notes=f"derived window of {parent_path} ({parent_sha[:12]}..)",
                      provider=parent.clock.provider, broker=parent.clock.broker,
                      clock_id=parent.clock.clock_id)
    return ResolvedClock(parent.clock, rec, "inherited_parent")


def resolve_clock(
    path: str | os.PathLike,
    *,
    registry: Optional[Path] = None,
    dataset: Optional[dict] = None,
    _depth: int = 0,
) -> ResolvedClock:
    """Resolve the configured clock a corpus file is declared on, or raise `ClockProvenanceError`.

    A dataset without an explicit, configured clock identity cannot enter the research system, and
    the declared provider/broker/clock_id must EXACTLY match the configured definition. Nothing is
    guessed: no detector verdict, no filename, no "same broker, probably same clock".

    `dataset` — the bound dataset-identity record when the file is a registered corpus; its own
    (provider, broker, clock_id) declaration must equal the artifact record's.
    """
    key = normalize_key(path)
    if not Path(path).exists():
        raise FileNotFoundError(f"OHLCV corpus not found: {path}")
    clocks = load_clocks(registry)

    def _def(cid: str, where: str) -> ClockDef:
        if cid not in clocks:
            raise ClockProvenanceError(
                f"{where}: clock_id {cid!r} is not a configured clock "
                f"(configured: {sorted(clocks)}). Add it to {REGISTRY_RELPATH} 'clocks' first.")
        return clocks[cid]

    decl = _in_process_decl(path, key)
    if decl is not None:
        cid, reason = decl
        cd = _def(cid, f"in-process declaration for {key}")
        rec = ClockRecord(path=key, sha256="<in-process>", timezone="", user_reviewed=True,
                          reviewed_by="in-process declaration", reviewed_at=utcnow_iso(),
                          notes=reason, provider=cd.provider, broker=cd.broker, clock_id=cd.clock_id)
        return ResolvedClock(cd, rec, "in_process")

    rec = load_registry(registry).get(key)
    if rec is None:
        inh = _inherit_from_parent(path, registry, _depth)
        if inh is not None:
            return inh
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

    if not rec.clock_id:
        raise ClockProvenanceError(
            f"Clock identity MISSING for {key}: the record is reviewed (legacy label "
            f"{rec.timezone!r}) but declares no clock_id/provider/broker. A dataset without an "
            f"explicit, configured clock identity cannot enter the research system.\n"
            f"Declare it:\n"
            f"  python scripts/governance/review_ohlcv_clocks.py --review {key} --clock-id <id> "
            f"--reviewed-by <you>")
    cd = _def(rec.clock_id, key)
    require_exact_identity(cd, provider=rec.provider, broker=rec.broker, clock_id=rec.clock_id,
                           where=f"{key} (clock registry record)")
    if dataset is not None:
        require_exact_identity(cd, provider=dataset.get("provider"), broker=dataset.get("broker"),
                               clock_id=dataset.get("clock_id"),
                               where=f"dataset {dataset.get('dataset_id')} (dataset identity record)")
    return ResolvedClock(cd, rec, "registry")


def require_reviewed_clock(
    path: str | os.PathLike,
    *,
    registry: Optional[Path] = None,
    dataset: Optional[dict] = None,
) -> ResolvedClock:
    """Raise `ClockProvenanceError` unless this corpus has a reviewed, SHA-matching record naming
    a configured clock. (The former `basis=` double-conversion guard is retired: nothing downstream
    converts any more, so there is no second conversion to guard.)"""
    return resolve_clock(path, registry=registry, dataset=dataset)


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
