"""
compress_logs_for_llm.py
========================
Compress one or more opportunity / fusion JSONL logs into a token-efficient
summary suitable for LLM review (governance orchestrator, hypertuning prompts).

Streams the input line-by-line — never loads the full log into memory. The
resulting summary captures:
  - aggregate counts (total, by outcome, by direction, by instrument)
  - rr distribution (mean / std / quantiles)
  - feature-level correlations with rr (top positive / negative)
  - feature deltas between TP_HIT and SL_HIT clusters
  - anomalies (large SL clusters, severe MAE outliers)

Schema matches what reflection_buffer_advanced.py expects when called with
--compressed-summary: top-level keys {summary, data, anomalies}.
"""

from __future__ import annotations

import argparse
import glob
import json
import logging
import math
import sys
from pathlib import Path
from typing import Iterable

logger = logging.getLogger("CompressLogs")

# Threshold above which a JSONL file is flagged as systemically corrupted.
MAX_CORRUPTION_RATIO: float = 0.10

try:
    from src.utils.integrity_events import emit_integrity_event  # noqa: F401
except Exception:  # pragma: no cover
    def emit_integrity_event(*_a, **_kw):  # type: ignore[no-redef]
        return None


def _iter_records(paths: Iterable[Path]):
    for p in paths:
        try:
            fh = p.open("r", encoding="utf-8")
        except OSError as exc:
            logger.warning("skip %s: %s", p, exc)
            continue
        malformed = 0
        valid = 0
        with fh:
            for lineno, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    valid += 1
                    yield rec
                except json.JSONDecodeError as exc:
                    malformed += 1
                    emit_integrity_event(
                        "JSONL_CORRUPTION",
                        "WARNING",
                        "compress_logs_for_llm",
                        {
                            "path":        str(p),
                            "line_number": lineno,
                            "raw_preview": line[:160],
                            "error":       str(exc),
                        },
                    )
                    continue
        total = malformed + valid
        if total and (malformed / total) > MAX_CORRUPTION_RATIO:
            emit_integrity_event(
                "JSONL_CORRUPTION_THRESHOLD_EXCEEDED",
                "ERROR",
                "compress_logs_for_llm",
                {
                    "path":             str(p),
                    "malformed_lines":  malformed,
                    "valid_lines":      valid,
                    "corruption_ratio": malformed / total,
                },
            )


def _quantile(sorted_xs: list[float], q: float) -> float:
    if not sorted_xs:
        return 0.0
    idx = int(round((len(sorted_xs) - 1) * q))
    return float(sorted_xs[max(0, min(idx, len(sorted_xs) - 1))])


def compress(paths: list[Path], top_n_features: int = 8) -> dict:
    n_total = 0
    counts_outcome: dict[str, int] = {}
    counts_direction: dict[str, int] = {}
    counts_instrument: dict[str, int] = {}
    rr_values: list[float] = []
    mae_values: list[float] = []
    duration_values: list[int] = []

    # Streaming sums for per-feature correlation with rr
    feature_sum_x: dict[str, float] = {}
    feature_sum_x2: dict[str, float] = {}
    feature_sum_xy: dict[str, float] = {}
    feature_count: dict[str, int] = {}

    rr_sum = 0.0
    rr_sum_sq = 0.0

    # Mean features per outcome bucket
    feature_bucket_sum: dict[str, dict[str, float]] = {"TP_HIT": {}, "SL_HIT": {}}
    feature_bucket_count: dict[str, int] = {"TP_HIT": 0, "SL_HIT": 0}

    severe_mae: list[dict] = []
    sl_clusters: list[dict] = []

    for rec in _iter_records(paths):
        n_total += 1
        outcome = str(rec.get("outcome", "UNKNOWN"))
        direction = str(rec.get("direction", "UNKNOWN"))
        instrument = str(rec.get("instrument", "UNKNOWN"))
        rr = float(rec.get("rr_achieved", 0.0) or 0.0)
        mae = float(rec.get("mae", 0.0) or 0.0)
        duration = int(rec.get("duration_candles", 0) or 0)

        counts_outcome[outcome] = counts_outcome.get(outcome, 0) + 1
        counts_direction[direction] = counts_direction.get(direction, 0) + 1
        counts_instrument[instrument] = counts_instrument.get(instrument, 0) + 1
        rr_values.append(rr)
        mae_values.append(mae)
        duration_values.append(duration)
        rr_sum += rr
        rr_sum_sq += rr * rr

        feats = rec.get("features") or {}
        if isinstance(feats, dict):
            for fname, fval in feats.items():
                try:
                    fv = float(fval)
                except (TypeError, ValueError):
                    continue
                feature_sum_x[fname] = feature_sum_x.get(fname, 0.0) + fv
                feature_sum_x2[fname] = feature_sum_x2.get(fname, 0.0) + fv * fv
                feature_sum_xy[fname] = feature_sum_xy.get(fname, 0.0) + fv * rr
                feature_count[fname] = feature_count.get(fname, 0) + 1
                if outcome in feature_bucket_sum:
                    feature_bucket_sum[outcome][fname] = \
                        feature_bucket_sum[outcome].get(fname, 0.0) + fv

        if outcome in feature_bucket_count:
            feature_bucket_count[outcome] += 1

        if mae <= -0.005:
            if len(severe_mae) < 32:
                severe_mae.append({
                    "timestamp": rec.get("timestamp"),
                    "instrument": instrument,
                    "direction": direction,
                    "mae": mae,
                    "rr_achieved": rr,
                })

    if n_total == 0:
        raise ValueError("No records found in inputs.")

    rr_values.sort()
    rr_mean = rr_sum / n_total
    rr_var = max(0.0, rr_sum_sq / n_total - rr_mean * rr_mean)
    rr_std = math.sqrt(rr_var)

    correlations: dict[str, float] = {}
    for fname, count in feature_count.items():
        if count < 30:
            continue
        sum_x = feature_sum_x[fname]
        sum_x2 = feature_sum_x2[fname]
        sum_xy = feature_sum_xy[fname]
        n = count
        mean_x = sum_x / n
        var_x = max(0.0, sum_x2 / n - mean_x * mean_x)
        cov_xy = sum_xy / n - mean_x * rr_mean
        denom = math.sqrt(var_x * rr_var)
        if denom <= 1e-12:
            continue
        correlations[fname] = float(round(cov_xy / denom, 4))

    sorted_corrs = sorted(correlations.items(), key=lambda kv: kv[1], reverse=True)
    top_positive = sorted_corrs[:top_n_features]
    top_negative = sorted_corrs[-top_n_features:][::-1] if sorted_corrs else []

    feature_deltas: dict[str, float] = {}
    if feature_bucket_count["TP_HIT"] and feature_bucket_count["SL_HIT"]:
        for fname in feature_sum_x.keys():
            tp_mean = (
                feature_bucket_sum["TP_HIT"].get(fname, 0.0)
                / feature_bucket_count["TP_HIT"]
            )
            sl_mean = (
                feature_bucket_sum["SL_HIT"].get(fname, 0.0)
                / feature_bucket_count["SL_HIT"]
            )
            feature_deltas[fname] = float(round(tp_mean - sl_mean, 4))

    sorted_deltas = sorted(
        feature_deltas.items(), key=lambda kv: abs(kv[1]), reverse=True
    )[:top_n_features]

    # Anomaly: any outcome accounts for >70% of records
    for outcome, count in counts_outcome.items():
        share = count / n_total
        if share > 0.7:
            sl_clusters.append({
                "outcome": outcome,
                "share": round(share, 4),
                "count": count,
            })

    summary = {
        "n_total":      n_total,
        "rr_mean":      round(rr_mean, 4),
        "rr_std":       round(rr_std, 4),
        "rr_p10":       round(_quantile(rr_values, 0.10), 4),
        "rr_p50":       round(_quantile(rr_values, 0.50), 4),
        "rr_p90":       round(_quantile(rr_values, 0.90), 4),
        "counts_outcome":    counts_outcome,
        "counts_direction":  counts_direction,
        "counts_instrument": counts_instrument,
    }
    data = {
        "top_positive_corr": top_positive,
        "top_negative_corr": top_negative,
        "top_tp_minus_sl_delta": sorted_deltas,
    }
    anomalies = severe_mae + sl_clusters
    return {"summary": summary, "data": data, "anomalies": anomalies}


def _read_run_id_from_jsonl(path: Path) -> str:
    """Return run_id from the first-line run_header of a JSONL, or empty string."""
    try:
        with path.open("r", encoding="utf-8") as fh:
            rec = json.loads(fh.readline().strip())
        if rec.get("type") == "run_header":
            return rec.get("run_id", "")
    except Exception:
        pass
    return ""


def _expand_globs(patterns: list[str]) -> list[Path]:
    paths: list[Path] = []
    for pat in patterns:
        matched = sorted(glob.glob(pat))
        if matched:
            paths.extend(Path(m) for m in matched)
        else:
            paths.append(Path(pat))
    return paths


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--logs", nargs="+", required=True,
                    help="One or more JSONL paths (globs allowed)")
    ap.add_argument("--output", type=Path, default=None,
                    help="Destination JSON file. Required unless --instrument is provided.")
    ap.add_argument("--instrument", default="",
                    help="Instrument label (e.g. EURUSD, BTCUSDT). When provided and "
                         "--output is absent, output is run-scoped: "
                         "logs/{instrument}/{run_id}/compressed.json")
    ap.add_argument("--run-id", default=None,
                    help="Override run_id for output path "
                         "(default: read from JSONL run_header)")
    ap.add_argument("--top-n-features", type=int, default=8)
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    # Upfront input validation (must happen before output path resolution so we
    # can read the run_header from the first JSONL file)
    expanded = _expand_globs(args.logs)
    missing = [p for p in expanded if not p.exists()]
    if missing:
        for p in missing:
            print(f"ERROR: input file not found: {p}", file=sys.stderr)
        return 1
    paths = expanded

    # Resolve output path (run-scoped when instrument is given)
    if args.output is None:
        _run_id = args.run_id
        if not _run_id and paths:
            _run_id = _read_run_id_from_jsonl(paths[0])
        if args.instrument and _run_id:
            args.output = Path("logs") / args.instrument / _run_id / "compressed.json"
        elif args.instrument:
            # Fallback: no run_id available (old flat JSONL without run_header)
            args.output = Path("logs") / f"compressed_{args.instrument}.json"
        else:
            print("ERROR: --output is required when --instrument is not given.",
                  file=sys.stderr)
            return 1

    summary = compress(paths, top_n_features=args.top_n_features)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    logger.info(
        "compressed %d files -> %s (%d records)",
        len(paths), args.output, summary["summary"]["n_total"],
    )
    print(f"OUTPUT:compressed:{args.output.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
