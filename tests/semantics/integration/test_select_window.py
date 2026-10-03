"""R1-C selection is deterministic, maximises lifecycle coverage, then minimises bars."""

from __future__ import annotations

from datetime import datetime, timedelta

from semantics.integration.select_window import EngineTrade, choose_window, satisfied, unavailable, write_slice

T0 = datetime(2026, 1, 5, 0, 0)


def _ts(i):
    return T0 + timedelta(minutes=15 * i)


def _trade(i, open_bar, close_bar, direction, reason):
    return EngineTrade(f"CRT-{i:04d}", direction, reason, _ts(open_bar), _ts(close_bar))


STAMPS = [_ts(i) for i in range(400)]
SWEEPS = [_ts(b) for b in (8, 48, 98, 198, 298)]


def test_lifecycle_tags():
    assert _trade(1, 10, 12, "LONG", "STOPPED").lifecycle == {"trade", "long", "stop_exit"}
    assert _trade(1, 10, 12, "SHORT", "TP1_TP2").lifecycle == {"trade", "short", "tp1", "tp2"}
    assert _trade(1, 10, 12, "LONG", "TP1_BE_STOP").lifecycle == {"trade", "long", "stop_exit", "tp1"}


def test_widest_coverage_then_fewest_bars_then_earliest():
    trades = [
        _trade(1, 10, 20, "LONG", "STOPPED"),
        _trade(2, 50, 60, "SHORT", "TP1_TP2"),       # 1+2: all six hard criteria
        _trade(3, 100, 110, "LONG", "STOPPED"),
        _trade(4, 200, 205, "SHORT", "TP1_TP2"),     # 3+4 also all six, but a wider window
    ]
    w = choose_window(trades, STAMPS, SWEEPS, lead_bars=5)
    assert (w.first, w.last) == (0, 1)
    assert w.satisfied == ["trade", "long", "short", "stop_exit", "tp1", "tp2", "multiple_trades"]
    assert choose_window(trades, STAMPS, SWEEPS, lead_bars=5).__dict__ == w.__dict__   # deterministic


def test_missing_criteria_are_reported_not_manufactured():
    trades = [_trade(1, 10, 20, "LONG", "STOPPED"), _trade(2, 50, 60, "LONG", "TP1_BE_STOP")]
    w = choose_window(trades, STAMPS, SWEEPS, lead_bars=5)
    missing = unavailable(trades, w)
    assert any(m.startswith("short (not in the corpus") for m in missing)
    assert any(m.startswith("tp2 (not in the corpus") for m in missing)
    assert "multiple_trades" in satisfied(trades)


def test_count_clock_grid_aligns_the_start_row():
    trades = [_trade(1, 50, 60, "LONG", "STOPPED")]
    w = choose_window(trades, STAMPS, SWEEPS, lead_bars=5, grid=16)
    assert w.start_row % 16 == 0 and w.start_row <= 48 - 5


def test_a_slice_never_overwrites_a_different_cut(tmp_path):
    corpus = tmp_path / "XAUUSD_M15.csv"
    header = "timestamp,open,high,low,close,volume"
    rows = [f"2026-01-05 {i // 4:02d}:{15 * (i % 4):02d}:00,1,2,0,1,10" for i in range(40)]
    corpus.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")
    first = write_slice(corpus, 10, 20, tmp_path)
    again = write_slice(corpus, 10, 20, tmp_path)
    other = write_slice(corpus, 12, 20, tmp_path)
    assert first == again and other != first and other.name.endswith("-r12.csv")
    assert len(first.read_text(encoding="utf-8").splitlines()) == 12
