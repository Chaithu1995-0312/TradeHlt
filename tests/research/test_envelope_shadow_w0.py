"""Tests for ENV_SHADOW_W0_V1 weight-0 shadow logger."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from research.envelope_offline.shadow import (
    SHADOW_CHARTER_ID,
    ShadowConfig,
    load_shadow_bundle,
    run_shadow,
)
from research.envelope_offline.train import (
    CHARTER_ID as TRAIN_CHARTER_ID,
    REQUIRED_PROTOCOL,
    TrainConfig,
    run_offline_train,
)


def _plant_dataset(tmp_path: Path, n: int = 600) -> Path:
    rng = np.random.default_rng(1)
    lines = []
    for i in range(n):
        vec = rng.normal(size=38).tolist()
        mfe = float(vec[0] * 2.0 + rng.normal(0, 0.2))
        lines.append(
            json.dumps(
                {
                    "unit_id": f"u{i}",
                    "decision_ts": f"2024-01-01 00:{i % 60:02d}:00",
                    "entry_index": i,
                    "side": "long" if i % 2 == 0 else "short",
                    "feature_vector": vec,
                    "y_mfe_r": mfe,
                    "y_mae_r_heat": float(abs(vec[1]) + 0.1),
                    "y_holding_bars": float(max(1.0, 4 + vec[2])),
                    "y_time_to_mfe": float(max(1.0, 2 + vec[3] * 0.5)),
                }
            )
        )
    ds = tmp_path / "clean_labels.jsonl"
    ds.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (tmp_path / "dataset_meta.json").write_text(
        json.dumps(
            {
                "protocol_id": REQUIRED_PROTOCOL,
                "protocol_hash": "test_hash",
                "pit_status": "PIT_UNCLEAN_STORED_FEATURES",
            }
        ),
        encoding="utf-8",
    )
    return ds


def test_shadow_weight_zero_and_complete(tmp_path: Path):
    ds = _plant_dataset(tmp_path)
    train_out = tmp_path / "train"
    run_offline_train(
        TrainConfig(
            dataset_path=str(ds),
            out_dir=str(train_out),
            max_depth=3,
            max_iter=30,
            min_samples_leaf=8,
        )
    )
    shadow_out = tmp_path / "shadow"
    summary = run_shadow(
        ShadowConfig(
            bundle_dir=str(train_out),
            dataset_path=str(ds),
            out_dir=str(shadow_out),
            instrument="TEST",
        )
    )
    assert summary["status"] == "SHADOW_COMPLETE"
    assert summary["weight_violations"] == 0
    assert summary["charter_id"] == SHADOW_CHARTER_ID
    n = 0
    with (shadow_out / "shadow.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            assert rec["decision_weight"] == 0.0
            assert rec["fusion_weight"] == 0.0
            assert rec["planner_influence"] is False
            assert rec["spine_consumed"] is False
            if rec.get("kind") == "envelope_shadow_w0":
                assert "pred" in rec
                n += 1
    assert n == summary["n_ok"]
    assert n >= 500


def test_refuses_bad_rollup(tmp_path: Path):
    bundle = {
        "charter_id": TRAIN_CHARTER_ID,
        "signal_rollup": "SIGNAL_FAIL",
        "head_artifacts": {},
    }
    (tmp_path / "envelope_bundle.json").write_text(json.dumps(bundle), encoding="utf-8")
    with pytest.raises(ValueError, match="signal_rollup"):
        load_shadow_bundle(tmp_path)
