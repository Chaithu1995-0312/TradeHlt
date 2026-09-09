#!/usr/bin/env python3
"""Draw engine events onto a captured shot, using the chart's own coordinates.

Replaces annotate_engine_events.py / annotate_shot05.py / annotate_shot06.py,
which each hardcoded "measured candle centers on this 1920x1080 capture" plus a
hand-guessed price->pixel scale. Everything here comes from the sidecar written by
capture_tv.py, which read it out of the chart.

The rule that matters: an event that is not on the captured frame is NEVER drawn.
The old shot-04 annotator clamped with max(PLOT_LEFT + 1, x_at(utc)), so three
events that fell before the left edge were rendered as a left-edge "cluster" —
the image asserted a mapping onto candles that were not in it. Here, off-frame
events are listed under the table as absent, and --strict makes them an error.

Usage:
    python tools/tv_forensic/annotate.py --shot 04_m15_jul28_forensic
    python tools/tv_forensic/annotate.py --all
    python tools/tv_forensic/annotate.py --shot 05_m15_jul28_displacement --strict
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
SHOTS = HERE / "shots"

WHITE = (255, 255, 255, 236)
INK = (20, 20, 20)
GREY = (90, 90, 90)


def font(size: int, bold: bool = False):
    names = ["consolab.ttf", "consola.ttf"] if bold else ["consola.ttf", "arial.ttf"]
    for name in names:
        try:
            return ImageFont.truetype(f"C:/Windows/Fonts/{name}", size)
        except OSError:
            continue
    return ImageFont.load_default()


def text_w(draw: ImageDraw.ImageDraw, s: str, f) -> int:
    return int(draw.textlength(s, font=f))


def dash_h(d, x1, x2, y, fill, w=2, on=6, off=5):
    x, end = min(x1, x2), max(x1, x2)
    while x < end:
        d.line([(x, y), (min(x + on, end), y)], fill=fill, width=w)
        x += on + off


def dash_v(d, x, y1, y2, fill, w=2, on=7, off=5):
    y, end = min(y1, y2), max(y1, y2)
    while y < end:
        d.line([(x, y), (x, min(y + on, end))], fill=fill, width=w)
        y += on + off


class Frame:
    """Pixel geometry of one captured shot, straight from the sidecar."""

    def __init__(self, meta: dict) -> None:
        self.rect = meta["plot"]["rect"]
        cal = meta["plot"]["price_calibration"]
        (self.p1, self.y1), (self.p2, self.y2) = (
            (c["price"], c["y"]) for c in cal
        )
        pr = meta["plot"]["visible_price_range"]
        self.price_lo, self.price_hi = min(pr["from"], pr["to"]), max(pr["from"], pr["to"])

    @property
    def left(self) -> float:
        return self.rect["x"]

    @property
    def right(self) -> float:
        return self.rect["x"] + self.rect["w"]

    @property
    def top(self) -> float:
        return self.rect["y"]

    @property
    def bottom(self) -> float:
        return self.rect["y"] + self.rect["h"]

    def y_of(self, price: float) -> float:
        # D-13 (semantic + screenshot layer review, 2026-08-16): tv_bridge.py's
        # own Snapshot.y_of guards this identical formula with an explicit
        # ValueError; this copy did not, so a degenerate sidecar (p2 == p1)
        # raised an opaque ZeroDivisionError here instead. Matched to the same
        # guard/message for consistency.
        if self.p2 == self.p1:
            raise ValueError("degenerate price calibration")
        return self.y1 + (price - self.p1) * (self.y2 - self.y1) / (self.p2 - self.p1)

    def price_visible(self, price: float) -> bool:
        return self.price_lo <= price <= self.price_hi


def _stagger_key(ev: dict) -> tuple[str, str]:
    return (ev["event"], ev["broker"])


def stagger(
    events: list[dict], min_gap: float = 96.0, rows: int = 3,
) -> dict[tuple[str, str], int]:
    """Assign label rows so tightly-spaced marks do not overwrite each other.

    D-6 (semantic + screenshot layer review, 2026-08-16): keyed on `event` name
    alone, this silently collided whenever a shot's frame spans more than one
    episode with a repeated event name — verified live on shot 09
    (h4_jul15_20), which draws both the Jul 15 and Jul 20 episodes and has
    `RETEST` x2 / `SWEEP` x2 / `DISPLACEMENT` x2 / etc. The later event in
    iteration order silently overwrote the earlier one's row assignment,
    and where that pushed two labels onto the same (x, y) the later-drawn one
    hid the earlier — while the caption table and `_ANNOTATED.json`'s `drawn[]`
    still listed both, so the image and its own sidecar disagreed. Keying on
    `(event, broker)` makes every mark's row assignment independent of any
    same-named mark elsewhere in the frame.
    """
    assigned: dict[tuple[str, str], int] = {}
    last_x: list[float] = [-1e9] * rows
    for ev in sorted((e for e in events if e["in_frame"]), key=lambda e: e["x"]):
        key = _stagger_key(ev)
        for r in range(rows):
            if ev["x"] - last_x[r] >= min_gap:
                assigned[key] = r
                last_x[r] = ev["x"]
                break
        else:
            r = min(range(rows), key=lambda i: last_x[i])
            assigned[key] = r
            last_x[r] = ev["x"]
    return assigned


def draw_events(d, fr: Frame, events: list[dict], f_small, f_bold) -> None:
    rows = stagger(events)
    label_top = fr.top + 44

    for ev in events:
        if not ev["in_frame"]:
            continue
        x = ev["x"]
        col = tuple(ev["color"])
        row = rows.get(_stagger_key(ev), 0)
        ly = label_top + row * 24

        dash_v(d, x, ly + 20, fr.bottom - 6, col + (215,), 2)

        # High/low ticks from the engine's own bar, so the mark is checkable.
        oh = ev.get("engine_ohlc")
        if oh and fr.price_visible(oh["H"]) and fr.price_visible(oh["L"]):
            for price in (oh["H"], oh["L"]):
                y = fr.y_of(price)
                d.line([(x - 9, y), (x + 9, y)], fill=col + (240,), width=2)

        label = ev["event"]
        if ev.get("status") == "SUPERSEDED":
            label += " *"  # no longer emitted by the current engine
        tw = text_w(d, label, f_bold) + 12
        lx = min(max(x - tw / 2, fr.left + 2), fr.right - tw - 2)
        d.rectangle([(lx, ly), (lx + tw, ly + 20)], fill=WHITE, outline=col, width=2)
        d.text((lx + 6, ly + 3), label, fill=col, font=f_bold)

        level = ev.get("level")
        if level is not None and fr.price_visible(level):
            ylv = fr.y_of(level)
            dash_h(d, fr.left + 4, fr.right - 8, ylv, col + (195,), 2)
            tag = f"{ev['event']} {level:.2f}"
            tgw = text_w(d, tag, f_small) + 10
            d.rectangle(
                [(fr.left + 6, ylv - 18), (fr.left + 6 + tgw, ylv - 1)],
                fill=WHITE,
                outline=col,
            )
            d.text((fr.left + 10, ylv - 17), tag, fill=col, font=f_small)


def build_table(meta: dict, events: list[dict]) -> tuple[list[tuple[str, tuple]], str]:
    clock = meta["clock"]
    win = meta["window"]
    off = clock["offset_hours"]

    # D-7 (semantic + screenshot layer review, 2026-08-16): `[11:]` always
    # dropped the date, leaving only time-of-day. On a frame spanning more
    # than one calendar day (h4_jul27_31 spans 5 days, h4_jul15_20 spans a
    # week and contains two entirely separate episodes 5 days apart with
    # repeated event names — see the stagger() note above) two rows with the
    # same event name and the same time-of-day become indistinguishable in
    # the caption, the ONE place a reader could otherwise recover which
    # episode a mark belongs to. Print the date too whenever the frame spans
    # more than a single day.
    multi_day = win["achieved"]["start_utc"][:10] != win["achieved"]["end_utc"][:10]
    ts_w = 16 if multi_day else 6

    def _ts(s: str) -> str:
        return s if multi_day else s[11:]

    lines: list[tuple[str, tuple]] = []
    lines.append((f"{'BROKER':<{ts_w}} {'UTC':<{ts_w}} {'EVENT':<13} "
                  f"{'ENGINE O/H/L/C':<36} {'TV O/H/L/C':<36}", INK))
    inexact = False
    superseded = False
    for ev in events:
        if not ev["in_frame"]:
            continue
        e, t = ev.get("engine_ohlc"), ev.get("tv_ohlc")
        es = (f"{e['O']:.2f} {e['H']:.2f} {e['L']:.2f} {e['C']:.2f}" if e else "-")
        ts = (f"{t['O']:.2f} {t['H']:.2f} {t['L']:.2f} {t['C']:.2f}" if t else "-")
        if t and not ev.get("exact_bar", True):
            ts = "~ " + ts  # containing candle, not the same bar
            inexact = True
        name = ev["event"]
        if ev.get("status") == "SUPERSEDED":
            name += " *"
            superseded = True
        lines.append(
            (f"{_ts(ev['broker']):<{ts_w}} {_ts(ev['utc']):<{ts_w}} {name:<13} "
             f"{es:<36} {ts:<36}", tuple(ev["color"])),
        )

    absent = [e for e in events if not e["in_frame"]]
    if absent:
        lines.append(("", INK))
        for ev in absent:
            lines.append(
                (f"{_ts(ev['broker']):<{ts_w}} {_ts(ev['utc']):<{ts_w}} {ev['event']:<13} "
                 f"NOT IN FRAME - not drawn", GREY),
            )

    lines.append(("", INK))
    lines.append((f"Clock: broker = UTC{off:+d}, resolved by OHLC match "
                  f"(err {clock['match_error']}, runner-up {clock['runner_up_error']}).", GREY))
    lines.append((f"Frame: {win['achieved']['start_utc']} -> "
                  f"{win['achieved']['end_utc']} UTC.  Feed: {meta['shot']['symbol']}.", GREY))
    if inexact:
        lines.append((f"~ = engine event falls inside that {meta['shot']['interval']}m "
                      "candle rather than on its open; OHLC is the whole candle.", GREY))

    # D-1 (semantic + screenshot layer review, 2026-08-16): an absent engine_vs_tv
    # block used to omit this caption line silently, indistinguishable from a
    # deliberate layout choice. capture_tv.py now always writes a `status`
    # (OK / DIVERGENT / NOT_APPLICABLE) — the caption states the NOT_APPLICABLE
    # case explicitly instead of just going quiet.
    evt = meta.get("engine_vs_tv") or {}
    diff = evt.get("summary")
    if diff:
        divergent_flag = " [DIVERGENT]" if evt.get("status") == "DIVERGENT" else ""
        lines.append((f"Engine vs TV over {diff['compared']} bars: mean |err| "
                      f"{diff['mean_abs_error']}, max {diff['max_abs_error']}, "
                      f"divergent {diff['divergent']}.{divergent_flag}",
                      (170, 60, 0) if evt.get("status") == "DIVERGENT" else GREY))
    elif evt.get("status") == "NOT_APPLICABLE":
        lines.append((f"Engine vs TV: NOT RECONCILED ({evt.get('reason', 'no reason recorded')})",
                      (170, 60, 0)))
    prov = meta.get("engine_events_provenance") or {}
    if superseded and prov.get("status") == "SUPERSEDED":
        lines.append(("", INK))
        lines.append(("* = NO LONGER EMITTED by the current engine.", (170, 60, 0)))
        lines.append((f"  superseded by {prov.get('superseded_by', 'a later contract')}", (170, 60, 0)))
        lines.append((f"  events from {prov.get('source_run', 'an earlier run')}", (170, 60, 0)))
        if prov.get("verified_run"):
            lines.append((f"  re-verified against {prov['verified_run']}", (170, 60, 0)))

    lines.append(("Marks only. No OB / FVG / SMC / narrative. No trade inference.", GREY))

    title = f"{meta['shot']['name']}  -  engine events on {meta['shot']['interval']}m candles"
    return lines, title


def place_table(fr: Frame, events: list[dict], width: int, height: int) -> tuple[int, int]:
    """Put the table where it covers the fewest marks."""
    xs = [e["x"] for e in events if e["in_frame"]]
    candidates = [
        (fr.left + 20, fr.top + 130),
        (fr.right - width - 20, fr.top + 130),
        (fr.left + (fr.right - fr.left - width) / 2, fr.top + 130),
    ]
    best, best_cost = candidates[0], None
    for cx, cy in candidates:
        cost = sum(1 for x in xs if cx - 30 <= x <= cx + width + 30)
        if best_cost is None or cost < best_cost:
            best, best_cost = (cx, cy), cost
    return int(best[0]), int(best[1])


def annotate(shot_name: str, strict: bool = False) -> Path:
    meta_path = SHOTS / f"{shot_name}.json"
    src_path = SHOTS / f"{shot_name}.png"
    if not meta_path.exists() or not src_path.exists():
        raise SystemExit(
            f"missing {meta_path.name} / {src_path.name} — run capture_tv.py first"
        )

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if "plot" not in meta or "price_calibration" not in meta.get("plot", {}):
        raise SystemExit(
            f"{meta_path.name} predates the geometry-carrying sidecar. Re-capture it."
        )

    events = meta["engine_events"]
    absent = [e for e in events if not e["in_frame"]]
    if strict and absent:
        raise SystemExit(
            f"{shot_name}: {len(absent)} engine event(s) are outside the captured "
            f"frame ({', '.join(e['event'] for e in absent)}). "
            "Widen the shot window or drop --strict."
        )

    fr = Frame(meta)
    base = Image.open(src_path).convert("RGBA")
    ov = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    f_small, f_bold, f_title = font(13), font(14, bold=True), font(16, bold=True)

    draw_events(d, fr, events, f_small, f_bold)

    lines, title = build_table(meta, events)
    line_h = 16
    tw = max([text_w(d, s, f_small) for s, _ in lines] + [text_w(d, title, f_title)]) + 24
    th = 30 + line_h * len(lines)
    tx, ty = place_table(fr, events, tw, th)

    d.rectangle([(tx, ty), (tx + tw, ty + th)], fill=WHITE, outline=INK, width=2)
    d.text((tx + 12, ty + 6), title, fill=INK, font=f_title)
    yy = ty + 28
    for line, col in lines:
        if line:
            d.text((tx + 12, yy), line, fill=col, font=f_small)
        yy += line_h

    out_png = SHOTS / f"{shot_name}_ANNOTATED.png"
    Image.alpha_composite(base, ov).convert("RGB").save(out_png, "PNG")

    out_meta = SHOTS / f"{shot_name}_ANNOTATED.json"
    out_meta.write_text(
        json.dumps(
            {
                "source": src_path.name,
                "clock": meta["clock"],
                "window": meta["window"],
                "drawn": [
                    {k: e[k] for k in ("event", "broker", "utc", "x", "level",
                                       "engine_ohlc", "tv_ohlc")}
                    for e in events
                    if e["in_frame"]
                ],
                "not_in_frame": [
                    {k: e[k] for k in ("event", "broker", "utc")} for e in absent
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    drawn = len(events) - len(absent)
    print(f"{shot_name}: drew {drawn}/{len(events)} events -> {out_png.name}")
    for e in absent:
        print(f"    not in frame (skipped): {e['event']} broker {e['broker']}")
    return out_png


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Annotate captured TradingView shots.")
    p.add_argument("--shot", help="shot name without extension")
    p.add_argument("--all", action="store_true", help="every captured shot with a sidecar")
    p.add_argument("--strict", action="store_true",
                   help="fail if any engine event falls outside the frame")
    args = p.parse_args(argv)

    if args.all:
        # D-6/D-7 fix (2026-08-16 review) surfaced this: the old filter only
        # excluded a stem ENDING in "_ANNOTATED", which missed the *_PRE_D1 /
        # *_ANNOTATED_PRE_D6 backup files this same review started writing
        # (per CLAUDE.md 6.2 rule 4 -- preserve the pre-fix artifact rather
        # than overwrite it). --all tried to annotate a backup JSON as if it
        # were a base sidecar and failed on its different schema. Excluding
        # any "_ANNOTATED" or "_PRE_" substring, not just a suffix, is
        # correct for both today's backups and any future ones.
        names = sorted(
            j.stem for j in SHOTS.glob("*.json")
            if "_ANNOTATED" not in j.stem and "_PRE_" not in j.stem
            and (SHOTS / f"{j.stem}.png").exists()
        )
        if not names:
            raise SystemExit("no captured shots found")
    elif args.shot:
        names = [args.shot]
    else:
        raise SystemExit("pass --shot <name> or --all")

    for name in names:
        annotate(name, strict=args.strict)
    return 0


if __name__ == "__main__":
    sys.exit(main())
