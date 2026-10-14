"""Rebuild the XAUUSD bar-features page: runs the six steps in README.md in order, from the repo
root (configs/production/ACTIVE_VERSION is resolved relative to it). Stops on the first failure."""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
STEPS = ["xau_10d_features.py", "zone_full.py", "zone_10d.py", "zone_edge.py", "attach_now.py", "render_xau.py"]

for step in STEPS:
    print(f"== {step}", flush=True)
    subprocess.run([sys.executable, str(HERE / step)], cwd=ROOT, check=True)
print("done:", HERE / "xau_bar_features.html")
