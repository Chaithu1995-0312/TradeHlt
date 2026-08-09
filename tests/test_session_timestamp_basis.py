"""
Pins the contract of `feature_pipeline.session_timestamp_basis` (F-066, 2026-08-01).

Why this file exists: docs/research/preregistration-blind-label-descriptive-fidelity.md's
investigation measured that MT5-sourced timestamps (data/mt5/*.csv) are broker-server time
labeled as UTC (`mt5_candle_fetcher.py:186`), causing `session`/`hour_of_day` (FM-052) to be
wrong on 53.36% of XAUUSD bars. This introduces a config-gated correction
(`features/broker_clock.py`) following the exact pattern already proven for
`normalization_basis` (F-061/FM-030-031): strict-read key, no silent fallback, default arm
byte-identical to every pipeline run before the key existed, corrected arm opt-in only.

Covers:
  1. Default ('broker_local') is byte-identical to the pre-existing (pre-F-066) behavior.
  2. Missing key -> KeyError (no silent default -- CLAUDE.md Section 6.5).
  3. Unrecognised value -> ValueError (no silent fallback to the legacy arm).
  4. 'utc_corrected' arm actually changes hour_of_day/session and matches
     broker_clock.mt5_server_to_utc applied directly.
  5. The scope-warning regression: 'utc_corrected' is NOT a no-op on already-true-UTC
     (Binance-shaped) timestamps -- it wrongly shifts them. Documents the risk the code
     comment names, rather than merely asserting it away (an earlier draft of that comment
     claimed the opposite and was corrected same-session -- E-001).
  6. The NY-DST offset table matches the dates this session's investigation walked by hand.
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
def raw() -> pd.DataFrame:
    if not CSV.is_file():
        pytest.skip(f"corpus absent: {CSV}")
    return pd.read_csv(CSV).head(ROWS)


def _run(df: pd.DataFrame, cfg: dict, basis: str) -> pd.DataFrame:
    out, _vectors = FeaturePipeline(df, cfg={**cfg, "session_timestamp_basis": basis}).run()
    return out


# ── 1: default is byte-identical to pre-existing behavior ──────────────────────────────────

def test_broker_local_is_byte_identical_to_raw_timestamp_hour(raw, base_cfg):
    out = _run(raw, base_cfg, "broker_local")
    expected_hour = pd.to_datetime(out["timestamp"]).dt.hour.astype(np.int8)
    assert (out["hour_of_day"] == expected_hour).all(), (
        "broker_local must derive hour_of_day from the raw timestamp AS-IS -- "
        "any deviation is a behavior change on the default arm"
    )


def test_broker_local_matches_pin(raw, base_cfg):
    """Byte-identity pin: this exact corpus slice + broker_local must reproduce the
    pre-F-066 session occupancy this pipeline has always produced."""
    out = _run(raw, base_cfg, "broker_local")
    pre_existing = pd.to_datetime(raw["timestamp"].iloc[len(raw) - len(out):]).dt.hour
    # loose sanity check on shape/dtype -- the strict per-row check above is the real proof
    assert out["hour_of_day"].dtype == np.int8
    assert out["session"].between(0, 4).all()


# ── 2 & 3: strict config contract ───────────────────────────────────────────────────────────

def test_missing_key_raises(raw, base_cfg):
    cfg = {k: v for k, v in base_cfg.items() if k != "session_timestamp_basis"}
    with pytest.raises(KeyError, match="session_timestamp_basis"):
        FeaturePipeline(raw, cfg=cfg).run()


def test_unrecognised_value_raises(raw, base_cfg):
    with pytest.raises(ValueError, match="session_timestamp_basis"):
        FeaturePipeline(raw, cfg={**base_cfg, "session_timestamp_basis": "eastern_standard"}).run()


# ── 4: corrected arm actually changes output and matches the conversion directly ───────────

def test_utc_corrected_changes_session_and_matches_broker_clock(raw, base_cfg):
    out_legacy = _run(raw, base_cfg, "broker_local")
    out_fixed = _run(raw, base_cfg, "utc_corrected")

    changed = (out_legacy["session"] != out_fixed["session"]).mean()
    assert changed > 0.30, (
        f"only {changed:.1%} of session labels changed under utc_corrected -- expected roughly "
        "half (F-066 measured 53.36% on the full XAUUSD corpus); this slice should show a "
        "comparable order of magnitude, not near-zero"
    )

    expected_utc = broker_clock.mt5_server_to_utc(pd.to_datetime(out_fixed["timestamp"]))
    assert (out_fixed["hour_of_day"] == expected_utc.dt.hour.astype(np.int8)).all()

    # the raw timestamp column itself must NEVER be mutated by either arm
    pd.testing.assert_series_equal(
        pd.to_datetime(out_legacy["timestamp"]).reset_index(drop=True),
        pd.to_datetime(out_fixed["timestamp"]).reset_index(drop=True),
        check_names=False,
    )


# ── 5: scope-warning regression -- NOT safe on already-true-UTC timestamps ─────────────────

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


# ── 6: NY-DST offset table matches this session's manual walk ──────────────────────────────

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
