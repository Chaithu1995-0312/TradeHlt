"""
_promote_v4_bnb_cutover.py — one-off GOVERNED cutover.

Builds v4_multi_2026_06 = the running 'v2_multi_2026_04 - deepdeektry' config
(ml Gaussian + its engine sections, the +20.59% sweep lineage) + a BNBUSDT
all-sessions allowed_sessions_overrides. SOLUSDT intentionally excluded (PF~1).

Governance: runs ConfigValidator on the changed instrument (BNBUSDT) with the
candidate engine_runner; only on decision == APPROVE does it (a) write the new
full config file, (b) flip ACTIVE_VERSION, (c) append a PROMOTED log entry, with
a params_fingerprint freshness anchor. Nothing mutates unless APPROVE.

Why not PromotionManager.promote_*? That path carries only the 5 `params` and
merges them onto a base, INHERITING engine sections from the base — it would drop
the allowed_sessions_overrides (which live in engine_runner). So a full-config
session-override promotion must be written directly, then governed via the log +
freshness anchor (verified at the end with config_integrity.audit).
"""
from __future__ import annotations
import hashlib, json, shutil, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # repo root
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from config_layer.config_validator import ConfigValidator          # noqa: E402
from governance import config_integrity as ci                      # noqa: E402
from governance.promotion_manager import PromotionManager          # noqa: E402

PROD = ROOT / "configs" / "production"
ACTIVE = PROD / "ACTIVE_VERSION"
LOG = ROOT / "configs" / "promotion_log.jsonl"      # real PROMOTION_LOG_FILE location
SRC_CFG = PROD / "v2_multi_2026_04 - deepdeektry.json"
NEW_VERSION = "v4_multi_2026_06"
BNB_ALL_SESSIONS = ["london", "new_york", "overlap", "asia", "off_session"]
SWEEP_EVIDENCE = ("BNBUSDT all-sessions sweep (auto_tuner, ml Gaussian, production path): "
                  "35 trades, PF 2.535, +20.59% total, MAR 6.65, DD 3.10%. "
                  "ConfigValidator path is gaussian-blind/pessimistic; its APPROVE is the "
                  "governance gate, not the headline ROI.")


def _fp(params: dict) -> str:
    return hashlib.sha256(json.dumps(params, sort_keys=True).encode("utf-8")).hexdigest()


def main() -> int:
    cfg = json.load(open(SRC_CFG, encoding="utf-8"))
    cfg["engine_runner"]["allowed_sessions_overrides"] = {"BNBUSDT": list(BNB_ALL_SESSIONS)}
    params = cfg["params"]
    fp = _fp(params)
    print(f"[1] candidate built from {SRC_CFG.name}; gaussian_impl="
          f"{cfg['engine_runner'].get('gaussian_impl')!r}; params_fingerprint={fp[:16]}…")

    # ── GOVERNED GATE: validate the changed instrument with candidate sessions ──
    csv_paths = {"BNBUSDT": str(ROOT / "data" / "BNBUSDT_M15.csv")}
    print(f"[2] validating BNBUSDT (override-aware) … this runs a backtest, ~minutes")
    report = ConfigValidator.validate(
        params=params, csv_paths=csv_paths,
        config_id=f"{NEW_VERSION}_promote", engine_runner=cfg["engine_runner"],
    )
    decision = report.get("decision")
    metrics = report.get("metrics", {})
    print(f"[2] decision={decision} final_score={metrics.get('final_score')} "
          f"trades={metrics.get('total_trades')} maxDD={metrics.get('max_drawdown_across')}")
    if decision != "APPROVE":
        print(f"ABORT — validation not APPROVE: hard_failures={report.get('hard_failures')} "
              f"warnings={report.get('warnings')}. Nothing changed.")
        return 1

    # ── MUTATE (only after APPROVE). Rollback = `git checkout` ACTIVE_VERSION +
    #    configs/promotion_log.jsonl (both git-tracked); delete the v4 file. ──
    now = datetime.now(timezone.utc).isoformat()
    vs = {
        "config_id": report.get("config_id"),
        "final_score": metrics.get("final_score", 0.0),
        "mean_score": metrics.get("mean_score", 0.0),
        "total_trades": metrics.get("total_trades", 0),
        "max_drawdown": metrics.get("max_drawdown_across", 0.0),
        "instruments": report.get("instruments_tested", []),
        "per_instrument": report.get("per_instrument", {}),
        "warnings": report.get("warnings", []),
        "params_fingerprint": fp,                 # freshness anchor (config_integrity)
        "production_path_evidence": SWEEP_EVIDENCE,
    }
    notes = ("Governed cutover: running deepdeektry (ml Gaussian + its engine sections) + "
             "BNBUSDT all-sessions override. SOLUSDT excluded (PF~1) per audit-2026-06-02. "
             "Supersedes the ungoverned 'v2_multi_2026_04 - deepdeektry'.")
    cfg.update({
        "version": NEW_VERSION, "promoted_version": NEW_VERSION,
        "config_id": f"{NEW_VERSION}_promote", "created_at": now, "promoted_at": now,
        "config_hash": fp, "validation_summary": vs, "notes": notes,
    })
    out = PROD / f"{NEW_VERSION}.json"
    json.dump(cfg, open(out, "w", encoding="utf-8"), indent=2)
    print(f"[3] wrote {out.name}")
    ACTIVE.write_text(NEW_VERSION + "\n", encoding="utf-8")
    print(f"[4] flipped ACTIVE_VERSION -> {NEW_VERSION}")
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "event": "PROMOTED", "version": NEW_VERSION, "config_id": cfg["config_id"],
            "params": params, "config_hash": fp,
            "score": metrics.get("final_score", 0.0), "score_std_dev": 0.0,
            "timestamp": now, "notes": notes,
        }) + "\n")
    print(f"[5] appended PROMOTED entry to {LOG.name}")

    # ── VERIFY ──
    loaded = PromotionManager.load_version(NEW_VERSION)          # raises on hash mismatch
    gov_ok, gov_reason = ci.active_version_is_governed(str(PROD), log_path=str(LOG))
    fresh_ok = ci.validation_summary_is_fresh(loaded)
    print(f"[6] load_version integrity OK")
    print(f"[6] active_version_is_governed = {gov_ok} ({gov_reason})")
    print(f"[6] validation_summary_is_fresh = {fresh_ok}")
    ok = gov_ok and fresh_ok
    print("DONE — GOVERNED" if ok else "DONE — but guards NOT fully green (review)")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
