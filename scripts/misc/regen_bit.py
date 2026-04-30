import argparse
import glob
import os
import pandas as pd

def _adapt_trades_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize/bridge CSV schema to what rr_dataset_builder expects.

    Required by rr_dataset_builder:
      - rr_achieved (float)  -> use pnl_rr_net / pnl_rr_raw
      - outcome (str/int)    -> derive from rr_achieved
      - entry_time (str/dt)  -> use opened_at if present (for hour features)
    """
    df_out = df.copy()

    # rr_achieved mapping
    if "rr_achieved" not in df_out.columns:
        if "pnl_rr_net" in df_out.columns:
            df_out["rr_achieved"] = df_out["pnl_rr_net"]
        elif "pnl_rr_raw" in df_out.columns:
            df_out["rr_achieved"] = df_out["pnl_rr_raw"]
        else:
            df_out["rr_achieved"] = 0.0

    # outcome mapping (string) if missing
    if "outcome" not in df_out.columns:
        rr = df_out["rr_achieved"].fillna(0.0)
        df_out["outcome"] = rr.apply(lambda v: "win" if float(v) > 0 else "loss")

    # entry_time mapping for hour extraction
    if "entry_time" not in df_out.columns and "opened_at" in df_out.columns:
        df_out["entry_time"] = df_out["opened_at"]

    return df_out
from train_pipeline import run_bitnet_search

def _infer_instrument(path: str) -> str:
    base = os.path.basename(path)
    if base.lower().endswith("_trades.csv"):
        return base[:-11]
    return os.path.splitext(base)[0]

def _collect_csvs(args):
    if args.csv:
        return [args.csv]
    if args.dir:
        return glob.glob(os.path.join(args.dir, "**", "*_trades.csv"), recursive=True)
    if args.glob:
        return glob.glob(args.glob, recursive=True)
    # fallback: newest trades csv under results/
    paths = glob.glob("results/**/*trades*.csv", recursive=True)
    paths = sorted(paths, key=lambda p: os.path.getmtime(p), reverse=True)
    return paths[:1]

def main():
    ap = argparse.ArgumentParser(description="Regenerate BitNet zones from trades CSVs")
    ap.add_argument("--csv", help="Path to a single *_trades.csv")
    ap.add_argument("--dir", help="Directory to scan for *_trades.csv (recursive)")
    ap.add_argument("--glob", help="Glob pattern for trades CSVs")
    ap.add_argument("--output-root", default="models/bitnet",
                    help="Base output dir for per-instrument registries")
    ap.add_argument("--global-registry", action="store_true",
                    help="Write to models/zone_registry.json (single global file)")
    args = ap.parse_args()

    paths = _collect_csvs(args)
    if not paths:
        raise SystemExit("No trades CSV found. Use --csv or --dir.")

    for trade_csv in paths:
        inst = _infer_instrument(trade_csv).upper()
        print("Using:", trade_csv)
        df = pd.read_csv(trade_csv)
        df = _adapt_trades_df(df)
        trades = df.to_dict("records")

        if args.global_registry:
            out_dir = "models"
            print(f"Output: {os.path.join(out_dir, 'zone_registry.json')}")
        else:
            out_dir = os.path.join(args.output_root, inst)
            print(f"Output: {os.path.join(out_dir, 'zone_registry.json')}")

        res = run_bitnet_search(trades, output_dir=out_dir)
        print(res)

if __name__ == "__main__":
    main()
