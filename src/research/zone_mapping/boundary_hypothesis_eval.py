"""
Geometry-boundary hypothesis test.

H1: DISPLACEMENT is enriched near zone *boundaries* (small best−second margin),
    not near zone *centers* (large margin / high center similarity).

H2: Under CRT-context conditioning (esp. SWEEP), margin explains DISPLACEMENT
    better than cluster_score — which can invert (high score → lower hit rate).

Measures
--------
  margin = best_zone_score − second_best_score  (from top-2 Gaussian similarities)
  cluster_score = EngineRunner hard-path cluster aggregate

  - Mean margin / score for DISPLACEMENT bars vs non-DISPLACEMENT
  - Same for DISPLACEMENT *starts*
  - Quintile enrichment: P(DISPLACEMENT | margin quintile) vs P(DISPLACEMENT | score quintile)
  - Conditioned on crt_state ∈ {RANGE, SWEEP, ALL}
  - Rank-style lift: top-20% lowest margin vs top-20% highest cluster_score

Research-only.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from research.zone_mapping.crt_zone_crosstab import (
    BarJointLabel,
    collect_crt_zone_joint_labels,
)
from research.zone_mapping.displacement_zone_event_study import find_displacement_starts


def _mean(xs: Sequence[float]) -> Optional[float]:
    return float(sum(xs) / len(xs)) if xs else None


def _quantile_edges(values: Sequence[float], n_bins: int = 5) -> list[float]:
    """Return n_bins+1 edges for equal-count bins (sorted unique-aware)."""
    if not values:
        return [0.0, 1.0]
    s = sorted(values)
    n = len(s)
    edges = [s[0]]
    for b in range(1, n_bins):
        idx = min(n - 1, int(round(b * n / n_bins)))
        edges.append(s[idx])
    edges.append(s[-1] + 1e-15)
    # ensure strictly increasing
    for i in range(1, len(edges)):
        if edges[i] <= edges[i - 1]:
            edges[i] = edges[i - 1] + 1e-12
    return edges


def _bin_index(x: float, edges: Sequence[float]) -> int:
    # last bin inclusive on right
    for i in range(len(edges) - 1):
        if edges[i] <= x < edges[i + 1]:
            return i
    return len(edges) - 2


def _enrichment_table(
    labels: Sequence[BarJointLabel],
    *,
    feature: str,  # "margin_best_second" | "cluster_score"
    positive: Sequence[bool],
    n_bins: int = 5,
    invert_for_boundary: bool = False,
) -> dict[str, Any]:
    """
    Bin feature into equal-count quintiles; report P(positive) per bin.

    If invert_for_boundary and feature is margin, bin 0 = lowest margin (boundary).
    """
    assert len(labels) == len(positive)
    if feature == "cluster_score":
        vals = [float(lab.cluster_score) for lab in labels]
    elif feature == "margin_best_second":
        vals = [float(lab.margin_best_second) for lab in labels]
    else:
        raise ValueError(f"unknown feature {feature!r}")

    edges = _quantile_edges(vals, n_bins)
    bin_pos = [0] * n_bins
    bin_n = [0] * n_bins
    for v, y in zip(vals, positive):
        b = _bin_index(v, edges)
        bin_n[b] += 1
        if y:
            bin_pos[b] += 1

    base_rate = sum(1 for y in positive if y) / len(positive) if positive else 0.0
    rows = []
    for b in range(n_bins):
        n = bin_n[b]
        p = float(bin_pos[b]) / n if n else 0.0
        rows.append(
            {
                "bin": b,
                "n": n,
                "feature_lo": edges[b],
                "feature_hi": edges[b + 1],
                "hit_rate": p,
                "lift_vs_base": (p / base_rate) if base_rate > 0 else None,
                "label": (
                    "boundary(low margin)"
                    if invert_for_boundary and b == 0
                    else (
                        "center(high margin)"
                        if invert_for_boundary and b == n_bins - 1
                        else (
                            "low score"
                            if not invert_for_boundary and b == 0
                            else (
                                "high score"
                                if not invert_for_boundary and b == n_bins - 1
                                else f"bin_{b}"
                            )
                        )
                    )
                ),
            }
        )

    # Monotonicity score: for margin (boundary hyp), hit rate should fall with bin index
    # Spearman-like: correlation of bin index with hit_rate
    if n_bins >= 2:
        xs = list(range(n_bins))
        ys = [r["hit_rate"] for r in rows]
        mx = sum(xs) / n_bins
        my = sum(ys) / n_bins
        num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        denx = sum((x - mx) ** 2 for x in xs) ** 0.5
        deny = sum((y - my) ** 2 for y in ys) ** 0.5
        corr = float(num / (denx * deny)) if denx > 0 and deny > 0 else 0.0
    else:
        corr = 0.0

    return {
        "feature": feature,
        "n_bins": n_bins,
        "base_rate": base_rate,
        "bins": rows,
        "bin_index_hit_rate_corr": corr,
        # boundary support: negative corr for margin (higher bin = higher margin = lower hits)
        "boundary_pattern_score": (-corr if invert_for_boundary else corr),
    }


def _top_frac_hit_rate(
    labels: Sequence[BarJointLabel],
    positive: Sequence[bool],
    *,
    feature: str,
    frac: float = 0.2,
    lowest: bool = True,
) -> dict[str, Any]:
    """Hit rate in the extreme fraction of the feature distribution."""
    n = len(labels)
    if n == 0:
        return {"n": 0, "hit_rate": None}
    indexed = []
    for i, lab in enumerate(labels):
        v = lab.margin_best_second if feature == "margin_best_second" else lab.cluster_score
        indexed.append((v, bool(positive[i])))
    indexed.sort(key=lambda t: t[0], reverse=not lowest)
    k = max(1, int(round(frac * n)))
    head = indexed[:k]
    hits = sum(1 for _, y in head if y)
    base = sum(1 for y in positive if y) / n
    hr = hits / k
    return {
        "feature": feature,
        "extreme": "lowest" if lowest else "highest",
        "frac": frac,
        "n": k,
        "hit_rate": hr,
        "base_rate": base,
        "lift": (hr / base) if base > 0 else None,
    }


def _forward_disp_start(
    disp_start_indices: Sequence[int], i: int, K: int
) -> bool:
    """True if a DISPLACEMENT start occurs in (i, i+K] (strictly after bar i)."""
    hi = i + K
    for d in disp_start_indices:
        if d <= i:
            continue
        if d > hi:
            break
        return True
    return False


def evaluate_boundary_hypothesis(
    labels: Sequence[BarJointLabel],
    *,
    contexts: Sequence[str] = ("ALL", "RANGE", "SWEEP"),
    n_bins: int = 5,
    forward_K: int = 5,
) -> dict[str, Any]:
    """
    Test DISPLACEMENT enrichment near boundaries vs centers; compare to cluster_score.

    Context conditioning
    --------------------
    ALL:
      - contemporaneous: crt_state == DISPLACEMENT vs not
      - starts: DISPLACEMENT start bars vs not
    RANGE / SWEEP:
      - bars with that CRT state only
      - positive = DISPLACEMENT *start* occurs in the next forward_K bars
        (predictive; contemporaneous DISPLACEMENT is impossible inside RANGE/SWEEP)
    """
    n = len(labels)
    starts = find_displacement_starts(labels)
    disp_start_idx = sorted(e.t0_index for e in starts)
    is_disp_state = [lab.crt_state == "DISPLACEMENT" for lab in labels]
    is_disp_start = [False] * n
    for e in starts:
        if 0 <= e.t0_index < n:
            is_disp_start[e.t0_index] = True

    by_context: dict[str, Any] = {}
    for ctx in contexts:
        if ctx == "ALL":
            labs = list(labels)
            y_state = is_disp_state
            y_start = is_disp_start
            y_fwd = [
                _forward_disp_start(disp_start_idx, i, forward_K) for i in range(n)
            ]
            mode = "contemporaneous_and_starts"
        else:
            labs = []
            y_state = []  # unused for non-ALL
            y_start = []
            y_fwd = []
            for i, lab in enumerate(labels):
                if lab.crt_state != ctx:
                    continue
                labs.append(lab)
                y_state.append(False)
                y_start.append(False)
                y_fwd.append(_forward_disp_start(disp_start_idx, i, forward_K))
            mode = f"forward_DISPLACEMENT_start_within_{forward_K}"

        if len(labs) < 50:
            by_context[ctx] = {"n": len(labs), "insufficient": True}
            continue

        # Primary positive for enrichment tables:
        # ALL → contemporaneous DISPLACEMENT state; RANGE/SWEEP → forward start
        y_primary = y_state if ctx == "ALL" else y_fwd

        margin_vals = [lab.margin_best_second for lab in labs]
        score_vals = [lab.cluster_score for lab in labs]
        m_pos = [lab.margin_best_second for lab, y in zip(labs, y_primary) if y]
        m_neg = [lab.margin_best_second for lab, y in zip(labs, y_primary) if not y]
        s_pos = [lab.cluster_score for lab, y in zip(labs, y_primary) if y]
        s_neg = [lab.cluster_score for lab, y in zip(labs, y_primary) if not y]

        enr_margin = _enrichment_table(
            labs,
            feature="margin_best_second",
            positive=y_primary,
            n_bins=n_bins,
            invert_for_boundary=True,
        )
        enr_score = _enrichment_table(
            labs,
            feature="cluster_score",
            positive=y_primary,
            n_bins=n_bins,
            invert_for_boundary=False,
        )

        # For ALL also keep start-based enrichment
        enr_margin_start = None
        enr_score_start = None
        if ctx == "ALL":
            enr_margin_start = _enrichment_table(
                labs,
                feature="margin_best_second",
                positive=y_start,
                n_bins=n_bins,
                invert_for_boundary=True,
            )
            enr_score_start = _enrichment_table(
                labs,
                feature="cluster_score",
                positive=y_start,
                n_bins=n_bins,
                invert_for_boundary=False,
            )

        by_context[ctx] = {
            "n": len(labs),
            "positive_definition": mode,
            "n_positive": sum(1 for y in y_primary if y),
            "n_displacement_state": sum(1 for y in y_state if y) if ctx == "ALL" else None,
            "n_displacement_starts_on_subset": (
                sum(1 for y in y_start if y) if ctx == "ALL" else sum(1 for y in y_fwd if y)
            ),
            "mean_margin_all": _mean(margin_vals),
            "mean_margin_positive": _mean(m_pos),
            "mean_margin_negative": _mean(m_neg),
            # aliases for markdown / back-compat naming
            "mean_margin_DISPLACEMENT_state": _mean(m_pos) if ctx == "ALL" else None,
            "mean_margin_other_state": _mean(m_neg) if ctx == "ALL" else None,
            "delta_margin_disp_minus_other": (
                (_mean(m_pos) - _mean(m_neg)) if m_pos and m_neg else None
            ),
            "mean_cluster_score_all": _mean(score_vals),
            "mean_cluster_score_positive": _mean(s_pos),
            "mean_cluster_score_negative": _mean(s_neg),
            "mean_cluster_score_DISPLACEMENT_state": _mean(s_pos) if ctx == "ALL" else None,
            "mean_cluster_score_other_state": _mean(s_neg) if ctx == "ALL" else None,
            "delta_score_disp_minus_other": (
                (_mean(s_pos) - _mean(s_neg)) if s_pos and s_neg else None
            ),
            "enrichment_DISPLACEMENT_state": {
                "margin": enr_margin,
                "cluster_score": enr_score,
            },
            "enrichment_DISPLACEMENT_start": {
                "margin": enr_margin_start,
                "cluster_score": enr_score_start,
            }
            if ctx == "ALL"
            else {"margin": enr_margin, "cluster_score": enr_score},
            "top20pct": {
                "lowest_margin_state": _top_frac_hit_rate(
                    labs, y_primary, feature="margin_best_second", frac=0.2, lowest=True
                ),
                "highest_margin_state": _top_frac_hit_rate(
                    labs, y_primary, feature="margin_best_second", frac=0.2, lowest=False
                ),
                "lowest_score_state": _top_frac_hit_rate(
                    labs, y_primary, feature="cluster_score", frac=0.2, lowest=True
                ),
                "highest_score_state": _top_frac_hit_rate(
                    labs, y_primary, feature="cluster_score", frac=0.2, lowest=False
                ),
            },
            "hypothesis_support": {
                "margin_lower_on_positive": (
                    _mean(m_pos) is not None
                    and _mean(m_neg) is not None
                    and _mean(m_pos) < _mean(m_neg)
                ),
                "score_higher_on_positive": (
                    _mean(s_pos) is not None
                    and _mean(s_neg) is not None
                    and _mean(s_pos) > _mean(s_neg)
                ),
                "margin_boundary_bin_corr": enr_margin["bin_index_hit_rate_corr"],
                "score_center_bin_corr": enr_score["bin_index_hit_rate_corr"],
                "boundary_hyp_supported_for_state": enr_margin["bin_index_hit_rate_corr"]
                < -0.3,
                "score_hyp_supported_for_state": enr_score["bin_index_hit_rate_corr"]
                > 0.3,
                "score_inverted_for_state": enr_score["bin_index_hit_rate_corr"] < -0.3,
                # aliases used by CLI / markdown
                "margin_lower_on_DISPLACEMENT": (
                    _mean(m_pos) is not None
                    and _mean(m_neg) is not None
                    and _mean(m_pos) < _mean(m_neg)
                ),
                "score_higher_on_DISPLACEMENT": (
                    _mean(s_pos) is not None
                    and _mean(s_neg) is not None
                    and _mean(s_pos) > _mean(s_neg)
                ),
            },
        }

    return {
        "schema_version": "boundary_hypothesis_eval_v1",
        "n_bars": n,
        "forward_K": forward_K,
        "definitions": {
            "margin_best_second": "best_zone_score − second_best_score (top-2 similarities)",
            "boundary": "small margin (competitive zones)",
            "center": "large margin (dominant single zone)",
            "cluster_score": "EngineRunner hard-path cluster aggregate",
            "ALL_positive": "crt_state == DISPLACEMENT (contemporaneous)",
            "RANGE_SWEEP_positive": f"DISPLACEMENT start within next {forward_K} bars",
        },
        "by_context": by_context,
    }


def boundary_eval_to_markdown(ev: Mapping[str, Any], *, title: str = "") -> str:
    lines = [
        title or "# Geometry boundary hypothesis vs cluster score",
        "",
        f"**Bars:** {ev.get('n_bars')}",
        "",
        "### Definitions",
        "",
        f"- margin = `{ev.get('definitions', {}).get('margin_best_second')}`",
        f"- boundary = {ev.get('definitions', {}).get('boundary')}",
        f"- cluster_score = {ev.get('definitions', {}).get('cluster_score')}",
        "",
        "## Mean geometry by CRT slice",
        "",
        "| context | n | n_pos | positive def | mean margin (all) | mean margin (pos) | mean margin (neg) | Δmargin | mean score (pos) | mean score (neg) | Δscore |",
        "|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for ctx, pack in (ev.get("by_context") or {}).items():
        if pack.get("insufficient"):
            lines.append(f"| {ctx} | {pack.get('n')} | — | insufficient |")
            continue
        lines.append(
            "| {c} | {n} | {np} | {pd} | {ma:.4f} | {md:.4f} | {mo:.4f} | {dm} | {sd:.4f} | {so:.4f} | {ds} |".format(
                c=ctx,
                n=pack["n"],
                np=pack.get("n_positive", pack.get("n_displacement_state")),
                pd=str(pack.get("positive_definition", ""))[:40],
                ma=float(pack["mean_margin_all"] or 0),
                md=float(pack.get("mean_margin_positive") or pack.get("mean_margin_DISPLACEMENT_state") or 0),
                mo=float(pack.get("mean_margin_negative") or pack.get("mean_margin_other_state") or 0),
                dm=_fmt(pack.get("delta_margin_disp_minus_other")),
                sd=float(pack.get("mean_cluster_score_positive") or pack.get("mean_cluster_score_DISPLACEMENT_state") or 0),
                so=float(pack.get("mean_cluster_score_negative") or pack.get("mean_cluster_score_other_state") or 0),
                ds=_fmt(pack.get("delta_score_disp_minus_other")),
            )
        )

    for ctx in ("ALL", "RANGE", "SWEEP"):
        pack = (ev.get("by_context") or {}).get(ctx)
        if not pack or pack.get("insufficient"):
            continue
        lines.extend(
            [
                f"",
                f"## Enrichment quintiles — context={ctx}",
                f"Positive: `{pack.get('positive_definition')}`",
                "",
            ]
        )
        lines.append("")  # keep structure; next lines still add margin header
        lines.append("### margin (bin0=boundary … bin4=center)")
        lines.append("")
        lines.append("| bin | n | margin range | P(DISP) | lift |")
        lines.append("|---:|---:|---|---:|---:|")
        for row in pack["enrichment_DISPLACEMENT_state"]["margin"]["bins"]:
            lines.append(
                f"| {row['bin']} | {row['n']} | [{row['feature_lo']:.4f}, {row['feature_hi']:.4f}) | "
                f"{row['hit_rate']:.4f} | {_fmt(row.get('lift_vs_base'))} |"
            )
        lines.append("")
        lines.append(
            f"bin↔hit_rate corr (margin): "
            f"**{pack['enrichment_DISPLACEMENT_state']['margin']['bin_index_hit_rate_corr']:.3f}** "
            f"(boundary hyp wants **negative**)"
        )
        lines.append("")
        lines.append("### cluster_score (bin0=low … bin4=high)")
        lines.append("")
        lines.append("| bin | n | score range | P(DISP) | lift |")
        lines.append("|---:|---:|---|---:|---:|")
        for row in pack["enrichment_DISPLACEMENT_state"]["cluster_score"]["bins"]:
            lines.append(
                f"| {row['bin']} | {row['n']} | [{row['feature_lo']:.4f}, {row['feature_hi']:.4f}) | "
                f"{row['hit_rate']:.4f} | {_fmt(row.get('lift_vs_base'))} |"
            )
        lines.append("")
        lines.append(
            f"bin↔hit_rate corr (score): "
            f"**{pack['enrichment_DISPLACEMENT_state']['cluster_score']['bin_index_hit_rate_corr']:.3f}** "
            f"(center hyp wants **positive**; inverted if negative)"
        )

        hs = pack.get("hypothesis_support") or {}
        lines.extend(
            [
                "",
                f"### Hypothesis flags ({ctx})",
                "",
                f"- margin lower on DISPLACEMENT: **{hs.get('margin_lower_on_DISPLACEMENT')}**",
                f"- score higher on DISPLACEMENT: **{hs.get('score_higher_on_DISPLACEMENT')}**",
                f"- boundary pattern (margin): **{hs.get('boundary_hyp_supported_for_state')}**",
                f"- score center pattern: **{hs.get('score_hyp_supported_for_state')}**",
                f"- score inverted: **{hs.get('score_inverted_for_state')}**",
                "",
                "### Top 20% extremes (DISPLACEMENT *state* hit rate)",
                "",
            ]
        )
        t20 = pack.get("top20pct") or {}
        for key in (
            "lowest_margin_state",
            "highest_margin_state",
            "lowest_score_state",
            "highest_score_state",
        ):
            r = t20.get(key) or {}
            lines.append(
                f"- **{key}**: n={r.get('n')} hit_rate={_fmt(r.get('hit_rate'))} "
                f"lift={_fmt(r.get('lift'))}"
            )

    lines.append("")
    return "\n".join(lines)


def _fmt(x: Any) -> str:
    if x is None:
        return "—"
    try:
        return f"{float(x):.4f}"
    except (TypeError, ValueError):
        return str(x)


def run_from_csv(csv_path: str, *, instrument: str = "XAUUSD") -> dict[str, Any]:
    labels = collect_crt_zone_joint_labels(csv_path, instrument=instrument)
    ev = evaluate_boundary_hypothesis(labels)
    ev["meta"] = {
        "csv_path": csv_path,
        "instrument": instrument,
        "n_labels": len(labels),
    }
    return ev
