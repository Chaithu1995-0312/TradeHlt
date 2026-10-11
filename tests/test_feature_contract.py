"""Feature-definition contract: canonical body_ratio formula, implementation parity, and identity behaviour."""
import ast
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from features import feature_contract as fc

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------- reference formula
def test_reference_values_and_zero_range():
    assert fc.ref_body_ratio(100, 104, 98, 102) == pytest.approx(2 / 6)
    assert fc.ref_wick_size(100, 104, 98, 102) == 6.0           # full range, not the shadow
    assert fc.ref_body_size(100, 104, 98, 102) == 2.0
    assert fc.ref_body_ratio(5, 5, 5, 5) == 0.0                 # zero range -> 0.0, never NaN or a division error
    assert fc.ref_body_ratio(5, 6, 5, 6) == 1.0                 # marubozu


def test_reference_ratio_is_bounded_for_valid_candles():
    rng = np.random.default_rng(0)
    lo = rng.uniform(100, 110, 2000); hi = lo + rng.uniform(0, 5, 2000)
    o = lo + (hi - lo) * rng.uniform(0, 1, 2000); c = lo + (hi - lo) * rng.uniform(0, 1, 2000)
    r = fc.ref_body_ratio(o, hi, lo, c)
    assert np.all((r >= 0) & (r <= 1 + 1e-12))


def test_spec_states_zero_range_behavior():
    s = fc.FORMAL_SPECS["body_ratio"]
    assert s["formula"] == "body_size / wick_size" and "0.0" in s["zero_range_behavior"]
    assert fc.FORMAL_SPECS["wick_size"]["formula"] == "high - low"


# ---------------------------------------------------------------- parity: implementations that comply
def _synthetic_ohlc(n=700, seed=1):
    rng = np.random.default_rng(seed)
    close = 2000 + np.cumsum(rng.normal(0, 1.0, n))
    open_ = close + rng.normal(0, 0.4, n)
    high = np.maximum(open_, close) + rng.uniform(0, 1, n)
    low = np.minimum(open_, close) - rng.uniform(0, 1, n)
    flat = np.arange(n) % 37 == 5                               # zero-range bars, including after warm-up
    open_[flat] = close[flat] = high[flat] = low[flat] = close[flat]
    return pd.DataFrame({"timestamp": pd.date_range("2025-01-01", periods=n, freq="15min"),
                         "open": open_, "high": high, "low": low, "close": close, "volume": rng.integers(100, 200, n).astype(float)})


def test_pipeline_matches_contract_including_zero_range():
    from features.feature_pipeline import FeaturePipeline
    raw = _synthetic_ohlc()
    df, _ = FeaturePipeline(raw.copy()).run()
    ts = pd.to_datetime(df["timestamp"])
    r = raw.set_index("timestamp").reindex(ts)
    o, h, l, c = (r[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    zero = (h - l) == 0
    assert zero.any(), "synthetic data must contain zero-range bars after warm-up"
    np.testing.assert_allclose(df["body_size"].to_numpy(float), fc.ref_body_size(o, h, l, c), rtol=1e-6, atol=1e-9)
    np.testing.assert_allclose(df["wick_size"].to_numpy(float), fc.ref_wick_size(o, h, l, c), rtol=1e-6, atol=1e-9)
    np.testing.assert_allclose(df["body_ratio"].to_numpy(float), fc.ref_body_ratio(o, h, l, c), rtol=1e-6, atol=1e-7)
    assert np.all(df["body_ratio"].to_numpy(float)[zero] == 0.0)


def test_crt_candle_matches_contract():
    import inspect
    from config_layer.crt_engine_v2 import Candle
    sig = inspect.signature(Candle).parameters
    rng = np.random.default_rng(2)
    for _ in range(300):
        lo = rng.uniform(100, 110); hi = lo + rng.choice([0.0, rng.uniform(0, 5)])
        o = rng.uniform(lo, hi) if hi > lo else lo; c = rng.uniform(lo, hi) if hi > lo else lo
        kw = dict(timestamp=pd.Timestamp("2025-01-01"), open=o, high=hi, low=lo, close=c, volume=1.0)
        cd = Candle(**{k: v for k, v in kw.items() if k in sig})
        assert cd.body_size == pytest.approx(fc.ref_body_size(o, hi, lo, c))
        assert cd.wick_size == pytest.approx(fc.ref_wick_size(o, hi, lo, c))
        assert cd.body_ratio == pytest.approx(fc.ref_body_ratio(o, hi, lo, c))


def test_manual_backtest_anatomy_matches_contract():
    src = (ROOT / "scripts/backtest/manual_backtest.py").read_text()
    ns: dict = {}
    for node in ast.parse(src).body:
        if isinstance(node, ast.FunctionDef) and node.name in ("body_ratio", "wick_size"):
            exec(ast.get_source_segment(src, node), ns)
    for o, h, l, c in [(100, 104, 98, 102), (5, 5, 5, 5), (5, 6, 5, 6), (3, 4, 2, 3)]:
        assert ns["body_ratio"](o, h, l, c) == pytest.approx(fc.ref_body_ratio(o, h, l, c))
        assert ns["wick_size"](o, h, l, c) == pytest.approx(fc.ref_wick_size(o, h, l, c))


# ---------------------------------------------------------------- parity: known non-compliant branches (strict xfail)
# These pin the mismatch recorded in the consumer registry (B1, D1).  When a branch is fixed the test XPASSes,
# strict mode fails the run, and the registry status must be updated deliberately.
HOOK_REASON = "B1: live hook computes wick_size as (high-low)-body and body_ratio as body/wick; contract is body/(high-low)"


@pytest.mark.xfail(strict=True, reason=HOOK_REASON)
def test_live_hook_body_ratio_matches_contract():
    from runtime.live_engine_hook import _build_ohlcv_and_auxiliary
    _, aux = _build_ohlcv_and_auxiliary(dict(open=100.0, high=104.0, low=98.0, close=102.0, volume=1.0))
    assert aux["body_ratio"] == pytest.approx(fc.ref_body_ratio(100, 104, 98, 102))


@pytest.mark.xfail(strict=True, reason=HOOK_REASON)
def test_live_hook_wick_size_matches_contract():
    from runtime.live_engine_hook import _build_ohlcv_and_auxiliary
    _, aux = _build_ohlcv_and_auxiliary(dict(open=100.0, high=104.0, low=98.0, close=102.0, volume=1.0))
    assert aux["wick_size"] == pytest.approx(fc.ref_wick_size(100, 104, 98, 102))


@pytest.mark.xfail(strict=True, reason="D1: bitnet_feature_builder uses the hook's non-contract anatomy (no callers)")
def test_bitnet_builder_body_ratio_matches_contract():
    from features.bitnet_feature_builder import build_bitnet_features
    f = build_bitnet_features({}, dict(open=100.0, high=104.0, low=98.0, close=102.0, volume=1.0), {})
    assert f["body_ratio"] == pytest.approx(fc.ref_body_ratio(100, 104, 98, 102))


# ---------------------------------------------------------------- identity behaviour
def _rehash_with_pipeline(monkeypatch, tmp_path, transform):
    src = (ROOT / "src/features/feature_pipeline.py").read_text()
    p = tmp_path / "feature_pipeline.py"
    p.write_text(transform(src))
    monkeypatch.setattr(fc, "_PIPELINE_PATH", p)
    for f in (fc._pipeline_digests, fc.build_contract, fc.contract_hash):
        f.cache_clear()
    try:
        return fc.contract_hash()
    finally:
        monkeypatch.undo()
        for f in (fc._pipeline_digests, fc.build_contract, fc.contract_hash):
            f.cache_clear()


def test_hash_is_stable_and_ignores_comments_and_formatting(monkeypatch, tmp_path):
    base = fc.contract_hash()
    assert fc.contract_hash() == base
    same = _rehash_with_pipeline(monkeypatch, tmp_path, lambda s: "# extra comment\n" + s.replace("    def ", "\n    def ") + "\n\n# trailing comment\n")
    assert same == base


def test_hash_changes_when_a_constant_or_formula_changes(monkeypatch, tmp_path):
    base = fc.contract_hash()
    const = _rehash_with_pipeline(monkeypatch, tmp_path, lambda s: s.replace("VOL_REGIME_WINDOW = 200", "VOL_REGIME_WINDOW = 201", 1))
    assert const != base
    formula = _rehash_with_pipeline(monkeypatch, tmp_path,
                                    lambda s: s.replace('df["body_size"] / df["wick_size"]', '(df["body_size"] + 1e-9) / df["wick_size"]', 1))
    assert formula != base


def test_hash_changes_when_a_formal_spec_changes(monkeypatch):
    base = fc.contract_hash()
    specs = json.loads(json.dumps(fc.FORMAL_SPECS))
    specs["body_ratio"]["zero_range_behavior"] = "1.0 when wick_size <= 0"
    monkeypatch.setattr(fc, "FORMAL_SPECS", specs)
    for f in (fc.build_contract, fc.contract_hash):
        f.cache_clear()
    try:
        assert fc.contract_hash() != base
    finally:
        monkeypatch.undo()
        for f in (fc.build_contract, fc.contract_hash):
            f.cache_clear()
    assert fc.contract_hash() == base


def test_contract_covers_all_35_features_in_order():
    from features.feature_schema import CANONICAL_FEATURES
    c = fc.build_contract()
    assert [f["name"] for f in c["features"]] == list(CANONICAL_FEATURES)
    assert {f["name"] for f in c["features"] if f["definition_status"] == "formal"} == {"body_size", "wick_size", "body_ratio"}
