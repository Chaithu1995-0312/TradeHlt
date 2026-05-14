"""
apply_llm_suggestions.py
========================
Reads LLM hyperparameter suggestions (JSON) and dispatches to the right
training script. Used by the Groq bridge `--apply-to-training` mode.

Supported targets:
  gaussian  → phase5_calibration.py --opportunities ... --feature-subset ...
              --class-weights ... --rr-buckets ...
  zone      → discover_zones.py with n_clusters / min_samples / feature_weights
  rr        → rr_pattern_miner.py with ridge_alpha / confidence_bypass_threshold
              / drift_threshold

Each branch parses the JSON, builds a subprocess command, and runs it.
The script does NOT execute any training logic itself — it is a dispatcher.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_suggestions(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8").strip()
    # Strip code fences / surrounding text if present.
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    fence = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw)
    if fence:
        try:
            return json.loads(fence.group(1))
        except json.JSONDecodeError:
            pass
    brace = re.search(r"\{[\s\S]+\}", raw)
    if brace:
        return json.loads(brace.group(0))
    raise ValueError(f"could not parse JSON from {path}")


def _csv(values) -> str:
    return ",".join(str(v) for v in values)


def _dispatch_gaussian(sugg: dict, opportunities: str, version: str) -> int:
    feature_subset = sugg.get("feature_subset", [])
    class_weights = sugg.get("class_weights", [])
    rr_buckets = sugg.get("rr_buckets", [])
    script = _REPO_ROOT / "scripts" / "training" / "phase5_calibration.py"
    cmd = [
        sys.executable, str(script),
        "--opportunities", opportunities,
        "--version", version,
        "--train",
    ]
    if feature_subset:
        cmd += ["--feature-subset", _csv(feature_subset)]
    if class_weights:
        cmd += ["--class-weights", _csv(class_weights)]
    if rr_buckets:
        cmd += ["--rr-buckets", _csv(rr_buckets)]
    print("→", " ".join(cmd))
    return subprocess.call(cmd, cwd=_REPO_ROOT)


def _dispatch_zone(sugg: dict, opportunities: str, version: str) -> int:
    n_clusters = sugg.get("n_clusters")
    min_samples = sugg.get("min_samples")
    feature_weights = sugg.get("feature_weights", [])
    script = _REPO_ROOT / "scripts" / "research" / "discover_zones.py"
    if not script.exists():
        print(f"ERROR: zone-discovery script not found at {script}", file=sys.stderr)
        return 1
    out_path = _REPO_ROOT / "models" / f"zone_registry_{version}.json"
    cmd = [
        sys.executable, str(script),
        "--opportunities", opportunities,
        "--output", str(out_path),
    ]
    if n_clusters is not None:
        cmd += ["--n-clusters", str(int(n_clusters))]
    if min_samples is not None:
        cmd += ["--min-samples", str(int(min_samples))]
    if feature_weights:
        cmd += ["--feature-weights", _csv(feature_weights)]
    print("→", " ".join(cmd))
    return subprocess.call(cmd, cwd=_REPO_ROOT)


def _dispatch_rr(sugg: dict, opportunities: str, version: str) -> int:
    ridge_alpha = sugg.get("ridge_alpha")
    confidence_bypass = sugg.get("confidence_bypass_threshold")
    drift_threshold = sugg.get("drift_threshold")
    script_candidates = [
        _REPO_ROOT / "src" / "training" / "rr_pattern_miner.py",
        _REPO_ROOT / "scripts" / "training" / "rr_pattern_miner.py",
    ]
    script = next((s for s in script_candidates if s.exists()), None)
    if script is None:
        print(
            "ERROR: rr_pattern_miner.py not found in src/training or scripts/training. "
            "Wire the path explicitly in apply_llm_suggestions.py.",
            file=sys.stderr,
        )
        return 1
    cmd = [
        sys.executable, str(script),
        "--opportunities", opportunities,
        "--version", version,
    ]
    if ridge_alpha is not None:
        cmd += ["--ridge-alpha", str(float(ridge_alpha))]
    if confidence_bypass is not None:
        cmd += ["--confidence-bypass", str(float(confidence_bypass))]
    if drift_threshold is not None:
        cmd += ["--drift-threshold", str(float(drift_threshold))]
    print("→", " ".join(cmd))
    return subprocess.call(cmd, cwd=_REPO_ROOT)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--target-model", required=True, choices=("gaussian", "zone", "rr"))
    ap.add_argument("--suggestions-file", required=True, type=Path,
                    help="LLM JSON response (raw or with code-fences)")
    ap.add_argument("--opportunities", required=True,
                    help="Path to opportunity JSONL log used for training")
    ap.add_argument("--version", required=True,
                    help="Version label embedded in the trained model filename")
    args = ap.parse_args(argv)

    if not args.suggestions_file.exists():
        print(f"ERROR: {args.suggestions_file} not found", file=sys.stderr)
        return 1
    sugg = _load_suggestions(args.suggestions_file)

    if args.target_model == "gaussian":
        return _dispatch_gaussian(sugg, args.opportunities, args.version)
    if args.target_model == "zone":
        return _dispatch_zone(sugg, args.opportunities, args.version)
    if args.target_model == "rr":
        return _dispatch_rr(sugg, args.opportunities, args.version)
    return 1


if __name__ == "__main__":
    sys.exit(main())
