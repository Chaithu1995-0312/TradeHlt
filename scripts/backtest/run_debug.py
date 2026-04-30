import sys
sys.path.insert(0, '.')
from backtest_v2 import BacktestConfig, BacktestRunner, CandleLoader
from config_layer.config_builder import ConfigBuilder
from datetime import time

wide_sessions = {
    "LONDON":   (time(6,  0), time(16, 0)),
    "NEWYORK":  (time(12, 0), time(22, 0)),
    "ASIA":     (time(22, 0), time(8,  0)),
}

INSTRUMENTS = [
    {"name": "EURCAD",  "csv": "data/EURCAD_M15.csv",  "pip": 0.0001, "spread": 0.0002},
    {"name": "GBPUSD",  "csv": "data/GBPUSD_M15.csv",  "pip": 0.0001, "spread": 0.0003},
    {"name": "BTCUSDT", "csv": "data/BTCUSDT_M15.csv", "pip": 1.0,    "spread": 0.0008},
]

for instr in INSTRUMENTS:
    print(f"\n{'='*62}")
    print(f"  INSTRUMENT: {instr['name']}")
    print(f"{'='*62}")
    # ConfigBuilder picks FOREX or CRYPTO base automatically for each instrument,
    # then layers in the shared debug overrides. wide_sessions override is applied too.
    crt_cfg = ConfigBuilder.build(
        instr["name"],
        overrides={
            "score_threshold":        0.70,
            "max_sweep_age_candles":  30,
            "score_decay_lambda":     0.05,
            "atr_multiplier_min":     1.2,
            "session_windows":        wide_sessions,
            "confirmation_body_min":  0.5,
        },
    )

    cfg = BacktestConfig(
        instrument            = instr["name"],
        pip_size              = instr["pip"],
        htf_candles_per_range = 16,
        warmup_candles        = 80,
        initial_capital       = 100_000.0,
        risk_pct_per_trade    = 0.01,
        use_compounding       = True,
        simulated_spread_pct  = instr["spread"],
        slippage_enabled      = True,
        slippage_atr_fraction = 0.08,
        slippage_seed         = 42,
        gap_reset_enabled     = True,
        gap_reset_minutes     = 120,
        event_flush_every     = 100,
        crt_config            = crt_cfg,
    )
    loader = CandleLoader(instr["csv"], instr["name"])
    runner = BacktestRunner(cfg)
    m = runner.run(loader.stream(), loader.count(), f"results/{instr['name']}_debug")
