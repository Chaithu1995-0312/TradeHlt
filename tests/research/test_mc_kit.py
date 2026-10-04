"""Parity pins for `research.mc_kit` — sealed-contract driver primitives.

Research-framework consolidation Phase 3. Every primitive here replaces logic duplicated (exactly,
or computationally with different statement order) across the trade-contract drivers
(`research.mother_range.driver`, `research.sujan_crt.driver`) and the prior-contract drivers
(`research.evidence.mother_range_prior`, `research.evidence.magnitude_prior`). Each replaced
variant is copied here VERBATIM (originals archived under archive/research_framework_phase3*/)
and compared against the kit on the same inputs — proof by output equivalence, not AST identity,
since two of the four variants restructure the same computation into different local variables.
"""
from __future__ import annotations

import csv
import math
import random
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from research import mc_kit
from research.mc_kit import bars as kit_bars
from research.mc_kit import stats as kit_stats
from research.mc_kit import trade as kit_trade
from research.costs import xau_measured_cost_model
from research.contracts import Signal
from research.measurement.forward_walk import AdverseFill


# ── verbatim originals ──────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class _Bar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    index: int


def _orig_parse_ts(raw: str) -> datetime:
    s = raw.strip().replace("T", " ")
    return datetime.fromisoformat(s[:19])


def _orig_load_bars_required(path: Path) -> list[_Bar]:
    """Verbatim `mother_range.driver.load_bars` / `evidence.mother_range_prior.load_bars`."""
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    out: list[_Bar] = []
    for i, row in enumerate(rows):
        out.append(_Bar(
            timestamp=_orig_parse_ts(row["timestamp"]), open=float(row["open"]),
            high=float(row["high"]), low=float(row["low"]), close=float(row["close"]),
            volume=float(row["volume"]), index=i,
        ))
    return out


def _orig_load_bars_zero_default(path: Path) -> list[_Bar]:
    """Verbatim `sujan_crt.driver.load_bars`."""
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    out: list[_Bar] = []
    for i, row in enumerate(rows):
        out.append(_Bar(
            timestamp=_orig_parse_ts(row["timestamp"]), open=float(row["open"]),
            high=float(row["high"]), low=float(row["low"]), close=float(row["close"]),
            volume=float(row.get("volume") or 0.0), index=i,
        ))
    return out


def _orig_exit_kind(outcome: str) -> str:
    return "SL_HIT" if outcome == "SL_HIT" else ("TP_HIT" if outcome == "TP_HIT" else "TIMEOUT")


def _orig_trade_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    if n == 0:
        return {"n": 0, "gross_mean": None, "net_mean": None, "win_rate": None, "pf": None}
    gross = [float(r["y_R_gross"]) for r in rows]
    net = [float(r["y_R_net"]) for r in rows]
    wins = [g for g in gross if g > 0]
    losses = [g for g in gross if g < 0]
    gp = sum(wins)
    gl = abs(sum(losses))
    pf = (gp / gl) if gl > 0 else (float("inf") if gp > 0 else 0.0)
    return {"n": n, "gross_mean": sum(gross) / n, "net_mean": sum(net) / n,
            "win_rate": sum(1 for g in gross if g > 0) / n, "pf": pf}


def _mean(xs: list[float]):
    """Verbatim `research.evidence.queries._mean` — `statistics.mean`, NOT naive `sum()/len()`.
    The distinction is load-bearing: an earlier draft of this test used naive summation here,
    which happened to agree with `statistics.mean` on small synthetic inputs but silently
    diverged in the last bit on the real `mother_range_prior` corpus (n=100+) — caught only by
    the Phase-3 end-to-end byte-identity gate, not by this unit test, until `test_arm_cells_mean_matches_statistics_mean_not_naive_sum` below was added specifically to close that gap."""
    return statistics.mean(xs) if xs else None


# variant A — mother_range_prior._arm_cells (inline contrast + inline list comps)
def _orig_arm_cells_a(rows, y_key):
    agree_xs, disag_xs, n_zero, n_null_y = [], [], 0, 0
    for r in rows:
        y = r.get(y_key)
        if y is None:
            n_null_y += 1
            continue
        if r.get("agree") is None:
            n_zero += 1
            continue
        (agree_xs if r["agree"] else disag_xs).append(float(y))
    ea, ed = _mean(agree_xs), _mean(disag_xs)
    return {
        "agree": {"n": len(agree_xs), "mean": ea,
                  "p_gt_0": (sum(1 for x in agree_xs if x > 0) / len(agree_xs)) if agree_xs else None,
                  "e_given_gt_0": _mean([x for x in agree_xs if x > 0])},
        "disagree": {"n": len(disag_xs), "mean": ed,
                     "p_gt_0": (sum(1 for x in disag_xs if x > 0) / len(disag_xs)) if disag_xs else None,
                     "e_given_gt_0": _mean([x for x in disag_xs if x > 0])},
        "contrast": None if ea is None or ed is None else ea - ed,
        "n_trend_zero_or_unknown": n_zero, "n_null_y": n_null_y,
    }


# variant B — magnitude_prior._arm_cells (precomputes contrast/pos_a/pos_d as locals)
def _orig_arm_cells_b(rows, y_key):
    agree_xs, disag_xs, n_zero, n_null_y = [], [], 0, 0
    for r in rows:
        y = r.get(y_key)
        if y is None:
            n_null_y += 1
            continue
        if r.get("agree") is None:
            n_zero += 1
            continue
        (agree_xs if r["agree"] else disag_xs).append(float(y))
    ea, ed = _mean(agree_xs), _mean(disag_xs)
    contrast = None if ea is None or ed is None else ea - ed
    pos_a = [x for x in agree_xs if x > 0]
    pos_d = [x for x in disag_xs if x > 0]
    return {
        "agree": {"n": len(agree_xs), "mean": ea,
                  "p_gt_0": (sum(1 for x in agree_xs if x > 0) / len(agree_xs)) if agree_xs else None,
                  "e_given_gt_0": _mean(pos_a)},
        "disagree": {"n": len(disag_xs), "mean": ed,
                     "p_gt_0": (sum(1 for x in disag_xs if x > 0) / len(disag_xs)) if disag_xs else None,
                     "e_given_gt_0": _mean(pos_d)},
        "contrast": contrast, "n_trend_zero_or_unknown": n_zero, "n_null_y": n_null_y,
    }


def _orig_sign(x):
    if x is None:
        return None
    if x > 0:
        return 1
    if x < 0:
        return -1
    return 0


# ── bars.py ──────────────────────────────────────────────────────────────────────────────────
@pytest.fixture()
def csv_with_volume(tmp_path: Path) -> Path:
    p = tmp_path / "bars.csv"
    p.write_text(
        "timestamp,open,high,low,close,volume\n"
        "2026-01-01T00:00:00,10,11,9,10.5,100\n"
        "2026-01-01 00:15:00,10.5,12,10,11.5,200\n",
        encoding="utf-8",
    )
    return p


@pytest.fixture()
def csv_missing_volume(tmp_path: Path) -> Path:
    p = tmp_path / "novol.csv"
    p.write_text(
        "timestamp,open,high,low,close,volume\n"
        "2026-01-01T00:00:00,10,11,9,10.5,\n",
        encoding="utf-8",
    )
    return p


def test_parse_ts_matches_original_for_t_and_space_separators() -> None:
    for raw in ("2026-01-01T00:15:00", "2026-01-01 00:15:00", "2026-01-01T00:15:00.123456"):
        assert kit_bars.parse_ts_iso19(raw) == _orig_parse_ts(raw)


def test_load_bars_required_matches_original(csv_with_volume: Path) -> None:
    expected = _orig_load_bars_required(csv_with_volume)
    actual = kit_bars.load_bars(csv_with_volume, _Bar, volume="required")
    assert actual == expected
    assert actual[0].index == 0 and actual[1].index == 1


def test_load_bars_zero_default_matches_original(csv_with_volume: Path) -> None:
    expected = _orig_load_bars_zero_default(csv_with_volume)
    actual = kit_bars.load_bars(csv_with_volume, _Bar, volume="zero_default")
    assert actual == expected


def test_load_bars_required_raises_on_missing_volume(csv_missing_volume: Path) -> None:
    with pytest.raises(ValueError):
        _orig_load_bars_required(csv_missing_volume)
    with pytest.raises(ValueError):
        kit_bars.load_bars(csv_missing_volume, _Bar, volume="required")


def test_load_bars_zero_default_defaults_missing_volume(csv_missing_volume: Path) -> None:
    expected = _orig_load_bars_zero_default(csv_missing_volume)
    actual = kit_bars.load_bars(csv_missing_volume, _Bar, volume="zero_default")
    assert actual == expected == [_Bar(timestamp=datetime(2026, 1, 1), open=10.0, high=11.0,
                                        low=9.0, close=10.5, volume=0.0, index=0)]


# ── trade.py ─────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("outcome", ["SL_HIT", "TP_HIT", "TIMEOUT", "SOMETHING_ELSE"])
def test_exit_kind_matches_original(outcome: str) -> None:
    assert kit_trade.exit_kind(outcome) == _orig_exit_kind(outcome)


def _bar(i: int, high: float, low: float, close: float):
    return _Bar(timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc), open=close, high=high,
                low=low, close=close, volume=0.0, index=i)


def test_walk_horizon_matches_manual_forward_walk_call() -> None:
    from research.measurement.forward_walk import forward_walk as _fw
    sig = Signal(instrument="XAUUSD", timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
                 entry_index=0, direction="long", entry=100.0, sl_atr_mult=1.0, tp_atr_mult=2.0,
                 atr=1.0)
    future = [_bar(1, 101, 99, 100.5), _bar(2, 103, 100, 102), _bar(3, 105, 101, 104)]
    bars = [_bar(0, 100, 100, 100)] + future
    adverse = AdverseFill(stop_slippage=0.09, model_gaps=True)
    expected = _fw(sig, future[:5], max_forward=5, exit_model="intrabar_fixed", adverse_fill=adverse)
    actual = kit_trade.walk_horizon(sig, bars, horizon_bars=5, adverse=adverse)
    assert actual == expected


def test_walk_horizon_none_when_no_future_bars() -> None:
    sig = Signal(instrument="XAUUSD", timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
                 entry_index=5, direction="long", entry=100.0, sl_atr_mult=1.0, tp_atr_mult=2.0,
                 atr=1.0)
    bars = [_bar(0, 100, 100, 100)]
    assert kit_trade.walk_horizon(sig, bars, horizon_bars=40,
                                  adverse=AdverseFill(stop_slippage=0.09)) is None


# ── stats.py ─────────────────────────────────────────────────────────────────────────────────
def test_trade_stats_matches_original_on_mixed_wins_losses() -> None:
    rows = [{"y_R_gross": 1.5, "y_R_net": 1.2}, {"y_R_gross": -1.0, "y_R_net": -1.1},
            {"y_R_gross": 0.5, "y_R_net": 0.3}, {"y_R_gross": -0.5, "y_R_net": -0.6}]
    assert kit_stats.trade_stats(rows) == _orig_trade_stats(rows)


def test_trade_stats_empty_and_pf_edge_cases() -> None:
    assert kit_stats.trade_stats([]) == _orig_trade_stats([]) == {
        "n": 0, "gross_mean": None, "net_mean": None, "win_rate": None, "pf": None}
    all_wins = [{"y_R_gross": 1.0, "y_R_net": 0.9}]
    assert kit_stats.trade_stats(all_wins)["pf"] == _orig_trade_stats(all_wins)["pf"] == float("inf")
    flat = [{"y_R_gross": 0.0, "y_R_net": 0.0}]
    assert kit_stats.trade_stats(flat)["pf"] == _orig_trade_stats(flat)["pf"] == 0.0


_ARM_ROWS = [
    {"agree": True, "y": 0.5}, {"agree": True, "y": -0.2}, {"agree": True, "y": 1.0},
    {"agree": False, "y": -0.3}, {"agree": False, "y": 0.1}, {"agree": None, "y": 0.9},
    {"agree": True, "y": None},
]


def test_arm_cells_matches_both_replaced_variants() -> None:
    expected_a = _orig_arm_cells_a(_ARM_ROWS, "y")
    expected_b = _orig_arm_cells_b(_ARM_ROWS, "y")
    assert expected_a == expected_b  # the two variants ARE equivalent (that's the whole point)
    assert kit_stats.arm_cells(_ARM_ROWS, "y") == expected_a


def test_arm_cells_all_null_or_unknown() -> None:
    rows = [{"agree": None, "y": 1.0}, {"agree": True, "y": None}]
    expected = _orig_arm_cells_a(rows, "y")
    assert kit_stats.arm_cells(rows, "y") == expected
    assert expected["agree"]["n"] == 0 and expected["contrast"] is None


def test_arm_cells_mean_matches_statistics_mean_not_naive_sum() -> None:
    """The bug this test exists to prevent from recurring: on a real (n=100+) dataset,
    `statistics.mean` (exact fraction-based summation, what `research.evidence.queries._mean`
    actually uses) and naive `sum(xs)/len(xs)` can disagree in the last float bit. An earlier
    draft of `mc_kit.stats._mean` used naive summation and passed every small synthetic unit
    test in this file while silently producing a different `contrast` on the real
    `mother_range_prior` corpus — caught only by the end-to-end byte-identity gate. This test
    manufactures that exact divergence on a synthetic input so it can never again pass silently.
    """
    rng = random.Random(0)
    ys = [rng.uniform(-1e6, 1e6) for _ in range(50)]
    naive = sum(ys) / len(ys)
    exact = statistics.mean(ys)
    assert naive != exact, "the planted input must itself exhibit the divergence, or this proves nothing"
    rows = [{"agree": True, "y": y} for y in ys]
    assert kit_stats.arm_cells(rows, "y")["agree"]["mean"] == exact
    assert kit_stats.arm_cells(rows, "y")["agree"]["mean"] != naive


@pytest.mark.parametrize("x", [1.0, -1.0, 0.0, None, 1e-12, -1e-12])
def test_sign_matches_original(x) -> None:
    assert kit_stats.sign(x) == _orig_sign(x)


# ── costs.py extension ──────────────────────────────────────────────────────────────────────
def test_xau_measured_cost_model_matches_the_duplicated_literal() -> None:
    m = xau_measured_cost_model()
    assert (m.half_spread, m.commission, m.entry_slippage, m.stop_slippage) == (0.045, 0.040, 0.090, 0.090)
    assert m.instrument == "XAUUSD" and m.status == "MEASURED"
    assert m.entry_slippage_basis == "PROXY_FROM_STOP"
    net = m.net_rr(1.0, 100.0, 1.0, exit_kind="SL_HIT", direction="long")
    assert isinstance(net, float) and not math.isnan(net)
