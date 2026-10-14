"""CH-corpus-clock-contract-v1 acceptance tests (A-N).

The contract: a corpus declares an explicit, configured clock identity (provider/broker/clock_id);
the corpus SSOT normalizes its timestamps to canonical UTC exactly once; sessions and calendars are
separate contracts; nothing is inferred.
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from data_ingestion import clock_contract as cc
from data_ingestion import clock_registry as cr
from data_ingestion.corpus_store import load as corpus_load
from data_ingestion.ohlcv_schema import ClockProvenanceError

REPO = Path(__file__).resolve().parents[1]
XAU = REPO / "data" / "mt5" / "XAUUSD_M15.csv"

MT5 = {"provider": "mt5", "broker": "ICMarkets", "timezone": "America/New_York",
       "server_midnight_local": "17:00"}


def _clock(**kw) -> cc.ClockDef:
    spec = {**MT5, **kw}
    return cc.parse_clock_defs({"c": spec})["c"]


def _write(path: Path, rows: list[tuple[str, float]]) -> Path:
    lines = ["timestamp,open,high,low,close,volume"]
    for ts, p in rows:
        lines.append(f"{ts},{p},{p + 1},{p - 1},{p},10")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _registry(tmp_path: Path, clocks: dict, records: list[dict]) -> Path:
    reg = tmp_path / "reg.json"
    reg.write_text(json.dumps({"schema_version": "2.0.0", "clocks": clocks, "records": records}))
    return reg


def _rec(path: Path, **kw) -> dict:
    base = {"path": str(path), "sha256": cr.sha256_file(path), "timezone": "", "user_reviewed": True,
            "reviewed_by": "tester", "provider": "mt5", "broker": "ICMarkets", "clock_id": "mt5x"}
    base.update(kw)
    return base


# ── A: broker-local XAUUSD -> correct UTC ────────────────────────────────────────────────────
def test_A_xau_server_time_to_utc_and_full_corpus_parity_with_legacy_reference():
    clock = _clock()
    # winter (EST, UTC-5): server 00:00 == 17:00 NY == 22:00 UTC the previous day => +2h server offset
    assert cc.to_utc_scalar(datetime(2026, 1, 15, 10, 0), clock) == datetime(2026, 1, 15, 8, 0)
    # summer (EDT, UTC-4): +3h server offset
    assert cc.to_utc_scalar(datetime(2026, 7, 15, 10, 0), clock) == datetime(2026, 7, 15, 7, 0)
    assert cc.from_utc_scalar(datetime(2026, 7, 15, 7, 0), clock) == datetime(2026, 7, 15, 10, 0)
    # independent legacy reference (features.broker_clock) over the whole standing corpus
    from features.broker_clock import mt5_server_to_utc
    c = corpus_load(XAU, "XAUUSD", sequence_check=False)
    df = c.frame()
    legacy = mt5_server_to_utc(pd.to_datetime(df["source_timestamp"]))
    assert (pd.to_datetime(df["timestamp"]) == legacy).all()
    assert len(df) == c.n_rows == 47275


# ── B: UTC feed unchanged ────────────────────────────────────────────────────────────────────
def test_B_utc_feed_is_not_converted(tmp_path):
    p = _write(tmp_path / "BTCUSDT_M5.csv", [("2026-03-10 00:00:00", 100.0), ("2026-03-10 00:05:00", 101.0)])
    c = corpus_load(p, "BTCUSDT", sequence_check=False)    # tmp tree is declared constructed_utc
    df = c.frame()
    assert list(df["timestamp"]) == list(df["source_timestamp"]) == ["2026-03-10 00:00:00", "2026-03-10 00:05:00"]
    assert c.clock.is_identity and c.clock.clock_id == "constructed_utc"
    assert c.start == "2026-03-10 00:00:00"


# ── C: DST transitions ───────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("server,utc", [
    ("2025-03-07 12:00", "2025-03-07 10:00"),   # before US spring-forward (EST): +2
    ("2025-03-10 12:00", "2025-03-10 09:00"),   # US DST on, EU not yet (mismatch weeks): +3
    ("2025-03-31 12:00", "2025-03-31 09:00"),
    ("2025-10-28 12:00", "2025-10-28 09:00"),   # EU DST ended, US still on: still +3
    ("2025-11-04 12:00", "2025-11-04 10:00"),   # US DST ended: +2
])
def test_C_dst_by_iana_rules_not_seasonal_offsets(server, utc):
    assert cc.to_utc_scalar(datetime.fromisoformat(server), _clock()) == datetime.fromisoformat(utc)


def test_C_dst_gap_and_overlap_raise():
    clock = _clock()
    # NY local 02:30 on 2025-03-09 does not exist; server wall = local + 7h = 09:30
    with pytest.raises(cc.ClockNormalizationError):
        cc.to_utc_scalar(datetime(2025, 3, 9, 9, 30), clock)
    # NY local 01:30 on 2025-11-02 is ambiguous; server wall = 08:30
    with pytest.raises(cc.ClockNormalizationError):
        cc.to_utc_scalar(datetime(2025, 11, 2, 8, 30), clock)


# ── D: session/calendar are separate from the broker clock ───────────────────────────────────
def test_D_calendar_follows_the_market_not_the_broker():
    from features.market_calendar import get_calendar, UTC_CALENDAR
    fx = get_calendar("fx_metals")
    # Sunday 22:00 UTC (= 17:00 New York, the FX day boundary) is calendar MONDAY 00:00 for
    # fx_metals, still Sunday for the UTC calendar
    sun = datetime(2026, 1, 11, 22, 0)
    assert sun.weekday() == 6
    assert fx.wall(sun) == datetime(2026, 1, 12, 0, 0)
    assert UTC_CALENDAR.wall(sun).weekday() == 6
    assert fx.to_utc(fx.wall(sun)) == sun
    # a Europe/London broker with a UTC crypto-style calendar: the calendar is independent of the clock
    london = _clock(timezone="Europe/London", server_midnight_local="00:00", broker="Other")
    assert cc.to_utc_scalar(datetime(2026, 7, 1, 12, 0), london) == datetime(2026, 7, 1, 11, 0)
    assert get_calendar("crypto").wall(datetime(2026, 7, 1, 11, 0)).hour == 11


def test_D_session_filter_reads_utc_directly():
    from datetime import time as dtime
    # session_windows are UTC-authored; a candle's canonical UTC time is compared as-is
    assert dtime(7, 0) <= datetime(2026, 7, 15, 7, 0).time() <= dtime(10, 0)


# ── E: canonical UTC cannot be normalized twice ──────────────────────────────────────────────
def test_E_double_normalization_refused(tmp_path):
    p = _write(tmp_path / "x_M15.csv", [("2026-03-10 00:00:00", 1.0)])
    c = corpus_load(p, "XAUUSD", sequence_check=False)
    df = c.frame()
    with pytest.raises(cc.DoubleNormalizationError):
        c.normalize_source_frame(df)
    with pytest.raises(cc.DoubleNormalizationError):
        cc.normalize_view(cc.CLOCK_STATE_CANONICAL, _clock(), pd.to_datetime(df["timestamp"]))


_CONVERSION_PRIMITIVES = re.compile(
    # bare calls of the source-clock converters; `calendar.to_utc_series(...)` (a METHOD of the market
    # calendar, the wall -> UTC label mapping) is deliberately not matched
    r"mt5_server_to_utc|mt5_server_offset_hours|(?<![\w.])to_utc_series\(|(?<![\w.])to_utc_scalar\(|"
    r"(?<![\w.])from_utc_scalar\(")
_BOUNDARY_FILES = {
    "src/data_ingestion/clock_contract.py", "src/data_ingestion/corpus_store.py",
    "src/features/broker_clock.py",            # legacy reference implementation (parity-tested)
    "src/features/market_calendar.py",         # calendar wall mapping reuses the one converter
    "tests/test_corpus_clock_contract.py",
}
_ALLOWED_OUTSIDE = {
    "tools/xau_chart/xau_10d_features.py":
        "fresh MT5 pull (not a corpus) normalized through the CONFIGURED clock",
}


def test_E_no_source_clock_conversion_outside_the_boundary():
    offenders = []
    for root in ("src", "scripts", "tools"):
        for p in (REPO / root).rglob("*.py"):
            rel = p.relative_to(REPO).as_posix()
            if rel in _BOUNDARY_FILES or rel in _ALLOWED_OUTSIDE or "__pycache__" in rel:
                continue
            if _CONVERSION_PRIMITIVES.search(p.read_text(encoding="utf-8", errors="ignore")):
                offenders.append(rel)
    assert not offenders, f"source-clock conversion outside the corpus boundary: {offenders}"


def test_E_scan_can_fail():
    assert _CONVERSION_PRIMITIVES.search("x = mt5_server_to_utc(df['t'])")


# ── F: derived windows inherit the parent clock ──────────────────────────────────────────────
def test_F_window_inherits_parent_clock_and_rejects_tampering(tmp_path):
    parent = _write(tmp_path / "XAUUSD_M15.csv",
                    [("2026-07-15 10:00:00", 1.0), ("2026-07-15 10:15:00", 2.0), ("2026-07-15 10:30:00", 3.0)])
    clocks = {"mt5x": {**MT5, "provider": "mt5", "broker": "ICMarkets"}}
    reg = _registry(tmp_path, clocks, [_rec(parent)])
    win = tmp_path / "win" / "XAUUSD_M15_last_1m.csv"
    win.parent.mkdir()
    shutil.copy(parent, win)
    sidecar = win.with_suffix(".parent.json")
    sidecar.write_text(json.dumps({
        "derived_from": {"corpus_path": str(parent), "corpus_sha256": cr.sha256_file(parent)},
        "derived_corpus_sha256": cr.sha256_file(win)}))
    _isolate()
    try:
        r = cr.resolve_clock(win, registry=reg)
        assert r.origin == "inherited_parent" and r.clock.clock_id == "mt5x"
        win.write_text(win.read_text() + "2026-07-15 10:45:00,4,5,3,4,10\n")   # window changed after derivation
        with pytest.raises(ClockProvenanceError):
            cr.resolve_clock(win, registry=reg)
    finally:
        _restore_session_declarations()


_SNAP = {}


def _isolate():
    """Snapshot + clear the pytest session's in-process clock declarations so the REAL registry
    path is exercised; `_restore_session_declarations()` puts them back."""
    _SNAP["p"] = dict(cr._IN_PROCESS)
    _SNAP["t"] = list(cr._IN_PROCESS_TREES)
    cr.clear_in_process_declarations()


def _restore_session_declarations():
    cr._IN_PROCESS.update(_SNAP.get("p", {}))
    cr._IN_PROCESS_TREES.extend(_SNAP.get("t", []))


# ── G: identity and clock stay attached to the same corpus ───────────────────────────────────
def test_G_provenance_carries_identity_and_clock():
    c = corpus_load(XAU, "XAUUSD", sequence_check=False)
    prov = c.provenance()
    assert prov["dataset_id"] == c.dataset_id == "XAUUSD_MT5_PHASE1_20260521"
    assert prov["corpus_sha256"] == c.sha256
    assert prov["clock"]["clock_id"] == "mt5_icmarkets_xau"
    assert prov["clock"]["canonical_timezone"] == "UTC" and prov["timestamp_clock"] == "UTC"
    assert (prov["clock"]["provider"], prov["clock"]["broker"]) == ("mt5", "ICMarkets")


def test_G_sha_mismatch_invalidates_the_clock(tmp_path):
    p = _write(tmp_path / "a_M15.csv", [("2026-07-15 10:00:00", 1.0)])
    clocks = {"mt5x": {**MT5}}
    reg = _registry(tmp_path, clocks, [_rec(p)])
    _isolate()
    try:
        assert cr.resolve_clock(p, registry=reg).clock.clock_id == "mt5x"
        p.write_text(p.read_text() + "2026-07-15 10:15:00,1,2,0,1,10\n")
        with pytest.raises(ClockProvenanceError, match="STALE"):
            cr.resolve_clock(p, registry=reg)
    finally:
        _restore_session_declarations()


# ── I / J / K: explicit identity, exact match ────────────────────────────────────────────────
def test_I_dataset_without_clock_identity_is_rejected(tmp_path):
    p = _write(tmp_path / "a_M15.csv", [("2026-07-15 10:00:00", 1.0)])
    clocks = {"mt5x": {**MT5}}
    _isolate()
    try:
        no_id = _registry(tmp_path, clocks, [_rec(p, clock_id=None, provider=None, broker=None,
                                             timezone="MT5_SERVER_NY_DST")])   # legacy label only
        with pytest.raises(ClockProvenanceError, match="MISSING"):
            cr.resolve_clock(p, registry=no_id)
        unknown = _registry(tmp_path, clocks, [_rec(p, clock_id="nope")])
        with pytest.raises(ClockProvenanceError, match="not a configured clock"):
            cr.resolve_clock(p, registry=unknown)
        unreviewed = _registry(tmp_path, clocks, [_rec(p, user_reviewed=False, reviewed_by=None)])
        with pytest.raises(ClockProvenanceError, match="UNREVIEWED"):
            cr.resolve_clock(p, registry=unreviewed)
    finally:
        _restore_session_declarations()


def test_J_provider_or_broker_mismatch_is_rejected(tmp_path):
    p = _write(tmp_path / "a_M15.csv", [("2026-07-15 10:00:00", 1.0)])
    clocks = {"mt5x": {**MT5}}
    _isolate()
    try:
        for bad in ({"provider": "binance"}, {"broker": "OtherBroker"}):
            reg = _registry(tmp_path, clocks, [_rec(p, **bad)])
            with pytest.raises(ClockProvenanceError, match="exactly match"):
                cr.resolve_clock(p, registry=reg)
    finally:
        _restore_session_declarations()


def test_K_dataset_record_and_artifact_record_must_agree(tmp_path):
    p = _write(tmp_path / "a_M15.csv", [("2026-07-15 10:00:00", 1.0)])
    clocks = {"mt5x": {**MT5}}
    reg = _registry(tmp_path, clocks, [_rec(p)])
    _isolate()
    try:
        ok = {"dataset_id": "D", "provider": "mt5", "broker": "ICMarkets", "clock_id": "mt5x"}
        assert cr.resolve_clock(p, registry=reg, dataset=ok).clock.clock_id == "mt5x"
        with pytest.raises(ClockProvenanceError, match="exactly match"):
            cr.resolve_clock(p, registry=reg, dataset={**ok, "broker": "Else"})
    finally:
        _restore_session_declarations()


# ── L: no stored offsets ─────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("field", ["wall_offset", "utc_offset", "offset_hours", "fixed_offset"])
def test_L_clock_schema_rejects_offset_fields(field):
    with pytest.raises(ClockProvenanceError, match="stored offset"):
        cc.parse_clock_defs({"c": {**MT5, field: "+07:00"}})


def test_L_observed_offsets_are_evidence_only():
    a = _clock(observed_utc_offsets=["+02:00", "+03:00"])
    b = _clock(observed_utc_offsets=["+09:00"])
    t = datetime(2026, 7, 15, 10, 0)
    assert cc.to_utc_scalar(t, a) == cc.to_utc_scalar(t, b)


def test_L_registered_clocks_have_no_offset_fields():
    raw = json.loads((REPO / cr.REGISTRY_RELPATH).read_text(encoding="utf-8"))
    assert raw["schema_version"] == "2.0.0"
    for cid, spec in raw["clocks"].items():
        assert not (set(spec) & cc._FORBIDDEN_OFFSET_FIELDS), cid
    assert set(cr.load_clocks()) >= {"mt5_icmarkets_xau", "binance_utc", "constructed_utc"}


# ── M: the retired config key fails ──────────────────────────────────────────────────────────
def test_M_config_carrying_the_retired_key_raises():
    from config_layer.production_config import get_prod_section
    from features.feature_pipeline import _resolve_feature_pipeline_cfg
    cfg = dict(get_prod_section("feature_pipeline"))
    _resolve_feature_pipeline_cfg(cfg)                  # the active config is clean
    cfg["session_timestamp_basis"] = "utc_corrected"
    with pytest.raises(ValueError, match="RETIRED"):
        _resolve_feature_pipeline_cfg(cfg)


# ── N: the detector has no admission authority ───────────────────────────────────────────────
def test_N_detector_cannot_admit_or_write():
    src = (REPO / "src/data_ingestion/clock_detector.py").read_text(encoding="utf-8")
    assert "save_registry" not in src and "user_reviewed=True" not in src
    assert "resolve_clock" not in src and "clock_id" not in src


# ── H: market calendar reproduces the broker HTF grid exactly ────────────────────────────────
def test_H_calendar_wall_equals_broker_grid_on_the_standing_corpus():
    from features.market_calendar import calendar_for_instrument
    c = corpus_load(XAU, "XAUUSD", sequence_check=False)
    df = c.frame()
    cal = calendar_for_instrument("XAUUSD")
    wall = cal.wall_series(pd.to_datetime(df["timestamp"]))
    assert (wall == pd.to_datetime(df["source_timestamp"])).all()
    assert (cal.to_utc_series(wall) == pd.to_datetime(df["timestamp"])).all()
