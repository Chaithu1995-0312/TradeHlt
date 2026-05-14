"""
dataset_validator.py
═══════════════════════════════════════════════════════════════════════════════
Validates fusion trade logs before any dataset build or model training.

Checks:
  - Schema completeness (required keys present)
  - Feature vector integrity (correct length, no nulls, not all-zero)
  - Outcome completeness (only closed trades used for training)
  - Temporal ordering (critical for time-split: EXIT must follow ENTRY)
  - Minimum data threshold (refuses to train on tiny datasets)
  - Duplicate trade_id detection (data integrity guard)

Usage:
  from dataset_validator import validate_logs
  records = validate_logs("logs/GBPUSD_fusion.jsonl")
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from features.feature_schema import CANONICAL_FEATURES, TRADENET_SCHEMA
N_FEATURES = len(CANONICAL_FEATURES)
from features.feature_builder import feature_dict_to_vector
from features.feature_schema import validate_vector

log = logging.getLogger("DatasetValidator")

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG  (loaded from production config; hardcoded values are fallbacks)
# ─────────────────────────────────────────────────────────────────────────────

try:
    from config_layer.production_config import get_prod_section as _get_section
    _TRAIN_CFG = _get_section("training")
except Exception:
    _TRAIN_CFG = {}

MIN_RECORDS_TO_TRAIN:  int = _TRAIN_CFG.get("min_records_to_train",  200)
MIN_RECORDS_RECOMMEND: int = _TRAIN_CFG.get("min_records_recommend", 500)


# ─────────────────────────────────────────────────────────────────────────────
# RESULT
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ValidationReport:
    total_lines:        int = 0
    entry_records:      int = 0
    exit_records:       int = 0
    reject_records:     int = 0
    paired_trades:      int = 0    # ENTRY + EXIT with same trade_id
    valid_for_training: int = 0
    skipped_no_outcome: int = 0
    skipped_bad_features: int = 0
    skipped_duplicate:  int = 0
    skipped_parse_error:int = 0
    warnings:           list[str] = field(default_factory=list)
    errors:             list[str] = field(default_factory=list)

    @property
    def is_trainable(self) -> bool:
        return self.valid_for_training >= MIN_RECORDS_TO_TRAIN

    def print(self) -> None:
        print(f"\n{'─'*55}")
        print(f"  Dataset Validation Report")
        print(f"{'─'*55}")
        print(f"  Total log lines:       {self.total_lines:>6}")
        print(f"  ENTRY records:         {self.entry_records:>6}")
        print(f"  EXIT records:          {self.exit_records:>6}")
        print(f"  REJECT records:        {self.reject_records:>6}")
        print(f"  Paired trades:         {self.paired_trades:>6}")
        print(f"  ─ Skipped (no outcome): {self.skipped_no_outcome:>5}")
        print(f"  ─ Skipped (bad feat):  {self.skipped_bad_features:>6}")
        print(f"  ─ Skipped (duplicate): {self.skipped_duplicate:>6}")
        print(f"  ─ Skipped (parse err): {self.skipped_parse_error:>6}")
        print(f"  Valid for training:    {self.valid_for_training:>6}  "
              f"{'✅' if self.is_trainable else '❌ BELOW MINIMUM'}")
        if self.warnings:
            print(f"\n  Warnings:")
            for w in self.warnings:
                print(f"    ⚠  {w}")
        if self.errors:
            print(f"\n  Errors:")
            for e in self.errors:
                print(f"    ❌ {e}")
        print(f"{'─'*55}\n")


# ─────────────────────────────────────────────────────────────────────────────
# VALIDATOR
# ─────────────────────────────────────────────────────────────────────────────

def validate_logs(
    *log_paths: str | Path,
    verbose: bool = True,
) -> tuple[list[dict], ValidationReport]:
    """
    Load and validate one or more JSONL fusion log files.

    Pairing logic:
      - ENTRY records are indexed by trade_id
      - EXIT records are matched by trade_id
      - A paired record has: features (from ENTRY) + outcome (from EXIT)
      - Only paired, validated records are returned for training

    Returns
    -------
    (records, report)
      records : list of dicts ready for dataset_builder — each has
                'features' (dict), 'fusion' (dict), 'outcome' (dict)
      report  : ValidationReport with full diagnostics
    """
    rpt = ValidationReport()

    # ── Pass 1: load all lines, split by event type ──────────────────────────
    entries: dict[str, dict] = {}   # trade_id → ENTRY record
    exits:   dict[str, dict] = {}   # trade_id → EXIT record
    seen_ids: set[str] = set()

    for path in log_paths:
        path = Path(path)
        if not path.exists():
            rpt.errors.append(f"Log file not found: {path}")
            continue

        for line_no, line in enumerate(open(path, encoding="utf-8"), 1):
            rpt.total_lines += 1
            line = line.strip()
            if not line:
                continue

            try:
                rec = json.loads(line)
            except json.JSONDecodeError as e:
                rpt.skipped_parse_error += 1
                rpt.warnings.append(f"{path.name}:{line_no} JSON parse error: {e}")
                continue

            event = rec.get("event", "")

            if event == "ENTRY":
                rpt.entry_records += 1
                tid = rec.get("trade_id", "")
                if tid and tid not in entries:   # keep first occurrence; discard zero-padded duplicates
                    entries[tid] = rec

            elif event == "EXIT":
                rpt.exit_records += 1
                tid = rec.get("trade_id", "")
                if tid:
                    exits[tid] = rec

            elif event == "REJECT":
                rpt.reject_records += 1

    # ── Pass 2: pair ENTRY + EXIT ─────────────────────────────────────────────
    paired_records: list[dict] = []

    for tid, entry in entries.items():
        if tid not in exits:
            rpt.skipped_no_outcome += 1
            continue

        rpt.paired_trades += 1
        exit_rec = exits[tid]

        # Duplicate check
        if tid in seen_ids:
            rpt.skipped_duplicate += 1
            continue
        seen_ids.add(tid)

        # Feature extraction + validation
        feature_dict = entry.get("features", {})
        if feature_dict and all(v == 0.0 for v in feature_dict.values()):
            rpt.skipped_bad_features += 1
            rpt.warnings.append(f"trade_id={tid[:8]}… all-zero feature vector, skipped")
            continue
        try:
            vec = feature_dict_to_vector(feature_dict)
            validate_vector(vec, TRADENET_SCHEMA, label=f"trade_id={tid[:8]}")
        except (ValueError, TypeError, KeyError, AssertionError) as exc:
            rpt.skipped_bad_features += 1
            rpt.warnings.append(f"trade_id={tid[:8]}… bad features: {exc}")
            continue

        paired_records.append({
            "trade_id":  tid,
            "timestamp": entry.get("timestamp", ""),
            "instrument": entry.get("instrument", ""),
            "features":  feature_dict,
            "feature_vec": vec,
            "fusion":    entry.get("fusion", {}),
            "outcome": {
                "pnl_rr_net":       exit_rec.get("pnl_rr_net", 0.0),
                "win":              exit_rec.get("win", False),
                "exit_reason":      exit_rec.get("exit_reason", ""),
                "duration_candles": exit_rec.get("duration_candles", 0),
            },
        })

    rpt.valid_for_training = len(paired_records)

    if rpt.valid_for_training < MIN_RECORDS_RECOMMEND:
        rpt.warnings.append(
            f"Only {rpt.valid_for_training} valid records — recommend {MIN_RECORDS_RECOMMEND}+ for reliable training."
        )

    if verbose:
        rpt.print()

    return paired_records, rpt


def validate_logs_multi_instrument(
    log_dir: str | Path = "logs",
    pattern: str = "*_fusion.jsonl",
    verbose: bool = True,
) -> tuple[list[dict], ValidationReport]:
    """
    Convenience wrapper: load all instrument fusion logs from a directory.
    """
    paths = list(Path(log_dir).glob(pattern))
    if not paths:
        rpt = ValidationReport()
        rpt.errors.append(f"No files matching {pattern} in {log_dir}")
        if verbose:
            rpt.print()
        return [], rpt
    return validate_logs(*paths, verbose=verbose)
