"""Historical OHLCV + FeaturePipeline substrate (one load path).

Warmup policy (invariant): FeaturePipeline runs on the full loaded CSV;
scoring window is applied after enrichment.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

import pandas as pd

from features.feature_pipeline import FeaturePipeline, build_features
from features.feature_schema import (
    CANONICAL_FEATURE_DIM,
    CANONICAL_FEATURES,
    FEATURE_ORDER_HASH,
    SCHEMA_HASH,
)
from research.model_runners.require_config import sha256_file


REQUIRED_OHLCV = ("timestamp", "open", "high", "low", "close", "volume")


@dataclass(frozen=True)
class BarContext:
    bar_index: int
    timestamp: str
    ohlcv: Mapping[str, float]
    features: Mapping[str, float]


@dataclass
class FeatureSubstrate:
    csv_path: Path
    csv_sha256: str
    enriched: pd.DataFrame
    feature_schema: dict[str, Any]
    n_loaded_rows: int
    n_enriched_rows: int


def _normalize_ohlcv_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Map case-insensitive OHLCV names to canonical lowercase columns.

    Uses a single rename table derived from required names only.
    Missing required columns → ValueError (no synthetic volume).
    """
    lower_map = {str(c).strip().lower(): c for c in df.columns}
    rename: dict[str, str] = {}
    for want in REQUIRED_OHLCV:
        if want not in lower_map:
            # common alias for timestamp
            if want == "timestamp":
                for alt in ("time", "datetime", "date"):
                    if alt in lower_map:
                        rename[lower_map[alt]] = "timestamp"
                        break
                else:
                    raise ValueError(
                        f"OHLCV CSV missing required column {want!r}; "
                        f"have={list(df.columns)}"
                    )
            else:
                raise ValueError(
                    f"OHLCV CSV missing required column {want!r}; "
                    f"have={list(df.columns)}"
                )
        else:
            rename[lower_map[want]] = want
    out = df.rename(columns=rename)
    missing = [c for c in REQUIRED_OHLCV if c not in out.columns]
    if missing:
        raise ValueError(f"OHLCV CSV missing columns after normalize: {missing}")
    return out


def load_ohlcv_csv(csv_path: Path) -> tuple[pd.DataFrame, str]:
    if not csv_path.is_file():
        raise FileNotFoundError(f"CSV not found: {csv_path}")
    digest = sha256_file(csv_path)
    df = pd.read_csv(csv_path)
    df = _normalize_ohlcv_columns(df)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=False)
    return df, digest


def build_feature_substrate(csv_path: Path) -> FeatureSubstrate:
    df, digest = load_ohlcv_csv(csv_path)
    n_loaded = len(df)
    pipe = FeaturePipeline(df)
    enriched, _vectors = pipe.run()
    if "timestamp" not in enriched.columns:
        raise RuntimeError("FeaturePipeline output missing timestamp column")
    enriched = enriched.copy()
    enriched["timestamp"] = pd.to_datetime(enriched["timestamp"], utc=False)
    return FeatureSubstrate(
        csv_path=csv_path.resolve(),
        csv_sha256=digest,
        enriched=enriched,
        feature_schema={
            "dim": CANONICAL_FEATURE_DIM,
            "SCHEMA_HASH": SCHEMA_HASH,
            "FEATURE_ORDER_HASH": FEATURE_ORDER_HASH,
            "canonical_features": list(CANONICAL_FEATURES),
        },
        n_loaded_rows=n_loaded,
        n_enriched_rows=len(enriched),
    )


def select_window(
    enriched: pd.DataFrame,
    *,
    start: pd.Timestamp | None,
    end: pd.Timestamp | None,
    limit: int | None,
) -> pd.DataFrame:
    """Filter enriched frame. Omitting start/end means full post-warmup series."""
    ts = pd.to_datetime(enriched["timestamp"])
    mask = pd.Series(True, index=enriched.index)
    if start is not None:
        mask &= ts >= start
    if end is not None:
        mask &= ts <= end
    window = enriched.loc[mask].reset_index(drop=True)
    if limit is not None:
        if limit < 1:
            raise ValueError(f"--limit must be >= 1, got {limit}")
        window = window.iloc[:limit].reset_index(drop=True)
    return window


def iter_bar_contexts(window_df: pd.DataFrame) -> Iterator[BarContext]:
    """Yield BarContext for each enriched row (features via build_features)."""
    for i, row in window_df.iterrows():
        features = build_features(row)
        ohlcv = {
            "open": float(features["open"]),
            "high": float(features["high"]),
            "low": float(features["low"]),
            "close": float(features["close"]),
            "volume": float(features["volume"]),
        }
        ts = row["timestamp"]
        ts_str = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
        yield BarContext(
            bar_index=int(i),
            timestamp=ts_str,
            ohlcv=ohlcv,
            features=features,
        )


def require_feature_keys(
    features: Mapping[str, float], keys: Sequence[str]
) -> None:
    missing = [k for k in keys if k not in features]
    if missing:
        raise KeyError(f"features missing required keys: {missing}")
