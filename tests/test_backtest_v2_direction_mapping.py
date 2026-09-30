"""
test_backtest_v2_direction_mapping.py
======================================
task_d0134aa6 (2026-09-30): backtest_v2.py's per-bar EngineRunner feature map cast
`int(Direction.LONG.value)` = `int("LONG")`, which always raises ValueError (caught
by a bare `except Exception`), so `direction`/`signal_dir`/`trade_direction` were
never threaded into EngineRunner on the backtest path. Masked for its whole history
because every corpus-observed trade happened to be LONG under the old fallback.
`_crt_direction_to_int` is the fix: an explicit enum->signed-int map, no cast.
"""

from runtime.backtest_v2 import _crt_direction_to_int
from config_layer.crt_engine_v2 import Direction


def test_long_direction_maps_to_positive_one():
    assert _crt_direction_to_int(Direction.LONG) == 1


def test_short_direction_maps_to_negative_one():
    assert _crt_direction_to_int(Direction.SHORT) == -1


def test_none_direction_maps_to_none():
    assert _crt_direction_to_int(Direction.NONE) is None
