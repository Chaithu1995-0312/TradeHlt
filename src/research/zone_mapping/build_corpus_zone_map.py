"""
Map every bar of a CSV corpus with HistoricalZoneMapper and compute zone census.

Research-only; no CRT / EngineRunner admission path.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from features.feature_pipeline import FeaturePipeline
from features.feature_schema import CANONICAL_FEATURES
from research.zone_mapping.historical_zone_mapper import (
    HistoricalZoneMapper,
    ZoneMapConfig,
)
from research.zone_mapping.zone_census import (
    census_to_markdown,
    compute_zone_census,
    labels_from_map_records,
)


def _registry_zone_ids(registry_path: str) -> list[str]:
    p = Path(registry_path)
    if not p.is_file():
        return []
    raw = json.loads(p.read_text(encoding="utf-8"))
    zones = raw.get("zones") or []
    return [str(z.get("id", f"zone_{i}")) for i, z in enumerate(zones)]


def _file_sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def map_corpus_frame(
    csv_path: str,
    *,
    instrument: str = "XAUUSD",
    zone_config: Optional[ZoneMapConfig] = None,
    progress_every: int = 5000,
) -> tuple[list[dict], dict[str, Any]]:
    """
    FeaturePipeline → map every finalized bar → census.

    Returns (map_records, census_dict).
    """
    cfg = zone_config or ZoneMapConfig.from_prod_engine_runner()
    mapper = HistoricalZoneMapper(cfg)

    raw = pd.read_csv(csv_path)
    raw.columns = [c.strip().lower() for c in raw.columns]
    if "timestamp" not in raw.columns:
        if "date" in raw.columns and "time" in raw.columns:
            raw["timestamp"] = raw["date"].astype(str) + " " + raw["time"].astype(str)
        elif "date" in raw.columns:
            raw["timestamp"] = raw["date"]
        else:
            raise ValueError(f"No timestamp column in {csv_path}")

    pipeline = FeaturePipeline(raw)
    enriched, vectors = pipeline.run()
    ts_series = pd.to_datetime(enriched["timestamp"])
    n = len(vectors)
    records: list[dict] = []
    for i in range(n):
        vec = vectors[i]
        if hasattr(vec, "tolist"):
            vec = vec.tolist()
        feat = {name: float(vec[j]) for j, name in enumerate(CANONICAL_FEATURES)}
        # OHLCV from enriched when present
        for col in ("open", "high", "low", "close", "volume"):
            if col in enriched.columns:
                feat[col] = float(enriched.iloc[i][col])
        ts = ts_series.iloc[i].strftime("%Y-%m-%d %H:%M:%S")
        rec = mapper.map_row(
            feat, timestamp=ts, bar_index=i, instrument=instrument
        )
        records.append(rec)
        if progress_every and (i + 1) % progress_every == 0:
            print(f"  mapped {i + 1}/{n} bars…", flush=True)

    zone_ids = _registry_zone_ids(cfg.registry_path)
    labels = labels_from_map_records(records)
    census = compute_zone_census(labels, registry_zone_ids=zone_ids)
    census["meta"] = {
        "instrument": instrument,
        "csv_path": str(csv_path),
        "csv_sha256": _file_sha256(csv_path) if Path(csv_path).is_file() else "",
        "registry_path": cfg.registry_path,
        "registry_sha256": mapper._registry_sha256,
        "zone_cluster_threshold": cfg.zone_cluster_threshold,
        "top_k": cfg.top_k,
        "cluster_min_n": cfg.cluster_min_n,
        "cluster_spread_max": cfg.cluster_spread_max,
        "n_map_records": len(records),
        "feature_rows_after_finalize": n,
    }
    return records, census


def write_census_artifacts(
    census: dict[str, Any],
    out_dir: str | Path,
    *,
    stem: str = "zone_census",
    write_markdown: bool = True,
) -> dict[str, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    jp = out / f"{stem}.json"
    jp.write_text(json.dumps(census, indent=2), encoding="utf-8")
    paths["json"] = jp
    if write_markdown:
        mp = out / f"{stem}.md"
        title = f"Zone Geometry Census — {census.get('meta', {}).get('instrument', '')}"
        mp.write_text(census_to_markdown(census, title=title.strip()), encoding="utf-8")
        paths["md"] = mp
    return paths
