#!/usr/bin/env python3
"""
RR L3 — Label generation under SIGNED L1 freeze + COMPLETE L2 feature matrix.

Consumes:
  - docs/governance/rr_l1_freeze/RR_L1_FREEZE_CERTIFICATE.json  (assert-signed)
  - results/rr_research/l2/<certificate_id>/feature_matrix.npz + L2_PROVENANCE.json
  - Frozen entry stream: opportunities JSONL (entries only; F-022 outcomes are x-ref)

Produces clean dataset with:
  y_rr  = net realized R via forward_walk(intrabar_fixed) − 12 bps cost in R
  y_win = 1 if y_rr > 0 else 0
  X     = L2 masked feature row at entry timestamp

Resolves: RR-LAB-004, RR-LAB-001, RR-LAB-002

Usage (repo root):
  python scripts/research/rr_l3_label_generation.py
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from config_layer.crt_engine_v2 import Candle  # noqa: E402
from research.contracts import Signal  # noqa: E402
from research.measurement.forward_walk import forward_walk  # noqa: E402
from research.zone_label_audit import COST_RT, MAX_FORWARD, net_r  # noqa: E402

from scripts.governance.rr_l1_freeze_certificate import (  # noqa: E402
    DEFAULT_CERT,
    compute_protocol_hash,
    cmd_assert_signed,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _norm_ts(ts: str) -> str:
    return str(ts).replace("T", " ").strip()


def _load_candles(csv_path: Path):
    candles, ts_to_idx = [], {}
    with csv_path.open(encoding="utf-8") as fh:
        for i, row in enumerate(csv.DictReader(fh)):
            ts = _norm_ts(row["timestamp"])
            c = Candle(
                timestamp=datetime.fromisoformat(ts.replace(" ", "T")),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row.get("volume", 0) or 0),
                index=i,
            )
            candles.append(c)
            ts_to_idx[ts] = i
    return candles, ts_to_idx


def _iter_opportunities(path: Path):
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("type") == "run_header":
                continue
            yield rec


def _honest_net_r(opp: dict, candles, ts_to_idx) -> Optional[Tuple[float, str, float]]:
    """Return (y_rr_net, outcome_str, y_rr_gross) or None if unlabelable."""
    ts = _norm_ts(opp["timestamp"])
    idx = ts_to_idx.get(ts)
    if idx is None:
        return None
    direction = str(opp["direction"]).lower()
    if direction not in ("long", "short"):
        return None
    entry = float(opp["entry"])
    sl = float(opp["sl"])
    tp = float(opp.get("tp", entry))
    risk = abs(entry - sl)
    if risk <= 0:
        return None
    future = candles[idx + 1 : idx + 1 + MAX_FORWARD]
    if not future:
        return None
    sig = Signal(
        instrument=str(opp.get("instrument", "")),
        timestamp=candles[idx].timestamp,
        entry_index=idx,
        direction=direction,
        entry=entry,
        sl_atr_mult=1.0,
        tp_atr_mult=abs(tp - entry) / risk,
        atr=risk,
    )
    out = forward_walk(sig, future, max_forward=MAX_FORWARD, exit_model="intrabar_fixed")
    gross = float(out.rr_achieved)
    y_net = float(net_r(out))
    return y_net, str(out.outcome), gross


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cert", type=Path, default=DEFAULT_CERT)
    ap.add_argument(
        "--l2-dir",
        type=Path,
        default=None,
        help="default: results/rr_research/l2/<certificate_id>/",
    )
    ap.add_argument(
        "--opportunities",
        type=Path,
        default=REPO_ROOT
        / "logs"
        / "BNBUSDT"
        / "bnbusdt_balanced_20260524"
        / "opportunities.jsonl",
    )
    ap.add_argument(
        "--candles",
        type=Path,
        default=REPO_ROOT / "data" / "BNBUSDT_M15.csv",
    )
    ap.add_argument("--out-dir", type=Path, default=None)
    args = ap.parse_args(argv)

    cert_path = args.cert if args.cert.is_absolute() else (REPO_ROOT / args.cert)
    if cmd_assert_signed(cert_path) != 0:
        return 2
    cert = json.loads(cert_path.read_text(encoding="utf-8"))
    if compute_protocol_hash(cert["contract"]) != cert["protocol_hash"]:
        print("FAIL: protocol_hash drift", file=sys.stderr)
        return 1

    contract = cert["contract"]
    ge = contract["governing_exit"]
    if ge.get("method") != "forward_walk":
        print(f"FAIL: governing_exit.method={ge.get('method')!r}", file=sys.stderr)
        return 1
    if (ge.get("params") or {}).get("mode") != "intrabar_fixed":
        print(f"FAIL: exit mode must be intrabar_fixed", file=sys.stderr)
        return 1
    td = contract["target_definition"]
    if td.get("primary_target_name") != "y_rr" or td.get("target_kind") != "continuous_realized_r":
        print("FAIL: target_definition mismatch", file=sys.stderr)
        return 1
    if td.get("win_forces_y_rr_plus_one_forbidden") is not True:
        print("FAIL: win_forces_y_rr_plus_one_forbidden must be true", file=sys.stderr)
        return 1

    cert_id = cert["certificate_id"]
    protocol_hash = cert["protocol_hash"]
    l2_dir = args.l2_dir
    if l2_dir is None:
        l2_dir = REPO_ROOT / "results" / "rr_research" / "l2" / cert_id
    else:
        l2_dir = l2_dir if l2_dir.is_absolute() else (REPO_ROOT / l2_dir)

    prov2_path = l2_dir / "L2_PROVENANCE.json"
    npz_path = l2_dir / "feature_matrix.npz"
    if not prov2_path.is_file() or not npz_path.is_file():
        print(f"FAIL: L2 artifacts missing in {l2_dir}", file=sys.stderr)
        return 1
    prov2 = json.loads(prov2_path.read_text(encoding="utf-8"))
    if prov2.get("protocol_hash") != protocol_hash:
        print("FAIL: L2 protocol_hash != L1", file=sys.stderr)
        return 1
    if prov2.get("certificate_id") != cert_id:
        print("FAIL: L2 certificate_id mismatch", file=sys.stderr)
        return 1
    schema_hash = prov2["schema_hash"]

    pack = np.load(npz_path, allow_pickle=True)
    X_all = np.asarray(pack["X"], dtype=np.float64)
    ts_l2 = [_norm_ts(t) for t in pack["timestamps"].tolist()]
    l2_ts_to_row = {t: i for i, t in enumerate(ts_l2)}
    feature_names = [str(x) for x in pack["feature_names"].tolist()]

    candles_path = args.candles if args.candles.is_absolute() else (REPO_ROOT / args.candles)
    opp_path = (
        args.opportunities
        if args.opportunities.is_absolute()
        else (REPO_ROOT / args.opportunities)
    )
    print(f"Loading candles: {candles_path}")
    candles, ts_to_idx = _load_candles(candles_path)
    print(f"  n_candles={len(candles)}")
    print(f"Loading opportunities (entry stream only): {opp_path}")

    X_rows: List[List[float]] = []
    y_rr: List[float] = []
    y_win: List[int] = []
    meta_rows: List[dict] = []
    skip = {
        "no_l2_row": 0,
        "no_candle": 0,
        "unlabelable": 0,
        "bad_direction": 0,
    }
    n_seen = 0
    # F-022 x-ref only
    n_outcome_agree = 0
    n_outcome_compare = 0

    for opp in _iter_opportunities(opp_path):
        n_seen += 1
        ts = _norm_ts(opp["timestamp"])
        row_i = l2_ts_to_row.get(ts)
        if row_i is None:
            skip["no_l2_row"] += 1
            continue
        labeled = _honest_net_r(opp, candles, ts_to_idx)
        if labeled is None:
            if ts not in ts_to_idx:
                skip["no_candle"] += 1
            else:
                skip["unlabelable"] += 1
            continue
        y_net, outcome_str, y_gross = labeled
        yw = 1 if y_net > 0.0 else 0
        # Degeneracy guard: do not force +1.0 on wins
        X_rows.append(X_all[row_i].tolist())
        y_rr.append(y_net)
        y_win.append(yw)
        meta_rows.append(
            {
                "timestamp": ts,
                "direction": str(opp["direction"]).lower(),
                "entry": float(opp["entry"]),
                "sl": float(opp["sl"]),
                "tp": float(opp.get("tp", opp["entry"])),
                "honest_outcome": outcome_str,
                "y_rr_gross": y_gross,
                "y_rr": y_net,
                "y_win": yw,
                "stream_outcome_xref": opp.get("outcome"),
                "stream_rr_achieved_xref": opp.get("rr_achieved"),
            }
        )
        if opp.get("outcome") is not None:
            n_outcome_compare += 1
            # rough agree on TP vs positive net is not required; count raw outcome string match to honest
            if str(opp.get("outcome")) == outcome_str:
                n_outcome_agree += 1

        if n_seen % 20000 == 0:
            print(f"  processed opportunities={n_seen} labeled={len(y_rr)} ...")

    n = len(y_rr)
    min_floor = int(contract["sampling"].get("min_samples_floor") or 500)
    if n < min_floor:
        print(f"FAIL: n={n} < min_samples_floor={min_floor}", file=sys.stderr)
        return 1

    y_rr_a = np.asarray(y_rr, dtype=np.float64)
    y_win_a = np.asarray(y_win, dtype=np.int32)
    X = np.asarray(X_rows, dtype=np.float32)

    # LAB-002 integrity: among wins, y_rr must not be identically +1.0
    wins = y_win_a > 0
    n_win = int(wins.sum())
    frac_win_exact_1 = float(np.mean(np.isclose(y_rr_a[wins], 1.0))) if n_win else 0.0
    if n_win > 100 and frac_win_exact_1 > 0.99:
        print(
            f"FAIL: degenerate y_rr on wins (frac y_rr==1.0 = {frac_win_exact_1:.4f})",
            file=sys.stderr,
        )
        return 1

    out_dir = args.out_dir
    if out_dir is None:
        out_dir = REPO_ROOT / "results" / "rr_research" / "l3" / cert_id
    else:
        out_dir = out_dir if out_dir.is_absolute() else (REPO_ROOT / out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    def _rel(p: Path) -> str:
        try:
            return str(p.relative_to(REPO_ROOT)).replace("\\", "/")
        except ValueError:
            return str(p)

    dataset = {
        "n_samples": n,
        "n_features": int(X.shape[1]),
        "feature_names": feature_names,
        "schema_hash": schema_hash,
        "protocol_hash": protocol_hash,
        "certificate_id": cert_id,
        "l1_certificate_path": _rel(cert_path),
        "l2_schema_hash": schema_hash,
        "X": X.tolist(),
        "y_rr": y_rr,
        "y_win": list(y_win),
        "label_def": {
            "y_rr": "forward_walk(intrabar_fixed) net of 12bps cost in R (zone_label_audit.net_r)",
            "y_win": "1 if y_rr > 0 else 0",
            "win_forces_y_rr_plus_one": False,
        },
        "governing_exit": ge,
        "cost_rt": COST_RT,
        "max_forward": MAX_FORWARD,
        "sampling_design": contract["sampling"]["design"],
        "entry_stream": {
            "path": _rel(opp_path),
            "role": "entry_geometry_only",
            "outcomes_role": "xref_only_F022",
        },
    }
    # Large JSON — also save npz for consumers
    npz_out = out_dir / "clean_dataset.npz"
    np.savez_compressed(
        npz_out,
        X=X,
        y_rr=y_rr_a,
        y_win=y_win_a,
        feature_names=np.array(feature_names, dtype=object),
        timestamps=np.array([m["timestamp"] for m in meta_rows], dtype=object),
    )

    # Compact JSON without full X for provenance-friendly inspect (optional full dump)
    summary_path = out_dir / "clean_dataset.summary.json"
    summary = {
        "n_samples": n,
        "n_features": int(X.shape[1]),
        "feature_names": feature_names,
        "schema_hash": schema_hash,
        "protocol_hash": protocol_hash,
        "certificate_id": cert_id,
        "label_def": dataset["label_def"],
        "y_rr_mean": float(y_rr_a.mean()),
        "y_rr_std": float(y_rr_a.std()),
        "y_rr_min": float(y_rr_a.min()),
        "y_rr_max": float(y_rr_a.max()),
        "win_rate": float(y_win_a.mean()),
        "n_win": n_win,
        "frac_win_y_rr_exact_1": frac_win_exact_1,
        "artifacts": {
            "clean_dataset_npz": _rel(npz_out),
            "row_meta_jsonl": _rel(out_dir / "row_meta.jsonl"),
        },
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    meta_path = out_dir / "row_meta.jsonl"
    with meta_path.open("w", encoding="utf-8") as fh:
        for m in meta_rows:
            fh.write(json.dumps(m, separators=(",", ":")) + "\n")

    provenance = {
        "layer": "L3_LABEL_GENERATION",
        "certificate_id": cert_id,
        "protocol_hash": protocol_hash,
        "l1_certificate_path": _rel(cert_path),
        "l2_dir": _rel(l2_dir),
        "l2_schema_hash": schema_hash,
        "l2_pit_status": prov2.get("pit_status"),
        "schema_hash": schema_hash,
        "pit_status": prov2.get("pit_status"),
        "rc_ids_resolved": ["RR-LAB-004", "RR-LAB-001", "RR-LAB-002"],
        "n_opportunities_seen": n_seen,
        "n_labeled": n,
        "skip_counts": skip,
        "entry_stream_path": _rel(opp_path),
        "candles_path": _rel(candles_path),
        "governing_exit": ge,
        "cost_rt": COST_RT,
        "max_forward": MAX_FORWARD,
        "label_def": dataset["label_def"],
        "f022_xref": {
            "n_compared": n_outcome_compare,
            "n_outcome_string_agree": n_outcome_agree,
            "agree_rate": (n_outcome_agree / n_outcome_compare) if n_outcome_compare else None,
            "note": "stream outcome/rr_achieved are non-authoritative x-ref only",
        },
        "degeneracy_check": {
            "n_win": n_win,
            "frac_win_y_rr_exact_1": frac_win_exact_1,
            "pass": not (n_win > 100 and frac_win_exact_1 > 0.99),
        },
        "sampling_design": contract["sampling"]["design"],
        "min_samples_floor": min_floor,
        "created_at_utc": _utc_now(),
        "artifacts": {
            "clean_dataset_npz": _rel(npz_out),
            "clean_dataset_summary": _rel(summary_path),
            "row_meta_jsonl": _rel(meta_path),
        },
    }
    (out_dir / "L3_PROVENANCE.json").write_text(
        json.dumps(provenance, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    completion = {
        "L3_COMPLETE": True,
        "certificate_id": cert_id,
        "protocol_hash": protocol_hash,
        "schema_hash": schema_hash,
        "n_samples": n,
        "win_rate": float(y_win_a.mean()),
        "y_rr_mean": float(y_rr_a.mean()),
        "frac_win_y_rr_exact_1": frac_win_exact_1,
        "out_dir": _rel(out_dir),
        "rc_ids_resolved": provenance["rc_ids_resolved"],
        "completed_at_utc": _utc_now(),
        "next_layer": "L4_RESEARCH_EXECUTION",
    }
    (out_dir / "L3_COMPLETION.json").write_text(
        json.dumps(completion, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "L3_COMPLETION.md").write_text(
        f"""# L3 Label Generation — COMPLETE

| Field | Value |
|-------|--------|
| certificate_id | `{cert_id}` |
| protocol_hash | `{protocol_hash}` |
| schema_hash | `{schema_hash}` |
| n_samples | {n} |
| win_rate | {float(y_win_a.mean()):.4f} |
| y_rr mean/std | {float(y_rr_a.mean()):.4f} / {float(y_rr_a.std()):.4f} |
| frac win with y_rr≈1.0 | {frac_win_exact_1:.4f} (must be ≪1) |
| entry stream | `{_rel(opp_path)}` (geometry only) |
| labels | forward_walk(intrabar_fixed) net 12 bps |

## RC resolved
RR-LAB-004 · RR-LAB-001 · RR-LAB-002

## Next
L4 Research execution (harness co-consistency + smoke + RS accepts + epoch charter).
""",
        encoding="utf-8",
    )

    print("L3_COMPLETE=YES")
    print(f"  n={n} win_rate={float(y_win_a.mean()):.4f} y_rr_mean={float(y_rr_a.mean()):.4f}")
    print(f"  frac_win_y_rr_exact_1={frac_win_exact_1:.4f}")
    print(f"  skip={skip}")
    print(f"  out_dir={out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
