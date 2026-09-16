"""live_alert_resolver.py — RESEARCH-ONLY alerts on live_chart_bind_v1 / PLAYBOOK.

Reads engine events.jsonl (constructor_id=engine), emits live_alert_v1 records.
No orders, no Ultron, no economic claims.
"""
from __future__ import annotations

import argparse
import json
from collections import deque
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[2]

PLAYBOOK_EXPANSION_MIN = 8


@dataclass
class Alert:
    schema_id: str = "live_alert_v1"
    kind: str = ""
    severity: str = "info"
    instrument: str = "XAUUSD"
    constructor_id: str = "engine"
    api_run_id: str | None = None
    content_run_id: str | None = None
    bar_ts: str | None = None
    candle_index: int | None = None
    direction: str | None = None
    message: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    remediation_id: str | None = None
    ts_utc: str = ""


def _iter_events(path: Path) -> Iterator[dict]:
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def resolve_costume_alerts(
    events_path: Path,
    *,
    instrument: str,
    api_run_id: str,
    content_run_id: str | None,
    expansion_min: int = PLAYBOOK_EXPANSION_MIN,
) -> list[Alert]:
    """Walk STATE_TRANSITION stream; emit A_SETUP / orange-death / EXECUTION alerts."""
    alerts: list[Alert] = []
    # Track open costume: after SWEEP seen, then D, then E dwell, then R
    phase = "idle"  # idle|S|D|E
    exp_bars = 0
    exp_start_ts = None
    exp_start_idx = None
    last_direction = None
    sweep_ts = None

    def mint(kind: str, severity: str, ev: dict, message: str, **evidence: Any) -> Alert:
        return Alert(
            kind=kind,
            severity=severity,
            instrument=instrument,
            api_run_id=api_run_id,
            content_run_id=content_run_id or ev.get("run_id"),
            bar_ts=ev.get("timestamp"),
            candle_index=ev.get("candle_index"),
            direction=evidence.get("direction") or ev.get("direction") or last_direction,
            message=message,
            evidence=evidence,
            ts_utc=datetime.now(timezone.utc).isoformat(),
        )

    for ev in _iter_events(events_path):
        et = ev.get("event")
        if et == "SWEEP":
            phase = "S"
            sweep_ts = ev.get("timestamp")
            last_direction = ev.get("direction") or last_direction
            exp_bars = 0
            continue
        if et != "STATE_TRANSITION":
            # REM-ALERT-01: any RESET breaks the costume. During E => orange death
            # with dwell from candle_index delta (not transition count).
            if et == "RESET":
                if phase == "E":
                    if exp_start_idx is not None and ev.get("candle_index") is not None:
                        exp_bars = max(1, int(ev["candle_index"]) - int(exp_start_idx))
                    alerts.append(
                        mint(
                            "EXPANSION_ORANGE_DEATH",
                            "watch",
                            ev,
                            f"Expansion died via RESET after {exp_bars} bars (before RETEST)",
                            expansion_bars=exp_bars,
                            expansion_start=exp_start_ts,
                            reason=ev.get("reason"),
                            direction=last_direction,
                            continuous=False,
                        )
                    )
                # S/D or post-death: hard idle (HTF/session kill)
                phase = "idle"
                exp_bars = 0
                exp_start_idx = None
                exp_start_ts = None
                sweep_ts = None
            continue

        frm, to = ev.get("state_from"), ev.get("state_to")
        if to == "SWEEP" or (frm and to == "SWEEP"):
            phase = "S"
            sweep_ts = ev.get("timestamp")
            last_direction = ev.get("direction") or last_direction
            exp_bars = 0
        elif to == "DISPLACEMENT" and phase in ("S", "idle"):
            phase = "D"
            last_direction = ev.get("direction") or last_direction
        elif to == "EXPANSION" and phase in ("D", "S", "E"):
            if phase != "E":
                exp_start_ts = ev.get("timestamp")
                exp_start_idx = ev.get("candle_index")
            phase = "E"
            last_direction = ev.get("direction") or last_direction
            # dwell estimated at exit via candle_index delta (transitions != bars)
            if exp_start_idx is not None and ev.get("candle_index") is not None:
                exp_bars = max(1, int(ev["candle_index"]) - int(exp_start_idx) + 1)
        elif to == "RETEST" and phase == "E":
            if exp_start_idx is not None and ev.get("candle_index") is not None:
                exp_bars = max(1, int(ev["candle_index"]) - int(exp_start_idx))
            if exp_bars > 200:
                alerts.append(
                    mint(
                        "A_SETUP_CANDIDATE",
                        "info",
                        ev,
                        f"Retest after non-continuous expansion span ({exp_bars} bars) — discarded",
                        expansion_bars=exp_bars,
                        expansion_start=exp_start_ts,
                        direction=last_direction,
                        near_miss=True,
                        noncontinuous=True,
                    )
                )
            elif exp_bars >= expansion_min:
                alerts.append(
                    mint(
                        "A_SETUP_CANDIDATE",
                        "action",
                        ev,
                        f"PLAYBOOK costume S→D→E({exp_bars}≥{expansion_min})→R",
                        expansion_bars=exp_bars,
                        expansion_start=exp_start_ts,
                        sweep_ts=sweep_ts,
                        direction=last_direction,
                        playbook="S→D→E≥8→R",
                    )
                )
            else:
                alerts.append(
                    mint(
                        "A_SETUP_CANDIDATE",
                        "info",
                        ev,
                        f"Retest after short expansion ({exp_bars}<{expansion_min}) — near-miss",
                        expansion_bars=exp_bars,
                        expansion_start=exp_start_ts,
                        direction=last_direction,
                        near_miss=True,
                    )
                )
            phase = "idle"
            exp_bars = 0
        elif to == "EXECUTION":
            alerts.append(
                mint(
                    "EXECUTION_RARE",
                    "watch",
                    ev,
                    "EXECUTION hit — trail inside expansion; do not wait for X to manage risk",
                    direction=ev.get("direction") or last_direction,
                )
            )
        elif phase == "E" and to in ("RANGE", "SHADOW_PENDING", "EXPIRED") and frm == "EXPANSION":
            alerts.append(
                mint(
                    "EXPANSION_ORANGE_DEATH",
                    "watch",
                    ev,
                    f"Orange death {frm}→{to} after {exp_bars} bars",
                    expansion_bars=exp_bars,
                    expansion_start=exp_start_ts,
                    direction=last_direction,
                )
            )
            phase = "idle"
            exp_bars = 0

        # dwell: consecutive EXPANSION self-transitions are rare; also count by candle gaps
        # If we stay in E and see another transition from EXPANSION to EXPANSION — handled above.
        # Approximate dwell: each STATE_TRANSITION while in E from EXPANSION increments once already.

    return alerts


def systemic_alerts(
    *,
    instrument: str,
    api_run_id: str,
    content_run_id: str | None,
    chart_bound: bool,
    live_rail_bound: bool,
    stamp_trust: str | None,
    cost_model_id: str | None,
) -> list[Alert]:
    now = datetime.now(timezone.utc).isoformat()
    out: list[Alert] = []
    base = dict(
        instrument=instrument,
        api_run_id=api_run_id,
        content_run_id=content_run_id,
        ts_utc=now,
        constructor_id="engine",
    )
    if not chart_bound:
        out.append(
            Alert(
                kind="CHART_UNBOUND",
                severity="blocker",
                message="Desk chart unbound — no engine occupancy for bind",
                remediation_id="REM-CRT-01",
                **base,
            )
        )
    if not live_rail_bound:
        out.append(
            Alert(
                kind="CHART_UNBOUND",
                severity="blocker",
                message="Live rail chart unbound (rail_skips_process_candle)",
                evidence={"reason": "rail_skips_process_candle"},
                remediation_id="REM-CRT-02",
                **base,
            )
        )
    if stamp_trust == "FRESH_EMIT_VERIFIED" and cost_model_id:
        out.append(
            Alert(
                kind="STAMP_TRUST_OK",
                severity="info",
                message=f"Cost stamp trusted: {cost_model_id}",
                evidence={"stamp_trust": stamp_trust, "cost_model_id": cost_model_id},
                remediation_id="REM-COST-01",
                **base,
            )
        )
    elif not cost_model_id or cost_model_id == "UNSTAMPED":
        out.append(
            Alert(
                kind="COST_UNSTAMPED",
                severity="blocker",
                message="Cost identity unstamped on active artifact",
                remediation_id="REM-COST-01",
                **base,
            )
        )
    # Standing open remediations worth surfacing
    for rid, msg in [
        ("REM-SOFT-01", "Ultron gates gross RR; ledger nets G1+G2"),
        ("REM-CRT-02", "Paper side-car exists; streaming/orchestrator density still research-open"),
    ]:
        out.append(
            Alert(
                kind="BLOCKER_OPEN",
                severity="blocker",
                message=msg,
                remediation_id=rid,
                **base,
            )
        )
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--instrument", default="XAUUSD")
    ap.add_argument("--api-run-id", required=True)
    ap.add_argument("--content-run-id", default=None)
    ap.add_argument("--expansion-min", type=int, default=PLAYBOOK_EXPANSION_MIN)
    ap.add_argument("--chart-bound", action="store_true")
    ap.add_argument("--live-rail-bound", action="store_true")
    ap.add_argument("--stamp-trust", default=None)
    ap.add_argument("--cost-model-id", default=None)
    ap.add_argument("--monitor-alerts", type=Path, default=ROOT / "ui_kits/live_monitor/alerts.json")
    args = ap.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    costume = resolve_costume_alerts(
        args.events,
        instrument=args.instrument,
        api_run_id=args.api_run_id,
        content_run_id=args.content_run_id,
        expansion_min=args.expansion_min,
    )
    systemic = systemic_alerts(
        instrument=args.instrument,
        api_run_id=args.api_run_id,
        content_run_id=args.content_run_id,
        chart_bound=args.chart_bound,
        live_rail_bound=args.live_rail_bound,
        stamp_trust=args.stamp_trust,
        cost_model_id=args.cost_model_id,
    )
    all_alerts = systemic + costume

    jsonl = args.out_dir / "alerts.jsonl"
    with jsonl.open("w", encoding="utf-8") as f:
        for a in all_alerts:
            f.write(json.dumps(asdict(a), default=str) + "\n")

    # Summarize
    from collections import Counter

    kinds = Counter(a.kind for a in all_alerts)
    action = [a for a in all_alerts if a.severity == "action"]
    watch = [a for a in all_alerts if a.severity == "watch"]
    blockers = [a for a in all_alerts if a.severity == "blocker"]

    snapshot = {
        "schema_id": "live_alert_v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "api_run_id": args.api_run_id,
        "content_run_id": args.content_run_id,
        "instrument": args.instrument,
        "n_alerts": len(all_alerts),
        "kinds": dict(kinds),
        "n_action": len(action),
        "n_watch": len(watch),
        "n_blocker": len(blockers),
        "open_blockers": [asdict(a) for a in blockers],
        "last_action": [asdict(a) for a in action[-10:]],
        "last_watch": [asdict(a) for a in watch[-10:]],
        "alerts_path": str(jsonl),
    }
    (args.out_dir / "alerts_snapshot.json").write_text(
        json.dumps(snapshot, indent=2) + "\n", encoding="utf-8"
    )
    args.monitor_alerts.parent.mkdir(parents=True, exist_ok=True)
    args.monitor_alerts.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")

    # Patch live_monitor state.json
    state_path = ROOT / "ui_kits/live_monitor/state.json"
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["alert_schema_id"] = "live_alert_v1"
        state["alerts_open"] = len(blockers) + len(action)
        state["alerts_n"] = len(all_alerts)
        state["alerts_kinds"] = dict(kinds)
        state["alerts_last"] = [asdict(a) for a in (action[-3:] + watch[-2:] + blockers[:3])]
        state["alerts_snapshot_path"] = "ui_kits/live_monitor/alerts.json"
        state["ts"] = datetime.now(timezone.utc).isoformat()
        state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"n": len(all_alerts), "kinds": dict(kinds), "out": str(jsonl)}, indent=2))


if __name__ == "__main__":
    main()
