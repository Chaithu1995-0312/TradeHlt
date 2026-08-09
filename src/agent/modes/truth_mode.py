"""
truth_mode.py — GrokAgenticAI TruthJanitor tools
─────────────────────────────────────────────────────────────────────────────
Governance / documentation hygiene (async kitchen only).

Tools (read-first):
  truth.construction_check  — construction_protocol.py check
  truth.feature_math_lint   — feature_math_lint.py (ownership lint)
  truth.script_census       — script_census.py summary JSON under results/
  truth.citation_floor      — pytest tests/test_doc_citations.py (collect report)
  truth.hygiene_pack        — WRITE results/hygiene/ rollup (confirm-gated)

Never mutates production configs, ACTIVE_VERSION, ontology, or living findings.
Never auto-applies doc patches (propose-only via hygiene pack notes).
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

logger = logging.getLogger("GrokAgenticAI.TruthJanitor")

_REPO = Path(__file__).resolve().parents[3]


def _now_slug() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def _run(
    argv: List[str],
    *,
    timeout_s: int = 180,
    cwd: Optional[Path] = None,
) -> dict:
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            cwd=str(cwd or _REPO),
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "error": f"timeout after {timeout_s}s",
            "cmd": argv,
            "returncode": -1,
        }
    except OSError as exc:
        return {"status": "error", "error": str(exc), "cmd": argv, "returncode": -1}

    ok = proc.returncode == 0
    return {
        "status": "ok" if ok else "fail",
        "returncode": proc.returncode,
        "cmd": argv,
        "stdout_tail": (proc.stdout or "")[-3000:],
        "stderr_tail": (proc.stderr or "")[-1500:],
        "error": None if ok else ((proc.stderr or proc.stdout or "non-zero exit")[-800:]),
        "passed": ok,
    }


@register_tool(
    name="truth.construction_check",
    description="TruthJanitor: run construction_protocol.py check (Gate-6 floor, read-only).",
    write=False,
    args_schema={
        "timeout_s": {"type": "int", "required": False, "desc": "Subprocess timeout seconds (default 240)"},
    },
)
def _construction_check(timeout_s: int = 240) -> dict:
    script = _REPO / "scripts" / "governance" / "construction_protocol.py"
    if not script.exists():
        return {"status": "error", "error": f"missing {script}", "passed": False}
    out = _run(
        [sys.executable, str(script), "check"],
        timeout_s=max(30, min(int(timeout_s or 240), 900)),
    )
    out["check"] = "construction_protocol"
    out["truth.complete"] = False
    # Soft parse: look for PASS/FAIL tokens in output
    blob = (out.get("stdout_tail") or "") + (out.get("stderr_tail") or "")
    out["signals"] = {
        "mentions_pass": "PASS" in blob.upper() or "OK" in blob.upper(),
        "mentions_fail": "FAIL" in blob.upper() or "DENIED" in blob.upper(),
    }
    return out


@register_tool(
    name="truth.feature_math_lint",
    description="TruthJanitor: run feature_math_lint ownership check (read-only).",
    write=False,
    args_schema={
        "check": {"type": "bool", "required": False, "desc": "If true, use --check (exit 1 on NEW violations)"},
        "timeout_s": {"type": "int", "required": False, "desc": "Timeout seconds (default 120)"},
    },
)
def _feature_math_lint(check: bool = True, timeout_s: int = 120) -> dict:
    script = _REPO / "scripts" / "analysis" / "feature_math_lint.py"
    if not script.exists():
        return {"status": "error", "error": f"missing {script}", "passed": False}
    argv = [sys.executable, str(script)]
    if check:
        argv.append("--check")
    out = _run(argv, timeout_s=max(30, min(int(timeout_s or 120), 600)))
    out["check"] = "feature_math_lint"
    out["truth.complete"] = False
    return out


@register_tool(
    name="truth.script_census",
    description="TruthJanitor: run script_census and write summary JSON under results/hygiene/ (observe; path is results/).",
    write=False,
    args_schema={
        "timeout_s": {"type": "int", "required": False, "desc": "Timeout seconds (default 180)"},
    },
)
def _script_census(timeout_s: int = 180) -> dict:
    """
    Observe-only census. Writes JSON under results/hygiene/ (allowed root).
    Does NOT --write-stubs (that would be a SITS mutation needing a separate confirmed tool).
    """
    script = _REPO / "scripts" / "analysis" / "script_census.py"
    if not script.exists():
        return {"status": "error", "error": f"missing {script}", "passed": False}

    out_dir = _REPO / "results" / "hygiene"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"script_census_{_now_slug()}.json"
    rel = f"results/hygiene/{json_path.name}"

    argv = [
        sys.executable,
        str(script),
        "--json",
        str(json_path),
    ]
    out = _run(argv, timeout_s=max(30, min(int(timeout_s or 180), 600)))
    out["check"] = "script_census"
    out["census_json"] = rel if json_path.exists() else None
    out["passed"] = bool(out.get("passed") and json_path.exists())
    if json_path.exists():
        try:
            summary = json.loads(json_path.read_text(encoding="utf-8"))
            if isinstance(summary, dict):
                # Keep small
                out["census_keys"] = list(summary.keys())[:30]
                for k in ("total", "count", "scripts", "n_scripts", "paths"):
                    if k in summary:
                        out[f"census_{k}"] = summary[k] if not isinstance(summary[k], list) else len(summary[k])
        except (OSError, json.JSONDecodeError) as exc:
            out["census_parse_error"] = str(exc)
    out["truth.complete"] = False
    return out


@register_tool(
    name="truth.citation_floor",
    description="TruthJanitor: run tests/test_doc_citations.py floor (read-only report).",
    write=False,
    args_schema={
        "timeout_s": {"type": "int", "required": False, "desc": "Timeout seconds (default 180)"},
    },
)
def _citation_floor(timeout_s: int = 180) -> dict:
    test_path = _REPO / "tests" / "test_doc_citations.py"
    if not test_path.exists():
        return {
            "status": "ok",
            "skipped": True,
            "reason": "tests/test_doc_citations.py not found",
            "passed": True,
            "check": "citation_floor",
        }
    argv = [
        sys.executable,
        "-m",
        "pytest",
        str(test_path),
        "-q",
        "--tb=no",
    ]
    out = _run(argv, timeout_s=max(30, min(int(timeout_s or 180), 600)))
    out["check"] = "citation_floor"
    out["truth.complete"] = False
    return out


@register_tool(
    name="truth.hygiene_pack",
    description="TruthJanitor: write hygiene rollup under results/hygiene/ (WRITE — confirm-gated). No production/doc mutation.",
    write=True,
    args_schema={
        "notes": {"type": "str", "required": False, "desc": "Optional operator notes"},
        "prior_json": {"type": "str", "required": False, "desc": "Optional JSON of prior step metrics"},
    },
)
def _hygiene_pack(notes: str = "", prior_json: str = "") -> dict:
    prior: dict = {}
    if prior_json:
        try:
            prior = json.loads(prior_json)
        except json.JSONDecodeError:
            prior = {"raw": prior_json[:4000]}

    out_dir = _REPO / "results" / "hygiene"
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = _now_slug()
    rel = f"results/hygiene/pack_{slug}.json"
    path = _REPO / Path(rel)

    # Derive overall gate from prior tool metrics if present
    checks: Dict[str, Any] = {}
    if isinstance(prior, dict):
        # Flatten common keys from merge_metrics-style blobs
        for key in (
            "construction_protocol",
            "feature_math_lint",
            "script_census",
            "citation_floor",
            "passed",
            "returncode",
            "status",
            "census_json",
            "check",
        ):
            if key in prior:
                checks[key] = prior[key]
        # tools_run list if present
        if "tools_run" in prior:
            checks["tools_run"] = prior["tools_run"]

    pack = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "product": "GrokAgenticAI",
        "specialist": "TruthJanitor",
        "notes": notes or "",
        "prior": prior,
        "checks": checks,
        "authority": "governance_hygiene_only",
        "disclaimer": (
            "Not a finding registration; not a promotion; does not edit docs/, "
            "configs/production/, or ontology. Operator may act on recommendations."
        ),
        "recommendations": [
            "If construction_check failed: open REPOSITORY_CONSTRUCTION_PROTOCOL.md and run validate-completion for the active manifest.",
            "If feature_math_lint failed: do not invent formulas — register via ontology/registry first.",
            "If script_census shows unregistered scripts: SITS flow (census --write-stubs → seed → matrix) with confirm.",
            "If citation_floor failed: update citations in the same turn as code moves (CLAUDE.md §6.3).",
            "DOC_DRIFT auto-fix only when unambiguous; AMBIGUOUS/finding reverse requires User approval (§6.2).",
        ],
    }
    path.write_text(json.dumps(pack, indent=2, default=str), encoding="utf-8")
    md_rel = str(Path(rel).with_suffix(".md")).replace("\\", "/")
    md_path = _REPO / Path(md_rel)
    md_body = (
        f"# Hygiene pack — TruthJanitor\n\n"
        f"- Product: GrokAgenticAI / TruthJanitor\n"
        f"- Time: {pack['ts']}\n"
        f"- Authority: governance hygiene only\n\n"
        f"## Notes\n{notes or '_none_'}\n\n"
        f"## Recommendations\n"
        + "\n".join(f"- {r}" for r in pack["recommendations"])
        + f"\n\n## Prior metrics\n```json\n{json.dumps(prior, indent=2, default=str)[:8000]}\n```\n"
    )
    md_path.write_text(md_body, encoding="utf-8")

    try:
        path_out = str(path.relative_to(_REPO)).replace("\\", "/")
    except ValueError:
        path_out = rel

    # Overall pass if no hard fail in prior status fields
    overall = True
    if isinstance(prior, dict):
        if prior.get("status") in ("error", "fail", "fatal"):
            overall = False
        if prior.get("passed") is False:
            overall = False

    return {
        "status": "ok",
        "hygiene_pack": True,
        "hygiene_path": path_out,
        "markdown_path": md_rel,
        "truth.complete": True,
        "hygiene.passed": overall,
        "authority": "governance_hygiene_only",
    }
