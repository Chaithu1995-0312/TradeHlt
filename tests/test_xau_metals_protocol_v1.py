"""Floors for pre-registered xau_metals_protocol_v1 (frozen before re-measure)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

PROTOCOL_JSON = ROOT / "configs" / "research" / "xau_metals_protocol_v1.json"


@pytest.fixture(scope="module")
def proto():
    from research.xau_metals_protocol import load_protocol, protocol_sha256

    assert PROTOCOL_JSON.exists()
    p = load_protocol(str(PROTOCOL_JSON))
    return p, protocol_sha256(str(PROTOCOL_JSON))


def test_protocol_id_and_status(proto):
    p, sha = proto
    assert p["protocol_id"] == "xau_metals_protocol_v1"
    assert p["status"] == "PRE_REGISTERED_NOT_EXECUTED"
    assert p["authority"]["grants_economic_authority"] is False
    assert p["authority"]["grants_live_wire"] is False
    assert len(sha) == 64


def test_cost_primary_is_fixed_usd_not_12bps(proto):
    p, _ = proto
    assert p["cost_model"]["primary"]["mode"] == "fixed_usd_round_trip"
    assert p["cost_model"]["primary"]["usd_round_trip"] == 0.40
    assert p["cost_model"]["legacy_diagnostic"]["role"].startswith("DIAGNOSTIC")
    grid = p["cost_model"]["sensitivity_pre_registered"]["usd_round_trip_grid"]
    assert 0.40 in grid
    assert grid == [0.20, 0.40, 0.80]


def test_cost_r_math_and_net():
    from research.xau_metals_protocol import cost_r_fixed_usd, net_rr

    # risk=2.0, usd=0.40 → cost_R=0.20; gross +1 → net 0.80
    assert abs(cost_r_fixed_usd(2500.0, 2.0, sl_atr_mult=1.0, usd_round_trip=0.40) - 0.2) < 1e-12
    n = net_rr(1.0, 2500.0, 2.0, sl_atr_mult=1.0, usd_round_trip=0.40)
    assert abs(n - 0.8) < 1e-12
    # tiny ATR: cost large but finite
    c = cost_r_fixed_usd(2500.0, 0.5, sl_atr_mult=1.0, usd_round_trip=0.40)
    assert abs(c - 0.8) < 1e-12


def test_entry_ontology_is_retest_not_sweep(proto):
    p, _ = proto
    prim = p["entry_ontology"]["primary"]
    assert prim["state"] == "RETEST"
    assert prim["edge"] == "enter"
    forbidden = p["entry_ontology"]["forbidden_without_new_protocol_id"]
    assert any("SWEEP" in x for x in forbidden)


def test_control_arm_size_match_acceptance():
    from research.xau_metals_protocol import (
        assert_control_acceptance,
        assign_random_match_control,
    )

    # 20 train + 10 oos; top = highest 2 train + 1 oos
    n = 30
    splits = ["train"] * 20 + ["oos"] * 10
    scores = list(range(30))  # 0..29
    # p90-like: mark top as last 2 train (18,19) and last 1 oos (29)
    in_top = [False] * 30
    in_top[18] = in_top[19] = in_top[29] = True
    member = assign_random_match_control(
        n_units=n, splits=splits, in_top=in_top
    )
    assert_control_acceptance(in_top=in_top, in_random=member, splits=splits)
    assert sum(member) == 3
    assert sum(member[i] for i in range(20)) == 2
    assert sum(member[i] for i in range(20, 30)) == 1


def test_control_rejects_mismatched_lengths():
    from research.xau_metals_protocol import ProtocolError, assert_control_acceptance

    with pytest.raises(ProtocolError):
        assert_control_acceptance(
            in_top=[True, False],
            in_random=[True],
            splits=["train", "train"],
        )


def test_no_retrain_and_model_pinned(proto):
    p, _ = proto
    assert p["model"]["retrain_under_this_protocol"] is False
    assert p["model"]["version"] == "xauusd_nb_20260722T194904Z"
    assert p["model"]["feature_dim_required"] == 39


def test_m4_primary_hypothesis(proto):
    p, _ = proto
    assert p["scoring_arms"]["primary_hypothesis_for_M4"] == "nb_top_decile"
    assert p["m4"]["control"] == "random_match_n"
    assert p["m4"]["min_samples"] == 30
    assert p["m4"]["expectancy_min"] == 0.0
