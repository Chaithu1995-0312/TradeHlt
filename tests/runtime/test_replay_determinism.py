"""
WS3 replay gate — formalizes docs/architecture/replay-governance.md §6 as an
executable test: the same CSV + seed + config must produce a byte-identical trade
ledger and identical headline metrics across two independent runs.

A failure here means replay determinism is broken — the #1 repo priority
(`replay correctness > ...`). See docs/analysis/backtest-trust-audit-2026-06-10.md.
"""
from __future__ import annotations

import itertools
import tempfile
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_CSV = _REPO / "data" / "BNBUSDT_M15.csv"
_INSTRUMENT = "BNBUSDT"
_N_CANDLES = 45_000   # smaller window; determinism doesn't need many trades

# A 2nd instrument proves determinism is a property of the engine, not of one CSV
# (research-readiness audit 2026-06-12). Skipped if its data file is absent.
_INSTRUMENT_2 = "SOLUSDT"
_CSV_2 = _REPO / "data" / "SOLUSDT_M15.csv"


def _run_capped(n: int, instrument: str = _INSTRUMENT, csv: Path = _CSV) -> tuple[str, dict]:
    from runtime.backtest_v2 import BacktestConfig, BacktestRunner, CandleLoader
    from config_layer.config_builder import ConfigBuilder

    crt_cfg = ConfigBuilder.build(instrument, overrides={})
    cfg = BacktestConfig.from_prod_config(instrument=instrument, crt_config=crt_cfg)
    loader = CandleLoader(str(csv), instrument)
    out_dir = tempfile.mkdtemp(prefix="replay_det_")
    runner = BacktestRunner(cfg, csv_path=str(csv))
    m = runner.run(itertools.islice(loader.stream(), n), n, output_dir=out_dir)
    trades_csv = next(Path(out_dir).rglob("*_trades.csv"), None)
    ledger_text = trades_csv.read_text(encoding="utf-8") if trades_csv else ""
    summary = {
        "trades": m.approved_trades,
        "win_rate": m.win_rate,
        "avg_rr_net": m.avg_rr_net,
        "total_pnl_rr_net": m.total_pnl_rr_net,
        "profit_factor": m.profit_factor,
        "max_drawdown_pct": m.max_drawdown_pct,
        "total_return_pct": m.total_return_pct,
    }
    return ledger_text, summary


def _run_artifacts(n: int, instrument: str, csv: Path) -> dict[str, bytes]:
    """Run a capped backtest and return {artifact_basename: raw_bytes} for every file
    written under the run's output_dir (trades.csv, *_telemetry.jsonl, *_events.jsonl,
    *_summary.json, *_report.txt). The run-dir NAME carries a wall-clock stamp, but the
    artifact CONTENTS must be replay-identical — that is what this captures."""
    from runtime.backtest_v2 import BacktestConfig, BacktestRunner, CandleLoader
    from config_layer.config_builder import ConfigBuilder

    crt_cfg = ConfigBuilder.build(instrument, overrides={})
    cfg = BacktestConfig.from_prod_config(instrument=instrument, crt_config=crt_cfg)
    out_dir = tempfile.mkdtemp(prefix="replay_art_")
    BacktestRunner(cfg, csv_path=str(csv)).run(
        itertools.islice(CandleLoader(str(csv), instrument).stream(), n), n,
        output_dir=out_dir)
    return {p.name: p.read_bytes() for p in Path(out_dir).rglob("*") if p.is_file()}


@pytest.fixture(scope="module")
def two_runs():
    if not _CSV.exists():
        pytest.skip(f"data CSV missing: {_CSV}")
    return _run_capped(_N_CANDLES), _run_capped(_N_CANDLES)


def test_trade_ledger_is_byte_identical(two_runs):
    (ledger_a, _), (ledger_b, _) = two_runs
    assert ledger_a == ledger_b, "trade ledger differs across identical runs — replay not deterministic"


def test_headline_metrics_are_identical(two_runs):
    (_, sum_a), (_, sum_b) = two_runs
    assert sum_a == sum_b, f"metrics differ across identical runs: {sum_a} != {sum_b}"


# ── Telemetry-artifact + multi-instrument determinism (audit 2026-06-12) ──────
# Replay correctness must extend beyond the ledger to the telemetry/events/summary
# artifacts a researcher uses to EXPLAIN a decision — otherwise two identical runs
# could yield different audit trails. Proven byte-identical for BNBUSDT + SOLUSDT.

@pytest.mark.parametrize("instrument,csv", [
    (_INSTRUMENT, _CSV),
    (_INSTRUMENT_2, _CSV_2),
])
def test_all_artifacts_byte_identical_across_runs(instrument, csv):
    if not csv.exists():
        pytest.skip(f"data CSV missing: {csv}")
    a = _run_artifacts(_N_CANDLES, instrument, csv)
    b = _run_artifacts(_N_CANDLES, instrument, csv)
    assert set(a) == set(b), f"artifact set differs across runs: {set(a) ^ set(b)}"
    # Telemetry + events are the decision-explainability trail; assert each identical.
    diffs = [name for name in a if a[name] != b.get(name)]
    assert not diffs, (
        f"{instrument}: artifacts differ across identical runs (replay not "
        f"deterministic for telemetry/events): {diffs}")
