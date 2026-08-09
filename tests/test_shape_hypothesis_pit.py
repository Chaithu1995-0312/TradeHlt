"""Blocking PIT / contamination audit for the Program-11 Market-Shape hypothesis (B1).

Two guarantees the clean-substrate re-test depends on:
  * F-022 tripwire — detect() must RAISE if any stream outcome field is injected, so a contaminated
    caller can never leak realized outcomes into a "pure" detector.
  * PIT (no-lookahead) — the shape assigned to bar p must be PREFIX-INVARIANT: identical whether
    computed from candles[:p+1] or from a longer run. This is the real proof that the projected
    shape features are causal (post-F-051), stronger than any static contaminated-dim list.
"""
from __future__ import annotations

from collections import namedtuple

import numpy as np
import pandas as pd
import pytest

from features.feature_pipeline import FeaturePipeline
from features.market_shape import MarketShapeClassifier
from research.hypotheses.market_shape_hypothesis import MarketShapeHypothesis

_Bar = namedtuple("_Bar", "index timestamp open high low close volume")


class _StubSource:
    def __init__(self, sig): self._sig = sig
    def signals(self, instrument): return self._sig


def _window(n=20, base_idx=100):
    rng = np.random.default_rng(0)
    bars = []
    px = 2000.0
    for i in range(n):
        px += rng.normal(0, 1.0)
        bars.append(_Bar(base_idx + i, pd.Timestamp("2025-01-01") + pd.Timedelta(minutes=15 * i),
                         px, px + 1.5, px - 1.5, px + rng.normal(0, 0.5), 100.0))
    return bars


# ── F-022 tripwire ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("bad_key", ["outcome", "rr_achieved", "mfe", "mae", "rr"])
def test_detect_raises_on_injected_stream_field(bad_key):
    hyp = MarketShapeHypothesis(source=_StubSource({119: "long"}))
    win = _window()
    with pytest.raises(ValueError):
        hyp.detect(win, {bad_key: 1.23}, {"instrument": "XAUUSD"})
    with pytest.raises(ValueError):
        hyp.detect(win, {}, {"instrument": "XAUUSD", bad_key: 1.23})


def test_detect_emits_signal_on_clean_inputs():
    win = _window(base_idx=100)
    hyp = MarketShapeHypothesis(source=_StubSource({win[-1].index: "short"}))
    out = hyp.detect(win, {}, {"instrument": "XAUUSD"})
    assert len(out) == 1
    assert out[0].direction == "short" and out[0].entry_index == win[-1].index


def test_detect_silent_when_no_shape_signal():
    win = _window(base_idx=100)
    hyp = MarketShapeHypothesis(source=_StubSource({}))     # no signal at this index
    assert hyp.detect(win, {}, {"instrument": "XAUUSD"}) == []


# ── PIT: prefix-invariance of the shape identity ──────────────────────────────

def _shape_names_from_prefix(raw: pd.DataFrame, upto: int) -> dict[int, str]:
    """Run the pipeline on raw[:upto] and return {raw_pos: shape.label} via the _pos join."""
    work = raw.iloc[:upto].reset_index(drop=True).copy()
    work["_pos"] = range(len(work))
    df, vectors = FeaturePipeline(work).run()
    pos = df["_pos"].to_numpy()
    clf = MarketShapeClassifier()
    return {int(pos[i]): clf.classify_vector(vectors[i]).label for i in range(len(pos))}


def test_shape_identity_is_prefix_invariant():
    """The shape at bar p must not change when future bars are added — no lookahead."""
    raw = pd.read_csv("data/mt5/XAUUSD_M15.csv")
    short = _shape_names_from_prefix(raw, 1500)      # bars 0..1499
    long_ = _shape_names_from_prefix(raw, 2200)      # bars 0..2199
    checked = 0
    for p in (900, 1100, 1300, 1499):
        assert p in short and p in long_, p
        assert short[p] == long_[p], f"shape at bar {p} changed with future data: {short[p]} != {long_[p]}"
        checked += 1
    assert checked == 4
