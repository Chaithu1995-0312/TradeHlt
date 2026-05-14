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
from utils.logging_config import get_flow_logger               # type: ignore

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

    Config keys (live_integration.telegram)
    ----------------------------------------
    bot_token        str    — Bot API token (required for live sends)
    chat_id          str    — Target chat / channel ID (required for live sends)
    enabled          bool   — Master on/off switch (default True)
    timeout_s        int    — HTTP timeout in seconds (default 5)
    dry_run          bool   — Log message only, no HTTP (default False)
    """

    _TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

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
    def from_prod_config(cls) -> "TelegramBridge":
        cfg = ((get_prod_section("live_integration") or {})
               .get("telegram", {}))
        return cls(
            bot_token = str(cfg.get("bot_token", "")),
            chat_id   = str(cfg.get("chat_id", "")),
            enabled   = bool(cfg.get("enabled", True)),
            timeout_s = int(cfg.get("timeout_s", 5)),
            dry_run   = bool(cfg.get("dry_run", False)),
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
