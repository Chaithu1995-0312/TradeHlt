"""
context_report.py — ContextReportAPI: Claude-powered ARCHITECTURE ANALYST for runs.

Follows RunReportAPI pattern exactly:
  - Stateless class, instantiated once in ControlPlaneServer.__init__
  - No src.* imports — operates on raw dicts passed from server routes
  - Optional-import guard for the `anthropic` package
  - Reads ANTHROPIC_API_KEY from .env / environment

Consumes the flow-context layer (`dot_graph_context`): the run's flow slice + dependency edges
feed an architecture-analyst prompt that situates the executed code in its subsystem and reasons
about impact radius — NOT a debugger, NOT a bug hunt. Dependency edges are architectural
("A depends on B"), never runtime order. Returns five structured sections: executive_summary,
architecture_notes, code_flow, impact_radius, structural_observations.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 1_024
_TEMPERATURE = 0.1

# Token budget: haiku 200 k context, but we aim for ~4 500 tokens total input.
_STDOUT_CHARS = 3_000
_STDERR_CHARS = 1_500
_CODE_CHARS_PER_SYMBOL = 2_000   # per extracted code block

_REPO_ROOT = Path(__file__).resolve().parents[2]

_SYSTEM_PROMPT = """\
You are an ARCHITECTURE ANALYST and code auditor for a quantitative trading system.
Your purpose is to explain how the system is structured, how components interact, and how a
change would propagate. You are NOT a debugger, NOT a style reviewer, and you do NOT hunt for
bugs. Focus on architecture, flows, dependencies, contracts, and impact radius.

You receive the execution context of a completed pipeline run: its flow (a curated subset of the
system), a dependency-graph slice, the flow manifest, the specific code that ran, logs, artifacts,
and runtime metadata. Treat these as authoritative.

HARD RULE — dependency edges are ARCHITECTURAL, not runtime:
  A dependency edge "A -> B" means "A depends on B" — NOT "A calls B", NOT "A executes before B".
  These are import/architectural relationships, never runtime order. Never infer execution order
  from imports. Use only this vocabulary: depends on, imported by, upstream, downstream, impact
  radius, architectural boundary.

FORBIDDEN LANGUAGE: avoid phrases such as "calls", "executes before", or "causes" when they are
inferred solely from dependency edges. Describe the relationship architecturally instead.

Return ONLY valid JSON — no preamble, no markdown fences, no explanation.
The JSON must have exactly these five keys:
  "executive_summary"       — string: what ran and the purpose of the executed code.
  "architecture_notes"      — string: subsystem responsibilities and boundaries; how the modules
                              fit into the overall architecture.
  "code_flow"               — string: architectural narration of how the executed modules fit the
                              larger subsystem, using the flow slice + dependency edges (ARCHITECTURAL,
                              not runtime order). Cover: modules depending on the current module ->
                              the current module -> modules it depends on; subsystem boundaries,
                              responsibilities, information movement, impact radius. Use graph notation
                              such as "FeaturePipeline -> EngineRunner -> DecisionEngine -> UltronRiskGate".
                              Only describe runtime sequencing when explicit evidence exists; never infer
                              execution order from imports. No bug hunting, no fixes.
  "impact_radius"           — string: modules importing this code, modules it imports, neighboring
                              subsystems, and likely propagation paths if it changed.
  "structural_observations" — string: Structural observations are DESCRIPTIVE, not prescriptive.
                              Examples: orchestration hubs, high fan-in modules, high fan-out modules,
                              coupling patterns, subsystem boundaries, isolated components. Do NOT suggest
                              fixes. Do NOT recommend improvements. Do NOT speculate about defects.

REMINDER (do not forget): "A -> B" means "A depends on B", NOT "A calls B" and NOT "A executes
before B". Reason about architecture and impact radius, never about runtime order inferred from imports.

Be factual and specific — reference actual module names and values from the provided context.
Keep each value concise (2-5 sentences max)."""


def _load_dotenv() -> None:
    env_path = _REPO_ROOT / ".env"
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val
    except Exception:
        pass


def _build_prompt(
    run: dict[str, Any],
    logs: dict[str, str],
    artifacts: list[dict[str, Any]],
    code_context: list[dict[str, Any]],
    graph_context: dict[str, Any] | None = None,
) -> str:
    parts: list[str] = []

    # ── Run metadata ──────────────────────────────────────────────────────────
    started  = run.get("started_at", "")
    ended    = run.get("ended_at", "")
    if started and ended:
        try:
            from datetime import datetime
            dur_s = (
                datetime.fromisoformat(ended) - datetime.fromisoformat(started)
            ).total_seconds()
            duration = f"{int(dur_s)}s"
        except Exception:
            duration = "unknown"
    else:
        duration = "unknown"

    args_str = "  ".join(f"{k}={v}" for k, v in (run.get("args") or {}).items())
    cmdline  = " ".join(run.get("command_line") or run.get("cmdline", "").split())

    parts.append("=== RUN METADATA ===")
    parts.append(f"command   : {run.get('command_id', '')}")
    parts.append(f"status    : {run.get('status', '')}  exit_code={run.get('exit_code', '')}")
    parts.append(f"duration  : {duration}")
    parts.append(f"cli       : {cmdline}")
    if args_str:
        parts.append(f"args      : {args_str}")
    if run.get("error"):
        parts.append(f"error     : {run['error']}")

    # ── Stdout ────────────────────────────────────────────────────────────────
    stdout = (logs.get("stdout") or "").strip()
    parts.append("\n=== STDOUT (last chars) ===")
    if stdout:
        tail = stdout[-_STDOUT_CHARS:]
        if len(stdout) > _STDOUT_CHARS:
            parts.append(f"[truncated — showing last {_STDOUT_CHARS} chars]")
        parts.append(tail)
    else:
        parts.append("(empty)")

    # ── Stderr ────────────────────────────────────────────────────────────────
    stderr = (logs.get("stderr") or "").strip()
    parts.append("\n=== STDERR (last chars) ===")
    if stderr:
        tail = stderr[-_STDERR_CHARS:]
        if len(stderr) > _STDERR_CHARS:
            parts.append(f"[truncated — showing last {_STDERR_CHARS} chars]")
        parts.append(tail)
    else:
        parts.append("(empty)")

    # ── Artifacts ─────────────────────────────────────────────────────────────
    parts.append("\n=== ARTIFACTS ===")
    if artifacts:
        parts.append(f"{'path':<60}  exists   size")
        parts.append("-" * 80)
        for a in artifacts:
            parts.append(
                f"{str(a.get('path','')):<60}  {str(a.get('exists','')):<7}  {a.get('size','')}"
            )
    else:
        parts.append("(none)")

    # ── Code context ──────────────────────────────────────────────────────────
    if code_context:
        parts.append("\n=== EXECUTED CODE CONTEXT ===")
        for sym in code_context:
            rel = sym.get("file", "")
            try:
                rel = str(Path(rel).relative_to(_REPO_ROOT))
            except ValueError:
                pass
            parts.append(f"\n[{rel} | {sym.get('kind','def')} {sym.get('symbol','')} | line {sym.get('start_line','')}]")
            code = sym.get("code", "")[:_CODE_CHARS_PER_SYMBOL]
            parts.append(f"```python\n{code}\n```")
    else:
        parts.append("\n=== EXECUTED CODE CONTEXT ===")
        parts.append("(no code context extracted — script path not found or AST parse failed)")

    # ── Pipeline flow (dependency graph slice) ────────────────────────────────
    # Edges are ARCHITECTURAL: "A depends on B" (import), never runtime order.
    gc = graph_context or {}
    if gc.get("available"):
        flow = gc.get("flow")
        if flow:
            parts.append(f"\n=== PIPELINE FLOW ({flow}) ===")
            parts.append(f"flow      : {flow} — {gc.get('title', flow)}")
            if gc.get("doc"):
                parts.append(f"flow doc  : {gc['doc']}")
        else:
            parts.append("\n=== PIPELINE FLOW (global neighbourhood) ===")
            parts.append("(no curated flow matched — showing the 1-hop dependency neighbourhood)")
        touched = gc.get("touched_modules") or []
        if touched:
            parts.append(f"executed modules: {', '.join(touched)}")
        parts.append("dependency edges (\"A depends on B\" — architectural, NOT runtime order):")
        edges = gc.get("edges") or []
        for src, dst in edges:
            parts.append(f"  {src} depends on {dst}")
        if not edges:
            parts.append("  (no edges in slice)")
    else:
        parts.append("\n=== PIPELINE FLOW ===")
        parts.append("(flow graph unavailable — analyse from executed code + logs only)")

    return "\n".join(parts)


_FLOW_KEYS = ("executive_summary", "architecture_notes", "code_flow",
              "impact_radius", "structural_observations")


def _parse_sections(raw: str, code_context: list[dict[str, Any]],
                    graph_context: dict[str, Any] | None, model: str) -> dict[str, Any]:
    """Strip markdown fences, parse the 5-key analyst JSON, coerce values to strings.

    Shared by the `api` and `local`/`groq` providers so every backend yields the same shape.
    """
    # Strip a ```json … ``` fence if the model wrapped the JSON.
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
        if raw.endswith("```"):
            raw = raw[:-3].strip()

    try:
        sections = json.loads(raw)
    except json.JSONDecodeError as exc:
        return {
            "ok": True,
            "sections": {k: (raw if k == "executive_summary" else "") for k in _FLOW_KEYS},
            "model": model,
            "code_context_count": len(code_context),
            "graph_context": graph_context,
            "parse_warning": f"JSON decode failed ({exc}); showing raw response",
        }

    # The 5 analyst keys are strings — coerce a stray list/None defensively.
    for key in _FLOW_KEYS:
        val = sections.get(key, "")
        if isinstance(val, list):
            sections[key] = "\n".join(f"- {v}" for v in val)
        elif not isinstance(val, str):
            sections[key] = "" if val is None else str(val)

    return {
        "ok": True,
        "sections": sections,
        "model": model,
        "code_context_count": len(code_context),
        "graph_context": graph_context,
    }


class ContextReportAPI:
    """
    Stateless helper instantiated once in ControlPlaneServer.__init__.

    Public method:
        context_analysis(run, logs, artifacts, code_context) → dict
    """

    def context_analysis(
        self,
        run: dict[str, Any],
        logs: dict[str, str],
        artifacts: list[dict[str, Any]],
        code_context: list[dict[str, Any]],
        graph_context: dict[str, Any] | None = None,
        provider: str = "export",
        llm_caller: "Any" = None,
    ) -> dict[str, Any]:
        """
        Build the architecture-analyst prompt and produce the 5-section report.

        `provider` selects who answers the prompt (zero-cost by default):
          - "export" (default): NO LLM call — returns the prompt + system for pasting into Claude
            Code (use your subscription, not metered API). `source="export"`.
          - "local" / "groq": call the injected `llm_caller(system, prompt) -> str` (the server wires
            this over `llm_inference_client.llm_chat`: BitNet-local → Groq free-tier). Keeps this
            module free of `src.*` imports.
          - "api": call the Anthropic API (`claude-haiku-4-5`) — metered; only if ANTHROPIC_API_KEY.

        `graph_context` feeds the prompt's PIPELINE FLOW section and is surfaced in the response.
        Fail-open: when it is unavailable the analyst still runs on code + logs.
        """
        prompt = _build_prompt(run, logs, artifacts, code_context, graph_context)
        flow = (graph_context or {}).get("flow")

        # ── export: hand the prompt to Claude Code; no LLM call, no cost ──────────
        if provider == "export":
            return {
                "ok":                 True,
                "source":             "export",
                "system":             _SYSTEM_PROMPT,
                "prompt":             prompt,
                "flow":               flow,
                "code_context_count": len(code_context),
                "graph_context":      graph_context,
            }

        # ── local / groq: injected free LLM caller (no src.* import here) ─────────
        if provider in ("local", "groq"):
            if llm_caller is None:
                return {"ok": False, "error": f"provider '{provider}' requires an llm_caller"}
            try:
                raw = (llm_caller(_SYSTEM_PROMPT, prompt) or "").strip()
            except Exception as exc:
                return {"ok": False, "error": f"local/groq LLM error: {exc}"}
            if not raw:
                return {"ok": False, "error": f"provider '{provider}' returned no output "
                                              "(BitNet server down and/or GROQ_API_KEY unset)"}
            return _parse_sections(raw, code_context, graph_context, model=provider)

        # ── api: metered Anthropic call (opt-in) ─────────────────────────────────
        if provider == "api":
            _load_dotenv()
            api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
            if not api_key:
                return {"ok": False,
                        "error": "ANTHROPIC_API_KEY not set in environment (add to .env or export)"}
            try:
                import anthropic  # optional-import guard
            except ImportError:
                return {"ok": False,
                        "error": "anthropic package not installed. Run: pip install anthropic"}
            try:
                client = anthropic.Anthropic(api_key=api_key)
                message = client.messages.create(
                    model=_MODEL,
                    max_tokens=_MAX_TOKENS,
                    temperature=_TEMPERATURE,
                    system=_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": prompt}],
                )
                raw = message.content[0].text.strip()
            except Exception as exc:
                return {"ok": False, "error": f"Claude API error: {exc}"}
            return _parse_sections(raw, code_context, graph_context, model=_MODEL)

        return {"ok": False, "error": f"unknown context-report provider: {provider!r}"}
