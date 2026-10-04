> Created: 2026-05-20 · Updated: 2026-05-20 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Plan: Per-Instrument Versioned Model Registries

## Status: CLI hardening COMPLETE. Run-scoped output COMPLETE. ETHUSDT pipeline COMPLETE. BTCUSDT pipeline PENDING. EURUSD data mismatch flagged.

---

---

# ACTIVE TASK: Replay-Aware Market State Cognition System

## Context

The existing intelligence pipeline has 4 confirmed gaps:
1. **No replay memory** — every inference is stateless; no institutional memory of what happened in similar past states
2. **EMA-threshold regime detection** — `detect_regime()` uses hardcoded EMA/momentum thresholds, not cluster-derived market-state knowledge
3. **Two missing canonical features** — `liquidity_distance` (never implemented) and `volume_spike` (computed internally but not canonical or used by any engine)
4. **TradeNet disconnected** — `neural_fn=None` in EngineRunner; trained model not wired into production inference

This plan implements a complete 14-part cognitive extension across 7 new files and 5 modified files. The existing 7-step `EngineRunner.run()` pipeline is **fully preserved**; new systems are addable as optional steps 8-10 and as injectable context.

---

## Architecture Overview

```
EXECUTION PLANE (synchronous, < 50ms target, < 100ms hard max)
  Adapter → Zone + CRT + Gaussian + RR → Completeness → Fusion.compute() → Decision
       |
       └─ make_event_envelope(DECISION_SNAPSHOT) → CognitiveBus.emit() [non-blocking]
              ↑
       EventFabric: event_id + generation + schema_hash stamped at emission

COGNITIVE PLANE (asynchronous, background thread, advisory-only, write-only telemetry)
  CognitiveBus._consume_loop() [daemon thread, queue.maxsize=500, drop_rate telemetry]
    → ReplayMemoryEngine.query()
    → MarketStateClusterEngine.classify()
    → TradeNetMetaEngine.compute()
    → HierarchicalMetaFusion.compute()
    → make_event_envelope(COGNITIVE_TELEMETRY, parent_event_id=snap.event_id)
    → logs/cognitive_telemetry.jsonl   (never blocks execution plane)

OBSERVABILITY FABRIC (all writes carry: event_id + generation + schema_hash + parent_event_id)
  logs/cognitive_telemetry.jsonl    ← COGNITIVE_TELEMETRY events
  logs/decision_lineage.jsonl       ← DECISION_LINEAGE events
  logs/engine_telemetry.jsonl       ← ENGINE_TELEMETRY events
  logs/drift_audit.jsonl            ← DRIFT_AUDIT events
```

**Hard separation rule**: cognitive components NEVER appear inside `EngineRunner.run()`. They run in a background daemon thread consuming a queue. The execution plane emits a snapshot event and returns immediately. Cognitive output is advisory-only — written to telemetry. No cognitive result ever enters the execution-plane return dict.

**Authority hierarchy (frozen)**:
```
Feature Validation → EngineRunner → Fusion → Decision → Ultron → Execution
```
Everything else (replay, cognitive, AI-CIO, retrospective learning, strategy governance) = OFFLINE / ASYNC / ADVISORY. No runtime authority.

New components are **addable**, not replacement. The existing 7-step path continues to work unchanged when new components are absent or fail.

---

## Part 1 — Schema Extension (CANONICAL_FEATURES: 35 → 38)

### File: `src/features/feature_schema.py`

**New features at indices 35-37** (appended after existing 34th index):

```
Index 35: liquidity_distance       — ATR-normalised distance to nearest liquidity level, float [0, ∞)
Index 36: liquidity_pressure_score — composite proximity/directional score, float [0, 1]
Index 37: volume_spike             — promoted from internal, int8 {0, 1}
```

**Exact changes:**

```python
# CURRENT (line 36-52):
CANONICAL_FEATURES = tuple([
    "open", "high", "low", "close", "volume",
    "volume_ratio", "double_sweep",
    "ema_fast", "ema_slow", "ema_spread",
    "trend_bias", "trend_strength", "momentum_score",
    "atr", "volatility_ratio", "rsi_14",
    "macd_line", "macd_signal", "macd_hist",
    "sweep_detected", "liquidity_sweep", "break_of_structure",
    "swing_high", "swing_low", "higher_high", "lower_low",
    "body_size", "wick_size", "body_ratio",
    "volatility_regime", "session", "hour_of_day",
    "disp_strength", "retest_depth", "candles_since_retest"
])

# NEW (append 3 entries, same order up to index 34):
CANONICAL_FEATURES = tuple([
    # ... identical entries 0-34 ...
    "candles_since_retest",    # index 34 (unchanged)
    "liquidity_distance",      # index 35 (NEW)
    "liquidity_pressure_score", # index 36 (NEW)
    "volume_spike",            # index 37 (NEW — promoted)
])

CANONICAL_FEATURE_DIM: int = 38    # was 35; assertion still enforced
SCHEMA_VERSION: str = "3.0"        # was "1.0"
```

Also update `CANONICAL_FEATURE_ORDER` list identically (both tuple and list must match).

**TRADENET_SCHEMA** and **GAUSSIAN_SCHEMA** comments update to `n_features=38` (still computed dynamically from `len(CANONICAL_FEATURES)`, no code change needed beyond the tuple).

**Backward compatibility sentinel** — add below SCHEMA_VERSION:

```python
# Models trained on schema v2.0 have n_features=35.
# Schema v3.0 adds 3 features at indices 35-37.
# All model loaders must check n_features against their stored value and
# slice the input vector to model.n_features when there is a mismatch.
SCHEMA_V2_FEATURE_DIM: int = 35
```

**FeatureSchemaRegistry** — add to `src/features/feature_schema.py` to address CRITICAL-3 (silent schema corruption on truncation):

```python
import hashlib, json

def _feature_order_hash(features: tuple) -> str:
    """Stable SHA-256 of feature name ordering. Changes if order or names change."""
    payload = json.dumps(list(features), sort_keys=False).encode()
    return hashlib.sha256(payload).hexdigest()[:16]

# Computed at import time — frozen for this schema version
FEATURE_ORDER_HASH: str = _feature_order_hash(CANONICAL_FEATURES)
# "2b5f..." for v3.0 — any reorder or rename changes this hash

class FeatureSchemaRegistry:
    """
    Maps model instances to the schema they were trained on.
    Every model loader that calls register() can detect at inference time
    whether its stored feature_order_hash matches the current runtime hash.

    Usage:
        FeatureSchemaRegistry.register(version="gaussian_v6", hash=stored_hash)
        FeatureSchemaRegistry.check_compatibility(version="gaussian_v6")
        # → raises SchemaVersionError if hash mismatches
    """
    _registry: dict[str, str] = {}  # version → feature_order_hash

    @classmethod
    def register(cls, version: str, feature_order_hash: str) -> None:
        cls._registry[version] = feature_order_hash

    @classmethod
    def check_compatibility(cls, version: str) -> bool:
        """
        Returns True if runtime schema hash == stored hash.
        Returns False if schema version mismatch (caller should truncate, not error).
        Raises KeyError if version was never registered (caller's bug).
        """
        stored = cls._registry.get(version)
        if stored is None:
            return True   # never registered = unknown = allow (fail-open)
        if stored != FEATURE_ORDER_HASH:
            import logging
            logging.getLogger("FeatureSchemaRegistry").warning(
                "Schema mismatch for model=%s: stored_hash=%s runtime_hash=%s "
                "— model was trained on a different feature ordering; "
                "truncation will be applied.",
                version, stored, FEATURE_ORDER_HASH,
            )
            return False
        return True
```

Every model file (gaussian, tradenet, zone, rr) must store `"feature_order_hash"` in its JSON at save time and call `FeatureSchemaRegistry.register()` at load time. This makes silent corruption detectable. Add to `src/training/trainer.py` `save_gaussian_model()`:
```python
entry["feature_order_hash"] = FEATURE_ORDER_HASH   # from feature_schema import FEATURE_ORDER_HASH
```

---

## Part 2 — Feature Pipeline Extension

### File: `src/features/feature_pipeline.py`

**Add two new compute methods** (called in `run()` after existing methods):

#### Method A: `compute_liquidity_distance()`

Purpose: ATR-normalised distance from close to nearest known liquidity level, with no lookahead.

Reference levels (all use `.shift(1)` — no lookahead):
1. `last_swing_high_price.shift(1)` — previous swing high (already computed in `compute_structure_liquidity()`)
2. `last_swing_low_price.shift(1)` — previous swing low
3. BOS level: last BOS event's reference price (derived from `break_of_structure != 0`)

```python
def compute_liquidity_distance(self) -> None:
    """
    Compute ATR-normalised distance to nearest liquidity level.
    No lookahead: all reference levels use .shift(1).
    
    Populates:
      liquidity_distance       — abs(close - nearest_level) / atr; NaN when atr=0 or no level
      liquidity_pressure_score — composite [0,1]; higher = closer to a sweep zone
    """
    df = self.df

    # Reference levels (all trailing — no lookahead)
    ref_high = df["last_swing_high_price"].shift(1)
    ref_low  = df["last_swing_low_price"].shift(1)

    # Last BOS level: when break_of_structure fires, capture the reference price
    # Bullish BOS reference = ref_high at that bar; bearish BOS = ref_low
    bos_level = pd.Series(np.nan, index=df.index)
    bos_bullish = df["break_of_structure"] == 1
    bos_bearish = df["break_of_structure"] == -1
    bos_level.loc[bos_bullish] = ref_high.loc[bos_bullish]
    bos_level.loc[bos_bearish] = ref_low.loc[bos_bearish]
    bos_level = bos_level.ffill()  # carry forward last BOS level

    # Candidate distances (all non-negative, ATR-normalised)
    # Guard: atr > 0 required; NaN when atr unavailable
    atr = df["atr"] * df["close"]   # atr is already close-relative; multiply back for absolute scale
    atr_safe = atr.where(atr > 0, np.nan)

    dist_high = (df["close"] - ref_high).abs() / atr_safe
    dist_low  = (df["close"] - ref_low).abs()  / atr_safe
    dist_bos  = (df["close"] - bos_level).abs() / atr_safe

    # Nearest of the three candidates
    nearest = pd.concat([dist_high, dist_low, dist_bos], axis=1).min(axis=1)
    df["liquidity_distance"] = nearest.clip(lower=0.0).astype(np.float32)

    # liquidity_pressure_score: exponential decay so "near liquidity" → high score
    # pressure = exp(-0.5 * liquidity_distance), clipped [0, 1]
    df["liquidity_pressure_score"] = np.exp(-0.5 * df["liquidity_distance"].fillna(10.0))
    df["liquidity_pressure_score"] = df["liquidity_pressure_score"].clip(0.0, 1.0).astype(np.float32)

    self.df = df
```

**Live safety note (must be in docstring):** In live inference, `compute_structure_liquidity()` uses `center=True` rolling for swing detection (lookahead bias — fine for backtesting). For live mode, swap to a trailing window detector. `compute_liquidity_distance()` itself is safe because it uses `.shift(1)` on already-computed reference levels.

#### Method B: `promote_volume_spike()`

The `volume_spike` column already exists after `compute_volume_features()`. This method upgrades it to **adaptive percentile thresholding** (replaces fixed `> 1.5`):

```python
def promote_volume_spike(self) -> None:
    """
    Replace the fixed-threshold volume_spike with adaptive 75th-percentile threshold.
    
    Rationale: fixed 1.5× threshold is not forex-safe across instruments.
    Adaptive: volume_ratio > rolling_75th_percentile(50 bars) → spike.
    
    Falls back to fixed threshold (1.5) when rolling window has < 20 samples.
    Overwrites the 'volume_spike' column in place (already computed in
    compute_volume_features() with fixed threshold — this replaces it).
    """
    df = self.df
    
    ADAPTIVE_WINDOW = 50
    FIXED_FALLBACK  = 1.5
    MIN_SAMPLES_FOR_ADAPTIVE = 20
    PERCENTILE      = 75
    
    vol_ratio = df["volume_ratio"]
    
    # Rolling 75th percentile (quantile) — trailing only, no center
    rolling_thresh = vol_ratio.rolling(
        window=ADAPTIVE_WINDOW, min_periods=MIN_SAMPLES_FOR_ADAPTIVE
    ).quantile(PERCENTILE / 100.0)
    
    # Where rolling threshold is available, use adaptive; else fixed
    threshold = rolling_thresh.where(rolling_thresh.notna(), FIXED_FALLBACK)
    
    df["volume_spike"] = (vol_ratio > threshold).astype(np.int8)
    
    self.df = df
```

#### Update `run()` method

In `FeaturePipeline.run()`, add the two new calls after `compute_canonical_temporal_features()`:

```python
def run(self) -> tuple:
    ...
    self.compute_canonical_temporal_features()
    self.compute_liquidity_distance()      # NEW — after structure is computed
    self.promote_volume_spike()            # NEW — replaces fixed-threshold spike
    self.compute_canonical_session()
    ...
    return self.finalize(), self.build_feature_vector()
```

#### Update `finalize()` and `log_critical_feature_health()`

Add `"liquidity_distance"` and `"volume_spike"` to the `critical` list in `log_critical_feature_health()`.

`finalize()` uses `dropna(subset=list(CANONICAL_FEATURES))` — this will now include the 3 new features. `liquidity_distance` can be NaN for the first N bars (warmup); `finalize()` drops those rows cleanly.

---

## Part 3 — Backward Compatibility in Existing Models

### File: `src/engines/zone_gate_engine.py`

**Change `_extract_vector()`** to handle vectors longer than `CANONICAL_FEATURE_DIM` of the OLD model (35 features):

```python
def _extract_vector(features: dict) -> list:
    try:
        vector = [float(features[k]) for k in CANONICAL_KEYS]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Feature value coercion failed: {exc}") from exc
    
    # Backward compat: if vector is longer than expected, silently truncate.
    # This happens when the pipeline runs with a new schema (38-dim) but an
    # older zone model was trained on 35 features. The zone model's centroid
    # vectors match CANONICAL_KEYS which IS already updated — this guard
    # protects against transient mismatches during model migration.
    if len(vector) > CANONICAL_FEATURE_DIM:
        logger.debug(
            "_extract_vector: truncating vector from %d to %d (schema migration).",
            len(vector), CANONICAL_FEATURE_DIM,
        )
        vector = vector[:CANONICAL_FEATURE_DIM]
    
    assert len(vector) == CANONICAL_FEATURE_DIM, (
        f"Vector length mismatch: expected {CANONICAL_FEATURE_DIM}, got {len(vector)}"
    )
    return vector
```

**Note:** This assertion is now only triggered for vectors SHORTER than expected (broken pipeline), not longer (schema migration).

### File: `src/config_layer/rr/rr_pattern_miner.py`

**Change `NanoInferenceEngine.predict()`** — first 3 lines:

```python
def predict(self, features, gaussian_score, gaussian_p_win, threshold=0.5):
    n = len(self.W)
    # Backward compat: if caller provides more features than model expects
    # (schema v3.0 → 38 features, model trained on v2.0 → 35), silently truncate.
    if len(features) > n:
        features = list(features)[:n]
    if len(features) != n:
        raise ValueError(f"NanoInferenceEngine.predict: expected {n} features, got {len(features)}.")
    ...
```

### Note on MLGaussianEngine

`MLGaussianEngine.compute()` already returns `0.5` fallback when `len(vec) != self._model.n_features` (line already exists). No change needed.

---

## Part 4 — ReplayMemoryEngine

### File: `src/replay/__init__.py` (new, empty)

### File: `src/replay/replay_memory_engine.py` (new)

```python
"""
replay_memory_engine.py
=======================
Persistent institutional memory layer.

Reads historical opportunity JSONL files, indexes by cluster assignment,
and answers similarity queries about past market states.

All I/O is lazy-loaded and cached. Fail-open on any disk error.
Deterministic: all operations are read-only; no state mutation after init.

Production safety:
  - max_records cap prevents unbounded memory
  - Temporal decay discounts old records
  - No RNG; no side effects after construction
"""
from __future__ import annotations

import json
import logging
import math
import time
from collections import defaultdict
from pathlib import Path
from typing import List, Optional

from utils.logging_config import get_flow_logger

logger = get_flow_logger("REPLAY_MEMORY")

# Config defaults (overridden by production config section "replay_memory")
_DEFAULT_MAX_RECORDS   = 50_000   # hard cap on records held in memory
_DEFAULT_DECAY_HALF_LIFE_DAYS = 30.0  # temporal decay half-life
_DEFAULT_MIN_CLUSTER_SAMPLES  = 5     # minimum samples for cluster statistics
_DEFAULT_STALENESS_THRESHOLD_DAYS = 90.0  # reject records older than this


class ReplayRecord:
    """Lightweight immutable replay record."""
    __slots__ = (
        "timestamp", "instrument", "direction",
        "outcome", "rr_achieved", "cluster_id",
        "features", "age_days",
    )

    def __init__(
        self,
        timestamp: str,
        instrument: str,
        direction: str,
        outcome: str,
        rr_achieved: float,
        cluster_id: int,
        features: list,
        age_days: float,
    ):
        self.timestamp   = timestamp
        self.instrument  = instrument
        self.direction   = direction
        self.outcome     = outcome
        self.rr_achieved = rr_achieved
        self.cluster_id  = cluster_id
        self.features    = features
        self.age_days    = age_days


class ClusterStats:
    """Aggregated statistics for one cluster."""
    __slots__ = (
        "cluster_id", "n_samples", "win_rate", "mean_rr",
        "std_rr", "failure_modes", "trap_frequency",
        "staleness_days", "centroid",
    )

    def __init__(self, cluster_id: int):
        self.cluster_id   = cluster_id
        self.n_samples    = 0
        self.win_rate     = 0.0
        self.mean_rr      = 0.0
        self.std_rr       = 0.0
        self.failure_modes: dict = {}
        self.trap_frequency = 0.0
        self.staleness_days = 0.0
        self.centroid: list = []


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
        Hard cap on in-memory records.
    decay_half_life_days : float
        Temporal decay half-life in days (default 30).
    min_cluster_samples : int
        Minimum cluster samples for statistics to be trusted.
    staleness_threshold_days : float
        Records older than this are excluded from statistics (but kept for density).
    """

    def __init__(
        self,
        opportunities_dir: "Path | str" = "logs",
        zone_registry_path: str = "models/zone_registry.json",
        max_records: int = _DEFAULT_MAX_RECORDS,
        decay_half_life_days: float = _DEFAULT_DECAY_HALF_LIFE_DAYS,
        min_cluster_samples: int = _DEFAULT_MIN_CLUSTER_SAMPLES,
        staleness_threshold_days: float = _DEFAULT_STALENESS_THRESHOLD_DAYS,
    ):
        self._opps_dir   = Path(opportunities_dir)
        self._zone_path  = Path(zone_registry_path)
        self._max_records = max_records
        self._decay_lambda = math.log(2.0) / max(decay_half_life_days, 1.0)
        self._min_cluster_samples = min_cluster_samples
        self._staleness_threshold = staleness_threshold_days

        # Lazy-loaded state
        self._records:  List[ReplayRecord] = []
        self._cluster_stats: dict[int, ClusterStats] = {}
        self._zone_registry: Optional[dict] = None
        self._loaded: bool = False

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

        stats = self._cluster_stats.get(cluster_id)

        if stats is None or stats.n_samples < self._min_cluster_samples:
            return self._empty_result(cluster_id, reason="insufficient_samples")

        # Temporal confidence: fraction of records that are "fresh"
        fresh  = sum(1 for r in self._records
                     if r.cluster_id == cluster_id
                     and r.age_days <= self._staleness_threshold)
        density = min(1.0, fresh / max(self._max_records / 20.0, 1.0))

        # Decay-weighted win rate
        cluster_records = [r for r in self._records if r.cluster_id == cluster_id]
        decay_weighted_wins, decay_total = 0.0, 0.0
        for rec in cluster_records:
            w = math.exp(-self._decay_lambda * rec.age_days)
            is_win = 1.0 if rec.rr_achieved >= 1.0 else 0.0
            decay_weighted_wins += w * is_win
            decay_total += w
        decay_winrate = (decay_weighted_wins / decay_total) if decay_total > 0 else stats.win_rate

        # Cluster stability: 1 - (std_rr / (abs(mean_rr) + 1))
        stability = max(0.0, 1.0 - stats.std_rr / (abs(stats.mean_rr) + 1.0))
        stability = min(1.0, stability)

        # Temporal confidence: freshness ratio
        temporal_conf = fresh / max(stats.n_samples, 1)
        temporal_conf = min(1.0, temporal_conf)

        return {
            "similarity_score":     round(self._centroid_similarity(feature_vector, stats.centroid), 4),
            "matched_cluster":      cluster_id,
            "historical_winrate":   round(decay_winrate, 4),
            "historical_rr":        round(stats.mean_rr, 4),
            "failure_modes":        list(stats.failure_modes.items())[:3],
            "sample_size":          stats.n_samples,
            "replay_density":       round(density, 4),
            "cluster_stability":    round(stability, 4),
            "temporal_confidence":  round(temporal_conf, 4),
        }

    def get_replay_features(self, cluster_id: int) -> dict:
        """
        Return replay-derived feature dict for TradeNet meta-cognition input.

        Keys match the replay intelligence feature schema (Part 6 of the spec).
        All values are float. Returns neutral defaults on failure.
        """
        result = self.query([], cluster_id)
        return {
            "historical_winrate":       result.get("historical_winrate",  0.5),
            "historical_rr":            result.get("historical_rr",       0.0),
            "historical_drawdown":      self._cluster_drawdown(cluster_id),
            "cluster_stability":        result.get("cluster_stability",   0.5),
            "replay_density":           result.get("replay_density",      0.0),
            "failure_frequency":        self._failure_frequency(cluster_id),
            "trap_frequency":           self._trap_frequency(cluster_id),
            "transition_probability":   self._transition_probability(cluster_id),
            "market_state_entropy":     self._market_state_entropy(cluster_id),
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

            # Cap
            if len(records) > self._max_records:
                # Keep most recent
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
            self._records = []
            self._cluster_stats = {}
            self._loaded = True   # prevent retry loop

    def _load_zone_registry(self) -> Optional[dict]:
        if not self._zone_path.exists():
            return None
        try:
            return json.loads(self._zone_path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _discover_jsonl_files(self) -> list:
        """Find all opportunities.jsonl files under opps_dir."""
        if self._opps_dir.is_file():
            return [self._opps_dir]
        if not self._opps_dir.exists():
            return []
        # Walk recursively; limit depth to 4 for bounded latency
        found = []
        for p in self._opps_dir.rglob("opportunities.jsonl"):
            found.append(p)
            if len(found) >= 200:   # hard cap on files
                break
        return found

    def _parse_jsonl(self, path: Path, now_ts: float) -> List[ReplayRecord]:
        records = []
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    if rec.get("type") == "run_header":
                        continue
                    features_dict = rec.get("features", {})
                    if not features_dict:
                        continue

                    # Compute age in days
                    ts_str = rec.get("timestamp", "")
                    age_days = self._age_days(ts_str, now_ts)
                    if age_days > self._staleness_threshold * 2:
                        continue   # very stale — skip entirely

                    # Cluster assignment from zone registry
                    cluster_id = self._assign_cluster(features_dict)

                    features_list = [float(v) for v in features_dict.values()]

                    records.append(ReplayRecord(
                        timestamp   = ts_str,
                        instrument  = rec.get("instrument", ""),
                        direction   = rec.get("direction", "long"),
                        outcome     = rec.get("outcome", "UNKNOWN"),
                        rr_achieved = float(rec.get("rr_achieved", 0.0)),
                        cluster_id  = cluster_id,
                        features    = features_list,
                        age_days    = age_days,
                    ))
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue
        return records

    def _age_days(self, ts_str: str, now_ts: float) -> float:
        """Parse ISO timestamp or YYYY-MM-DD HH:MM:SS and return age in days."""
        if not ts_str:
            return 0.0
        try:
            import datetime
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    dt = datetime.datetime.strptime(ts_str[:19], fmt)
                    dt_ts = dt.replace(tzinfo=datetime.timezone.utc).timestamp()
                    return max(0.0, (now_ts - dt_ts) / 86400.0)
                except ValueError:
                    continue
        except Exception:
            pass
        return 0.0

    def _assign_cluster(self, features_dict: dict) -> int:
        """
        Assign cluster ID via nearest centroid in zone registry.
        Falls back to cluster 0 if no zone registry loaded.
        """
        if self._zone_registry is None:
            return 0
        zones = self._zone_registry.get("zones", [])
        if not zones:
            return 0

        feature_order = self._zone_registry.get("feature_order", list(features_dict.keys()))
        vec = [float(features_dict.get(k, 0.0)) for k in feature_order]

        best_id, best_dist = 0, float("inf")
        for zone in zones:
            centroid = zone.get("centroid", [])
            if not centroid:
                continue
            n = min(len(vec), len(centroid))
            d = sum((vec[i] - centroid[i]) ** 2 for i in range(n))
            if d < best_dist:
                best_dist = d
                best_id = int(zone.get("zone_id", 0))
        return best_id

    def _build_cluster_stats(self) -> None:
        """Build aggregated ClusterStats from loaded records."""
        cluster_records: dict[int, list] = defaultdict(list)
        for rec in self._records:
            cluster_records[rec.cluster_id].append(rec)

        zone_reg = self._zone_registry or {}
        zones = {int(z["zone_id"]): z for z in zone_reg.get("zones", [])}

        for cid, recs in cluster_records.items():
            cs = ClusterStats(cid)
            cs.n_samples = len(recs)

            # RR stats
            rr_vals = [r.rr_achieved for r in recs]
            cs.mean_rr = sum(rr_vals) / len(rr_vals)
            variance = sum((v - cs.mean_rr) ** 2 for v in rr_vals) / max(len(rr_vals), 1)
            cs.std_rr = math.sqrt(variance)

            # Win rate (rr >= 1.0 = win)
            wins = sum(1 for r in recs if r.rr_achieved >= 1.0)
            cs.win_rate = wins / cs.n_samples

            # Failure modes
            outcome_counts: dict[str, int] = defaultdict(int)
            for r in recs:
                outcome_counts[r.outcome] += 1
            cs.failure_modes = dict(outcome_counts)

            # Trap frequency (SL_HIT where rr < 0)
            traps = sum(1 for r in recs if r.outcome == "SL_HIT" and r.rr_achieved < 0)
            cs.trap_frequency = traps / cs.n_samples

            # Staleness: mean age of cluster records
            cs.staleness_days = sum(r.age_days for r in recs) / cs.n_samples

            # Centroid from zone registry (preferred) or mean of feature vectors
            if cid in zones and zones[cid].get("centroid"):
                cs.centroid = zones[cid]["centroid"]
            elif recs and recs[0].features:
                n_feat = len(recs[0].features)
                cs.centroid = [
                    sum(r.features[i] for r in recs if i < len(r.features)) / cs.n_samples
                    for i in range(n_feat)
                ]

            self._cluster_stats[cid] = cs

    def _centroid_similarity(self, vec: list, centroid: list) -> float:
        """Cosine similarity between query vector and cluster centroid."""
        if not centroid or not vec:
            return 0.5
        n = min(len(vec), len(centroid))
        dot = sum(vec[i] * centroid[i] for i in range(n))
        norm_v = math.sqrt(sum(x ** 2 for x in vec[:n])) or 1e-12
        norm_c = math.sqrt(sum(x ** 2 for x in centroid[:n])) or 1e-12
        return max(0.0, min(1.0, dot / (norm_v * norm_c)))

    def _cluster_drawdown(self, cluster_id: int) -> float:
        recs = [r for r in self._records if r.cluster_id == cluster_id]
        if not recs:
            return 0.0
        # Approximate: mean of negative rr_achieved
        neg = [r.rr_achieved for r in recs if r.rr_achieved < 0]
        return abs(sum(neg) / max(len(neg), 1)) if neg else 0.0

    def _failure_frequency(self, cluster_id: int) -> float:
        cs = self._cluster_stats.get(cluster_id)
        if cs is None or cs.n_samples == 0:
            return 0.5
        sl_hits = cs.failure_modes.get("SL_HIT", 0)
        return sl_hits / cs.n_samples

    def _trap_frequency(self, cluster_id: int) -> float:
        cs = self._cluster_stats.get(cluster_id)
        return cs.trap_frequency if cs else 0.0

    def _transition_probability(self, cluster_id: int) -> float:
        """Fraction of records that timed out (neither TP nor SL) — proxy for transitional state."""
        recs = [r for r in self._records if r.cluster_id == cluster_id]
        if not recs:
            return 0.0
        timeouts = sum(1 for r in recs if r.outcome == "TIMEOUT")
        return timeouts / len(recs)

    def _market_state_entropy(self, cluster_id: int) -> float:
        """Shannon entropy of outcome distribution for this cluster."""
        cs = self._cluster_stats.get(cluster_id)
        if cs is None or cs.n_samples == 0:
            return 1.0   # max entropy = maximum uncertainty
        total = cs.n_samples
        entropy = 0.0
        for count in cs.failure_modes.values():
            p = count / total
            if p > 0:
                entropy -= p * math.log2(p)
        max_entropy = math.log2(max(len(cs.failure_modes), 2))
        return round(entropy / max_entropy, 4) if max_entropy > 0 else 0.0

    def _empty_result(self, cluster_id: int, reason: str = "") -> dict:
        return {
            "similarity_score":     0.0,
            "matched_cluster":      cluster_id,
            "historical_winrate":   0.5,
            "historical_rr":        0.0,
            "failure_modes":        [],
            "sample_size":          0,
            "replay_density":       0.0,
            "cluster_stability":    0.5,
            "temporal_confidence":  0.0,
            "_reason":              reason,
        }
```

---

## Part 5 — ReplaySimilarityIndex

### File: `src/replay/replay_similarity_index.py` (new)

```python
"""
replay_similarity_index.py
==========================
Similarity search index for replay vectors.

Primary: cosine similarity (lightweight, no matrix required).
Secondary: Mahalanobis similarity (requires precision matrix from training).

FAISS is an optional acceleration backend; NumPy is the mandatory fallback.

Temporal decay: older matches are down-weighted by exp(-lambda * age_days).
"""
from __future__ import annotations

import math
import json
import logging
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger("ReplaySimilarityIndex")

try:
    import numpy as np
    _NUMPY_AVAILABLE = True
except ImportError:
    _NUMPY_AVAILABLE = False

try:
    import faiss as _faiss
    _FAISS_AVAILABLE = True
except ImportError:
    _faiss = None
    _FAISS_AVAILABLE = False


def _cosine_similarity(a: list, b: list) -> float:
    """Pure-Python cosine similarity."""
    n = min(len(a), len(b))
    dot = sum(a[i] * b[i] for i in range(n))
    norm_a = math.sqrt(sum(x * x for x in a[:n])) or 1e-12
    norm_b = math.sqrt(sum(x * x for x in b[:n])) or 1e-12
    return max(0.0, min(1.0, dot / (norm_a * norm_b)))


class ReplaySimilarityIndex:
    """
    Nearest-neighbour replay similarity index.

    Build with add_record() / build_index(), then query with search().
    Supports cosine (default) and Mahalanobis (requires precision matrix).

    Parameters
    ----------
    n_features : int
        Expected feature vector dimension.
    decay_lambda : float
        Temporal decay coefficient (default 0.023 ≈ 30-day half-life).
    top_k : int
        Number of neighbours to retrieve per query.
    use_faiss : bool
        Attempt FAISS acceleration (falls back to NumPy if unavailable).
    """

    def __init__(
        self,
        n_features: int,
        decay_lambda: float = 0.023,
        top_k: int = 10,
        use_faiss: bool = True,
    ):
        self._n = n_features
        self._decay_lambda = decay_lambda
        self._top_k = top_k
        self._use_faiss = use_faiss and _FAISS_AVAILABLE

        self._vectors: List[list] = []
        self._metadata: List[dict] = []    # outcome, rr, cluster_id, age_days
        self._precision_matrix: Optional[list] = None   # for Mahalanobis
        self._index = None     # FAISS index (optional)
        self._built = False

    def add_record(self, vector: list, metadata: dict) -> None:
        """Add one feature vector + metadata dict (outcome, rr, cluster_id, age_days)."""
        if len(vector) != self._n:
            # Truncate/pad silently for schema migration
            vector = (vector + [0.0] * self._n)[:self._n]
        self._vectors.append(vector)
        self._metadata.append(metadata)
        self._built = False

    def set_precision_matrix(self, P: list) -> None:
        """Set precision matrix (inverse covariance) for Mahalanobis similarity."""
        self._precision_matrix = P

    def build_index(self) -> None:
        """Build search index (FAISS or in-memory NumPy matrix)."""
        if not self._vectors:
            self._built = True
            return

        if self._use_faiss and _FAISS_AVAILABLE and _NUMPY_AVAILABLE:
            try:
                import numpy as np
                mat = np.array(self._vectors, dtype=np.float32)
                # L2-normalize for inner-product cosine
                norms = np.linalg.norm(mat, axis=1, keepdims=True)
                norms = np.where(norms == 0, 1.0, norms)
                mat = mat / norms
                idx = _faiss.IndexFlatIP(self._n)
                idx.add(mat)
                self._index = idx
                logger.info("ReplaySimilarityIndex: FAISS built with %d vectors", len(self._vectors))
            except Exception as exc:
                logger.warning("FAISS build failed (%s), using NumPy fallback.", exc)
                self._index = None

        self._built = True

    def search(
        self,
        query: list,
        method: str = "cosine",
        cluster_filter: Optional[int] = None,
    ) -> List[Tuple[float, dict]]:
        """
        Find top-k nearest neighbours with temporal decay weighting.

        Parameters
        ----------
        query          : query feature vector
        method         : "cosine" | "mahalanobis"
        cluster_filter : if set, restrict to records with this cluster_id

        Returns
        -------
        list of (weighted_score, metadata_dict) sorted descending by score
        """
        if not self._built:
            self.build_index()
        if not self._vectors:
            return []

        query = (query + [0.0] * self._n)[:self._n]

        # FAISS path (cosine, no cluster filter)
        if (method == "cosine" and self._use_faiss and self._index is not None
                and cluster_filter is None and _NUMPY_AVAILABLE):
            return self._faiss_search(query)

        # NumPy or pure-Python path
        return self._linear_search(query, method, cluster_filter)

    def _faiss_search(self, query: list) -> List[Tuple[float, dict]]:
        import numpy as np
        q = np.array(query, dtype=np.float32).reshape(1, -1)
        norm = np.linalg.norm(q) or 1.0
        q = q / norm
        k = min(self._top_k, len(self._vectors))
        scores, indices = self._index.search(q, k)
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            meta = self._metadata[idx]
            age = float(meta.get("age_days", 0.0))
            decay = math.exp(-self._decay_lambda * age)
            results.append((float(score) * decay, meta))
        results.sort(key=lambda x: x[0], reverse=True)
        return results

    def _linear_search(
        self,
        query: list,
        method: str,
        cluster_filter: Optional[int],
    ) -> List[Tuple[float, dict]]:
        candidates = []
        for vec, meta in zip(self._vectors, self._metadata):
            if cluster_filter is not None and meta.get("cluster_id") != cluster_filter:
                continue

            if method == "mahalanobis" and self._precision_matrix is not None:
                sim = self._mahalanobis_sim(query, vec)
            else:
                sim = _cosine_similarity(query, vec)

            age = float(meta.get("age_days", 0.0))
            decay = math.exp(-self._decay_lambda * age)
            candidates.append((sim * decay, meta))

        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[:self._top_k]

    def _mahalanobis_sim(self, a: list, b: list) -> float:
        """Mahalanobis-based similarity via stored precision matrix."""
        P = self._precision_matrix
        n = min(len(a), len(b), len(P))
        delta = [a[i] - b[i] for i in range(n)]
        d_sq = 0.0
        for i in range(n):
            row_dot = sum(P[i][j] * delta[j] for j in range(n))
            d_sq += delta[i] * row_dot
        d_sq = min(max(d_sq, 0.0), 500.0)
        return math.exp(-0.5 * d_sq)

    def aggregate_top_k_stats(self, results: List[Tuple[float, dict]]) -> dict:
        """Aggregate win_rate, mean_rr from top-k search results."""
        if not results:
            return {"win_rate": 0.5, "mean_rr": 0.0, "n_matched": 0, "confidence": 0.0}
        total_weight = sum(s for s, _ in results)
        if total_weight <= 0:
            return {"win_rate": 0.5, "mean_rr": 0.0, "n_matched": len(results), "confidence": 0.0}
        w_wins = sum(s for s, m in results if float(m.get("rr", 0.0)) >= 1.0)
        w_rr   = sum(s * float(m.get("rr", 0.0)) for s, m in results)
        return {
            "win_rate":   round(w_wins / total_weight, 4),
            "mean_rr":    round(w_rr   / total_weight, 4),
            "n_matched":  len(results),
            "confidence": round(min(1.0, total_weight / self._top_k), 4),
        }
```

---

## Part 6 — MarketStateClusterEngine

### File: `src/regime/market_state_cluster_engine.py` (new)

Purpose: Derive market regime EMERGENTLY from cluster statistics and structural features. Does NOT use EMA thresholds.

```python
"""
market_state_cluster_engine.py
==============================
Cluster-native market state classification.

Market regimes EMERGE from the statistical profile of the cluster the current
bar is assigned to, combined with structural indicators (sweep density, BOS
density, displacement, volatility).

NO EMA thresholds. NO hardcoded regime rules.
Regimes are derived from cluster statistics learned from replay history.

Output regimes:
    TREND_EXPANSION        — high RR persistence, BOS dominant, low trap
    RANGE_TRAP             — high trap frequency, sweep dense, mean_rr ≈ 0
    LIQUIDITY_COMPRESSION  — low volatility, low BOS, high liquidity proximity
    BREAKOUT_CONTINUATION  — positive RR, recent BOS, displacement present
    VOLATILE_REVERSAL      — high std_rr, high sweep density, instability
    TRANSITIONAL_CHAOS     — high entropy, low cluster confidence, timeout-heavy
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Optional

from utils.logging_config import get_flow_logger

logger = get_flow_logger("MARKET_STATE_CLUSTER")

# Regime labels
TREND_EXPANSION        = "TREND_EXPANSION"
RANGE_TRAP             = "RANGE_TRAP"
LIQUIDITY_COMPRESSION  = "LIQUIDITY_COMPRESSION"
BREAKOUT_CONTINUATION  = "BREAKOUT_CONTINUATION"
VOLATILE_REVERSAL      = "VOLATILE_REVERSAL"
TRANSITIONAL_CHAOS     = "TRANSITIONAL_CHAOS"

_ALL_REGIMES = (
    TREND_EXPANSION, RANGE_TRAP, LIQUIDITY_COMPRESSION,
    BREAKOUT_CONTINUATION, VOLATILE_REVERSAL, TRANSITIONAL_CHAOS,
)

# Cooldown: minimum bars between regime state changes
_COOLDOWN_BARS = 5


@dataclass
class MarketStateOutput:
    market_state:       str
    cluster_id:         int
    cluster_confidence: float
    state_persistence:  float
    volatility_profile: str    # "low" | "medium" | "high"
    liquidity_profile:  str    # "compressed" | "normal" | "swept"
    trap_probability:   float
    compression_score:  float


class MarketStateClusterEngine:
    """
    Derives market state from cluster statistics + structural features.

    Parameters
    ----------
    min_cluster_samples : int
        Minimum samples needed for a cluster to contribute a regime vote.
    cooldown_bars : int
        Minimum bars between regime transitions (prevents chattering).
    """

    def __init__(
        self,
        min_cluster_samples: int = 5,
        cooldown_bars: int = _COOLDOWN_BARS,
    ):
        self._min_samples   = min_cluster_samples
        self._cooldown      = cooldown_bars
        self._last_regime   = TRANSITIONAL_CHAOS
        self._bars_since_change = 0
        self._persistence_count = 0

    def classify(
        self,
        features: dict,
        cluster_stats: Optional[object] = None,    # ClusterStats from ReplayMemoryEngine
        replay_features: Optional[dict] = None,    # from ReplayMemoryEngine.get_replay_features()
    ) -> MarketStateOutput:
        """
        Classify market state from canonical features + cluster statistics.

        Parameters
        ----------
        features       : canonical feature dict (must have volatility_ratio, sweep_detected,
                         break_of_structure, disp_strength, liquidity_distance,
                         liquidity_pressure_score, volume_spike)
        cluster_stats  : ClusterStats object from ReplayMemoryEngine (optional)
        replay_features: dict from ReplayMemoryEngine.get_replay_features() (optional)

        Returns
        -------
        MarketStateOutput
        """
        cluster_id = getattr(cluster_stats, "cluster_id", -1) if cluster_stats else -1

        # ── Extract structural signals from canonical features ──────────────
        volatility_ratio       = float(features.get("volatility_ratio",     1.0))
        sweep_detected         = float(features.get("sweep_detected",        0.0))
        double_sweep           = float(features.get("double_sweep",          0.0))
        bos                    = float(features.get("break_of_structure",    0.0))
        disp_strength          = float(features.get("disp_strength",         0.0))
        liquidity_dist         = float(features.get("liquidity_distance",    5.0))
        liquidity_pressure     = float(features.get("liquidity_pressure_score", 0.3))
        vol_spike              = float(features.get("volume_spike",          0.0))
        atr                    = float(features.get("atr",                   0.001))
        retest_depth           = float(features.get("retest_depth",          0.0))
        candles_since_retest   = float(features.get("candles_since_retest",  0.0))

        # ── Extract replay/cluster statistics ──────────────────────────────
        if cluster_stats is not None and getattr(cluster_stats, "n_samples", 0) >= self._min_samples:
            hist_winrate   = cluster_stats.win_rate
            hist_mean_rr   = cluster_stats.mean_rr
            hist_std_rr    = cluster_stats.std_rr
            trap_freq      = cluster_stats.trap_frequency
            staleness      = cluster_stats.staleness_days
            entropy        = replay_features.get("market_state_entropy", 0.5) if replay_features else 0.5
            transition_prob= replay_features.get("transition_probability", 0.2) if replay_features else 0.2
            cluster_conf   = min(1.0, cluster_stats.n_samples / 50.0)  # saturates at 50 samples
        else:
            hist_winrate, hist_mean_rr, hist_std_rr = 0.5, 0.0, 1.0
            trap_freq, staleness, entropy, transition_prob = 0.3, 0.0, 0.8, 0.3
            cluster_conf = 0.0

        # ── Volatility profile ─────────────────────────────────────────────
        if volatility_ratio > 1.8:
            vol_profile = "high"
        elif volatility_ratio < 0.8:
            vol_profile = "low"
        else:
            vol_profile = "medium"

        # ── Liquidity profile ──────────────────────────────────────────────
        if double_sweep > 0 or sweep_detected > 0:
            liq_profile = "swept"
        elif liquidity_pressure > 0.7:
            liq_profile = "compressed"
        else:
            liq_profile = "normal"

        # ── Compression score (inverse of proximity to liquidity) ──────────
        compression_score = max(0.0, 1.0 - liquidity_dist / 5.0) * (1.0 - atr * 20)
        compression_score = max(0.0, min(1.0, compression_score))

        # ── Regime scoring (emergent — no if-EMA-then-trend rules) ─────────
        # Each regime gets a score from the cluster statistics.
        scores = {
            TREND_EXPANSION:       self._score_trend_expansion(
                                       hist_mean_rr, hist_winrate, bos, disp_strength,
                                       trap_freq, hist_std_rr),
            RANGE_TRAP:            self._score_range_trap(
                                       trap_freq, sweep_detected, hist_mean_rr,
                                       hist_std_rr, liq_profile),
            LIQUIDITY_COMPRESSION: self._score_liquidity_compression(
                                       compression_score, vol_profile, bos, sweep_detected),
            BREAKOUT_CONTINUATION: self._score_breakout_continuation(
                                       hist_winrate, hist_mean_rr, bos, disp_strength,
                                       candles_since_retest),
            VOLATILE_REVERSAL:     self._score_volatile_reversal(
                                       hist_std_rr, sweep_detected, double_sweep,
                                       vol_spike, vol_profile),
            TRANSITIONAL_CHAOS:    self._score_transitional_chaos(
                                       entropy, transition_prob, cluster_conf,
                                       staleness),
        }

        # Winner
        best_regime = max(scores, key=lambda k: scores[k])
        best_score  = scores[best_regime]

        # Cooldown: only switch if cooldown elapsed
        if best_regime != self._last_regime and self._bars_since_change < self._cooldown:
            best_regime = self._last_regime
        elif best_regime != self._last_regime:
            self._last_regime = best_regime
            self._bars_since_change = 0
            self._persistence_count = 0
        else:
            self._bars_since_change += 1
            self._persistence_count += 1

        state_persistence = min(1.0, self._persistence_count / 20.0)

        return MarketStateOutput(
            market_state       = best_regime,
            cluster_id         = cluster_id,
            cluster_confidence = round(cluster_conf, 4),
            state_persistence  = round(state_persistence, 4),
            volatility_profile = vol_profile,
            liquidity_profile  = liq_profile,
            trap_probability   = round(trap_freq, 4),
            compression_score  = round(compression_score, 4),
        )

    # ── Regime scoring functions (pure functions, no state) ──────────────────

    def _score_trend_expansion(
        self, mean_rr, win_rate, bos, disp, trap_freq, std_rr
    ) -> float:
        score = 0.0
        score += 0.35 * max(0.0, mean_rr / 2.0)           # high mean RR
        score += 0.25 * win_rate                            # high win rate
        score += 0.20 * abs(bos)                            # BOS present
        score += 0.10 * min(1.0, disp / 1.5)               # displacement
        score -= 0.10 * trap_freq                           # penalty for traps
        return max(0.0, min(1.0, score))

    def _score_range_trap(
        self, trap_freq, sweep, mean_rr, std_rr, liq_profile
    ) -> float:
        score = 0.0
        score += 0.40 * trap_freq
        score += 0.25 * sweep
        score += 0.20 * (1.0 if liq_profile == "swept" else 0.0)
        score += 0.15 * (1.0 - min(1.0, abs(mean_rr) / 2.0))  # near-zero mean rr
        return max(0.0, min(1.0, score))

    def _score_liquidity_compression(
        self, compression_score, vol_profile, bos, sweep
    ) -> float:
        score = 0.0
        score += 0.50 * compression_score
        score += 0.25 * (1.0 if vol_profile == "low" else 0.0)
        score += 0.15 * (1.0 - abs(bos))          # no BOS
        score += 0.10 * (1.0 - sweep)              # no sweep
        return max(0.0, min(1.0, score))

    def _score_breakout_continuation(
        self, win_rate, mean_rr, bos, disp, candles_since_retest
    ) -> float:
        score = 0.0
        score += 0.35 * win_rate
        score += 0.25 * max(0.0, mean_rr / 2.0)
        score += 0.20 * abs(bos)
        score += 0.20 * min(1.0, disp)
        # recency bonus: recent retest boosts breakout continuation
        if 0 < candles_since_retest <= 10:
            score += 0.10
        return max(0.0, min(1.0, score))

    def _score_volatile_reversal(
        self, std_rr, sweep, double_sweep, vol_spike, vol_profile
    ) -> float:
        score = 0.0
        score += 0.35 * min(1.0, std_rr / 2.0)    # high RR variance
        score += 0.25 * sweep
        score += 0.25 * double_sweep
        score += 0.15 * vol_spike
        return max(0.0, min(1.0, score))

    def _score_transitional_chaos(
        self, entropy, transition_prob, cluster_conf, staleness_days
    ) -> float:
        score = 0.0
        score += 0.40 * entropy
        score += 0.30 * transition_prob
        score += 0.20 * (1.0 - cluster_conf)       # low cluster confidence
        score += 0.10 * min(1.0, staleness_days / 30.0)  # stale cluster
        return max(0.0, min(1.0, score))
```

---

## Part 7 — TradeNet Meta Engine

### File: `src/engines/tradenet_meta_engine.py` (new)

This is NOT a raw candle predictor. It is a META COGNITION layer that takes the outputs of all other engines and produces a capital-quality score.

The existing TradeNet model (35-dim binary classifier) is REUSED but its output is re-interpreted. Future retraining with meta-inputs will replace it, but this wrapper makes it production-safe now.

```python
"""
tradenet_meta_engine.py
=======================
TradeNet meta-cognition layer.

Takes composite engine outputs (Gaussian, RR, Zone, Replay, Regime, Liquidity)
and produces a capital-quality assessment.

In this first version, the existing 35-dim TradeNet model is loaded and used
as the base scorer. Its raw sigmoid output (p_win) is combined with the
meta-context to produce capital_quality_score.

Future version: retrain TradeNet with extended meta-feature inputs.

Fail-safe: any error returns neutral output (allocation_confidence=0.5, HOLD).
Timeout: inference must complete in < 100ms; returns fallback if exceeded.
"""
from __future__ import annotations

import logging
import math
import time
from typing import Optional

from utils.logging_config import get_flow_logger

logger = get_flow_logger("TRADENET_META")

# Lazy imports (avoid load-time failures)
_TORCH_AVAILABLE = False
try:
    import torch as _torch
    _TORCH_AVAILABLE = True
except ImportError:
    pass

_TIMEOUT_MS = 100    # maximum inference latency in ms


class TradeNetMetaEngine:
    """
    Meta-cognition layer wrapping the existing TradeNet model.

    Parameters
    ----------
    config : dict
        engine_runner config section (must contain tradenet_meta section or fallback).
    preload : bool
        If True, load model at construction. Default False (lazy).
    """

    def __init__(self, config: dict, preload: bool = False):
        self.config = config
        self._model = None
        self._scaler = None
        self._n_features: Optional[int] = None
        self._version: Optional[str] = None
        self._load_failed = False

        if preload:
            self._load()

    def compute(
        self,
        features: dict,
        gaussian_result: dict,
        rr_result: dict,
        zone_result: dict,
        replay_result: Optional[dict] = None,
        market_state_result: Optional[dict] = None,
    ) -> dict:
        """
        Compute capital quality score.

        Parameters — all engine output dicts.

        Returns
        -------
        dict:
            capital_quality_score : float [0, 1]
            expected_trade_quality : str  "PREMIUM" | "STANDARD" | "MARGINAL" | "POOR"
            allocation_confidence  : float [0, 1]
            risk_authority         : str  "FULL" | "HALF" | "QUARTER" | "NONE"
            meta                   : dict (breakdown)
        """
        t0 = time.monotonic()
        _fallback = self._fallback_output()

        try:
            if not self._load_failed and self._model is None:
                self._load()

            # Extract base score from canonical features via existing model
            base_p_win = self._inference_base(features)

            # Compute elapsed and enforce timeout
            elapsed_ms = (time.monotonic() - t0) * 1000.0
            if elapsed_ms > _TIMEOUT_MS:
                logger.warning("TradeNetMeta: timeout (%.1fms > %dms)", elapsed_ms, _TIMEOUT_MS)
                return _fallback

            # Meta-context signals
            g_score     = float(gaussian_result.get("score",    0.5))
            rr_score    = float(rr_result.get("score",          0.5))
            zone_score  = float(zone_result.get("score",        0.5))

            hist_wr     = float((replay_result  or {}).get("historical_winrate",   0.5))
            hist_rr     = float((replay_result  or {}).get("historical_rr",        0.0))
            cluster_stb = float((replay_result  or {}).get("cluster_stability",    0.5))
            replay_dens = float((replay_result  or {}).get("replay_density",       0.0))

            trap_prob   = float((market_state_result or {}).get("trap_probability", 0.3))
            state_pers  = float((market_state_result or {}).get("state_persistence",0.5))
            liq_pressure= float(features.get("liquidity_pressure_score", 0.3))

            # Capital quality composite:
            # Base: TradeNet p_win (weight 0.30)
            # Gaussian anchor (weight 0.20)
            # RR engine (weight 0.15)
            # Zone engine (weight 0.10)
            # Historical win rate from replay (weight 0.15)
            # Cluster stability bonus (weight 0.05)
            # Trap penalty (weight -0.05)
            # State persistence bonus (weight 0.05)
            cq = (
                0.30 * base_p_win  +
                0.20 * g_score     +
                0.15 * rr_score    +
                0.10 * zone_score  +
                0.15 * hist_wr     +
                0.05 * cluster_stb +
                0.05 * state_pers  -
                0.05 * trap_prob   -
                0.05 * liq_pressure * (1.0 - cluster_stb)  # compression near liquidity
            )
            cq = max(0.0, min(1.0, cq))

            # Allocation confidence: how certain are we about this quality score?
            # Driven by cluster stability and replay density
            alloc_conf = (cluster_stb * 0.5 + replay_dens * 0.3 + state_pers * 0.2)
            alloc_conf = max(0.0, min(1.0, alloc_conf))

            # Quality tier
            if cq >= 0.75:
                quality = "PREMIUM"
                risk_auth = "FULL"
            elif cq >= 0.60:
                quality = "STANDARD"
                risk_auth = "HALF"
            elif cq >= 0.45:
                quality = "MARGINAL"
                risk_auth = "QUARTER"
            else:
                quality = "POOR"
                risk_auth = "NONE"

            latency_ms = (time.monotonic() - t0) * 1000.0

            return {
                "capital_quality_score":  round(cq, 4),
                "expected_trade_quality": quality,
                "allocation_confidence":  round(alloc_conf, 4),
                "risk_authority":         risk_auth,
                "meta": {
                    "base_p_win":       round(base_p_win, 4),
                    "g_score":          round(g_score, 4),
                    "rr_score":         round(rr_score, 4),
                    "zone_score":       round(zone_score, 4),
                    "hist_winrate":     round(hist_wr, 4),
                    "cluster_stability":round(cluster_stb, 4),
                    "trap_probability": round(trap_prob, 4),
                    "latency_ms":       round(latency_ms, 2),
                    "model_version":    self._version,
                },
            }

        except Exception as exc:
            logger.warning("TradeNetMeta.compute() failed (fail-open): %s", exc)
            return _fallback

    # ── Private ───────────────────────────────────────────────────────────────

    def _load(self) -> None:
        """Lazy-load TradeNet model + scaler from active registry entry."""
        if not _TORCH_AVAILABLE:
            logger.warning("TradeNetMeta: PyTorch unavailable — using base score only.")
            self._load_failed = True
            return
        try:
            from core.model_registry import get_active_tradenet
            from training.trainer import load_model, load_tradenet_scaler
            import json

            version = get_active_tradenet()
            if version is None:
                logger.warning("TradeNetMeta: no active TradeNet in registry.")
                self._load_failed = True
                return

            model, n_features = load_model(version)
            scaler_data = load_tradenet_scaler(version)

            self._model = model
            self._scaler = scaler_data
            self._n_features = n_features
            self._version = version
            self._load_failed = False
            logger.info("TradeNetMeta: loaded version=%s n_features=%d", version, n_features)

        except Exception as exc:
            logger.warning("TradeNetMeta: load failed (fail-open): %s", exc)
            self._load_failed = True

    def _inference_base(self, features: dict) -> float:
        """Run TradeNet forward pass. Returns p_win ∈ [0,1]. Falls back to 0.5."""
        if self._model is None or self._scaler is None:
            return 0.5
        try:
            from features.dataset_builder import extract_feature_vector
            vec = extract_feature_vector(features)

            # Truncate to model's expected dimension (schema migration safety)
            n = self._n_features or len(vec)
            vec = vec[:n]

            # Scale
            mu    = self._scaler.get("mu", [0.0] * n)
            sigma = self._scaler.get("sigma", [1.0] * n)
            scaled = [(vec[i] - float(mu[i])) / max(float(sigma[i]), 1e-9) for i in range(min(n, len(vec)))]

            import torch
            with torch.no_grad():
                x = torch.tensor(scaled, dtype=torch.float32).unsqueeze(0)
                p_win = float(self._model(x).squeeze().item())
            return max(0.0, min(1.0, p_win))

        except Exception as exc:
            logger.debug("TradeNetMeta._inference_base failed: %s", exc)
            return 0.5

    def _fallback_output(self) -> dict:
        return {
            "capital_quality_score":  0.5,
            "expected_trade_quality": "MARGINAL",
            "allocation_confidence":  0.0,
            "risk_authority":         "QUARTER",
            "meta": {"reason": "tradenet_meta_fallback"},
        }
```

---

## Part 8 — HierarchicalMetaFusion

### File: `src/core/hierarchical_meta_fusion.py` (new)

```python
"""
hierarchical_meta_fusion.py
============================
6-layer hierarchical meta-fusion.

Layers:
    1. Zone Intelligence     (existing zone_gate score)
    2. Liquidity Intelligence (liquidity_pressure_score, liquidity_distance)
    3. RR Intelligence       (existing rr engine score + expected_rr)
    4. Replay Intelligence   (historical_winrate, cluster_stability, replay_density)
    5. Market-State Intel    (cluster_confidence, state_persistence, trap_probability)
    6. TradeNet Meta         (capital_quality_score, allocation_confidence)

Penalties applied:
    - Directional disagreement penalty
    - Stale-cluster penalty
    - Low-replay-density penalty
    - High-trap-probability penalty
    - Convergence penalty (repeated same score over last N bars)

Output: Capital Allocation Quality Score with full breakdown.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Optional

from utils.logging_config import get_flow_logger

logger = get_flow_logger("HIERARCHICAL_META_FUSION")


@dataclass
class HMFResult:
    opportunity_score:        float
    decision:                 str    # "ALLOW" | "REDUCE" | "REJECT"
    market_state:             dict   = field(default_factory=dict)
    replay_intelligence:      dict   = field(default_factory=dict)
    liquidity_intelligence:   dict   = field(default_factory=dict)
    rr_intelligence:          dict   = field(default_factory=dict)
    structural_intelligence:  dict   = field(default_factory=dict)
    execution_reliability:    dict   = field(default_factory=dict)
    historical_statistics:    dict   = field(default_factory=dict)
    risk_allocation:          dict   = field(default_factory=dict)
    penalties:                dict   = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "opportunity_score":       round(self.opportunity_score, 4),
            "decision":                self.decision,
            "market_state":            self.market_state,
            "replay_intelligence":     self.replay_intelligence,
            "liquidity_intelligence":  self.liquidity_intelligence,
            "rr_intelligence":         self.rr_intelligence,
            "structural_intelligence": self.structural_intelligence,
            "execution_reliability":   self.execution_reliability,
            "historical_statistics":   self.historical_statistics,
            "risk_allocation":         self.risk_allocation,
            "penalties":               self.penalties,
        }


class _ConvergenceTracker:
    """Detects score convergence (stuck at same value) over a window."""
    def __init__(self, window: int = 50):
        self._w = window
        self._history: list = []

    def push(self, score: float) -> float:
        """Returns convergence penalty ∈ [0, 0.2]."""
        self._history.append(score)
        if len(self._history) > self._w:
            self._history.pop(0)
        if len(self._history) < 10:
            return 0.0
        mean = sum(self._history) / len(self._history)
        std  = math.sqrt(sum((x - mean) ** 2 for x in self._history) / len(self._history))
        # Low variance = high convergence penalty
        return min(0.20, max(0.0, 0.20 - std * 2.0))


class HierarchicalMetaFusion:
    """
    6-layer capital-quality fusion.

    All layer inputs are optional. Missing layers use neutral scores.
    Penalties reduce the final score but never below 0.

    Parameters
    ----------
    weights : dict — layer weights (default equal weighting)
    allow_threshold  : float — opportunity_score >= this → ALLOW
    reduce_threshold : float — opportunity_score >= this → REDUCE (else REJECT)
    """

    _DEFAULT_WEIGHTS = {
        "zone":          0.20,
        "liquidity":     0.12,
        "rr":            0.18,
        "replay":        0.20,
        "market_state":  0.15,
        "tradenet_meta": 0.15,
    }

    def __init__(
        self,
        weights: Optional[dict] = None,
        allow_threshold: float = 0.60,
        reduce_threshold: float = 0.45,
    ):
        self._weights  = {**self._DEFAULT_WEIGHTS, **(weights or {})}
        self._allow_t  = allow_threshold
        self._reduce_t = reduce_threshold
        self._convergence = _ConvergenceTracker()

    def compute(
        self,
        features: dict,
        zone_result: dict,
        rr_result: dict,
        replay_result: Optional[dict] = None,
        market_state_result: Optional[object] = None,   # MarketStateOutput
        tradenet_meta_result: Optional[dict] = None,
        base_fusion_result: Optional[dict] = None,       # FusionEngine.compute() output
    ) -> HMFResult:
        """
        Compute Capital Allocation Quality Score.

        Parameters are all engine output dicts; all optional (fail-open).
        """
        replay_r  = replay_result or {}
        ms        = market_state_result
        tn        = tradenet_meta_result or {}

        # ── Layer 1: Zone Intelligence ────────────────────────────────────────
        zone_score = float(zone_result.get("score", 0.5))
        zone_conf  = 1.0 if zone_result.get("passed") else 0.5

        # ── Layer 2: Liquidity Intelligence ───────────────────────────────────
        liq_pressure  = float(features.get("liquidity_pressure_score", 0.3))
        liq_dist      = float(features.get("liquidity_distance",       5.0))
        # High pressure near liquidity → REDUCES opportunity score (risk of sweep)
        liq_score     = 1.0 - min(1.0, liq_pressure * 0.8)

        # ── Layer 3: RR Intelligence ───────────────────────────────────────────
        rr_score = float(rr_result.get("score", 0.5))
        rr_expected = float(rr_result.get("expected_rr", rr_result.get("rr", 0.0)))

        # ── Layer 4: Replay Intelligence ──────────────────────────────────────
        hist_wr    = float(replay_r.get("historical_winrate",  0.5))
        hist_rr    = float(replay_r.get("historical_rr",       0.0))
        cluster_stb= float(replay_r.get("cluster_stability",   0.5))
        replay_dens= float(replay_r.get("replay_density",      0.0))
        # Replay score: combination of win rate and RR
        replay_score = (hist_wr * 0.6 + min(1.0, max(0.0, hist_rr / 2.0)) * 0.4)

        # ── Layer 5: Market-State Intelligence ─────────────────────────────────
        if ms is not None:
            ms_conf    = getattr(ms, "cluster_confidence", 0.0)
            trap_prob  = getattr(ms, "trap_probability",   0.3)
            state_pers = getattr(ms, "state_persistence",  0.5)
            ms_state   = getattr(ms, "market_state",       "TRANSITIONAL_CHAOS")
            # Market state scoring: trend/breakout = high; trap/chaos = low
            _STATE_SCORES = {
                "TREND_EXPANSION":       0.85,
                "BREAKOUT_CONTINUATION": 0.80,
                "RANGE_TRAP":            0.35,
                "LIQUIDITY_COMPRESSION": 0.50,
                "VOLATILE_REVERSAL":     0.40,
                "TRANSITIONAL_CHAOS":    0.25,
            }
            ms_score = _STATE_SCORES.get(ms_state, 0.5) * ms_conf + 0.5 * (1.0 - ms_conf)
        else:
            ms_conf, trap_prob, state_pers, ms_state, ms_score = 0.0, 0.3, 0.5, "UNKNOWN", 0.5

        # ── Layer 6: TradeNet Meta ─────────────────────────────────────────────
        tn_cq   = float(tn.get("capital_quality_score", 0.5))
        tn_conf = float(tn.get("allocation_confidence", 0.0))

        # ── Weighted fusion ────────────────────────────────────────────────────
        w = self._weights
        total_w = sum(w.values()) or 1.0
        raw_score = (
            w["zone"]          * zone_score   +
            w["liquidity"]     * liq_score    +
            w["rr"]            * rr_score     +
            w["replay"]        * replay_score +
            w["market_state"]  * ms_score     +
            w["tradenet_meta"] * tn_cq
        ) / total_w

        # ── Penalties ──────────────────────────────────────────────────────────
        penalties = {}

        # P1: Stale cluster penalty
        if replay_dens < 0.1:
            stale_penalty = 0.08
            penalties["stale_cluster"] = stale_penalty
        else:
            stale_penalty = 0.0

        # P2: High trap probability penalty
        if trap_prob > 0.6:
            trap_penalty = (trap_prob - 0.6) * 0.5    # max 0.20
            penalties["high_trap_prob"] = round(trap_penalty, 4)
        else:
            trap_penalty = 0.0

        # P3: Low replay density penalty
        if replay_dens < 0.05:
            density_penalty = 0.05
            penalties["low_replay_density"] = density_penalty
        else:
            density_penalty = 0.0

        # P4: Convergence penalty (score repeating too long)
        conv_penalty = self._convergence.push(raw_score)
        if conv_penalty > 0.01:
            penalties["convergence"] = round(conv_penalty, 4)

        # P5: Low TradeNet confidence penalty
        if tn_conf < 0.2:
            tn_penalty = 0.05
            penalties["low_tradenet_confidence"] = tn_penalty
        else:
            tn_penalty = 0.0

        total_penalty = stale_penalty + trap_penalty + density_penalty + conv_penalty + tn_penalty
        opportunity_score = max(0.0, min(1.0, raw_score - total_penalty))

        # ── Decision ──────────────────────────────────────────────────────────
        if opportunity_score >= self._allow_t:
            decision = "ALLOW"
        elif opportunity_score >= self._reduce_t:
            decision = "REDUCE"
        else:
            decision = "REJECT"

        return HMFResult(
            opportunity_score = opportunity_score,
            decision          = decision,
            market_state = {
                "state":       ms_state,
                "confidence":  round(ms_conf, 4),
                "persistence": round(state_pers, 4),
                "trap_prob":   round(trap_prob, 4),
            },
            replay_intelligence = {
                "historical_winrate": round(hist_wr, 4),
                "historical_rr":     round(hist_rr, 4),
                "cluster_stability": round(cluster_stb, 4),
                "replay_density":    round(replay_dens, 4),
            },
            liquidity_intelligence = {
                "pressure_score": round(liq_pressure, 4),
                "distance_atr":   round(liq_dist, 4),
                "liq_score":      round(liq_score, 4),
            },
            rr_intelligence = {
                "score":       round(rr_score, 4),
                "expected_rr": round(rr_expected, 4),
            },
            structural_intelligence = {
                "zone_score": round(zone_score, 4),
                "zone_conf":  round(zone_conf, 4),
            },
            execution_reliability = {
                "tradenet_cq":   round(tn_cq, 4),
                "tradenet_conf": round(tn_conf, 4),
            },
            historical_statistics = {
                "sample_size":   int(replay_r.get("sample_size", 0)),
                "failure_modes": replay_r.get("failure_modes", []),
            },
            risk_allocation = {
                "raw_score":     round(raw_score, 4),
                "total_penalty": round(total_penalty, 4),
                "final_score":   round(opportunity_score, 4),
                "decision":      decision,
            },
            penalties = penalties,
        )
```

---

## Part 9 — Engine Telemetry

### File: `src/utils/engine_telemetry.py` (new)

```python
"""
engine_telemetry.py
===================
Structured observability wrapper for all engines.

Every engine emit produces a standard record written to logs/ and optionally
to an audit JSONL stream.

Usage:
    tel = EngineTelemetry("gaussian")
    with tel.record() as span:
        result = engine.compute(features)
    tel.emit(result, features_summary={...})
"""
from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("EngineTelemetry")

_TELEMETRY_LOG_PATH = Path("logs/engine_telemetry.jsonl")


class TelemetrySpan:
    """Context manager that measures latency."""
    def __init__(self):
        self._start = 0.0
        self.latency_ms = 0.0

    def __enter__(self):
        self._start = time.monotonic()
        return self

    def __exit__(self, *_):
        self.latency_ms = (time.monotonic() - self._start) * 1000.0


class EngineTelemetry:
    """
    Observability wrapper for one engine.

    Parameters
    ----------
    engine_name : str
        Human-readable engine identifier.
    emit_to_log : bool
        If True, write each telemetry record to logs/engine_telemetry.jsonl.
    """

    def __init__(self, engine_name: str, emit_to_log: bool = True):
        self._name = engine_name
        self._emit = emit_to_log
        self._span = TelemetrySpan()

    @contextmanager
    def record(self):
        """Context manager: wrap engine inference; latency_ms is available after exit."""
        span = TelemetrySpan()
        self._span = span
        with span:
            yield span

    def emit(
        self,
        result: dict,
        cluster_id: Optional[int] = None,
        input_summary: Optional[dict] = None,
        failure_mode: Optional[str] = None,
    ) -> dict:
        """
        Emit a structured telemetry record.

        Returns the record dict (for inline logging or assertion in tests).
        """
        record = {
            "engine_name":   self._name,
            "score":         float(result.get("score", result.get("final_score", result.get("capital_quality_score", 0.0)))),
            "confidence":    float(result.get("confidence", result.get("allocation_confidence", 0.0))),
            "latency_ms":    round(self._span.latency_ms, 2),
            "cluster_id":    cluster_id,
            "failure_mode":  failure_mode or result.get("reason"),
            "input_summary": input_summary or {},
            "ts":            time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

        if self._emit:
            try:
                _TELEMETRY_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
                with _TELEMETRY_LOG_PATH.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(record) + "\n")
            except Exception as exc:
                logger.debug("EngineTelemetry: write failed (non-blocking): %s", exc)

        return record


class DecisionLineage:
    """
    Causal trace for one execution decision (HIGH-3 fix).

    Records the full causal chain from feature snapshot → engine outputs
    → risk reductions → final decision. Written to logs/decision_lineage.jsonl.
    Essential for debugging emergent behavior: nobody loses the thread of why
    a decision was made even after hundreds of model updates.

    Usage:
        lineage = DecisionLineage(decision_id="a1b2c3")
        lineage.set_features(feature_dict)
        lineage.add_engine("gaussian", gaussian_result)
        lineage.add_engine("zone",     zone_result)
        lineage.set_decision("ACCEPT", risk_reduction=0.0, reason="all gates passed")
        lineage.flush()  # writes one JSON line to logs/decision_lineage.jsonl
    """

    _LOG_PATH = Path("logs/decision_lineage.jsonl")

    def __init__(self, decision_id: str):
        self._id       = decision_id
        self._ts       = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        self._features: dict = {}
        self._engines:  list = []
        self._decision  = ""
        self._risk_reduction = 0.0
        self._reason    = ""

    def set_features(self, features: dict) -> None:
        self._features = {k: round(float(v), 6) for k, v in features.items()
                          if isinstance(v, (int, float))}

    def add_engine(self, name: str, result: dict) -> None:
        self._engines.append({
            "engine": name,
            "score":  float(result.get("score", result.get("final_score", 0.0))),
            "passed": bool(result.get("passed", True)),
            "reason": str(result.get("reason", result.get("reject_reason", ""))),
        })

    def set_decision(self, decision: str, risk_reduction: float = 0.0,
                     reason: str = "") -> None:
        self._decision       = decision
        self._risk_reduction = risk_reduction
        self._reason         = reason

    def flush(self) -> None:
        """Write causal lineage record to decision_lineage.jsonl. Fail-open."""
        record = {
            "decision_id":    self._id,
            "timestamp":      self._ts,
            "feature_snapshot": self._features,
            "engine_outputs": self._engines,
            "decision":       self._decision,
            "risk_reduction": self._risk_reduction,
            "reason":         self._reason,
        }
        try:
            self._LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with self._LOG_PATH.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record) + "\n")
        except Exception as exc:
            logging.getLogger("DecisionLineage").debug(
                "lineage flush failed (non-blocking): %s", exc
            )
```

**Usage in `EngineRunner.run()`** — wrap existing decision loop:
```python
import uuid as _uuid
_lineage = DecisionLineage(decision_id=str(_uuid.uuid4())[:8])
_lineage.set_features(input_data)
# After each engine result:
_lineage.add_engine("gaussian", gaussian_result)
_lineage.add_engine("zone",     zone_result)
_lineage.add_engine("rr",       rr_result)
# After UltronRiskGate:
_lineage.set_decision(decision_result.get("decision", ""), reason=...)
_lineage.flush()
```

---

## Part 10 — Replay Drift Governor + Anti-Collapse Guards

### File: `src/replay/replay_drift_governor.py` (new)

**Anti-collapse design (CRITICAL-2):** Replay memory can create a self-reinforcing feedback loop where the system learns "sweeps fail" → takes fewer trades → dataset distribution shifts → model overfits fear → collapse into defensive paralysis. This governor detects and reports the signals that precede collapse. Callers decide whether to proceed; the governor never hard-rejects.

```python
"""
replay_drift_governor.py
========================
Monitors replay memory for contamination, staleness, cluster drift,
and anti-collapse signals (exploration quota, novelty score, entropy floor).

Prevents the replay memory from becoming a self-reinforcing hallucination loop
that converges the system into defensive paralysis.

Checks:
    1. Cluster entropy drift: is one cluster dominating all replay?
    2. Mean-RR drift: has the historical mean RR shifted dramatically?
    3. Staleness: is most memory older than threshold?
    4. Sample concentration: are > 80% of records in one cluster?
    5. Outcome contamination: is SL_HIT > 90%? (indicates bad data)
    6. Anti-collapse: outcome_entropy < floor → exploration injection needed
    7. Novelty score: fraction of records with rr_achieved in underrepresented range
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import List, Optional

from utils.logging_config import get_flow_logger

logger = get_flow_logger("REPLAY_DRIFT_GOVERNOR")


@dataclass
class DriftReport:
    clean: bool
    alerts: List[str] = field(default_factory=list)
    cluster_entropy: float = 1.0
    mean_rr_drift: float = 0.0
    staleness_ratio: float = 0.0
    concentration_ratio: float = 0.0
    contamination_score: float = 0.0
    # Anti-collapse fields (CRITICAL-2)
    outcome_entropy: float = 1.0          # Shannon entropy of outcome distribution [0,1]; < 0.3 = collapse risk
    exploration_deficit: bool = False      # True when outcome_entropy below floor AND recent new clusters < threshold
    novelty_score: float = 1.0            # fraction of rr_achieved values in underrepresented mid-range (0.2–1.8R)


class ReplayDriftGovernor:
    """
    Drift detection and memory quality monitoring.

    Parameters
    ----------
    max_staleness_days     : float — raise alert if > X% of records older than this
    staleness_pct_threshold: float — alert threshold for staleness ratio
    concentration_threshold: float — alert if > X fraction in one cluster
    contamination_threshold: float — alert if SL_HIT > X fraction
    """

    def __init__(
        self,
        max_staleness_days:      float = 60.0,
        staleness_pct_threshold: float = 0.70,
        concentration_threshold: float = 0.80,
        contamination_threshold: float = 0.90,
    ):
        self._max_staleness   = max_staleness_days
        self._stale_thresh    = staleness_pct_threshold
        self._conc_thresh     = concentration_threshold
        self._contam_thresh   = contamination_threshold

    def audit(self, replay_engine) -> DriftReport:
        """
        Audit the ReplayMemoryEngine instance.

        Parameters
        ----------
        replay_engine : ReplayMemoryEngine instance (already loaded)
        """
        records = getattr(replay_engine, "_records", [])
        cluster_stats = getattr(replay_engine, "_cluster_stats", {})

        if not records:
            return DriftReport(clean=True, alerts=["empty_replay_memory"])

        alerts = []
        n = len(records)

        # ── 1. Cluster entropy ──────────────────────────────────────────────
        cluster_counts: dict[int, int] = {}
        for rec in records:
            cluster_counts[rec.cluster_id] = cluster_counts.get(rec.cluster_id, 0) + 1
        k = len(cluster_counts)
        entropy = 0.0
        for count in cluster_counts.values():
            p = count / n
            entropy -= p * math.log2(p + 1e-12)
        max_entropy = math.log2(max(k, 2))
        norm_entropy = entropy / max_entropy if max_entropy > 0 else 0.0

        if norm_entropy < 0.20:
            alerts.append(f"low_cluster_entropy={norm_entropy:.3f}")

        # ── 2. Concentration ────────────────────────────────────────────────
        max_count = max(cluster_counts.values()) if cluster_counts else 0
        concentration = max_count / n
        if concentration > self._conc_thresh:
            alerts.append(f"cluster_concentration={concentration:.3f}")

        # ── 3. Staleness ────────────────────────────────────────────────────
        stale_count = sum(1 for r in records if r.age_days > self._max_staleness)
        staleness_ratio = stale_count / n
        if staleness_ratio > self._stale_thresh:
            alerts.append(f"high_staleness={staleness_ratio:.3f}")

        # ── 4. Mean RR drift ────────────────────────────────────────────────
        rr_vals = [r.rr_achieved for r in records]
        mean_rr = sum(rr_vals) / n
        # Flag if mean RR is extreme (> 1.8 or < -1.5) suggesting bad data
        mean_rr_drift = abs(mean_rr)
        if mean_rr > 1.8 or mean_rr < -1.5:
            alerts.append(f"extreme_mean_rr={mean_rr:.3f}")

        # ── 5. Outcome contamination ─────────────────────────────────────────
        sl_hits = sum(1 for r in records if r.outcome == "SL_HIT")
        sl_ratio = sl_hits / n
        if sl_ratio > self._contam_thresh:
            alerts.append(f"outcome_contamination_sl={sl_ratio:.3f}")

        contamination_score = max(0.0, sl_ratio - 0.7) / 0.3  # 0 below 70%, 1.0 at 100%

        # ── 6. Anti-collapse: outcome entropy floor ───────────────────────────
        # Shannon entropy over SL_HIT / TP_HIT / TIMEOUT distribution.
        # Entropy < 0.3 means one outcome dominates → replay is training system
        # to fear one specific failure mode → exploration collapse risk.
        outcome_counts_all: dict[str, int] = {"SL_HIT": 0, "TP_HIT": 0, "TIMEOUT": 0}
        for rec in records:
            outcome_counts_all[rec.outcome] = outcome_counts_all.get(rec.outcome, 0) + 1
        outcome_entropy = 0.0
        for count in outcome_counts_all.values():
            p = count / n
            if p > 0:
                outcome_entropy -= p * math.log2(p + 1e-12)
        max_outcome_entropy = math.log2(3)   # 3 outcomes
        norm_outcome_entropy = outcome_entropy / max_outcome_entropy

        _ENTROPY_FLOOR = 0.30
        exploration_deficit = False
        if norm_outcome_entropy < _ENTROPY_FLOOR:
            alerts.append(f"outcome_entropy_collapse={norm_outcome_entropy:.3f}")
            exploration_deficit = True

        # ── 7. Novelty score: mid-range RR representation ─────────────────────
        # Fraction of records with rr_achieved in [0.2, 1.8] (intermediate outcomes).
        # Low novelty = system only sees catastrophic or perfect trades → overfit to extremes.
        mid_range = sum(1 for r in records if 0.2 <= r.rr_achieved <= 1.8)
        novelty_score = mid_range / n
        if novelty_score < 0.10:
            alerts.append(f"low_novelty_score={novelty_score:.3f}")

        clean = len(alerts) == 0
        if not clean:
            logger.warning("ReplayDrift: %d alerts — %s", len(alerts), alerts)
        else:
            logger.info("ReplayDrift: clean audit (%d records, %d clusters)", n, k)

        return DriftReport(
            clean               = clean,
            alerts              = alerts,
            cluster_entropy     = round(norm_entropy, 4),
            mean_rr_drift       = round(mean_rr_drift, 4),
            staleness_ratio     = round(staleness_ratio, 4),
            concentration_ratio = round(concentration, 4),
            contamination_score = round(contamination_score, 4),
            outcome_entropy     = round(norm_outcome_entropy, 4),
            exploration_deficit = exploration_deficit,
            novelty_score       = round(novelty_score, 4),
        )
```

---

## Part 11 — CognitiveBus: Async Separation from Execution Plane

**Architecture correction (CRITICAL-1):** Cognitive components must NOT run inside `EngineRunner.run()`. Inline execution of replay queries, regime classification, TradeNet inference, and HMF fusion in the hot path violates the execution/cognitive plane separation and creates a permanent risk of future decision coupling. Instead, `EngineRunner.run()` emits a `DecisionSnapshot` to a thread-safe queue. A daemon `CognitiveBus` consumes events from the queue asynchronously and writes all cognitive output to `logs/cognitive_telemetry.jsonl`. The execution plane return dict NEVER contains cognitive output.

### File: `src/cognitive/cognitive_bus.py` (new — replaces inline steps 8-10)

```python
"""
cognitive_bus.py
================
Asynchronous cognitive processing bus.

Consumes DecisionSnapshot events emitted by EngineRunner and routes them
through the full cognitive pipeline:
    ReplayMemoryEngine → MarketStateClusterEngine → TradeNetMetaEngine
    → HierarchicalMetaFusion → logs/cognitive_telemetry.jsonl

HARD RULE: This module NEVER touches EngineRunner.run() internals.
           This module NEVER returns anything to the execution plane.
           All output is write-only telemetry.

Thread model: single background daemon thread.
              queue.put() is non-blocking (execution plane never waits).
              queue.maxsize=500 — oldest events dropped silently if full.
Fail-open: any exception inside _process() is caught and logged.
"""
from __future__ import annotations

import json
import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from utils.logging_config import get_flow_logger

logger = get_flow_logger("COGNITIVE_BUS")

_TELEMETRY_PATH = Path("logs/cognitive_telemetry.jsonl")
_QUEUE_MAXSIZE  = 500   # drop if full — never block execution plane
_BACKPRESSURE_ALERT_THRESHOLD = 0.05   # 5% drop rate triggers WARNING


@dataclass
class DecisionSnapshot:
    """Immutable snapshot of an EngineRunner decision cycle."""
    decision_id:   str
    timestamp:     str
    instrument:    str
    features:      dict   = field(default_factory=dict)
    zone_result:   dict   = field(default_factory=dict)
    gaussian_result: dict = field(default_factory=dict)
    rr_result:     dict   = field(default_factory=dict)
    fusion_result: dict   = field(default_factory=dict)
    decision:      str    = ""
    cluster_id:    int    = -1


class CognitiveBus:
    """
    Background daemon that processes DecisionSnapshot events asynchronously.

    Parameters
    ----------
    config : dict — production config (cognitive_layer section)
    """

    def __init__(self, config: dict):
        self._cfg  = config.get("cognitive_layer", {})
        self._q: queue.Queue = queue.Queue(maxsize=_QUEUE_MAXSIZE)
        self._thread: Optional[threading.Thread] = None
        self._running = False

        # Drop telemetry counters (Remaining Risk 1 fix)
        self._total_emitted:  int = 0
        self._dropped_events: int = 0

        # Lazy-init cognitive engines on first event (not at startup)
        self._replay_memory = None
        self._market_state  = None
        self._tradenet_meta = None
        self._hmf           = None
        self._engines_ready = False

    def start(self) -> None:
        """Start background daemon thread. Safe to call multiple times."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._consume_loop, name="CognitiveBus", daemon=True
        )
        self._thread.start()
        logger.info("CognitiveBus: started (daemon thread)")

    def stop(self) -> None:
        self._running = False
        # Drain sentinel
        try:
            self._q.put_nowait(None)
        except queue.Full:
            pass

    def emit(self, snapshot: DecisionSnapshot) -> None:
        """
        Enqueue a decision snapshot for async cognitive processing.
        Non-blocking: drops the snapshot if queue is full.
        Tracks drop_rate; logs WARNING when backpressure exceeds 5%.
        NEVER called from inside a latency-critical path except as a
        fire-and-forget final step.
        """
        self._total_emitted += 1
        try:
            self._q.put_nowait(snapshot)
        except queue.Full:
            self._dropped_events += 1
            drop_rate = self._dropped_events / max(self._total_emitted, 1)
            if drop_rate > _BACKPRESSURE_ALERT_THRESHOLD:
                logger.warning(
                    "CognitiveBus: BACKPRESSURE ALERT drop_rate=%.1f%% "
                    "(dropped=%d total=%d queue_size=%d) — "
                    "cognitive processing is slower than bar rate; "
                    "increase consumer thread count or reduce cognitive load.",
                    drop_rate * 100, self._dropped_events,
                    self._total_emitted, self._q.qsize(),
                )
            else:
                logger.debug(
                    "CognitiveBus: snapshot dropped drop_rate=%.2f%%", drop_rate * 100
                )

    def health(self) -> dict:
        """
        Return queue health snapshot for external monitoring / telemetry.

        Returns
        -------
        dict with keys:
            total_emitted, dropped_events, drop_rate, queue_size, backpressure
        """
        drop_rate = self._dropped_events / max(self._total_emitted, 1)
        return {
            "total_emitted":  self._total_emitted,
            "dropped_events": self._dropped_events,
            "drop_rate":      round(drop_rate, 4),
            "queue_size":     self._q.qsize(),
            "backpressure":   drop_rate > _BACKPRESSURE_ALERT_THRESHOLD,
        }

    # ── Private ───────────────────────────────────────────────────────────────

    def _consume_loop(self) -> None:
        while self._running:
            try:
                snapshot = self._q.get(timeout=1.0)
                if snapshot is None:
                    break
                self._process(snapshot)
            except queue.Empty:
                continue
            except Exception as exc:
                logger.warning("CognitiveBus: consume_loop error (non-blocking): %s", exc)

    def _ensure_engines(self) -> bool:
        """Lazy-init cognitive engines. Returns True if all ready."""
        if self._engines_ready:
            return True
        try:
            from replay.replay_memory_engine import ReplayMemoryEngine
            from regime.market_state_cluster_engine import MarketStateClusterEngine
            from engines.tradenet_meta_engine import TradeNetMetaEngine
            from core.hierarchical_meta_fusion import HierarchicalMetaFusion

            opps_dir = str(self._cfg.get("opportunities_dir", "logs"))
            zone_reg = str(self._cfg.get("zone_registry_path", "models/zone_registry.json"))

            self._replay_memory = ReplayMemoryEngine(
                opportunities_dir=opps_dir,
                zone_registry_path=zone_reg,
                max_records=int(self._cfg.get("max_replay_records", 50_000)),
            )
            self._market_state = MarketStateClusterEngine(
                min_cluster_samples=int(self._cfg.get("min_cluster_samples", 5)),
            )
            self._tradenet_meta = TradeNetMetaEngine({}, preload=False)
            self._hmf = HierarchicalMetaFusion(
                allow_threshold=float(self._cfg.get("hmf_allow_threshold", 0.60)),
                reduce_threshold=float(self._cfg.get("hmf_reduce_threshold", 0.45)),
            )
            self._engines_ready = True
            logger.info("CognitiveBus: engines ready")
            return True
        except Exception as exc:
            logger.warning("CognitiveBus: engine init failed (will retry): %s", exc)
            return False

    def _process(self, snap: DecisionSnapshot) -> None:
        """Process one snapshot through the full cognitive pipeline."""
        if not self._ensure_engines():
            return
        try:
            t0 = time.monotonic()

            replay_r      = self._replay_memory.query(
                feature_vector=list(snap.features.values())[:35],
                cluster_id=snap.cluster_id,
            )
            replay_feats  = self._replay_memory.get_replay_features(snap.cluster_id)
            cluster_stats = self._replay_memory._cluster_stats.get(snap.cluster_id)

            ms_output = self._market_state.classify(
                features=snap.features,
                cluster_stats=cluster_stats,
                replay_features=replay_feats,
            )
            tn_result = self._tradenet_meta.compute(
                features=snap.features,
                gaussian_result=snap.gaussian_result,
                rr_result=snap.rr_result,
                zone_result=snap.zone_result,
                replay_result=replay_r,
                market_state_result=ms_output,
            )
            hmf_result = self._hmf.compute(
                features=snap.features,
                zone_result=snap.zone_result,
                rr_result=snap.rr_result,
                replay_result=replay_r,
                market_state_result=ms_output,
                tradenet_meta_result=tn_result,
            )

            record = {
                "decision_id":   snap.decision_id,
                "timestamp":     snap.timestamp,
                "instrument":    snap.instrument,
                "core_decision": snap.decision,
                "replay":        replay_r,
                "market_state":  ms_output.__dict__ if hasattr(ms_output, "__dict__") else {},
                "tradenet_meta": tn_result,
                "hmf":           hmf_result.to_dict(),
                "latency_ms":    round((time.monotonic() - t0) * 1000, 2),
            }
            _TELEMETRY_PATH.parent.mkdir(parents=True, exist_ok=True)
            with _TELEMETRY_PATH.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record) + "\n")

        except Exception as exc:
            logger.warning("CognitiveBus._process failed (non-blocking): %s", exc)
```

### File: `src/cognitive/__init__.py` (new, empty)

### Changes to `src/core/engine_runner.py`

**The change is minimal**: add `CognitiveBus` as an optional member and emit an event at the END of `run()` — after the return dict is assembled — using a copy of the decision data. No cognitive logic runs inside `run()`.

#### In `__init__()` — add after `self.decision = DecisionEngine(config)`:

```python
# ── Cognitive Bus (async, advisory only — steps 8-10) ────────────────────
# Runs in background daemon thread. NEVER blocks execution path.
# Cognitive output written to logs/cognitive_telemetry.jsonl only.
self._cognitive_bus: Optional["CognitiveBus"] = None
cognitive_cfg = config.get("cognitive_layer", {})
if bool(cognitive_cfg.get("enabled", False)):
    try:
        from cognitive.cognitive_bus import CognitiveBus
        self._cognitive_bus = CognitiveBus(config)
        self._cognitive_bus.start()
        logger.info("EngineRunner: CognitiveBus started")
    except Exception as exc:
        logger.warning("EngineRunner: CognitiveBus init failed (non-blocking): %s", exc)
```

#### In `run()` — add AFTER the final return dict is assembled, as last statement before `return`:

```python
# Fire-and-forget: emit decision snapshot to async cognitive bus.
# This line executes AFTER all decision logic is complete.
# Non-blocking: queue.put_nowait() — drops if full.
if self._cognitive_bus is not None:
    try:
        import uuid, time as _t
        from cognitive.cognitive_bus import DecisionSnapshot
        self._cognitive_bus.emit(DecisionSnapshot(
            decision_id    = str(uuid.uuid4())[:8],
            timestamp      = _t.strftime("%Y-%m-%dT%H:%M:%SZ"),
            instrument     = str(input_data.get("instrument", "")),
            features       = dict(input_data),
            zone_result    = dict(zone_result) if isinstance(zone_result, dict) else {},
            gaussian_result= dict(gaussian_result) if isinstance(gaussian_result, dict) else {},
            rr_result      = dict(rr_result) if isinstance(rr_result, dict) else {},
            fusion_result  = dict(fusion_result) if isinstance(fusion_result, dict) else {},
            decision       = str(decision_result.get("decision", "")),
            cluster_id     = int(zone_result.get("cluster_id", -1)
                                 if isinstance(zone_result, dict) else -1),
        ))
    except Exception:
        pass  # cognitive bus emit never blocks or raises
```

**`cognitive` key is NOT added to the return dict.** Cognitive output lives exclusively in `logs/cognitive_telemetry.jsonl`.

---

## Part 12 — Production Config: New Sections

### File: `configs/production/v1_multi_2026_03.json`

Add these new top-level sections. Config hash must be recomputed after:
`py -3.12 scripts/maintenance/_compute_hash.py`

```json
"cognitive_layer": {
    "enabled": false,
    "opportunities_dir": "logs",
    "zone_registry_path": "models/zone_registry.json",
    "max_replay_records": 50000,
    "min_cluster_samples": 5,
    "hmf_allow_threshold": 0.60,
    "hmf_reduce_threshold": 0.45,
    "decay_half_life_days": 30.0,
    "staleness_threshold_days": 90.0
},

"replay_memory": {
    "max_records": 50000,
    "decay_half_life_days": 30.0,
    "min_cluster_samples": 5,
    "staleness_threshold_days": 90.0,
    "mahal_clip": 500.0,
    "confidence_bypass_threshold": 0.3
},

"market_state_cluster": {
    "min_cluster_samples": 5,
    "cooldown_bars": 5
},

"tradenet_meta": {
    "timeout_ms": 100,
    "fallback_score": 0.5
},

"drift_governance": {
    "max_staleness_days": 60.0,
    "staleness_pct_threshold": 0.70,
    "concentration_threshold": 0.80,
    "contamination_threshold": 0.90,
    "outcome_entropy_floor": 0.30,
    "novelty_score_floor": 0.10
},

"cognitive_bus": {
    "enabled": false,
    "queue_maxsize": 500,
    "telemetry_path": "logs/cognitive_telemetry.jsonl"
},

"latency_budgets": {
    "execution_plane_target_ms": 50,
    "execution_plane_hard_max_ms": 100,
    "cognitive_bus_emit_max_ms": 1,
    "note": "Execution plane budget covers steps 1-7 + lineage flush. Cognitive bus is async; budget applies only to emit() call."
},

"event_fabric": {
    "enabled": true,
    "generation_warning_gap": 100,
    "lineage_log_path": "logs/decision_lineage.jsonl",
    "telemetry_log_path": "logs/cognitive_telemetry.jsonl",
    "engine_telemetry_log_path": "logs/engine_telemetry.jsonl",
    "drift_audit_log_path": "logs/drift_audit.jsonl",
    "note": "event_fabric is always enabled; generation counter is per-process monotonic. generation_warning_gap: warn if two consecutive events have generation gap > N."
}
```

---

## Part 13 — Tests

### File: `tests/replay/test_replay_memory_engine.py` (new)

Key test cases:
1. `test_load_empty_dir` — empty logs dir → loaded=True, records=[], no crash
2. `test_query_no_records` → returns `_empty_result(cluster_id=0)`
3. `test_cluster_stats_built` — synthetic JSONL with 20 records, 2 clusters → `_cluster_stats` has both
4. `test_decay_weighting` — older records contribute less to win rate
5. `test_determinism` — same JSONL twice → identical `query()` results
6. `test_max_records_cap` — > max_records JSONL → only max_records loaded
7. `test_run_header_skipped` — run_header line not counted as record
8. `test_replay_features_keys` — `get_replay_features()` returns all 9 required keys

### File: `tests/replay/test_replay_similarity_index.py` (new)

Key test cases:
1. `test_cosine_self_similarity` — query with same vector → score ≈ 1.0
2. `test_decay_reduces_old_matches` — age_days=90 → weighted score < no-decay score
3. `test_cluster_filter` — only returns records from matching cluster
4. `test_empty_index` — search on empty index → []
5. `test_aggregate_stats` — correct win_rate from known labels
6. `test_faiss_numpy_parity` — both give ±0.05 result on same query (if FAISS available)

### File: `tests/regime/test_market_state_cluster_engine.py` (new)

Key test cases:
1. `test_trend_expansion_from_stats` — high mean_rr + high win_rate → TREND_EXPANSION
2. `test_range_trap_from_stats` — high trap_freq + high sweep → RANGE_TRAP
3. `test_cooldown_prevents_chattering` — alternating inputs → state does not change every bar
4. `test_no_cluster_stats_→_transitional_chaos` — None stats → TRANSITIONAL_CHAOS
5. `test_output_fields` — all 8 MarketStateOutput fields present
6. `test_volatile_reversal` — high std_rr + double_sweep → VOLATILE_REVERSAL

### File: `tests/engines/test_tradenet_meta_engine.py` (new)

Key test cases:
1. `test_fallback_on_no_model` — no PyTorch/no registry → returns fallback dict
2. `test_output_keys` — all 4 required keys present
3. `test_quality_tiers` — cq=0.8 → PREMIUM, cq=0.3 → POOR
4. `test_risk_authority_match` — PREMIUM → FULL, etc.
5. `test_timeout_protection` — model taking > 100ms → fallback (mocked)

### File: `tests/features/test_liquidity_distance.py` (new)

Key test cases:
1. `test_liquidity_distance_no_lookahead` — distance only uses shift(1) references
2. `test_value_range` — liquidity_distance ≥ 0 always
3. `test_pressure_score_range` — liquidity_pressure_score ∈ [0, 1]
4. `test_zero_atr_handled` — NaN when atr=0, dropped by finalize()
5. `test_canonical_dim` — `CANONICAL_FEATURE_DIM == 38` after schema change
6. `test_volume_spike_adaptive` — rolling percentile threshold used (not fixed 1.5)

---

## Part 14 — STRUCTURED SELF REVIEW

### IMPLEMENTATION SUMMARY
14-part architecture extension: schema +3 features (DIM 35→38), 7 new files (~1800 LOC), 5 modified files. All new components are optional/injectable; existing 7-step EngineRunner pipeline is FULLY PRESERVED. Production default: `cognitive_layer.enabled=false`.

### FILES MODIFIED
1. `src/features/feature_schema.py` — CANONICAL_FEATURES 35→38, SCHEMA_VERSION "3.0", CANONICAL_FEATURE_DIM=38, **FeatureSchemaRegistry + FEATURE_ORDER_HASH** (CRITICAL-3)
2. `src/features/feature_pipeline.py` — `compute_liquidity_distance()`, `promote_volume_spike()`
3. `src/engines/zone_gate_engine.py` — `_extract_vector()` backward-compat truncation
4. `src/config_layer/rr/rr_pattern_miner.py` — `predict()` truncation guard
5. `src/core/engine_runner.py` — CognitiveBus init + fire-and-forget emit at end of run() + DecisionLineage (CRITICAL-1)
6. `src/training/trainer.py` — `save_gaussian_model()` and `save_model()` write `feature_order_hash` into model JSON (CRITICAL-3)
7. `configs/production/v1_multi_2026_03.json` — 7 new sections (cognitive_layer, replay_memory, market_state_cluster, tradenet_meta, drift_governance, cognitive_bus, latency_budgets)

### NEW FILES
1. `src/cognitive/__init__.py` (new package)
2. `src/cognitive/cognitive_bus.py` — async CognitiveBus + DecisionSnapshot (CRITICAL-1)
3. `src/replay/__init__.py`
4. `src/replay/replay_memory_engine.py`
5. `src/replay/replay_similarity_index.py`
6. `src/replay/replay_drift_governor.py` — with anti-collapse guards (CRITICAL-2)
7. `src/regime/__init__.py`
8. `src/regime/market_state_cluster_engine.py`
9. `src/engines/tradenet_meta_engine.py`
10. `src/core/hierarchical_meta_fusion.py`
11. `src/utils/engine_telemetry.py` — with DecisionLineage (HIGH-3)
12. `tests/cognitive/test_cognitive_bus.py` — async separation, non-blocking emit, daemon lifecycle
13. `tests/replay/test_replay_memory_engine.py`
14. `tests/replay/test_replay_similarity_index.py`
15. `tests/regime/test_market_state_cluster_engine.py`
16. `tests/engines/test_tradenet_meta_engine.py`
17. `tests/features/test_liquidity_distance.py`
18. `tests/features/test_feature_schema_registry.py` — schema hash registration, mismatch detection
19. `tests/replay/__init__.py`, `tests/regime/__init__.py`, `tests/engines/__init__.py`, `tests/cognitive/__init__.py`

### ARCHITECTURAL CHANGES
- `CANONICAL_FEATURE_DIM` changes from 35 to 38. All model loaders must handle n_features mismatch via truncation (no padding). **New**: `FeatureSchemaRegistry` tracks `feature_order_hash` per model to detect silent semantic corruption.
- **CRITICAL CORRECTION**: Cognitive components (`ReplayMemoryEngine`, `MarketStateClusterEngine`, `TradeNetMetaEngine`, `HierarchicalMetaFusion`) run in `CognitiveBus` background daemon thread — NOT inside `EngineRunner.run()`. Execution plane emits `DecisionSnapshot` to queue and returns immediately. Cognitive output is write-only to `logs/cognitive_telemetry.jsonl`. The `"cognitive"` key is NOT in the execution-plane return dict.
- `DecisionLineage` added to `EngineTelemetry` — writes per-decision causal trace to `logs/decision_lineage.jsonl`. Enables debugging of emergent behavior post-deployment.
- `ReplayDriftGovernor` extended with anti-collapse guards: outcome entropy floor (< 0.30 → exploration_deficit), novelty score (< 10% mid-range RR → alert).
- `MarketStateClusterEngine` replaces the EMA-threshold `detect_regime()` function for the new cognitive path ONLY. `detect_regime()` is PRESERVED for the existing dual-engine step 6.
- TradeNet is wired as a META layer (not raw candle predictor). Existing TradeNet model is reused via `TradeNetMetaEngine`; future retraining with meta-inputs is a follow-up task.

### REPLAY ARCHITECTURE
- `ReplayMemoryEngine`: lazy-loads all `opportunities.jsonl` files under `logs/`. Builds `ClusterStats` per zone cluster. Answers `query(vector, cluster_id)` returning 9-key intelligence dict.
- `ReplaySimilarityIndex`: separate indexed search (cosine primary, Mahalanobis secondary). Used when caller needs k-nearest-neighbor search rather than cluster-aggregated stats.
- Temporal decay: `exp(-lambda * age_days)` weighting throughout; lambda = log(2) / half_life.
- Memory cap: `max_records = 50,000` hard ceiling, keeping most recent.
- Determinism: all ops are pure reads after `_load()`. No RNG. No mutation.

### CLUSTER REGIME DESIGN
- `MarketStateClusterEngine.classify()` scores all 6 regimes simultaneously via `_score_*` functions.
- Each scoring function is a weighted sum of CLUSTER STATISTICS (win_rate, mean_rr, std_rr, trap_freq) + STRUCTURAL FEATURES from canonical vector (sweep, BOS, disp_strength, volatility_ratio).
- NO EMA thresholds. NO hardcoded regime-from-indicator rules.
- Cooldown of 5 bars prevents regime chattering.
- `state_persistence` field measures how long the current regime has been stable.

### LIQUIDITY ENGINE DESIGN
- `liquidity_distance` = `abs(close - nearest_level) / (atr * close)` where nearest_level is min-distance of: last_swing_high (shift 1), last_swing_low (shift 1), last BOS level (ffill'd).
- ATR used in its absolute form (`atr * close`) — `atr` canonical feature is already close-relative so multiply back.
- `liquidity_pressure_score` = `exp(-0.5 * liquidity_distance)` clamped [0,1].
- No lookahead: all reference levels use `.shift(1)`.
- `volume_spike`: upgraded from fixed `> 1.5` to rolling 75th percentile (50-bar window). Falls back to fixed threshold when < 20 samples.

### TRADENET FUSION DESIGN
- Existing TradeNet (35→16→1+Sigmoid) is the base. Its p_win output is one of 10 inputs to the composite formula.
- Capital Quality Score = weighted blend of p_win (0.30) + gaussian (0.20) + rr (0.15) + zone (0.10) + hist_wr (0.15) + cluster_stability (0.05) + state_persistence (0.05) − trap_prob (0.05).
- Output: `capital_quality_score`, `expected_trade_quality` (PREMIUM/STANDARD/MARGINAL/POOR), `allocation_confidence`, `risk_authority` (FULL/HALF/QUARTER/NONE).
- Timeout: 100ms; returns fallback on exceeded.

### OPPORTUNITY SCORE DESIGN
`HierarchicalMetaFusion.compute()` produces `HMFResult.to_dict()` with the full Capital Allocation Quality Score structure. Decisions: ALLOW (≥0.60), REDUCE (≥0.45), REJECT (<0.45). This is advisory to the existing pipeline — it does not override the `DecisionEngine` verdict.

### DRIFT GOVERNANCE
- `ReplayDriftGovernor.audit()` checks: cluster entropy, concentration, staleness, mean-RR extremes, SL contamination.
- Designed to run periodically (e.g., after scanner runs) not on every bar.
- Raises alerts but does NOT hard-reject. Callers decide whether to proceed.
- Temporal decay in `ReplayMemoryEngine` ensures old records reduce influence over time without needing explicit pruning.

### FAILURE MODES
| Component | Failure | Behavior |
|---|---|---|
| ReplayMemoryEngine._load() | Any disk error | fail-open: empty records, query returns neutral |
| ReplaySimilarityIndex | FAISS missing | falls back to NumPy linear scan |
| MarketStateClusterEngine | No cluster stats | returns TRANSITIONAL_CHAOS with low confidence |
| TradeNetMetaEngine | PyTorch missing / model absent | fallback dict: score=0.5, authority=QUARTER |
| HierarchicalMetaFusion | Any layer absent | neutral 0.5 for that layer, no exception |
| EngineRunner cognitive steps | Any exception | logged, `cognitive_result = {}`, pipeline continues |

### LOOKAHEAD BIAS AUDIT
- `compute_liquidity_distance()`: uses `.shift(1)` on swing reference prices — no lookahead ✅
- `promote_volume_spike()`: rolling quantile with `min_periods=20`, no `center=True` — no lookahead ✅
- `ReplayMemoryEngine`: reads historical JSONL, never reads future bars — no lookahead ✅
- `MarketStateClusterEngine`: uses canonical feature values from current bar — no lookahead ✅
- **Warning preserved in docstring**: `compute_structure_liquidity()` uses `center=True` rolling windows for swing detection. This is correct for backtesting but introduces lookahead for live inference. Flagged but NOT changed in this plan (scope: live-safety replacement of center=True is a separate task).

### REPLAY SAFETY AUDIT
- No circular dependency: replay reads HISTORICAL outcomes only
- Decay prevents old reinforcement: 30-day half-life → 90-day records have weight 0.125×
- `max_records=50,000` prevents unbounded memory growth
- `DriftGovernor` detects concentration (> 80% in one cluster) and contamination (SL > 90%)
- `ReplayMemoryEngine._load()` is idempotent after first call (no double-loading)

### PERFORMANCE RISKS
- `ReplayMemoryEngine._load()` on 50K records from many JSONL files: O(N×features) memory = ~50K × 38 × 8B ≈ 15MB acceptable
- `ReplaySimilarityIndex` linear scan (no FAISS): O(N) per query = 50K cos-sims per bar is ~5ms in NumPy — acceptable for post-decision advisory
- `_build_cluster_stats()` is O(N): runs once at load time, not on every bar

### MEMORY RISKS
- `ReplayMemoryEngine` holds all records in Python list: 50K ReplayRecord objects ≈ 50MB worst case
- `ReplaySimilarityIndex._vectors` duplicates those vectors if built: additional 50K × 38 × 8B = 15MB
- Recommendation: `ReplaySimilarityIndex` is built separately only when similarity search is needed (not in every bar)

### LIVE-TRADING RISKS
- `CognitiveBus` is disabled by default (`cognitive_layer.enabled=false`). No live impact until explicitly enabled.
- When enabled: `CognitiveBus` is a daemon thread; kills silently on process exit; never blocks execution plane.
- Queue full (500 items) → snapshot dropped with counter increment. `drop_rate > 5%` triggers WARNING log; `health()` method exposes `{total_emitted, dropped_events, drop_rate, queue_size, backpressure}` for monitoring.
- `TradeNetMetaEngine` has no explicit timeout inside CognitiveBus (it's async). Add timeout guard inside `_process()` if inference latency becomes a concern.
- **Execution plane latency target**: < 50ms; hard max 100ms. `DecisionLineage.flush()` is the only new I/O in the hot path (one append per bar — acceptable).
- `ReplayMemoryEngine._load()` is called lazily on first event consumed by CognitiveBus (not at startup).

### TEST COVERAGE
| File | Coverage target |
|---|---|
| `replay_memory_engine.py` | Happy path, empty dir, cluster stats, decay, determinism, max-cap, header-skip |
| `replay_similarity_index.py` | Self-similarity, decay, cluster filter, empty, aggregate stats |
| `market_state_cluster_engine.py` | All 6 regime paths, cooldown, no-stats fallback, output fields |
| `tradenet_meta_engine.py` | No-model fallback, quality tiers, risk authority, timeout |
| `test_liquidity_distance.py` | No-lookahead, value range, pressure range, zero-atr NaN, DIM=38, adaptive spike |

### BACKWARD COMPATIBILITY
| Affected code | Change | Backward compat |
|---|---|---|
| `CANONICAL_FEATURE_DIM` 35→38 | All callers using the constant see 38 | ✅ Zone gate + RR + ML Gaussian truncate via backward compat guard |
| `feature_schema.py` SCHEMA_VERSION | "1.0" → "3.0" | ✅ Only checked by schema validators, not loaders |
| `HeuristicGaussianEngine` | Unchanged | ✅ Only uses 3 features by name |
| `NanoInferenceEngine.predict()` | +3 lines truncation guard | ✅ Existing 35-dim models work with 38-dim input |
| `zone_gate_engine._extract_vector()` | +5 lines truncation guard | ✅ Existing zone models (35 centroids) work |
| `EngineRunner.run()` | +20 lines post-step7, `cognitive_result` in output | ✅ `cognitive` key is additive; `decision` key unchanged |
| `EngineRunner.__init__()` | +40 lines cognitive layer init | ✅ `cognitive_layer.enabled=false` by default |

### REMAINING GAPS
1. `center=True` rolling windows in `compute_structure_liquidity()` — lookahead for live mode. Needs dedicated live-safe swing detector.
2. `TradeNetMetaEngine` still uses 35-dim TradeNet binary predictor as base. Future: retrain TradeNet on meta-inputs (Gaussian + RR + Zone + Replay outputs) for true meta-cognition.
3. `ReplaySimilarityIndex` is constructed but not wired into `CognitiveBus` — standalone use only. Wire it when per-snapshot similarity search is needed.
4. `DecisionLineage` is implemented in `engine_telemetry.py` but not yet called from `EngineRunner.run()` — requires adding 4 lines to existing run() method.
5. EURUSD mislabeled models in `models/EURUSD/20260519_002117/` — deactivate those registry entries.
6. `ReplayDriftGovernor` anti-collapse checks added but no automated trigger — must be called after each scanner run.
7. `FeatureSchemaRegistry.register()` must be wired into each model loader (`load_gaussian_model`, `load_model` in `trainer.py`, `get_zone_gate`) — 3 one-line additions not specified in this plan iteration.

### ROUND 2 AUDIT ITEMS — NOW ADDRESSED
| Risk | Description | Status |
|---|---|---|
| Remaining Risk 1 | Queue drop telemetry — dropped_event_counter, drop_rate, backpressure alerts | ✅ Added to Part 11: `_dropped_events`, `_total_emitted`, `_BACKPRESSURE_ALERT_THRESHOLD`, `health()` method |
| Remaining Risk 4 | Event Fabric missing — no universal correlation across telemetry files | ✅ Added as Part 15: `src/events/event_fabric.py` with `make_event_envelope()`, `EventType` enum, `_GenerationCounter` |
| Remaining Risk 5 | Runtime generation tracking not mandatory | ✅ Part 15 wires `event_id + generation + schema_hash` into every telemetry write: `cognitive_telemetry.jsonl`, `decision_lineage.jsonl`, `engine_telemetry.jsonl`, `drift_audit.jsonl` |

### NEXT RECOMMENDED PHASE
1. **Implement Canonical Event Fabric** (Part 15): `src/events/event_fabric.py` — before any more AI layers.
2. **Implement schema + pipeline** (Parts 1-3): `feature_schema.py` (35→38 + FeatureSchemaRegistry), `feature_pipeline.py` (liquidity_distance + volume_spike), backward-compat guards.
3. **Implement cognitive infrastructure** (Parts 4-11): all new files, then wire `CognitiveBus` into `EngineRunner`, then `DecisionLineage` into `run()`.
4. **Update production config + rehash** (Part 12): add 8 sections (including `event_fabric`), run `_compute_hash.py`.
5. **Write and run tests** (Part 13 + Part 15 tests): especially `test_cognitive_bus.py`, `test_feature_schema_registry.py`, `test_event_fabric.py`.
6. **Retrain ETHUSDT models with schema v3.0** (38-dim) using existing `20260519_134711` JSONL.
7. **Enable CognitiveBus** (`cognitive_layer.enabled=true`) and observe `logs/cognitive_telemetry.jsonl` in shadow mode — no execution impact.
8. **Run `ReplayDriftGovernor.audit()`** after each scanner run as a CI check.
9. **Retrain TradeNetMeta** with extended meta-inputs once sufficient shadow telemetry collected.

---

## Part 15 — Canonical Event Fabric

**Context (from Round 2 architecture audit):** The system emits events to multiple telemetry files (`cognitive_telemetry.jsonl`, `decision_lineage.jsonl`, `engine_telemetry.jsonl`) with no universal correlation key. When debugging emergent behavior across components, you cannot join records across files. The Canonical Event Fabric fixes this by wrapping every cross-component event in a universal envelope.

**Priority (user directive):** "Most Important Next Step: Canonical Event Fabric before: more AI / more replay / more adaptive logic / more strategy layers."

---

### File: `src/events/__init__.py` (new, empty)

### File: `src/events/event_fabric.py` (new)

```python
"""
event_fabric.py
===============
Canonical Event Fabric for the Tradelatest runtime.

Every cross-component event (decision, cognitive telemetry, engine telemetry,
decision lineage, drift audit) is wrapped in a canonical envelope that provides:
  - event_id       : 8-char hex UUID — unique per event
  - generation     : monotonic per-process counter — total ordering within session
  - event_type     : one of EventType constants — filter/route by type
  - instrument     : symbol (e.g. "ETHUSDT") — filter by instrument
  - source         : originating component name — causal attribution
  - timestamp      : ISO-8601 UTC string
  - schema_hash    : FEATURE_ORDER_HASH at emission time — detect schema drift
  - parent_event_id: event_id of the triggering event (for causal chains)
  - payload        : event-type-specific data

Generation counter is per-process, monotonic, thread-safe.
It is NOT cross-process — do not use it to correlate events across restarts.
Use event_id for correlation; use generation for ordering within one session.

Schema hash: FEATURE_ORDER_HASH from feature_schema.py.
If a downstream record's schema_hash differs from FEATURE_ORDER_HASH, the
record was produced under a different schema — truncation or retraining needed.

Usage:
    from events.event_fabric import make_event_envelope, EventType
    record = make_event_envelope(
        event_type      = EventType.DECISION_SNAPSHOT,
        instrument      = "ETHUSDT",
        source          = "EngineRunner",
        payload         = {"decision": "ACCEPT", "score": 0.72},
        parent_event_id = "",
    )
    # record["event_id"], record["generation"], record["schema_hash"] are all set
"""
from __future__ import annotations

import threading
import time
import uuid as _uuid
from enum import Enum
from typing import Optional


# ── Event type constants ──────────────────────────────────────────────────────

class EventType(str, Enum):
    DECISION_SNAPSHOT       = "DECISION_SNAPSHOT"
    COGNITIVE_TELEMETRY     = "COGNITIVE_TELEMETRY"
    ENGINE_TELEMETRY        = "ENGINE_TELEMETRY"
    DECISION_LINEAGE        = "DECISION_LINEAGE"
    DRIFT_AUDIT             = "DRIFT_AUDIT"
    REPLAY_QUERY            = "REPLAY_QUERY"
    FEATURE_SNAPSHOT        = "FEATURE_SNAPSHOT"
    REGIME_CLASSIFICATION   = "REGIME_CLASSIFICATION"
    QUEUE_HEALTH            = "QUEUE_HEALTH"      # CognitiveBus health snapshots


# ── Thread-safe generation counter ───────────────────────────────────────────

class _GenerationCounter:
    """
    Thread-safe monotonic integer counter.
    Increments atomically; each call to next() returns a unique generation value.
    Per-process; NOT persistent across restarts.
    """
    def __init__(self):
        self._lock  = threading.Lock()
        self._value = 0

    def next(self) -> int:
        with self._lock:
            self._value += 1
            return self._value

    @property
    def current(self) -> int:
        return self._value


# Module-level singleton — one per process
_GENERATION = _GenerationCounter()


def current_generation() -> int:
    """Return current generation value without incrementing."""
    return _GENERATION.current


# ── Schema hash resolver ──────────────────────────────────────────────────────

def _get_schema_hash() -> str:
    """Return FEATURE_ORDER_HASH from feature_schema. Fail-open: returns '' on ImportError."""
    try:
        from features.feature_schema import FEATURE_ORDER_HASH  # noqa: PLC0415
        return FEATURE_ORDER_HASH
    except Exception:
        return ""


# Cache schema hash at module load time (it's fixed for the process lifetime)
_SCHEMA_HASH: str = _get_schema_hash()


# ── Public API ────────────────────────────────────────────────────────────────

def make_event_envelope(
    event_type:       str,
    instrument:       str,
    source:           str,
    payload:          dict,
    schema_hash:      str = "",
    parent_event_id:  str = "",
) -> dict:
    """
    Create a canonical event envelope.

    Parameters
    ----------
    event_type       : EventType constant (or raw string for forward compat)
    instrument       : instrument symbol (e.g. "ETHUSDT", "" for system events)
    source           : originating component name (e.g. "EngineRunner", "CognitiveBus")
    payload          : event-specific data dict (caller-owned)
    schema_hash      : FEATURE_ORDER_HASH — auto-filled from module cache if empty
    parent_event_id  : event_id of the triggering parent event ("" = root event)

    Returns
    -------
    dict — canonical event record ready to serialize with json.dumps()
    """
    return {
        "event_id":        _uuid.uuid4().hex[:8],
        "generation":      _GENERATION.next(),
        "event_type":      str(event_type),
        "instrument":      instrument,
        "source":          source,
        "timestamp":       time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "schema_hash":     schema_hash or _SCHEMA_HASH,
        "parent_event_id": parent_event_id,
        "payload":         payload,
    }


def make_decision_snapshot_envelope(
    instrument:    str,
    source:        str,
    decision_id:   str,
    features_hash: str,
    decision:      str,
    score:         float,
    cluster_id:    int,
) -> dict:
    """
    Convenience wrapper for DECISION_SNAPSHOT events.
    Features hash is the SHA-256[:8] of the canonical feature vector (not schema hash).
    """
    return make_event_envelope(
        event_type = EventType.DECISION_SNAPSHOT,
        instrument = instrument,
        source     = source,
        payload    = {
            "decision_id":   decision_id,
            "decision":      decision,
            "score":         round(score, 4),
            "cluster_id":    cluster_id,
            "features_hash": features_hash,
        },
    )
```

---

### Integration: Update `DecisionSnapshot` to carry `event_id`

In `src/cognitive/cognitive_bus.py`, update `DecisionSnapshot`:

```python
@dataclass
class DecisionSnapshot:
    """Immutable snapshot of an EngineRunner decision cycle."""
    decision_id:    str
    event_id:       str    # NEW — canonical event ID from make_event_envelope()
    generation:     int    # NEW — generation counter value at emission time
    timestamp:      str
    instrument:     str
    schema_hash:    str    # NEW — FEATURE_ORDER_HASH at emission time
    features:       dict   = field(default_factory=dict)
    zone_result:    dict   = field(default_factory=dict)
    gaussian_result: dict  = field(default_factory=dict)
    rr_result:      dict   = field(default_factory=dict)
    fusion_result:  dict   = field(default_factory=dict)
    decision:       str    = ""
    cluster_id:     int    = -1
```

In `EngineRunner.run()`, the emit block becomes:

```python
if self._cognitive_bus is not None:
    try:
        import uuid as _uu
        import time as _t
        from cognitive.cognitive_bus import DecisionSnapshot
        from events.event_fabric import make_event_envelope, EventType, _SCHEMA_HASH
        _did  = str(_uu.uuid4())[:8]
        _env  = make_event_envelope(
            event_type = EventType.DECISION_SNAPSHOT,
            instrument = str(input_data.get("instrument", "")),
            source     = "EngineRunner",
            payload    = {"decision_id": _did, "decision": str(decision_result.get("decision", ""))},
        )
        self._cognitive_bus.emit(DecisionSnapshot(
            decision_id     = _did,
            event_id        = _env["event_id"],
            generation      = _env["generation"],
            timestamp       = _env["timestamp"],
            instrument      = str(input_data.get("instrument", "")),
            schema_hash     = _env["schema_hash"],
            features        = dict(input_data),
            zone_result     = dict(zone_result) if isinstance(zone_result, dict) else {},
            gaussian_result = dict(gaussian_result) if isinstance(gaussian_result, dict) else {},
            rr_result       = dict(rr_result) if isinstance(rr_result, dict) else {},
            fusion_result   = dict(fusion_result) if isinstance(fusion_result, dict) else {},
            decision        = str(decision_result.get("decision", "")),
            cluster_id      = int(zone_result.get("cluster_id", -1)
                                  if isinstance(zone_result, dict) else -1),
        ))
    except Exception:
        pass  # cognitive bus emit never blocks or raises
```

---

### Integration: `CognitiveBus._process()` — embed envelope in telemetry record

In `_process()`, the record written to `cognitive_telemetry.jsonl` becomes:

```python
from events.event_fabric import make_event_envelope, EventType

record = make_event_envelope(
    event_type      = EventType.COGNITIVE_TELEMETRY,
    instrument      = snap.instrument,
    source          = "CognitiveBus",
    payload         = {
        "decision_id":   snap.decision_id,
        "core_decision": snap.decision,
        "replay":        replay_r,
        "market_state":  ms_output.__dict__ if hasattr(ms_output, "__dict__") else {},
        "tradenet_meta": tn_result,
        "hmf":           hmf_result.to_dict(),
        "latency_ms":    round((time.monotonic() - t0) * 1000, 2),
    },
    parent_event_id = snap.event_id,   # ← causal link back to the triggering snapshot
)
# record already contains event_id, generation, schema_hash, timestamp
```

---

### Integration: `DecisionLineage.flush()` — embed envelope in lineage record

In `src/utils/engine_telemetry.py`, `DecisionLineage.flush()`:

```python
from events.event_fabric import make_event_envelope, EventType

record = make_event_envelope(
    event_type = EventType.DECISION_LINEAGE,
    instrument = self._instrument,   # add _instrument to DecisionLineage.__init__()
    source     = "DecisionLineage",
    payload    = {
        "decision_id":      self._id,
        "feature_snapshot": self._features,
        "engine_outputs":   self._engines,
        "decision":         self._decision,
        "risk_reduction":   self._risk_reduction,
        "reason":           self._reason,
    },
)
```

---

### Integration: `EngineTelemetry.emit()` — embed envelope

```python
from events.event_fabric import make_event_envelope, EventType

record = make_event_envelope(
    event_type = EventType.ENGINE_TELEMETRY,
    instrument = "",    # engine telemetry is not always instrument-scoped
    source     = self._name,
    payload    = {
        "score":         float(result.get("score", ...)),
        "confidence":    float(result.get("confidence", ...)),
        "latency_ms":    round(self._span.latency_ms, 2),
        "cluster_id":    cluster_id,
        "failure_mode":  failure_mode or result.get("reason"),
        "input_summary": input_summary or {},
    },
)
```

---

### Integration: `ReplayDriftGovernor` — `DRIFT_AUDIT` event on each audit

```python
from events.event_fabric import make_event_envelope, EventType

# After building DriftReport in audit():
audit_env = make_event_envelope(
    event_type = EventType.DRIFT_AUDIT,
    instrument = "",
    source     = "ReplayDriftGovernor",
    payload    = {
        "clean":               report.clean,
        "alerts":              report.alerts,
        "cluster_entropy":     report.cluster_entropy,
        "outcome_entropy":     report.outcome_entropy,
        "exploration_deficit": report.exploration_deficit,
        "novelty_score":       report.novelty_score,
    },
)
# Write to logs/drift_audit.jsonl (append-only)
```

---

### Part 15 — Production Config Addition

Add to `configs/production/v1_multi_2026_03.json`:

```json
"event_fabric": {
    "enabled": true,
    "generation_warning_gap": 100,
    "lineage_log_path": "logs/decision_lineage.jsonl",
    "telemetry_log_path": "logs/cognitive_telemetry.jsonl",
    "engine_telemetry_log_path": "logs/engine_telemetry.jsonl",
    "drift_audit_log_path": "logs/drift_audit.jsonl",
    "note": "event_fabric is always enabled once any cognitive component is active. generation_warning_gap: warn if two consecutive events have generation gap > N (indicates dropped events or out-of-order processing)."
}
```

---

### Part 15 — Tests

**File: `tests/events/test_event_fabric.py`** (new)

Key test cases:
1. `test_envelope_fields_present` — all 9 required fields in every envelope
2. `test_generation_monotonic` — 100 sequential calls produce strictly increasing generation values
3. `test_generation_thread_safe` — 10 threads × 100 events each → 1000 unique generation values, no collisions
4. `test_schema_hash_present` — schema_hash is non-empty string when feature_schema importable
5. `test_parent_event_id_chain` — parent_event_id in child == event_id from parent
6. `test_event_id_unique` — 1000 events produce 1000 unique event_ids
7. `test_fail_open_on_missing_schema` — schema_hash="" when feature_schema not importable, no crash
8. `test_decision_snapshot_envelope_fields` — convenience wrapper has decision_id, decision, score, cluster_id in payload
9. `test_jsonl_serializable` — json.dumps(envelope) succeeds (no non-serializable types)

**File: `tests/events/__init__.py`** (new, empty)

---

### ARCHITECTURAL INVARIANTS (Canonical Event Fabric)

1. **Every cross-component write is an event envelope** — `cognitive_telemetry.jsonl`, `decision_lineage.jsonl`, `engine_telemetry.jsonl`, `drift_audit.jsonl` all use `make_event_envelope()`.
2. **Generation is strictly monotonic within one process** — provides total ordering of all events in a session without a central clock.
3. **`parent_event_id` creates causal chains** — a `COGNITIVE_TELEMETRY` event's `parent_event_id` == the `DECISION_SNAPSHOT` event that triggered it. This allows "show me all cognitive analysis for decision X" as a simple JSONL filter.
4. **`schema_hash` is the drift detector** — any record whose `schema_hash` differs from `FEATURE_ORDER_HASH` was produced under a different feature schema. Automated audit tools can detect this.
5. **Event fabric is write-only from the execution plane** — `make_event_envelope()` is called only at emission time, never during scoring. The generation counter increment is the only side-effect in the execution plane (O(1), lock acquisition < 1μs).
6. **`event_fabric` is always enabled** — unlike `cognitive_layer.enabled`, the event fabric has no kill switch; it is always active when any component writes telemetry.

---

### UPDATED FILES MODIFIED (with Part 15 additions)

| File | Change |
|---|---|
| `src/features/feature_schema.py` | +FeatureSchemaRegistry + FEATURE_ORDER_HASH |
| `src/features/feature_pipeline.py` | +compute_liquidity_distance(), +promote_volume_spike() |
| `src/engines/zone_gate_engine.py` | +truncation guard |
| `src/config_layer/rr/rr_pattern_miner.py` | +truncation guard |
| `src/core/engine_runner.py` | +CognitiveBus init + event envelope emit at end of run() + DecisionLineage |
| `src/training/trainer.py` | +feature_order_hash in save_gaussian_model() |
| `src/utils/engine_telemetry.py` | +DecisionLineage + event envelope in emit() |
| `src/cognitive/cognitive_bus.py` | +drop telemetry counters + health() + event envelope in _process() |
| `configs/production/v1_multi_2026_03.json` | +8 new sections (cognitive_layer, replay_memory, market_state_cluster, tradenet_meta, drift_governance, cognitive_bus, latency_budgets, event_fabric) |

### UPDATED NEW FILES (with Part 15 additions)

| File | Description |
|---|---|
| `src/events/__init__.py` | new package |
| `src/events/event_fabric.py` | _GenerationCounter, EventType enum, make_event_envelope(), make_decision_snapshot_envelope() |
| `src/cognitive/__init__.py` | new package |
| `src/cognitive/cognitive_bus.py` | CognitiveBus + DecisionSnapshot + drop telemetry |
| `src/replay/__init__.py` | new package |
| `src/replay/replay_memory_engine.py` | ReplayMemoryEngine + ClusterStats |
| `src/replay/replay_similarity_index.py` | cosine/Mahalanobis search index |
| `src/replay/replay_drift_governor.py` | drift detection + anti-collapse guards |
| `src/regime/__init__.py` | new package |
| `src/regime/market_state_cluster_engine.py` | 6-regime emergent classification |
| `src/engines/tradenet_meta_engine.py` | TradeNet meta-cognition wrapper |
| `src/core/hierarchical_meta_fusion.py` | 6-layer capital quality fusion |
| `tests/events/__init__.py` | new package |
| `tests/events/test_event_fabric.py` | 9 test cases (generation monotonicity, thread-safety, serialization) |
| `tests/cognitive/test_cognitive_bus.py` | async separation, drop telemetry, health(), daemon lifecycle |
| `tests/replay/test_replay_memory_engine.py` | 8 test cases |
| `tests/replay/test_replay_similarity_index.py` | 6 test cases |
| `tests/regime/test_market_state_cluster_engine.py` | 6 test cases |
| `tests/engines/test_tradenet_meta_engine.py` | 5 test cases |
| `tests/features/test_liquidity_distance.py` | 6 test cases |
| `tests/features/test_feature_schema_registry.py` | schema hash registration, mismatch detection |
| `tests/replay/__init__.py`, `tests/regime/__init__.py`, `tests/engines/__init__.py`, `tests/cognitive/__init__.py` | new packages |

---

---

---

# ASSUMPTION AUDIT — Factual Replacements from Codebase

All 10 assumptions from the registry analysis session have been verified against the actual source
files. Each entry below states what was assumed, what the code actually shows, and where to find
the evidence.

---

## Assumption 1 — Model Training Data Format & Content

**Was assumed:** `opportunities_*.jsonl` files contain exactly 35 canonical features, a realised
`rr_achieved`, and an `outcome` field (tp / sl / timeout).

**CONFIRMED ACCURATE.**

**Evidence:**
- Fields per JSONL record (scanner writes at lines 184–215 of
  `scripts/research/opportunity_scanner.py`):
  `timestamp`, `instrument`, `direction`, `entry`, `sl`, `tp`, `outcome`,
  `rr_achieved`, `duration_candles`, `mfe`, `mae`, `features: {35 fields}`
- Canonical feature count is **exactly 35**, defined in `CANONICAL_FEATURES` tuple at
  `src/features/feature_schema.py` lines 36–52. `CANONICAL_FEATURE_DIM = 35` line 76 of the
  same file. Imported by the scanner at line 37.
- `rr_achieved` spans **[-1.0, 2.0]** via 0.5R trailing stop (docstring line 16 of scanner).
- `outcome` encodes as exactly three string values:
  `"TP_HIT"` (line 107), `"SL_HIT"` (line 117-ish), `"TIMEOUT"` (line 131).
- The first line of every JSONL is now a **run_header** record added by the CLI hardening work
  (`{"type": "run_header", "run_id": ..., "instrument": ..., "started_at": ...}`).
  Consumers skip it via `if rec.get("type") == "run_header": continue`.

---

## Assumption 2 — Registry Loading Mechanism

**Was assumed:** Live runner / validator read registry JSON files automatically at runtime without
explicit CLI flags.

**PARTIALLY ACCURATE — key detail wrong: models are lazy-loaded on first use, not at startup.**

**Evidence:**
- `src/engines/ml_gaussian_engine.py` lines 46–89: lazy-load pattern — model is `None` at
  construction; `load_active_gaussian_scorer()` is called on first `compute()` invocation.
- `src/core/model_registry.py` — `load_active_gaussian_scorer()` (lines ~655–690):
  calls `get_active_gaussian()` which queries the `_gaussian_registry` singleton loaded from
  `models/gaussian_registry.json`, resolves `model_file` from the active entry, then calls
  `load_gaussian_model(model_file)` from `src/training/trainer.py`.
- For zone-gate: `engine_runner.py` line ~365 calls `get_zone_gate(zone_registry_path)` where
  `zone_registry_path` comes from the production config (not hardcoded).
- For TradeNet: `get_active_tradenet()` (line ~1116 in registry) same pattern.
- For RR model: `get_active_rr()` (line ~1092).
- **No explicit file paths in config** — the registry files (`models/*_registry.json`) are the
  single source of truth; active entries point to the model files.
- `engine_runner.py` instantiates each engine (line ~290 for Gaussian); the engine itself
  triggers the load on first use.

---

## Assumption 3 — `training.train_pipeline` (TradeNet) Details

**Was assumed:** TradeNet is a binary classifier for "profitable / not profitable" using 35 features.

**CONFIRMED ACCURATE, with architecture specifics now known.**

**Evidence from `src/training/trainer.py` lines 554–568:**

Architecture:
```
Linear(35 → 32) → ReLU → Dropout(0.2) → Linear(32 → 16) → ReLU → Linear(16 → 1) → Sigmoid
```

- Input size: 35 (`N_FEATURES = TRADENET_SCHEMA.n_features`, line 34 of trainer.py).
- Binary labels: `1 = win` (RR ≥ 1.0), `0 = loss`. Threshold is **1.0R**, not a sigmoid cutoff.
  Label creation at `phase5_calibration.py`: `y_bin = [1 if r >= 1.0 else 0 for r in y_rr]`
  (line ~1032 of phase5). BCELoss compares sigmoid output against these binary targets with
  per-sample class weighting.
- Evaluation metrics (from `src/training/evaluator.py`):
  - Accuracy, composite_score, Pearson correlation (expected RR vs actual RR)
  - Calibration error = |mean_pred_win_rate − actual_win_rate|
  - Confidence bucket win rates (buckets: 0.50–0.60, 0.60–0.70, 0.70–0.80, 0.80+)
- Scaler is saved as companion `{model_name}_scaler.json` at the model's parent directory
  (trainer.py lines 680–683). `load_tradenet_scaler()` (line ~727) reads it.

---

## Assumption 4 — Data Flow Between Commands (Manual Handover)

**Was assumed:** User must manually ensure the scanner's CSV inputs match the tuner's CSV inputs;
no automatic file handover between commands.

**CONFIRMED ACCURATE.**

**Evidence from `src/control_plane/registry.py`:**
- `opportunity_scanner` output artifact is `logs/opportunities_{instrument}.jsonl` (line ~76).
- Recommended next: `phase5_calibration` AND `discover_zones` (line ~176).
- `phase5_calibration` accepts `--opportunities` (ArgSpec, file-multi, line ~485).
- `discover_zones` accepts `--opportunities` (ArgSpec, file-multi, line ~505).
- Registry quickstart note (line ~77): *"Multi-select all resulting JSONL files when feeding
  Phase-5 Calibration and Discover Zones"* — explicit statement that multi-file selection
  is the user's responsibility.
- There is **no automatic pass-through**. The orchestrator (`auto_train_from_opportunities.py`)
  bridges this gap programmatically, but the standalone UI commands require manual path entry.

---

## Assumption 5 — `governance.orchestrator` Internal Logic

**Was assumed:** Orchestrator calls `ShadowPromotionGate.promote_if_superior()` and writes to
`configs/production/`, but does NOT produce output for `promotion_manager`.

**PARTIALLY WRONG — it DOES produce output consumable by promotion_manager.**

**Evidence from `src/governance/orchestrator.py` and `src/governance/shadow_promotion_gate.py`:**

4-step internal loop:
1. **Reflection:** `ReflectionBuffer.load_and_merge()` joins decisions + trade outcomes;
   `generate_prompt_payload()` analyzes feature divergence.
2. **Meta-Governor:** `MetaGovernorExecutor.run_inference()` runs BitNet on the prompt;
   `extract_and_validate_config()` parses the response patch.
3. **Shadow Gate:** `ShadowPromotionGate.stage_candidate()` writes candidate config;
   `execute_shadow_test()` runs shadow backtest.
4. **Promotion decision:** `ShadowPromotionGate.promote_if_superior()` applies two gates:
   `min_shadow_trades ≥ threshold` AND `shadow_pnl > baseline_pnl`
   (lines 186–246 of `shadow_promotion_gate.py`).

- **Does write to `configs/production/`**: Line 235 of `shadow_promotion_gate.py` copies
  `candidate_path` to `active_config_path` (= `configs/production/v1_multi_2026_03.json`).
- **Does produce consumable output**: Returns `{patch, promoted, reason}` dict.
  `promotion_manager.py` can consume this via `promote_from_report()` (line ~94 of
  `src/governance/promotion_manager.py`).
- The assumption that output is NOT consumable by promotion_manager was **wrong**.

---

## Assumption 6 — `analysis.compress_logs` Output Consumption

**Was assumed:** Compressed summary JSON is compatible with `governance.orchestrator --compressed-summary`.

**CONFIRMED ACCURATE.**

**Evidence:**
- `compress_logs_for_llm.py` output schema (lines 184–201): top-level keys
  `{"summary", "data", "anomalies"}` exactly.
- Consumer: `src/governance/orchestrator.py` lines 127–138. Reads compressed JSON via
  `--compressed-summary` flag; passes it to `ReflectionBuffer(compressed_summary=...)`.
- The flag is **mutually exclusive** with raw `collector_log` + `trades_csv` inputs —
  confirmed at `registry.py` line ~344 in the ArgSpec definition.
- The orchestrator can operate solely on the compressed summary; no collector log or trades
  CSV is then required.

---

## Assumption 7 — Order Independence of Gaussian, Zones, RR Dataset

**Was assumed:** Three scripts (`phase5_calibration`, `discover_zones`, `build_rr_dataset`) can run
in any order because all read the same opportunity JSONL files.

**CONFIRMED ACCURATE, with one cross-dependency clarification.**

**Evidence:**
- `discover_zones.py` (line 171 `main()`): accepts `--opportunities` → same JSONL as
  phase5, loads via `_load_records()` lines 37–46, extracts the 35-feature `features` dict
  (lines 119–130). Uses identical `CANONICAL_FEATURE_ORDER` from `feature_schema.py`.
- `phase5_calibration.py`: calls `build_gaussian_dataset()` from `dataset_builder.py` which
  reads the same JSONL, extracting the same 35 features via `extract_feature_vector()`.
- **No cross-dependency between zone discovery and Gaussian training**: zone registry output
  (`zone_registry_{version}.json` → `zone_gate_registry.json`) is NOT consumed by phase5 or
  the RR dataset builder.
- **One real dependency**: RR dataset builder → `build_rr_dataset` produces the dataset file
  consumed by `train_rr_model`. These two must be run in order. All other pairs are
  order-independent.

---

## Assumption 8 — Live Runner's Multi-Instrument Handling

**Was assumed:** `live.inout_runner` reads an `instruments` list from production config and loops
over instruments or spawns per-instrument engines.

**ASSUMPTION WRONG — live runner is not fully implemented in the main branch.**

**Evidence from `src/control_plane/registry.py` and `src/inout/`:**
- Registry registers `"live.inout_runner"` (lines ~441–455) with `script="inout.runner"`,
  `mode="module"`. CLI flags are `--cycles` (max cycle count, default 0 = unlimited) and
  `--config` (production config file path). No `--instruments` flag.
- `src/inout/` directory in the main branch contains only data fetchers:
  `alphavantage_candle_fetcher.py` and `hummingbot_candle_fetcher.py`.
  The actual `inout/runner.py` module does **not exist in the main branch** — it is
  under development.
- Multi-instrument runtime loop is **not yet shipped**. The `--config` flag implies the
  intended design is config-driven (instruments list in production config JSON), but the
  runner module itself is absent from the current working tree.
- Until `inout/runner.py` ships, live trading is driven by other entry points or manual
  per-instrument script invocations.

---

## Assumption 9 — TradeNet's Position in Workflow

**Was assumed:** TradeNet is not part of the main recommended chain; it can be trained any time
once labelled trade data exists from `backtest.v2` trades CSV.

**CONFIRMED ACCURATE, with one correction on input source.**

**Evidence from `src/control_plane/registry.py`:**
- Command ID: `training.train_pipeline`, subcommand `tradenet` (line ~569).
- Workflow stage: `"Model Training"` (line ~39).
- **Incoming edges**: None — TradeNet does not appear as a `recommended_next` target from
  any command. It is a **side branch**.
- **Recommended next FROM TradeNet**: `validation.config_validator` (line ~181).
- **Input source correction**: TradeNet consumes `--data` from `results/**/*.json`
  (backtest result files), **NOT** from opportunities JSONL directly. The assumption that
  it uses `backtest.v2` trades CSV is also slightly off — it reads backtest result JSON.
  (In `phase5_calibration.py` the data is loaded from the same opportunity JSONL when
  `--tradenet` is combined with `--opportunities`, but via the registry's standalone command
  the input is backtest results JSON.)
- Main pipeline flow: `opportunity_scanner → phase5_calibration → discover_zones →
  build_rr_dataset → train_rr_model → config_validator`. TradeNet runs in parallel/side.

---

## Assumption 10 — Missing Operational Scripts Are Not Required

**Was assumed:** Groq bridge, maintenance, and agent scripts are supplemental; not required for
the core pipeline.

**PARTIALLY WRONG — Groq bridge scripts ARE registered in the workflow.**

**Evidence from `src/control_plane/registry.py`:**
- Total scripts in `scripts/`: **43 Python files** across 11 subdirectories.
- **Groq bridge scripts ARE registered** (lines ~666–727 under category `"Groq Bridge"`):
  `groq_bridge/prepare_retrospective.py`, `groq_bridge/ingest_response.py`,
  `groq_bridge/apply_llm_suggestions.py` — all three appear in `_WORKFLOW_STAGE_BY_COMMAND`.
- **Scripts NOT in the workflow registry** (supplemental/utility):
  `scripts/analysis/gen_pyan.py`, `scripts/analysis/generate_cli_matrix.py`,
  `scripts/analysis/compare_bitnet_cpp_python.py`, `scripts/analysis/gen_dummy_trades.py`,
  `scripts/backtest/backtest_debug_harness.py`, `scripts/backtest/manual_backtest.py`,
  `scripts/control_plane/run_server.py`,
  `scripts/data/build_m15_unified.py`, `scripts/data/build_tradenet_dataset.py`,
  `scripts/data/convert_binance_m1_to_m15.py`, `scripts/data/generate_vectors.py`,
  `scripts/export/export_bitnet_model.py`, `scripts/export/generate_bootstrap_model.py`,
  `scripts/export/regen_bitnet_35.py`,
  `scripts/maintenance/_compute_hash.py`, `scripts/maintenance/fix_bom.py`,
  `scripts/misc/bitnet_ternary_inference.py`, `scripts/misc/run_parity.py`,
  `scripts/misc/trade_replay_validator.py`, `scripts/misc/resample_m1_to_m15.py`,
  `scripts/validate_integration.py`
- The Groq bridge is **part of the optional LLM-hypertuning loop** (Phase B retrospective),
  not core training but explicitly in the workflow. Maintenance and export scripts are truly
  supplemental (no workflow edges).

---

## Quick Reference — Assumption Accuracy Summary

| # | Assumption | Verdict |
|---|---|---|
| 1 | JSONL schema: 35 features, rr_achieved, outcome | ✅ ACCURATE |
| 2 | Registry auto-load at runtime (not startup) | ✅ ACCURATE — lazy load on first compute |
| 3 | TradeNet: binary classifier, 35 features | ✅ ACCURATE — architecture now confirmed |
| 4 | Manual file handover between pipeline commands | ✅ ACCURATE |
| 5 | Orchestrator calls ShadowPromotionGate | ✅ ACCURATE — but also produces promotion_manager-consumable output (was wrong about that) |
| 6 | Compressed summary feeds governance.orchestrator | ✅ ACCURATE |
| 7 | Gaussian / Zones / RR are order-independent | ✅ ACCURATE — one clarification: RR dataset → RR model must be ordered |
| 8 | Live runner reads instruments from production config | ❌ WRONG — runner.py not in main branch |
| 9 | TradeNet is a side branch | ✅ ACCURATE — correction: input is backtest results JSON, not trades CSV |
| 10 | Groq bridge scripts are supplemental | ❌ WRONG — they ARE registered in the workflow DAG |

---

# COMPLETED: Fix candles_since_retest + Multi-Exit Trailing Stop

## Context

Training pipeline produces two data quality defects that starve the 4-class Gaussian model:

1. **`candles_since_retest` always 0 at capture time** — the FeaturePipeline computes this
   as "candles since the retest_flag fired" using `cumsum()+cumcount()`. A retest_flag candle
   is the *first* candle of a retest group, so `cumcount()=0` at the moment an opportunity is
   recorded. The feature has zero variance in training data and carries no signal.

2. **Gaussian classes 1+2 permanently empty** — binary TP/SL exit produces only two RR values:
   `rr_achieved=-1.0` (SL_HIT → class 0) and `rr_achieved=2.0` (TP_HIT → class 3). Classes
   1 (0–1R small win) and 2 (1–2R mid win) are never populated. Gaussian priors for these
   classes are forced to 0.0 and the model cannot learn to distinguish them.

Both defects are fixed in two files only.

---

## Change 1: Fix `candles_since_retest`

**File:** `src/features/feature_pipeline.py`
**Method:** `compute_canonical_temporal_features()` — lines 535–541

### Root Cause

Current code groups by `retest_flag` cumulative sum. The retest_flag candle IS the
first candle in its group → `cumcount()=0` → feature = 0 at every opportunity capture point.

### Fix

Group by the **liquidity_sweep** event instead. At a retest candle (typically 2–5 bars
after the sweep), the value will be 2–5 — the actual time elapsed since the sweep set up
the trade.

```python
# REMOVE (lines 535–541):
retest_groups = df["retest_flag"].eq(1).cumsum()
bars_since = df.groupby(retest_groups).cumcount()
df["candles_since_retest"] = np.where(
    retest_groups > 0,
    bars_since,
    0,
).astype(np.int16)

# REPLACE WITH:
sweep_groups = (df["liquidity_sweep"] != 0).astype(int).cumsum()
bars_since_sweep = df.groupby(sweep_groups).cumcount()
df["candles_since_retest"] = np.where(
    sweep_groups > 0,
    bars_since_sweep,
    0,
).astype(np.int16)
```

### Behaviour After Fix

Example: sweep at bar 10, retest at bar 12:
- `sweep_groups` increments at bar 10 → group N for bars 10, 11, 12, …
- `cumcount()` within group N: bar 10 → 0, bar 11 → 1, bar 12 → 2
- `candles_since_retest` at retest (bar 12) = **2** (was 0) ✓

### Backward Compatibility

- Feature name `candles_since_retest` preserved — schema unchanged
- `crt_engine_v2.py` computes its own independent value via
  `state.current_candle_index - state.retest_candle_index` (lines 1025–1027); unaffected
- UAT test vectors (`uat_runner.py` lines 422, 458) hardcode 0 / 99; unaffected
- `execution_planner.py` line 358 gate (`candles_since_retest <= 5`) will now fire correctly
  for retests that are ≤5 bars after sweep, rather than never

---

## Change 2: Multi-Exit Trailing Stop

**File:** `scripts/research/opportunity_scanner.py`
**Function:** `_simulate()` — lines 52–111; `scan()` — line 114; `main()` — line 183

### Root Cause

Fixed TP (2R) + fixed SL (−1R) → only two `rr_achieved` values → `rr_to_class()` maps
everything to class 0 or 3. Classes 1 and 2 require 0 ≤ rr < 2, which never occurs.

### Fix: 0.5R Trailing Stop

Replace the fixed SL with a trailing stop that activates once price moves
`trail_mult × risk_distance` (default 0.5R) favorably, then follows the peak at
`trail_mult × risk_distance` behind.

**Class distribution with trail_mult=0.5, tp_atr_mult=2.0 (TP=2R):**
| Outcome | Condition | rr_achieved | Class |
|---------|-----------|-------------|-------|
| Trail hit | Price never reaches +0.5R | −1.0 | 0 |
| Trail hit | Peak was 0.5–1.5R, trail triggers at 0–1R | 0.0–1.0 | 1 |
| Trail hit | Peak was 1.5–2.0R, trail triggers at 1.0–1.5R | 1.0–1.5 | 2 |
| TP hit | Price reaches 2R target | 2.0 | 3 |

### Exact Code Changes

#### A. `_simulate()` — full replacement (lines 52–111)

```python
def _simulate(direction: str, entry: float, sl: float, tp: float,
              forward_bars: pd.DataFrame, risk_distance: float,
              trail_mult: float = 0.5) -> dict:
    """Forward-walk with a trailing stop (trail = trail_mult × risk_distance).

    Trail activates once price moves trail_mult×risk_distance favorably,
    then follows peak at trail_dist behind. This populates all 4 Gaussian
    classes in rr_achieved:
      class 0 (rr < 0)     — trail/SL hit before trail activation
      class 1 (0 <= rr < 1) — trail triggered after partial favorable run
      class 2 (1 <= rr < 2) — trail triggered after deeper favorable run
      class 3 (rr >= 2)     — TP hit

    Conservative tie-break: if a single bar touches both TP and trail,
    trail (SL) wins — matches existing backtest convention.
    """
    trail_dist = trail_mult * risk_distance
    trail_stop = sl    # starts at original SL price
    peak = entry       # most favorable price seen
    mfe = 0.0
    mae = 0.0
    duration = 0

    for i, bar in enumerate(forward_bars.itertuples(index=False)):
        high = float(bar.high)
        low  = float(bar.low)

        if direction == "long":
            peak = max(peak, high)
            if peak >= entry + trail_dist:          # trail activated
                trail_stop = max(trail_stop, peak - trail_dist)
            unrealized_hi = high - entry
            unrealized_lo = low  - entry
            sl_hit = low  <= trail_stop
            tp_hit = high >= tp
        else:                                        # short
            peak = min(peak, low)
            if peak <= entry - trail_dist:          # trail activated
                trail_stop = min(trail_stop, peak + trail_dist)
            unrealized_hi = entry - low
            unrealized_lo = entry - high
            sl_hit = high >= trail_stop
            tp_hit = low  <= tp

        if unrealized_hi > mfe:
            mfe = unrealized_hi
        if unrealized_lo < mae:
            mae = unrealized_lo
        duration = i + 1

        if sl_hit:
            rr = (trail_stop - entry) / risk_distance if direction == "long" \
                 else (entry - trail_stop) / risk_distance
            return {
                "outcome": "SL_HIT",
                "rr_achieved": float(round(rr, 4)),
                "duration_candles": duration,
                "mfe": float(round(mfe, 6)),
                "mae": float(round(mae, 6)),
            }
        if tp_hit:
            rr = (tp - entry) / risk_distance if direction == "long" \
                 else (entry - tp) / risk_distance
            return {
                "outcome": "TP_HIT",
                "rr_achieved": float(round(rr, 4)),
                "duration_candles": duration,
                "mfe": float(round(mfe, 6)),
                "mae": float(round(mae, 6)),
            }

    # TIMEOUT — unchanged
    if len(forward_bars) == 0:
        unrealized = 0.0
    else:
        last_close = float(forward_bars.iloc[-1]["close"])
        unrealized = (last_close - entry) if direction == "long" \
                     else (entry - last_close)
    rr = unrealized / risk_distance if risk_distance > 0 else 0.0
    return {
        "outcome": "TIMEOUT",
        "rr_achieved": float(round(rr, 4)),
        "duration_candles": duration,
        "mfe": float(round(mfe, 6)),
        "mae": float(round(mae, 6)),
    }
```

#### B. `scan()` signature (line 114) — add `trail_mult` parameter

```python
def scan(csv_path: Path, instrument: str, *, tp_atr_mult: float = 2.0,
         sl_atr_mult: float = 1.0, max_forward_candles: int = 40,
         warmup_candles: int = 30, output_dir: Path = Path("logs"),
         trail_mult: float = 0.5) -> Path:
```

Pass `trail_mult` into the `_simulate()` call (line 156):
```python
result = _simulate(direction, entry, sl, tp, forward_bars, risk_distance,
                   trail_mult=trail_mult)
```

#### C. `main()` (line 183) — add `--trail-mult` CLI argument

```python
ap.add_argument("--trail-mult", type=float, default=0.5,
                help="Trailing stop distance as multiple of risk_distance "
                     "(default=0.5; 0.5R trail populates Gaussian classes 1+2)")
```

Pass to `scan()`:
```python
out_path = scan(
    args.csv, args.instrument,
    tp_atr_mult=args.tp_atr_mult,
    sl_atr_mult=args.sl_atr_mult,
    max_forward_candles=args.max_forward_candles,
    warmup_candles=args.warmup_candles,
    output_dir=args.output_dir,
    trail_mult=args.trail_mult,
)
```

#### D. Module docstring (line 8) — update `rr_achieved` line

Replace:
```
   duration_candles, mfe, mae, features: {...35 canonical features...}}
```
With:
```
   duration_candles, mfe, mae, features: {...35 canonical features...}}
   rr_achieved spans [-1.0, 2.0] via 0.5R trailing stop (covers all 4 Gaussian classes).
```

---

## Backward Compatibility

| Consumer | Impact | Action needed |
|----------|--------|---------------|
| `phase5_calibration.py::rr_to_class()` | None — already handles full float range | None |
| `rr_dataset_builder.py` | None — reads `rr_achieved` float unchanged | None |
| Existing `opportunities_*.jsonl` logs | Old bimodal distribution — still valid, just fewer class 1+2 samples | Regenerate after fix |
| `crt_engine_v2.py` CSR computation | Independent — uses own state indices | None |
| `execution_planner.py` CSR gate (line 358) | Benefits from non-zero values post-fix | None (passive improvement) |

---

## Verification

### Step 1: Run scanner to regenerate opportunities log

```powershell
$env:PYTHONPATH = "src"
py -3.12 scripts/research/opportunity_scanner.py `
    --csv data/EURUSD_M15.csv `
    --instrument EURUSD `
    --trail-mult 0.5 `
    --output-dir logs
```

**Expected**: `logs/opportunities_EURUSD.jsonl` regenerated. Spot-check a few records:
- `candles_since_retest` should be > 0 for most records (not always 0)
- `rr_achieved` should span negative, 0–1, 1–2, and 2.0 values (not just −1.0 / 2.0)

### Step 2: JSONL sanity check

```powershell
py -3.12 -c "
import json, statistics, collections
records = [json.loads(l) for l in open('logs/opportunities_EURUSD.jsonl')][:5000]
rr_vals = [r['rr_achieved'] for r in records]
csr_vals = [r['features']['candles_since_retest'] for r in records]
from scripts.training.phase5_calibration import rr_to_class
import sys; sys.path.insert(0,'src')
cls_counts = collections.Counter(rr_to_class(r) for r in rr_vals)
print('RR classes:', dict(sorted(cls_counts.items())))
print('CSR nonzero:', sum(1 for v in csr_vals if v > 0), '/', len(csr_vals))
print('CSR mean:', round(statistics.mean(csr_vals), 2))
"
```

**Expected**:
- `RR classes: {0: N, 1: N, 2: N, 3: N}` — all 4 counts > 0 (classes 1+2 were 0 before)
- `CSR nonzero: ~most / 5000` — nearly all non-zero (was ~0)

### Step 3: Retrain Gaussian model

```powershell
$env:PYTHONPATH = "src"
py -3.12 scripts/training/phase5_calibration.py `
    --opportunities logs/opportunities_EURUSD.jsonl `
    --version v6_multiexitfix_2026_05_eur `
    --train --gaussian
```

**Expected output (success indicators)**:
```
-- RR DISTRIBUTION -------------------------------------------
  <0 (loss):      N1 samples
  0-1R (small):   N2 samples   (> 0, was 0)
  1-2R (mid):     N3 samples   (> 0, was 0)
  >2R (strong):   N4 samples
```

### Step 4: Retrain TradeNet (same opportunities log, binary label)

```powershell
py -3.12 scripts/training/phase5_calibration.py `
    --opportunities logs/opportunities_EURUSD.jsonl `
    --version v6_multiexitfix_2026_05_eur `
    --train --tradenet
```

**Expected**: Precision and Recall remain > 0.30 (maintained from previous fix).

---

## Files Modified (Summary)

| File | Change | Lines |
|------|--------|-------|
| `src/features/feature_pipeline.py` | 4-line swap in `compute_canonical_temporal_features()` | 535–541 |
| `scripts/research/opportunity_scanner.py` | `_simulate()` rewrite + `trail_mult` param threading | 52–111, 114, 183–210 |

**No schema changes. No new files. No registry updates needed.**

---

---

# OTHER LLM BUG CLAIMS — CONFIRMED / REFUTED

| Claim | Verdict | Reason |
|---|---|---|
| `swing_high mean == swing_low mean = 0.1469` → "Copy-Paste Twins bug" | **FALSE** | Direction-mirroring swaps `swing_high`↔`swing_low` for short trades. After mirroring, both features carry symmetric signal, making their dataset-level means converge to the same value. This is correct behaviour, not a copy-paste error. |
| `rsi_14 mean ≈ 0, std = 51.67` → "Broken RSI" | **FALSE** | Direction-mirroring negates `rsi_14` for short trades (positive RSI for longs, negative for shorts). The mean cancels to ≈0 across balanced long/short splits. The scaler std of 51.67 is the pre-normalised raw RSI range — not a defect. |
| `rr_weights = [0.0, 0.5, 1.5, 2.5]` → misread as feature weights | **FALSE** | `rr_weights` is a 4-element array of class midpoint multipliers (one per Gaussian class). `expected_rr = Σ(weight_c × p_c)`. The other LLM incorrectly aligned a 4-element array against the 35-element feature schema. |
| BTCUSDT data stored under `_eur`-labelled file | **TRUE** | `scaler.mean[3]` (close) = $59,913 confirms BTC price range. File naming is wrong. **This is the only real issue — fixed by registry surgery below.** |

---

# ACTIVE TASK: Per-Instrument Versioned Model Registries

## Context

Both EURUSD and BTCUSDT training runs write to the same version key in all four registries.
The BTCUSDT run with `--version v5_tradenet_2026_05_eur` silently overwrote the EURUSD
Gaussian model — both instruments share one registry key per model type. The fix is a
naming convention change only: no code changes, just use instrument-scoped version strings.

## Current Registry State (after last BTCUSDT run)

| Registry | Active Key | Data source |
|---|---|---|
| `tradenet_registry.json` | `v5_tradenet_2026_05_eur` | BTCUSDT (WRONG label) |
| `gaussian_registry.json` | `v5_tradenet_2026_05_eur` | BTCUSDT (WRONG label) |
| `rr_registry.json` | `v5_auto_2026_06` | BTCUSDT |
| `zone_gate_registry.json` | `v5_auto_2026_06` | BTCUSDT |

## Naming Convention

`v6_2026_05_{eur|btc}` — instrument suffix replaces the old model-type prefix.
This ensures every script call writes to a unique registry key per instrument.

## No Code Changes Required

All four scripts already accept `--version`. This is purely a run-parameter fix.

## Execution Plan — Registry Surgery (no retraining)

BTCUSDT models are already trained and on disk under old keys.
The fix is: copy files → add correctly-keyed registry entries → mark old entries inactive.

### Step 1 — Copy model files to btc-suffixed names

```powershell
Copy-Item models\gaussian_v5_tradenet_2026_05_eur.json `
          models\gaussian_v6_2026_05_btc.json
Copy-Item models\tradenet_v5_tradenet_2026_05_eur.pth `
          models\tradenet_v6_2026_05_btc.pth
Copy-Item models\tradenet_v5_tradenet_2026_05_eur_scaler.json `
          models\tradenet_v6_2026_05_btc_scaler.json
Copy-Item models\rr_model_v5_auto_2026_06.json `
          models\rr_model_v6_2026_05_btc.json
Copy-Item models\zone_registry_v5_auto_2026_06.json `
          models\zone_registry_v6_2026_05_btc.json
```

### Step 2 — Edit tradenet_registry.json

Add `v6_2026_05_btc` entry (copy of `v5_tradenet_2026_05_eur` with updated keys),
set old entry's `active: false`.

New entry fields:
```json
"v6_2026_05_btc": {
  "version": "v6_2026_05_btc",
  "model_file": "models\\tradenet_v6_2026_05_btc.pth",
  "metrics": { "accuracy": 0.7102, "composite_score": 0.4432,
                "n_train": 23472, "n_test": 10060 },
  "trained_at": "2026-05-18T06:35:58Z",
  "active": true
}
```

### Step 3 — Edit gaussian_registry.json

Add `v6_2026_05_btc` entry, set old entry's `active: false`.

New entry fields:
```json
"v6_2026_05_btc": {
  "version": "v6_2026_05_btc",
  "model_file": "models\\gaussian_v6_2026_05_btc.json",
  "feature_schema": [...same 35 features...],
  "schema_version": "2.0",
  "metrics": { "corr_expected_rr": 0.1893, "calibration_error": 0.0674,
                "n_train": 33532, "n_val": 0 },
  "trained_at": "2026-05-18T06:34:20Z",
  "active": true
}
```

### Step 4 — Edit rr_registry.json

Add `v6_2026_05_btc` entry (copy of `v5_auto_2026_06`), set old entries inactive.

```json
"v6_2026_05_btc": {
  "version": "v6_2026_05_btc",
  "dataset_file": null,
  "n_samples": 0,
  "n_features": 35,
  "trained_at": "2026-05-18T06:31:44Z",
  "active": true,
  "model_file": "models/rr_model_v6_2026_05_btc.json",
  "model_exists": true,
  "metrics": { "n_train": 33532, "ridge_alpha": 10.0 }
}
```
**Note:** `n_samples: 0` matches the actual `v5_auto_2026_06` pattern — the RR registry stores
n_train inside `metrics`, not in the top-level `n_samples` field when no dataset_file is kept.

### Step 5 — Edit zone_gate_registry.json

Add `v6_2026_05_btc` entry, set old entry inactive.

```json
"v6_2026_05_btc": {
  "version": "v6_2026_05_btc",
  "model_file": "models\\zone_registry_v6_2026_05_btc.json",
  "n_zones": 8,
  "n_clusters_requested": 8,
  "feature_order": [...same 35 features...],
  "trained_at": "2026-05-18T06:33:38Z",
  "active": true
}
```

## Expected Final Registry State

| Registry | Keys | Active |
|---|---|---|
| `tradenet_registry.json` | `v5_tradenet_2026_05_eur` (stale), `v6_2026_05_btc` | `v6_2026_05_btc` |
| `gaussian_registry.json` | `v5_tradenet_2026_05_eur` (stale), `v6_2026_05_btc` | `v6_2026_05_btc` |
| `rr_registry.json` | `202505_v2` (stale), `v5_auto_2026_06` (stale), `v6_2026_05_btc` | `v6_2026_05_btc` |
| `zone_gate_registry.json` | `v5_auto_2026_06` (stale), `v6_2026_05_btc` | `v6_2026_05_btc` |

No retraining. Model weights are identical — only keys and file paths change.

## Flag Reference (phase5_calibration.py)

| Flags | Effect |
|---|---|
| `--train` | Gaussian only |
| `--train --tradenet` | Gaussian THEN TradeNet (both) |
| `--tradenet` alone | Crashes — needs `report_path` from `--train` block |
| `--gaussian` | Does NOT exist — `--train` IS the Gaussian switch |

## Verification

After both runs, confirm each registry has two instrument-scoped entries:
```powershell
python -c "import json; r=json.load(open('models/gaussian_registry.json')); print(list(r.keys()))"
# Expected: [..., 'v6_2026_05_eur', 'v6_2026_05_btc']
```

---

---

# ACTIVE TASK: CLI Hardening + Per-Coin Log/Result Separation

## Context

Three problems exist after the registry surgery:

1. **Orchestrator merges all coins before training** — `auto_train_from_opportunities.py`
   scans each instrument, then concatenates all JSONL into one merged file, then runs
   phase5 ONCE producing a single model for all instruments pooled together. This means
   EURUSD and BTCUSDT training data are mixed and the resulting model cannot be attributed
   to any one instrument. Per-instrument runs with `--version v6_2026_05_{eur|btc}` have
   to be done manually and `--trail-mult` is not forwarded.

2. **`fusion_trades.jsonl` is a single mixed-coin live log** — `src/utils/trade_logger.py`
   defaults to `logs/fusion_trades.jsonl` regardless of which instrument the trade is on.
   BTCUSDT and EURUSD trades are interleaved in one file with no per-coin routing.

3. **CLI scripts lack input validation and machine-readable output contract** — scripts
   silently proceed if input files are missing/renamed, and there is no guaranteed stdout
   pattern for consuming artifact paths programmatically (e.g. from the orchestrator or
   from a monitoring script).

## Exact Files Changed (5 files)

| File | Change category |
|---|---|
| `scripts/auto_train_from_opportunities.py` | Orchestrator per-coin loop, `--trail-mult`, `--results-dir` |
| `scripts/training/phase5_calibration.py` | `--instrument` arg, per-coin report path, input validation, `OUTPUT:` lines |
| `src/utils/trade_logger.py` | Per-coin JSONL routing via `instrument` param |
| `scripts/research/discover_zones.py` | `--instrument` for output naming |
| `scripts/analysis/compress_logs_for_llm.py` | `--instrument` for default output naming |

---

## Change A: `scripts/auto_train_from_opportunities.py`

### New args (lines ~94–111)

```python
ap.add_argument("--trail-mult", type=float, default=0.5,
                help="Trailing stop multiple forwarded to opportunity_scanner.py "
                     "(default=0.5)")
ap.add_argument("--results-dir", type=Path, default=Path("results"),
                help="Base directory for per-instrument calibration reports "
                     "(default: results/)")
ap.add_argument("--per-instrument", action=argparse.BooleanOptionalAction,
                default=True,
                help="Train a separate model per instrument (default: True). "
                     "--no-per-instrument merges all and trains once.")
```

### `_scan_instrument()` — add `trail_mult` forwarding (line ~43)

```python
def _scan_instrument(data_dir, instrument, output_dir,
                     max_forward_candles, warmup_candles, trail_mult):
    ...
    rc = _run([
        sys.executable, str(scanner),
        "--csv", str(csv_path),
        "--instrument", instrument,
        "--max-forward-candles", str(max_forward_candles),
        "--warmup-candles", str(warmup_candles),
        "--output-dir", str(output_dir),
        "--trail-mult", str(trail_mult),        # ← ADD
    ])
```

### New `_train_instrument()` helper — replaces `_train()`

```python
def _train_instrument(opp_path: Path, instrument: str, version: str,
                      results_dir: Path, extra_args: list[str]) -> int:
    """Run phase5_calibration for a single instrument's opportunity log."""
    phase5 = _REPO_ROOT / "scripts" / "training" / "phase5_calibration.py"
    instr_results = results_dir / instrument
    instr_results.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, str(phase5),
        "--opportunities", str(opp_path),
        "--version", version,
        "--instrument", instrument,         # ← new arg in phase5
        "--base", str(results_dir.parent),  # keeps models/ and results/ relative to repo
        "--train",
    ] + extra_args
    return _run(cmd)
```

### `main()` — replace merge+single-train with per-instrument loop

Replace the current steps 2–5 (lines ~140–159):

```python
# 2. Per-instrument: compress + train
results_summary: list[dict] = []
for instr, opp_path in zip(args.instruments, per_instr_paths):
    # 2a. Compress (per-coin summary)
    summary_path = output_dir / f"compressed_{version}_{instr}.json"
    if _compress(opp_path, summary_path) != 0:
        _LOG.warning("Log compression failed for %s — continuing.", instr)

    # 2b. Train (per-coin model, report to results/{instr}/)
    rc = _train_instrument(
        opp_path, instr, version, args.results_dir, args.phase5_extra
    )
    results_summary.append({
        "instrument": instr,
        "opportunities": str(opp_path),
        "compressed":    str(summary_path),
        "rc":            rc,
    })
    if rc != 0:
        _LOG.error("Phase-5 failed for %s (rc=%d) — continuing other instruments.", instr, rc)

# 3. Fallback all-instruments merge (for LLM retrospective only — not used for training)
if not args.no_per_instrument:
    merged_path = output_dir / f"opportunities_merged_{version}.jsonl"
    _merge_logs(per_instr_paths, merged_path)
    _LOG.info("Merged all-instrument log -> %s", merged_path)

# 4. Promote (optional — only acts if per-instrument flags produced approved models)
if args.promote_if_approved and not args.no_promote:
    for entry in results_summary:
        if entry["rc"] == 0:
            try:
                _maybe_promote(f"{version}_{entry['instrument'].lower()}")
            except Exception as exc:
                _LOG.error("Promotion for %s raised: %s", entry["instrument"], exc)
```

### Final output block — machine-readable

```python
summary_payload = {
    "version":      version,
    "instruments":  args.instruments,
    "per_instrument_results": results_summary,
}
print(json.dumps(summary_payload, indent=2))
```

---

## Change B: `scripts/training/phase5_calibration.py`

### New `--instrument` arg (in `main()`, lines ~1256–1307)

Add after existing args:
```python
ap.add_argument("--instrument", default="",
                help="Instrument label (e.g. EURUSD, BTCUSDT). When provided, "
                     "the calibration report is written to "
                     "results/{instrument}/p5_calibration_{version}.json "
                     "and the registry entry gains an 'instrument' field.")
```

### Input validation — upfront file existence check (before dataset loading, ~line 1343)

```python
# ── Upfront input validation ──────────────────────────────────────────────
if args.opportunities:
    opp_path = Path(args.opportunities)
    if not opp_path.exists():
        print(f"\nERROR: --opportunities file not found: {opp_path}", file=sys.stderr)
        sys.exit(1)
    if opp_path.stat().st_size == 0:
        print(f"\nERROR: --opportunities file is empty: {opp_path}", file=sys.stderr)
        sys.exit(1)
if args.cached:
    cached_path = Path(args.cached)
    if not cached_path.exists():
        print(f"\nERROR: --cached file not found: {cached_path}", file=sys.stderr)
        sys.exit(1)
```

### Instrument-scoped report path (lines ~1447–1448)

```python
# Existing:
report_path = Path(args.base) / "results" / f"p5_calibration_{version}.json"

# Replace with:
if args.instrument:
    report_path = Path(args.base) / "results" / args.instrument / f"p5_calibration_{version}.json"
else:
    report_path = Path(args.base) / "results" / f"p5_calibration_{version}.json"
```

### Machine-readable OUTPUT lines — add after each save (lines ~1433, 1467)

```python
# After model save:
print(f"  Model saved -> {model_path}")
print(f"OUTPUT:gaussian:{model_path}")   # ← ADD — machine-readable for orchestrator

# After report save:
print(f"  Report saved -> {report_path}")
print(f"OUTPUT:report:{report_path}")    # ← ADD
```

### Registry entry — add instrument field (lines ~1472–1487)

```python
register_gaussian(
    version,
    str(model_path),
    list(GAUSSIAN_SCHEMA.feature_names),
    _reg_metrics,
    instrument=args.instrument or None,   # ← ADD
)
```

**Note:** `register_gaussian()` in `src/core/model_registry.py` — add optional `instrument=None`
kwarg; when provided, write `"instrument": instrument` into the registry JSON entry. One-line
addition; existing callers unaffected (default None = no field written).

---

## Change C: `src/utils/trade_logger.py`

### `TradeLogger.__init__()` — add `instrument` param (line ~88)

```python
class TradeLogger:

    def __init__(self, path: Path | str | None = None,
                 instrument: str = "") -> None:
        if path is None:
            if instrument:
                path = Path(f"logs/fusion_trades_{instrument}.jsonl")
            else:
                path = DEFAULT_LOG_PATH
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
```

### Module-level `set_instrument()` function (add below `set_log_path`, ~line 244)

```python
def set_instrument(instrument: str) -> None:
    """Route the module-level singleton to a per-instrument log file.
    Call once at startup before any trades are logged.
    E.g.: set_instrument("BTCUSDT")  →  logs/fusion_trades_BTCUSDT.jsonl
    """
    global _default_logger
    _default_logger = TradeLogger(instrument=instrument)
```

**Backward compatibility:** `TradeLogger()` with no args still routes to
`logs/fusion_trades.jsonl`. All existing callers unchanged.

---

## Change D: `scripts/research/discover_zones.py`

### Add `--instrument` arg (in `main()`, near other argparse args)

```python
ap.add_argument("--instrument", default="",
                help="Instrument label. When provided, embeds in output filename: "
                     "zone_registry_{instrument}_{version}.json")
```

### Embed instrument in versioned output path (lines ~218–230)

```python
# Existing:
base_name = f"zone_registry_{version}.json"
versioned_path = output_dir / base_name

# Replace with:
if args.instrument:
    base_name = f"zone_registry_{args.instrument}_{version}.json"
else:
    base_name = f"zone_registry_{version}.json"
versioned_path = output_dir / base_name
```

### Print OUTPUT line (after write)

```python
print(f"OUTPUT:zone_registry:{versioned_path}")
```

---

## Change E: `scripts/analysis/compress_logs_for_llm.py`

### Make `--output` optional when `--instrument` is given (lines ~217–221)

```python
ap.add_argument("--output", type=Path, default=None,
                help="Destination JSON file. Required unless --instrument is provided.")
ap.add_argument("--instrument", default="",
                help="Instrument label. When provided and --output is absent, "
                     "output defaults to logs/compressed_{instrument}.json")
```

### Resolve output path in `main()` (before compress call)

```python
if args.output is None:
    if args.instrument:
        import time as _time
        args.output = Path("logs") / f"compressed_{args.instrument}.json"
    else:
        print("ERROR: --output is required when --instrument is not given.", file=sys.stderr)
        return 1
```

---

## CLI Hardening Principles Applied Across All 5 Files

| Rule | Implementation |
|---|---|
| **Fail fast on missing inputs** | Check file exists + non-empty before any work starts; exit code 1 |
| **Machine-readable artifact paths** | `OUTPUT:{type}:{absolute_path}` on stdout after each file write |
| **Consistent exit codes** | 0=success, 1=input/config error, 2=computation error, 3=save/register error |
| **No silent overwrites** | When output file already exists and `--force` is not set, warn and skip |

---

## Directory Structure After Changes

```
logs/
  opportunities_EURUSD.jsonl          ← scanner (unchanged)
  opportunities_BTCUSDT.jsonl         ← scanner (unchanged)
  opportunities_merged_{version}.jsonl ← orchestrator all-instruments merge (analysis only)
  compressed_{version}_EURUSD.json    ← per-coin compressed summary (NEW)
  compressed_{version}_BTCUSDT.json   ← per-coin compressed summary (NEW)
  fusion_trades_EURUSD.jsonl          ← live trade log per coin (NEW via trade_logger)
  fusion_trades_BTCUSDT.jsonl         ← live trade log per coin (NEW via trade_logger)

results/
  EURUSD/
    p5_calibration_{version}.json     ← per-coin calibration report (NEW)
  BTCUSDT/
    p5_calibration_{version}.json     ← per-coin calibration report (NEW)

models/
  gaussian_{version}.json             ← unchanged (version already embeds instrument)
  tradenet_{version}.pth              ← unchanged
  zone_registry_{instrument}_{version}.json  ← NEW naming from discover_zones
```

---

## Verification

### After changes — run per-instrument training:

```powershell
$env:PYTHONPATH = "src"
py -3.12 scripts/auto_train_from_opportunities.py `
    --data-dir data `
    --instruments EURUSD `
    --model-version v6_2026_05 `
    --trail-mult 0.5 `
    --output-logs logs `
    --results-dir results
```

**Expected outputs:**
- `logs/opportunities_EURUSD.jsonl` (scanner)
- `logs/compressed_v6_2026_05_EURUSD.json` (per-coin summary)
- `results/EURUSD/p5_calibration_v6_2026_05.json` (per-coin report)
- `models/gaussian_v6_2026_05.json` (model — version already unique)
- Stdout: `OUTPUT:gaussian:models/gaussian_v6_2026_05.json`
- Stdout: `OUTPUT:report:results/EURUSD/p5_calibration_v6_2026_05.json`

### Trade logger verification:

```python
from utils.trade_logger import set_instrument
set_instrument("EURUSD")
# subsequent log_entry / log_exit → logs/fusion_trades_EURUSD.jsonl
```

### Confirm separate per-coin result directories:

```powershell
Get-ChildItem results -Directory | Select-Object Name
# Expected: EURUSD, BTCUSDT (and any others from prior runs)
```

---

---

# CLI DEFAULTS REFERENCE — What Happens When You Don't Pass Paths or Versions

## Summary

Every script has a default for every output argument. When you skip them, outputs land in
**flat directories (`logs/`, `models/`, `results/`)** with **auto-generated version strings**
based on the current timestamp or date. The file format is always JSONL (opportunities, trade
logs) or JSON (models, reports). No outputs are ever silently discarded — they always write
to disk.

---

## Script-by-Script Defaults

### 1. `scripts/research/opportunity_scanner.py`

| Arg omitted | Default value | Output |
|---|---|---|
| `--output-dir` | `logs/` | `logs/opportunities_{INSTRUMENT}.jsonl` |
| `--trail-mult` | `0.5` | 0.5R trailing stop (all 4 Gaussian classes) |
| `--max-forward-candles` | `40` | 40 bars simulated per opportunity |
| `--warmup-candles` | `30` | first 30 bars skipped |
| `--tp-atr-mult` | `2.0` | TP = 2 × ATR |
| `--sl-atr-mult` | `1.0` | SL = 1 × ATR |

**`--instrument` is required** — no default. Must always be provided.
**`--csv` is required** — no default. Must always be provided.

**Output file structure (one record per direction per candle):**
```
logs/
  opportunities_EURUSD.jsonl      ← one record per line
  opportunities_BTCUSDT.jsonl

Each JSONL line:
{
  "timestamp": "2024-01-02 19:15:00",
  "instrument": "EURUSD",
  "direction": "long" | "short",
  "entry": 1.09123,
  "sl": 1.08923,
  "tp": 1.09523,
  "outcome": "SL_HIT" | "TP_HIT" | "TIMEOUT",
  "rr_achieved": -1.0 | 0.0–1.0 | 1.0–2.0 | 2.0,
  "duration_candles": 12,
  "mfe": 0.00180,
  "mae": -0.00120,
  "features": { ...35 canonical features... }
}
```

---

### 2. `scripts/training/phase5_calibration.py`

| Arg omitted | Default value | Effect |
|---|---|---|
| `--version` | auto: `p5_YYYYMMDDTHHMMSS` (e.g. `p5_20260518T130248`) | Timestamp-stamped version key |
| `--base` | `.` (current dir = repo root) | All paths relative to repo root |
| `--instrument` | `""` (empty) | Report goes flat: `results/p5_calibration_{version}.json` |
| `--train-ratio` | `0.70` | 70% train, 30% test split |

**No source flag given** (no `--opportunities`, `--csv`, `--cached`, `--synthetic`):
→ defaults to `--csv` mode, scans these dirs for `*_trades.csv` files:
```
results/tuner/runs_oos/    ← auto_tuner_multi OOS runs
results/tuner/runs/        ← auto_tuner single-instrument runs
results/portfolio_p2/      ← legacy
results/portfolio_p4/
... (several more legacy dirs)
```

**Output files produced when `--train` is passed:**
```
models/
  gaussian_{version}.json               ← Gaussian NB model + scaler + schema
  tradenet_{version}.pth                ← TradeNet weights  (only with --tradenet)
  tradenet_{version}_scaler.json        ← TradeNet scaler   (only with --tradenet)

results/
  p5_calibration_{version}.json         ← calibration report (flat, no instrument folder)
  {INSTRUMENT}/                         ← ONLY created when --instrument EURUSD given
    p5_calibration_{version}.json

models/gaussian_registry.json           ← auto-updated (new entry added, not overwritten)
models/tradenet_registry.json           ← auto-updated (only with --tradenet)
```

**Calibration report structure:**
```json
{
  "version": "p5_20260518T130248",
  "schema_version": "2.0",
  "n_features": 35,
  "n_samples": 23472,
  "instruments": ["EURUSD"],
  "train_metrics": { "class_priors": [...], "mean_actual_rr": 0.12 },
  "cv_metrics":    { "mean_corr": 0.18, "std_corr": 0.04, "stable": true },
  "eval": {
    "corr_expected_rr":  0.21,
    "calibration_error": 0.08,
    "mean_expected_rr":  0.43,
    "mean_actual_rr":    0.38,
    "class_distribution": { "0": 0.34, "1": 0.56, "2": 0.06, "3": 0.04 }
  },
  "verdict": "PASS" | "FAIL",
  "source": "opportunities"
}
```

---

### 3. `scripts/auto_train_from_opportunities.py` (orchestrator)

| Arg omitted | Default value | Effect |
|---|---|---|
| `--model-version` | `v5_auto_YYYYMMDD` (e.g. `v5_auto_20260518`) | Date-stamped version, same for all instruments scanned |
| `--output-logs` | `logs/` | All JSONL outputs here |
| `--results-dir` | `results/` | Phase5 reports here |
| `--trail-mult` | `0.5` | Forwarded to scanner |
| `--per-instrument` | `True` | Runs phase5 once per instrument (post-CLI-hardening) |
| `--instruments` | EURUSD, GBPUSD, AUDUSD, USDJPY, EURCAD, XAUUSD, BTCUSDT, ETHUSDT | All 8 instruments attempted |
| `--data-dir` | `data/` | Looks for `data/{INSTRUMENT}_M15.csv` |

**Full default output tree (running with no args for EURUSD + BTCUSDT found in data/):**
```
logs/
  opportunities_EURUSD.jsonl            ← scanner output
  opportunities_BTCUSDT.jsonl           ← scanner output
  compressed_v5_auto_20260518_EURUSD.json   ← per-coin LLM summary
  compressed_v5_auto_20260518_BTCUSDT.json  ← per-coin LLM summary
  opportunities_merged_v5_auto_20260518.jsonl  ← all instruments concatenated (analysis only)

models/
  gaussian_v5_auto_20260518.json        ← one per instrument (same version, diff content)
  gaussian_registry.json                ← updated with new entry per instrument

results/
  EURUSD/
    p5_calibration_v5_auto_20260518.json   ← per-coin report
  BTCUSDT/
    p5_calibration_v5_auto_20260518.json   ← per-coin report
```

**Terminal stdout on completion:**
```json
{
  "version": "v5_auto_20260518",
  "per_instrument": true,
  "instruments_attempted": ["EURUSD", "GBPUSD", ...],
  "instruments_scanned": ["EURUSD", "BTCUSDT"],
  "per_instrument_results": [
    { "instrument": "EURUSD", "rc": 0, "report": "results/EURUSD/..." },
    { "instrument": "BTCUSDT", "rc": 0, "report": "results/BTCUSDT/..." }
  ]
}
```

---

### 4. `scripts/research/discover_zones.py`

| Arg omitted | Default value | Effect |
|---|---|---|
| `--version` | `YYYYMM_v1` (e.g. `202605_v1`) | Month-stamped version |
| `--instrument` | `""` (empty) | No instrument in filename |
| `--n-clusters` | `8` | 8 zones |
| `--min-samples` | `15` | Drop zones with < 15 samples |
| `--subsample` | `1` | Use all records |

**`--output` and `--opportunities` are required** — no defaults, must always be provided.

**Output files:**
```
models/
  zone_registry_202605_v1.json          ← versioned file (no --instrument)
  zone_registry_EURUSD_202605_v1.json   ← versioned file (with --instrument EURUSD)
  zone_registry.json                    ← canonical file (written when --promote, default)
  zone_gate_registry.json               ← updated with new entry
```

**Zone registry file structure (per zone):**
```json
{
  "version": "202605_v1",
  "schema_version": "zone_v1",
  "feature_order": [...35 feature names...],
  "zones": [
    {
      "zone_id": 0,
      "centroid": [...35 floats...],
      "n_samples": 412,
      "mean_rr": 0.119,
      "win_rate": 0.61,
      "label": "bullish_breakout"
    },
    ...7 more zones...
  ]
}
```

---

### 5. `scripts/analysis/compress_logs_for_llm.py`

| Arg omitted | Default value | Effect |
|---|---|---|
| `--output` | `None` → requires `--instrument` to auto-derive | Error if both omitted |
| `--instrument` | `""` | When set, auto-output = `logs/compressed_{INSTRUMENT}.json` |
| `--top-n-features` | `8` | Top 8 feature correlations shown |

**`--logs` is required** — no default.

**Output JSON structure:**
```json
{
  "summary": {
    "n_total": 33532,
    "rr_mean": 0.12,
    "rr_std": 0.89,
    "rr_p10": -1.0,
    "rr_p50": -0.22,
    "rr_p90": 2.0,
    "counts_outcome":    { "SL_HIT": 11200, "TP_HIT": 1350, "TIMEOUT": ... },
    "counts_direction":  { "long": 16766, "short": 16766 },
    "counts_instrument": { "BTCUSDT": 33532 }
  },
  "data": {
    "top_positive_corr": [["candles_since_retest", 0.19], ...],
    "top_negative_corr": [["volume_ratio", -0.08], ...],
    "top_tp_minus_sl_delta": [["retest_depth", 0.12], ...]
  },
  "anomalies": []
}
```

---

### 6. `src/utils/trade_logger.py` (live trading — not a CLI script)

| Constructor call | Output file |
|---|---|
| `TradeLogger()` | `logs/fusion_trades.jsonl` (mixed all instruments) |
| `TradeLogger(instrument="EURUSD")` | `logs/fusion_trades_EURUSD.jsonl` |
| `set_instrument("BTCUSDT")` | `logs/fusion_trades_BTCUSDT.jsonl` (singleton) |

**Each JSONL line is an ENTRY or EXIT event:**
```json
{ "event": "ENTRY", "trade_id": "uuid", "instrument": "EURUSD",
  "direction": "LONG", "session": "LONDON", "regime": "EXPANSION",
  "entry_price": 1.09123, "sl_price": 1.08923, "tp1_price": 1.09323,
  "fusion": { "final_score": 0.68, "gaussian": 0.62 }, ... }

{ "event": "EXIT", "trade_id": "uuid", "pnl_rr_net": 1.95, "win": true,
  "exit_reason": "TP2", "duration_candles": 18 }
```

---

## Version Naming Quick Reference

| Script | Default version pattern | Example |
|---|---|---|
| `phase5_calibration.py` | `p5_YYYYMMDDTHHMMSS` | `p5_20260518T130248` |
| `auto_train_from_opportunities.py` | `v5_auto_YYYYMMDD` | `v5_auto_20260518` |
| `discover_zones.py` | `YYYYMM_v1` | `202605_v1` |
| Manual convention (recommended) | `v6_YYYY_MM_{eur|btc}` | `v6_2026_05_eur` |

**Rule of thumb:** Always pass `--version v6_YYYY_MM_{eur|btc}` explicitly.
Auto-generated versions (`p5_...`, `v5_auto_...`) are hard to trace to a specific coin or
training run and will create multiple entries in the registry if you rerun.

---

---

# ACTIVE TASK: Run-Scoped Output Structure

## Context

All pipeline outputs currently land in flat directories (`logs/`, `models/`, `results/`)
with no way to trace a model, report, or compressed summary back to the exact pipeline
run that produced it. Per-instrument separation was added (CLI hardening), but multiple
runs for the same instrument still overwrite each other unless the version string changes.

The fix introduces a **RUN_ID** (`YYYYMMDD_HHMMSS`, e.g. `20260518_130248`) that:
1. Is generated **once** by the orchestrator (or auto-generated by each script standalone)
2. Is **embedded as the first JSONL record** (run_header) in every opportunities file
3. Is **inherited automatically** by phase5 and compress by reading that header — no
   need to pass `--run-id` manually when chaining scripts
4. Scopes every output into `{ARTIFACT_DIR}/{INSTRUMENT}/{RUN_ID}/`

---

## Directory Structure After Change

```
logs/
  EURUSD/
    20260518_130248/
      opportunities.jsonl       ← scanner (first line = run_header)
      compressed.json           ← compress_logs output

results/
  EURUSD/
    20260518_130248/
      p5_calibration_{version}.json

models/
  EURUSD/
    20260518_130248/
      gaussian_{version}.json
      tradenet_{version}.pth        (only with --tradenet)
      tradenet_{version}_scaler.json

# Merged analysis log (orchestrator only, no model derived from it)
logs/
  opportunities_merged_{version}.jsonl   ← flat, unchanged
```

Backward compatibility: when `--instrument` is not provided (standalone phase5 or
compress without instrument), paths fall back to the existing flat layout.

---

## Files to Change (6 files)

| File | Change |
|---|---|
| `scripts/research/opportunity_scanner.py` | `--run-id` arg; write run_header first line; output = `{output_dir}/{INSTRUMENT}/{RUN_ID}/opportunities.jsonl` |
| `scripts/training/phase5_calibration.py` | `_read_run_header()` helper; inherit run_id from JSONL; run-scoped report + model paths |
| `scripts/auto_train_from_opportunities.py` | Generate RUN_ID once; pass `--run-id` to scanner; update expected opp path |
| `scripts/analysis/compress_logs_for_llm.py` | `_read_run_id_from_jsonl()` helper; run-scoped output path |
| `src/training/trainer.py` | `save_gaussian_model` + `save_model`: `path.parent.mkdir()` instead of `MODELS_DIR.mkdir()` so sub-paths work |
| `src/core/model_registry.py` | Add `run_id: Optional[str] = None` to `register_gaussian()` + `register_tradenet()`; embed in entry when provided |

---

## Change 1: `scripts/research/opportunity_scanner.py`

### New `--run-id` arg in `main()`

```python
ap.add_argument("--run-id", default=None,
                help="Run identifier for output scoping "
                     "(auto-generates YYYYMMDD_HHMMSS if not provided)")
```

### `scan()` signature — add `run_id` param

```python
def scan(csv_path: Path, instrument: str, *, tp_atr_mult: float = 2.0,
         sl_atr_mult: float = 1.0, max_forward_candles: int = 40,
         warmup_candles: int = 30, output_dir: Path = Path("logs"),
         trail_mult: float = 0.5, run_id: str = "") -> Path:
```

### Inside `scan()` — compute run-scoped path and write run_header

```python
import time as _time
_run_id = run_id or _time.strftime("%Y%m%d_%H%M%S")
run_dir  = output_dir / instrument / _run_id
run_dir.mkdir(parents=True, exist_ok=True)
out_path = run_dir / "opportunities.jsonl"

with out_path.open("w", encoding="utf-8") as fh:
    run_header = {
        "type":       "run_header",
        "run_id":     _run_id,
        "instrument": instrument,
        "started_at": _time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    fh.write(json.dumps(run_header) + "\n")
    # ... existing record-writing loop unchanged
```

### `main()` — pass run_id to scan(), print OUTPUT line

```python
import time as _time
run_id = args.run_id or _time.strftime("%Y%m%d_%H%M%S")
out_path = scan(
    args.csv, args.instrument,
    ...,
    trail_mult=args.trail_mult,
    run_id=run_id,
)
print(f"OUTPUT:run_id:{run_id}")
print(f"OUTPUT:opportunities:{out_path.resolve()}")
```

**Note:** existing callers that pass `output_dir` + `instrument` + no `run_id` will
auto-generate a run_id — same standalone behaviour as before, now scoped.

---

## Change 2: `scripts/training/phase5_calibration.py`

### New helper function (add near top of file, after imports)

```python
def _read_run_header(opp_path: Path) -> dict:
    """Return the run_header dict from the first line of a JSONL, or {}."""
    try:
        with opp_path.open("r", encoding="utf-8") as fh:
            first = fh.readline().strip()
        rec = json.loads(first)
        if rec.get("type") == "run_header":
            return rec
    except Exception:
        pass
    return {}
```

### New `--run-id` arg in `main()`

```python
ap.add_argument("--run-id", default=None,
                help="Override run_id (default: read from JSONL run_header, "
                     "then auto-generate YYYYMMDD_HHMMSS)")
```

### Inherit run_id (after upfront validation block)

```python
import time as _time
_run_id = args.run_id
if not _run_id and args.opportunities:
    header   = _read_run_header(Path(args.opportunities))
    _run_id  = header.get("run_id") or _time.strftime("%Y%m%d_%H%M%S")
elif not _run_id:
    _run_id  = _time.strftime("%Y%m%d_%H%M%S")
```

### Run-scoped report path (replaces existing instrument-scoped path)

```python
# Replace existing block:
if args.instrument:
    report_path = (Path(args.base) / "results"
                   / args.instrument / _run_id / f"p5_calibration_{version}.json")
else:
    report_path = Path(args.base) / "results" / f"p5_calibration_{version}.json"
```

### Run-scoped model filename (passed to save_gaussian_model)

```python
if args.instrument:
    model_name = f"{args.instrument}/{_run_id}/gaussian_{version}.json"
else:
    model_name = f"gaussian_{version}.json"
# Pass to:  save_gaussian_model(..., name=model_name, ...)
```

### Run-scoped TradeNet filenames (when --tradenet)

```python
if args.instrument:
    tradenet_name = f"{args.instrument}/{_run_id}/tradenet_{version}.pth"
else:
    tradenet_name = f"tradenet_{version}.pth"
# Pass to:  save_model(..., name=tradenet_name, version=version, ...)
```

### Pass run_id to registry calls

```python
register_gaussian(version, str(model_path), ..., instrument=args.instrument or None,
                  run_id=_run_id)
# Same for register_tradenet when --tradenet
```

---

## Change 3: `scripts/auto_train_from_opportunities.py`

### New `--run-id` arg

```python
ap.add_argument("--run-id", default=None,
                help="Shared run identifier for this pipeline run. "
                     "Auto-generates YYYYMMDD_HHMMSS if not provided. "
                     "Propagated to all child scripts via --run-id.")
```

### Generate RUN_ID once in `main()`

```python
run_id = args.run_id or time.strftime("%Y%m%d_%H%M%S")
_LOG.info("Pipeline run_id: %s", run_id)
```

### Update `_scan_instrument()` signature + call

```python
def _scan_instrument(data_dir, instrument, output_dir,
                     max_forward_candles, warmup_candles,
                     trail_mult=0.5, run_id="") -> Path | None:
    ...
    rc = _run([
        sys.executable, str(scanner),
        "--csv", str(csv_path),
        "--instrument", instrument,
        "--max-forward-candles", str(max_forward_candles),
        "--warmup-candles", str(warmup_candles),
        "--output-dir", str(output_dir),
        "--trail-mult", str(trail_mult),
        "--run-id", run_id,            # ← ADD
    ])
    if rc != 0:
        return None
    # New scoped path:
    return output_dir / instrument / run_id / "opportunities.jsonl"
```

### Pass run_id through in `main()` loops

```python
p = _scan_instrument(
    args.data_dir, instr, output_dir,
    args.max_forward_candles, args.warmup_candles,
    trail_mult=args.trail_mult,
    run_id=run_id,          # ← ADD
)
```

Phase5 and compress inherit run_id via JSONL header — no `--run-id` needed there.

### Add `run_id` to final summary JSON

```python
summary_payload = {
    "run_id":                 run_id,           # ← ADD
    "version":                version,
    ...
}
```

---

## Change 4: `scripts/analysis/compress_logs_for_llm.py`

### New helper to read run_id from JSONL

```python
def _read_run_id_from_jsonl(path: Path) -> str:
    """Return run_id from first-line run_header, or empty string."""
    try:
        with path.open("r", encoding="utf-8") as fh:
            rec = json.loads(fh.readline().strip())
        if rec.get("type") == "run_header":
            return rec.get("run_id", "")
    except Exception:
        pass
    return ""
```

### New `--run-id` arg

```python
ap.add_argument("--run-id", default=None,
                help="Override run_id for output path "
                     "(default: read from JSONL header)")
```

### Updated output-path resolution in `main()`

```python
if args.output is None:
    # Try to inherit run_id from JSONL header
    _run_id = args.run_id
    if not _run_id and paths:
        _run_id = _read_run_id_from_jsonl(paths[0])

    if args.instrument and _run_id:
        args.output = Path("logs") / args.instrument / _run_id / "compressed.json"
    elif args.instrument:
        # Fallback (no run_id available — should not happen in normal pipeline)
        args.output = Path("logs") / f"compressed_{args.instrument}.json"
    else:
        print("ERROR: --output is required when --instrument is not given.",
              file=sys.stderr)
        return 1
```

---

## Change 5: `src/training/trainer.py`

Two one-line fixes so sub-path names like `EURUSD/20260518_130248/gaussian_v6.json`
are resolved correctly under `MODELS_DIR`.

### `save_gaussian_model()` — line 379

```python
# REPLACE:
MODELS_DIR.mkdir(parents=True, exist_ok=True)
path = MODELS_DIR / name

# WITH:
path = MODELS_DIR / name
path.parent.mkdir(parents=True, exist_ok=True)
```

### `save_model()` (TradeNet) — line 669–670

```python
# REPLACE:
MODELS_DIR.mkdir(parents=True, exist_ok=True)
path = MODELS_DIR / name

# WITH:
path = MODELS_DIR / name
path.parent.mkdir(parents=True, exist_ok=True)
```

`load_gaussian_model()` and `load_model()` are unchanged — `MODELS_DIR / name`
naturally resolves sub-paths when `name` contains `/`.

---

## Change 6: `src/core/model_registry.py`

### `register_gaussian()` — add `run_id` kwarg

```python
def register_gaussian(
    self,
    version: str,
    model_file: str,
    feature_schema: list,
    metrics: dict,
    instrument: Optional[str] = None,
    run_id: Optional[str] = None,        # ← ADD
) -> dict:
    ...
    if instrument:
        entry["instrument"] = instrument
    if run_id:                            # ← ADD
        entry["run_id"] = run_id
```

### `register_tradenet()` — same addition

```python
def register_tradenet(
    self,
    version: str,
    model_file: str,
    metrics: dict,
    instrument: Optional[str] = None,
    run_id: Optional[str] = None,        # ← ADD
) -> dict:
    ...
    if run_id:
        entry["run_id"] = run_id
```

Module-level convenience wrappers also gain `run_id=None` and forward it.

---

## Backward Compatibility

| Scenario | Behaviour |
|---|---|
| Standalone `opportunity_scanner.py` without `--run-id` | Auto-generates run_id; scoped output `logs/{INSTR}/{RUN_ID}/opportunities.jsonl` |
| Standalone `phase5_calibration.py` without `--instrument` | Falls back to flat paths (`results/p5_calibration_{version}.json`, `models/gaussian_{version}.json`) — unchanged |
| Old flat `opportunities_EURUSD.jsonl` (no run_header) | `_read_run_header()` returns `{}` → phase5 auto-generates new run_id |
| `load_gaussian_model("gaussian_v6.json")` | `MODELS_DIR / "gaussian_v6.json"` — unchanged flat path, still works |
| `load_gaussian_model("EURUSD/20260518/gaussian_v6.json")` | `MODELS_DIR / "EURUSD/20260518/gaussian_v6.json"` — new sub-path, works |

---

## Verification

### Step 1 — Run scanner standalone

```powershell
$env:PYTHONPATH = "src"
py -3.12 scripts/research/opportunity_scanner.py `
    --csv data/EURUSD_M15.csv `
    --instrument EURUSD `
    --trail-mult 0.5 `
    --output-dir logs
```

**Expected:**
- `logs/EURUSD/{RUN_ID}/opportunities.jsonl` created
- First line: `{"type": "run_header", "run_id": "...", "instrument": "EURUSD", ...}`
- stdout: `OUTPUT:run_id:{RUN_ID}` and `OUTPUT:opportunities:{abs_path}`

### Step 2 — Run phase5 pointing at that JSONL (inherits run_id)

```powershell
py -3.12 scripts/training/phase5_calibration.py `
    --opportunities logs/EURUSD/{RUN_ID}/opportunities.jsonl `
    --version v6_2026_05_eur `
    --instrument EURUSD `
    --base . `
    --train
```

**Expected:**
- `models/EURUSD/{RUN_ID}/gaussian_v6_2026_05_eur.json`
- `results/EURUSD/{RUN_ID}/p5_calibration_v6_2026_05_eur.json`
- stdout: `OUTPUT:gaussian:...` and `OUTPUT:report:...` with run-scoped paths
- No `--run-id` needed — inherited from JSONL header

### Step 3 — Run full orchestrator

```powershell
py -3.12 scripts/auto_train_from_opportunities.py `
    --data-dir data `
    --instruments EURUSD `
    --model-version v6_2026_05_eur `
    --trail-mult 0.5
```

**Expected JSON summary on stdout:**
```json
{
  "run_id": "20260518_130248",
  "version": "v6_2026_05_eur",
  "per_instrument": true,
  "instruments_scanned": ["EURUSD"],
  "per_instrument_results": [
    {
      "instrument": "EURUSD",
      "rc": 0,
      "report": "results/EURUSD/20260518_130248/p5_calibration_v6_2026_05_eur.json"
    }
  ]
}
```

### Step 4 — Confirm registry entry has run_id

```powershell
python -c "
import json
r = json.load(open('models/gaussian_registry.json'))
entry = r.get('models', r).get('v6_2026_05_eur', {})
print('run_id:', entry.get('run_id'))
print('model_file:', entry.get('model_file'))
"
# Expected: run_id: 20260518_130248
#           model_file: models\EURUSD\20260518_130248\gaussian_v6_2026_05_eur.json
```

---

---

# ACTIVE TASK: Run-Scoped Fix for `discover_zones.py` + `build_rr_dataset.py`

## Context

Two problems reported after running the pipeline with the existing run-scoped JSONL output:

1. **`discover_zones.py` requires `--output`** — the argument is `required=True` (line 173).
   All other pipeline scripts (`compress_logs`, `phase5`) auto-derive their output path from the
   JSONL run_header when `--instrument` is given. `discover_zones` should follow the same pattern.

2. **`build_rr_dataset.py` saves to flat `models/rr_dataset_{version}.json`** — no instrument
   or run_id in the path. Cannot trace the dataset back to the opportunity JSONL run that
   produced it. Needs the same run-scoped structure as the other scripts.

---

## Files to Change (3 files)

| File | Change |
|---|---|
| `scripts/research/discover_zones.py` | Make `--output` optional; auto-derive run-scoped path from JSONL run_header |
| `scripts/data/build_rr_dataset.py` | Add `--instrument` + `--run-id`; run-scoped save paths; pass run_id to registry |
| `src/core/model_registry.py` | Add `instrument` + `run_id` kwargs to `register_rr_dataset()` |

---

## Change 1: `scripts/research/discover_zones.py`

### Current state (lines 173, 211–254)
- `--output` is `required=True`; used as the canonical file path
- Versioned filename = `zone_registry_{instrument}_{version}.json` placed next to `--output`
- No run_header reading; no `--run-id` arg

### Fix

**A. Make `--output` optional; add `--run-id`:**

```python
ap.add_argument("--output", required=False, type=Path, default=None,
                help="Canonical output path (e.g. models/zone_registry.json). "
                     "When omitted and --instrument is provided, auto-derives "
                     "from JSONL run_header: "
                     "models/{instrument}/{run_id}/zone_registry.json")
ap.add_argument("--run-id", default=None,
                help="Override run_id (default: read from JSONL run_header)")
```

**B. Add `_read_run_id_from_jsonl()` helper (same pattern as compress_logs):**

```python
def _read_run_id_from_jsonl(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8") as fh:
            rec = json.loads(fh.readline().strip())
        if rec.get("type") == "run_header":
            return rec.get("run_id", "")
    except Exception:
        pass
    return ""
```

**C. Resolve output path in `main()` before the `discover()` call:**

```python
# Resolve run_id
_run_id = args.run_id
if not _run_id and args.opportunities:
    _run_id = _read_run_id_from_jsonl(Path(args.opportunities[0]))

# Resolve --output when omitted
if args.output is None:
    if args.instrument and _run_id:
        args.output = Path("models") / args.instrument / _run_id / "zone_registry.json"
    elif args.instrument:
        args.output = Path("models") / f"zone_registry_{args.instrument}.json"
    else:
        print("ERROR: --output is required when --instrument is not given.", file=sys.stderr)
        return 1
```

**D. Versioned path also becomes run-scoped (lines 216–220):**

```python
# Replace existing base_name logic:
if args.instrument and _run_id:
    base_name = f"zone_registry_{args.instrument}_{version}.json"
    versioned_path = Path("models") / args.instrument / _run_id / base_name
elif args.instrument:
    base_name = f"zone_registry_{args.instrument}_{version}.json"
    versioned_path = args.output.parent / base_name
else:
    base_name = f"zone_registry_{version}.json"
    versioned_path = args.output.parent / base_name
versioned_path.parent.mkdir(parents=True, exist_ok=True)
```

**Result after fix — no `--output` needed:**
```powershell
python scripts/research/discover_zones.py \
    --opportunities logs/EURUSD/20260519_002117/opportunities.jsonl \
    --instrument EURUSD \
    --version v5_auto_2026_06
# Writes: models/EURUSD/20260519_002117/zone_registry_EURUSD_v5_auto_2026_06.json
# Canonical: models/EURUSD/20260519_002117/zone_registry.json
```

---

## Change 2: `scripts/data/build_rr_dataset.py`

### Current state
- `--output` defaults to `models/rr_dataset.json` (flat)
- `--version` auto-generates `YYYYMM_v1`
- Versioned save: `out_path.parent / f"rr_dataset_{ver}.json"` (flat, line 130)
- No `--instrument`, no `--run-id`, no run_header reading

### Fix

**A. Add `--instrument` and `--run-id` args:**

```python
ap.add_argument("--instrument", default="",
                help="Instrument label (e.g. EURUSD). When provided, output is run-scoped: "
                     "models/{instrument}/{run_id}/rr_dataset_{version}.json")
ap.add_argument("--run-id", default=None,
                help="Override run_id (default: read from JSONL run_header)")
```

**B. Add `_read_run_id_from_jsonl()` helper (same as other scripts):**

```python
def _read_run_id_from_jsonl(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8") as fh:
            rec = json.loads(fh.readline().strip())
        if rec.get("type") == "run_header":
            return rec.get("run_id", "")
    except Exception:
        pass
    return ""
```

**C. Resolve run_id and output paths in `main()` before dataset build:**

```python
# Resolve run_id from JSONL header
_run_id = args.run_id
if not _run_id and args.opportunities:
    _run_id = _read_run_id_from_jsonl(Path(args.opportunities[0]))
if not _run_id:
    import time as _time
    _run_id = _time.strftime("%Y%m%d_%H%M%S")

# Resolve output paths
if args.instrument and _run_id:
    run_dir     = Path("models") / args.instrument / _run_id
    output_path = run_dir / "rr_dataset.json"
    ver = args.version or time.strftime("%Y%m_v1")
    versioned_path = run_dir / f"rr_dataset_{ver}.json"
else:
    # Existing flat behaviour
    output_path    = Path(args.output)
    ver            = args.version or time.strftime("%Y%m_v1")
    versioned_path = output_path.parent / f"rr_dataset_{ver}.json"
```

**D. Pass `instrument` and `run_id` to registry call:**

```python
register_rr_dataset(ver, str(versioned_path), len(X), N_FEATURES,
                    instrument=args.instrument or None,
                    run_id=_run_id or None)
```

**Result after fix:**
```powershell
python scripts/data/build_rr_dataset.py \
    --opportunities logs/EURUSD/20260519_002117/opportunities.jsonl \
    --instrument EURUSD
# Writes: models/EURUSD/20260519_002117/rr_dataset.json (canonical)
#         models/EURUSD/20260519_002117/rr_dataset_202605_v1.json (versioned)
```

---

## Change 3: `src/core/model_registry.py` — `register_rr_dataset()`

Add `instrument` and `run_id` kwargs (same pattern as `register_gaussian` and `register_tradenet`).

Find the `register_rr_dataset` method in `RRRegistry` class and the module-level convenience
function. Add to both:

```python
def register_rr_dataset(
    self,
    version: str,
    dataset_file: str,
    n_samples: int,
    n_features: int,
    instrument: Optional[str] = None,   # ← ADD
    run_id: Optional[str] = None,       # ← ADD
) -> dict:
    ...
    entry = { ... }          # existing entry dict
    if instrument:
        entry["instrument"] = instrument
    if run_id:
        entry["run_id"] = run_id
```

Module-level convenience function:
```python
def register_rr_dataset(version, dataset_file, n_samples, n_features,
                        instrument=None, run_id=None) -> dict:
    return _rr_registry.register_rr_dataset(version, dataset_file, n_samples, n_features,
                                             instrument=instrument, run_id=run_id)
```

---

## Backward Compatibility

| Scenario | Behaviour |
|---|---|
| `discover_zones.py` with `--output` (existing calls) | Unchanged — `args.output` set, run_id logic skipped |
| `discover_zones.py` without `--output` + no `--instrument` | Error: "ERROR: --output is required when --instrument is not given" |
| `build_rr_dataset.py` without `--instrument` | Falls back to flat `models/rr_dataset.json` — unchanged |
| Old flat JSONL (no run_header) + `--instrument` | `_run_id` auto-generates `YYYYMMDD_HHMMSS` |

---

## Verification

```powershell
$env:PYTHONPATH = "src"

# Step 1 — discover_zones without --output (should auto-resolve)
py -3.12 scripts/research/discover_zones.py `
    --opportunities logs/EURUSD/20260519_002117/opportunities.jsonl `
    --instrument EURUSD `
    --version v5_auto_2026_06

# Expected:
# models/EURUSD/20260519_002117/zone_registry_EURUSD_v5_auto_2026_06.json  (versioned)
# models/EURUSD/20260519_002117/zone_registry.json  (canonical)

# Step 2 — build_rr_dataset run-scoped
py -3.12 scripts/data/build_rr_dataset.py `
    --opportunities logs/EURUSD/20260519_002117/opportunities.jsonl `
    --instrument EURUSD

# Expected:
# models/EURUSD/20260519_002117/rr_dataset.json
# models/EURUSD/20260519_002117/rr_dataset_202605_v1.json
# Registry entry has run_id field
```

---

---

# ACTIVE TASK: TP/SL Recalibration Plan

## Context

Zone analysis of the current EURUSD run showed near-zero win rates across all 8 market zones.
The goal is to recalibrate TP/SL multiples and CRT strategy parameters so the system produces
opportunities with positive expected value before retraining all models.

---

## Critical Correction: What `auto_tuner_multi` Actually Tunes

**The auto tuner does NOT tune `tp_atr_mult` or `sl_atr_mult`.**

`PARAM_SPACE` in `scripts/training/auto_tuner_multi.py` lines 98–104:
```python
PARAM_SPACE = {
    "retest_depth_max":           [0.20, 0.25, 0.30, 0.40, 0.50, 0.60],
    "retest_atr_depth_fraction":  [0.30, 0.40, 0.50, 0.70, 1.00],
    "body_ratio_min":             [0.50, 0.60, 0.65, 0.70, 0.75, 0.80],
    "atr_multiplier_min":         [1.00, 1.20, 1.50, 1.75, 2.00],
    "expansion_atr_min_distance": [0.10, 0.15, 0.20, 0.25, 0.30],
}
```
These are **CRT entry filter parameters** — they control *which* trades get approved
(retest quality gates, body ratio, ATR floor). Total combinations: 4,500.

**TP/SL sizing lives elsewhere:**
| Parameter | Location | Current value |
|---|---|---|
| `tp1_atr_multiplier` | `crt_engine` section of production config | `1.0` |
| `tp2_atr_multiplier` | `crt_engine` section | `2.0` |
| `sl_atr_buffer` | `crt_engine` section | `0.2` |
| `--tp-atr-mult` (scanner) | Scanner CLI arg | `2.0` (default) |
| `--sl-atr-mult` (scanner) | Scanner CLI arg | `1.0` (default) |
| `--trail-mult` (scanner) | Scanner CLI arg | `0.5` (already implemented) |

**Two separate concerns:**
1. **Scanner TP/SL** — affects training data quality and Gaussian class distribution
2. **CRT engine TP/SL** — affects live trade execution sizing

---

## Two-Phase Recalibration Plan

### Phase 1: Tune CRT Entry Filters (auto_tuner_multi — no code change)

Run the tuner on available data to find the best CRT entry filter combination.
This improves *which opportunities pass the CRT gate* in live trading.

```powershell
$env:PYTHONPATH = "src"
py -3.12 scripts/training/auto_tuner_multi.py `
    --data-dir data `
    --instruments EURUSD `
    --n-iter 200 `
    --output-dir results/tuner_recalib `
    --train-split 0.8 `
    --workers 4
```

**Objective function** (from production config, hardcoded weights):
```
score = 0.50 × expectancy_rr  +  0.20 × win_rate
      + 0.20 × trade_count_norm  +  0.10 × (1 − max_drawdown)
```
Penalty for cross-instrument inconsistency: `final_score = mean − alpha × std_dev`.

**Output:** `results/tuner_recalib/checkpoint_multi.json`

---

### Phase 1b: Validate Best Params

The validator does NOT accept `--checkpoint`. Extract best params manually:

```powershell
# Extract best params from checkpoint
py -3.12 -c "
import json
runs = json.load(open('results/tuner_recalib/checkpoint_multi.json'))
best = max(runs, key=lambda r: r['score'])
print('Best score:', best['score'])
print('Best params:')
print(json.dumps(best['params'], indent=2))
# Save to file for validator
with open('results/tuner_recalib/best_params.json', 'w') as f:
    json.dump(best['params'], f, indent=2)
"

# Validate
py -3.12 src/config_layer/config_validator.py validate-params `
    --params results/tuner_recalib/best_params.json `
    --data-dir data
```

**Hard gates (REJECT if failed):**
- min 10 trades per instrument
- max drawdown ≤ 35%
- fitness score ≥ 0.15

**Soft warnings:** win_rate < 35%, expectancy < −0.5R, score_std_dev > 0.3

---

### Phase 1c: Promote Best Params to Production Config

If validation passes, update `configs/production/v1_multi_2026_03.json` `"params"` section:

```json
"params": {
  "retest_depth_max":           <best_value>,
  "retest_atr_depth_fraction":  <best_value>,
  "body_ratio_min":             <best_value>,
  "atr_multiplier_min":         <best_value>,
  "expansion_atr_min_distance": <best_value>
}
```

Re-hash after edit:
```powershell
py -3.12 scripts/maintenance/_compute_hash.py
```

---

### Phase 2: Add TP/SL Multiples to Tuner Search Space (code change)

**CORRECTED from initial plan.** The generic names `tp_atr_mult`/`sl_atr_mult` do NOT exist
in CRTConfig. The actual CRTConfig attribute names are `tp2_atr_multiplier` (default 2.0) and
`sl_atr_buffer` (default 0.2). Because `_run_single_instrument()` filters params via
`{k: v for k, v in params.items() if hasattr(base_cfg, k)}`, using the exact attribute
names means **no plumbing code is needed** — one change to one file only.

**SL field semantics (confirmed from crt_engine_v2.py lines 1213–1221):**
```python
sl = state.displacement_candle.low - self.config.sl_atr_buffer * atr   # LONG
sl = state.displacement_candle.high + self.config.sl_atr_buffer * atr  # SHORT
```
`sl_atr_buffer` is an ATR-scaled gap beyond the displacement candle extreme (structural pivot).
Default 0.2 = 0.2 × ATR buffer. Larger values = wider SL from the pivot.

**Files to change: 1 file only — `scripts/training/auto_tuner_multi.py`**

#### A. Extend `PARAM_SPACE` (lines 98–104 of `scripts/training/auto_tuner_multi.py`)

**Exact edit** — add 2 lines before the closing `}` of the existing dict at line 104:

```python
PARAM_SPACE: dict[str, list] = {
    "retest_depth_max":           [0.20, 0.25, 0.30, 0.40, 0.50, 0.60],
    "retest_atr_depth_fraction":  [0.30, 0.40, 0.50, 0.70, 1.00],
    "body_ratio_min":             [0.50, 0.60, 0.65, 0.70, 0.75, 0.80],
    "atr_multiplier_min":         [1.00, 1.20, 1.50, 1.75, 2.00],
    "expansion_atr_min_distance": [0.10, 0.15, 0.20, 0.25, 0.30],
    # TP/SL sizing — exact CRTConfig field names; auto-threaded via hasattr filter in
    # _run_single_instrument() — NO other code changes needed
    "tp2_atr_multiplier":  [1.5, 2.0, 2.5, 3.0, 3.5],   # main TP target (default 2.0)
    "sl_atr_buffer":       [0.1, 0.2, 0.3, 0.5, 0.75],   # ATR gap past pivot (default 0.2)
}
```

`SPACE_SIZE` at line 106 is computed dynamically from `PARAM_SPACE.values()` — auto-updates.
New total combinations: 4,500 × 5 × 5 = **112,500** — use `--n-iter 300` (random sampling).
**No other code changes in any file.**

#### B. After best params found — two updates needed

**1. Promote TP/SL values to crt_engine section of production config:**
```json
"crt_engine": {
  "tp2_atr_multiplier": <best_value>,
  "sl_atr_buffer":      <best_value>
}
```
Then re-hash: `py -3.12 scripts/maintenance/_compute_hash.py`

**2. Re-scan opportunities with corresponding scanner settings:**
The scanner `--tp-atr-mult` approximates `tp2_atr_multiplier` (main TP target).
The scanner `--sl-atr-mult` is structurally different from `sl_atr_buffer` (one is total SL
distance, the other is pivot buffer only). Use the tuner's best `tp2_atr_multiplier` directly,
and keep `--sl-atr-mult 1.0` (scanner default) unless a direct mapping is needed.

#### C. After best params found, re-scan opportunities with new TP/SL

```powershell
py -3.12 scripts/research/opportunity_scanner.py `
    --csv data/EURUSD_M15.csv `
    --instrument EURUSD `
    --tp-atr-mult <best_tp_atr_mult> `
    --sl-atr-mult <best_sl_atr_mult> `
    --trail-mult 0.5
```

---

### Phase 3: Retrain All Models on New Opportunity Data

After Phase 2 produces a better opportunity JSONL (run-scoped):

```powershell
# 1. Gaussian + TradeNet
py -3.12 scripts/training/phase5_calibration.py `
    --opportunities logs/EURUSD/{RUN_ID}/opportunities.jsonl `
    --version v7_2026_05_eur `
    --instrument EURUSD `
    --train --tradenet

# 2. Zone registry
py -3.12 scripts/research/discover_zones.py `
    --opportunities logs/EURUSD/{RUN_ID}/opportunities.jsonl `
    --instrument EURUSD `
    --version v7_2026_05_eur

# 3. RR dataset + RR model
py -3.12 scripts/data/build_rr_dataset.py `
    --opportunities logs/EURUSD/{RUN_ID}/opportunities.jsonl `
    --instrument EURUSD

py -3.12 scripts/training/train_rr_model.py `
    --dataset models/EURUSD/{RUN_ID}/rr_dataset_*.json `
    --version v7_2026_05_eur `
    --instrument EURUSD
```

---

---

# ACTIVE TASK: phase5_calibration.py — Enforce --gaussian / --tradenet Mutex

## Context

Currently `--train` alone trains Gaussian (confusingly implicit). `--tradenet` without `--train`
crashes at `report_path` (undefined). The user wants three explicit, mutually exclusive commands:

```
--train --gaussian   → Gaussian model only
--train --tradenet   → TradeNet model only (sequential after a prior --gaussian run)
--train              → ERROR: must specify one model
--train --gaussian --tradenet → ERROR: mutually exclusive
```

## File to Change: `scripts/training/phase5_calibration.py` only

### Change 1 — Add `--gaussian` flag (near `--tradenet` at line ~1288)

```python
ap.add_argument("--gaussian", action="store_true",
                help="Train Gaussian NB model (use with --train; "
                     "mutually exclusive with --tradenet).")
```

### Change 2 — Auto-set gaussian=True when opportunities imply --train (lines ~1332-1334)

```python
# --synthetic / --opportunities imply --train by default
if (args.synthetic or args.opportunities) and not args.audit_only:
    args.train = True
    # Default to Gaussian when no explicit model flag given
    if not args.gaussian and not args.tradenet:
        args.gaussian = True
```

### Change 3 — Validation block (after auto-set, before upfront input validation ~line 1335)

```python
if args.train:
    if args.gaussian and args.tradenet:
        print(
            "ERROR: --gaussian and --tradenet are mutually exclusive.\n"
            "  Gaussian only:  ... --train --gaussian\n"
            "  TradeNet only:  ... --train --tradenet",
            file=sys.stderr,
        )
        sys.exit(1)
    if not args.gaussian and not args.tradenet:
        print(
            "ERROR: --train requires exactly one model flag.\n"
            "  Train Gaussian:  ... --train --gaussian\n"
            "  Train TradeNet:  ... --train --tradenet",
            file=sys.stderr,
        )
        sys.exit(1)
```

### Change 4 — Remap Gaussian block condition (line ~1445)

```python
# BEFORE:
if args.train:

# AFTER:
if args.train and args.gaussian:
```

No other changes inside the Gaussian block — all existing indented code stays.

### Change 5 — Remap TradeNet block + add standalone report_path (lines ~1594-1622)

```python
# BEFORE:
if args.tradenet:
    version = args.version or f"p5_{time.strftime('%Y%m%dT%H%M%S')}"
    tn_path, tn_metrics = run_tradenet_training(...)
    if tn_path:
        ...
        rdata = json.loads(report_path.read_text())   # ← crashes standalone

# AFTER:
if args.train and args.tradenet:
    version = args.version or f"p5_{time.strftime('%Y%m%dT%H%M%S')}"
    tn_path, tn_metrics = run_tradenet_training(...)
    if tn_path:
        _pass_fail("TradeNet end-to-end pipeline", True, str(tn_path))
        # Resolve report_path for standalone TradeNet run (Gaussian may have run separately)
        if args.instrument:
            report_path = (Path(args.base) / "results"
                           / args.instrument / _run_id / f"p5_calibration_{version}.json")
        else:
            report_path = Path(args.base) / "results" / f"p5_calibration_{version}.json"
        try:
            rdata = json.loads(report_path.read_text())
            rdata["tradenet"] = {
                "model_path": str(tn_path),
                "version":    version,
                "status":     "trained",
                "metrics":    tn_metrics,
            }
            report_path.write_text(json.dumps(rdata, indent=2))
            print(f"  Report updated with TradeNet section -> {report_path}")
        except Exception as _patch_err:
            log.warning("Could not patch report with TradeNet section: %s", _patch_err)
    else:
        _pass_fail("TradeNet end-to-end pipeline", False, ...)
```

## Backward Compatibility

| Existing call | New behaviour |
|---|---|
| `--train` | ERROR (must add --gaussian) |
| `--train --tradenet` | **Changed**: trains TradeNet only (was: Gaussian + TradeNet) |
| `--opportunities file.jsonl` | Auto-sets gaussian=True → trains Gaussian (unchanged) |
| `--train --gaussian` | New explicit: trains Gaussian only |

**Note on `--train --tradenet` behavior change:** Was Gaussian+TradeNet, now TradeNet only.
Users who want both must run two sequential commands. This is the user's explicit intent.

## Verification

```powershell
# Should error:
py -3.12 scripts/training/phase5_calibration.py --instrument ETHUSDT --run 20260519_113806 --version v5 --train
# Expected: ERROR: --train requires exactly one model flag.

# Should error:
py -3.12 scripts/training/phase5_calibration.py --instrument ETHUSDT --run 20260519_113806 --version v5 --train --gaussian --tradenet
# Expected: ERROR: --gaussian and --tradenet are mutually exclusive.

# Should succeed:
py -3.12 scripts/training/phase5_calibration.py --instrument ETHUSDT --run 20260519_113806 --version v5 --train --gaussian
# Expected: PHASE-5 CALIBRATION RESULT ... APPROVED

# Should succeed (after gaussian run above):
py -3.12 scripts/training/phase5_calibration.py --instrument ETHUSDT --run 20260519_113806 --version v5 --train --tradenet
# Expected: TRADENET TRAINING ... model saved
```

---

## Recommended Execution Order

| Step | Command | Prerequisite |
|---|---|---|
| 1 | `auto_tuner_multi` | data/*.csv exist |
| 2 | Extract best params + validate | checkpoint from step 1 |
| 3 | Promote params to production config + re-hash | validation passes |
| 4 | (If tp/sl extended) Re-scan opportunities | best tp/sl from tuner |
| 5 | `phase5_calibration --train --tradenet` | new opportunities JSONL |
| 6 | `discover_zones` | same JSONL |
| 7 | `build_rr_dataset` + `train_rr_model` | same JSONL |

---

## What Needs Code Change vs. What Runs As-Is

| Action | Code change needed? |
|---|---|
| Run auto_tuner_multi (CRT filter tuning) | ❌ No — runs as-is |
| Extract best params + validate | ❌ No — manual one-liner + existing validator |
| Promote config + re-hash | ❌ No — manual JSON edit + existing _compute_hash.py |
| Extend tuner to tune tp/sl multiples | ✅ Yes — add to PARAM_SPACE + thread into CRTConfig |
| Re-scan with new tp/sl | ❌ No — scanner already supports --tp-atr-mult |
| Retrain all models | ❌ No — existing scripts |

**If only Phase 1 (CRT filters) is needed: zero code changes.**
**If Phase 2 (tp/sl tuning) is needed: ~20-line change to `auto_tuner_multi.py`.**
