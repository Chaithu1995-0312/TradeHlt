# config_mutator.py — single-parameter deep-copy mutation with bounds checking
#
from copy import deepcopy
from src.expansion.policy_schema import PARAM_BOUNDS, MAX_PARAM_CHANGE


class ConfigMutator:
    """
    Applies a single bounded parameter change to a config dict.
    Never mutates the original — always deep-copies.
    Clips result to PARAM_BOUNDS and MAX_PARAM_CHANGE guard.
    """

    @staticmethod
    def mutate(
        config: dict,
        param: str,
        direction: str,
        step: float,
        baseline_value: float = None,
    ) -> dict:
        """
        Args:
            config: source config dict (not mutated)
            param: config key to change
            direction: "increase" | "decrease"
            step: magnitude of change
            baseline_value: original value for MAX_PARAM_CHANGE guard
        Returns:
            new config dict with single param changed
        Raises:
            ValueError if param not in config or bounds exceeded
        """
        if param not in config:
            raise ValueError(f"ConfigMutator: param {param!r} not in config")

        new_config = deepcopy(config)
        current = float(config[param])

        delta = step if direction == "increase" else -step
        new_value = current + delta

        # Apply PARAM_BOUNDS clip
        if param in PARAM_BOUNDS:
            lo, hi = PARAM_BOUNDS[param]
            new_value = max(lo, min(hi, new_value))

        # Apply MAX_PARAM_CHANGE guard from baseline
        if baseline_value is not None:
            total_change = abs(new_value - baseline_value)
            if total_change > MAX_PARAM_CHANGE:
                # Clip to max allowed change from baseline
                if new_value < baseline_value:
                    new_value = baseline_value - MAX_PARAM_CHANGE
                else:
                    new_value = baseline_value + MAX_PARAM_CHANGE

        new_config[param] = round(new_value, 4)
        return new_config

    @staticmethod
    def get_value(config: dict, param: str) -> float:
        """Safe getter with float cast."""
        return float(config.get(param, 0.0))