"""
R2.5 kill-test harness unit tests.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from bitnet.contract_c_trainer import TrainerConfig
from bitnet.r25_kill_test import (
    R25Config,
    R25_THRESHOLDS,
    expected_calibration_error,
    run_r25_kill_test,
    write_r25_report,
)


def _small_trainer(**kw) -> TrainerConfig:
    base = dict(
        epochs=20,
        lr=0.05,
        hidden_dim=12,
        latent_dim=6,
        n_residual_blocks=0,
        batch_size=16,
        seed=0,
        holdout_fraction=0.25,
    )
    base.update(kw)
    return TrainerConfig(**base)


def test_ece_perfect_and_worst():
    y = np.array([0.0, 0.0, 1.0, 1.0])
    perfect = np.array([0.0, 0.0, 1.0, 1.0])
    assert expected_calibration_error(y, perfect) == pytest.approx(0.0, abs=1e-6)
    bad = np.array([1.0, 1.0, 0.0, 0.0])
    assert expected_calibration_error(y, bad) > 0.4


def test_r25_strong_signal_earns_pass(tmp_path: Path):
    cfg = R25Config(
        trainer=_small_trainer(),
        n_seeds=2,
        synthetic=True,
        synthetic_n=300,
        synthetic_signal="strong",
        out_dir=str(tmp_path),
        run_name="strong_pass",
    )
    report = run_r25_kill_test(cfg)
    path = write_r25_report(report, tmp_path, "strong_pass")
    assert path.exists()
    assert report["stage"] == "R2.5"
    assert report["threshold_version"]
    ids = {t["id"] for t in report["tests"]}
    assert "label_shuffle_kill" in ids
    assert "constant_feature_kill" in ids
    # Strong synthetic should survive kill suite
    assert report["pass"] is True, json.dumps(report["tests"], indent=2)
    assert report["status"] == "PASS_EARN_R3"
    for t in report["tests"]:
        if t.get("kill_test"):
            assert t["pass"] is True


def test_r25_no_signal_overall_does_not_earn_r3(tmp_path: Path):
    """No real signal → suite must not PASS_EARN_R3 (usually holdout_gt_random fails)."""
    cfg = R25Config(
        trainer=_small_trainer(epochs=12, lr=0.03, seed=3),
        n_seeds=2,
        synthetic=True,
        synthetic_n=500,
        synthetic_signal="none",
        out_dir=str(tmp_path),
        run_name="no_signal",
    )
    report = run_r25_kill_test(cfg)
    by_id = {t["id"]: t for t in report["tests"]}
    # Constant features must not invent ranking skill
    assert by_id["constant_feature_kill"]["pass"] is True
    # Overall must not authorize R3 on pure noise
    assert report["pass"] is False
    assert report["status"] == "FAIL_INVESTIGATE_NO_R3"


def test_thresholds_pre_registered_immutable_keys():
    required = {
        "min_rel_loss_drop",
        "min_auc_above_chance",
        "max_ece",
        "min_pred_std",
        "max_seed_acc_range",
        "min_ablation_mse_increase",
        "max_abs_auc_from_chance_kill",
    }
    assert required <= set(R25_THRESHOLDS.keys())
