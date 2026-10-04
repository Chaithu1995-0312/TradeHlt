"""
False-alarm characterization for rare-zone → DISPLACEMENT detection.

For a fixed horizon K:
  - Partition signals by entered rare zone (1/4/5/6)
  - Label TP vs FA (DISPLACEMENT start in [t, t+K]?)
  - Follow CRT state path for the next H bars (default 20)
  - Taxonomy of post-signal CRT evolution
  - Compare FA vs TP evolution distributions (overall and per zone)

Research-only.
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
from research.zone_mapping.displacement_zone_event_study import find_displacement_starts
from research.zone_mapping.rare_zone_detection_eval import (
    RARE_ZONES,
    SignalEvent,
    _first_disp_in_window,
    find_zone_entries,
)

DEFAULT_K = 5
DEFAULT_FOLLOW = 20

# Ordered priority for multi-label → primary label (most "advanced" structure first)
_PRIMARY_PRIORITY = (
    "REACHED_EXECUTION",
    "REACHED_RETEST",
    "LATE_DISPLACEMENT",  # DISPLACEMENT after K but within follow window
    "REACHED_EXPANSION_NO_DISP",
    "REACHED_DISPLACEMENT",  # only for TP (within K) — still tracked in path tags
    "RANGE_TO_SWEEP_ONLY",
    "STAYED_SWEEP",
    "STAYED_RANGE",
    "SHADOW_OR_EXPIRED",
    "OTHER_MIXED",
)


@dataclass(frozen=True)
class PathTaxonomy:
    primary: str
    tags: tuple[str, ...]
    state_path: tuple[str, ...]
    unique_states: tuple[str, ...]
    max_structural_depth: int  # ordinal depth of deepest state seen


_STATE_DEPTH = {
    "RANGE": 0,
    "SHADOW_PENDING": 0,
    "SWEEP": 1,
    "DISPLACEMENT": 2,
    "EXPANSION": 3,
    "EXPIRED": 1,
    "RETEST": 4,
    "EXECUTION": 5,
    "RESOLUTION": 3,
}


def extract_crt_path(
    labels: Sequence[BarJointLabel], t: int, follow: int
) -> list[str]:
    """CRT states on bars [t, t+follow] inclusive (capped at stream end)."""
    path: list[str] = []
    hi = min(len(labels) - 1, t + follow)
    for i in range(t, hi + 1):
        path.append(labels[i].crt_state)
    return path


def classify_crt_evolution(
    path: Sequence[str],
    *,
    is_tp: bool,
    K: int,
    disp_starts_set: set[int],
    signal_index: int,
) -> PathTaxonomy:
    """
    Label subsequent CRT evolution after a rare-zone signal.

    Tags are multi-hot; primary is the highest-priority tag that applies.
    """
    if not path:
        return PathTaxonomy("OTHER_MIXED", ("EMPTY_PATH",), tuple(), tuple(), 0)

    states = list(path)
    uniq = []
    for s in states:
        if s not in uniq:
            uniq.append(s)
    uniq_t = tuple(uniq)
    tags: list[str] = []

    has = set(states)
    depth = max(_STATE_DEPTH.get(s, 0) for s in states)

    # Path shape tags
    if has <= {"RANGE"}:
        tags.append("STAYED_RANGE")
    if has <= {"SWEEP"} or (has <= {"RANGE", "SWEEP"} and "SWEEP" in has and "DISPLACEMENT" not in has):
        if "SWEEP" in has and "RANGE" in has:
            tags.append("RANGE_TO_SWEEP_ONLY")
        elif has <= {"SWEEP"}:
            tags.append("STAYED_SWEEP")

    if "DISPLACEMENT" in has:
        tags.append("SAW_DISPLACEMENT")
    if "EXPANSION" in has and "DISPLACEMENT" not in has:
        tags.append("REACHED_EXPANSION_NO_DISP")
    if "EXPANSION" in has and "DISPLACEMENT" in has:
        tags.append("EXPANSION_AFTER_DISP")
    if "RETEST" in has:
        tags.append("REACHED_RETEST")
    if "EXECUTION" in has:
        tags.append("REACHED_EXECUTION")
    if "SHADOW_PENDING" in has or "EXPIRED" in has:
        tags.append("SHADOW_OR_EXPIRED")

    # Transitions present
    for a, b in zip(states, states[1:]):
        if a != b:
            tags.append(f"TRANS_{a}_TO_{b}")

    # Late DISPLACEMENT: start in (t+K, t+follow]
    late = False
    for d in sorted(disp_starts_set):
        if d <= signal_index + K:
            continue
        if d > signal_index + len(states) - 1:
            break
        if signal_index < d <= signal_index + (len(states) - 1):
            late = True
            break
    if late and not is_tp:
        tags.append("LATE_DISPLACEMENT")
    if is_tp:
        tags.append("TP_DISPLACEMENT_IN_K")
        tags.append("REACHED_DISPLACEMENT")

    # Failed breakout heuristic: saw SWEEP and/or EXPANSION-ish structure without DISPLACEMENT
    if not is_tp and "DISPLACEMENT" not in has and (
        "SWEEP" in has or "EXPANSION" in has or "RETEST" in has
    ):
        tags.append("FAILED_BREAKOUT_LIKE")
    if not is_tp and has <= {"RANGE", "SHADOW_PENDING"}:
        tags.append("QUIET_RANGE")

    # Primary label
    primary = "OTHER_MIXED"
    for cand in _PRIMARY_PRIORITY:
        if cand in tags:
            primary = cand
            break
    if primary == "OTHER_MIXED":
        if "RANGE_TO_SWEEP_ONLY" in tags:
            primary = "RANGE_TO_SWEEP_ONLY"
        elif "STAYED_RANGE" in tags:
            primary = "STAYED_RANGE"
        elif "FAILED_BREAKOUT_LIKE" in tags:
            primary = "FAILED_BREAKOUT_LIKE"
        elif "QUIET_RANGE" in tags:
            primary = "STAYED_RANGE"

    # Deduplicate tags preserving order
    seen: set[str] = set()
    tags_u: list[str] = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            tags_u.append(t)

    return PathTaxonomy(
        primary=primary,
        tags=tuple(tags_u),
        state_path=tuple(states),
        unique_states=uniq_t,
        max_structural_depth=depth,
    )


def characterize_false_alarms(
    labels: Sequence[BarJointLabel],
    *,
    K: int = DEFAULT_K,
    follow: int = DEFAULT_FOLLOW,
    rare_zones: Sequence[str] = RARE_ZONES,
) -> dict[str, Any]:
    """
    Partition rare-zone signals into TP/FA; label 20-bar CRT evolution; compare.
    """
    K = int(K)
    follow = int(follow)
    rare = tuple(rare_zones)
    signals = find_zone_entries(labels, target_zones=rare)
    disp_starts = [e.t0_index for e in find_displacement_starts(labels)]
    disp_set = set(disp_starts)

    records: list[dict[str, Any]] = []
    for sig in signals:
        t = sig.index
        d = _first_disp_in_window(disp_starts, t, K)
        is_tp = d is not None
        path = extract_crt_path(labels, t, follow)
        tax = classify_crt_evolution(
            path,
            is_tp=is_tp,
            K=K,
            disp_starts_set=disp_set,
            signal_index=t,
        )
        lead = int(d - t) if d is not None else None
        records.append(
            {
                "signal_index": t,
                "timestamp": sig.timestamp,
                "zone_entered": sig.zone_entered,
                "zone_from": sig.zone_from,
                "is_tp": is_tp,
                "label": "TP" if is_tp else "FA",
                "lead_to_disp": lead,
                "primary_evolution": tax.primary,
                "tags": list(tax.tags),
                "unique_states": list(tax.unique_states),
                "max_structural_depth": tax.max_structural_depth,
                "state_path_compact": "→".join(tax.unique_states),
                # full path can be long; store only for samples
            }
        )

    # Aggregations
    def _agg(subset: list[dict[str, Any]]) -> dict[str, Any]:
        n = len(subset)
        by_primary = Counter(r["primary_evolution"] for r in subset)
        by_zone = Counter(r["zone_entered"] for r in subset)
        tag_c = Counter()
        for r in subset:
            for tag in r["tags"]:
                if tag.startswith("TRANS_"):
                    continue  # keep path tags separate volume
                tag_c[tag] += 1
        # zone × primary
        zone_primary: dict[str, Counter] = defaultdict(Counter)
        for r in subset:
            zone_primary[r["zone_entered"]][r["primary_evolution"]] += 1
        return {
            "n": n,
            "by_primary": {k: int(v) for k, v in by_primary.most_common()},
            "by_primary_pct": {
                k: (100.0 * v / n if n else 0.0) for k, v in by_primary.most_common()
            },
            "by_zone": {k: int(v) for k, v in by_zone.most_common()},
            "tag_counts": {k: int(v) for k, v in tag_c.most_common(40)},
            "zone_x_primary": {
                z: {p: int(c) for p, c in cnt.most_common()}
                for z, cnt in zone_primary.items()
            },
            "mean_max_structural_depth": (
                float(sum(r["max_structural_depth"] for r in subset) / n) if n else None
            ),
        }

    fa = [r for r in records if not r["is_tp"]]
    tp = [r for r in records if r["is_tp"]]

    fa_by_zone = {z: [r for r in fa if r["zone_entered"] == z] for z in rare}
    tp_by_zone = {z: [r for r in tp if r["zone_entered"] == z] for z in rare}

    # Delta primary % (FA − TP) for shared primaries
    fa_pct = _agg(fa)["by_primary_pct"]
    tp_pct = _agg(tp)["by_primary_pct"]
    all_prim = sorted(set(fa_pct) | set(tp_pct))
    primary_delta = {
        p: float(fa_pct.get(p, 0.0) - tp_pct.get(p, 0.0)) for p in all_prim
    }

    return {
        "schema_version": "rare_zone_fa_characterization_v1",
        "K": K,
        "follow_bars": follow,
        "rare_zones": list(rare),
        "n_signals": len(records),
        "n_tp": len(tp),
        "n_fa": len(fa),
        "precision": len(tp) / len(records) if records else 0.0,
        "overall": {
            "FA": _agg(fa),
            "TP": _agg(tp),
            "primary_pct_delta_FA_minus_TP": primary_delta,
        },
        "by_zone": {
            z: {
                "FA": _agg(fa_by_zone[z]),
                "TP": _agg(tp_by_zone[z]),
                "n_fa": len(fa_by_zone[z]),
                "n_tp": len(tp_by_zone[z]),
                "precision": (
                    len(tp_by_zone[z]) / (len(tp_by_zone[z]) + len(fa_by_zone[z]))
                    if (tp_by_zone[z] or fa_by_zone[z])
                    else 0.0
                ),
            }
            for z in rare
        },
        # compact sample paths for inspection
        "samples": {
            "FA": _sample_paths(labels, fa, follow, n=12),
            "TP": _sample_paths(labels, tp, follow, n=12),
        },
        "definitions": {
            "TP": f"DISPLACEMENT start in [t, t+{K}]",
            "FA": f"no DISPLACEMENT start in [t, t+{K}]",
            "follow": f"CRT path on bars [t, t+{follow}]",
            "LATE_DISPLACEMENT": f"DISPLACEMENT start in (t+{K}, t+{follow}]",
            "REACHED_EXPANSION_NO_DISP": "saw EXPANSION without DISPLACEMENT in follow window",
            "RANGE_TO_SWEEP_ONLY": "only RANGE/SWEEP (no DISPLACEMENT+)",
            "FAILED_BREAKOUT_LIKE": "SWEEP/EXPANSION/RETEST without DISPLACEMENT (FA)",
            "QUIET_RANGE": "only RANGE/SHADOW (FA)",
        },
    }


def _sample_paths(
    labels: Sequence[BarJointLabel],
    recs: Sequence[Mapping[str, Any]],
    follow: int,
    n: int = 10,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in recs[:n]:
        t = int(r["signal_index"])
        path = extract_crt_path(labels, t, follow)
        # compress runs: RANGE×5 → SWEEP×2
        compact = _compress_runs(path)
        out.append(
            {
                "timestamp": r["timestamp"],
                "zone_entered": r["zone_entered"],
                "primary": r["primary_evolution"],
                "path_runs": compact,
                "unique_states": r["unique_states"],
            }
        )
    return out


def _compress_runs(path: Sequence[str]) -> str:
    if not path:
        return ""
    parts: list[str] = []
    cur = path[0]
    n = 1
    for s in path[1:]:
        if s == cur:
            n += 1
        else:
            parts.append(f"{cur}×{n}")
            cur = s
            n = 1
    parts.append(f"{cur}×{n}")
    return " → ".join(parts)


def fa_char_to_markdown(rep: Mapping[str, Any], *, title: str = "") -> str:
    K = rep.get("K")
    follow = rep.get("follow_bars")
    lines = [
        title or "# Rare-zone false-alarm characterization",
        "",
        f"**K={K}** (TP if DISPLACEMENT in [t,t+K]) · **Follow={follow} bars** CRT path",
        "",
        f"Signals: **{rep.get('n_signals')}** · TP: **{rep.get('n_tp')}** · FA: **{rep.get('n_fa')}** · "
        f"Precision: **{100*float(rep.get('precision') or 0):.1f}%**",
        "",
        "## Definitions",
        "",
    ]
    for k, v in (rep.get("definitions") or {}).items():
        lines.append(f"- **{k}:** {v}")

    overall = rep.get("overall") or {}
    fa_o = overall.get("FA") or {}
    tp_o = overall.get("TP") or {}

    lines.extend(
        [
            "",
            "## FA vs TP — primary CRT evolution",
            "",
            "| primary evolution | FA n | FA % | TP n | TP % | Δpp (FA−TP) |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    primaries = sorted(
        set(fa_o.get("by_primary") or {}) | set(tp_o.get("by_primary") or {}),
        key=lambda p: -((fa_o.get("by_primary") or {}).get(p, 0)),
    )
    for p in primaries:
        fa_n = int((fa_o.get("by_primary") or {}).get(p, 0))
        tp_n = int((tp_o.get("by_primary") or {}).get(p, 0))
        fa_p = float((fa_o.get("by_primary_pct") or {}).get(p, 0.0))
        tp_p = float((tp_o.get("by_primary_pct") or {}).get(p, 0.0))
        lines.append(
            f"| {p} | {fa_n} | {fa_p:.1f} | {tp_n} | {tp_p:.1f} | {fa_p - tp_p:+.1f} |"
        )

    lines.extend(
        [
            "",
            f"Mean max structural depth — FA: {fa_o.get('mean_max_structural_depth')} · "
            f"TP: {tp_o.get('mean_max_structural_depth')}",
            "",
            "## FA partition by rare zone entered",
            "",
            "| zone | n_FA | n_TP | precision | top FA evolution |",
            "|---|---:|---:|---:|---|",
        ]
    )
    by_zone = rep.get("by_zone") or {}
    for z in rep.get("rare_zones") or []:
        zpack = by_zone.get(z) or {}
        fa_z = zpack.get("FA") or {}
        top = ""
        if fa_z.get("by_primary"):
            top_k = list((fa_z["by_primary"] or {}).items())[:2]
            top = ", ".join(f"{a} ({b})" for a, b in top_k)
        lines.append(
            f"| {z} | {zpack.get('n_fa', 0)} | {zpack.get('n_tp', 0)} | "
            f"{100*float(zpack.get('precision') or 0):.1f}% | {top} |"
        )

    lines.extend(["", "## Per-zone FA primary evolution (%)", ""])
    # table zones × primaries
    all_p = set()
    for z in rep.get("rare_zones") or []:
        all_p |= set(((by_zone.get(z) or {}).get("FA") or {}).get("by_primary") or {})
    all_p_l = sorted(all_p)
    if all_p_l:
        lines.append("| zone | " + " | ".join(all_p_l) + " |")
        lines.append("|---|" + "|".join(["---:" for _ in all_p_l]) + "|")
        for z in rep.get("rare_zones") or []:
            fa_z = (by_zone.get(z) or {}).get("FA") or {}
            pct = fa_z.get("by_primary_pct") or {}
            n = fa_z.get("n") or 1
            cells = " | ".join(f"{float(pct.get(p, 0)):.1f}" for p in all_p_l)
            lines.append(f"| {z} (n={fa_z.get('n', 0)}) | {cells} |")

    lines.extend(["", "## Per-zone TP primary evolution (%)", ""])
    all_p_tp = set()
    for z in rep.get("rare_zones") or []:
        all_p_tp |= set(((by_zone.get(z) or {}).get("TP") or {}).get("by_primary") or {})
    all_p_tp_l = sorted(all_p_tp)
    if all_p_tp_l:
        lines.append("| zone | " + " | ".join(all_p_tp_l) + " |")
        lines.append("|---|" + "|".join(["---:" for _ in all_p_tp_l]) + "|")
        for z in rep.get("rare_zones") or []:
            tp_z = (by_zone.get(z) or {}).get("TP") or {}
            pct = tp_z.get("by_primary_pct") or {}
            cells = " | ".join(f"{float(pct.get(p, 0)):.1f}" for p in all_p_tp_l)
            lines.append(f"| {z} (n={tp_z.get('n', 0)}) | {cells} |")

    lines.extend(["", "## Sample FA paths (compressed runs)", ""])
    for s in (rep.get("samples") or {}).get("FA") or []:
        lines.append(
            f"- `{s.get('timestamp')}` enter **{s.get('zone_entered')}** → "
            f"**{s.get('primary')}**: {s.get('path_runs')}"
        )
    lines.extend(["", "## Sample TP paths (compressed runs)", ""])
    for s in (rep.get("samples") or {}).get("TP") or []:
        lines.append(
            f"- `{s.get('timestamp')}` enter **{s.get('zone_entered')}** → "
            f"**{s.get('primary')}**: {s.get('path_runs')}"
        )
    lines.append("")
    return "\n".join(lines)


def run_from_csv(
    csv_path: str,
    *,
    instrument: str = "XAUUSD",
    K: int = DEFAULT_K,
    follow: int = DEFAULT_FOLLOW,
) -> dict[str, Any]:
    labels = collect_crt_zone_joint_labels(csv_path, instrument=instrument)
    rep = characterize_false_alarms(labels, K=K, follow=follow)
    rep["meta"] = {
        "csv_path": csv_path,
        "instrument": instrument,
        "n_labels": len(labels),
    }
    return rep
