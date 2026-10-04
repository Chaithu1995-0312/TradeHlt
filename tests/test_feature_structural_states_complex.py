"""Complex structural states — FM-057 / FM-058 / FM-060 / FM-061.

# NEEDS_VERIFICATION
====================
These features form a dependency chain through swing detection (FM-045/046),
which uses the FC1-A causal-delayed centered pivot (center=True math, published
with k-bar shift). Exact value matching against an independent swing oracle is
DEFERRED pending human review of the FC1-A contract.

What THIS file verifies (machine-checked):
  1. Ontology lifecycle + id + non-empty states for each feature.
  2. Pipeline output domain ⊆ ontology-declared state values.
  3. Cross-feature invariants that do NOT require trusting swing refs:
       - liquidity_sweep and break_of_structure mutually exclusive on same bar
         when both non-zero with opposing acceptance rules (ontology caveat).
       - double_sweep implies both directions of liquidity_sweep in the window
         (formula-level, using pipeline's own liquidity_sweep series).
       - retest_flag implies recent_sweep AND near_ema (formula-level).
       - sweep / BOS domain only.

What is NOT verified here (explicit gaps):
  - Exact last_swing_*_price vs independent FC1-A oracle
    → **closed in** `tests/test_fc1a_swing_oracle_parity.py` (type-1 oracle + scenarios).
  - Exact bar-by-bar BOS/sweep truth against human chart labels (gold set) — still open.
  - Economic meaning of any flag.

Human review markers: search this file for NEEDS_VERIFICATION (domain-only tests).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from config_layer.production_config import get_prod_section
from features.feature_pipeline import FeaturePipeline
from features.registry import load_ontology


# ── helpers ──────────────────────────────────────────────────────────────────

def _structural(name: str) -> dict:
    ont = load_ontology()
    if "structural_states" not in ont:
        raise KeyError("ontology missing structural_states")
    if name not in ont["structural_states"]:
        raise KeyError(f"structural_states missing {name!r}")
    entry = ont["structural_states"][name]
    if "lifecycle" not in entry:
        raise KeyError(f"{name}: lifecycle required (no silent omit)")
    if "id" not in entry:
        raise KeyError(f"{name}: id required")
    if not entry.get("states"):
        raise AssertionError(f"{name}: empty states — cannot domain-check")
    return entry


def _state_domain(name: str) -> set[int]:
    return {int(s["value"]) for s in _structural(name)["states"]}


def _fp_cfg() -> dict:
    return get_prod_section("feature_pipeline")


def _synthetic(n: int = 600, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    ts = pd.date_range("2024-02-01", periods=n, freq="15min")
    close = 100 + np.cumsum(rng.normal(0, 0.35, n))
    open_ = close + rng.normal(0, 0.06, n)
    high = np.maximum(open_, close) + rng.uniform(0.05, 0.9, n)
    low = np.minimum(open_, close) - rng.uniform(0.05, 0.9, n)
    return pd.DataFrame(
        {
            "timestamp": ts,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": rng.uniform(100, 2500, n),
        }
    )


def _run_structure(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    cfg = _fp_cfg()
    fp = FeaturePipeline(df, cfg=cfg)
    fp.compute_price_features()
    fp.compute_volume_features()
    fp.compute_indicators()
    fp.compute_trend_features()
    fp.compute_volatility_regime()
    fp.compute_context()
    fp.compute_structure_liquidity()
    fp.compute_normalization()
    fp.compute_canonical_price_features()
    fp.compute_canonical_volatility_features()
    fp.compute_canonical_ema_features()
    fp.compute_canonical_trend_features()
    fp.compute_canonical_structure_features()
    return fp.df, cfg


# ── ontology presence ────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "name,fid",
    [
        ("break_of_structure", "FM-057"),
        ("liquidity_sweep", "FM-058"),
        ("double_sweep", "FM-060"),
        ("retest_flag", "FM-061"),
    ],
)
def test_complex_structural_ontology_ids(name: str, fid: str):
    entry = _structural(name)
    assert entry["id"] == fid
    assert entry["lifecycle"]


# ── domain floors (trust pipeline; do not assert independent swing truth) ────
# NEEDS_VERIFICATION: domain ⊆ declared states only — not bar-level correctness.

def test_break_of_structure_domain():
    """# NEEDS_VERIFICATION: domain only; exact BOS vs hand labels deferred."""
    out, _ = _run_structure(_synthetic())
    domain = _state_domain("break_of_structure")
    vals = set(int(v) for v in out["break_of_structure"].dropna().unique())
    assert vals <= domain, f"BOS values {vals} outside ontology domain {domain}"


def test_liquidity_sweep_domain():
    """# NEEDS_VERIFICATION: domain only; exact sweep vs hand labels deferred."""
    out, _ = _run_structure(_synthetic())
    domain = _state_domain("liquidity_sweep")
    vals = set(int(v) for v in out["liquidity_sweep"].dropna().unique())
    assert vals <= domain


def test_double_sweep_domain():
    """# NEEDS_VERIFICATION: domain only."""
    out, _ = _run_structure(_synthetic())
    domain = _state_domain("double_sweep")
    vals = set(int(v) for v in out["double_sweep"].dropna().unique())
    assert vals <= domain


def test_retest_flag_domain():
    """# NEEDS_VERIFICATION: domain only; no vector slot but registered for FM-021."""
    out, _ = _run_structure(_synthetic())
    domain = _state_domain("retest_flag")
    vals = set(int(v) for v in out["retest_flag"].dropna().unique())
    assert vals <= domain


# ── formula-level invariants (given pipeline intermediate columns) ───────────

def test_double_sweep_matches_rolling_both_directions():
    """formula: any(sweep>0) and any(sweep<0) over rolling(double_sweep_window).

    Independent of how liquidity_sweep was produced — once that series exists,
    double_sweep must equal the rolling both-sides conjunction.
    """
    out, cfg = _run_structure(_synthetic())
    if "double_sweep_window" not in cfg:
        raise KeyError("double_sweep_window required")
    window = int(cfg["double_sweep_window"])
    sweep = out["liquidity_sweep"]
    seen_up = (sweep > 0).rolling(window=window, min_periods=1).max().astype(bool)
    seen_dn = (sweep < 0).rolling(window=window, min_periods=1).max().astype(bool)
    expected = (seen_up & seen_dn).astype(np.int8)
    np.testing.assert_array_equal(out["double_sweep"].to_numpy(), expected.to_numpy())


def test_retest_flag_matches_lookback_and_band():
    """formula: rolling_any(sweep!=0, lookback) AND |close-ema_fast| <= mult*atr*close."""
    out, cfg = _run_structure(_synthetic())
    for key in ("retest_lookback", "retest_atr_band_mult"):
        if key not in cfg:
            raise KeyError(f"{key} required")
    lookback = int(cfg["retest_lookback"])
    mult = float(cfg["retest_atr_band_mult"])
    recent = (
        (out["liquidity_sweep"] != 0)
        .rolling(window=lookback, min_periods=1)
        .max()
        .astype(bool)
    )
    near = (out["close"] - out["ema_fast"]).abs() <= (mult * out["atr"] * out["close"])
    expected = (recent & near).astype(np.int8)
    np.testing.assert_array_equal(out["retest_flag"].to_numpy(), expected.to_numpy())


def test_bos_and_sweep_match_ref_formulas_given_pipeline_swings():
    """Apply ontology BOS/sweep formulas to pipeline last_swing_* (not re-derived).

    # NEEDS_VERIFICATION of last_swing_* themselves (FC1-A causal delay).
    This asserts the STRUCTURE GRAPH math only.
    """
    out, _ = _run_structure(_synthetic())
    ref_high = out["last_swing_high_price"].shift(1)
    ref_low = out["last_swing_low_price"].shift(1)

    bos_exp = np.where(
        out["close"] > ref_high, 1,
        np.where(out["close"] < ref_low, -1, 0),
    ).astype(np.int8)
    np.testing.assert_array_equal(out["break_of_structure"].to_numpy(), bos_exp)

    sweep_hi = (out["high"] > ref_high) & (out["close"] <= ref_high)
    sweep_lo = (out["low"] < ref_low) & (out["close"] >= ref_low)
    sweep_exp = np.where(sweep_hi, 1, np.where(sweep_lo, -1, 0)).astype(np.int8)
    np.testing.assert_array_equal(out["liquidity_sweep"].to_numpy(), sweep_exp)


def test_bos_and_sweep_mutually_exclusive_on_same_reference_side():
    """Ontology caveat: sweep requires close back inside; BOS requires close outside.

    On a given bar, (bos==1 and sweep==1) or (bos==-1 and sweep==-1) cannot both
    hold under the formula (same ref comparison). Mixed signs on opposite sides
    remain possible in principle; we only assert the same-side contradiction.
    """
    out, _ = _run_structure(_synthetic())
    bos = out["break_of_structure"].to_numpy()
    sw = out["liquidity_sweep"].to_numpy()
    same_side_both = ((bos == 1) & (sw == 1)) | ((bos == -1) & (sw == -1))
    assert not same_side_both.any(), (
        "same-side BOS+sweep co-occurrence violates ontology mutual-exclusion"
    )


# ── documentation anchor for human review ────────────────────────────────────

def test_needs_verification_markers_present():
    """Keep the deferred surface greppable — do not silently claim full proof."""
    import pathlib

    src = pathlib.Path(__file__).read_text(encoding="utf-8")
    assert src.count("NEEDS_VERIFICATION") >= 4
    assert "FC1-A" in src
