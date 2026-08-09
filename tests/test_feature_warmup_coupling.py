"""Warmup coupling floor (T-16) — the derived feature warmup must equal the measured one,
and the backtest's configured skip must never be shorter than it.

WHY THIS EXISTS
---------------
`FeaturePipeline.finalize()` drops every row with NaN in any CANONICAL_FEATURES column. That
count (78 on the active config) was a *measured comment*, while `backtest.warmup_candles` was an
unrelated literal (30). Bars 30..77 therefore ran through the CRT state machine with no feature
row behind them, and a trade opened in that window silently received a zero vector.

`required_warmup_rows()` now derives the count from the three config windows that produce it. A
derivation is only worth having if it is pinned to reality — the identity is an easy off-by-one
(first-valid *index* vs *count* of dropped rows), and it was in fact wrong on the first pass.
These tests bind the formula to the real pipeline and to the config that must respect it.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from config_layer.production_config import get_prod_section
from features.feature_pipeline import FeaturePipeline, required_warmup_rows


def _synthetic_ohlcv(n: int = 800, seed: int = 7) -> pd.DataFrame:
    """Deterministic random-walk OHLCV — enough rows to clear any plausible warmup.

    Synthetic (not a corpus file) so the floor runs in CI without the gitignored data/ tree and
    without touching the XAUUSD Phase-1 pin.
    """
    rng = np.random.default_rng(seed)
    close = 100.0 + np.cumsum(rng.normal(0.0, 0.5, n))
    high = close + np.abs(rng.normal(0.0, 0.3, n))
    low = close - np.abs(rng.normal(0.0, 0.3, n))
    open_ = np.concatenate([[close[0]], close[:-1]])
    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="15min"),
        "open": open_, "high": np.maximum(high, np.maximum(open_, close)),
        "low": np.minimum(low, np.minimum(open_, close)), "close": close,
        "volume": rng.integers(100, 1000, n).astype(float),
    })


def test_derived_warmup_matches_measured_drop() -> None:
    """The formula equals what finalize() actually drops. The load-bearing assertion."""
    raw = _synthetic_ohlcv()
    n_before = len(raw)
    enriched, _vectors = FeaturePipeline(raw).run()
    measured = n_before - len(enriched)
    assert measured == required_warmup_rows(), (
        f"required_warmup_rows()={required_warmup_rows()} but FeaturePipeline.finalize() dropped "
        f"{measured} rows. The derivation has drifted from the pipeline — fix the formula in "
        "features/feature_pipeline.py::required_warmup_rows, not this test."
    )


def test_derived_warmup_is_prefix_only() -> None:
    """The drop is a leading prefix, which is what makes count == first-valid-index legitimate.

    If finalize() ever dropped rows from the middle, `warmup_candles` could not close the gap and
    only the per-lookup fail-closed check would catch it.
    """
    raw = _synthetic_ohlcv()
    enriched, _ = FeaturePipeline(raw.copy()).run()
    first_kept = pd.to_datetime(enriched["timestamp"]).iloc[0]
    expected_first = pd.to_datetime(raw["timestamp"]).iloc[required_warmup_rows()]
    assert first_kept == expected_first, (
        f"first surviving row is {first_kept}, expected {expected_first} — finalize() is not "
        "dropping a clean prefix, so the warmup coupling is not sufficient on its own."
    )


def test_warmup_scales_with_its_config_windows() -> None:
    """The three windows that set the warmup actually move it (guards a hardcoded return)."""
    base = dict(get_prod_section("feature_pipeline"))
    baseline = required_warmup_rows(base)
    assert required_warmup_rows({**base, "zscore_window": base["zscore_window"] + 10}) == baseline + 10
    assert required_warmup_rows(
        {**base, "trend_strength_window": base["trend_strength_window"] + 5}
    ) == baseline + 5
    bumped_ma = list(base["ma_periods"]); bumped_ma[0] += 3
    assert required_warmup_rows({**base, "ma_periods": bumped_ma}) == baseline + 3


def test_active_config_warmup_covers_pipeline_warmup() -> None:
    """The config invariant BacktestRunner enforces at init — pinned here so a config edit
    that reopens the gap fails in CI rather than at the next backtest."""
    configured = int(get_prod_section("backtest")["warmup_candles"])
    derived = required_warmup_rows()
    assert configured >= derived, (
        f"backtest.warmup_candles={configured} < pipeline warmup {derived}. Candles "
        f"{configured}..{derived - 1} would run with no feature row behind them."
    )


def test_required_warmup_rows_is_strict_on_missing_keys() -> None:
    """No silent default (CLAUDE.md 6.5) — a partial section raises rather than guessing."""
    with pytest.raises((KeyError, ValueError)):
        required_warmup_rows({"zscore_window": 50})


# ── fail-closed scoping ───────────────────────────────────────────────────────────────────
# The fail-closed lookup must fire ONLY where a feature frame was actually expected. Two
# construction modes legitimately have no frame and must keep zero-filling; scoping the raise to
# `skip_features` alone would have broken the second one (the programmatic path F-057 names:
# tuner / embedders / tests construct BacktestRunner(cfg) with no csv_path at all).

def _runner(**kwargs):
    from config_layer.config_builder import ConfigBuilder
    from runtime.backtest_v2 import BacktestConfig, BacktestRunner
    from config_layer.production_config import get_active_version, load_prod_config_from_registry
    cfg = BacktestConfig.from_prod_config(
        instrument="BNBUSDT",
        crt_config=load_prod_config_from_registry(get_active_version(), "BNBUSDT"),
    )
    cfg.instrument = "BNBUSDT"
    return BacktestRunner(cfg, **kwargs)


def test_no_csv_path_is_a_legitimate_no_feature_mode() -> None:
    """BacktestRunner(cfg) with no csv_path streams caller-supplied candles and has no frame."""
    assert _runner()._features_expected is False


def test_skip_features_is_a_legitimate_no_feature_mode(tmp_path) -> None:
    """Tuner workers pass skip_features=True and never read feature columns."""
    csv = tmp_path / "BNBUSDT_M15.csv"
    csv.write_text("timestamp,open,high,low,close,volume\n", encoding="utf-8")
    assert _runner(csv_path=str(csv), skip_features=True)._features_expected is False


def _live_production_configs() -> list:
    """Every loadable production config — archived snapshots excluded.

    Archived configs are preserved history (CLAUDE.md 6.2 rule 4) and are not hot-swappable, so
    they are deliberately NOT held to a contract introduced after they were frozen.
    """
    from pathlib import Path
    return sorted(
        p for p in Path("configs/production").glob("*.json")
        if "archived" not in p.name
    )


@pytest.mark.parametrize("cfg_path", _live_production_configs(), ids=lambda p: p.stem)
def test_every_live_config_declares_the_coupled_keys(cfg_path) -> None:
    """Both T-16 keys must exist in EVERY live config, not just the active one.

    Learned the hard way: `warmup_candles` was raised only in the active config, so the very next
    run against a shadow config (v2_multi_dimfix_shadow_2026_07) died on the new assert. Both keys
    are read strictly at BacktestRunner construction, so a config missing either is unrunnable —
    which should fail here, at commit time, not mid-experiment.
    """
    import json
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    bt = cfg.get("backtest")
    if bt is None:
        pytest.skip(f"{cfg_path.name} declares no 'backtest' section")
    derived = required_warmup_rows()
    assert "warmup_candles" in bt and int(bt["warmup_candles"]) >= derived, (
        f"{cfg_path.name}: backtest.warmup_candles={bt.get('warmup_candles')!r} does not cover "
        f"the pipeline warmup ({derived}); BacktestRunner will refuse to start."
    )
    assert isinstance(bt.get("engine_gate_enabled"), bool), (
        f"{cfg_path.name}: backtest.engine_gate_enabled missing or non-boolean "
        f"({bt.get('engine_gate_enabled')!r}). It is read strictly (F-058) — a config without it "
        "raises at construction."
    )


def test_process_candle_count_matches_feature_row_count_at_exact_warmup_boundary(tmp_path) -> None:
    """Structural invariant at the T-16 equality boundary (`warmup_candles ==
    required_warmup_rows()`, the active config's own case, 78 == 78): every candle the replay
    loop hands to `CRTEngine.process_candle` must have a feature row behind it, and vice versa.

    A prior investigation suspected a fencepost here — the replay loop's warmup skip is
    `candle_idx < warmup_candles` with a 1-based `candle_idx`, which in isolation looks like it
    drops one row fewer than `FeaturePipeline.finalize()`'s 0-based prefix drop. Empirically that
    theory was WRONG: the "Initialise" block immediately after warmup (`:2151-2163`) `continue`s
    without calling `process_candle` on its own candle, consuming exactly the row the warmup
    check appears to under-skip. The two off-by-ones cancel — verified by intercepting
    `CRTEngine.process_candle` on a full run and confirming call-count and first-timestamp both
    match `feature_ts_to_idx` exactly. This test pins that healthy invariant so a future change to
    either the warmup skip OR the Initialise block's control flow (which could reintroduce a real
    mismatch) fails here instead of silently reaching a `TRADE_OPENED` with no feature row.
    """
    import unittest.mock as mock

    from config_layer.config_builder import ConfigBuilder
    from config_layer.crt_engine_v2 import CRTEngine
    from runtime.backtest_v2 import BacktestConfig, BacktestRunner, CandleLoader

    raw = _synthetic_ohlcv()
    csv_path = tmp_path / "BNBUSDT_M15.csv"
    raw.to_csv(csv_path, index=False)

    from config_layer.production_config import get_active_version, load_prod_config_from_registry
    cfg = BacktestConfig.from_prod_config(
        instrument="BNBUSDT",
        crt_config=load_prod_config_from_registry(get_active_version(), "BNBUSDT"),
    )
    cfg.instrument = "BNBUSDT"
    cfg.warmup_candles = required_warmup_rows()  # exact-equality boundary, not slack

    runner = BacktestRunner(cfg, csv_path=str(csv_path))
    loader = CandleLoader(str(csv_path), cfg.instrument)

    calls: list = []

    def _spy(self, candle, htf_candle_id):
        calls.append(candle.timestamp)
        return {"action": "NONE"}

    with mock.patch.object(CRTEngine, "process_candle", _spy):
        runner.run(loader.stream(), loader.count(), str(tmp_path))

    assert calls, "CRTEngine.process_candle was never invoked — warmup never completed."
    assert len(calls) == len(runner.feature_ts_to_idx), (
        f"process_candle was called {len(calls)} times but {len(runner.feature_ts_to_idx)} "
        "feature rows exist — the replay loop and FeaturePipeline have drifted out of sync."
    )
    first_call_key = pd.Timestamp(calls[0]).strftime("%Y-%m-%d %H:%M:%S")
    assert first_call_key == min(runner.feature_ts_to_idx), (
        f"first candle handed to the CRT engine ({first_call_key}) is not the first feature row "
        f"({min(runner.feature_ts_to_idx)}) — a warmup/initialise boundary mismatch."
    )


def test_features_expected_only_when_a_frame_was_built() -> None:
    """The predicate must match __init__'s own guard exactly, or the two disagree about
    which runs are contract-checked."""
    from runtime.backtest_v2 import BacktestRunner
    import inspect
    src = inspect.getsource(BacktestRunner.__init__)
    assert "if self.csv_path and not skip_features:" in src, (
        "__init__'s pipeline-build guard changed; _features_expected must be updated to match it."
    )
