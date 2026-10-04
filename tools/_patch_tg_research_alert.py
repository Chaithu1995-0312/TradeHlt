from pathlib import Path
p = Path("src/live/telegram_bridge.py")
t = p.read_text(encoding="utf-8")
if "def send_research_alert" in t:
    print("already has send_research_alert")
else:
    needle = "    def is_configured(self) -> bool:\n        return self._enabled and _REQUESTS_AVAILABLE"
    insert = '''    def send_research_alert(self, text: str) -> bool:
        """Send a free-form research / live_alert_v1 message (not a BUY/SELL signal).

        Same fail-open transport as other sends. Callers that must not hit the
        network should construct the bridge with dry_run=True (REM-TG-01).
        """
        return self._send(text)

    def is_configured(self) -> bool:
        return self._enabled and _REQUESTS_AVAILABLE'''
    if needle not in t:
        raise SystemExit("needle not found for send_research_alert")
    p.write_text(t.replace(needle, insert, 1), encoding="utf-8")
    print("TelegramBridge.send_research_alert added")
