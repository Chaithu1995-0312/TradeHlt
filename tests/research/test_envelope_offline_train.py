"""Unit tests for ENV_OFFLINE_TRAIN_V1 (synthetic, no full corpus)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from features.feature_schema import CANONICAL_FEATURES
from research.envelope_offline.train import (
    CHARTER_ID,
    REQUIRED_PROTOCOL,
    TrainConfig,
    run_offline_train,
    time_split,
)


def test_time_split_ordered():
    ei = np.arange(500, dtype=float)
    rng = np.random.default_rng(0)
    rng.shuffle(ei)
    tr, va, te = time_split(ei, 0.6, 0.2)
    assert len(tr) + len(va) + len(te) == len(ei)
    # contiguous in sorted time order: max train time <= min val time <= max val <= min test
    assert ei[tr].max() <= ei[va].min()
    assert ei[va].max() <= ei[te].min()
    assert set(tr).isdisjoint(set(va))
    assert set(tr).isdisjoint(set(te))


def test_refuses_wrong_protocol(tmp_path: Path):
    ds = tmp_path / "clean_labels.jsonl"
    # one row
    vec = [0.0] * 38
    row = {
        "feature_vector": vec,
        "entry_index": 0,
        "side": "long",
        "y_mfe_r": 1.0,
        "y_mae_r_heat": 1.0,
        "y_holding_bars": 2.0,
        "y_time_to_mfe": 1.0,
    }
    ds.write_text(json.dumps(row) + "\n", encoding="utf-8")
    (tmp_path / "dataset_meta.json").write_text(
        json.dumps({"protocol_id": "TN_ENV_CLEAN_L1"}), encoding="utf-8"
    )
    cfg = TrainConfig(dataset_path=str(ds), out_dir=str(tmp_path / "out"))
    with pytest.raises(ValueError, match="TN_ENV_CLEAN_L2"):
        run_offline_train(cfg)


def test_train_synthetic_signal(tmp_path: Path):
    """y_mfe_r = f0 + noise so IC should be positive on test if enough rows."""
    rng = np.random.default_rng(0)
    n = 800
    lines = []
    for i in range(n):
        vec = rng.normal(size=38).tolist()
        # plant signal in feature 0
        mfe = float(vec[0] * 2.0 + rng.normal(0, 0.3))
        mae = float(abs(vec[1]) + rng.normal(0, 0.2))
        hold = float(max(1.0, 5.0 + vec[2] * 3.0 + rng.normal(0, 0.5)))
        ttm = float(max(1.0, 2.0 + vec[3] + rng.normal(0, 0.4)))
        lines.append(
            json.dumps(
                {
                    "feature_vector": vec,
                    "entry_index": i,
                    "side": "long" if i % 2 == 0 else "short",
                    "y_mfe_r": mfe,
                    "y_mae_r_heat": mae,
                    "y_holding_bars": hold,
                    "y_time_to_mfe": ttm,
                }
            )
        )
    ds = tmp_path / "clean_labels.jsonl"
    ds.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (tmp_path / "dataset_meta.json").write_text(
        json.dumps(
            {
                "protocol_id": REQUIRED_PROTOCOL,
                "protocol_hash": "test",
                "pit_status": "PIT_UNCLEAN_STORED_FEATURES",
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "out"
    cfg = TrainConfig(
        dataset_path=str(ds),
        out_dir=str(out),
        max_depth=3,
        max_iter=40,
        min_samples_leaf=10,
    )
    bundle = run_offline_train(cfg)
    assert bundle["charter_id"] == CHARTER_ID
    assert bundle["status"] == "TRAIN_COMPLETE"
    assert (out / "envelope_bundle.json").is_file()
    assert (out / "head_mfe_r.joblib").is_file()
    # planted signal should retain some rank correlation on mfe
    assert bundle["heads"]["mfe_r"]["test_ic"] is not None
    assert bundle["heads"]["mfe_r"]["test_ic"] > 0.3
