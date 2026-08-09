"""L3 swing-structural family certification floor — the durable gate that higher_high / lower_low /
break_of_structure / liquidity_sweep stay certified by BOTH a formula-parity oracle and an
independent CAUSAL online oracle, with the inclusive sweep boundary exercised.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

_REPO = Path(__file__).resolve().parents[1]
_PROBE = _REPO / "scripts" / "analysis" / "feature_dag_structural_certification.py"


def _load():
    spec = importlib.util.spec_from_file_location("feature_dag_structural_certification", _PROBE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["feature_dag_structural_certification"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def probe():
    if not _PROBE.exists():
        pytest.skip("structural certification probe not present")
    return _load()


@pytest.fixture(scope="module")
def synth(probe):
    return probe._synthetic()


def test_both_oracles_match_pipeline(probe, synth):
    arm = probe.certify_arm(synth, "floor")
    # covers the swing-structural family + the derived sweep_detected projection
    assert "sweep_detected" in arm["per_flag"]
    for f, r in arm["per_flag"].items():
        assert r["formula_parity_centered"], f"{f}: centered formula oracle != pipeline"
        assert r["causal_online_matches_pipeline"], f"{f}: CAUSAL online oracle != pipeline (causality break)"


def test_causal_online_oracle_is_prefix_invariant(probe, synth):
    """The causality proof as a property: the online oracle at bar t uses only bars <= t, so
    truncating the input reproduces the head of the full computation EXACTLY."""
    full = probe._oracle_causal_online(synth)
    for frac in (0.5, 0.8):
        m = int(len(synth) * frac)
        pref = probe._oracle_causal_online(synth.head(m))
        shared = pref.index.intersection(full.index)
        assert len(shared) > 100
        for f in probe._ALL_FLAGS:
            a = pref.loc[shared, f].to_numpy()
            b = full.loc[shared, f].to_numpy()
            assert np.array_equal(a, b), f"{f}: online oracle is prefix-VARIANT — future dependence"


def test_inclusive_sweep_boundary_exercised_and_reproduced(probe):
    """Integer-rounded prices force close==ref ties so the INCLUSIVE <=/>= sweep boundary is actually
    hit; both oracles must still equal the pipeline on those boundary rows."""
    raw = probe._synthetic(n=1400, seed=7).copy()
    for c in ("open", "high", "low", "close"):
        raw[c] = raw[c].round().astype(float)
    arm = probe.certify_arm(raw, "floor_int")
    b = arm["equality_boundary_counts"]
    assert (b["close_eq_ref_high"] + b["close_eq_ref_low"]) > 0, "boundary not exercised — strengthen fixture"
    for f, r in arm["per_flag"].items():
        assert r["formula_parity_centered"] and r["causal_online_matches_pipeline"], (
            f"{f}: oracle mismatch on integer/boundary data"
        )


def test_double_sweep_window_boundary_semantics(probe):
    """Exact-window boundary + conjunction-not-count: up@t and down@t+4 (within the trailing 5-window)
    → 1 at t+4; up@t and down@t+5 (out of window) → 0 at t+5; two ups, no down → 0 everywhere."""
    import numpy as np
    W = probe._DOUBLE_SWEEP_WINDOW
    assert W == 5
    n = 20
    # up at idx 2, down at idx 2+(W-1)=6 → within one trailing 5-window at idx 6
    a = np.zeros(n, dtype="int8"); a[2] = 1; a[2 + (W - 1)] = -1
    ds = probe._double_sweep(a)
    assert ds[2 + (W - 1)] == 1, "up@t & down@t+4 must be a double_sweep within the 5-window"
    # up at idx 2, down at idx 2+W=7 → idx 2 has fallen out of the trailing window at idx 7
    b = np.zeros(n, dtype="int8"); b[2] = 1; b[2 + W] = -1
    dsb = probe._double_sweep(b)
    assert dsb[2 + W] == 0, "up@t & down@t+5 must NOT be a double_sweep (up out of window)"
    # two same-direction sweeps, no opposite → never a double_sweep (conjunction, not count)
    c = np.zeros(n, dtype="int8"); c[3] = 1; c[4] = 1
    assert probe._double_sweep(c).sum() == 0, "two up-sweeps (no down) must never be a double_sweep"


def test_double_sweep_prefix_invariant_explicit(probe, synth):
    """Direct (not inherited) prefix invariance for the new windowed transform, causal-online oracle:
    double_sweep(full)[:n] == double_sweep(full.head(n))."""
    import numpy as np
    assert "double_sweep" in probe._ALL_FLAGS
    full = probe._oracle_causal_online(synth)
    for frac in (0.5, 0.8):
        m = int(len(synth) * frac)
        pref = probe._oracle_causal_online(synth.head(m))
        shared = pref.index.intersection(full.index)
        assert len(shared) > 100
        assert np.array_equal(pref.loc[shared, "double_sweep"].to_numpy(),
                              full.loc[shared, "double_sweep"].to_numpy()), "double_sweep prefix-VARIANT"


# ── candles_since_retest counter property battery (each pinned separately) ──────────

def test_csr_before_first_sweep_all_zeros(probe):
    import numpy as np
    liq = np.zeros(25, dtype="int8")            # no sweep ever
    assert np.all(probe._candles_since_retest(liq) == 0)
    liq2 = np.zeros(25, dtype="int8"); liq2[10] = 1   # first sweep at 10
    csr = probe._candles_since_retest(liq2)
    assert np.all(csr[:10] == 0), "a long no-event run BEFORE the first sweep must stay all zeros"


def test_csr_after_sweep_increments(probe):
    import numpy as np
    liq = np.zeros(25, dtype="int8"); liq[3] = 1     # single sweep at 3, then long no-event run
    csr = probe._candles_since_retest(liq)
    assert csr[3] == 0, "event bar publishes 0"
    assert csr[4] == 1, "first bar after the event = 1"
    assert list(csr[3:10]) == [0, 1, 2, 3, 4, 5, 6], "after a sweep the run increments 0,1,2,3,…"


def test_csr_consecutive_events_each_zero(probe):
    import numpy as np
    liq = np.zeros(15, dtype="int8"); liq[3] = 1; liq[4] = -1; liq[5] = 1
    csr = probe._candles_since_retest(liq)
    assert list(csr[3:6]) == [0, 0, 0], "consecutive sweeps each reset to 0 (own group)"


def test_csr_multiple_separated_events_reset_each(probe):
    import numpy as np
    liq = np.zeros(20, dtype="int8"); liq[3] = 1; liq[8] = -1
    csr = probe._candles_since_retest(liq)
    assert list(csr[3:9]) == [0, 1, 2, 3, 4, 0], "each separated sweep resets the counter"


def test_csr_prefix_invariant_and_dtype(probe, synth):
    import numpy as np
    full = probe._oracle_causal_online(synth)
    assert full["candles_since_retest"].to_numpy().dtype == np.int16
    for frac in (0.5, 0.8):
        m = int(len(synth) * frac)
        pref = probe._oracle_causal_online(synth.head(m))
        shared = pref.index.intersection(full.index)
        assert np.array_equal(pref.loc[shared, "candles_since_retest"].to_numpy(),
                              full.loc[shared, "candles_since_retest"].to_numpy()), "csr prefix-VARIANT"


# ── class-B fallback fence (runtime-first) ──────────────────────────────────────────

def test_csr_runtime_production_path_uses_liquidity_sweep(probe, monkeypatch):
    """PRIMARY fence: instrument (test-layer only) the actual run() control flow — at
    compute_canonical_temporal_features ENTRY, liquidity_sweep must exist (int8, domain ⊆{-1,0,1}),
    and the emitted candles_since_retest must equal the online recurrence over it (production branch)."""
    import numpy as np
    from features.feature_pipeline import FeaturePipeline
    cap = {}
    orig = FeaturePipeline.compute_canonical_temporal_features

    def spy(self):
        cap["has_liq"] = "liquidity_sweep" in self.df.columns
        cap["dtype"] = str(self.df["liquidity_sweep"].dtype) if cap["has_liq"] else None
        cap["liq"] = self.df["liquidity_sweep"].to_numpy().copy() if cap["has_liq"] else None
        r = orig(self)
        cap["csr"] = self.df["candles_since_retest"].to_numpy().copy()
        return r

    monkeypatch.setattr(FeaturePipeline, "compute_canonical_temporal_features", spy)
    FeaturePipeline(probe._synthetic().copy()).run()
    assert cap["has_liq"], "RUNTIME: temporal features reached WITHOUT liquidity_sweep — fallback reachable in production!"
    assert cap["dtype"] == "int8"
    assert set(np.unique(cap["liq"])).issubset({-1, 0, 1}), "liquidity_sweep domain contract violated"
    assert np.array_equal(probe._candles_since_retest(cap["liq"]), cap["csr"]), (
        "emitted candles_since_retest != online recurrence over liquidity_sweep — production branch not taken"
    )


def test_csr_source_order_secondary_guard():
    """SECONDARY governance alarm: run() computes structure/liquidity before temporal features."""
    src = (Path(__file__).resolve().parents[1] / "src" / "features" / "feature_pipeline.py").read_text(encoding="utf-8")
    i_struct = src.index("self.compute_structure_liquidity()")
    i_temporal = src.index("self.compute_canonical_temporal_features()")
    assert i_struct < i_temporal, "run() must compute liquidity_sweep before candles_since_retest"


def test_csr_branch_discrimination_deterministic(probe):
    """The two input contracts are provably DISTINCT identities (semantic, not corpus-contingent):
    liquidity_sweep events {3,8} vs retest_flag events {5} → different counters."""
    import numpy as np
    liq_stream = np.zeros(15, dtype="int8"); liq_stream[3] = 1; liq_stream[8] = -1
    rf_stream = np.zeros(15, dtype="int8"); rf_stream[5] = 1    # fallback resets where retest_flag==1
    prod = probe._candles_since_retest(liq_stream)
    fallback = probe._candles_since_retest(rf_stream)
    assert not np.array_equal(prod, fallback), (
        "production (liquidity_sweep) and fallback (retest_flag) branches must be provably distinct"
    )


# ── liquidity_distance (FM-025) property battery ────────────────────────────────────

def test_ld_no_bos_uses_swing_levels_only(probe):
    import numpy as np
    # no BOS → bos_level NaN → min over ref_high/ref_low only. atr_abs = atr*close = 0.1*8 = 0.8
    ld = probe._liquidity_distance([10.0], [5.0], [0], [8.0], [0.1])
    assert abs(ld[0] - abs(8.0 - 10.0) / 0.8) < 1e-4   # nearest = ref_high, 2.5


def test_ld_positive_bos_ffill_participates(probe):
    import numpy as np
    # t0 BOS==1 sets bos_level=ref_high(10); at t1 the swings moved away (20,15) but the ffill'd
    # bos_level(10) is nearest → proves positive-BOS level + ffill participate in the min.
    ld = probe._liquidity_distance([10.0, 20.0], [1.0, 15.0], [1, 0], [10.5, 10.5], [0.1, 0.1])
    assert abs(ld[1] - abs(10.5 - 10.0) / (0.1 * 10.5)) < 1e-4   # bos_level ffill'd is nearest


def test_ld_negative_bos_uses_ref_low(probe):
    ld = probe._liquidity_distance([10.0, 20.0], [8.0, 1.0], [-1, 0], [8.5, 8.5], [0.1, 0.1])
    assert abs(ld[1] - abs(8.5 - 8.0) / (0.1 * 8.5)) < 1e-4      # bos_level = ref_low(8) ffill'd, nearest


def test_ld_distance_exactly_zero(probe):
    ld = probe._liquidity_distance([10.0], [5.0], [0], [10.0], [0.1])   # close == ref_high
    assert ld[0] == 0.0


def test_ld_atr_zero_and_warmup_are_nan(probe):
    import numpy as np
    assert np.isnan(probe._liquidity_distance([10.0], [5.0], [0], [8.0], [0.0])[0])          # atr=0
    assert np.isnan(probe._liquidity_distance([10.0], [5.0], [0], [8.0], [np.nan])[0])       # atr NaN (warmup)


def test_ld_nonneg_no_inf_and_nan_policy(probe, synth):
    import numpy as np
    onl = probe._oracle_causal_online(synth)
    close_full, atr_full = probe._indep_close_relative_atr(synth)
    ld = probe._liquidity_distance(onl["ref_high"].to_numpy(), onl["ref_low"].to_numpy(),
                                   onl["break_of_structure"].to_numpy(), close_full, atr_full)
    assert not np.isinf(ld).any(), "liquidity_distance must never be Inf (atr_safe>0 guard)"
    fin = np.isfinite(ld)
    assert np.all(ld[fin] >= 0.0), "distance is a magnitude — always >= 0"


def test_ld_prefix_invariant(probe, synth):
    import numpy as np
    onl = probe._oracle_causal_online(synth)
    close_full, atr_full = probe._indep_close_relative_atr(synth)
    full = probe._liquidity_distance(onl["ref_high"].to_numpy(), onl["ref_low"].to_numpy(),
                                     onl["break_of_structure"].to_numpy(), close_full, atr_full)
    for frac in (0.5, 0.8):
        n = int(len(synth) * frac)
        pref = probe._liquidity_distance(onl["ref_high"].to_numpy()[:n], onl["ref_low"].to_numpy()[:n],
                                         onl["break_of_structure"].to_numpy()[:n], close_full[:n], atr_full[:n])
        a, b = pref, full[:n]
        eq = (a == b) | (np.isnan(a) & np.isnan(b))
        assert eq.all(), "liquidity_distance (with bos_level ffill) must be prefix-invariant"


def test_ld_scale_invariance(probe):
    import numpy as np
    from features.feature_pipeline import FeaturePipeline
    raw = probe._synthetic()
    f1, _ = FeaturePipeline(raw.copy()).run()
    scaled = raw.copy()
    for c in ("open", "high", "low", "close"):
        scaled[c] = scaled[c] * 100.0
    f100, _ = FeaturePipeline(scaled).run()
    a = f1.set_index("timestamp")["liquidity_distance"]
    b = f100.set_index("timestamp")["liquidity_distance"]
    sh = a.index.intersection(b.index)
    assert len(sh) > 100
    assert np.allclose(a.loc[sh].to_numpy("float64"), b.loc[sh].to_numpy("float64"), rtol=1e-3, atol=1e-4), (
        "liquidity_distance is ATR-normalized → must be scale-invariant"
    )


def test_verdicts_certified_and_deterministic(probe):
    r1 = probe.build_report(limit=0, include_corpus=False)
    r2 = probe.build_report(limit=0, include_corpus=False)
    import json
    assert json.dumps(r1["verdicts"], sort_keys=True) == json.dumps(r2["verdicts"], sort_keys=True)
    assert r1["overall"] == "CERTIFIED"
    for f in probe._ALL_CERTIFIED:
        assert r1["verdicts"][f] == "CERTIFIED"
    assert "sweep_detected" in r1["verdicts"] and "liquidity_distance" in r1["verdicts"]
    # PIT evidence is dependency-bound (carries a repo_state_hash + the online oracle as causality proof)
    assert r1["pit_evidence"]["repo_state_hash"]
    assert r1["pit_evidence"]["causal_online_oracle"] == "matched"
