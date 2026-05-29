"""
cognitive_bus.py
================
Asynchronous cognitive processing bus.

Consumes DecisionSnapshot events emitted by EngineRunner and routes them
through the full cognitive pipeline:
    ReplayMemoryEngine → MarketStateClusterEngine → TradeNetMetaEngine
    → HierarchicalMetaFusion → logs/cognitive_telemetry.jsonl

HARD RULES:
    1. This module NEVER touches EngineRunner.run() internals.
    2. This module NEVER returns anything to the execution plane.
    3. All output is write-only telemetry (logs/cognitive_telemetry.jsonl).
    4. The "cognitive" key is NOT in the EngineRunner return dict.

Thread model:
    Single background daemon thread. queue.maxsize=500.
    emit() is non-blocking — drops silently when queue is full.
    Drop telemetry: _total_emitted and _dropped_events counters.
    WARNING logged when drop_rate exceeds _BACKPRESSURE_ALERT_THRESHOLD (5%).

Fail-open:
    Any exception inside _process() is caught, logged at WARNING, and skipped.
    Engine init failures are retried on next event (up to 3 failures, then disabled).
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

_TELEMETRY_PATH              = Path("logs/cognitive_telemetry.jsonl")
_REPLAY_QUERY_PATH           = Path("logs/replay_queries.jsonl")  # M2 — monitoring-only
_QUEUE_MAXSIZE               = 500    # hard cap; oldest events dropped silently if full
_BACKPRESSURE_ALERT_THRESHOLD = 0.05  # 5% drop rate → WARNING log
_MAX_ENGINE_INIT_FAILURES    = 3      # after this many failures, stop retrying


@dataclass
class DecisionSnapshot:
    """
    Immutable snapshot of one EngineRunner decision cycle.

    Carries event_id, generation, and schema_hash from the canonical event
    fabric so that COGNITIVE_TELEMETRY events can be linked back to their
    parent DECISION_SNAPSHOT via parent_event_id.
    """
    decision_id:     str
    event_id:        str    # canonical event ID from make_event_envelope()
    generation:      int    # generation counter value at emission time
    timestamp:       str
    instrument:      str
    schema_hash:     str    # FEATURE_ORDER_HASH at emission time
    features:        dict   = field(default_factory=dict)
    zone_result:     dict   = field(default_factory=dict)
    gaussian_result: dict   = field(default_factory=dict)
    rr_result:       dict   = field(default_factory=dict)
    fusion_result:   dict   = field(default_factory=dict)
    decision:        str    = ""
    cluster_id:      int    = -1


class CognitiveBus:
    """
    Background daemon that processes DecisionSnapshot events asynchronously.

    Parameters
    ----------
    config : dict
        Production config dict. Reads the "cognitive_layer" sub-section.
    """

    def __init__(self, config: dict) -> None:
        self._cfg = config.get("cognitive_layer", {})
        self._q: queue.Queue = queue.Queue(maxsize=_QUEUE_MAXSIZE)
        self._thread: Optional[threading.Thread] = None
        self._running = False

        # Drop telemetry counters
        self._total_emitted:    int = 0
        self._dropped_events:   int = 0

        # Engine init tracking
        self._engine_init_failures: int = 0
        self._engines_ready: bool = False

        # Lazy-init cognitive engines (initialised on first event, not at startup)
        self._replay_memory  = None
        self._market_state   = None
        self._tradenet_meta  = None
        self._hmf            = None

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the background daemon thread. Safe to call multiple times."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._consume_loop,
            name="CognitiveBus",
            daemon=True,
        )
        self._thread.start()
        logger.info("CognitiveBus: started (daemon thread, queue_maxsize=%d)", _QUEUE_MAXSIZE)

    def stop(self) -> None:
        """Signal the consumer loop to exit cleanly."""
        self._running = False
        # Enqueue a sentinel to unblock the blocking get()
        try:
            self._q.put_nowait(None)
        except queue.Full:
            pass

    def emit(self, snapshot: DecisionSnapshot) -> None:
        """
        Enqueue a DecisionSnapshot for async cognitive processing.

        Non-blocking: if the queue is full, the snapshot is dropped and
        _dropped_events is incremented. A WARNING is logged when the drop
        rate exceeds _BACKPRESSURE_ALERT_THRESHOLD.

        NEVER call this from inside a latency-critical path except as the
        very last fire-and-forget statement before return.
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
                    "consider reducing cognitive load or increasing queue size.",
                    drop_rate * 100,
                    self._dropped_events,
                    self._total_emitted,
                    self._q.qsize(),
                )
            else:
                logger.debug(
                    "CognitiveBus: snapshot dropped (queue full) drop_rate=%.2f%%",
                    drop_rate * 100,
                )

    def health(self) -> dict:
        """
        Return queue health snapshot for external monitoring.

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
        """Consumer thread: blocks on queue, processes each snapshot."""
        while self._running:
            try:
                snapshot = self._q.get(timeout=1.0)
                if snapshot is None:    # stop sentinel
                    break
                self._process(snapshot)
            except queue.Empty:
                continue
            except Exception as exc:
                logger.warning(
                    "CognitiveBus: consume_loop unhandled error (non-blocking): %s", exc
                )

    def _ensure_engines(self) -> bool:
        """
        Lazy-init all cognitive engines on first event.

        Returns True if all engines are ready, False on failure.
        Tracks failure count; disables retries after _MAX_ENGINE_INIT_FAILURES.
        """
        if self._engines_ready:
            return True
        if self._engine_init_failures >= _MAX_ENGINE_INIT_FAILURES:
            return False

        try:
            from replay.replay_memory_engine import ReplayMemoryEngine    # noqa
            from regime.market_state_cluster_engine import (               # noqa
                MarketStateClusterEngine,
            )
            from engines.tradenet_meta_engine import TradeNetMetaEngine    # noqa
            from core.hierarchical_meta_fusion import HierarchicalMetaFusion  # noqa

            opps_dir = str(self._cfg.get("opportunities_dir",    "logs"))
            zone_reg = str(self._cfg.get("zone_registry_path",   "models/zone_registry.json"))

            self._replay_memory = ReplayMemoryEngine(
                opportunities_dir  = opps_dir,
                zone_registry_path = zone_reg,
                max_records        = int(self._cfg.get("max_replay_records",  50_000)),
                decay_half_life_days = float(self._cfg.get("decay_half_life_days", 30.0)),
                min_cluster_samples  = int(self._cfg.get("min_cluster_samples",    5)),
                staleness_threshold_days = float(
                    self._cfg.get("staleness_threshold_days", 90.0)
                ),
            )
            self._market_state = MarketStateClusterEngine(
                min_cluster_samples = int(self._cfg.get("min_cluster_samples", 5)),
            )
            self._tradenet_meta = TradeNetMetaEngine({}, preload=False)
            self._hmf = HierarchicalMetaFusion(
                allow_threshold  = float(self._cfg.get("hmf_allow_threshold",  0.60)),
                reduce_threshold = float(self._cfg.get("hmf_reduce_threshold", 0.45)),
            )

            self._engines_ready = True
            logger.info("CognitiveBus: all cognitive engines initialised")
            return True

        except Exception as exc:
            self._engine_init_failures += 1
            logger.warning(
                "CognitiveBus: engine init failed (%d/%d) — %s",
                self._engine_init_failures, _MAX_ENGINE_INIT_FAILURES, exc,
            )
            return False

    def _emit_replay_query(self, snap: DecisionSnapshot, replay_r: dict) -> None:
        """M2 dual-write: emit the replay-memory lookup as a REPLAY_QUERY envelope to
        logs/replay_queries.jsonl. Monitoring-only (async thread → non-replay-comparable);
        observation only, never feeds a decision. Fail-open: errors are swallowed."""
        try:
            from events.event_fabric import make_event_envelope, EventType  # noqa
            env = make_event_envelope(
                event_type      = EventType.REPLAY_QUERY.value,
                instrument      = snap.instrument,
                source          = "CognitiveBus",
                payload         = {
                    "decision_id":         snap.decision_id,
                    "cluster_id":          snap.cluster_id,
                    "similarity_score":    replay_r.get("similarity_score"),
                    "historical_winrate":  replay_r.get("historical_winrate"),
                    "cluster_stability":   replay_r.get("cluster_stability"),
                    "sample_size":         replay_r.get("sample_size"),
                },
                parent_event_id = snap.event_id,
            )
            _REPLAY_QUERY_PATH.parent.mkdir(parents=True, exist_ok=True)
            with _REPLAY_QUERY_PATH.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(env) + "\n")
        except Exception:  # noqa: BLE001
            pass

    def _process(self, snap: DecisionSnapshot) -> None:
        """
        Process one snapshot through the full cognitive pipeline.
        All exceptions are caught (non-blocking).
        """
        if not self._ensure_engines():
            return

        try:
            t0 = time.monotonic()

            # ── Replay memory query ───────────────────────────────────────────
            # Use first 35 features (execution-plane model dimension) for cluster lookup
            feature_vals = list(snap.features.values())[:35]
            replay_r     = self._replay_memory.query(
                feature_vector=feature_vals,
                cluster_id=snap.cluster_id,
            )
            # M2 — REPLAY_QUERY event. Emitted from the CognitiveBus worker thread, so it
            # is MONITORING-ONLY and NOT replay-comparable (async emission order is not
            # deterministic, like generation/wall-clock timestamp). Never feeds a decision.
            self._emit_replay_query(snap, replay_r)
            replay_feats  = self._replay_memory.get_replay_features(snap.cluster_id)
            cluster_stats = self._replay_memory._cluster_stats.get(snap.cluster_id)

            # ── Market state classification ───────────────────────────────────
            ms_output = self._market_state.classify(
                features      = snap.features,
                cluster_stats = cluster_stats,
                replay_features = replay_feats,
            )

            # ── TradeNet meta cognition ───────────────────────────────────────
            tn_result = self._tradenet_meta.compute(
                features             = snap.features,
                gaussian_result      = snap.gaussian_result,
                rr_result            = snap.rr_result,
                zone_result          = snap.zone_result,
                replay_result        = replay_r,
                market_state_result  = ms_output,
            )

            # ── Hierarchical meta fusion ──────────────────────────────────────
            hmf_result = self._hmf.compute(
                features             = snap.features,
                zone_result          = snap.zone_result,
                rr_result            = snap.rr_result,
                replay_result        = replay_r,
                market_state_result  = ms_output,
                tradenet_meta_result = tn_result,
            )

            latency_ms = round((time.monotonic() - t0) * 1000.0, 2)

            # ── Write cognitive telemetry (COGNITIVE_TELEMETRY event) ─────────
            try:
                from events.event_fabric import make_event_envelope, EventType  # noqa
                record = make_event_envelope(
                    event_type      = EventType.COGNITIVE_TELEMETRY,
                    instrument      = snap.instrument,
                    source          = "CognitiveBus",
                    payload         = {
                        "decision_id":   snap.decision_id,
                        "core_decision": snap.decision,
                        "replay":        replay_r,
                        "market_state":  (
                            ms_output.__dict__
                            if hasattr(ms_output, "__dict__") else {}
                        ),
                        "tradenet_meta": tn_result,
                        "hmf":           hmf_result.to_dict(),
                        "latency_ms":    latency_ms,
                    },
                    parent_event_id = snap.event_id,   # causal link back to snapshot
                )
            except Exception:
                # Fallback envelope without generation counter
                record = {
                    "event_type":    "COGNITIVE_TELEMETRY",
                    "source":        "CognitiveBus",
                    "instrument":    snap.instrument,
                    "timestamp":     time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "decision_id":   snap.decision_id,
                    "core_decision": snap.decision,
                    "replay":        replay_r,
                    "market_state":  (
                        ms_output.__dict__
                        if hasattr(ms_output, "__dict__") else {}
                    ),
                    "tradenet_meta": tn_result,
                    "hmf":           hmf_result.to_dict(),
                    "latency_ms":    latency_ms,
                }

            _TELEMETRY_PATH.parent.mkdir(parents=True, exist_ok=True)
            with _TELEMETRY_PATH.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record) + "\n")

        except Exception as exc:
            logger.warning(
                "CognitiveBus._process() failed (non-blocking): %s", exc
            )
