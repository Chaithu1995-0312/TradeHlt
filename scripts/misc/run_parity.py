"""
run_parity.py — fully automated C++/Python parity runner.

Executes the four steps in order and exits non-zero if parity fails:
  1. generate_vectors.py  → test_vectors.json  (35-feature canonical schema)
  2. export_model.py      → model.json         (35-input 3-layer ternary model)
  3. python_runner.py     → python_outputs.json
  4. cpp_runner.exe       → cpp_outputs.json
  5. compare.py           → prints delta report; exits 1 on mismatch

All artefacts are written to --work-dir (default: results/parity/).
"""

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).parent.parent.parent
_CPP_RUNNER   = _REPO / "tools"    / "cpp"      / "cpp_runner.exe"
_GEN_VECTORS  = _REPO / "scripts"  / "data"     / "generate_vectors.py"
_EXPORT_MODEL = _REPO / "scripts"  / "export"   / "export_model.py"
_PY_RUNNER    = _REPO / "scripts"  / "misc"     / "python_runner.py"
_COMPARE      = _REPO / "scripts"  / "analysis" / "compare.py"


def _run(cmd, cwd, label):
    print(f"\n{'─'*60}\n{label}\n{'─'*60}")
    result = subprocess.run(cmd, cwd=str(cwd), capture_output=False)
    if result.returncode != 0:
        print(f"[FAIL] {label} exited with code {result.returncode}")
        sys.exit(result.returncode)


def main():
    p = argparse.ArgumentParser(description="C++/Python BitNet parity runner")
    p.add_argument(
        "--work-dir", default="results/parity",
        help="Directory for intermediate artefacts (created if missing)",
    )
    p.add_argument(
        "--n-vectors", default=200, type=int,
        help="Number of test vectors to generate",
    )
    args = p.parse_args()

    work_dir = Path(args.work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    # Step 1 — generate test vectors
    _run(
        [sys.executable, str(_GEN_VECTORS)],
        cwd=work_dir,
        label="Step 1/4  generate_vectors.py",
    )

    # Step 2 — export model
    _run(
        [sys.executable, str(_EXPORT_MODEL)],
        cwd=work_dir,
        label="Step 2/4  export_model.py",
    )

    # Step 3 — Python inference
    _run(
        [sys.executable, str(_PY_RUNNER)],
        cwd=work_dir,
        label="Step 3/4  python_runner.py",
    )

    # Step 4 — C++ inference
    if not _CPP_RUNNER.exists():
        print(f"\n[SKIP] cpp_runner.exe not found at {_CPP_RUNNER}. Skipping C++ step.")
        sys.exit(0)

    _run(
        [str(_CPP_RUNNER)],
        cwd=work_dir,
        label="Step 4/4  cpp_runner.exe",
    )

    # Step 5 — compare
    py_path  = work_dir / "python_outputs.json"
    cpp_path = work_dir / "cpp_outputs.json"

    py_out  = json.loads(py_path.read_text())
    cpp_out = json.loads(cpp_path.read_text())

    mismatches = []
    for i, (py, cpp) in enumerate(zip(py_out, cpp_out)):
        py_val  = float(py["final"])
        cpp_val = float(cpp["final"])
        if not math.isclose(py_val, cpp_val, abs_tol=1e-5):
            mismatches.append((i, py_val, cpp_val))

    print(f"\n{'─'*60}\nParity result: {len(py_out)} vectors compared\n{'─'*60}")
    if mismatches:
        print(f"[FAIL] {len(mismatches)} mismatch(es):")
        for idx, py_val, cpp_val in mismatches:
            print(f"  [{idx}]  Python={py_val:.8f}  C++={cpp_val:.8f}  diff={abs(py_val-cpp_val):.2e}")
        sys.exit(1)
    else:
        print("[PASS] All outputs match within abs_tol=1e-5")
        sys.exit(0)


if __name__ == "__main__":
    main()
