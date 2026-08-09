"""
Tests for ``runtime.unified_replay_harness`` helpers.

``test_derive_symbol_from_filename`` was relocated here from
``tests/test_zone_gate.py``, where it was the only executing test in a file whose
remaining eight tests were inert. It never exercised ZoneGate code — it tests the
replay harness's symbol-derivation helper — so it was filed under the wrong subject.
"""

from runtime.unified_replay_harness import _derive_symbol_from_data_path


def test_derive_symbol_from_filename():
    assert _derive_symbol_from_data_path("data/AUDUSD_M15.csv") == "AUDUSD"
    assert _derive_symbol_from_data_path("D:/x/EURUSD.csv") == "EURUSD"
    assert _derive_symbol_from_data_path("BTCUSDT_M5.csv") == "BTCUSDT"
