"""Phase E1 floors: train-only quantiles, arm assignment, kill rule.

Design: docs/implementation_plan/xauusd-gaussian-toward-economics-2026-07-23.md §E1
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "research" / "xauusd_gaussian_econ_ledger.py"
UNITS = ROOT / "results" / "gaussian_xauusd_econ" / "units_LATEST.jsonl"


def _load():
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    name = "xauusd_gaussian_econ_ledger"
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # Required on Py3.14+ before exec_module so @dataclass can resolve annotations
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def e1():
    if not SCRIPT.exists():
        pytest.skip("E1 script missing")
    return _load()


def test_e1_quantiles_use_train_only(e1):
    units = [
        {"split": "train", "score": 0.1, "direction": "long", "timestamp": "t1"},
        {"split": "train", "score": 0.2, "direction": "long", "timestamp": "t2"},
        {"split": "train", "score": 0.3, "direction": "short", "timestamp": "t3"},
        {"split": "train", "score": 0.4, "direction": "short", "timestamp": "t4"},
        {"split": "train", "score": 0.5, "direction": "long", "timestamp": "t5"},
        {"split": "train", "score": 0.6, "direction": "long", "timestamp": "t6"},
        {"split": "train", "score": 0.7, "direction": "short", "timestamp": "t7"},
        {"split": "train", "score": 0.8, "direction": "short", "timestamp": "t8"},
        {"split": "train", "score": 0.9, "direction": "long", "timestamp": "t9"},
        {"split": "train", "score": 1.0, "direction": "long", "timestamp": "t10"},
        # OOS extreme — must not affect quantiles
        {"split": "oos", "score": 100.0, "direction": "long", "timestamp": "t99"},
        {"split": "oos", "score": -100.0, "direction": "short", "timestamp": "t98"},
    ]
    q = e1.train_quantiles(units)
    assert q["source_split"] == "train_only"
    assert q["n_train_scores"] == 10
    assert q["p90"] < 50  # not polluted by OOS 100
    assert q["p10"] > -50  # not polluted by OOS -100


def test_e1_top_decile_membership_uses_train_threshold(e1):
    units = [
        {"split": "train", "score": float(i) / 10.0, "direction": "long", "timestamp": f"t{i}"}
        for i in range(1, 11)
    ]
    units += [
        {"split": "oos", "score": 0.95, "direction": "short", "timestamp": "o1"},
        {"split": "oos", "score": 0.05, "direction": "short", "timestamp": "o2"},
    ]
    q = e1.train_quantiles(units)
    arms = e1.assign_arms(units, q, seed=42)
    top = set(arms["nb_top_decile"])
    # OOS high score should still qualify if >= train p90
    assert any(units[i]["timestamp"] == "o1" for i in top)
    # OOS low score in bottom
    bot = set(arms["nb_bottom_decile"])
    assert any(units[i]["timestamp"] == "o2" for i in bot)
    assert len(arms["random_match_n"]) == len(arms["nb_top_decile"])


def test_e1_kill_no_skill(e1):
    arm_report = {
        "nb_top_decile": {"oos": {"mean_net_rr": -1.0, "n": 20}},
        "all_units": {"oos": {"mean_net_rr": -0.5, "n": 100}},
        "random_match_n": {"oos": {"mean_net_rr": -0.4, "n": 20}},
    }
    k = e1.apply_kill_criteria(arm_report)
    assert k["verdict"] == "NO_SKILL_KILL"
    assert k["not_economic_authority"] is True


def test_e1_kill_skill_signal_still_not_authority(e1):
    arm_report = {
        "nb_top_decile": {"oos": {"mean_net_rr": 0.2, "n": 20}},
        "all_units": {"oos": {"mean_net_rr": -0.5, "n": 100}},
        "random_match_n": {"oos": {"mean_net_rr": -0.1, "n": 20}},
    }
    k = e1.apply_kill_criteria(arm_report)
    assert k["verdict"] == "SKILL_SIGNAL_RESEARCH_ONLY"
    assert k["not_economic_authority"] is True
    assert k["beats_all_units_oos"] is True


def test_e1_arm_metrics_empty(e1):
    m = e1.arm_metrics([])
    assert m["n"] == 0
    assert m["mean_net_rr"] is None


@pytest.mark.skipif(not UNITS.exists(), reason="E0 units_LATEST missing")
def test_e1_units_load_and_quantiles_real(e1):
    units = e1.load_units(UNITS)
    assert len(units) == 3247
    q = e1.train_quantiles(units)
    assert q["n_train_scores"] == 2980
    assert 0.0 <= q["p10"] <= q["p90"] <= 1.0
    arms = e1.assign_arms(units, q, seed=e1._seed_u32(e1.PROTOCOL_ID))
    assert len(arms["all_units"]) == 3247
    assert len(arms["nb_top_decile"]) > 0
    assert len(arms["random_match_n"]) == len(arms["nb_top_decile"])
