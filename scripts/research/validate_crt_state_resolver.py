"""
CRT State Resolver Validation Script
=====================================
Validates the config-driven CRT state resolver against real market data.

This script:
1. Loads the CRT state resolver (config-driven)
2. Loads market data (OHLCV CSV → FeaturePipeline, enriched Parquet/JSONL, or synthetic)
3. Resolves CRT states for each bar
4. Reports per-state counts and compares against reference counts
5. Generates a validation report

Usage:
    # Preferred: rebuild features from the same MT5 M15 candles the CRT engine used
    python scripts/research/validate_crt_state_resolver.py \\
        --data data/mt5/XAUUSD_M15.csv \\
        --output reports/crt_state_resolver_validation.md

    # Enriched trade-level corpus (feature_* columns; not a full bar stream)
    python scripts/research/validate_crt_state_resolver.py \\
        --data results/research/trace_corpus/xauusd/trace_corpus_enriched.jsonl \\
        --output reports/crt_state_resolver_entry_level.md

    # Synthetic (default when --data omitted)
    python scripts/research/validate_crt_state_resolver.py --synthetic --bars 5000

Reference counts default to the CRT engine dwell distribution from
results/run_20260724_104845_XAUUSD/XAUUSD_summary.json (47,275 XAUUSD M15 bars):
  RANGE 35,159 | SWEEP 6,995 | EXPANSION 4,605 | DISPLACEMENT 373 |
  SHADOW_PENDING 43 | RETEST 17 | EXECUTION 5 | RESOLUTION 5 | EXPIRED 0
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Optional

import yaml

# Add project root + src to path
_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))

from features.crt_state_resolver import CRTStateResolver, CRTStateResolverError
# CLAUDE.md §4: non-ASCII console output must go through console_safe (cp1252
# fallback). print_report emits U+2713/U+2717 tick marks, which raised
# UnicodeEncodeError on a stock Windows console before this was routed.
from utils.console_safe import safe_print

logger = logging.getLogger("CRT_STATE_VALIDATOR")

# ── Reference counts (CRT engine dwell — XAUUSD M15, 47,275 bars) ─
# Source: results/run_20260724_104845_XAUUSD/XAUUSD_summary.json state_distribution
# RESOLUTION=5 is inferred as EXECUTION dwell twin; EXPIRED=0 per expansion_dwell_stats.
REFERENCE_COUNTS: dict[str, int] = {
    "RANGE": 35159,
    "SWEEP": 6995,
    "EXPANSION": 4605,
    "DISPLACEMENT": 373,
    "SHADOW_PENDING": 43,
    "RETEST": 17,
    "EXECUTION": 5,
    "RESOLUTION": 5,
    "EXPIRED": 0,
}

ALL_STATES = list(REFERENCE_COUNTS.keys())

# Extra non-vector stateful columns needed by predicates
_EXTRA_STATEFUL = ("retest_flag", "displacement_flag", "rsi_state")
_FEATURE_PREFIX = "feature_"


# ── Synthetic test data generator ────────────────────────────────

def _make_synthetic_features(
    liquidity_sweep: int = 0,
    sweep_detected: int = 0,
    double_sweep: int = 0,
    break_of_structure: int = 0,
    higher_high: int = 0,
    lower_low: int = 0,
    retest_flag: int = 0,
    displacement_flag: int = 0,
    volatility_regime: int = 1,
    trend_bias: int = 0,
    rsi_state: int = 0,
    **kwargs,
) -> dict[str, float]:
    """Create a synthetic feature dict for testing.

    Only the stateful features that the CRT resolver predicates reference
    are meaningful. Other features are filled with defaults.
    """
    features = {
        # Stateful features (vector-bound)
        "liquidity_sweep": float(liquidity_sweep),
        "sweep_detected": float(sweep_detected),
        "double_sweep": float(double_sweep),
        "break_of_structure": float(break_of_structure),
        "higher_high": float(higher_high),
        "lower_low": float(lower_low),
        "volatility_regime": float(volatility_regime),
        "trend_bias": float(trend_bias),
        # Non-vector stateful features
        "retest_flag": float(retest_flag),
        "displacement_flag": float(displacement_flag),
        "rsi_state": float(rsi_state),
        # Fillers (continuous features the encoder doesn't care about)
        "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0,
        "volume": 1000.0, "volume_ratio": 1.0,
        "ema_fast": 1.0, "ema_slow": 1.0, "ema_spread": 0.0,
        "trend_strength": 0.0, "momentum_score": 0.0,
        "atr": 0.01, "volatility_ratio": 1.0, "rsi_14": 50.0,
        "macd_line": 0.0, "macd_signal": 0.0, "macd_hist": 0.0,
        "swing_high": 0.0, "swing_low": 0.0,
        "body_size": 0.0, "wick_size": 0.0, "body_ratio": 0.5,
        "session": 0.0, "hour_of_day": 0.0,
        "disp_strength": 0.0, "retest_depth": 0.0,
        "candles_since_retest": 0.0,
        "liquidity_distance": 10.0, "liquidity_pressure_score": 0.0,
        "volume_spike": 0.0,
        # FM-083, vector-bound (idx 47) AND stateful since 2026-08-15, so
        # FeatureStateEncoder.classify() hard-requires it. Its absence made this
        # synthetic path raise on bar 0 before it could validate anything.
        "change_of_character": 0.0,
        # v4.0 canonical name. `wick_size` above is the pre-v4.0 spelling, kept
        # because _displacement_entry_allowed still carries a documented
        # wick_size fallback -- both are supplied so neither branch is starved.
        "candle_range": 0.0,
    }
    features.update(kwargs)
    return features


def _generate_synthetic_sequence(length: int = 1000) -> list[dict[str, float]]:
    """Generate a synthetic feature sequence that exercises all CRT states.

    Creates a realistic sequence with:
    - Mostly RANGE bars
    - Occasional SWEEP events
    - Some SWEEP → DISPLACEMENT progressions
    - Some DISPLACEMENT → EXPANSION progressions
    - Rare EXPANSION → RETEST progressions
    - Very rare RETEST → EXECUTION progressions
    """
    import random
    random.seed(42)

    sequence: list[dict[str, float]] = []
    sweep_cooldown = 0
    displacement_cooldown = 0
    expansion_active = False
    expansion_bars = 0
    retest_active = False
    execution_active = False

    for i in range(length):
        # Default: RANGE
        feat = _make_synthetic_features()

        if execution_active:
            # EXECUTION → RESOLUTION after a few bars
            if random.random() < 0.3:
                execution_active = False
                feat["retest_flag"] = 0
                feat["trend_bias"] = 0
                feat["rsi_state"] = 0
            else:
                feat["retest_flag"] = 1
                feat["trend_bias"] = 1
                feat["rsi_state"] = 0
                feat["session"] = 3.0  # OVERLAP — required for EXECUTION predicate
            sequence.append(feat)
            continue

        if retest_active:
            # RETEST → EXECUTION rarely
            if random.random() < 0.05:
                retest_active = False
                execution_active = True
                feat["retest_flag"] = 1
                feat["trend_bias"] = 1
                feat["rsi_state"] = 0
            elif random.random() < 0.3:
                retest_active = False
                expansion_active = False
                # Back to RANGE
            else:
                feat["retest_flag"] = 1
                feat["sweep_detected"] = 1
                feat["break_of_structure"] = 0
            sequence.append(feat)
            continue

        if expansion_active:
            expansion_bars += 1
            # EXPANSION → RETEST rarely
            if expansion_bars > 5 and random.random() < 0.02:
                expansion_active = False
                retest_active = True
                feat["retest_flag"] = 1
                feat["sweep_detected"] = 1
                feat["break_of_structure"] = 0
                feat["displacement_flag"] = 0
            elif expansion_bars > 20 and random.random() < 0.1:
                expansion_active = False
                # Back to RANGE
            else:
                feat["break_of_structure"] = 1
                feat["volatility_regime"] = 2
                feat["displacement_flag"] = 1
            sequence.append(feat)
            continue

        if displacement_cooldown > 0:
            displacement_cooldown -= 1
            if displacement_cooldown == 0 and random.random() < 0.3:
                # DISPLACEMENT → EXPANSION
                expansion_active = True
                expansion_bars = 0
                feat["break_of_structure"] = 1
                feat["volatility_regime"] = 2
                feat["displacement_flag"] = 1
            else:
                feat["sweep_detected"] = 1
                feat["displacement_flag"] = 1
                feat["break_of_structure"] = 0
            sequence.append(feat)
            continue

        if sweep_cooldown > 0:
            sweep_cooldown -= 1
            if sweep_cooldown == 0 and random.random() < 0.15:
                # SWEEP → DISPLACEMENT
                displacement_cooldown = random.randint(1, 3)
                feat["sweep_detected"] = 1
                feat["displacement_flag"] = 1
                feat["break_of_structure"] = 0
            else:
                feat["liquidity_sweep"] = random.choice([-1, 1])
                feat["sweep_detected"] = 1
                feat["break_of_structure"] = 0
                feat["displacement_flag"] = 0
            sequence.append(feat)
            continue

        # RANGE: occasional sweep
        if random.random() < 0.05:
            sweep_cooldown = random.randint(1, 3)
            feat["liquidity_sweep"] = random.choice([-1, 1])
            feat["sweep_detected"] = 1
            feat["break_of_structure"] = 0
            feat["displacement_flag"] = 0

        sequence.append(feat)

    return sequence


# ── Validation logic ─────────────────────────────────────────────

def validate_resolver(
    resolver: CRTStateResolver,
    feature_vectors: list[dict[str, float]],
    label: str = "validation",
) -> dict[str, Any]:
    """Run the resolver on a sequence of feature vectors and report results."""
    resolver.reset_counts()
    resolver.reset_memory()

    state_sequence: list[str] = []
    for fv in feature_vectors:
        state = resolver.resolve(fv)
        state_sequence.append(state)

    counts = resolver.counts
    total = sum(counts.values())

    # Build report
    report = {
        "label": label,
        "total_bars": total,
        "counts": counts,
        "transitions": resolver.transition_count,
        "state_sequence_sample": state_sequence[:20],  # first 20 for inspection
    }

    return report


def print_report(report: dict[str, Any], reference: dict[str, int] | None = None) -> None:
    """Print a formatted validation report."""
    safe_print(f"\n{'='*60}")
    safe_print(f"CRT State Resolver Validation: {report['label']}")
    safe_print(f"{'='*60}")
    safe_print(f"Total bars: {report['total_bars']}")
    safe_print(f"Transitions: {report['transitions']}")
    safe_print(f"\n{'State':<20} {'Count':<10} {'%':<8} {'Reference':<10} {'Match?':<10}")
    safe_print(f"{'-'*60}")

    counts = report["counts"]
    total = report["total_bars"]
    ref = reference or {}

    for state in ALL_STATES:
        c = counts.get(state, 0)
        pct = (c / total * 100) if total > 0 else 0
        r = ref.get(state, 0)
        match = "✓" if abs(c - r) <= max(1, r * 0.1) else "✗"
        safe_print(f"{state:<20} {c:<10} {pct:<8.2f} {r:<10} {match:<10}")

    # Unmatched states
    unmatched = set(counts.keys()) - set(ALL_STATES)
    if unmatched:
        safe_print(f"\nUNMATCHED STATES: {unmatched}")

    safe_print(f"\nFirst 20 states: {report['state_sequence_sample']}")
    safe_print(f"{'='*60}\n")


def run_synthetic_test(resolver: CRTStateResolver, bars: int = 5000) -> dict[str, Any]:
    """Run the resolver on synthetic data that exercises all states.

    `bars` was previously hardcoded here, so the `--bars` CLI flag was declared
    but never read -- a declared-but-unconsumed knob (the config-illusion class,
    cf. F-056). It is threaded through now.
    """
    print(f"Generating synthetic feature sequence ({bars} bars)...")
    sequence = _generate_synthetic_sequence(bars)
    report = validate_resolver(resolver, sequence, "synthetic")
    print_report(report, REFERENCE_COUNTS)
    return report


def _derive_rsi_state(rsi_14: float, overbought: float = 70.0, oversold: float = 30.0) -> float:
    """Map continuous rsi_14 → rsi_state ternary (FM-068)."""
    if rsi_14 > overbought:
        return 1.0
    if rsi_14 < oversold:
        return -1.0
    return 0.0


def _row_to_feature_dict(
    row: Any,
    columns: list[str],
    *,
    rsi_overbought: float = 70.0,
    rsi_oversold: float = 30.0,
) -> dict[str, float]:
    """Extract a feature dict from a DataFrame row (handles feature_ prefix)."""
    from features.feature_schema import CANONICAL_FEATURES

    fv: dict[str, float] = {}
    colset = set(columns)

    def _get(name: str) -> Optional[float]:
        for key in (name, f"{_FEATURE_PREFIX}{name}"):
            if key in colset:
                val = row[key]
                try:
                    import pandas as pd
                    if pd.isna(val):
                        return None
                except Exception:
                    pass
                return float(val)
        return None

    for name in CANONICAL_FEATURES:
        val = _get(name)
        if val is not None:
            fv[name] = val

    for name in _EXTRA_STATEFUL:
        val = _get(name)
        if val is not None:
            fv[name] = val

    # Derive rsi_state from rsi_14 when absent (non-vector FM-068)
    if "rsi_state" not in fv:
        rsi = fv.get("rsi_14")
        if rsi is not None:
            fv["rsi_state"] = _derive_rsi_state(rsi, rsi_overbought, rsi_oversold)
        else:
            fv["rsi_state"] = 0.0

    # Defaults for missing non-vector flags (predicate fails closed without them)
    for name in ("retest_flag", "displacement_flag"):
        if name not in fv:
            fv[name] = 0.0

    return fv


def _load_dataframe(path: Path):
    """Load OHLCV/enriched data from CSV, Parquet, or JSONL."""
    import pandas as pd

    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return pd.read_parquet(path)
    if suffix == ".csv":
        df = pd.read_csv(path)
        # Normalize timestamp column if present
        for ts_col in ("timestamp", "time", "datetime", "date"):
            if ts_col in df.columns:
                df[ts_col] = pd.to_datetime(df[ts_col])
                break
        return df
    if suffix == ".jsonl":
        rows = []
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        return pd.DataFrame(rows)
    raise ValueError(f"Unsupported data format: {suffix} (use .csv/.parquet/.jsonl)")


def _is_ohlcv_only(df) -> bool:
    """True when the frame is raw candles (needs FeaturePipeline enrichment)."""
    cols = {c.lower() for c in df.columns}
    ohlcv = {"open", "high", "low", "close", "volume"}
    has_ohlcv = ohlcv.issubset(cols)
    # Already enriched if any structural feature is present (raw or feature_ prefixed)
    structural = {
        "liquidity_sweep", "sweep_detected", "break_of_structure",
        "feature_liquidity_sweep", "feature_sweep_detected",
    }
    col_names = set(df.columns) | cols
    already = bool(structural & col_names)
    return has_ohlcv and not already


def _enrich_ohlcv(df):
    """Run FeaturePipeline on raw OHLCV → enriched frame + non-vector flags."""
    from features.feature_pipeline import FeaturePipeline

    # Ensure lowercase OHLCV column names
    rename = {c: c.lower() for c in df.columns if c.lower() in
              {"open", "high", "low", "close", "volume", "timestamp", "time"}}
    work = df.rename(columns=rename)
    print(f"  Running FeaturePipeline on {len(work):,} OHLCV bars...")
    pipeline = FeaturePipeline(work)
    enriched, _vectors = pipeline.run()
    print(f"  Enriched → {len(enriched):,} bars (warmup rows dropped by finalize)")
    # Non-vector columns are retained on the pipeline df before finalize; re-merge if lost
    for col in _EXTRA_STATEFUL:
        if col not in enriched.columns and col in pipeline.df.columns:
            # Align by index intersection
            enriched[col] = pipeline.df.loc[enriched.index, col]
    # rsi_state may not be a pipeline column — derived later from rsi_14
    return enriched


def load_feature_vectors(
    data_path: str,
    *,
    rsi_overbought: float = 70.0,
    rsi_oversold: float = 30.0,
) -> tuple[list[dict[str, float]], str]:
    """Load feature vectors from CSV/Parquet/JSONL.

    Returns (feature_vectors, label).
    """
    path = Path(data_path)
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")

    print(f"Loading data from {path}...")
    df = _load_dataframe(path)
    print(f"  Raw rows: {len(df):,}  columns: {len(df.columns)}")

    if _is_ohlcv_only(df):
        print("  Detected raw OHLCV — building features via FeaturePipeline")
        df = _enrich_ohlcv(df)
    else:
        print("  Detected pre-enriched / feature_* frame")

    # Column inventory
    from features.feature_schema import CANONICAL_FEATURES
    present = []
    for name in CANONICAL_FEATURES:
        if name in df.columns or f"{_FEATURE_PREFIX}{name}" in df.columns:
            present.append(name)
    missing = [c for c in CANONICAL_FEATURES if c not in present]
    if missing:
        print(f"  WARNING: {len(missing)} canonical features missing: {missing[:12]}...")
    for col in _EXTRA_STATEFUL:
        has = col in df.columns or f"{_FEATURE_PREFIX}{col}" in df.columns
        if not has and col != "rsi_state":
            print(f"  WARNING: '{col}' absent — defaulting to 0 (predicates may under-fire)")
        elif not has and col == "rsi_state":
            print("  INFO: rsi_state absent — deriving from rsi_14 (FM-068)")

    feature_vectors: list[dict[str, float]] = []
    cols = list(df.columns)
    for _, row in df.iterrows():
        feature_vectors.append(
            _row_to_feature_dict(
                row, cols,
                rsi_overbought=rsi_overbought,
                rsi_oversold=rsi_oversold,
            )
        )

    print(f"  Built {len(feature_vectors):,} feature vectors "
          f"({len(present)}/{len(CANONICAL_FEATURES)} canonical present)")
    return feature_vectors, path.stem


def run_data_test(
    resolver: CRTStateResolver,
    data_path: str,
    reference: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Run the resolver on real data (OHLCV CSV / Parquet / JSONL)."""
    thr = resolver._config.get("thresholds", {})
    feature_vectors, label = load_feature_vectors(
        data_path,
        rsi_overbought=float(thr.get("rsi_overbought", 70)),
        rsi_oversold=float(thr.get("rsi_oversold", 30)),
    )
    report = validate_resolver(resolver, feature_vectors, label)
    print_report(report, reference or REFERENCE_COUNTS)
    return report


# Back-compat alias
def run_parquet_test(
    resolver: CRTStateResolver,
    parquet_path: str,
) -> dict[str, Any]:
    return run_data_test(resolver, parquet_path)


# ── Threshold tuning mode ────────────────────────────────────────

def interactive_tune(resolver: CRTStateResolver, feature_vectors: list[dict[str, float]]) -> None:
    """Interactive threshold tuning mode.

    Allows the user to adjust thresholds and see how counts change.
    """
    import shlex

    print("\n" + "="*60)
    print("INTERACTIVE THRESHOLD TUNING MODE")
    print("="*60)
    print("Commands:")
    print("  show                    — show current thresholds and counts")
    print("  set <key> <value>      — set a threshold (e.g., set body_ratio_min 0.80)")
    print("  reload                 — reload config from file")
    print("  run                    — re-run validation with current thresholds")
    print("  save <path>            — save current config to path")
    print("  help                   — show this help")
    print("  quit                   — exit")
    print()

    while True:
        try:
            cmd = input("tune> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not cmd:
            continue

        parts = shlex.split(cmd)
        action = parts[0].lower()

        if action == "quit":
            break
        elif action == "show":
            print(f"\nCurrent thresholds:")
            for k, v in resolver._config.get("thresholds", {}).items():
                print(f"  {k}: {v}")
            print(f"\nCurrent counts:")
            for state, count in sorted(resolver.counts.items()):
                print(f"  {state}: {count}")
        elif action == "set" and len(parts) >= 3:
            key = parts[1]
            try:
                value = float(parts[2])
            except ValueError:
                print(f"Invalid value: {parts[2]}")
                continue
            if "thresholds" not in resolver._config:
                resolver._config["thresholds"] = {}
            resolver._config["thresholds"][key] = value
            print(f"Set {key} = {value}")
        elif action == "reload":
            resolver._config = resolver._load_config()
            print("Config reloaded.")
        elif action == "run":
            resolver.reset_counts()
            resolver.reset_memory()
            for fv in feature_vectors:
                resolver.resolve(fv)
            print(f"\nResults after tuning:")
            for state, count in sorted(resolver.counts.items()):
                ref = REFERENCE_COUNTS.get(state, 0)
                match = "✓" if abs(count - ref) <= max(1, ref * 0.1) else "✗"
                print(f"  {state:<20} {count:<10} (ref: {ref:<10}) {match}")
        elif action == "save" and len(parts) >= 2:
            path = parts[1]
            try:
                with open(path, "w", encoding="utf-8") as fh:
                    yaml.dump(resolver._config, fh, default_flow_style=False)
                print(f"Config saved to {path}")
            except Exception as e:
                print(f"Save failed: {e}")
        else:
            print("Unknown command. Type 'help' for available commands.")


# ── Main ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Validate CRT state resolver against market data"
    )
    parser.add_argument(
        "--data", type=str, default=None,
        help="Path to OHLCV CSV, enriched Parquet, or feature JSONL"
    )
    parser.add_argument(
        "--config", type=str, default=None,
        help="Path to CRT states config (default: configs/formulas/market_crt_states.yaml)"
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Path to write validation report (Markdown)"
    )
    parser.add_argument(
        "--synthetic", action="store_true", default=False,
        help="Run synthetic test (also default when --data omitted)"
    )
    parser.add_argument(
        "--threshold-tune", action="store_true", default=False,
        help="Interactive threshold tuning mode"
    )
    parser.add_argument(
        "--bars", type=int, default=5000,
        help="Number of synthetic bars to generate (default: 5000)"
    )
    parser.add_argument(
        "--reference-summary", type=str, default=None,
        help="Optional CRT engine summary.json to override REFERENCE_COUNTS "
             "(reads state_distribution)"
    )
    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s | %(message)s",
    )

    # Optional reference override from engine summary
    reference = dict(REFERENCE_COUNTS)
    if args.reference_summary:
        with open(args.reference_summary, "r", encoding="utf-8") as fh:
            summary = json.load(fh)
        dist = summary.get("state_distribution") or {}
        if not dist:
            print(f"ERROR: no state_distribution in {args.reference_summary}")
            sys.exit(1)
        reference = {s: int(dist.get(s, 0)) for s in ALL_STATES}
        # Fill RESOLUTION/EXPIRED if engine omits them
        if "RESOLUTION" not in dist:
            reference["RESOLUTION"] = reference.get("EXECUTION", 0)
        if "EXPIRED" not in dist:
            reference["EXPIRED"] = 0
        print(f"Reference counts loaded from {args.reference_summary}")
        print(f"  {reference}")

    # Create resolver
    print("Initializing CRT State Resolver...")
    try:
        resolver = CRTStateResolver(config_path=args.config)
        print(f"  Config: {resolver._config_path}")
        print(f"  States defined: {[s['name'] for s in resolver._config['states']]}")
        print(f"  Stateful features: {len(resolver._encoder.stateful_features)}")
        # Confirm session is on EXECUTION
        exec_when = next(
            (s.get("when", {}) for s in resolver._config["states"] if s["name"] == "EXECUTION"),
            {},
        )
        print(f"  EXECUTION predicates: {exec_when}")
        range_when = next(
            (s.get("when", {}) for s in resolver._config["states"] if s["name"] == "RANGE"),
            {},
        )
        print(f"  RANGE predicates include swings: "
              f"swing_high={range_when.get('swing_high')}, swing_low={range_when.get('swing_low')}")
    except CRTStateResolverError as e:
        print(f"ERROR initializing resolver: {e}")
        sys.exit(1)

    # Run tests
    reports: list[dict[str, Any]] = []
    feature_vectors_for_tune: list[dict[str, float]] | None = None

    if args.data:
        thr = resolver._config.get("thresholds", {})
        feature_vectors_for_tune, label = load_feature_vectors(
            args.data,
            rsi_overbought=float(thr.get("rsi_overbought", 70)),
            rsi_oversold=float(thr.get("rsi_oversold", 30)),
        )
        report = validate_resolver(resolver, feature_vectors_for_tune, label)
        print_report(report, reference)
        reports.append(report)
    elif args.synthetic or not args.data:
        report = run_synthetic_test(resolver, bars=args.bars)
        reports.append(report)

    # Interactive tuning
    if args.threshold_tune:
        if feature_vectors_for_tune is None:
            print("ERROR: --threshold-tune requires --data")
            sys.exit(1)
        interactive_tune(resolver, feature_vectors_for_tune)

    # Write report
    if args.output and reports:
        _write_markdown_report(reports, args.output, reference)


def _match_rate(count: int, ref: int) -> float:
    """Relative match: 1.0 = exact; 0.0 = completely off. Cap at 1.0."""
    if ref == 0:
        return 1.0 if count == 0 else 0.0
    return max(0.0, 1.0 - abs(count - ref) / ref)


def _write_markdown_report(
    reports: list[dict[str, Any]],
    path: str,
    reference: dict[str, int] | None = None,
) -> None:
    """Write a Markdown validation report."""
    ref = reference or REFERENCE_COUNTS
    lines = [
        "# CRT State Resolver Validation Report",
        f"\n> Generated: {__import__('datetime').datetime.now().isoformat()}",
        "",
        "## Reference source",
        "",
        "CRT engine dwell counts from XAUUSD M15 (`state_distribution` in engine",
        "summary). Resolver counts are **bar-level predicate + transition graph**",
        "classifications — not expected to match byte-for-byte (engine has soft-confirm,",
        "score threshold, session filter, and HTF reset logic beyond feature predicates).",
        "",
        f"Reference total: **{sum(ref.values()):,}** bar-dwells",
        "",
    ]

    for report in reports:
        counts = report["counts"]
        total = report["total_bars"]
        n_match = sum(
            1 for s in ALL_STATES
            if abs(counts.get(s, 0) - ref.get(s, 0)) <= max(1, ref.get(s, 0) * 0.1)
        )
        lines.extend([
            f"## Dataset: `{report['label']}`",
            f"",
            f"- **Total bars resolved:** {total:,}",
            f"- **Transitions:** {report['transitions']:,}",
            f"- **States within 10% of reference:** {n_match}/{len(ALL_STATES)}",
            f"",
            f"| State | Resolver | % | Reference | Δ | Rel. match | Within 10% |",
            f"|-------|----------|---|-----------|---|------------|------------|",
        ])
        for state in ALL_STATES:
            c = counts.get(state, 0)
            pct = (c / total * 100) if total > 0 else 0
            r = ref.get(state, 0)
            delta = c - r
            mr = _match_rate(c, r)
            ok = "✓" if abs(c - r) <= max(1, r * 0.1) else "✗"
            lines.append(
                f"| {state} | {c:,} | {pct:.2f}% | {r:,} | {delta:+,} | {mr:.1%} | {ok} |"
            )

        # Funnel view (engine ordering)
        funnel = ["RANGE", "SWEEP", "DISPLACEMENT", "EXPANSION", "RETEST", "EXECUTION"]
        lines.extend([
            f"",
            f"### Funnel (resolver vs engine)",
            f"",
            f"| Stage | Resolver | Reference | Conversion (resolver) |",
            f"|-------|----------|-----------|----------------------|",
        ])
        prev_c = None
        for state in funnel:
            c = counts.get(state, 0)
            r = ref.get(state, 0)
            if prev_c and prev_c > 0:
                conv = f"{100.0 * c / prev_c:.2f}%"
            else:
                conv = "—"
            lines.append(f"| {state} | {c:,} | {r:,} | {conv} |")
            prev_c = c if c > 0 else prev_c

        lines.extend([
            f"",
            f"### State Sequence (first 20 bars)",
            f"```",
            f"{' → '.join(report['state_sequence_sample'])}",
            f"```",
            f"",
            f"### Interpretation notes",
            f"",
            f"- **RANGE/SWEEP** should be in the same order of magnitude if",
            f"  `liquidity_sweep` / `sweep_detected` match the engine's sweep geometry.",
            f"- **DISPLACEMENT/EXPANSION/RETEST** diverge when predicates use feature-pipeline",
            f"  flags (`displacement_flag`, `retest_flag`) that are *similar but not identical*",
            f"  to CRT engine gates (`body_ratio>=0.70`, EMA retest band, expansion ATR distance).",
            f"- **EXECUTION** requires `session ∈ {{LONDON,NEWYORK,OVERLAP}}` + retest + trend +",
            f"  neutral RSI — still under-counts vs engine because score/soft-confirm are not",
            f"  feature-state predicates.",
            f"- **SHADOW_PENDING / EXPIRED / RESOLUTION** are memory states; feature-only",
            f"  resolution cannot fully reproduce HTF-reset and trade-lifecycle logic.",
            f"",
        ])

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"Report written to {out}")


if __name__ == "__main__":
    main()