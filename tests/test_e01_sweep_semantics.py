"""feature_pipeline.sweep_semantics = "e01_lifecycle" (FM-090..093): batch pipeline, causal_structure
twin and live FeatureStore produce the same lifecycle sweep slots; the legacy default is untouched
(proved by tests/test_feature_layer_freeze.py's XAUUSD vector regression)."""

from __future__ import annotations

import numpy as np
import pytest

from features.causal_structure import causal_structure_series
from features.feature_pipeline import (
    SWEEP_E01_LIFECYCLE, SWEEP_LEGACY, FeaturePipeline, _resolve_feature_pipeline_cfg,
)
from features.feature_schema import CANONICAL_FEATURES
from tests.test_fc1a_swing_causal import _synthetic

SLOTS = ("liquidity_sweep", "sweep_detected", "double_sweep")


def _cfg(mode: str) -> dict:
    return dict(_resolve_feature_pipeline_cfg(None), sweep_semantics=mode)


def _structure_stage(raw, mode):
    p = FeaturePipeline(raw.copy(), cfg=_cfg(mode))
    p.compute_price_features()
    p.compute_indicators()
    p.compute_canonical_price_features()
    p.compute_canonical_volatility_features()
    p.compute_structure_liquidity()
    p.compute_canonical_ema_features()
    p.compute_canonical_structure_features()
    p.compute_canonical_temporal_features()
    return p.df


def test_unknown_sweep_semantics_is_refused():
    with pytest.raises(ValueError):
        _resolve_feature_pipeline_cfg(dict(_resolve_feature_pipeline_cfg(None), sweep_semantics="both"))


def test_batch_pipeline_matches_the_causal_twin_in_e01_mode():
    raw = _synthetic(400)
    df = _structure_stage(raw, SWEEP_E01_LIFECYCLE)
    series = causal_structure_series(df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy(),
                                     df["atr"].to_numpy(), sweep_semantics=SWEEP_E01_LIFECYCLE)
    for col in SLOTS:
        np.testing.assert_array_equal(series[col].astype(np.int8), df[col].to_numpy().astype(np.int8), err_msg=col)
    legacy = _structure_stage(raw, SWEEP_LEGACY)
    assert (legacy["liquidity_sweep"] != df["liquidity_sweep"]).any(), "modes must differ on this corpus"


def test_e01_sweeps_are_consumed_and_double_sweep_reads_per_side_events():
    df = _structure_stage(_synthetic(400), SWEEP_E01_LIFECYCLE)
    up, down = df["_e01_sweep_upper"].to_numpy(), df["_e01_sweep_lower"].to_numpy()
    assert up.sum() > 0 and down.sum() > 0
    np.testing.assert_array_equal(df["sweep_detected"].to_numpy(), ((up == 1) | (down == 1)).astype(np.int8))
    w = int(_cfg(SWEEP_E01_LIFECYCLE)["double_sweep_window"])
    want = [int(up[max(0, i - w + 1): i + 1].any() and down[max(0, i - w + 1): i + 1].any()) for i in range(len(up))]
    np.testing.assert_array_equal(df["double_sweep"].to_numpy(), np.array(want, dtype=np.int8))
    # candles_since_sweep (FM-093): 0 on an event bar, +1 per bar after, 0 before the first event
    css, last = df["candles_since_sweep"].to_numpy(), None
    for i in range(len(up)):
        if up[i] or down[i]:
            last = i
        assert css[i] == (0 if last is None else i - last), i


def test_live_store_carries_the_lifecycle_and_matches_batch(monkeypatch):
    import features.feature_pipeline as fp
    from core.feature_store import FeatureStore

    monkeypatch.setattr(fp, "resolve_sweep_semantics", lambda cfg=None: SWEEP_E01_LIFECYCLE)
    raw = _synthetic(300)
    store = FeatureStore(max_history=30)          # far shorter than the history: state must be carried
    got = {k: [] for k in SLOTS + ("candles_since_sweep",)}
    for i, row in raw.iterrows():
        ohlcv = {k: float(row[k]) for k in ("open", "high", "low", "close", "volume")}
        aux = {k: 0.0 for k in CANONICAL_FEATURES if k not in ohlcv}
        aux.update(atr=0.01, session=1, volume_ratio=1.0)
        frame = store.process(i, row["timestamp"], ohlcv, aux)
        for k in got:
            got[k].append(int(frame.features[k]))
    batch = causal_structure_series(raw["high"].to_numpy(), raw["low"].to_numpy(), raw["close"].to_numpy(),
                                    np.full(len(raw), 0.01), sweep_semantics=SWEEP_E01_LIFECYCLE)
    for col in SLOTS:
        np.testing.assert_array_equal(np.array(got[col]), batch[col].astype(int), err_msg=col)
    assert sum(abs(v) for v in got["liquidity_sweep"]) > 0


# ── FM-094 / FM-095: retest_flag / retest_depth fed by the E01 sweep (CH-e01-lifecycle-retest-identity) ──
# retest_flag (FM-061) reads liquidity_sweep, and retest_depth (FM-021) is gated on retest_flag, so the
# sweep switch moves both. The live rail takes retest_depth from LiveRailFeeder (full-history pipeline,
# last row); FeatureStore never recomputes it. These tests pin the declared formula to the code and prove
# live == batch at every prefix, in both modes.

def _retest_rule(df, lookback, band_mult):
    recent = (df["liquidity_sweep"] != 0).rolling(window=lookback, min_periods=1).max().astype(bool)
    near = (df["close"] - df["ema_fast"]).abs() <= band_mult * df["atr"] * df["close"]
    return (recent & near).astype(np.int8).to_numpy()


@pytest.mark.parametrize("mode", [SWEEP_E01_LIFECYCLE, SWEEP_LEGACY])
def test_retest_flag_follows_the_selected_sweep_identity(mode):
    cfg = _cfg(mode)
    df = _structure_stage(_synthetic(400), mode)
    want = _retest_rule(df, int(cfg["retest_lookback"]), float(cfg["retest_atr_band_mult"]))
    np.testing.assert_array_equal(df["retest_flag"].to_numpy().astype(np.int8), want)
    assert want.sum() > 0


def test_retest_identity_differs_between_modes():
    raw = _synthetic(400)
    e01, legacy = _structure_stage(raw, SWEEP_E01_LIFECYCLE), _structure_stage(raw, SWEEP_LEGACY)
    assert (e01["retest_flag"] != legacy["retest_flag"]).any()
    assert (e01["retest_depth"] != legacy["retest_depth"]).any()


@pytest.mark.parametrize("mode", [SWEEP_E01_LIFECYCLE, SWEEP_LEGACY])
def test_live_feeder_matches_batch_at_every_prefix(monkeypatch, mode):
    import config_layer.production_config as pc
    from features.feature_pipeline import required_warmup_rows
    from runtime.live_rail_feeder import LiveRailFeeder
    from tests.test_live_rail_feeder import _PORTFOLIO, _bar

    real = pc.get_prod_section
    monkeypatch.setattr(pc, "get_prod_section",
                        lambda section, version=None: (dict(real(section, version), sweep_semantics=mode)
                                                       if section == "feature_pipeline" else real(section, version)))
    n = required_warmup_rows() + 90
    bars = [_bar(i) for i in range(n)]
    feeder = LiveRailFeeder(symbol="XAUUSD", timeframe="M15")
    live = []
    for b in bars:
        feeder.push(b)
        if feeder.ready():
            td = feeder.as_trade_data(b, _PORTFOLIO)
            live.append((td["timestamp"], {k: float(td[k]) for k in SLOTS + ("candles_since_sweep", "retest_depth")}))
    batch, _ = FeaturePipeline(feeder._bars_to_frame(), cfg=_cfg(mode)).run()
    by_ts = {str(ts): row for ts, row in zip(batch["timestamp"].astype(str), batch.to_dict("records"))}
    assert len(live) == 90
    for ts, got in live:
        row = by_ts[str(ts)]
        for k, v in got.items():
            assert v == pytest.approx(float(row[k]), abs=0.0), (mode, ts, k)
    assert any(g["retest_depth"] != 0.0 for _, g in live)
