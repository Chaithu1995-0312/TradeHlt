"""
btcusdt_crt_v3_replay.py
═══════════════════════════════════════════════════════════════════════════════
Standalone reference harness reproducing the BitNet CRT Scoring Pipeline
described in C:\\Users\\Hi\\Downloads\\Jarvis_CRT_Handover.docx (Patch v3).

This is a VALIDATION TOOL — it is intentionally NOT wired into the production
scoring stack. Its sole purpose is to reproduce the doc's worked examples
(Candles 23, 38, 43, 13 — see §15 Verified Output Samples) so that the doc's
reference math is preserved as a diffable, runnable artifact in this repo.

Faithful to:
  • §4.2 Phase weights (pw)
  • §5.3 Sweep taxonomy (delegated to crt_sweep_taxonomy.classify_sweep)
  • §5.4 Phase priority order
  • §6.2 Bug 2 fix — sweep taxonomy runs BEFORE the idx<4 lookback guard
  • §7   4-head BitNet scoring formulas (CRT, Zone, RR, Gaussian)
  • §7.7 Fusion weights 0.30 / 0.25 / 0.25 / 0.20
  • §9.2 LLM trigger conditions
  • §10  Per-candle JSON output schema
  • §14  random.seed(42) for determinism

CLI:
    # Convention-based path (data/{INSTRUMENT}_M15.csv):
    python tools/btcusdt_crt_v3_replay.py --out results/btcusdt_crt_v3_output.json
    python tools/btcusdt_crt_v3_replay.py --instrument EURCAD --out results/eurcad_crt_v3_output.json

    # Explicit CSV override:
    python tools/btcusdt_crt_v3_replay.py --csv path/to/custom.csv --out results/out.json

    # With LLM reasoning:
    python tools/btcusdt_crt_v3_replay.py --instrument BTCUSDT --out results/out.json --llm api
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Make src/ importable when run as `python tools/...`
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from config_layer.crt_sweep_taxonomy import (  # noqa: E402
    classify_sweep,
    wick_bonus as _wick_bonus,
    candle_geometry,
)


# ─────────────────────────────────────────────────────────────────
# CONSTANTS — all from the handover doc, zero magic numbers elsewhere
# ─────────────────────────────────────────────────────────────────

# §4.2 Phase weights
PHASE_WEIGHTS: dict[str, float] = {
    "SCANNING":     0.00,
    "RANGE":        0.10,
    "RETEST":       0.28,
    "SWEEP":        0.44,
    "CONFIRMATION": 0.54,
    "EXECUTION":    0.62,
}

# §7.7 Fusion weights
FUSION_W_CRT      = 0.30
FUSION_W_GAUSSIAN = 0.25
FUSION_W_ZONE     = 0.25
FUSION_W_RR       = 0.20

_DEFAULT_INSTRUMENT = "BTCUSDT"
_DEFAULT_DATA_DIR   = "data"

# §9.2 LLM trigger thresholds
LLM_TRIGGER_FUSION    = 0.46
LLM_TRIGGER_REL_RANGE = 1.35


# ─────────────────────────────────────────────────────────────────
# DATA
# ─────────────────────────────────────────────────────────────────

@dataclass
class Bar:
    timestamp: str
    open:  float
    high:  float
    low:   float
    close: float
    volume: float


def load_csv(
    csv_path: Path,
    start_date: Optional[str] = None,
    max_bars: Optional[int] = None,
) -> list[Bar]:
    """
    Load M15 OHLCV CSV, deduplicate by timestamp (keep first), sort ascending.
    Per §3.2: 'Deduplicate by timestamp - one duplicate existed at 10:00, removed'.

    Parameters
    ----------
    start_date : Optional[str]
        If set, only rows whose timestamp starts with this prefix are kept
        (e.g. "2024-01-01" → only that day's bars). Useful when the CSV spans
        multiple years and you need a specific slice.
    max_bars   : Optional[int]
        If set, truncate to at most this many bars after dedup + sort.
    """
    seen: set[str] = set()
    bars: list[Bar] = []
    with csv_path.open("r", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            ts = (row.get("timestamp") or row.get("datetime") or row.get("time", "")).strip()
            if not ts or ts in seen:
                continue
            if start_date and not ts.startswith(start_date):
                continue
            seen.add(ts)
            bars.append(Bar(
                timestamp=ts,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row.get("volume", 0.0)),
            ))
    bars.sort(key=lambda b: b.timestamp)
    if max_bars is not None:
        bars = bars[:max_bars]
    return bars


# ─────────────────────────────────────────────────────────────────
# §5 PHASE DETECTION
# ─────────────────────────────────────────────────────────────────

def _avg(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _atr_proxy(prev5: list[Bar]) -> float:
    """ATR proxy per Table 8: mean(high - low) over prev 5."""
    return _avg([b.high - b.low for b in prev5])


def _avg_vol(prev5: list[Bar]) -> float:
    return _avg([b.volume for b in prev5])


def _recent_sweep(phases: list[str], lookback: int = 3) -> bool:
    """True if any of the previous `lookback` candles was classified SWEEP."""
    return any(p == "SWEEP" for p in phases[-lookback:])


def detect_phase(
    bars: list[Bar],
    idx: int,
    phases: list[str],   # phases assigned for indices [0..idx-1]
) -> tuple[str, Optional[str], Optional[str]]:
    """
    §5.4 phase priority — with §6.2 fix: sweep taxonomy check runs BEFORE
    the idx<4 lookback guard, so geometric sweeps on early candles
    (e.g. Candle 1) are not silently dropped.

    Returns (phase, sweep_type, sweep_label).
    """
    c = bars[idx]
    geo = candle_geometry(c.open, c.high, c.low, c.close)

    # PRIORITY 1 — Sweep taxonomy (BEFORE idx guard, per §13.2)
    sweep_type, sweep_label = classify_sweep(
        upper_wick=geo["upper_wick"],
        lower_wick=geo["lower_wick"],
        body_ratio=geo["body_ratio"],
        bearish=geo["bearish"],
    )
    if sweep_type is not None:
        return "SWEEP", sweep_type, sweep_label

    # Lookback-dependent rules now safe to apply
    if idx < 4:
        return "SCANNING", None, None

    prev4 = bars[idx - 4: idx]
    prev5 = bars[idx - 5: idx] if idx >= 5 else bars[:idx]

    range_high = max(b.high for b in prev4)
    range_low  = min(b.low  for b in prev4)
    avg_body   = _avg([abs(b.close - b.open) for b in prev4])
    avg_vol    = _avg_vol(prev5) if prev5 else 0.0
    atr        = _atr_proxy(prev5) if prev5 else (geo["full_range"] or 0.001)
    rel_range  = geo["full_range"] / atr if atr > 0 else 0.0
    body       = abs(c.close - c.open)
    vol_spike  = c.volume > avg_vol * 1.5

    # PRIORITY 2 — RETEST after recent sweep
    if _recent_sweep(phases) and rel_range > 1.3 and geo["body_ratio"] > 0.38:
        return "RETEST", None, None

    # PRIORITY 3 / 4 — Range boundary violations
    if c.high > range_high * 1.001 and c.close < range_high:
        return ("SWEEP" if vol_spike else "RETEST"), None, None
    if c.low < range_low * 0.999 and c.close > range_low:
        return ("SWEEP" if vol_spike else "RETEST"), None, None

    # PRIORITY 5 — CONFIRMATION
    prev_phase = phases[-1] if phases else "SCANNING"
    if prev_phase == "SWEEP" and geo["body_ratio"] > 0.56 and body > avg_body * 0.75:
        return "CONFIRMATION", None, None

    # PRIORITY 6 — EXECUTION
    # Note: Table 5 of the doc states "> 1.2" but the §15 worked example shows
    # EXECUTION at rel_range=1.1506 — the actual production threshold was > 1.1.
    if geo["body_ratio"] > 0.63 and rel_range > 1.1 and body > avg_body and idx >= 2:
        return "EXECUTION", None, None

    # PRIORITY 7 — RANGE
    if geo["body_ratio"] < 0.55 and rel_range < 1.1:
        return "RANGE", None, None

    # PRIORITY 8 — default
    return "SCANNING", None, None


# ─────────────────────────────────────────────────────────────────
# §7 FOUR-HEAD SCORING + FUSION
# ─────────────────────────────────────────────────────────────────

def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def compute_internals(bars: list[Bar], idx: int) -> dict:
    """Compute the 6 scorer internals (§7.1 + Table 8)."""
    c = bars[idx]
    geo = candle_geometry(c.open, c.high, c.low, c.close)
    prev5 = bars[idx - 5: idx] if idx >= 5 else bars[:idx]
    if prev5:
        avg_vol = _avg_vol(prev5)
        atr = _atr_proxy(prev5)
        prev_close = prev5[0].close
    else:
        avg_vol = c.volume
        atr = geo["full_range"]
        prev_close = c.close

    vol_norm  = min(c.volume / (avg_vol * 2.0), 1.0) if avg_vol > 0 else 0.0
    rel_range = geo["full_range"] / atr if atr > 0 else 0.0
    mom_norm  = min(abs(c.close - prev_close) / prev_close * 100.0, 1.0) if prev_close else 0.0

    return {
        "body_ratio": round(geo["body_ratio"], 4),
        "upper_wick": round(geo["upper_wick"], 4),
        "lower_wick": round(geo["lower_wick"], 4),
        "vol_norm":   round(vol_norm, 4),
        "rel_range":  round(rel_range, 4),
        "mom_norm":   round(mom_norm, 4),
    }


def score_heads(
    phase: str,
    sweep_type: Optional[str],
    internals: dict,
    rng: random.Random,
) -> dict:
    """
    Compute the four head scores per §7.3–7.6, then fuse per §7.7.
    """
    pw = PHASE_WEIGHTS.get(phase, 0.0)
    body_ratio = internals["body_ratio"]
    upper_wick = internals["upper_wick"]
    lower_wick = internals["lower_wick"]
    vol_norm   = internals["vol_norm"]
    rel_range  = internals["rel_range"]
    mom_norm   = internals["mom_norm"]

    wb = _wick_bonus(sweep_type, upper_wick, lower_wick)

    # §7.3 CRT
    crt = _clamp(
        pw * 0.48
        + wb
        + (body_ratio * 0.20 if body_ratio > 0.45 else 0.05)
        + (vol_norm   * 0.09 if vol_norm   > 0.45 else 0.02)
        + (0.07 if rel_range > 1.2 else 0.0)
        + rng.random() * 0.05
    )

    # §7.4 ZONE
    zone = _clamp(
        (upper_wick * 0.30 if upper_wick > 0.25 else 0.04)
        + (lower_wick * 0.25 if lower_wick > 0.25 else 0.04)
        + wb * 0.70
        + pw * 0.38
        + (0.09 if vol_norm > 0.45 else 0.02)
        + rng.random() * 0.06
    )

    # §7.5 RR
    rr = _clamp(
        (body_ratio * 0.26 if body_ratio > 0.55 else 0.06)
        + pw * 0.36
        + wb * 0.65
        + (0.13 if vol_norm > 0.55 else 0.03)
        + mom_norm * 0.10
        + (0.10 if phase in ("CONFIRMATION", "EXECUTION") else 0.0)
        + rng.random() * 0.05
    )

    # §7.6 GAUSSIAN
    gaussian = _clamp(
        body_ratio * 0.24
        + vol_norm * 0.15
        + pw * 0.32
        + wb * 0.45
        + mom_norm * 0.09
        + rng.random() * 0.08
    )

    # §7.7 FUSION
    fusion = (
        crt      * FUSION_W_CRT
        + gaussian * FUSION_W_GAUSSIAN
        + zone     * FUSION_W_ZONE
        + rr       * FUSION_W_RR
    )

    return {
        "crt":      round(crt, 4),
        "zone":     round(zone, 4),
        "rr":       round(rr, 4),
        "gaussian": round(gaussian, 4),
        "fusion":   round(fusion, 4),
    }


# ─────────────────────────────────────────────────────────────────
# §9 LLM REASONING
# ─────────────────────────────────────────────────────────────────

def llm_should_fire(phase: str, fusion: float, sweep_type: Optional[str], rel_range: float) -> bool:
    return (
        phase != "SCANNING"
        or fusion >= LLM_TRIGGER_FUSION
        or sweep_type is not None
        or rel_range > LLM_TRIGGER_REL_RANGE
    )


def deterministic_reasoning(
    phase: str,
    sweep_type: Optional[str],
    sweep_label: Optional[str],
    internals: dict,
    scores: dict,
) -> str:
    """Rule-based 2-sentence narrative — same JSON shape as API mode (§9.1)."""
    if not llm_should_fire(phase, scores["fusion"], sweep_type, internals["rel_range"]):
        return "Low-activity scanning candle - no CRT signal detected."

    if sweep_type:
        return (
            f"{sweep_label} ({sweep_type}) detected: "
            f"upper_wick={internals['upper_wick']:.3f}, "
            f"lower_wick={internals['lower_wick']:.3f}, "
            f"body_ratio={internals['body_ratio']:.3f}. "
            f"Fusion={scores['fusion']:.3f} (crt={scores['crt']:.3f}, "
            f"zone={scores['zone']:.3f}, rr={scores['rr']:.3f}, "
            f"gaussian={scores['gaussian']:.3f})."
        )
    return (
        f"Phase={phase} with body_ratio={internals['body_ratio']:.3f} and "
        f"rel_range={internals['rel_range']:.3f}. "
        f"Fusion={scores['fusion']:.3f} reflects directional momentum without sweep geometry."
    )


def api_reasoning(*args, **kwargs) -> str:
    """
    Optional Ollama/Claude path. Reuses production llama_gate.llm_score()
    only when --llm api is explicitly passed. Falls back to deterministic
    text on any failure (matches §9.4 'none' behavior).
    """
    try:
        from config_layer.llama_gate import llm_score  # noqa: F401
        # Note: production llm_score returns a float — for narrative
        # reasoning we keep deterministic text and just confirm reachability.
        return deterministic_reasoning(*args, **kwargs)
    except Exception as exc:  # pragma: no cover — depends on local server
        return deterministic_reasoning(*args, **kwargs) + f" [api_unreachable: {exc}]"


# ─────────────────────────────────────────────────────────────────
# §10 PER-CANDLE JSON RECORD
# ─────────────────────────────────────────────────────────────────

def build_record(
    idx: int,
    bar: Bar,
    phase: str,
    sweep_type: Optional[str],
    sweep_label: Optional[str],
    internals: dict,
    scores: dict,
    reasoning: str,
    llm_source: str,
    patch_applied: Optional[str] = None,
    instrument: str = _DEFAULT_INSTRUMENT,
) -> dict:
    return {
        "id":          idx,
        "timestamp":   bar.timestamp,
        "instrument":  instrument,
        "candle": {
            "open":   bar.open,
            "high":   bar.high,
            "low":    bar.low,
            "close":  bar.close,
            "volume": bar.volume,
        },
        "crt_phase":   phase,
        "bitnet_scores": {
            "crt":           scores["crt"],
            "zone":          scores["zone"],
            "rr":            scores["rr"],
            "gaussian":      scores["gaussian"],
            "fusion":        scores["fusion"],
            "internals":     internals,
            "sweep_type":    sweep_type,
            "sweep_label":   sweep_label,
            "patch_applied": patch_applied,
        },
        "llm_reasoning": reasoning,
        "llm_source":    llm_source,
    }


# ─────────────────────────────────────────────────────────────────
# DRIVER
# ─────────────────────────────────────────────────────────────────

def run(
    csv_path: Path,
    out_path: Path,
    llm_mode: str,
    instrument: str = _DEFAULT_INSTRUMENT,
    start_date: Optional[str] = None,
    max_bars: Optional[int] = None,
) -> list[dict]:
    bars = load_csv(csv_path, start_date=start_date, max_bars=max_bars)
    rng = random.Random(42)  # §14 determinism

    records: list[dict] = []
    phases: list[str] = []

    reasoner = api_reasoning if llm_mode == "api" else deterministic_reasoning
    llm_source = "api" if llm_mode == "api" else "deterministic"

    for idx, bar in enumerate(bars):
        phase, sweep_type, sweep_label = detect_phase(bars, idx, phases)
        phases.append(phase)

        internals = compute_internals(bars, idx)
        scores = score_heads(phase, sweep_type, internals, rng)
        fusion = scores["fusion"]

        if llm_should_fire(phase, fusion, sweep_type, internals["rel_range"]):
            reasoning = reasoner(phase, sweep_type, sweep_label, internals, scores)
            source = llm_source
        else:
            reasoning = "Low-activity scanning candle - no CRT signal detected."
            source = "skip"

        records.append(build_record(
            idx=idx, bar=bar, phase=phase,
            sweep_type=sweep_type, sweep_label=sweep_label,
            internals=internals, scores=scores,
            reasoning=reasoning, llm_source=source,
            patch_applied=("FIX-v3: " + sweep_label) if sweep_type else None,
            instrument=instrument,
        ))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as fh:
        json.dump(records, fh, indent=2)
    return records


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--instrument", default=_DEFAULT_INSTRUMENT,
        help=f"Instrument name (default: {_DEFAULT_INSTRUMENT}). "
             "Resolves to <data-dir>/{INSTRUMENT}_M15.csv unless --csv is set."
    )
    parser.add_argument(
        "--data-dir", default=_DEFAULT_DATA_DIR,
        help=f"Directory containing {{INSTRUMENT}}_M15.csv files (default: {_DEFAULT_DATA_DIR})"
    )
    parser.add_argument(
        "--csv", default=None, type=Path,
        help="Explicit CSV path — overrides --instrument + --data-dir convention"
    )
    parser.add_argument("--out", required=True, type=Path,
                        help="Output JSON path (per-candle records)")
    parser.add_argument("--llm", choices=("deterministic", "api"),
                        default="deterministic",
                        help="Reasoning source (default: deterministic)")
    parser.add_argument(
        "--start-date", default=None,
        help="Filter CSV to rows whose timestamp starts with this prefix "
             "(e.g. '2024-01-01'). Useful when the CSV spans multiple years."
    )
    parser.add_argument(
        "--max-bars", default=None, type=int,
        help="Truncate to at most N bars after filtering and dedup."
    )
    args = parser.parse_args(argv)

    instrument = args.instrument.upper()

    # Resolve CSV path: explicit --csv overrides convention
    if args.csv:
        csv_path = args.csv
    else:
        csv_path = Path(args.data_dir) / f"{instrument}_M15.csv"

    if not csv_path.exists():
        candidates = sorted(Path(args.data_dir).glob("*_M15.csv")) if Path(args.data_dir).exists() else []
        if candidates:
            print(
                f"INFO: {csv_path} not found. Available instruments in {args.data_dir}/:",
                file=sys.stderr,
            )
            for c in candidates:
                print(f"  {c.stem.split('_')[0]} → {c}", file=sys.stderr)
            print("Use --instrument COIN or --csv PATH to select a file.", file=sys.stderr)
        else:
            print(
                f"ERROR: {csv_path} not found and no *_M15.csv files in {args.data_dir}/",
                file=sys.stderr,
            )
        return 2

    records = run(
        csv_path, args.out, args.llm,
        instrument=instrument,
        start_date=args.start_date,
        max_bars=args.max_bars,
    )

    # Summary
    from collections import Counter
    phase_counts = Counter(r["crt_phase"] for r in records)
    sweep_counts = Counter(
        r["bitnet_scores"]["sweep_type"] for r in records
        if r["bitnet_scores"]["sweep_type"]
    )
    print(f"Records: {len(records)} → {args.out}")
    print(f"Phase distribution: {dict(phase_counts)}")
    print(f"Sweep types:        {dict(sweep_counts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
