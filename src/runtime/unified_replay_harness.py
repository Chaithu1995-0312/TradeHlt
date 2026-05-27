"""
unified_replay_harness.py
=========================
Run execution-truth backtest (v2) and BitNet gate modes on the same dataset,
then emit one normalized comparison JSON report.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# Ensure repo root is importable when run as script from runtime/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config_layer.config_builder import ConfigBuilder
from runtime.backtest_bitnet import run_backtest as run_backtest_bitnet
from runtime.backtest_v2 import BacktestConfig, BacktestRunner, CandleLoader
from utils.console_safe import safe_print


INSTRUMENT_PIP = {
    "EURUSD": 0.0001,
    "GBPUSD": 0.0001,
    "USDJPY": 0.01,
    "AUDUSD": 0.0001,
    "NZDUSD": 0.0001,
    "USDCHF": 0.0001,
    "BTCUSDT": 1.0,
    "ETHUSDT": 0.01,
    "XAUUSD": 0.01,
    "US30": 1.0,
    "NAS100": 0.25,
    "SP500": 0.25,
}


def _derive_symbol_from_data_path(data_path: str) -> str:
    stem = os.path.splitext(os.path.basename(data_path))[0].upper()
    if not stem:
        return "UNKNOWN"
    return stem.split("_")[0]


def _resolve_timestamp_series(df: pd.DataFrame) -> pd.Series:
    lower_map = {str(c).strip().lower(): c for c in df.columns}

    single_candidates = ["timestamp", "datetime", "date time", "open time"]
    for key in single_candidates:
        if key in lower_map:
            return pd.to_datetime(df[lower_map[key]], errors="coerce")

    if "date" in lower_map and "time" in lower_map:
        merged = df[lower_map["date"]].astype(str) + " " + df[lower_map["time"]].astype(str)
        return pd.to_datetime(merged, errors="coerce")

    raise ValueError(
        "Could not resolve timestamp column. Expected one of "
        "timestamp/datetime/date time/open time or date+time."
    )


def _materialize_month_window_csv(data_path: str, months: int, output_dir: str) -> str:
    if months <= 0:
        raise ValueError(f"months must be > 0, got {months}")

    df = pd.read_csv(data_path)
    ts = _resolve_timestamp_series(df)
    if ts.isna().all():
        raise ValueError("Timestamp parse failed for all rows; cannot apply month filter.")

    max_ts = ts.max()
    cutoff = max_ts - pd.DateOffset(months=months)
    out_df = df.loc[ts >= cutoff].copy().reset_index(drop=True)

    out_dir = Path(output_dir) / "filtered_inputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(data_path).stem
    out_path = out_dir / f"{stem}_last_{months}m.csv"
    out_df.to_csv(out_path, index=False)
    return str(out_path)


def _build_backtest_v2_config(config: dict, instrument: str) -> BacktestConfig:
    params = config.get("params", {}) if isinstance(config, dict) else {}

    crt_cfg = ConfigBuilder.build(instrument, overrides=params) if params else ConfigBuilder.build(instrument)

    return BacktestConfig.from_prod_config(
        instrument=instrument,
        pip_size=INSTRUMENT_PIP.get(instrument, 0.0001),
        crt_config=crt_cfg,
    )


def _summarize_bitnet_results(results: list[dict]) -> dict:
    total = len(results)
    bitnet_reject = 0
    errors = 0
    execute = 0
    reject = 0
    adapter_reject = 0
    accepted_by_score = 0
    accepted_by_fallback = 0
    accepted_by_override = 0

    for row in results:
        decision = str(row.get("decision", "")).upper()
        reason = str(row.get("reason", ""))
        raw_decision = str(row.get("bitnet_raw_decision", row.get("bitnet_decision", ""))).upper()
        final_decision = str(row.get("bitnet_decision", "")).upper()
        bitnet_error = row.get("bitnet_error")

        if decision == "BITNET_REJECT":
            bitnet_reject += 1
        elif decision == "ERROR":
            errors += 1
        elif decision == "EXECUTE":
            execute += 1
        elif decision == "REJECT":
            reject += 1

        if reason.startswith("adapter_"):
            adapter_reject += 1

        if final_decision == "ACCEPT":
            if raw_decision != "ACCEPT":
                accepted_by_override += 1
            elif bitnet_error:
                accepted_by_fallback += 1
            else:
                accepted_by_score += 1

    return {
        "rows_total": total,
        "bitnet_reject": bitnet_reject,
        "errors": errors,
        "engine_execute": execute,
        "engine_reject": reject,
        "adapter_reject": adapter_reject,
        "accepted_by_score": accepted_by_score,
        "accepted_by_fallback": accepted_by_fallback,
        "accepted_by_override": accepted_by_override,
    }


def run_unified_replay(
    config: dict,
    data_path: str,
    output_dir: str = "results/alignment",
    months: int | None = None,
) -> dict:
    effective_data_path = data_path
    if months is not None:
        effective_data_path = _materialize_month_window_csv(data_path, months, output_dir)

    instrument = _derive_symbol_from_data_path(effective_data_path)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    out_base = Path(output_dir)
    out_base.mkdir(parents=True, exist_ok=True)

    # Layer A: execution-truth metrics from backtest_v2
    bt_cfg = _build_backtest_v2_config(config, instrument)
    loader = CandleLoader(effective_data_path, instrument)
    runner_v2 = BacktestRunner(bt_cfg, csv_path=effective_data_path)
    metrics_v2 = runner_v2.run(
        loader.stream(),
        loader.count(),
        output_dir=str(out_base / f"{instrument}_{ts}_v2_truth"),
    )

    # Layer B: gate-mode comparisons (raises if BitNet model file is missing)
    modes = ["hard_gate", "score_only_audit", "force_accept_baseline"]
    gate_results = {}
    try:
        for mode in modes:
            rows = run_backtest_bitnet(config, effective_data_path, gate_mode=mode, months=None)
            gate_results[mode] = {
                "summary": _summarize_bitnet_results(rows),
                "sample_rows": rows[:25],
            }
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"Unified replay requires a BitNet model but none was found: {exc}. "
            f"Train one with: python scripts/training/train_bitnet.py --csv data/*.csv"
        ) from exc

    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "data_path": data_path,
        "effective_data_path": effective_data_path,
        "months_window": months,
        "instrument": instrument,
        "schema_hash": config.get("schema_hash"),
        "config_version": config.get("version"),
        "execution_truth_v2": metrics_v2.to_dict(),
        "gate_modes": gate_results,
    }

    out_path = out_base / f"{instrument}_{ts}_unified_report.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    report["report_path"] = str(out_path)
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="Unified replay harness (v2 truth + BitNet gate modes)")
    ap.add_argument("--config", default="configs/production/v1_multi_2026_03.json")
    ap.add_argument("--data", required=True)
    ap.add_argument("--months", type=int, default=None)
    ap.add_argument("--output-dir", default="results/alignment")
    args = ap.parse_args()

    with open(args.config, encoding="utf-8") as f:
        config = json.load(f)

    data_path = Path(args.data)
    if data_path.is_dir():
        csv_files = sorted(data_path.glob("*.csv"))
        if not csv_files:
            safe_print(f"No CSV files found in {data_path}")
            return 1
        reports = []
        for csv_file in csv_files:
            report = run_unified_replay(
                config,
                str(csv_file),
                output_dir=args.output_dir,
                months=args.months,
            )
            reports.append({"report_path": report.get("report_path"), "instrument": report.get("instrument")})
        safe_print(json.dumps(reports, indent=2))
    else:
        report = run_unified_replay(
            config,
            str(data_path),
            output_dir=args.output_dir,
            months=args.months,
        )
        safe_print(json.dumps({"report_path": report.get("report_path"), "instrument": report.get("instrument")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
