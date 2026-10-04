"""
ingest_response.py
================================================================================
Phase 1 Groq Bridge -- ingests Groq's JSON response, updates the session
registry, writes structured insights to logs/groq_bridge/insights.jsonl,
updates trace_index.md, and prints actionable config change recommendations.

Usage
-----
    # Ingest a response file
    python scripts/groq_bridge/ingest_response.py ^
        --session RETRO_20260507_143022_EURUSD_100 ^
        --response-file C:/path/to/groq_response.txt

    # List all sessions
    python scripts/groq_bridge/ingest_response.py --list-sessions

    # Show insights for a session
    python scripts/groq_bridge/ingest_response.py ^
        --session RETRO_20260507_143022_EURUSD_100 --show

    # Record a post-backtest score delta
    python scripts/groq_bridge/ingest_response.py ^
        --session RETRO_20260507_143022_EURUSD_100 ^
        --record-score 0.612

    # Apply config changes (writes + rehashes config)
    python scripts/groq_bridge/ingest_response.py ^
        --session RETRO_20260507_143022_EURUSD_100 ^
        --apply-config
================================================================================
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Path bootstrap ────────────────────────────────────────────────────────────
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent.parent
_LOGS_BRIDGE = _REPO_ROOT / "logs" / "groq_bridge"

_REGISTRY_FILE = _LOGS_BRIDGE / "session_registry.jsonl"
_INSIGHTS_FILE = _LOGS_BRIDGE / "insights.jsonl"
_TRACE_INDEX = _LOGS_BRIDGE / "trace_index.md"
_PROD_CONFIG = _REPO_ROOT / "configs" / "production" / "v1_multi_2026_03.json"
_HASH_SCRIPT = _REPO_ROOT / "scripts" / "maintenance" / "_compute_hash.py"


# ============================================================================
# REGISTRY HELPERS
# ============================================================================

def _load_registry() -> list[dict]:
    if not _REGISTRY_FILE.exists():
        return []
    records = []
    with open(_REGISTRY_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records


def _save_registry(records: list[dict]) -> None:
    _LOGS_BRIDGE.mkdir(parents=True, exist_ok=True)
    with open(_REGISTRY_FILE, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def _get_session(session_id: str) -> dict | None:
    for r in _load_registry():
        if r.get("session_id") == session_id:
            return r
    return None


def _update_session(session_id: str, updates: dict) -> bool:
    records = _load_registry()
    found = False
    for r in records:
        if r.get("session_id") == session_id:
            r.update(updates)
            found = True
            break
    if found:
        _save_registry(records)
    return found


# ============================================================================
# RESPONSE PARSING
# ============================================================================

_REQUIRED_KEYS = {
    "top_engine_signal",
    "sessions_to_avoid",
    "recommended_fusion_min",
    "bitnet_disagreement_verdict",
    "config_changes",
    "trap_pattern",
}


def _extract_json(raw: str) -> dict:
    """Extract JSON from Groq response -- handles markdown code fences."""
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    fence_match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    brace_match = re.search(r"\{[\s\S]+\}", raw)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(
        "Could not parse JSON from Groq response. "
        "Make sure Groq returned valid JSON as specified in the prompt."
    )


def _validate_response(parsed: dict) -> list[str]:
    return [k for k in _REQUIRED_KEYS if k not in parsed]


# ============================================================================
# INSIGHTS LOG
# ============================================================================

def _append_insight(session_id: str, parsed: dict, session: dict, groq_model: str) -> None:
    _LOGS_BRIDGE.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "kind": "GROQ_INSIGHT",
        "session_id": session_id,
        "instrument": session.get("instrument", "UNKNOWN"),
        "trades_analyzed": session.get("trades_analyzed", 0),
        "model": groq_model,
        "prompt_hash": session.get("prompt_hash", ""),
        **parsed,
    }
    with open(_INSIGHTS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


# ============================================================================
# TRACE INDEX UPDATE
# ============================================================================

def _update_trace_row(session_id: str, updates: dict) -> None:
    if not _TRACE_INDEX.exists():
        return
    lines = _TRACE_INDEX.read_text(encoding="utf-8").splitlines(keepends=True)
    new_lines = []
    for line in lines:
        if session_id in line:
            status = updates.get("status", "UPDATED")
            score_after = updates.get("score_after")
            roi_delta = updates.get("roi_delta")
            line = re.sub(
                r"\|\s*\w+\s*\|?\s*$",
                f"| {score_after or '-'} | {f'+{roi_delta:.3f}' if roi_delta and roi_delta > 0 else (f'{roi_delta:.3f}' if roi_delta else '-')} | {status} |\n",
                line,
            )
        new_lines.append(line)
    _TRACE_INDEX.write_text("".join(new_lines), encoding="utf-8")


# ============================================================================
# CONFIG APPLY
# ============================================================================

def _apply_config_changes(config_changes: list[dict], session_id: str) -> None:
    if not _PROD_CONFIG.exists():
        print(f"  ERROR: production config not found at {_PROD_CONFIG}")
        return

    cfg = json.loads(_PROD_CONFIG.read_text(encoding="utf-8"))

    applied = []
    skipped = []
    for change in config_changes:
        param = change.get("param", "")
        to_val = change.get("to")
        rationale = change.get("rationale", "")

        found = False
        for section_key, section in cfg.items():
            if isinstance(section, dict) and param in section:
                old_val = section[param]
                section[param] = to_val
                applied.append((section_key, param, old_val, to_val, rationale))
                found = True
                break

        if not found:
            skipped.append(param)

    if not applied:
        print("  No config changes could be applied (params not found in any section).")
        print(f"  Skipped params: {skipped}")
        return

    # Archive current config before modifying
    archive_name = _PROD_CONFIG.stem + f"_retro_{session_id}" + _PROD_CONFIG.suffix
    archive_path = _PROD_CONFIG.parent / archive_name
    archive_path.write_text(_PROD_CONFIG.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"  Config archived: {archive_path.name}")

    _PROD_CONFIG.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    for section_key, param, old_val, to_val, rationale in applied:
        print(f"  APPLIED [{section_key}] {param}: {old_val} -> {to_val}")
        if rationale:
            print(f"    Rationale: {rationale}")

    if skipped:
        print(f"  SKIPPED (not found in config): {', '.join(skipped)}")

    if _HASH_SCRIPT.exists():
        print("  Recomputing config hash...")
        result = subprocess.run(
            [sys.executable, str(_HASH_SCRIPT)],
            capture_output=True,
            text=True,
            cwd=_REPO_ROOT,
        )
        if result.returncode == 0:
            print("  Hash recomputed OK")
        else:
            print(f"  WARNING: hash recomputation failed:\n{result.stderr[:300]}")
    else:
        print(f"  Run manually: python {_HASH_SCRIPT}")


# ============================================================================
# DISPLAY HELPERS
# ============================================================================

def _print_action_items(parsed: dict, session: dict) -> None:
    print("\n" + "=" * 60)
    print("  GROQ ANALYSIS RESULTS")
    print("=" * 60)

    top = parsed.get("top_engine_signal", {})
    if top:
        print(f"\nTOP SIGNAL: engine={top.get('engine','?')} "
              f"regime={top.get('regime','?')} "
              f"threshold={top.get('threshold','?')}")
        print(f"  {top.get('rationale', '')}")

    fusion_min = parsed.get("recommended_fusion_min")
    if fusion_min is not None:
        print(f"\nRECOMMENDED fusion_min_score: {fusion_min:.3f}")

    bitnet = parsed.get("bitnet_disagreement_verdict", "")
    if bitnet:
        print(f"\nBITNET DISAGREEMENT verdict: {bitnet.upper()}")

    avoid = parsed.get("sessions_to_avoid", [])
    if avoid:
        print(f"\nFILTER OUT ({len(avoid)} regime/engine combos):")
        for item in avoid:
            print(f"  - regime={item.get('regime','?')} engine={item.get('engine','?')} "
                  f"-> {item.get('reason','')}")

    changes = parsed.get("config_changes", [])
    if changes:
        print(f"\nCONFIG CHANGES ({len(changes)} recommended):")
        for c in changes:
            print(f"  - {c.get('param','?')}: {c.get('from','?')} -> {c.get('to','?')}")
            if c.get("rationale"):
                print(f"    {c.get('rationale')}")

    trap = parsed.get("trap_pattern", {})
    if trap and trap.get("description"):
        print(f"\nTRAP PATTERN: {trap.get('description','')}")
        print(f"  Filter rule: {trap.get('filter_rule','')}")

    print("\n" + "=" * 60)

    session_id = session.get("session_id", "")
    if changes:
        print(f"\nTo apply config changes, run:")
        print(f"  python scripts/groq_bridge/ingest_response.py --session {session_id} --apply-config")
    print()


def _print_session_list(records: list[dict]) -> None:
    if not records:
        print("No sessions registered yet.")
        return
    print(f"\n{'Session ID':<45} {'Date':<12} {'Instr':<8} {'Trades':<7} {'Status':<20} {'ROI Delta'}")
    print("-" * 110)
    for r in records:
        sid = r.get("session_id", "")[:44]
        ts = r.get("ts", "")[:10]
        instr = r.get("instrument", "?")[:7]
        n = r.get("trades_analyzed", "?")
        status = r.get("status", "?")[:19]
        delta = r.get("roi_delta")
        delta_str = f"+{delta:.3f}" if delta and delta > 0 else (f"{delta:.3f}" if delta else "-")
        print(f"{sid:<45} {ts:<12} {instr:<8} {str(n):<7} {status:<20} {delta_str}")
    print()


# ============================================================================
# MAIN
# ============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest Groq response and manage retrospective sessions."
    )
    parser.add_argument("--session", help="Session ID (RETRO_...)")
    parser.add_argument("--response-file", help="Path to file containing Groq's JSON response")
    parser.add_argument("--list-sessions", action="store_true", help="List all sessions")
    parser.add_argument("--show", action="store_true", help="Show insights for a session")
    parser.add_argument(
        "--record-score",
        type=float,
        metavar="SCORE",
        help="Record post-backtest validation score (e.g. 0.612)",
    )
    parser.add_argument(
        "--apply-config",
        action="store_true",
        help="Apply config changes from session insights to production JSON",
    )
    parser.add_argument(
        "--apply-to-training",
        action="store_true",
        help=(
            "Treat the response as LLM hypertuning suggestions and forward "
            "them to scripts/groq_bridge/apply_llm_suggestions.py. "
            "The response must include hyperparameter keys matching the "
            "target model (gaussian/zone/rr)."
        ),
    )
    parser.add_argument(
        "--target-model",
        choices=("gaussian", "zone", "rr"),
        default=None,
        help="Target model for --apply-to-training (default: gaussian).",
    )
    parser.add_argument(
        "--opportunities",
        default=None,
        help="Path to opportunity log forwarded to apply_llm_suggestions.py "
             "(required when --apply-to-training is set).",
    )
    parser.add_argument(
        "--version",
        default=None,
        help="Model version label forwarded to apply_llm_suggestions.py.",
    )
    parser.add_argument(
        "--groq-model",
        default="llama-3.3-70b-versatile",
        help="Groq model name for logging (default: llama-3.3-70b-versatile)",
    )
    args = parser.parse_args()

    _LOGS_BRIDGE.mkdir(parents=True, exist_ok=True)

    if args.list_sessions:
        _print_session_list(_load_registry())
        return

    if not args.session:
        parser.error("--session is required (unless using --list-sessions)")

    session_id = args.session
    session = _get_session(session_id)
    if session is None:
        print(f"ERROR: session '{session_id}' not found in registry.", file=sys.stderr)
        print("Run --list-sessions to see available sessions.", file=sys.stderr)
        sys.exit(1)

    # Show existing insights
    if args.show:
        if not _INSIGHTS_FILE.exists():
            print("No insights file found yet.")
            return
        with open(_INSIGHTS_FILE, encoding="utf-8") as f:
            for line in f:
                obj = json.loads(line.strip())
                if obj.get("session_id") == session_id:
                    print(json.dumps(obj, indent=2))
                    return
        print(f"No insights found for session {session_id}")
        return

    # Record score
    if args.record_score is not None:
        score_after = args.record_score
        baseline = session.get("baseline_score") or session.get("avg_score_before")
        roi_delta = round(score_after - baseline, 4) if baseline else None
        status = "VALIDATED" if (roi_delta is not None and roi_delta > 0) else "REJECTED"
        updates = {"score_after": score_after, "roi_delta": roi_delta, "status": status}
        _update_session(session_id, updates)
        _update_trace_row(session_id, updates)
        icon = "OK" if status == "VALIDATED" else "FAIL"
        print(f"[{icon}] Session {session_id}: score_after={score_after:.4f} "
              f"roi_delta={roi_delta:+.4f} -> status={status}")
        return

    # Apply config changes
    if args.apply_config:
        if not _INSIGHTS_FILE.exists():
            print("ERROR: no insights file. Ingest a response first.", file=sys.stderr)
            sys.exit(1)
        insight = None
        with open(_INSIGHTS_FILE, encoding="utf-8") as f:
            for line in f:
                obj = json.loads(line.strip())
                if obj.get("session_id") == session_id:
                    insight = obj
        if insight is None:
            print(f"ERROR: no insights for session {session_id}.", file=sys.stderr)
            sys.exit(1)
        changes = insight.get("config_changes", [])
        if not changes:
            print("No config_changes in this session's insights.")
            return
        print(f"Applying {len(changes)} config changes from session {session_id}...")
        _apply_config_changes(changes, session_id)
        _update_session(session_id, {
            "insights_applied": True,
            "status": "INSIGHTS_APPLIED",
            "config_version_after": f"v1_multi_2026_03_retro_{session_id}",
        })
        _update_trace_row(session_id, {"status": "INSIGHTS_APPLIED"})
        print(f"\nSession status: INSIGHTS_APPLIED")
        print(f"Next: re-run backtest, then:")
        print(f"  python scripts/groq_bridge/ingest_response.py "
              f"--session {session_id} --record-score <new_score>")
        return

    # Ingest response
    if not args.response_file:
        parser.error("--response-file is required to ingest a response")

    response_path = Path(args.response_file)
    if not response_path.exists():
        print(f"ERROR: response file not found: {response_path}", file=sys.stderr)
        sys.exit(1)

    raw = response_path.read_text(encoding="utf-8")
    print(f"Parsing Groq response from: {response_path}")

    try:
        parsed = _extract_json(raw)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # ── Hypertuning branch — forward to apply_llm_suggestions.py ─────────────
    if args.apply_to_training:
        target = args.target_model or "gaussian"
        if not args.opportunities:
            print(
                "ERROR: --apply-to-training requires --opportunities <path>.",
                file=sys.stderr,
            )
            sys.exit(2)
        applier = (
            _REPO_ROOT / "scripts" / "groq_bridge" / "apply_llm_suggestions.py"
        )
        version_label = args.version or f"llm_{target}_{session_id}"
        cmd = [
            sys.executable, str(applier),
            "--target-model", target,
            "--suggestions-file", str(response_path),
            "--opportunities", args.opportunities,
            "--version", version_label,
        ]
        print("Forwarding to apply_llm_suggestions.py:", " ".join(cmd))
        rc = subprocess.call(cmd, cwd=_REPO_ROOT)
        _update_session(session_id, {
            "status": "TRAINING_TRIGGERED" if rc == 0 else "TRAINING_FAILED",
            "target_model": target,
            "version_label": version_label,
        })
        sys.exit(rc)

    missing = _validate_response(parsed)
    if missing:
        print(f"WARNING: response is missing keys: {missing}")
        print("Proceeding with partial insights.")

    changes = parsed.get("config_changes", [])
    top_engine = parsed.get("top_engine_signal", {})
    insights_summary = (
        f"top_engine={top_engine.get('engine','?')} "
        f"fusion_min={parsed.get('recommended_fusion_min','?')} "
        f"changes={len(changes)}"
    )

    saved_response = _LOGS_BRIDGE / f"response_{session_id}.txt"
    saved_response.write_text(raw, encoding="utf-8")

    _append_insight(session_id, parsed, session, args.groq_model)

    _update_session(session_id, {
        "status": "RESPONSE_RECEIVED",
        "response_file": str(saved_response),
        "groq_model": args.groq_model,
        "insights_summary": insights_summary,
    })

    _update_trace_row(session_id, {"status": "RESPONSE_RECEIVED"})

    print(f"\nSession {session_id} -> RESPONSE_RECEIVED")
    print(f"Response saved: {saved_response}")
    print(f"Insights logged: {_INSIGHTS_FILE}")

    _print_action_items(parsed, session)


if __name__ == "__main__":
    main()
