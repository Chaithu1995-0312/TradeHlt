"""Floors for `features.resolver_supply` -- the producer-side supply contract.

The defect this module closes: `CRTStateResolver.resolve()` classifies EVERY key
the caller passes and `.update()`s the result over `classify()`'s output, so
`feature_states` is a function of what the caller happened to supply. Two callers
taking different slices of the same `FeaturePipeline.run()` return produced two
occupancy series differing by 17,563 RANGE bars.

These tests pin the contract, not the outcome:
  * canonical names are sourced from `vectors`, never from a same-named
    enriched column
  * exactly the non-vector `when:`-named features come from `enriched`
  * nothing else is passed (this is what defuses the overwrite loop)
  * a fabricated/absent non-vector feature fails closed rather than
    manufacturing a confident state
  * the NaN policy is explicit and recorded, never silent
  * the fingerprint changes iff the supply construction changes
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from features.crt_state_resolver import CRTStateResolver  # noqa: E402
from features.feature_schema import CANONICAL_FEATURES  # noqa: E402
from features.resolver_supply import (  # noqa: E402
    SUPPLY_SET_ID,
    ResolverSupplyError,
    build_supply_rows,
    plan_supply,
)


@pytest.fixture(scope="module")
def resolver():
    return CRTStateResolver()


def _enriched(n: int = 4, **extra) -> pd.DataFrame:
    """An enriched frame shaped like FeaturePipeline's: canonical columns PLUS
    the non-vector intermediates PLUS base-layer noise."""
    data = {name: np.arange(n, dtype=float) + 1.0 for name in CANONICAL_FEATURES}
    data.update({
        "retest_flag": np.zeros(n),
        "displacement_flag": np.zeros(n),
        "rsi_state": np.zeros(n),
        "ma_20": np.full(n, 999.0),      # base-layer intermediate
        "_pos": np.arange(n),
        "timestamp": pd.date_range("2026-01-05", periods=n, freq="15min"),
    })
    data.update(extra)
    return pd.DataFrame(data)


def _vectors(df: pd.DataFrame) -> np.ndarray:
    return df[list(CANONICAL_FEATURES)].astype(np.float32).values


# ------------------------------------------------------------------- plan ---

def test_plan_sources_canonical_from_vector_and_only_nonvector_from_enriched(resolver):
    df = _enriched()
    plan = plan_supply(resolver, df.columns)
    assert plan.from_vector == tuple(CANONICAL_FEATURES)
    # every `when:`-named feature that is not canonical, and nothing more
    required = set(resolver.required_when_features)
    assert set(plan.from_enriched) == required - set(CANONICAL_FEATURES)
    assert set(plan.from_enriched).isdisjoint(CANONICAL_FEATURES)


def test_nothing_beyond_the_contract_is_passed(resolver):
    """The load-bearing assertion. `resolve()` classifies every supplied key and
    overwrites `classify()`'s output, so extra keys are not inert."""
    df = _enriched()
    plan = plan_supply(resolver, df.columns)
    leaked = {"ma_20", "_pos", "timestamp"} & set(plan.keys)
    assert leaked == set(), f"caller-dependent keys leaked into the supply: {leaked}"


def test_missing_nonvector_feature_fails_closed(resolver):
    """Previously an absent flag made the predicate silently return False, so a
    state simply never fired and the run looked clean."""
    df = _enriched().drop(columns=["rsi_state"])
    with pytest.raises(ResolverSupplyError, match="rsi_state"):
        plan_supply(resolver, df.columns)


def test_rejects_unknown_nan_policy(resolver):
    with pytest.raises(ResolverSupplyError):
        plan_supply(resolver, _enriched().columns, nan_policy="whatever")


# ------------------------------------------------------------------ rows ----

def test_canonical_values_come_from_the_vector_not_the_frame(resolver):
    """If a canonical name were read from `enriched`, poisoning that column would
    change the supply. It must not."""
    df = _enriched()
    vecs = _vectors(df)
    df["close"] = -12345.0                      # poison AFTER the vector is built
    rows, _stats = build_supply_rows(df, vecs, plan_supply(resolver, df.columns))
    assert rows[0]["close"] == pytest.approx(1.0)
    assert rows[0]["close"] != -12345.0


def test_nan_propagates_by_default_and_is_counted(resolver):
    """Coercing NaN to 0.0 turns 'no evidence' into a confident `NoRetest`."""
    df = _enriched()
    df.loc[0, "retest_flag"] = np.nan
    rows, stats = build_supply_rows(df, _vectors(df), plan_supply(resolver, df.columns))
    assert np.isnan(rows[0]["retest_flag"])
    assert stats["nan_counts"]["retest_flag"] == 1
    assert stats["nan_policy"] == "propagate"


def test_legacy_zero_coercion_must_be_asked_for_by_name(resolver):
    df = _enriched()
    df.loc[0, "retest_flag"] = np.nan
    plan = plan_supply(resolver, df.columns, nan_policy="zero")
    rows, stats = build_supply_rows(df, _vectors(df), plan)
    assert rows[0]["retest_flag"] == 0.0
    assert stats["nan_counts"]["retest_flag"] == 1   # still counted, never silent


def test_length_mismatch_fails_closed(resolver):
    df = _enriched(4)
    with pytest.raises(ResolverSupplyError, match="length mismatch"):
        build_supply_rows(df, _vectors(df)[:2], plan_supply(resolver, df.columns))


def test_supply_is_accepted_by_the_resolvers_own_contract(resolver):
    """End-to-end: the produced dict must satisfy the consumer's published
    `required_when_features`, which `resolve()` enforces."""
    df = _enriched()
    rows, _ = build_supply_rows(df, _vectors(df), plan_supply(resolver, df.columns))
    missing = set(resolver.required_when_features) - rows[0].keys()
    assert missing == set()


# ----------------------------------------------------------- fingerprint ---

def test_fingerprint_is_stable_and_policy_sensitive(resolver):
    df = _enriched()
    a = plan_supply(resolver, df.columns)
    b = plan_supply(resolver, df.columns)
    c = plan_supply(resolver, df.columns, nan_policy="zero")
    assert a.fingerprint == b.fingerprint
    assert a.fingerprint != c.fingerprint, "a different construction must not reuse the id"
    assert a.supply_set_id == SUPPLY_SET_ID
    assert len(a.fingerprint) == 64


def test_extra_enriched_columns_do_not_move_the_fingerprint(resolver):
    """Adding a base-layer column to the frame must not change the supply set --
    that independence is exactly what was missing before."""
    a = plan_supply(resolver, _enriched().columns)
    b = plan_supply(resolver, _enriched(extra_noise=np.zeros(4)).columns)
    assert a.fingerprint == b.fingerprint
