"""P1 floors — schema identity, timeline construction, no-lookahead, F-022 discipline."""
from __future__ import annotations

from dataclasses import replace

import pytest

from research.episodes.builder import build_episode
from research.episodes.projectors.detection import project_record, project_stream
from research.episodes.schema import (
    Derived,
    EntrySnapshot,
    EpisodeProvenance,
    Observation,
    OpportunityEpisode,
    episode_id,
    recompute_derived,
)


class Bar:
    """Minimal candle stand-in matching the loader's duck type."""

    def __init__(self, i, o, h, low, c, v=1.0):
        self.index, self.open, self.high, self.low, self.close, self.volume = i, o, h, low, c, v
        self.timestamp = f"2026-01-01 {i // 4:02d}:{(i % 4) * 15:02d}:00"


@pytest.fixture
def candles():
    # A gentle uptrend with a dip at bar 3, so MFE and MAE are both non-trivial.
    spec = [
        (100.0, 101.0, 99.5, 100.5),
        (100.5, 102.0, 100.0, 101.5),
        (101.5, 103.0, 101.0, 102.5),
        (102.5, 102.8, 98.0, 99.0),    # adverse spike
        (99.0, 105.0, 98.8, 104.5),    # favorable spike
        (104.5, 106.0, 104.0, 105.5),
    ]
    return [Bar(i, *s) for i, s in enumerate(spec)]


@pytest.fixture
def entry():
    return EntrySnapshot(
        bar_index=0, timestamp="2026-01-01 00:00:00", direction="long",
        entry_price=100.0, sl_price=98.0, tp_price=104.0,
    )


# ── schema ────────────────────────────────────────────────────────────────
def test_entry_snapshot_geometry():
    e = EntrySnapshot(bar_index=0, timestamp="t", direction="long",
                      entry_price=100.0, sl_price=98.0, tp_price=104.0)
    assert e.risk_distance == 2.0
    assert e.tp_reward_mult == 2.0


def test_tp_reward_mult_is_none_without_a_target():
    e = EntrySnapshot(bar_index=0, timestamp="t", direction="long",
                      entry_price=100.0, sl_price=98.0, tp_price=None)
    assert e.tp_reward_mult is None


def test_provenance_has_no_exit_policy_hash():
    """Invariant 1: policy identity lives on the LabelSet, never the Episode."""
    assert not hasattr(EpisodeProvenance(), "exit_policy_hash")
    assert "exit_policy_hash" not in EpisodeProvenance.__dataclass_fields__


def test_derived_carries_no_policy_state():
    """Invariant 2: a trailing stop is policy state, not derived state."""
    for banned in ("stop", "tp", "trail_stop", "is_active"):
        assert banned not in Derived.__dataclass_fields__


def test_unknown_population_is_rejected(entry):
    with pytest.raises(ValueError, match="unknown population"):
        OpportunityEpisode(
            episode_id="x", population="NOT_A_POPULATION", instrument="T",
            timeframe="M15", entry=entry, steps=[], provenance=EpisodeProvenance(),
        )


def test_episode_id_is_deterministic_and_population_scoped():
    args = ("BNBUSDT", "2026-01-01 00:00:00", "long", 100.0, 98.0)
    assert episode_id(*args, "DETECTION_STREAM") == episode_id(*args, "DETECTION_STREAM")
    assert episode_id(*args, "DETECTION_STREAM") != episode_id(*args, "SPINE_TRADE")


# ── builder ───────────────────────────────────────────────────────────────
def test_timeline_starts_at_entry_bar(candles, entry):
    ep = build_episode(instrument="T", population="DETECTION_STREAM",
                       entry=entry, candles=candles, max_forward=3)
    assert [s.obs.t for s in ep.steps] == [0, 1, 2, 3]
    assert ep.steps[0].obs.bar_index == entry.bar_index
    assert ep.steps[0].obs.close == candles[0].close


def test_forward_steps_exclude_the_entry_bar(candles, entry):
    ep = build_episode(instrument="T", population="DETECTION_STREAM",
                       entry=entry, candles=candles, max_forward=3)
    fwd = ep.forward_steps
    assert [s.obs.t for s in fwd] == [1, 2, 3]
    # This is precisely forward_walk's no-lookahead precondition.
    assert all(s.obs.bar_index > entry.bar_index for s in fwd)


def test_entry_bar_has_no_derived_state(candles, entry):
    """A policy may not act on its own entry bar, so t=0 carries no path metrics."""
    ep = build_episode(instrument="T", population="DETECTION_STREAM",
                       entry=entry, candles=candles, max_forward=3)
    assert ep.steps[0].derived is None
    assert all(s.derived is not None for s in ep.steps[1:])


def test_timeline_is_truncated_at_the_end_of_data(candles, entry):
    ep = build_episode(instrument="T", population="DETECTION_STREAM",
                       entry=entry, candles=candles, max_forward=999)
    assert len(ep.steps) == len(candles)


def test_reindexed_slice_is_rejected(candles, entry):
    """Passing a slice silently breaks the global-index join — must fail loudly."""
    sliced = candles[1:]     # bar.index values no longer match their positions
    e = replace(entry, bar_index=0)
    with pytest.raises(ValueError, match="candle index mismatch"):
        build_episode(instrument="T", population="DETECTION_STREAM",
                      entry=e, candles=sliced, max_forward=3)


def test_zero_risk_distance_is_rejected(candles):
    e = EntrySnapshot(bar_index=0, timestamp="t", direction="long",
                      entry_price=100.0, sl_price=100.0)
    with pytest.raises(ValueError, match="non-positive risk_distance"):
        build_episode(instrument="T", population="DETECTION_STREAM",
                      entry=e, candles=candles)


def test_out_of_range_entry_is_rejected(candles, entry):
    with pytest.raises(ValueError, match="out of range"):
        build_episode(instrument="T", population="DETECTION_STREAM",
                      entry=replace(entry, bar_index=999), candles=candles)


# ── determinism (acceptance gate 1) ───────────────────────────────────────
def test_content_hash_is_deterministic(candles, entry):
    a = build_episode(instrument="T", population="DETECTION_STREAM",
                      entry=entry, candles=candles, max_forward=4)
    b = build_episode(instrument="T", population="DETECTION_STREAM",
                      entry=entry, candles=candles, max_forward=4)
    assert a.content_hash() == b.content_hash()
    assert a.episode_id == b.episode_id


def test_content_hash_ignores_regenerable_caches(candles, entry):
    """Dropping the Derived cache must not change canonical identity."""
    cached = build_episode(instrument="T", population="DETECTION_STREAM", entry=entry,
                           candles=candles, max_forward=4, cache_derived=True)
    lean = build_episode(instrument="T", population="DETECTION_STREAM", entry=entry,
                         candles=candles, max_forward=4, cache_derived=False)
    assert cached.content_hash() == lean.content_hash()


def test_content_hash_changes_with_geometry(candles, entry):
    a = build_episode(instrument="T", population="DETECTION_STREAM",
                      entry=entry, candles=candles, max_forward=4)
    b = build_episode(instrument="T", population="DETECTION_STREAM",
                      entry=replace(entry, sl_price=97.0), candles=candles, max_forward=4)
    assert a.content_hash() != b.content_hash()


# ── derived math ──────────────────────────────────────────────────────────
def test_recompute_derived_tracks_running_excursions(candles, entry):
    obs = [Observation(t=i, bar_index=i, timestamp="", open=b.open, high=b.high,
                       low=b.low, close=b.close, volume=b.volume)
           for i, b in enumerate(candles)]
    d = recompute_derived(entry, obs)
    assert d[0] is None
    # risk = 2.0; bar 1 high 102 -> mfe 2.0 -> 1.0R
    assert d[1].mfe_r == pytest.approx(1.0)
    # bar 3 low 98.0 -> mae -2.0 -> -1.0R, and MFE is a running max (3.0 from bar 2)
    assert d[3].mae_r == pytest.approx(-1.0)
    assert d[3].mfe_r == pytest.approx(1.5)
    # bar 4 high 105 -> mfe 5.0 -> 2.5R
    assert d[4].mfe_r == pytest.approx(2.5)
    assert d[4].bars_held == 4


def test_recompute_derived_is_direction_aware(candles):
    short = EntrySnapshot(bar_index=0, timestamp="t", direction="short",
                          entry_price=100.0, sl_price=102.0, tp_price=96.0)
    obs = [Observation(t=i, bar_index=i, timestamp="", open=b.open, high=b.high,
                       low=b.low, close=b.close, volume=b.volume)
           for i, b in enumerate(candles)]
    d = recompute_derived(short, obs)
    # For a short, the bar-3 dip to 98.0 is FAVORABLE: (100-98)/2 = 1.0R
    assert d[3].mfe_r == pytest.approx(1.0)


def test_recompute_derived_is_pure(candles, entry):
    obs = [Observation(t=i, bar_index=i, timestamp="", open=b.open, high=b.high,
                       low=b.low, close=b.close, volume=b.volume)
           for i, b in enumerate(candles)]
    assert recompute_derived(entry, obs) == recompute_derived(entry, obs)


# ── detection projector / F-022 ───────────────────────────────────────────
def _rec(**over):
    base = {
        "timestamp": "2026-01-01 00:00:00", "direction": "long",
        "entry": 100.0, "sl": 98.0, "tp": 104.0,
        "outcome": "TP_HIT", "rr_achieved": 2.0, "mfe": 5.0, "mae": -2.0,
    }
    base.update(over)
    return base


@pytest.fixture
def ts_to_idx(candles):
    return {b.timestamp: b.index for b in candles}


def test_projector_quarantines_stream_labels(candles, ts_to_idx):
    ep, reason = project_record(_rec(), candles, ts_to_idx, instrument="T")
    assert reason is None
    diag = ep.metadata["diagnostics"]
    assert diag["outcome"] == "TP_HIT" and diag["rr_achieved"] == 2.0
    # F-022: none of it may reach a canonical surface.
    canonical = ep.entry.__dict__ | {"steps": ep.steps}
    for banned in ("outcome", "rr_achieved", "mfe", "mae"):
        assert banned not in canonical


def test_projector_does_not_store_feature_vectors(candles, ts_to_idx):
    """Substrate §7: join features by bar_index; never inline them on Tier 1."""
    ep, _ = project_record(_rec(features={"a": 1.0}), candles, ts_to_idx, instrument="T")
    assert ep.entry.feature_vector is None
    assert ep.metadata["has_stream_features"] is True


@pytest.mark.parametrize("over,expected", [
    ({"entry": 100.0, "sl": 100.0}, "bad_geometry"),
    ({"direction": "sideways"}, "bad_geometry"),
    ({"timestamp": "1999-01-01 00:00:00"}, "no_candle_ts"),
])
def test_projector_skip_reasons(candles, ts_to_idx, over, expected):
    ep, reason = project_record(_rec(**over), candles, ts_to_idx, instrument="T")
    assert ep is None and reason == expected


def test_projector_skips_entry_on_the_last_bar(candles, ts_to_idx):
    last = candles[-1].timestamp
    ep, reason = project_record(_rec(timestamp=last), candles, ts_to_idx, instrument="T")
    assert ep is None and reason == "no_future_bars"


def test_project_stream_counts_and_filters(candles, ts_to_idx):
    records = [
        _rec(),
        _rec(instrument="OTHER"),
        {"not": "an opportunity"},
        _rec(sl=100.0),
    ]
    eps, skips = project_stream(records, candles, ts_to_idx, instrument="T")
    assert len(eps) == 1
    assert skips == {"wrong_instrument": 1, "not_opportunity": 1, "bad_geometry": 1}


def test_project_stream_respects_max_units(candles, ts_to_idx):
    records = [_rec(timestamp=b.timestamp) for b in candles[:4]]
    eps, _ = project_stream(records, candles, ts_to_idx, instrument="T", max_units=2)
    assert len(eps) == 2
