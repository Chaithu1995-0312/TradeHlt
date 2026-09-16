import json
from pathlib import Path
from datetime import datetime, timezone

sidecar_alerts = json.loads(Path("results/live_alerts_sidecar_smoke_20260916/alerts_snapshot.json").read_text(encoding="utf-8"))
desk = json.loads(Path("results/live_alerts_20260916/alerts_snapshot.json").read_text(encoding="utf-8"))
meta = json.loads(Path("results/live_rail_crt_sidecar_smoke_20260916/SIDECAR_META.json").read_text(encoding="utf-8"))

combined = {
  "schema_id": "live_alert_v1",
  "generated_utc": datetime.now(timezone.utc).isoformat(),
  "rem_crt_02_orchestrator": "SIDECAR_SMOKE_PASS",
  "sidecar": {
    "report_dir": "results/live_rail_crt_sidecar_smoke_20260916",
    "meta": meta,
    "alerts": {k: sidecar_alerts[k] for k in ("n_alerts", "kinds", "n_action", "n_watch", "n_blocker")},
  },
  "desk": {
    "api_run_id": "run_20260916_225925_XAUUSD",
    "alerts": {k: desk[k] for k in ("n_alerts", "kinds", "n_action", "n_watch", "n_blocker")},
  },
  "n_alerts": sidecar_alerts["n_alerts"],
  "kinds": sidecar_alerts["kinds"],
  "n_action": sidecar_alerts["n_action"],
  "n_watch": sidecar_alerts["n_watch"],
  "n_blocker": sidecar_alerts["n_blocker"],
  "open_blockers": sidecar_alerts.get("open_blockers") or [],
  "last_action": sidecar_alerts.get("last_action") or [],
  "last_watch": sidecar_alerts.get("last_watch") or [],
  "note": "Side-car proves paper rail + CRT occupancy dual-write. Desk full-run remains A-setup count authority.",
}
Path("ui_kits/live_monitor/alerts.json").write_text(json.dumps(combined, indent=2) + "\n", encoding="utf-8")

state = json.loads(Path("ui_kits/live_monitor/state.json").read_text(encoding="utf-8"))
state["rem_crt_02"] = {
  "status": "SIDECAR_SMOKE_PASS",
  "report_dir": "results/live_rail_crt_sidecar_smoke_20260916",
  "flag": "--crt-occupancy-sidecar",
  "cli": "scripts/live/run_live_rail.py --paper ... --crt-occupancy-sidecar",
}
state["live_rail_chart_bound"] = True
state["live_rail_chart_unbound_reason"] = None
state["feeder_chart_bound"] = True
state["paper_run_dir"] = "results/live_rail_crt_sidecar_smoke_20260916"
state["alerts_n"] = combined["n_alerts"]
state["alerts_kinds"] = combined["kinds"]
state["alerts_open"] = combined["n_blocker"] + combined["n_action"]
state["ts"] = datetime.now(timezone.utc).isoformat()
Path("ui_kits/live_monitor/state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

ledger = Path("docs/research/LIVE_ALERTS_OPEN_REMEDIATIONS_2026-09-16.md")
extra = """

### REM-CRT-02 paper side-car (2026-09-16 night)

**SIDECAR SMOKE PASS:** `results/live_rail_crt_sidecar_smoke_20260916`
- Flag: `--crt-occupancy-sidecar` on paper `run_live_rail.py` only
- Rail `audit.jsonl` + `crt_occupancy/XAUUSD_events.jsonl` (82 events, chart-parseable)
- Lib: `scripts/research/crt_occupancy_lib.py`
- Alerts: `results/live_alerts_sidecar_smoke_20260916`
- Still open: larger limit / tickdb hours; REM-COST-04; REM-SOFT-01
"""
text = ledger.read_text(encoding="utf-8")
if "REM-CRT-02 paper side-car (2026-09-16 night)" not in text:
    ledger.write_text(text.rstrip() + extra, encoding="utf-8")
print("ok", "sidecar_action", sidecar_alerts["n_action"], "kinds", sidecar_alerts["kinds"])
