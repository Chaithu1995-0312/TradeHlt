"""
Pins the hour / session / day-of-week semantics after `feature_pipeline.session_timestamp_basis`
was RETIRED (CH-corpus-clock-contract-v1, 2026-10-08; originally F-066 / F-117).

History: MT5 timestamps (data/mt5/*.csv) are broker-server time labeled UTC
(`mt5_candle_fetcher.py:186`), so `session`/`hour_of_day` (FM-052) were wrong on 53.36% of XAUUSD
bars; a config switch (`broker_local` | `utc_corrected`) chose whether to convert. The conversion
now happens exactly once, at the corpus SSOT, from a configured clock; downstream reads UTC and
there is no switch. This file pins that:

  1. FM-052 `hour_of_day` / `session` derive from the canonical UTC timestamp (no conversion) and
     match the independent legacy reference (`features.broker_clock`) applied to the SOURCE stamp.
  2. `day_of_week` follows the MARKET calendar (the FX day starts 17:00 New York), not UTC.
  3. A config that still carries the retired key is refused (no silent reinterpretation).
  4. The legacy reference function is NOT a no-op on true-UTC timestamps (why it must never be
     called outside the corpus boundary) and its NY-DST offset table matches the hand walk.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
_SRC = ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from config_layer.production_config import get_prod_section  # noqa: E402
from features.feature_pipeline import FeaturePipeline  # noqa: E402
from features import broker_clock  # noqa: E402

CSV = ROOT / "data" / "mt5" / "XAUUSD_M15.csv"
ROWS = 3000  # clears warmup, keeps the floor fast


@pytest.fixture(scope="module")
def base_cfg() -> dict:
    return dict(get_prod_section("feature_pipeline"))


@pytest.fixture(scope="module")
def ssot_df() -> pd.DataFrame:
    if not CSV.is_file():
        pytest.skip(f"corpus absent: {CSV}")
    from data_ingestion.corpus_store import load
    return load(CSV, "XAUUSD", sequence_check=False).frame().head(ROWS)


def _run(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    out, _vectors = FeaturePipeline(df, cfg=cfg).run()
    return out


# ── 1: hour/session come straight from canonical UTC and match the legacy reference ───────

def test_hour_of_day_is_the_utc_hour_of_the_canonical_timestamp(ssot_df, base_cfg):
    out = _run(ssot_df, base_cfg)
    ts = pd.to_datetime(out["timestamp"])
    assert (out["hour_of_day"] == ts.dt.hour.astype(np.int8)).all()
    assert out["session"].between(0, 4).all() and out["hour_of_day"].dtype == np.int8


def test_hour_of_day_equals_legacy_conversion_of_the_source_stamp(ssot_df, base_cfg):
    """Independent reference: broker_clock applied to the SOURCE stamp gives the same hour."""
    out = _run(ssot_df, base_cfg)
    src = pd.to_datetime(out["source_timestamp"])
    legacy_utc = broker_clock.mt5_server_to_utc(src)
    assert (out["hour_of_day"] == legacy_utc.dt.hour.astype(np.int8)).all()
    # the old broker-label hour would have disagreed on a large share of bars (F-066: 53.36%)
    assert (out["hour_of_day"] != src.dt.hour.astype(np.int8)).mean() > 0.30


# ── 2: day-of-week follows the market calendar ───────────────────────────────────────────

def test_day_of_week_follows_the_market_calendar_not_utc(ssot_df, base_cfg):
    out = _run(ssot_df, base_cfg)
    src = pd.to_datetime(out["source_timestamp"])
    # fx_metals calendar wall == the broker grid, so the calendar day-of-week is the source one
    assert (out["day_of_week"] == src.dt.dayofweek.astype(np.int8)).all()
    utc_dow = pd.to_datetime(out["timestamp"]).dt.dayofweek.astype(np.int8)
    assert (out["day_of_week"] != utc_dow).any(), "a UTC-day-of-week would differ near the day boundary"


# ── 3: the retired key is refused ────────────────────────────────────────────────────────

@pytest.mark.parametrize("value", ["broker_local", "utc_corrected", "eastern_standard"])
def test_retired_key_is_refused(ssot_df, base_cfg, value):
    with pytest.raises(ValueError, match="RETIRED"):
        FeaturePipeline(ssot_df, cfg={**base_cfg, "session_timestamp_basis": value})


# ── 4a: the legacy reference is NOT a no-op on true-UTC timestamps (never call it outside the boundary) ──

def test_utc_corrected_is_not_a_noop_on_true_utc_timestamps():
    """Binance-shaped corpora carry genuinely-UTC timestamps. Applying the MT5 server-time
    correction to them is WRONG -- it must visibly shift the hour, not no-op. This is the
    regression for the scope warning in feature_pipeline.py (an earlier comment draft claimed
    the opposite and was corrected same-session)."""
    true_utc = pd.Series(pd.date_range("2025-06-15 12:00", periods=5, freq="15min"))
    shifted = broker_clock.mt5_server_to_utc(true_utc)
    assert not (shifted == true_utc).any(), (
        "mt5_server_to_utc must NOT be a no-op on already-UTC timestamps -- it has no way to "
        "detect provenance, so misapplying it (e.g. to Binance data) silently corrupts the hour"
    )
    assert (true_utc - shifted).iloc[0] == pd.Timedelta(hours=3)  # June -> NY on EDT


# ── 4b: NY-DST offset table of the legacy reference matches this session's manual walk ───────

@pytest.mark.parametrize("date_str,expected_offset", [
    ("2024-07-15", 3),   # deep summer -> EDT -> server UTC+3
    ("2024-12-15", 2),   # deep winter -> EST -> server UTC+2
    ("2025-01-06", 2),   # winter, NFP day used in the manual investigation
    ("2025-03-05", 2),   # before the 2025 US spring-forward (Mar 9)
    ("2025-03-10", 3),   # after the 2025 US spring-forward (Mar 9) -- EU is still EET this week
    ("2025-10-30", 3),   # BEFORE the 2025 US fall-back (Nov 2) -- still EDT -> offset 3. EU
                          # already fell back Oct 26, so this date IS the mismatch window the
                          # boundary census used to prove the server follows US, not EU, rules.
])
def test_ny_dst_offset_table(date_str, expected_offset):
    ts = pd.Series(pd.to_datetime([date_str + " 12:00:00"]))
    offset = broker_clock.mt5_server_offset_hours(ts)
    assert int(offset.iloc[0]) == expected_offset, (
        f"{date_str}: expected offset {expected_offset}, got {offset.iloc[0]} -- "
        "NY DST transition table drifted from the empirically-verified boundary dates"
    )
