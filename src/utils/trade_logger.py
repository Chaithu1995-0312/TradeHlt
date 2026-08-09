"""
trade_logger.py
═══════════════════════════════════════════════════════════════════════════════
Structured JSONL trade logger for the CRT + Fusion pipeline.

Every TRADE ENTRY and TRADE EXIT is written as a separate record.
Entry and exit are linked by `trade_id` (same UUID used by BacktestRunner).

Log schema
──────────
Entry record:
  {
    "event":        "ENTRY",
    "trade_id":     "...",
    "timestamp":    "2024-01-15T09:30:00.000000",
    "instrument":   "GBPUSD",
    "direction":    "LONG",
    "session":      "LONDON",
    "regime":       "EXPANSION",
    "features": {
      "retest_depth": 0.22,
      "body_ratio":   0.71,
      "disp_str":     1.45,
      ...
    },
    "fusion": {
      "final_score": 0.68,
      "gaussian":    0.62,
      "neural":      null,
      "llm":         0.71,
      "llm_fired":   true,
      "action":      "TRADE",
      "risk_mult":   0.5
    },
    "risk_pct":     0.005,
    "entry_price":  1.26540,
    "sl_price":     1.26340,
    "tp1_price":    1.26740,
    "tp2_price":    1.26940,
  }

Exit record:
  {
    "event":       "EXIT",
    "trade_id":    "...",        ← same as ENTRY — join on this
    "timestamp":   "...",
    "exit_reason": "TP2",
    "pnl_rr_net":  1.95,
    "win":         true,
    "duration_candles": 18,
  }

Usage
──────────
  from trade_logger import TradeLogger
  logger = TradeLogger()               # default: logs/fusion_trades.jsonl
  logger.log_entry(trade_id, record, fusion_result, features)
  logger.log_exit(trade_id, trade_record)

  # or use the module-level singleton via:
  from trade_logger import log_entry, log_exit
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from fusion_engine import FusionResult
    from typing import Union

log = logging.getLogger("TradeLogger")

DEFAULT_LOG_PATH = Path("logs/fusion_trades.jsonl")

# M1 telemetry normalization — canonical enveloped dual-write target.
TRADE_LIFECYCLE_LOG = Path("logs/trade_lifecycle.jsonl")

# Optional event-fabric import. Fail-open: if unavailable, the flat
# fusion_trades.jsonl write is completely unaffected.
try:
    from events.event_fabric import make_event_envelope, EventType
    _ENVELOPE_OK = True
except Exception:  # noqa: BLE001
    _ENVELOPE_OK = False


# ─────────────────────────────────────────────────────────────────────────────
# LOGGER CLASS
# ─────────────────────────────────────────────────────────────────────────────

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

    # ──────────────────────────────────────────────────────────────────────────

    def log_entry(
        self,
        trade_id:      str,
        instrument:    str,
        direction:     str,
        session:       str,
        regime:        str,
        features:      dict,
        fusion_result: "Union[FusionResult, dict]",
        risk_pct:      float,
        entry_price:   float,
        sl_price:      float,
        tp1_price:     float,
        tp2_price:     float,
        opened_at:     Optional[datetime] = None,
        provenance:         Optional[dict] = None,
        feature_vector_sha: str = "",
        gates_fired:        Optional[dict] = None,
    ) -> None:
        """
        Called immediately after a trade is opened.
        Write everything needed to later reconstruct the decision.

        provenance / feature_vector_sha / gates_fired (target-strategy-architecture.md
        §13 item8 / §9 — additive, default-empty so existing readers are unaffected):
          provenance         — TradeProvenanceV1.to_dict() (config version/hash, model
                                pins, strategy_id) — WHY this trade was allowed to exist.
          feature_vector_sha — sha256 fingerprint of the canonical feature vector at
                                decision time, so the exact market state is joinable
                                without storing the full vector on every line.
          gates_fired        — the CRTConfig threshold snapshot active for this trade
                                (dataclasses.asdict(crt_cfg)) — WHAT let it through.
        """
        record = {
            "event":       "ENTRY",
            "trade_id":    trade_id,
            "timestamp":   _now_iso(opened_at),
            "instrument":  instrument,
            "direction":   str(direction),
            "session":     session,
            "regime":      regime,
            "features":    _safe_features(features),
            "fusion":      fusion_result.to_dict() if hasattr(fusion_result, "to_dict") else (fusion_result or {}),
            "risk_pct":    round(risk_pct, 6),
            "entry_price": round(entry_price, 6),
            "sl_price":    round(sl_price,    6),
            "tp1_price":   round(tp1_price,   6),
            "tp2_price":   round(tp2_price,   6),
            "provenance":         provenance or {},
            "feature_vector_sha": feature_vector_sha,
            "gates_fired":        gates_fired or {},
        }
        self._write(record)

    # ──────────────────────────────────────────────────────────────────────────

    def log_exit(
        self,
        trade_id:         str,
        pnl_rr_net:       float,
        exit_reason:      str,
        duration_candles: int,
        closed_at:        Optional[datetime] = None,
    ) -> None:
        """
        Called after a trade closes (TP / SL / TIME_STOP).
        Linked to ENTRY via trade_id.
        """
        record = {
            "event":            "EXIT",
            "trade_id":         trade_id,
            "timestamp":        _now_iso(closed_at),
            "exit_reason":      exit_reason,
            "pnl_rr_net":       round(pnl_rr_net, 4),
            "win":              pnl_rr_net > 0,
            "duration_candles": duration_candles,
        }
        self._write(record)

    # ──────────────────────────────────────────────────────────────────────────

    def log_rejection(
        self,
        instrument:    str,
        features:      dict,
        fusion_result: "FusionResult",
        reason:        str,
        candle_idx:    int,
    ) -> None:
        """
        Log rejected signals — critical for learning loop.
        Rejections that later turn out to be profitable reveal gate weakness.
        """
        record = {
            "event":      "REJECT",
            "timestamp":  _now_iso(),
            "instrument": instrument,
            "candle_idx": candle_idx,
            "reason":     reason,
            "features":   _safe_features(features),
            "fusion":     fusion_result.to_dict(),
        }
        self._write(record)

    # ──────────────────────────────────────────────────────────────────────────

    def _write(self, record: dict) -> None:
        try:
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record) + "\n")
        except Exception as e:
            log.error(f"TradeLogger write failed: {e}")
        self._emit_enveloped(record)

    def _emit_enveloped(self, record: dict) -> None:
        """M1 dual-write: emit the same record as a canonical TRADE_LIFECYCLE envelope
        to logs/trade_lifecycle.jsonl. Read-only projection of the flat record — the
        flat write above is the source of truth and is never altered. Fail-open: any
        error is swallowed so trade logging and replay are never disrupted."""
        if not _ENVELOPE_OK:
            return
        try:
            env = make_event_envelope(
                event_type = EventType.TRADE_LIFECYCLE.value,  # plain string, matches existing emitters
                instrument = str(record.get("instrument", "")),
                source     = "TradeLogger",
                payload    = record,
            )
            TRADE_LIFECYCLE_LOG.parent.mkdir(parents=True, exist_ok=True)
            with open(TRADE_LIFECYCLE_LOG, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(env) + "\n")
        except Exception as e:  # noqa: BLE001
            log.debug(f"TradeLogger envelope emit failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _now_iso(dt: Optional[datetime] = None) -> str:
    if dt is None:
        dt = datetime.now(tz=timezone.utc)
    return dt.isoformat()


def _safe_features(features: dict) -> dict:
    """Round floats for compact storage; skip None values."""
    if not features:
        return {}
    out = {}
    for k, v in features.items():
        if v is None:
            continue
        try:
            out[k] = round(float(v), 6)
        except (TypeError, ValueError):
            out[k] = v
    return out


# ─────────────────────────────────────────────────────────────────────────────
# MODULE-LEVEL SINGLETON  (convenience — avoids passing logger everywhere)
# ─────────────────────────────────────────────────────────────────────────────

_default_logger: Optional[TradeLogger] = None


def _get_logger() -> TradeLogger:
    global _default_logger
    if _default_logger is None:
        _default_logger = TradeLogger()
    return _default_logger


def log_entry(**kwargs) -> None:
    _get_logger().log_entry(**kwargs)


def log_exit(**kwargs) -> None:
    _get_logger().log_exit(**kwargs)


def log_rejection(**kwargs) -> None:
    _get_logger().log_rejection(**kwargs)


def set_log_path(path: str | Path) -> None:
    """Override default log path (call before first trade)."""
    global _default_logger
    _default_logger = TradeLogger(path)


def set_instrument(instrument: str) -> None:
    """Route the module-level singleton to a per-instrument log file.
    Call once at startup before any trades are logged.

    Example:
        set_instrument("BTCUSDT")  →  logs/fusion_trades_BTCUSDT.jsonl
        set_instrument("EURUSD")   →  logs/fusion_trades_EURUSD.jsonl
    """
    global _default_logger
    _default_logger = TradeLogger(instrument=instrument)
