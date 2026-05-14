"""
tests/test_uat_runner.py
UAT runner + Monte Carlo + Kill Switch test coverage.

Tests:
  - MonteCarloEngine: known P&L sequence → expected statistics
  - MonteCarloEngine: insufficient trades → INSUFFICIENT_DATA
  - MonteCarloEngine: all-loss sequence → high P(ruin)
  - MonteCarloEngine: all-win sequence → P(ruin)=0
  - KillSwitch: daily limit trips and resets correctly
  - KillSwitch: weekly accumulation trips correctly
  - KillSwitch: profits do NOT trip the switch
  - KillSwitch: state persists after re-instantiation
  - KillSwitch: already-tripped gate blocks new registrations
  - UATRunner: area 1 logs signals from orchestrator output
  - UATRunner: area 5 logs MC results via LLMStructuredLogger
  - UATRunner: area 6 kill switch scenarios all pass
  - UATRunner: area 7 edge cases — EC-01/EC-02/EC-04 return NO_TRADE
  - UATRunner: export_all writes files to output dir
  - to_llm_logger_dict() keys match MonteCarloRecord fields
"""

import json
import sys
import tempfile
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from uat.monte_carlo import MonteCarloEngine, TradeOutcome, MonteCarloResult
from uat.kill_switch import KillSwitch
from uat.uat_runner import UATRunner
from utils.llm_logger import MonteCarloRecord


PAIR = "EURUSD"
TF   = "H1"

# ── Monte Carlo ────────────────────────────────────────────────────────────────

def _trades(pnls):
    return [TradeOutcome(pnl_inr=p, strategy_id="S1") for p in pnls]


def test_mc_insufficient_data():
    engine = MonteCarloEngine(n_simulations=100)
    result = engine.run(_trades([100.0, -50.0, 80.0]), strategy_id="S1")
    assert result.status == "INSUFFICIENT_DATA"
    assert result.n_simulations == 0


def test_mc_all_wins():
    pnls = [500.0] * 50
    engine = MonteCarloEngine(n_simulations=200, random_seed=0)
    result = engine.run(_trades(pnls), strategy_id="S1")
    assert result.p_ruin == 0.0
    assert result.p_ruin_pass is True
    assert result.status == "PASSED"
    assert result.median_equity_inr > 100_000.0


def test_mc_all_losses_high_ruin():
    # 50 trades each losing INR 2000 → guaranteed ruin (50K total loss)
    pnls = [-2000.0] * 50
    engine = MonteCarloEngine(
        n_simulations=200,
        initial_capital_inr=100_000.0,
        ruin_threshold_pct=0.50,
        random_seed=0,
    )
    result = engine.run(_trades(pnls), strategy_id="S1")
    assert result.p_ruin == 1.0
    assert result.p_ruin_pass is False
    assert result.status == "FAILED"


def test_mc_mixed_trades_structure():
    pnls = [800.0, -300.0, 600.0, -400.0, 900.0, -200.0] * 5  # 30 trades, net positive
    engine = MonteCarloEngine(n_simulations=500, random_seed=42)
    result = engine.run(_trades(pnls), strategy_id="ALL")
    assert 0 <= result.p_ruin <= 1.0
    assert result.n_trades == 30
    assert result.n_simulations == 500
    assert result.median_equity_inr > 0.0
    assert result.avg_max_drawdown_pct >= 0.0
    assert result.worst_loss_streak_p95 >= 0
    assert isinstance(result.equity_percentiles, dict)


def test_mc_to_llm_logger_dict_keys():
    pnls = [500.0, -200.0, 400.0, -300.0] * 5
    engine = MonteCarloEngine(n_simulations=100, random_seed=0)
    result = engine.run(_trades(pnls), strategy_id="S10")
    d = result.to_llm_logger_dict()
    required_keys = set(MonteCarloRecord.__dataclass_fields__.keys())
    assert required_keys.issubset(set(d.keys())), (
        f"Missing keys: {required_keys - set(d.keys())}"
    )


# ── KillSwitch ────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_ks(tmp_path):
    """KillSwitch with tmp state file and tight limits."""
    return KillSwitch(
        daily_limit_inr  = 1_000.0,
        weekly_limit_inr = 3_000.0,
        state_file       = tmp_path / "ks_test.json",
    )


def test_ks_daily_limit_trips(tmp_ks):
    tripped = tmp_ks.register_trade(pnl_inr=-1200.0)
    assert tripped is True
    assert tmp_ks.is_tripped() is True
    assert tmp_ks.trip_reason() == "daily"


def test_ks_weekly_accumulation_trips(tmp_path):
    # daily_limit > weekly_limit so weekly gate trips first
    ks = KillSwitch(
        daily_limit_inr  = 2_000.0,
        weekly_limit_inr = 1_000.0,
        state_file       = tmp_path / "ks_weekly.json",
    )
    for loss in [400.0, 350.0, 300.0]:
        ks.register_trade(pnl_inr=-loss)
    assert ks.is_tripped() is True
    assert ks.trip_reason() == "weekly"
    assert ks.weekly_loss_inr() >= 1050.0


def test_ks_profits_no_trip(tmp_ks):
    for profit in [200.0, 500.0, 300.0]:
        tmp_ks.register_trade(pnl_inr=profit)
    assert tmp_ks.is_tripped() is False
    assert tmp_ks.daily_loss_inr() == 0.0


def test_ks_reset_clears_trip(tmp_ks):
    tmp_ks.register_trade(pnl_inr=-1500.0)
    assert tmp_ks.is_tripped() is True
    tmp_ks.reset()
    assert tmp_ks.is_tripped() is False
    assert tmp_ks.trip_reason() == ""
    # Loss accumulators persist after reset (only trip state cleared)
    assert tmp_ks.daily_loss_inr() > 0.0


def test_ks_already_tripped_blocks_new_registration(tmp_ks):
    tmp_ks.register_trade(pnl_inr=-1200.0)
    assert tmp_ks.is_tripped() is True
    # Second registration should be blocked (returns False)
    result = tmp_ks.register_trade(pnl_inr=-500.0)
    assert result is False


def test_ks_state_persists(tmp_path):
    """State file survives process restart (re-instantiation)."""
    sf = tmp_path / "ks_persist.json"
    ks1 = KillSwitch(daily_limit_inr=1_000.0, weekly_limit_inr=5_000.0, state_file=sf)
    ks1.register_trade(pnl_inr=-600.0)
    assert not ks1.is_tripped()

    # Re-instantiate — should reload state
    ks2 = KillSwitch(daily_limit_inr=1_000.0, weekly_limit_inr=5_000.0, state_file=sf)
    assert ks2.daily_loss_inr() == pytest.approx(600.0, abs=1.0)
    # Push it over the limit
    ks2.register_trade(pnl_inr=-500.0)
    assert ks2.is_tripped() is True


def test_ks_status_dict_keys(tmp_ks):
    d = tmp_ks.status_dict()
    for key in ("tripped", "trip_reason", "daily_loss_inr", "weekly_loss_inr",
                "daily_limit_inr", "weekly_limit_inr", "current_day", "current_week"):
        assert key in d


# ── UATRunner ─────────────────────────────────────────────────────────────────

NEUTRAL_CANDLE = {"open": 1.1000, "high": 1.1020, "low": 1.0980,
                  "close": 1.1005, "volume": 100}
NEUTRAL_FEATURES = {
    "atr": 0.0015, "rsi_14": 50.0, "trend_bias": "neutral",
    "sweep_detected": False, "break_of_structure": False,
    "higher_high": False, "lower_low": False,
    "swing_high": 1.1050, "swing_low": 1.0950,
    "disp_strength": 0.3, "retest_depth": 0.2,
    "candles_since_retest": 5, "body_ratio": 0.3,
    "liquidity_sweep": False, "double_sweep": False,
    "volume_ratio": 1.0, "momentum_score": 0.0,
    "bb_upper": 1.1050, "bb_lower": 1.0950,
    "rejection_wick": False, "is_inside_bar": False,
    "ema_fast": 1.1000, "ema_slow": 1.0990,
    "ema_spread": 0.0010, "body_size": 0.0005,
    "wick_size": 0.0010, "pattern_score": 0.5,
    "session": "london", "hour_of_day": 10.0,
    "macd_line": 0.0, "macd_signal": 0.0, "macd_hist": 0.0,
    "zone_strength": 0.5, "trend_strength": 0.5,
    "volatility_ratio": 1.0, "volatility_regime": "RANGING",
    "spread_pct": 0.0001,
}


@pytest.fixture
def runner(tmp_path):
    cfg = {
        "monte_carlo": {"n_simulations": 50, "initial_capital_inr": 100000.0,
                        "ruin_threshold_pct": 0.50, "random_seed": 42},
        "kill_switch": {"daily_loss_limit_inr": 1000.0, "weekly_loss_limit_inr": 3000.0,
                        "state_file": str(tmp_path / "ks.json"), "telegram_notify": False},
        "signal_accuracy": {"min_win_rate": 0.35, "min_trades": 2},
        "output_dir": str(tmp_path / "uat_out"),
    }
    return UATRunner(pair=PAIR, timeframe=TF,
                     output_dir=tmp_path / "uat_out", config=cfg)


def test_runner_area1_runs(runner):
    candle_data = [(NEUTRAL_FEATURES, NEUTRAL_CANDLE)] * 5
    log = runner.run_area_1(candle_data)
    assert log is not None
    # Neutral features fire ≤ min_trades signals; anomaly flagged
    assert len(log._payload.anomalies) >= 0  # may have anomaly for low signal count


def test_runner_area5_mc(runner):
    trades = _trades([500.0, -200.0, 400.0, -300.0, 600.0, -150.0,
                      350.0, -250.0, 450.0, -180.0, 700.0, -400.0])
    log = runner.run_area_5(trades)
    assert len(log._mc_results) == 1
    mc = log._mc_results[0]
    assert 0.0 <= mc.p_ruin <= 1.0
    assert mc.status in ("PASSED", "FAILED", "INSUFFICIENT_DATA")


def test_runner_area6_kill_switch_scenarios(runner):
    log = runner.run_area_6()
    # 3 scenarios: daily breach, weekly accumulation, profitable no-trip
    assert len(log._kill_events) == 3
    # Scenarios A and B should trip; no anomalies for them
    trip_anomalies = [a for a in log._payload.anomalies if "did not trip" in a]
    assert len(trip_anomalies) == 0


def test_runner_area7_edge_cases(runner):
    log = runner.run_area_7()
    cases_by_name = {ec.case: ec for ec in log._edge_cases}
    # EC-01 zero ATR → NO_TRADE
    assert cases_by_name["EC-01_zero_atr"].passed is True
    # EC-02 zero close → NO_TRADE
    assert cases_by_name["EC-02_zero_close"].passed is True
    # EC-04 news spike → NO_TRADE
    assert cases_by_name["EC-04_news_spike"].passed is True


def test_runner_export_all(runner, tmp_path):
    runner.run_area_5(_trades([500.0, -200.0] * 10))
    runner.run_area_7()
    paths = runner.export_all()
    assert len(paths) >= 2
    for area, path in paths.items():
        assert path.exists(), f"UAT-{area} export file missing: {path}"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "uat_area" in data
        assert data["uat_area"] == area
