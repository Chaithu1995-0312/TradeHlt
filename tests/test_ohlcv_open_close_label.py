"""Synthetic BC-2 open/close label scorer — no live MT5.

Covers the frozen prereg section 5 rules AND the emission-layer contract added by
the 2026-09-03 amendment (section 9): G-06 tri-state, the synthetic-cannot-prove
gate, the staleness guard, and one report shape on every exit path.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from research.ohlcv_open_close_label import (
    G06_CONTRADICTED,
    G06_PROVEN,
    G06_UNPROVEN,
    SOURCE_LIVE,
    SOURCE_SYNTHETIC,
    STALE_THRESHOLD_SECONDS,
    VERDICT_CLOSE,
    VERDICT_INSUFFICIENT,
    VERDICT_OPEN,
    VERDICT_OTHER,
    BarSnap,
    FetchSnap,
    _base_report,
    _finalize,
    classify_label_pair,
    on_m15_lattice,
    verify_admitted_artifact,
)

UTC = timezone.utc
T0 = datetime(2026, 9, 2, 12, 0, 0, tzinfo=UTC)


def _bar(ts: datetime, **ohlc) -> BarSnap:
    return BarSnap(
        timestamp=ts,
        open=ohlc.get("open", 3500.0),
        high=ohlc.get("high", 3501.0),
        low=ohlc.get("low", 3499.0),
        close=ohlc.get("close", 3500.5),
        volume=ohlc.get("volume", 100.0),
    )


def _snap(
    fetched_at: datetime,
    bars: list[BarSnap],
    clock: str = "mt5_tick",
    *,
    source: str = SOURCE_SYNTHETIC,
    skew: float | None = None,
) -> FetchSnap:
    return FetchSnap(
        fetched_at=fetched_at,
        symbol="XAUUSD",
        bars=tuple(bars),
        clock=clock,
        source=source,
        wall_clock_skew_seconds=skew,
    )


def _score(a: FetchSnap, b: FetchSnap) -> dict:
    # Hermetic: never depend on the admitted CSV being on this machine.
    return classify_label_pair(a, b, verify_admitted=False)


# ── frozen section 5 rules ─────────────────────────────────────────────────────
def test_lattice():
    assert on_m15_lattice(T0)
    assert not on_m15_lattice(T0 + timedelta(minutes=1))


def test_open_forming_mutation():
    a = _snap(
        T0 + timedelta(minutes=7),
        [_bar(T0 - timedelta(minutes=15)), _bar(T0, close=3500.5, high=3501.0, volume=100)],
    )
    b = _snap(
        T0 + timedelta(minutes=16),
        [_bar(T0, close=3502.0, high=3503.0, volume=180), _bar(T0 + timedelta(minutes=15))],
    )
    r = _score(a, b)
    assert r["verdict"] == VERDICT_OPEN
    assert r["g06_mt5"] == G06_PROVEN
    assert r["grants_g06_mt5"] is True
    assert r["ohlcv_closure"] == "UNCHANGED"


def test_close_forming_mutation():
    close_t = T0 + timedelta(minutes=15)
    a = _snap(
        T0 + timedelta(minutes=7),
        [_bar(T0), _bar(close_t, close=3500.5, high=3501.0, volume=100)],
    )
    b = _snap(
        close_t + timedelta(minutes=2),
        [_bar(close_t, close=3502.0, high=3503.0, volume=180)],
    )
    r = _score(a, b)
    assert r["verdict"] == VERDICT_CLOSE
    assert r["reason"] == "close_candidate_and_mutation"


def test_no_mutation_is_insufficient_not_close():
    a = _snap(T0 + timedelta(minutes=7), [_bar(T0, close=3500.5, volume=100)])
    b = _snap(T0 + timedelta(minutes=16), [_bar(T0, close=3500.5, volume=100)])
    r = _score(a, b)
    assert r["verdict"] == VERDICT_INSUFFICIENT
    assert r["reason"] == "no_mutation"
    assert r["grants_g06_mt5"] is False


def test_not_mid_interval():
    a = _snap(T0 + timedelta(seconds=10), [_bar(T0)])
    b = _snap(T0 + timedelta(minutes=16), [_bar(T0, close=3509.0)])
    r = _score(a, b)
    assert r["verdict"] == VERDICT_INSUFFICIENT
    assert r["reason"] == "not_mid_interval"


def test_not_post_close():
    a = _snap(T0 + timedelta(minutes=7), [_bar(T0)])
    b = _snap(T0 + timedelta(minutes=10), [_bar(T0, close=3509.0)])
    r = _score(a, b)
    assert r["verdict"] == VERDICT_INSUFFICIENT
    assert r["reason"] == "not_post_close"


def test_utc_now_clock_forbidden():
    a = _snap(T0 + timedelta(minutes=7), [_bar(T0)], clock="datetime_now_utc")
    b = _snap(T0 + timedelta(minutes=16), [_bar(T0, close=3509.0)], clock="datetime_now_utc")
    r = _score(a, b)
    assert r["verdict"] == VERDICT_INSUFFICIENT
    assert r["reason"] == "clock=unavailable"


def test_off_lattice_other():
    odd = T0 + timedelta(minutes=7)
    # Force mid-interval by setting fetched_at 7m after odd — not on lattice.
    a = _snap(odd + timedelta(minutes=7), [_bar(odd)])
    b = _snap(odd + timedelta(minutes=16), [_bar(odd, close=3509.0)])
    r = _score(a, b)
    assert r["verdict"] == VERDICT_OTHER
    assert r["reason"] == "t_not_on_m15_lattice"


def test_t_missing_in_b_other():
    a = _snap(T0 + timedelta(minutes=7), [_bar(T0)])
    b = _snap(T0 + timedelta(minutes=16), [_bar(T0 + timedelta(minutes=15))])
    r = _score(a, b)
    assert r["verdict"] == VERDICT_OTHER
    assert r["reason"] == "t_missing_in_b"


# ── D1: G-06 is "open-time labeling"; CLOSE contradicts it ─────────────────────
def test_close_contradicts_g06_and_does_not_grant_it():
    close_t = T0 + timedelta(minutes=15)
    a = _snap(T0 + timedelta(minutes=7), [_bar(T0), _bar(close_t, volume=100)])
    b = _snap(close_t + timedelta(minutes=2), [_bar(close_t, close=3502.0, volume=180)])
    r = _score(a, b)
    assert r["verdict"] == VERDICT_CLOSE
    assert r["g06_mt5"] == G06_CONTRADICTED
    assert r["grants_g06_mt5"] is False


def test_other_and_insufficient_leave_g06_unproven():
    a = _snap(T0 + timedelta(minutes=7), [_bar(T0)])
    b = _snap(T0 + timedelta(minutes=16), [_bar(T0 + timedelta(minutes=15))])
    assert _score(a, b)["g06_mt5"] == G06_UNPROVEN
    c = _snap(T0 + timedelta(seconds=10), [_bar(T0)])
    assert _score(c, b)["g06_mt5"] == G06_UNPROVEN


# ── D3: synthetic fixtures never flip governance ───────────────────────────────
def test_synthetic_open_is_not_executable_proof():
    a = _snap(T0 + timedelta(minutes=7), [_bar(T0, volume=100)])
    b = _snap(T0 + timedelta(minutes=16), [_bar(T0, close=3502.0, volume=180)])
    r = _score(a, b)
    assert r["verdict"] == VERDICT_OPEN
    assert r["source_a"] == SOURCE_SYNTHETIC
    assert r["executable_open_vs_close_label_proof"] is False


def test_live_open_without_admitted_match_is_not_proof():
    """A live OPEN still withholds the proof claim if the binding is unchecked."""
    a = _snap(T0 + timedelta(minutes=7), [_bar(T0, volume=100)], source=SOURCE_LIVE, skew=-10800.0)
    b = _snap(
        T0 + timedelta(minutes=16),
        [_bar(T0, close=3502.0, volume=180)],
        source=SOURCE_LIVE,
        skew=-10800.0,
    )
    r = classify_label_pair(a, b, verify_admitted=False)
    assert r["verdict"] == VERDICT_OPEN
    assert r["admitted_sha256_match"] is None
    assert r["executable_open_vs_close_label_proof"] is False


def test_verify_admitted_artifact_absent_returns_none_match(tmp_path):
    present, match = verify_admitted_artifact(tmp_path)
    assert present is False
    assert match is None


# ── D5 (amendment 9.1): staleness guard, one-directional ───────────────────────
def test_healthy_broker_offset_is_not_stale():
    """A live terminal legitimately reads ~UTC+3 (F-066). It must not be rejected."""
    skew = -10799.0  # measured on ICMarketsSC-Demo, 2026-09-02
    assert abs(skew) < STALE_THRESHOLD_SECONDS
    a = _snap(T0 + timedelta(minutes=7), [_bar(T0, volume=100)], source=SOURCE_LIVE, skew=skew)
    b = _snap(
        T0 + timedelta(minutes=16),
        [_bar(T0, close=3502.0, volume=180)],
        source=SOURCE_LIVE,
        skew=skew,
    )
    assert _score(a, b)["verdict"] == VERDICT_OPEN


def test_stale_live_feed_is_insufficient():
    stale = float(STALE_THRESHOLD_SECONDS + 1)
    a = _snap(T0 + timedelta(minutes=7), [_bar(T0, volume=100)], source=SOURCE_LIVE, skew=stale)
    b = _snap(
        T0 + timedelta(minutes=16),
        [_bar(T0, close=3502.0, volume=180)],
        source=SOURCE_LIVE,
        skew=stale,
    )
    r = _score(a, b)
    assert r["verdict"] == VERDICT_INSUFFICIENT
    assert r["reason"] == "stale_feed_a"
    assert r["grants_g06_mt5"] is False


def test_live_snapshot_without_measured_skew_fails_closed():
    a = _snap(T0 + timedelta(minutes=7), [_bar(T0, volume=100)], source=SOURCE_LIVE, skew=None)
    b = _snap(
        T0 + timedelta(minutes=16),
        [_bar(T0, close=3502.0, volume=180)],
        source=SOURCE_LIVE,
        skew=None,
    )
    r = _score(a, b)
    assert r["verdict"] == VERDICT_INSUFFICIENT
    assert r["reason"] == "stale_feed_unmeasured_a"


def test_staleness_guard_can_only_downgrade():
    """It never turns a non-verdict into OPEN/CLOSE — only the reverse."""
    fresh = _snap(T0 + timedelta(minutes=7), [_bar(T0, volume=100)], source=SOURCE_LIVE, skew=0.0)
    b = _snap(
        T0 + timedelta(minutes=16),
        [_bar(T0, close=3502.0, volume=180)],
        source=SOURCE_LIVE,
        skew=0.0,
    )
    stale = _snap(
        T0 + timedelta(minutes=7),
        [_bar(T0, volume=100)],
        source=SOURCE_LIVE,
        skew=float(STALE_THRESHOLD_SECONDS + 1),
    )
    assert _score(fresh, b)["verdict"] == VERDICT_OPEN
    assert _score(stale, b)["verdict"] == VERDICT_INSUFFICIENT


# ── D2: one report shape on every exit path ────────────────────────────────────
def test_every_exit_path_returns_the_same_key_set():
    close_t = T0 + timedelta(minutes=15)
    pairs = [
        # clock unavailable
        (
            _snap(T0 + timedelta(minutes=7), [_bar(T0)], clock="x"),
            _snap(T0 + timedelta(minutes=16), [_bar(T0)], clock="x"),
        ),
        # empty rates
        (_snap(T0 + timedelta(minutes=7), []), _snap(T0 + timedelta(minutes=16), [_bar(T0)])),
        # not mid interval
        (
            _snap(T0 + timedelta(seconds=10), [_bar(T0)]),
            _snap(T0 + timedelta(minutes=16), [_bar(T0, close=3509.0)]),
        ),
        # OPEN
        (
            _snap(T0 + timedelta(minutes=7), [_bar(T0, volume=100)]),
            _snap(T0 + timedelta(minutes=16), [_bar(T0, close=3502.0, volume=180)]),
        ),
        # CLOSE
        (
            _snap(T0 + timedelta(minutes=7), [_bar(T0), _bar(close_t, volume=100)]),
            _snap(close_t + timedelta(minutes=2), [_bar(close_t, close=3502.0, volume=180)]),
        ),
    ]
    keysets = {frozenset(_score(a, b)) for a, b in pairs}
    assert len(keysets) == 1, "score reports diverged in shape"
    # the capture-failure path (main's snapshot_capture_failed) must match too
    failure = _finalize(_base_report(verify_admitted=False))
    assert frozenset(failure) == keysets.pop()


def test_failure_report_carries_governance_keys():
    failure = _finalize(_base_report(verify_admitted=False))
    for key in ("probe_id", "prereg", "ohlcv_closure", "g06_mt5", "dataset_id"):
        assert key in failure
    assert failure["ohlcv_closure"] == "UNCHANGED"
    assert failure["grants_g06_mt5"] is False
    assert failure["executable_open_vs_close_label_proof"] is False
