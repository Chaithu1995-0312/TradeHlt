"""P3 floors — events are pure, policy-free, derived, and regenerable.

Acceptance gate 4 lives here: a v2 rulepack must produce a new EventSet with the
episode bytes unchanged.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from research.episodes.builder import build_episode
from research.episodes.events import (
    RULEPACK_V1,
    RULEPACKS,
    EventEngine,
    Rulepack,
    register_rulepack,
)
from research.episodes.schema import EntrySnapshot
from research.episodes.store import to_dict


class Bar:
    def __init__(self, i, o, h, low, c, v=1.0):
        self.index, self.open, self.high, self.low, self.close, self.volume = i, o, h, low, c, v
        self.timestamp = f"2026-01-01 {i // 4:02d}:{(i % 4) * 15:02d}:00"


# entry 100, sl 98 (risk 2), tp 104.
#  t1 high 102 -> mfe 1.0R      t2 high 103 -> 1.5R
#  t3 low 98.5 -> mae -0.75R, close 98.6 -> distance_to_sl 0.6 => 0.3R
#  t4 high 106 -> mfe 3.0R and touches tp 104
SPEC = [
    (100.0, 100.2, 99.9, 100.0),
    (100.0, 102.0, 99.8, 101.5),
    (101.5, 103.0, 101.0, 102.5),
    (102.5, 102.6, 98.5, 98.6),
    (98.6, 106.0, 98.5, 105.0),
    (105.0, 105.5, 104.0, 104.5),
]
CANDLES = [Bar(i, *s) for i, s in enumerate(SPEC)]
ENTRY = EntrySnapshot(bar_index=0, timestamp="2026-01-01 00:00:00", direction="long",
                      entry_price=100.0, sl_price=98.0, tp_price=104.0)


def _ep(entry=ENTRY, candles=CANDLES, **kw):
    return build_episode(instrument="T", population="DETECTION_STREAM",
                         entry=entry, candles=candles, max_forward=5, **kw)


@pytest.fixture
def engine():
    return EventEngine()


@pytest.fixture(autouse=True)
def isolated_rulepacks():
    """Snapshot/restore the global registry so tests never depend on each other's
    registrations (or on running in file order)."""
    saved = dict(RULEPACKS)
    yield
    RULEPACKS.clear()
    RULEPACKS.update(saved)


V2 = Rulepack(
    rulepack_id="v2",
    detectors=("ENTRY", "REACHED_R", "BE_ELIGIBLE"),
    params={"r_thresholds": [1.0, 4.0], "be_mfe_r": 1.5},
)


# ── shape + determinism ───────────────────────────────────────────────────
def test_eventset_carries_rulepack_identity(engine):
    es = engine.detect(_ep())
    assert es.rulepack_id == "v1"
    assert es.rulepack_hash == RULEPACK_V1.hash()
    assert es.engine_hash and es.protocol_id == "OE_L1"


def test_detection_is_deterministic(engine):
    a, b = engine.detect(_ep()), engine.detect(_ep())
    assert a.events == b.events


def test_events_are_ordered_by_step(engine):
    ts = [e.t for e in engine.detect(_ep()).events]
    assert ts == sorted(ts)


def test_every_event_carries_a_real_bar_index(engine):
    ep = _ep()
    valid = {s.obs.t: s.obs.bar_index for s in ep.steps}
    for e in engine.detect(ep).events:
        assert valid[e.t] == e.bar_index


# ── v1 detector semantics ─────────────────────────────────────────────────
def test_entry_event_anchors_at_t0(engine):
    entry_ev = engine.detect(_ep()).first("ENTRY")
    assert entry_ev is not None and entry_ev.t == 0
    assert entry_ev.payload["risk_distance"] == 2.0


def test_reached_r_fires_once_per_threshold_at_first_crossing(engine):
    es = engine.detect(_ep())
    got = {e.payload["r"]: e.t for e in es.of_kind("REACHED_R")}
    # 0.5R and 1.0R both first satisfied at t1 (high 102 == +1.0R)
    assert got[0.5] == 1 and got[1.0] == 1
    assert got[1.5] == 2          # high 103
    assert got[2.0] == 4 and got[3.0] == 4   # high 106 == +3.0R
    assert len(es.of_kind("REACHED_R")) == 5


def test_new_mfe_only_on_strict_improvement(engine):
    es = engine.detect(_ep())
    ts = [e.t for e in es.of_kind("NEW_MFE")]
    assert ts == [1, 2, 4]        # t3 is adverse, t5 does not exceed t4


def test_new_mae_only_on_strict_deterioration(engine):
    es = engine.detect(_ep())
    ts = [e.t for e in es.of_kind("NEW_MAE")]
    assert ts == [1, 3]           # t1 low 99.8 is the first adverse, t3 low 98.5 deepens it


def test_be_eligible_uses_the_rulepack_threshold(engine):
    ev = engine.detect(_ep()).first("BE_ELIGIBLE")
    assert ev.t == 1 and ev.payload["threshold_r"] == 1.0


def test_sl_threat_is_close_based_not_wick_based(engine):
    """A wick toward the stop is an exit question; this measures pressure only."""
    es = engine.detect(_ep())
    ts = [e.t for e in es.of_kind("SL_THREAT")]
    # t3 closes at 98.6 -> 0.3R from the 98.0 stop... just outside the 0.25 default
    assert ts == []
    pack = Rulepack("threat_wide", ("SL_THREAT",), {"sl_threat_r": 0.5})
    register_rulepack(pack)
    assert [e.t for e in engine.detect(_ep(), "threat_wide").of_kind("SL_THREAT")] == [3]


def test_tp_touch_is_geometry_not_outcome(engine):
    ev = engine.detect(_ep()).first("TP_TOUCH")
    assert ev.t == 4 and ev.payload["tp_price"] == 104.0
    # Explicitly NOT an outcome claim — no policy verdict is emitted by the engine.
    assert "TP_HIT" not in engine.detect(_ep()).kinds()
    assert not {"SL_HIT", "EXIT", "TIMEOUT"} & engine.detect(_ep()).kinds()


def test_tp_touch_absent_without_a_target(engine):
    ep = _ep(replace(ENTRY, tp_price=None))
    assert engine.detect(ep).first("TP_TOUCH") is None


def test_short_direction_is_handled(engine):
    short = EntrySnapshot(bar_index=0, timestamp="2026-01-01 00:00:00", direction="short",
                          entry_price=100.0, sl_price=102.0, tp_price=96.0)
    es = engine.detect(_ep(short))
    # For a short, t3's dip to 98.5 is favorable: (100-98.5)/2 = 0.75R
    assert es.first("REACHED_R", r=0.5).t == 3


# ── the cross-check that stops a second definition of "reached 1R" ───────
def test_reached_1r_agrees_with_horizon_excursion(engine):
    from research.contracts import Signal
    from research.measurement.forward_walk import horizon_excursion

    class _B:
        def __init__(self, o):
            self.index, self.high, self.low, self.close = o.bar_index, o.high, o.low, o.close

    ep = _ep()
    sig = Signal(instrument="T", timestamp=ENTRY.timestamp, entry_index=0, direction="long",
                 entry=100.0, sl_atr_mult=1.0, tp_atr_mult=1.0, atr=ENTRY.risk_distance)
    expected = horizon_excursion(sig, [_B(s.obs) for s in ep.forward_steps], max_forward=5)
    got = engine.detect(ep).first("REACHED_R", r=1.0)
    assert got.t == expected["bars_to_first_1r"]


@pytest.mark.parametrize("seed", range(15))
def test_reached_1r_agrees_with_horizon_excursion_on_random_paths(seed, engine):
    import random

    from research.contracts import Signal
    from research.measurement.forward_walk import horizon_excursion

    rng = random.Random(seed)
    bars, price = [], 100.0
    for i in range(30):
        o = price
        c = max(1.0, o + rng.uniform(-1.5, 1.5))
        h = max(o, c) + abs(rng.uniform(0, 1.5))
        low = max(0.5, min(o, c) - abs(rng.uniform(0, 1.5)))
        bars.append(Bar(i, o, h, low, c))
        price = c

    class _B:
        def __init__(self, o):
            self.index, self.high, self.low, self.close = o.bar_index, o.high, o.low, o.close

    ep = build_episode(instrument="T", population="DETECTION_STREAM",
                       entry=ENTRY, candles=bars, max_forward=20)
    sig = Signal(instrument="T", timestamp=ENTRY.timestamp, entry_index=0, direction="long",
                 entry=100.0, sl_atr_mult=1.0, tp_atr_mult=1.0, atr=2.0)
    expected = horizon_excursion(sig, [_B(s.obs) for s in ep.forward_steps], max_forward=20)
    got = engine.detect(ep).first("REACHED_R", r=1.0)
    assert (got.t if got else None) == expected["bars_to_first_1r"]


def test_exact_1r_boundary_follows_the_kernel_not_a_rounded_ratio(engine):
    """Regression: real BNBUSDT float boundary that made the two definitions disagree.

    entry 601.3 / sl 602.4 short: risk = 1.1000000000000227 while a bar low of 600.2
    gives fav = 1.099999999999909 — i.e. fav < risk by 1.1e-13. The audited kernel
    says "not yet 1R". An earlier ratio-with-epsilon form said "reached", because
    fav/risk = 0.9999999999998966 rounds to exactly 1.0 at 8 dp.

    Measured impact before the fix: 2 disagreements per 2999 real episodes.
    """
    entry = EntrySnapshot(bar_index=0, timestamp="2026-01-01 00:00:00", direction="short",
                          entry_price=601.3, sl_price=602.4, tp_price=599.0)
    risk = entry.risk_distance
    fav = entry.entry_price - 600.2
    assert fav < risk, "fixture no longer reproduces the boundary"

    bars = [Bar(0, 601.3, 601.4, 601.2, 601.3),
            Bar(1, 601.3, 601.4, 600.2, 600.5),      # fav just SHORT of 1R
            Bar(2, 600.5, 600.6, 599.5, 599.8)]      # comfortably past 1R
    ep = build_episode(instrument="T", population="DETECTION_STREAM",
                       entry=entry, candles=bars, max_forward=2)

    got = engine.detect(ep).first("REACHED_R", r=1.0)
    assert got.t == 2, "detector fired on a bar the governing kernel does not count as 1R"

    from research.contracts import Signal
    from research.measurement.forward_walk import horizon_excursion

    class _B:
        def __init__(self, o):
            self.index, self.high, self.low, self.close = o.bar_index, o.high, o.low, o.close

    sig = Signal(instrument="T", timestamp=entry.timestamp, entry_index=0, direction="short",
                 entry=601.3, sl_atr_mult=1.0, tp_atr_mult=1.0, atr=risk)
    expected = horizon_excursion(sig, [_B(s.obs) for s in ep.forward_steps], max_forward=2)
    assert got.t == expected["bars_to_first_1r"]


def test_derived_layer_is_not_rounded():
    """Rounding the derived cache is what created the boundary bug — keep full precision."""
    from research.episodes.schema import recompute_derived

    entry = EntrySnapshot(bar_index=0, timestamp="t", direction="short",
                          entry_price=601.3, sl_price=602.4)
    ep = build_episode(instrument="T", population="DETECTION_STREAM", entry=entry,
                       candles=[Bar(0, 601.3, 601.4, 601.2, 601.3),
                                Bar(1, 601.3, 601.4, 600.2, 600.5)], max_forward=1)
    d = recompute_derived(entry, [s.obs for s in ep.steps])[1]
    assert d.mfe_r != 1.0                      # would be exactly 1.0 if rounded to 8dp
    assert d.mfe_r == pytest.approx(1.0, abs=1e-12)


# ── ACCEPTANCE GATE 4 — regenerability ───────────────────────────────────
def test_v2_rulepack_regenerates_without_touching_the_episode(engine):
    ep = _ep()
    before_hash = ep.content_hash()
    before_bytes = to_dict(ep)

    v1 = engine.detect(ep, "v1")

    register_rulepack(V2)
    v2 = engine.detect(ep, "v2")

    # a genuinely different EventSet …
    assert v2.rulepack_id == "v2" and v2.rulepack_hash != v1.rulepack_hash
    assert v2.events != v1.events
    assert v2.first("BE_ELIGIBLE").t == 2          # 1.5R threshold, not 1.0R
    assert v2.first("REACHED_R", r=4.0) is None    # never reached
    # … over a byte-identical episode.
    assert ep.content_hash() == before_hash
    assert to_dict(ep) == before_bytes


def test_rulepack_versions_coexist(engine):
    register_rulepack(V2)
    assert {"v1", "v2"} <= set(RULEPACKS)
    ep = _ep()
    assert engine.detect(ep, "v1").rulepack_hash != engine.detect(ep, "v2").rulepack_hash


def test_rulepacks_are_immutable():
    with pytest.raises(ValueError, match="already registered"):
        register_rulepack(Rulepack("v1", ("ENTRY",)))


def test_unknown_detector_is_rejected():
    with pytest.raises(ValueError, match="unknown detectors"):
        register_rulepack(Rulepack("bad_pack", ("NOT_A_DETECTOR",)))


def test_unknown_rulepack_is_rejected(engine):
    with pytest.raises(ValueError, match="unknown rulepack"):
        engine.detect(_ep(), "nope")


# ── works on observation-only corpora ────────────────────────────────────
def test_events_identical_on_lean_and_cached_episodes(engine):
    cached = _ep(cache_derived=True)
    lean = _ep(cache_derived=False)
    assert all(s.derived is None for s in lean.steps)
    assert engine.detect(lean).events == engine.detect(cached).events
