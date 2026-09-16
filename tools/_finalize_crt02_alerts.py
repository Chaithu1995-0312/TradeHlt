import json
from pathlib import Path
from datetime import datetime, timezone

feeder_snap = json.loads(Path("results/live_alerts_feeder_smoke_20260916/alerts_snapshot.json").read_text(encoding="utf-8"))
desk_snap = json.loads(Path("results/live_alerts_20260916/alerts_snapshot.json").read_text(encoding="utf-8"))
verify = json.loads(Path("results/live_crt_occupancy_smoke_20260916/FEEDER_VERIFY.json").read_text(encoding="utf-8"))

combined = {
  "schema_id": "live_alert_v1",
  "generated_utc": datetime.now(timezone.utc).isoformat(),
  "sources": {
    "desk_bound_run": "results/live_alerts_20260916/alerts_snapshot.json",
    "feeder_smoke": "results/live_alerts_feeder_smoke_20260916/alerts_snapshot.json",
  },
  "feeder": {
    "dir": "results/live_crt_occupancy_smoke_20260916",
    "remediation_id": "REM-CRT-02",
    "status": "SMOKE_PASS",
    "chart_overlay_parseable": True,
    "n_events": verify["n_events_total"],
    "alerts": {k: feeder_snap[k] for k in ("n_alerts", "kinds", "n_action", "n_watch", "n_blocker")},
  },
  "desk": {
    "api_run_id": "run_20260916_225925_XAUUSD",
    "alerts": {k: desk_snap[k] for k in ("n_alerts", "kinds", "n_action", "n_watch", "n_blocker")},
  },
  "n_alerts": feeder_snap["n_alerts"],
  "kinds": feeder_snap["kinds"],
  "n_action": feeder_snap["n_action"],
  "n_watch": feeder_snap["n_watch"],
  "n_blocker": feeder_snap["n_blocker"],
  "open_blockers": feeder_snap["open_blockers"],
  "last_action": feeder_snap.get("last_action") or [],
  "last_watch": feeder_snap.get("last_watch") or [],
  "note": "Feeder smoke limit=3000 is REM-CRT-02 proof; desk full-run remains A-setup count authority.",
}
Path("ui_kits/live_monitor/alerts.json").write_text(json.dumps(combined, indent=2) + "\n", encoding="utf-8")

state = json.loads(Path("ui_kits/live_monitor/state.json").read_text(encoding="utf-8"))
state["rem_crt_02"] = {
  "status": "SMOKE_PASS",
  "out_dir": "results/live_crt_occupancy_smoke_20260916",
  "chart_overlay_parseable": True,
  "n_events": verify["n_events_total"],
  "script": "scripts/research/crt_occupancy_feeder_smoke.py",
}
state["feeder_chart_bound"] = True
state["live_rail_chart_bound"] = False
state["live_rail_chart_unbound_reason"] = "rail_skips_process_candle; feeder is side-car smoke not wired into orchestrator"
state["alerts_n"] = combined["n_alerts"]
state["alerts_kinds"] = combined["kinds"]
state["alerts_open"] = combined["n_blocker"] + combined["n_action"]
state["ts"] = datetime.now(timezone.utc).isoformat()
Path("ui_kits/live_monitor/state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

ledger = Path("docs/research/LIVE_ALERTS_OPEN_REMEDIATIONS_2026-09-16.md")
extra = "\n\n### REM-CRT-02 smoke (2026-09-16 late)\n\n**SMOKE PASS:** results/live_crt_occupancy_smoke_20260916 — 485 events, chart-parseable. Alerts: results/live_alerts_feeder_smoke_20260916. Still OPEN: wire into paper LiveRailOrchestrator.\n"
text = ledger.read_text(encoding="utf-8")
if "REM-CRT-02 smoke (2026-09-16 late)" not in text:
    ledger.write_text(text.rstrip() + extra, encoding="utf-8")
print("ok", "feeder_action", feeder_snap["n_action"], "desk_action", desk_snap["n_action"], "blockers", feeder_snap["n_blocker"])
