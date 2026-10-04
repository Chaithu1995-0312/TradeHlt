"""
construction_protocol.py — Gate-6 Repository Construction Contract validator.

Machine enforcement for the mandatory change lifecycle (docs/governance/
REPOSITORY_CONSTRUCTION_PROTOCOL.md). Extends the existing GREEN_FLOOR spine
(scripts/maintenance/check_governance_invariants.py) — not a parallel framework.

Subcommands
  validate-impact <manifest.json>      pre-build gate: schema + change-class mapping; any UNKNOWN
                                       in a mandatory field BLOCKS implementation.
  validate-completion <manifest.json>  post-build gate: declared-vs-actual `git diff` surfaces
                                       (undeclared governed files = FAIL), then RUNS the required
                                       checks itself (results are never log-trusted) and embeds the
                                       repo-state hash. COMPLETE only if everything is green.
  check                                one-command construction floor (the governance check set an
                                       agent runs before claiming completion of any governed change).

Design rules: UNKNOWN is admissible only as an explicit blocker, never silently. Check results are
produced by execution at validation time, not read from prior logs. DOCUMENTATION_ONLY changes get
the lightweight path (doc floors only + a no-behavior-surface diff guard).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_ROOT = Path(__file__).resolve().parents[2]
_CONTRACTS = _ROOT / "docs" / "governance" / "change_contracts.json"

# Governed surfaces for the undeclared-change check (superset of the invariant gate's list —
# these are the construction-contract surfaces, aligned with GOVERNED_* there).
GOVERNED_SURFACE_PREFIXES = (
    "src/", "configs/", "scripts/", "models/", "tests/",
)
DOC_ONLY_ALLOWED_PREFIXES = ("docs/", "context/", "reports/", "README", "AGENTS.md", "CLAUDE.md",
                             "assistant_project.md", "llm_project_assistant.md")

_IMPACT_MANDATORY = (
    "change_id", "objective", "change_classes", "affected_files",
    "required_checks_ack", "unknowns", "rollback_boundary",
)
_COMPLETION_MANDATORY = (
    "change_id", "declared_files", "checks_executed", "repo_state_hash", "completion_status",
)


def _load_contracts() -> dict:
    return json.loads(_CONTRACTS.read_text(encoding="utf-8"))


def _git(args: list[str]) -> str:
    # encoding pinned: git emits UTF-8; Windows text=True would decode cp1252 and a non-ASCII
    # diff byte kills the reader thread (stdout=None). errors="replace" keeps the hash stable
    # enough for state binding (same tree -> same replaced text -> same hash).
    r = subprocess.run(["git", *args], cwd=_ROOT, capture_output=True,
                       encoding="utf-8", errors="replace")
    return r.stdout or ""


def _repo_state_hash() -> str:
    """HEAD hash + working-tree diff hash — binds check results to the exact repo state."""
    head = _git(["rev-parse", "HEAD"]).strip()
    diff = _git(["diff", "HEAD"])
    import hashlib
    return f"{head[:12]}+{hashlib.sha256(diff.encode('utf-8', 'ignore')).hexdigest()[:12]}"


def _changed_files() -> list[str]:
    out = _git(["status", "--porcelain"])
    files = []
    for line in out.splitlines():
        if len(line) > 3:
            p = line[3:].strip().strip('"').replace("\\", "/")
            if " -> " in p:
                p = p.split(" -> ")[-1]
            files.append(p)
    return files


def _run_pytest(targets: list[str]) -> tuple[bool, str]:
    if not targets:
        return True, "no targets"
    cmd = [sys.executable, "-m", "pytest", "-q", *targets]
    r = subprocess.run(cmd, cwd=_ROOT, capture_output=True, text=True, timeout=1800)
    tail = "\n".join((r.stdout or "").splitlines()[-3:])
    return r.returncode == 0, tail


def validate_impact(manifest_path: Path) -> tuple[bool, list[str]]:
    problems: list[str] = []
    try:
        m = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return False, [f"unreadable manifest: {e}"]
    contracts = _load_contracts()["change_classes"]

    for field in _IMPACT_MANDATORY:
        if field not in m:
            problems.append(f"missing mandatory field: {field}")
    for field, val in m.items():
        if isinstance(val, str) and val.strip().upper() == "UNKNOWN" and field != "unknowns":
            problems.append(f"BLOCKED: mandatory field '{field}' is UNKNOWN — resolve before implementation")
    for u in m.get("unknowns", []) or []:
        blocking = u.get("blocking", True) if isinstance(u, dict) else True
        if blocking:
            problems.append(f"BLOCKED: unresolved blocking unknown: {u}")

    classes = m.get("change_classes", []) or []
    if not classes:
        problems.append("no change_classes declared")
    for c in classes:
        if c not in contracts:
            problems.append(f"unknown change class: {c}")
    # the manifest must acknowledge every required check of its classes
    required = {chk for c in classes if c in contracts for chk in contracts[c]["required_checks"]}
    acked = set(m.get("required_checks_ack", []) or [])
    missing = required - acked
    if missing:
        problems.append(f"required checks not acknowledged: {sorted(missing)}")
    return not problems, problems


def validate_completion(manifest_path: Path, run_checks: bool = True) -> tuple[bool, list[str], dict]:
    problems: list[str] = []
    detail: dict = {}
    try:
        m = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return False, [f"unreadable manifest: {e}"], {}
    contracts = _load_contracts()["change_classes"]

    for field in _COMPLETION_MANDATORY:
        if field not in m:
            problems.append(f"missing mandatory field: {field}")

    # 1. declared vs actual surfaces — undeclared governed changes = FAIL
    declared = {p.replace("\\", "/") for p in (m.get("declared_files") or [])}
    actual = set(_changed_files())
    manifest_rel = str(manifest_path.resolve().relative_to(_ROOT)).replace("\\", "/") \
        if manifest_path.resolve().is_relative_to(_ROOT) else None
    undeclared = {
        f for f in (actual - declared)
        if f != manifest_rel
        and any(f.startswith(p) for p in GOVERNED_SURFACE_PREFIXES)
    }
    detail["undeclared_changed_files"] = sorted(undeclared)
    if undeclared:
        problems.append(f"UNDECLARED governed surfaces changed: {sorted(undeclared)[:8]}")

    # 2. DOCUMENTATION_ONLY guard: no behavior surface may change
    classes = m.get("change_classes", []) or []
    if classes == ["DOCUMENTATION_ONLY"]:
        behavior = [f for f in actual if any(f.startswith(p) for p in ("src/", "configs/", "models/"))]
        if behavior:
            problems.append(f"DOCUMENTATION_ONLY manifest but behavior surfaces changed: {behavior[:5]}")

    # 2b. SITS belt-and-suspenders: declared script paths require script-registry floor
    # (SCRIPT_LIFECYCLE_CHANGE already lists the checks; this catches scripts declared under
    # other classes without acknowledging the inventory floor.)
    script_declared = [
        f for f in declared
        if f.endswith(".py")
        and (
            f.startswith("scripts/")
            or ("/" not in f and not f.startswith("src/"))
        )
    ]
    detail["script_declared"] = script_declared
    if script_declared:
        sits_floor = "tests/test_script_registry.py"
        required_preview = {
            chk for c in classes if c in contracts for chk in contracts[c]["required_checks"]
        }
        executed = set(m.get("checks_executed") or [])
        if sits_floor not in required_preview and sits_floor not in executed:
            problems.append(
                f"declared script path(s) {script_declared[:5]} require {sits_floor} "
                f"(use change class SCRIPT_LIFECYCLE_CHANGE or acknowledge the SITS floor)"
            )

    # 3. repo-state binding: stale check results are impossible — we re-run here
    current_hash = _repo_state_hash()
    detail["repo_state_hash_now"] = current_hash
    if m.get("repo_state_hash") not in ("PENDING", current_hash):
        problems.append(
            f"stale manifest: repo_state_hash {m.get('repo_state_hash')!r} != current {current_hash!r}"
        )

    # 4. execute the required checks (never log-trusted)
    required = sorted({chk for c in classes if c in contracts for chk in contracts[c]["required_checks"]})
    detail["required_checks"] = required
    if run_checks:
        pytest_targets = [c for c in required if c.startswith("tests/")]
        ok, tail = _run_pytest(pytest_targets)
        detail["checks_result"] = tail
        if not ok:
            problems.append(f"required checks FAILED: {tail}")
    status_ok = (m.get("completion_status") == "COMPLETE")
    if status_ok and problems:
        problems.append("manifest claims COMPLETE but validation failed — status is mechanically DENIED")
    return not problems, problems, detail


# One-command construction floor: the feature-math + registry + census + lineage + docs floors.
CONSTRUCTION_FLOOR = (
    "tests/test_formula_registry.py",
    "tests/test_candle_math.py",
    "tests/test_derived_math.py",
    "tests/test_feature_math_lint.py",
    "tests/test_feature_lineage.py",
    "tests/test_geometry_census.py",
    "tests/test_gate2b_closure.py",
    "tests/test_active_models_registry.py",
    "tests/test_current_findings.py",
    "tests/test_doc_citations.py",
    "tests/test_session_log.py",
)


def main() -> int:
    ap = argparse.ArgumentParser(description="Gate-6 construction-protocol validator")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("validate-impact"); p1.add_argument("manifest")
    p2 = sub.add_parser("validate-completion"); p2.add_argument("manifest")
    p2.add_argument("--no-run", action="store_true", help="skip check execution (schema/diff only)")
    sub.add_parser("check")
    args = ap.parse_args()

    if args.cmd == "validate-impact":
        ok, problems = validate_impact(Path(args.manifest))
        print("IMPACT:", "APPROVED" if ok else "BLOCKED")
        for p in problems:
            print("  -", p)
        return 0 if ok else 1
    if args.cmd == "validate-completion":
        ok, problems, detail = validate_completion(Path(args.manifest), run_checks=not args.no_run)
        print("COMPLETION:", "COMPLETE" if ok else "BLOCKED")
        for p in problems:
            print("  -", p)
        print("repo_state:", detail.get("repo_state_hash_now"))
        return 0 if ok else 1
    if args.cmd == "check":
        ok, tail = _run_pytest(list(CONSTRUCTION_FLOOR))
        print("CONSTRUCTION FLOOR:", "GREEN" if ok else "RED")
        print(tail)
        print("as-of", datetime.now(timezone.utc).isoformat(), "repo:", _repo_state_hash())
        return 0 if ok else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
