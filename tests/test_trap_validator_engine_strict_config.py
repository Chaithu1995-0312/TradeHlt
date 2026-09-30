"""EPIC-84 L-C (src/engines): TrapValidatorEngine has no code defaults.

min_atr/allowed_sessions used to fall back to code literals (0.0005 /
[asia, london, new_york]) whenever the passed-in config lacked them. `config`
here is NOT the full production config — engine_runner.py's real caller
(backtest_v2.py: `_er_cfg = dict(get_prod_section("engine_runner"))`) passes
the flattened `engine_runner` section, so both keys are read at the top
level of `config`, matching `engine_runner.min_atr` / `engine_runner.
allowed_sessions` in configs/production/*.json — both already declared there
(0.0003 / [london, new_york, overlap]; the old code literals never actually
fired on the real call path). Both are now required at construction.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from config_layer.strict_config import ConfigKeyMissingError  # noqa: E402
from engines.trap_validator_engine import TrapValidatorEngine  # noqa: E402

_ER_CFG = {"min_atr": 0.0005, "allowed_sessions": ["asia", "london", "new_york"]}

_VALID_INPUT = {
    "_data_integrity": "real",
    "close": 1.2910, "high": 1.3010, "low": 1.2890, "open": 1.2920,
    "volume": 100.0, "atr": 0.0010, "ema_fast": 1.29, "ema_slow": 1.28,
    "session": "asia",
}


def _engine(cfg=None) -> TrapValidatorEngine:
    return TrapValidatorEngine(dict(cfg) if cfg is not None else dict(_ER_CFG))


def test_construction_reads_declared_values():
    eng = _engine()
    assert eng.min_atr == 0.0005
    assert eng.allowed_sessions == ["asia", "london", "new_york"]


@pytest.mark.parametrize("key", sorted(_ER_CFG))
def test_construction_missing_key_raises_naming_it(key):
    cfg = {k: v for k, v in _ER_CFG.items() if k != key}
    with pytest.raises(ConfigKeyMissingError) as ei:
        _engine(cfg)
    assert key in ei.value.missing
    assert ei.value.section == "engine_runner"


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


def test_engine_runner_section_shape_matches_active_config():
    """Parity guard: the active production config's engine_runner section
    already declares both keys (this fix needed no new DECLARATIONS)."""
    from config_layer.production_config import get_prod_section
    er = get_prod_section("engine_runner")
    eng = TrapValidatorEngine(dict(er))
    assert eng.min_atr == er["min_atr"]
    assert eng.allowed_sessions == er["allowed_sessions"]
