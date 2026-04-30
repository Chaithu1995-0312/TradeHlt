"""
cli.py — CRT Trading Agent interactive REPL
─────────────────────────────────────────────────────────────────────────────
Usage:
    python -m src.agent.cli
    python -m src.agent.cli --resume ses_1234567890

The agent config is loaded from configs/production/v1_multi_2026_03.json
under the "agent" key. If absent, safe defaults are used.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure src/ on path when run as script
_SRC = str(Path(__file__).resolve().parent.parent)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import agent  # noqa: F401 — triggers modes import → tool registration


def _load_config() -> dict:
    try:
        from config_layer.production_config import get_prod_section
        return get_prod_section("agent")
    except (KeyError, RuntimeError):
        return {
            "enabled": True,
            "server_url": "http://127.0.0.1:8080/completion",
            "chat_max_tokens": 512,
            "chat_temperature": 0.2,
            "max_iterations_per_turn": 6,
            "intent_router": {
                "use_llm": True,
                "llm_confidence_floor": 0.6,
                "regex_fallback_table": "src/agent/prompts/intent_patterns.json",
            },
            "write_tools_enabled": [],
            "copilot_auto_narrate": False,
            "audit_log_path": "logs/agent_audit.jsonl",
            "session_dir": "logs/agent_sessions",
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="CRT Trading Agent CLI")
    parser.add_argument("--resume", metavar="SESSION_ID", help="Resume a prior session")
    args = parser.parse_args()

    config = _load_config()
    if not config.get("enabled", True):
        print("Agent disabled in config (agent.enabled=false).")
        sys.exit(0)

    from agent.agent_core import AgentCore
    from agent.state import AgentState

    core = AgentCore(config)

    if args.resume:
        try:
            core.state = AgentState.load(
                args.resume,
                session_dir=config.get("session_dir", "logs/agent_sessions"),
            )
            print(f"[resumed session {args.resume}]")
        except FileNotFoundError:
            print(f"[session {args.resume} not found — starting fresh]")

    print(f"CRT Agent  session={core.state.session_id}")
    print("Examples: 'tune EURUSD and promote if passes' | 'advise on BTCUSDT signal' | 'run governance'")
    print("Type 'exit' or Ctrl-C to quit.\n")

    while True:
        try:
            user_input = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if user_input.lower() in ("exit", "quit", "q"):
            break
        if not user_input:
            continue

        try:
            core.turn(user_input)
        except Exception as exc:
            print(f"[error] {exc}")
            logger_msg = f"Turn error: {exc}"
            import logging
            logging.getLogger("AgentCLI").exception(logger_msg)

    print(f"\nSession {core.state.session_id} saved to {config.get('session_dir')}.")


if __name__ == "__main__":
    main()
