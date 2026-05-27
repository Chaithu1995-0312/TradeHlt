"""
stage1_dataset_builder.py
=========================
Stage-1 Truth Dataset Builder for TradingLLM.

Reads opportunities.jsonl from each (instrument, run_id) pair under the JSONL
root, enriches with regime / RR-bucket / duration-bucket / win_flag /
feature_quality / replay_ready, rejects malformed or low-quality records, and
writes a deterministic per-scope JSONL dataset plus four integrity reports.

Architecture
------------
    Discovery → Validation → Transform → Shard write → External merge → Hash → Reports

Memory bound is O(per-instrument-run-shard); the full dataset is NEVER held in
RAM. Per-run shards are written to ``reports/.stage1_shards/`` then heap-merged
to the final output atomically. Shards are deleted on success.

Determinism
-----------
- All directory iteration is sorted.
- All JSON serialization uses ``sort_keys=True``.
- Per-instrument merge orders by ``(timestamp, run_id, line_no, direction)``.
- Across instruments: alphabetical concatenation.
- The build timestamp lives in the integrity report, NOT in dataset records.

Locked design decisions (Stage-1 v1)
------------------------------------
1. Hybrid input discovery: ``logs/{INSTRUMENT}/{RUN_ID}/`` for JSONL,
   ``results/**/*trades*.csv`` for CSV. compressed.json is optional/derivative.
2. ``--market-scope`` ∈ {auto, crypto, forex, all}; auto resolves by scanning
   discovered instruments.
3. Contract-first schema: require all 38 CANONICAL_FEATURES; preserve unknowns
   in ``extra_features``; never silently drop / reorder / zero-fill.
4. Static buckets, ``bucket_version=1``; inclusive lower / exclusive upper.
5. Feature quality is a 4-component composite (present, non_default, finite,
   variance) with rejection at < 0.70 (configurable).
6. Replay-readiness flag: features valid AND finite RR AND non-negative
   duration → ``replay_ready=True, replay_version=1``.
"""
from __future__ import annotations

import argparse
import csv
import fnmatch
import hashlib
import heapq
import json
import logging
import os
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Optional

# Bootstrap src/ when invoked as a path-relative module.
_HERE = Path(__file__).resolve()
if _HERE.parent.name == "training":
    _SRC = _HERE.parents[1]
    if str(_SRC) not in sys.path:
        sys.path.insert(0, str(_SRC))

from features.feature_schema import (
    CANONICAL_FEATURES,
    FEATURE_ORDER_HASH,
    SCHEMA_VERSION,
)
from utils.integrity_events import emit_integrity_event, Severity


log = logging.getLogger("dataset_builder")


# ─── CONSTANTS ────────────────────────────────────────────────────────────────

BUILDER_VERSION: str = "stage1.v1"
BUCKET_VERSION: int = 1
REPLAY_VERSION: int = 1
CANONICAL_KEY_SET = frozenset(CANONICAL_FEATURES)

# (low_inclusive, high_exclusive, id, label) — inf bounds for first/last.
RR_BUCKETS: tuple = (
    (float("-inf"), 0.0, 0, "LOSS"),
    (0.0,           1.0, 1, "SCRATCH"),
    (1.0,           2.0, 2, "BASE"),
    (2.0,           3.0, 3, "STRONG"),
    (3.0, float("inf"), 4, "OUTLIER"),
)

DURATION_BUCKETS: tuple = (
    (0,             4,  0, "FAST"),       # 0–3
    (4,             11, 1, "NORMAL"),     # 4–10
    (11,            31, 2, "SWING"),      # 11–30
    (31,            91, 3, "EXTENDED"),   # 31–90
    (91, float("inf"), 4, "RUNNER"),      # >90
)

SCOPE_PATTERNS: dict = {
    "crypto": ("*USDT", "BTC*", "ETH*", "SOL*", "DOGE*", "XRP*", "BNB*"),
    "forex":  ("EUR*", "GBP*", "USD*", "AUD*", "XAU*"),
}

SCOPE_OUTPUT_NAMES: dict = {
    "crypto": "master_crypto_training.jsonl",
    "forex":  "master_forex_training.jsonl",
    "all":    "master_multiasset_training.jsonl",
}

# Regime classification thresholds — mirror src/regime/regime_classifier.py defaults.
_ATR_HIGH: float = 0.8
_TREND_HIGH: float = 0.7

_REJECTION_SAMPLE_CAP: int = 50


# ─── DATACLASSES ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class BuilderConfig:
    jsonl_root: Path = Path("logs")
    csv_root: Path = Path("results")
    output_dir: Path = Path("data")
    reports_dir: Path = Path("reports")
    market_scope: str = "crypto"          # auto | crypto | forex | all
    validation_level: str = "WARN"        # STRICT | WARN | LENIENT
    strict_layout: bool = False
    min_feature_quality: float = 0.70
    instruments_override: Optional[tuple] = None  # tuple[str, ...] | None

    def output_path(self, effective_scope: str | None = None) -> Path:
        scope = (effective_scope or self.market_scope)
        if scope == "auto":
            scope = "crypto"
        name = SCOPE_OUTPUT_NAMES.get(scope, SCOPE_OUTPUT_NAMES["all"])
        return self.output_dir / name


@dataclass
class RejectionLedger:
    malformed_json: int = 0
    missing_features: int = 0
    schema_mismatch: int = 0
    type_mismatch: int = 0
    duplicate: int = 0
    out_of_scope: int = 0
    low_feature_quality: int = 0
    no_outcome: int = 0
    samples: list = field(default_factory=list)

    def add_sample(self, reason: str, snippet: dict) -> None:
        if len(self.samples) < _REJECTION_SAMPLE_CAP:
            self.samples.append({"reason": reason, "record": snippet})

    def total(self) -> int:
        return (self.malformed_json + self.missing_features + self.schema_mismatch
                + self.type_mismatch + self.duplicate + self.out_of_scope
                + self.low_feature_quality + self.no_outcome)


@dataclass
class BuildResult:
    output_path: Path
    output_sha256: str
    integrity_report_path: Path
    instrument_summary_path: Path
    input_manifest_path: Path
    scope_summary_path: Path
    accepted: int
    rejected: RejectionLedger
    effective_scope: str


# ─── DISCOVERY ────────────────────────────────────────────────────────────────

def _iter_sorted_dirs(root: Path) -> Iterator[Path]:
    if not root.exists() or not root.is_dir():
        return iter(())
    return iter(sorted([p for p in root.iterdir() if p.is_dir()], key=lambda p: p.name))


def _glob_opportunities(jsonl_root: Path) -> list:
    """Return sorted list of (instrument, run_id, opp_path) tuples."""
    out: list = []
    for inst_dir in _iter_sorted_dirs(jsonl_root):
        for run_dir in _iter_sorted_dirs(inst_dir):
            opp = run_dir / "opportunities.jsonl"
            if opp.exists():
                out.append((inst_dir.name, run_dir.name, opp))
    return out


def _glob_compressed(jsonl_root: Path) -> dict:
    out: dict = {}
    for inst_dir in _iter_sorted_dirs(jsonl_root):
        for run_dir in _iter_sorted_dirs(inst_dir):
            comp = run_dir / "compressed.json"
            if comp.exists():
                out[(inst_dir.name, run_dir.name)] = comp
    return out


def _glob_trades_csv(csv_root: Path) -> dict:
    """Map (instrument, run_id) → trades_csv path. Parses
    ``run_{YYYYMMDD}_{HHMMSS}_{INSTRUMENT}`` and ``{INSTRUMENT}/{YYYYMMDD_HHMMSS}``
    layouts.
    """
    out: dict = {}
    if not csv_root.exists():
        return out
    for path in sorted(csv_root.rglob("*trades*.csv"), key=lambda p: str(p)):
        parent = path.parent.name
        instrument, run_id = "", ""
        if parent.startswith("run_"):
            parts = parent.split("_")
            if len(parts) >= 4:
                run_id = "_".join(parts[1:3])
                instrument = "_".join(parts[3:])
        else:
            run_id = parent
            instrument = path.parent.parent.name
        if instrument and run_id:
            out.setdefault((instrument, run_id), path)
    return out


def discover_inputs(cfg: BuilderConfig) -> dict:
    """Build the input manifest. Opportunities is required; trades.csv and
    compressed.json are optional enrichment.
    """
    opps = _glob_opportunities(cfg.jsonl_root)
    trades = _glob_trades_csv(cfg.csv_root)
    compressed = _glob_compressed(cfg.jsonl_root)

    pairs: list = []
    missing_trades: list = []
    missing_compressed: list = []
    for instrument, run_id, opp_path in opps:
        key = (instrument, run_id)
        trades_path = trades.get(key)
        comp_path = compressed.get(key)
        if trades_path is None:
            missing_trades.append({"instrument": instrument, "run_id": run_id})
        if comp_path is None:
            missing_compressed.append({"instrument": instrument, "run_id": run_id})
        pairs.append({
            "instrument": instrument,
            "run_id": run_id,
            "opportunities": str(opp_path).replace("\\", "/"),
            "trades_csv": str(trades_path).replace("\\", "/") if trades_path else None,
            "compressed_json": str(comp_path).replace("\\", "/") if comp_path else None,
        })

    return {
        "jsonl_root": str(cfg.jsonl_root).replace("\\", "/"),
        "csv_root":   str(cfg.csv_root).replace("\\", "/"),
        "strict_layout": cfg.strict_layout,
        "pairs": pairs,
        "n_pairs": len(pairs),
        "missing_trades": missing_trades,
        "missing_compressed": missing_compressed,
    }


# ─── SCOPE CLASSIFICATION ─────────────────────────────────────────────────────

def classify_scope(instrument: str, scope: str) -> bool:
    """True if ``instrument`` falls within ``scope``. ``all`` accepts everything."""
    if scope in ("all", "auto"):
        return True
    patterns = SCOPE_PATTERNS.get(scope)
    if not patterns:
        return True
    inst_upper = (instrument or "").upper()
    return any(fnmatch.fnmatchcase(inst_upper, p) for p in patterns)


def resolve_auto_scope(instruments: list) -> str:
    """Resolve ``--market-scope auto`` by inspecting discovered instruments.

    Returns ``crypto`` if every instrument matches crypto patterns, ``forex`` if
    every instrument matches forex patterns, else ``all``.
    """
    if not instruments:
        return "crypto"
    inst_set = set(instruments)
    if all(classify_scope(i, "crypto") for i in inst_set):
        return "crypto"
    if all(classify_scope(i, "forex") for i in inst_set):
        return "forex"
    return "all"


# ─── BUCKETING ────────────────────────────────────────────────────────────────

def rr_bucket(rr: float) -> tuple:
    """Return (id, label). NaN/inf inputs → (-1, "INVALID")."""
    try:
        v = float(rr)
    except (TypeError, ValueError):
        return -1, "INVALID"
    if v != v:  # NaN
        return -1, "INVALID"
    for low, high, bid, label in RR_BUCKETS:
        if low <= v < high:
            return bid, label
    return -1, "INVALID"


def duration_bucket(candles) -> tuple:
    """Return (id, label). Negative / non-numeric → (-1, "INVALID")."""
    try:
        n = int(candles)
    except (TypeError, ValueError):
        return -1, "INVALID"
    if n < 0:
        return -1, "INVALID"
    for low, high, bid, label in DURATION_BUCKETS:
        if low <= n < high:
            return bid, label
    return -1, "INVALID"


# ─── REGIME (stateless, per-record) ───────────────────────────────────────────

def regime_for(features: dict) -> str:
    """Stateless regime classification for dataset labeling.

    Matches the priority of ``src/regime/regime_classifier.py`` but without the
    live-trading cooldown — each training record must be labeled independently.
    """
    try:
        atr = float(features.get("atr", 0.5) or 0.0)
        # The runtime classifier reads ``trend_score``; our canonical schema
        # uses ``trend_strength`` (signed). Use |trend_strength| as proxy.
        trend_score = abs(float(features.get("trend_strength", 0.5) or 0.0))
    except (TypeError, ValueError):
        return "RANGING"
    if atr > _ATR_HIGH:
        return "HIGH_VOLATILITY"
    if trend_score > _TREND_HIGH:
        return "TRENDING"
    return "RANGING"


# ─── FEATURE QUALITY ──────────────────────────────────────────────────────────

def compute_feature_quality(features: dict) -> dict:
    """Composite per-record quality score on [0, 1].

    Components (each on [0, 1], averaged):
      - present_frac:    fraction of canonical keys present in the dict
      - non_default_frac: fraction of canonical features with non-zero magnitude
      - finite_frac:     fraction of canonical features that are finite numbers
      - variance_flag:   1.0 if the vector has any variance, else 0.0

    A vector that is all-zero or all-NaN falls below 0.70 and is rejected.
    """
    n = len(CANONICAL_FEATURES)
    present_count = 0
    finite_count = 0
    nonzero_count = 0
    vals: list = []

    for k in CANONICAL_FEATURES:
        if k in features:
            present_count += 1
        raw = features.get(k)
        try:
            f = float(raw) if raw is not None else None
        except (TypeError, ValueError):
            f = None
        if f is None:
            continue
        if f == f and f != float("inf") and f != float("-inf"):
            finite_count += 1
            vals.append(f)
            if abs(f) > 1e-12:
                nonzero_count += 1

    present = present_count / n
    finite = finite_count / n
    non_default = nonzero_count / n
    if len(vals) >= 2:
        mean = sum(vals) / len(vals)
        var = sum((x - mean) ** 2 for x in vals) / len(vals)
        variance_flag = 1.0 if var > 1e-12 else 0.0
    else:
        variance_flag = 0.0

    composite = (present + non_default + finite + variance_flag) / 4.0
    return {
        "score": round(composite, 6),
        "present_frac": round(present, 6),
        "non_default_frac": round(non_default, 6),
        "finite_frac": round(finite, 6),
        "variance_flag": variance_flag,
    }


# ─── VALIDATION + TRANSFORM ───────────────────────────────────────────────────

def is_run_header(rec) -> bool:
    return isinstance(rec, dict) and (
        rec.get("type") == "run_header" or rec.get("kind") == "run_header"
    )


def _safe_float(v) -> float:
    try:
        return float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def validate_record_shape(rec, validation_level: str = "WARN") -> tuple:
    """Hard schema checks. Returns (ok, reason, normalized) where normalized is
    {"features": dict[str, float], "extra_features": dict} on success."""
    if not isinstance(rec, dict):
        return False, "malformed_json", None

    if "timestamp" not in rec or "instrument" not in rec:
        return False, "schema_mismatch", None

    if "rr_achieved" not in rec and "pnl_rr_net" not in rec:
        return False, "no_outcome", None

    feats = rec.get("features")
    if not isinstance(feats, dict):
        return False, "missing_features", None

    missing = CANONICAL_KEY_SET - feats.keys()
    if missing:
        return False, "missing_features", None

    canonical: dict = {}
    extras: dict = {}
    for k, v in feats.items():
        if k in CANONICAL_KEY_SET:
            try:
                canonical[k] = float(v) if v is not None else 0.0
            except (TypeError, ValueError):
                if validation_level == "STRICT":
                    return False, "type_mismatch", None
                canonical[k] = 0.0
        else:
            extras[k] = v

    # Type-mismatch sentinel checks under STRICT — values outside known ranges
    # for known-categorical features should fail in STRICT mode.
    if validation_level == "STRICT":
        # session is encoded as 0.0..3.0 or SESSION_UNKNOWN=-1.0
        sess = canonical.get("session", 0.0)
        if sess not in (-1.0, 0.0, 1.0, 2.0, 3.0):
            return False, "type_mismatch", None

    return True, "", {"features": canonical, "extra_features": extras}


def transform_record(
    raw: dict,
    normalized: dict,
    source_meta: dict,
    min_feature_quality: float,
) -> tuple:
    """Enrich a normalized record. Returns (record_or_None, rejection_reason)."""
    features = normalized["features"]
    extras = normalized["extra_features"]

    rr_raw = raw.get("rr_achieved", raw.get("pnl_rr_net"))
    try:
        rr = float(rr_raw)
    except (TypeError, ValueError):
        return None, "schema_mismatch"

    duration_raw = raw.get("duration_candles", 0)
    try:
        duration = int(duration_raw) if duration_raw is not None else 0
    except (TypeError, ValueError):
        duration = 0

    mfe = _safe_float(raw.get("mfe"))
    mae = _safe_float(raw.get("mae"))

    win_flag = 1 if rr > 0 else 0
    rr_bid, rr_label = rr_bucket(rr)
    dur_bid, dur_label = duration_bucket(duration)
    regime = regime_for(features)

    quality = compute_feature_quality(features)
    if quality["score"] < min_feature_quality:
        return None, "low_feature_quality"

    rr_is_finite = (rr == rr and rr != float("inf") and rr != float("-inf"))
    replay_ready = bool(
        quality["score"] >= min_feature_quality
        and rr_is_finite
        and duration >= 0
        and len(features) == len(CANONICAL_FEATURES)
    )

    record = {
        "instrument": raw["instrument"],
        "timestamp": raw["timestamp"],
        "direction": raw.get("direction", ""),
        "entry": _safe_float(raw.get("entry")),
        "sl": _safe_float(raw.get("sl")),
        "tp": _safe_float(raw.get("tp")),
        "outcome": raw.get("outcome", "UNKNOWN"),
        "rr_achieved": rr,
        "duration_candles": duration,
        "mfe": mfe,
        "mae": mae,
        "win_flag": win_flag,
        "regime": regime,
        "rr_bucket_id": rr_bid,
        "rr_bucket_label": rr_label,
        "duration_bucket_id": dur_bid,
        "duration_bucket_label": dur_label,
        "features": features,
        "extra_features": extras,
        "metadata": {
            "schema_version": SCHEMA_VERSION,
            "feature_dim": len(CANONICAL_FEATURES),
            "feature_hash": FEATURE_ORDER_HASH,
            "feature_quality": quality["score"],
            "feature_quality_components": {
                "present_frac": quality["present_frac"],
                "non_default_frac": quality["non_default_frac"],
                "finite_frac": quality["finite_frac"],
                "variance_flag": quality["variance_flag"],
            },
            "extra_feature_count": len(extras),
            "bucket_version": BUCKET_VERSION,
            "replay_ready": replay_ready,
            "replay_version": REPLAY_VERSION,
            "source_run_id": source_meta["run_id"],
            "source_line_no": source_meta["line_no"],
            "source_path": source_meta["path"],
        },
    }
    return record, None


# ─── STREAMING I/O ────────────────────────────────────────────────────────────

def iter_opportunities(path: Path) -> Iterator:
    """Yield (line_no, parsed_or_None, parse_error_or_None). Skips run_header lines.

    Line numbers are 1-based and reflect the position in the source file.
    """
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line_no, line in enumerate(fh, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                rec = json.loads(stripped)
            except json.JSONDecodeError as exc:
                yield line_no, None, str(exc)
                continue
            if is_run_header(rec):
                continue
            yield line_no, rec, None


def _count_records_quick(path: Path) -> int:
    """Best-effort line count minus the header. Used for out-of-scope tallies."""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            return max(0, sum(1 for line in fh if line.strip()) - 1)
    except OSError:
        return 0


def _atomic_write(path: Path, line_generator) -> str:
    """Stream lines via line_generator() into ``path.tmp``, rename atomically,
    return the sha256 hex digest of the bytes written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    sha = hashlib.sha256()
    try:
        with tmp.open("w", encoding="utf-8", newline="\n") as fh:
            for line in line_generator():
                data = line if line.endswith("\n") else line + "\n"
                sha.update(data.encode("utf-8"))
                fh.write(data)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
    return sha.hexdigest()


def _write_json_atomic(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    payload = json.dumps(data, indent=2, sort_keys=True, default=str)
    with tmp.open("w", encoding="utf-8") as fh:
        fh.write(payload)
    os.replace(tmp, path)


# ─── MAIN BUILD ───────────────────────────────────────────────────────────────

def build_dataset(cfg: BuilderConfig) -> BuildResult:
    """Top-level entry point."""
    started = time.time()
    log.info(
        "stage1 build starting | scope=%s level=%s min_quality=%.2f",
        cfg.market_scope, cfg.validation_level, cfg.min_feature_quality,
    )

    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    cfg.reports_dir.mkdir(parents=True, exist_ok=True)

    # 1. Discovery
    manifest = discover_inputs(cfg)
    manifest_path = cfg.reports_dir / "input_manifest.json"
    _write_json_atomic(manifest_path, manifest)

    if not manifest["pairs"]:
        emit_integrity_event(
            "STAGE1_NO_INPUTS", Severity.ERROR, "dataset_builder",
            {"jsonl_root": str(cfg.jsonl_root)},
        )
        if cfg.strict_layout:
            raise RuntimeError(f"No opportunities.jsonl found under {cfg.jsonl_root}")

    if cfg.strict_layout and (manifest["missing_trades"] or manifest["missing_compressed"]):
        raise RuntimeError(
            "strict_layout=True; missing companions: "
            f"trades={len(manifest['missing_trades'])} "
            f"compressed={len(manifest['missing_compressed'])}"
        )
    if manifest["missing_compressed"]:
        emit_integrity_event(
            "STAGE1_COMPRESSED_OPTIONAL_ABSENT", Severity.INFO, "dataset_builder",
            {"count": len(manifest["missing_compressed"])},
        )
    if manifest["missing_trades"]:
        emit_integrity_event(
            "STAGE1_TRADES_CSV_MISSING", Severity.WARNING, "dataset_builder",
            {"count": len(manifest["missing_trades"])},
        )

    # 2. Effective scope
    if cfg.market_scope == "auto":
        effective_scope = resolve_auto_scope([p["instrument"] for p in manifest["pairs"]])
        log.info("auto-scope resolved → %s", effective_scope)
    else:
        effective_scope = cfg.market_scope

    # 3. Per-run shard generation
    ledger = RejectionLedger()
    accepted_count = 0
    instrument_accepted: dict = {}
    rejected_instruments: set = set()
    per_instrument_stats: dict = {}
    bucket_counts_rr: dict = {}
    bucket_counts_dur: dict = {}
    regime_counts: dict = {}
    replay_ready_count = 0

    shard_dir = cfg.reports_dir / ".stage1_shards"
    if shard_dir.exists():
        shutil.rmtree(shard_dir, ignore_errors=True)
    shard_dir.mkdir(parents=True, exist_ok=True)

    instrument_shards: dict = {}

    for pair in manifest["pairs"]:
        instrument = pair["instrument"]
        run_id = pair["run_id"]
        opp_path = Path(pair["opportunities"])

        # Coarse scope filter (folder-name based, before opening the file).
        if cfg.instruments_override is not None:
            if instrument not in cfg.instruments_override:
                ledger.out_of_scope += _count_records_quick(opp_path)
                rejected_instruments.add(instrument)
                continue
        elif not classify_scope(instrument, effective_scope):
            ledger.out_of_scope += _count_records_quick(opp_path)
            rejected_instruments.add(instrument)
            continue

        shard_path = shard_dir / f"{instrument}__{run_id}.shard.jsonl"
        seen_in_run: set = set()
        # Buffer (sort_key, serialized_line) per shard so the final
        # heapq.merge sees pre-sorted shards. Per-shard memory is bounded
        # by a single (instrument, run_id) — far smaller than the global
        # dataset and acceptable for offline tooling.
        shard_buffer: list = []
        for line_no, raw, parse_err in iter_opportunities(opp_path):
            if parse_err is not None:
                ledger.malformed_json += 1
                ledger.add_sample("malformed_json", {
                    "path": str(opp_path).replace("\\", "/"),
                    "line": line_no,
                    "err": parse_err[:120],
                })
                continue

            # Per-record scope re-check (catches mis-foldered records).
            rec_inst = raw.get("instrument", instrument) if isinstance(raw, dict) else instrument
            if cfg.instruments_override is not None and rec_inst not in cfg.instruments_override:
                ledger.out_of_scope += 1
                rejected_instruments.add(rec_inst)
                continue
            if cfg.instruments_override is None and not classify_scope(rec_inst, effective_scope):
                ledger.out_of_scope += 1
                rejected_instruments.add(rec_inst)
                continue

            ok, reason, normalized = validate_record_shape(raw, cfg.validation_level)
            if not ok:
                _inc_ledger(ledger, reason)
                ledger.add_sample(reason, {"line": line_no, "instrument": rec_inst})
                continue

            record, rej = transform_record(
                raw, normalized,
                {
                    "run_id": run_id,
                    "line_no": line_no,
                    "path": str(opp_path).replace("\\", "/"),
                },
                cfg.min_feature_quality,
            )
            if record is None:
                _inc_ledger(ledger, rej or "schema_mismatch")
                continue

            dup_key = (
                record["instrument"],
                record["timestamp"],
                record["direction"],
                round(record["entry"], 8),
                round(record["sl"], 8),
                record["metadata"]["source_run_id"],
            )
            if dup_key in seen_in_run:
                ledger.duplicate += 1
                continue
            seen_in_run.add(dup_key)

            sort_key = (
                record["timestamp"],
                record["metadata"]["source_run_id"],
                record["metadata"]["source_line_no"],
                record["direction"],
            )
            shard_buffer.append((sort_key, json.dumps(record, sort_keys=True)))
            accepted_count += 1
            if record["metadata"]["replay_ready"]:
                replay_ready_count += 1
            instrument_accepted[rec_inst] = instrument_accepted.get(rec_inst, 0) + 1

            bucket_counts_rr[record["rr_bucket_label"]] = (
                bucket_counts_rr.get(record["rr_bucket_label"], 0) + 1
            )
            bucket_counts_dur[record["duration_bucket_label"]] = (
                bucket_counts_dur.get(record["duration_bucket_label"], 0) + 1
            )
            regime_counts[record["regime"]] = regime_counts.get(record["regime"], 0) + 1

            pis = per_instrument_stats.setdefault(rec_inst, {
                "n": 0, "sum_rr": 0.0, "wins": 0, "sum_dur": 0,
                "sum_quality": 0.0, "regimes": {}, "rr_buckets": {},
                "replay_ready": 0,
            })
            pis["n"] += 1
            pis["sum_rr"] += record["rr_achieved"]
            pis["wins"] += record["win_flag"]
            pis["sum_dur"] += record["duration_candles"]
            pis["sum_quality"] += record["metadata"]["feature_quality"]
            pis["regimes"][record["regime"]] = pis["regimes"].get(record["regime"], 0) + 1
            pis["rr_buckets"][record["rr_bucket_label"]] = pis["rr_buckets"].get(
                record["rr_bucket_label"], 0
            ) + 1
            if record["metadata"]["replay_ready"]:
                pis["replay_ready"] += 1

        # Sort the shard buffer and flush to disk so heapq.merge sees
        # a pre-sorted input. Per-shard memory is bounded by the size of
        # one (instrument, run_id) — acceptable for offline tooling.
        shard_buffer.sort(key=lambda t: t[0])
        with shard_path.open("w", encoding="utf-8", newline="\n") as shard_fh:
            for _, line in shard_buffer:
                shard_fh.write(line + "\n")
        del shard_buffer

        instrument_shards.setdefault(instrument, []).append(shard_path)

    # 4. External merge → final atomic write
    output_path = cfg.output_path(effective_scope)
    sha = _merge_shards_to_final(instrument_shards, output_path)

    # 5. Clean shards (keep them on debug if STAGE1_KEEP_SHARDS=1)
    if not os.environ.get("STAGE1_KEEP_SHARDS"):
        shutil.rmtree(shard_dir, ignore_errors=True)

    # 6. Reports
    duration_sec = round(time.time() - started, 3)
    integrity = _build_integrity_report(
        cfg, manifest, sha, str(output_path).replace("\\", "/"),
        accepted_count, ledger, bucket_counts_rr, bucket_counts_dur,
        regime_counts, instrument_accepted, duration_sec,
        effective_scope, replay_ready_count,
    )
    integrity_path = cfg.reports_dir / "integrity_report.json"
    _write_json_atomic(integrity_path, integrity)

    summary_path = cfg.reports_dir / "instrument_summary.csv"
    _write_instrument_summary_csv(summary_path, per_instrument_stats)

    scope_summary_path = cfg.reports_dir / "scope_summary.json"
    _write_json_atomic(scope_summary_path, {
        "scope": effective_scope,
        "rules": {k: list(v) for k, v in SCOPE_PATTERNS.items()},
        "accepted_count": accepted_count,
        "rejected_count": ledger.out_of_scope,
        "accepted_instruments": sorted(instrument_accepted.keys()),
        "rejected_instruments": sorted(rejected_instruments),
    })

    log.info(
        "stage1 build complete | accepted=%d rejected=%d replay_ready=%d sha=%s | %ss",
        accepted_count, ledger.total(), replay_ready_count, sha[:12], duration_sec,
    )

    return BuildResult(
        output_path=output_path,
        output_sha256=sha,
        integrity_report_path=integrity_path,
        instrument_summary_path=summary_path,
        input_manifest_path=manifest_path,
        scope_summary_path=scope_summary_path,
        accepted=accepted_count,
        rejected=ledger,
        effective_scope=effective_scope,
    )


def _inc_ledger(ledger: RejectionLedger, reason: str) -> None:
    if hasattr(ledger, reason) and reason != "samples":
        setattr(ledger, reason, getattr(ledger, reason) + 1)
    else:
        ledger.schema_mismatch += 1


def _merge_shards_to_final(instrument_shards: dict, output_path: Path) -> str:
    """heapq.merge per instrument, alphabetical across instruments."""
    def line_gen():
        for instrument in sorted(instrument_shards.keys()):
            shards = instrument_shards[instrument]
            iterators = [_shard_iter(s) for s in shards]
            for _key, line in heapq.merge(*iterators, key=lambda kv: kv[0]):
                yield line

    return _atomic_write(output_path, line_gen)


def _shard_iter(path: Path) -> Iterator:
    """Yield (sort_key, original_line_with_newline) from a shard file."""
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                rec = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            md = rec.get("metadata", {})
            key = (
                rec.get("timestamp", ""),
                md.get("source_run_id", ""),
                md.get("source_line_no", 0),
                rec.get("direction", ""),
            )
            yield key, stripped + "\n"


def _write_instrument_summary_csv(path: Path, stats: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    headers = [
        "instrument", "n_records", "win_rate", "mean_rr",
        "mean_duration_candles", "mean_feature_quality",
        "replay_ready_count", "regime_dist", "rr_bucket_dist",
    ]
    with tmp.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(headers)
        for instrument in sorted(stats.keys()):
            s = stats[instrument]
            n = max(1, s["n"])
            writer.writerow([
                instrument,
                s["n"],
                round(s["wins"] / n, 6),
                round(s["sum_rr"] / n, 6),
                round(s["sum_dur"] / n, 4),
                round(s["sum_quality"] / n, 6),
                s["replay_ready"],
                json.dumps(s["regimes"], sort_keys=True),
                json.dumps(s["rr_buckets"], sort_keys=True),
            ])
    os.replace(tmp, path)


def _build_integrity_report(
    cfg: BuilderConfig, manifest: dict, sha: str, output_path_str: str,
    accepted: int, ledger: RejectionLedger,
    rr_b: dict, dur_b: dict, regimes: dict,
    per_inst: dict, duration_sec: float,
    effective_scope: str, replay_ready_count: int,
) -> dict:
    return {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "builder_version": BUILDER_VERSION,
        "bucket_version": BUCKET_VERSION,
        "replay_version": REPLAY_VERSION,
        "schema_version": SCHEMA_VERSION,
        "feature_dim": len(CANONICAL_FEATURES),
        "feature_hash": FEATURE_ORDER_HASH,
        "scope_requested": cfg.market_scope,
        "scope_effective": effective_scope,
        "min_feature_quality": cfg.min_feature_quality,
        "validation_level": cfg.validation_level,
        "strict_layout": cfg.strict_layout,
        "output_path": output_path_str,
        "output_sha256": sha,
        "input_pairs": len(manifest["pairs"]),
        "missing_trades_csv": len(manifest["missing_trades"]),
        "missing_compressed_json": len(manifest["missing_compressed"]),
        "totals": {
            "accepted": accepted,
            "replay_ready": replay_ready_count,
            "rejected_total": ledger.total(),
            "rejected": {
                "malformed_json": ledger.malformed_json,
                "missing_features": ledger.missing_features,
                "schema_mismatch": ledger.schema_mismatch,
                "type_mismatch": ledger.type_mismatch,
                "duplicate": ledger.duplicate,
                "out_of_scope": ledger.out_of_scope,
                "low_feature_quality": ledger.low_feature_quality,
                "no_outcome": ledger.no_outcome,
            },
        },
        "per_instrument_accepted": per_inst,
        "rr_bucket_distribution": rr_b,
        "duration_bucket_distribution": dur_b,
        "regime_distribution": regimes,
        "rejection_samples": ledger.samples[:_REJECTION_SAMPLE_CAP],
        "duration_seconds": duration_sec,
    }


# ─── CLI ──────────────────────────────────────────────────────────────────────

def _parse_args(argv) -> tuple:
    p = argparse.ArgumentParser(description="Stage-1 Truth Dataset Builder")
    p.add_argument("--jsonl-root", default="logs")
    p.add_argument("--csv-root", default="results")
    p.add_argument("--output-dir", default="data")
    p.add_argument("--reports-dir", default="reports")
    p.add_argument("--market-scope", choices=["auto", "crypto", "forex", "all"],
                   default="crypto")
    p.add_argument("--validation-level", choices=["STRICT", "WARN", "LENIENT"],
                   default="WARN")
    p.add_argument("--strict-layout", action="store_true")
    p.add_argument("--min-feature-quality", type=float, default=0.70)
    p.add_argument("--instruments", default=None,
                   help="Comma-separated whitelist (overrides scope)")
    p.add_argument("--dry-run", action="store_true",
                   help="Discovery + manifest only, no records emitted")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    instruments = None
    if args.instruments:
        instruments = tuple(s.strip() for s in args.instruments.split(",") if s.strip())

    cfg = BuilderConfig(
        jsonl_root=Path(args.jsonl_root),
        csv_root=Path(args.csv_root),
        output_dir=Path(args.output_dir),
        reports_dir=Path(args.reports_dir),
        market_scope=args.market_scope,
        validation_level=args.validation_level,
        strict_layout=args.strict_layout,
        min_feature_quality=args.min_feature_quality,
        instruments_override=instruments,
    )
    return cfg, args.dry_run


def main(argv=None) -> int:
    cfg, dry_run = _parse_args(argv)
    if dry_run:
        manifest = discover_inputs(cfg)
        cfg.reports_dir.mkdir(parents=True, exist_ok=True)
        _write_json_atomic(cfg.reports_dir / "input_manifest.json", manifest)
        log.info("dry-run: discovered %d pairs", manifest["n_pairs"])
        return 0
    result = build_dataset(cfg)
    log.info("output: %s", result.output_path)
    log.info("output_sha256: %s", result.output_sha256)
    log.info("integrity_report: %s", result.integrity_report_path)
    log.info("instrument_summary: %s", result.instrument_summary_path)
    log.info("scope_summary: %s", result.scope_summary_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
