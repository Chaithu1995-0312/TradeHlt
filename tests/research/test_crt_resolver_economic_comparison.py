"""
CRT resolver vs engine economic comparison — behavioral floor.

Exercises scripts/research/crt_resolver_economic_comparison.py (F-069 follow-up).
Skips the corpus-dependent tests entirely if the real XAUUSD M15 corpus / engine
run directory is absent (per standing instruction, this program never
substitutes another instrument). The pure-logic tests (transition detection,
direction fallback, SL formula, inversion rejection) run unconditionally with
synthetic fixtures.
"""
from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO / "scripts" / "research" / "crt_resolver_economic_comparison.py"
_ENGINE_TRADES_CSV = (_REPO / "results" / "run_20260805_105350_XAUUSD" / "XAUUSD_trades.csv")
_OHLCV = _REPO / "data" / "mt5" / "XAUUSD_M15.csv"


def _load_module():
    spec = importlib.util.spec_from_file_location("crt_resolver_economic_comparison", _MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["crt_resolver_economic_comparison"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def m():
    if not _MODULE_PATH.exists():
        pytest.skip("crt_resolver_economic_comparison.py not present")
    return _load_module()


@dataclass
class _FakeMemory:
    displacement_direction: int = 0
    pending_displacement_dir: str = "NONE"
    displacement_candle_index: int = -1


class TestExpansionEntryDetection:
    """The detector must fire on transitions INTO EXPANSION, never on
    occupancy of an already-EXPANSION bar."""

    def test_detects_transition_not_occupancy(self, m):
        states = ["RANGE", "SWEEP", "EXPANSION", "EXPANSION", "RANGE", "EXPANSION"]
        # Build minimal fixtures so build_expansion_entry_signals can run
        # without hitting real-corpus-only code paths (ATR/raw_df access).
        import pandas as pd
        memories = [
            _FakeMemory(displacement_direction=1) if s == "EXPANSION" else _FakeMemory()
            for s in states
        ]
        atr_abs_list = [1.0] * len(states)
        trend_bias_list = [0.0] * len(states)
        source_indices = list(range(len(states)))
        raw_df = pd.DataFrame({
            "low": [100.0] * len(states), "high": [110.0] * len(states),
            "close": [105.0] * len(states),
        })
        signals, counters = m.build_expansion_entry_signals(
            states, memories, atr_abs_list, trend_bias_list, source_indices, raw_df,
            sl_atr_buffer=0.2, tp1_atr_multiplier=1.0,
        )
        # Entries at index 2 and 5 only — index 3 is occupancy, must not count.
        assert counters["entries_found"] == 2
        assert len(signals) == 2
        assert {s.entry_index for s in signals} == {2, 5}


class TestDirectionFallback:
    """Direction falls back memory -> pending_shadow -> trend_bias,
    deterministically, and skips (never guesses) when all three are empty."""

    def _run_single_entry(self, m, mem: _FakeMemory, trend_bias: float, atr: float = 1.0):
        import pandas as pd
        states = ["RANGE", "EXPANSION"]
        memories = [_FakeMemory(), mem]
        atr_abs_list = [1.0, atr]
        trend_bias_list = [0.0, trend_bias]
        source_indices = [0, 1]
        raw_df = pd.DataFrame({"low": [100.0, 100.0], "high": [110.0, 110.0],
                                "close": [105.0, 105.0]})
        return m.build_expansion_entry_signals(
            states, memories, atr_abs_list, trend_bias_list, source_indices, raw_df,
            sl_atr_buffer=0.2, tp1_atr_multiplier=1.0,
        )

    def test_uses_memory_direction_when_present(self, m):
        mem = _FakeMemory(displacement_direction=1)
        signals, counters = self._run_single_entry(m, mem, trend_bias=-5.0)
        assert len(signals) == 1
        assert signals[0].direction == "long"  # memory wins over trend_bias
        assert counters["direction_source_memory"] == 1

    def test_falls_back_to_pending_shadow(self, m):
        mem = _FakeMemory(displacement_direction=0, pending_displacement_dir="SHORT")
        signals, counters = self._run_single_entry(m, mem, trend_bias=5.0)
        assert len(signals) == 1
        assert signals[0].direction == "short"  # pending_shadow wins over trend_bias
        assert counters["direction_source_pending_shadow"] == 1

    def test_falls_back_to_trend_bias(self, m):
        mem = _FakeMemory(displacement_direction=0, pending_displacement_dir="NONE")
        signals, counters = self._run_single_entry(m, mem, trend_bias=3.0)
        assert len(signals) == 1
        assert signals[0].direction == "long"
        assert counters["direction_source_trend_bias_fallback"] == 1

    def test_skips_when_all_three_empty(self, m):
        mem = _FakeMemory(displacement_direction=0, pending_displacement_dir="NONE")
        signals, counters = self._run_single_entry(m, mem, trend_bias=0.0)
        assert len(signals) == 0
        assert counters["skipped_no_direction"] == 1

    def test_deterministic_across_repeated_calls(self, m):
        mem = _FakeMemory(displacement_direction=0, pending_displacement_dir="LONG")
        r1, _ = self._run_single_entry(m, mem, trend_bias=-1.0)
        r2, _ = self._run_single_entry(m, mem, trend_bias=-1.0)
        assert r1[0].direction == r2[0].direction == "long"


class TestSLConstruction:
    """SL formula must match the engine's shape byte-for-byte on a
    hand-built synthetic bar, and inverted SLs must be rejected and counted."""

    def test_sl_matches_engine_formula_long(self, m):
        import pandas as pd
        states = ["RANGE", "EXPANSION"]
        memories = [_FakeMemory(), _FakeMemory(displacement_direction=1)]
        atr_abs_list = [1.0, 2.0]
        trend_bias_list = [0.0, 0.0]
        source_indices = [0, 1]
        raw_df = pd.DataFrame({"low": [100.0, 100.0], "high": [105.0, 105.0],
                                "close": [104.0, 104.0]})
        signals, _ = m.build_expansion_entry_signals(
            states, memories, atr_abs_list, trend_bias_list, source_indices, raw_df,
            sl_atr_buffer=0.2, tp1_atr_multiplier=1.0,
        )
        # No displacement candle trackable (displacement_candle_index=-1) ->
        # falls back to the entry bar's own low: sl = 100.0 - 0.2*2.0 = 99.6
        assert len(signals) == 1
        assert signals[0].sl_raw == pytest.approx(99.6)
        assert signals[0].meta["sl_anchor_source"] == "entry_bar_fallback"

    def test_inverted_sl_rejected_and_counted(self, m):
        import pandas as pd
        # Construct a pathological case: entry close BELOW the anchor low minus
        # buffer would normally be fine for LONG; force inversion by making the
        # entry bar's low far ABOVE its own close (synthetic, not realistic
        # OHLC, but isolates the inversion-guard logic under test).
        states = ["RANGE", "EXPANSION"]
        memories = [_FakeMemory(), _FakeMemory(displacement_direction=1)]
        atr_abs_list = [1.0, 0.01]  # tiny buffer
        trend_bias_list = [0.0, 0.0]
        source_indices = [0, 1]
        raw_df = pd.DataFrame({"low": [200.0, 200.0], "high": [205.0, 205.0],
                                "close": [100.0, 100.0]})  # close << low: inverted
        signals, counters = m.build_expansion_entry_signals(
            states, memories, atr_abs_list, trend_bias_list, source_indices, raw_df,
            sl_atr_buffer=0.2, tp1_atr_multiplier=1.0,
        )
        assert len(signals) == 0
        assert counters["rejected_inverted_sl"] == 1


@pytest.mark.slow
class TestEngineLedgerRealCsv:
    def test_parses_real_trades_csv_to_expected_row(self, m):
        if not _ENGINE_TRADES_CSV.exists():
            pytest.skip(f"engine trades fixture not present: {_ENGINE_TRADES_CSV}")
        trades = m.load_engine_trades(_ENGINE_TRADES_CSV)
        assert len(trades) == 1
        t = trades[0]
        assert t.direction == "long"
        assert abs(t.pnl_rr_net - (-0.0383)) < 1e-3
        assert abs(t.entry_raw - 2318.21) < 1e-2


class TestBootstrapDegenerateCI:
    def test_n1_ci_is_degenerate_and_marked(self, m):
        from research.measurement.bootstrap import bootstrap_ci, seed_from_key
        seed = seed_from_key("crt_resolver_economic_comparison_v1")
        lo, hi = bootstrap_ci([0.5028], n_boot=100, alpha=0.05, seed=seed)
        assert lo == hi == pytest.approx(0.5028)


class TestReportStructure:
    def test_methodology_precedes_comparison_table(self, m, tmp_path):
        from research.contracts import Outcome, Signal
        from datetime import datetime

        sig = Signal(instrument="XAUUSD", timestamp=datetime(2024, 1, 1),
                     entry_index=0, direction="long", entry=100.0,
                     sl_atr_mult=1.0, tp_atr_mult=1.0, atr=1.0,
                     meta={"native_pnl_rr_net": -0.01})
        outcome = Outcome(signal=sig, outcome="SL_HIT", rr_achieved=-1.0, mfe=0.0,
                           mae=-1.0, duration_candles=1, time_to_tp=None,
                           time_to_failure=1, reached_1r=False)
        comparison = m.compare([outcome], [outcome])

        @dataclass
        class _FakeTrade:
            entry_raw: float = 100.0
            sl: float = 99.0

        out_path = tmp_path / "report.md"
        m.write_report(
            out_path, comparison=comparison, engine_provenance={"trades_csv": "x", "mode": "reuse"},
            resolver_counters={"entries_found": 1}, forward_walk_counters={},
            engine_trades=[_FakeTrade()], corpus_path=Path("x.csv"),
        )
        text = out_path.read_text(encoding="utf-8")
        assert "## Methodology" in text
        assert "## Comparison table" in text
        assert text.index("## Methodology") < text.index("## Comparison table")
