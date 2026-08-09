"""P4 floors — selections are views, immutable to chain, and hashable.

The reference query from substrate §14 lives here:
*reached 1R within 6 bars without exceeding 0.4R adverse.*
"""
from __future__ import annotations

import pytest

from research.episodes.builder import build_episode
from research.episodes.query import (
    EpisodeQuery,
    max_adverse_r_at_least,
    min_forward_bars,
    reached_r_within,
)
from research.episodes.schema import EntrySnapshot


class Bar:
    def __init__(self, i, o, h, low, c, v=1.0):
        self.index, self.open, self.high, self.low, self.close, self.volume = i, o, h, low, c, v
        self.timestamp = f"2026-01-{1 + i // 24:02d} {i % 24:02d}:00:00"


def _flat(n=12, base=100.0):
    return [Bar(i, base, base + 0.1, base - 0.1, base) for i in range(n)]


def _winner(n=12):
    """Reaches +1R (entry 100, sl 98 -> risk 2) at t=2, never worse than -0.2R."""
    bars = [Bar(0, 100.0, 100.2, 99.9, 100.0), Bar(1, 100.0, 101.0, 99.6, 100.8)]
    bars.append(Bar(2, 100.8, 102.5, 100.5, 102.0))          # +1.25R
    bars += [Bar(i, 102.0, 102.2, 101.8, 102.0) for i in range(3, n)]
    return bars


def _deep_drawdown(n=12):
    """Reaches +1R at t=2 but only after a -0.6R excursion at t=1."""
    bars = [Bar(0, 100.0, 100.2, 99.9, 100.0), Bar(1, 100.0, 100.1, 98.8, 98.9)]
    bars.append(Bar(2, 98.9, 102.5, 98.9, 102.0))
    bars += [Bar(i, 102.0, 102.2, 101.8, 102.0) for i in range(3, n)]
    return bars


def _slow_winner(n=14):
    """Reaches +1R only at t=9 — outside a 6-bar window."""
    bars = [Bar(i, 100.0, 100.3, 99.8, 100.0) for i in range(9)]
    bars.append(Bar(9, 100.0, 102.5, 100.0, 102.0))
    bars += [Bar(i, 102.0, 102.2, 101.8, 102.0) for i in range(10, n)]
    return bars


def _entry(ts="2026-01-01 00:00:00", direction="long", tp=104.0):
    return EntrySnapshot(bar_index=0, timestamp=ts, direction=direction,
                         entry_price=100.0, sl_price=98.0, tp_price=tp)


def _ep(candles, instrument="BNBUSDT", population="DETECTION_STREAM", entry=None, **kw):
    return build_episode(instrument=instrument, population=population,
                         entry=entry or _entry(), candles=candles, max_forward=10, **kw)


@pytest.fixture
def corpus():
    return [
        _ep(_winner()),                                        # 0 clean winner
        _ep(_deep_drawdown(), entry=_entry(ts="2026-01-02 00:00:00")),   # 1 deep DD
        _ep(_slow_winner(), entry=_entry(ts="2026-01-03 00:00:00")),     # 2 slow
        _ep(_flat(), entry=_entry(ts="2026-01-04 00:00:00")),            # 3 nothing
        _ep(_winner(), instrument="ETHUSDT", entry=_entry(ts="2026-01-05 00:00:00")),
        _ep(_winner(), population="SPINE_TRADE", entry=_entry(ts="2026-01-06 00:00:00")),
    ]


# ── THE REFERENCE QUERY (substrate §14) ──────────────────────────────────
def test_reference_query_reached_1r_within_6_bars_without_04r_adverse(corpus):
    result = (EpisodeQuery(corpus)
              .filter_instrument("BNBUSDT")
              .where_derived(reached_r_within(1.0, 6))
              .where_derived(max_adverse_r_at_least(-0.4))
              .run())

    assert result.n == 2, result.summary()
    # the clean winner (idx 0) and the SPINE_TRADE winner (idx 5) qualify;
    # deep-drawdown fails the adverse leg, slow fails the 6-bar leg, flat fails both.
    assert result.episodes[0].episode_id == corpus[0].episode_id
    assert corpus[1].episode_id not in result.episode_ids()
    assert corpus[2].episode_id not in result.episode_ids()
    assert corpus[3].episode_id not in result.episode_ids()


def test_reference_query_funnel_is_reported(corpus):
    result = (EpisodeQuery(corpus)
              .filter_instrument("BNBUSDT")
              .where_derived(reached_r_within(1.0, 6))
              .where_derived(max_adverse_r_at_least(-0.4))
              .run())
    steps = [s for s, _ in result.funnel]
    assert steps[0] == "input" and result.funnel[0][1] == 6
    counts = [k for _, k in result.funnel]
    assert counts == sorted(counts, reverse=True)   # monotonically narrowing
    assert "reached_r_within(r=1.0,bars=6)" in " ".join(steps)


# ── predicate factories ──────────────────────────────────────────────────
def test_reached_r_within_respects_the_bar_window(corpus):
    wide = EpisodeQuery([corpus[2]]).where_derived(reached_r_within(1.0, 10)).run()
    narrow = EpisodeQuery([corpus[2]]).where_derived(reached_r_within(1.0, 6)).run()
    assert wide.n == 1 and narrow.n == 0


def test_max_adverse_floor_is_inclusive_of_shallower_paths(corpus):
    lenient = EpisodeQuery([corpus[1]]).where_derived(max_adverse_r_at_least(-1.0)).run()
    strict = EpisodeQuery([corpus[1]]).where_derived(max_adverse_r_at_least(-0.4)).run()
    assert lenient.n == 1 and strict.n == 0


def test_min_forward_bars_guards_power(corpus):
    assert EpisodeQuery(corpus).where_derived(min_forward_bars(5)).run().n == 6
    assert EpisodeQuery(corpus).where_derived(min_forward_bars(99)).run().n == 0


def test_predicates_work_on_observation_only_episodes():
    lean = _ep(_winner(), cache_derived=False)
    assert all(s.derived is None for s in lean.steps)
    assert EpisodeQuery([lean]).where_derived(reached_r_within(1.0, 6)).run().n == 1


# ── episode-level filters ────────────────────────────────────────────────
def test_filter_population_and_instrument(corpus):
    assert EpisodeQuery(corpus).filter_population("SPINE_TRADE").run().n == 1
    assert EpisodeQuery(corpus).filter_instrument("ETHUSDT").run().n == 1


def test_filter_time_range_is_half_open(corpus):
    r = EpisodeQuery(corpus).filter_time_range("2026-01-02 00:00:00",
                                               "2026-01-04 00:00:00").run()
    ts = [e.entry.timestamp for e in r.episodes]
    assert ts == ["2026-01-02 00:00:00", "2026-01-03 00:00:00"]


def test_filter_direction(corpus):
    assert EpisodeQuery(corpus).filter_direction("long").run().n == 6
    assert EpisodeQuery(corpus).filter_direction("short").run().n == 0


def test_limit(corpus):
    assert EpisodeQuery(corpus).limit(2).run().n == 2


# ── joins ────────────────────────────────────────────────────────────────
def test_join_labels_attaches_a_labelset_per_selected_episode(corpus):
    r = EpisodeQuery(corpus).filter_instrument("BNBUSDT").join_labels("intrabar_fixed").run()
    assert set(r.labels) == set(r.episode_ids())
    assert all(ls.exit_policy_id == "intrabar_fixed" for ls in r.labels.values())


def test_where_label_filters_on_a_joined_field(corpus):
    r = (EpisodeQuery(corpus)
         .join_labels("intrabar_fixed")
         .where_label(lambda ls: ls.reached_1r, name="reached_1r")
         .run())
    assert 0 < r.n < len(corpus)                   # a real partition, not all-or-nothing
    assert all(ls.reached_1r for ls in r.labels.values())
    assert set(r.labels) == set(r.episode_ids())   # artifacts realigned to the final set


def test_join_events_and_where_events(corpus):
    r = (EpisodeQuery(corpus)
         .filter_instrument("BNBUSDT")
         .join_events("v1")
         .where_events(lambda es: es.first("REACHED_R", r=1.0) is not None,
                       name="reached_1r")
         .run())
    # of the 5 BNBUSDT episodes: winner, deep-drawdown, slow winner, spine winner.
    # The flat one never reaches 1R.
    assert r.n == 4
    assert set(r.events) == set(r.episode_ids())


def test_joins_run_only_over_survivors(corpus):
    """Lazy joins: filtering first must shrink the joined artifact count."""
    early = EpisodeQuery(corpus).filter_instrument("ETHUSDT").join_labels().run()
    late = EpisodeQuery(corpus).join_labels().run()
    assert len(early.labels) == 1 and len(late.labels) == 6


def test_where_label_without_join_raises(corpus):
    with pytest.raises(ValueError, match="requires join_labels"):
        EpisodeQuery(corpus).where_label(lambda ls: True)


def test_where_events_without_join_raises(corpus):
    with pytest.raises(ValueError, match="requires join_events"):
        EpisodeQuery(corpus).where_events(lambda es: True)


# ── immutability + identity ──────────────────────────────────────────────
def test_chaining_is_immutable_so_queries_can_branch(corpus):
    base = EpisodeQuery(corpus).filter_instrument("BNBUSDT")
    a = base.where_derived(reached_r_within(1.0, 6))
    b = base.where_derived(reached_r_within(3.0, 6))

    assert base.run().n == 5       # 5 of the 6 fixtures are BNBUSDT
    assert a.run().n == 3
    assert b.run().n == 0
    assert base.run().n == 5       # base is unchanged by either branch


def test_query_hash_is_stable_and_order_sensitive(corpus):
    q1 = EpisodeQuery(corpus).filter_instrument("BNBUSDT").where_derived(reached_r_within(1.0, 6))
    q2 = EpisodeQuery(corpus).filter_instrument("BNBUSDT").where_derived(reached_r_within(1.0, 6))
    q3 = EpisodeQuery(corpus).where_derived(reached_r_within(1.0, 6)).filter_instrument("BNBUSDT")
    assert q1.query_hash() == q2.query_hash()
    assert q1.query_hash() != q3.query_hash()


def test_query_hash_distinguishes_parameters(corpus):
    a = EpisodeQuery(corpus).where_derived(reached_r_within(1.0, 6))
    b = EpisodeQuery(corpus).where_derived(reached_r_within(1.0, 7))
    assert a.query_hash() != b.query_hash()


def test_result_carries_its_own_query_hash(corpus):
    q = EpisodeQuery(corpus).filter_instrument("BNBUSDT")
    assert q.run().query_hash == q.query_hash()


def test_describe_names_the_predicate_factories(corpus):
    q = EpisodeQuery(corpus).where_derived(max_adverse_r_at_least(-0.4, within=6))
    assert q.describe() == ["where_derived(max_adverse_r_at_least(floor_r=-0.4,within=6))"]


# ── results are VIEWS, not new truth ─────────────────────────────────────
def test_result_holds_references_and_mutates_nothing(corpus):
    before = [e.content_hash() for e in corpus]
    r = EpisodeQuery(corpus).filter_instrument("BNBUSDT").join_labels().join_events().run()
    assert [e.content_hash() for e in corpus] == before
    # identity, not copies
    assert r.episodes[0] is corpus[0]


def test_summary_is_serializable(corpus):
    import json

    s = EpisodeQuery(corpus).filter_instrument("BNBUSDT").run().summary()
    assert json.loads(json.dumps(s))["n_selected"] == 5


def test_derived_selection_is_forward_looking_and_carries_no_authority(corpus):
    """The reference query selects on the FUTURE path — its labels are circular.

    Documented as an executable warning rather than prose: the survivors of a
    derived-path filter win *because they were chosen for winning*. Measured on 4,999
    real BNBUSDT episodes this query returns 414 survivors at 98.1% TP_HIT / +1.97R —
    an artifact of the selection, not an edge (E-001).

    A tradeable predicate must be computable at t=0. `where_derived` never is.
    """
    selected = (EpisodeQuery(corpus)
                .where_derived(reached_r_within(1.0, 6))
                .where_derived(max_adverse_r_at_least(-0.4))
                .join_labels("intrabar_fixed")
                .run())
    everything = EpisodeQuery(corpus).join_labels("intrabar_fixed").run()

    # The filter guarantees its own success — every survivor reached 1R by construction.
    assert selected.n < everything.n
    assert all(ls.reached_1r for ls in selected.labels.values())
    assert not all(ls.reached_1r for ls in everything.labels.values())

    # The module says so where a reader will actually see it.
    import research.episodes.query as qmod

    assert "NOT AN EDGE" in qmod.__doc__
    assert "forward-looking" in qmod.__doc__.lower()


def test_empty_corpus_is_handled():
    r = EpisodeQuery([]).filter_instrument("X").where_derived(reached_r_within(1.0, 6)).run()
    assert r.n == 0 and r.n_input == 0
