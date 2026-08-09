"""
Model shadow protocol floor (target-strategy-architecture.md §13 item7 / §14.E).

model_shadow_protocol.py generalizes scripts/research/bitnet_shadow_diagnostic.py
(which is left unchanged, as the frozen BitNet-specific record) into a reusable
(off_config, on_config, instruments, label) A/B. These tests exercise the pure
stats/EdgeReport-shim logic directly — a full end-to-end run additionally
requires a real spine corpus + a fully-populated production config pair, which
is an integration concern (see NOTE below), not what these tests pin.

NOTE (found while wiring Phase G, not a regression): the pre-existing
`configs/production/v2_multi_bitnet_shadow_2026_07.json` is missing a
`feature_pipeline` section and so FAILS an end-to-end run through
`ProductionSpineSource` — identically for both the original
bitnet_shadow_diagnostic.py (unmodified) and this generalized script. This is a
pre-existing config-completeness gap in that one historical shadow file, not
something introduced here.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "research"))

from model_shadow_protocol import _stats, _stats_to_edge_report  # noqa: E402


class _FakeEntry:
    def __init__(self, rr: float):
        self.meta = {"backtest_pnl_rr_net": rr}


def test_stats_computes_expectancy_and_pf():
    entries = [_FakeEntry(1.5), _FakeEntry(-1.0), _FakeEntry(2.0), _FakeEntry(-0.5)]
    s = _stats(entries)
    assert s["n"] == 4
    assert s["win_rate"] == 0.5
    assert s["expectancy_rr"] == 0.5
    assert s["profit_factor"] == 2.3333  # (1.5+2.0)/(1.0+0.5), rounded to 4dp


def test_stats_empty_book():
    s = _stats([])
    assert s["n"] == 0
    assert s["expectancy_rr"] is None


def test_stats_to_edge_report_none_on_empty_book():
    assert _stats_to_edge_report("x", _stats([])) is None


def test_stats_to_edge_report_shim_carries_only_measured_fields():
    s = _stats([_FakeEntry(1.0), _FakeEntry(-1.0)])
    edge = _stats_to_edge_report("bitnet_on", s)
    assert edge is not None
    assert edge.n == 2
    assert edge.win_rate == s["win_rate"]
    assert edge.expectancy_rr == s["expectancy_rr"]
    # Unmeasured-by-this-diagnostic fields are honest zero placeholders, not claims.
    assert edge.mfe_p50 == 0.0 and edge.max_drawdown_rr == 0.0


def test_scope_language_present_and_no_config_write_call():
    """Never-writes-enable-flag scope statement must survive refactors, and the
    module must contain no call that opens a production config file for writing."""
    src = Path(__file__).resolve().parents[1] / "scripts" / "research" / "model_shadow_protocol.py"
    text = src.read_text(encoding="utf-8")
    assert "never writes" in text.lower()
    assert 'open(' not in text or 'json.dumps(report' in text  # only writes its OWN report file
    assert "configs/production" not in text.replace("research_config", "")  # no prod-config path literal
