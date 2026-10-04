import argparse
import json
import glob
import os
import sys
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

# Adjust path to import canonical feature list
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from features.feature_schema import CANONICAL_FEATURES

PNL_COL = "pnl_rr_net"

def load_trade_csvs(root_dir="results"):
    """Find all *_trades.csv files under root_dir."""
    pattern = os.path.join(root_dir, "**", "*_trades.csv")
    return glob.glob(pattern, recursive=True)

def collect_profitable_vectors(trade_csv_paths, instrument: str = None):
    """
    For each trade CSV, read rows where pnl_rr_net > 0,
    extract the 35 canonical features (if present), and return a matrix.

    Parameters
    ----------
    trade_csv_paths : list of CSV file paths to scan
    instrument      : if given (e.g. "EURUSD"), filter rows to that instrument
                      using the ``instrument`` column.  Case-insensitive.
                      Pass None to include all instruments (global registry).
    """
    all_vectors = []
    metadata = []   # instrument, trade_id, pnl, etc.
    instr_upper = instrument.upper() if instrument else None

    for path in trade_csv_paths:
        df = pd.read_csv(path)
        if PNL_COL not in df.columns:
            print(f"Warning: {path} missing {PNL_COL}, skipping.")
            continue

        # ── Per-instrument filter ──────────────────────────────────────────
        if instr_upper is not None:
            if "instrument" not in df.columns:
                # Fall back to filename-based check
                basename = os.path.basename(path).upper()
                if instr_upper not in basename:
                    continue
            else:
                df = df[df["instrument"].str.upper() == instr_upper]
                if df.empty:
                    continue

        profitable = df[df[PNL_COL] > 0].copy()
        if profitable.empty:
            continue

        # Check which canonical columns are actually present
        present_cols = [c for c in CANONICAL_FEATURES if c in profitable.columns]
        missing = set(CANONICAL_FEATURES) - set(present_cols)
        if missing:
            print(f"Warning: {path} missing canonical columns: {missing}. Skipping file.")
            continue

        # Extract feature vectors
        vectors = profitable[present_cols].values.astype(np.float64)
        all_vectors.append(vectors)

        # Store metadata for debugging (optional)
        for idx, row in profitable.iterrows():
            metadata.append({
                "file": os.path.basename(path),
                "instrument": row.get("instrument", instr_upper or "UNKNOWN"),
                "trade_id": row.get("trade_id", idx),
                "pnl": row[PNL_COL],
                "opened_at": row.get("opened_at", "")
            })

    if not all_vectors:
        raise ValueError(
            f"No profitable trades with complete canonical features found"
            + (f" for instrument {instr_upper}" if instr_upper else "") + "."
        )

    X = np.vstack(all_vectors)
    return X, metadata

def cluster_zones(X, n_clusters=None):
    """Determine number of clusters automatically if not given."""
    n_samples = X.shape[0]
    if n_clusters is None:
        # heuristic: at most 15 clusters, but at least 2
        n_clusters = max(2, min(15, n_samples // 5))
    print(f"Clustering {n_samples} vectors into {n_clusters} clusters...")
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    kmeans.fit(X)
    return kmeans

def build_zones(kmeans, X, min_points=5):
    """Convert KMeans results into zone registry format."""
    zones = []
    labels = kmeans.labels_
    for i in range(kmeans.n_clusters):
        cluster_points = X[labels == i]
        if len(cluster_points) < min_points:
            continue
        center = kmeans.cluster_centers_[i]
        radius = np.std(cluster_points, axis=0)
        zones.append({
            "mu": center.tolist(),
            "sigma": radius.tolist(),
            "weights": [1.0 / len(cluster_points)] * len(center),  # equal weight within cluster
            "threshold": 0.5,
            "weight": float(len(cluster_points))
        })
    return zones

def save_zones(zones, output_path="models/zone_registry.json"):
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "zones": zones,
            "schema_version": "v2",
            "migrated": True
        }, f, indent=2)
    print(f"Saved {len(zones)} zones to {output_path}")

def main():
    parser = argparse.ArgumentParser(
        description="Build a zone registry from profitable trade CSVs.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--instrument", default=None,
        help="Filter by instrument symbol (e.g. EURUSD).  "
             "When set, output is written to models/bitnet/<INSTRUMENT>_M15/zone_registry.json "
             "unless --output overrides it.",
    )
    parser.add_argument(
        "--output", default=None,
        help="Override output path.  Defaults to models/zone_registry.json (global) "
             "or models/bitnet/<INSTRUMENT>_M15/zone_registry.json (per-instrument).",
    )
    parser.add_argument(
        "--min-points", type=int, default=5,
        help="Minimum points per cluster to keep the zone.",
    )
    parser.add_argument(
        "--results-dir", default="results",
        help="Root directory to scan for *_trades.csv files.",
    )
    args = parser.parse_args()

    # ── Resolve output path ─────────────────────────────────────────────────
    if args.output:
        output_path = args.output
    elif args.instrument:
        # Per-instrument path — matches get_zone_registry_path("EURUSD_M15") in live_engine.py
        instr_key = f"{args.instrument.upper()}_M15"
        output_path = os.path.join("models", "bitnet", instr_key, "zone_registry.json")
    else:
        output_path = "models/zone_registry.json"

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    # ── Load and cluster ────────────────────────────────────────────────────
    trade_files = load_trade_csvs(args.results_dir)
    print(f"Found {len(trade_files)} trade CSV files.")

    try:
        X, metadata = collect_profitable_vectors(trade_files, instrument=args.instrument)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    lbl = f" ({args.instrument})" if args.instrument else " (global)"
    print(f"Collected {X.shape[0]} profitable trades{lbl} with {X.shape[1]} canonical features each.")

    if X.shape[0] < 10:
        print(
            f"Too few profitable trades{lbl} (<10). "
            "Consider using a larger dataset or run without --instrument for a global registry."
        )
        return

    kmeans = cluster_zones(X)
    zones = build_zones(kmeans, X, min_points=args.min_points)
    save_zones(zones, output_path=output_path)
    print(f"Generated {len(zones)} zones → {output_path}")
    total_samples = sum(z.get("weight", 0) for z in zones)
    print(f"Total training samples across zones: {total_samples:.0f}")
    if total_samples < 50:
        print(
            f"⚠ Total samples ({total_samples:.0f}) < 50 — zone gate will auto-bypass "
            "(underpowered_zone_registry) until registry reaches ≥ 50 samples."
        )

if __name__ == "__main__":
    main()