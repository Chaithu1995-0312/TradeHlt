"""
cli.py — GrokAgenticAI interactive REPL
─────────────────────────────────────────────────────────────────────────────
Usage:
    python -m src.agent.cli
    python -m src.agent.cli --resume ses_1234567890
    python -m src.agent.cli --agent ops_doctor
    python -m src.agent.cli --agent campaign_runner

Product name: GrokAgenticAI
  Ask GrokAgenticAI to diagnose why BNBUSDT has no trades
  Ask GrokAgenticAI campaign for EURUSD until validate

Config: production JSON key "agent" (soft defaults if absent).
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
            "product_name": "GrokAgenticAI",
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
            "goal_loop": {
                "enabled": True,
                "specialists": ["ops_doctor", "campaign_runner"],
            },
        }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="GrokAgenticAI — multi-agent kitchen REPL (OpsDoctor, CampaignRunner, …)",
    )
    parser.add_argument("--resume", metavar="SESSION_ID", help="Resume a prior session")
    parser.add_argument(
        "--agent",
        metavar="SPECIALIST",
        choices=["ops_doctor", "campaign_runner", "truth_janitor"],
        help="Pin specialist for this session (prefix each turn)",
    )
    parser.add_argument(
        "-c", "--command",
        metavar="TEXT",
        help="Run one shot command then exit (non-interactive)",
    )
    args = parser.parse_args()

    config = _load_config()
    if not config.get("enabled", True):
        print("Agent disabled in config (agent.enabled=false).")
        sys.exit(0)

    from agent.agent_core import AgentCore
    from agent.grok_agentic import PRODUCT_NAME, help_banner, list_specialists
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

    print(f"{PRODUCT_NAME}  session={core.state.session_id}")
    specs = ", ".join(s.display_name for s in list_specialists())
    print(f"Specialists: {specs}")
    if args.agent:
        print(f"Pinned agent: {args.agent}")
    print("Say: Ask GrokAgenticAI <goal>  |  help  |  exit")
    print("Examples:")
    print("  Ask GrokAgenticAI OpsDoctor diagnose throughput on BNBUSDT")
    print("  Ask GrokAgenticAI CampaignRunner tune EURUSD until validate")
    print("  Ask GrokAgenticAI TruthJanitor run repo hygiene")
    print("  tune and promote EURUSD   (legacy linear plan)\n")

    def _maybe_pin(text: str) -> str:
        if not args.agent:
            return text
        # Avoid double-prefix if user already named the specialist
        low = text.lower()
        if args.agent.replace("_", " ") in low or args.agent in low:
            return text
        pin = {
            "ops_doctor": "OpsDoctor",
            "campaign_runner": "CampaignRunner",
            "truth_janitor": "TruthJanitor",
        }.get(args.agent, args.agent)
        return f"Ask GrokAgenticAI {pin} {text}"

    if args.command:
        try:
            core.turn(_maybe_pin(args.command.strip()))
        except Exception as exc:
            print(f"[error] {exc}")
            import logging
            logging.getLogger("AgentCLI").exception("Turn error: %s", exc)
            sys.exit(1)
        print(f"\nSession {core.state.session_id} saved to {config.get('session_dir')}.")
        return

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
        if user_input.lower() in ("help", "?", "agents"):
            print(help_banner())
            continue

        try:
            core.turn(_maybe_pin(user_input))
        except Exception as exc:
            print(f"[error] {exc}")
            import logging
            logging.getLogger("AgentCLI").exception("Turn error: %s", exc)

    print(f"\nSession {core.state.session_id} saved to {config.get('session_dir')}.")


if __name__ == "__main__":
    main()
