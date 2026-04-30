# ARCHIVED 2026-04-28 — Dead Code Pass
# Reason: no runner, no callers, no tests — pure stub; Flask dashboard never launched in production.
# Original: src/ui/dashboard.py
# Action required on original: remove src/ui/dashboard.py (src/ui/__init__.py left in place)
# dashboard.py — minimal Flask REST dashboard for signal/position visibility
#
# Endpoints:
#   GET /signals    — last N signals
#   GET /positions  — open positions
#   GET /status     — system state
#   POST /pause     — pause execution loop
#   POST /resume    — resume execution loop
#
import logging
import json

log = logging.getLogger(__name__)

_state = {
    "signals": [],
    "positions": [],
    "paused": False,
    "running": True,
}


def get_state() -> dict:
    return _state


def update_state(key: str, value) -> None:
    _state[key] = value


def create_app(state: dict = None):
    try:
        from flask import Flask, jsonify, request
    except ImportError:
        log.error("Flask not installed. Run: pip install flask")
        raise

    app_state = state if state is not None else _state
    app = Flask(__name__)

    @app.route("/signals")
    def signals():
        return jsonify(app_state.get("signals", []))

    @app.route("/positions")
    def positions():
        return jsonify(app_state.get("positions", []))

    @app.route("/status")
    def status():
        return jsonify({
            "paused": app_state.get("paused", False),
            "running": app_state.get("running", True),
            "signal_count": len(app_state.get("signals", [])),
            "position_count": len(app_state.get("positions", [])),
        })

    @app.route("/pause", methods=["POST"])
    def pause():
        app_state["paused"] = True
        log.warning("Dashboard: system PAUSED via API")
        return jsonify({"status": "paused"})

    @app.route("/resume", methods=["POST"])
    def resume():
        app_state["paused"] = False
        log.info("Dashboard: system RESUMED via API")
        return jsonify({"status": "running"})

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=False)
