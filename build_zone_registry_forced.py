import json
import argparse
import glob
import os
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from features.feature_schema import CANONICAL_FEATURES

PNL_COL = "pnl_rr_net"

def load_trade_csvs(root_dir="results"):
    pattern = os.path.join(root_dir, "**", "*_trades.csv")
    return glob.glob(pattern, recursive=True)

def collect_profitable_vectors(trade_csv_paths):
    all_vectors = []
    metadata = []
    for path in trade_csv_paths:
        df = pd.read_csv(path)
        if PNL_COL not in df.columns:
            print(f"Warning: {path} missing {PNL_COL}, skipping.")
            continue
        profitable = df[df[PNL_COL] > 0].copy()
        if profitable.empty:
            continue
        present_cols = [c for c in CANONICAL_FEATURES if c in profitable.columns]
        missing = set(CANONICAL_FEATURES) - set(present_cols)
        if missing:
            print(f"Warning: {path} missing columns: {missing}. Skipping.")
            continue
        vectors = profitable[present_cols].values.astype(np.float64)
        all_vectors.append(vectors)
        for idx, row in profitable.iterrows():
            metadata.append({
                "file": os.path.basename(path),
                "trade_id": row.get("trade_id", idx),
                "pnl": row[PNL_COL],
                "opened_at": row.get("opened_at", "")
            })
    if not all_vectors:
        raise ValueError("No profitable trades with complete features found.")
    X = np.vstack(all_vectors)
    return X, metadata

def cluster_zones_forced(X, n_clusters=3):
    print(f"Clustering {X.shape[0]} vectors into {n_clusters} clusters (forced).")
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    kmeans.fit(X)
    return kmeans

def build_zones(kmeans, X, min_points=3):
    zones = []
    labels = kmeans.labels_
    for i in range(kmeans.n_clusters):
        cluster_points = X[labels == i]
        if len(cluster_points) < min_points:
            print(f"  Skipping cluster {i}: only {len(cluster_points)} points (<{min_points})")
            continue
        center = kmeans.cluster_centers_[i]
        radius = np.std(cluster_points, axis=0)
        zones.append({
            "mu": center.tolist(),
            "sigma": radius.tolist(),
            "weights": [1.0 / len(cluster_points)] * len(center),  # uniform within cluster
            "threshold": 0.5,
            "weight": float(len(cluster_points))
        })
    return zones

def save_zones(zones, output_path="models/zone_registry.json"):
    with open(output_path, "w") as f:
        json.dump({
            "zones": zones,
            "schema_version": "v2",
            "migrated": True
        }, f, indent=2)
    print(f"Saved {len(zones)} zones to {output_path}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-clusters", type=int, default=3, help="Number of clusters to force (default 3)")
    parser.add_argument("--min-points", type=int, default=3, help="Minimum points per cluster to keep (default 3)")
    parser.add_argument("--output", type=str, default="models/zone_registry.json", help="Output path")
    args = parser.parse_args()

    trade_files = load_trade_csvs("results")
    print(f"Found {len(trade_files)} trade CSV files.")

    X, meta = collect_profitable_vectors(trade_files)
    print(f"Collected {X.shape[0]} profitable trades with {X.shape[1]} features each.")

    if X.shape[0] < args.min_points * 2:
        print(f"Warning: Only {X.shape[0]} profitable trades. Forcing {args.n_clusters} clusters may produce very small clusters.")
    if X.shape[0] < args.n_clusters:
        print(f"Error: Not enough samples ({X.shape[0]}) to create {args.n_clusters} clusters. Reduce --n-clusters.")
        return

    kmeans = cluster_zones_forced(X, n_clusters=args.n_clusters)
    zones = build_zones(kmeans, X, min_points=args.min_points)

    if len(zones) < 2:
        print("Warning: Fewer than 2 zones created. Consider lowering --min-points or increasing sample size.")

    save_zones(zones, args.output)

if __name__ == "__main__":
    main()