"""
Lead/lag event study: CRT DISPLACEMENT starts vs zone assignments.

For each bar where CRT state first enters DISPLACEMENT:
  - window [t-H, t+H] of best_zone_id (default H=10)
  - occupancy of rare geometry zones {zone_1, zone_4, zone_5, zone_6}
  - timing of transitions *into* those zones relative to t=0

Research-only. No admission authority.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from research.zone_mapping.crt_zone_crosstab import (
    BarJointLabel,
    collect_crt_zone_joint_labels,
)

RARE_ZONES = ("zone_1", "zone_4", "zone_5", "zone_6")
DEFAULT_HALF_WINDOW = 10


@dataclass(frozen=True)
class DisplacementEvent:
    t0_index: int  # index into joint labels
    timestamp: str
    candle_index: int


def find_displacement_starts(labels: Sequence[BarJointLabel]) -> list[DisplacementEvent]:
    """Indices of first bar of each DISPLACEMENT run."""
    events: list[DisplacementEvent] = []
    prev = None
    for i, lab in enumerate(labels):
        if lab.crt_state == "DISPLACEMENT" and prev != "DISPLACEMENT":
            events.append(
                DisplacementEvent(
                    t0_index=i,
                    timestamp=lab.timestamp,
                    candle_index=lab.candle_index,
                )
            )
        prev = lab.crt_state
    return events


def _zone_at(labels: Sequence[BarJointLabel], i: int) -> Optional[str]:
    if 0 <= i < len(labels):
        return labels[i].zone_id
    return None


def compute_displacement_zone_event_study(
    labels: Sequence[BarJointLabel],
    *,
    half_window: int = DEFAULT_HALF_WINDOW,
    rare_zones: Sequence[str] = RARE_ZONES,
) -> dict[str, Any]:
    """
    Align DISPLACEMENT starts; summarize zone path in [−H, +H].

    Returns occupancy by lag, rare-zone rates, and entry-timing of rare zones.
    """
    H = int(half_window)
    rare = tuple(rare_zones)
    events = find_displacement_starts(labels)
    lags = list(range(-H, H + 1))

    # Per-lag zone counts (over events with defined bar at that lag)
    zone_at_lag: dict[int, Counter] = {tau: Counter() for tau in lags}
    n_defined_at_lag: Counter = Counter()
    rare_hits_at_lag: Counter = Counter()  # events with zone in rare at lag

    # First transition into each rare zone within window, relative lag
    # (only counting first entry into that zone in the window, if any)
    first_entry_lag: dict[str, list[int]] = {z: [] for z in rare}
    any_rare_entry_lags: list[int] = []  # first rare-zone entry among any of rare

    # Also: lag of zone transition INTO rare that is nearest to 0 (signed)
    entry_events_all: list[dict[str, Any]] = []

    for ev in events:
        t0 = ev.t0_index
        # path for this event
        path: dict[int, Optional[str]] = {}
        for tau in lags:
            z = _zone_at(labels, t0 + tau)
            path[tau] = z
            if z is not None:
                n_defined_at_lag[tau] += 1
                zone_at_lag[tau][z] += 1
                if z in rare:
                    rare_hits_at_lag[tau] += 1

        # transitions into rare zones within window
        first_rare_tau: Optional[int] = None
        seen_entry: set[str] = set()
        for tau in lags:
            i = t0 + tau
            if i <= 0 or i >= len(labels):
                continue
            z_now = labels[i].zone_id
            z_prev = labels[i - 1].zone_id
            if z_now in rare and z_now != z_prev:
                entry_events_all.append(
                    {
                        "event_ts": ev.timestamp,
                        "lag": tau,
                        "zone_entered": z_now,
                        "zone_from": z_prev,
                        "crt_state_at_entry": labels[i].crt_state,
                    }
                )
                if z_now not in seen_entry:
                    first_entry_lag[z_now].append(tau)
                    seen_entry.add(z_now)
                if first_rare_tau is None:
                    first_rare_tau = tau
        if first_rare_tau is not None:
            any_rare_entry_lags.append(first_rare_tau)

    n_ev = len(events)
    # P(zone | lag) and rare rate
    lag_profiles: dict[str, Any] = {}
    for tau in lags:
        n_def = int(n_defined_at_lag[tau])
        counts = zone_at_lag[tau]
        lag_profiles[str(tau)] = {
            "n_events_defined": n_def,
            "zone_counts": dict(counts),
            "p_zone": {
                z: (float(counts[z]) / n_def if n_def > 0 else 0.0) for z in counts
            },
            "rare_zone_rate": (
                float(rare_hits_at_lag[tau]) / n_def if n_def > 0 else 0.0
            ),
            "p_zone_1": float(counts.get("zone_1", 0)) / n_def if n_def else 0.0,
            "p_zone_4": float(counts.get("zone_4", 0)) / n_def if n_def else 0.0,
            "p_zone_5": float(counts.get("zone_5", 0)) / n_def if n_def else 0.0,
            "p_zone_6": float(counts.get("zone_6", 0)) / n_def if n_def else 0.0,
            "p_rare_union": (
                float(rare_hits_at_lag[tau]) / n_def if n_def > 0 else 0.0
            ),
        }

    def _hist(lags_list: list[int]) -> dict[str, int]:
        c = Counter(lags_list)
        return {str(tau): int(c.get(tau, 0)) for tau in lags}

    def _summary(lags_list: list[int]) -> dict[str, Any]:
        if not lags_list:
            return {
                "n": 0,
                "mean_lag": None,
                "median_lag": None,
                "frac_before": None,
                "frac_at_0": None,
                "frac_after": None,
            }
        srt = sorted(lags_list)
        mid = srt[len(srt) // 2]
        n = len(lags_list)
        return {
            "n": n,
            "mean_lag": float(sum(lags_list) / n),
            "median_lag": float(mid),
            "frac_before": sum(1 for x in lags_list if x < 0) / n,
            "frac_at_0": sum(1 for x in lags_list if x == 0) / n,
            "frac_after": sum(1 for x in lags_list if x > 0) / n,
            "histogram": _hist(lags_list),
        }

    entry_timing = {
        z: {
            "first_entry_lags": first_entry_lag[z],
            **_summary(first_entry_lag[z]),
        }
        for z in rare
    }
    entry_timing["any_rare"] = {
        "first_entry_lags": any_rare_entry_lags,
        **_summary(any_rare_entry_lags),
    }

    # Baseline rare rate on full label stream (for comparison)
    n_all = len(labels)
    baseline_rare = (
        sum(1 for lab in labels if lab.zone_id in rare) / n_all if n_all else 0.0
    )

    return {
        "schema_version": "displacement_zone_event_study_v1",
        "half_window": H,
        "rare_zones": list(rare),
        "n_displacement_starts": n_ev,
        "n_joint_bars": n_all,
        "baseline_rare_zone_rate": baseline_rare,
        "lags": lags,
        "lag_profiles": lag_profiles,
        "rare_entry_timing": entry_timing,
        "n_rare_zone_entry_events_in_windows": len(entry_events_all),
        "events_sample": [
            {"timestamp": e.timestamp, "candle_index": e.candle_index}
            for e in events[:20]
        ],
    }


def event_study_to_markdown(es: Mapping[str, Any], *, title: str = "") -> str:
    H = int(es.get("half_window", 10))
    rare = es.get("rare_zones") or list(RARE_ZONES)
    lags = es.get("lags") or list(range(-H, H + 1))
    prof = es.get("lag_profiles") or {}
    lines = [
        title or "# DISPLACEMENT lead/lag × rare zones",
        "",
        f"**DISPLACEMENT starts:** {es.get('n_displacement_starts')}  ·  "
        f"**Window:** [{ -H}, +{H}]  ·  "
        f"**Rare zones:** {', '.join(rare)}",
        "",
        f"**Baseline rare-zone rate (all bars):** {100 * float(es.get('baseline_rare_zone_rate') or 0):.2f}%",
        "",
        "## Rare-zone occupancy by lag (relative to DISPLACEMENT start t=0)",
        "",
        "| lag | n | P(rare) | P(z1) | P(z4) | P(z5) | P(z6) |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for tau in lags:
        r = prof.get(str(tau)) or {}
        lines.append(
            "| {tau:+d} | {n} | {pr:.3f} | {p1:.3f} | {p4:.3f} | {p5:.3f} | {p6:.3f} |".format(
                tau=int(tau),
                n=r.get("n_events_defined", 0),
                pr=float(r.get("p_rare_union") or 0.0),
                p1=float(r.get("p_zone_1") or 0.0),
                p4=float(r.get("p_zone_4") or 0.0),
                p5=float(r.get("p_zone_5") or 0.0),
                p6=float(r.get("p_zone_6") or 0.0),
            )
        )

    lines.extend(
        [
            "",
            "## Timing of first transition *into* rare zones (within window)",
            "",
            "Lag of first entry into each rare zone after aligning DISPLACEMENT starts "
            "(negative = before CRT transition, 0 = same bar, positive = after).",
            "",
            "| Zone | n_events_with_entry | mean_lag | median_lag | P(before) | P(at 0) | P(after) |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    timing = es.get("rare_entry_timing") or {}
    for key in list(rare) + ["any_rare"]:
        t = timing.get(key) or {}
        if not t.get("n"):
            lines.append(f"| {key} | 0 | — | — | — | — | — |")
            continue
        lines.append(
            "| {k} | {n} | {mn:.2f} | {md:.1f} | {fb:.3f} | {f0:.3f} | {fa:.3f} |".format(
                k=key,
                n=t["n"],
                mn=float(t["mean_lag"]),
                md=float(t["median_lag"]),
                fb=float(t["frac_before"]),
                f0=float(t["frac_at_0"]),
                fa=float(t["frac_after"]),
            )
        )

    # Histograms for any_rare and each zone
    lines.extend(["", "## Entry lag histograms (counts)", ""])
    for key in list(rare) + ["any_rare"]:
        t = timing.get(key) or {}
        hist = t.get("histogram") or {}
        if not t.get("n"):
            continue
        lines.append(f"### {key} (n={t['n']})")
        lines.append("")
        lines.append("| lag | count |")
        lines.append("|---:|---:|")
        for tau in lags:
            c = int(hist.get(str(tau), 0))
            if c:
                lines.append(f"| {int(tau):+d} | {c} |")
        lines.append("")

    lines.append("")
    return "\n".join(lines)


def run_study_from_csv(
    csv_path: str,
    *,
    instrument: str = "XAUUSD",
    half_window: int = DEFAULT_HALF_WINDOW,
) -> tuple[dict[str, Any], list[BarJointLabel]]:
    labels = collect_crt_zone_joint_labels(csv_path, instrument=instrument)
    es = compute_displacement_zone_event_study(labels, half_window=half_window)
    es["meta"] = {
        "csv_path": csv_path,
        "instrument": instrument,
        "half_window": half_window,
        "n_labels": len(labels),
    }
    return es, labels
