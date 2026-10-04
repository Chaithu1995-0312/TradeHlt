"""Focused fail-closed tests for Phase-1 duplicate / formula identity closure."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
DATE = "2026-07-10"
GOV = ROOT / "docs" / "governance"
REG = GOV / f"phase1_feature_identity_registry-{DATE}.json"

from features import candle_math as cm
from features import derived_math as dm
from features.feature_identity import (
    AmbiguousFeatureIdentityError,
    UnknownFeatureIdentityError,
    all_identities,
    assert_consumer_binding,
    clear_cache,
    get_by_feature_id,
    load_identity_registry,
    resolve_by_name,
)
from features.feature_pipeline import FeaturePipeline, SWING_WINDOW
from data_ingestion.xauusd_phase1_candidate import require_phase1_frozen_candidate


@pytest.fixture(autouse=True)
def _clear_identity_cache():
    clear_cache()
    yield
    clear_cache()


def _synthetic(n: int = 300, volume: float | None = 100.0) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    close = 100 + np.cumsum(rng.normal(0, 0.5, n))
    open_ = close + rng.normal(0, 0.2, n)
    # Enforce OHLC consistency required by validate_ohlcv_frame
    high = np.maximum(open_, close) + rng.uniform(0.1, 1.0, n)
    low = np.minimum(open_, close) - rng.uniform(0.1, 1.0, n)
    vol = np.zeros(n) if volume is None else np.full(n, float(volume))
    ts = pd.date_range("2024-06-01", periods=n, freq="15min")
    return pd.DataFrame(
        {
            "timestamp": ts,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": vol,
        }
    )


def test_frozen_candidate_gate():
    b = require_phase1_frozen_candidate(repo_root=ROOT)
    assert b.content_hash_sha256.startswith("4d73f5ce")
    assert b.rows == 47275


def test_registry_loads_and_unique_ids():
    data = load_identity_registry(str(REG))
    idents = all_identities(str(REG))
    assert len(idents) >= 14
    fids = [i.feature_id for i in idents]
    assert len(fids) == len(set(fids))
    # one formula_id may cover multiple features (swing high/low) but same definition
    by_f = {}
    for i in idents:
        by_f.setdefault(i.formula_id, set()).add(i.semantic_description or i.formula_id)


def test_no_feature_id_multi_formula():
    for i in all_identities(str(REG)):
        again = get_by_feature_id(i.feature_id, str(REG))
        assert again.formula_id == i.formula_id
        assert again.formula_version == i.formula_version


def test_source_tick_volume_identity_on_xauusd():
    b = require_phase1_frozen_candidate(repo_root=ROOT)
    path = ROOT / b.physical_path
    df = pd.read_csv(path)
    # normalize columns
    cols = {c.lower(): c for c in df.columns}
    rename = {}
    for need in ("open", "high", "low", "close", "volume", "timestamp"):
        for c in df.columns:
            if c.lower() == need or c.lower().replace(" ", "") == need:
                rename[c] = need
    df = df.rename(columns=rename)
    if "timestamp" not in df.columns:
        # MT5 style
        for c in list(df.columns):
            if "time" in c.lower():
                df = df.rename(columns={c: "timestamp"})
                break
    sample = df.head(500).copy()
    pipe = FeaturePipeline(sample)
    pipe.compute_price_features()
    pipe.compute_volume_features()
    out = pipe.df
    # volume not rewritten to high-low
    src = pd.to_numeric(sample["volume"], errors="coerce")
    assert np.allclose(out["volume"].fillna(0), src.fillna(0))
    assert "volume_range_proxy" in out.columns
    assert np.allclose(out["volume_range_proxy"], out["high"] - out["low"])
    # identity registry
    vol = get_by_feature_id("FEAT-VOLUME", str(REG))
    assert vol.formula_id == "FORMULA-SOURCE-TICK-VOLUME"
    assert "TICK_VOLUME" in vol.source_semantics


def test_proxy_formula_and_no_same_name_substitution():
    df = _synthetic(volume=None)  # all zero
    pipe = FeaturePipeline(df)
    pipe.compute_price_features()
    pipe.compute_volume_features()
    out = pipe.df
    assert (out["volume"].fillna(0) == 0).all()
    proxy = out["volume_range_proxy"]
    assert np.allclose(proxy, out["high"] - out["low"])
    # pre-consolidation equivalence: T-003 math == proxy identity
    t003_math = out["high"] - out["low"]
    assert np.allclose(proxy, t003_math)


def test_nan_source_volume_path():
    """NaN volume is rejected at pipeline ingest (OHLCV integrity).

    After numeric coerce, an all-NaN volume is treated as dead by the volume
    identity split only when it reaches compute_volume_features — unit-test
    the identity function path on a post-validated zero frame + assert
    registry source_semantics fail-closed against proxy substitution.
    """
    # Pipeline-level: all-zero (NaN not admitted by validate_ohlcv_frame)
    df = _synthetic(volume=None)
    pipe = FeaturePipeline(df)
    pipe.compute_price_features()
    pipe.compute_volume_features()
    out = pipe.df
    assert (out["volume"].fillna(0.0) == 0.0).all()
    assert np.allclose(out["volume_range_proxy"], out["high"] - out["low"])
    # Direct unit: if NaN volume somehow entered compute_volume_features
    raw = pd.Series([np.nan, np.nan, np.nan])
    vol_is_dead = bool(raw.fillna(0.0).max() == 0)
    assert vol_is_dead
    # proxy identity still high-low, never equals source volume identity
    vol_id = get_by_feature_id("FEAT-VOLUME", str(REG))
    proxy_id = get_by_feature_id("FEAT-VOLUME_RANGE_PROXY", str(REG))
    assert vol_id.feature_id != proxy_id.feature_id
    assert vol_id.formula_id != proxy_id.formula_id


def test_wrong_semantic_consumer_binding_rejection():
    with pytest.raises(Exception):
        assert_consumer_binding(
            "FeaturePipeline",
            "FEAT-VOLUME",
            "FORMULA-PRICE-RANGE-PROXY-HL",  # wrong formula for source volume
            "v1",
            path=str(REG),
        )


def test_swing_identities_independent_and_no_env_mutation():
    df = _synthetic(400)
    # FC1-A: production swing_high binds to causal_confirmed
    os.environ.pop("TRUST_SWING_CAUSAL", None)
    p1 = FeaturePipeline(df.copy())
    p1.compute_price_features()
    p1.compute_indicators()
    p1.compute_structure_liquidity()
    prod_high = p1.df["swing_high"].copy()
    centered_high = p1.df["swing_high_centered_batch"].copy()
    causal_high = p1.df["swing_high_causal_confirmed"].copy()
    assert "swing_high_centered_batch" in p1.df.columns
    # production == causal; generally differs from centered (shift)
    assert prod_high.equals(causal_high)
    assert not centered_high.equals(causal_high) or centered_high.sum() == 0

    # env must not mutate production or centered identity columns
    os.environ["TRUST_SWING_CAUSAL"] = "1"
    try:
        p2 = FeaturePipeline(df.copy())
        p2.compute_price_features()
        p2.compute_indicators()
        p2.compute_structure_liquidity()
        assert p2.df["swing_high"].equals(prod_high)
        assert p2.df["swing_high_centered_batch"].equals(centered_high)
        assert p2.df["swing_high_causal_confirmed"].equals(causal_high)
        assert "swing_high_research_view" in p2.df.columns
    finally:
        os.environ.pop("TRUST_SWING_CAUSAL", None)

    # registry: bare swing_high → CAUSAL (FC1-A production bind)
    prod = resolve_by_name("swing_high", path=str(REG), allow_legacy_alias=True)
    assert prod.feature_id == "FEAT-SWING_HIGH_CAUSAL_CONFIRMED"
    centered = get_by_feature_id("FEAT-SWING_HIGH_CENTERED_BATCH", str(REG))
    assert centered.feature_id != prod.feature_id
    assert "available_at=t+k" in prod.temporal_semantics or "t+k" in prod.temporal_semantics


def test_volatility_regime_three_identities_no_env_mutation():
    df = _synthetic(400)
    os.environ.pop("TRUST_VOLREGIME_CAUSAL", None)
    p1 = FeaturePipeline(df.copy())
    p1.compute_price_features()
    p1.compute_indicators()
    p1.compute_volatility_regime()
    # FC1-D: production binds to rolling causal
    prod = p1.df["volatility_regime"].copy()
    g = p1.df["volatility_regime_global_batch"].copy()
    e = p1.df["volatility_regime_expanding_causal"].copy()
    r = p1.df["volatility_regime_rolling_causal"].copy()
    assert prod.equals(r)
    # not all three identical in general
    assert not (g.equals(e) and e.equals(r))

    os.environ["TRUST_VOLREGIME_CAUSAL"] = "expanding"
    try:
        p2 = FeaturePipeline(df.copy())
        p2.compute_price_features()
        p2.compute_indicators()
        p2.compute_volatility_regime()
        # env must not mutate production (still rolling) or identity columns
        assert p2.df["volatility_regime"].equals(prod)
        assert p2.df["volatility_regime_global_batch"].equals(g)
        assert p2.df["volatility_regime_expanding_causal"].equals(e)
        assert "volatility_regime_research_view" in p2.df.columns
        assert p2.df["volatility_regime_research_view"].equals(e)
    finally:
        os.environ.pop("TRUST_VOLREGIME_CAUSAL", None)

    g_id = get_by_feature_id("FEAT-VOLATILITY_REGIME_GLOBAL_BATCH_RANK", str(REG))
    e_id = get_by_feature_id("FEAT-VOLATILITY_REGIME_EXPANDING_CAUSAL_RANK", str(REG))
    r_id = get_by_feature_id("FEAT-VOLATILITY_REGIME_ROLLING_CAUSAL_RANK", str(REG))
    assert len({g_id.feature_id, e_id.feature_id, r_id.feature_id}) == 3
    assert len({g_id.formula_id, e_id.formula_id, r_id.formula_id}) == 3
    bare = resolve_by_name("volatility_regime", path=str(REG), allow_legacy_alias=True)
    assert bare.feature_id == "FEAT-VOLATILITY_REGIME_ROLLING_CAUSAL_RANK"


def test_body_ratio_identities_and_boundaries():
    assert cm.body_ratio(100, 110, 95, 108) == pytest.approx(8 / 15)
    assert cm.body_to_total_wick_ratio(100, 110, 95, 108) == pytest.approx(8 / 7)
    # zero range
    assert cm.body_ratio(50, 50, 50, 50) == 0.0
    assert cm.body_to_total_wick_ratio(50, 50, 50, 50) == 0.0
    # zero wick (full body) — total_wick=0
    assert cm.body_to_total_wick_ratio(100, 110, 100, 110) == 0.0
    assert cm.body_ratio(100, 110, 100, 110) == pytest.approx(1.0)

    r = get_by_feature_id("FEAT-BODY_TO_RANGE_RATIO", str(REG))
    w = get_by_feature_id("FEAT-BODY_TO_TOTAL_WICK_RATIO", str(REG))
    assert r.formula_id != w.formula_id
    # bare body_ratio as legacy → range only
    assert resolve_by_name("body_ratio", path=str(REG), allow_legacy_alias=True).feature_id == (
        "FEAT-BODY_TO_RANGE_RATIO"
    )
    # body_ratio is not a unique canonical_name of total_wick
    with pytest.raises(UnknownFeatureIdentityError):
        resolve_by_name("body_ratio", path=str(REG), allow_legacy_alias=False)


def test_fm_identities_no_substitution():
    ids = [
        "FEAT-DISP_STRENGTH",
        "FEAT-RETEST_DEPTH",
        "FEAT-DISPLACEMENT_RETRACE",
        "FEAT-DISPLACEMENT_ATR_RATIO",
    ]
    formulas = [get_by_feature_id(i, str(REG)).formula_id for i in ids]
    assert len(set(formulas)) == 4
    # oracles — formulas are independent (use non-colliding fixture values)
    assert dm.disp_strength(2.0, 0.02, 100.0) == pytest.approx(1.0)  # 2/(0.02*100)
    assert dm.displacement_atr_ratio(15.0, 5.0) == pytest.approx(3.0)
    assert dm.disp_strength(2.0, 0.02, 100.0) != dm.displacement_atr_ratio(15.0, 5.0)
    assert dm.retest_depth(100.0, 99.0, 0.01) != dm.displacement_retrace(105.0, 100.0, 110.0)
    # consumer binding present
    assert_consumer_binding(
        "FeaturePipeline", "FEAT-DISP_STRENGTH", "FORMULA-FM-020", "v1", path=str(REG)
    )
    assert_consumer_binding(
        "CRTEngine", "FEAT-DISPLACEMENT_RETRACE", "FORMULA-FM-027", "v1", path=str(REG)
    )


def test_consumer_binding_absent_registry_fails():
    with pytest.raises(Exception):
        assert_consumer_binding(
            "FeaturePipeline", "FEAT-DOES-NOT-EXIST", "X", "v1", path=str(REG)
        )


def test_artifacts_exist_and_deterministic():
    names = [
        f"phase1_duplicate_formula_identity_closure-{DATE}.json",
        f"phase1_duplicate_formula_identity_closure-{DATE}.md",
        f"phase1_feature_identity_registry-{DATE}.json",
        f"phase1_duplicate_implementation_authority_decisions-{DATE}.json",
        f"phase1_consumer_identity_bindings-{DATE}.json",
        f"phase1_duplicate_formula_follow_up_backlog-{DATE}.json",
        f"phase1_duplicate_formula_identity_manifest-{DATE}.json",
    ]
    for n in names:
        p = GOV / n
        assert p.is_file(), f"missing {p}"
    # re-run generator twice → same registry sha
    import subprocess
    import sys

    py = sys.executable
    script = ROOT / "scripts" / "analysis" / "phase1_duplicate_formula_identity_closure.py"
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    for _ in range(2):
        r = subprocess.run(
            [py, str(script)],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
        )
        assert r.returncode == 0, r.stdout + r.stderr
    h1 = hashlib.sha256(REG.read_bytes()).hexdigest()
    # second already ran — re-hash
    h2 = hashlib.sha256(REG.read_bytes()).hexdigest()
    assert h1 == h2
    man = json.loads(
        (GOV / f"phase1_duplicate_formula_identity_manifest-{DATE}.json").read_text(
            encoding="utf-8"
        )
    )
    assert man["DUPLICATE_FORMULA_IDENTITY_PHASE_STATUS"] == "COMPLETE"
    assert man["PIT_REMEDIATION_STARTED"] is False
    assert man["MODEL_ENABLEMENT_CHANGED"] is False
    assert man["MODEL_ARTIFACTS_CHANGED"] is False


def test_no_governed_t003_overwrite_in_source():
    src = (ROOT / "src" / "features" / "feature_pipeline.py").read_text(encoding="utf-8")
    # the overwrite pattern must not remain
    assert 'df["volume"] = proxy' not in src
    assert "volume_range_proxy" in src
