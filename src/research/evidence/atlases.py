"""Three atlases over the bar×direction outcome surface.

1. Opportunity leakage — path excursion that did not become unit TP.
2. State value — E[MFE], E[MAE], E[time], E[TP1], E[TP2] per already-emitted state.
3. Asymmetry — Long MFE − Short MFE at the same timestamp.

Not a training set. Path-conditioned counts are not t=0 policies.
CRT engine states are a different grain and are not attached here.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from research.evidence.queries import (
    _as_float_y,
    _col,
    _mean,
    _pct,
    _y_tp1,
)
from research.evidence.records import (
    EvidenceRecord,
    contrast_confidence,
    descriptive_confidence,
)

# Path heat thresholds in R (unit of the stored labels, not a new formula).
_MFE_HIGH = 1.0
_MAE_HIGH = 1.0
_MAE_LOW = 0.5

_BINARY_FLAGS = frozenset({
    "sweep_detected", "liquidity_sweep", "double_sweep",
    "break_of_structure", "volume_spike", "higher_high", "lower_low",
})

_STATE_COLS: tuple[tuple[str, str], ...] = (
    ("features.session", "session"),
    ("features.volatility_regime", "volatility"),
    ("features.hour_of_day", "hour"),
    ("features.trend_bias", "trend_bias"),
    ("side", "side"),
    ("features.sweep_detected", "sweep_detected"),
    ("features.liquidity_sweep", "liquidity_sweep"),
    ("features.double_sweep", "double_sweep"),
    ("features.break_of_structure", "break_of_structure"),
    ("features.volume_spike", "volume_spike"),
    ("features.higher_high", "higher_high"),
    ("features.lower_low", "lower_low"),
)


def _n(cols: dict[str, list]) -> int:
    y = _col(cols, "y_tp1")
    return len(y) if y is not None else 0


def _side_series(cols: dict[str, list]) -> list:
    return _col(cols, "side", "direction") or []


def _ts_series(cols: dict[str, list]) -> list:
    return _col(cols, "decision_ts", "timestamp") or []


def _flag_level(label: str, raw: Any) -> str:
    """Collapse 0/1 ontology flags; leave session/hour/vol/trend_bias as emitted."""
    if label not in _BINARY_FLAGS:
        return str(raw)
    try:
        x = float(raw)
    except (TypeError, ValueError):
        return str(raw)
    if x > 0:
        return "present"
    return "absent"


def _value_bundle(cols: dict[str, list], idx: list[int]) -> dict[str, Any]:
    def pick(name: str, *alts: str) -> list[float]:
        series = _col(cols, name, *alts)
        if series is None:
            return []
        out: list[float] = []
        for i in idx:
            v = series[i]
            if v is None:
                continue
            try:
                x = float(v)
            except (TypeError, ValueError):
                continue
            if x == x:
                out.append(x)
        return out

    mfe = pick("y_mfe_r", "path_mfe_r")
    mae = pick("y_mae_r_heat", "path_mae_r_heat")
    t_mfe = pick("y_time_to_mfe")
    hold = pick("y_holding_bars")
    tp1 = pick("y_tp1")
    tp2 = pick("y_tp2")
    e_mfe = _mean(mfe)
    e_mae = _mean(mae)
    path_net = None if e_mfe is None or e_mae is None else e_mfe - e_mae
    return {
        "n": len(idx),
        "e_mfe": e_mfe,
        "e_mae": e_mae,
        "e_time_to_mfe": _mean(t_mfe),
        "e_holding_bars": _mean(hold),
        "e_tp1": _mean(tp1),
        "e_tp2": _mean(tp2),
        "path_net": path_net,
        "mfe_p50": _pct(mfe, 50),
        "mae_p50": _pct(mae, 50),
    }


# ── 1. Leakage atlas ────────────────────────────────────────────────────────
def leakage_atlas(cols: dict[str, list]) -> list[EvidenceRecord]:
    y = _as_float_y(_y_tp1(cols))
    r05 = _as_float_y(_col(cols, "y_reached_0_5r") or [])
    r1 = _as_float_y(_col(cols, "y_reached_1r_horizon", "y_survives_be") or [])
    r2 = _as_float_y(_col(cols, "y_reached_2r_horizon", "y_tp2") or [])
    mfe = _as_float_y(_col(cols, "y_mfe_r", "path_mfe_r") or [])
    mae = _as_float_y(_col(cols, "y_mae_r_heat", "path_mae_r_heat") or [])
    n = len(y)
    if n == 0 or not r05 or not r1:
        return [EvidenceRecord(
            question="opportunity leakage atlas",
            surface="clean_labels",
            n=n,
            effect_name="missing_path_labels",
            effect_size=None,
            confidence="INSUFFICIENT",
            candidate_finding="Need y_tp1 plus reached-0.5/1R labels.",
        )]

    def hit(series: list, i: int) -> bool:
        return i < len(series) and series[i] == 1.0

    def num(series: list, i: int) -> float | None:
        if i >= len(series):
            return None
        return series[i]

    modes = {
        "reached_0_5_missed_tp": 0,
        "reached_1_missed_tp": 0,
        "reached_2_missed_tp": 0,
        "high_mfe_high_mae": 0,
        "low_mae_failed_tp": 0,
    }
    ladder = {
        "tp_captured": 0,
        "leak_reached_2_missed_tp": 0,
        "leak_reached_1_not_2": 0,
        "leak_reached_0_5_not_1": 0,
        "missed_tp_no_half_r": 0,
    }
    for i in range(n):
        missed = y[i] == 0.0
        captured = y[i] == 1.0
        if hit(r05, i) and missed:
            modes["reached_0_5_missed_tp"] += 1
        if hit(r1, i) and missed:
            modes["reached_1_missed_tp"] += 1
        if hit(r2, i) and missed:
            modes["reached_2_missed_tp"] += 1
        mv, av = num(mfe, i), num(mae, i)
        if mv is not None and av is not None and mv >= _MFE_HIGH and av >= _MAE_HIGH:
            modes["high_mfe_high_mae"] += 1
        if missed and av is not None and av < _MAE_LOW:
            modes["low_mae_failed_tp"] += 1
        if captured:
            ladder["tp_captured"] += 1
        elif hit(r2, i):
            ladder["leak_reached_2_missed_tp"] += 1
        elif hit(r1, i):
            ladder["leak_reached_1_not_2"] += 1
        elif hit(r05, i):
            ladder["leak_reached_0_5_not_1"] += 1
        else:
            ladder["missed_tp_no_half_r"] += 1

    recs = [
        EvidenceRecord(
            question=f"leakage mode: {name}",
            surface="clean_labels",
            n=n,
            effect_name="mode_rate",
            effect_size=(count / n) if n else None,
            confidence=descriptive_confidence(n),
            candidate_finding=f"{name}: {count}/{n} ({count / n:.4f}). Path-conditioned, not a t=0 policy.",
            extra={"count": count, "lookahead": True},
        )
        for name, count in modes.items()
    ]
    recs.append(EvidenceRecord(
        question="opportunity leakage atlas (exclusive missed-TP ladder)",
        surface="clean_labels",
        n=n,
        effect_name="leak_reached_1_not_2_rate",
        effect_size=(ladder["leak_reached_1_not_2"] / n) if n else None,
        confidence=descriptive_confidence(n),
        candidate_finding=(
            "Exclusive partition of the ledger: "
            + ", ".join(f"{k}={v}" for k, v in ladder.items())
            + ". Nested modes overlap; the ladder does not."
        ),
        extra={"modes": modes, "ladder": ladder, "lookahead": True},
    ))
    return recs


# ── 2. State value surface ──────────────────────────────────────────────────
def state_value_surface(cols: dict[str, list]) -> list[EvidenceRecord]:
    n = _n(cols)
    recs: list[EvidenceRecord] = []
    all_cells: list[dict[str, Any]] = []
    for col, label in _STATE_COLS:
        if col not in cols and not (label == "side" and _side_series(cols)):
            continue
        series = cols[col] if col in cols else _side_series(cols)
        buckets: dict[str, list[int]] = defaultdict(list)
        for i, raw in enumerate(series):
            buckets[_flag_level(label, raw)].append(i)
        cells = []
        nets = []
        for level, idx in sorted(buckets.items(), key=lambda kv: -len(kv[1])):
            if len(idx) < 30:
                continue
            bundle = _value_bundle(cols, idx)
            bundle["state"] = f"{label}={level}"
            cells.append(bundle)
            all_cells.append(bundle)
            if bundle["path_net"] is not None:
                nets.append(bundle["path_net"])
        mfes = [c["e_mfe"] for c in cells if c["e_mfe"] is not None]
        times = [c["e_time_to_mfe"] for c in cells if c["e_time_to_mfe"] is not None]
        mfe_spread = (max(mfes) - min(mfes)) if len(mfes) >= 2 else 0.0
        time_spread = (max(times) - min(times)) if len(times) >= 2 else 0.0
        net_spread = (max(nets) - min(nets)) if len(nets) >= 2 else 0.0
        recs.append(EvidenceRecord(
            question=f"state value: {label}",
            surface="clean_labels",
            n=n,
            effect_name="e_mfe_spread",
            effect_size=mfe_spread,
            confidence=contrast_confidence(n, abs(mfe_spread), floor=0.2),
            candidate_finding=(
                f"{label}: {len(cells)} cells, E[MFE] spread={mfe_spread:.4f}, "
                f"E[time] spread={time_spread:.4f}, path_net spread={net_spread:.4f}. "
                "E[MFE]/E[MAE]/E[time]/E[TP1]/E[TP2] — not win rate."
            ),
            extra={
                "cells": cells,
                "e_mfe_spread": mfe_spread,
                "e_time_spread": time_spread,
                "path_net_spread": net_spread,
            },
        ))
    by_mfe = sorted(
        [c for c in all_cells if c.get("state", "").split("=")[0] != "side"],
        key=lambda c: (c.get("e_mfe") is None, -(c.get("e_mfe") or 0.0)),
    )
    recs.insert(0, EvidenceRecord(
        question="state value surface",
        surface="clean_labels",
        n=n,
        effect_name="cells_ranked_by_e_mfe",
        effect_size=by_mfe[0]["e_mfe"] if by_mfe else None,
        confidence=descriptive_confidence(n),
        candidate_finding=(
            "State value is E[MFE], E[MAE], E[time], E[TP1], E[TP2]. "
            "path_net=E[MFE]−E[MAE] is ~0 for any state shared by both sides "
            "(long MFE ≈ short MAE on this grain). CRT engine states are not on this grain. "
            + (
                f"Largest E[MFE] cell {by_mfe[0]['state']} e_mfe={by_mfe[0]['e_mfe']:.4f} "
                f"e_time={by_mfe[0]['e_time_to_mfe']:.3f} e_tp1={by_mfe[0]['e_tp1']:.4f}."
                if by_mfe else "No powered cells."
            )
        ),
        extra={
            "top_by_e_mfe": by_mfe[:12],
            "side_path_net": [c for c in all_cells if c.get("state", "").startswith("side=")],
            "grain_identity": "pooled both-sides => E[MFE]≈E[MAE] for direction-blind states",
        },
    ))
    recs.append(EvidenceRecord(
        question="state value scope",
        surface="clean_labels",
        n=n,
        effect_name="not_win_rate",
        effect_size=0.0,
        confidence="CERTAIN",
        candidate_finding=(
            "e_tp1/e_tp2 are expected hit indicators on stored labels, reported as "
            "value components, not as a strategy win rate. No G001."
        ),
    ))
    return recs


# ── 3. Asymmetry atlas ──────────────────────────────────────────────────────
def _pair_sides(cols: dict[str, list]) -> list[tuple[int, int, str]]:
    ts = _ts_series(cols)
    side = [str(s or "").lower() for s in _side_series(cols)]
    by: dict[str, dict[str, int]] = {}
    for i, t in enumerate(ts):
        key = str(t)
        by.setdefault(key, {})[side[i] if i < len(side) else ""] = i
    pairs: list[tuple[int, int, str]] = []
    for t, d in by.items():
        if "long" in d and "short" in d:
            pairs.append((d["long"], d["short"], t))
    return pairs


def asymmetry_atlas(cols: dict[str, list]) -> list[EvidenceRecord]:
    pairs = _pair_sides(cols)
    mfe = _as_float_y(_col(cols, "y_mfe_r", "path_mfe_r") or [])
    mae = _as_float_y(_col(cols, "y_mae_r_heat", "path_mae_r_heat") or [])
    tp1 = _as_float_y(_y_tp1(cols)) if _col(cols, "y_tp1") is not None else []
    n_pairs = len(pairs)
    if n_pairs < 30:
        return [EvidenceRecord(
            question="asymmetry atlas",
            surface="clean_labels",
            n=n_pairs,
            effect_name="paired_timestamps",
            effect_size=None,
            confidence="INSUFFICIENT",
            candidate_finding=f"Need paired long+short at the same timestamp; got {n_pairs}.",
        )]

    def _delta(series: list, li: int, si: int) -> float | None:
        if li >= len(series) or si >= len(series):
            return None
        a, b = series[li], series[si]
        if a is None or b is None:
            return None
        return float(a) - float(b)

    d_mfe = [d for li, si, _ in pairs if (d := _delta(mfe, li, si)) is not None]
    d_mae = [d for li, si, _ in pairs if (d := _delta(mae, li, si)) is not None]
    d_tp1 = [d for li, si, _ in pairs if (d := _delta(tp1, li, si)) is not None]
    e_dmfe = _mean(d_mfe)
    pos = sum(1 for x in d_mfe if x > 0) / len(d_mfe) if d_mfe else None
    recs = [
        EvidenceRecord(
            question="asymmetry: Long MFE − Short MFE (unconditional)",
            surface="clean_labels",
            n=len(d_mfe),
            effect_name="e_long_mfe_minus_short_mfe",
            effect_size=e_dmfe,
            confidence=descriptive_confidence(len(d_mfe)),
            candidate_finding=(
                f"Paired timestamps n={n_pairs}. E[MFE_L−MFE_S]={e_dmfe}; "
                f"P(ΔMFE>0)={pos}; median={_pct(d_mfe, 50)}. "
                "Same-bar both-sides grain. Directional path information, not a trade."
            ),
            extra={
                "n_pairs": n_pairs,
                "p_delta_mfe_gt_0": pos,
                "median": _pct(d_mfe, 50),
                "p10": _pct(d_mfe, 10),
                "p90": _pct(d_mfe, 90),
                "e_delta_mae": _mean(d_mae),
                "e_delta_tp1": _mean(d_tp1),
            },
        )
    ]
    # Condition on t=0 discrete state (shared across sides — read the long row).
    for col, label in _STATE_COLS:
        if label == "side":
            continue
        if col not in cols:
            continue
        buckets: dict[str, list[float]] = defaultdict(list)
        for li, si, _t in pairs:
            d = _delta(mfe, li, si)
            if d is None:
                continue
            buckets[_flag_level(label, cols[col][li])].append(d)
        cells = []
        means = []
        for level, vs in sorted(buckets.items(), key=lambda kv: -len(kv[1])):
            if len(vs) < 30:
                continue
            mu = _mean(vs)
            cells.append({
                "state": f"{label}={level}",
                "n": len(vs),
                "e_delta_mfe": mu,
                "excess_vs_uncond": None if mu is None or e_dmfe is None else mu - e_dmfe,
                "p_delta_gt_0": sum(1 for x in vs if x > 0) / len(vs),
            })
            if mu is not None:
                means.append(mu)
        spread = (max(means) - min(means)) if len(means) >= 2 else 0.0
        recs.append(EvidenceRecord(
            question=f"asymmetry given {label}",
            surface="clean_labels",
            n=n_pairs,
            effect_name="delta_mfe_spread_across_cells",
            effect_size=spread,
            confidence=contrast_confidence(n_pairs, abs(spread), floor=0.05),
            candidate_finding=(
                f"{label}: E[MFE_L−MFE_S] spread={spread:.4f} across {len(cells)} cells. "
                "Excess vs unconditional is the directional association."
            ),
            extra={"cells": cells, "unconditional_e_delta_mfe": e_dmfe},
        ))
    recs.append(EvidenceRecord(
        question="asymmetry atlas scope",
        surface="clean_labels",
        n=n_pairs,
        effect_name="paired_grain",
        effect_size=float(n_pairs),
        confidence="CERTAIN",
        candidate_finding=(
            "Asymmetry uses the bar×direction grain the ledger actually has. "
            "It does not use CRT TRADE_OPENED. Information ≠ value ≠ authority."
        ),
    ))
    return recs
