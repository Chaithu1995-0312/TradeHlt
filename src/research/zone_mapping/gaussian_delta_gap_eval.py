"""
H-GAUSS-DELTA-001 — calibration gap Δ = ML − H evaluation (measure-only).

Implements the frozen protocol in:
  docs/research-readiness/h-gauss-delta-001-preregistration.md

Primary signal: signed delta = score_ml - score_h
NOT consensus / coordinator. No fusion authority.

Reuses dual-score bar collection from gaussian_family_shadow_eval.
"""
from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from research.contracts import Signal
from research.costs import DEFAULT_COST_MODEL, CostModel
from research.measurement.forward_walk import forward_walk
from research.zone_mapping.gaussian_family_shadow_eval import (
    AGREE_THR,
    GaussianShadowBar,
    _BarView,
    _load_candles,
    collect_gaussian_shadow_bars,
)
from research.zone_mapping.rare_zone_detection_eval import RARE_ZONES
from config_layer.crt_engine_v2 import Candle

SCHEMA_VERSION = "h_gauss_delta_001_v1"
PROGRAM = "H-GAUSS-DELTA-001"
OOS_FRACTION = 0.30
MIN_N_OOS = 100
N_PERM = 1000
PERM_SEED = 42
BH_Q = 0.10
SL_ATR = 1.0
TP_ATR = 2.0
MAX_FORWARD = 40

PRIMARY_STRATA = (
    "S-RARE_ZONE",
    "S-RARE_ENTRY",
    "S-BOUNDARY",
    "S-DISPLACEMENT",
)
DIAGNOSTIC_STRATA = (
    "S-ALL",
    "S-RARE_ENTRY_x_DISPLACEMENT",
    "S-BOUNDARY_x_DISPLACEMENT",
)


def _mean(xs: Sequence[float]) -> Optional[float]:
    return float(sum(xs) / len(xs)) if xs else None


def _spearman(xs: Sequence[float], ys: Sequence[float]) -> Optional[float]:
    """Spearman rank correlation (average ranks for ties)."""
    n = len(xs)
    if n < 3 or n != len(ys):
        return None
    rx = _ranks(xs)
    ry = _ranks(ys)
    return _pearson(rx, ry)


def _ranks(vals: Sequence[float]) -> list[float]:
    n = len(vals)
    order = sorted(range(n), key=lambda i: vals[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0  # 1-based average rank
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _pearson(xs: Sequence[float], ys: Sequence[float]) -> Optional[float]:
    n = len(xs)
    if n < 3:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx <= 0 or dy <= 0:
        return None
    return float(num / (dx * dy))


def _percentile(sorted_vals: Sequence[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    idx = min(len(sorted_vals) - 1, max(0, int(round(p * (len(sorted_vals) - 1)))))
    return float(sorted_vals[idx])


def _tercile_edges(values: Sequence[float]) -> tuple[float, float]:
    s = sorted(values)
    if not s:
        return (0.0, 1.0)
    return (_percentile(s, 1.0 / 3.0), _percentile(s, 2.0 / 3.0))


def _ols_residual_coeffs(
    x: Sequence[float], y: Sequence[float]
) -> tuple[float, float]:
    """Return (intercept, slope) for y ~ a + b x. Degenerate → (mean(y), 0)."""
    n = len(x)
    if n < 2 or n != len(y):
        return (0.0, 0.0)
    mx = sum(x) / n
    my = sum(y) / n
    varx = sum((xi - mx) ** 2 for xi in x)
    if varx <= 1e-18:
        return (my, 0.0)
    cov = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    b = cov / varx
    a = my - b * mx
    return (a, b)


def _apply_residual(
    y: Sequence[float], x: Sequence[float], a: float, b: float
) -> list[float]:
    return [yi - (a + b * xi) for yi, xi in zip(y, x)]


def _bh_significant(p_values: Sequence[Optional[float]], q: float = BH_Q) -> list[bool]:
    """Benjamini–Hochberg; None p → not significant."""
    indexed = [(i, p) for i, p in enumerate(p_values) if p is not None]
    out = [False] * len(p_values)
    m = len(indexed)
    if m == 0:
        return out
    indexed.sort(key=lambda t: t[1])
    thresh_rank = -1
    for rank, (i, p) in enumerate(indexed, start=1):
        if p <= (rank / m) * q:
            thresh_rank = rank
    if thresh_rank < 0:
        return out
    for rank, (i, p) in enumerate(indexed, start=1):
        if rank <= thresh_rank:
            out[i] = True
    return out


def _perm_spearman_p(
    x: Sequence[float],
    y: Sequence[float],
    *,
    n_perm: int = N_PERM,
    seed: int = PERM_SEED,
) -> tuple[Optional[float], Optional[float]]:
    """Two-sided perm p for Spearman(x,y); returns (rho, p)."""
    rho = _spearman(x, y)
    if rho is None:
        return (None, None)
    rng = random.Random(seed)
    y_list = list(y)
    abs_rho = abs(rho)
    ge = 0
    for _ in range(n_perm):
        rng.shuffle(y_list)
        r = _spearman(x, y_list)
        if r is not None and abs(r) >= abs_rho:
            ge += 1
    p = (ge + 1) / (n_perm + 1)
    return (rho, p)


@dataclass(frozen=True)
class _Row:
    bar: GaussianShadowBar
    net_r: float
    is_oos: bool


def _filter_stratum(
    bars: Sequence[GaussianShadowBar],
    stratum: str,
    *,
    boundary_ids: Optional[set[int]] = None,
) -> list[GaussianShadowBar]:
    """
    Filter bars into a geometry stratum.

    ``boundary_ids`` — bar_pos set labeled BOUNDARY using **IS-fit** margin Q1
    edges (protocol §4). If None, falls back to collector full-sample flag
    (exploratory only; primary runs should pass IS-fit ids).
    """
    s = stratum.upper()

    def _dir_ok(b: GaussianShadowBar) -> bool:
        return b.direction != 0 and b.atr_price > 0

    def _is_boundary(b: GaussianShadowBar) -> bool:
        if boundary_ids is not None:
            return b.bar_pos in boundary_ids
        return bool(b.is_boundary)

    if s == "S-ALL":
        return [b for b in bars if _dir_ok(b)]
    if s == "S-RARE_ZONE":
        return [b for b in bars if b.is_rare_zone and _dir_ok(b)]
    if s == "S-RARE_ENTRY":
        return [b for b in bars if b.is_rare_entry and _dir_ok(b)]
    if s == "S-BOUNDARY":
        return [b for b in bars if _is_boundary(b) and _dir_ok(b)]
    if s == "S-DISPLACEMENT":
        return [b for b in bars if b.crt_state == "DISPLACEMENT" and _dir_ok(b)]
    if s == "S-RARE_ENTRY_X_DISPLACEMENT":
        return [
            b
            for b in bars
            if b.is_rare_entry and b.crt_state == "DISPLACEMENT" and _dir_ok(b)
        ]
    if s == "S-BOUNDARY_X_DISPLACEMENT":
        return [
            b
            for b in bars
            if _is_boundary(b) and b.crt_state == "DISPLACEMENT" and _dir_ok(b)
        ]
    raise ValueError(f"unknown stratum {stratum!r}")


def _boundary_ids_is_fit(bars: Sequence[GaussianShadowBar]) -> set[int]:
    """
    Label BOUNDARY using margin Q1 edges fit on the first 70% of directional bars
    (time-ordered), applied to the full series — matches prereg §4 / §5 OOS rule.
    """
    directional = [b for b in bars if b.direction != 0 and b.atr_price > 0]
    if not directional:
        return set()
    mask = _time_split_mask(directional)
    is_margins = [
        b.margin_best_second for b, oos in zip(directional, mask) if not oos
    ]
    if not is_margins:
        return set()
    # Q1 upper edge of equal-count quintile on IS
    s = sorted(is_margins)
    # edge between bin0 and bin1 of 5 bins ≈ 20th percentile
    q1_hi = _percentile(s, 0.20)
    return {
        b.bar_pos
        for b in directional
        if b.margin_best_second <= q1_hi
    }


def _forward_net_r(
    bar: GaussianShadowBar,
    candles: Sequence[Candle],
    *,
    instrument: str,
    cost: CostModel = DEFAULT_COST_MODEL,
) -> Optional[float]:
    idx = bar.bar_pos
    if idx < 0 or idx >= len(candles) - 1:
        return None
    if bar.atr_price <= 0 or bar.direction == 0:
        return None
    direction = "long" if bar.direction > 0 else "short"
    future = [
        _BarView(j, candles[j].high, candles[j].low, candles[j].close)
        for j in range(idx + 1, min(len(candles), idx + 1 + MAX_FORWARD))
    ]
    entry_c = candles[idx]
    ts = entry_c.timestamp
    if not isinstance(ts, datetime):
        ts = datetime.fromisoformat(str(ts))
    sig = Signal(
        instrument=instrument,
        timestamp=ts,
        entry_index=idx,
        direction=direction,
        entry=float(bar.close),
        sl_atr_mult=SL_ATR,
        tp_atr_mult=TP_ATR,
        atr=float(bar.atr_price),
        meta={"delta": bar.delta, "score_h": bar.score_h, "score_ml": bar.score_ml},
    )
    try:
        out = forward_walk(
            sig, future, max_forward=MAX_FORWARD, exit_model="intrabar_fixed"
        )
    except ValueError:
        return None
    risk = SL_ATR * bar.atr_price
    return float(cost.net_rr(out.rr_achieved, bar.close, risk))


def _time_split_mask(bars: Sequence[GaussianShadowBar]) -> list[bool]:
    """True = OOS (last 30% by bar order / time)."""
    n = len(bars)
    if n == 0:
        return []
    cut = int(math.floor(n * (1.0 - OOS_FRACTION)))
    return [i >= cut for i in range(n)]


def _tercile_econ(
    deltas: Sequence[float],
    net_rs: Sequence[float],
    edges: tuple[float, float],
) -> dict[str, Any]:
    lo, hi = edges
    top = [r for d, r in zip(deltas, net_rs) if d >= hi]
    bot = [r for d, r in zip(deltas, net_rs) if d <= lo]
    e_top = _mean(top)
    e_bot = _mean(bot)
    return {
        "n_top": len(top),
        "n_bot": len(bot),
        "e_top": (round(e_top, 4) if e_top is not None else None),
        "e_bot": (round(e_bot, 4) if e_bot is not None else None),
        "delta_e_top_minus_bot": (
            round(e_top - e_bot, 4)
            if e_top is not None and e_bot is not None
            else None
        ),
        "edges": {"p33": lo, "p66": hi},
    }


def _score_tercile_econ(
    scores: Sequence[float],
    net_rs: Sequence[float],
) -> dict[str, Any]:
    edges = _tercile_edges(scores)
    return _tercile_econ(scores, net_rs, edges)


def evaluate_stratum(
    rows: Sequence[_Row],
    *,
    stratum: str,
    primary: bool,
) -> dict[str, Any]:
    """Evaluate one stratum on pre-built rows with net_r + OOS flags."""
    oos = [r for r in rows if r.is_oos]
    ins = [r for r in rows if not r.is_oos]
    n_oos = len(oos)
    n_is = len(ins)
    base: dict[str, Any] = {
        "stratum": stratum,
        "primary": primary,
        "n_is": n_is,
        "n_oos": n_oos,
        "insufficient": n_oos < MIN_N_OOS,
    }
    if n_oos < MIN_N_OOS or n_is < 10:
        base["verdict"] = "INSUFFICIENT"
        return base

    # IS fit residual coeffs: delta ~ a + b * score
    d_is = [r.bar.delta for r in ins]
    h_is = [r.bar.score_h for r in ins]
    ml_is = [r.bar.score_ml for r in ins]
    a_h, b_h = _ols_residual_coeffs(h_is, d_is)
    a_ml, b_ml = _ols_residual_coeffs(ml_is, d_is)

    d_oos = [r.bar.delta for r in oos]
    h_oos = [r.bar.score_h for r in oos]
    ml_oos = [r.bar.score_ml for r in oos]
    y_oos = [r.net_r for r in oos]
    abs_d_oos = [abs(d) for d in d_oos]

    res_h_oos = _apply_residual(d_oos, h_oos, a_h, b_h)
    res_ml_oos = _apply_residual(d_oos, ml_oos, a_ml, b_ml)

    # IS edges for Δ terciles applied to OOS
    d_edges = _tercile_edges(d_is)

    rho_d, p_d = _perm_spearman_p(d_oos, y_oos)
    rho_rh, p_rh = _perm_spearman_p(res_h_oos, y_oos)
    rho_rm, p_rm = _perm_spearman_p(res_ml_oos, y_oos)
    rho_h, p_h = _perm_spearman_p(h_oos, y_oos)
    rho_ml, p_ml = _perm_spearman_p(ml_oos, y_oos)
    rho_abs, p_abs = _perm_spearman_p(abs_d_oos, y_oos)

    terc_d = _tercile_econ(d_oos, y_oos, d_edges)
    terc_h = _score_tercile_econ(h_oos, y_oos)
    terc_ml = _score_tercile_econ(ml_oos, y_oos)

    base.update(
        {
            "mean_delta_oos": round(_mean(d_oos) or 0.0, 4),
            "mean_h_oos": round(_mean(h_oos) or 0.0, 4),
            "mean_ml_oos": round(_mean(ml_oos) or 0.0, 4),
            "residual_fit_is": {
                "delta_on_h": {"intercept": a_h, "slope": b_h},
                "delta_on_ml": {"intercept": a_ml, "slope": b_ml},
            },
            "tests": {
                "T-SP-D": {
                    "rho": (round(rho_d, 4) if rho_d is not None else None),
                    "p_perm": (round(p_d, 4) if p_d is not None else None),
                },
                "T-SP-RES-H": {
                    "rho": (round(rho_rh, 4) if rho_rh is not None else None),
                    "p_perm": (round(p_rh, 4) if p_rh is not None else None),
                },
                "T-SP-RES-ML": {
                    "rho": (round(rho_rm, 4) if rho_rm is not None else None),
                    "p_perm": (round(p_rm, 4) if p_rm is not None else None),
                },
                "T-TERC-D": terc_d,
                "baseline_h": {
                    "rho": (round(rho_h, 4) if rho_h is not None else None),
                    "p_perm": (round(p_h, 4) if p_h is not None else None),
                    "tercile": terc_h,
                },
                "baseline_ml": {
                    "rho": (round(rho_ml, 4) if rho_ml is not None else None),
                    "p_perm": (round(p_ml, 4) if p_ml is not None else None),
                    "tercile": terc_ml,
                },
                "baseline_abs_delta": {
                    "rho": (round(rho_abs, 4) if rho_abs is not None else None),
                    "p_perm": (round(p_abs, 4) if p_abs is not None else None),
                },
            },
        }
    )
    # Provisional cell verdict before BH (BH applied at instrument rollup)
    base["provisional"] = {
        "terc_d_positive": bool(
            (terc_d.get("delta_e_top_minus_bot") or 0) > 0
        ),
        "top_delta_e_positive": bool((terc_d.get("e_top") or 0) > 0),
        "beats_h_top": (
            terc_d.get("e_top") is not None
            and terc_h.get("e_top") is not None
            and terc_d["e_top"] > terc_h["e_top"]
        ),
        "beats_ml_top": (
            terc_d.get("e_top") is not None
            and terc_ml.get("e_top") is not None
            and terc_d["e_top"] > terc_ml["e_top"]
        ),
    }
    return base


def _apply_bh_and_claims(stratum_results: list[dict[str, Any]]) -> dict[str, Any]:
    """BH over primary cells' residual p-values; attach claim labels."""
    primary = [s for s in stratum_results if s.get("primary") and not s.get("insufficient")]
    # Family: each primary stratum contributes T-SP-RES-H and T-SP-RES-ML p-values
    family: list[tuple[str, str, Optional[float]]] = []
    for s in primary:
        tests = s.get("tests") or {}
        family.append(
            (s["stratum"], "T-SP-RES-H", (tests.get("T-SP-RES-H") or {}).get("p_perm"))
        )
        family.append(
            (s["stratum"], "T-SP-RES-ML", (tests.get("T-SP-RES-ML") or {}).get("p_perm"))
        )
    ps = [p for _, _, p in family]
    sig = _bh_significant(ps, BH_Q)
    sig_map: dict[tuple[str, str], bool] = {}
    for (stratum, test_id, _), ok in zip(family, sig):
        sig_map[(stratum, test_id)] = ok

    claims: dict[str, Any] = {}
    any_informative = False
    any_consumable = False
    for s in stratum_results:
        sid = s["stratum"]
        if s.get("insufficient"):
            claims[sid] = "INSUFFICIENT"
            s["claim"] = "INSUFFICIENT"
            continue
        if not s.get("primary"):
            claims[sid] = "DIAGNOSTIC_ONLY"
            s["claim"] = "DIAGNOSTIC_ONLY"
            continue
        res_h_sig = sig_map.get((sid, "T-SP-RES-H"), False)
        res_ml_sig = sig_map.get((sid, "T-SP-RES-ML"), False)
        prov = s.get("provisional") or {}
        residual_ok = res_h_sig or res_ml_sig
        terc_ok = bool(prov.get("terc_d_positive"))
        if residual_ok and terc_ok:
            if (
                prov.get("top_delta_e_positive")
                and prov.get("beats_h_top")
                and prov.get("beats_ml_top")
            ):
                claim = "CONSUMABLE_RESEARCH_ONLY"
                any_consumable = True
            else:
                claim = "INFORMATIVE_NOT_CONSUMABLE"
            any_informative = True
        else:
            claim = "NULL_CELL"
        claims[sid] = claim
        s["claim"] = claim
        s["bh"] = {
            "T-SP-RES-H_sig": res_h_sig,
            "T-SP-RES-ML_sig": res_ml_sig,
            "q": BH_Q,
        }

    if any_consumable:
        program_verdict = "CONSUMABLE_CANDIDATE_RESEARCH_ONLY"
    elif any_informative:
        program_verdict = "INFORMATIVE_NOT_CONSUMABLE"
    elif all(
        s.get("insufficient") for s in stratum_results if s.get("primary")
    ):
        program_verdict = "ALL_INSUFFICIENT"
    else:
        program_verdict = "H0_UPHELD_NULL"

    return {
        "cell_claims": claims,
        "program_verdict": program_verdict,
        "bh_family_size": len(family),
        "bh_q": BH_Q,
        "coordinator_authorized": False,
        "fusion_wire_authorized": False,
        "gaussian_impl_flip_authorized": False,
    }


def evaluate_instrument(
    bars: Sequence[GaussianShadowBar],
    candles: Sequence[Candle],
    *,
    instrument: str,
) -> dict[str, Any]:
    """Full H-GAUSS-DELTA-001 evaluation for one instrument."""
    # ML readiness
    n = len(bars)
    n_fb = sum(1 for b in bars if b.ml_reason == "ml_gaussian_fallback")
    fb_rate = (n_fb / n) if n else 1.0
    if n == 0 or fb_rate > 0.01:
        return {
            "schema_version": SCHEMA_VERSION,
            "program": PROGRAM,
            "instrument": instrument,
            "skipped": True,
            "skip_reason": f"ml_fallback_rate={fb_rate:.4f} or empty",
            "authority": "research_only",
            "production_behavior_changed": False,
        }

    # Precompute net_r for all directional bars once
    net_cache: dict[int, float] = {}
    for b in bars:
        if b.direction == 0 or b.atr_price <= 0:
            continue
        nr = _forward_net_r(b, candles, instrument=instrument)
        if nr is not None:
            net_cache[b.bar_pos] = nr

    boundary_ids = _boundary_ids_is_fit(bars)

    stratum_results: list[dict[str, Any]] = []
    all_strata = list(PRIMARY_STRATA) + list(DIAGNOSTIC_STRATA)
    for sid in all_strata:
        subset = _filter_stratum(bars, sid, boundary_ids=boundary_ids)
        # time split within stratum (ordered as collected = time order)
        mask = _time_split_mask(subset)
        rows: list[_Row] = []
        for b, is_oos in zip(subset, mask):
            if b.bar_pos not in net_cache:
                continue
            rows.append(_Row(bar=b, net_r=net_cache[b.bar_pos], is_oos=is_oos))
        primary = sid in PRIMARY_STRATA
        stratum_results.append(
            evaluate_stratum(rows, stratum=sid, primary=primary)
        )

    gate = _apply_bh_and_claims(stratum_results)

    return {
        "schema_version": SCHEMA_VERSION,
        "program": PROGRAM,
        "instrument": instrument,
        "skipped": False,
        "authority": "research_only",
        "production_behavior_changed": False,
        "n_bars_scored": n,
        "ml_fallback_rate": round(fb_rate, 4),
        "agree_threshold_note": (
            f"binary thr={AGREE_THR} is NOT a primary metric in this program"
        ),
        "protocol": {
            "oos_fraction": OOS_FRACTION,
            "min_n_oos": MIN_N_OOS,
            "n_perm": N_PERM,
            "perm_seed": PERM_SEED,
            "bh_q": BH_Q,
            "sl_atr_mult": SL_ATR,
            "tp_atr_mult": TP_ATR,
            "max_forward": MAX_FORWARD,
            "cost_bps": DEFAULT_COST_MODEL.round_trip_bps,
            "exit_model": "intrabar_fixed",
            "primary_signal": "delta = score_ml - score_h",
            "rare_zones": list(RARE_ZONES),
        },
        "strata": stratum_results,
        "gate": gate,
        "notes": [
            "H-GAUSS-DELTA-001 measure-only; no GaussianCoordinator.",
            "Primary evidence is OOS residual Spearman + Δ tercile lift under BH.",
            "BNBUSDT full-sample shadow pilot is non-primary exploratory.",
        ],
    }


def run_from_csv(
    csv_path: str,
    *,
    instrument: str,
    max_bars: int = 0,
    progress_every: int = 10000,
) -> dict[str, Any]:
    bars = collect_gaussian_shadow_bars(
        csv_path,
        instrument=instrument,
        max_bars=max_bars,
        progress_every=progress_every,
    )
    candles = _load_candles(csv_path)
    rep = evaluate_instrument(bars, candles, instrument=instrument)
    rep["csv_path"] = str(csv_path)
    return rep


def report_to_markdown(rep: Mapping[str, Any], *, title: str = "") -> str:
    inst = rep.get("instrument", "?")
    title = title or f"{PROGRAM} — {inst}"
    lines = [
        f"# {title}",
        "",
        f"**Program:** `{rep.get('program')}`  ·  **Schema:** `{rep.get('schema_version')}`",
        f"**Authority:** research only  ·  **PRODUCTION_BEHAVIOR_CHANGED:** "
        f"{rep.get('production_behavior_changed')}",
        "",
    ]
    if rep.get("skipped"):
        lines.append(f"**SKIPPED:** {rep.get('skip_reason')}")
        lines.append("")
        return "\n".join(lines)

    gate = rep.get("gate") or {}
    lines.extend(
        [
            f"**Program verdict:** `{gate.get('program_verdict')}`",
            f"**Coordinator authorized:** `{gate.get('coordinator_authorized')}` "
            f"· **Fusion wire:** `{gate.get('fusion_wire_authorized')}` "
            f"· **ML flip:** `{gate.get('gaussian_impl_flip_authorized')}`",
            "",
            f"Bars scored: {rep.get('n_bars_scored')}  ·  ML fallback: {rep.get('ml_fallback_rate')}",
            f"CSV: `{rep.get('csv_path', '')}`",
            "",
            "## Cell claims",
            "",
            "| stratum | claim | n_oos | T-SP-RES-H p | T-SP-RES-ML p | Δ tercile lift |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for s in rep.get("strata") or []:
        tests = s.get("tests") or {}
        rh = (tests.get("T-SP-RES-H") or {}).get("p_perm")
        rm = (tests.get("T-SP-RES-ML") or {}).get("p_perm")
        lift = (tests.get("T-TERC-D") or {}).get("delta_e_top_minus_bot")
        lines.append(
            f"| {s.get('stratum')} | {s.get('claim')} | {s.get('n_oos')} | "
            f"{rh} | {rm} | {lift} |"
        )

    lines.extend(["", "## Primary strata detail (OOS)", ""])
    for s in rep.get("strata") or []:
        if not s.get("primary"):
            continue
        lines.append(f"### {s.get('stratum')} — `{s.get('claim')}`")
        if s.get("insufficient"):
            lines.append("")
            lines.append(f"INSUFFICIENT (n_oos={s.get('n_oos')})")
            lines.append("")
            continue
        tests = s.get("tests") or {}
        lines.append("")
        lines.append(
            f"- mean Δ OOS: {s.get('mean_delta_oos')}  ·  H: {s.get('mean_h_oos')}  ·  "
            f"ML: {s.get('mean_ml_oos')}"
        )
        for tid in ("T-SP-D", "T-SP-RES-H", "T-SP-RES-ML"):
            t = tests.get(tid) or {}
            lines.append(f"- {tid}: rho={t.get('rho')} p_perm={t.get('p_perm')}")
        td = tests.get("T-TERC-D") or {}
        lines.append(
            f"- T-TERC-D: e_top={td.get('e_top')} e_bot={td.get('e_bot')} "
            f"lift={td.get('delta_e_top_minus_bot')} (n_top={td.get('n_top')}, "
            f"n_bot={td.get('n_bot')})"
        )
        bh = s.get("bh") or {}
        lines.append(
            f"- BH: RES-H_sig={bh.get('T-SP-RES-H_sig')} "
            f"RES-ML_sig={bh.get('T-SP-RES-ML_sig')}"
        )
        lines.append("")

    lines.extend(
        [
            "## Notes",
            "",
            "- Primary signal is **signed Δ = ML − H**, not consensus.",
            "- No GaussianCoordinator; no production wire.",
            "- See prereg: `docs/research-readiness/h-gauss-delta-001-preregistration.md`.",
            "",
        ]
    )
    return "\n".join(lines)
