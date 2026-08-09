"""
Tests that ConfigValidator validates per-instrument session overrides the same
way production runtime does (RME backlog #1).

Before the fix, validate() built ONE crt_config and reused it for every
instrument — a config whose ROI gain comes from per-instrument
allowed_sessions_overrides was mis-scored. These tests pin the fixed behavior by
monkeypatching the module-level _run_instrument to record the allowed_sessions
each instrument's backtest actually receives (no real backtest / CSV needed).
"""
from __future__ import annotations

import config_layer.config_validator as cv


def _fake_metrics(crt_config) -> dict:
    """APPROVE-passing metrics; trade count varies with the session-set size so
    a per-instrument override is observable in the returned report."""
    return {
        "score":          0.80,
        "trades":         10 + len(crt_config.allowed_sessions),
        "win_rate":       0.60,
        "expectancy_rr":  0.50,
        "max_drawdown":   0.10,
        "total_pnl_rr":   5.00,
        "total_return_pct":      10.0,
        "annualized_return_pct":  5.0,
        "profit_factor":          2.0,
        "return_to_max_dd":       3.0,
        "error":          None,
    }


def _patch_runner(monkeypatch):
    recorded: dict[str, tuple] = {}

    def fake_run(instrument, csv_path, crt_config, warmup=None, factory=None):
        recorded[instrument] = tuple(crt_config.allowed_sessions)
        return _fake_metrics(crt_config)

    monkeypatch.setattr(cv, "_run_instrument", fake_run)
    return recorded


def test_validator_applies_per_instrument_override(tmp_path, monkeypatch):
    recorded = _patch_runner(monkeypatch)
    a = tmp_path / "BNBUSDT.csv"; a.write_text("x", encoding="utf-8")
    b = tmp_path / "ETHUSDT.csv"; b.write_text("x", encoding="utf-8")
    csv_paths = {"BNBUSDT": str(a), "ETHUSDT": str(b)}
    engine_runner = {
        "allowed_sessions": ["london", "new_york", "overlap"],
        "allowed_sessions_overrides": {
            "BNBUSDT": ["london", "new_york", "overlap", "asia", "off_session"],
        },
    }
    report = cv.ConfigValidator.validate(
        params={}, csv_paths=csv_paths, config_id="t", engine_runner=engine_runner
    )

    # BNBUSDT got its expanded set; ETHUSDT kept the global set.
    assert "ASIA" in recorded["BNBUSDT"] and "OFF_SESSION" in recorded["BNBUSDT"]
    assert recorded["ETHUSDT"] == ("LONDON", "NEWYORK", "OVERLAP")
    assert "ASIA" not in recorded["ETHUSDT"]
    # The override is observable end-to-end in the report (more sessions → more trades).
    assert (
        report["per_instrument"]["BNBUSDT"]["trades"]
        != report["per_instrument"]["ETHUSDT"]["trades"]
    )


def test_validator_without_engine_runner_is_unchanged(tmp_path, monkeypatch):
    """engine_runner=None (default) → every instrument uses the base crt_config."""
    recorded = _patch_runner(monkeypatch)
    a = tmp_path / "BNBUSDT.csv"; a.write_text("x", encoding="utf-8")
    cv.ConfigValidator.validate(params={}, csv_paths={"BNBUSDT": str(a)}, config_id="t")
    base = cv._params_to_crt_config({})
    assert recorded["BNBUSDT"] == tuple(base.allowed_sessions)
