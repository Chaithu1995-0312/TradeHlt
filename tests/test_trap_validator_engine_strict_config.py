"""EPIC-84 L-C (src/engines): TrapValidatorEngine has no code defaults.

min_atr/allowed_sessions used to fall back to code literals (0.0005 /
[asia, london, new_york]) whenever the passed-in config lacked a
`trap_validator` section — which it always did on the real production spine
(engine_runner.py constructs TrapValidatorEngine(config) with the full prod
config dict, which declares no such section). Both are now DECLARED under
`trap_validator` and required at construction.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from config_layer.strict_config import ConfigKeyMissingError  # noqa: E402
from engines.trap_validator_engine import TrapValidatorEngine  # noqa: E402

_TRAP_SECTION = {"min_atr": 0.0005, "allowed_sessions": ["asia", "london", "new_york"]}

_VALID_INPUT = {
    "_data_integrity": "real",
    "close": 1.2910, "high": 1.3010, "low": 1.2890, "open": 1.2920,
    "volume": 100.0, "atr": 0.0010, "ema_fast": 1.29, "ema_slow": 1.28,
    "session": "asia",
}


def _engine(section=None) -> TrapValidatorEngine:
    return TrapValidatorEngine({"trap_validator": section if section is not None else dict(_TRAP_SECTION)})


def test_construction_reads_declared_values():
    eng = _engine()
    assert eng.min_atr == 0.0005
    assert eng.allowed_sessions == ["asia", "london", "new_york"]


def test_construction_missing_section_raises():
    with pytest.raises(ConfigKeyMissingError) as ei:
        TrapValidatorEngine({})
    assert ei.value.missing == ("trap_validator",)


@pytest.mark.parametrize("key", sorted(_TRAP_SECTION))
def test_construction_missing_key_raises_naming_it(key):
    section = {k: v for k, v in _TRAP_SECTION.items() if k != key}
    with pytest.raises(ConfigKeyMissingError) as ei:
        _engine(section)
    assert key in ei.value.missing
    assert ei.value.section == "trap_validator"


def test_compute_passes_valid_input():
    result = _engine().compute(dict(_VALID_INPUT))
    assert result == {"score": 1.0, "reason": "pass"}


def test_compute_uses_declared_min_atr():
    """A min_atr declared higher than the input's atr rejects (proves the
    declared value, not a hardcoded 0.0005, is what's actually applied)."""
    eng = _engine({"min_atr": 0.005, "allowed_sessions": ["asia"]})
    result = eng.compute(dict(_VALID_INPUT))
    assert result["reason"] == "low_atr:0.001"


def test_compute_uses_declared_allowed_sessions():
    """A session absent from the declared allowed_sessions rejects."""
    eng = _engine({"min_atr": 0.0005, "allowed_sessions": ["london"]})
    result = eng.compute(dict(_VALID_INPUT))
    assert result["reason"] == "invalid_session:asia"
