"""
agent_core.py
─────────────────────────────────────────────────────────────────────────────
AgentCore — main turn loop for **GrokAgenticAI**.

Per turn:
  1. Strip "Ask GrokAgenticAI" brand prefix; detect specialist if present
  2. IntentRouter classifies NL input → {mode, intent_key}
  3. Specialist intents (OpsDoctor / CampaignRunner) → GoalLoop
  4. Legacy intents → PlanCompiler linear plan
  5. Write tools pause for y/N confirmation (Executor fences)
  6. Session summary + intent log written on close
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from .audit import AuditLogger
from .executor import Executor, PendingConfirmation
from .goal_loop import GoalLoop
from .grok_agentic import (
    INTENT_TO_SPECIALIST,
    PRODUCT_NAME,
    build_goal,
    detect_specialist,
    help_banner,
    strip_product_prefix,
)
from .intent_router import IntentRouter
from .plan_compiler import PlanCompiler
from .state import AgentState
from .tool_planner import ArgFiller

logger = logging.getLogger("AgentCore")

_SKIP_RULES = [
    (["skip tun", "no tun"],                              "tuner.run_multi"),
    (["skip backtest", "no backtest"],                    "backtest.run_v2"),
    (["skip live", "no live"],                            "live_hook.dry_run"),
    (["skip promot", "no promot", "just validate"],       "promotion.promote_from_checkpoint"),
    (["skip valid", "no valid"],                          "validator.validate"),
]


class AgentCore:
    def __init__(self, config: dict):
        self._cfg = config
        audit_path  = config.get("audit_log_path", "logs/agent_audit.jsonl")
        intent_path = "logs/agent_intent_log.jsonl"
        self._session_dir = config.get("session_dir", "logs/agent_sessions")
        self._max_iters   = config.get("max_iterations_per_turn", 6)

        self.audit  = AuditLogger(audit_path=audit_path, intent_path=intent_path)
        self.state  = AgentState()
        self.executor = Executor(
            state=self.state,
            audit=self.audit,
            write_tools_enabled=config.get("write_tools_enabled", []),
        )

        ir_cfg = config.get("intent_router", {})
        self.intent_router = IntentRouter(
            llm_chat_fn=self._llm_chat,
            patterns_path=ir_cfg.get("regex_fallback_table", "src/agent/prompts/intent_patterns.json"),
            use_llm=ir_cfg.get("use_llm", True),
            confidence_floor=ir_cfg.get("llm_confidence_floor", 0.6),
        )
        self.arg_filler = ArgFiller(llm_chat_fn=self._llm_chat)

    @staticmethod
    def _llm_chat(messages, **kwargs):
        from config_layer.llm_inference_client import llm_chat
        return llm_chat(messages, **kwargs)

    # ── Public API ────────────────────────────────────────────────────────────

    def turn(self, user_input: str) -> str:
        """Process one user turn. Returns agent response string."""
        t0 = time.monotonic()
        self.state.add_message("user", user_input)

        raw = user_input.strip()
        lower = raw.lower()
        if lower in ("help", "?", "agents", "specialists", PRODUCT_NAME.lower()):
            return self._reply(help_banner())

        body = strip_product_prefix(raw)
        specialist_key = detect_specialist(raw) or detect_specialist(body)

        # 1. Classify intent (on body so brand prefix does not confuse regex)
        classification = self.intent_router.classify(body or raw, self.state.messages)
        intent_key     = classification.get("intent_key", "ask_user")
        mode           = classification.get("mode")

        # Specialist forces intent when NL named the agent clearly
        if specialist_key and specialist_key in (
            "ops_doctor",
            "campaign_runner",
            "truth_janitor",
        ):
            forced = {
                "ops_doctor": "ops_diagnose",
                "campaign_runner": "campaign_run",
                "truth_janitor": "truth_janitor",
            }[specialist_key]
            intent_key = forced
            mode = {
                "ops_doctor": "ops",
                "campaign_runner": "pipeline",
                "truth_janitor": "truth",
            }[specialist_key]

        if intent_key == "ask_user" and specialist_key is None:
            msg = (
                f"{PRODUCT_NAME} — need more detail.\n"
                f"{help_banner()}\n"
                "Legacy: tune / validate / promote / backtest | advise signal | governance run"
            )
            return self._reply(msg)

        # 2. Update state
        self.state.mode       = mode
        self.state.intent_key = intent_key
        self.state.plan_id    = f"{self.state.session_id}_p{int(time.time())}"

        # 3. GrokAgenticAI specialist path (GoalLoop)
        if intent_key in INTENT_TO_SPECIALIST:
            return self._turn_goal(raw, body or raw, intent_key, t0)

        # 4. Legacy linear plan
        plan = PlanCompiler.build(intent_key)
        skip = self._parse_skip(user_input)
        if skip:
            plan = PlanCompiler.filter(plan, skip)

        if not plan.steps:
            return self._reply("Nothing to execute after applying skip constraints.")

        steps_str = " → ".join(s.tool for s in plan.steps)
        print(f"\n{PRODUCT_NAME}: plan={{{steps_str}}}")

        results: List[Tuple[str, Any]] = []
        write_confirmed = False

        for i, step in enumerate(plan.steps):
            if i >= self._max_iters:
                print(f"  [max_iterations={self._max_iters} reached]")
                break

            from agent.tool_registry import REGISTRY
            spec = REGISTRY.get(step.tool)
            if spec is None:
                print(f"  step {i+1} {step.tool} — UNKNOWN TOOL, skipping")
                continue

            filled = self.arg_filler.fill(
                tool_name=step.tool,
                args_schema=spec.args_schema,
                current_args=dict(step.default_args),
                conversation=self.state.messages,
            )
            if filled.get("clarify"):
                return self._reply(filled["clarify"])

            args = filled["args"]
            print(f"  step {i+1}/{len(plan.steps)} {step.tool}...", end=" ", flush=True)

            result = self.executor.dispatch(step.tool, args, confirmed=False)

            if isinstance(result, PendingConfirmation):
                print(f"\n{result.preview}")
                confirm = input("  Confirm? y/N: ").strip().lower()
                if confirm == "y":
                    write_confirmed = True
                    result = self.executor.dispatch(step.tool, args, confirmed=True)
                    print("  confirmed.")
                else:
                    self.executor.dispatch_denied(step.tool, args)
                    print("  denied.")
                    break
            elif isinstance(result, str) and result.startswith("REFUSED:"):
                print(f"\n  {result}")
                break
            else:
                print("done")

            results.append((step.tool, result))

        total_ms = int((time.monotonic() - t0) * 1000)
        metrics  = self._extract_metrics(results)
        outcome  = self._derive_outcome(plan.steps)

        self.audit.write_session_summary(
            session_id=self.state.session_id,
            plan_id=self.state.plan_id,
            intent=user_input,
            intent_key=intent_key,
            mode=mode,
            plan_steps=[s.tool for s in plan.steps],
            outcome=outcome,
            metrics=metrics,
            write_confirmed=write_confirmed,
            total_latency_ms=total_ms,
        )

        summary = self._build_summary(results, outcome)
        return self._reply(summary)

    def _turn_goal(self, raw: str, body: str, intent_key: str, t0: float) -> str:
        """Run OpsDoctor / CampaignRunner via GoalLoop."""
        from agent.tool_registry import REGISTRY
        from .grok_agentic import extract_instruments

        specialist_key = INTENT_TO_SPECIALIST[intent_key]
        instruments = extract_instruments(body) or extract_instruments(raw)
        goal = build_goal(
            specialist_key,
            objective=body,
            instruments=instruments,
            context={
                "include_promote": "promot" in body.lower(),
                "include_backtest": not any(
                    p in body.lower() for p in ("skip backtest", "no backtest")
                ),
            },
        )
        self.state.mode_context["goal"] = goal.to_dict()
        print(
            f"\n{PRODUCT_NAME}/{goal.specialist}: goal_id={goal.goal_id} "
            f"kind={goal.kind} instruments={goal.instruments or ['—']}"
        )

        def _fill(tool_name: str, schema: dict, defaults: dict) -> dict:
            return self.arg_filler.fill(
                tool_name=tool_name,
                args_schema=schema,
                current_args=dict(defaults),
                conversation=self.state.messages,
            )

        def _schema(tool_name: str) -> Optional[dict]:
            spec = REGISTRY.get(tool_name)
            return spec.args_schema if spec else None

        loop = GoalLoop(
            dispatch=self.executor.dispatch,
            dispatch_denied=self.executor.dispatch_denied,
            fill_args=_fill,
            get_tool_schema=_schema,
        )
        gr = loop.run(goal)

        # Enrich incident pack with prior metrics if last step was pack-only
        total_ms = int((time.monotonic() - t0) * 1000)
        metrics = dict(gr.metrics)
        metrics["goal_id"] = goal.goal_id
        metrics["specialist"] = goal.specialist
        metrics["product"] = PRODUCT_NAME

        self.audit.write_session_summary(
            session_id=self.state.session_id,
            plan_id=self.state.plan_id,
            intent=raw,
            intent_key=intent_key,
            mode=self.state.mode,
            plan_steps=gr.steps_run,
            outcome=gr.outcome,
            metrics=metrics,
            write_confirmed=gr.write_confirmed,
            total_latency_ms=total_ms,
            _ctx={"goal_id": goal.goal_id, "specialist": goal.specialist, "product": PRODUCT_NAME},
        )
        return self._reply(gr.summary)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _reply(self, msg: str) -> str:
        print(f"\n  {msg}")
        self.state.add_message("assistant", msg)
        self.state.save(self._session_dir)
        return msg

    def _parse_skip(self, text: str) -> set:
        skip = set()
        t = text.lower()
        for phrases, tool in _SKIP_RULES:
            if any(p in t for p in phrases):
                skip.add(tool)
        return skip

    def _extract_metrics(self, results: List[Tuple[str, Any]]) -> dict:
        metrics: Dict[str, Any] = {}
        for _, res in results:
            if isinstance(res, dict):
                for k in ("fitness", "trades", "win_rate", "drawdown",
                          "max_drawdown_pct", "expectancy_rr", "approved_trades"):
                    if k in res:
                        metrics[k] = res[k]
        return metrics

    def _derive_outcome(self, steps) -> str:
        outcomes = [tc.outcome for tc in self.state.tool_calls[-len(steps):]]
        if not outcomes:
            return "no_op"
        if "denied" in outcomes:
            return "denied"
        if all(o == "success" for o in outcomes):
            return "success"
        if any(o == "success" for o in outcomes):
            return "partial"
        return "fail"

    def _build_summary(self, results: List[Tuple[str, Any]], outcome: str) -> str:
        completed = [tool for tool, _ in results]
        if not completed:
            return f"No steps completed. Session {self.state.session_id}."
        return (
            f"Completed [{outcome}]: {' → '.join(completed)}. "
            f"Session {self.state.session_id}."
        )
