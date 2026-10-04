"""
trade_replay_validator.py — Deterministic Candle Replay
═══════════════════════════════════════════════════════════════════════════════
Replays each trade candle-by-candle against the trade's entry / SL / TP1 / TP2
to recompute its realized RR, then compares against the persisted ``pnl_rr_net``.

Replaces the previous stub (which trusted ``pnl_rr_net`` blindly). Mismatches
land in ``logs/integrity_events.jsonl`` as REPLAY_MISMATCH and missing inputs
emit REPLAY_TRADE_INCOMPLETE / REPLAY_NO_CANDLES so silent backtest corruption
becomes observable.

Existing CSV output at ``logs/validator_dataset.csv`` is preserved as a strict
superset (new columns appended for replay metadata).
═══════════════════════════════════════════════════════════════════════════════
"""

import logging
import math
import os
from typing import Any, Dict, List, Optional

import pandas as pd

# Lazy/try import so the script also runs from environments without src on path.
try:
    from src.utils.integrity_events import emit_integrity_event, Severity  # noqa: F401
except Exception:  # pragma: no cover - fallback only
    def emit_integrity_event(*_a, **_kw):  # type: ignore[no-redef]
        return None

    class Severity:  # type: ignore[no-redef]
        INFO = "INFO"
        WARNING = "WARNING"
        ERROR = "ERROR"
        CRITICAL = "CRITICAL"


log = logging.getLogger("ValidatorConnector")

# Trade field aliases. The replay function accepts whichever name the upstream
# producer uses (e.g. manual_backtest emits "entry_price_raw"/"sl"/"tp1"/"tp2";
# the live engine emits canonical "entry_price"/"sl_price"/"tp1_price"/"tp2_price").
# A trade is "incomplete" only when none of the aliases for one of the canonical
# fields resolves to a non-None value.
_TRADE_FIELD_ALIASES = {
    "trade_id":    ("trade_id", "id"),
    "entry_price": ("entry_price", "entry_price_raw", "entry", "entry_fill", "entry_price_fill"),
    "sl_price":    ("sl_price", "sl", "stop_loss"),
    "tp1_price":   ("tp1_price", "tp1", "take_profit_1"),
    "tp2_price":   ("tp2_price", "tp2", "take_profit_2"),
    "direction":   ("direction", "side"),
}
REQUIRED_TRADE_FIELDS = tuple(_TRADE_FIELD_ALIASES.keys())

# Maximum allowed |recomputed_rr - original_rr|. Anything above this is a
# REPLAY_MISMATCH integrity event.
MAX_RR_DELTA: float = 0.05


def _trade_field(trade: Dict[str, Any], canonical: str) -> Any:
    """Resolve a canonical trade field from any of its accepted aliases."""
    for key in _TRADE_FIELD_ALIASES.get(canonical, (canonical,)):
        if key in trade and trade[key] is not None:
            return trade[key]
    return None


def classify_outcome(exit_reason: str) -> str:
    """Classifies raw engine exit reasons into standardized ML labels."""
    if exit_reason == "TP2":
        return "TP2"
    elif exit_reason in ("SL-BE", "TP1_BE"):  # Catching common BE variations
        return "TP1_BE"
    elif exit_reason in ("SL", "STOPPED"):
        return "SL"
    elif exit_reason == "TIMEOUT":
        return "TIMEOUT"
    return "OTHER"


def _normalize_direction(value: Any) -> Optional[str]:
    """Return canonical 'LONG' / 'SHORT' or None if uninterpretable."""
    if value is None:
        return None
    try:
        s = str(value).strip().upper()
    except Exception:  # noqa: BLE001
        return None
    if s in ("LONG", "BUY", "1", "+1"):
        return "LONG"
    if s in ("SHORT", "SELL", "-1"):
        return "SHORT"
    return None


def _candle_field(candle: Dict[str, Any], *keys: str) -> Optional[float]:
    """First non-None numeric field from candle for any of the given keys."""
    for k in keys:
        v = candle.get(k)
        if v is None:
            continue
        try:
            return float(v)
        except (TypeError, ValueError):
            continue
    return None


def replay_single_trade(
    trade: Dict[str, Any],
    candles: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Deterministically replay one trade against its candle stream.

    The trade dict must carry entry_price, sl_price, tp1_price, tp2_price, and
    direction in addition to its identity fields. Candles must be ordered and
    expose high/low/close (with timestamp recommended).

    On any integrity failure (missing fields, no candles, zero risk) the
    function emits an integrity event and returns an error row — it never
    raises, so ``validate_all`` can aggregate cleanly.
    """
    trade_id = _trade_field(trade, "trade_id") or "UNKNOWN"

    # ── 1. Required-field validation (fail-closed; alias-aware) ─────────────
    resolved = {k: _trade_field(trade, k) for k in REQUIRED_TRADE_FIELDS}
    missing = [k for k, v in resolved.items() if v is None]
    if missing:
        emit_integrity_event(
            "REPLAY_TRADE_INCOMPLETE",
            Severity.ERROR,
            "trade_replay_validator",
            {"trade_id": trade_id, "missing_fields": missing},
        )
        return {
            "error":          "incomplete_trade",
            "trade_id":       trade_id,
            "missing_fields": missing,
        }

    # ── 2. Candle stream validation ────────────────────────────────────────
    if not candles:
        emit_integrity_event(
            "REPLAY_NO_CANDLES",
            Severity.ERROR,
            "trade_replay_validator",
            {"trade_id": trade_id},
        )
        return {"error": "no_candles", "trade_id": trade_id}

    direction = _normalize_direction(resolved["direction"])
    if direction is None:
        emit_integrity_event(
            "REPLAY_TRADE_INCOMPLETE",
            Severity.ERROR,
            "trade_replay_validator",
            {"trade_id": trade_id, "missing_fields": ["direction"], "raw": str(resolved["direction"])},
        )
        return {
            "error":          "incomplete_trade",
            "trade_id":       trade_id,
            "missing_fields": ["direction"],
        }

    try:
        entry_price = float(resolved["entry_price"])
        sl_price    = float(resolved["sl_price"])
        tp1_price   = float(resolved["tp1_price"])
        tp2_price   = float(resolved["tp2_price"])
    except (TypeError, ValueError):
        emit_integrity_event(
            "REPLAY_TRADE_INCOMPLETE",
            Severity.ERROR,
            "trade_replay_validator",
            {"trade_id": trade_id, "missing_fields": ["entry/sl/tp1/tp2 not float-castable"]},
        )
        return {"error": "incomplete_trade", "trade_id": trade_id}

    risk = abs(entry_price - sl_price)
    if risk == 0:
        emit_integrity_event(
            "REPLAY_ZERO_RISK",
            Severity.ERROR,
            "trade_replay_validator",
            {"trade_id": trade_id, "entry_price": entry_price, "sl_price": sl_price},
        )
        return {"error": "zero_risk", "trade_id": trade_id}

    # ── 3. Deterministic forward simulation ────────────────────────────────
    tp1_hit            = False
    sl_effective       = sl_price
    exit_price: Optional[float] = None
    exit_reason: Optional[str]  = None
    tp1_hit_at_index: Optional[int] = None
    exit_index: Optional[int]       = None
    exit_timestamp: Optional[Any]   = None
    candles_processed = 0

    for idx, candle in enumerate(candles):
        candles_processed += 1
        high = _candle_field(candle, "high", "h", "High")
        low  = _candle_field(candle, "low",  "l", "Low")
        close = _candle_field(candle, "close", "c", "Close")
        if high is None or low is None:
            # Missing OHLC on a candle is itself an integrity event — but we
            # don't bail out, we just skip the bar (matches BacktestRunner
            # robustness behavior). Visibility goes through the events log.
            emit_integrity_event(
                "REPLAY_CANDLE_INCOMPLETE",
                Severity.WARNING,
                "trade_replay_validator",
                {"trade_id": trade_id, "candle_index": idx, "candle_keys": list(candle.keys())},
            )
            continue

        if direction == "LONG":
            # Pessimistic SL-first (matches BacktestRunner ordering).
            if low <= sl_effective:
                exit_price  = sl_effective
                exit_reason = "SL-BE" if tp1_hit else "SL"
                exit_index  = idx
                exit_timestamp = candle.get("timestamp") or candle.get("ts")
                break
            if high >= tp2_price:
                exit_price  = tp2_price
                exit_reason = "TP2"
                exit_index  = idx
                exit_timestamp = candle.get("timestamp") or candle.get("ts")
                break
            if (not tp1_hit) and high >= tp1_price:
                tp1_hit          = True
                tp1_hit_at_index = idx
                sl_effective     = entry_price  # break-even move
        else:  # SHORT (mirrored)
            if high >= sl_effective:
                exit_price  = sl_effective
                exit_reason = "SL-BE" if tp1_hit else "SL"
                exit_index  = idx
                exit_timestamp = candle.get("timestamp") or candle.get("ts")
                break
            if low <= tp2_price:
                exit_price  = tp2_price
                exit_reason = "TP2"
                exit_index  = idx
                exit_timestamp = candle.get("timestamp") or candle.get("ts")
                break
            if (not tp1_hit) and low <= tp1_price:
                tp1_hit          = True
                tp1_hit_at_index = idx
                sl_effective     = entry_price

    # No exit within the candle window → timeout at last close.
    if exit_price is None:
        last = candles[-1]
        last_close = _candle_field(last, "close", "c", "Close")
        if last_close is None:
            # Total candle blackout — escalate.
            emit_integrity_event(
                "REPLAY_NO_VALID_CLOSE",
                Severity.ERROR,
                "trade_replay_validator",
                {"trade_id": trade_id, "candle_count": len(candles)},
            )
            return {"error": "no_valid_close", "trade_id": trade_id}
        exit_price     = last_close
        exit_reason    = "TIMEOUT"
        exit_index     = len(candles) - 1
        exit_timestamp = last.get("timestamp") or last.get("ts")

    # ── 4. RR recomputation ────────────────────────────────────────────────
    sign = 1.0 if direction == "LONG" else -1.0
    recomputed_rr = sign * (exit_price - entry_price) / risk

    # ── 5. Mismatch detection ──────────────────────────────────────────────
    original_rr = float(trade.get("pnl_rr_net", 0.0) or 0.0)
    rr_delta = recomputed_rr - original_rr
    replay_consistent = abs(rr_delta) <= MAX_RR_DELTA

    if not replay_consistent:
        emit_integrity_event(
            "REPLAY_MISMATCH",
            Severity.WARNING,
            "trade_replay_validator",
            {
                "trade_id":              trade_id,
                "expected_rr":           original_rr,
                "recomputed_rr":         recomputed_rr,
                "delta":                 rr_delta,
                "original_exit_reason":  trade.get("exit_reason"),
                "replayed_exit_reason":  exit_reason,
            },
        )

    has_hit_tp1 = bool(tp1_hit) or (exit_reason == "TP2")
    diff = recomputed_rr - original_rr
    is_match = math.isclose(recomputed_rr, original_rr, abs_tol=0.01)

    return {
        # ── identity ────────────────────────────────────────────────────
        "trade_id": trade_id,

        # ── validation (back-compat keys) ───────────────────────────────
        "recomputed_rr": recomputed_rr,
        "original_rr":   original_rr,
        "diff":          diff,
        "is_match":      is_match,

        # ── replay verdict (new) ────────────────────────────────────────
        "replay_consistent": replay_consistent,
        "rr_delta":          rr_delta,

        # ── execution trace ─────────────────────────────────────────────
        "exit_reason":       exit_reason,
        "candles_processed": candles_processed,
        "tp1_hit":           has_hit_tp1,
        "tp2_hit":           (exit_reason == "TP2"),

        # ── replay metadata (new) ───────────────────────────────────────
        "replay_path": {
            "candles_processed":     candles_processed,
            "tp1_hit_at_index":      tp1_hit_at_index,
            "exit_index":            exit_index,
            "exit_timestamp":        exit_timestamp,
            "exit_reason_replayed":  exit_reason,
        },

        # ── feature snapshot (preserved, mapped directly) ───────────────
        "features": {
            "retest_depth":     trade.get("retest_depth", 0.0),
            "body_ratio":       trade.get("body_ratio", 0.0),
            "disp_str":         trade.get("disp_str", 0.0),
            "atr_vol":          trade.get("atr_vol"),
            "session":          trade.get("session"),
            "double_confirmed": trade.get("double_confirmed"),
        },

        # ── outcome labels (for training) ───────────────────────────────
        "outcome": {
            "rr":        recomputed_rr,
            "class":     classify_outcome(exit_reason or "UNKNOWN"),
            "is_winner": recomputed_rr > 0,
        },
    }


def validate_all(
    trades: List[Dict[str, Any]],
    all_candles: Dict[str, List[Dict[str, Any]]],
) -> pd.DataFrame:
    """
    Validate all trades and flatten them into a dataset_builder-compatible DataFrame.

    Emits a REPLAY_BATCH_SUMMARY integrity event at the end with aggregate
    counters: replay_consistent_count, replay_mismatch_count, error_count.
    """
    if not trades:
        return pd.DataFrame()

    results: List[Dict[str, Any]] = []
    for trade in trades:
        trade_id = trade.get("trade_id")
        candles = all_candles.get(trade_id, [])
        results.append(replay_single_trade(trade, candles))

    # Separate valid replays from errors to ensure DataFrame integrity.
    valid_results = [r for r in results if "error" not in r]
    error_count   = len(results) - len(valid_results)

    if not valid_results:
        log.error("No valid trades processed. Returning empty DataFrame.")
        emit_integrity_event(
            "REPLAY_BATCH_SUMMARY",
            Severity.WARNING,
            "trade_replay_validator",
            {
                "trades_total":          len(trades),
                "replay_consistent":     0,
                "replay_mismatch":       0,
                "error_count":           error_count,
            },
        )
        return pd.DataFrame()

    consistent_count = sum(1 for r in valid_results if r.get("replay_consistent"))
    mismatch_count   = len(valid_results) - consistent_count

    df = pd.DataFrame(valid_results)

    # Flatten nested fields for dataset_builder compatibility.
    features_df = pd.json_normalize(df["features"])
    outcome_df  = pd.json_normalize(df["outcome"])

    # replay_path is dict-typed; flatten with a prefix to avoid column collisions.
    replay_path_df = pd.json_normalize(df["replay_path"]).add_prefix("replay_")

    final_df = pd.concat(
        [
            df.drop(columns=["features", "outcome", "replay_path"]),
            features_df,
            outcome_df,
            replay_path_df,
        ],
        axis=1,
    )

    os.makedirs("logs", exist_ok=True)
    export_path = "logs/validator_dataset.csv"
    final_df.to_csv(export_path, index=False)
    log.info("Dataset exported to %s (%d rows)", export_path, len(final_df))

    emit_integrity_event(
        "REPLAY_BATCH_SUMMARY",
        Severity.INFO if mismatch_count == 0 and error_count == 0 else Severity.WARNING,
        "trade_replay_validator",
        {
            "trades_total":      len(trades),
            "replay_consistent": consistent_count,
            "replay_mismatch":   mismatch_count,
            "error_count":       error_count,
            "export_path":       export_path,
        },
    )

    return final_df
