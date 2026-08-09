"""CLI: ENV_SHADOW_W0_V1 — batch shadow log of Envelope predictions (weight 0).

Usage:
  python scripts/research/run_envelope_shadow_weight0.py
  python scripts/research/run_envelope_shadow_weight0.py --max-rows 5000
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

from research.envelope_offline.shadow import (  # noqa: E402
    SHADOW_CHARTER_ID,
    ShadowConfig,
    run_shadow,
)


def _resolve_bundle(instrument: str, explicit: str | None) -> Path:
    if explicit:
        p = Path(explicit)
        return p if p.is_absolute() else ROOT / p
    pointer = ROOT / "results" / "envelope_offline" / instrument / "LATEST" / "pointer.json"
    if not pointer.is_file():
        raise FileNotFoundError(f"no offline train LATEST at {pointer}")
    data = json.loads(pointer.read_text(encoding="utf-8"))
    return Path(data["out_dir"])


def _resolve_dataset(instrument: str, explicit: str | None) -> Path:
    if explicit:
        p = Path(explicit)
        return p if p.is_absolute() else ROOT / p
    pointer = ROOT / "results" / "clean_labels" / instrument / "LATEST" / "pointer.json"
    if not pointer.is_file():
        raise FileNotFoundError(f"no clean-label LATEST at {pointer}")
    data = json.loads(pointer.read_text(encoding="utf-8"))
    return Path(data["paths"]["dataset"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--instrument", default="BNBUSDT")
    ap.add_argument("--bundle-dir", default=None, help="ENV_OFFLINE_TRAIN_V1 run dir")
    ap.add_argument("--dataset", default=None, help="TN_ENV_CLEAN_L2 clean_labels.jsonl")
    ap.add_argument("--max-rows", type=int, default=None)
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args(argv)

    try:
        bundle_dir = _resolve_bundle(args.instrument, args.bundle_dir)
        dataset = _resolve_dataset(args.instrument, args.dataset)
    except FileNotFoundError as exc:
        print(f"[{SHADOW_CHARTER_ID}] ERROR: {exc}")
        return 2

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = (
        Path(args.out_dir)
        if args.out_dir
        else ROOT / "results" / "envelope_shadow" / args.instrument / run_id
    )
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir

    print(f"[{SHADOW_CHARTER_ID}] bundle={bundle_dir}")
    print(f"[{SHADOW_CHARTER_ID}] dataset={dataset}")
    print(f"[{SHADOW_CHARTER_ID}] out={out_dir}")

    cfg = ShadowConfig(
        bundle_dir=str(bundle_dir),
        dataset_path=str(dataset),
        out_dir=str(out_dir),
        instrument=args.instrument,
        max_rows=args.max_rows,
    )
    try:
        summary = run_shadow(cfg)
    except Exception as exc:  # noqa: BLE001
        print(f"[{SHADOW_CHARTER_ID}] FAILED: {type(exc).__name__}: {exc}")
        return 1

    latest = ROOT / "results" / "envelope_shadow" / args.instrument / "LATEST"
    latest.mkdir(parents=True, exist_ok=True)
    (latest / "pointer.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "out_dir": str(out_dir),
                "charter_id": SHADOW_CHARTER_ID,
                "status": summary["status"],
                "shadow_path": summary["shadow_path"],
                "summary_path": str(out_dir / "summary.json"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    docs = ROOT / "docs" / "analysis" / "envelope-shadow-w0-BNBUSDT.LATEST.md"
    docs.write_text((out_dir / "report.md").read_text(encoding="utf-8"), encoding="utf-8")
    (ROOT / "docs" / "analysis" / "envelope-shadow-w0-BNBUSDT.LATEST.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    print(f"[{SHADOW_CHARTER_ID}] status={summary['status']} n_ok={summary['n_ok']}")
    for k, c in summary["calibration"].items():
        print(f"  {k}: ic={c['spearman_ic_vs_actual']}")
    print(f"[{SHADOW_CHARTER_ID}] wrote {out_dir}")
    return 0 if summary["status"] == "SHADOW_COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
