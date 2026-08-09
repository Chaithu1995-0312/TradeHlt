"""Session-semantics floor — FM-052 schema v4.0 (2026-07-22).

Pins the two things that made "session" a four-way collision:

  1. There is exactly ONE feature encoder, and it is TOTAL (every hour maps to exactly one
     ordinal). Consumers must agree with it by construction, not by coincidence.
  2. The FEATURE and the FILTER are different questions with different vocabularies, and the
     module keeps them apart on purpose. A test that "unified" them would be enforcing the bug.
"""
from __future__ import annotations

import sys
from datetime import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from features import session_classifier as sc                      # noqa: E402


# ── 1. the feature is a TOTAL classification ────────────────────────────────────────────────
def test_every_hour_classifies_exactly_once():
    values = [sc.classify_session_feature(h) for h in range(24)]
    assert len(values) == 24
    assert all(v in sc.SESSION_ORDINAL_TO_NAME for v in values)


def test_out_of_range_hour_raises():
    for bad in (-1, 24, 99):
        with pytest.raises(ValueError, match=r"hour_of_day"):
            sc.classify_session_feature(bad)


def test_default_window_table_is_the_documented_one():
    """Pins the exact hour->session table. A change here IS a feature redefinition."""
    expected = {
        **{h: "ASIA" for h in range(0, 7)},
        **{h: "LONDON" for h in range(7, 12)},
        **{h: "OVERLAP" for h in range(12, 16)},
        **{h: "NEWYORK" for h in range(16, 21)},
        **{h: "CLOSED" for h in range(21, 24)},
    }
    got = {h: sc.decode_session_ordinal(sc.classify_session_feature(h)) for h in range(24)}
    assert got == expected


def test_all_five_values_are_reachable():
    """Guards against a degenerate window table where OVERLAP or CLOSED can never fire —
    the failure mode of adopting the FILTER's narrow non-overlapping bands as the feature."""
    seen = {sc.decode_session_ordinal(sc.classify_session_feature(h)) for h in range(24)}
    assert seen == {"ASIA", "LONDON", "NEWYORK", "OVERLAP", "CLOSED"}


def test_legacy_ordinals_are_preserved():
    """ASIA/LONDON/NEWYORK keep their v3.0 ordinals so old decoders stay correct for them."""
    assert (int(sc.SessionOrdinal.ASIA), int(sc.SessionOrdinal.LONDON),
            int(sc.SessionOrdinal.NEWYORK)) == (0, 1, 2)


# ── 2. precedence is deliberate, not incidental ─────────────────────────────────────────────
def test_london_ny_overlap_wins_over_either_alone():
    windows = {"ASIA": (0, 9), "LONDON": (7, 16), "NEWYORK": (12, 21)}
    cfg = {"session_windows_utc": windows}
    assert sc.decode_session_ordinal(sc.classify_session_feature(13, cfg)) == "OVERLAP"


def test_asia_london_overlap_resolves_to_london():
    """Documented tie-break: the later session wins, so 07:00-08:59 is LONDON, not ASIA."""
    cfg = {"session_windows_utc": {"ASIA": (0, 9), "LONDON": (7, 16), "NEWYORK": (12, 21)}}
    assert sc.decode_session_ordinal(sc.classify_session_feature(8, cfg)) == "LONDON"


def test_bounds_are_half_open():
    """[start, end) — matches the v3.0 `hour < end` convention it replaces."""
    cfg = {"session_windows_utc": {"ASIA": (0, 9), "LONDON": (7, 16), "NEWYORK": (12, 21)}}
    assert sc.decode_session_ordinal(sc.classify_session_feature(20, cfg)) == "NEWYORK"   # end-1
    assert sc.decode_session_ordinal(sc.classify_session_feature(21, cfg)) == "CLOSED"    # == end


# ── 3. config discipline: no silent defaults on the live path ───────────────────────────────
def test_missing_config_key_raises():
    with pytest.raises(KeyError, match="session_windows_utc"):
        sc.resolve_feature_windows({"some_other_key": 1})


def test_derived_values_cannot_be_configured():
    """OVERLAP/CLOSED are DERIVED. Letting them be configured would allow two sources of truth."""
    for name in ("OVERLAP", "CLOSED"):
        cfg = {"session_windows_utc": {"ASIA": (0, 9), "LONDON": (7, 16),
                                       "NEWYORK": (12, 21), name: (1, 2)}}
        with pytest.raises(ValueError, match="DERIVED|only ASIA"):
            sc.resolve_feature_windows(cfg)


@pytest.mark.parametrize("bounds", [(9, 9), (16, 7), (-1, 5), (0, 25)])
def test_invalid_windows_raise(bounds):
    cfg = {"session_windows_utc": {"ASIA": bounds, "LONDON": (7, 16), "NEWYORK": (12, 21)}}
    with pytest.raises(ValueError):
        sc.resolve_feature_windows(cfg)


def test_incomplete_window_set_raises():
    cfg = {"session_windows_utc": {"ASIA": (0, 9)}}
    with pytest.raises(ValueError, match="missing window"):
        sc.resolve_feature_windows(cfg)


# ── 4. scalar <-> vector parity (the candle_math/derived_math discipline) ───────────────────
def test_series_helper_matches_scalar():
    sc.set_series_config(None)
    try:
        hours = list(range(24)) * 3
        vec = sc.classify_session_feature_series(hours)
        assert [int(v) for v in vec] == [sc.classify_session_feature(h) for h in hours]
    finally:
        sc.set_series_config(None)


# ── 5. name normalization replaces the private per-consumer dicts ───────────────────────────
@pytest.mark.parametrize("raw,expect", [
    ("new_york", "NEWYORK"), ("NEW_YORK", "NEWYORK"), ("ny", "NEWYORK"),
    ("asian", "ASIA"), ("Asia", "ASIA"), ("london", "LONDON"),
    ("OFF_SESSION", "CLOSED"), ("overlap", "OVERLAP"), ("nonsense", None),
])
def test_canonical_session_name(raw, expect):
    assert sc.canonical_session_name(raw) == expect


def test_encode_decode_roundtrip():
    for s in sc.SessionOrdinal:
        assert sc.encode_session_ordinal(s.name) == int(s)
        assert sc.decode_session_ordinal(int(s)) == s.name


def test_encode_unknown_returns_sentinel():
    """-1 sentinel preserved from the v3.0 feature_schema.encode_session_ordinal contract."""
    assert sc.encode_session_ordinal("nope") == -1
    assert sc.encode_session_ordinal(None) == -1


def test_decode_out_of_domain_raises_rather_than_guessing():
    """A stored 5/6/-1 must fail loudly — silently mapping it would resurrect the collision."""
    for bad in (5, -1, 99):
        with pytest.raises(ValueError, match="outside the FM-052 domain"):
            sc.decode_session_ordinal(bad)


# ── 6. the filter is a DIFFERENT question and must stay different ───────────────────────────
def test_filter_returns_off_session_where_the_feature_never_can():
    """The distinction in one assertion: the filter admits 'none of my windows', the feature
    always names a state. Merging them would collapse this."""
    narrow = {"LONDON": (time(7, 0), time(10, 0)),
              "NEWYORK": (time(13, 0), time(16, 0)),
              "ASIA": (time(0, 0), time(3, 0))}
    assert sc.resolve_session_window(time(11, 30), narrow) == sc.OFF_SESSION
    # ... while the feature classifies that same instant as a real session
    assert sc.decode_session_ordinal(sc.classify_session_feature(11)) == "LONDON"


def test_filter_preserves_incumbent_inclusive_bounds():
    """backtest_v2._session used `start <= t <= end`. Behavior is preserved byte-for-byte;
    this module is only its canonical home."""
    narrow = {"LONDON": (time(7, 0), time(10, 0))}
    assert sc.resolve_session_window(time(10, 0), narrow) == "LONDON"     # inclusive end
    assert sc.resolve_session_window(time(10, 1), narrow) == sc.OFF_SESSION


def test_filter_windows_would_be_a_degenerate_feature():
    """Documents WHY the two concepts are not merged: using the filter's bands as the feature
    leaves most of the day uncovered."""
    narrow_hours = set(range(7, 10)) | set(range(13, 16)) | set(range(0, 3))
    assert len(narrow_hours) == 9, "filter bands cover only 9 of 24 hours"
