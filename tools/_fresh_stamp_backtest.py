"""Fresh-start stamped backtest emit — trust artifact, not sidecar."""
from __future__ import annotations
import json, os, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.chdir(ROOT)
os.environ.setdefault("BACKTEST_ENGINE_GATE", "0")

from config_layer.production_config import get_active_version, PROD_VERSION
from runtime.backtest_v2 import (
    BacktestConfig, BacktestRunner, CandleLoader, load_prod_config_from_registry,
    BACKTEST_COST_MODEL_ID, BACKTEST_RISK_DENOM_ID,
)

def main() -> None:
    out = Path(os.environ["FRESH_OUT"])
    out.mkdir(parents=True, exist_ok=True)
    instrument = "XAUUSD"
    csv_path = "data/mt5/XAUUSD_M15.csv"
    meta = {
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "REM-COST-01 fresh stamp trust emit",
        "authority": "RESEARCH_ONLY",
        "active_version": get_active_version(),
        "prod_version": PROD_VERSION,
        "expected_cost_model_id": BACKTEST_COST_MODEL_ID,
        "expected_risk_denominator_id": BACKTEST_RISK_DENOM_ID,
        "csv": csv_path,
        "BACKTEST_ENGINE_GATE": os.environ.get("BACKTEST_ENGINE_GATE"),
    }
    (out / "FRESH_START_META.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print("META", json.dumps(meta), flush=True)

    crt_cfg = load_prod_config_from_registry(PROD_VERSION, instrument)
    cfg = BacktestConfig.from_prod_config(crt_config=crt_cfg)
    cfg.instrument = instrument
    cfg.pip_size = 0.01
    cfg.scorer_mode = "calibrated"
    print("cfg.cost_model_id", cfg.cost_model_id, "hash", cfg.cost_model_params_hash, "denom", getattr(cfg, "risk_denominator_id", None), flush=True)

    loader = CandleLoader(csv_path, instrument)
    n = loader.count()
    print(f"candles={n}", flush=True)
    runner = BacktestRunner(cfg, csv_path=csv_path, skip_features=False)
    metrics = runner.run(loader.stream(), n, str(out))
    print("done metrics keys", list(metrics)[:12] if isinstance(metrics, dict) else type(metrics), flush=True)

    # Verify stamp on written CSV
    trades = sorted(out.rglob(f"{instrument}_trades.csv"))
    summaries = sorted(out.rglob(f"{instrument}_summary.json"))
    report = {
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "trades_csv": str(trades[-1]) if trades else None,
        "summary_json": str(summaries[-1]) if summaries else None,
    }
    if trades:
        import pandas as pd
        df = pd.read_csv(trades[-1])
        cols = list(df.columns)
        report["has_cost_model_id"] = "cost_model_id" in cols
        report["has_cost_model_params_hash"] = "cost_model_params_hash" in cols
        report["has_risk_denominator_id"] = "risk_denominator_id" in cols
        report["n_trades"] = int(len(df))
        if len(df):
            report["cost_model_id_values"] = sorted(set(map(str, df.get("cost_model_id", []))))
            report["risk_denominator_id_values"] = sorted(set(map(str, df.get("risk_denominator_id", []))))
            if "cost_model_params_hash" in cols:
                report["cost_model_params_hash_values"] = sorted(set(map(str, df["cost_model_params_hash"])))
            if "run_id" in cols:
                report["content_run_id"] = str(df["run_id"].iloc[0])
            report["pnl_rr_net_sum"] = float(df["pnl_rr_net"].sum()) if "pnl_rr_net" in cols else None
    if summaries:
        s = json.loads(summaries[-1].read_text(encoding="utf-8"))
        report["summary_cost_model_id"] = s.get("cost_model_id")
        report["summary_cost_model_params_hash"] = s.get("cost_model_params_hash")
        report["summary_risk_denominator_id"] = s.get("risk_denominator_id")
        report["summary_run_id"] = s.get("run_id")
        report["summary_total_pnl_rr_net"] = s.get("total_pnl_rr_net")
    (out / "FRESH_STAMP_VERIFY.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("VERIFY", json.dumps(report, indent=2), flush=True)
    ok = report.get("has_cost_model_id") and report.get("has_risk_denominator_id")
    sys.exit(0 if ok else 2)

if __name__ == "__main__":
    main()
