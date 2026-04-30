import subprocess, sys, json, os
os.chdir(r"d:\Tradelatest")
proc = subprocess.Popen(
    [sys.executable, "-m", "pytest",
     "tests/test_expansion_governance_bridge.py",
     "tests/test_regime_classifier.py",
     "tests/test_portfolio_allocator.py",
     "tests/test_scanner_ranker.py",
     "tests/test_execution_loop.py",
     "tests/test_analytics.py",
     "-v", "--tb=short"],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=r"d:\Tradelatest",
)
stdout, stderr = proc.communicate(timeout=180)
results = {"returncode": proc.returncode, "stdout": stdout.decode("utf-8", errors="replace"), "stderr": stderr.decode("utf-8", errors="replace")}
with open("test_capture.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)