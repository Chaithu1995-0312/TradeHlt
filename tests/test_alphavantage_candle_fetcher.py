"""EPIC-84 L-C (src/inout): AlphaVantageFetcherConfig has no code defaults.

request_delay_s used to fall back to a code literal (1.2) via a dataclass field
default and a `.get(key, 1.2)` read; both are now required, matching every other
field this config already reads through the module's own `_require` helper.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from inout.alphavantage_candle_fetcher import AlphaVantageFetcherConfig  # noqa: E402

_SECTION = {
    "api_key": "demo",
    "from_symbol": "aud",
    "to_symbol": "usd",
    "interval": "15min",
    "start_date": "2024-01-01",
    "end_date": "2025-01-01",
    "output_dir": "data/alphavantage",
    "request_delay_s": 1.2,
}


def test_from_section_reads_declared_request_delay_s():
    cfg = AlphaVantageFetcherConfig.from_section(dict(_SECTION))
    assert cfg.request_delay_s == 1.2


@pytest.mark.parametrize("key", sorted(_SECTION))
def test_from_section_missing_key_raises(key):
    section = {k: v for k, v in _SECTION.items() if k != key}
    with pytest.raises(KeyError):
        AlphaVantageFetcherConfig.from_section(section)
