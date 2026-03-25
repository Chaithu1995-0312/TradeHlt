"""
live_engine.py
═══════════════════════════════════════════════════════════════════════════════
Live trading decision + Telegram alert system.

Design principles:
  - NO auto-trading, NO broker calls, NO order placement
  - Human is ALWAYS final executor
  - Gaussian = primary signal, ML = advisory layer
  - Every alert (sent or suppressed) is logged to logs/live_alerts.jsonl
  - Per-symbol cooldown + duplicate setup filter prevent spam
  - Kill switch via env var LIVE_ENGINE_ENABLED=0

Usage:
    from live_engine import LiveEngine, LiveEngineConfig
    engine = LiveEngine(LiveEngineConfig.from_env())
    result = engine.process(trade_data, gaussian_model, scaler, neural_fn)
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

log = logging.getLogger("LiveEngine")

LOGS_DIR       = Path("logs")
ALERT_LOG_PATH = LOGS_DIR / "live_alerts.jsonl"

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class LiveEngineConfig:
    """
    All live engine parameters. Load from env with LiveEngineConfig.from_env().

    Environment variables:
        TELEGRAM_BOT_TOKEN       : required for sending alerts
        TELEGRAM_CHAT_ID         : required for sending alerts
        LIVE_ENGINE_ENABLED      : set to "1" to enable (default: disabled)
        LIVE_RR_THRESHOLD        : minimum expected RR to consider (default 1.5)
        LIVE_CONF_MIN            : minimum confidence to avoid BLOCK (default 0.55)
        LIVE_CONF_STRONG         : confidence threshold for strong setup (default 0.60)
        LIVE_ML_OVERRIDE         : ML score threshold for WATCH signal (default 0.75)
        LIVE_COOLDOWN_SECONDS    : per-symbol alert cooldown (default 60)
        LIVE_DEDUP_CANDLES       : same setup dedup window in candles (default 4)
    """
    bot_token:              str   = ""
    chat_id:                str   = ""
    enabled:                bool  = False
    rr_threshold:           float = 1.5
    confidence_min:         float = 0.55
    confidence_strong:      float = 0.60
    ml_override_threshold:  float = 0.75
    alert_cooldown_seconds: int   = 60
    dedup_candles:          int   = 4

    @classmethod
    def from_env(cls) -> "LiveEngineConfig":
        return cls(
            bot_token              = os.environ.get("TELEGRAM_BOT_TOKEN", "8540111634:AAF29RTVnbIiBBMxITfSJ50WnwiQVGaZqhY"),
            chat_id                = os.environ.get("TELEGRAM_CHAT_ID",   "1103644701"),
            enabled                = os.environ.get("LIVE_ENGINE_ENABLED", "0") == "1",
            rr_threshold           = float(os.environ.get("LIVE_RR_THRESHOLD",    "1.5")),
            confidence_min         = float(os.environ.get("LIVE_CONF_MIN",        "0.55")),
            confidence_strong      = float(os.environ.get("LIVE_CONF_STRONG",     "0.60")),
            ml_override_threshold  = float(os.environ.get("LIVE_ML_OVERRIDE",     "0.75")),
            alert_cooldown_seconds = int(os.environ.get("LIVE_COOLDOWN_SECONDS",  "60")),
            dedup_candles          = int(os.environ.get("LIVE_DEDUP_CANDLES",     "4")),
        )

    def validate(self) -> list[str]:
        """Return list of config warnings (non-fatal)."""
        issues = []
        if not self.bot_token:
            issues.append("TELEGRAM_BOT_TOKEN not set — alerts will be logged only")
        if not self.chat_id:
            issues.append("TELEGRAM_CHAT_ID not set — alerts will be logged only")
        if not self.enabled:
            issues.append("LIVE_ENGINE_ENABLED=0 — engine is in DRY RUN mode")
        return issues


# ─────────────────────────────────────────────────────────────────────────────
# DECISION LOGIC
# ─────────────────────────────────────────────────────────────────────────────

def decide_trade(
    expected_rr:  float,
    confidence:   float,
    ml_score:     Optional[float],
    threshold:    float = 1.5,
    conf_min:     float = 0.55,
    conf_strong:  float = 0.60,
    ml_override:  float = 0.75,
) -> tuple[str, str]:
    """
    Deterministic decision engine. Returns (decision, reason).

    Decision ladder (evaluated top-to-bottom, first match wins):
      1. confidence < conf_min             → BLOCK  (low_confidence)
      2. rr >= threshold AND conf >= strong → EXECUTE (strong_setup)
      3. rr >= threshold AND conf < strong  → WARN   (rr_good_but_low_conf)
      4. ml_score > ml_override AND rr < t  → WATCH  (ml_disagrees_positive)
      5. otherwise                          → BLOCK  (no_edge)

    Parameters
    ----------
    expected_rr  : Gaussian expected risk/reward
    confidence   : max P(class) from Gaussian
    ml_score     : optional neural/ML score (None if not available)
    threshold    : minimum expected_rr to execute (default 1.5)
    conf_min     : below this → always block (default 0.55)
    conf_strong  : threshold for 'strong' confidence (default 0.60)
    ml_override  : ML score that triggers WATCH even if rr below threshold
    """
    # Rule 1: Hard block on low confidence
    if confidence < conf_min:
        return "BLOCK", "low_confidence"

    # Rule 2: Strong setup — both RR and confidence meet bars
    if expected_rr >= threshold and confidence >= conf_strong:
        return "EXECUTE", "strong_setup"

    # Rule 3: RR good but confidence borderline
    if expected_rr >= threshold and confidence < conf_strong:
        return "WARN", "rr_good_but_low_conf"

    # Rule 4: ML has strong positive view despite weak Gaussian
    if ml_score is not None and ml_score > ml_override and expected_rr < threshold:
        return "WATCH", "ml_disagrees_positive"

    # Default: no clear edge
    return "BLOCK", "no_edge"


# ─────────────────────────────────────────────────────────────────────────────
# TELEGRAM SENDER
# ─────────────────────────────────────────────────────────────────────────────

def send_telegram_alert(
    message:   str,
    bot_token: str,
    chat_id:   str,
    timeout:   int = 5,
) -> tuple[bool, Optional[str]]:
    """
    Send a Telegram message. Fail-safe — never raises.

    Returns (success: bool, error: str | None)
    """
    if not bot_token or not chat_id:
        log.debug("Telegram not configured — message suppressed (bot_token or chat_id missing)")
        return False, "not_configured"

    try:
        import requests  # type: ignore
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id":    chat_id,
            "text":       message,
            "parse_mode": "Markdown",
        }
        resp = requests.post(url, json=payload, timeout=timeout)
        if resp.status_code == 200:
            return True, None
        else:
            err = f"HTTP {resp.status_code}: {resp.text[:200]}"
            log.warning(f"Telegram send failed: {err}")
            return False, err
    except ImportError:
        log.warning("requests not installed — Telegram alert skipped")
        return False, "requests_not_installed"
    except Exception as e:
        log.warning(f"Telegram exception: {e}")
        return False, str(e)


# ─────────────────────────────────────────────────────────────────────────────
# MESSAGE FORMATTER
# ─────────────────────────────────────────────────────────────────────────────

_DECISION_ICONS = {
    "EXECUTE": "✅",
    "WARN":    "⚠️",
    "WATCH":   "👀",
    "BLOCK":   "❌",
}

def format_alert_message(
    symbol:      str,
    expected_rr: float,
    confidence:  float,
    decision:    str,
    reason:      str,
    ml_score:    Optional[float] = None,
    probabilities: Optional[list] = None,
    regime:      str = "UNKNOWN",
    session:     str = "UNKNOWN",
    time_decay:  float = 1.0,
    timeframe:   str = "M15",
) -> str:
    """
    Format clean, actionable Telegram alert message.
    """
    icon = _DECISION_ICONS.get(decision, "❓")
    ml_line = f"🧠 *ML Score:* `{ml_score:.2f}`\n" if ml_score is not None else ""

    prob_line = ""
    if probabilities and len(probabilities) == 4:
        p_loss, p_small, p_mid, p_big = [round(p, 2) for p in probabilities]
        prob_line = (
            f"📉 Loss `{p_loss:.0%}`  "
            f"📊 Small `{p_small:.0%}`  "
            f"📈 Mid `{p_mid:.0%}`  "
            f"🔥 Big `{p_big:.0%}`\n"
        )

    msg = (
        f"🚨 *TRADE SETUP DETECTED*\n\n"
        f"*Symbol:* `{symbol}`  ·  *TF:* `{timeframe}`\n\n"
        f"📊 *Gaussian Analysis:*\n"
        f"  RR: `{expected_rr:.2f}`\n"
        f"  Confidence: `{confidence:.0%}`\n"
        f"{prob_line}"
        f"\n{ml_line}"
        f"⚖️ *Decision:* {icon} `{decision}`\n"
        f"*Reason:* `{reason}`\n\n"
        f"🔥 Regime: `{regime}`\n"
        f"⏱ Session: `{session}`\n"
        f"⌛ Time Decay: `{time_decay:.2f}`\n\n"
        f"👉 _Accept within 30s or skip_"
    )
    return msg


# ─────────────────────────────────────────────────────────────────────────────
# ALERT STATE (cooldown + dedup)
# ─────────────────────────────────────────────────────────────────────────────

class _AlertState:
    """Tracks per-symbol cooldown and setup deduplication."""

    def __init__(self, cooldown_seconds: int = 60, dedup_candles: int = 4) -> None:
        self._cooldown   = cooldown_seconds
        self._dedup      = dedup_candles
        self._last_time: dict[str, float] = {}
        self._last_setup: dict[str, tuple[str, int]] = {}  # symbol → (setup_hash, candle_idx)

    def _setup_hash(self, symbol: str, session: str, regime: str) -> str:
        key = f"{symbol}:{session}:{regime}"
        return hashlib.md5(key.encode()).hexdigest()[:8]

    def should_alert(self, symbol: str, session: str, regime: str, candle_idx: int = 0) -> tuple[bool, str]:
        now = time.time()

        # Cooldown check
        last = self._last_time.get(symbol, 0.0)
        if now - last < self._cooldown:
            wait = int(self._cooldown - (now - last))
            return False, f"cooldown ({wait}s remaining)"

        # Duplicate setup check
        h = self._setup_hash(symbol, session, regime)
        last_setup = self._last_setup.get(symbol)
        if last_setup:
            last_h, last_cidx = last_setup
            if last_h == h and (candle_idx - last_cidx) < self._dedup:
                return False, f"duplicate_setup (same structure within {self._dedup} candles)"

        return True, "ok"

    def record(self, symbol: str, session: str, regime: str, candle_idx: int = 0) -> None:
        self._last_time[symbol] = time.time()
        h = self._setup_hash(symbol, session, regime)
        self._last_setup[symbol] = (h, candle_idx)


# ─────────────────────────────────────────────────────────────────────────────
# AUDIT LOGGER
# ─────────────────────────────────────────────────────────────────────────────

def _log_alert(entry: dict) -> None:
    """Append alert entry to logs/live_alerts.jsonl (fail-safe)."""
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        with ALERT_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        log.warning(f"Audit log write failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# LIVE ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class LiveEngine:
    """
    Main live engine orchestrator.

    Integrates:
      - dataset_builder feature construction (single source of truth)
      - GaussianNBModel inference (expected_rr + confidence)
      - Optional neural/ML advisory score
      - Deterministic decision rules
      - Telegram alert dispatch
      - Per-symbol cooldown + dedup filter
      - Audit log (every signal, sent or suppressed)
      - Kill switch (LIVE_ENGINE_ENABLED env var)

    Human remains final executor — this system NEVER places orders.
    """

    def __init__(self, config: Optional[LiveEngineConfig] = None) -> None:
        self.config = config or LiveEngineConfig()
        self._state = _AlertState(
            cooldown_seconds = self.config.alert_cooldown_seconds,
            dedup_candles    = self.config.dedup_candles,
        )

        # Warn about missing config at startup
        issues = self.config.validate()
        for issue in issues:
            log.warning(f"LiveEngine config: {issue}")

    def process(
        self,
        trade_data:     dict,
        gaussian_model,
        scaler,
        neural_fn       = None,
        candle_idx:     int   = 0,
        timeframe:      str   = "M15",
    ) -> dict:
        """
        Full live inference pipeline for one trade setup.

        Parameters
        ----------
        trade_data     : dict with CRT trade fields (see dataset_builder.build_feature_vector)
        gaussian_model : GaussianNBModel from load_active_gaussian_scorer()
        scaler         : StandardScaler from load_active_gaussian_scorer()
        neural_fn      : optional neural callable (from load_active_neural_fn()) — None = skip
        candle_idx     : current candle index for dedup tracking
        timeframe      : label for the alert message

        Returns
        -------
        dict: {decision, reason, expected_rr, confidence, ml_score, sent, suppressed_reason}
        """
        symbol  = str(trade_data.get("symbol", "UNKNOWN"))
        session = str(trade_data.get("session", "UNKNOWN"))
        regime  = str(trade_data.get("regime",  "NEUTRAL"))

        result = {
            "timestamp":        time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "symbol":           symbol,
            "decision":         "BLOCK",
            "reason":           "not_processed",
            "expected_rr":      0.0,
            "confidence":       0.0,
            "ml_score":         None,
            "ml_info":          None,
            "probabilities":    None,
            "sent":             False,
            "suppressed_reason": None,
        }

        # ── Kill switch ───────────────────────────────────────────────────────
        if not self.config.enabled:
            log.debug(f"LiveEngine disabled (kill switch) — skipping {symbol}")
            result["suppressed_reason"] = "kill_switch_disabled"
            _log_alert(result)
            return result

        # ── Step 1: Build + validate feature vector ───────────────────────────
        try:
            from dataset_builder import build_feature_vector, validate_feature_vector
            vec = build_feature_vector(trade_data, lambda_decay=0.05)
            validate_feature_vector(vec, context="LiveEngine.process")
        except Exception as e:
            log.error(f"Feature build failed for {symbol}: {e}")
            result["reason"] = f"feature_error: {e}"
            _log_alert(result)
            return result

        # ── Step 2: Scale ─────────────────────────────────────────────────────
        try:
            vec_scaled = scaler.transform_one(vec)
        except Exception as e:
            log.error(f"Scaler transform failed for {symbol}: {e}")
            result["reason"] = f"scaler_error: {e}"
            _log_alert(result)
            return result

        # ── Step 3: Gaussian inference ────────────────────────────────────────
        try:
            expected_rr, confidence, probabilities = gaussian_model.predict_expected_rr(vec_scaled)
            result["expected_rr"]   = round(expected_rr,  4)
            result["confidence"]    = round(confidence,   4)
            result["probabilities"] = [round(p, 4) for p in probabilities]
        except Exception as e:
            log.error(f"Gaussian inference failed for {symbol}: {e}")
            result["reason"] = f"gaussian_error: {e}"
            _log_alert(result)
            return result

        # ── Step 4: RR Pattern Miner advisory score (fail-open) ───────────────
        # Uses RRFusionLayer as primary ML source; falls back to neural_fn if
        # the RR model is not loaded. Neither source can override CRT/Gaussian.
        ml_score = None
        ml_info  = None
        try:
            from rr_fusion import get_fusion_layer as _get_rr_layer
            _rr_layer = _get_rr_layer()
            if _rr_layer.is_loaded:
                # Augment trade_data with Gaussian results for fusion formula.
                # gaussian_score = Gaussian confidence (0-1 normalized).
                # gaussian_p_win = max class probability from Gaussian model.
                _aug = dict(trade_data)
                _aug["gaussian_score"] = confidence
                _aug["gaussian_p_win"] = (
                    max(probabilities) if probabilities else 0.5
                )
                ml_info  = _rr_layer.score(_aug, threshold=self.config.confidence_min)
                ml_score = ml_info.get("final_score")
        except Exception as e:
            log.debug(f"RR fusion skipped for {symbol}: {e}")

        # Fallback: legacy neural_fn if RR model not available
        if ml_score is None and neural_fn is not None:
            try:
                ml_score = float(neural_fn(vec))
                ml_score = max(0.0, min(1.0, ml_score))
            except Exception as e:
                log.debug(f"ML inference (neural_fn) skipped for {symbol}: {e}")
                ml_score = None

        result["ml_score"] = round(ml_score, 4) if ml_score is not None else None
        result["ml_info"]  = ml_info

        # ── Step 5: Decision ──────────────────────────────────────────────────
        decision, reason = decide_trade(
            expected_rr  = expected_rr,
            confidence   = confidence,
            ml_score     = ml_score,
            threshold    = self.config.rr_threshold,
            conf_min     = self.config.confidence_min,
            conf_strong  = self.config.confidence_strong,
            ml_override  = self.config.ml_override_threshold,
        )
        result["decision"] = decision
        result["reason"]   = reason

        # ── Step 6: Cooldown + dedup filter ──────────────────────────────────
        if decision in ("BLOCK",):
            # Blocked by decision logic — don't even check cooldown
            _log_alert(result)
            return result

        ok_to_alert, suppress_reason = self._state.should_alert(symbol, session, regime, candle_idx)
        if not ok_to_alert:
            result["suppressed_reason"] = suppress_reason
            log.debug(f"Alert suppressed for {symbol}: {suppress_reason}")
            _log_alert(result)
            return result

        # ── Step 7: Format message ────────────────────────────────────────────
        time_decay = float(trade_data.get("time_decay_feature",
                    math.exp(-0.05 * int(trade_data.get("candles_since_retest", 0)))))

        message = format_alert_message(
            symbol        = symbol,
            expected_rr   = expected_rr,
            confidence     = confidence,
            decision       = decision,
            reason         = reason,
            ml_score       = ml_score,
            probabilities  = probabilities,
            regime         = regime,
            session        = session,
            time_decay     = time_decay,
            timeframe      = timeframe,
        )

        # ── Step 8: Send Telegram ─────────────────────────────────────────────
        sent, err = send_telegram_alert(
            message   = message,
            bot_token = self.config.bot_token,
            chat_id   = self.config.chat_id,
        )
        result["sent"] = sent

        if sent:
            self._state.record(symbol, session, regime, candle_idx)
            log.info(
                f"Alert sent | {symbol} | {decision} | "
                f"RR={expected_rr:.2f} conf={confidence:.0%}"
            )
        else:
            log.warning(f"Alert NOT sent for {symbol}: {err}")
            result["suppressed_reason"] = f"telegram_error: {err}"

        # ── Step 9: Audit log ─────────────────────────────────────────────────
        _log_alert(result)
        return result

    def dry_run(
        self,
        trade_data:     dict,
        gaussian_model,
        scaler,
        neural_fn       = None,
        candle_idx:     int = 0,
        timeframe:      str = "M15",
    ) -> dict:
        """
        Run the full pipeline without sending Telegram — for testing/backtesting.
        All validation, inference, and decision logic still executes.
        """
        orig = self.config.enabled
        self.config.enabled = True  # override kill switch so pipeline runs
        orig_token = self.config.bot_token
        self.config.bot_token = ""  # blank token → send_telegram_alert returns (False, not_configured)

        try:
            return self.process(trade_data, gaussian_model, scaler, neural_fn, candle_idx, timeframe)
        finally:
            self.config.enabled   = orig
            self.config.bot_token = orig_token


# ─────────────────────────────────────────────────────────────────────────────
# CONVENIENCE: standalone alert from raw scores (no model needed)
# ─────────────────────────────────────────────────────────────────────────────

def alert_from_scores(
    symbol:      str,
    expected_rr: float,
    confidence:  float,
    ml_score:    Optional[float] = None,
    regime:      str = "NEUTRAL",
    session:     str = "UNKNOWN",
    time_decay:  float = 1.0,
    config:      Optional[LiveEngineConfig] = None,
    timeframe:   str = "M15",
) -> dict:
    """
    Send a Telegram alert directly from pre-computed scores.
    Useful when Gaussian and ML inference are run outside LiveEngine.

    Returns result dict.
    """
    cfg = config or LiveEngineConfig.from_env()

    decision, reason = decide_trade(
        expected_rr = expected_rr,
        confidence  = confidence,
        ml_score    = ml_score,
        threshold   = cfg.rr_threshold,
        conf_min    = cfg.confidence_min,
        conf_strong = cfg.confidence_strong,
        ml_override = cfg.ml_override_threshold,
    )

    msg = format_alert_message(
        symbol       = symbol,
        expected_rr  = expected_rr,
        confidence   = confidence,
        decision     = decision,
        reason       = reason,
        ml_score     = ml_score,
        regime       = regime,
        session      = session,
        time_decay   = time_decay,
        timeframe    = timeframe,
    )

    sent, err = send_telegram_alert(msg, cfg.bot_token, cfg.chat_id)

    entry = {
        "timestamp":   time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "symbol":      symbol,
        "decision":    decision,
        "reason":      reason,
        "expected_rr": round(expected_rr, 4),
        "confidence":  round(confidence, 4),
        "ml_score":    round(ml_score, 4) if ml_score is not None else None,
        "sent":        sent,
        "suppressed_reason": None if sent else f"telegram_error: {err}",
    }
    _log_alert(entry)
    return entry


# ─────────────────────────────────────────────────────────────────────────────
# QUICK SELF-TEST
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)-8s %(message)s")

    print("\n=== LiveEngine self-test ===\n")

    # Test decision logic
    cases = [
        (1.8, 0.63, None,  "EXECUTE"),
        (1.8, 0.57, None,  "WARN"),
        (0.8, 0.72, None,  "BLOCK"),   # low RR, no ML
        (0.8, 0.72, 0.80,  "WATCH"),   # low RR but ML strong
        (1.5, 0.45, None,  "BLOCK"),   # low confidence
    ]
    all_pass = True
    for rr, conf, ml, expected in cases:
        dec, reason = decide_trade(rr, conf, ml)
        ok = dec == expected
        status = "✅" if ok else "❌"
        print(f"  {status} RR={rr:.1f} conf={conf:.2f} ml={ml} → {dec} ({reason}) [expected {expected}]")
        if not ok:
            all_pass = False

    print(f"\n  Decision logic: {'ALL PASS' if all_pass else 'FAILURES DETECTED'}")

    # Test message formatter
    msg = format_alert_message(
        symbol="BTCUSDT", expected_rr=1.72, confidence=0.67,
        decision="EXECUTE", reason="strong_setup",
        ml_score=0.71, probabilities=[0.18, 0.21, 0.35, 0.26],
        regime="EXPANSION", session="LONDON", time_decay=0.88,
    )
    print("\n  Sample alert message:")
    print("  " + "\n  ".join(msg.split("\n")))

    # Test schema validation guard in dry_run path
    print("\n  Schema validation test:")
    try:
        from dataset_builder import validate_feature_vector
        validate_feature_vector([0.0] * 9, "self_test")
        print("  ❌ ERROR: should have raised ValueError")
    except ValueError as e:
        print(f"  ✅ Schema guard correct: {str(e)[:70]}...")

    print("\n=== Self-test complete ===\n")