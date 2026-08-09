"""FM-030/031 normalization-basis floor — program FM-030-031-DIMENSIONAL-MIX-MIGRATION.

Pins the contract of `feature_pipeline.normalization_basis` (2026-07-22):

  1. DEFAULT PARITY   — the active config selects "atr_relative", and that arm reproduces the
                        legacy FM-022/FM-023 math exactly. (The repo-level proof is the XAUUSD
                        vector SHA in tests/test_feature_layer_freeze.py; this file pins the
                        column math directly so a regression names the right feature.)
  2. CLOSED FORM      — "atr_absolute" output == "atr_relative" output / close. This is what makes
                        the defect a pure scale factor, and it is the reason F-061's saturation
                        story is arithmetic rather than empirical.
  3. SCALE INVARIANCE — 100x the price series: FM-030/031 are unchanged, FM-022/023 are multiplied
                        by 100. The second half is the DEFECT, pinned deliberately so a future
                        "fix" to the legacy arm cannot land silently.
  4/5. STRICTNESS     — a missing key raises, and an unrecognised value raises. No silent
                        fall-through to the legacy arm (CLAUDE.md §6.5 hard rule).
  6. SCALAR PARITY    — derived_math.ema_spread_atr / momentum_score_atr agree with the pipeline
                        columns. This is the coverage that entitles FM-030/031 to lifecycle
                        `parity_verified` in tests/test_feature_lineage.py::_PARITY_COVERED.

Grants NO production authority (§6.5): the corrected identities stay `active: false`.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from config_layer.production_config import get_prod_section          # noqa: E402
from features import derived_math as dm                              # noqa: E402
from features.feature_pipeline import FeaturePipeline                # noqa: E402
from features.registry import compute_derived, load_ontology         # noqa: E402

CSV = ROOT / "data" / "BNBUSDT_M15.csv"
ROWS = 3000          # enough to clear warm-up and exercise both arms; keeps the floor fast
COLS = ("ema_spread", "momentum_score")


@pytest.fixture(scope="module")
def base_cfg() -> dict:
    return dict(get_prod_section("feature_pipeline"))


@pytest.fixture(scope="module")
def raw() -> pd.DataFrame:
    if not CSV.is_file():
        pytest.skip(f"corpus absent: {CSV}")
    return pd.read_csv(CSV).head(ROWS)


def _run(df: pd.DataFrame, cfg: dict, basis: str) -> pd.DataFrame:
    out, _vectors = FeaturePipeline(df, cfg={**cfg, "normalization_basis": basis}).run()
    return out


# ── 1. the active config ships the legacy arm, and it is the legacy math ────────────────────
def test_active_config_default_is_legacy_basis(base_cfg):
    assert base_cfg["normalization_basis"] == "atr_relative", (
        "the active production config must keep the LEGACY arm as default — switching it is an "
        "activation decision requiring demonstrated G001 improvement, not a config edit"
    )


def test_legacy_arm_reproduces_legacy_formula(raw, base_cfg):
    out = _run(raw, base_cfg, "atr_relative")
    atr = out["atr"].to_numpy(np.float64)
    expect_spread = (out["ema_fast"].to_numpy(np.float64) - out["ema_slow"].to_numpy(np.float64)) / atr
    ok = np.isfinite(expect_spread) & np.isfinite(out["ema_spread"].to_numpy(np.float64))
    assert ok.sum() > 100
    np.testing.assert_allclose(
        out["ema_spread"].to_numpy(np.float64)[ok], expect_spread[ok], rtol=1e-5,
    )


# ── 2. the closed form: corrected == legacy / close ─────────────────────────────────────────
@pytest.mark.parametrize("col", COLS)
def test_corrected_equals_legacy_over_close(raw, base_cfg, col):
    legacy = _run(raw, base_cfg, "atr_relative")
    corrected = _run(raw, base_cfg, "atr_absolute")
    assert len(legacy) == len(corrected), "basis must not change warm-up drop semantics"

    a = legacy[col].to_numpy(np.float64)
    b = corrected[col].to_numpy(np.float64)
    close = legacy["close"].to_numpy(np.float64)
    ok = np.isfinite(a) & np.isfinite(b)
    assert ok.sum() > 100
    # float32 emission: compare at single precision, not byte-equality
    np.testing.assert_allclose(b[ok], (a / close)[ok], rtol=1e-5)


# ── 3. scale invariance (and the pinned defect) ─────────────────────────────────────────────
@pytest.mark.parametrize("col", COLS)
def test_scale_invariance_corrected_and_defect_legacy(raw, base_cfg, col):
    scaled = raw.copy()
    for c in ("open", "high", "low", "close"):
        scaled[c] = scaled[c] * 100.0

    def med(df, basis):
        v = _run(df, base_cfg, basis)[col].to_numpy(np.float64)
        return float(np.nanmedian(np.abs(v)))

    corr_ratio = med(scaled, "atr_absolute") / med(raw, "atr_absolute")
    leg_ratio = med(scaled, "atr_relative") / med(raw, "atr_relative")

    assert corr_ratio == pytest.approx(1.0, rel=1e-3), (
        f"FM-030/031 must be scale-invariant; {col} moved by {corr_ratio:.4f}x at 100x price"
    )
    # The DEFECT, pinned on purpose: legacy scales with price level. If this ever fails, the
    # legacy arm changed — which would break every artifact bound to it (LEGACY_BOUND).
    assert leg_ratio == pytest.approx(100.0, rel=1e-3), (
        f"FM-022/023 legacy arm changed: {col} scaled by {leg_ratio:.4f}x, expected 100x"
    )


# ── 4/5. strict config discipline — no silent fall-through ──────────────────────────────────
def test_missing_basis_key_raises(raw, base_cfg):
    cfg = {k: v for k, v in base_cfg.items() if k != "normalization_basis"}
    with pytest.raises(KeyError, match="normalization_basis"):
        FeaturePipeline(raw, cfg=cfg)


def test_unrecognised_basis_raises(raw, base_cfg):
    with pytest.raises(ValueError, match="normalization_basis"):
        FeaturePipeline(raw, cfg={**base_cfg, "normalization_basis": "atr_typo"})


# ── 6. scalar <-> pipeline parity (the lifecycle=parity_verified warrant) ───────────────────
@pytest.mark.parametrize(
    "col,scalar,args",
    [
        ("ema_spread", dm.ema_spread_atr, ("ema_fast", "ema_slow", "atr", "close")),
        ("momentum_score", dm.momentum_score_atr, ("close_delta", "atr", "close")),
    ],
)
def test_scalar_matches_pipeline_under_atr_absolute(raw, base_cfg, col, scalar, args):
    out = _run(raw, base_cfg, "atr_absolute")
    out = out.reset_index(drop=True)
    out["close_delta"] = out["close"].diff()

    checked = 0
    for i in range(50, min(len(out), 400)):
        row = out.iloc[i]
        vals = [float(row[a]) for a in args]
        if not all(np.isfinite(v) for v in vals) or not np.isfinite(row[col]):
            continue
        assert float(scalar(*vals)) == pytest.approx(float(row[col]), rel=1e-4)
        checked += 1
    assert checked > 50, "parity battery did not exercise enough finite rows"


def test_registry_dispatch_resolves_new_identities():
    """The identities must execute through the registry facade (NO eval), like every other FM."""
    ont = load_ontology()
    for name, fid in (("ema_spread_atr", "FM-030"), ("momentum_score_atr", "FM-031")):
        spec = ont["derived_metrics"][name]
        assert spec["id"] == fid
        assert spec["active"] is False, f"{name} must stay inactive — registration is not activation"
        assert spec["config_key"] == "feature_pipeline.normalization_basis"

    # (ema_fast-ema_slow)/(atr*close) = (2-1)/(0.5*4) = 0.5
    assert compute_derived(
        "ema_spread_atr", ema_fast=2.0, ema_slow=1.0, atr=0.5, close=4.0
    ) == pytest.approx(0.5)
    # close_delta/(atr*close) = 1/(0.25*8) = 0.5
    assert compute_derived(
        "momentum_score_atr", close_delta=1.0, atr=0.25, close=8.0
    ) == pytest.approx(0.5)


def test_scalar_nan_discipline_mirrors_legacy():
    """NaN fallbacks must match FM-022/023 so finalize() drops identical warm-up rows."""
    assert np.isnan(dm.ema_spread_atr(2.0, 1.0, 0.0, 100.0))
    assert np.isnan(dm.ema_spread_atr(2.0, 1.0, 0.5, 0.0))
    assert np.isnan(dm.momentum_score_atr(1.0, 0.0, 100.0))
    assert np.isnan(dm.momentum_score_atr(1.0, 0.25, 0.0))
