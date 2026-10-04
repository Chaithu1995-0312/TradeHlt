"""v0 certify: specimen JOINT_STATE_SL_TP + unit helpers."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from research.measurement.trade_lifecycle_engine import (
    JOINT_STATES,
    Bar,
    joint_state_id,
    measure,
)


def test_joint_state_id_frozen_set():
    assert joint_state_id("SL", "TP") == "JOINT_STATE_SL_TP"
    assert joint_state_id("TP", "SL") == "JOINT_STATE_TP_SL"
    assert joint_state_id("SL", "SL") == "BOTH_SL"
    assert joint_state_id("TP", "TP") == "BOTH_TP"
    assert joint_state_id("TIMEOUT", "TIMEOUT") == "BOTH_TIMEOUT"
    assert joint_state_id("SL", "TIMEOUT") == "JOINT_STATE_SL_TIMEOUT"
    with pytest.raises(ValueError):
        joint_state_id("TP", "TIMEOUT")  # not in frozen six


def test_specimen_ac95_joint_state_sl_tp():
    root = Path(__file__).resolve().parents[2]
    csv = root / "data" / "mt5" / "XAUUSD_M15.csv"
    if not csv.exists():
        pytest.skip(f"missing {csv}")

    df = pd.read_csv(csv, parse_dates=["timestamp"])
    t0 = pd.Timestamp("2025-06-16 07:15:00")
    hits = df.index[df["timestamp"] == t0]
    assert len(hits) == 1
    i0 = int(hits[0])
    assert i0 == 25223

    fwd = df.iloc[i0 + 1 : i0 + 41]
    bars = [
        Bar(
            high=float(r.high),
            low=float(r.low),
            close=float(r.close),
            open=float(r.open),
            index=int(i),
            timestamp=r.timestamp,
        )
        for i, r in enumerate(fwd.itertuples(index=False), start=1)
    ]

    entry, sl, tp = 3430.37, 3435.1664285714282, 3420.7771428571427
    m = measure(
        entry=entry,
        sl=sl,
        tp=tp,
        side="short",
        forward_bars=bars,
        meta={"unit_id": "ac95cf287cbdfa3b"},
    )

    assert m.contract_id == "MC-JOINT-01"
    assert m.Y_scanner == "SL"
    assert m.Y_oracle == "TP"
    assert m.Y_joint == "JOINT_STATE_SL_TP"
    assert m.Y_joint in JOINT_STATES
    assert m.authority_outcome.source == "path"
    assert m.authority_outcome.path_outcome == "TP"
    assert m.exit_mechanism_scanner == "TRAIL_HIT"
    assert m.exit_mechanism_oracle == "TP_HIT"
    assert m.rr_scanner == pytest.approx(0.213, abs=1e-3)
    assert m.duration_scanner == 2
    assert m.duration_oracle == 5
    assert m.rr_oracle == pytest.approx(2.0, abs=1e-6)
    assert m.authority_outcome.y_R_net < m.rr_oracle
