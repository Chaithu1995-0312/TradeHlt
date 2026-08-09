"""Thin CLI: build an OpportunityEpisode corpus (protocol OE_L1).

Research tooling only. Reads the production ledger / detection stream OFFLINE and
writes to results/research/episodes/. Never writes a production surface, never runs
in a hot path, and grants no promotion authority (CLAUDE.md §6.5).

Usage:
  python scripts/research/build_episodes.py --instrument BNBUSDT --max-units 500
  python scripts/research/build_episodes.py --instrument BNBUSDT --sizing-probe
  python scripts/research/build_episodes.py \\
      --opportunities logs/BNBUSDT/bnbusdt_training_20260524/opportunities.jsonl \\
      --candles data/BNBUSDT_M15.csv --instrument BNBUSDT --observation-only
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT / "scripts" / "analysis"))

from bnbusdt_trade_anatomy import load_candles  # noqa: E402
from research.episodes.projectors.detection import project_stream  # noqa: E402
from research.episodes.projectors.spine import (  # noqa: E402
    entry_geometry_parity,
    probe_ledger,
    project_ledger,
    read_ledger,
)
from research.episodes.protocol import (  # noqa: E402
    MAX_FORWARD,
    PROTOCOL_ID,
    compute_protocol_hash,
)
from research.episodes.store import (  # noqa: E402
    corpus_dir,
    default_root,
    sizing_probe,
    verify_corpus,
    write_episodes,
)


def _iter_jsonl(path: Path, max_scan: int | None):
    with path.open(encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            if max_scan is not None and i >= max_scan:
                break
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--instrument", default="BNBUSDT")
    ap.add_argument("--population", default="DETECTION_STREAM",
                    choices=["DETECTION_STREAM", "SPINE_TRADE"],
                    help="HYPOTHESIS_SIGNAL lands in a later phase")
    ap.add_argument("--trades", default=None,
                    help="SPINE_TRADE only: path to {INSTRUMENT}_trades.csv")
    ap.add_argument("--probe-ledger", action="store_true",
                    help="SPINE_TRADE only: report ledger completeness and exit")
    ap.add_argument("--opportunities",
                    default="logs/BNBUSDT/bnbusdt_training_20260524/opportunities.jsonl")
    ap.add_argument("--candles", default="data/BNBUSDT_M15.csv")
    ap.add_argument("--max-forward", type=int, default=MAX_FORWARD)
    ap.add_argument("--max-units", type=int, default=None, help="cap episodes built")
    ap.add_argument("--max-scan", type=int, default=None, help="cap source lines read")
    ap.add_argument("--observation-only", action="store_true",
                    help="drop the regenerable Derived cache from storage")
    ap.add_argument("--sizing-probe", action="store_true",
                    help="measure bytes/episode and exit without writing a corpus")
    ap.add_argument("--out-root", default=None)
    args = ap.parse_args(argv)

    candle_path = ROOT / args.candles
    if not candle_path.is_file():
        print(f"ERROR: candles not found: {candle_path}")
        return 2

    protocol_hash = compute_protocol_hash({"instrument": args.instrument})

    if args.population == "SPINE_TRADE":
        if not args.trades:
            print("ERROR: --trades is required for SPINE_TRADE")
            return 2
        trades_path = ROOT / args.trades
        if not trades_path.is_file():
            print(f"ERROR: trades ledger not found: {trades_path}")
            return 2

        rows = read_ledger(trades_path)
        probe = probe_ledger(rows)
        print("-- ledger completeness probe --")
        print(json.dumps(probe, indent=2))
        if not probe["required_present"]:
            print("ERROR: ledger missing required columns — refusing to synthesize them")
            return 2
        if args.probe_ledger:
            return 0

        candles, ts_to_idx, _ = load_candles(candle_path)
        episodes, skips = project_ledger(
            rows, candles, ts_to_idx,
            instrument=args.instrument,
            max_forward=args.max_forward,
            protocol_hash=protocol_hash,
            cache_derived=not args.observation_only,
            candle_source=str(candle_path.relative_to(ROOT)),
            source_run_id=trades_path.parent.name,
        )
        parity = entry_geometry_parity(episodes, rows, candles)
        print(f"\nentry-geometry parity: "
              f"{'OK' if parity['ok'] else 'MISMATCH ' + str(parity['mismatches'][:3])} "
              f"({parity['n']} trades)")
        if not parity["ok"]:
            return 1
    else:
        opp_path = ROOT / args.opportunities
        if not opp_path.is_file():
            print(f"ERROR: opportunities not found: {opp_path}")
            return 2
        candles, ts_to_idx, _ = load_candles(candle_path)
        episodes, skips = project_stream(
            _iter_jsonl(opp_path, args.max_scan),
            candles, ts_to_idx,
            instrument=args.instrument,
            max_forward=args.max_forward,
            max_units=args.max_units,
            protocol_hash=protocol_hash,
            cache_derived=not args.observation_only,
            candle_source=str(candle_path.relative_to(ROOT)),
            source_run_id=opp_path.parent.name,
        )

    print(f"protocol      : {PROTOCOL_ID} ({protocol_hash[:16]})")
    print(f"instrument    : {args.instrument}  population: {args.population}")
    print(f"candles       : {len(candles)} bars from {candle_path.name}")
    print(f"episodes built: {len(episodes)}")
    print(f"skips         : {json.dumps(skips, sort_keys=True)}")

    if not episodes:
        print("no episodes built — nothing written")
        return 1

    if args.sizing_probe:
        probe = sizing_probe(episodes)
        print("\n-- sizing probe (P5 gate) --")
        print(json.dumps(probe, indent=2))
        full_stream = 139_942  # F-022 detection count, BNBUSDT reference corpus
        per = probe["gz_bytes_per_episode_observation_only"]
        print(f"\nextrapolated full DETECTION_STREAM ({full_stream:,} units, observation-only): "
              f"{per * full_stream / 1e9:.2f} GB")
        return 0

    root = Path(args.out_root) if args.out_root else default_root(ROOT)
    out_dir = corpus_dir(root, args.population, args.instrument)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = out_dir / run_id

    manifest = write_episodes(episodes, out_dir,
                              cache_derived=not args.observation_only)
    manifest["skips"] = skips
    manifest["protocol_id"] = PROTOCOL_ID
    manifest["protocol_hash"] = protocol_hash
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    check = verify_corpus(manifest["path"])
    print(f"\nwrote         : {manifest['path']}")
    print(f"bytes         : {manifest['bytes_on_disk']:,} "
          f"({manifest['bytes_per_episode']:,} B/episode)")
    print(f"hash verify   : {'OK' if check['ok'] else 'MISMATCH ' + str(check)}")
    return 0 if check["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
