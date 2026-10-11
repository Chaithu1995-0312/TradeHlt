"""Causality and matching-contract tests for scripts/analysis/pnp_incremental_test.py."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "analysis"))
import pnp_incremental_test as pit  # noqa: E402


def synth(n=4000, seed=0):
    rng = np.random.default_rng(seed)
    close = 2000 * np.exp(np.cumsum(rng.normal(0, 0.0007, n)))
    return pd.DataFrame({"timestamp": pd.date_range("2024-01-01", periods=n, freq="15min"), "close": close,
                         "volatility_ratio": rng.uniform(0.5, 1.5, n), "volatility_regime": rng.integers(0, 3, n),
                         "session": rng.integers(0, 3, n)})


def test_context_is_prefix_invariant():
    df = synth()
    full = pit.build_context(df)
    for cut in (1500, 2600, 3999):
        part = pit.build_context(df.iloc[:cut].copy())
        a, b = part.drop(columns="timestamp").to_numpy(float), full.drop(columns="timestamp").iloc[:cut].to_numpy(float)
        assert np.allclose(a, b, equal_nan=True), cut


def test_htf_state_ignores_incomplete_bucket():
    df = synth(800)
    base = pit.build_context(df)["htf_state"].to_numpy()
    df2 = df.copy(); df2.loc[df2.index[-1], "close"] *= 3          # change only the last (incomplete) bar
    assert np.array_equal(base[:-1], pit.build_context(df2)["htf_state"].to_numpy()[:-1])


def test_matching_respects_strata_caliper_exclusion_and_no_reuse():
    df = synth(6000, 1); ctx = pit.build_context(df)
    n = len(df); fsign = np.where(np.random.default_rng(2).random(n) > .5, 1, -1)
    ok = np.isfinite(ctx[["prior_ret_16", "prior_ret_64", "volatility_ratio"]].to_numpy(float)).all(axis=1)
    ev = np.where(ok & (np.arange(n) % 97 == 0) & (np.arange(n) > 300))[0]
    excl = np.zeros(n, bool)
    for i in ev:
        excl[max(0, i - 16):i + 17] = True
    sd = np.nanstd(ctx[["prior_ret_16", "prior_ret_64", "volatility_ratio"]].to_numpy(float), axis=0)
    pairs, unm = pit.match_family(ev, np.ones(len(ev), int), fsign, ctx, ok, excl, np.ones(n, bool), cal=0.5, k=1, replace=False, sd=sd)
    used = [c for _, ch in pairs for c in ch]
    assert len(used) == len(set(used))
    cov = ctx[["prior_ret_16", "prior_ret_64", "volatility_ratio"]].to_numpy(float)
    for pos, ch in pairs:
        i, c = ev[pos], ch[0]
        assert not excl[c] and fsign[c] == 1
        for col in ("htf_state", "volatility_regime", "session", "hour"):
            assert ctx[col].iloc[c] == ctx[col].iloc[i]
        assert np.all(np.abs(cov[c] - cov[i]) / sd <= 0.5 + 1e-12)
    assert len(pairs) + len(unm) == len(ev)


def test_bootstrap_detects_shift_and_not_null():
    rng = np.random.default_rng(1)
    days = np.repeat(np.arange(60), 5)
    assert pit.cluster_boot(rng.normal(5, 2, 300), days, rng)["p"] < 0.01
    assert pit.cluster_boot(rng.normal(0, 2, 300), days, rng)["p"] > 0.05


def test_cluster_ols_recovers_event_coefficient():
    rng = np.random.default_rng(3); n = 400
    flag = (np.arange(n) % 2).astype(float); X = np.column_stack([np.ones(n), rng.normal(size=n), flag])
    y = 1.0 + 0.5 * X[:, 1] + 2.0 * flag + rng.normal(0, .3, n)
    b, se = pit.cluster_ols(y, X, np.repeat(np.arange(40), 10))
    assert abs(b[-1] - 2.0) < 0.2 and se[-1] > 0
