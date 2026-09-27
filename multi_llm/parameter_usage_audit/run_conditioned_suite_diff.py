#!/usr/bin/env python3
"""Conditioned BEFORE/AFTER suite orchestrator with completion gates."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"D:\Tradelatest")
AUDIT = ROOT / "multi_llm" / "parameter_usage_audit"
SNAP = Path(os.environ.get("TEMP", "/tmp")) / "fail_closed_after_snap_v3"
PY = ROOT / ".venv" / "Scripts" / "python.exe"
DESELECTS = [
    # Hang family: FeaturePipeline -> detect_causal_swings (pre-existing; not Path A)
    "tests/research/test_trace_corpus.py::test_pit_alignment_features_join_by_stream_position",
    "tests/research/test_xauusd_spine_smoke.py::test_spine_collect_runs_on_frozen_candidate_without_active_version_drift",
]
ALLOW_INCOMPLETE = "--incomplete" in sys.argv
PYTEST_FLAGS = [
    "-v",
    "--tb=no",
    "--timeout=120",
    "--timeout-method=thread",
    "--continue-on-collection-errors",
]
for _node in DESELECTS:
    PYTEST_FLAGS.extend(["--deselect", _node])
OUTCOME_RE = re.compile(
    r"^(?P<node>.+?::\S+)\s+(?P<result>PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS)\b"
)

CORE_SURFACE = [
    r"tests\Claude\_fixtures.py",  # PERMISSIVE pad (Path-A required keys)
    r"src\config_layer\state_identity.py",
    r"src\features\crt_state_resolver.py",
    r"scripts\backtest\manual_backtest.py",
    r"scripts\research\retest_divergence_probe.py",
    r"configs\formulas\market_crt_states.yaml",
    r"tests\helpers\crt_config.py",
    r"tests\helpers\__init__.py",
    r"src\config_layer\crt_config_provenance.py",
]


def ts() -> str:
    return datetime.now().astimezone().isoformat()


def log_status(path: Path, msg: str) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(msg + "\n")


def parse_outcomes(log_path: Path) -> tuple[set[str], set[str], set[str]]:
    passed, failed, skipped = set(), set(), set()
    if not log_path.exists():
        return passed, failed, skipped
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = OUTCOME_RE.match(line.strip())
        if not m:
            continue
        node, result = m.group("node"), m.group("result")
        # normalize node to tests/... form if absolute
        if "tests/" in node.replace("\\", "/"):
            node = "tests/" + node.replace("\\", "/").split("tests/", 1)[-1]
        if result == "PASSED" or result == "XPASS":
            passed.add(node)
        elif result in ("FAILED", "ERROR"):
            failed.add(node)
        elif result in ("SKIPPED", "XFAIL"):
            skipped.add(node)
    return passed, failed, skipped




def parse_selected_count(log_path: Path) -> int | None:
    """Return pytest selected-count from collection summary, else None."""
    if not log_path.exists():
        return None
    text = log_path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"(\d+)\s+selected", text)
    if m:
        return int(m.group(1))
    m = re.search(r"collected\s+(\d+)\s+items", text)
    if m:
        collected = int(m.group(1))
        return max(0, collected - len(DESELECTS))
    return None


def outcome_count(passed: Path, failed: Path) -> int:
    pc = len([l for l in passed.read_text(encoding="utf-8").splitlines() if l.strip()]) if passed.exists() else 0
    fc = len([l for l in failed.read_text(encoding="utf-8").splitlines() if l.strip()]) if failed.exists() else 0
    return pc + fc

def write_set(path: Path, items: set[str]) -> None:
    path.write_text("\n".join(sorted(items)) + ("\n" if items else ""), encoding="utf-8")


def run_pytest(label: str, log_path: Path, status_path: Path, junit_path: Path) -> int:
    status_path.write_text(f"{label}_START {ts()}\n", encoding="utf-8")
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{ROOT};{ROOT / 'src'}"
    cmd = [
        str(PY),
        "-m",
        "pytest",
        "tests/",
        *PYTEST_FLAGS,
        f"--junitxml={junit_path}",
    ]
    with log_path.open("w", encoding="utf-8") as out:
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT),
            env=env,
            stdout=out,
            stderr=subprocess.STDOUT,
        )
    log_status(status_path, f"{label}_EXIT={proc.returncode} {ts()}")
    return proc.returncode


def discover_surface() -> list[str]:
    surface = list(CORE_SURFACE)
    for base in (ROOT / "tests", ROOT / "scripts", ROOT / "msip_1_verification_package"):
        if not base.exists():
            continue
        for p in base.rglob("*.py"):
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if "crt_config_for_test" in text:
                surface.append(str(p.relative_to(ROOT)))
    # unique preserve order
    seen = set()
    out = []
    for s in surface:
        s2 = s.replace("/", "\\")
        if s2 not in seen:
            seen.add(s2)
            out.append(s2)
    return out


def snap_surface(surface: list[str]) -> None:
    if SNAP.exists():
        shutil.rmtree(SNAP, ignore_errors=True)
    SNAP.mkdir(parents=True, exist_ok=True)
    (SNAP / "_surface.txt").write_text("\n".join(surface) + "\n", encoding="utf-8")
    for rel in surface:
        src = ROOT / rel
        if src.exists():
            dest = SNAP / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)


def restore_surface() -> None:
    surface = (SNAP / "_surface.txt").read_text(encoding="utf-8").splitlines()
    for rel in surface:
        src = SNAP / rel
        if src.exists():
            dest = ROOT / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)


def checkout_before(surface: list[str]) -> None:
    tracked = []
    for rel in surface:
        posix = rel.replace("\\", "/")
        r = subprocess.run(
            ["git", "ls-files", "--", posix],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        if r.stdout.strip():
            tracked.append(posix)
    if tracked:
        subprocess.run(["git", "checkout", "HEAD", "--", *tracked], cwd=str(ROOT), check=False)
    helper = ROOT / "tests" / "helpers" / "crt_config.py"
    if helper.exists():
        r = subprocess.run(
            ["git", "ls-files", "--", "tests/helpers/crt_config.py"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        if not r.stdout.strip():
            dest = SNAP / "tests" / "helpers" / "crt_config.py"
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(helper, dest)
            helper.unlink()


def classify(n: str) -> str:
    low = n.lower()
    if any(k in low for k in ("provenance", "fingerprint", "compare_surfaces", "schema_fingerprint")):
        return "expected-caused-by-A"
    if "census" in low and "complet" in low:
        return "pre-existing-census"
    if "reachability" in low:
        return "pre-existing-reachability"
    return "SIGNAL"


def write_diff(before_f: set[str], after_f: set[str], before_p: set[str], after_p: set[str]) -> Path:
    became_red = sorted(after_f - before_f)
    became_green = sorted(before_f - after_f)
    still_red = sorted(before_f & after_f)
    lines = [
        "# Full-suite BEFORE/AFTER name diff (conditioned)",
        "",
        "Deselected both sides: " + ", ".join(f"`{d}`" for d in DESELECTS),
        "",
        f"BEFORE failed={len(before_f)} passed={len(before_p)}",
        f"AFTER  failed={len(after_f)} passed={len(after_p)}",
        "",
        "## Became RED (expected: 2 provenance; else SIGNAL)",
    ]
    for n in became_red:
        lines.append(f"- [{classify(n)}] {n}")
    lines += ["", "## Became GREEN"]
    for n in became_green:
        lines.append(f"- [{classify(n)}] {n}")
    lines += ["", "## Still RED both sides (pre-existing; not diff signal)"]
    for n in still_red:
        lines.append(f"- [{classify(n)}] {n}")
    sig = [n for n in became_red if classify(n) == "SIGNAL"]
    exp = [n for n in became_red if classify(n) == "expected-caused-by-A"]
    lines += [
        "",
        f"SUMMARY became_red={len(became_red)} expected_A={len(exp)} SIGNAL={len(sig)} "
        f"became_green={len(became_green)} still_red={len(still_red)}",
        "",
    ]
    path = AUDIT / "FULL_SUITE_DIFF.md"
    text = "\n".join(lines)
    path.write_text(text, encoding="utf-8")
    return path



def completion_gate(
    before_failed: Path,
    after_failed: Path,
    before_passed: Path,
    after_passed: Path,
    diff_path: Path,
    before_log: Path,
    after_log: Path,
) -> None:
    """Hard gate: never claim DIFF_COMPLETE unless the run is actually complete.

    Accept when:
      - both sides produced outcomes for >= 95% of selected tests, OR
      - --incomplete was explicitly passed on the orchestrator CLI
    Same-partial (~equal %) without --incomplete is REJECTED so we do not
    repeat the false DIFF_COMPLETE at ~27%.
    """
    errors: list[str] = []
    for p in (before_failed, after_failed, before_passed, after_passed):
        if not p.exists():
            errors.append(f"missing {p.name}")
    for p in (before_passed, after_passed):
        if not p.exists() or not p.read_text(encoding="utf-8").strip():
            errors.append(f"passed list empty: {p.name}")
    if not diff_path.exists() or diff_path.stat().st_size == 0:
        errors.append("FULL_SUITE_DIFF.md missing/empty")
    else:
        head = diff_path.read_text(encoding="utf-8")[:300]
        if "BEFORE/AFTER" not in head and "before" not in head.lower():
            errors.append("FULL_SUITE_DIFF.md missing header")

    b_sel = parse_selected_count(before_log)
    a_sel = parse_selected_count(after_log)
    b_out = outcome_count(before_passed, before_failed)
    a_out = outcome_count(after_passed, after_failed)

    def pct(outcomes: int, selected: int | None) -> float | None:
        if not selected or selected <= 0:
            return None
        return 100.0 * outcomes / selected

    b_pct = pct(b_out, b_sel)
    a_pct = pct(a_out, a_sel)

    complete_enough = (
        b_pct is not None and a_pct is not None and b_pct >= 95.0 and a_pct >= 95.0
    )

    if ALLOW_INCOMPLETE:
        log_status(
            AUDIT / "DIFF_STATUS.txt",
            f"INCOMPLETE_FLAG_SET before_pct={b_pct} after_pct={a_pct}",
        )
    elif complete_enough:
        pass
    else:
        errors.append(
            f"incomplete run before_out={b_out}/{b_sel} ({b_pct}) "
            f"after_out={a_out}/{a_sel} ({a_pct}); "
            f"need >=95% both sides or pass --incomplete"
        )

    if errors:
        msg = "COMPLETION_GATE_FAILED\n" + "\n".join(errors) + "\n"
        (AUDIT / "DIFF_STATUS.txt").write_text(msg, encoding="utf-8")
        print(msg, file=sys.stderr)
        sys.exit(2)


def main() -> int:
    AUDIT.mkdir(parents=True, exist_ok=True)
    (AUDIT / "DIFF_STATUS.txt").write_text(f"ORCH_START {ts()}\n", encoding="utf-8")

    # --- AFTER (current fail-closed tree) ---
    after_log = AUDIT / "suite_AFTER.txt"
    after_status = AUDIT / "suite_AFTER_status.txt"
    after_junit = AUDIT / "suite_AFTER_junit.xml"
    run_pytest("AFTER", after_log, after_status, after_junit)
    after_p, after_f, _ = parse_outcomes(after_log)
    # also merge junit if present
    if after_junit.exists():
        try:
            import xml.etree.ElementTree as ET

            root = ET.parse(after_junit).getroot()
            for tc in root.iter("testcase"):
                node = f"{tc.attrib.get('classname', '')}::{tc.attrib.get('name', '')}"
                if "tests." in node:
                    # classname style tests.foo.bar::name -> tests/foo/bar.py::name approx keep as-is from log primarily
                    pass
                if tc.find("failure") is not None or tc.find("error") is not None:
                    after_f.add(node)
                elif tc.find("skipped") is None:
                    after_p.add(node)
        except Exception as e:
            log_status(AUDIT / "DIFF_STATUS.txt", f"AFTER_JUNIT_PARSE_WARN {e}")

    write_set(AUDIT / "suite_AFTER_failed.txt", after_f)
    write_set(AUDIT / "suite_AFTER_passed.txt", after_p)
    log_status(AUDIT / "DIFF_STATUS.txt", f"AFTER_PARSED failed={len(after_f)} passed={len(after_p)} {ts()}")

    a_sel = parse_selected_count(after_log)
    a_out = len(after_p) + len(after_f)
    a_pct = (100.0 * a_out / a_sel) if a_sel else None
    if not ALLOW_INCOMPLETE and (a_pct is None or a_pct < 95.0):
        (AUDIT / "DIFF_STATUS.txt").write_text(
            f"ABORT_AFTER_INCOMPLETE passed={len(after_p)} failed={len(after_f)} selected={a_sel} pct={a_pct} {ts()}\n",
            encoding="utf-8",
        )
        return 3

    # --- snap + BEFORE ---
    surface = discover_surface()
    snap_surface(surface)
    checkout_before(surface)

    before_log = AUDIT / "suite_BEFORE.txt"
    before_status = AUDIT / "suite_BEFORE_status.txt"
    before_junit = AUDIT / "suite_BEFORE_junit.xml"
    run_pytest("BEFORE", before_log, before_status, before_junit)
    before_p, before_f, _ = parse_outcomes(before_log)
    write_set(AUDIT / "suite_BEFORE_failed.txt", before_f)
    write_set(AUDIT / "suite_BEFORE_passed.txt", before_p)
    log_status(AUDIT / "DIFF_STATUS.txt", f"BEFORE_PARSED failed={len(before_f)} passed={len(before_p)} {ts()}")

    # restore AFTER surface regardless
    restore_surface()
    log_status(AUDIT / "DIFF_STATUS.txt", f"RESTORED_AFTER {ts()}")

    b_sel = parse_selected_count(before_log)
    b_out = len(before_p) + len(before_f)
    b_pct = (100.0 * b_out / b_sel) if b_sel else None
    if not ALLOW_INCOMPLETE and (b_pct is None or b_pct < 95.0):
        (AUDIT / "DIFF_STATUS.txt").write_text(
            f"ABORT_BEFORE_INCOMPLETE passed={len(before_p)} failed={len(before_f)} selected={b_sel} pct={b_pct} {ts()}\n",
            encoding="utf-8",
        )
        return 4

    diff_path = write_diff(before_f, after_f, before_p, after_p)
    completion_gate(
        AUDIT / "suite_BEFORE_failed.txt",
        AUDIT / "suite_AFTER_failed.txt",
        AUDIT / "suite_BEFORE_passed.txt",
        AUDIT / "suite_AFTER_passed.txt",
        diff_path,
        before_log,
        after_log,
    )
    (AUDIT / "DIFF_STATUS.txt").write_text(f"DIFF_COMPLETE {ts()}\n", encoding="utf-8")
    print(diff_path.read_text(encoding="utf-8")[-1500:])
    return 0


if __name__ == "__main__":
    sys.exit(main())
