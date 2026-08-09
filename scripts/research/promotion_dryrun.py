"""
promotion_dryrun.py — ODL-G3a/b proof + governed-promotion dry-run (SCRATCH registry, never the real one).

Produces results/live_path_replay/LINEAGE_PROOF.md:
  1. Fallback regression matrix for _load_full_base_config (ACTIVE=v4/v1, sparse, corrupted, missing).
  2. Full promote_from_report(crt_engine_overrides=BNB:1.3) into a TEMP registry, then load_version(v5)
     consistency audit: zero resurrected sections, CRT==Planner per symbol, config_hash/full/fingerprint.

The real configs/production/ACTIVE_VERSION is NEVER touched (everything runs in a tmp copy).
Run with: PYTHONUTF8=1 python scripts/research/promotion_dryrun.py
"""
from __future__ import annotations
import json, shutil, sys, tempfile
from pathlib import Path

sys.path.insert(0, "src")
import governance.promotion_manager as PM
from governance.promotion_manager import PromotionManager
from config_layer.config_validator import ConfigValidator
from config_layer.production_config import resolve_breakout_disp_threshold
from config_layer.crt_engine_v2 import ExecutionEngine
from config_layer.execution_planner import ExecutionPlannerV1_2

REAL = Path("configs/production")
OVERRIDE = {"breakout_disp_threshold": 1.5, "breakout_disp_threshold_overrides": {"BNBUSDT": 1.3}}
SYMS = ["BNBUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"]
OUT = Path("results/live_path_replay"); OUT.mkdir(parents=True, exist_ok=True)


def _secs(d): return {k for k, v in d.items() if isinstance(v, dict)}


def _set_active(tmp: Path, name: str):
    (tmp / "ACTIVE_VERSION").write_text(name + "\n", encoding="utf-8")


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="promo_dryrun_"))
    for p in REAL.glob("*.json"):
        shutil.copy2(p, tmp / p.name)
    shutil.copy2(REAL / "ACTIVE_VERSION", tmp / "ACTIVE_VERSION")
    # Redirect ALL promotion writes/reads into the scratch registry.
    PM.PRODUCTION_REGISTRY_DIR = str(tmp)
    PM.PROMOTION_LOG_FILE = str(tmp / "promotion_log.jsonl")

    v4 = json.load(open(tmp / "v4_multi_2026_06.json", encoding="utf-8"))
    v4_secs = _secs(v4)

    # ── 1. Fallback regression matrix ────────────────────────────────────────
    matrix = []
    def sel(label):
        try:
            base = PromotionManager._load_full_base_config(tmp)
            bid = (base or {}).get("config_id") or (base or {}).get("version") or "None"
            matrix.append((label, bid, "no" if bid not in ("None",) and "cfg_initial" not in str(bid) else "yes/baseline"))
        except Exception as e:
            matrix.append((label, f"EXC:{type(e).__name__}", "—"))

    _set_active(tmp, "v4_multi_2026_06"); sel("ACTIVE=v4 (full)")
    if (tmp / "v1_multi_2026_03.json").exists():
        _set_active(tmp, "v1_multi_2026_03"); sel("ACTIVE=v1 (full)")
    # sparse ACTIVE (no engine_runner sentinel)
    (tmp / "sparsecfg.json").write_text(json.dumps({"params": {"x": 1}, "config_id": "sparsecfg"}), encoding="utf-8")
    _set_active(tmp, "sparsecfg"); sel("ACTIVE sparse (no sentinel)")
    # corrupted ACTIVE (bad JSON)
    (tmp / "corrupt.json").write_text("{ not json", encoding="utf-8")
    _set_active(tmp, "corrupt"); sel("ACTIVE corrupted (bad JSON)")
    # missing ACTIVE pointer
    (tmp / "ACTIVE_VERSION").unlink()
    sel("ACTIVE_VERSION missing")
    # restore ACTIVE=v4 for the promotion
    _set_active(tmp, "v4_multi_2026_06")

    # ── 2. Governed promotion DRY-RUN into the scratch registry ───────────────
    report = ConfigValidator.validate(
        params=v4.get("params", {}),
        csv_paths={"BNBUSDT": "data/BNBUSDT_M15.csv"},
        config_id="v5_dryrun",
        engine_runner=v4.get("engine_runner"),
        crt_engine={**(v4.get("crt_engine") or {}), **OVERRIDE},
    )
    (tmp / "report.json").write_text(json.dumps(report), encoding="utf-8")
    promo = PromotionManager.promote_from_report(
        report_path=str(tmp / "report.json"),
        version="v5_bnb_disp13_2026_06",
        csv_paths={"BNBUSDT": "data/BNBUSDT_M15.csv"},
        notes="DRY-RUN: BNB disp 1.5->1.3 (scratch registry).",
        crt_engine_overrides=OVERRIDE,
    )
    v5 = PromotionManager.load_version("v5_bnb_disp13_2026_06", registry_dir=str(tmp))
    v5_secs = _secs(v5)
    resurrected = sorted(v5_secs - v4_secs)
    lost = sorted(v4_secs - v5_secs)
    v5_crt = v5.get("crt_engine", {})

    # CRT==Planner per symbol on the PROMOTED v5
    rows = []
    feats = {"body_ratio": 0.8, "disp_strength": 1.4, "retest_depth": 0.9, "candles_since_retest": 9,
             "momentum_score": 0.0, "sweep_detected": False, "double_sweep": False,
             "ema_fast": 1.0, "ema_slow": 2.0}
    er = {"decision": "execute", "direction": 1}
    for s in SYMS:
        thr = resolve_breakout_disp_threshold(v5_crt, s); thr = 1.5 if thr is None else thr
        crt_bo = ExecutionEngine._derive_trade_intent(feats, thr) == "breakout"
        pl_bo = ExecutionPlannerV1_2({"breakout_disp_threshold": thr})._derive_intent(feats, er)[0] == "BREAKOUT"
        rows.append((s, thr, "PASS" if crt_bo == pl_bo else "FAIL"))

    # ── Write LINEAGE_PROOF.md ────────────────────────────────────────────────
    L = ["# ODL-G3a/b — Lineage Proof + Promotion Dry-Run (scratch registry; real ACTIVE untouched)\n"]
    L.append("## 1. Fallback regression matrix (`_load_full_base_config`)\n")
    L.append("| Scenario | Selected base (config_id) | Fallback? |\n|---|---|---|")
    for lab, bid, fb in matrix:
        L.append(f"| {lab} | {bid} | {fb} |")
    L.append("\n## 2. Lineage: current vs proposed (v4→v5)\n")
    L.append("| Algorithm | Merge base | v5 resurrects | v5 loses |\n|---|---|---|---|")
    L.append("| CURRENT (superset guard) | v1 (cfg_initial_2026_03_24) | 11 pruned sections | live_integration, uat |")
    L.append(f"| PROPOSED (sentinel) | v4_multi_2026_06 | {resurrected or 'NONE'} | {lost or 'NONE'} |")
    L.append("\n## 3. Promotion dry-run consistency audit (promoted v5)\n")
    L.append(f"- promote decision: **{promo.get('status', promo.get('decision', '?'))}**")
    L.append(f"- v5 sections == v4 sections: **{v5_secs == v4_secs}** (resurrected={resurrected or 'NONE'}, lost={lost or 'NONE'})")
    L.append(f"- config_hash == sha256(params): **{v5.get('config_hash') == PromotionManager._compute_config_hash(v5.get('params', {}))}**")
    L.append(f"- config_hash_full present: **{'config_hash_full' in v5}**")
    L.append(f"- validation_summary.params_fingerprint present: **{'params_fingerprint' in v5.get('validation_summary', {})}**")
    L.append("\n| Symbol | v5 resolved disp | CRT==Planner |\n|---|--:|---|")
    for s, thr, verdict in rows:
        L.append(f"| {s} | {thr} | {verdict} |")
    ok = (v5_secs == v4_secs) and all(v == "PASS" for _, _, v in rows) and ("config_hash_full" in v5)
    L.append(f"\n**DRY-RUN VERDICT: {'PASS — safe to promote for real' if ok else 'FAIL — DO NOT PROMOTE'}**")
    (OUT / "LINEAGE_PROOF.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    print(f"\nwrote {OUT / 'LINEAGE_PROOF.md'}  | scratch registry: {tmp}")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
