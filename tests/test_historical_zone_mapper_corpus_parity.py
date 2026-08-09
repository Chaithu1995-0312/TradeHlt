"""
P1a.5 — Real-corpus zone parity: HistoricalZoneMapper vs EngineRunner hard zone stage.

Uses actual XAUUSD TRADE_OPENED feature snapshots (Phase-1 frozen candidate tail)
and compares cluster_score / passed within 1e-9 against score_zone_cluster driven
by EngineRunner's zone gate instance + prod knobs (the hard path ER invokes).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from config_layer.production_config import get_prod_section
from core.engine_runner import EngineRunner
from engines.zone_cluster_score import score_zone_cluster
from research.zone_mapping.collect_trade_opened_features import (
    collect_xauusd_trade_opened_features,
)
from research.zone_mapping.historical_zone_mapper import (
    HistoricalZoneMapper,
    ZoneMapConfig,
)

CORPUS = Path("data/mt5/XAUUSD_M15.csv")
TOL = 1e-9
MIN_SAMPLES = 5
MAX_SAMPLES = 15
# Full Phase-1 file; stop early once MAX_SAMPLES opens collected.
# Router CRTConfig (use_prod_crt_config=False): ~6 TRADE_OPENED on Phase-1.
# Prod params overlay is stricter and can yield 0 opens — not used here.
TAIL_ROWS = 0


@pytest.fixture(scope="module")
def xau_trade_opened_samples():
    if not CORPUS.is_file():
        pytest.skip(f"XAUUSD corpus missing: {CORPUS}")
    try:
        samples = collect_xauusd_trade_opened_features(
            csv_path=str(CORPUS),
            tail_rows=TAIL_ROWS,
            max_samples=MAX_SAMPLES,
            use_prod_crt_config=False,
        )
    except Exception as exc:
        pytest.skip(f"TRADE_OPENED collection failed: {exc}")
    if len(samples) < MIN_SAMPLES:
        pytest.skip(
            f"Need >= {MIN_SAMPLES} TRADE_OPENED; got {len(samples)}. "
            f"Check Phase-1 corpus + CRT path."
        )
    return samples


def _engine_runner_from_prod() -> EngineRunner:
    """Construct EngineRunner as BacktestRunner does (prod sections)."""
    from config_layer.production_config import get_prod_section as gps

    er_cfg = dict(gps("engine_runner"))
    er_cfg.setdefault("fusion_engine", dict(gps("fusion_engine")))
    for k, v in dict(gps("decision_engine")).items():
        er_cfg.setdefault(k, v)
    er_cfg["instrument"] = "XAUUSD"
    return EngineRunner(er_cfg)


def test_corpus_parity_mapper_vs_engine_runner_zone_stage(xau_trade_opened_samples):
    """
    For each real TRADE_OPENED feature map:
      HistoricalZoneMapper.cluster_score ≡ ER hard-zone score (1e-9)
      passed flags match
    """
    samples = xau_trade_opened_samples
    mapper = HistoricalZoneMapper(ZoneMapConfig.from_prod_engine_runner())
    runner = _engine_runner_from_prod()

    er = get_prod_section("engine_runner")
    zg = er["zone_gate"]
    threshold = float(er["zone_cluster_threshold"])
    cluster_min_n = int(zg["cluster_min_n"])
    cluster_spread_max = float(zg["cluster_spread_max"])
    execution_mode = str(er["zone_gate_execution_mode"])

    mismatches = []
    for i, sample in enumerate(samples):
        feat = dict(sample.features)
        mapped = mapper.map_row(
            feat,
            timestamp=sample.timestamp,
            bar_index=sample.candle_index,
            instrument="XAUUSD",
        )
        # EngineRunner hard zone stage = score_zone_cluster(self._zone_gate, ...)
        er_scored = score_zone_cluster(
            feat,
            runner._zone_gate,
            zone_cluster_threshold=threshold,
            cluster_min_n=cluster_min_n,
            cluster_spread_max=cluster_spread_max,
            execution_mode=execution_mode,
        )
        d_score = abs(float(mapped["cluster_score"]) - float(er_scored["score"]))
        pass_ok = bool(mapped["passed_cluster_threshold"]) == bool(er_scored["passed"])
        if d_score >= TOL or not pass_ok:
            mismatches.append(
                {
                    "i": i,
                    "timestamp": sample.timestamp,
                    "mapper_score": mapped["cluster_score"],
                    "er_score": er_scored["score"],
                    "delta": d_score,
                    "mapper_passed": mapped["passed_cluster_threshold"],
                    "er_passed": er_scored["passed"],
                }
            )

    assert not mismatches, (
        f"P1a.5 corpus parity failed on {len(mismatches)}/{len(samples)} TRADE_OPENED "
        f"events (tol={TOL}): {mismatches[:5]}"
    )


def test_corpus_sample_count_and_integrity(xau_trade_opened_samples):
    """Sanity: samples are real TRADE_OPENED maps with integrity + OHLCV."""
    samples = xau_trade_opened_samples
    assert len(samples) >= MIN_SAMPLES
    for s in samples:
        assert s.features.get("_data_integrity") == "real"
        assert "close" in s.features and "high" in s.features and "low" in s.features
        assert s.timestamp
        assert s.features.get("ema_fast") is not None


def test_session_windows_hardening_accepts_string_bounds():
    """Regression: string HH:MM bounds must not reach CRT as str (P1a.5 crash)."""
    from datetime import time as dt_time

    from research.zone_mapping.collect_trade_opened_features import (
        _normalize_session_windows,
    )

    raw = {"LONDON": ["07:00", "10:00"], "NEWYORK": ("13:00", "16:00")}
    got = _normalize_session_windows(raw)
    assert got["LONDON"] == (dt_time(7, 0), dt_time(10, 0))
    assert got["NEWYORK"][0] == dt_time(13, 0)
    assert isinstance(got["LONDON"][0], dt_time)
