"""
WS3 parity gate — the independent oracle must reconcile with the production
`BacktestMetrics` path on a real run, and must itself stay independent of that path.

A divergence here is a Backtest Trust Layer failure (see
docs/analysis/backtest-trust-audit-2026-06-10.md).

TOLERANCE BASIS
    The oracle recomputes from the *published* trades CSV — the durable ledger
    artifact downstream analysis consumes. That CSV serializes `pnl_rr_net` at 4 dp
    and `capital_*` at 2 dp (`backtest_v2.py:902, 905-906`), while the canonical
    `BacktestMetrics` sums full-precision in-memory values. So the expected residual
    is pure serialization rounding, not formula divergence:
      - R-sum metrics (expectancy, max-DD R): ~N·5e-5 → 1e-3..2e-3
      - capital metrics (DD%, return, CAGR): 2dp on ~1e5 capital → ~1e-5
    The *exactness* of the oracle's formulas is proven separately at 1e-12 by the
    golden-ledger and invariant suites; this gate confirms the published ledger is
    precise enough to reconstruct the reported headline metrics.
"""
from __future__ import annotations

import csv
import itertools
import tempfile
from pathlib import Path

import pytest

from analytics import metrics_oracle as mo

_REPO = Path(__file__).resolve().parents[2]
_CSV = _REPO / "data" / "BNBUSDT_M15.csv"
_INSTRUMENT = "BNBUSDT"
_N_CANDLES = 50_000   # enough of the BNBUSDT span to generate ~15 trades, ~10s


def _run_capped(n: int):
    from runtime.backtest_v2 import BacktestConfig, BacktestRunner, CandleLoader
    from config_layer.production_config import get_active_version, load_prod_config_from_registry

    # P2 F-057: PRODUCTION_MERGED required on BacktestRunner product path.
    crt_cfg = load_prod_config_from_registry(get_active_version(), _INSTRUMENT)
    cfg = BacktestConfig.from_prod_config(instrument=_INSTRUMENT, crt_config=crt_cfg)
    loader = CandleLoader(str(_CSV), _INSTRUMENT)
    out_dir = tempfile.mkdtemp(prefix="oracle_parity_")
    runner = BacktestRunner(cfg, csv_path=str(_CSV))
    m = runner.run(itertools.islice(loader.stream(), n), n, output_dir=out_dir)
    trades_csv = next(Path(out_dir).rglob("*_trades.csv"), None)
    return m, trades_csv


def _read_ledger(trades_csv: Path):
    rr: list[float] = []
    cap_after: list[float] = []
    cap_before0 = None
    with open(trades_csv, newline="", encoding="utf-8") as f:
        for i, row in enumerate(csv.DictReader(f)):
            rr.append(float(row["pnl_rr_net"]))
            cap_after.append(float(row["capital_after"]))
            if i == 0:
                cap_before0 = float(row["capital_before"])
    equity = [cap_before0] + cap_after
    return rr, equity, cap_before0, cap_after[-1]


@pytest.fixture(scope="module")
def run_result():
    if not _CSV.exists():
        pytest.skip(f"data CSV missing: {_CSV}")
    m, trades_csv = _run_capped(_N_CANDLES)
    if trades_csv is None:
        pytest.skip("no trades produced in capped window")
    rr, equity, init, final = _read_ledger(trades_csv)
    if len(rr) < 5:
        pytest.skip(f"too few trades for a meaningful parity check ({len(rr)})")
    oracle = mo.recompute(
        rr,
        equity_curve=equity,
        initial_capital=init,
        final_capital=final,
        total_candles=_N_CANDLES,
    )
    return m, oracle, rr


def test_trade_count_parity(run_result):
    m, oracle, rr = run_result
    assert oracle.trades == m.approved_trades == len(rr)


def test_win_rate_parity(run_result):
    m, oracle, _ = run_result
    assert oracle.win_rate == pytest.approx(m.win_rate, abs=1e-9)


def test_profit_factor_parity(run_result):
    m, oracle, _ = run_result
    # ratio of two 4dp R-sums
    assert oracle.profit_factor == pytest.approx(m.profit_factor, abs=1e-3)


def test_expectancy_parity(run_result):
    m, oracle, _ = run_result
    # mean of 4dp pnl_rr_net values
    assert oracle.expectancy_mean == pytest.approx(m.avg_rr_net, abs=1e-3)


def test_max_drawdown_rr_parity(run_result):
    m, oracle, _ = run_result
    # cumulative walk over 4dp pnl_rr_net (rounding accumulates over N)
    assert oracle.max_drawdown_rr == pytest.approx(m.max_drawdown_rr, abs=2e-3)


def test_max_drawdown_pct_parity(run_result):
    m, oracle, _ = run_result
    # equity reconstructed from 2dp capital column
    assert oracle.max_drawdown_pct == pytest.approx(m.max_drawdown_pct, abs=1e-5)


def test_total_return_parity(run_result):
    m, oracle, _ = run_result
    assert oracle.total_return_pct == pytest.approx(m.total_return_pct, abs=1e-5)


def test_cagr_parity(run_result):
    m, oracle, _ = run_result
    assert oracle.cagr == pytest.approx(m.annualized_return_pct, abs=1e-5)


def test_return_to_max_dd_parity(run_result):
    m, oracle, _ = run_result
    assert oracle.return_to_max_dd == pytest.approx(m.return_to_max_dd, abs=1e-4)


def test_oracle_is_independent_of_production_path():
    """Step 4: the oracle must not import the canonical metrics code, or a bug in
    MetricsEngine could certify itself green."""
    src = Path(mo.__file__).read_text(encoding="utf-8")
    forbidden = ["MetricsEngine", "BacktestMetrics", "CapitalCurve",
                 "from runtime", "import runtime", "backtest_v2"]
    # Strip the module docstring (it legitimately names these for context).
    body = src.split('"""', 2)[-1]
    offenders = [tok for tok in forbidden if tok in body]
    assert not offenders, f"metrics_oracle imports/references production path: {offenders}"
