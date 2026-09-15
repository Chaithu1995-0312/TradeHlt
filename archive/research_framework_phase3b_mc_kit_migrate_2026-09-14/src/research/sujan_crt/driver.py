"""MC-SUJAN-XAUUSD-M15-V1 driver. Bindings frozen in the sealed instance.

PRIMARY admission is SEM-031 R4 (nested vetoes). SEM-023 score is diagnostic.
F-083: split, embargo, purge, and controls are executed here, not merely declared.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import random
from datetime import datetime
from pathlib import Path
from typing import Any

from data_ingestion.dataset_integrity import validate_dataset
from research.contracts import Signal
from research.costs import ComponentCostModel
from research.indicators import atr as research_atr
from research.measurement.forward_walk import AdverseFill, forward_walk
from research.sujan_crt.geometry import Bar, VetoParams
from research.sujan_crt.vetoes import SujanCandidate, detect_funnel_entries

CONTRACT_ID = "MC-SUJAN-XAUUSD-M15-V1"
SEM_ID = "SEM-031"
HORIZON_BARS = 96
ATR_PERIOD = 14
CORPUS = Path("data/mt5/XAUUSD_M15.csv")
SEED = 20260822
N_RANDOM_SEEDS = 100
RUNGS = ("R0", "R1", "R2", "R3", "R4")

PARAMS = VetoParams(
    expansion_min_range_ratio=1.2,
    accumulation_max_range_ratio=0.7,
    distribution_min_range_ratio=1.0,
    location_tolerance_atr=2.0,
    rr_floor=5.0,
    max_sweep_age_bars=20,
    max_return_age_bars=20,
)

_XAU_COST = ComponentCostModel(
    half_spread=0.045,
    commission=0.040,
    entry_slippage=0.090,
    stop_slippage=0.090,
    swap_long_per_night=None,
    swap_short_per_night=None,
    instrument="XAUUSD",
    source="F-082 measured broker calibration; SEM-015 diagnostic net only",
    status="MEASURED",
    entry_slippage_basis="PROXY_FROM_STOP",
)


def _parse_ts(raw: str) -> datetime:
    s = raw.strip().replace("T", " ")
    return datetime.fromisoformat(s[:19])


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_bars(path: Path) -> list[Bar]:
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    bars: list[Bar] = []
    for i, row in enumerate(rows):
        bars.append(
            Bar(
                timestamp=_parse_ts(row["timestamp"]),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row.get("volume") or 0.0),
                index=i,
            )
        )
    return bars


def _atr_series(bars: list[Bar]) -> list[float]:
    return [research_atr(bars[: i + 1], period=ATR_PERIOD) for i in range(len(bars))]


def _signal(c: SujanCandidate, instrument: str) -> Signal:
    risk = abs(c.entry - c.stop)
    reward = abs(c.target - c.entry)
    return Signal(
        instrument=instrument,
        timestamp=c.timestamp if isinstance(c.timestamp, datetime) else _parse_ts(str(c.timestamp)),
        entry_index=c.entry_index,
        direction=c.direction,
        entry=c.entry,
        sl_atr_mult=1.0,
        tp_atr_mult=(reward / risk) if risk else 1.0,
        atr=risk,
        meta={"sem_id": SEM_ID, "contract_id": CONTRACT_ID, "max_rung": c.max_rung},
    )


def _walk(sig: Signal, bars: list[Bar], adverse: AdverseFill) -> Any:
    future = [b for b in bars if b.index > sig.entry_index][:HORIZON_BARS]
    if not future:
        return None
    return forward_walk(
        sig, future, max_forward=HORIZON_BARS, exit_model="intrabar_fixed",
        adverse_fill=adverse,
    )


def _stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    if n == 0:
        return {"n": 0, "gross_mean": None, "net_mean": None, "win_rate": None, "pf": None}
    gross = [float(r["y_R_gross"]) for r in rows]
    net = [float(r["y_R_net"]) for r in rows]
    wins = [g for g in gross if g > 0]
    losses = [g for g in gross if g < 0]
    gp = sum(wins)
    gl = abs(sum(losses))
    pf = (gp / gl) if gl > 0 else (float("inf") if gp > 0 else 0.0)
    return {
        "n": n,
        "gross_mean": sum(gross) / n,
        "net_mean": sum(net) / n,
        "win_rate": sum(1 for g in gross if g > 0) / n,
        "pf": pf,
    }


def _lag1_corr(xs: list[float]) -> float | None:
    if len(xs) < 3:
        return None
    a, b = xs[:-1], xs[1:]
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = math.sqrt(sum((x - ma) ** 2 for x in a))
    db = math.sqrt(sum((y - mb) ** 2 for y in b))
    if da == 0 or db == 0:
        return None
    return num / (da * db)


def _effective_n(n: int, rho: float | None) -> float | None:
    if rho is None:
        return None
    if rho >= 1:
        return 1.0
    if rho <= 0:
        return float(n)
    return n * (1.0 - rho) / (1.0 + rho)


def _row(c: SujanCandidate, out: Any, split: str) -> dict[str, Any]:
    risk = abs(c.entry - c.stop)
    exit_kind = "SL_HIT" if out.outcome == "SL_HIT" else (
        "TP_HIT" if out.outcome == "TP_HIT" else "TIMEOUT"
    )
    net = _XAU_COST.net_rr(out.rr_achieved, c.entry, risk, exit_kind=exit_kind, direction=c.direction)
    ts = c.timestamp.isoformat(sep=" ") if isinstance(c.timestamp, datetime) else str(c.timestamp)
    return {
        "split": split,
        "timestamp": ts,
        "entry_index": c.entry_index,
        "direction": c.direction,
        "entry": c.entry,
        "stop": c.stop,
        "target": c.target,
        "risk": risk,
        "rr_structural": c.rr,
        "max_rung": c.max_rung,
        "rungs": list(c.rungs),
        "alignment_score": c.alignment_score,
        "location_kind": c.location_kind,
        "weekly_state": c.weekly_state,
        "daily_state": c.daily_state,
        "romeo_clock": c.romeo_clock,
        "y_R_gross": out.rr_achieved,
        "y_R_net": net,
        "outcome": out.outcome,
        "duration": out.duration_candles,
        "cost_r": risk and (out.rr_achieved - net),
    }


def run(
    corpus: Path = CORPUS,
    *,
    instrument: str = "XAUUSD",
) -> dict[str, Any]:
    validate_dataset(str(corpus), instrument=instrument, bar_minutes=15, write_report=False)
    bars = load_bars(corpus)
    n_bars = len(bars)
    boundary = int(n_bars * 0.75)
    embargo = HORIZON_BARS
    atr = _atr_series(bars)
    funnel = detect_funnel_entries(bars, PARAMS, atr)
    adverse = AdverseFill(stop_slippage=0.09, model_gaps=True)

    ledger: list[dict[str, Any]] = []
    purged = 0
    for c in funnel:
        if c.entry_index + HORIZON_BARS > n_bars:
            continue
        crosses = (c.entry_index < boundary <= c.entry_index + HORIZON_BARS)
        in_embargo = boundary - embargo <= c.entry_index < boundary
        if crosses or in_embargo:
            purged += 1
            continue
        split = "holdout" if c.entry_index >= boundary else "train"
        sig = _signal(c, instrument)
        out = _walk(sig, bars, adverse)
        if out is None:
            continue
        ledger.append(_row(c, out, split))

    def _rung_split(rung: str, split: str) -> list[dict[str, Any]]:
        return [r for r in ledger if r["split"] == split and rung in r["rungs"]]

    funnel_stats = {
        rung: {"train": _stats(_rung_split(rung, "train")), "holdout": _stats(_rung_split(rung, "holdout"))}
        for rung in RUNGS
    }
    primary_h = _rung_split("R4", "holdout")
    rho = _lag1_corr([float(r["y_R_net"]) for r in primary_h])
    h_stats = _stats(primary_h)

    # Control 1: random_entry, 100 seeds, same n and direction mix and geometry.
    rng_templates = primary_h
    eligible = [
        i for i in range(n_bars)
        if i >= boundary and i + HORIZON_BARS <= n_bars and i >= boundary
    ]
    random_beats = 0
    random_means: list[float] = []
    n_ctl = len(rng_templates)
    if n_ctl and eligible:
        dirs = [r["direction"] for r in rng_templates]
        for s in range(N_RANDOM_SEEDS):
            rng = random.Random(SEED + s)
            picks = [rng.choice(eligible) for _ in range(n_ctl)]
            nets: list[float] = []
            for k, idx in enumerate(picks):
                tmpl = rng_templates[k]
                bar = bars[idx]
                risk = float(tmpl["risk"])
                reward = abs(float(tmpl["target"]) - float(tmpl["entry"]))
                direction = dirs[k]
                entry = bar.close
                sl = entry - risk if direction == "long" else entry + risk
                tp = entry + reward if direction == "long" else entry - reward
                sig = Signal(
                    instrument=instrument,
                    timestamp=bar.timestamp,
                    entry_index=bar.index,
                    direction=direction,
                    entry=entry,
                    sl_atr_mult=1.0,
                    tp_atr_mult=(reward / risk) if risk else 1.0,
                    atr=risk,
                    meta={"control": "random_entry", "seed": SEED + s},
                )
                out = _walk(sig, bars, adverse)
                if out is None:
                    continue
                nets.append(_XAU_COST.net_rr(
                    out.rr_achieved, entry, risk,
                    exit_kind="SL_HIT" if out.outcome == "SL_HIT" else (
                        "TP_HIT" if out.outcome == "TP_HIT" else "TIMEOUT"
                    ),
                    direction=direction,
                ))
            if not nets:
                continue
            mean = sum(nets) / len(nets)
            random_means.append(mean)
            if h_stats["net_mean"] is not None and h_stats["net_mean"] > mean:
                random_beats += 1

    # Control 2: long_only on PRIMARY holdout bars.
    long_only_nets: list[float] = []
    for r in primary_h:
        entry = float(r["entry"])
        risk = float(r["risk"])
        reward = abs(float(r["target"]) - entry)
        sig = Signal(
            instrument=instrument,
            timestamp=_parse_ts(r["timestamp"]),
            entry_index=int(r["entry_index"]),
            direction="long",
            entry=entry,
            sl_atr_mult=1.0,
            tp_atr_mult=(reward / risk) if risk else 1.0,
            atr=risk,
            meta={"control": "long_only"},
        )
        out = _walk(sig, bars, adverse)
        if out is None:
            continue
        long_only_nets.append(_XAU_COST.net_rr(
            out.rr_achieved, entry, risk,
            exit_kind="SL_HIT" if out.outcome == "SL_HIT" else (
                "TP_HIT" if out.outcome == "TP_HIT" else "TIMEOUT"
            ),
            direction="long",
        ))
    lo_mean = (sum(long_only_nets) / len(long_only_nets)) if long_only_nets else None

    # Control 3: funnel_matched — n from R3 holdout (isolates SEM-025).
    r3_h = _rung_split("R3", "holdout")
    fm_nets: list[float] = []
    if r3_h and n_ctl:
        rng = random.Random(SEED)
        picks = [rng.choice(r3_h) for _ in range(n_ctl)]
        fm_nets = [float(p["y_R_net"]) for p in picks]
    fm_mean = (sum(fm_nets) / len(fm_nets)) if fm_nets else None

    gate = {
        "n_ge_30": h_stats["n"] >= 30,
        "net_mean_gt_0": bool(h_stats["net_mean"] is not None and h_stats["net_mean"] > 0),
        "pf_gt_1": bool(h_stats["pf"] is not None and h_stats["pf"] > 1),
        "beats_long_only": bool(
            h_stats["net_mean"] is not None and lo_mean is not None and h_stats["net_mean"] > lo_mean
        ),
        "beats_random_majority": bool(n_ctl and random_beats > 50),
        "beats_funnel_matched": bool(
            h_stats["net_mean"] is not None and fm_mean is not None and h_stats["net_mean"] > fm_mean
        ),
    }
    promote_shaped = all((
        gate["n_ge_30"], gate["net_mean_gt_0"], gate["pf_gt_1"],
        gate["beats_long_only"], gate["beats_random_majority"],
    ))
    if h_stats["n"] < 30:
        verdict = "INSUFFICIENT"
    elif promote_shaped:
        verdict = "DIAGNOSTIC_PASS_NOT_ECONOMIC"
    else:
        verdict = "REJECT"

    return {
        "contract_id": CONTRACT_ID,
        "sem_id": SEM_ID,
        "corpus": str(corpus).replace("\\", "/"),
        "corpus_sha256": _sha256(corpus),
        "n_bars": n_bars,
        "boundary_index": boundary,
        "boundary_timestamp": bars[boundary].timestamp.isoformat(sep=" ") if bars else None,
        "embargo_bars": embargo,
        "purged_cross_boundary": purged,
        "detected_funnel": len(funnel),
        "ledger_n": len(ledger),
        "params": {
            "expansion_min_range_ratio": PARAMS.expansion_min_range_ratio,
            "accumulation_max_range_ratio": PARAMS.accumulation_max_range_ratio,
            "distribution_min_range_ratio": PARAMS.distribution_min_range_ratio,
            "location_tolerance_atr": PARAMS.location_tolerance_atr,
            "rr_floor": PARAMS.rr_floor,
            "max_sweep_age_bars": PARAMS.max_sweep_age_bars,
            "max_return_age_bars": PARAMS.max_return_age_bars,
            "atr_period": ATR_PERIOD,
            "horizon_bars": HORIZON_BARS,
        },
        "funnel": funnel_stats,
        "primary": "R4",
        "holdout": h_stats,
        "train": _stats(_rung_split("R4", "train")),
        "holdout_net_lag1_rho": rho,
        "holdout_effective_n": _effective_n(h_stats["n"], rho),
        "controls": {
            "random_entry_seeds": N_RANDOM_SEEDS,
            "random_entry_r4_beats": random_beats,
            "random_entry_mean_of_means": (sum(random_means) / len(random_means)) if random_means else None,
            "long_only_n": len(long_only_nets),
            "long_only_net_mean": lo_mean,
            "funnel_matched_n": len(fm_nets),
            "funnel_matched_net_mean": fm_mean,
        },
        "gate": gate,
        "verdict": verdict,
        "economic_claims_allowed": False,
        "mt00": "UNRUN",
        "mt01_matrix_coverage": "UNRUN",
        "ledger": ledger,
    }


def write_report(report: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    slim = {k: v for k, v in report.items() if k != "ledger"}
    (out_dir / "metrics.json").write_text(json.dumps(slim, indent=2), encoding="utf-8")
    (out_dir / "ledger.jsonl").write_text(
        "\n".join(json.dumps(r) for r in report["ledger"]) + ("\n" if report["ledger"] else ""),
        encoding="utf-8",
    )
    (out_dir / "split_manifest.json").write_text(
        json.dumps({
            "scheme": "single_holdout_chronologic",
            "n_bars": report["n_bars"],
            "boundary_index": report["boundary_index"],
            "boundary_timestamp": report["boundary_timestamp"],
            "embargo_bars": report["embargo_bars"],
            "purge": "candidates whose forward window crosses the boundary, or that sit in the embargo, are dropped from BOTH partitions",
            "seed": SEED,
            "oos_fraction": 0.25,
            "written_by_the_run": True,
        }, indent=2),
        encoding="utf-8",
    )
    (out_dir / "population_fingerprint.json").write_text(
        json.dumps({
            "corpus": report["corpus"],
            "corpus_sha256": report["corpus_sha256"],
            "n_bars": report["n_bars"],
            "detected_funnel": report["detected_funnel"],
            "ledger_n": report["ledger_n"],
        }, indent=2),
        encoding="utf-8",
    )
    md = [
        f"# {CONTRACT_ID} measurement",
        "",
        f"**Verdict:** {report['verdict']}",
        f"**PRIMARY:** {report['primary']} (SEM-031 full conjunction). SEM-023 is not a gate.",
        f"**Economic claims allowed:** {report['economic_claims_allowed']}",
        f"**Boundary:** index {report['boundary_index']} `{report['boundary_timestamp']}`",
        "",
        f"- funnel detected: {report['detected_funnel']}",
        f"- purged cross-boundary/embargo: {report['purged_cross_boundary']}",
        f"- train R4 n: {report['train']['n']}",
        f"- holdout R4 n: {report['holdout']['n']}",
        f"- holdout gross mean: {report['holdout']['gross_mean']}",
        f"- holdout net mean: {report['holdout']['net_mean']}",
        f"- holdout PF: {report['holdout']['pf']}",
        f"- effective n: {report['holdout_effective_n']}",
        f"- long_only net mean: {report['controls']['long_only_net_mean']}",
        f"- random_entry R4 beats: {report['controls']['random_entry_r4_beats']}/{N_RANDOM_SEEDS}",
        f"- funnel_matched net mean: {report['controls']['funnel_matched_net_mean']}",
        f"- gate: {report['gate']}",
        "",
        "mt00/mt01 UNRUN. No retune. Not production. Not G001.",
        "",
    ]
    (out_dir / "report.md").write_text("\n".join(md), encoding="utf-8")
