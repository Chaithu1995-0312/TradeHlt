"""Phase 4 — entry-point import smoke (catches syntax/wiring errors without live MT5)."""
from __future__ import annotations


def test_thin_shells_import():
    from mt5_analytics.core import daemon, rebuild, triggers  # noqa: F401

    assert callable(rebuild.run) and callable(rebuild.main)
    assert callable(daemon.tick) and callable(daemon.run)
    assert triggers.has_new_deals(0, 1) is True
    assert triggers.is_new_m15_bar(100, 200) is True
    assert triggers.has_new_deals(5, 5) is False
