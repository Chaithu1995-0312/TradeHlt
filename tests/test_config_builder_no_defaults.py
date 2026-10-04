"""EPIC-84 A1: CRTConfig has no code defaults; ConfigBuilder builds only from declared fields."""
import dataclasses

import pytest

from config_layer.config_builder import ConfigBuilder
from config_layer.market_router import UnknownInstrumentError
from config_layer.production_config import get_active_version, load_prod_config_from_registry
from config_layer.state_identity import CRTConfig
from config_layer.strict_config import ConfigKeyMissingError
from tests.helpers.crt_config import crt_test_fields

FIELDS = [f.name for f in dataclasses.fields(CRTConfig)]


def test_no_crtconfig_field_has_a_default():
    with_default = [
        f.name for f in dataclasses.fields(CRTConfig)
        if f.default is not dataclasses.MISSING or f.default_factory is not dataclasses.MISSING
    ]
    assert with_default == []
    with pytest.raises(TypeError):
        CRTConfig()


def test_bare_build_fails_closed_listing_every_field():
    with pytest.raises(ConfigKeyMissingError) as ei:
        ConfigBuilder.build("XAUUSD")
    assert set(ei.value.missing) == set(FIELDS)


@pytest.mark.parametrize("field", FIELDS)
def test_build_missing_any_one_field_fails_closed(field):
    fields = crt_test_fields()
    fields.pop(field)
    with pytest.raises(ConfigKeyMissingError) as ei:
        ConfigBuilder.build("XAUUSD", overrides=fields)
    assert ei.value.missing == (field,)


def test_build_complete_field_set_ok_and_unknown_instrument_rejected():
    cfg = ConfigBuilder.build("XAUUSD", overrides=crt_test_fields())
    assert isinstance(cfg, CRTConfig)
    with pytest.raises(UnknownInstrumentError):
        ConfigBuilder.build("NOT_A_SYMBOL", overrides=crt_test_fields())


def test_from_production_equals_the_registry_and_applies_overrides():
    prod = load_prod_config_from_registry(get_active_version(), "XAUUSD")
    assert dataclasses.asdict(ConfigBuilder.from_production("XAUUSD")) == dataclasses.asdict(prod)
    tuned = ConfigBuilder.from_production("XAUUSD", overrides={"score_threshold": 0.61})
    assert tuned.score_threshold == 0.61
    assert tuned.sl_atr_buffer == prod.sl_atr_buffer
    with pytest.raises(ValueError, match="unknown override key"):
        ConfigBuilder.from_production("XAUUSD", overrides={"nope": 1})


def test_from_existing_keeps_every_field_without_a_router_base():
    prod = load_prod_config_from_registry(get_active_version(), "XAUUSD")
    out = ConfigBuilder.from_existing("XAUUSD", prod, extra_overrides={"body_ratio_min": 0.55})
    expect = dataclasses.asdict(prod) | {"body_ratio_min": 0.55}
    assert dataclasses.asdict(out) == expect
