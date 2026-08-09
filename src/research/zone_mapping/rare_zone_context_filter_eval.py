"""
Context-filter experiment: rare-zone entry × CRT state at signal time.

Compares RANGE vs SWEEP (and residual contexts) without changing zone thresholds.

Precision (by context S)
  P(DISPLACEMENT start in [t, t+K] | rare-zone entry at t AND crt_state(t)=S)

Recall (by context S)
  P(∃ rare entry in [t0−K, t0] with crt_state(entry)=S | DISPLACEMENT start at t0)

Also reports:
  - overall rare-zone detector metrics (same as detection eval)
  - interaction: precision_SWEEP − precision_RANGE, odds ratios
  - calibration: precision by cluster_score tercile within each context

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

PRIMARY_CONTEXTS = ("RANGE", "SWEEP")
DEFAULT_K_VALUES = (1, 2, 3, 5, 10)


@dataclass(frozen=True)
class ContextualSignal:
    index: int
    timestamp: str
    zone_entered: str
    zone_from: str
    crt_context: str
    cluster_score: float


def build_contextual_rare_signals(
    labels: Sequence[BarJointLabel],
    *,
    rare_zones: Sequence[str] = RARE_ZONES,
) -> list[ContextualSignal]:
    """Rare-zone entries annotated with CRT state at the entry bar."""
    base = find_zone_entries(labels, target_zones=rare_zones)
    out: list[ContextualSignal] = []
    for s in base:
        lab = labels[s.index]
        # Prefer cluster_score from labels if we stored it — BarJointLabel has it
        out.append(
            ContextualSignal(
                index=s.index,
                timestamp=s.timestamp,
                zone_entered=s.zone_entered,
                zone_from=s.zone_from,
                crt_context=str(lab.crt_state),
                cluster_score=float(lab.cluster_score),
            )
        )
    return out


def _evaluate_signal_subset(
    labels: Sequence[BarJointLabel],
    signals: Sequence[ContextualSignal],
    *,
    K: int,
    context_name: str,
) -> dict[str, Any]:
    disp_starts = [e.t0_index for e in find_displacement_starts(labels)]
    n_disp = len(disp_starts)
    n_sig = len(signals)
    tp = 0
    fp = 0
    leads: list[int] = []
    scores_tp: list[float] = []
    scores_fp: list[float] = []
    zone_tp: Counter = Counter()
    zone_fp: Counter = Counter()

    sig_idx_by_context = sorted(s.index for s in signals)

    for s in signals:
        d = _first_disp_in_window(disp_starts, s.index, K)
        if d is not None:
            tp += 1
            leads.append(int(d - s.index))
            scores_tp.append(s.cluster_score)
            zone_tp[s.zone_entered] += 1
        else:
            fp += 1
            scores_fp.append(s.cluster_score)
            zone_fp[s.zone_entered] += 1

    # Recall: DISPLACEMENT starts with a signal from this context subset in [t0-K, t0]
    recalled = 0
    for t0 in disp_starts:
        lo = t0 - K
        hit = False
        for idx in sig_idx_by_context:
            if idx < lo:
                continue
            if idx > t0:
                break
            hit = True
            break
        if hit:
            recalled += 1

    precision = float(tp) / n_sig if n_sig else 0.0
    recall = float(recalled) / n_disp if n_disp else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )

    def _mean(xs: list[float]) -> Optional[float]:
        return float(sum(xs) / len(xs)) if xs else None

    # Calibration: score terciles within this context
    all_scores = [s.cluster_score for s in signals]
    calibration = _score_tercile_precision(signals, disp_starts, K)

    return {
        "context": context_name,
        "K": int(K),
        "n_signals": n_sig,
        "n_displacement_starts": n_disp,
        "tp": tp,
        "fp": fp,
        "recalled_displacements": recalled,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "false_alarm_rate": float(fp) / n_sig if n_sig else 0.0,
        "mean_lead": _mean([float(x) for x in leads]),
        "mean_cluster_score_tp": _mean(scores_tp),
        "mean_cluster_score_fp": _mean(scores_fp),
        "mean_cluster_score_all": _mean(all_scores),
        "score_gap_tp_minus_fp": (
            (_mean(scores_tp) - _mean(scores_fp))
            if scores_tp and scores_fp
            else None
        ),
        "tp_by_zone": dict(zone_tp),
        "fp_by_zone": dict(zone_fp),
        "calibration_by_score_tercile": calibration,
    }


def _score_tercile_precision(
    signals: Sequence[ContextualSignal],
    disp_starts: Sequence[int],
    K: int,
) -> list[dict[str, Any]]:
    if len(signals) < 3:
        return []
    scores = sorted(s.cluster_score for s in signals)
    n = len(scores)
    t1 = scores[n // 3]
    t2 = scores[(2 * n) // 3]

    def bucket(sc: float) -> str:
        if sc <= t1:
            return "low"
        if sc <= t2:
            return "mid"
        return "high"

    buckets: dict[str, list[ContextualSignal]] = {"low": [], "mid": [], "high": []}
    for s in signals:
        buckets[bucket(s.cluster_score)].append(s)

    out: list[dict[str, Any]] = []
    for name in ("low", "mid", "high"):
        sub = buckets[name]
        if not sub:
            out.append({"tercile": name, "n": 0, "precision": None})
            continue
        tp = 0
        for s in sub:
            if _first_disp_in_window(list(disp_starts), s.index, K) is not None:
                tp += 1
        out.append(
            {
                "tercile": name,
                "n": len(sub),
                "score_lo": min(s.cluster_score for s in sub),
                "score_hi": max(s.cluster_score for s in sub),
                "precision": float(tp) / len(sub),
            }
        )
    return out


def evaluate_context_filter(
    labels: Sequence[BarJointLabel],
    *,
    K_values: Sequence[int] = DEFAULT_K_VALUES,
    rare_zones: Sequence[str] = RARE_ZONES,
    primary_contexts: Sequence[str] = PRIMARY_CONTEXTS,
) -> dict[str, Any]:
    """Full RANGE vs SWEEP (and other) context comparison across K horizons."""
    all_sig = build_contextual_rare_signals(labels, rare_zones=rare_zones)
    by_ctx: dict[str, list[ContextualSignal]] = defaultdict(list)
    for s in all_sig:
        by_ctx[s.crt_context].append(s)

    contexts_present = sorted(by_ctx.keys(), key=lambda c: -len(by_ctx[c]))
    # Ensure primary first
    ordered_ctx = []
    for c in primary_contexts:
        if c in by_ctx:
            ordered_ctx.append(c)
    for c in contexts_present:
        if c not in ordered_ctx:
            ordered_ctx.append(c)

    by_K: dict[str, Any] = {}
    for K in K_values:
        K = int(K)
        overall = _evaluate_signal_subset(
            labels, all_sig, K=K, context_name="ALL_RARE"
        )
        per_ctx = {
            c: _evaluate_signal_subset(labels, by_ctx[c], K=K, context_name=c)
            for c in ordered_ctx
        }

        # Interaction effects (RANGE vs SWEEP)
        p_range = per_ctx.get("RANGE", {}).get("precision")
        p_sweep = per_ctx.get("SWEEP", {}).get("precision")
        r_range = per_ctx.get("RANGE", {}).get("recall")
        r_sweep = per_ctx.get("SWEEP", {}).get("recall")
        n_r = per_ctx.get("RANGE", {}).get("n_signals") or 0
        n_s = per_ctx.get("SWEEP", {}).get("n_signals") or 0
        tp_r = per_ctx.get("RANGE", {}).get("tp") or 0
        tp_s = per_ctx.get("SWEEP", {}).get("tp") or 0
        fp_r = per_ctx.get("RANGE", {}).get("fp") or 0
        fp_s = per_ctx.get("SWEEP", {}).get("fp") or 0

        # Odds ratio: (tp_s/fp_s) / (tp_r/fp_r)
        odds_ratio = None
        if fp_r > 0 and fp_s > 0 and tp_r >= 0 and tp_s >= 0:
            # Haldane-Anscombe correction if zeros
            a, b, c, d = tp_s + 0.5, fp_s + 0.5, tp_r + 0.5, fp_r + 0.5
            odds_ratio = (a / b) / (c / d)

        interaction = {
            "precision_SWEEP_minus_RANGE": (
                float(p_sweep - p_range)
                if p_sweep is not None and p_range is not None
                else None
            ),
            "recall_SWEEP_minus_RANGE": (
                float(r_sweep - r_range)
                if r_sweep is not None and r_range is not None
                else None
            ),
            "precision_ratio_SWEEP_over_RANGE": (
                float(p_sweep / p_range)
                if p_sweep is not None and p_range and p_range > 0
                else None
            ),
            "odds_ratio_TP_SWEEP_vs_RANGE": odds_ratio,
            "n_RANGE": n_r,
            "n_SWEEP": n_s,
            "share_signals_RANGE": n_r / len(all_sig) if all_sig else 0.0,
            "share_signals_SWEEP": n_s / len(all_sig) if all_sig else 0.0,
            # If we *only* keep SWEEP-context signals (filter experiment)
            "filter_keep_SWEEP_only": {
                "n_signals": n_s,
                "precision": p_sweep,
                "recall": r_sweep,
                "f1": per_ctx.get("SWEEP", {}).get("f1"),
                "signal_retention": n_s / len(all_sig) if all_sig else 0.0,
                "precision_lift_vs_all": (
                    float(p_sweep - overall["precision"])
                    if p_sweep is not None
                    else None
                ),
                "recall_delta_vs_all": (
                    float(r_sweep - overall["recall"])
                    if r_sweep is not None
                    else None
                ),
            },
            "filter_keep_RANGE_only": {
                "n_signals": n_r,
                "precision": p_range,
                "recall": r_range,
                "f1": per_ctx.get("RANGE", {}).get("f1"),
                "signal_retention": n_r / len(all_sig) if all_sig else 0.0,
                "precision_lift_vs_all": (
                    float(p_range - overall["precision"])
                    if p_range is not None
                    else None
                ),
                "recall_delta_vs_all": (
                    float(r_range - overall["recall"])
                    if r_range is not None
                    else None
                ),
            },
        }

        by_K[str(K)] = {
            "overall_rare": overall,
            "by_context": per_ctx,
            "interaction_RANGE_vs_SWEEP": interaction,
        }

    ctx_counts = {c: len(by_ctx[c]) for c in ordered_ctx}
    return {
        "schema_version": "rare_zone_context_filter_eval_v1",
        "rare_zones": list(rare_zones),
        "n_bars": len(labels),
        "n_rare_signals": len(all_sig),
        "n_displacement_starts": len(find_displacement_starts(labels)),
        "signal_counts_by_crt_context": ctx_counts,
        "K_values": list(K_values),
        "by_K": by_K,
        "definitions": {
            "context": "CRT state on the rare-zone entry bar (not lagged)",
            "precision": "P(DISPLACEMENT in [t,t+K] | rare entry at t, context=S)",
            "recall": "P(rare entry with context=S in [t0-K,t0] | DISPLACEMENT at t0)",
            "interaction": "precision/recall SWEEP − RANGE; odds ratio of TP among signals",
            "filter_keep_SWEEP_only": "hypothetical detector that drops RANGE-context rare entries",
        },
    }


def context_eval_to_markdown(ev: Mapping[str, Any], *, title: str = "") -> str:
    lines = [
        title or "# Rare-zone entry × CRT context (RANGE vs SWEEP)",
        "",
        f"**Bars:** {ev.get('n_bars')} · **Rare signals:** {ev.get('n_rare_signals')} · "
        f"**DISPLACEMENT starts:** {ev.get('n_displacement_starts')}",
        "",
        "### Signal counts by CRT context at entry",
        "",
        "| CRT context | n_signals | share |",
        "|---|---:|---:|",
    ]
    total = int(ev.get("n_rare_signals") or 0) or 1
    for c, n in (ev.get("signal_counts_by_crt_context") or {}).items():
        lines.append(f"| {c} | {n} | {100.0 * n / total:.1f}% |")

    lines.extend(
        [
            "",
            "## Precision / recall by context and K",
            "",
            "| K | context | n_sig | precision | recall | F1 | FA rate | mean lead | score_gap (TP−FP) |",
            "|---:|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for K in ev.get("K_values") or []:
        pack = (ev.get("by_K") or {}).get(str(K)) or {}
        # overall first
        o = pack.get("overall_rare") or {}
        if o:
            lines.append(_row(K, o))
        for c, m in (pack.get("by_context") or {}).items():
            lines.append(_row(K, m))

    lines.extend(
        [
            "",
            "## Interaction: SWEEP vs RANGE",
            "",
            "| K | P_SWEEP | P_RANGE | ΔP | P ratio | R_SWEEP | R_RANGE | ΔR | odds ratio | "
            "keep_SWEEP P | keep_SWEEP R | keep_SWEEP retain |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for K in ev.get("K_values") or []:
        inter = ((ev.get("by_K") or {}).get(str(K)) or {}).get(
            "interaction_RANGE_vs_SWEEP"
        ) or {}
        filt = inter.get("filter_keep_SWEEP_only") or {}
        byc = ((ev.get("by_K") or {}).get(str(K)) or {}).get("by_context") or {}
        pr = byc.get("RANGE", {}).get("precision")
        ps = byc.get("SWEEP", {}).get("precision")
        rr = byc.get("RANGE", {}).get("recall")
        rs = byc.get("SWEEP", {}).get("recall")
        lines.append(
            "| {K} | {ps} | {pr} | {dp} | {ratio} | {rss} | {rr} | {dr} | {odds} | {fsp} | {fsr} | {ret} |".format(
                K=K,
                ps=_fmt(ps),
                pr=_fmt(pr),
                dp=_fmt(inter.get("precision_SWEEP_minus_RANGE")),
                ratio=_fmt(inter.get("precision_ratio_SWEEP_over_RANGE")),
                rss=_fmt(rs),
                rr=_fmt(rr),
                dr=_fmt(inter.get("recall_SWEEP_minus_RANGE")),
                odds=_fmt(inter.get("odds_ratio_TP_SWEEP_vs_RANGE")),
                fsp=_fmt(filt.get("precision")),
                fsr=_fmt(filt.get("recall")),
                ret=_fmt(filt.get("signal_retention")),
            )
        )

    # Calibration detail for K=5
    lines.extend(["", "## Calibration (cluster_score terciles) — K=5", ""])
    pack5 = (ev.get("by_K") or {}).get("5") or {}
    for name, m in [
        ("ALL", pack5.get("overall_rare")),
        *[(c, m) for c, m in (pack5.get("by_context") or {}).items() if c in ("RANGE", "SWEEP")],
    ]:
        if not m:
            continue
        lines.append(f"### {name}")
        lines.append("")
        lines.append("| tercile | n | score range | precision |")
        lines.append("|---|---:|---|---:|")
        for row in m.get("calibration_by_score_tercile") or []:
            if row.get("n", 0) == 0:
                lines.append(f"| {row.get('tercile')} | 0 | — | — |")
                continue
            lines.append(
                f"| {row['tercile']} | {row['n']} | "
                f"[{row.get('score_lo', 0):.3f}, {row.get('score_hi', 0):.3f}] | "
                f"{float(row.get('precision') or 0):.3f} |"
            )
        lines.append("")

    lines.append("")
    return "\n".join(lines)


def _fmt(x: Any) -> str:
    if x is None:
        return "—"
    try:
        return f"{float(x):.3f}"
    except (TypeError, ValueError):
        return str(x)


def _row(K: int, m: Mapping[str, Any]) -> str:
    gap = m.get("score_gap_tp_minus_fp")
    return (
        "| {K} | {c} | {ns} | {p:.3f} | {r:.3f} | {f:.3f} | {fa:.3f} | {ml} | {gap} |".format(
            K=K,
            c=m.get("context", "?"),
            ns=m.get("n_signals", 0),
            p=float(m.get("precision") or 0),
            r=float(m.get("recall") or 0),
            f=float(m.get("f1") or 0),
            fa=float(m.get("false_alarm_rate") or 0),
            ml=_fmt(m.get("mean_lead")),
            gap=_fmt(gap),
        )
    )


def run_from_csv(
    csv_path: str,
    *,
    instrument: str = "XAUUSD",
    K_values: Sequence[int] = DEFAULT_K_VALUES,
) -> dict[str, Any]:
    labels = collect_crt_zone_joint_labels(csv_path, instrument=instrument)
    ev = evaluate_context_filter(labels, K_values=K_values)
    ev["meta"] = {
        "csv_path": csv_path,
        "instrument": instrument,
        "n_labels": len(labels),
    }
    return ev
