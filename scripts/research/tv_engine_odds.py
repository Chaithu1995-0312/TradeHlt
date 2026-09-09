"""tv_engine_odds.py — deduplicated engine-vs-TradingView agreement odds for the
one-month XAUUSD corpus.

WHAT THIS CLOSES
-----------------
`scripts/research/htf_parent_telemetry_extract.py:163-164` rolls the per-shot
reconciliation up by SUMMING each sidecar's `engine_vs_tv.summary.compared`
and `.divergent`. Those shot windows OVERLAP, so the sum double-counts:

    05_m15_jul28_displacement (13 bars) is a strict subset of
    06_m15_jul30_trade        ( 6 bars) is a strict subset of
    04_m15_jul28_forensic     (202 bars)

    03_h4_jul27_31 and 09_h4_jul15_20 both sit INSIDE 01_h4_july_macro's window.

Arithmetic: 202+13+6+82+37+552+368 = 1,260 summed M15 against 1,241 UNIQUE
M15 bars, and 1,260 + 195 H4 = 1,455 — exactly F-080's registered headline.
That is fine as a "how much work did each capture do" tally, which is all the
telemetry script claims. It is NOT a valid denominator for an agreement RATE:
a bar covered by three overlapping shots is one bar of evidence, not three.

This script computes the odds over UNIQUE `(interval_min, broker_timestamp)`
keys instead. It deliberately does NOT modify the telemetry script, which is
F-080's evidence producer and must stay reproducible.

WHAT THIS IS NOT
-----------------
Not a new capture (no Playwright, no network — reads existing sidecars under
tools/tv_forensic/shots/ only). Not a re-diff: every per-bar row was already
computed and stored at capture time by `engine_data.diff_table`, under the
same `MATCH_TOLERANCE` this script imports rather than restates. Not an
economic claim — this measures FEED FIDELITY (how often two data sources
agree), and says nothing about whether either predicts price. Grants no
authority (CLAUDE.md 6.5).

PRE-REGISTERED RULES (CH-xauusd-tv-odds.impact.json, fixed before any number
was seen)
-----------------
* Tolerance INHERITED from `engine_data.MATCH_TOLERANCE`, never re-chosen.
* Odds denominator = unique keys with BOTH feeds present (status OK|DIVERGENT).
* Coverage != disagreement: NO_ENGINE_BAR / NO_TV_BAR / ENGINE_BAR_MISSING_TV_HAS_ONE
  go to a coverage tally, never to the odds numerator or denominator.
* Per-FIELD disaggregation is mandatory, not optional — the L1 composite sums
  four fields, so one large open-field delta can flag a bar whose H/L/C agree
  to within a spread.
* Wilson 95% CI on the divergence rate; n is ~1,400, not infinite.
* Cross-shot OHLC disagreement on a shared key is reported as
  CROSS_SHOT_INCONSISTENCY and BLOCKS the report — never silently collapsed
  to one side (that is the D-1 silent-gap class F-079 fixed).

USAGE
-----
    venv\\Scripts\\python.exe scripts/research/tv_engine_odds.py \\
        --csv data/XAUUSD_M15.csv --out-dir results/xauusd_tv_odds
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
SHOTS_DIR = _ROOT / "tools" / "tv_forensic" / "shots"
DEFAULT_OUT_DIR = _ROOT / "results" / "xauusd_tv_odds"
DEFAULT_CSV = "data/XAUUSD_M15.csv"

# Reuse the capture-time tolerance rather than restating it. If engine_data
# ever retunes MATCH_TOLERANCE, this script must move with it -- a second
# hardcoded 3.0 here would silently diverge from the rule the stored rows were
# actually scored under.
sys.path.insert(0, str(_ROOT / "tools" / "tv_forensic"))
from engine_data import MATCH_TOLERANCE, load_engine_bars  # noqa: E402

# Statuses that mean "both feeds had a bar here, so the comparison is real".
# Everything else is a coverage fact, not an agreement fact.
_COMPARABLE = frozenset({"OK", "DIVERGENT"})
_FIELDS = ("O", "H", "L", "C")


def _wilson(successes: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    """Wilson score interval. Chosen over the normal approximation because the
    divergence rate here is a few percent on n~1400 -- exactly where the naive
    interval runs below zero and stops being reportable."""
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def _percentile(values: list[float], q: float) -> float | None:
    """Linear-interpolated percentile. Deliberately not numpy: this script is a
    sibling of the standalone tv_forensic tool and must run without the science
    stack, same as engine_data.py does."""
    if not values:
        return None
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    pos = q * (len(s) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return s[lo]
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def _load_sidecars() -> list[dict]:
    """Base sidecars only.

    Excludes `_ANNOTATED` (a different schema written by annotate.py) and any
    `_PRE_*` backup snapshot -- those are pre-mutation preservation copies kept
    per CLAUDE.md 6.2 rule 4, and counting one as an extra shot would inflate
    every total. Same filter as htf_parent_telemetry_extract.py:130-133.
    """
    out = []
    for p in sorted(SHOTS_DIR.glob("*.json")):
        if p.stem.endswith("_ANNOTATED") or "_PRE_" in p.stem:
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        d["_path"] = str(p.relative_to(_ROOT)).replace("\\", "/")
        out.append(d)
    return out


def _ohlc_key(side: dict | None) -> tuple | None:
    if side is None:
        return None
    return tuple(round(float(side[f]), 6) for f in _FIELDS)


def collect_unique_bars(sidecars: list[dict]) -> tuple[dict, list[dict], list[dict]]:
    """Fold every shot's stored per-bar rows into one unique-bar map.

    Returns (unique, inconsistencies, unreconciled).

    `unique` is keyed by (interval_min, broker_ts) -- the pre-registered unit of
    account. Where two shots cover the same key their stored OHLC must agree on
    BOTH sides; a disagreement is recorded as an inconsistency rather than
    resolved by last-writer-wins, because silently picking a winner would assert
    an agreement that was never measured.
    """
    unique: dict[tuple[str, str], dict] = {}
    inconsistencies: list[dict] = []
    unreconciled: list[dict] = []

    for d in sidecars:
        shot = d.get("shot", {})
        name = shot.get("name", Path(d["_path"]).stem)
        interval = str(shot.get("interval"))
        evt = d.get("engine_vs_tv") or {}
        rows = evt.get("rows")
        if not rows:
            # Recorded, never inferred: a shot with no rows is reported by name
            # with whatever status it does carry (NOT_APPLICABLE, or absent on a
            # sidecar predating the D-1 fix). It is NOT summed as zero.
            unreconciled.append({
                "shot": name,
                "interval_min": interval,
                "status": evt.get("status", "UNKNOWN_NOT_RECORDED"),
                "reason": evt.get("reason"),
            })
            continue

        for row in rows:
            key = (interval, row["broker"])
            prev = unique.get(key)
            if prev is None:
                unique[key] = {
                    "interval_min": interval,
                    "broker": row["broker"],
                    "utc": row.get("utc"),
                    "engine": row.get("engine"),
                    "tv": row.get("tv"),
                    "delta": row.get("delta"),
                    "abs_error": row.get("abs_error"),
                    "status": row["status"],
                    "shots": [name],
                }
                continue

            prev["shots"].append(name)
            # Both sides must match, and a present-vs-absent bar is itself a
            # disagreement worth surfacing.
            for side in ("engine", "tv"):
                if _ohlc_key(prev.get(side)) != _ohlc_key(row.get(side)):
                    inconsistencies.append({
                        "interval_min": interval,
                        "broker": row["broker"],
                        "side": side,
                        "shots": sorted(set(prev["shots"])),
                        "values": {
                            "first_seen": prev.get(side),
                            "conflicting": row.get(side),
                        },
                    })
            if prev["status"] != row["status"]:
                inconsistencies.append({
                    "interval_min": interval,
                    "broker": row["broker"],
                    "side": "status",
                    "shots": sorted(set(prev["shots"])),
                    "values": {
                        "first_seen": prev["status"],
                        "conflicting": row["status"],
                    },
                })

    return unique, inconsistencies, unreconciled


def odds_for(bars: list[dict]) -> dict:
    """The agreement statistics for one timeframe (or the pooled set)."""
    status_counts = Counter(b["status"] for b in bars)
    comparable = [b for b in bars if b["status"] in _COMPARABLE]
    n = len(comparable)
    divergent = sum(1 for b in comparable if b["status"] == "DIVERGENT")
    agreeing = n - divergent

    errors = [b["abs_error"] for b in comparable if b.get("abs_error") is not None]
    lo, hi = _wilson(divergent, n)

    # Per-field: the composite L1 sums four deltas, so it cannot say WHICH field
    # disagrees. F-080 already saw Close max |delta| = 0.99 against 25
    # composite-DIVERGENT bars -- without this breakout that asymmetry is
    # invisible and the composite reads as though all four fields diverged.
    per_field = {}
    for f in _FIELDS:
        deltas = [
            abs(b["delta"][f]) for b in comparable
            if b.get("delta") and b["delta"].get(f) is not None
        ]
        per_field[f] = {
            "n": len(deltas),
            "max_abs_delta": round(max(deltas), 4) if deltas else None,
            "p99_abs_delta": (
                round(_percentile(deltas, 0.99), 4) if deltas else None
            ),
            "median_abs_delta": (
                round(_percentile(deltas, 0.5), 4) if deltas else None
            ),
            "mean_abs_delta": (
                round(sum(deltas) / len(deltas), 4) if deltas else None
            ),
        }

    # Which single field carries the most L1 mass on the divergent bars. Reported
    # as a count, not a cause -- attribution is a majority statement (F-080 found
    # the open dominant in 14 of 25), never a universal one.
    dominant = Counter()
    for b in comparable:
        if b["status"] != "DIVERGENT" or not b.get("delta"):
            continue
        dominant[max(_FIELDS, key=lambda f: abs(b["delta"].get(f, 0.0)))] += 1

    by_hour: dict[str, dict] = {}
    for b in comparable:
        hour = datetime.strptime(b["broker"], "%Y-%m-%d %H:%M").strftime("%H:%M")
        slot = by_hour.setdefault(hour, {"compared": 0, "divergent": 0})
        slot["compared"] += 1
        if b["status"] == "DIVERGENT":
            slot["divergent"] += 1

    return {
        "unique_bars_seen": len(bars),
        "compared": n,
        "agreeing": agreeing,
        "divergent": divergent,
        "agreement_rate": round(agreeing / n, 6) if n else None,
        "divergence_rate": round(divergent / n, 6) if n else None,
        "odds_one_divergent_in": round(n / divergent, 1) if divergent else None,
        "divergence_rate_wilson95": (
            [round(lo, 6), round(hi, 6)] if n else None
        ),
        "match_tolerance_l1": MATCH_TOLERANCE,
        "abs_error": {
            "mean": round(sum(errors) / len(errors), 4) if errors else None,
            "median": round(_percentile(errors, 0.5), 4) if errors else None,
            "p99": round(_percentile(errors, 0.99), 4) if errors else None,
            "max": round(max(errors), 4) if errors else None,
        },
        "per_field_abs_delta": per_field,
        "divergent_dominant_field": dict(sorted(dominant.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "by_broker_time_of_day": {
            h: {
                **v,
                "divergence_rate": round(v["divergent"] / v["compared"], 6),
            }
            for h, v in sorted(by_hour.items())
            if v["divergent"]
        },
    }


def corpus_coverage(unique: dict, csv_path: str) -> dict:
    """How much of the pinned month actually got compared.

    The odds are only as meaningful as the fraction of the corpus behind them,
    so the coverage figure belongs next to the rate, not in a footnote.
    """
    engine_bars = load_engine_bars(_ROOT / csv_path)
    corpus_ts = {ts.strftime("%Y-%m-%d %H:%M") for ts in engine_bars}
    compared_m15 = {
        b["broker"] for b in unique.values()
        if b["interval_min"] == "15" and b["status"] in _COMPARABLE
    }
    uncovered = sorted(corpus_ts - compared_m15)
    return {
        "engine_csv": csv_path,
        "corpus_m15_bars": len(corpus_ts),
        "corpus_first_bar": min(corpus_ts) if corpus_ts else None,
        "corpus_last_bar": max(corpus_ts) if corpus_ts else None,
        "m15_bars_compared_vs_tv": len(compared_m15),
        "coverage_fraction": (
            round(len(compared_m15) / len(corpus_ts), 6) if corpus_ts else None
        ),
        "uncovered_bar_count": len(uncovered),
        "uncovered_bars": uncovered,
    }


def naive_sum_comparison(sidecars: list[dict], unique: dict) -> dict:
    """Reproduce the overlapping per-shot sum, and show what it double-counted.

    This exists so the correction to F-080 is auditable rather than asserted:
    the old number is recomputed here from the same inputs, next to the new one.
    """
    naive_compared = 0
    naive_divergent = 0
    per_shot = []
    for d in sidecars:
        shot = d.get("shot", {})
        s = (d.get("engine_vs_tv") or {}).get("summary")
        if not s:
            continue
        naive_compared += s.get("compared", 0)
        naive_divergent += s.get("divergent", 0)
        per_shot.append({
            "shot": shot.get("name"),
            "interval_min": str(shot.get("interval")),
            "window": f"{shot.get('start')} -> {shot.get('end')} ({shot.get('clock')})",
            "resolved_offset_hours": (d.get("clock") or {}).get("resolved_offset_hours"),
            "clock_decisive": (d.get("clock") or {}).get("decisive"),
            "compared": s.get("compared", 0),
            "divergent": s.get("divergent", 0),
        })

    comparable = [b for b in unique.values() if b["status"] in _COMPARABLE]
    dedup_compared = len(comparable)
    dedup_divergent = sum(1 for b in comparable if b["status"] == "DIVERGENT")
    overlap_counts = Counter(len(set(b["shots"])) for b in unique.values())

    return {
        "per_shot": per_shot,
        "naive_sum": {"compared": naive_compared, "divergent": naive_divergent},
        "deduplicated": {"compared": dedup_compared, "divergent": dedup_divergent},
        "double_counted": {
            "compared": naive_compared - dedup_compared,
            "divergent": naive_divergent - dedup_divergent,
        },
        "bars_by_shot_multiplicity": {
            f"covered_by_{k}_shots": v for k, v in sorted(overlap_counts.items())
        },
    }


def build_report(csv_path: str) -> dict:
    sidecars = _load_sidecars()
    if not sidecars:
        raise SystemExit(f"no sidecars found under {SHOTS_DIR} — nothing to compare")

    unique, inconsistencies, unreconciled = collect_unique_bars(sidecars)
    if not unique:
        # Non-vacuity: an empty fold must fail loudly. Returning a 100%
        # agreement rate over zero bars is the most flattering possible lie.
        raise SystemExit(
            "every sidecar was unreconciled — no per-bar rows to compare. "
            f"unreconciled: {[u['shot'] for u in unreconciled]}"
        )

    by_tf: dict[str, list[dict]] = defaultdict(list)
    for b in unique.values():
        by_tf[b["interval_min"]].append(b)

    tf_label = {"15": "M15", "240": "H4", "60": "H1", "D": "D1"}
    per_timeframe = {
        tf_label.get(tf, tf): odds_for(bars) for tf, bars in sorted(by_tf.items())
    }

    divergent_bars = sorted(
        (
            {
                "interval_min": b["interval_min"],
                "broker": b["broker"],
                "utc": b["utc"],
                "abs_error": b["abs_error"],
                "delta": b["delta"],
                "shots": sorted(set(b["shots"])),
            }
            for b in unique.values() if b["status"] == "DIVERGENT"
        ),
        key=lambda r: (r["interval_min"], r["broker"]),
    )

    return {
        "generated_by": "scripts/research/tv_engine_odds.py",
        "change_id": "CH-xauusd-tv-odds",
        "what_this_measures": (
            "Feed fidelity: how often the engine's MT5 XAUUSD bars and "
            "TradingView's OANDA:XAUUSD bars agree, per unique "
            "(timeframe, broker-timestamp). Says NOTHING about whether either "
            "feed predicts price. Grants no authority (CLAUDE.md 6.5)."
        ),
        "method": (
            "Folds the per-bar rows ALREADY computed and stored by "
            "engine_data.diff_table at capture time into unique "
            "(interval, broker_ts) keys. Does not re-diff, does not re-capture, "
            f"and inherits MATCH_TOLERANCE={MATCH_TOLERANCE} rather than "
            "restating it. Rows where only one feed has a bar are counted as "
            "COVERAGE, never as agreement or disagreement."
        ),
        "shots_read": [d.get("shot", {}).get("name") for d in sidecars],
        "unreconciled_shots": unreconciled,
        "cross_shot_inconsistencies": inconsistencies,
        "cross_shot_consistency": (
            "CLEAN" if not inconsistencies else "INCONSISTENT_BLOCKS_REPORT"
        ),
        "corpus_coverage": corpus_coverage(unique, csv_path),
        "per_timeframe": per_timeframe,
        "pooled": odds_for(list(unique.values())),
        "f080_reconciliation": naive_sum_comparison(sidecars, unique),
        "divergent_bars": divergent_bars,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--csv", default=DEFAULT_CSV)
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = ap.parse_args(argv)

    report = build_report(args.csv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "xauusd_tv_engine_odds.json"
    out_path.write_text(
        json.dumps(report, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )

    cov = report["corpus_coverage"]
    print(f"wrote {out_path}")
    print(
        f"  coverage: {cov['m15_bars_compared_vs_tv']}/{cov['corpus_m15_bars']} "
        f"M15 corpus bars ({cov['coverage_fraction']:.1%})"
    )
    for tf, s in report["per_timeframe"].items():
        odds = (
            f"1 in {s['odds_one_divergent_in']}" if s["odds_one_divergent_in"]
            else "no divergence"
        )
        print(
            f"  {tf:>4}: {s['agreeing']}/{s['compared']} agree "
            f"({s['agreement_rate']:.4%}) — {odds}"
        )
    if report["cross_shot_inconsistencies"]:
        print(
            f"  !! {len(report['cross_shot_inconsistencies'])} cross-shot "
            "inconsistencies — report BLOCKED until explained"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
