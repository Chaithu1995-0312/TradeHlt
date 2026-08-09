"""
test_timing_reconstructor.py
============================
Tests for the Pattern Timing Library core (src/replay/timing_reconstructor.py).

Covers:
  - first-crossing timing on hand-computed synthetic candle paths
  - conservative same-bar tie-break (losing-stop exit suppresses favorable credit;
    a trail that has moved into profit credits it)
  - legacy outcome/rr/duration/mfe/mae parity with the documented convention
  - determinism (same inputs -> identical dict)
  - no-lookahead (timing of bar k is independent of any bar > k)
  - scanner-path vs offline re-walker agreement (shared core => identical)
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from replay.timing_reconstructor import (
    R_LEVELS,
    simulate_with_timing,
    load_candles,
    reconstruct_record,
    iter_jsonl,
)

# A LONG with entry=100, sl=90 => risk_distance=10.
#   0.25R=+2.5 (102.5)   0.5R=+5 (105)   1R=+10 (110)   tp=2R=120
#   trail_mult=0.5 => trail_dist=5
ENTRY, SL, TP, RD = 100.0, 90.0, 120.0, 10.0


def _long(bars):
    return simulate_with_timing("long", ENTRY, SL, TP, bars, RD, trail_mult=0.5)


def test_progressive_winner_first_crossings():
    # fav reaches 0.25R@1, 0.5R@2, 1R@3, then trail-stops in profit @4.
    bars = [
        (103.0, 99.0, 102.0),   # fav 0.3R -> 0.25R at step 1
        (106.0, 104.0, 105.0),  # fav 0.6R -> 0.5R at step 2; trail -> 101
        (111.0, 108.0, 110.0),  # fav 1.1R -> 1R at step 3; trail -> 106
        (112.0, 100.0, 101.0),  # trail -> 107; low 100 <= 107 -> trail exit (profit)
    ]
    r = _long(bars)
    assert r["time_to_025R"] == 1
    assert r["time_to_05R"] == 2
    assert r["time_to_1R"] == 3
    assert r["outcome"] == "SL_HIT"           # exited on the trail
    assert r["duration_candles"] == 4
    assert r["time_to_sl"] == 4
    assert r["time_to_tp"] is None
    assert r["rr_achieved"] == pytest.approx(0.7)  # (107-100)/10


def test_pure_loser_never_favorable():
    bars = [(99.0, 88.0, 89.0)]  # straight down, SL@90 hit step 1
    r = _long(bars)
    assert r["outcome"] == "SL_HIT"
    assert r["rr_achieved"] == pytest.approx(-1.0)
    assert r["time_to_025R"] is None
    assert r["time_to_05R"] is None
    assert r["time_to_1R"] is None
    assert r["time_to_sl"] == 1
    assert r["time_to_tp"] is None


def test_conservative_tiebreak_losing_stop_suppresses_credit():
    # entry=100 sl=98 (RD=2); 0.25R=100.5. One bar wicks UP to 100.6 (above 0.25R)
    # and DOWN to 97.5 (below SL); trail NOT activated (peak 100.6 < 100+1).
    # Ambiguous intra-bar order + losing stop => NO favorable credit.
    bars = [(100.6, 97.5, 98.0)]
    r = simulate_with_timing("long", 100.0, 98.0, 104.0, bars, 2.0, trail_mult=0.5)
    assert r["outcome"] == "SL_HIT"
    assert r["time_to_025R"] is None     # suppressed (conservative)
    assert r["time_to_05R"] is None


def test_trail_in_profit_credits_crossing_same_bar():
    # entry=100 sl=98 (RD=2); trail_dist=1. Bar spikes to 101.5 (fav 0.75R) then
    # low 100.5 hits the trail which has moved to 100.5 (IN PROFIT) => credit.
    bars = [(101.5, 100.5, 101.0)]
    r = simulate_with_timing("long", 100.0, 98.0, 104.0, bars, 2.0, trail_mult=0.5)
    assert r["outcome"] == "SL_HIT"
    assert r["rr_achieved"] == pytest.approx(0.25)   # trail exit at 100.5
    assert r["time_to_025R"] == 1                    # credited (trail in profit)
    assert r["time_to_05R"] == 1


def test_tp_hit_credits_all_levels():
    # Unambiguous TP: high reaches 2R, low stays above the trail (no tie).
    bars = [(121.0, 119.0, 120.5)]
    r = _long(bars)
    assert r["outcome"] == "TP_HIT"
    assert r["time_to_025R"] == 1
    assert r["time_to_05R"] == 1
    assert r["time_to_1R"] == 1
    assert r["time_to_tp"] == 1
    assert r["time_to_sl"] is None


def test_short_direction_symmetry():
    # SHORT entry=100 sl=110 (RD=10); favorable = entry - low. tp=80.
    bars = [
        (101.0, 97.0, 98.0),    # fav (100-97)/10 = 0.3R -> 0.25R step1
        (99.0, 94.0, 95.0),     # fav 0.6R -> 0.5R step2
    ]
    r = simulate_with_timing("short", 100.0, 110.0, 80.0, bars, 10.0, trail_mult=0.5)
    assert r["time_to_025R"] == 1
    assert r["time_to_05R"] == 2


def test_timeout_marks_to_last_close():
    bars = [(101.0, 99.5, 100.5), (101.5, 100.0, 101.0)]  # no TP/SL
    r = _long(bars)
    assert r["outcome"] == "TIMEOUT"
    assert r["duration_candles"] == 2
    assert r["rr_achieved"] == pytest.approx((101.0 - 100.0) / 10.0)


def test_determinism():
    bars = [(103.0, 99.0, 102.0), (106.0, 104.0, 105.0)]
    a = _long(bars)
    b = _long(list(bars))
    assert a == b


def test_no_lookahead_prefix_independence():
    # Timing of early bars must not change when later bars are appended.
    prefix = [(103.0, 99.0, 102.0), (106.0, 104.0, 105.0)]  # crosses .25@1 .5@2
    r_short = _long(prefix)
    r_long = _long(prefix + [(130.0, 100.0, 125.0)])         # later TP bar
    assert r_short["time_to_025R"] == r_long["time_to_025R"] == 1
    assert r_short["time_to_05R"] == r_long["time_to_05R"] == 2


def test_scanner_path_matches_offline_rewalker(tmp_path: Path):
    # Build a tiny CSV; an "entry" at row idx=1; offline re-walk must equal a
    # direct core call on the same forward bars.
    # volume is part of the mandatory six-column dataset contract (ohlcv_schema)
    # even though load_candles consumes only timestamp/high/low/close — a real
    # M15 source always carries it, so the fixture must too.
    rows = [
        ("2026-01-01 00:00", 100.0, 99.0, 99.5, 100.0, 1000.0),  # idx 0
        ("2026-01-01 00:15", 100.0, 99.0, 99.5, 100.0, 1000.0),  # idx 1  <- entry bar
        ("2026-01-01 00:30", 103.0, 99.0, 102.0, 100.0, 1000.0), # step 1
        ("2026-01-01 00:45", 106.0, 104.0, 105.0, 100.0, 1000.0),# step 2
        ("2026-01-01 01:00", 111.0, 108.0, 110.0, 100.0, 1000.0),# step 3
    ]
    csv_path = tmp_path / "X_M15.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "high", "low", "close", "open", "volume"])
        for ts, hi, lo, cl, op, vol in rows:
            w.writerow([ts, hi, lo, cl, op, vol])

    ts, highs, lows, closes = load_candles(csv_path)
    idx = {t: i for i, t in enumerate(ts)}
    record = {"timestamp": "2026-01-01 00:15", "instrument": "X",
              "direction": "long", "entry": 100.0, "sl": 90.0, "tp": 120.0}

    offline = reconstruct_record(record, highs, lows, closes, idx,
                                 max_forward_candles=40, trail_mult=0.5)
    # Direct core call on the same forward bars (rows after entry idx=1).
    bars = [(rows[i][1], rows[i][2], rows[i][3]) for i in range(2, len(rows))]
    direct = simulate_with_timing("long", 100.0, 90.0, 120.0, bars, 10.0, 0.5)
    assert offline == direct
    assert offline["time_to_025R"] == 1
    assert offline["time_to_05R"] == 2
    assert offline["time_to_1R"] == 3


def test_load_candles_rejects_volume_less_ohlc(tmp_path: Path):
    # Regression: load_candles consumes only timestamp/high/low/close, but it
    # deliberately enforces the full six-column OHLCV dataset contract
    # (ohlcv_schema.require_ohlcv_columns) — a real M15 source always carries
    # volume. A volume-less CSV must fail fast, not be silently tolerated.
    csv_path = tmp_path / "NOVOL_M15.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "high", "low", "close", "open"])
        w.writerow(["2026-01-01 00:00", 100.0, 99.0, 99.5, 100.0])
    with pytest.raises(ValueError, match="missing required columns: volume"):
        load_candles(csv_path)


def test_iter_jsonl_skips_run_header(tmp_path: Path):
    p = tmp_path / "opportunities.jsonl"
    with p.open("w", encoding="utf-8") as f:
        f.write(json.dumps({"type": "run_header", "run_id": "x"}) + "\n")
        f.write(json.dumps({"timestamp": "t", "entry": 1.0}) + "\n")
        f.write("not-json\n")  # malformed -> skipped
        f.write(json.dumps({"timestamp": "t2", "entry": 2.0}) + "\n")
    recs = list(iter_jsonl(p))
    assert len(recs) == 2
    assert recs[0]["timestamp"] == "t"
    assert recs[1]["timestamp"] == "t2"


def test_r_levels_constant():
    assert R_LEVELS == (0.25, 0.5, 1.0)


# ── TimingAdvisor (consumer contract, dormant weight-0.0) ──────────────────
from replay.timing_advisor import (  # noqa: E402
    TimingAdvisor, cluster_key, cluster_key_from_features, geometry_bucket,
)


def _toy_library():
    return {
        "schema": "pattern_timing_v1",
        "cells": {
            "dir=long|sess=0|vreg=1|geo=body_mid": {
                "n": 1000, "win_rate": 0.66, "expectancy_per_candle": 0.20,
                "winrate_decay_on_025R": {
                    "1": {"win_rate_if_not_by_k": 0.33, "win_rate_if_by_k": 0.86},
                    "3": {"win_rate_if_not_by_k": 0.10, "win_rate_if_by_k": 0.86},
                },
            },
            "dir=short|sess=2|vreg=0|geo=body_hi": {
                "n": 800, "win_rate": 0.55, "expectancy_per_candle": -0.05,
                "winrate_decay_on_025R": {
                    "1": {"win_rate_if_not_by_k": 0.40, "win_rate_if_by_k": 0.70},
                    "3": {"win_rate_if_not_by_k": 0.20, "win_rate_if_by_k": 0.70},
                },
            },
        },
    }


def test_geometry_bucket_and_key():
    assert geometry_bucket({"body_ratio": 0.1}) == "body_lo"
    assert geometry_bucket({"body_ratio": 0.5}) == "body_mid"
    assert geometry_bucket({"body_ratio": 0.9}) == "body_hi"
    assert cluster_key("long", 0, 1, "body_mid") == "dir=long|sess=0|vreg=1|geo=body_mid"
    k = cluster_key_from_features("long", {"session": 0.0, "volatility_regime": 1.0,
                                           "body_ratio": 0.5})
    assert k == "dir=long|sess=0|vreg=1|geo=body_mid"


def test_advisor_rank_score_normalized_and_neutral():
    adv = TimingAdvisor(_toy_library())
    assert adv.loaded
    # Highest epc -> 1.0, lowest -> 0.0
    assert adv.rank_score("dir=long|sess=0|vreg=1|geo=body_mid") == 1.0
    assert adv.rank_score("dir=short|sess=2|vreg=0|geo=body_hi") == 0.0
    # Unknown cluster -> neutral 0.0
    assert adv.rank_score("dir=long|sess=9|vreg=9|geo=body_lo") == 0.0


def test_advisor_abnormality_flags_late_trade():
    adv = TimingAdvisor(_toy_library())
    key = "dir=long|sess=0|vreg=1|geo=body_mid"
    # Not reached +0.25R by candle 3 -> conditional win 0.10 < floor -> ABNORMAL
    a = adv.abnormality(key, candles_since_entry=3, reached_025R=False)
    assert a["advisory"] == "ABNORMAL"
    assert a["flag_abnormal"] is True
    assert a["conditional_win_rate"] == 0.10
    assert a["weight"] == 0.0 and a["enabled"] is False     # dormant
    # Already reached -> not flagged
    b = adv.abnormality(key, candles_since_entry=3, reached_025R=True)
    assert b["flag_abnormal"] is False


def test_advisor_failopen_neutral_on_missing_file(tmp_path: Path):
    adv = TimingAdvisor.from_path(tmp_path / "does_not_exist.json")
    assert adv.loaded is False
    assert adv.rank_score("anything") == 0.0
    out = adv.abnormality("anything", 5, False)
    assert out["advisory"] == "NEUTRAL" and out["enabled"] is False
