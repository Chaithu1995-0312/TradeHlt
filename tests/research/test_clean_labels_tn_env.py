"""Unit tests for dual TradeNet + EnvelopeNet clean-label builder (GATE-L / ENV-L)."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from config_layer.crt_engine_v2 import Candle
from features.feature_schema import CANONICAL_FEATURES, SCHEMA_HASH
from research.clean_labels.builder import (
    BuildConfig,
    build_dataset,
    label_one_unit,
    write_dataset_artifacts,
)
from research.clean_labels.protocol import (
    PROTOCOL_ID,
    TP2_ATR_MULT,
    TP2_POLICY,
    compute_protocol_hash,
    freeze_block,
)


def _bar(i: int, o: float, h: float, l: float, c: float) -> Candle:
    return Candle(
        timestamp=datetime(2024, 1, 1, 0, 0) if i == 0 else datetime(2024, 1, 1, 0, 15 * i),
        open=o,
        high=h,
        low=l,
        close=c,
        volume=100.0,
        index=i,
    )


def _feats(**overrides) -> dict:
    base = {name: 0.0 for name in CANONICAL_FEATURES}
    base.update(
        {
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0,
            "atr": 1.0,
            "session": 0.0,
            "trend_bias": 0.0,
        }
    )
    base.update(overrides)
    return base


def _candles_long_tp() -> list[Candle]:
    """Entry at bar 0; subsequent bars run up through +2R then more."""
    # entry context bar
    bars = [_bar(0, 100, 100.5, 99.5, 100)]
    # bar 1: mild up
    bars.append(_bar(1, 100, 100.8, 99.9, 100.5))
    # bar 2: hit +1R and +2R (entry 100, sl 99 → risk 1; +2R = 102)
    bars.append(_bar(2, 100.5, 102.5, 100.4, 102.0))
    # bar 3: more
    bars.append(_bar(3, 102.0, 103.0, 101.5, 102.5))
    return bars


def _candles_long_sl() -> list[Candle]:
    bars = [_bar(0, 100, 100.5, 99.5, 100)]
    bars.append(_bar(1, 100, 100.2, 98.5, 98.8))  # hits SL at 99
    bars.append(_bar(2, 98.8, 99.0, 98.0, 98.5))
    return bars


def _ts_map(candles) -> dict[str, int]:
    out = {}
    for c in candles:
        ts = c.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        # also space-normalized key
        out[ts] = c.index
        out[ts.replace("T", " ")] = c.index
    # match builder's _norm_ts on opportunity timestamps
    return {k.replace("T", " ").strip(): v for k, v in out.items()}


def test_protocol_hash_stable():
    a = compute_protocol_hash({"instrument": "BNBUSDT"})
    b = compute_protocol_hash({"instrument": "BNBUSDT"})
    assert a == b
    assert len(a) == 64
    freeze = freeze_block()
    assert freeze["protocol_id"] == PROTOCOL_ID == "TN_ENV_CLEAN_L2"
    assert freeze["tp2_policy"] == TP2_POLICY == "STRETCH_3R_BEFORE_SL"
    assert TP2_ATR_MULT == 3.0
    assert "stream.outcome" in freeze["forbidden_primary_y"]


def test_label_long_tp_path():
    candles = _candles_long_tp()
    ts_to_idx = _ts_map(candles)
    # opportunity timestamp must match candle 0
    ts = candles[0].timestamp.strftime("%Y-%m-%d %H:%M:%S")
    rec = {
        "instrument": "TEST",
        "timestamp": ts,
        "direction": "long",
        "entry": 100.0,
        "sl": 99.0,
        "tp": 101.5,  # 1.5R
        "outcome": "SL_HIT",  # stream lie — clean should disagree
        "mfe": 0.1,
        "features": _feats(),
    }
    cfg = BuildConfig(instrument="TEST", source_path="test", candle_path="test")
    row, reason = label_one_unit(rec, candles, ts_to_idx, cfg)
    assert reason is None, reason
    assert row is not None
    assert row["y_tp1"] == 1.0  # path hits unit TP 101.5
    assert row["y_tp2"] == 1.0  # L2 stretch 3R (high reaches 103)
    assert row["tp2_policy"] == "STRETCH_3R_BEFORE_SL"
    assert row["tp2_stretch_r"] == 3.0
    assert row["y_survives_be"] == 1.0
    assert row["y_mfe_r"] is not None and row["y_mfe_r"] >= 1.0
    assert row["y_mae_r_heat"] is not None
    assert row["y_holding_bars"] >= 1
    assert row["provenance"]["stream_y_primary"] is False
    assert row["provenance"]["schema_hash"] == SCHEMA_HASH
    # stream diagnostic preserved but not primary
    assert row["diagnostics"]["stream_y_tp1"] == 0.0  # stream said SL_HIT


def test_tp2_stretch_harder_than_unit_tp_at_2r():
    """When unit TP is 2R, stretch 3R must be strictly harder (can disagree)."""
    # bar0 entry context; bar1 mild; bar2 hits exactly 2R (102) not 3R; bar3 SL
    bars = [
        _bar(0, 100, 100.5, 99.5, 100),
        _bar(1, 100, 100.8, 99.9, 100.5),
        _bar(2, 100.5, 102.0, 100.4, 101.8),  # hits 2R TP, not 3R
        _bar(3, 101.8, 101.9, 98.5, 99.0),
    ]
    ts_to_idx = _ts_map(bars)
    ts = bars[0].timestamp.strftime("%Y-%m-%d %H:%M:%S")
    rec = {
        "instrument": "TEST",
        "timestamp": ts,
        "direction": "long",
        "entry": 100.0,
        "sl": 99.0,
        "tp": 102.0,  # unit TP = 2R (matches BNB stream geometry)
        "outcome": "TP_HIT",
        "mfe": 2.0,
        "features": _feats(),
    }
    cfg = BuildConfig(instrument="TEST")
    row, reason = label_one_unit(rec, bars, ts_to_idx, cfg)
    assert reason is None, reason
    assert abs(row["tp1_reward_mult"] - 2.0) < 1e-9
    assert row["y_tp1"] == 1.0  # unit 2R hit
    assert row["y_tp2"] == 0.0  # stretch 3R not hit before SL/exit
    assert row["y_tp1"] != row["y_tp2"]


def test_label_long_sl_path():
    candles = _candles_long_sl()
    ts_to_idx = _ts_map(candles)
    ts = candles[0].timestamp.strftime("%Y-%m-%d %H:%M:%S")
    rec = {
        "instrument": "TEST",
        "timestamp": ts,
        "direction": "long",
        "entry": 100.0,
        "sl": 99.0,
        "tp": 102.0,
        "outcome": "TP_HIT",  # stream lie
        "mfe": 5.0,
        "features": _feats(),
    }
    cfg = BuildConfig(instrument="TEST")
    row, reason = label_one_unit(rec, candles, ts_to_idx, cfg)
    assert reason is None, reason
    assert row["y_tp1"] == 0.0
    assert row["path_outcome"] == "SL_HIT"
    assert row["diagnostics"]["stream_y_tp1"] == 1.0  # contaminated stream


def test_build_and_write(tmp_path: Path):
    candles = _candles_long_tp()
    ts_to_idx = _ts_map(candles)
    ts = candles[0].timestamp.strftime("%Y-%m-%d %H:%M:%S")
    records = [
        {
            "instrument": "TEST",
            "timestamp": ts,
            "direction": "long",
            "entry": 100.0,
            "sl": 99.0,
            "tp": 101.0,
            "outcome": "SL_HIT",
            "mfe": 0.0,
            "features": _feats(),
        }
    ]
    cfg = BuildConfig(instrument="TEST", source_path="x", candle_path="y")
    result = build_dataset(records, candles, ts_to_idx, cfg)
    assert result.n_clean == 1
    assert result.protocol_hash
    paths = write_dataset_artifacts(result, tmp_path)
    assert Path(paths["dataset"]).is_file()
    assert Path(paths["meta"]).is_file()
    assert Path(paths["rederive_report"]).is_file()
    meta = json.loads(Path(paths["meta"]).read_text(encoding="utf-8"))
    assert meta["protocol_id"] == PROTOCOL_ID
    assert meta["gate_l_checklist"]["builder_refuses_stream_primary_y"] is True
    assert meta["agreement"]["n"] == 1
    # dataset row has both TN and ENV fields
    line = Path(paths["dataset"]).read_text(encoding="utf-8").strip()
    row = json.loads(line)
    for key in ("y_tp1", "y_tp2", "y_survives_be", "y_mfe_r", "y_mae_r_heat", "y_holding_bars"):
        assert key in row


def test_skip_missing_features():
    candles = _candles_long_tp()
    ts_to_idx = _ts_map(candles)
    ts = candles[0].timestamp.strftime("%Y-%m-%d %H:%M:%S")
    rec = {
        "instrument": "TEST",
        "timestamp": ts,
        "direction": "long",
        "entry": 100.0,
        "sl": 99.0,
        "tp": 101.0,
        "features": {"open": 1.0},  # incomplete
    }
    cfg = BuildConfig(instrument="TEST")
    row, reason = label_one_unit(rec, candles, ts_to_idx, cfg)
    assert row is None
    assert reason == "bad_features"
