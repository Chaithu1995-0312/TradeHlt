"""Semantic OS integration run (CLI). Thin wrapper over src/semantics/integration.

Runs the real backtest twice on one corpus (observed + plain), refuses to judge unless the two event
streams are identical (replay gate), then compares every observed bar with the v2 concept contracts.
Writes results/semantic_os_integration/<stamp>/{rows.jsonl, summary.json, report.md}.
Not a performance run: no P&L, expectancy or win rate.

    venv/Scripts/python.exe scripts/governance/semantic_os_integration.py
    venv/Scripts/python.exe scripts/governance/semantic_os_integration.py --csv data/mt5/XAUUSD_W2026-07-06-to-2026-08-07.csv
    venv/Scripts/python.exe scripts/governance/semantic_os_integration.py --version v2_htfcrt_e01lifecycle_shadow_2026_10
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def main(argv=None) -> int:
    from semantics.integration.observe import (
        MONTH_SLICE, observe_backtest, plain_backtest, prod_version, read_events, replay_gate,
    )

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--csv", default=str(MONTH_SLICE), help="XAUUSD M15 corpus (default: the one-month slice)")
    ap.add_argument("--instrument", default="XAUUSD")
    ap.add_argument("--out", default=str(ROOT / "results" / "semantic_os_integration"))
    ap.add_argument("--version", default=None,
                    help="run under this config version (e.g. a non-promoted shadow) instead of ACTIVE_VERSION")
    args = ap.parse_args(argv)

    from semantics.integration import CheckContext, d_levels, run_checks, write_report
    from semantics.registry import active_config_value, load_concept_contracts, load_representation_shards

    csv = Path(args.csv).resolve()
    out = Path(args.out) / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    with prod_version(args.version):
        from config_layer.production_config import get_prod_section

        sweep_semantics = get_prod_section("feature_pipeline")["sweep_semantics"]
        observed = observe_backtest(csv, out, instrument=args.instrument)
        plain = plain_backtest(csv, out, instrument=args.instrument)
    gate = replay_gate(observed.events, read_events(plain))
    manifest = json.loads((observed.run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    identity = {
        "corpus": str(csv), "corpus_sha256": _sha256(csv), "bars_observed": len(observed.bars),
        "bars_with_feature_row": len(observed.features or {}),
        "config_version": manifest.get("fingerprint", {}).get("config_version"),
        "config_hash": manifest.get("fingerprint", {}).get("config_hash"),
        "code_sha": _git("rev-parse", "HEAD"), "tree_dirty": bool(_git("status", "--porcelain", "--", "src")),
        "observed_run": str(observed.run_dir), "plain_run": str(plain),
        "entry_semantics": active_config_value("setup.entry_semantics"),
        "version_override": args.version, "sweep_semantics": sweep_semantics,
    }
    concepts = load_concept_contracts()["concepts"]
    shards = load_representation_shards()
    if gate["status"] != "PASS":
        summary = write_report(out, [], identity, gate, d_levels(concepts, shards, []))
        print(json.dumps({"out": str(out), **summary["replay_gate"]}, indent=2))
        return 2
    rows = run_checks(CheckContext(observed.bars, observed.events, concepts,
                                   features=observed.features, history=observed.history), shards)
    summary = write_report(out, rows, identity, gate, d_levels(concepts, shards, rows))
    print(json.dumps({"out": str(out), "replay_gate": gate["status"], "verdicts": summary["verdicts"],
                      "d_levels": summary["d_levels"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
