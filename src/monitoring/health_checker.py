"""
health_checker.py
================================================================================
HealthChecker — lightweight stdlib HTTP health endpoint on port 8788.

GET /health        JSON with system status (always 200)
GET /status        JSON with detailed component status (always 200)

Designed for liveness/readiness probes in Docker and Kubernetes.
No third-party deps — uses stdlib http.server only.

Usage
-----
    # Run standalone:
    python -m monitoring.health_checker

    # Import and embed:
    from monitoring.health_checker import HealthChecker
    checker = HealthChecker(port=8788)
    checker.start_background()   # starts daemon thread

Config: live_integration section read for kill switch state.
================================================================================
"""

from __future__ import annotations

import json
import sys
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from utils.logging_config import get_flow_logger  # type: ignore

logger = get_flow_logger("LIVE_HOOK")

_DEFAULT_PORT = 8788


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _collect_status() -> dict:
    """Build the status payload. Never raises — errors are reported in-payload."""
    status: dict = {
        "ts":          _now_iso(),
        "service":     "tradelatest",
        "overall":     "ok",
        "components":  {},
    }

    # Production config version
    try:
        from config_layer.production_config import get_prod_metadata  # type: ignore
        meta = get_prod_metadata() or {}
        status["components"]["config"] = {
            "version": meta.get("version", "unknown"),
            "hash":    (meta.get("config_hash") or "")[:16],
            "status":  "ok",
        }
    except Exception as exc:
        status["components"]["config"] = {"status": "error", "detail": str(exc)}
        status["overall"] = "degraded"

    # Kill switch
    try:
        from uat.kill_switch import KillSwitch  # type: ignore
        ks = KillSwitch.from_prod_config()
        tripped = ks.is_tripped()
        status["components"]["kill_switch"] = {
            "tripped":         tripped,
            "trip_reason":     ks.trip_reason(),
            "daily_loss_inr":  round(ks.daily_loss_inr(), 2),
            "weekly_loss_inr": round(ks.weekly_loss_inr(), 2),
            "status":          "tripped" if tripped else "ok",
        }
        if tripped:
            status["overall"] = "halted"
    except Exception as exc:
        status["components"]["kill_switch"] = {"status": "unavailable", "detail": str(exc)}

    # Strategy orchestrator importability
    try:
        from strategies.strategy_orchestrator import StrategyOrchestrator  # type: ignore
        status["components"]["orchestrator"] = {"status": "ok", "strategies": 10}
    except Exception as exc:
        status["components"]["orchestrator"] = {"status": "unavailable", "detail": str(exc)}
        status["overall"] = "degraded"

    # Telegram bridge
    try:
        from live.telegram_bridge import TelegramBridge  # type: ignore
        tg = TelegramBridge.from_prod_config()
        status["components"]["telegram"] = {
            "configured": tg.is_configured(),
            "status":     "ok",
        }
    except Exception as exc:
        status["components"]["telegram"] = {"status": "unavailable", "detail": str(exc)}

    # MT5 bridge
    try:
        from live.mt5_bridge import MT5Bridge  # type: ignore
        mt5 = MT5Bridge.from_prod_config()
        status["components"]["mt5"] = {
            "dry_run": mt5._dry_run,
            "status":  "ok",
        }
    except Exception as exc:
        status["components"]["mt5"] = {"status": "unavailable", "detail": str(exc)}

    return status


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path in ("/health", "/"):
            body = json.dumps({"status": "ok", "ts": _now_iso()}).encode()
        elif self.path == "/status":
            body = json.dumps(_collect_status(), indent=2).encode()
        else:
            self.send_response(404)
            self.end_headers()
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:  # noqa: ANN001
        logger.debug("HealthChecker: " + fmt, *args)


class HealthChecker:
    """
    Runs a minimal HTTP server exposing /health and /status endpoints.
    """

    def __init__(self, port: int = _DEFAULT_PORT) -> None:
        self._port   = port
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start_background(self) -> None:
        """Start server in a daemon thread (non-blocking)."""
        self._server = HTTPServer(("0.0.0.0", self._port), _Handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
            name="health-checker",
        )
        self._thread.start()
        logger.info(
            "HealthChecker: listening on port %d (/health /status)", self._port
        )

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server = None

    def collect_status(self) -> dict:
        """Public access to status payload (for tests)."""
        return _collect_status()


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Tradelatest health checker")
    parser.add_argument("--port", type=int, default=_DEFAULT_PORT)
    args = parser.parse_args()

    checker = HealthChecker(port=args.port)
    print(f"HealthChecker: starting on port {args.port} — Ctrl-C to stop")
    server = HTTPServer(("0.0.0.0", args.port), _Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nHealthChecker: stopped.")


if __name__ == "__main__":
    main()
