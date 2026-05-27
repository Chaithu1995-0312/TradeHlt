"""
training_trigger.py
===================
Programmatic gate for invoking the auto-train pipeline.

Lets in-process consumers (backtest completion hook, live engine drift
detector, agent tool, etc.) ask "should we retrain now?" without spawning
``scripts/auto_train_from_opportunities.py`` on a blind clock.

Three independent gates, ALL must be open for ``should_trigger()`` to
return True:

  - ``_has_enough_samples(n_min)``
      New opportunity records since the last fire exceed ``n_min``.
  - ``_drift_gate_open()``
      Recent activity in ``logs/integrity_events.jsonl`` matching the
      configured drift kinds exceeds the threshold within the window.
  - ``_cooldown_elapsed(hours)``
      Wall-clock cooldown since the last fire. First-run case opens.

Marker file (default: ``results/training_trigger.json``) persists state
across restarts: ``{"last_fired_ts": ..., "last_sample_count": ...}``.

Configuration
-------------
Read from ``get_prod_section("training_trigger")``. All keys have sensible
defaults so an absent section doesn't break the class. Recommended
production block::

    "training_trigger": {
        "min_new_samples":       500,
        "drift_window_hours":    24,
        "drift_event_threshold": 5,
        "cooldown_hours":        6,
        "marker_path":           "results/training_trigger.json",
        "opportunity_glob":      "logs/**/opportunities.jsonl",
        "integrity_log":         "logs/integrity_events.jsonl",
        "drift_event_kinds":     ["RR_BYPASS", "RR_LLM_FALLBACK",
                                  "PROMOTION_FAILED"]
    }

Public API
----------
    trigger = TrainingTrigger.from_prod_config()
    if trigger.should_trigger():
        # caller invokes the orchestrator however they want (subprocess,
        # in-process import, agent tool, etc.)
        trigger.mark_fired()

Design notes
------------
- No subprocess spawn here — the trigger ONLY answers "yes/no". Caller
  owns the side effect. Keeps the class testable and decoupled.
- All disk reads are best-effort. A corrupt marker file, missing
  integrity log, or unreadable opportunity files NEVER raise — the
  affected gate returns False (closed) and a debug log line is emitted.
  This preserves the bias toward "don't trigger when uncertain."
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

_LOG = logging.getLogger("TrainingTrigger")

# Module-level defaults — used when the production config section is absent
# or partially populated.
_DEFAULTS = {
    "min_new_samples":       500,
    "drift_window_hours":    24,
    "drift_event_threshold": 5,
    "cooldown_hours":        6.0,
    "marker_path":           "results/training_trigger.json",
    "opportunity_glob":      "logs/**/opportunities.jsonl",
    "integrity_log":         "logs/integrity_events.jsonl",
    "drift_event_kinds":     ["RR_BYPASS", "RR_LLM_FALLBACK",
                              "PROMOTION_FAILED"],
}


@dataclass
class TrainingTriggerConfig:
    min_new_samples:       int
    drift_window_hours:    float
    drift_event_threshold: int
    cooldown_hours:        float
    marker_path:           Path
    opportunity_glob:      str
    integrity_log:         Path
    drift_event_kinds:     tuple[str, ...]

    @classmethod
    def from_section(cls, section: dict) -> "TrainingTriggerConfig":
        s = section or {}
        return cls(
            min_new_samples       = int(s.get("min_new_samples",       _DEFAULTS["min_new_samples"])),
            drift_window_hours    = float(s.get("drift_window_hours",  _DEFAULTS["drift_window_hours"])),
            drift_event_threshold = int(s.get("drift_event_threshold", _DEFAULTS["drift_event_threshold"])),
            cooldown_hours        = float(s.get("cooldown_hours",      _DEFAULTS["cooldown_hours"])),
            marker_path           = Path(s.get("marker_path",          _DEFAULTS["marker_path"])),
            opportunity_glob      = str(s.get("opportunity_glob",      _DEFAULTS["opportunity_glob"])),
            integrity_log         = Path(s.get("integrity_log",        _DEFAULTS["integrity_log"])),
            drift_event_kinds     = tuple(s.get("drift_event_kinds",   _DEFAULTS["drift_event_kinds"])),
        )


class TrainingTrigger:
    """Three-gate decision: only fire when samples + drift + cooldown all open."""

    def __init__(self, config: Optional[TrainingTriggerConfig] = None):
        self.cfg = config or TrainingTriggerConfig.from_section({})

    # ── Construction helpers ─────────────────────────────────────────────────

    @classmethod
    def from_prod_config(cls) -> "TrainingTrigger":
        """Load config from production config; fall back to defaults if absent."""
        try:
            from config_layer.production_config import get_prod_section  # type: ignore
            section = get_prod_section("training_trigger") or {}
        except Exception as exc:  # noqa: BLE001 — never block the trigger on config
            _LOG.debug("TrainingTrigger: prod config unavailable (%s); using defaults", exc)
            section = {}
        return cls(TrainingTriggerConfig.from_section(section))

    # ── Public API ───────────────────────────────────────────────────────────

    def should_trigger(self) -> bool:
        """Return True iff all three gates open. Logs the gate-by-gate reasoning."""
        cool = self._cooldown_elapsed(self.cfg.cooldown_hours)
        samples_ok, sample_count, delta = self._has_enough_samples(self.cfg.min_new_samples)
        drift_ok, drift_count = self._drift_gate_open()
        decision = cool and samples_ok and drift_ok
        _LOG.info(
            "TrainingTrigger gates: cooldown=%s samples_ok=%s (count=%d, delta=%d) "
            "drift_ok=%s (events=%d) → trigger=%s",
            cool, samples_ok, sample_count, delta, drift_ok, drift_count, decision,
        )
        return decision

    def mark_fired(self) -> None:
        """Persist {last_fired_ts, last_sample_count} so subsequent calls see
        the correct cooldown + delta baseline. Failures are logged, not raised."""
        try:
            _, sample_count, _ = self._has_enough_samples(self.cfg.min_new_samples)
            self.cfg.marker_path.parent.mkdir(parents=True, exist_ok=True)
            self.cfg.marker_path.write_text(
                json.dumps({
                    "last_fired_ts":     time.time(),
                    "last_sample_count": sample_count,
                }, indent=2),
                encoding="utf-8",
            )
            _LOG.info("TrainingTrigger.mark_fired: marker updated at %s "
                      "(sample_count=%d)", self.cfg.marker_path, sample_count)
        except Exception as exc:  # noqa: BLE001
            _LOG.warning("TrainingTrigger.mark_fired: failed to write marker — %s", exc)

    # ── Private gates ────────────────────────────────────────────────────────

    def _has_enough_samples(self, n_min: int) -> tuple[bool, int, int]:
        """Returns (gate_open, current_total, delta_since_last_fire).

        Counts opportunity-JSONL lines across the configured glob. Comparison
        is total-since-baseline so backfilled logs count correctly. Returns
        gate_closed on any disk error (bias to not triggering)."""
        marker = self._read_marker()
        baseline = int(marker.get("last_sample_count", 0)) if marker else 0
        try:
            total = self._count_opportunity_lines()
        except Exception as exc:  # noqa: BLE001
            _LOG.debug("_has_enough_samples: count failed — %s", exc)
            return False, baseline, 0
        delta = total - baseline
        return delta >= n_min, total, delta

    def _drift_gate_open(self) -> tuple[bool, int]:
        """Returns (gate_open, count_in_window). Reads the integrity log
        tail; counts events whose 'event' matches drift_event_kinds within
        the last drift_window_hours."""
        log_path = self.cfg.integrity_log
        if not log_path.exists():
            return False, 0
        cutoff = time.time() - (self.cfg.drift_window_hours * 3600.0)
        kinds  = set(self.cfg.drift_event_kinds)
        count  = 0
        try:
            with log_path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if rec.get("event") not in kinds:
                        continue
                    ts_str = rec.get("ts", "")
                    if not self._ts_within_window(ts_str, cutoff):
                        continue
                    count += 1
        except OSError as exc:
            _LOG.debug("_drift_gate_open: read failed — %s", exc)
            return False, 0
        return count >= self.cfg.drift_event_threshold, count

    def _cooldown_elapsed(self, hours: float) -> bool:
        """First-run case (no marker) returns True. Marker present returns
        True iff (now - last_fired_ts) >= hours."""
        marker = self._read_marker()
        if not marker:
            return True
        last = float(marker.get("last_fired_ts", 0.0))
        return (time.time() - last) >= (hours * 3600.0)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _read_marker(self) -> dict:
        if not self.cfg.marker_path.exists():
            return {}
        try:
            return json.loads(self.cfg.marker_path.read_text(encoding="utf-8")) or {}
        except (OSError, json.JSONDecodeError) as exc:
            _LOG.debug("_read_marker: failed — %s", exc)
            return {}

    def _count_opportunity_lines(self) -> int:
        """Total non-blank lines across all matching JSONL files. Uses
        Path.glob with the configured pattern (which supports ** via rglob
        when the base is 'logs')."""
        root = Path(".")
        total = 0
        # Path.glob honors ** segments natively in Python 3.10+.
        for p in root.glob(self.cfg.opportunity_glob):
            try:
                with p.open("r", encoding="utf-8") as fh:
                    for line in fh:
                        if line.strip():
                            total += 1
            except OSError:
                continue
        return total

    @staticmethod
    def _ts_within_window(ts_str: str, cutoff_epoch: float) -> bool:
        """Parse integrity_events ISO-Z timestamp; return True iff > cutoff.
        Unparseable timestamps are treated as out-of-window (conservative)."""
        if not ts_str:
            return False
        try:
            # Format: "YYYY-mm-ddTHH:MM:SSZ" — strptime is enough for stdlib
            t = time.strptime(ts_str, "%Y-%m-%dT%H:%M:%SZ")
            epoch = time.mktime(t) - time.timezone  # treat Z as UTC
            return epoch >= cutoff_epoch
        except (ValueError, TypeError):
            return False


__all__ = ["TrainingTrigger", "TrainingTriggerConfig"]
