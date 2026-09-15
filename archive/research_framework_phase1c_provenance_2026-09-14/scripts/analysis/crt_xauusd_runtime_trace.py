#!/usr/bin/env python3
"""
Observational CRT IN/OUT runtime trace for XAUUSD (canonical backtest path).

Behavior-neutral: wraps CRTEngine.process_candle AFTER the real call returns;
appends JSONL only. No formula/config/RNG/execution-order changes.

Usage:
  PYTHONPATH=src BACKTEST_ENGINE_GATE=0 python scripts/analysis/crt_xauusd_runtime_trace.py \\
    --mode baseline|trace|both --output-dir results/crt_xauusd_trace_run
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
os.chdir(ROOT)

# Force CRT-isolated research spine (F-037): no EngineRunner fusion veto.
os.environ.setdefault("BACKTEST_ENGINE_GATE", "0")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _run_backtest(output_dir: str, enable_trace: bool, trace_path: Path | None) -> dict:
    from config_layer.config_builder import ConfigBuilder
    from config_layer.crt_engine_v2 import CRTEngine, Direction
    from config_layer.production_config import PROD_VERSION, get_active_version
    from runtime.backtest_v2 import (
        BacktestConfig,
        BacktestRunner,
        CandleLoader,
        load_prod_config_from_registry,
    )

    instrument = "XAUUSD"
    csv_path = "data/mt5/XAUUSD_M15.csv"
    crt_cfg = load_prod_config_from_registry(PROD_VERSION, instrument)
    cfg = BacktestConfig.from_prod_config(crt_config=crt_cfg)
    cfg.instrument = instrument
    cfg.pip_size = 0.01
    cfg.scorer_mode = "calibrated"

    # ── Observational wrap (post-call append only) ──────────────────────────
    orig_process = CRTEngine.process_candle
    sample_budget = {"n": 0, "max_samples": 80, "all_events": 0}

    def process_candle_traced(self, candle, htf_candle_id):  # type: ignore[no-untyped-def]
        state_before = self.state.current_state.name
        atr_before = float(self.state.atr_abs)
        result = orig_process(self, candle, htf_candle_id)
        if not enable_trace or trace_path is None:
            return result

        action = result.get("action", "NONE")
        state_after = self.state.current_state.name
        interesting = (
            action not in ("NONE",)
            or state_before != state_after
            or (self.state.active_trade is not None and action.startswith("TRADE_"))
        )
        # Always keep terminal / gate events; keep a small raw sample for IN proof.
        keep_sample = sample_budget["n"] < sample_budget["max_samples"] and (
            sample_budget["n"] < 5
            or candle.index % 5000 == 0
            or interesting
        )
        if not keep_sample and not interesting:
            return result

        sample_budget["n"] += 1 if keep_sample else 0
        if interesting:
            sample_budget["all_events"] += 1

        rng = self.state.active_range
        sw = self.state.sweep_event
        disp = self.state.displacement_candle
        rt = self.state.retest_candle
        rs = self.state.risk_score
        trade = self.state.active_trade

        # Recompute CRT-consumed geometry for trace (read-only; not fed back).
        body_size = abs(candle.close - candle.open)
        candle_range = candle.high - candle.low
        body_ratio = (body_size / candle_range) if candle_range > 0 else 0.0
        mid = ((rng.h_ref + rng.l_ref) / 2.0) if rng else None

        formula_rows = []
        formula_rows.append({
            "formula_id": "FM-ATR-SMA",
            "inputs": {"period": self.config.atr_period, "buffer_len": len(self.candle_buffer)},
            "output": float(self.state.atr_abs),
        })
        formula_rows.append({
            "formula_id": "FM-BODY_RATIO",
            "inputs": {"open": candle.open, "high": candle.high, "low": candle.low, "close": candle.close},
            "output": body_ratio,
        })
        formula_rows.append({
            "formula_id": "FM-CANDLE_RANGE",
            "inputs": {"high": candle.high, "low": candle.low},
            "output": candle_range,
        })
        formula_rows.append({
            "formula_id": "FM-BODY_SIZE",
            "inputs": {"open": candle.open, "close": candle.close},
            "output": body_size,
        })
        formula_rows.append({
            "formula_id": "FM-EMA",
            "inputs": {
                "close": candle.close,
                "ema_fast": self.config.ema_fast,
                "ema_slow": self.config.ema_slow,
            },
            "output": {
                "ema_fast_val": float(self.state.ema_fast_val),
                "ema_slow_val": float(self.state.ema_slow_val),
            },
        })
        if rs is not None:
            formula_rows.append({
                "formula_id": "FM-RISK_SCORE_FINAL",
                "inputs": {
                    "sweep": rs.sweep_score,
                    "breakout": rs.breakout_score,
                    "retest": rs.retest_score,
                    "time": rs.time_score,
                    "decay": rs.decay_factor,
                    "override": rs.score_override,
                },
                "output": float(rs.final),
            })
        if self.state.cached_features:
            formula_rows.append({
                "formula_id": "FM-027/FM-028_CACHE",
                "inputs": dict(self.state.cached_features),
                "output": dict(self.state.cached_features),
            })

        gates = []
        if action in (
            "DISPLACEMENT_CONFIRMED",
            "EXPANSION_CONFIRMED",
            "RETEST_CONFIRMED",
            "TRADE_OPENED",
            "FILTER_REJECTED",
            "SWEEP_EXPIRED",
            "EXPANSION_EXPIRED",
            "SHADOW_ADVISORY_BLOCK",
        ):
            gates.append({
                "gate_name": action,
                "threshold_or_config": {
                    "body_ratio_min": self.config.body_ratio_min,
                    "atr_min_displacement": self.config.atr_min_displacement,
                    "atr_multiplier_min": self.config.atr_multiplier_min,
                    "expansion_atr_min_distance": self.config.expansion_atr_min_distance,
                    "retest_depth_max": self.config.retest_depth_max,
                    "retest_atr_depth_fraction": self.config.retest_atr_depth_fraction,
                    "max_displacement_strength": self.config.max_displacement_strength,
                    "tier_1_threshold": self.config.tier_1_threshold,
                    "tier_2_threshold": self.config.tier_2_threshold,
                    "score_threshold": self.config.score_threshold,
                    "allowed_sessions": list(self.config.allowed_sessions),
                },
                "observed": {
                    "body_ratio": body_ratio,
                    "body_size": body_size,
                    "candle_range": candle_range,
                    "atr": float(self.state.atr_abs),
                    "atr_before": atr_before,
                },
                "pass_fail": "pass" if action in (
                    "DISPLACEMENT_CONFIRMED",
                    "EXPANSION_CONFIRMED",
                    "RETEST_CONFIRMED",
                    "TRADE_OPENED",
                ) else "terminal_non_trade",
            })

        rec = {
            "symbol": instrument,
            "timestamp": candle.timestamp.isoformat(sep=" "),
            "candle_index": candle.index,
            "raw_ohlcv": {
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": candle.volume,
            },
            "crt_inputs": {
                "htf_candle_id": htf_candle_id,
                "atr": float(self.state.atr_abs),
                "active_range": (
                    {
                        "h_ref": rng.h_ref,
                        "l_ref": rng.l_ref,
                        "equilibrium": rng.equilibrium,
                        "size": rng.size,
                        "htf_candle_id": rng.htf_candle_id,
                        "session": rng.session,
                    }
                    if rng
                    else None
                ),
                "sweep": (
                    {
                        "direction": sw.direction.value if sw else None,
                        "price": sw.price if sw else None,
                        "double_confirmed": sw.double_confirmed if sw else None,
                        "candle_index": sw.candle_index if sw else None,
                        "sweep_type": sw.sweep_type if sw else None,
                    }
                    if sw
                    else None
                ),
                "displacement_ohlc": (
                    {
                        "open": disp.open,
                        "high": disp.high,
                        "low": disp.low,
                        "close": disp.close,
                        "index": disp.index,
                    }
                    if disp
                    else None
                ),
                "retest_ohlc": (
                    {
                        "open": rt.open,
                        "high": rt.high,
                        "low": rt.low,
                        "close": rt.close,
                        "index": rt.index,
                    }
                    if rt
                    else None
                ),
                "ema_fast_val": float(self.state.ema_fast_val),
                "ema_slow_val": float(self.state.ema_slow_val),
                "direction": (
                    self.state.direction.value
                    if self.state.direction is not None
                    else None
                ),
                "cached_features": dict(self.state.cached_features)
                if self.state.cached_features
                else None,
                "evaluating_soft_conf": self.state.evaluating_soft_conf,
                "soft_conf_candles": self.state.soft_conf_candles,
            },
            "crt_formulas": formula_rows,
            "crt_state": {
                "state_before": state_before,
                "state_after": state_after,
                "transition_reason": result.get("reason")
                or (action if state_before != state_after else None),
            },
            "crt_gates": gates,
            "crt_output": {
                "terminal_result": action,
                "emitted_values": {
                    k: result[k]
                    for k in result
                    if k not in ("candle",)
                },
                "trade": (
                    {
                        "id": trade.id,
                        "direction": trade.direction.value,
                        "entry": trade.entry_price,
                        "sl": trade.sl_price,
                        "tp1": trade.tp1_price,
                        "tp2": trade.tp2_price,
                        "risk_pct": trade.risk_pct,
                        "status": trade.status,
                    }
                    if trade is not None and action == "TRADE_OPENED"
                    else None
                ),
                "range_mid": mid,
            },
        }
        with open(trace_path, "a", encoding="utf-8") as tf:
            tf.write(json.dumps(rec, default=str) + "\n")
        return result

    if enable_trace:
        CRTEngine.process_candle = process_candle_traced  # type: ignore[method-assign]
        if trace_path is not None:
            trace_path.parent.mkdir(parents=True, exist_ok=True)
            if trace_path.exists():
                trace_path.unlink()
            trace_path.write_text("", encoding="utf-8")

    try:
        loader = CandleLoader(csv_path, instrument)
        runner = BacktestRunner(cfg, csv_path=csv_path, skip_features=False)
        metrics = runner.run(loader.stream(), loader.count(), output_dir)
    finally:
        CRTEngine.process_candle = orig_process  # type: ignore[method-assign]

    out = Path(output_dir)
    # find latest instrument dir
    trade_csvs = sorted(out.rglob(f"{instrument}_trades.csv"))
    summary_jsons = sorted(out.rglob(f"{instrument}_summary.json"))
    report_txts = sorted(out.rglob(f"{instrument}_report.txt"))

    summary = {}
    if summary_jsons:
        summary = json.loads(summary_jsons[-1].read_text(encoding="utf-8"))

    trade_path = trade_csvs[-1] if trade_csvs else None
    trade_hash = _sha256(trade_path) if trade_path and trade_path.exists() else None
    summary_path = summary_jsons[-1] if summary_jsons else None
    summary_hash = _sha256(summary_path) if summary_path and summary_path.exists() else None

    pin = {
        "active_version": get_active_version(),
        "prod_version": PROD_VERSION,
        "instrument": instrument,
        "csv_path": str(Path(csv_path).resolve()),
        "corpus_sha256": _sha256(Path(csv_path)),
        "BACKTEST_ENGINE_GATE": os.environ.get("BACKTEST_ENGINE_GATE"),
        "scorer_mode": cfg.scorer_mode,
        "output_dir": str(out.resolve()),
        "trade_csv": str(trade_path) if trade_path else None,
        "trade_csv_sha256": trade_hash,
        "summary_json": str(summary_path) if summary_path else None,
        "summary_json_sha256": summary_hash,
        "report_txt": str(report_txts[-1]) if report_txts else None,
        "metrics": {
            "approved_trades": getattr(metrics, "approved_trades", None),
            "win_rate": getattr(metrics, "win_rate", None),
            "avg_rr_net": getattr(metrics, "avg_rr_net", None),
            "profit_factor": getattr(metrics, "profit_factor", None),
            "max_drawdown_pct": getattr(metrics, "max_drawdown_pct", None),
            "total_pnl_rr_net": getattr(metrics, "total_pnl_rr_net", None),
            "funnel_counts": getattr(metrics, "funnel_counts", None),
        },
        "trace_enabled": enable_trace,
        "trace_path": str(trace_path) if trace_path else None,
        "trace_event_count": sample_budget["all_events"] if enable_trace else 0,
        "trace_sample_rows": sample_budget["n"] if enable_trace else 0,
        "crt_config": asdict(crt_cfg) if hasattr(crt_cfg, "__dataclass_fields__") else {},
    }
    # serialize time objects
    pin_path = out / ("baseline_pin.json" if not enable_trace else "trace_pin.json")
    pin_path.parent.mkdir(parents=True, exist_ok=True)
    with open(pin_path, "w", encoding="utf-8") as f:
        json.dump(pin, f, indent=2, default=str)
    return pin


def _compare(baseline: dict, traced: dict) -> dict:
    b_tr = baseline.get("trade_csv_sha256")
    t_tr = traced.get("trade_csv_sha256")
    b_sum = baseline.get("summary_json_sha256")
    t_sum = traced.get("summary_json_sha256")
    bm = baseline.get("metrics") or {}
    tm = traced.get("metrics") or {}
    keys = [
        "approved_trades",
        "win_rate",
        "avg_rr_net",
        "profit_factor",
        "max_drawdown_pct",
        "total_pnl_rr_net",
    ]
    metric_eq = {k: (bm.get(k) == tm.get(k)) for k in keys}
    # funnel may be dict — compare as json
    funnel_eq = json.dumps(bm.get("funnel_counts"), sort_keys=True, default=str) == json.dumps(
        tm.get("funnel_counts"), sort_keys=True, default=str
    )
    trade_id = b_tr is not None and b_tr == t_tr
    summary_id = b_sum is not None and b_sum == t_sum
    parity = trade_id and all(metric_eq.values()) and funnel_eq
    return {
        "TRACE_BEHAVIOR_PARITY": "PASS" if parity else "FAIL",
        "trade_csv_byte_identical": trade_id,
        "summary_json_byte_identical": summary_id,
        "metric_equality": metric_eq,
        "funnel_equality": funnel_eq,
        "baseline_trades": bm.get("approved_trades"),
        "trace_trades": tm.get("approved_trades"),
        "baseline_trade_sha256": b_tr,
        "trace_trade_sha256": t_tr,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["baseline", "trace", "both"], default="both")
    ap.add_argument("--output-dir", default="results/crt_xauusd_trace_run")
    args = ap.parse_args()
    root = Path(args.output_dir)
    root.mkdir(parents=True, exist_ok=True)

    baseline_pin = None
    trace_pin = None
    if args.mode in ("baseline", "both"):
        print("=== BASELINE RUN ===", flush=True)
        baseline_pin = _run_backtest(
            str(root / "baseline"),
            enable_trace=False,
            trace_path=None,
        )
        print(json.dumps(baseline_pin.get("metrics"), indent=2), flush=True)

    if args.mode in ("trace", "both"):
        print("=== TRACE RUN ===", flush=True)
        trace_pin = _run_backtest(
            str(root / "trace"),
            enable_trace=True,
            trace_path=root / "runtime_trace.jsonl",
        )
        print(json.dumps(trace_pin.get("metrics"), indent=2), flush=True)

    if baseline_pin and trace_pin:
        cmp = _compare(baseline_pin, trace_pin)
        cmp_path = root / "parity_compare.json"
        cmp_path.write_text(json.dumps(cmp, indent=2), encoding="utf-8")
        print("=== PARITY ===", flush=True)
        print(json.dumps(cmp, indent=2), flush=True)
        return 0 if cmp["TRACE_BEHAVIOR_PARITY"] == "PASS" else 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
