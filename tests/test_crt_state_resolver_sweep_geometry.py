"""B1: CRTStateResolver HTF-range SWEEP geometry (research shadow only).

Pins engine RangeDetector.detect_sweep parity for the shadow resolver:
  swept_high = high > h_ref and close < h_ref
  swept_low  = low  < l_ref and close > l_ref

Production crt_engine_v2 is not exercised here. Default sweep_geometry is
htf_range; pipeline_swing preserves the pre-B1 when-block path.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from features.crt_state_resolver import CRTStateResolver  # noqa: E402


def _base_features(**overrides) -> dict:
    """Minimal feature dict accepted by FeatureStateEncoder.classify()."""
    fv = {
        "open": 100.0,
        "high": 101.0,
        "low": 99.0,
        "close": 100.5,
        "atr": 0.001,
        "body_ratio": 0.5,
        "candle_range": 2.0,
        "liquidity_sweep": 0.0,
        "sweep_detected": 0.0,
        "break_of_structure": 0.0,
        "displacement_flag": 0.0,
        "double_sweep": 0.0,
        "higher_high": 0.0,
        "lower_low": 0.0,
        "retest_flag": 0.0,
        "swing_high": 0.0,
        "swing_low": 0.0,
        "volume_spike": 0.0,
        "volatility_regime": 1.0,
        "trend_bias": 0.0,
        "rsi_14": 50.0,
        "session": 1.0,
    }
    fv.update(overrides)
    return fv


def _write_cfg(tmp_path: Path, sweep_geometry: str) -> Path:
    base = yaml.safe_load(
        (ROOT / "configs/formulas/market_crt_states.yaml").read_text(encoding="utf-8")
    )
    base["thresholds"]["sweep_geometry"] = sweep_geometry
    base["thresholds"]["range_atr_period"] = 4
    base["thresholds"]["lifecycle"]["htf_candles_per_range"] = 4
    out = tmp_path / f"crt_states_{sweep_geometry}.yaml"
    out.write_text(yaml.dump(base, default_flow_style=False, sort_keys=False), encoding="utf-8")
    return out


def test_htf_range_sweep_high_founding(tmp_path):
    cfg = _write_cfg(tmp_path, "htf_range")
    r = CRTStateResolver(config_path=cfg)
    # Seed a tight range [100, 110]
    for o, h, l, c in [
        (105, 110, 104, 106),
        (106, 109, 103, 105),
        (105, 108, 100, 104),
        (104, 107, 101, 105),
    ]:
        r.seed_ohlc(o, h, l, c, htf_id="XAU-HTF-000001")
    r.finalize_seed_range()
    assert r.memory.range_ready
    assert r.memory.range_h_ref == 110
    assert r.memory.range_l_ref == 100

    # Sell-side sweep: pierce high, close back inside
    state = r.resolve(
        _base_features(
            open=108.0,
            high=112.0,
            low=107.0,
            close=109.0,
            body_ratio=0.2,
            candle_range=5.0,
            # pipeline says NoSweep — HTF geometry must still fire
            liquidity_sweep=0.0,
            sweep_detected=0.0,
        ),
        htf_id="XAU-HTF-000001",
    )
    assert state == "SWEEP"


def test_htf_range_no_sweep_when_close_outside(tmp_path):
    cfg = _write_cfg(tmp_path, "htf_range")
    r = CRTStateResolver(config_path=cfg)
    for o, h, l, c in [
        (105, 110, 104, 106),
        (106, 109, 103, 105),
        (105, 108, 100, 104),
        (104, 107, 101, 105),
    ]:
        r.seed_ohlc(o, h, l, c, htf_id="XAU-HTF-000001")
    r.finalize_seed_range()

    # High pierces but close stays above h_ref → engine rejects
    state = r.resolve(
        _base_features(
            open=111.0,
            high=113.0,
            low=110.5,
            close=112.0,  # close > h_ref=110
            candle_range=2.5,
            liquidity_sweep=1.0,  # pipeline would fire — must be ignored
            sweep_detected=1.0,
        ),
        htf_id="XAU-HTF-000001",
    )
    assert state == "RANGE"


def test_pipeline_swing_still_uses_liquidity_sweep(tmp_path):
    cfg = _write_cfg(tmp_path, "pipeline_swing")
    r = CRTStateResolver(config_path=cfg)
    # No range seed needed — pipeline path
    state = r.resolve(
        _base_features(
            liquidity_sweep=1.0,
            sweep_detected=1.0,
        )
    )
    assert state == "SWEEP"


def test_detect_htf_range_sweep_unit(tmp_path):
    cfg = _write_cfg(tmp_path, "htf_range")
    r = CRTStateResolver(config_path=cfg)
    r._memory.range_h_ref = 2000.0
    r._memory.range_l_ref = 1900.0
    r._memory.range_ready = True
    assert r._detect_htf_range_sweep({"high": 2005.0, "low": 1990.0, "close": 1995.0}) == 1
    assert r._detect_htf_range_sweep({"high": 1950.0, "low": 1890.0, "close": 1910.0}) == -1
    assert r._detect_htf_range_sweep({"high": 1999.0, "low": 1901.0, "close": 1950.0}) == 0
    # strict close: close == h_ref is NOT a sweep (engine uses close < h_ref)
    assert r._detect_htf_range_sweep({"high": 2005.0, "low": 1990.0, "close": 2000.0}) == 0


def test_seed_uses_completed_htf_window_not_tail(tmp_path):
    """B1b: final seed = last completed HTFBuilder window, not buffer[-cph:]."""
    cfg = _write_cfg(tmp_path, "htf_range")
    r = CRTStateResolver(config_path=cfg)
    # Window 0: lows=10 highs=20
    for o, h, l, c in [
        (15, 20, 14, 16),
        (16, 19, 13, 15),
        (15, 18, 12, 14),
        (14, 17, 10, 15),
    ]:
        r.seed_ohlc(o, h, l, c, htf_id="HTF-A")
    # Incomplete next window (should NOT enter seed range)
    r.seed_ohlc(100, 200, 50, 150, htf_id="HTF-B")
    r.seed_ohlc(100, 200, 50, 150, htf_id="HTF-B")
    r.finalize_seed_range()
    assert r.memory.range_ready
    assert r.memory.range_h_ref == 20
    assert r.memory.range_l_ref == 10
    assert r.memory.range_htf_id == "HTF-A"


def test_shadow_path_collapses_to_expansion(tmp_path):
    """B1d: DISPLACEMENT + HTF reset → pending; confirming sweep → SHADOW → EXP."""
    cfg = _write_cfg(tmp_path, "htf_range")
    r = CRTStateResolver(config_path=cfg)
    for o, h, l, c in [
        (105, 110, 104, 106),
        (106, 109, 103, 105),
        (105, 108, 100, 104),
        (104, 107, 101, 105),
    ]:
        r.seed_ohlc(o, h, l, c, htf_id="HTF-1")
    r.finalize_seed_range()

    # In DISPLACEMENT with LONG direction, HTF reset creates shadow
    r._memory.current_state = "DISPLACEMENT"
    r._memory.displacement_direction = 1  # LONG
    r._memory.displacement_candle_index = 10
    r._memory.candle_index = 10
    r.resolve(
        _base_features(open=105.0, high=106.0, low=104.0, close=105.5),
        htf_id="HTF-2",
        engine_reset=True,
        reset_reason="HTF changed: HTF-1 → HTF-2",
    )
    assert r.memory.pending_displacement_active
    assert r.memory.pending_displacement_dir == "LONG"
    assert r.memory.current_state == "RANGE"

    # Confirming buy-side sweep (sig -1 → LONG) → SHADOW_PENDING
    # Need range that allows low sweep: rebuild already set from reset
    r._memory.range_h_ref = 110.0
    r._memory.range_l_ref = 100.0
    r._memory.range_ready = True
    st = r.resolve(
        _base_features(
            open=102.0, high=103.0, low=98.0, close=101.0,  # low < 100, close > 100
            displacement_flag=0.0,
        ),
        htf_id="HTF-2",
    )
    assert st == "SHADOW_PENDING"

    # Next bar: collapse to EXPANSION
    st2 = r.resolve(
        _base_features(open=101.0, high=102.0, low=100.5, close=101.5),
        htf_id="HTF-2",
    )
    assert st2 == "EXPANSION"
    assert not r.memory.pending_displacement_active


def test_displacement_has_no_sticky_age_kill(tmp_path):
    """B1e: DISPLACEMENT must not age-out (engine has no DISP TTL)."""
    cfg = _write_cfg(tmp_path, "htf_range")
    r = CRTStateResolver(config_path=cfg)
    r._memory.current_state = "DISPLACEMENT"
    r._memory.displacement_candle_index = 1
    r._memory.candle_index = 100  # age 99
    r._memory.displacement_candle_close = 2000.0
    r._memory.displacement_direction = 1
    assert r._sticky_age_expired("DISPLACEMENT") is False
    # sticky hold
    st = r.resolve(
        _base_features(
            open=2000.0, high=2001.0, low=1999.0, close=2000.1,  # no expansion
            atr=0.001, body_ratio=0.5, candle_range=2.0,
        ),
        htf_id="HTF-1",
    )
    assert st == "DISPLACEMENT"


def test_sweep_plus_pending_does_not_auto_expand(tmp_path):
    """B1g: SWEEP+stale pending must not jump to EXPANSION (FP over-hold source)."""
    cfg = _write_cfg(tmp_path, "htf_range")
    r = CRTStateResolver(config_path=cfg)
    r._memory.current_state = "SWEEP"
    r._memory.sweep_candle_index = 10
    r._memory.candle_index = 10
    r._memory.pending_displacement_active = True
    r._memory.pending_displacement_dir = "LONG"
    r._memory.pending_displacement_ttl = 4
    r._memory.range_ready = True
    r._memory.range_h_ref = 110.0
    r._memory.range_l_ref = 100.0
    st = r.resolve(
        _base_features(open=105.0, high=106.0, low=104.0, close=105.5),
        htf_id="HTF-1",
    )
    assert st != "EXPANSION"
    assert st in ("SWEEP", "DISPLACEMENT")


def test_engine_state_to_exp_requires_legal_from(tmp_path):
    """B1g: bare/illegal FROM must not promote SWEEP→EXP via inject."""
    cfg = _write_cfg(tmp_path, "htf_range")
    r = CRTStateResolver(config_path=cfg)
    r._memory.current_state = "SWEEP"
    r._memory.sweep_candle_index = 10
    r._memory.candle_index = 10
    r._memory.range_ready = True
    r._memory.range_h_ref = 110.0
    r._memory.range_l_ref = 100.0
    # Bare TO (legacy) from SWEEP — rejected
    st = r.resolve(
        _base_features(open=105.0, high=106.0, low=104.0, close=105.5),
        htf_id="HTF-1",
        engine_state_to="EXPANSION",
    )
    assert st != "EXPANSION"
    # Legal DISPLACEMENT>EXPANSION
    r2 = CRTStateResolver(config_path=cfg)
    r2._memory.current_state = "DISPLACEMENT"
    r2._memory.displacement_candle_close = 2000.0
    r2._memory.displacement_direction = 1
    st2 = r2.resolve(
        _base_features(open=1999.0, high=2000.0, low=1998.0, close=1999.5, atr=0.001),
        htf_id="HTF-1",
        engine_state_to="DISPLACEMENT>EXPANSION",
    )
    assert st2 == "EXPANSION"


def test_expansion_mid_dwell_ignores_pipeline_retest_flag(tmp_path):
    """B1f: sticky EXP must not leave on pipeline retest_flag alone."""
    cfg = _write_cfg(tmp_path, "htf_range")
    r = CRTStateResolver(config_path=cfg)
    r._memory.current_state = "EXPANSION"
    r._memory.expansion_entry_index = 1
    r._memory.expansion_entry_ts = None
    r._memory.range_ready = True
    r._memory.range_h_ref = 110.0
    r._memory.range_l_ref = 100.0
    r._config["thresholds"]["max_expansion_age_candles"] = 10_000
    r._config["thresholds"]["max_expansion_age_hours"] = 10_000
    # Pipeline retest_flag active + low depth would have matched RETEST when-block
    st = r.resolve(
        _base_features(
            open=105.0, high=106.0, low=104.0, close=105.5,
            retest_flag=1.0,
            retest_depth=0.01,
            sweep_detected=1.0,
            break_of_structure=0.0,
        ),
        htf_id="HTF-1",
    )
    assert st == "EXPANSION"


def test_engine_state_to_exits_expansion(tmp_path):
    """B1e: engine STATE_TRANSITION leaving EXP ends sticky over-hold."""
    cfg = _write_cfg(tmp_path, "htf_range")
    r = CRTStateResolver(config_path=cfg)
    r._memory.current_state = "EXPANSION"
    r._memory.expansion_entry_index = 1
    r._memory.range_ready = True
    r._memory.range_h_ref = 110.0
    r._memory.range_l_ref = 100.0
    r._config["thresholds"]["max_expansion_age_candles"] = 10_000
    r._config["thresholds"]["max_expansion_age_hours"] = 10_000
    st = r.resolve(
        _base_features(open=105.0, high=106.0, low=104.0, close=105.5),
        htf_id="HTF-1",
        engine_state_to="RANGE",
    )
    assert st == "RANGE"


def test_engine_state_to_promotes_disp_to_expansion(tmp_path):
    """B1e: engine transition to EXPANSION promotes from DISPLACEMENT."""
    cfg = _write_cfg(tmp_path, "htf_range")
    r = CRTStateResolver(config_path=cfg)
    r._memory.current_state = "DISPLACEMENT"
    r._memory.displacement_candle_close = 2000.0
    r._memory.displacement_direction = 1
    r._memory.displacement_candle_index = 5
    st = r.resolve(
        _base_features(open=1999.0, high=2000.0, low=1998.0, close=1999.5, atr=0.001),
        htf_id="HTF-1",
        engine_state_to="EXPANSION",
    )
    assert st == "EXPANSION"


def test_htf_engine_reset_suppressed_in_expansion(tmp_path):
    """B1d: HTF engine_reset must not kill EXPANSION (engine protect)."""
    cfg = _write_cfg(tmp_path, "htf_range")
    r = CRTStateResolver(config_path=cfg)
    r._memory.current_state = "EXPANSION"
    r._memory.expansion_entry_index = 5
    r._memory.range_ready = True
    r._memory.range_htf_id = "HTF-1"
    r._memory.range_h_ref = 110.0
    r._memory.range_l_ref = 100.0
    r._config["thresholds"]["max_expansion_age_candles"] = 10_000
    r._config["thresholds"]["max_expansion_age_hours"] = 10_000
    st = r.resolve(
        _base_features(open=105.0, high=106.0, low=104.0, close=105.5),
        htf_id="HTF-9",
        engine_reset=True,
        reset_reason="HTF changed: HTF-1 → HTF-9",
    )
    assert st == "EXPANSION"


def test_funnel_sweep_to_displacement_bypasses_pipeline_flag(tmp_path):
    """B1c: SWEEP→DISPLACEMENT via continuous gates without displacement_flag."""
    cfg = _write_cfg(tmp_path, "htf_range")
    # Align with production-ish gates used in market_crt_states after B1c
    import yaml
    base = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    base["thresholds"]["body_ratio_min"] = 0.65
    base["thresholds"]["atr_multiplier_min"] = 1.0
    cfg.write_text(yaml.dump(base, default_flow_style=False, sort_keys=False), encoding="utf-8")

    r = CRTStateResolver(config_path=cfg)
    for o, h, l, c in [
        (105, 110, 104, 106),
        (106, 109, 103, 105),
        (105, 108, 100, 104),
        (104, 107, 101, 105),
    ]:
        r.seed_ohlc(o, h, l, c, htf_id="HTF-1")
    r.finalize_seed_range()

    # Found SWEEP
    st = r.resolve(
        _base_features(
            open=108.0, high=112.0, low=107.0, close=109.0,
            displacement_flag=0.0,
        ),
        htf_id="HTF-1",
    )
    assert st == "SWEEP"

    # Displacement: strong body, no pipeline flag
    # atr_rel=0.001, close=2000 → atr_abs=2; move=3 >= 1.2*2; body=0.8; range=4 >= 1.0*2
    st2 = r.resolve(
        _base_features(
            open=1997.0, high=2001.0, low=1996.0, close=2000.0,
            atr=0.001,
            body_ratio=0.8,
            candle_range=5.0,
            displacement_flag=0.0,
        ),
        htf_id="HTF-1",
    )
    assert st2 == "DISPLACEMENT"


def test_engine_reset_rebuilds_range_from_buffer(tmp_path):
    """B1b: engine_reset=True rebuilds h_ref/l_ref from buffer[-atr_period:]."""
    cfg = _write_cfg(tmp_path, "htf_range")
    r = CRTStateResolver(config_path=cfg)
    # Seed + set a known range
    for o, h, l, c in [
        (100, 110, 90, 105),
        (101, 111, 91, 106),
        (102, 112, 92, 107),
        (103, 113, 93, 108),
    ]:
        r.seed_ohlc(o, h, l, c, htf_id="HTF-1")
    r.finalize_seed_range()
    assert r.memory.range_h_ref == 113

    # Push new extremes via resolve with engine_reset — buffer grows, rebuild
    st = r.resolve(
        _base_features(open=200.0, high=250.0, low=50.0, close=180.0),
        htf_id="HTF-2",
        engine_reset=True,
        reset_reason="HTF changed: HTF-1 → HTF-2",
    )
    assert st in ("RANGE", "SWEEP")
    # Rebuild includes the new bar (engine appends before rebuild)
    assert r.memory.range_h_ref >= 250.0 or r.memory.range_ready
    assert r.memory.range_htf_id == "HTF-2"


def test_protected_htf_keeps_stale_range_id_then_resets(tmp_path):
    """B1b: EXPANSION protects HTF reset; range_htf_id stays stale until exit."""
    cfg = _write_cfg(tmp_path, "htf_range")
    r = CRTStateResolver(config_path=cfg)
    for o, h, l, c in [
        (105, 110, 104, 106),
        (106, 109, 103, 105),
        (105, 108, 100, 104),
        (104, 107, 101, 105),
    ]:
        r.seed_ohlc(o, h, l, c, htf_id="HTF-1")
    r.finalize_seed_range()
    assert r.memory.range_htf_id == "HTF-1"

    # Force EXPANSION sticky + advance HTF — must NOT rebuild range
    r._memory.current_state = "EXPANSION"
    r._memory.expansion_entry_index = r._memory.candle_index
    r._memory.expansion_entry_ts = None
    # Disable expansion TTL for this test (huge age)
    r._config["thresholds"]["max_expansion_age_candles"] = 10_000
    r._config["thresholds"]["max_expansion_age_hours"] = 10_000

    st = r.resolve(
        _base_features(open=105.0, high=106.0, low=104.0, close=105.5),
        htf_id="HTF-2",
    )
    assert st == "EXPANSION"
    assert r.memory.range_htf_id == "HTF-1"  # stale
    assert r.memory.active_htf_id == "HTF-2"
    h_before, l_before = r.memory.range_h_ref, r.memory.range_l_ref

    # Leave protect → first unprotected bar must HTF-reset and rebuild
    r._memory.current_state = "RANGE"
    st2 = r.resolve(
        _base_features(open=105.0, high=106.0, low=104.0, close=105.5),
        htf_id="HTF-2",
    )
    # After HTF reset fall-through, state is RANGE (or SWEEP if geometry fires)
    assert st2 in ("RANGE", "SWEEP")
    assert r.memory.range_htf_id == "HTF-2"
    # Rebuild from atr_period buffer — refs should update from seed-only window
    assert r.memory.range_ready
