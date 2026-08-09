"""P5 floors — Tier 2 and Tier 3 are idempotent, derived views. Never truth."""
from __future__ import annotations

import numpy as np
import pytest

from research.episodes.builder import build_episode
from research.episodes.events import EventEngine
from research.episodes.flat import (
    DERIVED_COLUMNS,
    columns,
    flat_rows,
    flat_table,
    read_flat,
    write_flat,
)
from research.episodes.policy import PolicyEvaluator
from research.episodes.schema import EntrySnapshot
from research.episodes.tensors import (
    CHANNELS,
    DEFAULT_CHANNELS,
    TensorSpec,
    build_tensor,
    load_tensor,
    path_relative,
    save_tensor,
)


class Bar:
    def __init__(self, i, o, h, low, c, v=1.0):
        self.index, self.open, self.high, self.low, self.close, self.volume = i, o, h, low, c, v
        self.timestamp = f"2026-01-01 {i // 4:02d}:{(i % 4) * 15:02d}:00"


SPEC = [
    (100.0, 100.2, 99.9, 100.0),
    (100.0, 102.0, 99.8, 101.5),
    (101.5, 103.0, 101.0, 102.5),
    (102.5, 102.6, 98.5, 98.6),
    (98.6, 106.0, 98.5, 105.0),
]
CANDLES = [Bar(i, *s) for i, s in enumerate(SPEC)]
ENTRY = EntrySnapshot(bar_index=0, timestamp="2026-01-01 00:00:00", direction="long",
                      entry_price=100.0, sl_price=98.0, tp_price=104.0)
SHORT = EntrySnapshot(bar_index=0, timestamp="2026-01-01 00:00:00", direction="short",
                      entry_price=100.0, sl_price=102.0, tp_price=96.0)


def _ep(entry=ENTRY, **kw):
    return build_episode(instrument="T", population="DETECTION_STREAM",
                         entry=entry, candles=CANDLES, max_forward=4, **kw)


@pytest.fixture
def corpus():
    return [_ep(), _ep(SHORT)]


# ═══════════════════════════ TIER 2 — FLAT ═══════════════════════════
def test_one_row_per_timestep(corpus):
    rows = flat_rows(corpus[0])
    assert len(rows) == len(corpus[0].steps) == 5
    assert [r["t"] for r in rows] == [0, 1, 2, 3, 4]


def test_entry_bar_carries_blank_derived_not_zeros(corpus):
    """t=0 has no path state; blanks stop a reader mistaking it for a flat path."""
    row = flat_rows(corpus[0])[0]
    assert all(row[c] is None for c in DERIVED_COLUMNS)
    assert flat_rows(corpus[0])[1]["mfe_r"] is not None


def test_entry_bar_can_be_excluded(corpus):
    rows = flat_rows(corpus[0], include_entry_bar=False)
    assert [r["t"] for r in rows] == [1, 2, 3, 4]


def test_projection_is_idempotent(corpus):
    """Tier 2 is derived — rebuilding must reproduce it exactly."""
    assert flat_rows(corpus[0]) == flat_rows(corpus[0])
    assert list(flat_table(corpus)) == list(flat_table(corpus))


def test_projection_matches_the_episode_it_came_from(corpus):
    ep = corpus[0]
    for row, step in zip(flat_rows(ep), ep.steps):
        assert row["bar_index"] == step.obs.bar_index
        assert row["close"] == step.obs.close
        assert row["episode_id"] == ep.episode_id
        assert row["risk_distance"] == ep.entry.risk_distance


def test_works_on_observation_only_episodes():
    lean = _ep(cache_derived=False)
    rows = flat_rows(lean)
    assert rows[1]["mfe_r"] == pytest.approx(1.0)   # rebuilt, not blank


def test_labels_and_events_are_opt_in(corpus):
    ep = corpus[0]
    assert "label_outcome" not in flat_rows(ep)[0]
    assert "event_kinds" not in flat_rows(ep)[0]

    ls = PolicyEvaluator(max_forward=4).evaluate(ep, "intrabar_fixed")
    es = EventEngine().detect(ep)
    rows = flat_rows(ep, labels=ls, events=es)
    assert rows[0]["label_outcome"] == ls.outcome
    assert all(r["label_outcome"] == ls.outcome for r in rows)   # denormalized
    assert "ENTRY" in rows[0]["event_kinds"]


def test_columns_are_stable_and_ordered():
    base = columns()
    assert base[:4] == ["episode_id", "population", "instrument", "timeframe"]
    assert "t" in base and "mfe_r" in base
    assert columns(with_labels=True)[-len(base):] != base   # labels appended, not inserted
    assert columns() == base                                # pure


def test_write_read_round_trip(tmp_path, corpus):
    manifest = write_flat(corpus, tmp_path)
    assert manifest["n_episodes"] == 2
    assert manifest["n_rows"] == 10
    assert manifest["tier"] == 2 and manifest["derived_from"] == "tier1_episodes"

    back = list(read_flat(manifest["path"]))
    assert len(back) == 10
    assert back[0]["episode_id"] == corpus[0].episode_id
    assert back[0]["mfe_r"] == ""            # t=0 blank survives as empty
    assert float(back[1]["mfe_r"]) == pytest.approx(1.0)


def test_write_with_joins(tmp_path, corpus):
    ev, eng = PolicyEvaluator(max_forward=4), EventEngine()
    labels = {e.episode_id: ev.evaluate(e, "intrabar_fixed") for e in corpus}
    events = {e.episode_id: eng.detect(e) for e in corpus}
    m = write_flat(corpus, tmp_path, labels=labels, events=events)
    assert "label_outcome" in m["columns"] and "event_kinds" in m["columns"]
    assert all("label_outcome" in r for r in read_flat(m["path"]))


# ═══════════════════════════ TIER 3 — TENSORS ═══════════════════════════
def test_shape_and_mask(corpus):
    b = build_tensor(corpus, TensorSpec(max_steps=6))
    assert b.shape == (2, 6, len(DEFAULT_CHANNELS))
    # 4 real forward steps per episode, padded to 6
    assert b.mask.sum() == 8
    assert b.mask[0].tolist() == [1, 1, 1, 1, 0, 0]
    assert b.lengths == [4, 4]


def test_entry_bar_is_excluded_from_the_path(corpus):
    """t=0 carries no path state, so the tensor starts at the first forward bar."""
    b = build_tensor(corpus, TensorSpec(channels=("mfe_r",), max_steps=6))
    assert b.channel("mfe_r")[0, 0] == pytest.approx(1.0)   # t=1, not t=0


def test_padding_uses_the_declared_value(corpus):
    b = build_tensor(corpus, TensorSpec(max_steps=6, pad_value=-99.0))
    assert (b.X[0, 4:, :] == -99.0).all()
    assert (b.mask[0, 4:] == 0).all()


def test_truncation_to_max_steps(corpus):
    b = build_tensor(corpus, TensorSpec(max_steps=2))
    assert b.shape[1] == 2 and b.lengths == [2, 2]


def test_channels_are_r_normalized_and_direction_signed(corpus):
    """A long and a short with mirrored geometry must produce comparable rows."""
    b = build_tensor(corpus, TensorSpec(channels=("close_r",), max_steps=4))
    long_t1 = b.channel("close_r")[0, 0]     # close 101.5, entry 100, risk 2 -> +0.75
    short_t1 = b.channel("close_r")[1, 0]    # same bar, short: -(101.5-100)/2 -> -0.75
    assert long_t1 == pytest.approx(0.75)
    assert short_t1 == pytest.approx(-0.75)


def test_derived_channels_are_already_direction_aware(corpus):
    b = build_tensor(corpus, TensorSpec(channels=("mfe_r",), max_steps=4))
    # long's favorable bar is the short's adverse one, so their MFEs differ
    assert b.channel("mfe_r")[0, 0] == pytest.approx(1.0)
    assert b.channel("mfe_r")[1, 0] == pytest.approx(0.1)


def test_build_is_deterministic_and_order_preserving(corpus):
    a, b = build_tensor(corpus), build_tensor(corpus)
    assert np.array_equal(a.X, b.X) and np.array_equal(a.mask, b.mask)
    assert a.episode_ids == [e.episode_id for e in corpus]


def test_works_on_observation_only_episodes():
    lean = build_tensor([_ep(cache_derived=False)], TensorSpec(channels=("mfe_r",), max_steps=4))
    cached = build_tensor([_ep(cache_derived=True)], TensorSpec(channels=("mfe_r",), max_steps=4))
    assert np.array_equal(lean.X, cached.X)


def test_unknown_channel_is_rejected():
    with pytest.raises(ValueError, match="unknown channels"):
        TensorSpec(channels=("not_a_channel",))


def test_empty_channels_rejected():
    with pytest.raises(ValueError, match="at least one channel"):
        TensorSpec(channels=())


def test_spec_hash_distinguishes_views():
    a = TensorSpec(channels=("mfe_r",), max_steps=10)
    b = TensorSpec(channels=("mfe_r",), max_steps=20)
    c = TensorSpec(channels=("mae_r",), max_steps=10)
    assert len({a.spec_hash(), b.spec_hash(), c.spec_hash()}) == 3
    assert a.spec_hash() == TensorSpec(channels=("mfe_r",), max_steps=10).spec_hash()


def test_path_relative_matches_the_ic002_identity(corpus):
    """Same transform as ic002_entry_evolution.schema.path_relative_row."""
    from research.ic002_entry_evolution.schema import path_relative_row

    b = build_tensor(corpus, TensorSpec(channels=("close_r", "range_r"), max_steps=4))
    z = path_relative(b)
    expected = path_relative_row(b.X[0, 2, :].tolist(), b.X[0, 0, :].tolist())
    assert z[0, 2, :].tolist() == pytest.approx(expected)
    assert z[0, 0, :].tolist() == pytest.approx([0.0, 0.0])   # relative to itself


def test_path_relative_zeroes_padding(corpus):
    b = build_tensor(corpus, TensorSpec(max_steps=6))
    z = path_relative(b)
    assert (z[0, 4:, :] == 0.0).all()


def test_save_load_round_trip(tmp_path, corpus):
    b = build_tensor(corpus, TensorSpec(channels=("mfe_r", "mae_r"), max_steps=6))
    manifest = save_tensor(b, tmp_path)
    assert manifest["tier"] == 3 and manifest["authority"].startswith("none")

    back = load_tensor(tmp_path)
    assert np.array_equal(back.X, b.X) and np.array_equal(back.mask, b.mask)
    assert back.episode_ids == b.episode_ids
    assert back.spec == b.spec
    assert back.spec.spec_hash() == b.spec.spec_hash()


def test_summary_reports_pad_fraction(corpus):
    s = build_tensor(corpus, TensorSpec(max_steps=8)).summary()
    assert s["n_episodes"] == 2 and s["max_steps"] == 8
    assert s["real_steps"] == 8
    assert s["pad_fraction"] == pytest.approx(0.5)


def test_every_declared_channel_is_computable(corpus):
    """Registry exhaustiveness — a channel that cannot be built is a broken promise."""
    b = build_tensor(corpus, TensorSpec(channels=tuple(CHANNELS), max_steps=4))
    assert np.isfinite(b.X[b.mask.astype(bool)]).all()


# ═══════════════════════ TIERS ARE NOT TRUTH ═══════════════════════
def test_deriving_views_never_mutates_tier_1(corpus, tmp_path):
    before = [e.content_hash() for e in corpus]
    write_flat(corpus, tmp_path)
    save_tensor(build_tensor(corpus), tmp_path)
    assert [e.content_hash() for e in corpus] == before
