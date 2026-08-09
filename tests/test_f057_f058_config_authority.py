"""
F-057 / F-058-class remediation floor (target-strategy-architecture.md sec13 items 1-2).

F-057: market_router is config-driven and fail-closed; BacktestRunner's crt_config
fallback resolves through the SAME governed loader the CLI uses, instead of the bare
router-only ConfigBuilder.build().

F-058-class: the zone_gate_invalid backtest bypass is config-declared
(backtest.bypass_zone_invalid), not an undeclared os.getenv(..., "1") default.
"""
from __future__ import annotations

import dataclasses

import pytest

from config_layer.config_builder import ConfigBuilder
from config_layer.market_router import UnknownInstrumentError, classify_market
from config_layer.production_config import (
    PROD_VERSION,
    get_prod_section,
    load_prod_config_from_registry,
)


def test_classify_market_fails_closed_on_unknown_instrument():
    with pytest.raises(UnknownInstrumentError):
        classify_market("NOTAREALSYMBOL")


def test_classify_market_crypto_majors_reclassified():
    """BNBUSDT/SOLUSDT were 'safe-default FOREX' before the fix (crt_config_reachability.json
    bnb_market_class_bug, MED) — now correctly CRYPTO."""
    assert classify_market("BNBUSDT") == "CRYPTO"
    assert classify_market("SOLUSDT") == "CRYPTO"


def test_classify_market_tolerates_filename_derived_hints():
    """backtest_v2's CLI sets cfg.instrument = csv_path.stem.upper() for AUTO mode, which
    can carry the whole filename (e.g. "XAUUSD_W2026-03-23-to-2026-05-21"). The leading
    symbol token must still resolve rather than raising."""
    assert classify_market("XAUUSD_M15") == "FOREX"
    assert classify_market("XAUUSD_W2026-03-23-to-2026-05-21") == "FOREX"


def test_bare_config_builder_now_matches_governed_profile_class():
    """get_crt_config's base profile is config-driven from the same market_router
    section classify_market reads — BNBUSDT's base is now the CRYPTO profile."""
    bare = ConfigBuilder.build("BNBUSDT")
    governed = load_prod_config_from_registry(PROD_VERSION, "BNBUSDT")
    # The 5 router-profile keys are overridden by `params` on the governed path (this is
    # F-057's "latent on the governed path" note) — assert governed matches the ACTIVE
    # config's params section directly, which is the real acceptance criterion.
    params = get_prod_section("params")
    for k in ("body_ratio_min", "atr_multiplier_min", "retest_depth_max",
              "expansion_atr_min_distance", "retest_atr_depth_fraction"):
        assert getattr(governed, k) == params[k]
    # And the bare-builder base (no params/crt_engine merge) is the CRYPTO profile, not FOREX.
    crypto_profile = get_prod_section("market_router")["classes"]["CRYPTO"]
    for k, v in crypto_profile.items():
        assert getattr(bare, k) == v


def test_backtest_runner_fallback_resolves_governed_config_not_bare_router():
    """F-057 core fix: BacktestRunner(cfg) with crt_config=None resolves the SAME
    CRTConfig load_prod_config_from_registry() would build for the same instrument —
    not the bare router-only profile."""
    from runtime.backtest_v2 import BacktestConfig, BacktestRunner

    cfg = BacktestConfig.from_prod_config(instrument="BNBUSDT")
    assert cfg.crt_config is None
    runner = BacktestRunner(cfg)  # no csv_path — legitimate no-feature mode (see
                                  # test_feature_warmup_coupling.py)
    expected = load_prod_config_from_registry(PROD_VERSION, "BNBUSDT")
    assert dataclasses.asdict(runner.crt_cfg) == dataclasses.asdict(expected)


def test_backtest_runner_raises_on_unset_instrument_no_crt_config():
    """No silent 'EURUSD' default (F-057 sec14.A) when neither crt_config nor a real
    instrument is supplied."""
    from runtime.backtest_v2 import BacktestConfig, BacktestRunner

    cfg = BacktestConfig.from_prod_config()  # instrument defaults to "UNKNOWN"
    assert cfg.crt_config is None
    with pytest.raises(ValueError):
        BacktestRunner(cfg)


def test_bypass_zone_invalid_is_config_declared():
    """F-058-class fix: no longer an undeclared os.getenv(..., '1') default."""
    bt_cfg = get_prod_section("backtest")
    assert "bypass_zone_invalid" in bt_cfg
    assert isinstance(bt_cfg["bypass_zone_invalid"], bool)
