"""
Phase-3 clock-provenance floor.

Phases 1-2 of `ohlcv_schema` validate WHAT the numbers are. Phase 3 validates what the TIMESTAMPS
MEAN: a corpus may not be read until a human has DECLARED its timezone and REVIEWED that
declaration. `mt5_candle_fetcher.py:186` stamps MT5 broker-server time as UTC, so a file's own
claim about its clock is not evidence (F-066).

These tests pin the fail-closed behaviour, the double-conversion guard, and — via
`test_every_file_backed_reader_is_gated` — the structural property that a NEW OHLCV reader cannot
silently skip the gate.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from data_ingestion import clock_registry as cr
from data_ingestion.clock_detector import (
    VERDICT_INCONCLUSIVE, VERDICT_MT5_NY, detect_clock, load_raw_ohlcv,
)
from data_ingestion.ohlcv_schema import ClockProvenanceError

REPO_ROOT = Path(__file__).resolve().parents[1]


# ── fixtures ───────────────────────────────────────────────────────────────────
def _write_corpus(path: Path, *, days: int = 40, day_start_hour: int = 0) -> Path:
    """A schema-valid M15 corpus whose trading day runs `day_start_hour`:00 -> 23:45.

    `day_start_hour=1` reproduces the MT5 broker-day shape (01:00 -> 23:45) that makes T3's
    "opens at UTC midnight" signal absent. Emitted day-by-day, because a continuous bar stream
    would still start every day after the first at 00:00 and leave the modal open at midnight.
    """
    rows = ["timestamp,open,high,low,close,volume"]
    i = 0
    for d in range(days):
        t = datetime(2025, 1, 1, day_start_hour, 0) + timedelta(days=d)
        while t.day == (datetime(2025, 1, 1) + timedelta(days=d)).day:
            amp = 1.0 + (t.hour % 12) / 12.0          # repeatable intraday hump (non-zero variance)
            o = 100.0 + (i % 7) * 0.1
            rows.append(
                f"{t:%Y-%m-%d %H:%M:%S},{o:.2f},{o + amp:.2f},{o - amp:.2f},{o:.2f},{100 + i % 50}"
            )
            t += timedelta(minutes=15)
            i += 1
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def _isolate_in_process_declarations():
    """These tests must see the REAL gate.

    `tests/conftest.py` declares the whole pytest tmp tree in-process so ordinary tests can write
    throwaway corpora. That would mask every assertion in this module, whose fixtures also live in
    tmp_path — so drop the declarations for the duration and put them back afterwards.
    """
    saved_files, saved_trees = dict(cr._IN_PROCESS), list(cr._IN_PROCESS_TREES)
    cr.clear_in_process_declarations()
    yield
    cr.clear_in_process_declarations()
    cr._IN_PROCESS.update(saved_files)
    cr._IN_PROCESS_TREES.extend(saved_trees)


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    return _write_corpus(tmp_path / "SYNTH_M15.csv")


@pytest.fixture
def registry(tmp_path: Path) -> Path:
    p = tmp_path / "registry.json"
    p.write_text(json.dumps({"schema_version": cr.REGISTRY_SCHEMA_VERSION, "records": []}),
                 encoding="utf-8")
    return p


def _record(corpus: Path, registry: Path, **over) -> None:
    base = dict(path=cr.normalize_key(corpus), sha256=cr.sha256_file(corpus),
                timezone=cr.TZ_MT5_SERVER_NY_DST, user_reviewed=True, reviewed_by="tester",
                reviewed_at=cr.utcnow_iso())
    base.update(over)
    cr.save_registry({base["path"]: cr.ClockRecord(**base)}, registry)


# ── fail-closed ────────────────────────────────────────────────────────────────
def test_no_record_raises(corpus, registry):
    with pytest.raises(ClockProvenanceError, match="UNREVIEWED"):
        cr.require_reviewed_clock(corpus, registry=registry)


def test_unreviewed_record_raises(corpus, registry):
    _record(corpus, registry, user_reviewed=False, reviewed_by=None, reviewed_at=None)
    with pytest.raises(ClockProvenanceError, match="user_reviewed=false"):
        cr.require_reviewed_clock(corpus, registry=registry)


def test_reviewed_and_matching_sha_passes(corpus, registry):
    _record(corpus, registry)
    rec = cr.require_reviewed_clock(corpus, registry=registry)
    assert rec.user_reviewed is True
    assert rec.timezone == cr.TZ_MT5_SERVER_NY_DST


def test_sha_drift_reopens_review(corpus, registry):
    """A re-fetched corpus must re-open review even though a reviewed record exists."""
    _record(corpus, registry)
    with corpus.open("a", encoding="utf-8") as fh:
        fh.write("2025-12-31 23:45:00,1,1,1,1,1\n")
    with pytest.raises(ClockProvenanceError, match="STALE"):
        cr.require_reviewed_clock(corpus, registry=registry)


def test_missing_file_raises_filenotfound(tmp_path, registry):
    with pytest.raises(FileNotFoundError):
        cr.require_reviewed_clock(tmp_path / "nope.csv", registry=registry)


def test_corrupt_registry_is_an_error_not_an_empty_mapping(corpus, tmp_path):
    """Silently treating malformed governance state as absent is how a gate stops gating."""
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(ClockProvenanceError):
        cr.require_reviewed_clock(corpus, registry=bad)


# ── declaration integrity ──────────────────────────────────────────────────────
def test_reviewed_record_requires_attributable_reviewer():
    with pytest.raises(ValueError, match="reviewed_by"):
        cr.ClockRecord(path="x.csv", sha256="a", timezone="UTC", user_reviewed=True)


def test_illegal_timezone_rejected():
    with pytest.raises(ValueError, match="not legal"):
        cr.validate_timezone_value("Mars/Olympus")


def test_named_and_iana_timezones_accepted():
    for tz in (cr.TZ_UTC, cr.TZ_MT5_SERVER_NY_DST, "Europe/Athens", "America/New_York"):
        cr.validate_timezone_value(tz)


def test_non_boolean_user_reviewed_rejected():
    with pytest.raises(ValueError, match="non-boolean"):
        cr.ClockRecord.from_json(
            {"path": "x.csv", "sha256": "a", "timezone": "UTC", "user_reviewed": "true"}
        )


# ── double-conversion guard ────────────────────────────────────────────────────
def test_utc_corpus_under_utc_corrected_basis_raises(corpus, registry):
    """broker_clock's SCOPE: a genuinely-UTC corpus must NEVER take the MT5->UTC conversion."""
    _record(corpus, registry, timezone=cr.TZ_UTC)
    with pytest.raises(ClockProvenanceError, match="DOUBLE CONVERSION"):
        cr.require_reviewed_clock(corpus, registry=registry, basis=cr.BASIS_UTC_CORRECTED)


def test_utc_corpus_under_broker_local_basis_passes(corpus, registry):
    _record(corpus, registry, timezone=cr.TZ_UTC)
    assert cr.require_reviewed_clock(
        corpus, registry=registry, basis=cr.BASIS_BROKER_LOCAL
    ).timezone == cr.TZ_UTC


def test_mt5_corpus_under_utc_corrected_basis_passes(corpus, registry):
    _record(corpus, registry, timezone=cr.TZ_MT5_SERVER_NY_DST)
    cr.require_reviewed_clock(corpus, registry=registry, basis=cr.BASIS_UTC_CORRECTED)


def test_unknown_basis_rejected(corpus, registry):
    _record(corpus, registry)
    with pytest.raises(ClockProvenanceError, match="is not one of"):
        cr.require_reviewed_clock(corpus, registry=registry, basis="local_time")


# ── detector: advisory, deterministic, honest without a reference ──────────────
def test_detector_is_deterministic(corpus):
    a, b = detect_clock(corpus), detect_clock(corpus)
    assert json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)


def test_detector_without_reference_refuses_to_claim_a_dst_answer(corpus, tmp_path):
    """Regression for the defect that produced this design.

    The first T1 compared modal daily-open across DST regimes WITHIN one file and read a zero step
    as "fixed offset". That is structurally impossible: the broker's day boundary is defined in the
    broker's own clock, so the seasonal shift is absorbed. Measured on the real corpus it labelled
    a DST-observing feed LOOKS_FIXED_OFFSET_NON_UTC at HIGH confidence. Without a reference the
    detector must decline to reach a DST/offset conclusion at all.
    """
    for c in (corpus, _write_corpus(tmp_path / "OFFSET_M15.csv", day_start_hour=1)):
        d = detect_clock(c)
        assert d["tests"]["t1_seasonal_step"]["status"] == "NO_REFERENCE"
        assert d["tests"]["t2_reference_xcorr"]["status"] == "NO_REFERENCE"
        # It may say "consistent with UTC" off the day boundary alone (T3), but must never claim
        # a DST verdict, and must never do so with confidence.
        assert d["verdict"] != VERDICT_MT5_NY
        assert d["confidence"] == "low"

    # A corpus that does NOT open at midnight has no T3 signal either, so: no answer.
    assert detect_clock(tmp_path / "OFFSET_M15.csv")["verdict"] == VERDICT_INCONCLUSIVE


def test_detector_never_sets_user_reviewed(corpus):
    """Detection informs a review; it must never be able to satisfy one."""
    d = detect_clock(corpus)
    # No `user_reviewed` KEY anywhere in the bundle (the advisory banner mentions the phrase).
    def _keys(o):
        if isinstance(o, dict):
            for k, v in o.items():
                yield k
                yield from _keys(v)
        elif isinstance(o, list):
            for v in o:
                yield from _keys(v)
    assert "user_reviewed" not in set(_keys(d))
    assert d["authority"].startswith("ADVISORY_ONLY")


def test_detector_self_alignment_is_zero_shift(corpus):
    """A corpus measured against itself must show no offset - the method's own sanity check."""
    ref = load_raw_ohlcv(corpus)
    d = detect_clock(corpus, reference=ref)
    assert d["tests"]["t2_reference_xcorr"]["shift_hours"] == 0.0


# ── structural: the gate cannot be skipped by a new reader ─────────────────────
FILE_BACKED_READERS = (
    "src/runtime/backtest_v2.py",
    "src/data_ingestion/dataset_integrity.py",
    "src/data_ingestion/historical_fetcher.py",
    "src/analytics/sl_tp_comparator.py",
    "src/replay/timing_reconstructor.py",
)


@pytest.mark.parametrize("rel", FILE_BACKED_READERS)
def test_every_file_backed_reader_is_gated(rel):
    """Each module that OPENS an OHLCV corpus must invoke Phase 3.

    Phase 3 deliberately does NOT live inside `require_ohlcv_columns`: that function is also called
    on in-memory frames (`feature_pipeline.py`, `research/synthetic/story_builder.py`) which have
    no source file and therefore no clock to review. Gating it there would be wrong, so the
    obligation sits on the readers and this test is what keeps it honest.
    """
    src = (REPO_ROOT / rel).read_text(encoding="utf-8")
    assert "require_reviewed_clock" in src, (
        f"{rel} reads OHLCV from disk but never calls require_reviewed_clock(). "
        f"Phase 3 is not optional - see data_ingestion/clock_registry.py."
    )


def test_no_production_module_declares_in_process():
    """`declare_in_process` exists for test/synthetic corpora only.

    Production code never constructs the corpora it reads, so a call under `src/` would be a
    bypass of the human review gate wearing a helper's name. Keeping this mechanical is the whole
    reason the escape is a function call rather than an environment variable.
    """
    offenders = [
        p.relative_to(REPO_ROOT).as_posix()
        for p in (REPO_ROOT / "src").rglob("*.py")
        if p.name != "clock_registry.py"
        and ("declare_in_process" in p.read_text(encoding="utf-8", errors="ignore")
             or "declare_tree_in_process" in p.read_text(encoding="utf-8", errors="ignore"))
    ]
    assert not offenders, (
        "production modules must not declare their own clock provenance: " + ", ".join(offenders)
    )


def test_in_process_declaration_still_enforces_double_conversion(tmp_path):
    """The synthetic escape relaxes REVIEW, never the basis-compatibility invariant."""
    c = _write_corpus(tmp_path / "IP_M15.csv", days=2)
    cr.declare_in_process(c, cr.TZ_UTC, reason="unit test")
    try:
        with pytest.raises(ClockProvenanceError, match="DOUBLE CONVERSION"):
            cr.require_reviewed_clock(c, basis=cr.BASIS_UTC_CORRECTED)
    finally:
        cr.clear_in_process_declarations()


def test_registry_file_is_versioned_and_wellformed():
    """The committed registry must always parse - a corrupt one disables every read."""
    records = cr.load_registry()
    assert isinstance(records, dict)
    raw = json.loads(cr.registry_path().read_text(encoding="utf-8"))
    assert raw["schema_version"] == cr.REGISTRY_SCHEMA_VERSION
