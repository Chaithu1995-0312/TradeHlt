"""EPIC-84 L-C (src/inout): HummingbotFetcherConfig has no code defaults.

instruments/max_records_per_request used to fall back to code literals
([] / 500) via dataclass field defaults and `.get(key, literal)` reads in both
from_prod_config() and from_section(); all four are now required, matching
every other field this config already reads through the module's `_require`
helper.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from inout.hummingbot_candle_fetcher import HummingbotFetcherConfig  # noqa: E402

_SECTION = {
    "exchange": "binance",
    "trading_pair": "BTCUSDT",
    "interval": "15m",
    "start_date": "2024-01-01",
    "end_date": "2025-12-31",
    "output_dir": "data/hummingbot",
    "instruments": ["BTCUSDT", "ETHUSDT"],
    "max_records_per_request": 500,
}


def test_from_section_reads_declared_values():
    cfg = HummingbotFetcherConfig.from_section(dict(_SECTION))
    assert cfg.instruments == ["BTCUSDT", "ETHUSDT"]
    assert cfg.max_records_per_request == 500


def test_from_prod_config_reads_declared_values():
    cfg = HummingbotFetcherConfig.from_prod_config({"hummingbot_data": dict(_SECTION)})
    assert cfg.instruments == ["BTCUSDT", "ETHUSDT"]
    assert cfg.max_records_per_request == 500


@pytest.mark.parametrize("key", sorted(_SECTION))
def test_from_section_missing_key_raises(key):
    section = {k: v for k, v in _SECTION.items() if k != key}
    with pytest.raises(KeyError):
        HummingbotFetcherConfig.from_section(section)


@pytest.mark.parametrize("key", sorted(_SECTION))
def test_from_prod_config_missing_key_raises(key):
    section = {k: v for k, v in _SECTION.items() if k != key}
    with pytest.raises(KeyError):
        HummingbotFetcherConfig.from_prod_config({"hummingbot_data": section})


def test_fetch_all_instruments_falls_back_to_trading_pair_when_instruments_empty():
    """Declared instruments=[] means single-instrument mode (documented, not a
    config-authoring omission) — this is application logic, not a config read."""
    section = dict(_SECTION)
    section["instruments"] = []
    cfg = HummingbotFetcherConfig.from_section(section)
    assert cfg.instruments == []
    assert (cfg.instruments or [cfg.trading_pair]) == ["BTCUSDT"]
