"""Episode store — canonical serialization + I/O.

FORMAT-AGNOSTIC BY DESIGN. The v1 backend is stdlib gzipped JSONL (one episode per
line) because `pyarrow`/`duckdb` are not installed in this environment — they appear
only under the `mt5_analytics` optional-dependency group in `pyproject.toml`. The
schema is unchanged by that choice: a Parquet backend can be added later behind the
same `write_episodes`/`read_episodes` interface with no migration.

Round-trip contract: `from_dict(to_dict(ep))` preserves `content_hash()` exactly.
The `derived` layer is a regenerable cache — `write_episodes(..., cache_derived=False)`
drops it from storage and `read_episodes(..., rebuild_derived=True)` reconstructs it.
"""
from __future__ import annotations

import gzip
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

from research.episodes.protocol import ARTIFACT_ROOT
from research.episodes.schema import (
    Annotations,
    Derived,
    EntrySnapshot,
    EpisodeProvenance,
    EpisodeStep,
    Observation,
    OpportunityEpisode,
    recompute_derived,
)


# ─────────────────────────────────────────────────────────────────
# SERIALIZATION
# ─────────────────────────────────────────────────────────────────
def to_dict(ep: OpportunityEpisode, *, cache_derived: bool = True) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    for s in ep.steps:
        row: dict[str, Any] = {"obs": asdict(s.obs)}
        if cache_derived and s.derived is not None:
            row["derived"] = asdict(s.derived)
        if s.annotations is not None:
            row["annotations"] = asdict(s.annotations)
        steps.append(row)
    return {
        "episode_id": ep.episode_id,
        "population": ep.population,
        "instrument": ep.instrument,
        "timeframe": ep.timeframe,
        "entry": asdict(ep.entry),
        "steps": steps,
        "provenance": asdict(ep.provenance),
        "metadata": ep.metadata,
        "content_hash": ep.content_hash(),
    }


def from_dict(d: dict[str, Any], *, rebuild_derived: bool = False) -> OpportunityEpisode:
    entry = EntrySnapshot(**d["entry"])
    observations = [Observation(**s["obs"]) for s in d["steps"]]

    if rebuild_derived:
        derived: list[Derived | None] = recompute_derived(entry, observations)
    else:
        derived = [
            Derived(**s["derived"]) if s.get("derived") is not None else None
            for s in d["steps"]
        ]

    steps = [
        EpisodeStep(
            obs=o,
            derived=dv,
            annotations=Annotations(**s["annotations"]) if s.get("annotations") else None,
        )
        for o, dv, s in zip(observations, derived, d["steps"])
    ]
    return OpportunityEpisode(
        episode_id=d["episode_id"],
        population=d["population"],
        instrument=d["instrument"],
        timeframe=d["timeframe"],
        entry=entry,
        steps=steps,
        provenance=EpisodeProvenance(**d["provenance"]),
        metadata=dict(d.get("metadata") or {}),
    )


# ─────────────────────────────────────────────────────────────────
# LAYOUT
# ─────────────────────────────────────────────────────────────────
def corpus_dir(root: Path | str, population: str, instrument: str) -> Path:
    return Path(root) / population / instrument


def default_root(repo_root: Path | str) -> Path:
    return Path(repo_root) / ARTIFACT_ROOT


# ─────────────────────────────────────────────────────────────────
# I/O
# ─────────────────────────────────────────────────────────────────
def write_episodes(
    episodes: Iterable[OpportunityEpisode],
    out_dir: Path | str,
    *,
    filename: str = "episodes.jsonl.gz",
    cache_derived: bool = True,
) -> dict[str, Any]:
    """Write a corpus shard. Returns a manifest (counts, bytes, hashes).

    `bytes_on_disk` is what the P5 sizing gate consumes: the DETECTION_STREAM
    population is ~140k detections × T=40, so the corpus must be measured on one
    instrument before a full build is attempted (substrate §7).
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename

    n = 0
    hashes: list[str] = []
    with gzip.open(path, "wt", encoding="utf-8", newline="\n") as fh:
        for ep in episodes:
            d = to_dict(ep, cache_derived=cache_derived)
            hashes.append(d["content_hash"])
            fh.write(json.dumps(d, sort_keys=True, separators=(",", ":"), default=str) + "\n")
            n += 1

    manifest = {
        "path": str(path),
        "n_episodes": n,
        "cache_derived": cache_derived,
        "bytes_on_disk": path.stat().st_size,
        "bytes_per_episode": round(path.stat().st_size / n, 2) if n else 0,
        "content_hashes_sample": hashes[:5],
        "backend": "gzip_jsonl_v1",
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest


def read_episodes(
    path: Path | str,
    *,
    rebuild_derived: bool = False,
    limit: int | None = None,
) -> Iterator[OpportunityEpisode]:
    """Stream episodes back. Lazy — never loads a whole corpus into memory."""
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            if limit is not None and i >= limit:
                return
            line = line.strip()
            if not line:
                continue
            yield from_dict(json.loads(line), rebuild_derived=rebuild_derived)


def verify_corpus(path: Path | str) -> dict[str, Any]:
    """Re-derive every stored content_hash and report mismatches."""
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    n = 0
    mismatches: list[str] = []
    with opener(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            n += 1
            if from_dict(d).content_hash() != d.get("content_hash"):
                mismatches.append(d.get("episode_id", "?"))
    return {"n": n, "n_mismatch": len(mismatches), "mismatched_ids": mismatches[:20],
            "ok": not mismatches}


def sizing_probe(episodes: Sequence[OpportunityEpisode]) -> dict[str, Any]:
    """Measured bytes/episode for both storage modes — the P5 gate's instrument."""
    def _bytes(cache: bool) -> int:
        blob = "\n".join(
            json.dumps(to_dict(e, cache_derived=cache), sort_keys=True,
                       separators=(",", ":"), default=str)
            for e in episodes
        )
        return len(gzip.compress(blob.encode("utf-8")))

    n = len(episodes)
    if not n:
        return {"n": 0}
    full, lean = _bytes(True), _bytes(False)
    steps = sum(len(e.steps) for e in episodes)
    return {
        "n_episodes": n,
        "total_steps": steps,
        "mean_steps": round(steps / n, 2),
        "gz_bytes_with_derived": full,
        "gz_bytes_observation_only": lean,
        "gz_bytes_per_episode_with_derived": round(full / n, 2),
        "gz_bytes_per_episode_observation_only": round(lean / n, 2),
        "derived_cache_overhead_pct": round(100 * (full - lean) / lean, 1) if lean else 0,
    }
