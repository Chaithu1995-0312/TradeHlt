"""Ontology-authoritative floor for FM-051 hour_of_day and FM-052 session.

Purely additive. Reads expected session ordinals / names from
configs/formulas/market_ontology.yaml (structural_states / temporal_context),
never hardcodes the ordinal table beyond what the ontology declares.

No fallbacks: hours outside every configured window must map to CLOSED (value
from ontology), not a silent default. Missing ontology keys raise.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from features.feature_pipeline import FeaturePipeline
from features.registry import load_ontology
from features import session_classifier as sc
from config_layer.production_config import get_prod_section


# ── ontology helpers (no defaults) ───────────────────────────────────────────

def _temporal_entry(name: str) -> dict:
    ont = load_ontology()
    if "temporal_context" not in ont:
        raise KeyError("ontology missing temporal_context section")
    section = ont["temporal_context"]
    if name not in section:
        raise KeyError(f"ontology temporal_context missing {name!r}")
    return section[name]


def _session_state_map() -> dict[str, int]:
    """name -> value from ontology states (ASIA=0, …). Empty states = fail."""
    entry = _temporal_entry("session")
    states = entry["states"]
    if not states:
        raise AssertionError("FM-052 session declares empty states — cannot validate")
    out: dict[str, int] = {}
    for s in states:
        if "name" not in s or "value" not in s:
            raise KeyError(f"session state missing name/value: {s!r}")
        out[s["name"]] = int(s["value"])
    return out


def _session_windows_utc() -> dict:
    """Strict production config — missing key raises (no silent defaults)."""
    fp = get_prod_section("feature_pipeline")
    if "session_windows_utc" not in fp:
        raise KeyError("feature_pipeline.session_windows_utc missing from production config")
    return fp["session_windows_utc"]


def _one_bar_per_hour() -> pd.DataFrame:
    """24 bars: hour 0..23 on a single UTC day (enough for context features only)."""
    base = datetime(2024, 6, 3, 0, 0, 0)  # Monday, mid-year UTC
    rows = []
    for h in range(24):
        ts = base + timedelta(hours=h)
        # flat valid OHLCV — temporal features ignore price levels
        rows.append(
            dict(
                timestamp=ts,
                open=100.0,
                high=100.5,
                low=99.5,
                close=100.0,
                volume=1000.0,
            )
        )
    return pd.DataFrame(rows)


def _context_only(df: pd.DataFrame) -> pd.DataFrame:
    """Run only compute_context (hour_of_day + session) — no finalize drop."""
    fp = FeaturePipeline(df)
    fp.compute_context()
    return fp.df


# ── FM-051 hour_of_day ───────────────────────────────────────────────────────

def test_hour_of_day_is_timestamp_hour():
    """Ontology formula: timestamp.dt.hour -> int8."""
    entry = _temporal_entry("hour_of_day")
    assert entry["id"] == "FM-051"
    assert "lifecycle" in entry  # no silent lifecycle omission

    df = _one_bar_per_hour()
    out = _context_only(df)

    expected = pd.to_datetime(df["timestamp"]).dt.hour.astype(np.int8)
    got = out["hour_of_day"].astype(np.int8)
    assert list(got) == list(expected)
    assert list(got) == list(range(24))


def test_hour_of_day_bounds_from_ontology():
    entry = _temporal_entry("hour_of_day")
    bounds = entry["bounds"]
    assert bounds == "[0, 23]"
    df = _one_bar_per_hour()
    out = _context_only(df)
    assert out["hour_of_day"].min() == 0
    assert out["hour_of_day"].max() == 23


# ── FM-052 session ───────────────────────────────────────────────────────────

def test_session_states_match_ontology_ordinals():
    """Every ontology state name/value must equal SessionOrdinal."""
    state_map = _session_state_map()
    for name, value in state_map.items():
        assert name in sc.SESSION_NAME_TO_ORDINAL, f"ontology state {name} not in classifier"
        assert sc.SESSION_NAME_TO_ORDINAL[name] == value
        assert int(sc.SessionOrdinal[name]) == value


def test_every_hour_maps_to_ontology_session():
    """Pipeline session column equals session_classifier on each hour.

    Outside all windows → CLOSED (ontology value), never a silent invent.
    """
    state_map = _session_state_map()
    closed_val = state_map["CLOSED"]
    windows = _session_windows_utc()
    cfg = {"session_windows_utc": windows}

    df = _one_bar_per_hour()
    out = _context_only(df)

    for _, row in out.iterrows():
        h = int(row["hour_of_day"])
        expected = sc.classify_session_feature(h, cfg)
        assert int(row["session"]) == expected
        # domain membership
        assert int(row["session"]) in set(state_map.values())

    # Explicit CLOSED proof for hours outside every window
    covered: set[int] = set()
    for name in ("ASIA", "LONDON", "NEWYORK"):
        start, end = windows[name]
        covered.update(range(int(start), int(end)))
    outside = [h for h in range(24) if h not in covered]
    assert outside, "test setup broken: no hour outside windows (cannot prove CLOSED)"
    for h in outside:
        assert sc.classify_session_feature(h, cfg) == closed_val
        row = out.loc[out["hour_of_day"] == h].iloc[0]
        assert int(row["session"]) == closed_val


def test_session_all_five_ontology_states_reachable():
    state_map = _session_state_map()
    windows = _session_windows_utc()
    cfg = {"session_windows_utc": windows}
    seen = {
        sc.decode_session_ordinal(sc.classify_session_feature(h, cfg))
        for h in range(24)
    }
    assert seen == set(state_map.keys())


def test_pipeline_full_run_preserves_temporal_context():
    """Full pipeline.run() still emits hour_of_day / session matching classifier."""
    # Need enough bars for finalize warmup; stamp hours cycle 0..23
    n = 600
    base = datetime(2024, 6, 3, 0, 0, 0)
    rng = np.random.default_rng(0)
    close = 100 + np.cumsum(rng.normal(0, 0.2, n))
    open_ = close + rng.normal(0, 0.05, n)
    high = np.maximum(open_, close) + rng.uniform(0.05, 0.5, n)
    low = np.minimum(open_, close) - rng.uniform(0.05, 0.5, n)
    ts = [base + timedelta(minutes=15 * i) for i in range(n)]
    df = pd.DataFrame(
        {
            "timestamp": ts,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": rng.uniform(100, 2000, n),
        }
    )
    windows = _session_windows_utc()
    cfg = {"session_windows_utc": windows}

    piped, _ = FeaturePipeline(df).run()
    assert "hour_of_day" in piped.columns
    assert "session" in piped.columns

    hours = pd.to_datetime(piped["timestamp"]).dt.hour.astype(int)
    assert list(piped["hour_of_day"].astype(int)) == list(hours)

    for h, sess in zip(hours, piped["session"].astype(int)):
        assert sess == sc.classify_session_feature(int(h), cfg)
