"""
replay_drift_governor.py
========================
Monitors replay memory for contamination, staleness, cluster drift,
and anti-collapse signals.

Anti-collapse design:
  Replay memory can create a self-reinforcing feedback loop where the system
  learns "sweeps fail" → takes fewer trades → dataset shifts → model overfits
  fear → collapse into defensive paralysis. This governor detects the signals
  that precede collapse. Callers decide whether to proceed; the governor
  NEVER hard-rejects.

Checks performed by audit():
    1. Cluster entropy drift   — is one cluster dominating all replay?
    2. Sample concentration    — > threshold fraction in one cluster?
    3. Staleness ratio         — majority of records older than threshold?
    4. Mean-RR extremes        — historical mean RR beyond plausible range?
    5. Outcome contamination   — SL_HIT > threshold fraction?
    6. Anti-collapse: outcome entropy floor
                               — Shannon entropy of outcome dist < 0.30?
                                 (one outcome dominates → exploration collapse risk)
    7. Novelty score           — < 10% of records in mid-range RR [0.2, 1.8]?
                                 (system only sees catastrophic or perfect trades)

Each check sets an alert string in DriftReport.alerts.
DriftReport.clean is True only when zero alerts fire.

Each audit() call writes a DRIFT_AUDIT event to logs/drift_audit.jsonl via
the canonical event fabric.

Usage:
    gov = ReplayDriftGovernor()
    report = gov.audit(replay_memory_engine_instance)
    if not report.clean:
        for alert in report.alerts:
            log.warning("Drift alert: %s", alert)
    if report.exploration_deficit:
        log.error("Anti-collapse: outcome entropy below floor — review training data")
"""
from __future__ import annotations

import json
import logging
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from utils.logging_config import get_flow_logger

logger = get_flow_logger("REPLAY_DRIFT_GOVERNOR")

_DRIFT_AUDIT_LOG = Path("logs/drift_audit.jsonl")

# Anti-collapse thresholds
_OUTCOME_ENTROPY_FLOOR = 0.30    # normalized Shannon entropy; below = collapse risk
_NOVELTY_SCORE_FLOOR   = 0.10   # fraction of mid-range RR records [0.2, 1.8]


@dataclass
class DriftReport:
    """Full drift audit result."""
    clean:               bool
    alerts:              List[str] = field(default_factory=list)
    cluster_entropy:     float = 1.0    # normalised Shannon entropy of cluster dist
    mean_rr_drift:       float = 0.0   # abs(mean_rr) — high = potentially biased data
    staleness_ratio:     float = 0.0   # fraction of records older than threshold
    concentration_ratio: float = 0.0   # fraction of records in the dominant cluster
    contamination_score: float = 0.0   # [0,1] SL contamination severity

    # Anti-collapse fields
    outcome_entropy:     float = 1.0   # normalised Shannon entropy of outcome dist
    exploration_deficit: bool  = False  # True when outcome_entropy < floor
    novelty_score:       float = 1.0   # fraction of rr_achieved in mid-range [0.2,1.8]


class ReplayDriftGovernor:
    """
    Drift detection and memory quality monitoring.

    Parameters
    ----------
    max_staleness_days       : float — threshold for "stale" record (default 60 days)
    staleness_pct_threshold  : float — alert when stale fraction > this (default 0.70)
    concentration_threshold  : float — alert when max cluster fraction > this (default 0.80)
    contamination_threshold  : float — alert when SL_HIT fraction > this (default 0.90)
    """

    def __init__(
        self,
        max_staleness_days:      float = 60.0,
        staleness_pct_threshold: float = 0.70,
        concentration_threshold: float = 0.80,
        contamination_threshold: float = 0.90,
    ) -> None:
        self._max_staleness  = max_staleness_days
        self._stale_thresh   = staleness_pct_threshold
        self._conc_thresh    = concentration_threshold
        self._contam_thresh  = contamination_threshold

    def audit(self, replay_engine: object) -> DriftReport:
        """
        Audit a ReplayMemoryEngine instance and return a DriftReport.

        Also writes a DRIFT_AUDIT event to logs/drift_audit.jsonl.

        Parameters
        ----------
        replay_engine : ReplayMemoryEngine (already loaded, or will be empty-safe)

        Returns
        -------
        DriftReport — always valid, never raises.
        """
        try:
            return self._audit_inner(replay_engine)
        except Exception as exc:
            logger.warning("ReplayDriftGovernor.audit() failed (fail-open): %s", exc)
            return DriftReport(clean=True, alerts=["audit_error"])

    # ── Private ───────────────────────────────────────────────────────────────

    def _audit_inner(self, replay_engine: object) -> DriftReport:
        records       = getattr(replay_engine, "_records",       [])
        cluster_stats = getattr(replay_engine, "_cluster_stats", {})

        # Empty memory — not an error, just note it
        if not records:
            report = DriftReport(clean=True, alerts=["empty_replay_memory"])
            self._write_audit_event(report, n_records=0, n_clusters=0)
            return report

        alerts: List[str] = []
        n = len(records)

        # ── 1. Cluster entropy ─────────────────────────────────────────────────
        cluster_counts: dict[int, int] = {}
        for rec in records:
            cid = rec.cluster_id
            cluster_counts[cid] = cluster_counts.get(cid, 0) + 1

        k = len(cluster_counts)
        entropy = 0.0
        for count in cluster_counts.values():
            p = count / n
            if p > 0:
                entropy -= p * math.log2(p + 1e-12)
        max_entropy = math.log2(max(k, 2))
        norm_cluster_entropy = entropy / max_entropy if max_entropy > 0 else 0.0

        if norm_cluster_entropy < 0.20:
            alerts.append(f"low_cluster_entropy={norm_cluster_entropy:.3f}")

        # ── 2. Concentration ───────────────────────────────────────────────────
        max_count = max(cluster_counts.values()) if cluster_counts else 0
        concentration = max_count / n
        if concentration > self._conc_thresh:
            alerts.append(f"cluster_concentration={concentration:.3f}")

        # ── 3. Staleness ───────────────────────────────────────────────────────
        stale_count   = sum(1 for r in records if r.age_days > self._max_staleness)
        staleness_ratio = stale_count / n
        if staleness_ratio > self._stale_thresh:
            alerts.append(f"high_staleness={staleness_ratio:.3f}")

        # ── 4. Mean RR drift ───────────────────────────────────────────────────
        rr_vals  = [r.rr_achieved for r in records]
        mean_rr  = sum(rr_vals) / n
        mean_rr_drift = abs(mean_rr)
        if mean_rr > 1.8 or mean_rr < -1.5:
            alerts.append(f"extreme_mean_rr={mean_rr:.3f}")

        # ── 5. Outcome contamination ───────────────────────────────────────────
        sl_hits    = sum(1 for r in records if r.outcome == "SL_HIT")
        sl_ratio   = sl_hits / n
        if sl_ratio > self._contam_thresh:
            alerts.append(f"outcome_contamination_sl={sl_ratio:.3f}")
        # Severity score: 0 below 70% SL rate, 1.0 at 100%
        contamination_score = max(0.0, (sl_ratio - 0.70) / 0.30)

        # ── 6. Anti-collapse: outcome entropy floor ────────────────────────────
        # Shannon entropy over SL_HIT / TP_HIT / TIMEOUT.
        # Low entropy → one outcome dominates → system may be training itself
        # to fear a single failure mode → exploration collapse.
        outcome_counts: dict[str, int] = {"SL_HIT": 0, "TP_HIT": 0, "TIMEOUT": 0}
        for rec in records:
            key = rec.outcome if rec.outcome in outcome_counts else "TIMEOUT"
            outcome_counts[key] += 1

        outcome_entropy_raw = 0.0
        for count in outcome_counts.values():
            p = count / n
            if p > 0:
                outcome_entropy_raw -= p * math.log2(p + 1e-12)
        max_outcome_entropy = math.log2(3)   # 3 possible outcomes
        norm_outcome_entropy = (
            outcome_entropy_raw / max_outcome_entropy
            if max_outcome_entropy > 0 else 0.0
        )

        exploration_deficit = False
        if norm_outcome_entropy < _OUTCOME_ENTROPY_FLOOR:
            alerts.append(f"outcome_entropy_collapse={norm_outcome_entropy:.3f}")
            exploration_deficit = True

        # ── 7. Novelty score: mid-range RR representation ─────────────────────
        # Low fraction of intermediate outcomes → system biased toward extremes.
        mid_range    = sum(1 for r in records if 0.2 <= r.rr_achieved <= 1.8)
        novelty_score = mid_range / n
        if novelty_score < _NOVELTY_SCORE_FLOOR:
            alerts.append(f"low_novelty_score={novelty_score:.3f}")

        clean = len(alerts) == 0

        if not clean:
            logger.warning(
                "ReplayDrift: %d alert(s) — %s", len(alerts), alerts
            )
        else:
            logger.info(
                "ReplayDrift: clean audit (%d records, %d clusters)",
                n, k,
            )

        report = DriftReport(
            clean               = clean,
            alerts              = alerts,
            cluster_entropy     = round(norm_cluster_entropy, 4),
            mean_rr_drift       = round(mean_rr_drift, 4),
            staleness_ratio     = round(staleness_ratio, 4),
            concentration_ratio = round(concentration, 4),
            contamination_score = round(contamination_score, 4),
            outcome_entropy     = round(norm_outcome_entropy, 4),
            exploration_deficit = exploration_deficit,
            novelty_score       = round(novelty_score, 4),
        )

        self._write_audit_event(report, n_records=n, n_clusters=k)
        return report

    def _write_audit_event(
        self,
        report: DriftReport,
        n_records: int,
        n_clusters: int,
    ) -> None:
        """Write DRIFT_AUDIT event to logs/drift_audit.jsonl (fail-open)."""
        try:
            try:
                from events.event_fabric import make_event_envelope  # noqa: PLC0415
                record = make_event_envelope(
                    event_type="DRIFT_AUDIT",
                    instrument="",
                    source="ReplayDriftGovernor",
                    payload={
                        "clean":               report.clean,
                        "alerts":              report.alerts,
                        "n_records":           n_records,
                        "n_clusters":          n_clusters,
                        "cluster_entropy":     report.cluster_entropy,
                        "mean_rr_drift":       report.mean_rr_drift,
                        "staleness_ratio":     report.staleness_ratio,
                        "concentration_ratio": report.concentration_ratio,
                        "contamination_score": report.contamination_score,
                        "outcome_entropy":     report.outcome_entropy,
                        "exploration_deficit": report.exploration_deficit,
                        "novelty_score":       report.novelty_score,
                    },
                )
            except Exception:
                # Fallback: plain record without generation counter
                record = {
                    "event_type": "DRIFT_AUDIT",
                    "source":     "ReplayDriftGovernor",
                    "timestamp":  time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "payload": {
                        "clean":   report.clean,
                        "alerts":  report.alerts,
                        "n_records": n_records,
                    },
                }

            _DRIFT_AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
            with _DRIFT_AUDIT_LOG.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record) + "\n")

        except Exception as exc:
            logger.debug(
                "ReplayDriftGovernor: drift_audit.jsonl write failed "
                "(non-blocking): %s", exc,
            )
