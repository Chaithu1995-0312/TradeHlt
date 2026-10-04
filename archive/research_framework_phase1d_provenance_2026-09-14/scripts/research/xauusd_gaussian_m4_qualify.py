#!/usr/bin/env python3
"""
xauusd_gaussian_m4_qualify.py — Phase E2
========================================
Run M4 QualificationGate (gates 1–7) on E1 ledger arms for the XAUUSD Gaussian.

Design: docs/implementation_plan/xauusd-gaussian-toward-economics-2026-07-23.md §E2

Uses existing research machinery only:
  * research.qualification.evaluate_pre_bh / finalize / benjamini_hochberg
  * research.measurement.metrics.EdgeAggregator
  * research.costs.CostModel (12 bps)

OOS split: chronological suffix matching E0 holdout (train then oos by timestamp).
Per-arm oos_split = n_oos / n_arm so the gate cut matches the journal HOLDOUT boundary.

Authority: RESEARCH_ONLY. Verdict is M4 research telemetry — does NOT grant
production authority, does NOT flip gaussian_impl, does NOT update findings
unless a human registers a finding later.

Usage:
  python scripts/research/xauusd_gaussian_m4_qualify.py
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

INSTRUMENT = "XAUUSD"
PHASE = "E2_M4_QUALIFY"
PROTOCOL_ID = "xauusd_gaussian_e2_m4_v1"
AUTHORITY = (
    "RESEARCH_ONLY — M4 research verdict only; not production PromotionManager; "
    "not ΔG001 authority; REGISTRY_ACTIVE ≠ ECONOMIC_AUTHORITY"
)

DEFAULT_LEDGER = "results/gaussian_xauusd_econ/ledger_LATEST.jsonl"
DEFAULT_UNITS = "results/gaussian_xauusd_econ/units_LATEST.jsonl"
DEFAULT_QUAL = "configs/research/research_config_majors.json"

# Primary hypotheses under test (pre-registered cohort for BH)
HYPOTHESES = (
    "nb_top_decile",
    "nb_bottom_decile",
    "all_units",
    "long_only",
    "short_only",
)
# Control peer for gate 4 / permutation (pre-registered)
CONTROL_ARM = "random_match_n"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _qual_config(path: Path):
    from research.qualification import QualConfig

    cfg = json.loads(path.read_text(encoding="utf-8"))
    q = cfg.get("qualification") or {}
    costs = cfg.get("costs") or {}
    return QualConfig(
        min_samples=int(q.get("min_samples", 30)),
        expectancy_min=float(q.get("expectancy_min", 0.0)),
        pf_min=float(q.get("pf_min", 1.0)),
        oos_split=float(q.get("oos_split", 0.3)),  # overridden per arm
        oos_retention_min=float(q.get("oos_retention_min", 0.5)),
        n_permutations=int(q.get("n_permutations", 2000)),
        significance_alpha=float(q.get("significance_alpha", 0.05)),
    ), float(costs.get("round_trip_bps", 12.0))


def _unit_key(u: dict) -> tuple:
    return (str(u.get("timestamp")), str(u.get("direction")))


def build_outcomes_for_arm(
    ledger: list[dict],
    units_by_key: dict,
    arm: str,
) -> list:
    """Chronological Outcomes for one arm. gross_rr in Outcome; cost applied by aggregator."""
    from research.contracts import Outcome, Signal

    rows = [r for r in ledger if arm in (r.get("arms") or [])]
    # random arm may only appear as random_match_n in membership
    if arm == CONTROL_ARM:
        rows = [
            r
            for r in ledger
            if CONTROL_ARM in (r.get("arms") or [])
            or "random_match_n_train" in (r.get("arms") or [])
            or "random_match_n_oos" in (r.get("arms") or [])
        ]
        # de-dupe by ts+dir
        seen = set()
        deduped = []
        for r in rows:
            k = (r["timestamp"], r["direction"])
            if k in seen:
                continue
            seen.add(k)
            deduped.append(r)
        rows = deduped

    rows = sorted(rows, key=lambda r: (r["timestamp"], r["direction"]))
    outs = []
    for r in rows:
        u = units_by_key.get(_unit_key(r), {})
        entry = u.get("train_entry")
        atr = u.get("train_atr_abs")
        if entry is None or atr is None or float(atr) <= 0:
            # reconstruct risk distance from gross/net if needed
            entry = float(entry) if entry is not None else 1.0
            atr = float(atr) if atr is not None and float(atr) > 0 else 1.0
        else:
            entry = float(entry)
            atr = float(atr)

        ts = r["timestamp"]
        try:
            ts_dt = datetime.fromisoformat(str(ts).replace(" ", "T"))
        except Exception:
            ts_dt = datetime(1970, 1, 1)

        idx = int(r.get("bar_index") or u.get("bar_index") or 0)
        sig = Signal(
            instrument=INSTRUMENT,
            timestamp=ts_dt,
            entry_index=idx,
            direction=str(r["direction"]),
            entry=entry,
            sl_atr_mult=float(u.get("train_sl_atr_mult") or 1.0),
            tp_atr_mult=float(u.get("train_tp_atr_mult") or 1.0),
            atr=atr,
            meta={
                "score": r.get("score"),
                "split": r.get("split"),
                "arm": arm,
            },
        )
        gross = float(r.get("gross_rr") or 0.0)
        outs.append(
            Outcome(
                signal=sig,
                outcome=str(r.get("exit_reason") or "UNKNOWN"),
                rr_achieved=gross,
                mfe=max(gross, 0.0) * atr,  # rough; research only
                mae=min(gross, 0.0) * atr,
                duration_candles=0,
                time_to_tp=None,
                time_to_failure=None,
                reached_1r=bool(gross >= 1.0),
            )
        )
    return outs


def _edge_report_to_dict(er) -> dict:
    d = dataclasses.asdict(er)
    # sanitize inf
    pf = d.get("profit_factor")
    if pf == float("inf"):
        d["profit_factor"] = None
        d["profit_factor_infinite"] = True
    return d


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="E2: M4 qualify XAUUSD Gaussian arms")
    ap.add_argument("--ledger", default=DEFAULT_LEDGER)
    ap.add_argument("--units", default=DEFAULT_UNITS)
    ap.add_argument("--qual-config", default=DEFAULT_QUAL)
    ap.add_argument("--out-dir", default="results/gaussian_xauusd_econ")
    ap.add_argument(
        "--n-permutations",
        type=int,
        default=0,
        help="Override qual n_permutations (0 = use config; use 200 for smoke)",
    )
    args = ap.parse_args(argv)

    ledger_path = ROOT / args.ledger
    units_path = ROOT / args.units
    if not ledger_path.exists():
        print(f"ERROR: ledger missing: {ledger_path}", file=sys.stderr)
        return 2
    if not units_path.exists():
        print(f"ERROR: units missing: {units_path}", file=sys.stderr)
        return 2

    from research.costs import CostModel
    from research.measurement.metrics import EdgeAggregator
    from research.qualification import (
        BH_METHOD_VERSION,
        PERMUTATION_METHOD_VERSION,
        QUALIFICATION_VERSION,
        benjamini_hochberg,
        evaluate_pre_bh,
        finalize,
    )

    base_qcfg, cost_bps = _qual_config(ROOT / args.qual_config)
    if args.n_permutations > 0:
        base_qcfg = dataclasses.replace(
            base_qcfg, n_permutations=int(args.n_permutations)
        )
    cost = CostModel(round_trip_bps=cost_bps)
    agg = EdgeAggregator()

    ledger = _load_jsonl(ledger_path)
    units = _load_jsonl(units_path)
    units_by_key = {_unit_key(u): u for u in units}

    print(f"[E2] protocol={PROTOCOL_ID}")
    print(f"[E2] ledger={ledger_path} n={len(ledger)}")
    print(
        f"[E2] qual min_samples={base_qcfg.min_samples} E_min={base_qcfg.expectancy_min} "
        f"PF_min={base_qcfg.pf_min} n_perm={base_qcfg.n_permutations}"
    )
    print(f"[E2] authority={AUTHORITY}")

    # Build control first
    ctrl_outs = build_outcomes_for_arm(ledger, units_by_key, CONTROL_ARM)
    ctrl_outs = sorted(ctrl_outs, key=lambda o: (o.signal.timestamp, o.signal.direction))
    n_ctrl_oos = sum(
        1
        for r in ledger
        if r.get("split") == "oos"
        and (
            CONTROL_ARM in (r.get("arms") or [])
            or "random_match_n_oos" in (r.get("arms") or [])
        )
    )
    # unique oos count for control
    ctrl_oos_keys = {
        (r["timestamp"], r["direction"])
        for r in ledger
        if r.get("split") == "oos"
        and (
            CONTROL_ARM in (r.get("arms") or [])
            or "random_match_n_oos" in (r.get("arms") or [])
        )
    }
    n_ctrl = len(ctrl_outs)
    oos_frac_ctrl = (len(ctrl_oos_keys) / n_ctrl) if n_ctrl else base_qcfg.oos_split
    qcfg_ctrl = dataclasses.replace(base_qcfg, oos_split=oos_frac_ctrl)
    ctrl_report = agg.aggregate(CONTROL_ARM, [INSTRUMENT], ctrl_outs, cost_model=cost)
    from research.qualification import _net_rrs

    ctrl_rrs = _net_rrs(ctrl_outs, cost)
    ctrl_exp = ctrl_report.expectancy_rr
    print(
        f"[E2] control={CONTROL_ARM} n={ctrl_report.n} E[R]={ctrl_exp} "
        f"PF={ctrl_report.profit_factor} oos_frac={oos_frac_ctrl:.4f}"
    )

    pre_states = {}
    for hyp in HYPOTHESES:
        outs = build_outcomes_for_arm(ledger, units_by_key, hyp)
        outs = sorted(outs, key=lambda o: (o.signal.timestamp, o.signal.direction))
        if not outs:
            print(f"[E2] {hyp}: n=0 — skip")
            continue
        n_oos = sum(
            1
            for r in ledger
            if hyp in (r.get("arms") or []) and r.get("split") == "oos"
        )
        oos_frac = n_oos / len(outs) if outs else base_qcfg.oos_split
        # clamp to (0,1)
        oos_frac = min(max(oos_frac, 1e-6), 1.0 - 1e-6)
        qcfg = dataclasses.replace(base_qcfg, oos_split=oos_frac)
        report = agg.aggregate(hyp, [INSTRUMENT], outs, cost_model=cost)
        per_inst = {INSTRUMENT: outs}
        state = evaluate_pre_bh(
            report,
            per_inst,
            CONTROL_ARM,
            ctrl_rrs,
            ctrl_exp,
            qcfg,
            cost,
        )
        pre_states[hyp] = (state, qcfg, oos_frac, n_oos)
        print(
            f"[E2] {hyp}: n={report.n} E={report.expectancy_rr} PF={report.profit_factor} "
            f"oos_frac={oos_frac:.3f} n_oos≈{n_oos} passed_1_6={state.passed_1_to_6} "
            f"reasons={state.reject_reasons[:1]}"
        )

    # Gate 7 BH across hypotheses that produced a p-value and passed 1-6 or all with p
    pvalues = {
        name: st.p_value
        for name, (st, _q, _f, _n) in pre_states.items()
        if not st.insufficient
    }
    survivors = benjamini_hochberg(pvalues, base_qcfg.significance_alpha)

    results = {}
    for name, (st, qcfg, oos_frac, n_oos) in pre_states.items():
        final = finalize(st, survivors, qcfg)
        results[name] = {
            "verdict": final.verdict,
            "reject_reasons": list(final.reject_reasons),
            "report": _edge_report_to_dict(final),
            "oos_split_used": oos_frac,
            "n_oos_members": n_oos,
            "passed_gates_1_to_6": st.passed_1_to_6,
            "p_value": st.p_value,
            "bh_survivor": name in survivors,
        }

    # Cohort summary
    from collections import Counter

    verdicts = Counter(r["verdict"] for r in results.values())
    any_promote = any(r["verdict"] == "PROMOTE" for r in results.values())

    ts = _utc()
    out_dir = ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "phase": PHASE,
        "protocol_id": PROTOCOL_ID,
        "run_id": f"xauusd_gaussian_m4_{ts}",
        "timestamp_utc": ts,
        "authority": AUTHORITY,
        "design_doc": (
            "docs/implementation_plan/xauusd-gaussian-toward-economics-2026-07-23.md"
        ),
        "qualification_versions": {
            "QUALIFICATION_VERSION": QUALIFICATION_VERSION,
            "PERMUTATION_METHOD_VERSION": PERMUTATION_METHOD_VERSION,
            "BH_METHOD_VERSION": BH_METHOD_VERSION,
        },
        "qual_config": {
            "min_samples": base_qcfg.min_samples,
            "expectancy_min": base_qcfg.expectancy_min,
            "pf_min": base_qcfg.pf_min,
            "oos_retention_min": base_qcfg.oos_retention_min,
            "n_permutations": base_qcfg.n_permutations,
            "significance_alpha": base_qcfg.significance_alpha,
            "oos_split_policy": "per_arm_n_oos/n_arm chronological suffix (E0 holdout)",
            "source_file": args.qual_config,
            "cost_bps": cost_bps,
        },
        "control": {
            "arm": CONTROL_ARM,
            "n": ctrl_report.n,
            "expectancy_rr": ctrl_report.expectancy_rr,
            "profit_factor": (
                None
                if ctrl_report.profit_factor == float("inf")
                else ctrl_report.profit_factor
            ),
            "win_rate": ctrl_report.win_rate,
        },
        "hypotheses": list(HYPOTHESES),
        "results": results,
        "cohort": {
            "verdict_counts": dict(verdicts),
            "any_promote": any_promote,
            "bh_survivors": sorted(survivors),
            "economic_authority_granted": False,
            "note": (
                "Even PROMOTE here is research M4 only — production authority "
                "requires separate E3 + human gate + measured ΔG001 on live path."
            ),
        },
        "inputs": {
            "ledger_path": str(ledger_path).replace("\\", "/"),
            "ledger_sha256": _sha256_file(ledger_path),
            "units_path": str(units_path).replace("\\", "/"),
            "units_sha256": _sha256_file(units_path),
        },
        "e1_kill_context": {
            "note": "E1 found relative OOS rank skill with absolute E[R]<0 for all arms",
            "expected_m4": "REJECT on gate2_expectancy for primary arms",
        },
    }

    man_path = out_dir / f"e2_m4_manifest_{ts}.json"
    latest = out_dir / "e2_m4_manifest_LATEST.json"
    for p in (man_path, latest):
        p.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    print("--- E2 DONE ---")
    print(f"any_PROMOTE={any_promote}  economic_authority=False")
    for name, r in results.items():
        print(f"  {name:18s} {r['verdict']:14s} {r['reject_reasons'][:1]}")
    print(f"manifest: {man_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
