"""
scripts/training/build_stage1_dataset.py
─────────────────────────────────────────────────────────────────────────────
CLI entry point for the Stage-1 Truth Dataset Builder.

All business logic lives in:
    src/training/stage1_dataset_builder.py

Usage:
    python scripts/training/build_stage1_dataset.py --market-scope crypto
    python scripts/training/build_stage1_dataset.py --dry-run
    python scripts/training/build_stage1_dataset.py \
        --jsonl-root logs --csv-root results \
        --market-scope all --validation-level STRICT \
        --min-feature-quality 0.70 \
        --output-dir data --reports-dir reports

Produces:
    data/master_{scope}_training.jsonl
    reports/integrity_report.json
    reports/instrument_summary.csv
    reports/input_manifest.json
    reports/scope_summary.json
─────────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import sys
from pathlib import Path

# Bootstrap src/ onto sys.path so the package import resolves regardless of cwd.
_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from training.stage1_dataset_builder import (  # noqa: F401,E402 (re-export)
    BuilderConfig,
    BuildResult,
    build_dataset,
    discover_inputs,
    main,
)


if __name__ == "__main__":
    sys.exit(main())
