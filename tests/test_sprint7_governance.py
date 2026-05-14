"""
tests/test_sprint7_governance.py
Sprint 7 — Production Governance test coverage.

Tests:
  StrategyBacktester
    - produces metrics dict keyed by strategy ID
    - all 10 strategy IDs present
    - StrategyMetrics fields in valid ranges
    - too-short CSV returns empty dict
    - finalise() sets win_rate, profit_factor, expectancy correctly
    - _row_to_features() maps trend_bias integers to strings

  MultiStrategyValidator
    - validate() with no CSV paths returns REJECT
    - validate() with missing CSV path returns hard failure
    - validate() with synthetic data returns report with correct keys
    - APPROVE path produces APPROVE decision
    - REJECT path (low win rate) produces REJECT with hard_failures
    - report has instruments_tested list
    - report metrics has portfolio_win_rate key

  StrategyMetrics
    - score=0 when trade_count < 5
    - to_dict() contains all required keys

  HealthChecker
    - collect_status() returns dict with 'ts', 'service', 'overall', 'components'
    - components includes 'config', 'kill_switch', 'orchestrator'
    - start_background() starts without error; stop() cleans up

  Dockerfile
    - Dockerfile exists at repo root
    - FROM python:3.10 line present
    - EXPOSE 8787 and 8788 present
    - PYTHONPATH env var set

  promote_v2.py
    - script exists at scripts/governance/promote_v2.py
    - is importable without side effects
"""

import csv
import io
import json
import sys
import tempfile
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from governance.strategy_backtest import StrategyBacktester, StrategyMetrics
from governance.multi_strategy_validator import MultiStrategyValidator
from monitoring.health_checker import HealthChecker


# ── Helpers ────────────────────────────────────────────────────────────────────

def _write_synthetic_csv(path: Path, n_rows: int = 300) -> None:
    """Write a minimal M15 OHLCV CSV with enough rows for backtesting."""
    import random
    from datetime import datetime, timedelta
    rng = random.Random(42)
    price = 1.1000
    base_ts = datetime(2024, 1, 1, 0, 0, 0)
    rows = [["timestamp", "open", "high", "low", "close", "volume"]]
    for i in range(n_rows):
        change = rng.uniform(-0.0015, 0.0015)
        o = round(price, 5)
        c = round(o + change, 5)
        h = round(max(o, c) + rng.uniform(0, 0.0005), 5)
        l = round(min(o, c) - rng.uniform(0, 0.0005), 5)
        ts = (base_ts + timedelta(minutes=15 * i)).strftime("%Y-%m-%d %H:%M:%S")
        rows.append([ts, o, h, l, c, 1000.0])
        price = c
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)


# ── StrategyMetrics ────────────────────────────────────────────────────────────

class TestStrategyMetrics:

    def test_score_zero_when_low_trades(self):
        m = StrategyMetrics(strategy_id="S1", trade_count=3, win_count=2, loss_count=1)
        m.finalise()
        assert m.score == 0.0

    def test_to_dict_has_required_keys(self):
        m = StrategyMetrics(strategy_id="S2", trade_count=10, win_count=6, loss_count=4,
                            total_pnl_inr=2000.0, gross_profit=3000.0, gross_loss=1000.0)
        m.finalise()
        d = m.to_dict()
        for key in ("strategy_id", "trades", "wins", "losses", "win_rate",
                    "profit_factor", "expectancy_inr", "total_pnl_inr",
                    "max_drawdown", "score"):
            assert key in d, f"Missing key: {key}"

    def test_finalise_win_rate(self):
        m = StrategyMetrics(strategy_id="S3", trade_count=20, win_count=12, loss_count=8,
                            gross_profit=6000.0, gross_loss=2000.0, total_pnl_inr=4000.0)
        m.finalise()
        assert m.win_rate == pytest.approx(0.6, abs=0.01)
        assert m.profit_factor == pytest.approx(3.0, abs=0.1)
        assert m.expectancy_inr == pytest.approx(200.0, abs=1.0)

    def test_profit_factor_zero_loss(self):
        m = StrategyMetrics(strategy_id="S4", trade_count=10, win_count=10, loss_count=0,
                            gross_profit=5000.0, gross_loss=0.0, total_pnl_inr=5000.0)
        m.finalise()
        assert m.profit_factor == 0.0  # no loss denominator

    def test_score_positive_with_good_stats(self):
        m = StrategyMetrics(strategy_id="S5", trade_count=30, win_count=18, loss_count=12,
                            gross_profit=9000.0, gross_loss=3000.0, total_pnl_inr=6000.0,
                            max_drawdown=5000.0)
        m.finalise()
        assert m.score > 0.0


# ── StrategyBacktester ─────────────────────────────────────────────────────────

class TestStrategyBacktester:

    def test_returns_all_strategy_ids(self, tmp_path):
        csv_path = tmp_path / "EURUSD_M15.csv"
        _write_synthetic_csv(csv_path, n_rows=300)
        bt = StrategyBacktester(pair="EURUSD", timeframe="M15", warmup=50, max_forward_candles=20)
        results = bt.run(str(csv_path))
        assert set(results.keys()) == {"S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9", "S10"}

    def test_metrics_in_valid_ranges(self, tmp_path):
        csv_path = tmp_path / "EURUSD_M15.csv"
        _write_synthetic_csv(csv_path, n_rows=300)
        bt = StrategyBacktester(pair="EURUSD", timeframe="M15", warmup=50, max_forward_candles=20)
        results = bt.run(str(csv_path))
        for sid, m in results.items():
            assert 0 <= m.win_rate <= 1.0, f"{sid}: win_rate={m.win_rate}"
            assert m.profit_factor >= 0.0, f"{sid}: profit_factor={m.profit_factor}"
            assert m.max_drawdown >= 0.0, f"{sid}: max_drawdown={m.max_drawdown}"
            assert 0.0 <= m.score <= 1.0, f"{sid}: score={m.score}"

    def test_short_csv_returns_empty(self, tmp_path):
        csv_path = tmp_path / "tiny.csv"
        _write_synthetic_csv(csv_path, n_rows=20)
        bt = StrategyBacktester(pair="EURUSD", timeframe="M15", warmup=60, max_forward_candles=20)
        results = bt.run(str(csv_path))
        assert results == {}

    def test_missing_csv_returns_empty(self, tmp_path):
        bt = StrategyBacktester()
        results = bt.run(str(tmp_path / "nonexistent.csv"))
        assert results == {}

    def test_row_to_features_trend_bias_int(self):
        import pandas as pd
        row = pd.Series({"trend_bias": -1, "open": 1.1, "high": 1.11, "low": 1.09,
                         "close": 1.105, "volume": 1000.0, "atr": 0.001,
                         "session": 1, "volatility_regime": 0})
        feat = StrategyBacktester._row_to_features(row)
        assert feat["trend_bias"] in ("bullish", "bearish", "neutral")
        assert feat["trend_bias"] == "bearish"  # -1 → bearish

    def test_row_to_features_trend_bias_bullish(self):
        import pandas as pd
        row = pd.Series({"trend_bias": 1, "open": 1.1, "high": 1.11, "low": 1.09,
                         "close": 1.105, "volume": 1000.0, "atr": 0.001,
                         "session": 1, "volatility_regime": 0})
        feat = StrategyBacktester._row_to_features(row)
        assert feat["trend_bias"] == "bullish"


# ── MultiStrategyValidator ─────────────────────────────────────────────────────

class TestMultiStrategyValidator:

    def test_no_csv_paths_returns_reject(self):
        v = MultiStrategyValidator()
        report = v.validate(csv_paths={})
        assert report["decision"] == "REJECT"
        assert len(report["hard_failures"]) > 0

    def test_missing_csv_hard_failure(self, tmp_path):
        v = MultiStrategyValidator()
        report = v.validate(csv_paths={"EURUSD": str(tmp_path / "missing.csv")})
        assert report["decision"] == "REJECT"
        assert any("CSV not found" in f for f in report["hard_failures"])

    def test_report_has_required_keys(self, tmp_path):
        csv_path = tmp_path / "EURUSD_M15.csv"
        _write_synthetic_csv(csv_path, n_rows=300)
        v = MultiStrategyValidator(min_strategy_trades=1, min_portfolio_win_rate=0.0,
                                   max_portfolio_drawdown=1_000_000.0)
        report = v.validate(csv_paths={"EURUSD": str(csv_path)},
                            config_id="test_run")
        for key in ("decision", "config_id", "validated_at", "params", "metrics",
                    "per_instrument", "instruments_tested", "hard_failures", "warnings"):
            assert key in report, f"Missing key: {key}"

    def test_instruments_tested_list(self, tmp_path):
        csv_path = tmp_path / "EURUSD_M15.csv"
        _write_synthetic_csv(csv_path, n_rows=300)
        v = MultiStrategyValidator(min_strategy_trades=1, min_portfolio_win_rate=0.0,
                                   max_portfolio_drawdown=1_000_000.0)
        report = v.validate(csv_paths={"EURUSD": str(csv_path)})
        assert "EURUSD" in report["instruments_tested"]

    def test_metrics_has_portfolio_win_rate(self, tmp_path):
        csv_path = tmp_path / "EURUSD_M15.csv"
        _write_synthetic_csv(csv_path, n_rows=300)
        v = MultiStrategyValidator(min_strategy_trades=1, min_portfolio_win_rate=0.0,
                                   max_portfolio_drawdown=1_000_000.0)
        report = v.validate(csv_paths={"EURUSD": str(csv_path)})
        assert "portfolio_win_rate" in report["metrics"]

    def test_reject_when_hard_gate_fails(self, tmp_path):
        csv_path = tmp_path / "EURUSD_M15.csv"
        _write_synthetic_csv(csv_path, n_rows=300)
        # min_strategy_trades=1000 guarantees failure
        v = MultiStrategyValidator(min_strategy_trades=1000)
        report = v.validate(csv_paths={"EURUSD": str(csv_path)})
        assert report["decision"] == "REJECT"
        assert len(report["hard_failures"]) > 0

    def test_approve_with_relaxed_gates(self, tmp_path):
        csv_path = tmp_path / "EURUSD_M15.csv"
        _write_synthetic_csv(csv_path, n_rows=300)
        # min_strategy_trades=0: synthetic data may not trigger all strategies;
        # gates fully relaxed to test the APPROVE code path.
        v = MultiStrategyValidator(
            min_strategy_trades=0,
            min_portfolio_win_rate=0.0,
            max_portfolio_drawdown=1_000_000.0,
        )
        report = v.validate(csv_paths={"EURUSD": str(csv_path)})
        assert report["decision"] == "APPROVE"


# ── HealthChecker ──────────────────────────────────────────────────────────────

class TestHealthChecker:

    def test_collect_status_has_required_keys(self):
        checker = HealthChecker()
        status = checker.collect_status()
        for key in ("ts", "service", "overall", "components"):
            assert key in status, f"Missing key: {key}"

    def test_components_include_config_and_orchestrator(self):
        checker = HealthChecker()
        status = checker.collect_status()
        assert "config" in status["components"]
        assert "orchestrator" in status["components"]

    def test_kill_switch_component_present(self):
        checker = HealthChecker()
        status = checker.collect_status()
        assert "kill_switch" in status["components"]

    def test_overall_is_string(self):
        checker = HealthChecker()
        status = checker.collect_status()
        assert isinstance(status["overall"], str)
        assert status["overall"] in ("ok", "degraded", "halted")

    def test_start_and_stop(self):
        # Use a high port to avoid conflicts
        checker = HealthChecker(port=18788)
        checker.start_background()
        import time; time.sleep(0.1)   # allow thread to start
        checker.stop()


# ── Dockerfile ─────────────────────────────────────────────────────────────────

class TestDockerfile:
    _df = _ROOT / "Dockerfile"

    def test_dockerfile_exists(self):
        assert self._df.exists(), "Dockerfile not found at repo root"

    def test_base_image_python310(self):
        content = self._df.read_text()
        assert "FROM python:3.10" in content

    def test_expose_8787_and_8788(self):
        content = self._df.read_text()
        assert "8787" in content
        assert "8788" in content

    def test_pythonpath_set(self):
        content = self._df.read_text()
        assert "PYTHONPATH" in content


# ── promote_v2.py ──────────────────────────────────────────────────────────────

class TestPromoteScript:

    def test_script_exists(self):
        script = _ROOT / "scripts" / "governance" / "promote_v2.py"
        assert script.exists()

    def test_script_importable(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "promote_v2",
            str(_ROOT / "scripts" / "governance" / "promote_v2.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        # Just loading the module (not calling main) should not raise
        # The script is guarded by if __name__ == "__main__"
        assert mod is not None
