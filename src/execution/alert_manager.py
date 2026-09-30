# alert_manager.py — Signal notification (CLI + extensible to external channels)
#
# HARD RULES:
# - No auto-execution — alerts inform human; human decides
# - Logging is always the primary channel
# - External hooks (Telegram, webhook) are optional and injected
#
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Callable

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from config_layer.strict_config import missing_keys, missing_reason  # noqa: E402

log = logging.getLogger(__name__)

#: Per-trade values this module reads from the signal payload. Absence is not a
#: default: the alert is REJECTED with the keys named (EPIC-84 trade-time rule) —
#: never sent with a placeholder that could be mistaken for a real signal.
_REQUIRED_SIGNAL_KEYS = ("symbol", "action", "confidence", "rr", "risk")


class AlertManager:
    """
    Sends trade signal alerts to configured channels.

    Channels:
      - Always: Python logging (INFO level)
      - Optional: CLI print (stdout)
      - Optional: external_hook (callable for Telegram/webhook/etc.)

    Usage:
        # Basic (log only):
        am = AlertManager()
        am.send(signal)

        # With CLI output:
        am = AlertManager(print_to_stdout=True)

        # With Telegram hook:
        am = AlertManager(external_hook=telegram_send_fn)
    """

    def __init__(
        self,
        print_to_stdout: bool = False,
        external_hook: Optional[Callable] = None,
    ):
        self.print_to_stdout = print_to_stdout
        self.external_hook = external_hook

    def send(self, signal: dict) -> dict:
        """
        Send a trade signal alert through all configured channels.

        Args:
            signal: dict with required keys 'symbol', 'action', 'confidence', 'rr',
                'risk' (EPIC-84: no field is defaulted — an incomplete signal is
                REJECTED, never alerted on with a placeholder value)

        Returns:
            dict with keys: sent (bool), message (str), symbol (str)[, reason (str)
            when rejected]
        """
        absent = missing_keys(signal, _REQUIRED_SIGNAL_KEYS)
        if absent:
            reason = missing_reason("signal", absent)
            log.warning("AlertManager: signal REJECTED — %s", reason)
            return {"sent": False, "message": "", "symbol": signal.get("symbol", ""), "reason": reason}

        symbol     = signal["symbol"]
        action     = signal["action"]
        confidence = signal["confidence"]
        rr         = signal["rr"]
        risk       = signal["risk"]

        message = (
            f"TRADE SIGNAL | {symbol} | {action} | "
            f"conf={confidence:.2f} rr={rr:.2f} risk={risk:.4f}"
        )

        log.info("AlertManager: %s", message)

        if self.print_to_stdout:
            print(message)

        if self.external_hook is not None:
            try:
                self.external_hook(signal, message)
            except Exception as exc:
                log.warning("AlertManager: external_hook failed: %s", exc)

        return {"sent": True, "message": message, "symbol": symbol}
