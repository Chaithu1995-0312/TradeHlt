"""Single-pass mother-range measurement. Bindings = MC-MRANGE-XAUUSD-M15-V1.

Geometry is frozen. Do not retune after seeing y.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from data_ingestion.dataset_integrity import validate_dataset
from research.contracts import Signal
from research.costs import ComponentCostModel
from research.measurement.forward_walk import AdverseFill, forward_walk
from research.mother_range.geometry import Bar, InsideCloseEntry, detect_inside_close_entries

CONTRACT_ID = "MC-MRANGE-XAUUSD-M15-V1"
SEM_ID = "SEM-026"
HORIZON_BARS = 40
HOLDOUT_START = datetime(2025, 12, 24, 19, 15, 0)
CORPUS = Path("data/mt5/XAUUSD_M15.csv")
CORPUS_SHA = "4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56"

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
                volume=float(row["volume"]),
                index=i,
            )
        )
    return bars


def _signal(entry: InsideCloseEntry, instrument: str) -> Signal:
    return Signal(
        instrument=instrument,
        timestamp=entry.timestamp,
        entry_index=entry.entry_index,
        direction=entry.direction,
        entry=entry.entry,
        sl_atr_mult=1.0,
        tp_atr_mult=abs(entry.tp - entry.entry) / entry.risk,
        atr=entry.risk,
        meta={
            "inside_score": entry.inside_score,
            "mother_high": entry.mother_high,
            "mother_low": entry.mother_low,
            "sem_id": SEM_ID,
            "contract_id": CONTRACT_ID,
        },
    )


def _walk(sig: Signal, bars: list[Bar], adverse: AdverseFill) -> Any:
    future = [b for b in bars if b.index > sig.entry_index][:HORIZON_BARS]
    if not future:
        return None
    return forward_walk(
        sig, future, max_forward=HORIZON_BARS, exit_model="intrabar_fixed",
        adverse_fill=adverse,
    )


def run(
    corpus: Path = CORPUS,
    *,
    instrument: str = "XAUUSD",
    holdout_start: datetime = HOLDOUT_START,
) -> dict[str, Any]:
    validate_dataset(str(corpus), instrument=instrument, bar_minutes=15, write_report=False)
    bars = load_bars(corpus)
    detected = detect_inside_close_entries(bars)
    adverse = AdverseFill(stop_slippage=0.09, model_gaps=True)

    ledger: list[dict[str, Any]] = []
    open_until = -1
    suppressed = 0
    for ev in detected:
        if ev.entry_index <= open_until:
            suppressed += 1
            continue
        sig = _signal(ev, instrument)
        out = _walk(sig, bars, adverse)
        if out is None:
            continue
        open_until = ev.entry_index + out.duration_candles
        split = "holdout" if ev.timestamp >= holdout_start else "train"
        exit_kind = "SL_HIT" if out.outcome == "SL_HIT" else (
            "TP_HIT" if out.outcome == "TP_HIT" else "TIMEOUT"
        )
        net = _XAU_COST.net_rr(
            out.rr_achieved, ev.entry, ev.risk,
            exit_kind=exit_kind, direction=ev.direction,
        )
        ledger.append({
            "split": split,
            "timestamp": ev.timestamp.isoformat(sep=" "),
            "entry_index": ev.entry_index,
            "direction": ev.direction,
            "entry": ev.entry,
            "sl": ev.sl,
            "tp": ev.tp,
            "risk": ev.risk,
            "inside_score": ev.inside_score,
            "y_R_gross": out.rr_achieved,
            "y_R_net": net,
            "outcome": out.outcome,
            "duration": out.duration_candles,
            "mfe": out.mfe,
            "mae": out.mae,
        })

    holdout = [r for r in ledger if r["split"] == "holdout"]
    train = [r for r in ledger if r["split"] == "train"]

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

    long_only_rows = []
    for r in holdout:
        ev_dir = "long"
        risk = float(r["risk"])
        entry = float(r["entry"])
        tp_dist = abs(float(r["tp"]) - entry)
        sig = Signal(
            instrument=instrument,
            timestamp=datetime.fromisoformat(r["timestamp"].replace(" ", "T")[:19]),
            entry_index=int(r["entry_index"]),
            direction=ev_dir,
            entry=entry,
            sl_atr_mult=1.0,
            tp_atr_mult=tp_dist / risk if risk else 1.0,
            atr=risk,
            meta={"control": "long_only"},
        )
        out = _walk(sig, bars, adverse)
        if out is None:
            continue
        long_only_rows.append(out.rr_achieved)

    lo_mean = (sum(long_only_rows) / len(long_only_rows)) if long_only_rows else None
    h = _stats(holdout)
    gate = {
        "n_ge_30": h["n"] >= 30,
        "net_mean_gt_0": bool(h["net_mean"] is not None and h["net_mean"] > 0),
        "pf_gt_1": bool(h["pf"] is not None and h["pf"] > 1),
        "beats_long_only": bool(
            h["gross_mean"] is not None and lo_mean is not None and h["gross_mean"] > lo_mean
        ),
    }
    promote = all(gate.values())
    if h["n"] < 30:
        verdict = "INSUFFICIENT"
    elif promote:
        verdict = "DIAGNOSTIC_PASS_NOT_ECONOMIC"
    else:
        verdict = "REJECT"

    return {
        "contract_id": CONTRACT_ID,
        "sem_id": SEM_ID,
        "corpus": str(corpus).replace("\\", "/"),
        "corpus_sha256": CORPUS_SHA,
        "holdout_start": holdout_start.isoformat(sep=" "),
        "detected": len(detected),
        "suppressed_one_open": suppressed,
        "ledger_n": len(ledger),
        "train": _stats(train),
        "holdout": h,
        "long_only_holdout_gross_mean": lo_mean,
        "long_only_n": len(long_only_rows),
        "gate": gate,
        "verdict": verdict,
        "economic_claims_allowed": False,
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
    split_manifest = {
        "scheme": "single_holdout_chronologic",
        "holdout_start": report["holdout_start"],
        "embargo_bars": 96,
        "purge_horizon": HORIZON_BARS,
        "f086_stride_holdout_spent": False,
    }
    (out_dir / "split_manifest.json").write_text(
        json.dumps(split_manifest, indent=2), encoding="utf-8",
    )
    md = [
        "# MC-MRANGE-XAUUSD-M15-V1 holdout measurement",
        "",
        f"**Verdict:** {report['verdict']}",
        f"**Economic claims allowed:** {report['economic_claims_allowed']}",
        f"**Holdout start:** `{report['holdout_start']}`",
        "",
        f"- detected (pre one-open): {report['detected']}",
        f"- suppressed one-open: {report['suppressed_one_open']}",
        f"- train n: {report['train']['n']}",
        f"- holdout n: {report['holdout']['n']}",
        f"- holdout gross mean: {report['holdout']['gross_mean']}",
        f"- holdout net mean: {report['holdout']['net_mean']}",
        f"- holdout win rate: {report['holdout']['win_rate']}",
        f"- holdout PF: {report['holdout']['pf']}",
        f"- long_only holdout gross mean: {report['long_only_holdout_gross_mean']}",
        f"- gate: {report['gate']}",
        "",
        "Train expectancy is diagnostic and does not gate. No retune. Not production.",
        "",
    ]
    (out_dir / "report.md").write_text("\n".join(md), encoding="utf-8")
