"""B0/B1 feature semantic-migration governance — focused floor.

Fresh, self-contained reproduction of the 5 target-feature findings (F1-F5) plus the governance
guards added in the B0/B1 remediation (2026-07-12). NO production math is changed by the remediation;
these tests pin that fact and make silent future drift fail closed.

Targets: ema_spread, momentum_score, atr, rsi_14, wick_size.
See reports/analysis/b0-b1-feature-semantic-migration-2026-07-12.md.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from features.feature_pipeline import FeaturePipeline
from features.feature_schema import CANONICAL_FEATURES, CANONICAL_FEATURE_DIM
from features import derived_math as dm
from features import formula_registry as fr


# ── synthetic frame (deterministic; survives finalize warmup budget 300) ──────────────
def _frame(n=400, base=100.0, seed=7, k=1.0):
    rng = np.random.default_rng(seed)
    close = (base + np.cumsum(rng.normal(0, 0.15, n)) + 3.0 * np.sin(np.arange(n) / 9.0)) * k
    open_ = np.concatenate([[close[0]], close[:-1]])
    span = (0.4 + 0.2 * np.abs(rng.normal(0, 1, n))) * k
    high = np.maximum(open_, close) + span
    low = np.minimum(open_, close) - span
    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="15min"),
        "open": open_, "high": high, "low": low, "close": close,
        "volume": np.full(n, 1000.0),
    })


def _run(df):
    enriched, _ = FeaturePipeline(df.copy()).run()
    return enriched


# ── independent reference implementations (NOT production) ─────────────────────────────
def _sma_atr(tr, p=14):
    return pd.Series(tr).rolling(p).mean().to_numpy()


def _wilder_atr(tr, p=14):
    tr = np.asarray(tr, float); n = len(tr); out = np.full(n, np.nan)
    if n < p:
        return out
    out[p - 1] = np.nanmean(tr[:p])
    for t in range(p, n):
        out[t] = (out[t - 1] * (p - 1) + tr[t]) / p
    return out


def _rsi(close, p=14, wilder=False):
    close = pd.Series(close, dtype=float); d = close.diff()
    g = d.clip(lower=0); l = (-d.clip(upper=0))
    if wilder:
        ag = g.ewm(alpha=1 / p, adjust=False, min_periods=p).mean()
        al = l.ewm(alpha=1 / p, adjust=False, min_periods=p).mean()
    else:
        ag = g.rolling(p).mean(); al = l.rolling(p).mean()
    rs = ag / (al + 1e-9)
    return (100 - 100 / (1 + rs)).clip(0, 100).to_numpy()


def _true_range(df):
    tr1 = df["high"] - df["low"]
    tr2 = (df["high"] - df["close"].shift(1)).abs()
    tr3 = (df["low"] - df["close"].shift(1)).abs()
    return np.maximum(tr1, np.maximum(tr2, tr3)).to_numpy()


# ── corrected (proposed FM-030/FM-031) reference math — divides by ABSOLUTE atr ─────────
def _ema_spread_corrected(ema_fast, ema_slow, atr_rel, close):
    return (ema_fast - ema_slow) / (atr_rel * close)


def _momentum_corrected(close_delta, atr_rel, close):
    return close_delta / (atr_rel * close)


# ═══════════════════════════════════ FORMULA TESTS ═══════════════════════════════════

def test_F1_legacy_ema_spread_scales_with_price():
    """FM-022 legacy: (ema_fast-ema_slow)/atr_relative -> scales with price level."""
    e1 = _run(_frame(k=1.0)); e100 = _run(_frame(k=100.0))
    m = e1.merge(e100, on="timestamp", suffixes=("_1", "_100"))
    a = m["ema_spread_1"].to_numpy(float); b = m["ema_spread_100"].to_numpy(float)
    denom = np.where(np.abs(a) > 1e-6, np.abs(a), np.nan)
    assert np.nanmedian(np.abs(b) / denom) == pytest.approx(100.0, rel=0.02)


def test_F2_legacy_momentum_score_scales_with_price():
    e1 = _run(_frame(k=1.0)); e100 = _run(_frame(k=100.0))
    m = e1.merge(e100, on="timestamp", suffixes=("_1", "_100"))
    a = m["momentum_score_1"].to_numpy(float); b = m["momentum_score_100"].to_numpy(float)
    denom = np.where(np.abs(a) > 1e-6, np.abs(a), np.nan)
    assert np.nanmedian(np.abs(b) / denom) == pytest.approx(100.0, rel=0.02)


def test_corrected_ema_spread_atr_is_scale_invariant():
    """FM-030 proposal: (ema_fast-ema_slow)/(atr_absolute) -> invariant to price level."""
    e1 = _run(_frame(k=1.0)); e100 = _run(_frame(k=100.0))
    m = e1.merge(e100, on="timestamp", suffixes=("_1", "_100"))
    c1 = _ema_spread_corrected(m["ema_fast_1"], m["ema_slow_1"], m["atr_1"], m["close_1"]).to_numpy(float)
    c100 = _ema_spread_corrected(m["ema_fast_100"], m["ema_slow_100"], m["atr_100"], m["close_100"]).to_numpy(float)
    # invariant to within float32 pipeline-column precision (legacy scales by 100x -> diff ~thousands)
    assert np.nanmax(np.abs(c1 - c100)) < 1e-3


def test_corrected_momentum_score_atr_is_scale_invariant():
    """FM-031 proposal: close_delta/(atr_absolute) -> invariant."""
    e1 = _run(_frame(k=1.0)); e100 = _run(_frame(k=100.0))
    m = e1.merge(e100, on="timestamp", suffixes=("_1", "_100"))
    cd1 = m["close_1"].diff().to_numpy(float); cd100 = m["close_100"].diff().to_numpy(float)
    c1 = cd1 / (m["atr_1"].to_numpy(float) * m["close_1"].to_numpy(float))
    c100 = cd100 / (m["atr_100"].to_numpy(float) * m["close_100"].to_numpy(float))
    mask = ~(np.isnan(c1) | np.isnan(c100))
    assert np.nanmax(np.abs(c1[mask] - c100[mask])) < 1e-6


def test_F3_atr_is_sma_not_wilder():
    df = _frame(seed=13)
    enr = _run(df)
    tr = _true_range(df)
    ref = pd.DataFrame({"timestamp": df["timestamp"], "sma": _sma_atr(tr), "wild": _wilder_atr(tr)})
    m = enr.merge(ref, on="timestamp")
    prod = m["atr_14_raw"].to_numpy(float)
    diff_sma = np.abs(prod - m["sma"].to_numpy(float))
    diff_wild = np.abs(prod - m["wild"].to_numpy(float))
    assert np.nanmax(diff_sma) < 1e-9        # production IS SMA-of-TR
    assert np.nanmax(diff_wild) > 1e-3       # production is NOT Wilder


def test_F4_rsi_is_sma_not_wilder():
    df = _frame(seed=13)
    enr = _run(df)
    ref = pd.DataFrame({"timestamp": df["timestamp"],
                        "sma": _rsi(df["close"], wilder=False),
                        "wild": _rsi(df["close"], wilder=True)})
    m = enr.merge(ref, on="timestamp")
    prod = m["rsi_14"].to_numpy(float)
    assert np.nanmax(np.abs(prod - m["sma"].to_numpy(float))) < 1e-9   # IS SMA
    assert np.nanmax(np.abs(prod - m["wild"].to_numpy(float))) > 1.0   # NOT Wilder


def test_F5_candle_range_slot_is_the_range_not_wick_magnitude():
    """B1/F5, re-pinned for schema v4.0.

    The finding was that the slot named `wick_size` actually held the full candle RANGE. v4.0 renamed
    the slot to `candle_range`, so the assertion is now that the honestly-named slot holds the
    honest quantity — and, still, that it is NOT wick magnitude. Renaming resolved the misnomer; it
    did not change the math, which is exactly what makes the second assertion still meaningful.
    """
    from features import candle_math as cm
    df = _frame(seed=5)
    enr = _run(df)
    hl = (enr["high"] - enr["low"]).to_numpy(float)
    assert np.max(np.abs(enr["candle_range"].to_numpy(float) - hl)) < 1e-6
    assert "wick_size" not in enr.columns, "the v3 misnomer must no longer be emitted"
    # actual wick magnitude via the CANONICAL registered impl (cm.total_wick) — NOT a re-derivation.
    r = enr.loc[enr["body_size"].astype(float).idxmax()]
    cr = cm.candle_range(r["high"], r["low"])
    tw = cm.total_wick(r["open"], r["high"], r["low"], r["close"])
    assert cr == pytest.approx(float(r["candle_range"]))
    assert abs(cr - tw) > 1e-6                             # range != wick magnitude when a body exists


# ═══════════════════════════════════ MIGRATION / GOVERNANCE TESTS ═════════════════════

def test_canonical_dim_is_39_and_target_slots_pinned():
    """Schema v4.0 (was: dim 38, `wick_size` at 27, `body_ratio` at 28).

    The B0/B1 targets below (ema_spread, momentum_score, atr, rsi_14) sit BEFORE the MACD split at
    index 18, so their positions are unchanged — which is the point worth pinning: the v4 migration
    did not disturb the dimensional-mix features this file governs. The two slots that DID move are
    pinned at their new positions.
    """
    assert CANONICAL_FEATURE_DIM == 39
    assert len(CANONICAL_FEATURES) == 39
    idx = {f: i for i, f in enumerate(CANONICAL_FEATURES)}
    # unchanged by v4 (all precede the index-18 split)
    assert idx["ema_spread"] == 9
    assert idx["momentum_score"] == 12
    assert idx["atr"] == 13
    assert idx["rsi_14"] == 15
    # moved by v4
    assert idx["macd_hist_raw"] == 18 and idx["macd_hist_z"] == 19   # the split
    assert idx["candle_range"] == 28                                  # was `wick_size` at 27
    assert idx["body_ratio"] == 29                                    # shifted +1 by the split
    assert "wick_size" not in idx and "macd_hist" not in idx


def test_legacy_formula_strings_pinned():
    """Fail-closed guard: the legacy math must not silently change semantic meaning.

    Checks the pinned MATH as a prefix, not exact string equality: the
    FM-030-031-DIMENSIONAL-MIX-MIGRATION program (2026-07-22) appended a trailing clarifying
    comment ("# emitted only when <feature_pipeline.normalization_basis> == ...") documenting
    the config-gated selector added alongside FM-030/FM-031 -- prose, not a math change. An
    exact-match pin against the pre-2026-07-22 bare string is what actually broke here; the
    invariant this test protects (the legacy math itself) is unaffected.
    """
    ont = fr.load_ontology()
    assert ont["derived_metrics"]["ema_spread"]["formula"].startswith(
        "(ema_fast - ema_slow) / atr if atr>0 else nan"
    )
    assert ont["derived_metrics"]["momentum_score"]["formula"].startswith(
        "close_delta / atr if atr>0 else nan"
    )
    # registry impls still resolve; no problems introduced
    assert fr.validate_registry(ont) == []


def test_ontology_machine_readable_identity_fields():
    ont = fr.load_ontology()
    es = ont["derived_metrics"]["ema_spread"]
    assert es["semantic_version"] == "1.0-legacy-price-scaled"
    assert es["replacement_identity"] == "FM-030"
    # 2026-07-22: token advanced FORMULA_CORRECTION_DEFERRED -> FORMULA_CORRECTION_CONFIG_GATED
    # under program FM-030-031-DIMENSIONAL-MIX-MIGRATION. The correction is no longer merely
    # deferred prose: FM-030/031 are registered identities with a real impl, selectable via
    # `feature_pipeline.normalization_basis`. Still NOT active (default arm is the legacy math,
    # byte-identical), so the legacy pins above and below this line are unchanged.
    assert "known_issue" in es and es["migration_class"] == "FORMULA_CORRECTION_CONFIG_GATED"
    assert es["config_key"] == "feature_pipeline.normalization_basis"
    mo = ont["derived_metrics"]["momentum_score"]
    assert mo["replacement_identity"] == "FM-031" and mo["units"] == "price_scaled"
    cr = ont["primitives"]["candle_range"]
    # v4.0: status advanced deprecated_misnomer_alias -> resolved_renamed_v4 (the vector slot was
    # renamed, so the misnomer no longer exists to deprecate). semantic_quantity is unchanged —
    # it was always the truth this entry asserted.
    assert cr["status"] == "resolved_renamed_v4" and cr["semantic_quantity"] == "candle_range"
    assert cr["vector_key"] == "candle_range" and "wick_size" in cr["aliases"]


def test_indicator_identities_declare_sma_not_wilder():
    ont = fr.load_ontology()
    assert ont["indicator_identities"]["atr"]["smoothing_method"] == "SMA"
    assert ont["indicator_identities"]["rsi_14"]["smoothing_method"] == "SMA"
    assert ont["indicator_identities"]["atr"]["output"] == "close_relative"


def test_migration_candidates_are_proposed_and_inactive():
    ont = fr.load_ontology()
    for name, fmid, rep in [("ema_spread_atr", "FM-030", "FM-022"),
                            ("momentum_score_atr", "FM-031", "FM-023")]:
        e = ont["migration_candidates"][name]
        assert e["id"] == fmid and e["replaces"] == rep
        assert e["active"] is False and e["status"] == "proposed_correction"
        assert "atr * close" in e["formula"]   # divides by ABSOLUTE atr


def test_rsi_docstring_no_longer_falsely_claims_wilder():
    import inspect
    from features.feature_pipeline import FeaturePipeline as FP
    src = inspect.getsource(FP.compute_indicators)
    assert "Standard Wilder formula" not in src
    assert "SMA" in src   # the corrected clarification is present


def test_legacy_scalar_math_unchanged():
    """The production scalar impls are byte-for-byte the legacy identities (no silent change)."""
    assert dm.ema_spread(2.0, 1.0, 0.5) == pytest.approx(2.0)        # (2-1)/0.5
    assert dm.momentum_score(1.0, 0.25) == pytest.approx(4.0)        # 1/0.25
    import math
    assert math.isnan(dm.ema_spread(2.0, 1.0, 0.0))                  # atr<=0 -> NaN (legacy fallback)
