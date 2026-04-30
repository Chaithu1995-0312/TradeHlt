"""Run Phase A tests and write results to file."""
import subprocess
import sys

result = subprocess.run(
    [sys.executable, "-m", "pytest",
     "tests/test_expansion_governance_bridge.py",
     "-v", "--tb=short", "--no-header"],
    capture_output=True,
    text=True,
    cwd=r"d:\Tradelatest",
)

output = result.stdout + result.stderr
with open("phase_a_test_results.txt", "w", encoding="utf-8") as f:
    f.write(output)
    f.write(f"\nReturn code: {result.returncode}\n")

print("Done. Return code:", result.returncode)
print("Output length:", len(output))
print(output[-2000:])