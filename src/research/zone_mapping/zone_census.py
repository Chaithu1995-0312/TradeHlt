"""
Zone geometry census — baseline description of market geometry from a bar map.

Metrics (per zone id, plus corpus-level summary):
  - n_bars / occupancy
  - coverage_pct
  - mean_cluster_score (confidence)
  - mean_dwell_length (persistence of consecutive same-zone runs)
  - transition matrix (dynamics: P[from→to] over consecutive bars)

Assignment rule (baseline):
  each bar is assigned to ``best_zone_id`` from HistoricalZoneMapper
  (argmax per-zone similarity), independent of pass/fail threshold.
  Separate ``passed`` stats are reported for threshold occupancy.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional, Sequence


OUTSIDE = "__outside__"  # best_zone_id missing / none


@dataclass(frozen=True)
class BarZoneLabel:
    timestamp: str
    best_zone_id: str
    cluster_score: float
    passed: bool


def _zone_key(zid: Any) -> str:
    if zid is None or zid == "" or zid == "none":
        return OUTSIDE
    return str(zid)


def labels_from_map_records(records: Sequence[Mapping[str, Any]]) -> list[BarZoneLabel]:
    out: list[BarZoneLabel] = []
    for r in records:
        out.append(
            BarZoneLabel(
                timestamp=str(r.get("timestamp", "")),
                best_zone_id=_zone_key(r.get("best_zone_id")),
                cluster_score=float(r.get("cluster_score", 0.0)),
                passed=bool(r.get("passed_cluster_threshold", False)),
            )
        )
    return out


def _dwell_lengths(zone_seq: Sequence[str]) -> dict[str, list[int]]:
    """Run-length encode consecutive identical zone labels."""
    dwells: dict[str, list[int]] = defaultdict(list)
    if not zone_seq:
        return dwells
    cur = zone_seq[0]
    run = 1
    for z in zone_seq[1:]:
        if z == cur:
            run += 1
        else:
            dwells[cur].append(run)
            cur = z
            run = 1
    dwells[cur].append(run)
    return dwells


def compute_zone_census(
    labels: Sequence[BarZoneLabel],
    *,
    registry_zone_ids: Optional[Sequence[str]] = None,
) -> dict[str, Any]:
    """
    Compute occupancy / coverage / confidence / dwell / transition matrix.

    Parameters
    ----------
    labels
        Chronological bar labels (must be time-ordered).
    registry_zone_ids
        Optional ordered list of known zone ids so empty zones still appear.
    """
    n = len(labels)
    zone_ids = list(registry_zone_ids or [])
    seen = {_zone_key(z) for z in zone_ids}
    for lab in labels:
        if lab.best_zone_id not in seen:
            zone_ids.append(lab.best_zone_id)
            seen.add(lab.best_zone_id)
    if OUTSIDE in seen and OUTSIDE not in zone_ids:
        zone_ids.append(OUTSIDE)

    # Occupancy + score sums
    occ = Counter(lab.best_zone_id for lab in labels)
    score_sum: dict[str, float] = defaultdict(float)
    score_n: dict[str, int] = defaultdict(int)
    passed_occ = Counter()
    for lab in labels:
        score_sum[lab.best_zone_id] += lab.cluster_score
        score_n[lab.best_zone_id] += 1
        if lab.passed:
            passed_occ[lab.best_zone_id] += 1

    zone_seq = [lab.best_zone_id for lab in labels]
    dwells = _dwell_lengths(zone_seq)

    # Transition counts: from[i] -> to[i+1]
    trans_counts: dict[str, Counter] = {z: Counter() for z in zone_ids}
    for a, b in zip(zone_seq, zone_seq[1:]):
        if a not in trans_counts:
            trans_counts[a] = Counter()
        trans_counts[a][b] += 1
        if b not in zone_ids:
            zone_ids.append(b)

    per_zone: dict[str, Any] = {}
    for z in zone_ids:
        n_bars = int(occ.get(z, 0))
        mean_score = (
            float(score_sum[z] / score_n[z]) if score_n.get(z, 0) > 0 else None
        )
        dlist = dwells.get(z, [])
        mean_dwell = float(sum(dlist) / len(dlist)) if dlist else None
        row_counts = trans_counts.get(z, Counter())
        row_total = sum(row_counts.values())
        trans_prob = {
            t: (float(c) / row_total if row_total > 0 else 0.0)
            for t, c in sorted(row_counts.items())
        }
        # Full matrix row over all zone_ids (zeros for missing)
        trans_row_full = {
            t: float(row_counts.get(t, 0)) / row_total if row_total > 0 else 0.0
            for t in zone_ids
        }
        per_zone[z] = {
            "n_bars": n_bars,
            "coverage_pct": (100.0 * n_bars / n) if n > 0 else 0.0,
            "mean_cluster_score": mean_score,
            "mean_dwell_length": mean_dwell,
            "n_dwells": len(dlist),
            "max_dwell_length": max(dlist) if dlist else 0,
            "n_bars_passed_threshold": int(passed_occ.get(z, 0)),
            "passed_coverage_pct": (
                100.0 * int(passed_occ.get(z, 0)) / n if n > 0 else 0.0
            ),
            "self_transition_prob": trans_row_full.get(z, 0.0),
            "transition_probs": trans_prob,
            "transition_row": trans_row_full,
        }

    # Matrix as nested lists (ordered zone_ids)
    matrix_counts = [
        [int(trans_counts.get(a, Counter()).get(b, 0)) for b in zone_ids]
        for a in zone_ids
    ]
    matrix_probs = []
    for a in zone_ids:
        row = trans_counts.get(a, Counter())
        tot = sum(row.values())
        matrix_probs.append(
            [float(row.get(b, 0)) / tot if tot > 0 else 0.0 for b in zone_ids]
        )

    n_passed = sum(1 for lab in labels if lab.passed)
    return {
        "schema_version": "zone_census_v1",
        "n_bars": n,
        "n_bars_passed_threshold": n_passed,
        "passed_threshold_pct": (100.0 * n_passed / n) if n > 0 else 0.0,
        "zone_ids": zone_ids,
        "assignment_rule": "best_zone_id (argmax similarity); threshold stats separate",
        "per_zone": per_zone,
        "transition_matrix": {
            "order": zone_ids,
            "counts": matrix_counts,
            "probabilities": matrix_probs,
        },
    }


def census_to_markdown(census: Mapping[str, Any], *, title: str = "Zone Geometry Census") -> str:
    """Human-readable baseline table."""
    lines = [
        f"# {title}",
        "",
        f"**Bars:** {census.get('n_bars')}  ·  "
        f"**Passed threshold:** {census.get('n_bars_passed_threshold')} "
        f"({census.get('passed_threshold_pct'):.2f}%)",
        "",
        f"Assignment: `{census.get('assignment_rule')}`",
        "",
        "## Per-zone metrics",
        "",
        "| Zone | n_bars | coverage_% | mean_cluster_score | mean_dwell | max_dwell | self_P | passed_bars |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    per = census.get("per_zone") or {}
    for z in census.get("zone_ids") or []:
        r = per.get(z) or {}
        ms = r.get("mean_cluster_score")
        md = r.get("mean_dwell_length")
        lines.append(
            "| {z} | {n} | {cov:.3f} | {ms} | {md} | {mx} | {sp:.3f} | {pb} |".format(
                z=z,
                n=r.get("n_bars", 0),
                cov=float(r.get("coverage_pct") or 0.0),
                ms=f"{ms:.4f}" if ms is not None else "—",
                md=f"{md:.2f}" if md is not None else "—",
                mx=r.get("max_dwell_length", 0),
                sp=float(r.get("self_transition_prob") or 0.0),
                pb=r.get("n_bars_passed_threshold", 0),
            )
        )

    lines.extend(
        [
            "",
            "## Transition matrix (probabilities, rows=from, cols=to)",
            "",
        ]
    )
    order = census.get("transition_matrix", {}).get("order") or []
    probs = census.get("transition_matrix", {}).get("probabilities") or []
    if order and probs:
        header = "| from \\ to | " + " | ".join(order) + " |"
        sep = "|---|" + "|".join(["---:" for _ in order]) + "|"
        lines.append(header)
        lines.append(sep)
        for i, z in enumerate(order):
            row = probs[i] if i < len(probs) else []
            cells = " | ".join(f"{float(p):.3f}" for p in row)
            lines.append(f"| {z} | {cells} |")
    lines.append("")
    return "\n".join(lines)
