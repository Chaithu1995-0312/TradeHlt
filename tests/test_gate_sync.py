"""
test_gate_sync.py
═══════════════════════════════════════════════════════════════════════════════
Asserts that config_validator._FITNESS_WEIGHTS stays in sync with
tuner.fitness_weights in the production config JSON.

Both sections optimise and gate on the same formula; if they drift, the tuner
can maximise a metric that the validator ignores.

Run:
    pytest tests/test_gate_sync.py -v
═══════════════════════════════════════════════════════════════════════════════
"""

from config_layer.config_validator import _FITNESS_WEIGHTS
from config_layer.production_config import get_prod_section

_EXPECTED_KEYS = ("expectancy_rr", "win_rate", "trade_count_norm", "drawdown")


def test_fitness_weight_sync():
    """config_validator._FITNESS_WEIGHTS must match tuner.fitness_weights exactly."""
    tuner_weights = get_prod_section("tuner")["fitness_weights"]
    assert _FITNESS_WEIGHTS == tuner_weights, (
        f"Fitness weight drift detected.\n"
        f"  config_validator: {_FITNESS_WEIGHTS}\n"
        f"  tuner:            {tuner_weights}\n"
        "Update one section to match the other in configs/production/v1_multi_2026_03.json"
    )


def test_fitness_weights_sum_to_one():
    """Weights must sum to 1.0 so the fitness score is properly normalised."""
    total = sum(_FITNESS_WEIGHTS.values())
    assert abs(total - 1.0) < 1e-9, (
        f"config_validator fitness weights sum to {total}, expected 1.0"
    )


def test_tuner_fitness_weights_sum_to_one():
    """Tuner weights must also sum to 1.0 independently."""
    tuner_weights = get_prod_section("tuner")["fitness_weights"]
    total = sum(tuner_weights.values())
    assert abs(total - 1.0) < 1e-9, (
        f"tuner fitness_weights sum to {total}, expected 1.0"
    )


def test_expected_keys_present():
    """All four scoring dimensions must be present in config_validator weights."""
    for key in _EXPECTED_KEYS:
        assert key in _FITNESS_WEIGHTS, (
            f"Key '{key}' missing from config_validator._FITNESS_WEIGHTS"
        )


def test_tuner_expected_keys_present():
    """All four scoring dimensions must be present in tuner weights too."""
    tuner_weights = get_prod_section("tuner")["fitness_weights"]
    for key in _EXPECTED_KEYS:
        assert key in tuner_weights, (
            f"Key '{key}' missing from tuner.fitness_weights"
        )


def test_no_extra_keys():
    """Neither section should have undocumented weight keys."""
    validator_keys = set(_FITNESS_WEIGHTS.keys())
    tuner_keys = set(get_prod_section("tuner")["fitness_weights"].keys())
    assert validator_keys == tuner_keys, (
        f"Key mismatch between sections.\n"
        f"  validator-only: {validator_keys - tuner_keys}\n"
        f"  tuner-only:     {tuner_keys - validator_keys}"
    )
