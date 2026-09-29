"""
telegram_bridge.py
================================================================================
TelegramBridge — real-time Forex signal alerts via Telegram Bot API.

Optional dependency: requests. If unavailable, all sends are no-ops (fail-open
per CONVENTIONS.md optional-import pattern). Telegram is a notification channel;
trading decisions are never gated on its availability.

Supported alert types
---------------------
  send_signal_alert   — new actionable signal (BUY/SELL) with SL/TP/RR
  send_kill_switch    — kill switch trip notification
  send_daily_summary  — end-of-day P&L summary

Config section: live_integration.telegram in production JSON.

EPIC-84 (user rule 2026-09-28): every key this class reads is DECLARED in
``live_integration.telegram`` and read exactly once — no code default and no
fallback. The environment is no longer a second source for the credentials:
``from_env()`` is the explicit legacy/research path and fails closed when
``TELEGRAM_BOT_TOKEN`` / ``TELEGRAM_CHAT_ID`` are absent.
================================================================================
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from config_layer.production_config import get_prod_section   # type: ignore
from config_layer.strict_config import (                        # type: ignore
    ConfigKeyMissingError,
    missing_keys,
    require,
    require_all,
)
from utils.logging_config import get_flow_logger               # type: ignore

_ENV_KEYS = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")

logger = get_flow_logger("LIVE_HOOK")

try:
    import requests as _requests
    _REQUESTS_AVAILABLE = True
except ImportError:
    _requests = None  # type: ignore[assignment]
    _REQUESTS_AVAILABLE = False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TelegramBridge:
    """
    Sends trade alerts to a Telegram Bot channel.

    Fail-open: any network/API error is logged as WARNING and swallowed.
    Never raises — Telegram is informational, not a trading gate.

    Config keys (live_integration.telegram) — ALL DECLARED, no code defaults
    ------------------------------------------------------------------------
    bot_token        str    — Bot API token (required for live sends)
    chat_id          str    — Target chat / channel ID (required for live sends)
    enabled          bool   — Master on/off switch
    timeout_s        int    — HTTP timeout in seconds
    dry_run          bool   — Log message only, no HTTP
    """

    _TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

    #: Every key this class reads from `live_integration.telegram` (EPIC-84: declared once).
    _CFG_KEYS = ("enabled", "bot_token", "chat_id", "timeout_s", "dry_run")

    def __init__(
        self,
        bot_token: str = "",
        chat_id: str = "",
        enabled: bool = True,
        timeout_s: int = 5,
        dry_run: bool = False,
    ) -> None:
        self._token   = bot_token
        self._chat_id = chat_id
        self._enabled = enabled and bool(bot_token) and bool(chat_id)
        self._timeout = timeout_s
        self._dry_run = dry_run

        if not _REQUESTS_AVAILABLE:
            logger.warning(
                "TelegramBridge: 'requests' not installed — all sends are no-ops."
            )

    @classmethod
    def from_env(cls, *, enabled: bool = True, timeout_s: int = 5, dry_run: bool = False) -> "TelegramBridge":
        """Build from TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID (legacy / research path).

        EPIC-84: the environment is read through the shared strict primitive. Both
        variables must be DECLARED in the environment — absence fails closed with
        ``ConfigKeyMissingError(section="env")`` instead of substituting ``""``.
        The supported construction path is ``from_prod_config()``.
        """
        import os
        missing = missing_keys(os.environ, _ENV_KEYS)
        if missing:
            raise ConfigKeyMissingError(
                missing, section="env", consumer="TelegramBridge.from_env",
            )
        return cls(
            bot_token=str(os.environ[_ENV_KEYS[0]]),
            chat_id=str(os.environ[_ENV_KEYS[1]]),
            enabled=enabled,
            timeout_s=timeout_s,
            dry_run=dry_run,
        )

    @classmethod
    def from_prod_config(cls) -> "TelegramBridge":
        """Build from the DECLARED ``live_integration.telegram`` section.

        EPIC-84: all five keys are required and read exactly once; a missing key
        raises ``ConfigKeyMissingError`` naming every key that is absent. The
        ``TELEGRAM_*`` environment fallback that used to shadow an empty JSON
        value is gone — the declared value is the only source.
        """
        section = get_prod_section("live_integration")
        tg = require(section, "telegram", section_name="live_integration",
                     consumer="TelegramBridge")
        cfg = require_all(tg, cls._CFG_KEYS, section_name="live_integration.telegram",
                          consumer="TelegramBridge")
        return cls(
            bot_token=str(cfg["bot_token"]),
            chat_id=str(cfg["chat_id"]),
            enabled=bool(cfg["enabled"]),
            timeout_s=int(cfg["timeout_s"]),
            dry_run=bool(cfg["dry_run"]),
        )

    # ── Public API ─────────────────────────────────────────────────────────────

    def send_signal_alert(
        self,
        pair: str,
        timeframe: str,
        signal: str,
        confidence: float,
        entry_price: float,
        sl_inr: float,
        tp_inr: float,
        rr_ratio: float,
        strategy_scores: Optional[dict] = None,
    ) -> bool:
        """Format and send a new BUY/SELL signal alert."""
        lines = [
            f"SIGNAL | {pair} {timeframe}",
            f"Action:     {signal}",
            f"Entry:      {entry_price:.5f}",
            f"Confidence: {confidence:.0%}",
            f"SL (INR):   {sl_inr:,.0f}",
            f"TP (INR):   {tp_inr:,.0f}",
            f"RR:         {rr_ratio:.2f}R",
            f"Time:       {_now_iso()}",
        ]
        if strategy_scores:
            top = sorted(strategy_scores.items(), key=lambda x: -x[1])[:3]
            lines.append("Top strategies: " + ", ".join(f"{s}={v:.2f}" for s, v in top))

        return self._send("\n".join(lines))

    def send_kill_switch(
        self,
        reason: str,
        daily_loss_inr: float,
        weekly_loss_inr: float,
        pair: str = "",
    ) -> bool:
        """Send an urgent kill switch trip notification."""
        lines = [
            "KILL SWITCH TRIPPED",
            f"Reason:      {reason.upper()} limit breached",
            f"Daily loss:  INR {daily_loss_inr:,.0f}",
            f"Weekly loss: INR {weekly_loss_inr:,.0f}",
            f"Pair:        {pair or 'ALL'}",
            f"Time:        {_now_iso()}",
            "Trading halted. Manual reset required.",
        ]
        return self._send("\n".join(lines))

    def send_daily_summary(
        self,
        trades: int,
        wins: int,
        daily_pnl_inr: float,
        weekly_pnl_inr: float,
    ) -> bool:
        """Send end-of-day P&L summary."""
        win_rate = (wins / trades * 100) if trades else 0.0
        sign = "+" if daily_pnl_inr >= 0 else ""
        lines = [
            "DAILY SUMMARY",
            f"Trades:      {trades}",
            f"Win rate:    {win_rate:.0f}%",
            f"Day P&L:     INR {sign}{daily_pnl_inr:,.0f}",
            f"Week P&L:    INR {weekly_pnl_inr:,.0f}",
            f"Time:        {_now_iso()}",
        ]
        return self._send("\n".join(lines))

    def send_research_alert(self, text: str) -> bool:
        """Send a free-form research / live_alert_v1 message (not a BUY/SELL signal).

        Same fail-open transport as other sends. Callers that must not hit the
        network should construct the bridge with dry_run=True (REM-TG-01).
        """
        return self._send(text)

    def is_configured(self) -> bool:
        return self._enabled and _REQUESTS_AVAILABLE

    # ── Private ────────────────────────────────────────────────────────────────

    def _send(self, text: str) -> bool:
        """POST message to Telegram. Returns True on success, False on any error."""
        if not self._enabled:
            logger.debug("TelegramBridge: disabled — skipping send.")
            return False

        if self._dry_run or not _REQUESTS_AVAILABLE:
            logger.info("TelegramBridge [DRY-RUN]: %s", text.replace("\n", " | "))
            return True

        url = self._TELEGRAM_API.format(token=self._token)
        payload = {
            "chat_id": self._chat_id,
            "text": text,
            "parse_mode": "HTML",
        }
        try:
            resp = _requests.post(url, json=payload, timeout=self._timeout)
            if resp.status_code == 200:
                logger.info("TelegramBridge: message sent successfully.")
                return True
            logger.warning(
                "TelegramBridge: API error %d — %s",
                resp.status_code, resp.text[:200],
            )
            return False
        except Exception as exc:
            logger.warning("TelegramBridge: send failed (network/timeout): %s", exc)
            return False
