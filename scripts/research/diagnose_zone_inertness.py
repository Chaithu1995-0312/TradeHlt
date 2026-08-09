# -*- coding: utf-8 -*-
"""diagnose_zone_inertness.py — WHY is the zone cluster inert on the live spine? (mechanism behind F-036)

F-036 proved top_k is inert (ΔG001 ≡ 0) but left the MECHANISM open. Zone reaches an entry
decision ONLY through the engine_runner fusion veto (CRT proposes; config use_bitnet=false →
CRT itself ignores zones), via two channels:
  • SCORE channel     — fusion_engine.weight_zone_gate (the weighted-average contribution)
  • DIRECTION channel — engine_runner.zone_cluster_threshold (zone "passed" → BUY vote / abstain)

ABLATION-FIRST (decisive, deterministic). Sweep each channel config-only and compare the
ENTRY SET (trade-ledger sha256) vs the * baseline. Byte-identical ledger ⇒ that channel is
NON-PIVOTAL — a proof, no statistics needed (you can't bootstrap a difference that is exactly
zero). ONLY cells that CHANGE the entry set are routed through the existing M4 QualificationGate
(perm/BH/OOS/controls) — the repo's significance instrument, reused, nothing new built.

  SCORE cells:     weight_zone_gate ∈ {0.0, 0.2*, 0.4, 0.6}   (threshold at default 0.25)
  DIRECTION cells: zone_cluster_threshold ∈ {0.0, 0.25*, 0.5}  (weight at default 0.2)

CAVEAT (honest): FusionEngine renormalizes by the sum of PRESENT weights (fusion_engine.py:487),
so weight=0 cleanly removes zone from the weighted average + renormalizes the other 3. But the
ConvergenceController stability layer still sees zone's RAW score in its variance/entropy term
(a weak third channel); fully neutralizing that needs a code hook (deferred unless a config cell
surfaces a lead). The weight+threshold sweep covers the two PRIMARY channels.

PHASE 2 (explanatory, no new instrumentation). One baseline BNB run with debug_mode=True →
the existing SignalAuditRecorder writes per-candidate-bar {zone score, all engine scores, fused
score, decision} to logs/signal_audit.jsonl. Parse → zone-score distribution on ACCEPT vs REJECT
candidate bars, distance to 0.25, zone's rank among the four engines.

Reuses the qualify_zone_topk harness verbatim (spine run + M4 + provenance). Injection via the
same get_prod_section deep-copy wrap. MEASURE-ONLY: no JSON edit, no rehash, no promotion.

Usage:
    python scripts/research/diagnose_zone_inertness.py                 # 4 majors, both channels
    python scripts/research/diagnose_zone_inertness.py --instruments BNBUSDT
    python scripts/research/diagnose_zone_inertness.py --no-phase2     # ablation only
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import logging
import os
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
_RESEARCH = _ROOT / "scripts" / "research"
for _p in (str(_SRC), str(_RESEARCH)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
os.chdir(_ROOT)

# Reuse the F-036 harness verbatim (keeps spine-run semantics byte-identical to qualify_zone_topk).
import qualify_zone_topk as qz                                        # noqa: E402
from research.provenance import provenance_block                     # noqa: E402
from research.config import ResearchConfig                           # noqa: E402
from research.qualification import (                                  # noqa: E402
    BH_METHOD_VERSION, PERMUTATION_METHOD_VERSION, QUALIFICATION_VERSION,
)
from utils.console_safe import safe_print                            # noqa: E402

_pc = qz._pc
SPINE_CONFIG = qz.SPINE_CONFIG
MAJORS = qz.MAJORS
AUDIT_LOG = Path("logs/signal_audit.jsonl")

# Active-config defaults = the byte-parity baseline of BOTH channels.
DEF_WEIGHT = 0.2
DEF_THRESH = 0.25

# Channel sweeps (baseline value marked with *).
SCORE_WEIGHTS = [0.0, 0.2, 0.4, 0.6]      # 0.2*
DIR_THRESHOLDS = [0.0, 0.25, 0.5]          # 0.25*


# ─────────────────────────────────────────────────────────────────────────────
# Injection — wrap get_prod_section to override the zone channels (+ optional debug).
# ─────────────────────────────────────────────────────────────────────────────
class _InjectZoneChannels:
    """Context manager: patch production_config.get_prod_section so a read of 'fusion_engine'
    carries weight_zone_gate and a read of 'engine_runner' carries zone_cluster_threshold (and,
    for Phase 2, debug_mode). Deep-copies the section so the cached config is never mutated."""

    def __init__(self, weight: float, threshold: float, debug: bool | None = None):
        self.weight = weight
        self.threshold = threshold
        self.debug = debug
        self._orig = None

    def __enter__(self):
        orig = _pc.get_prod_section
        w, t, dbg = self.weight, self.threshold, self.debug

        def patched(name, *args, **kwargs):
            sec = orig(name, *args, **kwargs)
            if name == "fusion_engine":
                sec = copy.deepcopy(sec)
                sec["weight_zone_gate"] = w
            elif name == "engine_runner":
                sec = copy.deepcopy(sec)
                sec["zone_cluster_threshold"] = t
                if dbg is not None:
                    sec["debug_mode"] = dbg
            return sec

        self._orig = orig
        _pc.get_prod_section = patched
        return self

    def __exit__(self, *exc):
        _pc.get_prod_section = self._orig
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Cells
# ─────────────────────────────────────────────────────────────────────────────
def _cells() -> list[dict]:
    """Baseline first (ΔG001 + sha reference), then the score & direction channel cells."""
    cells = [{"id": "baseline_w0p2_t0p25", "channel": "baseline",
              "weight": DEF_WEIGHT, "threshold": DEF_THRESH}]
    for w in SCORE_WEIGHTS:
        if w == DEF_WEIGHT:
            continue
        cells.append({"id": f"score_w{str(w).replace('.', 'p')}", "channel": "score",
                      "weight": w, "threshold": DEF_THRESH})
    for t in DIR_THRESHOLDS:
        if t == DEF_THRESH:
            continue
        cells.append({"id": f"dir_t{str(t).replace('.', 'p')}", "channel": "direction",
                      "weight": DEF_WEIGHT, "threshold": t})
    return cells


# ─────────────────────────────────────────────────────────────────────────────
# Self-check — patched-default == unpatched (injection neutral at the active defaults).
# ─────────────────────────────────────────────────────────────────────────────
def _selfcheck(version: str, root: Path, instrument: str) -> dict:
    _, _, sha_un = qz._run_spine_once(instrument, version, root / "_selfcheck_unpatched")
    with _InjectZoneChannels(DEF_WEIGHT, DEF_THRESH):
        _, _, sha_pa = qz._run_spine_once(instrument, version, root / "_selfcheck_patched")
    return {"instrument": instrument, "unpatched_sha": sha_un, "patched_default_sha": sha_pa,
            "byte_identical": bool(sha_un) and sha_un == sha_pa}


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2 — parse logs/signal_audit.jsonl from a debug_mode=True baseline BNB run.
# ─────────────────────────────────────────────────────────────────────────────
def _phase2_distribution(version: str, root: Path, instrument: str) -> dict:
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_LOG.write_text("", encoding="utf-8")  # truncate — recorder appends
    with _InjectZoneChannels(DEF_WEIGHT, DEF_THRESH, debug=True):
        l1, _, sha = qz._run_spine_once(instrument, version, root / "_phase2_debug")
    rows = []
    if AUDIT_LOG.exists():
        for line in AUDIT_LOG.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    def _zone_score(r):
        return float(((r.get("zone") or {}).get("score")) or
                     ((r.get("engines") or {}).get("zone_gate", {}) or {}).get("score", 0.0))

    def _eng(r, k):
        return float(((r.get("engines") or {}).get(k, {}) or {}).get("score", 0.0))

    def _accepted(r):
        return str(r.get("decision", "")).lower() in ("execute", "approve")

    def _stats(vals):
        vals = [v for v in vals if v is not None]
        if not vals:
            return {"n": 0}
        s = sorted(vals)
        return {
            "n": len(vals),
            "mean": round(statistics.fmean(vals), 4),
            "median": round(statistics.median(vals), 4),
            "min": round(s[0], 4), "max": round(s[-1], 4),
            "p10": round(s[max(0, int(0.10 * (len(s) - 1)))], 4),
            "p90": round(s[min(len(s) - 1, int(0.90 * (len(s) - 1)))], 4),
        }

    zone_all = [_zone_score(r) for r in rows]
    acc = [r for r in rows if _accepted(r)]
    rej = [r for r in rows if not _accepted(r)]
    # How often zone is the strongest / weakest of the four engines on a bar.
    eng_names = ("crt", "gaussian", "zone_gate", "rr")
    zone_rank = []  # 0 = strongest .. 3 = weakest
    for r in rows:
        scores = {k: _eng(r, k) for k in eng_names}
        if not any(scores.values()):
            continue
        order = sorted(eng_names, key=lambda k: scores[k], reverse=True)
        zone_rank.append(order.index("zone_gate"))
    n = max(len(zone_all), 1)
    return {
        "instrument": instrument,
        "debug_run_sha": sha,
        "debug_run_trades": l1.get("approved_trades", 0),
        "audit_bars": len(rows),
        "zone_score_all": _stats(zone_all),
        "zone_score_accept": _stats([_zone_score(r) for r in acc]),
        "zone_score_reject": _stats([_zone_score(r) for r in rej]),
        "pct_bars_zone_ge_0p20": round(sum(1 for v in zone_all if v >= 0.20) / n, 4),
        "pct_bars_zone_ge_0p25": round(sum(1 for v in zone_all if v >= 0.25) / n, 4),
        "mean_distance_to_threshold": round(statistics.fmean(zone_all) - DEF_THRESH, 4) if zone_all else None,
        "zone_strongest_engine_pct": round(sum(1 for r in zone_rank if r == 0) / max(len(zone_rank), 1), 4),
        "zone_weakest_engine_pct": round(sum(1 for r in zone_rank if r == 3) / max(len(zone_rank), 1), 4),
        "engine_mean_scores": {k: round(statistics.fmean([_eng(r, k) for r in rows]), 4) if rows else 0.0
                               for k in eng_names},
    }


# ─────────────────────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="diagnose_zone_inertness",
                                description="Diagnose WHY the zone cluster is inert (mechanism behind F-036).")
    p.add_argument("--instruments", nargs="*", default=MAJORS)
    p.add_argument("--out", default="results/research/zone_inertness")
    p.add_argument("--no-phase2", action="store_true")
    p.add_argument("--no-selfcheck", action="store_true")
    args = p.parse_args(argv)

    os.environ["RESEARCH_SPINE_CONFIG"] = SPINE_CONFIG
    logging.getLogger("CRT").setLevel(logging.ERROR)
    logging.getLogger("ENGINE_RUNNER").setLevel(logging.ERROR)
    logging.getLogger("ZONE_GATE").setLevel(logging.ERROR)

    spine_block = json.loads(Path(SPINE_CONFIG).read_text(encoding="utf-8")).get("spine", {})
    version = spine_block.get("prod_version") or qz._bt.PROD_VERSION
    instruments = [i for i in args.instruments if (Path("data") / f"{i}_M15.csv").exists()]
    if not instruments:
        raise SystemExit(f"no data CSVs for {args.instruments}")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    spine_root = out_dir / "_spine"

    # ── self-check ────────────────────────────────────────────────────────────
    selfcheck = None
    if not args.no_selfcheck:
        safe_print("self-check (injection neutral at defaults)…")
        selfcheck = _selfcheck(version, spine_root, instruments[0])
        safe_print(f"  {selfcheck['instrument']}: byte_identical={selfcheck['byte_identical']}")
        if not selfcheck["byte_identical"]:
            raise SystemExit("self-check FAILED — get_prod_section wrap not neutral at defaults. STOP.")

    # ── ablation sweep ─────────────────────────────────────────────────────────
    cells = _cells()
    safe_print(f"\nAblation: {len(cells)} cells × {len(instruments)} instruments "
               f"(baseline weight={DEF_WEIGHT} threshold={DEF_THRESH})\n")
    cell_results: dict[str, dict] = {}
    baseline_sha: dict[str, str] = {}
    baseline_l1: dict[str, dict] = {}
    any_change = False

    for cell in cells:
        cid = cell["id"]
        safe_print(f"[cell {cid}] channel={cell['channel']} "
                   f"weight_zone_gate={cell['weight']} zone_cluster_threshold={cell['threshold']}")
        l1_by, entries_by, sha_by, changed_by = {}, {}, {}, {}
        with _InjectZoneChannels(cell["weight"], cell["threshold"]):
            for inst in instruments:
                try:
                    l1, entries, sha = qz._run_spine_once(inst, version, spine_root / cid / inst)
                    l1_by[inst], entries_by[inst], sha_by[inst] = l1, entries, sha
                    changed = bool(cell["channel"] != "baseline" and baseline_sha.get(inst)
                                   and sha != baseline_sha[inst])
                    changed_by[inst] = changed
                    any_change = any_change or changed
                    flag = "  CHANGED" if changed else ""
                    safe_print(f"    {inst}: trades={l1['approved_trades']} "
                               f"E_r={l1['expectancy_r']:+.4f} entries={len(entries)} "
                               f"sha={sha[:10]}{flag}")
                except Exception as e:                                       # noqa: BLE001
                    safe_print(f"    {inst}: ERROR {e}")
                    l1_by[inst] = {"error": str(e)}

        if cell["channel"] == "baseline":
            baseline_sha = dict(sha_by)
            baseline_l1 = dict(l1_by)

        # M4 only on cells that changed at least one instrument's entry set.
        changed_insts = [i for i in instruments if changed_by.get(i)]
        m4 = qz._m4_for_cell({i: entries_by[i] for i in changed_insts}, changed_insts) if changed_insts else {}

        cell_results[cid] = {
            "cell": cell,
            "layer1_g001": l1_by,
            "entry_counts": {i: len(entries_by.get(i, {})) for i in instruments},
            "trades_sha": sha_by,
            "entries_changed_vs_baseline": changed_by,
            "delta_expectancy_r_vs_baseline": {
                i: round(l1_by[i]["expectancy_r"] - baseline_l1[i]["expectancy_r"], 6)
                for i in instruments
                if i in baseline_l1 and "error" not in l1_by.get(i, {})
                and "error" not in baseline_l1.get(i, {})
            },
            "layer2_m4_on_change": m4,
        }

    # ── Phase 2 distribution ────────────────────────────────────────────────────
    phase2 = None
    if not args.no_phase2:
        safe_print("\nPhase 2 — baseline debug_mode audit distribution (BNB)…")
        try:
            phase2 = _phase2_distribution(version, spine_root, instruments[0])
            z = phase2["zone_score_all"]
            safe_print(f"  audit_bars={phase2['audit_bars']} zone_score mean={z.get('mean')} "
                       f"median={z.get('median')} ; %≥0.25={phase2['pct_bars_zone_ge_0p25']} ; "
                       f"zone strongest-engine {phase2['zone_strongest_engine_pct']:.0%}")
        except Exception as e:                                               # noqa: BLE001
            safe_print(f"  Phase 2 ERROR: {e}")
            phase2 = {"error": str(e)}

    # ── verdict ─────────────────────────────────────────────────────────────────
    verdict = ("ZONE_NON_PIVOTAL (entries byte-identical across both channels → zone never flips a "
               "live decision; default stays)" if not any_change
               else "ENTRY_SET_CHANGED — at least one cell moved entries; see layer2_m4_on_change")

    rc = ResearchConfig.from_file(SPINE_CONFIG)
    body = {
        "experiment": "zone_inertness_mechanism",
        "explains_finding": "F-036",
        "baseline": {"weight_zone_gate": DEF_WEIGHT, "zone_cluster_threshold": DEF_THRESH},
        "score_channel_weights": SCORE_WEIGHTS,
        "direction_channel_thresholds": DIR_THRESHOLDS,
        "instruments": instruments,
        "prod_version": version,
        "qualification_version": QUALIFICATION_VERSION,
        "permutation_method_version": PERMUTATION_METHOD_VERSION,
        "bh_method_version": BH_METHOD_VERSION,
        "spine_config_sha256": rc.sha256(),
        **provenance_block(rc.exit_model, rc.round_trip_bps),
        "selfcheck": selfcheck,
        "any_entry_change": any_change,
        "verdict": verdict,
        "cells": cell_results,
        "phase2_distribution": phase2,
    }
    body_json = json.dumps(body, sort_keys=True, indent=2)
    body_sha = hashlib.sha256(body_json.encode("utf-8")).hexdigest()
    (out_dir / "zone_inertness.json").write_text(body_json, encoding="utf-8")
    (out_dir / "zone_inertness_manifest.json").write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": qz._git_commit(),
        "body_sha256": body_sha,
        "spine_config_sha256": rc.sha256(),
    }, sort_keys=True, indent=2), encoding="utf-8")

    safe_print(f"\nVERDICT: {verdict}")
    safe_print(f"body_sha256={body_sha}")
    safe_print(f"-> {out_dir / 'zone_inertness.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
