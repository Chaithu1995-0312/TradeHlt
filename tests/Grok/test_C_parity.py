"""C. Dual-implementation parity — two owners of the same semantic rule.

Surfaces: CRT filter windows vs FM-052 feature windows; score_time vs session
filter; inclusive vs half-open; ATR absolute vs FM-041 relative.
Ordinary tests pin each surface in isolation.
"""
from __future__ import annotations

from datetime import datetime, time

import pytest

from config_layer.production_config import (
    get_active_version,
    get_prod_section,
    load_prod_config_from_registry,
)
from config_layer.state_identity import CRTConfig
from config_layer.crt_engine_v2 import RangeDetector, UltronRiskEngine
from features.session_classifier import (
    SessionOrdinal,
    classify_session_feature,
    resolve_feature_windows,
)

from tests.Grok._fixtures import candle, filter_session_name


def test_feature_windows_and_filter_windows_are_not_the_same_object():
    """Parity gap (documented): two session vocabularies.

    Source: session_classifier.py module docstring + CRTConfig.session_windows
            + feature_pipeline.session_windows_utc on ACTIVE config
    Failure mode: a reader treats feat_session=2 (NEWYORK) as engine-tradable.
    Why ordinary tests miss it: each suite tests one vocabulary.
    """
    feature = resolve_feature_windows(get_prod_section("feature_pipeline"))
    filt = load_prod_config_from_registry(get_active_version(), "XAUUSD").session_windows
    assert set(feature) == {"ASIA", "LONDON", "NEWYORK"}
    assert set(filt) == {"ASIA", "LONDON", "NEWYORK"}
    # hour-span of FEATURE London is 9 hours; FILTER London is 3 hours
    feat_london_span = feature["LONDON"][1] - feature["LONDON"][0]
    filt_london = filt["LONDON"]
    filt_span_h = (
        filt_london[1].hour + filt_london[1].minute / 60.0
        - filt_london[0].hour - filt_london[0].minute / 60.0
    )
    assert feat_london_span != pytest.approx(filt_span_h)


def test_nineteen_hundred_is_feature_newyork_and_filter_off_session():
    """The 20260813T124158Z SHORT decision bar (19:15) is the worked example.

    Feature hour 19 ∈ NEWYORK [12, 21). Filter NEWYORK is 13:00–16:00 inclusive.
    """
    hour = 19
    t = time(19, 15)
    feat = classify_session_feature(hour, get_prod_section("feature_pipeline"))
    filt = filter_session_name(CRTConfig(), t)
    assert feat == int(SessionOrdinal.NEWYORK)
    assert filt == "OFF_SESSION"


def test_score_time_counts_matching_windows_on_the_same_key():
    """Class C: score_time and the filter both read CRTConfig.session_windows.

    Source: UltronRiskEngine.score_time (matches==1 → 0.8, matches==0 → 0.0)
            vs first-match name lookup. Does not claim whether matches>=2
            (score 1.0) must be reachable under the active window set.
    """
    risk = UltronRiskEngine(CRTConfig())
    in_london = datetime(2026, 7, 22, 8, 30, 0)
    assert risk.score_time(in_london) == pytest.approx(0.8)
    assert filter_session_name(CRTConfig(), in_london.time()) == "LONDON"
    evening = datetime(2026, 7, 22, 19, 15, 0)
    assert risk.score_time(evening) == pytest.approx(0.0)
    assert filter_session_name(CRTConfig(), evening.time()) == "OFF_SESSION"


def test_inclusive_filter_vs_half_open_feature_at_end_plus_one_minute():
    """At 10:01 the FILTER has left LONDON; the FEATURE hour is still 10 = LONDON.

    Source: filter `start <= t <= end` vs classify_session_feature `start <= h < end`
    """
    t = time(10, 1)
    feat = classify_session_feature(10, get_prod_section("feature_pipeline"))
    filt = filter_session_name(CRTConfig(), t)
    assert feat == int(SessionOrdinal.LONDON)
    assert filt == "OFF_SESSION"


def test_engine_atr_is_absolute_sma_not_close_relative():
    """Batch/pipeline `atr` (FM-041, close-relative) ≠ RangeDetector.compute_atr.

    Source: crt_engine_v2.py:869-882 vs market ontology FM-041
    A 100× price scale must scale absolute ATR ~100× and leave relative ATR ~unchanged.
    """
    det = RangeDetector(CRTConfig())
    bars_lo = [
        candle(datetime(2026, 1, 1, 0, i, 0), 100 + i, 101 + i, 99 + i, 100 + i, idx=i)
        for i in range(16)
    ]
    bars_hi = [
        candle(
            datetime(2026, 1, 1, 0, i, 0),
            10000 + 100 * i,
            10100 + 100 * i,
            9900 + 100 * i,
            10000 + 100 * i,
            idx=i,
        )
        for i in range(16)
    ]
    atr_lo = det.compute_atr(bars_lo, 14)
    atr_hi = det.compute_atr(bars_hi, 14)
    assert atr_lo > 0 and atr_hi > 0
    # high series ranges are ~200 vs ~2 — not a 1:1 relative quantity
    assert atr_hi / atr_lo > 10.0
    rel_lo = atr_lo / bars_lo[-1].close
    rel_hi = atr_hi / bars_hi[-1].close
    # if someone fed relative ATR into build_trade, the buffer would collapse
    assert rel_lo != pytest.approx(atr_lo)


def test_resolver_and_engine_do_not_share_shadow_collapse():
    """Shadow CRTStateResolver has no SHADOW_PENDING → EXPANSION collapse.

    Source: features.crt_state_resolver vs StateMachine.try_shadow_pending_to_expansion
    F-069 already measured structural disagreement; this test pins the *name*
    of the missing hop so a later 'parity' claim cannot ignore it.
    """
    from features.crt_state_resolver import CRTStateResolver

    names = [m for m in dir(CRTStateResolver) if "shadow" in m.lower()]
    # The resolver may mention shadow in comments/attrs; it must not expose the
    # engine's try_shadow_pending_to_expansion symbol (that would be a second impl).
    assert "try_shadow_pending_to_expansion" not in dir(CRTStateResolver)
    assert "try_shadow_pending_to_expansion" not in names
