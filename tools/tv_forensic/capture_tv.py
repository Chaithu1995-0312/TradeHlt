#!/usr/bin/env python3
"""Capture TradingView screenshots for engine-trace comparison.

Standalone Playwright tool. Does not touch the trading engine.

What this produces per shot is not just a PNG. The sidecar JSON carries the
resolved clock (with its evidence), the achieved visible range, every bar on
screen with its page-pixel x, a price->y calibration, and an engine-vs-TradingView
per-bar diff. That turns the comparison from "look at two pictures" into "read one
table", and it gives annotate.py real coordinates instead of hand-measured ones.

The shared layout https://in.tradingview.com/chart/Io3C5clp/ needs its owner's
login. The public Superchart does not, and exposes the same widget API:

    https://www.tradingview.com/chart/?symbol=OANDA:XAUUSD&interval=15

Usage:
    python tools/tv_forensic/capture_tv.py --preset jul28-long
    python tools/tv_forensic/capture_tv.py --preset jul28-m15 --headed
    python tools/tv_forensic/capture_tv.py \
        --symbol OANDA:XAUUSD --interval 15 \
        --from "2026-07-28 03:45" --to "2026-07-30 08:00" --name my_shot
    python tools/tv_forensic/capture_tv.py --dump-engine-bars "2026-07-30 06:00" "2026-07-30 09:00"

Times are BROKER (engine) timestamps unless the shot sets "clock": "utc".
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

import engine_data as ed
import htf_bars as hb
import ui_fallback as ui
from tv_bridge import TVBridge

HERE = Path(__file__).resolve().parent
PLAN_PATH = HERE / "shot_plan.json"
DEFAULT_OUT = HERE / "shots"
DEFAULT_CHART = "https://www.tradingview.com/chart/?symbol={symbol}&interval={interval}"

# Provisional framing pad. The true broker->UTC offset is unknown until we have
# bars to measure against, so the first pass frames wide enough that the real
# window is inside it for any offset in +/-12h.
CLOCK_PAD = timedelta(hours=14)
BAR_SECONDS = {"1": 60, "5": 300, "15": 900, "30": 1800, "60": 3600,
               "120": 7200, "180": 10800, "240": 14400, "D": 86400}


@dataclass
class Shot:
    name: str
    symbol: str
    interval: str
    start: str
    end: str
    clock: str = "broker"
    note: str = ""

    def parsed(self, which: str) -> datetime:
        return datetime.strptime(getattr(self, which), "%Y-%m-%d %H:%M")


@dataclass
class RunClock:
    """Broker->UTC offset for this run, resolved by measurement."""

    offset_hours: int
    evidence: dict = field(default_factory=dict)

    def to_utc(self, broker: datetime) -> datetime:
        return broker - timedelta(hours=self.offset_hours)

    def epoch(self, broker: datetime) -> int:
        return ed.to_utc_epoch(broker, self.offset_hours)


def load_plan() -> dict:
    return json.loads(PLAN_PATH.read_text(encoding="utf-8"))


def shots_from_preset(preset: str, plan: dict) -> list[Shot]:
    if preset not in plan["presets"]:
        raise SystemExit(
            f"Unknown preset {preset!r}. Known: {', '.join(plan['presets'])}"
        )
    return [Shot(**plan["shots"][n]) for n in plan["presets"][preset]["shots"]]


# --------------------------------------------------------------------------- clock


def calibrate_clock(
    bridge: TVBridge, plan: dict, engine_bars: dict, symbol: str
) -> RunClock:
    """Resolve broker->UTC once per run, on M15, against known engine bars.

    Offset resolution needs M15 TradingView bars to compare with M15 engine bars,
    so it always runs at 15m even when the shots are 4H. All shots in a pack sit
    within days of each other, so one resolution covers them.
    """
    # D-4 (semantic + screenshot layer review, 2026-08-16): this used to build the
    # candidate anchor list, silently filter to those present in engine_bars, and
    # move on -- one surviving anchor out of nineteen was enough to pass, with
    # zero record of which anchors were dropped or why. Validate every declared
    # event first (time AND level, where checkable) and report drops explicitly.
    problems = ed.validate_engine_events(plan["engine_events"], engine_bars)
    if problems:
        print(f"  engine_events validation: {len(problems)} problem(s) found:")
        for p in problems:
            print(f"    [{p['problem']}] {p['event']} @ {p['time']}: {p['detail']}")

    all_times = [e["time"] for e in plan["engine_events"]]
    anchors_all = [
        datetime.strptime(e["time"], "%Y-%m-%d %H:%M") for e in plan["engine_events"]
    ]
    dropped = [(t, a) for t, a in zip(all_times, anchors_all) if a not in engine_bars]
    if dropped:
        print(f"  {len(dropped)}/{len(anchors_all)} engine_events anchor(s) not "
              f"found in the engine CSV, dropped from clock calibration:")
        for t, _ in dropped:
            print(f"    {t}")
    anchors = [a for a in anchors_all if a in engine_bars]
    if not anchors:
        raise SystemExit(
            "None of the engine_events timestamps exist in the engine CSV; "
            "cannot calibrate the clock."
        )

    lo, hi = min(anchors) - CLOCK_PAD, max(anchors) + CLOCK_PAD
    print(f"  calibrating clock on {len(anchors)} anchors "
          f"({lo:%Y-%m-%d %H:%M} .. {hi:%Y-%m-%d %H:%M} broker, padded)")

    bridge.setup(symbol, "15")
    lo_epoch = int(lo.replace(tzinfo=timezone.utc).timestamp())
    hi_epoch = int(hi.replace(tzinfo=timezone.utc).timestamp())
    bridge.load_history(lo_epoch)
    bridge.frame(lo_epoch, hi_epoch)

    snap = bridge.snapshot()
    result = ed.resolve_offset(engine_bars, snap.bars_by_epoch, anchors)

    # D-2 (semantic + screenshot layer review, 2026-08-16): `runner_up_hours`/
    # `runner_up_error` are None when only one candidate offset scored at all —
    # `:+d`/`:.3f` on None raised an obscure TypeError here instead of the clear
    # refusal message the code intends. Format defensively either way.
    runner_up_str = (
        f"{result.runner_up_hours:+d} @ {result.runner_up_error:.3f}"
        if result.runner_up_hours is not None
        else "none (only one candidate offset produced any TradingView match)"
    )
    print(f"  offset = UTC{result.hours:+d}  "
          f"mean|err| {result.error:.3f}  "
          f"runner-up {runner_up_str}")

    if not result.decisive:
        raise SystemExit(
            f"Clock resolution is not decisive (best {result.error:.3f} at "
            f"{result.hours:+d}h, runner-up {runner_up_str}). Refusing to guess — "
            "a wrong offset is exactly how shot 04 came to mark candles that "
            "were not in frame."
        )
    return RunClock(result.hours, result.as_dict())


# ---------------------------------------------------------------------- capture


def frame_shot(bridge: TVBridge, shot: Shot, clock: RunClock, via_ui: bool) -> dict:
    """Put the requested window on screen and prove the chart honoured it."""
    start_b, end_b = shot.parsed("start"), shot.parsed("end")
    if shot.clock == "broker":
        start_u, end_u = clock.to_utc(start_b), clock.to_utc(end_b)
    elif shot.clock == "utc":
        start_u, end_u = start_b, end_b
    else:
        raise SystemExit(f"{shot.name}: unknown clock {shot.clock!r} (use broker|utc)")

    from_epoch = int(start_u.replace(tzinfo=timezone.utc).timestamp())
    to_epoch = int(end_u.replace(tzinfo=timezone.utc).timestamp())

    bridge.setup(shot.symbol, shot.interval)
    bridge.load_history(from_epoch)

    if via_ui:
        ui.set_custom_range(
            bridge.page, start_u.strftime("%Y-%m-%d %H:%M"), end_u.strftime("%Y-%m-%d %H:%M")
        )
        framed = {"method": "ui"}
    else:
        framed = bridge.frame(from_epoch, to_epoch)
        framed["method"] = "api"

    snap = bridge.snapshot()
    achieved_from = snap.visible_range["from"]
    achieved_to = snap.visible_range["to"]

    # One bar of slack: zoomToBarsRange snaps to bar boundaries.
    #
    # D-9 (semantic + screenshot layer review, 2026-08-16): this used to only
    # check the NARROW-frame direction (achieved window smaller than requested).
    # tv_bridge.py's own docstring documents that the object-form
    # `zoomToBarsRange({from, to})` call can silently no-op, leaving the chart
    # showing whatever it already had — which can be a month or more WIDER than
    # requested on either side. A too-narrow frame was caught; a too-wide one
    # (the no-op signature) passed silently. The assertion is now two-sided.
    slack = BAR_SECONDS.get(str(shot.interval), 900)
    too_narrow = achieved_from > from_epoch + slack or achieved_to < to_epoch - slack
    too_wide = achieved_from < from_epoch - slack or achieved_to > to_epoch + slack
    if too_narrow or too_wide:
        kind = "NARROWER" if too_narrow else "WIDER"
        raise RuntimeError(
            f"{shot.name}: chart framed "
            f"{_iso(achieved_from)}..{_iso(achieved_to)} but "
            f"{_iso(from_epoch)}..{_iso(to_epoch)} was requested "
            f"(achieved window is {kind} than requested beyond the {slack}s slack"
            + (" — possible zoomToBarsRange no-op, see tv_bridge.py's docstring)"
               if too_wide else ")")
        )

    return {
        "requested": {
            "clock": shot.clock,
            "start": shot.start,
            "end": shot.end,
            "start_utc": start_u.strftime("%Y-%m-%d %H:%M"),
            "end_utc": end_u.strftime("%Y-%m-%d %H:%M"),
            "start_epoch": from_epoch,
            "end_epoch": to_epoch,
        },
        "achieved": {
            "start_utc": _iso(achieved_from),
            "end_utc": _iso(achieved_to),
            "start_epoch": achieved_from,
            "end_epoch": achieved_to,
        },
        "framing": framed,
        "_snapshot": snap,
    }


def _iso(epoch: int) -> str:
    return datetime.fromtimestamp(int(epoch), tz=timezone.utc).strftime("%Y-%m-%d %H:%M")


def _event_belongs_to_shot(ev: dict, shot: Shot, plan: dict) -> bool:
    """Optional per-event 'shots' list keeps a pack from drawing every episode
    on every frame. Untagged events stay on every shot (backward compatible)."""
    allowed = ev.get("shots")
    if not allowed:
        return True
    keys = {shot.name}
    for k, spec in plan.get("shots", {}).items():
        if spec.get("name") == shot.name:
            keys.add(k)
            break
    return bool(keys & set(allowed))


def build_events(
    plan: dict, snap, clock: RunClock, engine_bars: dict, interval: str,
    shot: Shot | None = None,
) -> list[dict]:
    """Locate each engine event on the captured frame — or mark it absent.

    Events carry M15 timestamps, so on a coarser chart an event lands *inside* a
    candle rather than on its open. Match the containing bar: on M15 that is the
    exact bar, on 4H it is the candle the event happened within.

    An event with no containing bar on screen gets x=None and in_frame=False, and
    annotate.py refuses to draw it. The old annotator clamped such events to the
    left edge with max(PLOT_LEFT + 1, ...), which is how an off-window event came
    to look like an on-window one.
    """
    span = BAR_SECONDS.get(str(interval), 900)
    ordered = sorted(snap.bars, key=lambda b: b["t"])

    def containing(epoch: int) -> dict | None:
        lo, hi = 0, len(ordered) - 1
        found = None
        while lo <= hi:  # rightmost bar whose open <= epoch
            mid = (lo + hi) // 2
            if ordered[mid]["t"] <= epoch:
                found = ordered[mid]
                lo = mid + 1
            else:
                hi = mid - 1
        if found is None or epoch >= found["t"] + span:
            return None
        return found

    out = []
    for ev in plan["engine_events"]:
        if shot is not None and not _event_belongs_to_shot(ev, shot, plan):
            continue
        broker = datetime.strptime(ev["time"], "%Y-%m-%d %H:%M")
        epoch = clock.epoch(broker)
        bar = containing(epoch)
        eng = engine_bars.get(broker)
        rec = {
            "event": ev["event"],
            "broker": ev["time"],
            "utc": _iso(epoch),
            "epoch": epoch,
            "detail": ev.get("detail", ""),
            "color": ev.get("color", [30, 30, 30]),
            "level": ev.get("level"),
            # CURRENT = the live engine still emits this; SUPERSEDED = it was in the
            # source run but a later contract (e.g. F-074) removed it.
            "status": ev.get("status", "CURRENT"),
            "in_frame": bar is not None,
            "x": round(bar["x"], 2) if bar else None,
            "engine_ohlc": (
                {"O": eng.o, "H": eng.h, "L": eng.l, "C": eng.c} if eng else None
            ),
            "tv_ohlc": (
                {"O": bar["o"], "H": bar["h"], "L": bar["l"], "C": bar["c"]}
                if bar
                else None
            ),
            # On a coarser chart the mapped candle opens before the event.
            "tv_bar_open_utc": _iso(bar["t"]) if bar else None,
            "exact_bar": bool(bar and int(bar["t"]) == epoch),
        }
        out.append(rec)
    return out


def build_engine_vs_tv(
    shot: Shot,
    engine_bars: dict,
    tv_by_epoch: dict,
    offset_hours: int,
) -> dict:
    """The engine-vs-TradingView reconciliation block for one shot's sidecar.

    Three outcomes, all of them RECORDED — never an absent key.

    D-1 (semantic + screenshot layer review, 2026-08-16): this used to omit
    `engine_vs_tv` entirely on a non-M15 shot, which made a SKIPPED
    reconciliation indistinguishable from one that was never examined. Three
    downstream consumers each had to guess what the missing key meant, and one
    guessed wrong and wrote a false "already used the correct per-shot interval"
    claim into a generated report. An explicit status makes that guess
    unnecessary.

    That fix recorded the absence honestly but left it PERMANENT: every H4 shot
    was unreconcilable by construction. `htf_bars` now supplies canonically
    aggregated parents and a MEASURED grid phase, so a supported HTF interval
    gets a real verdict. NOT_APPLICABLE survives for the cases that genuinely
    cannot be computed, each with its own distinguishable reason.

    Factored out of `run_shot` so the backfill path computes the identical block
    from a sidecar's own stored bars — one implementation, not two.
    """
    start = shot.parsed("start")
    end = shot.parsed("end")
    if shot.clock != "broker":
        start += timedelta(hours=offset_hours)
        end += timedelta(hours=offset_hours)

    interval = str(shot.interval)

    if interval == "15":
        rows = ed.diff_table(engine_bars, tv_by_epoch, offset_hours, start, end)
        summary = ed.summarize_diff(rows)
        # D-8: a divergent bar used to only get printed, never marked in the
        # payload itself — a sidecar with every bar DIVERGENT was structurally
        # identical to a clean one. `status` now carries that fact for any
        # consumer that reads the payload without re-deriving it from `rows`.
        return {
            "status": "DIVERGENT" if summary["divergent"] > 0 else "OK",
            "summary": summary,
            "rows": rows,
        }

    if interval not in hb.SUPPORTED_INTERVALS:
        return {
            "status": "NOT_APPLICABLE",
            "reason": (
                f"shot interval {interval} has no ParentCandleBuilder rule "
                f"(supported: {sorted(hb.SUPPORTED_INTERVALS)}). No OHLC/clock "
                f"reconciliation was computed — a recorded absence, not an omission."
            ),
        }

    rule, step_minutes = hb.SUPPORTED_INTERVALS[interval]
    try:
        anchor, parents = hb.resolve_htf_anchor(
            engine_bars, tv_by_epoch, rule, step_minutes, offset_hours
        )
    except hb.SrcUnavailable as exc:
        return {
            "status": "NOT_APPLICABLE",
            "reason": (
                f"SRC_UNAVAILABLE: canonical {rule} aggregation needs "
                f"features.parent_candle, which could not be imported ({exc}). "
                f"This tool never re-implements HTF aggregation locally."
            ),
        }

    if not anchor.decisive:
        return {
            "status": "NOT_APPLICABLE",
            "reason": (
                f"H4_GRID_UNRESOLVED: no {rule} grid phase matched TradingView's "
                f"bars decisively (best phase {anchor.phase_hours}, mean |err| "
                f"{anchor.error:.4f}). Fails closed — an unresolved grid is a "
                f"recorded absence, never a silent pass."
            ),
            "htf_anchor": anchor.as_dict(),
        }

    rows = ed.diff_table(
        parents, tv_by_epoch, offset_hours, start, end,
        step_minutes=step_minutes,
        # An HTF window can legitimately start before the corpus does
        # (01_h4_july_macro asks for Jul 1; data/XAUUSD_M15.csv starts Jul 7),
        # so uncovered slots are counted, not quietly dropped.
        record_missing_engine=True,
    )
    summary = ed.summarize_diff(rows)
    return {
        "status": "DIVERGENT" if summary["divergent"] > 0 else "OK",
        "timeframe": {"rule": rule, "step_minutes": step_minutes},
        "htf_anchor": anchor.as_dict(),
        "summary": summary,
        "rows": rows,
    }


def run_shot(
    bridge: TVBridge,
    shot: Shot,
    clock: RunClock,
    plan: dict,
    engine_bars: dict,
    out_dir: Path,
    via_ui: bool,
) -> Path:
    print(f"\n--- {shot.name} ---")
    print(f"    {shot.symbol}  {shot.interval}  "
          f"{shot.start} -> {shot.end}  ({shot.clock} clock)")
    if shot.note:
        print(f"    {shot.note}")

    framed = frame_shot(bridge, shot, clock, via_ui)
    snap = framed.pop("_snapshot")

    ui.dismiss_overlays(bridge.page)
    bridge.page.wait_for_timeout(900)

    dest = out_dir / f"{shot.name}.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    bridge.page.screenshot(path=str(dest), full_page=False)

    events = build_events(plan, snap, clock, engine_bars, shot.interval, shot=shot)
    in_frame = sum(1 for e in events if e["in_frame"])

    payload = {
        "shot": asdict(shot),
        "saved": dest.name,
        "captured_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "page_url": bridge.page.url,
        "clock": {"basis": "broker->utc", "offset_hours": clock.offset_hours,
                  **clock.evidence},
        "window": {k: framed[k] for k in ("requested", "achieved", "framing")},
        "plot": {
            "rect": snap.rect,
            "bar_spacing": snap.bar_spacing,
            "visible_price_range": snap.visible_price_range,
            "price_calibration": snap.price_calibration,
        },
        "bars": snap.bars,
        "engine_events": events,
        "engine_events_provenance": plan.get("engine_events_provenance"),
    }

    payload["engine_vs_tv"] = build_engine_vs_tv(
        shot, engine_bars, snap.bars_by_epoch, clock.offset_hours
    )
    ev = payload["engine_vs_tv"]
    if ev["status"] in ("OK", "DIVERGENT"):
        s = ev["summary"]
        print(f"    bars {len(snap.bars)}  events in frame {in_frame}/{len(events)}  "
              f"diff mean|err| {s['mean_abs_error']} max {s['max_abs_error']} "
              f"divergent {s['divergent']}"
              + (f"  [DIVERGENT: {s['divergent']}/{s['compared']}]"
                 if s["divergent"] > 0 else ""))
    else:
        print(f"    bars {len(snap.bars)}  events in frame {in_frame}/{len(events)} "
              f"(engine_vs_tv.status={ev['status']}: {ev.get('reason', '')[:80]})")

    dest.with_suffix(".json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    print(f"    saved {dest}")
    return dest


def open_chart(page, url: str, symbol: str, interval: str) -> None:
    target = url.format(symbol=symbol, interval=interval)
    print(f"Opening {target}")
    page.goto(target, wait_until="domcontentloaded", timeout=90000)
    page.wait_for_timeout(3500)
    ui.dismiss_overlays(page)
    ui.wait_for_chart(page, timeout_ms=60000)
    ui.dismiss_overlays(page)
    ui.hide_watchlist(page)
    ui.wait_for_chart(page)


# ------------------------------------------------------------------------- cli


def dump_engine_bars(start: str, end: str, csv_path: str) -> int:
    """Replaces the throwaway _dump_jul28_bars.py / _dump_jul30_bars.py."""
    bars = ed.load_engine_bars(csv_path)
    lo = datetime.strptime(start, "%Y-%m-%d %H:%M")
    hi = datetime.strptime(end, "%Y-%m-%d %H:%M")
    cursor = lo
    print(f"{'broker':<17} {'O':>9} {'H':>9} {'L':>9} {'C':>9}")
    while cursor <= hi:
        b = bars.get(cursor)
        if b:
            print(f"{cursor:%Y-%m-%d %H:%M} {b.o:9.2f} {b.h:9.2f} {b.l:9.2f} {b.c:9.2f}")
        cursor += timedelta(minutes=15)
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Capture TradingView screenshots against the engine trace."
    )
    p.add_argument(
        "--plan",
        type=Path,
        default=None,
        help="Shot-plan JSON (defaults to tools/tv_forensic/shot_plan.json).",
    )
    p.add_argument("--preset", default=None, help="Preset name in the loaded plan.")
    p.add_argument(
        "--continue-on-frame-error",
        action="store_true",
        help=(
            "Record a frame_shot refusal and continue the pack. "
            "Does not loosen the two-sided assertion; the refused window "
            "is coverage, not a captured shot."
        ),
    )
    p.add_argument("--symbol", default="OANDA:XAUUSD")
    p.add_argument("--interval", default="15", help="15, 240 (4H), 60, D, ...")
    p.add_argument("--from", dest="start", help='e.g. "2026-07-28 03:45" (broker clock)')
    p.add_argument("--to", dest="end", help='e.g. "2026-07-30 08:00" (broker clock)')
    p.add_argument("--clock", choices=["broker", "utc"], default="broker")
    p.add_argument("--name", default="custom_shot")
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--url", default=DEFAULT_CHART)
    p.add_argument("--engine-csv", default=None, help="defaults to shot_plan engine_csv")
    p.add_argument("--headed", action="store_true")
    p.add_argument("--slowmo", type=int, default=0)
    p.add_argument(
        "--via-ui",
        action="store_true",
        help="Frame with the Go-to-date dialog instead of the widget API (fallback)",
    )
    p.add_argument(
        "--dump-engine-bars",
        nargs=2,
        metavar=("START", "END"),
        help="Print engine CSV bars for a broker-time range and exit",
    )
    p.add_argument(
        "--validate-events",
        action="store_true",
        help=(
            "D-4: cross-check every shot_plan.json engine_events entry's "
            "time/level against the engine CSV and exit. No Playwright, no "
            "network, no browser -- CSV+JSON only."
        ),
    )
    p.add_argument(
        "--backfill-reconciliation",
        action="store_true",
        help=(
            "Recompute engine_vs_tv for every already-captured sidecar from its "
            "OWN stored bars and exit. No Playwright, no network, no re-capture. "
            "Used to give the H4 shots the reconciliation they never could have "
            "had; prior payloads are preserved as *_PRE_H4RECON.json."
        ),
    )
    return p.parse_args(argv)


def backfill_reconciliation(out_dir: Path, engine_bars: dict) -> int:
    """Recompute `engine_vs_tv` on captured sidecars from their own stored bars.

    Deterministic and offline: every input (the shot definition, the TradingView
    bars, the resolved clock) is already inside each sidecar. Same precedent as
    the D-1 backfill — a sidecar's recorded reconciliation should reflect what
    the tool can compute today, without spending a fresh capture to find out.
    """
    base = sorted(
        p for p in out_dir.glob("*.json")
        if not p.stem.endswith(("_ANNOTATED", "_PRE_D1", "_PRE_H4RECON"))
        and not p.stem.endswith("_ANNOTATED_PRE_D6")
    )
    if not base:
        print(f"no captured sidecars under {out_dir}")
        return 1

    changed = 0
    for path in base:
        payload = json.loads(path.read_text(encoding="utf-8"))
        shot = Shot(**payload["shot"])
        tv_by_epoch = {int(b["t"]): b for b in payload.get("bars", [])}
        offset = int(payload["clock"]["offset_hours"])

        before = payload.get("engine_vs_tv")
        after = build_engine_vs_tv(shot, engine_bars, tv_by_epoch, offset)
        if before == after:
            print(f"  {path.stem}: unchanged ({after['status']})")
            continue

        # Preserve the prior payload rather than overwrite it (CLAUDE.md 6.2
        # rule 4 — history is kept for replay; truth evolves on top of it).
        backup = path.with_name(f"{path.stem}_PRE_H4RECON.json")
        if not backup.exists():
            backup.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        payload["engine_vs_tv"] = after
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        changed += 1

        was = (before or {}).get("status", "ABSENT")
        if after["status"] in ("OK", "DIVERGENT"):
            s = after["summary"]
            print(f"  {path.stem}: {was} -> {after['status']} "
                  f"(compared {s['compared']}, divergent {s['divergent']}, "
                  f"mean |err| {s['mean_abs_error']}, max {s['max_abs_error']})")
        else:
            print(f"  {path.stem}: {was} -> {after['status']} "
                  f"({after.get('reason', '')[:90]})")

    print(f"\n{changed}/{len(base)} sidecar(s) updated.")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    plan_path = args.plan if args.plan else PLAN_PATH
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    csv_path = args.engine_csv or plan.get("engine_csv", str(ed.DEFAULT_CSV))

    if args.dump_engine_bars:
        return dump_engine_bars(*args.dump_engine_bars, csv_path)

    if args.validate_events:
        engine_bars = ed.load_engine_bars(csv_path)
        problems = ed.validate_engine_events(plan["engine_events"], engine_bars)
        n = len(plan["engine_events"])
        if not problems:
            print(f"OK: all {n} engine_events entries validated "
                  f"(time exists as a bar; level, where checkable, is inside "
                  f"that bar's O/H/L/C envelope).")
            return 0
        print(f"{len(problems)}/{n} engine_events problem(s):")
        for p in problems:
            print(f"  [{p['problem']}] {p['event']} @ {p['time']}: {p['detail']}")
        return 1

    if args.backfill_reconciliation:
        engine_bars = ed.load_engine_bars(csv_path)
        print(f"engine bars: {len(engine_bars)} from {csv_path}")
        print(f"backfilling engine_vs_tv under {args.out}")
        return backfill_reconciliation(args.out, engine_bars)

    if args.preset:
        shots = shots_from_preset(args.preset, plan)
    elif args.start and args.end:
        shots = [
            Shot(
                name=args.name,
                symbol=args.symbol,
                interval=str(args.interval),
                start=args.start,
                end=args.end,
                clock=args.clock,
                note="one-off capture",
            )
        ]
    else:
        shots = shots_from_preset("jul28-m15", plan)

    engine_bars = ed.load_engine_bars(csv_path)
    print(f"engine bars: {len(engine_bars)} from {csv_path}")

    args.out.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not args.headed, slow_mo=args.slowmo)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            timezone_id="UTC",
            device_scale_factor=1,  # page pixels == PNG pixels; annotate.py relies on this
        )
        page = context.new_page()
        page.set_default_timeout(30000)
        open_chart(page, args.url, shots[0].symbol, shots[0].interval)

        bridge = TVBridge(page)
        if not bridge.available():
            raise SystemExit(
                "window.TradingViewApi is not exposed on this page. "
                "Re-run with --via-ui to use the Go-to-date dialog instead."
            )

        clock = calibrate_clock(bridge, plan, engine_bars, shots[0].symbol)

        refusals: list[dict] = []
        for shot in shots:
            try:
                saved.append(
                    str(run_shot(bridge, shot, clock, plan, engine_bars, args.out, args.via_ui))
                )
            except RuntimeError as exc:
                msg = str(exc)
                if "chart framed" not in msg and "framed" not in msg:
                    raise
                if not args.continue_on_frame_error:
                    raise
                print(f"    REFUSED (coverage): {msg}")
                refusals.append({"shot": shot.name, "error": msg})
        if refusals:
            ref_path = args.out / "frame_refusals.jsonl"
            with ref_path.open("a", encoding="utf-8") as fh:
                for row in refusals:
                    fh.write(json.dumps(row) + "\n")
            print(f"\n{len(refusals)} window(s) refused; recorded {ref_path}")
        browser.close()

    print("\nDone.")
    for path in saved:
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
