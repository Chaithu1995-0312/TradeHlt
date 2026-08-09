"""P6 floors — SpineProjector, ledger honesty, and the parity the data supports.

The plan's stated blocking floor was "episode MFE/MAE == TradePathStats.mfe_price/
mae_price per trade". The ledger probe found that oracle is NOT PERSISTED, so that
floor is not executable against real artifacts. These tests pin what replaced it:

  * `probe_ledger` REPORTS the gap instead of a caller assuming the field exists
  * entry-geometry parity validates the JOIN exactly (the precondition for any claim)
  * aggregate path parity is the strongest remaining check, and labels itself weaker
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from research.episodes.projectors.spine import (
    PATH_ORACLE_COLUMNS,
    POPULATION,
    aggregate_path_parity,
    entry_geometry_parity,
    probe_ledger,
    project_ledger,
    project_trade,
    read_ledger,
)


class Bar:
    def __init__(self, i, o, h, low, c, v=1.0):
        self.index, self.open, self.high, self.low, self.close, self.volume = i, o, h, low, c, v
        self.timestamp = f"2026-01-01 {i // 4:02d}:{(i % 4) * 15:02d}:00"


CANDLES = [Bar(i, 100.0 + i, 101.0 + i, 99.0 + i, 100.5 + i) for i in range(12)]
TS_TO_IDX = {b.timestamp: b.index for b in CANDLES}


def _row(**over):
    base = {
        "trade_id": "CRT-0001", "instrument": "T", "direction": "LONG",
        "entry_raw": "100.0", "sl": "98.0", "tp1": "104.0", "tp2": "106.0",
        "exit_fill": "104.2", "exit_reason": "TP2", "duration_candles": "4",
        "pnl_rr_raw": "2.0", "pnl_rr_net": "1.9",
        "opened_at": "2026-01-01T00:00:00", "closed_at": "2026-01-01T01:00:00",
        # the +1 convention measured on the real ledger
        "candle_idx": "1", "config_version": "v2_multi_2026_04",
        "session": "LONDON", "risk_score": "0.5", "live_atr": "1.5",
    }
    base.update(over)
    return base


# ── ledger probe ─────────────────────────────────────────────────────────
def test_probe_reports_a_missing_path_oracle_rather_than_assuming_it():
    p = probe_ledger([_row()])
    assert p["required_present"] is True
    assert p["path_oracle_present"] is False
    assert p["per_trade_path_parity_executable"] is False
    assert "not emitted by TradeJournal.to_csv_rows()" in p["note"]


def test_probe_detects_an_oracle_when_one_exists():
    enriched = _row()
    enriched.update({c: "0.0" for c in PATH_ORACLE_COLUMNS})
    p = probe_ledger([enriched])
    assert p["path_oracle_present"] is True
    assert p["per_trade_path_parity_executable"] is True
    assert sorted(p["path_oracle_columns_found"]) == sorted(PATH_ORACLE_COLUMNS)


def test_probe_flags_missing_required_columns():
    row = _row()
    del row["sl"]
    p = probe_ledger([row])
    assert p["required_present"] is False and "sl" in p["missing_required"]


def test_probe_handles_an_empty_ledger():
    assert probe_ledger([])["n_rows"] == 0


# ── projection ───────────────────────────────────────────────────────────
def test_projects_a_spine_trade_episode():
    ep, reason = project_trade(_row(), CANDLES, TS_TO_IDX, instrument="T", max_forward=6)
    assert reason is None
    assert ep.population == POPULATION
    assert ep.entry.entry_price == 100.0 and ep.entry.sl_price == 98.0
    assert ep.entry.tp_price == 104.0          # tp1 only — OE_L1 is single-TP
    assert ep.entry.atr_entry == 1.5
    assert ep.steps[0].obs.bar_index == 0      # anchored on opened_at, not candle_idx


def test_join_is_by_timestamp_not_the_offset_candle_idx():
    """candle_idx runs +1 vs opened_at on the real ledger; the join must not use it."""
    ep, _ = project_trade(_row(candle_idx="999"), CANDLES, TS_TO_IDX,
                          instrument="T", max_forward=6)
    assert ep.entry.bar_index == 0
    assert ep.metadata["ledger"]["candle_idx_offset_vs_timestamp"] == 999


def test_observed_offset_is_recorded_for_audit():
    ep, _ = project_trade(_row(), CANDLES, TS_TO_IDX, instrument="T", max_forward=6)
    assert ep.metadata["ledger"]["candle_idx_offset_vs_timestamp"] == 1


def test_tp2_is_preserved_as_a_diagnostic_never_folded_into_geometry():
    ep, _ = project_trade(_row(), CANDLES, TS_TO_IDX, instrument="T", max_forward=6)
    assert ep.entry.tp_price == 104.0
    assert ep.metadata["ledger"]["tp2"] == "106.0"


def test_spine_outcome_is_quarantined_with_a_comparability_warning():
    """The ledger's outcome comes from a multi-level, stop-moving model (F-056)."""
    ep, _ = project_trade(_row(), CANDLES, TS_TO_IDX, instrument="T", max_forward=6)
    led = ep.metadata["ledger"]
    assert led["exit_reason"] == "TP2" and led["pnl_rr_net"] == "1.9"
    assert "MULTI-LEVEL" in led["_warning"]
    # and none of it reached a canonical field
    assert "exit_reason" not in ep.entry.__dict__
    assert ep.entry.feature_vector is None


@pytest.mark.parametrize("over,expected", [
    ({"direction": "sideways"}, "bad_direction"),
    ({"entry_raw": "100.0", "sl": "100.0"}, "bad_geometry"),
    ({"opened_at": "1999-01-01T00:00:00"}, "no_candle_ts"),
    ({"sl": ""}, "missing_columns"),
])
def test_skip_reasons(over, expected):
    ep, reason = project_trade(_row(**over), CANDLES, TS_TO_IDX, instrument="T")
    assert ep is None and reason.split(":")[0] == expected


def test_project_ledger_counts_skips():
    rows = [_row(), _row(trade_id="X", direction="sideways")]
    eps, skips = project_ledger(rows, CANDLES, TS_TO_IDX, instrument="T", max_forward=6)
    assert len(eps) == 1 and skips == {"bad_direction": 1}


# ── parity ───────────────────────────────────────────────────────────────
def test_entry_geometry_parity_passes_on_a_correct_join():
    rows = [_row()]
    eps, _ = project_ledger(rows, CANDLES, TS_TO_IDX, instrument="T", max_forward=6)
    assert entry_geometry_parity(eps, rows, CANDLES)["ok"] is True


def test_entry_geometry_parity_catches_a_corrupted_ledger():
    rows = [_row()]
    eps, _ = project_ledger(rows, CANDLES, TS_TO_IDX, instrument="T", max_forward=6)
    tampered = [_row(entry_raw="123.45")]
    result = entry_geometry_parity(eps, tampered, CANDLES)
    assert result["ok"] is False
    assert "entry_price" in result["mismatches"][0]["failed"]


def test_aggregate_parity_labels_itself_as_weaker_evidence():
    rows = [_row()]
    eps, _ = project_ledger(rows, CANDLES, TS_TO_IDX, instrument="T", max_forward=6)
    out = aggregate_path_parity(eps, rows, survival={})
    assert out["strength"].startswith("AGGREGATE_ONLY")
    assert out["n_compared"] == 0        # nothing to compare against an empty summary


def test_aggregate_parity_truncates_at_realized_duration():
    """TradePathStats stops at close; an episode keeps walking. Truncate to compare."""
    rows = [_row(duration_candles="2")]
    eps, _ = project_ledger(rows, CANDLES, TS_TO_IDX, instrument="T", max_forward=10)
    short = aggregate_path_parity(eps, rows, survival={})["comparison"]["mfe_rr_p50"]
    rows_long = [_row(duration_candles="9")]
    long = aggregate_path_parity(eps, rows_long, survival={})["comparison"]["mfe_rr_p50"]
    assert long["episode_derived"] > short["episode_derived"]


# ═══════════════ REAL LEDGER (skips when absent) ═══════════════
ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / "results" / "backtest" / "BNBUSDT_gateON_2026_07_04" / "run_20260704_034601_BNBUSDT"
TRADES = RUN / "BNBUSDT_trades.csv"
SUMMARY = RUN / "BNBUSDT_summary.json"
CANDLE_CSV = ROOT / "data" / "BNBUSDT_M15.csv"

_real = pytest.mark.skipif(
    not (TRADES.is_file() and SUMMARY.is_file() and CANDLE_CSV.is_file()),
    reason="reference backtest run not present (results/ and data/ are untracked)",
)


@pytest.fixture(scope="module")
def real():
    import sys

    sys.path.insert(0, str(ROOT / "scripts" / "analysis"))
    from bnbusdt_trade_anatomy import load_candles

    candles, ts_to_idx, _ = load_candles(CANDLE_CSV)
    rows = read_ledger(TRADES)
    eps, skips = project_ledger(rows, candles, ts_to_idx, instrument="BNBUSDT")
    return rows, candles, eps, skips


@_real
def test_real_ledger_probe_confirms_the_documented_gap(real):
    rows, *_ = real
    p = probe_ledger(rows)
    assert p["n_rows"] == 11 and p["n_columns"] == 76
    assert p["required_present"] is True
    assert p["per_trade_path_parity_executable"] is False


@_real
def test_real_ledger_projects_every_trade(real):
    rows, _, eps, skips = real
    assert len(eps) == len(rows) == 11
    assert skips == {}


@_real
def test_real_candle_idx_offset_is_uniformly_plus_one(real):
    _, _, eps, _ = real
    offsets = {e.metadata["ledger"]["candle_idx_offset_vs_timestamp"] for e in eps}
    assert offsets == {1}, f"ledger index convention changed: {offsets}"


@_real
def test_real_entry_geometry_parity_is_exact(real):
    rows, candles, eps, _ = real
    result = entry_geometry_parity(eps, rows, candles)
    assert result["ok"] is True, result["mismatches"]
    assert result["n"] == 11


@_real
def test_real_aggregate_path_parity_matches_the_ledger_summary(real):
    """All 5 survival statistics reproduce to the summary's own 6-dp rounding.

    Measured 2026-07-23: mfe_rr_p50/p90, mae_rr_p50/p90 and median_bars_to_peak all
    agree within ~1e-7 — i.e. the episode's MFE/MAE tracking is numerically identical
    to the hot-loop TradePathStats, verified at the only resolution persisted.
    """
    rows, _, eps, _ = real
    survival = json.loads(SUMMARY.read_text(encoding="utf-8"))[
        "distribution"]["metrics_v2"]["survival"]
    out = aggregate_path_parity(eps, rows, survival, tol=1e-6)
    assert out["n"] == 11
    assert out["n_compared"] == 5
    assert out["n_agree"] == 5, out["comparison"]


@_real
def test_real_ledger_has_no_path_oracle_columns(real):
    """Pins the gap: if TradeJournal ever emits path stats, this goes red and the
    stronger per-trade floor becomes available."""
    rows, *_ = real
    with TRADES.open(encoding="utf-8", newline="") as fh:
        cols = set(next(csv.reader(fh)))
    assert not (set(PATH_ORACLE_COLUMNS) & cols)
