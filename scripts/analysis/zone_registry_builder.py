import json

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

from src.features.feature_pipeline import FeaturePipeline
from src.features.feature_schema import CANONICAL_FEATURES
from src.features.schema_validator import validate_features, validate_feature_values

PNL_COL = "pnl_rr_net"
FEATURES = list(CANONICAL_FEATURES)


def load_trades(path):
    return pd.read_csv(path)


def _build_canonical_features_df(df: pd.DataFrame) -> pd.DataFrame:
    enriched_df, _ = FeaturePipeline(df).run()
    if enriched_df.empty:
        raise ValueError("bitnet_zone_builder: FeaturePipeline produced no rows after warmup.")
    return enriched_df.reset_index(drop=True)


def build_feature_matrix(df):
    features_df = _build_canonical_features_df(df)
    matrix = []
    for i in range(len(features_df)):
        features = features_df.iloc[i][FEATURES].to_dict()
        validate_features(features, tuple(FEATURES))
        validate_feature_values(features)
        matrix.append([float(features[k]) for k in FEATURES])
    return np.asarray(matrix, dtype=np.float64)


def filter_profitable(df):
    return df[df[PNL_COL] > 0]


def cluster_zones(X, n_clusters=5):
    kmeans = KMeans(n_clusters=n_clusters, random_state=42)
    kmeans.fit(X)
    return kmeans


def build_zones(kmeans, X):
    zones = []
    labels = kmeans.labels_

    for i in range(kmeans.n_clusters):
        cluster_points = X[labels == i]
        if len(cluster_points) < 10:
            continue

        center = kmeans.cluster_centers_[i]
        radius = np.std(cluster_points, axis=0)

        zones.append(
            {
                "center": center.tolist(),
                "radius": radius.tolist(),
                "min_score": 0.5,
                "weight": float(len(cluster_points)),
            }
        )

    return zones


def save_zones(zones, path="models/zone_registry_kmeans.json"):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"zones": zones}, f, indent=2)


def validate_columns(df):
    required = ["timestamp", "open", "high", "low", "close", PNL_COL]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(
            f"[BitNet] Missing required columns for canonical pipeline: {missing}. "
            f"Available columns: {list(df.columns)}"
        )


def run(trade_csv):
    df = load_trades(trade_csv)
    validate_columns(df)
    df = filter_profitable(df)

    X = build_feature_matrix(df)

    kmeans = cluster_zones(X)
    zones = build_zones(kmeans, X)

    save_zones(zones)

    print(f"[BitNet] Generated {len(zones)} zones")
    print("[BitNet] NOTE: KMeans zones saved to models/zone_registry_kmeans.json")


if __name__ == "__main__":
    run("results/test_run/EURUSD_trades.csv")

