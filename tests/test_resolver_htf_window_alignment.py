"""CH-timeframe-ssot-v2 — the resolver's HTF window equals the engine's.

`CRTStateResolver` and the backtest engine are compared bar for bar (F-069). The engine's HTF clock is
`backtest.htf_candles_per_range` (HTFBuilder, bars per HTF window); the resolver's is
`thresholds.lifecycle.htf_candles_per_range` in `configs/formulas/market_crt_states.yaml`, a COPY of that value.
The copy read 4 while the active config said 16, so the resolver reset on its HTF clock four times as often as
the engine it was compared with. Demonstrated drift, so this is an executable invariant. Also pinned: the
window has no silent default in the resolver, and the engine's would_expand score reads its window.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def _yaml_window() -> int:
    cfg = yaml.safe_load((_ROOT / "configs/formulas/market_crt_states.yaml").read_text(encoding="utf-8"))
    return int(cfg["thresholds"]["lifecycle"]["htf_candles_per_range"])


def test_resolver_window_equals_the_active_backtest_window():
    from config_layer.production_config import get_prod_section

    active = int(get_prod_section("backtest")["htf_candles_per_range"])
    assert _yaml_window() == active, (
        f"market_crt_states.yaml lifecycle.htf_candles_per_range={_yaml_window()} but the active config's "
        f"backtest.htf_candles_per_range={active}: the resolver's HTF clock would not track the engine's."
    )


def test_resolver_has_no_silent_default_for_the_window(tmp_path):
    from features.crt_state_resolver import CRTStateResolver

    cfg = yaml.safe_load((_ROOT / "configs/formulas/market_crt_states.yaml").read_text(encoding="utf-8"))
    del cfg["thresholds"]["lifecycle"]["htf_candles_per_range"]
    path = tmp_path / "no_window.yaml"
    path.write_text(yaml.dump(cfg, sort_keys=False), encoding="utf-8")
    with pytest.raises(ValueError, match="htf_candles_per_range is required"):
        CRTStateResolver(instrument="XAUUSD", config_path=path)


def _reset_record(window: int, remaining: int) -> dict:
    from config_layer.crt_engine_v2 import TelemetryCollector

    t = TelemetryCollector()
    t.on_reset("DISPLACEMENT", "HTF window change", 10, displacement_age_candles=3, ema_aligned=False,
               remaining_htf_candles=remaining, direction_consistent=False, candle_ts=None, shadow_used=False,
               candidate_age_at_entry=0, htf_window_candles=window)
    return t._reset_records[-1]


def test_would_expand_score_is_read_out_of_the_window():
    # displacement term 0.30 (age 3 of 3); ema/direction off; remaining 8 of a 16-bar window = 0.5 -> +0.075
    assert _reset_record(16, 8)["would_expand_score"] == pytest.approx(0.30 + 0.075, abs=1e-4)
    # the same remaining position in a 4-bar window saturates (min(8/4, 1) = 1) -> +0.15
    assert _reset_record(4, 8)["would_expand_score"] == pytest.approx(0.30 + 0.15, abs=1e-4)
    # the last bar of a 16-bar window contributes nothing
    assert _reset_record(16, 0)["would_expand_score"] == pytest.approx(0.30, abs=1e-4)


def test_unsupplied_window_keeps_the_legacy_four_and_warns(caplog):
    import logging

    from config_layer.crt_engine_v2 import TelemetryCollector

    t = TelemetryCollector()
    with caplog.at_level(logging.WARNING, logger="CRT.Telemetry"):
        t.on_reset("DISPLACEMENT", "HTF window change", 10, displacement_age_candles=3, ema_aligned=False,
                   remaining_htf_candles=8, direction_consistent=False, candle_ts=None, shadow_used=False,
                   candidate_age_at_entry=0)
    assert t._reset_records[-1]["would_expand_score"] == pytest.approx(0.30 + 0.15, abs=1e-4)
    assert "htf_window_candles not supplied" in caplog.text
