# alert_manager.py — Signal notification (CLI + extensible to external channels)
#
# HARD RULES:
# - No auto-execution — alerts inform human; human decides
# - Logging is always the primary channel
# - External hooks (Telegram, webhook) are optional and injected
#
import logging
from datetime import datetime, timezone
from typing import Optional, Callable

log = logging.getLogger(__name__)


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
            signal: dict with at minimum 'symbol', 'action', 'confidence', 'rr'

        Returns:
            dict with keys: sent (bool), message (str), symbol (str)
        """
        symbol     = signal.get("symbol",     "?")
        action     = signal.get("action",     "?")
        confidence = signal.get("confidence", 0.0)
        rr         = signal.get("rr",         0.0)
        risk       = signal.get("risk",        0.0)

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
