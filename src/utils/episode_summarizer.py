"""
episode_summarizer.py
═════════════════════════════════════════════════════════════════════════════
Per-run, per-instrument CRT episode aggregator (M1 Part 2).

An **episode** is one CRT lifecycle traversal that starts when the state
machine leaves RANGE and ends when it returns to RANGE (via RESOLUTION,
EXPIRED, or any reset_to_range call).  At close, one summary record is
flushed to ``logs/llm_episodes.jsonl``.

Design invariants
──────────────────
- **Deterministic:** uses candle timestamps exclusively (never wall-clock);
  same CSV + seed → byte-identical output.
- **Read-only projection:** never influences any decision or gate.
- **Fail-open:** every write error is swallowed; the calling code path
  is unaffected.
- **No lookahead:** only data from candles already processed.

LLM episode summary schema
────────────────────────────
  {
    "episode_id":      "BNBUSDT_run_20260529_ep0042",
    "run_id":          "run_20260529_123456",
    "instrument":      "BNBUSDT",
    "episode_n":       42,
    "start_candle_ts": "2024-01-15T09:30:00",
    "end_candle_ts":   "2024-01-15T14:15:00",
    "state_path":      ["RANGE→SWEEP","SWEEP→DISPLACEMENT","DISPLACEMENT→EXPANSION",
                        "EXPANSION→RETEST","RETEST→EXECUTION","EXECUTION→RESOLUTION",
                        "RESOLUTION→RANGE"],
    "trade_id":        "abc123" | null,
    "entry_price":     1.2654 | null,
    "sl_price":        1.2634 | null,
    "tp2_price":       1.2694 | null,
    "direction":       "LONG" | null,
    "entry_candle_ts": "2024-01-15T12:00:00" | null,
    "exit_candle_ts":  "2024-01-15T14:00:00" | null,
    "exit_reason":     "TP2" | "STOPPED" | "RESET_CLOSE" | ... | null,
    "pnl_rr_net":      1.95 | null,
    "win":             true | null,
    "key_features":    {"retest_depth": 0.22, "body_ratio": 0.71, ...},
    "rejection_reasons": ["score_below_threshold"],
    "drift_flags":     ["hard_drift"],
    "governance_flags": [],
    "outcome":         "TRADE_WIN" | "TRADE_LOSS" | "REJECTED" | "EXPIRED" | "RESET" | "NO_SIGNAL",
  }

Usage (backtest_v2.py)
───────────────────────
  from utils.episode_summarizer import EpisodeSummarizer
  ep = EpisodeSummarizer(instrument="BNBUSDT", run_id=_RUN_ID)
  # per-candle, after engine.process_candle():
  if prev_state != curr_state:
      ep.on_state_transition(prev_state, curr_state, candle.timestamp, candle_idx)
  # after trade events:
  ep.on_trade_opened(trade_id, entry_price, sl_price, tp2_price, direction,
                     candle.timestamp, features)
  ep.on_trade_closed(trade_id, pnl_rr_net, exit_reason, candle.timestamp)
  ep.on_rejected(reason, candle.timestamp)
  ep.on_drift(severity, candle.timestamp)
  # end of run:
  ep.flush()
═════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

_log = logging.getLogger("EpisodeSummarizer")

LLM_EPISODES_LOG = Path("logs/llm_episodes.jsonl")

# Optional event-fabric import — used only for envelope wrapping.
# Fail-open: if unavailable, the flat llm_episodes.jsonl write still works.
try:
    from events.event_fabric import make_event_envelope, EventType
    _ENVELOPE_OK = True
except Exception:          # noqa: BLE001
    _ENVELOPE_OK = False


# ─────────────────────────────────────────────────────────────────────────────
# Outcome constants
# ─────────────────────────────────────────────────────────────────────────────

_OUTCOME_TRADE_WIN  = "TRADE_WIN"
_OUTCOME_TRADE_LOSS = "TRADE_LOSS"
_OUTCOME_REJECTED   = "REJECTED"
_OUTCOME_EXPIRED    = "EXPIRED"
_OUTCOME_RESET      = "RESET"
_OUTCOME_NO_SIGNAL  = "NO_SIGNAL"


# ─────────────────────────────────────────────────────────────────────────────
# EpisodeSummarizer
# ─────────────────────────────────────────────────────────────────────────────

class EpisodeSummarizer:
    """Deterministic per-run episode aggregator.

    One instance per ``BacktestRunner.run()`` call.  Each *→RANGE transition
    closes the current episode and opens the next.
    """

    def __init__(self, instrument: str, run_id: str) -> None:
        self._instrument = instrument
        self._run_id     = run_id
        self._episode_n  = 0          # monotonic per-run episode counter

        # Episode-local accumulators — reset on each new episode
        self._in_episode        = False
        self._state_path:      list[str]  = []
        self._start_candle_ts: Optional[datetime] = None
        self._end_candle_ts:   Optional[datetime] = None

        # Trade fields (populated when TRADE_OPENED inside this episode)
        self._trade_id:        Optional[str]   = None
        self._entry_price:     Optional[float] = None
        self._sl_price:        Optional[float] = None
        self._tp2_price:       Optional[float] = None
        self._direction:       Optional[str]   = None
        self._entry_candle_ts: Optional[datetime] = None
        self._exit_candle_ts:  Optional[datetime] = None
        self._exit_reason:     Optional[str]   = None
        self._pnl_rr_net:      Optional[float] = None
        self._key_features:    dict = {}

        # Episode-level signal lists
        self._rejection_reasons: list[str] = []
        self._drift_flags:       list[str] = []
        self._governance_flags:  list[str] = []

    # ──────────────────────────────────────────────────────────────────────────
    # Public event API
    # ──────────────────────────────────────────────────────────────────────────

    def on_state_transition(
        self,
        from_state:  str,
        to_state:    str,
        candle_ts:   datetime,
        candle_idx:  int,           # noqa: ARG002  (reserved for future use)
        reason:      str = "",      # noqa: ARG002
    ) -> None:
        """Called for every CRT state change.

        Leaving RANGE starts an episode; arriving at RANGE closes it.
        """
        transition = f"{from_state}→{to_state}"

        # ── Start episode ────────────────────────────────────────────────────
        if from_state == "RANGE" and to_state != "RANGE":
            if not self._in_episode:
                self._start_episode(candle_ts)

        # Accumulate path
        if self._in_episode:
            self._state_path.append(transition)

        # ── Close episode on any → RANGE ────────────────────────────────────
        if to_state == "RANGE" and self._in_episode:
            self._end_candle_ts = candle_ts
            self._flush_episode()
            self._reset_episode()

    def on_trade_opened(
        self,
        trade_id:   str,
        entry_price: float,
        sl_price:    float,
        tp2_price:   float,
        direction:   str,
        candle_ts:   datetime,
        features:    dict,
    ) -> None:
        """Record trade entry details for the current episode."""
        self._trade_id        = trade_id
        self._entry_price     = entry_price
        self._sl_price        = sl_price
        self._tp2_price       = tp2_price
        self._direction       = direction
        self._entry_candle_ts = candle_ts
        # Store a compact subset of features (top-level float values only)
        self._key_features = _extract_key_features(features)

    def on_trade_closed(
        self,
        trade_id:    str,           # noqa: ARG002  (correlation cross-check)
        pnl_rr_net:  float,
        exit_reason: str,
        candle_ts:   datetime,
    ) -> None:
        """Record trade exit for the current episode."""
        self._exit_candle_ts = candle_ts
        self._exit_reason    = exit_reason
        self._pnl_rr_net     = pnl_rr_net

    def on_rejected(self, reason: str, candle_ts: datetime) -> None:  # noqa: ARG002
        """Record a signal rejection inside the current episode."""
        if reason and reason not in self._rejection_reasons:
            self._rejection_reasons.append(reason)

    def on_drift(self, severity: str, candle_ts: datetime) -> None:   # noqa: ARG002
        """Record a drift flag (e.g. 'hard_drift', 'soft_drift')."""
        if severity and severity not in self._drift_flags:
            self._drift_flags.append(severity)

    def on_governance_flag(self, flag: str) -> None:
        """Record a governance event (e.g. 'kill_switch', 'circuit_open')."""
        if flag and flag not in self._governance_flags:
            self._governance_flags.append(flag)

    def flush(self) -> None:
        """Force-flush any open episode at backtest end (BACKTEST_END marker).

        If the state machine never returned to RANGE on the final bar the
        episode is still open — write it with outcome RESET.
        """
        if self._in_episode:
            self._flush_episode()
            self._reset_episode()

    # ──────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _start_episode(self, candle_ts: datetime) -> None:
        self._in_episode       = True
        self._start_candle_ts  = candle_ts

    def _flush_episode(self) -> None:
        """Determine outcome and write the summary record."""
        outcome = self._compute_outcome()
        episode_id = f"{self._instrument}_{self._run_id}_ep{self._episode_n:04d}"

        record: dict = {
            "episode_id":       episode_id,
            "run_id":           self._run_id,
            "instrument":       self._instrument,
            "episode_n":        self._episode_n,
            "start_candle_ts":  _iso(self._start_candle_ts),
            "end_candle_ts":    _iso(self._end_candle_ts),
            "state_path":       list(self._state_path),
            "trade_id":         self._trade_id,
            "entry_price":      _r6(self._entry_price),
            "sl_price":         _r6(self._sl_price),
            "tp2_price":        _r6(self._tp2_price),
            "direction":        self._direction,
            "entry_candle_ts":  _iso(self._entry_candle_ts),
            "exit_candle_ts":   _iso(self._exit_candle_ts),
            "exit_reason":      self._exit_reason,
            "pnl_rr_net":       _r4(self._pnl_rr_net),
            "win":              (self._pnl_rr_net > 0) if self._pnl_rr_net is not None else None,
            "key_features":     dict(self._key_features),
            "rejection_reasons": list(self._rejection_reasons),
            "drift_flags":       list(self._drift_flags),
            "governance_flags":  list(self._governance_flags),
            "outcome":           outcome,
        }

        self._write(record)
        self._episode_n += 1

    def _compute_outcome(self) -> str:
        """Infer episode outcome from accumulated state."""
        if self._pnl_rr_net is not None:
            return _OUTCOME_TRADE_WIN if self._pnl_rr_net > 0 else _OUTCOME_TRADE_LOSS
        if self._rejection_reasons:
            return _OUTCOME_REJECTED
        # Check for EXPIRED in the state path
        if any("EXPIRED" in t for t in self._state_path):
            return _OUTCOME_EXPIRED
        if self._in_episode and self._end_candle_ts is None:
            # flush() called with open episode = BACKTEST_END reset
            return _OUTCOME_RESET
        # Episode that reached RANGE without any of the above
        return _OUTCOME_NO_SIGNAL

    def _write(self, record: dict) -> None:
        """Append flat record and emit canonical envelope."""
        try:
            LLM_EPISODES_LOG.parent.mkdir(parents=True, exist_ok=True)
            with open(LLM_EPISODES_LOG, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record) + "\n")
        except Exception as e:  # noqa: BLE001
            _log.error("EpisodeSummarizer write failed: %s", e)
        self._emit_enveloped(record)

    def _emit_enveloped(self, record: dict) -> None:
        """Optional canonical envelope write.  Fail-open."""
        if not _ENVELOPE_OK:
            return
        try:
            env = make_event_envelope(
                event_type = EventType.COGNITIVE_TELEMETRY.value,
                instrument = self._instrument,
                source     = "EpisodeSummarizer",
                payload    = record,
            )
            # reuse the same log — envelope written alongside the flat record
            # (flat record IS the payload; this adds routing metadata only)
            # Written to a dedicated enveloped stream to keep it auditable.
            _ep_env_log = LLM_EPISODES_LOG.with_suffix(".enveloped.jsonl")
            _ep_env_log.parent.mkdir(parents=True, exist_ok=True)
            with open(_ep_env_log, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(env) + "\n")
        except Exception as e:  # noqa: BLE001
            _log.debug("EpisodeSummarizer envelope emit failed: %s", e)

    def _reset_episode(self) -> None:
        """Reset all episode-local state for the next episode."""
        self._in_episode        = False
        self._state_path        = []
        self._start_candle_ts   = None
        self._end_candle_ts     = None
        self._trade_id          = None
        self._entry_price       = None
        self._sl_price          = None
        self._tp2_price         = None
        self._direction         = None
        self._entry_candle_ts   = None
        self._exit_candle_ts    = None
        self._exit_reason       = None
        self._pnl_rr_net        = None
        self._key_features      = {}
        self._rejection_reasons = []
        self._drift_flags       = []
        self._governance_flags  = []


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt is not None else None


def _r6(v: Optional[float]) -> Optional[float]:
    return round(v, 6) if v is not None else None


def _r4(v: Optional[float]) -> Optional[float]:
    return round(v, 4) if v is not None else None


# Key features to surface in the episode summary.
# Subset of CANONICAL_FEATURES most useful for LLM causal reasoning.
_KEY_FEATURE_NAMES = frozenset({
    "retest_depth", "body_ratio", "disp_strength", "atr_ratio",
    "volume_ratio", "session_volatility", "htf_trend_score",
    "rr_ratio", "entry_quality", "zone_strength",
})


def _extract_key_features(features: dict) -> dict:
    """Return a compact float-rounded subset of features for the episode record."""
    if not features:
        return {}
    out: dict = {}
    for k, v in features.items():
        if k not in _KEY_FEATURE_NAMES:
            continue
        if v is None:
            continue
        try:
            out[k] = round(float(v), 6)
        except (TypeError, ValueError):
            pass
    return out
