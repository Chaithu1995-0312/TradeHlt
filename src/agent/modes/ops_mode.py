"""
ops_mode.py — GrokAgenticAI OpsDoctor tools (read-only + incident pack)
─────────────────────────────────────────────────────────────────────────────
Tools:
  ops.throughput_snapshot  — scan logs/results for recent trade/run signals
  ops.funnel_diagnose      — wrap scripts/analysis/crt_funnel_diagnostic.py
  ops.fail_reasons         — best-effort fail-reason artifact / script
  ops.incident_pack        — WRITE results/incidents/{ts}_{instrument}.json

Never places trades. Never mutates production configs.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..tool_registry import register_tool

logger = logging.getLogger("GrokAgenticAI.OpsDoctor")

_REPO = Path(__file__).resolve().parents[3]


def _now_slug() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def _tail_jsonl(path: Path, n: int = 50) -> List[dict]:
    if not path.exists() or not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        logger.debug("tail %s: %s", path, exc)
        return []
    out: List[dict] = []
    for line in lines[-n:]:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            out.append({"raw": line[:500]})
    return out


@register_tool(
    name="ops.throughput_snapshot",
    description="OpsDoctor: snapshot recent run/trade activity from logs and results (read-only).",
    write=False,
    args_schema={
        "instrument": {"type": "str", "required": False, "desc": "Optional instrument filter"},
        "n": {"type": "int", "required": False, "desc": "Tail depth (default 40)"},
    },
)
def _throughput_snapshot(instrument: str = "", n: int = 40) -> dict:
    n = max(5, min(int(n or 40), 200))
    inst = (instrument or "").upper()
    candidates = [
        _REPO / "logs" / "collector.jsonl",
        _REPO / "logs" / "agent_audit.jsonl",
        _REPO / "logs" / "agent_findings.jsonl",
    ]
    # results/** summary-ish json
    results_hits: List[str] = []
    results_root = _REPO / "results"
    if results_root.exists():
        for p in results_root.rglob("*.json"):
            name = p.name.lower()
            if inst and inst.lower() not in str(p).lower() and inst.lower() not in name:
                continue
            if any(k in name for k in ("summary", "metric", "report", "checkpoint")):
                results_hits.append(str(p.relative_to(_REPO)).replace("\\", "/"))
                if len(results_hits) >= 15:
                    break

    log_tails: Dict[str, Any] = {}
    for path in candidates:
        key = path.name
        rows = _tail_jsonl(path, n)
        if inst:
            filtered = []
            for r in rows:
                blob = json.dumps(r, default=str).upper()
                if inst in blob:
                    filtered.append(r)
            rows = filtered or rows[-min(5, len(rows)):]
        log_tails[key] = {"count": len(rows), "sample": rows[-5:]}

    trade_like = 0
    for rows in log_tails.values():
        for r in rows.get("sample") or []:
            blob = json.dumps(r, default=str).lower()
            if "trade" in blob or "entry" in blob or "pnl" in blob:
                trade_like += 1

    return {
        "status": "ok",
        "instrument": inst or None,
        "trade_like_signals": trade_like,
        "results_artifacts": results_hits,
        "logs": {k: {"count": v["count"]} for k, v in log_tails.items()},
        "log_samples": log_tails,
        "ops.complete": False,
        "note": "Descriptive snapshot only — not an economic claim.",
    }


@register_tool(
    name="ops.funnel_diagnose",
    description="OpsDoctor: run CRT funnel diagnostic when a run-dir is available (read-only measure).",
    write=False,
    args_schema={
        "instrument": {"type": "str", "required": False, "desc": "Instrument label for search"},
        "run_dir": {"type": "str", "required": False, "desc": "Backtest run directory with summary/telemetry"},
    },
)
def _funnel_diagnose(instrument: str = "", run_dir: str = "") -> dict:
    script = _REPO / "scripts" / "analysis" / "crt_funnel_diagnostic.py"
    if not script.exists():
        return {"status": "error", "error": f"missing script {script}", "ops.complete": False}

    rd = run_dir.strip()
    if not rd and instrument:
        # Best-effort: newest results/<INSTR>* directory
        root = _REPO / "results"
        if root.exists():
            matches = sorted(
                [p for p in root.rglob("*") if p.is_dir() and instrument.upper() in p.name.upper()],
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if matches:
                rd = str(matches[0])

    if not rd:
        return {
            "status": "ok",
            "skipped": True,
            "reason": "no run_dir — pass run_dir= or produce a backtest results folder first",
            "instrument": instrument or None,
            "hint": "python scripts/analysis/crt_funnel_diagnostic.py --run-dir <path>",
        }

    cmd = [sys.executable, str(script), "--run-dir", rd]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(_REPO),
        )
    except subprocess.TimeoutExpired:
        return {"status": "error", "error": "funnel diagnostic timed out (120s)", "run_dir": rd}
    except OSError as exc:
        return {"status": "error", "error": str(exc), "run_dir": rd}

    return {
        "status": "ok" if proc.returncode == 0 else "error",
        "returncode": proc.returncode,
        "run_dir": rd,
        "stdout_tail": (proc.stdout or "")[-2000:],
        "stderr_tail": (proc.stderr or "")[-1000:],
        "error": None if proc.returncode == 0 else (proc.stderr or proc.stdout or "non-zero exit")[-500:],
    }


@register_tool(
    name="ops.fail_reasons",
    description="OpsDoctor: load latest CRT fail-reason diagnostic artifact if present (read-only).",
    write=False,
    args_schema={
        "instrument": {"type": "str", "required": False, "desc": "Optional filter"},
    },
)
def _fail_reasons(instrument: str = "") -> dict:
    gov = _REPO / "docs" / "governance"
    artifacts: List[Path] = []
    if gov.exists():
        artifacts = sorted(
            gov.glob("crt_fail_reason*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
    if not artifacts:
        return {
            "status": "ok",
            "skipped": True,
            "reason": "no crt_fail_reason*.json under docs/governance/",
            "hint": "python scripts/analysis/crt_fail_reason_diagnostic.py",
        }
    path = artifacts[0]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "error", "error": str(exc), "path": str(path)}

    # Keep payload bounded
    summary: Any = payload
    if isinstance(payload, dict):
        summary = {
            k: payload[k]
            for k in list(payload.keys())[:20]
        }
        if "top fails" in str(payload).lower() or "top_fails" in payload:
            summary["top_fails"] = payload.get("top_fails") or payload.get("top fails")
    try:
        path_s = str(path.relative_to(_REPO)).replace("\\", "/")
    except ValueError:
        path_s = str(path)
    return {
        "status": "ok",
        "path": path_s,
        "artifact": summary,
        "instrument": instrument or None,
    }


@register_tool(
    name="ops.incident_pack",
    description="OpsDoctor: write a structured incident pack under results/incidents/ (WRITE — confirm-gated).",
    write=True,
    args_schema={
        "instrument": {"type": "str", "required": False, "desc": "Instrument label"},
        "notes": {"type": "str", "required": False, "desc": "Optional free-text notes"},
        "prior_json": {"type": "str", "required": False, "desc": "Optional JSON blob of prior step metrics"},
    },
)
def _incident_pack(instrument: str = "", notes: str = "", prior_json: str = "") -> dict:
    prior: dict = {}
    if prior_json:
        try:
            prior = json.loads(prior_json)
        except json.JSONDecodeError:
            prior = {"raw": prior_json[:2000]}

    inst = (instrument or prior.get("instrument") or "UNKNOWN").upper()
    out_dir = _REPO / "results" / "incidents"
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = _now_slug()
    rel = f"results/incidents/{slug}_{inst}.json"
    path = _REPO / Path(rel)

    pack = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "product": "GrokAgenticAI",
        "specialist": "OpsDoctor",
        "instrument": inst,
        "notes": notes or "",
        "prior": prior,
        "authority": "ops_diagnostic_only",
        "disclaimer": "Not an economic promote claim; not a living finding.",
    }
    path.write_text(json.dumps(pack, indent=2, default=str), encoding="utf-8")
    md_rel = str(Path(rel).with_suffix(".md")).replace("\\", "/")
    md_path = _REPO / Path(md_rel)
    md_path.write_text(
        f"# Incident pack — {inst}\n\n"
        f"- Product: GrokAgenticAI / OpsDoctor\n"
        f"- Time: {pack['ts']}\n"
        f"- Authority: diagnostic only\n\n"
        f"## Notes\n{notes or '_none_'}\n\n"
        f"## Prior metrics (JSON)\n```json\n{json.dumps(prior, indent=2, default=str)[:8000]}\n```\n",
        encoding="utf-8",
    )
    try:
        path_out = str(path.relative_to(_REPO)).replace("\\", "/")
    except ValueError:
        path_out = rel
    return {
        "status": "ok",
        "incident_pack": True,
        "incident_path": path_out,
        "markdown_path": md_rel,
        "ops.complete": True,
        "instrument": inst,
    }
