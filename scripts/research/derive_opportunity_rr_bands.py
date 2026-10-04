"""
derive_opportunity_rr_bands.py
===============================
Phase 1 of the layered-outcome-ontology plan (docs/implementation_plan/
i-have-everything-i-crispy-dawn.md): a READ-ONLY arithmetic deriver over an existing
opportunity_scanner.py run. Produces the sidecar `opportunities_rr_bands.jsonl`
registered as STR-OPP-RR-BAND-SIDECAR in docs/governance/jsonl_claim_catalog.yaml.

Does NOT re-simulate the SEM-037 kernel, does NOT touch the source file, does NOT
change the scanner. Every field it writes is CC-OPP-BAND-RESTATEMENT admissible (a
recomputable arithmetic fact) and CC-OPP-BAND-NOT-ECONOMIC refuses any world-reading
of it — this script asserts nothing about profitability, win rate, or trade quality.

Thin wrapper only (CLAUDE.md 3.3): all business logic lives in
`research.opportunity_bands` / `research.band_tables`. This file is argparse + I/O.

Output rows carry the JOIN KEYS (timestamp, instrument, direction) plus the derived
fields only — NOT a duplicate of entry/sl/tp/outcome/rr_achieved/mfe/mae/features,
which remain the source of record on opportunities.jsonl (a duplicated copy is a
second authority the claim catalog does not grant and this design set out to avoid).

Usage:
  python scripts/research/derive_opportunity_rr_bands.py \
      --input logs/XAUUSD/20260913_130531/opportunities.jsonl
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Allow running as a plain script: prepend src/ to sys.path (opportunity_scanner.py's
# own convention).
_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from research.band_tables import load_band_table  # noqa: E402
from research.opportunity_bands import (  # noqa: E402
    OpportunityBandsError,
    derive_row_bands,
    sidecar_header,
)

logger = logging.getLogger("DeriveOpportunityRRBands")

SIDECAR_FILENAME = "opportunities_rr_bands.jsonl"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", required=True, type=Path,
                    help="path to an opportunity_scanner.py output JSONL (must start with a run_header line)")
    p.add_argument("--output", type=Path, default=None,
                    help=f"sidecar output path (default: colocated with --input as {SIDECAR_FILENAME})")
    p.add_argument("--force", action="store_true",
                    help="overwrite an existing sidecar (default: fail closed if it already exists)")
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args(argv)


def derive_file(input_path: Path, output_path: Path, *, force: bool = False) -> dict:
    """Reads input_path (a scanner run), writes output_path (the sidecar).

    Returns a summary dict {rows_read, rows_written, errors, exit_mechanism_counts,
    ...} for the caller to log/assert on. Raises FileExistsError if output_path
    exists and force is False — never silently overwrites a prior derivation.
    """
    if not input_path.exists():
        raise FileNotFoundError(f"--input does not exist: {input_path}")
    if output_path.exists() and not force:
        raise FileExistsError(
            f"{output_path} already exists — pass --force to overwrite, or this run's "
            "prior derivation stays untouched (fail-closed, mirrors the scanner's own "
            "overwrite-in-place caution)")

    econ_table = load_band_table("BT-RR-ECON-V1")
    capture_table = load_band_table("BT-CAPTURE-V1")

    run_header: dict | None = None
    rows_read = 0
    rows_written = 0
    errors: list[str] = []
    exit_mechanism_counts: dict[str, int] = {}

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(input_path, encoding="utf-8") as fin, open(output_path, "w", encoding="utf-8") as fout:
        for line_no, line in enumerate(fin, start=1):
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)

            if record.get("type") == "run_header":
                if run_header is not None:
                    raise OpportunityBandsError(f"{input_path}: more than one run_header line")
                run_header = record
                header = sidecar_header(
                    source_path=str(input_path).replace("\\", "/"),
                    source_run_id=record.get("run_id", "UNKNOWN"),
                    source_trace_id=record.get("trace_id", "UNKNOWN"),
                )
                fout.write(json.dumps(header) + "\n")
                continue

            if run_header is None:
                raise OpportunityBandsError(
                    f"{input_path}:{line_no}: data row before any run_header line — "
                    "refusing to derive from a file whose source run is unidentified")

            rows_read += 1
            try:
                d = derive_row_bands(record, econ_table=econ_table, capture_table=capture_table)
            except OpportunityBandsError as exc:
                errors.append(f"{input_path}:{line_no}: {exc}")
                continue

            exit_mechanism_counts[d.exit_mechanism] = exit_mechanism_counts.get(d.exit_mechanism, 0) + 1
            out_row = {
                # Join keys — copied verbatim from the source, not a claim of any kind.
                "timestamp": record["timestamp"],
                "instrument": record["instrument"],
                "direction": record["direction"],
                # Derived fields — every one CC-OPP-BAND-RESTATEMENT admissible.
                "exit_mechanism": d.exit_mechanism,
                "trail_state": d.trail_state,
                "risk_distance": d.risk_distance,
                "mfe_r": d.mfe_r,
                "mae_r": d.mae_r,
                "exit_bounded_capture": d.exit_bounded_capture,
                "capture_state": d.capture_state,
                "rr_band": d.rr_band,
            }
            fout.write(json.dumps(out_row) + "\n")
            rows_written += 1

    if run_header is None:
        # Nothing valid was written; remove the empty/partial file rather than leave
        # a header-less sidecar that would silently fail CC-ENVELOPE-SHAPE.
        output_path.unlink(missing_ok=True)
        raise OpportunityBandsError(f"{input_path}: no run_header line found")

    return {
        "input": str(input_path),
        "output": str(output_path),
        "run_id": run_header.get("run_id"),
        "trace_id": run_header.get("trace_id"),
        "rows_read": rows_read,
        "rows_written": rows_written,
        "errors": errors,
        "exit_mechanism_counts": exit_mechanism_counts,
    }


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    output_path = args.output or (args.input.parent / SIDECAR_FILENAME)
    try:
        summary = derive_file(args.input, output_path, force=args.force)
    except (FileNotFoundError, FileExistsError, OpportunityBandsError) as exc:
        logger.error(str(exc))
        return 1

    logger.info("wrote %d/%d rows to %s (run_id=%s trace_id=%s)",
                summary["rows_written"], summary["rows_read"], summary["output"],
                summary["run_id"], summary["trace_id"])
    if summary["errors"]:
        logger.warning("%d rows failed to classify (fail-closed, not skipped silently):",
                       len(summary["errors"]))
        for err in summary["errors"][:10]:
            logger.warning("  %s", err)
        if len(summary["errors"]) > 10:
            logger.warning("  ... and %d more", len(summary["errors"]) - 10)
    logger.info("exit_mechanism_counts: %s", summary["exit_mechanism_counts"])
    return 0 if not summary["errors"] else 2


if __name__ == "__main__":
    sys.exit(main())
