"""
Event-detection evaluation: rare-zone entry → CRT DISPLACEMENT within K bars.

Signal definition
-----------------
  Rare-zone *entry* at bar t: best_zone_id ∈ RARE and best_zone_id ≠ previous bar.
  (Same transition notion as the lead/lag study.)

Target definition
-----------------
  DISPLACEMENT *start* at bar t0: CRT state first enters DISPLACEMENT.

Detection window
----------------
  Forward (precision / false alarms):
      signal at t is a TRUE POSITIVE if some DISPLACEMENT start ∈ [t, t+K].
  Backward (recall):
      DISPLACEMENT start at t0 is RECALLED if some rare-zone entry ∈ [t0−K, t0].

Lead time (true positives only)
-------------------------------
  lead = t0 − t_signal  (≥ 0 when signal is at or before the CRT start;
  if multiple DISPLACEMENT starts in window, use the *first*).

Baselines
---------
  1. random_timing — same #signals as rare entries, uniform random bar indices
  2. persistent_zone_entry — transitions into zone_2 or zone_7 (bulk/persistent)
  3. any_zone_entry — any best_zone_id change (optional reference)

Research-only. No admission authority.
"""
from __future__ import annotations

import json
import random
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from research.zone_mapping.crt_zone_crosstab import (
    BarJointLabel,
    collect_crt_zone_joint_labels,
)
from research.zone_mapping.displacement_zone_event_study import (
    find_displacement_starts,
)

RARE_ZONES = ("zone_1", "zone_4", "zone_5", "zone_6")
PERSISTENT_ZONES = ("zone_2", "zone_7")
DEFAULT_K_VALUES = (1, 2, 3, 5, 10)


@dataclass(frozen=True)
class SignalEvent:
    index: int
    timestamp: str
    zone_entered: str
    zone_from: str


def find_zone_entries(
    labels: Sequence[BarJointLabel],
    *,
    target_zones: Sequence[str],
) -> list[SignalEvent]:
    """Bars where best_zone_id transitions into one of target_zones."""
    targets = set(target_zones)
    out: list[SignalEvent] = []
    for i in range(1, len(labels)):
        z_now = labels[i].zone_id
        z_prev = labels[i - 1].zone_id
        if z_now in targets and z_now != z_prev:
            out.append(
                SignalEvent(
                    index=i,
                    timestamp=labels[i].timestamp,
                    zone_entered=z_now,
                    zone_from=z_prev,
                )
            )
    return out


def _displacement_start_indices(labels: Sequence[BarJointLabel]) -> list[int]:
    return [e.t0_index for e in find_displacement_starts(labels)]


def _first_disp_in_window(
    disp_starts: Sequence[int], t: int, K: int
) -> Optional[int]:
    """First DISPLACEMENT start index in [t, t+K], or None."""
    hi = t + K
    for d in disp_starts:
        if d < t:
            continue
        if d > hi:
            break
        return d
    return None


def _has_signal_in_backward_window(
    signal_indices_sorted: Sequence[int], t0: int, K: int
) -> bool:
    """True if some signal index ∈ [t0−K, t0]."""
    lo = t0 - K
    # binary-search style linear scan ok for moderate N
    for s in signal_indices_sorted:
        if s < lo:
            continue
        if s > t0:
            break
        return True
    return False


def evaluate_detector(
    labels: Sequence[BarJointLabel],
    signals: Sequence[SignalEvent],
    *,
    K: int,
    detector_name: str,
) -> dict[str, Any]:
    """
    Precision / recall / lead-time / false-alarm for one signal set and horizon K.
    """
    n_bars = len(labels)
    disp_starts = _displacement_start_indices(labels)
    disp_set = set(disp_starts)
    sig_idx = sorted(s.index for s in signals)
    n_sig = len(signals)
    n_disp = len(disp_starts)

    tp = 0
    fp = 0
    lead_times: list[int] = []
    tp_by_zone: Counter = Counter()
    fp_by_zone: Counter = Counter()

    for sig in signals:
        t = sig.index
        d = _first_disp_in_window(disp_starts, t, K)
        if d is not None:
            tp += 1
            lead_times.append(int(d - t))
            tp_by_zone[sig.zone_entered] += 1
        else:
            fp += 1
            fp_by_zone[sig.zone_entered] += 1

    # Recall: fraction of DISPLACEMENT starts with a signal in [t0-K, t0]
    recalled = 0
    for t0 in disp_starts:
        if _has_signal_in_backward_window(sig_idx, t0, K):
            recalled += 1

    precision = float(tp) / n_sig if n_sig else 0.0
    recall = float(recalled) / n_disp if n_disp else 0.0
    f1 = (
        (2 * precision * recall / (precision + recall))
        if (precision + recall) > 0
        else 0.0
    )
    false_alarm_rate = float(fp) / n_sig if n_sig else 0.0  # among signals
    # Rate of false alarms per bar (and per 1000 bars)
    fa_per_bar = float(fp) / n_bars if n_bars else 0.0
    signal_rate = float(n_sig) / n_bars if n_bars else 0.0

    lead_summary: dict[str, Any]
    if lead_times:
        srt = sorted(lead_times)
        lead_summary = {
            "n": len(lead_times),
            "mean": float(sum(lead_times) / len(lead_times)),
            "median": float(srt[len(srt) // 2]),
            "p25": float(srt[len(srt) // 4]),
            "p75": float(srt[(3 * len(srt)) // 4]),
            "frac_lead_0": sum(1 for x in lead_times if x == 0) / len(lead_times),
            "frac_lead_ge_1": sum(1 for x in lead_times if x >= 1) / len(lead_times),
            "histogram": {str(k): v for k, v in sorted(Counter(lead_times).items())},
        }
    else:
        lead_summary = {
            "n": 0,
            "mean": None,
            "median": None,
            "p25": None,
            "p75": None,
            "frac_lead_0": None,
            "frac_lead_ge_1": None,
            "histogram": {},
        }

    return {
        "detector": detector_name,
        "K": int(K),
        "n_bars": n_bars,
        "n_signals": n_sig,
        "n_displacement_starts": n_disp,
        "tp": tp,
        "fp": fp,
        "fn": n_disp - recalled,  # missed displacements
        "recalled_displacements": recalled,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "false_alarm_rate": false_alarm_rate,
        "false_alarms_per_bar": fa_per_bar,
        "false_alarms_per_1000_bars": 1000.0 * fa_per_bar,
        "signal_rate_per_bar": signal_rate,
        "lead_time_bars": lead_summary,
        "tp_by_zone_entered": dict(tp_by_zone),
        "fp_by_zone_entered": dict(fp_by_zone),
    }


def _random_signals(
    n_bars: int,
    n_signals: int,
    *,
    rng: random.Random,
    labels: Sequence[BarJointLabel],
) -> list[SignalEvent]:
    """Uniform random bar indices as fake 'entries' (index ≥ 1)."""
    if n_bars < 2 or n_signals <= 0:
        return []
    # sample without replacement when possible
    pool = list(range(1, n_bars))
    if n_signals >= len(pool):
        chosen = pool
    else:
        chosen = rng.sample(pool, n_signals)
    out: list[SignalEvent] = []
    for i in sorted(chosen):
        out.append(
            SignalEvent(
                index=i,
                timestamp=labels[i].timestamp,
                zone_entered="__random__",
                zone_from=labels[i - 1].zone_id if i > 0 else "",
            )
        )
    return out


def evaluate_all_detectors(
    labels: Sequence[BarJointLabel],
    *,
    K_values: Sequence[int] = DEFAULT_K_VALUES,
    rare_zones: Sequence[str] = RARE_ZONES,
    persistent_zones: Sequence[str] = PERSISTENT_ZONES,
    n_random_trials: int = 50,
    random_seed: int = 42,
) -> dict[str, Any]:
    """Full multi-K, multi-detector evaluation pack."""
    rare_sig = find_zone_entries(labels, target_zones=rare_zones)
    pers_sig = find_zone_entries(labels, target_zones=persistent_zones)
    any_sig = find_zone_entries(
        labels,
        target_zones=tuple(
            sorted({lab.zone_id for lab in labels if lab.zone_id and lab.zone_id != "__outside__"})
        ),
    )
    # any zone change: target all zones that appear
    any_change = find_zone_entries(
        labels,
        target_zones=tuple({lab.zone_id for lab in labels}),
    )

    results_by_K: dict[str, Any] = {}
    rng = random.Random(random_seed)

    for K in K_values:
        K = int(K)
        rare_m = evaluate_detector(labels, rare_sig, K=K, detector_name="rare_zone_entry")
        pers_m = evaluate_detector(
            labels, pers_sig, K=K, detector_name="persistent_zone_entry"
        )
        any_m = evaluate_detector(labels, any_change, K=K, detector_name="any_zone_entry")

        # Random baseline: mean ± empirical over trials
        rand_precs: list[float] = []
        rand_recalls: list[float] = []
        rand_fa: list[float] = []
        rand_leads: list[float] = []
        for _ in range(n_random_trials):
            rsig = _random_signals(
                len(labels), len(rare_sig), rng=rng, labels=labels
            )
            rm = evaluate_detector(labels, rsig, K=K, detector_name="random_timing")
            rand_precs.append(rm["precision"])
            rand_recalls.append(rm["recall"])
            rand_fa.append(rm["false_alarm_rate"])
            if rm["lead_time_bars"]["mean"] is not None:
                rand_leads.append(float(rm["lead_time_bars"]["mean"]))

        def _mean(xs: list[float]) -> Optional[float]:
            return float(sum(xs) / len(xs)) if xs else None

        def _std(xs: list[float]) -> Optional[float]:
            if len(xs) < 2:
                return 0.0 if xs else None
            m = sum(xs) / len(xs)
            return float((sum((x - m) ** 2 for x in xs) / len(xs)) ** 0.5)

        random_summary = {
            "detector": "random_timing",
            "K": K,
            "n_trials": n_random_trials,
            "n_signals_matched_to_rare": len(rare_sig),
            "precision_mean": _mean(rand_precs),
            "precision_std": _std(rand_precs),
            "recall_mean": _mean(rand_recalls),
            "recall_std": _std(rand_recalls),
            "false_alarm_rate_mean": _mean(rand_fa),
            "false_alarm_rate_std": _std(rand_fa),
            "lead_time_mean_of_means": _mean(rand_leads),
            # lift of rare vs random precision
            "precision_lift_vs_random": (
                (rare_m["precision"] / _mean(rand_precs))
                if _mean(rand_precs) and _mean(rand_precs) > 0
                else None
            ),
        }

        results_by_K[str(K)] = {
            "rare_zone_entry": rare_m,
            "persistent_zone_entry": pers_m,
            "any_zone_entry": any_m,
            "random_timing": random_summary,
            "precision_delta_vs_persistent": rare_m["precision"] - pers_m["precision"],
            "precision_delta_vs_random": (
                rare_m["precision"] - float(random_summary["precision_mean"] or 0.0)
            ),
            "recall_delta_vs_persistent": rare_m["recall"] - pers_m["recall"],
            "recall_delta_vs_random": (
                rare_m["recall"] - float(random_summary["recall_mean"] or 0.0)
            ),
        }

    return {
        "schema_version": "rare_zone_detection_eval_v1",
        "rare_zones": list(rare_zones),
        "persistent_zones": list(persistent_zones),
        "n_bars": len(labels),
        "n_rare_signals": len(rare_sig),
        "n_persistent_signals": len(pers_sig),
        "n_any_zone_change_signals": len(any_change),
        "n_displacement_starts": len(_displacement_start_indices(labels)),
        "K_values": list(K_values),
        "n_random_trials": n_random_trials,
        "random_seed": random_seed,
        "by_K": results_by_K,
        "definitions": {
            "signal": "transition into target zone set",
            "precision": "P(DISPLACEMENT start in [t, t+K] | signal at t)",
            "recall": "P(rare signal in [t0-K, t0] | DISPLACEMENT start at t0)",
            "false_alarm_rate": "1 - precision (among signals)",
            "lead_time": "bars from signal to first DISPLACEMENT start in window (TP only)",
        },
    }


def detection_eval_to_markdown(ev: Mapping[str, Any], *, title: str = "") -> str:
    lines = [
        title or "# Rare-zone entry → DISPLACEMENT detection evaluation",
        "",
        f"**Bars:** {ev.get('n_bars')}  ·  "
        f"**DISPLACEMENT starts:** {ev.get('n_displacement_starts')}  ·  "
        f"**Rare signals:** {ev.get('n_rare_signals')}  ·  "
        f"**Persistent signals:** {ev.get('n_persistent_signals')}",
        "",
        f"Rare zones: `{', '.join(ev.get('rare_zones') or [])}`  ·  "
        f"Persistent: `{', '.join(ev.get('persistent_zones') or [])}`",
        "",
        "## Definitions",
        "",
        f"- Signal: {ev.get('definitions', {}).get('signal')}",
        f"- Precision: {ev.get('definitions', {}).get('precision')}",
        f"- Recall: {ev.get('definitions', {}).get('recall')}",
        f"- False-alarm rate: {ev.get('definitions', {}).get('false_alarm_rate')}",
        f"- Lead time: {ev.get('definitions', {}).get('lead_time')}",
        "",
        "## Main results by horizon K",
        "",
        "| K | detector | n_sig | precision | recall | F1 | FA rate | FA/1000 bars | mean lead |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    by_K = ev.get("by_K") or {}
    for K in ev.get("K_values") or []:
        pack = by_K.get(str(K)) or {}
        for name in (
            "rare_zone_entry",
            "persistent_zone_entry",
            "any_zone_entry",
        ):
            m = pack.get(name) or {}
            if not m:
                continue
            lead = (m.get("lead_time_bars") or {}).get("mean")
            lead_s = f"{lead:.2f}" if lead is not None else "—"
            lines.append(
                "| {K} | {d} | {ns} | {p:.3f} | {r:.3f} | {f:.3f} | {fa:.3f} | {fa1k:.2f} | {ld} |".format(
                    K=K,
                    d=m.get("detector", name),
                    ns=m.get("n_signals", 0),
                    p=float(m.get("precision") or 0),
                    r=float(m.get("recall") or 0),
                    f=float(m.get("f1") or 0),
                    fa=float(m.get("false_alarm_rate") or 0),
                    fa1k=float(m.get("false_alarms_per_1000_bars") or 0),
                    ld=lead_s,
                )
            )
        rnd = pack.get("random_timing") or {}
        if rnd:
            lines.append(
                "| {K} | random_timing (mean±std, {nt} trials) | {ns} | "
                "{p:.3f}±{ps:.3f} | {r:.3f}±{rs:.3f} | — | {fa:.3f}±{fas:.3f} | — | {ld} |".format(
                    K=K,
                    nt=rnd.get("n_trials", 0),
                    ns=rnd.get("n_signals_matched_to_rare", 0),
                    p=float(rnd.get("precision_mean") or 0),
                    ps=float(rnd.get("precision_std") or 0),
                    r=float(rnd.get("recall_mean") or 0),
                    rs=float(rnd.get("recall_std") or 0),
                    fa=float(rnd.get("false_alarm_rate_mean") or 0),
                    fas=float(rnd.get("false_alarm_rate_std") or 0),
                    ld=(
                        f"{rnd['lead_time_mean_of_means']:.2f}"
                        if rnd.get("lead_time_mean_of_means") is not None
                        else "—"
                    ),
                )
            )

    lines.extend(
        [
            "",
            "## Lift vs baselines (rare − baseline)",
            "",
            "| K | Δprecision vs random | Δprecision vs persistent | Δrecall vs random | Δrecall vs persistent | precision_lift vs random |",
            "|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for K in ev.get("K_values") or []:
        pack = by_K.get(str(K)) or {}
        rnd = pack.get("random_timing") or {}
        lines.append(
            "| {K} | {dpr:.3f} | {dpp:.3f} | {drr:.3f} | {drp:.3f} | {lift} |".format(
                K=K,
                dpr=float(pack.get("precision_delta_vs_random") or 0),
                dpp=float(pack.get("precision_delta_vs_persistent") or 0),
                drr=float(pack.get("recall_delta_vs_random") or 0),
                drp=float(pack.get("recall_delta_vs_persistent") or 0),
                lift=(
                    f"{float(rnd['precision_lift_vs_random']):.2f}"
                    if rnd.get("precision_lift_vs_random") is not None
                    else "—"
                ),
            )
        )

    # Detail for primary K=5 and K=10
    lines.extend(["", "## Detail — rare_zone_entry lead-time distribution", ""])
    for K in ev.get("K_values") or []:
        m = (by_K.get(str(K)) or {}).get("rare_zone_entry") or {}
        lt = m.get("lead_time_bars") or {}
        if not lt.get("n"):
            continue
        lines.append(f"### K = {K} (TP n={lt['n']})")
        lines.append("")
        lines.append(
            f"mean={lt.get('mean'):.2f}  median={lt.get('median'):.1f}  "
            f"p25={lt.get('p25')}  p75={lt.get('p75')}  "
            f"P(lead=0)={lt.get('frac_lead_0'):.3f}  P(lead≥1)={lt.get('frac_lead_ge_1'):.3f}"
        )
        lines.append("")
        hist = lt.get("histogram") or {}
        if hist:
            lines.append("| lead (bars) | count |")
            lines.append("|---:|---:|")
            for k, v in hist.items():
                lines.append(f"| {k} | {v} |")
            lines.append("")

    lines.append("")
    return "\n".join(lines)


def run_eval_from_csv(
    csv_path: str,
    *,
    instrument: str = "XAUUSD",
    K_values: Sequence[int] = DEFAULT_K_VALUES,
    n_random_trials: int = 50,
) -> dict[str, Any]:
    labels = collect_crt_zone_joint_labels(csv_path, instrument=instrument)
    ev = evaluate_all_detectors(
        labels, K_values=K_values, n_random_trials=n_random_trials
    )
    ev["meta"] = {
        "csv_path": csv_path,
        "instrument": instrument,
        "n_labels": len(labels),
    }
    return ev
