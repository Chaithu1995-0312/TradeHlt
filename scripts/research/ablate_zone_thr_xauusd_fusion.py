# -*- coding: utf-8 -*-
"""Full-fusion ZoneGate threshold ablation on XAUUSD.

Gate-ON (BACKTEST_ENGINE_GATE=1) so EngineRunner fusion actually runs — the
research default is gate-OFF (F-037). Sweeps engine_runner.zone_cluster_threshold
with weight_zone_gate fixed at the active 0.2. Compares trade-ledger SHA and
Layer-1 G001 metrics vs baseline thr=0.25.

MEASURE-ONLY: injects knobs via get_prod_section wrap — no JSON edit, no rehash,
no promotion. Authority: research observation only.

Usage:
  python scripts/research/ablate_zone_thr_xauusd_fusion.py
  python scripts/research/ablate_zone_thr_xauusd_fusion.py --thresholds 0.25 0.5 0.75 0.9
  python scripts/research/ablate_zone_thr_xauusd_fusion.py --no-selfcheck
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import logging
import os
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

# Full-fusion path (overrides .env research default BACKTEST_ENGINE_GATE=0).
os.environ["BACKTEST_ENGINE_GATE"] = "1"
os.environ.setdefault(
    "RESEARCH_SPINE_CONFIG",
    "configs/research/research_config_spine_majors.json",
)

import qualify_zone_topk as qz  # noqa: E402
import config_layer.production_config as _pc  # noqa: E402
from research.config import ResearchConfig  # noqa: E402
from research.provenance import provenance_block  # noqa: E402
from research.qualification import (  # noqa: E402
    BH_METHOD_VERSION,
    PERMUTATION_METHOD_VERSION,
    QUALIFICATION_VERSION,
)
from utils.console_safe import safe_print  # noqa: E402

SPINE_CONFIG = os.environ["RESEARCH_SPINE_CONFIG"]
INSTRUMENT = "XAUUSD"
DEF_WEIGHT = 0.2
DEF_THRESH = 0.25

# Dense thr grid around the scores.jsonl discriminative region (prior thr sweep).
DEFAULT_THRESHOLDS = [
    0.0,
    0.25,  # active baseline
    0.40,
    0.50,
    0.60,
    0.65,
    0.70,
    0.75,
    0.80,
    0.85,
    0.90,
]


class _InjectZoneThr:
    """Patch fusion weight (fixed) + engine_runner.zone_cluster_threshold (cell)."""

    def __init__(self, weight: float, threshold: float):
        self.weight = weight
        self.threshold = threshold
        self._orig = None

    def __enter__(self):
        orig = _pc.get_prod_section
        w, t = self.weight, self.threshold

        def patched(name, *args, **kwargs):
            sec = orig(name, *args, **kwargs)
            if name == "fusion_engine":
                sec = copy.deepcopy(sec)
                sec["weight_zone_gate"] = w
            elif name == "engine_runner":
                sec = copy.deepcopy(sec)
                sec["zone_cluster_threshold"] = t
            return sec

        self._orig = orig
        _pc.get_prod_section = patched
        return self

    def __exit__(self, *exc):
        _pc.get_prod_section = self._orig
        return False


def _selfcheck(version: str, root: Path) -> dict:
    # Unpatched (gate already ON via env)
    _, _, sha_un = qz._run_spine_once(INSTRUMENT, version, root / "_selfcheck_unpatched")
    with _InjectZoneThr(DEF_WEIGHT, DEF_THRESH):
        _, _, sha_pa = qz._run_spine_once(INSTRUMENT, version, root / "_selfcheck_patched")
    return {
        "instrument": INSTRUMENT,
        "unpatched_sha": sha_un,
        "patched_default_sha": sha_pa,
        "byte_identical": bool(sha_un) and sha_un == sha_pa,
        "backtest_engine_gate": os.environ.get("BACKTEST_ENGINE_GATE"),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--thresholds",
        nargs="*",
        type=float,
        default=DEFAULT_THRESHOLDS,
        help="zone_cluster_threshold values to ablate",
    )
    ap.add_argument(
        "--out",
        default="results/research/zone_thr_ablation_xauusd_fusion",
    )
    ap.add_argument("--no-selfcheck", action="store_true")
    ap.add_argument("--no-m4", action="store_true", help="skip M4 on changed cells")
    args = ap.parse_args(argv)

    if not (Path("data") / f"{INSTRUMENT}_M15.csv").exists():
        raise SystemExit(f"missing data/{INSTRUMENT}_M15.csv")

    logging.getLogger("CRT").setLevel(logging.ERROR)
    logging.getLogger("ENGINE_RUNNER").setLevel(logging.ERROR)
    logging.getLogger("ZONE_GATE").setLevel(logging.ERROR)
    logging.getLogger("FEATURE_PIPELINE").setLevel(logging.ERROR)

    spine_block = json.loads(Path(SPINE_CONFIG).read_text(encoding="utf-8")).get("spine", {})
    version = spine_block.get("prod_version") or qz._bt.PROD_VERSION

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    spine_root = out_dir / "_spine"

    safe_print("=== XAUUSD full-fusion ZoneGate thr ablation ===")
    safe_print(f"BACKTEST_ENGINE_GATE={os.environ.get('BACKTEST_ENGINE_GATE')}")
    safe_print(f"prod_version={version}")
    safe_print(f"weight_zone_gate fixed={DEF_WEIGHT}")
    safe_print(f"thresholds={args.thresholds}")

    selfcheck = None
    if not args.no_selfcheck:
        safe_print("\nself-check (injection neutral at thr=0.25)…")
        selfcheck = _selfcheck(version, spine_root)
        safe_print(
            f"  byte_identical={selfcheck['byte_identical']} "
            f"sha={ (selfcheck['unpatched_sha'] or '')[:12] }"
        )
        if not selfcheck["byte_identical"]:
            raise SystemExit(
                "self-check FAILED — get_prod_section wrap not neutral at defaults. STOP."
            )

    # Ensure baseline thr is first
    thresholds = list(args.thresholds)
    if DEF_THRESH not in thresholds:
        thresholds = [DEF_THRESH] + thresholds
    # de-dupe preserve order
    seen = set()
    thr_list = []
    for t in thresholds:
        if t not in seen:
            thr_list.append(float(t))
            seen.add(t)

    baseline_sha = ""
    baseline_l1: dict = {}
    cells: dict = {}
    any_change = False

    for thr in thr_list:
        cid = f"thr_{str(thr).replace('.', 'p')}"
        is_baseline = abs(thr - DEF_THRESH) < 1e-12
        safe_print(f"\n[cell {cid}] zone_cluster_threshold={thr} weight={DEF_WEIGHT}")
        with _InjectZoneThr(DEF_WEIGHT, thr):
            try:
                l1, entries, sha = qz._run_spine_once(
                    INSTRUMENT, version, spine_root / cid / INSTRUMENT
                )
            except Exception as e:  # noqa: BLE001
                safe_print(f"  ERROR: {e}")
                cells[cid] = {
                    "threshold": thr,
                    "weight_zone_gate": DEF_WEIGHT,
                    "error": str(e),
                }
                continue

        if is_baseline:
            baseline_sha = sha
            baseline_l1 = dict(l1)

        changed = (not is_baseline) and bool(baseline_sha) and sha != baseline_sha
        any_change = any_change or changed
        flag = "  CHANGED" if changed else ("  BASELINE" if is_baseline else "  identical")
        safe_print(
            f"  trades={l1.get('approved_trades')} E_r={l1.get('expectancy_r', 0):+.4f} "
            f"tpm={l1.get('trades_per_month')} WR={l1.get('win_rate')} "
            f"entries={len(entries)} sha={(sha or '')[:12]}{flag}"
        )

        m4 = {}
        if changed and not args.no_m4:
            try:
                m4 = qz._m4_for_cell({INSTRUMENT: entries}, [INSTRUMENT])
                safe_print(f"  M4: { {k: v.get('verdict') for k, v in m4.items()} }")
            except Exception as e:  # noqa: BLE001
                m4 = {"error": str(e)}
                safe_print(f"  M4 ERROR: {e}")

        delta_e = None
        if baseline_l1 and "expectancy_r" in l1 and "expectancy_r" in baseline_l1:
            delta_e = round(
                float(l1["expectancy_r"]) - float(baseline_l1["expectancy_r"]), 6
            )

        cells[cid] = {
            "threshold": thr,
            "weight_zone_gate": DEF_WEIGHT,
            "is_baseline": is_baseline,
            "layer1_g001": l1,
            "entry_count": len(entries),
            "trades_sha": sha,
            "entries_changed_vs_baseline": changed,
            "delta_expectancy_r_vs_baseline": delta_e,
            "delta_trades_vs_baseline": (
                int(l1.get("approved_trades", 0))
                - int(baseline_l1.get("approved_trades", 0))
                if baseline_l1
                else None
            ),
            "layer2_m4_on_change": m4,
        }

    if not any_change:
        verdict = (
            "ZONE_THR_NON_PIVOTAL_ON_XAUUSD_FUSION — entry set byte-identical across all "
            f"tested zone_cluster_threshold values (gate-ON, weight={DEF_WEIGHT}); thr lever "
            "does not flip live decisions on this corpus."
        )
    else:
        changed_cells = [
            k for k, v in cells.items() if v.get("entries_changed_vs_baseline")
        ]
        verdict = (
            "ENTRY_SET_CHANGED — at least one thr moved the XAUUSD fusion entry set: "
            + ", ".join(changed_cells)
        )

    rc = ResearchConfig.from_file(SPINE_CONFIG)
    body = {
        "experiment": "zone_thr_ablation_xauusd_full_fusion",
        "instrument": INSTRUMENT,
        "mode": "full_fusion_gate_on",
        "backtest_engine_gate": os.environ.get("BACKTEST_ENGINE_GATE"),
        "baseline": {
            "weight_zone_gate": DEF_WEIGHT,
            "zone_cluster_threshold": DEF_THRESH,
        },
        "thresholds": thr_list,
        "prod_version": version,
        "qualification_version": QUALIFICATION_VERSION,
        "permutation_method_version": PERMUTATION_METHOD_VERSION,
        "bh_method_version": BH_METHOD_VERSION,
        "spine_config_sha256": rc.sha256(),
        **provenance_block(rc.exit_model, rc.round_trip_bps),
        "selfcheck": selfcheck,
        "any_entry_change": any_change,
        "verdict": verdict,
        "cells": cells,
        "authority": (
            "research observation only — no promote, no config edit; "
            "tunability ≠ authority (CLAUDE.md §6.5)"
        ),
        "prior_context": {
            "scores_jsonl_thr_sweep": "results/analysis/zone_gate_xauusd_trace/threshold_sweep.json",
            "note": (
                "Standalone ZoneGate scores on XAUUSD were 100% pass at thr<=0.40; "
                "this ablation tests whether thr still moves the FULL fusion entry set "
                "(CRT proposes; fusion+decision consume zone pass/fail + score)."
            ),
        },
    }
    body_json = json.dumps(body, sort_keys=True, indent=2)
    body_sha = hashlib.sha256(body_json.encode("utf-8")).hexdigest()
    (out_dir / "zone_thr_ablation_xauusd_fusion.json").write_text(
        body_json, encoding="utf-8"
    )
    (out_dir / "zone_thr_ablation_xauusd_fusion_manifest.json").write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "git_commit": qz._git_commit(),
                "body_sha256": body_sha,
                "spine_config_sha256": rc.sha256(),
                "instrument": INSTRUMENT,
                "any_entry_change": any_change,
                "verdict": verdict,
            },
            sort_keys=True,
            indent=2,
        ),
        encoding="utf-8",
    )

    # Compact table for console
    safe_print("\n=== SUMMARY TABLE ===")
    safe_print(
        f"{'thr':>6} {'trades':>7} {'entries':>8} {'E_r':>9} "
        f"{'dE':>9} {'dN':>5} {'vs base':>10}"
    )
    for thr in thr_list:
        cid = f"thr_{str(thr).replace('.', 'p')}"
        c = cells.get(cid, {})
        if "error" in c:
            safe_print(f"{thr:6.2f} ERROR {c['error'][:60]}")
            continue
        l1 = c.get("layer1_g001") or {}
        tag = (
            "BASELINE"
            if c.get("is_baseline")
            else ("CHANGED" if c.get("entries_changed_vs_baseline") else "identical")
        )
        dE = c.get("delta_expectancy_r_vs_baseline")
        dN = c.get("delta_trades_vs_baseline")
        dE_s = f"{dE:+.4f}" if dE is not None else "n/a"
        dN_s = f"{dN:+d}" if dN is not None else "n/a"
        safe_print(
            f"{thr:6.2f} {l1.get('approved_trades', 0):7d} {c.get('entry_count', 0):8d} "
            f"{float(l1.get('expectancy_r') or 0):+9.4f} {dE_s:>9} {dN_s:>5} {tag:>10}"
        )

    safe_print(f"\nVERDICT: {verdict}")
    safe_print(f"body_sha256={body_sha}")
    safe_print(f"-> {out_dir / 'zone_thr_ablation_xauusd_fusion.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
