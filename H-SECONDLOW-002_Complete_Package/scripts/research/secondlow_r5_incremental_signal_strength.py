#!/usr/bin/env python3
"""R5 family incremental signal strength — count-only under H-SECONDLOW-006."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO / "src") not in sys.path:
    sys.path.insert(0, str(_REPO / "src"))

from research.secondlow_v1.corpus import CANONICAL_XAUUSD_M15
from research.secondlow_v1.detector import (
    DISCOVERY_END,
    detect_independent_events,
    load_ohlcv,
    sha256_prefix,
)
from research.secondlow_v1.regime_metrics import regime_metrics_at_purge

PRE_THRESHOLD = -1.5
DEPTH_THRESHOLDS = [0.6, 0.7, 0.8, 0.9, 1.0]
MARGINAL_BAND = 0.1
HIGH_VOL_RATIO = 1.2
N_BOOT = 5000
SEED = 42
LEDGER = _REPO / "data/secondlow_prospective_events.jsonl"
OUTPUT = _REPO / "H-SECONDLOW-002_Complete_Package/results/r5_incremental_signal_strength"


def assign_session(ts: pd.Timestamp) -> str:
    h = ts.hour
    if 0 <= h < 7:
        return "ASIA"
    if 7 <= h < 12:
        return "LONDON"
    if 12 <= h < 16:
        return "OVERLAP"
    if 16 <= h < 21:
        return "NY"
    return "LATE"


def r5_exposed(depth: float, pre_2h: float, depth_x: float) -> bool:
    return depth >= depth_x or pre_2h <= PRE_THRESHOLD


def bootstrap_ci(
    values: np.ndarray,
    *,
    n_boot: int = N_BOOT,
    seed: int = SEED,
) -> dict | None:
    if len(values) == 0:
        return None
    rng = np.random.default_rng(seed)
    samples = np.empty(n_boot)
    for i in range(n_boot):
        draw = rng.choice(values, size=len(values), replace=True)
        samples[i] = float(np.mean(draw))
    return {
        "low": float(np.percentile(samples, 2.5)),
        "high": float(np.percentile(samples, 97.5)),
        "n_boot": n_boot,
        "seed": seed,
    }


def bootstrap_prop_ci(flags: np.ndarray, *, n_boot: int = N_BOOT, seed: int = SEED) -> dict | None:
    if len(flags) == 0:
        return None
    rng = np.random.default_rng(seed)
    samples = np.empty(n_boot)
    for i in range(n_boot):
        draw = rng.choice(flags, size=len(flags), replace=True)
        samples[i] = float(np.mean(draw))
    return {
        "low": float(np.percentile(samples, 2.5)),
        "high": float(np.percentile(samples, 97.5)),
        "n_boot": n_boot,
        "seed": seed,
    }


def build_event_table(df: pd.DataFrame, events: list) -> pd.DataFrame:
    rows = []
    for e in events:
        pos = df.index.get_loc(e.purge_time)
        reg = regime_metrics_at_purge(df, pos)
        ratio = float(reg.atr_ratio_14_over_100) if reg else float("nan")
        rows.append(
            {
                "purge_time": e.purge_time,
                "purge_depth_atr": float(e.purge_depth_atr),
                "pre_2h_return_atr": float(e.pre_2h_return_atr),
                "session": assign_session(e.purge_time),
                "atr_ratio_14_over_100": ratio,
                "high_vol": bool(ratio > HIGH_VOL_RATIO) if np.isfinite(ratio) else False,
                "post_discovery": bool(e.purge_time > DISCOVERY_END),
            }
        )
    return pd.DataFrame(rows)


def exposed_set(table: pd.DataFrame, depth_x: float) -> set[pd.Timestamp]:
    mask = table.apply(
        lambda r: r5_exposed(r["purge_depth_atr"], r["pre_2h_return_atr"], depth_x),
        axis=1,
    )
    return set(table.loc[mask, "purge_time"])


def incremental_set(table: pd.DataFrame, depth_x: float, depth_stricter: float | None) -> pd.DataFrame:
    at_x = table[
        table.apply(lambda r: r5_exposed(r["purge_depth_atr"], r["pre_2h_return_atr"], depth_x), axis=1)
    ]
    if depth_stricter is None:
        return at_x
    keep = []
    for _, r in at_x.iterrows():
        if not r5_exposed(r["purge_depth_atr"], r["pre_2h_return_atr"], depth_stricter):
            keep.append(True)
        else:
            keep.append(False)
    return at_x.loc[keep]


def qualify_leg(row: pd.Series, depth_x: float) -> str:
    depth_ok = row["purge_depth_atr"] >= depth_x
    pre_ok = row["pre_2h_return_atr"] <= PRE_THRESHOLD
    if depth_ok and pre_ok:
        return "both"
    if depth_ok:
        return "depth_only"
    if pre_ok:
        return "pre_only"
    return "neither"


def summarize_incremental(inc: pd.DataFrame, depth_x: float) -> dict:
    if inc.empty:
        return {
            "n_incremental": 0,
            "mean_depth": None,
            "mean_depth_ci_95": None,
            "median_depth": None,
            "depth_percentiles": None,
            "mean_pre_or_leg": None,
            "mean_pre_or_leg_ci_95": None,
            "n_pre_or_leg_only": 0,
            "mean_regime_ratio": None,
            "mean_regime_ratio_ci_95": None,
            "pct_high_vol": None,
            "pct_high_vol_ci_95": None,
            "pct_marginal_depth": None,
            "pct_marginal_depth_ci_95": None,
            "session_counts": {},
            "qualify_leg_counts": {},
        }

    depths = inc["purge_depth_atr"].to_numpy(dtype=float)
    ratios = inc["atr_ratio_14_over_100"].replace([np.inf, -np.inf], np.nan).dropna().to_numpy(dtype=float)
    pre_or = inc[inc.apply(lambda r: qualify_leg(r, depth_x) in {"pre_only", "both"}, axis=1)]
    pre_vals = pre_or["pre_2h_return_atr"].to_numpy(dtype=float) if len(pre_or) else np.array([])
    pre_only_n = int((inc.apply(lambda r: qualify_leg(r, depth_x) == "pre_only", axis=1)).sum())

    marginal_flags = np.array(
        [
            (r["purge_depth_atr"] >= depth_x) and (r["purge_depth_atr"] - depth_x <= MARGINAL_BAND)
            for _, r in inc.iterrows()
        ],
        dtype=bool,
    )
    high_vol_flags = inc["high_vol"].to_numpy(dtype=bool) if "high_vol" in inc else np.array([])

    leg_counts = inc.apply(lambda r: qualify_leg(r, depth_x), axis=1).value_counts().to_dict()
    session_counts = inc["session"].value_counts().to_dict()

    return {
        "n_incremental": int(len(inc)),
        "mean_depth": round(float(np.mean(depths)), 4),
        "mean_depth_ci_95": bootstrap_ci(depths),
        "median_depth": round(float(np.median(depths)), 4),
        "depth_percentiles": {
            "p10": round(float(np.percentile(depths, 10)), 4),
            "p25": round(float(np.percentile(depths, 25)), 4),
            "p75": round(float(np.percentile(depths, 75)), 4),
            "p90": round(float(np.percentile(depths, 90)), 4),
        },
        "mean_pre_or_leg": round(float(np.mean(pre_vals)), 4) if len(pre_vals) else None,
        "mean_pre_or_leg_ci_95": bootstrap_ci(pre_vals) if len(pre_vals) else None,
        "n_pre_or_leg_only": pre_only_n,
        "mean_regime_ratio": round(float(np.mean(ratios)), 4) if len(ratios) else None,
        "mean_regime_ratio_ci_95": bootstrap_ci(ratios) if len(ratios) else None,
        "pct_high_vol": round(float(np.mean(high_vol_flags)), 4) if len(high_vol_flags) else None,
        "pct_high_vol_ci_95": bootstrap_prop_ci(high_vol_flags) if len(high_vol_flags) else None,
        "pct_marginal_depth": round(float(np.mean(marginal_flags)), 4),
        "pct_marginal_depth_ci_95": bootstrap_prop_ci(marginal_flags),
        "session_counts": {str(k): int(v) for k, v in session_counts.items()},
        "qualify_leg_counts": {str(k): int(v) for k, v in leg_counts.items()},
        "incremental_events": [
            {
                "purge_time": str(r["purge_time"]),
                "purge_depth_atr": round(r["purge_depth_atr"], 4),
                "pre_2h_return_atr": round(r["pre_2h_return_atr"], 4),
                "qualify_leg": qualify_leg(r, depth_x),
                "marginal_depth": bool(
                    r["purge_depth_atr"] >= depth_x and r["purge_depth_atr"] - depth_x <= MARGINAL_BAND
                ),
                "session": r["session"],
                "atr_ratio_14_over_100": round(r["atr_ratio_14_over_100"], 4)
                if np.isfinite(r["atr_ratio_14_over_100"])
                else None,
            }
            for _, r in inc.iterrows()
        ],
    }


def analyze_cohort(table: pd.DataFrame, cohort_name: str) -> dict:
    v02_depth_only = int((table["purge_depth_atr"] >= 1.0).sum())
    rows = []
    sorted_th = sorted(DEPTH_THRESHOLDS)
    for i, depth_x in enumerate(sorted_th):
        # Incremental band = events gained relaxing from the next *stricter* threshold down to X.
        stricter = sorted_th[i + 1] if i + 1 < len(sorted_th) else None
        total_mask = table.apply(
            lambda r: r5_exposed(r["purge_depth_atr"], r["pre_2h_return_atr"], depth_x),
            axis=1,
        )
        n_total = int(total_mask.sum())
        if stricter is not None:
            inc_df = incremental_set(table, depth_x, stricter)
            inc_summary = summarize_incremental(inc_df, depth_x)
            inc_label = f"relax_{stricter}_to_{depth_x}"
        else:
            inc_summary = summarize_incremental(pd.DataFrame(), depth_x)
            inc_summary["note"] = "strictest_grid_tier — no incremental band above 1.0"
            inc_label = "strictest_reference"
        rows.append(
            {
                "depth_threshold": depth_x,
                "rule": f"depth >= {depth_x} OR pre_2h <= {PRE_THRESHOLD}",
                "total_r5_exposed": n_total,
                "delta_total_vs_v02_depth_only": n_total - v02_depth_only,
                "stricter_threshold": stricter,
                "incremental_band": inc_label,
                "incremental_vs_stricter": inc_summary,
            }
        )

    return {
        "cohort": cohort_name,
        "n_events": int(len(table)),
        "v02_depth_only_exposed": v02_depth_only,
        "thresholds": rows,
    }


def main() -> None:
    corpus = _REPO / CANONICAL_XAUUSD_M15
    df = load_ohlcv(corpus)
    _, events = detect_independent_events(df, require_post_window=False)
    full_table = build_event_table(df, events)

    ledger_times: set[pd.Timestamp] = set()
    if LEDGER.exists():
        for line in LEDGER.read_text(encoding="utf-8").splitlines():
            if line.strip():
                ledger_times.add(pd.Timestamp(json.loads(line)["purge_time"]))
    post_table = full_table[full_table["purge_time"].isin(ledger_times)].copy()
    if len(post_table) != len(ledger_times):
        raise SystemExit(f"Ledger {len(ledger_times)} times, matched {len(post_table)} in detector")

    report = {
        "governance": "COUNT_ONLY_NO_OUTCOMES",
        "hypothesis_framework": "H-SECONDLOW-006 v0.1 APPROVED",
        "r5_rule_template": f"depth >= X OR pre_2h_return_atr <= {PRE_THRESHOLD}",
        "depth_thresholds": DEPTH_THRESHOLDS,
        "incremental_definition": "events qualifying at X but not at next stricter threshold in grid",
        "marginal_band_atr": MARGINAL_BAND,
        "high_vol_ratio_threshold": HIGH_VOL_RATIO,
        "bootstrap": {"n_boot": N_BOOT, "seed": SEED, "method": "percentile"},
        "corpus": str(corpus),
        "corpus_hash_prefix": sha256_prefix(corpus),
        "cohorts": {
            "all_independent": analyze_cohort(full_table, "all_independent_50"),
            "prospective_ledger": analyze_cohort(post_table, "prospective_ledger_14"),
        },
    }

    OUTPUT.mkdir(parents=True, exist_ok=True)
    json_path = OUTPUT / "r5_incremental_signal_strength.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    # Compact summary table for terminal / quick reference
    lines = [
        "# R5 incremental signal strength (count-only)",
        "",
        "## Prospective ledger (14 events)",
        "",
        "| X | Total R5 | Incr | Mean depth (incr) | 95% CI | % marginal | 95% CI | % high vol | pre-only incr |",
        "|---|---:|---:|---:|---|---:|---|---:|---:|",
    ]
    for row in report["cohorts"]["prospective_ledger"]["thresholds"]:
        inc = row["incremental_vs_stricter"]
        ci_d = inc.get("mean_depth_ci_95") or {}
        ci_m = inc.get("pct_marginal_depth_ci_95") or {}
        ci_h = inc.get("pct_high_vol_ci_95") or {}
        d_ci = f"[{ci_d.get('low', '—')}, {ci_d.get('high', '—')}]" if ci_d else "—"
        m_ci = f"[{ci_m.get('low', '—')}, {ci_m.get('high', '—')}]" if ci_m else "—"
        h_pct = inc.get("pct_high_vol")
        h_ci = f"[{ci_h.get('low', '—')}, {ci_h.get('high', '—')}]" if ci_h and h_pct is not None else "—"
        lines.append(
            f"| {row['depth_threshold']} | {row['total_r5_exposed']} | {inc['n_incremental']} | "
            f"{inc.get('mean_depth', '—')} | {d_ci} | "
            f"{inc.get('pct_marginal_depth', '—')} | {m_ci} | "
            f"{h_pct if h_pct is not None else '—'} | {inc.get('n_pre_or_leg_only', 0)} |"
        )
    md_path = OUTPUT / "r5_incremental_signal_strength_summary.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2))
    print(f"\nWrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()