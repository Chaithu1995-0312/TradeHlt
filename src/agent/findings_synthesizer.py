"""
findings_synthesizer.py — Post-run findings via Groq Llama-3.1-70B
─────────────────────────────────────────────────────────────────────────────
Pulls run record + log tails + relevant source slice, sends a redacted
prompt to GroqClient, and appends a structured finding to
``logs/agent_findings.jsonl``.

Invoked on demand by the ``findings.synthesize`` tool. Not run on a
background poller — see plan §"Alert trigger: On-demand only".

Finding line schema:
  {ts, run_id, command_id, status, summary, anomalies[], recommended_next[],
   prompt_hash, response_hash, model, latency_ms, error}

Never raises. On any failure, appends a finding with ``status="synthesis_unavailable"``
and an explanatory ``error`` field, so the audit chain stays unbroken.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("FindingsSynthesizer")

_FINDINGS_LOG = "logs/agent_findings.jsonl"
_DEFAULT_LOG_TAIL = 200
_DEFAULT_MAX_SOURCE_CHARS = 8000


# ── helpers ──────────────────────────────────────────────────────────────────
def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _hash16(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", errors="replace")).hexdigest()[:16]


def _tail_text(path: str | None, lines: int) -> str:
    if not path:
        return ""
    p = Path(path)
    if not p.exists() or not p.is_file():
        return ""
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            buf = f.readlines()
        return "".join(buf[-lines:])
    except Exception as exc:
        logger.debug("tail %s failed: %s", path, exc)
        return ""


def _source_slice(script_path: str | None, max_chars: int) -> tuple[str, str]:
    """
    Return (head, tail) text from a script file — head=first 200 lines,
    tail=last 100 lines, each capped at max_chars/2.
    """
    if not script_path:
        return "", ""
    # registry stores POSIX-relative; resolve from repo root
    candidates = [Path(script_path), Path("D:/Tradelatest") / script_path]
    src = next((c for c in candidates if c.exists() and c.is_file()), None)
    if src is None:
        return "", ""
    try:
        with open(src, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
    except Exception as exc:
        logger.debug("read %s failed: %s", script_path, exc)
        return "", ""

    head = "".join(all_lines[:200])
    tail = "".join(all_lines[-100:]) if len(all_lines) > 200 else ""
    cap = max(2000, max_chars // 2)
    return head[:cap], tail[:cap]


def _load_run_record(run_id: str) -> dict | None:
    """
    Locate a run record JSON in results/{INSTRUMENT}/*.json by run_id.
    Falls back to legacy logs/control_plane/runs/{run_id}.json.
    """
    root = Path("D:/Tradelatest")
    for results_dir in [root / "results", Path("results")]:
        if not results_dir.exists():
            continue
        for jf in results_dir.glob(f"**/*{run_id[:8]}*.json"):
            try:
                payload = json.loads(jf.read_text(encoding="utf-8"))
                if payload.get("_run_record") and payload.get("run_id", "").startswith(run_id[:8]):
                    return payload
            except Exception:
                continue
    # Legacy
    for legacy in [root / "logs/control_plane/runs", Path("logs/control_plane/runs")]:
        legacy_file = legacy / f"{run_id}.json"
        if legacy_file.exists():
            try:
                return json.loads(legacy_file.read_text(encoding="utf-8"))
            except Exception:
                continue
    return None


def _append_finding(record: dict) -> None:
    Path(_FINDINGS_LOG).parent.mkdir(parents=True, exist_ok=True)
    with open(_FINDINGS_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _build_prompt(
    run: dict,
    stdout_tail: str,
    stderr_tail: str,
    src_head: str,
    src_tail: str,
) -> str:
    """Compact diagnostic prompt — explicit JSON output contract."""
    return (
        "You are a CRT trading-pipeline diagnostic assistant.\n"
        "Analyse the following CRT run and emit a JSON object with keys:\n"
        '  "summary":          one-sentence outcome\n'
        '  "anomalies":        list of short anomaly strings (empty list if none)\n'
        '  "recommended_next": list of short action strings (empty list if none)\n'
        "Return ONLY the JSON object, no prose.\n"
        "\n"
        "─── RUN METADATA ───\n"
        f"command_id : {run.get('command_id')}\n"
        f"status     : {run.get('status')}\n"
        f"exit_code  : {run.get('exit_code')}\n"
        f"started_at : {run.get('started_at')}\n"
        f"ended_at   : {run.get('ended_at')}\n"
        f"args       : {json.dumps(run.get('args', {}), default=str)[:1500]}\n"
        f"artifacts  : {json.dumps(run.get('artifact_paths', []), default=str)[:1000]}\n"
        f"error      : {str(run.get('error'))[:500]}\n"
        "\n"
        "─── STDOUT TAIL ───\n"
        f"{stdout_tail[-3000:]}\n"
        "\n"
        "─── STDERR TAIL ───\n"
        f"{stderr_tail[-3000:]}\n"
        "\n"
        "─── SCRIPT HEAD (first ~200 lines) ───\n"
        f"{src_head}\n"
        "\n"
        "─── SCRIPT TAIL (last ~100 lines) ───\n"
        f"{src_tail}\n"
    )


def _parse_json_object(text: str) -> dict:
    """Extract first JSON object from LLM reply. Tolerant of leading prose."""
    if not text:
        return {}
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        return json.loads(text[start:end + 1])
    except Exception:
        return {}


# ── public API ───────────────────────────────────────────────────────────────
def synthesize_finding(run_id: str) -> dict:
    """
    Produce a finding for one run and append it to logs/agent_findings.jsonl.

    Always returns a dict (even when synthesis is unavailable). Never raises.
    """
    if not run_id or not isinstance(run_id, str):
        finding = {
            "ts": _now_iso(), "run_id": str(run_id), "status": "invalid_input",
            "summary": "", "anomalies": [], "recommended_next": [],
            "error": "run_id must be a non-empty string",
        }
        _append_finding(finding)
        return finding

    # Load run record
    run = _load_run_record(run_id)
    if run is None:
        finding = {
            "ts": _now_iso(), "run_id": run_id, "status": "run_not_found",
            "summary": "", "anomalies": [], "recommended_next": [],
            "error": f"No run record found for run_id={run_id}",
        }
        _append_finding(finding)
        return finding

    # Pull config for caps
    try:
        from config_layer.production_config import get_prod_section
        agent_cfg = get_prod_section("agent") or {}
    except Exception:
        agent_cfg = {}
    findings_cfg = agent_cfg.get("findings") or {}
    if not findings_cfg.get("enabled", True):
        finding = {
            "ts": _now_iso(), "run_id": run_id, "status": "disabled_in_config",
            "summary": "", "anomalies": [], "recommended_next": [],
            "error": "agent.findings.enabled=false",
        }
        _append_finding(finding)
        return finding

    log_tail_lines = int(findings_cfg.get("log_tail_lines", _DEFAULT_LOG_TAIL))
    max_source_chars = int(findings_cfg.get("max_source_chars", _DEFAULT_MAX_SOURCE_CHARS))

    # Gather context
    log_paths = run.get("log_paths") or {}
    stdout_tail = _tail_text(log_paths.get("stdout"), log_tail_lines)
    stderr_tail = _tail_text(log_paths.get("stderr"), log_tail_lines)

    script_path = _resolve_script_path(run)
    src_head, src_tail = _source_slice(script_path, max_source_chars)

    prompt = _build_prompt(run, stdout_tail, stderr_tail, src_head, src_tail)
    system = (
        "Be terse, technical, and concrete. Anomalies must reference specific "
        "stderr lines, exit codes, or args. Recommended_next must reference "
        "real CRT command IDs (e.g. data.prepare_data, training.auto_train)."
    )

    # Call Groq
    from agent.groq_client import GroqClient
    client = GroqClient()
    t0 = time.monotonic()
    response = client.chat(prompt=prompt, system=system, max_tokens=1024)
    latency_ms = int((time.monotonic() - t0) * 1000)

    if not response:
        finding = {
            "ts": _now_iso(), "run_id": run_id,
            "command_id": run.get("command_id"), "status": "synthesis_unavailable",
            "summary": "", "anomalies": [], "recommended_next": [],
            "prompt_hash": _hash16(prompt),
            "response_hash": None,
            "model": (agent_cfg.get("groq") or {}).get("model", "llama-3.1-70b-versatile"),
            "latency_ms": latency_ms,
            "error": "Groq client returned empty (key missing, circuit open, or network)",
        }
        _append_finding(finding)
        return finding

    parsed = _parse_json_object(response)
    finding = {
        "ts": _now_iso(),
        "run_id": run_id,
        "command_id": run.get("command_id"),
        "status": run.get("status"),
        "summary": str(parsed.get("summary", "")).strip()[:1000],
        "anomalies": [str(a)[:300] for a in (parsed.get("anomalies") or [])][:10],
        "recommended_next": [str(r)[:300] for r in (parsed.get("recommended_next") or [])][:10],
        "prompt_hash": _hash16(prompt),
        "response_hash": _hash16(response),
        "model": (agent_cfg.get("groq") or {}).get("model", "llama-3.1-70b-versatile"),
        "latency_ms": latency_ms,
        "error": None if parsed else "LLM returned non-JSON or malformed JSON",
    }
    _append_finding(finding)
    return finding


def _resolve_script_path(run: dict) -> str | None:
    """
    Best-effort: find the script source for this run.
    Priority: command_line[1] (path arg) → registry lookup by command_id.
    """
    cmd_line = run.get("command_line") or []
    if isinstance(cmd_line, list) and len(cmd_line) >= 2:
        candidate = str(cmd_line[1])
        # Skip the Python executable; the second positional is usually the script
        if candidate.endswith(".py") or "scripts" in candidate or "/src/" in candidate or "\\src\\" in candidate:
            return candidate
    # Registry fallback
    try:
        from control_plane.registry import command_map, core_command_specs
        spec = command_map(core_command_specs()).get(run.get("command_id", ""))
        if spec is not None:
            return spec.script
    except Exception:
        pass
    return None


def list_recent(limit: int = 10) -> list[dict]:
    """Return the most recent N findings from logs/agent_findings.jsonl."""
    p = Path(_FINDINGS_LOG)
    if not p.exists():
        return []
    try:
        with open(p, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return []
    out: list[dict] = []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
        if len(out) >= limit:
            break
    return out


def explain(run_id: str) -> dict | None:
    """Return the most recent finding for a given run_id, or None."""
    for f in list_recent(limit=500):
        if f.get("run_id", "").startswith(run_id[:8]):
            return f
    return None
