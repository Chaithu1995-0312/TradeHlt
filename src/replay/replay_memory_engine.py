"""
replay_memory_engine.py
=======================
Persistent institutional memory layer.

Reads historical opportunity JSONL files, indexes by cluster assignment,
and answers similarity queries about past market states.

All I/O is lazy-loaded and cached. Fail-open on any disk error.
Deterministic: all operations are read-only after _load(); no state mutation.

Production safety:
  - max_records cap prevents unbounded memory growth
  - Temporal decay exp(-λ × age_days) discounts old records
  - Staleness threshold rejects very old records entirely
  - No RNG; no side effects after construction

Consumed by:
  - CognitiveBus._process()  (async, after every EngineRunner decision)
  - ReplayDriftGovernor.audit()  (periodic, called after scanner runs)
"""
from __future__ import annotations

import json
import logging
import math
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("ReplayMemoryEngine")

# Config defaults (overridden via production config "replay_memory" section)
_DEFAULT_MAX_RECORDS             = 50_000
_DEFAULT_DECAY_HALF_LIFE_DAYS    = 30.0
_DEFAULT_MIN_CLUSTER_SAMPLES     = 5
_DEFAULT_STALENESS_THRESHOLD_DAYS = 90.0

# Threshold above which opportunity JSONL files are flagged systemically corrupted.
MAX_CORRUPTION_RATIO: float = 0.10

try:
    from src.utils.integrity_events import emit_integrity_event  # noqa: F401
except Exception:  # pragma: no cover
    def emit_integrity_event(*_a, **_kw):  # type: ignore[no-redef]
        return None

try:
    from src.utils.registry_refresh import RegistryWatcher  # noqa: F401
except Exception:  # pragma: no cover
    try:
        from utils.registry_refresh import RegistryWatcher  # type: ignore[no-redef]
    except Exception:
        class RegistryWatcher:  # type: ignore[no-redef]
            def __init__(self, *_a, **_kw): pass
            def needs_reload(self) -> bool: return False
            def mark_loaded(self) -> None: pass


class ReplayRecord:
    """Lightweight immutable replay record."""
    __slots__ = (
        "timestamp", "instrument", "direction",
        "outcome", "rr_achieved", "cluster_id",
        "features", "age_days",
        "strategy_id",   # Phase D: winning strategy ID ("S1" | "S3" | "" if unknown)
    )

    def __init__(
        self,
        timestamp:   str,
        instrument:  str,
        direction:   str,
        outcome:     str,
        rr_achieved: float,
        cluster_id:  int,
        features:    list,
        age_days:    float,
        strategy_id: str = "",
    ):
        self.timestamp   = timestamp
        self.instrument  = instrument
        self.direction   = direction
        self.outcome     = outcome
        self.rr_achieved = rr_achieved
        self.cluster_id  = cluster_id
        self.features    = features
        self.age_days    = age_days
        self.strategy_id = strategy_id


class ClusterStats:
    """Aggregated statistics for one zone cluster."""
    __slots__ = (
        "cluster_id", "n_samples", "win_rate", "mean_rr",
        "std_rr", "failure_modes", "trap_frequency",
        "staleness_days", "centroid",
    )

    def __init__(self, cluster_id: int):
        self.cluster_id    = cluster_id
        self.n_samples     = 0
        self.win_rate      = 0.0
        self.mean_rr       = 0.0
        self.std_rr        = 0.0
        self.failure_modes: dict = {}
        self.trap_frequency = 0.0
        self.staleness_days = 0.0
        self.centroid:      list = []


class ReplayMemoryEngine:
    """
    Institutional memory layer backed by historical opportunity JSONL files.

    Parameters
    ----------
    opportunities_dir : Path or str
        Directory (or single file) containing opportunities.jsonl files.
    zone_registry_path : str
        Path to the active zone registry JSON (for cluster assignment).
    max_records : int
        Hard cap on in-memory records (keeps most recent).
    decay_half_life_days : float
        Temporal decay half-life in days (default 30).
    min_cluster_samples : int
        Minimum samples for cluster statistics to be used.
    staleness_threshold_days : float
        Records older than this are excluded from statistics.
    """

    def __init__(
        self,
        opportunities_dir:        "Path | str" = "logs",
        zone_registry_path:       str          = "models/zone_registry.json",
        max_records:              int          = _DEFAULT_MAX_RECORDS,
        decay_half_life_days:     float        = _DEFAULT_DECAY_HALF_LIFE_DAYS,
        min_cluster_samples:      int          = _DEFAULT_MIN_CLUSTER_SAMPLES,
        staleness_threshold_days: float        = _DEFAULT_STALENESS_THRESHOLD_DAYS,
    ):
        self._opps_dir        = Path(opportunities_dir)
        self._zone_path       = Path(zone_registry_path)
        self._max_records     = max_records
        self._decay_lambda    = math.log(2.0) / max(decay_half_life_days, 1.0)
        self._min_cluster_samples = min_cluster_samples
        self._staleness_threshold = staleness_threshold_days

        # Lazy-loaded state (populated on first query)
        self._records:       List[ReplayRecord]      = []
        self._cluster_stats: Dict[int, ClusterStats] = {}
        self._zone_registry: Optional[dict]          = None
        self._loaded:        bool                    = False

        # Hot-reload watcher on the zone registry file. When discover_zones.py
        # promotes a new clustering, the next query() reloads automatically.
        self._zone_watcher = RegistryWatcher(self._zone_path)

    # ── Public API ────────────────────────────────────────────────────────────

    def query(self, feature_vector: list, cluster_id: int) -> dict:
        """
        Query memory for a cluster-conditioned intelligence summary.

        Parameters
        ----------
        feature_vector : list of float (canonical, 35 or 38 dim)
        cluster_id     : zone cluster assignment for current bar

        Returns
        -------
        dict with keys:
            similarity_score, matched_cluster, historical_winrate,
            historical_rr, failure_modes, sample_size, replay_density,
            cluster_stability, temporal_confidence
        """
        if not self._loaded:
            self._load()
            self._zone_watcher.mark_loaded()
        elif self._zone_watcher.needs_reload():
            logger.info(
                "ReplayMemory: zone registry changed at %s; reloading", self._zone_path
            )
            self._loaded = False
            self._records = []
            self._cluster_stats = {}
            self._load()

        stats = self._cluster_stats.get(cluster_id)
        if stats is None or stats.n_samples < self._min_cluster_samples:
            return self._empty_result(cluster_id, reason="insufficient_samples")

        # Decay-weighted win rate (recent trades count more)
        cluster_records = [r for r in self._records if r.cluster_id == cluster_id]
        decay_wins = decay_total = 0.0
        for rec in cluster_records:
            w = math.exp(-self._decay_lambda * rec.age_days)
            decay_wins  += w * (1.0 if rec.rr_achieved >= 1.0 else 0.0)
            decay_total += w
        decay_winrate = (decay_wins / decay_total) if decay_total > 0 else stats.win_rate

        # Freshness: fraction of records within staleness threshold
        fresh = sum(
            1 for r in cluster_records if r.age_days <= self._staleness_threshold
        )
        density = min(1.0, fresh / max(self._max_records / 20.0, 1.0))

        # Cluster stability: 1 - std_rr / (|mean_rr| + 1)
        stability = max(0.0, 1.0 - stats.std_rr / (abs(stats.mean_rr) + 1.0))
        stability = min(1.0, stability)

        temporal_conf = min(1.0, fresh / max(stats.n_samples, 1))

        return {
            "similarity_score":    round(self._centroid_similarity(feature_vector, stats.centroid), 4),
            "matched_cluster":     cluster_id,
            "historical_winrate":  round(decay_winrate, 4),
            "historical_rr":       round(stats.mean_rr, 4),
            "failure_modes":       list(stats.failure_modes.items())[:3],
            "sample_size":         stats.n_samples,
            "replay_density":      round(density, 4),
            "cluster_stability":   round(stability, 4),
            "temporal_confidence": round(temporal_conf, 4),
        }

    def get_replay_features(self, cluster_id: int) -> dict:
        """
        Return replay-derived feature dict for TradeNet meta-cognition input.

        All values are float. Returns neutral defaults on failure.
        """
        result = self.query([], cluster_id)
        return {
            "historical_winrate":     result.get("historical_winrate",  0.5),
            "historical_rr":          result.get("historical_rr",       0.0),
            "historical_drawdown":    self._cluster_drawdown(cluster_id),
            "cluster_stability":      result.get("cluster_stability",   0.5),
            "replay_density":         result.get("replay_density",      0.0),
            "failure_frequency":      self._failure_frequency(cluster_id),
            "trap_frequency":         self._trap_frequency(cluster_id),
            "transition_probability": self._transition_probability(cluster_id),
            "market_state_entropy":   self._market_state_entropy(cluster_id),
        }

    def load(self) -> "ReplayMemoryEngine":
        """Explicitly trigger loading (otherwise lazy on first query())."""
        self._load()
        return self

    # ── Private ───────────────────────────────────────────────────────────────

    def _load(self) -> None:
        """Load all JSONL replay artifacts and build cluster statistics."""
        if self._loaded:
            return
        try:
            self._zone_registry = self._load_zone_registry()
            jsonl_files = self._discover_jsonl_files()
            now_ts = time.time()
            records: List[ReplayRecord] = []

            for path in jsonl_files:
                try:
                    records.extend(self._parse_jsonl(path, now_ts))
                except Exception as exc:
                    logger.warning("ReplayMemory: skipping %s — %s", path, exc)

            # Cap: keep most recent
            if len(records) > self._max_records:
                records = sorted(records, key=lambda r: r.age_days)[:self._max_records]

            self._records = records
            self._build_cluster_stats()
            self._loaded = True
            logger.info(
                "ReplayMemory: loaded %d records from %d files, %d clusters",
                len(self._records), len(jsonl_files), len(self._cluster_stats),
            )
        except Exception as exc:
            logger.warning("ReplayMemory: load failed (fail-open) — %s", exc)
            self._records       = []
            self._cluster_stats = {}
            self._loaded        = True  # prevent retry loop

    def _load_zone_registry(self) -> Optional[dict]:
        if not self._zone_path.exists():
            return None
        try:
            return json.loads(self._zone_path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _discover_jsonl_files(self) -> list:
        """Find all opportunities.jsonl files under opps_dir (max 200 files)."""
        if self._opps_dir.is_file():
            return [self._opps_dir]
        if not self._opps_dir.exists():
            return []
        found = []
        for p in self._opps_dir.rglob("opportunities.jsonl"):
            found.append(p)
            if len(found) >= 200:
                break
        return found

    def _parse_jsonl(self, path: Path, now_ts: float) -> List[ReplayRecord]:
        records = []
        malformed = 0
        valid = 0
        with path.open("r", encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                # Separate JSON-parse failures (corruption) from record-shape
                # rejects (KeyError / ValueError) so only the former emits
                # integrity events.
                try:
                    rec = json.loads(line)
                    valid += 1
                except json.JSONDecodeError as exc:
                    malformed += 1
                    emit_integrity_event(
                        "JSONL_CORRUPTION",
                        "WARNING",
                        "src.replay.replay_memory_engine",
                        {
                            "path":        str(path),
                            "line_number": lineno,
                            "raw_preview": line[:160],
                            "error":       str(exc),
                        },
                    )
                    continue
                try:
                    if rec.get("type") == "run_header":
                        continue
                    features_dict = rec.get("features", {})
                    if not features_dict:
                        continue

                    age_days = self._age_days(rec.get("timestamp", ""), now_ts)
                    if age_days > self._staleness_threshold * 2:
                        continue  # very stale — skip entirely

                    cluster_id     = self._assign_cluster(features_dict)
                    features_list  = [float(v) for v in features_dict.values()]

                    records.append(ReplayRecord(
                        timestamp   = str(rec.get("timestamp", "")),
                        instrument  = str(rec.get("instrument", "")),
                        direction   = str(rec.get("direction", "long")),
                        outcome     = str(rec.get("outcome", "UNKNOWN")),
                        rr_achieved = float(rec.get("rr_achieved", 0.0)),
                        cluster_id  = cluster_id,
                        features    = features_list,
                        age_days    = age_days,
                        # Phase D: backward-compatible — old records have no strategy key
                        strategy_id = str(rec.get("strategy", {}).get("winning_id", "")
                                         if isinstance(rec.get("strategy"), dict)
                                         else rec.get("strategy_id", "")),
                    ))
                except (KeyError, ValueError):
                    continue
        total = malformed + valid
        if total and (malformed / total) > MAX_CORRUPTION_RATIO:
            emit_integrity_event(
                "JSONL_CORRUPTION_THRESHOLD_EXCEEDED",
                "ERROR",
                "src.replay.replay_memory_engine",
                {
                    "path":             str(path),
                    "malformed_lines":  malformed,
                    "valid_lines":      valid,
                    "corruption_ratio": malformed / total,
                },
            )
        return records

    def _age_days(self, ts_str: str, now_ts: float) -> float:
        """Parse ISO or 'YYYY-MM-DD HH:MM:SS' timestamp and return age in days."""
        if not ts_str:
            return 0.0
        import datetime
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt    = datetime.datetime.strptime(ts_str[:19], fmt)
                dt_ts = dt.replace(tzinfo=datetime.timezone.utc).timestamp()
                return max(0.0, (now_ts - dt_ts) / 86400.0)
            except ValueError:
                continue
        return 0.0

    @staticmethod
    def _zone_cluster_id(zone: dict, schema_version: str) -> int:
        """
        Integer cluster id for a zone, dispatched by schema_version (explicit, fail-fast).

        Two registry schemas are officially in use and intentionally coexist:
          schema_version="zone_v1"     → zone["zone_id"] is already an int
                                          (RME per-instrument / models/replay/*.json)
          schema_version="v2_gaussian" → zone["id"] is a "zone_N" string; the cluster id
                                          is the trailing int (default models/zone_registry.json)

        Per §6.5 (no silent defaults), an unknown schema raises rather than guessing —
        the caller's fail-open wrapper logs it as a load failure instead of corrupting
        cluster ids with a hidden 0.
        """
        if schema_version == "zone_v1":
            return int(zone["zone_id"])
        if schema_version == "v2_gaussian":
            return int(str(zone["id"]).rsplit("_", 1)[-1])
        raise ValueError(f"ReplayMemory: unknown zone registry schema_version={schema_version!r}")

    def _assign_cluster(self, features_dict: dict) -> int:
        """
        Assign cluster ID via nearest zone center. Falls back to 0.

        Centers are written by the producer (scripts/research/discover_zones.py)
        in *weighted* feature space (each feature scaled by feature_weights before
        K-Means), so the query vector must be weighted the same way before the
        distance — otherwise raw OHLCV scale dominates and every record collapses
        to cluster 0 (the 2026-06-02 RME repair; see docs/topics/replay-memory.md).
        """
        if self._zone_registry is None:
            return 0
        zones = self._zone_registry.get("zones", [])
        if not zones:
            return 0

        feature_order = self._zone_registry.get(
            "feature_order", list(features_dict.keys())
        )
        weights = self._zone_registry.get("feature_weights", [])
        vec = [
            float(features_dict.get(k, 0.0)) * (weights[i] if i < len(weights) else 1.0)
            for i, k in enumerate(feature_order)
        ]

        best_id, best_dist = 0, float("inf")
        for zone in zones:
            center = zone.get("center", zone.get("centroid", []))
            if not center:
                continue
            n = min(len(vec), len(center))
            d = sum((vec[i] - center[i]) ** 2 for i in range(n))
            if d < best_dist:
                best_dist = d
                best_id   = int(zone.get("zone_id", 0))
        return best_id

    def _build_cluster_stats(self) -> None:
        cluster_records: Dict[int, list] = defaultdict(list)
        for rec in self._records:
            cluster_records[rec.cluster_id].append(rec)

        zone_reg  = self._zone_registry or {}
        sv        = zone_reg.get("schema_version", "")
        zones     = {self._zone_cluster_id(z, sv): z for z in zone_reg.get("zones", [])}

        for cid, recs in cluster_records.items():
            cs           = ClusterStats(cid)
            cs.n_samples = len(recs)

            rr_vals      = [r.rr_achieved for r in recs]
            cs.mean_rr   = sum(rr_vals) / len(rr_vals)
            variance     = sum((v - cs.mean_rr) ** 2 for v in rr_vals) / max(len(rr_vals), 1)
            cs.std_rr    = math.sqrt(variance)

            wins         = sum(1 for r in recs if r.rr_achieved >= 1.0)
            cs.win_rate  = wins / cs.n_samples

            outcome_counts: Dict[str, int] = defaultdict(int)
            for r in recs:
                outcome_counts[r.outcome] += 1
            cs.failure_modes = dict(outcome_counts)

            traps              = sum(1 for r in recs if r.outcome == "SL_HIT" and r.rr_achieved < 0)
            cs.trap_frequency  = traps / cs.n_samples
            cs.staleness_days  = sum(r.age_days for r in recs) / cs.n_samples

            if cid in zones and zones[cid].get("centroid"):
                cs.centroid = zones[cid]["centroid"]
            elif recs and recs[0].features:
                n_feat      = len(recs[0].features)
                cs.centroid = [
                    sum(r.features[i] for r in recs if i < len(r.features)) / cs.n_samples
                    for i in range(n_feat)
                ]

            self._cluster_stats[cid] = cs

    def _centroid_similarity(self, vec: list, centroid: list) -> float:
        if not centroid or not vec:
            return 0.5
        n     = min(len(vec), len(centroid))
        dot   = sum(vec[i] * centroid[i] for i in range(n))
        nv    = math.sqrt(sum(x ** 2 for x in vec[:n]))    or 1e-12
        nc    = math.sqrt(sum(x ** 2 for x in centroid[:n])) or 1e-12
        return max(0.0, min(1.0, dot / (nv * nc)))

    def _cluster_drawdown(self, cluster_id: int) -> float:
        recs = [r for r in self._records if r.cluster_id == cluster_id]
        if not recs:
            return 0.0
        neg = [r.rr_achieved for r in recs if r.rr_achieved < 0]
        return abs(sum(neg) / max(len(neg), 1)) if neg else 0.0

    def _failure_frequency(self, cluster_id: int) -> float:
        cs = self._cluster_stats.get(cluster_id)
        if cs is None or cs.n_samples == 0:
            return 0.5
        return cs.failure_modes.get("SL_HIT", 0) / cs.n_samples

    def _trap_frequency(self, cluster_id: int) -> float:
        cs = self._cluster_stats.get(cluster_id)
        return cs.trap_frequency if cs else 0.0

    def _transition_probability(self, cluster_id: int) -> float:
        recs = [r for r in self._records if r.cluster_id == cluster_id]
        if not recs:
            return 0.0
        return sum(1 for r in recs if r.outcome == "TIMEOUT") / len(recs)

    def _market_state_entropy(self, cluster_id: int) -> float:
        cs = self._cluster_stats.get(cluster_id)
        if cs is None or cs.n_samples == 0:
            return 1.0
        total   = cs.n_samples
        entropy = 0.0
        for count in cs.failure_modes.values():
            p = count / total
            if p > 0:
                entropy -= p * math.log2(p)
        max_entropy = math.log2(max(len(cs.failure_modes), 2))
        return round(entropy / max_entropy, 4) if max_entropy > 0 else 0.0

    def _empty_result(self, cluster_id: int, reason: str = "") -> dict:
        return {
            "similarity_score":    0.0,
            "matched_cluster":     cluster_id,
            "historical_winrate":  0.5,
            "historical_rr":       0.0,
            "failure_modes":       [],
            "sample_size":         0,
            "replay_density":      0.0,
            "cluster_stability":   0.5,
            "temporal_confidence": 0.0,
            "_reason":             reason,
        }
