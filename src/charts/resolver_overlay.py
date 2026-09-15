"""resolver_overlay.py — precompute + serve the CRTStateResolver per-bar track for a chart.

Distinct from `charts.crt_overlay`, which reads the ENGINE (spine) track out of a run's
`events.jsonl`. This module runs `CRTStateResolver` (`features/market_crt_states.yaml`)
directly over a corpus and caches the result — the two tracks are DIFFERENT CONSTRUCTIONS
of "CRT state at bar t", not two measurements of the same thing (F-069: 88.16% agreement on
XAUUSD, EXPANSION recall 10.77%, structurally config-unreachable). Callers must show them as
two ribbons and never merge or reconcile them.

Reuses, unmodified, the exact chain `scripts/research/run_crt_state_on_mt5_xauusd.py`
established: `FeaturePipeline` -> `resolver_supply.build_resolver_supply` ->
`crt_state_resolver.build_htf_id_timeline` -> `CRTStateResolver.resolve` per bar. That chain
is a multi-minute pass over a full corpus, so it is NEVER run inside a dashboard request —
only via the offline CLI (`scripts/analysis/build_resolver_overlay.py`); the read path here
(`load_cached_track`) only ever reads a file.

KNOWN TRAP (recorded in project memory): `FeaturePipeline.run()` drops warmup rows and
resets the index. `states.csv` therefore holds one row per POST-WARMUP bar; alignment back
onto a full base series is by TIMESTAMP (never position), with warmup bars padded
`RESOLVER_UNAVAILABLE`.
"""
from __future__ import annotations

import csv as _csv
import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence

log = logging.getLogger("charts.resolver_overlay")

CACHE_ROOT = Path("results/charts/_resolver_cache")

RESOLVER_UNAVAILABLE = "UNAVAILABLE"
DEFAULT_VARIANT = "default"


def _sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()


def cache_dir(instrument: str, corpus_sha256: str, variant: str = DEFAULT_VARIANT) -> Path:
    return CACHE_ROOT / f"{instrument}__{corpus_sha256[:8]}__{variant}"


@dataclass(frozen=True)
class ResolverCacheResult:
    status: str                     # "ok" | "not_cached" | "stale_cache" | "error"
    states: list[str]
    source: str
    transitions: int
    variant_id: Optional[str] = None
    detail: Optional[str] = None

    def as_dict(self) -> dict:
        return {
            "status": self.status, "states": self.states, "source": self.source,
            "transitions": self.transitions, "variant_id": self.variant_id,
            "detail": self.detail,
        }


def build_and_cache(
    instrument: str,
    csv_path: str | Path,
    variant: str = DEFAULT_VARIANT,
) -> Path:
    """Run FeaturePipeline + CRTStateResolver over `csv_path` and cache the per-bar track.

    Offline-only (multi-minute on a full corpus). Returns the cache directory written.
    """
    import pandas as pd

    from data_ingestion.corpus_gate import admit_corpus
    from features.feature_pipeline import FeaturePipeline
    from features.crt_state_resolver import CRTStateResolver, build_htf_id_timeline
    from features.resolver_supply import build_resolver_supply
    from config_layer.production_config import get_prod_section

    csv_path = Path(csv_path)
    corpus_sha = _sha256_file(csv_path)

    admission = admit_corpus(str(csv_path), instrument, write_report=False,
                             enforce=False, log=log)
    df = pd.read_csv(admission.filepath)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    total_raw = len(df)

    pipeline = FeaturePipeline(df)
    enriched_df, vectors = pipeline.run()
    total_enriched = len(enriched_df)
    dropped = total_raw - total_enriched

    candles_per_htf = int(get_prod_section("backtest")["htf_candles_per_range"])
    full_htf_ids = build_htf_id_timeline(
        total_raw, candles_per_htf=candles_per_htf, instrument=instrument,
    )
    htf_ids = full_htf_ids[dropped:]
    if len(htf_ids) != total_enriched:
        raise ValueError(
            f"htf_id timeline length {len(htf_ids)} != enriched row count {total_enriched}"
        )

    resolver = CRTStateResolver()
    supply_rows, supply_stats = build_resolver_supply(resolver, enriched_df, vectors)
    resolver.reset_counts()
    resolver.reset_memory()

    timestamps = enriched_df["timestamp"].tolist()
    states: list[str] = []
    for i, feat_dict in enumerate(supply_rows):
        states.append(resolver.resolve(feat_dict, timestamp=timestamps[i], htf_id=htf_ids[i]))

    out_dir = cache_dir(instrument, corpus_sha, variant)
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(out_dir / "states.csv", "w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f)
        w.writerow(["timestamp", "state"])
        for ts, st in zip(timestamps, states):
            w.writerow([ts.isoformat() if hasattr(ts, "isoformat") else str(ts), st])

    meta = {
        "instrument": instrument,
        "corpus_path": str(csv_path).replace("\\", "/"),
        "corpus_sha256": corpus_sha,
        "corpus_rows": total_raw,
        "resolved_rows": total_enriched,
        "dropped_warmup_rows": dropped,
        "variant": variant,
        "variant_id": resolver.variant_id,
        "enabled_links": sorted(resolver.enabled_links),
        "waived_when_features": sorted(resolver.waived_when_features),
        "supply_set_id": supply_stats.get("supply_set_id"),
        "supply_fingerprint": supply_stats.get("supply_fingerprint"),
        "built_at": datetime.now().isoformat(),
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n",
                                        encoding="utf-8")
    log.info("resolver_overlay: cached %d states -> %s", len(states), out_dir)
    return out_dir


def load_cached_track(
    instrument: str,
    corpus_sha256: Optional[str],
    base_ts: Sequence[datetime],
    variant: str = DEFAULT_VARIANT,
) -> ResolverCacheResult:
    """Read a cached resolver track and align it onto `base_ts` BY TIMESTAMP.

    Never computes — a missing or sha-mismatched cache degrades honestly rather than
    blocking the request or fabricating a state (same discipline as `crt_overlay`).
    """
    n = len(base_ts)
    if not corpus_sha256:
        return ResolverCacheResult("not_cached", [RESOLVER_UNAVAILABLE] * n,
                                    "UNAVAILABLE:no_corpus_sha", 0)

    out_dir = cache_dir(instrument, corpus_sha256, variant)
    meta_path = out_dir / "meta.json"
    states_path = out_dir / "states.csv"
    if not meta_path.exists() or not states_path.exists():
        return ResolverCacheResult("not_cached", [RESOLVER_UNAVAILABLE] * n,
                                    "UNAVAILABLE:not_cached", 0)

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception as exc:                                       # noqa: BLE001
        return ResolverCacheResult("error", [RESOLVER_UNAVAILABLE] * n,
                                    f"UNAVAILABLE:meta_unreadable ({exc})", 0)

    if meta.get("corpus_sha256") != corpus_sha256:
        return ResolverCacheResult("stale_cache", [RESOLVER_UNAVAILABLE] * n,
                                    "UNAVAILABLE:stale_cache", 0,
                                    detail=f"cached={meta.get('corpus_sha256')} requested={corpus_sha256}")

    by_ts: dict[str, str] = {}
    try:
        with open(states_path, "r", newline="", encoding="utf-8") as f:
            for row in _csv.DictReader(f):
                by_ts[row["timestamp"]] = row["state"]
    except Exception as exc:                                       # noqa: BLE001
        return ResolverCacheResult("error", [RESOLVER_UNAVAILABLE] * n,
                                    f"UNAVAILABLE:states_unreadable ({exc})", 0)

    aligned = [by_ts.get(ts.isoformat(), RESOLVER_UNAVAILABLE) for ts in base_ts]
    transitions = sum(1 for i in range(1, n) if aligned[i] != aligned[i - 1]) if n else 0
    variant_id = meta.get("variant_id") or meta.get("variant") or variant
    return ResolverCacheResult("ok", aligned, f"RESOLVED:{variant_id}", transitions, variant_id)
