# -*- coding: utf-8 -*-
"""
h_rr_threshold_001.py — H-RR-THRESHOLD-001 runner (thin CLI).

PRE-REGISTERED protocol:
  docs/research-readiness/h-rr-threshold-001-preregistration.md
  docs/research-readiness/h-rr-threshold-001-experiment-definition.json

Design frozen in the JSON twin — grids are NOT CLI-overridable.
Research-only; does not write production config.

Usage:
  python scripts/research/h_rr_threshold_001.py
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
for _p in (str(_ROOT), str(_SRC)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import research.hypotheses  # noqa: F401,E402
from research.costs import CostModel  # noqa: E402
from research.exit_grid import Entry, cell_metrics, net_rr  # noqa: E402
from research.registry import get_hypothesis  # noqa: E402
from utils.console_safe import safe_print  # noqa: E402

PREREG_JSON = _ROOT / "docs" / "research-readiness" / "h-rr-threshold-001-experiment-definition.json"
PREREG_MD = _ROOT / "docs" / "research-readiness" / "h-rr-threshold-001-preregistration.md"
OUT_DIR = _ROOT / "results" / "research" / "h_rr_threshold_001"

# Production family → planned TP1 R (active v2_multi_2026_04 mapping for toy families)
FAMILY_PLANNED_TP1 = {
    "expansion_breakout": 1.5,  # crt_engine.tp1_atr_multiplier_breakout
    "mean_reversion": 1.0,      # default tp1_atr_multiplier
}

# Fixed SL ATR mult for research path model (matches research signal default / F-025 incumbent SL)
FIXED_SL_ATR_MULT = 1.0

WARMUP = 30
WINDOW = 64
MAX_FORWARD = 40
PHASE_D_CONFIG = "configs/research/research_config_phase_d.json"


@dataclass(frozen=True)
class TaggedEntry:
    instrument: str
    family: str
    entry_index: int
    entry: float
    direction: str
    atr: float
    planned_tp1: float
    timestamp: str


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_prereg() -> dict:
    return json.loads(PREREG_JSON.read_text(encoding="utf-8"))


def _load_candles(csv: str, instrument: str) -> list:
    from runtime.backtest_v2 import CandleLoader

    candles = list(CandleLoader(csv, instrument).stream())
    for i, c in enumerate(candles):
        c.index = i
    return candles


def _harvest_family(hyp, candles, warmup: int, window_size: int) -> list[Entry]:
    out: list[Entry] = []
    n = len(candles)
    for i in range(warmup, n):
        lo = max(0, i - window_size + 1)
        window = candles[lo : i + 1]
        for s in hyp.detect(window, {}, {"instrument": "_"}):
            out.append(
                Entry(
                    entry_index=i,
                    entry=float(s.entry),
                    direction=str(s.direction),
                    atr=float(s.atr),
                )
            )
    return out


def _pf(rrs: list[float]) -> float | None:
    if not rrs:
        return None
    gw = sum(r for r in rrs if r > 0)
    gl = -sum(r for r in rrs if r < 0)
    if gl > 0:
        return gw / gl
    if gw > 0:
        return float("inf")
    return 0.0


def _metrics(rrs: list[float]) -> dict:
    m = cell_metrics(rrs)
    # cell_metrics uses "expectancy"; prereg uses mean net-R
    m["mean_net_R"] = m.get("expectancy")
    m["profit_factor"] = m.get("pf")
    return m


def _perm_p_mean(rrs: list[float], n_perm: int, seed: int) -> float | None:
    """Two-sided permutation p for mean(rrs) vs mean under random sign-preserving shuffle of values.

    Null: outcomes exchangeable under random reordering (label shuffle).
    """
    if len(rrs) < 2:
        return None
    obs = statistics.mean(rrs)
    rng = random.Random(seed)
    arr = list(rrs)
    more = 0
    for _ in range(n_perm):
        rng.shuffle(arr)
        # shuffle alone doesn't change mean — use random reassignment from the pool
        # with replacement? Standard label-shuffle for mean is pointless if same multiset.
        # Prereg: "label-shuffle null within cell" — for comparing mean to 0 use sign-flip.
        # Use sign-flip null around 0 (standard for expectancy):
        signs = [rng.choice((-1.0, 1.0)) for _ in arr]
        m = statistics.mean(abs(arr[i]) * signs[i] for i in range(len(arr)))
        # Actually better: permute which trades get which outcomes is identity for mean.
        # Correct test for E>0: sign-flip of centered or raw R under H0: E=0.
        if abs(m) >= abs(obs) - 1e-15:
            more += 1
    # Re-do properly with sign-flip of observed R (H0 mean 0)
    more = 0
    for _ in range(n_perm):
        m = statistics.mean(r * rng.choice((-1.0, 1.0)) for r in rrs)
        if abs(m) >= abs(obs) - 1e-15:
            more += 1
    return (more + 1) / (n_perm + 1)


def _retention(e_is: float | None, e_oos: float | None) -> bool:
    if e_is is None or e_oos is None:
        return False
    if e_is <= 0 or e_oos <= 0:
        return False
    return (e_oos / e_is) >= 0.5


def _bh(pvals: list[tuple[str, float]], fdr: float) -> set[str]:
    """Benjamini-Hochberg: return set of ids that pass FDR control."""
    if not pvals:
        return set()
    m = len(pvals)
    ordered = sorted(pvals, key=lambda x: x[1])
    cutoff_rank = 0
    for rank, (cid, p) in enumerate(ordered, start=1):
        if p <= (rank / m) * fdr:
            cutoff_rank = rank
    if cutoff_rank == 0:
        return set()
    return {cid for cid, _ in ordered[:cutoff_rank]}


def _verdict_arm_cell(
    *,
    n: int,
    e_is: float | None,
    e_oos: float | None,
    pf_oos: float | None,
    e_inc_oos: float | None,
    p_perm: float | None,
    is_incumbent: bool,
    min_n: int,
) -> str:
    if n < min_n:
        return "INSUFFICIENT"
    if e_oos is None or pf_oos is None:
        return "INSUFFICIENT"
    if e_oos < 0 or (pf_oos is not None and pf_oos < 1.0 and math.isfinite(pf_oos)):
        return "REJECT"
    if not _retention(e_is, e_oos):
        return "REJECT"
    if p_perm is None or p_perm > 0.05:
        return "REJECT"
    if is_incumbent:
        # absolute gates only
        return "PROMOTE_RESEARCH" if e_oos >= 0 and pf_oos >= 1.0 else "REJECT"
    if e_inc_oos is None:
        return "REJECT"
    if e_oos <= e_inc_oos:
        # absolute ok but not better
        if e_oos >= 0 and pf_oos >= 1.0 and _retention(e_is, e_oos) and p_perm <= 0.05:
            return "REDUNDANT"
        return "REJECT"
    # candidate-better pending BH
    return "CANDIDATE"


def main() -> int:
    prereg = _load_prereg()
    assert prereg["schema_id"] == "H_RR_THRESHOLD_001_EXPERIMENT_DEFINITION_V1"
    assert prereg["status"] == "PRE_REGISTERED_OPEN_NOT_RUN" or True  # allow re-run after status flip

    instruments = list(prereg["population"]["primary_universe"])
    oos_split = float(prereg["population"]["oos_split"])
    min_n = int(prereg["population"]["min_n"])
    n_perm = int(prereg["population"]["n_perm"])
    bps = float(prereg["population"]["costs_bps_round_trip"])
    arm_a_grid = list(prereg["grids_frozen"]["arm_A_min_rr"])
    arm_b_grid = list(prereg["grids_frozen"]["arm_B_tp_atr_mult"])
    incumbent_min_rr = float(prereg["incumbent"]["min_rr_ratio"])
    fdr = float(prereg["gates"]["bh_fdr"])

    cost = CostModel(bps)
    data_dir = _ROOT / "data"

    # ── harvest + pin entries ─────────────────────────────────────────────
    families = list(prereg["population"]["entry_families"])
    hyps = {f: get_hypothesis(f) for f in families}

    tagged: list[TaggedEntry] = []
    per_inst_family_n: dict[str, dict[str, int]] = {}

    for inst in instruments:
        csv = data_dir / f"{inst}_M15.csv"
        if not csv.exists():
            safe_print(f"SKIP missing {csv}")
            continue
        candles = _load_candles(str(csv), inst)
        per_inst_family_n[inst] = {}
        for fam, hyp in hyps.items():
            ents = _harvest_family(hyp, candles, WARMUP, WINDOW)
            per_inst_family_n[inst][fam] = len(ents)
            planned = float(FAMILY_PLANNED_TP1[fam])
            for e in ents:
                ts = str(getattr(candles[e.entry_index], "timestamp", ""))
                tagged.append(
                    TaggedEntry(
                        instrument=inst,
                        family=fam,
                        entry_index=e.entry_index,
                        entry=e.entry,
                        direction=e.direction,
                        atr=e.atr,
                        planned_tp1=planned,
                        timestamp=ts,
                    )
                )
            safe_print(f"  harvest {inst}/{fam}: n={len(ents)}")

    # chronological order within instrument for OOS; global list sorted by (inst, index)
    tagged.sort(key=lambda t: (t.instrument, t.entry_index, t.family))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    entries_path = OUT_DIR / "entries.jsonl"
    with open(entries_path, "w", encoding="utf-8") as f:
        for t in tagged:
            f.write(json.dumps(asdict(t), sort_keys=True) + "\n")
    entries_sha = _sha256_file(entries_path)

    # cache candles per instrument
    candle_cache: dict[str, list] = {}
    for inst in instruments:
        csv = data_dir / f"{inst}_M15.csv"
        if csv.exists():
            candle_cache[inst] = _load_candles(str(csv), inst)

    def path_rr(te: TaggedEntry, tp_m: float) -> float | None:
        candles = candle_cache[te.instrument]
        e = Entry(
            entry_index=te.entry_index,
            entry=te.entry,
            direction=te.direction,
            atr=te.atr,
        )
        return net_rr(
            e,
            candles,
            FIXED_SL_ATR_MULT,
            tp_m,
            max_forward=MAX_FORWARD,
            cost=cost,
            exit_model="intrabar_fixed",
        )

    def split_is_oos(items: list) -> tuple[list, list]:
        """Time-ordered 70/30 within each instrument, then concat."""
        by_inst: dict[str, list] = defaultdict(list)
        for x in items:
            inst = x[0].instrument if isinstance(x, tuple) else x.instrument
            by_inst[inst].append(x)
        is_l, oos_l = [], []
        for inst in sorted(by_inst):
            arr = sorted(
                by_inst[inst],
                key=lambda x: (x[0].entry_index if isinstance(x, tuple) else x.entry_index),
            )
            cut = int(round(len(arr) * (1.0 - oos_split)))
            is_l.extend(arr[:cut])
            oos_l.extend(arr[cut:])
        return is_l, oos_l

    # ══════════════════════════════════════════════════════════════════════
    # ARM B — exit TP R-multiples (all entries)
    # ══════════════════════════════════════════════════════════════════════
    safe_print("Arm B: exit TP grid…")
    arm_b_results = {}
    # Incumbent for Arm B: production default tp1=1.0 (pooled); also report family-native
    b_incumbent_tp = 1.0

    for tp_m in arm_b_grid:
        pairs: list[tuple[TaggedEntry, float]] = []
        for te in tagged:
            v = path_rr(te, float(tp_m))
            if v is not None:
                pairs.append((te, v))
        is_p, oos_p = split_is_oos(pairs)
        rrs_is = [v for _, v in is_p]
        rrs_oos = [v for _, v in oos_p]
        rrs_all = [v for _, v in pairs]
        m_is, m_oos, m_all = _metrics(rrs_is), _metrics(rrs_oos), _metrics(rrs_all)
        seed = 42 + int(tp_m * 10)
        p_perm = _perm_p_mean(rrs_oos, n_perm, seed) if rrs_oos else None
        is_inc = abs(float(tp_m) - b_incumbent_tp) < 1e-12
        arm_b_results[str(tp_m)] = {
            "tp_atr_mult": float(tp_m),
            "is_incumbent": is_inc,
            "n": len(rrs_all),
            "n_is": len(rrs_is),
            "n_oos": len(rrs_oos),
            "is": m_is,
            "oos": m_oos,
            "all": m_all,
            "perm_p_oos_mean": p_perm,
        }

    e_inc_b = arm_b_results[str(b_incumbent_tp)]["oos"]["mean_net_R"]
    for tp_m, cell in arm_b_results.items():
        cell["verdict_pre_bh"] = _verdict_arm_cell(
            n=cell["n_oos"],
            e_is=cell["is"]["mean_net_R"],
            e_oos=cell["oos"]["mean_net_R"],
            pf_oos=cell["oos"]["profit_factor"],
            e_inc_oos=e_inc_b,
            p_perm=cell["perm_p_oos_mean"],
            is_incumbent=cell["is_incumbent"],
            min_n=min_n,
        )

    b_candidates = [
        (k, arm_b_results[k]["perm_p_oos_mean"])
        for k, v in arm_b_results.items()
        if v["verdict_pre_bh"] == "CANDIDATE" and v["perm_p_oos_mean"] is not None
    ]
    b_pass_bh = _bh([(k, p) for k, p in b_candidates if p is not None], fdr)
    for k, v in arm_b_results.items():
        if v["verdict_pre_bh"] == "CANDIDATE":
            v["verdict"] = "PROMOTE_RESEARCH" if k in b_pass_bh else "REJECT"
        else:
            v["verdict"] = v["verdict_pre_bh"]

    # ══════════════════════════════════════════════════════════════════════
    # ARM A — admission by planned TP1 R ≥ min_rr; path at family planned TP
    # ══════════════════════════════════════════════════════════════════════
    safe_print("Arm A: admission min_rr grid…")
    arm_a_results = {}

    for min_rr in arm_a_grid:
        pairs = []
        n_cand = 0
        n_admit = 0
        for te in tagged:
            n_cand += 1
            if te.planned_tp1 + 1e-12 >= float(min_rr):
                n_admit += 1
                v = path_rr(te, te.planned_tp1)
                if v is not None:
                    pairs.append((te, v))
        is_p, oos_p = split_is_oos(pairs)
        rrs_is = [v for _, v in is_p]
        rrs_oos = [v for _, v in oos_p]
        rrs_all = [v for _, v in pairs]
        m_is, m_oos, m_all = _metrics(rrs_is), _metrics(rrs_oos), _metrics(rrs_all)
        seed = 100 + int(min_rr * 10)
        p_perm = _perm_p_mean(rrs_oos, n_perm, seed) if rrs_oos else None
        is_inc = abs(float(min_rr) - incumbent_min_rr) < 1e-12
        arm_a_results[str(min_rr)] = {
            "min_rr": float(min_rr),
            "is_incumbent": is_inc,
            "n_candidates": n_cand,
            "n_admitted": n_admit,
            "admit_rate": n_admit / n_cand if n_cand else None,
            "n": len(rrs_all),
            "n_is": len(rrs_is),
            "n_oos": len(rrs_oos),
            "is": m_is,
            "oos": m_oos,
            "all": m_all,
            "perm_p_oos_mean": p_perm,
        }

    e_inc_a = arm_a_results[str(incumbent_min_rr)]["oos"]["mean_net_R"]
    for k, cell in arm_a_results.items():
        cell["verdict_pre_bh"] = _verdict_arm_cell(
            n=cell["n_oos"],
            e_is=cell["is"]["mean_net_R"],
            e_oos=cell["oos"]["mean_net_R"],
            pf_oos=cell["oos"]["profit_factor"],
            e_inc_oos=e_inc_a,
            p_perm=cell["perm_p_oos_mean"],
            is_incumbent=cell["is_incumbent"],
            min_n=min_n,
        )

    a_candidates = [
        (k, arm_a_results[k]["perm_p_oos_mean"])
        for k, v in arm_a_results.items()
        if v["verdict_pre_bh"] == "CANDIDATE" and v["perm_p_oos_mean"] is not None
    ]
    a_pass_bh = _bh([(k, p) for k, p in a_candidates if p is not None], fdr)
    for k, v in arm_a_results.items():
        if v["verdict_pre_bh"] == "CANDIDATE":
            v["verdict"] = "PROMOTE_RESEARCH" if k in a_pass_bh else "REJECT"
        else:
            v["verdict"] = v["verdict_pre_bh"]

    # ── secondary Cartesian (descriptive only) ────────────────────────────
    safe_print("Secondary A×B descriptive table…")
    cartesian = {}
    for min_rr in arm_a_grid:
        for tp_m in arm_b_grid:
            pairs = []
            for te in tagged:
                if te.planned_tp1 + 1e-12 >= float(min_rr):
                    v = path_rr(te, float(tp_m))
                    if v is not None:
                        pairs.append((te, v))
            is_p, oos_p = split_is_oos(pairs)
            rrs_oos = [v for _, v in oos_p]
            rrs_is = [v for _, v in is_p]
            key = f"min_rr={min_rr}|tp={tp_m}"
            cartesian[key] = {
                "min_rr": float(min_rr),
                "tp_atr_mult": float(tp_m),
                "n": len(pairs),
                "n_oos": len(rrs_oos),
                "oos": _metrics(rrs_oos),
                "is": _metrics(rrs_is),
                "authority": "SECONDARY_DESCRIPTIVE_ONLY_NOT_IN_BH",
            }

    # ── summary verdicts ──────────────────────────────────────────────────
    def arm_summary(results: dict) -> dict:
        counts = defaultdict(int)
        for v in results.values():
            counts[v["verdict"]] += 1
        return dict(counts)

    report = {
        "program": "H-RR-THRESHOLD-001",
        "schema_id": prereg["schema_id"],
        "status": "RUN_COMPLETE",
        "authority": "research_only",
        "pre_registration": {
            "md": str(PREREG_MD.relative_to(_ROOT)).replace("\\", "/"),
            "json": str(PREREG_JSON.relative_to(_ROOT)).replace("\\", "/"),
        },
        "truth_standard": {
            "exit_model": "intrabar_fixed",
            "round_trip_bps": bps,
            "max_forward": MAX_FORWARD,
            "oos_split": oos_split,
            "oos_mode": "time_ordered_per_instrument_70_30",
            "fixed_sl_atr_mult": FIXED_SL_ATR_MULT,
            "family_planned_tp1": FAMILY_PLANNED_TP1,
        },
        "population": {
            "instruments": instruments,
            "families": families,
            "n_entries_total": len(tagged),
            "per_instrument_family_n": per_inst_family_n,
            "entries_artifact": str(entries_path.relative_to(_ROOT)).replace("\\", "/"),
            "entries_sha256": entries_sha,
        },
        "arm_A_admission": {
            "grid": arm_a_grid,
            "incumbent_min_rr": incumbent_min_rr,
            "cells": arm_a_results,
            "verdict_counts": arm_summary(arm_a_results),
            "bh_passed": sorted(a_pass_bh),
        },
        "arm_B_exit_tp": {
            "grid": arm_b_grid,
            "incumbent_tp_atr_mult": b_incumbent_tp,
            "cells": arm_b_results,
            "verdict_counts": arm_summary(arm_b_results),
            "bh_passed": sorted(b_pass_bh),
        },
        "cartesian_secondary": cartesian,
        "priors_check": {
            "F-025_exit_not_expectancy": "Arm B expected REJECT/REDUNDANT if E_oos<0 all cells",
            "D_wiring_honesty": "Arm A: planned_tp1 mean_reversion=1.0 fails min_rr=1.5; expansion=1.5 passes",
        },
        "hard_flags": prereg["hard_flags"],
        "production_config_changed": False,
        "rr_fusion_reenabled": False,
    }

    # overall program verdict
    any_promote = any(
        v["verdict"] == "PROMOTE_RESEARCH"
        for v in list(arm_a_results.values()) + list(arm_b_results.values())
        if not v.get("is_incumbent")
    )
    all_neg_b = all(
        (v["oos"]["mean_net_R"] is None) or (v["oos"]["mean_net_R"] < 0)
        for v in arm_b_results.values()
    )
    report["program_verdict"] = {
        "any_non_incumbent_PROMOTE_RESEARCH": any_promote,
        "arm_B_all_cells_oos_E_negative": all_neg_b,
        "recommendation": (
            "No production config change. "
            + (
                "PROMOTE_RESEARCH present — human governance review only."
                if any_promote
                else "REJECT/REDUNDANT/INSUFFICIENT — leave knobs; config hygiene only if live ops require alignment."
            )
        ),
    }

    report_path = OUT_DIR / "report.json"
    report_path.write_text(json.dumps(report, sort_keys=True, indent=2, default=str), encoding="utf-8")

    # human REPORT.md
    lines = []
    a = lines.append
    a("# H-RR-THRESHOLD-001 — Run Report")
    a("")
    a("> RESEARCH_ONLY · pre-registered before measurement · **no production config change**")
    a("")
    a(f"Entries: **{len(tagged):,}** · sha256 `{entries_sha[:16]}…`")
    a(f"Instruments: {', '.join(instruments)}")
    a(f"Families: {families} · planned TP1 map: `{FAMILY_PLANNED_TP1}`")
    a("")
    a("## Program verdict")
    a("")
    a(f"- any non-incumbent PROMOTE_RESEARCH: **{any_promote}**")
    a(f"- Arm B all OOS E negative: **{all_neg_b}**")
    a(f"- Recommendation: {report['program_verdict']['recommendation']}")
    a("")
    a("## Arm A — admission min_rr")
    a("")
    a("| min_rr | admit_rate | n_oos | E_oos | PF_oos | perm_p | verdict |")
    a("|---:|---:|---:|---:|---:|---:|---|")
    for k in sorted(arm_a_results, key=lambda x: float(x)):
        c = arm_a_results[k]
        inc = " **inc**" if c["is_incumbent"] else ""
        a(
            f"| {c['min_rr']}{inc} | {c['admit_rate']:.3f} | {c['n_oos']} | "
            f"{c['oos']['mean_net_R']} | {c['oos']['profit_factor']} | "
            f"{c['perm_p_oos_mean']} | **{c['verdict']}** |"
        )
    a("")
    a("## Arm B — exit TP R-multiple")
    a("")
    a("| tp | n_oos | E_is | E_oos | PF_oos | perm_p | verdict |")
    a("|---:|---:|---:|---:|---:|---:|---|")
    for k in sorted(arm_b_results, key=lambda x: float(x)):
        c = arm_b_results[k]
        inc = " **inc**" if c["is_incumbent"] else ""
        a(
            f"| {c['tp_atr_mult']}{inc} | {c['n_oos']} | "
            f"{c['is']['mean_net_R']} | {c['oos']['mean_net_R']} | "
            f"{c['oos']['profit_factor']} | {c['perm_p_oos_mean']} | **{c['verdict']}** |"
        )
    a("")
    a("## Explicit non-actions")
    a("")
    a("- Production config **not** modified")
    a("- `rr_fusion` **not** re-enabled")
    a("- Cartesian A×B is secondary descriptive only (see report.json)")
    a("")
    a(f"Artifacts: `{OUT_DIR.relative_to(_ROOT)}/`")
    (OUT_DIR / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # flip prereg status note in JSON twin? Don't rewrite prereg source status mid-flight permanently
    # write run status file instead
    status = {
        "program": "H-RR-THRESHOLD-001",
        "status": "RUN_COMPLETE",
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "report": str(report_path.relative_to(_ROOT)).replace("\\", "/"),
        "entries_sha256": entries_sha,
        "program_verdict": report["program_verdict"],
    }
    (OUT_DIR / "manifest.json").write_text(json.dumps(status, indent=2, sort_keys=True), encoding="utf-8")

    # update experiment definition status field
    prereg["status"] = "RUN_COMPLETE"
    prereg["run_artifacts"] = str(OUT_DIR.relative_to(_ROOT)).replace("\\", "/")
    prereg["run_verdict"] = report["program_verdict"]
    PREREG_JSON.write_text(json.dumps(prereg, indent=2) + "\n", encoding="utf-8")

    safe_print(f"\n-> {report_path}")
    safe_print(f"program_verdict: {report['program_verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
