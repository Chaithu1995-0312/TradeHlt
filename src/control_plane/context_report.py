"""
context_report.py — ContextReportAPI: Claude-powered operational intelligence for runs.

Follows RunReportAPI pattern exactly:
  - Stateless class, instantiated once in ControlPlaneServer.__init__
  - No src.* imports — operates on raw dicts passed from server routes
  - Optional-import guard for the `anthropic` package
  - Reads ANTHROPIC_API_KEY from .env / environment

Returns structured sections: root_cause, architecture_notes, artifact_analysis,
recommendations (list) — not a chatbot, an operational intelligence engine.
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
You are an operational intelligence engine for a quantitative trading system.
You will receive the execution context of a completed pipeline run (metadata, logs,
artifacts, and the specific code that ran) and must return a structured JSON object.

Return ONLY valid JSON — no preamble, no markdown fences, no explanation.
The JSON must have exactly these four keys:
  "root_cause"         — string: concise explanation of why the run succeeded or failed
  "architecture_notes" — string: any structural observations about the code flow or architecture
  "artifact_analysis"  — string: status of expected artifacts (present / missing / unexpected)
  "recommendations"    — list of strings: ordered next actions for the operator (most important first)

Be factual and specific — reference actual values from the logs where present.
Keep each value concise (2-5 sentences or items max)."""


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

    return "\n".join(parts)


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
    ) -> dict[str, Any]:
        """
        Build execution context prompt, send to Claude, parse structured JSON response.

        Returns:
            {"ok": True,  "sections": {...}, "model": str, "code_context_count": int}
            {"ok": False, "error": str}
        """
        _load_dotenv()
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            return {
                "ok": False,
                "error": "ANTHROPIC_API_KEY not set in environment (add to .env or export)",
            }

        try:
            import anthropic  # optional-import guard
        except ImportError:
            return {
                "ok": False,
                "error": "anthropic package not installed. Run: pip install anthropic",
            }

        prompt = _build_prompt(run, logs, artifacts, code_context)

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

        # Strip markdown fences if Claude wraps the JSON
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
            # Return raw text so the UI can still display something useful
            return {
                "ok": True,
                "sections": {
                    "root_cause":         raw,
                    "architecture_notes": "",
                    "artifact_analysis":  "",
                    "recommendations":    [],
                },
                "model":               _MODEL,
                "code_context_count":  len(code_context),
                "parse_warning":       f"JSON decode failed ({exc}); showing raw response",
            }

        # Normalise: recommendations must be a list
        recs = sections.get("recommendations", [])
        if isinstance(recs, str):
            recs = [r.strip() for r in recs.splitlines() if r.strip()]
            sections["recommendations"] = recs

        return {
            "ok":                 True,
            "sections":           sections,
            "model":              _MODEL,
            "code_context_count": len(code_context),
        }
