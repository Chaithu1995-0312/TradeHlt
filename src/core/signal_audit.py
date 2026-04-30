"""
core/signal_audit.py — Per-bar Signal Audit + Leak Detection

Records one structured JSON-lines record per bar to logs/signal_audit.jsonl.
Exposes leak-rate warnings after a session run.

Usage (in EngineRunner):
    recorder = SignalAuditRecorder(debug_mode=config.get("debug_mode", False))
    recorder.start_bar(bar_id, timestamp, price)
    recorder.record_zone(zone_raw)
    recorder.record_engines(engine_results)
    recorder.record_fusion(fusion_result)
    recorder.record_risk(risk_result)         # optional — call if available
    recorder.finalize(decision, reason)
    recorder.flush()

Invariants:
  - All methods are no-ops when debug_mode=False (zero overhead).
  - flush() never raises — OSError is caught and logged to COLLECTOR.
  - One JSON record is written per bar, in append mode.
  - force_pass_override=True records must be filtered before training ingestion.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

_COLLECTOR_LOG = logging.getLogger("COLLECTOR")

# Leak detection thresholds
_ZONE_PASS_WARN   = 0.80
_FUSION_PASS_WARN = 0.50
_TRADE_RATE_WARN  = 0.30

DEFAULT_LOG_PATH = "logs/signal_audit.jsonl"


class SignalAuditRecorder:
    """
    Per-bar audit recorder. Appends one JSON line per bar to a JSONL file.
    All public methods are no-ops when debug_mode=False.
    """

    def __init__(
        self,
        debug_mode: bool = True,
        log_path: str = DEFAULT_LOG_PATH,
    ) -> None:
        self.debug_mode = debug_mode
        self.log_path   = log_path

        # Per-bar accumulator (reset by start_bar)
        self._current: dict[str, Any] = {}

        # Session-lifetime counters
        self._total_bars:    int = 0
        self._zone_passes:   int = 0
        self._fusion_passes: int = 0
        self._trade_count:   int = 0
        self._flush_errors:  int = 0

    # ------------------------------------------------------------------
    # Lifecycle methods
    # ------------------------------------------------------------------

    def start_bar(self, bar_id: str, timestamp: str, price: float) -> None:
        if not self.debug_mode:
            return
        self._current = {
            "bar_id":    str(bar_id),
            "timestamp": str(timestamp),
            "price":     float(price),
            "zone":      {},
            "engines":   {},
            "fusion":    {},
            "risk":      {},
            "decision":  None,
            "reason":    None,
            "force_pass_override": False,
        }

    def record_zone(self, zone_result: dict) -> None:
        if not self.debug_mode:
            return
        safe = zone_result or {}
        self._current["zone"] = {
            "passed":              bool(safe.get("passed", False)),
            "score":               float(safe.get("score", 0.0)),
            "reason":              str(safe.get("reason", "")),
            "force_pass_override": bool(safe.get("force_pass_override", False)),
            "real_passed":         safe.get("real_passed"),
        }
        self._current["force_pass_override"] = bool(safe.get("force_pass_override", False))
        if safe.get("passed"):
            self._zone_passes += 1

    def record_engines(self, engine_results: dict) -> None:
        if not self.debug_mode:
            return
        safe = engine_results or {}
        self._current["engines"] = {
            name: {"score": float((result or {}).get("score", 0.0))}
            for name, result in safe.items()
        }

    def record_fusion(self, fusion_result: dict) -> None:
        if not self.debug_mode:
            return
        safe = fusion_result or {}
        self._current["fusion"] = {
            "final_score": float(safe.get("final_score", 0.0)),
            "variance":    safe.get("variance"),
            "entropy":     safe.get("entropy"),
            "threshold":   safe.get("threshold"),
            "accepted":    safe.get("accepted"),
        }
        if float(safe.get("final_score", 0.0)) >= 0.5:
            self._fusion_passes += 1

    def record_risk(self, risk_result: dict) -> None:
        if not self.debug_mode:
            return
        safe = risk_result or {}
        self._current["risk"] = {
            "decision":    str(safe.get("decision", "")),
            "risk_reason": str(safe.get("risk_reason", "")),
        }

    def finalize(self, decision: str, reason: str) -> None:
        if not self.debug_mode:
            return
        self._current["decision"] = str(decision)
        self._current["reason"]   = str(reason)
        self._total_bars += 1
        if str(decision).lower() in ("execute", "approve"):
            self._trade_count += 1

    def flush(self) -> None:
        """Append current bar record to the JSONL file. Never raises."""
        if not self.debug_mode:
            return
        if not self._current:
            return
        try:
            os.makedirs(os.path.dirname(self.log_path) if os.path.dirname(self.log_path) else ".", exist_ok=True)
            with open(self.log_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(self._current) + "\n")
        except OSError as exc:
            self._flush_errors += 1
            _COLLECTOR_LOG.warning(
                "signal_audit flush failed (error #%d): %s | record=%s",
                self._flush_errors,
                exc,
                json.dumps(self._current),
            )
        finally:
            self._current = {}

    # ------------------------------------------------------------------
    # Leak detection
    # ------------------------------------------------------------------

    def check_leak_rates(self) -> list[str]:
        """
        Compute session-wide pass/trade rates and return warning strings
        for any rate that exceeds its threshold. Call at end of session.
        """
        if not self.debug_mode or self._total_bars == 0:
            return []

        warnings: list[str] = []
        n = self._total_bars

        zone_rate   = self._zone_passes   / n
        fusion_rate = self._fusion_passes / n
        trade_rate  = self._trade_count   / n

        if zone_rate > _ZONE_PASS_WARN:
            warnings.append(
                f"LEAK: zone passing {zone_rate:.1%} of bars "
                f"(threshold {_ZONE_PASS_WARN:.0%}) — check ZoneGateEngine thresholds"
            )
        if fusion_rate > _FUSION_PASS_WARN:
            warnings.append(
                f"LEAK: fusion passing {fusion_rate:.1%} of bars "
                f"(threshold {_FUSION_PASS_WARN:.0%}) — check FusionEngine calibration"
            )
        if trade_rate > _TRADE_RATE_WARN:
            warnings.append(
                f"LEAK: trade rate {trade_rate:.1%} of bars "
                f"(threshold {_TRADE_RATE_WARN:.0%}) — acceptance rate too high"
            )

        if self._flush_errors > 0:
            warnings.append(
                f"AUDIT: {self._flush_errors} flush error(s) — check disk space / permissions on {self.log_path}"
            )

        return warnings

    # ------------------------------------------------------------------
    # Session summary
    # ------------------------------------------------------------------

    def summary(self) -> dict:
        """Return session counters as a plain dict."""
        n = max(self._total_bars, 1)
        return {
            "total_bars":    self._total_bars,
            "zone_passes":   self._zone_passes,
            "fusion_passes": self._fusion_passes,
            "trade_count":   self._trade_count,
            "zone_pass_rate":   round(self._zone_passes   / n, 4),
            "fusion_pass_rate": round(self._fusion_passes / n, 4),
            "trade_rate":       round(self._trade_count   / n, 4),
            "flush_errors":  self._flush_errors,
        }
