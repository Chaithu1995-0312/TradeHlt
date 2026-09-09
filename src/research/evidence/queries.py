"""Named evidence queries over column maps.

Input is a dict[str, list] of equal length (already flattened `features.*` keys).
Output is EvidenceRecord list. No model. No re-detection. No new market formula.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean, median
from typing import Any, Iterable, Sequence

from research.evidence.catalog import (
    CONTAMINATED_FEATURES,
    OHLC_LEVEL_FEATURES,
    assert_join,
)
from research.evidence.records import (
    EvidenceRecord,
    contrast_confidence,
    descriptive_confidence,
)

FORBIDDEN_PRIMARY_Y = (
    "outcome",
    "rr_achieved",
    "diagnostics.stream_outcome",
    "diagnostics.stream_rr_achieved",
    "diagnostics.stream_y_tp1",
)


def _finite_at(vals: Sequence[Any]) -> list[tuple[int, float]]:
    out: list[tuple[int, float]] = []
    for i, v in enumerate(vals):
        if v is None:
            continue
        try:
            x = float(v)
        except (TypeError, ValueError):
            continue
        if x == x:
            out.append((i, x))
    return out


def _mean(xs: Iterable[float]) -> float | None:
    seq = list(xs)
    return mean(seq) if seq else None


def _pct(xs: Sequence[float], p: float) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * (p / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    frac = k - lo
    return s[lo] + (s[hi] - s[lo]) * frac


def _col(cols: dict[str, list], *names: str) -> list | None:
    for n in names:
        if n in cols:
            return cols[n]
    return None


def _y_tp1(cols: dict[str, list]) -> list:
    y = _col(cols, "y_tp1")
    if y is None:
        raise KeyError("clean_labels y_tp1 is required; refusing stream outcome as y")
    return y


def _as_float_y(y: Sequence[Any]) -> list[float | None]:
    out: list[float | None] = []
    for v in y:
        if v is None:
            out.append(None)
            continue
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            out.append(None)
    return out


def flatten_row(row: dict) -> dict:
    """Lift nested `features` / `diagnostics` so queries see `features.atr` keys."""
    out = dict(row)
    feat = row.get("features")
    if isinstance(feat, dict):
        for k, v in feat.items():
            out.setdefault(f"features.{k}", v)
    diag = row.get("diagnostics")
    if isinstance(diag, dict):
        for k, v in diag.items():
            out.setdefault(f"diagnostics.{k}", v)
    return out


def rows_to_cols(rows: Sequence[dict]) -> dict[str, list]:
    flat = [flatten_row(r) for r in rows]
    keys: set[str] = set()
    for r in flat:
        keys.update(r)
    cols: dict[str, list] = {k: [] for k in keys}
    for r in flat:
        for k in keys:
            cols[k].append(r.get(k))
    return cols


def join_ledger(opp_rows: Sequence[dict], lab_rows: Sequence[dict]) -> list[dict]:
    """Legal 1:1 join of opportunities geometry onto clean_labels identity."""
    assert_join("opportunities", "clean_labels")
    from research.evidence.catalog import identity_tuple

    labs = {identity_tuple(flatten_row(r), "clean_labels"): flatten_row(r) for r in lab_rows}
    joined: list[dict] = []
    for raw in opp_rows:
        o = flatten_row(raw)
        lab = labs.get(identity_tuple(o, "opportunities"))
        if lab is None:
            continue
        merged = dict(o)
        merged.update(lab)
        # geometry aliases
        merged.setdefault("direction", merged.get("side"))
        joined.append(merged)
    return joined


def join_cols(opp_cols: dict[str, list], lab_cols: dict[str, list]) -> dict[str, list]:
    """Same legal join as join_ledger, over already-flattened column maps."""
    assert_join("opportunities", "clean_labels")
    ts = lab_cols.get("decision_ts") or lab_cols.get("timestamp") or []
    inst = lab_cols.get("instrument") or []
    side = lab_cols.get("side") or lab_cols.get("direction") or []
    index: dict[tuple, int] = {}
    for i in range(len(ts)):
        index[(str(ts[i]), str(inst[i] if i < len(inst) else ""), str(side[i] if i < len(side) else "").lower())] = i
    ots = opp_cols.get("timestamp") or opp_cols.get("decision_ts") or []
    oinst = opp_cols.get("instrument") or []
    odir = opp_cols.get("direction") or opp_cols.get("side") or []
    keep_o: list[int] = []
    keep_l: list[int] = []
    for i in range(len(ots)):
        key = (
            str(ots[i]),
            str(oinst[i] if i < len(oinst) else ""),
            str(odir[i] if i < len(odir) else "").lower(),
        )
        j = index.get(key)
        if j is None:
            continue
        keep_o.append(i)
        keep_l.append(j)
    merged: dict[str, list] = {}
    for k, v in opp_cols.items():
        merged[k] = [v[i] for i in keep_o]
    for k, v in lab_cols.items():
        if k not in merged:
            merged[k] = [v[j] for j in keep_l]
    return merged


# ── 1. Feature effectiveness census ─────────────────────────────────────────
def feature_effectiveness(cols: dict[str, list]) -> list[EvidenceRecord]:
    y = _as_float_y(_y_tp1(cols))
    n = len(y)
    recs: list[EvidenceRecord] = []
    feat_names = sorted(
        k[len("features."):]
        for k in cols
        if k.startswith("features.") and k[len("features."):] not in OHLC_LEVEL_FEATURES
    )
    ranked: list[tuple[float, EvidenceRecord]] = []
    for name in feat_names:
        series = cols[f"features.{name}"]
        pairs = [(i, x) for i, x in _finite_at(series) if y[i] is not None]
        coverage = len(pairs) / n if n else 0.0
        if len(pairs) < 30:
            recs.append(EvidenceRecord(
                question=f"feature effectiveness: {name}",
                surface="clean_labels",
                n=len(pairs),
                effect_name="coverage",
                effect_size=coverage,
                confidence="INSUFFICIENT",
                candidate_finding=f"{name} coverage={coverage:.3f} n={len(pairs)} — too small to contrast.",
                extra={"feature": name, "contaminated": name in CONTAMINATED_FEATURES},
            ))
            continue
        vals = [p[1] for p in pairs]
        ys = [float(y[p[0]]) for p in pairs]
        unique = sorted(set(vals))
        extra = {
            "feature": name,
            "coverage": round(coverage, 4),
            "p10": _pct(vals, 10),
            "p90": _pct(vals, 90),
            "contaminated": CONTAMINATED_FEATURES.get(name),
        }
        if len(unique) <= 6:
            buckets: dict[float, list[float]] = defaultdict(list)
            for v, yy in zip(vals, ys):
                buckets[v].append(yy)
            levels = {
                str(k): {"n": len(vs), "y_tp1": round(_mean(vs) or 0.0, 4)}
                for k, vs in sorted(buckets.items(), key=lambda kv: -len(kv[1]))
            }
            powered = [c["y_tp1"] for c in levels.values() if c["n"] >= 30]
            delta = (max(powered) - min(powered)) if len(powered) >= 2 else 0.0
            extra["levels"] = levels
            extra["split"] = "categorical"
            effect_name = "y_tp1_spread_across_levels"
        else:
            med = median(vals)
            hi = [yy for v, yy in zip(vals, ys) if v > med]
            lo = [yy for v, yy in zip(vals, ys) if v <= med]
            r_hi = _mean(hi) or 0.0
            r_lo = _mean(lo) or 0.0
            delta = r_hi - r_lo
            extra.update({
                "n_hi": len(hi),
                "n_lo": len(lo),
                "median": med,
                "y_tp1_hi": round(r_hi, 4),
                "y_tp1_lo": round(r_lo, 4),
                "split": "median",
            })
            effect_name = "y_tp1_hi_minus_lo"
        caveats = []
        if name in CONTAMINATED_FEATURES:
            caveats.append(CONTAMINATED_FEATURES[name])
        if extra.get("split") == "categorical":
            finding = (
                f"{name}: coverage={coverage:.3f}, categorical spread Δy_tp1={delta:+.4f} "
                f"across {len(extra['levels'])} levels."
            )
        else:
            finding = (
                f"{name}: coverage={coverage:.3f}, median-split Δy_tp1={delta:+.4f} "
                f"(hi {extra['y_tp1_hi']:.3f} n={extra['n_hi']} / lo {extra['y_tp1_lo']:.3f} n={extra['n_lo']})."
            )
        if name in CONTAMINATED_FEATURES:
            finding += " CONTAMINATED — not skill evidence."
        rec = EvidenceRecord(
            question=f"feature effectiveness: {name}",
            surface="clean_labels",
            n=len(pairs),
            effect_name=effect_name,
            effect_size=delta,
            confidence=contrast_confidence(len(pairs), abs(delta)),
            candidate_finding=finding,
            caveats=caveats,
            extra=extra,
        )
        ranked.append((abs(delta), rec))
    ranked.sort(key=lambda t: t[0], reverse=True)
    recs.extend(r for _, r in ranked)
    recs.insert(0, EvidenceRecord(
        question="feature effectiveness census",
        surface="clean_labels",
        n=n,
        effect_name="features_enumerated",
        effect_size=float(len(feat_names)),
        confidence=descriptive_confidence(n),
        candidate_finding=(
            f"Enumerated {len(feat_names)} non-OHLC features on n={n}. "
            "Largest |Δy_tp1| is evidence of association, not of a model."
        ),
        extra={"features": feat_names, "top": [r.extra.get("feature") for _, r in ranked[:8]]},
    ))
    return recs


# ── 2. Regime discovery ─────────────────────────────────────────────────────
_REGIME_COLS = (
    ("features.session", "session"),
    ("features.volatility_regime", "volatility"),
    ("features.hour_of_day", "hour"),
    ("features.trend_bias", "trend_bias"),
    ("side", "side"),
    ("direction", "side"),
)


def regime_discovery(cols: dict[str, list]) -> list[EvidenceRecord]:
    y = _as_float_y(_y_tp1(cols))
    n = len(y)
    recs: list[EvidenceRecord] = []
    seen_side = False
    for col, label in _REGIME_COLS:
        if col not in cols:
            continue
        if label == "side" and seen_side:
            continue
        if label == "side":
            seen_side = True
        buckets: dict[str, list[float]] = defaultdict(list)
        for i, raw in enumerate(cols[col]):
            if y[i] is None:
                continue
            buckets[str(raw)].append(float(y[i]))
        cells = {
            k: {"n": len(vs), "y_tp1": round(_mean(vs) or 0.0, 4)}
            for k, vs in sorted(buckets.items(), key=lambda kv: -len(kv[1]))
        }
        rates = [c["y_tp1"] for c in cells.values() if c["n"] >= 30]
        spread = (max(rates) - min(rates)) if len(rates) >= 2 else 0.0
        recs.append(EvidenceRecord(
            question=f"regime: {label}",
            surface="clean_labels",
            n=n,
            effect_name="y_tp1_spread_across_cells",
            effect_size=spread,
            confidence=contrast_confidence(n, spread),
            candidate_finding=(
                f"{label} cells={len(cells)}, y_tp1 spread={spread:.4f}. "
                "Existing columns only — no new clustering."
            ),
            extra={"cells": cells},
        ))
    return recs


# ── 3. Opportunity quality ──────────────────────────────────────────────────
def opportunity_quality(cols: dict[str, list]) -> list[EvidenceRecord]:
    y = _as_float_y(_y_tp1(cols))
    mfe = _col(cols, "y_mfe_r", "path_mfe_r")
    reached_1 = _col(cols, "y_reached_1r_horizon", "y_survives_be")
    mae = _col(cols, "y_mae_r_heat", "path_mae_r_heat")
    net = _col(cols, "y_R_net")
    n = len(y)
    if mfe is None or reached_1 is None:
        return [EvidenceRecord(
            question="opportunity quality",
            surface="clean_labels",
            n=n,
            effect_name="missing_path_labels",
            effect_size=None,
            confidence="INSUFFICIENT",
            candidate_finding="MFE / reached-1R columns absent — cannot separate quality from outcome.",
        )]
    mfe_f = _as_float_y(mfe)
    r1 = _as_float_y(reached_1)
    mae_f = _as_float_y(mae) if mae is not None else [None] * n
    net_f = _as_float_y(net) if net is not None else [None] * n

    loss_large_mfe = sum(
        1 for i in range(n)
        if y[i] == 0.0 and mfe_f[i] is not None and mfe_f[i] >= 1.0
    )
    high_mfe_low_tp = sum(
        1 for i in range(n)
        if (r1[i] == 1.0 or (mfe_f[i] is not None and mfe_f[i] >= 1.0)) and y[i] == 0.0
    )
    wins = sum(1 for i in range(n) if y[i] == 1.0)
    wins_deep_mae = sum(
        1 for i in range(n)
        if y[i] == 1.0 and mae_f[i] is not None and mae_f[i] >= 0.8
    )
    high_tp_low_r = sum(
        1 for i in range(n)
        if y[i] == 1.0 and net_f[i] is not None and net_f[i] <= 0.0
    )
    slices = {
        "losses_with_mfe_ge_1R": loss_large_mfe,
        "high_mfe_low_tp": high_mfe_low_tp,
        "wins": wins,
        "wins_with_mae_ge_0_8R": wins_deep_mae,
        "tp1_wins_with_nonpositive_net": high_tp_low_r,
    }
    return [
        EvidenceRecord(
            question="opportunity quality vs trade outcome",
            surface="clean_labels",
            n=n,
            effect_name="high_mfe_low_tp_rate",
            effect_size=(high_mfe_low_tp / n) if n else None,
            confidence=descriptive_confidence(n),
            candidate_finding=(
                f"Quality ≠ outcome: {high_mfe_low_tp}/{n} reached ≥1R yet missed unit TP; "
                f"{loss_large_mfe}/{n} labelled losses still printed MFE≥1R; "
                f"{wins_deep_mae}/{wins or 1} wins drew MAE≥0.8R; "
                f"{high_tp_low_r} TP1 wins have y_R_net≤0 (12bps diagnostic)."
            ),
            extra=slices,
        )
    ]


# ── 4. Exit research (path labels only — no re-detection) ───────────────────
def exit_research(cols: dict[str, list]) -> list[EvidenceRecord]:
    y = _as_float_y(_y_tp1(cols))
    r05 = _col(cols, "y_reached_0_5r")
    r1 = _col(cols, "y_reached_1r_horizon", "y_survives_be")
    r2 = _col(cols, "y_reached_2r_horizon", "y_tp2")
    t_mfe = _col(cols, "y_time_to_mfe")
    hold = _col(cols, "y_holding_bars")
    n = len(y)
    recs: list[EvidenceRecord] = []

    def _rate(col: list | None) -> tuple[float | None, int]:
        if col is None:
            return None, 0
        vals = [float(v) for v in _as_float_y(col) if v is not None]
        return (_mean(vals), len(vals))

    for label, col in (("0.5R", r05), ("1R", r1), ("2R_or_tp2", r2), ("unit_tp1", y)):
        rate, k = _rate(col if label != "unit_tp1" else y)
        recs.append(EvidenceRecord(
            question=f"path hit rate at {label}",
            surface="clean_labels",
            n=k,
            effect_name="hit_rate",
            effect_size=rate,
            confidence=descriptive_confidence(k),
            candidate_finding=(
                f"Observed path hit {label}={rate:.4f} n={k}. "
                "COUNTERFACTUAL on stored paths — not a t=0 policy, not an edge."
            ),
            extra={"lookahead": True, "rerun_detection": False},
        ))
    if r1 is not None:
        r1f = _as_float_y(r1)
        conv = [
            float(y[i]) for i in range(n)
            if r1f[i] == 1.0 and y[i] is not None
        ]
        recs.append(EvidenceRecord(
            question="conversion of 1R excursion into unit TP (2R geometry)",
            surface="clean_labels",
            n=len(conv),
            effect_name="tp1_given_reached_1r",
            effect_size=_mean(conv),
            confidence=descriptive_confidence(len(conv)),
            candidate_finding=(
                f"Among paths that reached 1R, unit-TP conversion={_mean(conv)}. "
                "Measures stored 2R target vs 1R excursion; does not retune a stop."
            ),
            extra={"lookahead": True},
        ))
    if t_mfe is not None and hold is not None:
        tm = [p[1] for p in _finite_at(t_mfe)]
        hd = [p[1] for p in _finite_at(hold)]
        recs.append(EvidenceRecord(
            question="timing: bars to MFE vs holding",
            surface="clean_labels",
            n=min(len(tm), len(hd)),
            effect_name="median_time_to_mfe_bars",
            effect_size=_pct(tm, 50),
            confidence=descriptive_confidence(len(tm)),
            candidate_finding=(
                f"median time-to-MFE={_pct(tm, 50)} bars; median hold={_pct(hd, 50)} bars."
            ),
            extra={"median_hold": _pct(hd, 50), "p90_mfe": _pct(tm, 90)},
        ))
    recs.append(EvidenceRecord(
        question="exit research scope",
        surface="clean_labels",
        n=n,
        effect_name="no_redetection",
        effect_size=0.0,
        confidence="CERTAIN",
        candidate_finding=(
            "Exit numbers are read off stored MFE/MAE/hit labels. Detection was not rerun. "
            "A path-conditioned hit rate is not a tradeable stop/TP rule (EpisodeQuery warning)."
        ),
    ))
    return recs


# ── 5. Candidate lifecycle (telemetry + events) ─────────────────────────────
def candidate_lifecycle(tel_cols: dict[str, list], ev_cols: dict[str, list] | None = None) -> list[EvidenceRecord]:
    recs: list[EvidenceRecord] = []
    n = len(next(iter(tel_cols.values()), []))
    kind = tel_cols.get("kind") or []
    death = tel_cols.get("death_reason") or []
    rej = tel_cols.get("rejection_reason") or []
    ended = tel_cols.get("ended_by") or []
    reject = tel_cols.get("reject_reason") or []
    accepted = tel_cols.get("accepted") or []

    def _count_record(question: str, values: list, name: str) -> EvidenceRecord:
        c = Counter(v for v in values if v not in (None, "", False))
        top = c.most_common(12)
        return EvidenceRecord(
            question=question,
            surface="telemetry",
            n=sum(c.values()),
            effect_name=name,
            effect_size=float(top[0][1]) if top else 0.0,
            confidence=descriptive_confidence(n),
            candidate_finding=f"{name}: " + ", ".join(f"{k}={v}" for k, v in top[:8]),
            extra={"counts": dict(top)},
        )

    recs.append(_count_record("telemetry kind", kind, "kind_mode_count"))
    recs.append(_count_record("candidate death", death, "death_mode_count"))
    recs.append(_count_record("rejection_reason", rej, "rejection_mode_count"))
    recs.append(_count_record("ended_by", ended, "ended_mode_count"))
    recs.append(_count_record("reject_reason", reject, "reject_reason_mode_count"))
    acc_true = sum(1 for v in accepted if v is True)
    recs.append(EvidenceRecord(
        question="approval pathway",
        surface="telemetry",
        n=n,
        effect_name="accepted_true",
        effect_size=float(acc_true),
        confidence=descriptive_confidence(n),
        candidate_finding=f"telemetry accepted=True on {acc_true}/{n} rows (sparse kinds).",
        extra={"accepted_true": acc_true},
    ))
    if ev_cols:
        events = ev_cols.get("event") or []
        frm = ev_cols.get("state_from") or []
        to = ev_cols.get("state_to") or []
        recs.append(EvidenceRecord(
            question="crt event kinds",
            surface="events",
            n=len(events),
            effect_name="event_mode_count",
            effect_size=float(Counter(events).most_common(1)[0][1]) if events else 0.0,
            confidence=descriptive_confidence(len(events)),
            candidate_finding="events: " + ", ".join(
                f"{k}={v}" for k, v in Counter(events).most_common(10)
            ),
            extra={"counts": dict(Counter(events).most_common(12))},
        ))
        trans = Counter(
            (str(a), str(b)) for a, b in zip(frm, to) if a or b
        )
        recs.append(EvidenceRecord(
            question="state transition bottlenecks",
            surface="events",
            n=sum(trans.values()),
            effect_name="top_transition",
            effect_size=float(trans.most_common(1)[0][1]) if trans else 0.0,
            confidence=descriptive_confidence(sum(trans.values())),
            candidate_finding="transitions: " + ", ".join(
                f"{a}->{b}={c}" for (a, b), c in trans.most_common(10)
            ),
            extra={"counts": {f"{a}->{b}": c for (a, b), c in trans.most_common(15)}},
        ))
    recs.append(EvidenceRecord(
        question="lifecycle grain",
        surface="telemetry",
        n=n,
        effect_name="not_joined_to_94k",
        effect_size=0.0,
        confidence="CERTAIN",
        candidate_finding=(
            "Candidate lifecycle is the later CRT spine run. It is not the 94k "
            "bar×direction ledger. TRADE_OPENED on this journal is a process count."
        ),
    ))
    return recs


# ── 6. Ontology validation (coincidence, not certification) ─────────────────
_ONTOLOGY_FLAGS = (
    "features.sweep_detected",
    "features.liquidity_sweep",
    "features.double_sweep",
    "features.break_of_structure",
    "features.volume_spike",
    "features.higher_high",
    "features.lower_low",
)


def ontology_validation(cols: dict[str, list]) -> list[EvidenceRecord]:
    y = _as_float_y(_y_tp1(cols))
    n = len(y)
    recs: list[EvidenceRecord] = []
    # split first/second half by row order (proxy for calendar) for stability
    mid = n // 2
    for col in _ONTOLOGY_FLAGS:
        if col not in cols:
            continue
        name = col.split(".", 1)[-1]
        pairs = [(i, x) for i, x in _finite_at(cols[col]) if y[i] is not None]
        if len(pairs) < 30:
            continue
        # present = value > 0 for spike-like flags
        present = [float(y[i]) for i, x in pairs if x > 0]
        absent = [float(y[i]) for i, x in pairs if x <= 0]
        delta = (_mean(present) or 0.0) - (_mean(absent) or 0.0)
        occ = len(present) / len(pairs) if pairs else 0.0
        first = [float(y[i]) for i, x in pairs if i < mid and x > 0]
        second = [float(y[i]) for i, x in pairs if i >= mid and x > 0]
        recs.append(EvidenceRecord(
            question=f"ontology coincidence: {name}",
            surface="clean_labels",
            n=len(pairs),
            effect_name="y_tp1_present_minus_absent",
            effect_size=delta,
            confidence=contrast_confidence(len(pairs), abs(delta)),
            candidate_finding=(
                f"{name} occurs {occ:.3f}; Δy_tp1 present-absent={delta:+.4f} "
                f"(present n={len(present)} { _mean(present)}; "
                f"absent n={len(absent)} {_mean(absent)}). "
                f"half-split present y_tp1 { _mean(first)} vs {_mean(second)}."
            ),
            extra={
                "occurrence": occ,
                "n_present": len(present),
                "n_absent": len(absent),
                "y_present": _mean(present),
                "y_absent": _mean(absent),
                "y_present_first_half": _mean(first),
                "y_present_second_half": _mean(second),
            },
        ))
    recs.append(EvidenceRecord(
        question="ontology validation scope",
        surface="clean_labels",
        n=n,
        effect_name="coincidence_not_certification",
        effect_size=0.0,
        confidence="CERTAIN",
        candidate_finding=(
            "These are occurrence + y_tp1 shifts for already-emitted flags. "
            "They do not graduate a SEM node and do not reverse F-086."
        ),
    ))
    return recs


# ── 7. Evidence graph ───────────────────────────────────────────────────────
def evidence_graph(
    lab_cols: dict[str, list],
    ev_cols: dict[str, list] | None = None,
    tel_cols: dict[str, list] | None = None,
) -> list[EvidenceRecord]:
    edges: list[dict] = []
    y = _as_float_y(_y_tp1(lab_cols))
    n = len(y)
    if "features.session" in lab_cols:
        buckets: dict[str, list[float]] = defaultdict(list)
        for i, s in enumerate(lab_cols["features.session"]):
            if y[i] is None:
                continue
            buckets[str(s)].append(float(y[i]))
        for s, vs in buckets.items():
            edges.append({
                "src_type": "state", "src": f"session={s}",
                "dst_type": "outcome", "dst": "y_tp1",
                "n": len(vs), "rate": _mean(vs),
            })
    # top feature associations already computed by caller; keep a structural edge
    edges.append({
        "src_type": "surface", "src": "clean_labels",
        "dst_type": "surface", "dst": "opportunities",
        "n": n, "rate": None, "join": "legal_bar_x_direction",
    })
    if ev_cols:
        trans = Counter(
            (str(a), str(b))
            for a, b in zip(ev_cols.get("state_from") or [], ev_cols.get("state_to") or [])
            if a or b
        )
        for (a, b), c in trans.most_common(8):
            edges.append({
                "src_type": "state", "src": a, "dst_type": "state", "dst": b,
                "n": c, "rate": None, "grain": "crt_spine_run",
            })
    if tel_cols:
        death = Counter(v for v in (tel_cols.get("death_reason") or []) if v)
        for k, c in death.most_common(6):
            edges.append({
                "src_type": "decision", "src": "candidate",
                "dst_type": "decision", "dst": f"death={k}",
                "n": c, "rate": None, "grain": "crt_spine_run",
            })
    return [EvidenceRecord(
        question="evidence graph",
        surface="catalog",
        n=len(edges),
        effect_name="edge_count",
        effect_size=float(len(edges)),
        confidence=descriptive_confidence(n),
        candidate_finding=(
            f"{len(edges)} evidence-backed edges. Feature→outcome on the 94k grain; "
            "state→state and candidate→death on the spine-run grain. Not one graph."
        ),
        extra={"edges": edges},
    )]


# ── 8. Question → candidate finding ─────────────────────────────────────────
_ROUTES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("leak", "leakage", "missed tp", "0.5r", "2r"), "leakage"),
    (("state value", "expected mfe", "expected mae"), "state_value"),
    (("asymmetry", "long mfe", "short mfe", "directional"), "asymmetry"),
    (("feature", "census", "effectiveness", "coverage"), "census"),
    (("regime", "session", "volatility", "hour"), "regimes"),
    (("quality", "mfe", "mae", "opportunity"), "quality"),
    (("exit", "trail", "stop", "tp", "time exit"), "exits"),
    (("lifecycle", "reject", "death", "candidate", "bottleneck"), "lifecycle"),
    (("ontology", "semantic", "sweep", "volume_spike"), "ontology"),
    (("graph", "relationship", "edge"), "graph"),
)


def route_question(question: str) -> str:
    q = question.lower()
    for keys, dest in _ROUTES:
        if any(k in q for k in keys):
            return dest
    return "all"


def run_named(
    name: str,
    *,
    lab: dict[str, list] | None = None,
    tel: dict[str, list] | None = None,
    ev: dict[str, list] | None = None,
) -> list[EvidenceRecord]:
    if name == "census":
        assert lab is not None
        return feature_effectiveness(lab)
    if name == "regimes":
        assert lab is not None
        return regime_discovery(lab)
    if name == "quality":
        assert lab is not None
        return opportunity_quality(lab)
    if name == "exits":
        assert lab is not None
        return exit_research(lab)
    if name == "lifecycle":
        assert tel is not None
        return candidate_lifecycle(tel, ev)
    if name == "ontology":
        assert lab is not None
        return ontology_validation(lab)
    if name == "graph":
        assert lab is not None
        return evidence_graph(lab, ev, tel)
    if name in ("leakage", "state_value", "asymmetry"):
        from research.evidence.atlases import (
            asymmetry_atlas,
            leakage_atlas,
            state_value_surface,
        )
        assert lab is not None
        if name == "leakage":
            return leakage_atlas(lab)
        if name == "state_value":
            return state_value_surface(lab)
        return asymmetry_atlas(lab)
    recs: list[EvidenceRecord] = []
    if lab is not None:
        recs.extend(feature_effectiveness(lab))
        recs.extend(regime_discovery(lab))
        recs.extend(opportunity_quality(lab))
        recs.extend(exit_research(lab))
        recs.extend(ontology_validation(lab))
        recs.extend(evidence_graph(lab, ev, tel))
        from research.evidence.atlases import (
            asymmetry_atlas,
            leakage_atlas,
            state_value_surface,
        )
        recs.extend(leakage_atlas(lab))
        recs.extend(state_value_surface(lab))
        recs.extend(asymmetry_atlas(lab))
    if tel is not None:
        recs.extend(candidate_lifecycle(tel, ev))
    return recs


def answer_question(
    question: str,
    *,
    lab: dict[str, list] | None = None,
    tel: dict[str, list] | None = None,
    ev: dict[str, list] | None = None,
) -> list[EvidenceRecord]:
    dest = route_question(question)
    recs = run_named(dest, lab=lab, tel=tel, ev=ev)
    recs.insert(0, EvidenceRecord(
        question=question,
        surface="catalog",
        n=len(recs),
        effect_name="route",
        effect_size=None,
        confidence="CERTAIN",
        candidate_finding=f"Routed {question!r} → {dest} ({len(recs)} evidence records).",
        extra={"route": dest},
    ))
    return recs
