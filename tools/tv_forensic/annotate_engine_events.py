"""Forensic overlay on the existing M15 full-window shot.

Does not recapture TradingView. Draws only the four engine events after
the measured UTC+3 -> UTC shift. No SMC / 4H / trade drawings.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
SRC = HERE / "shots" / "04_m15_jul28_forensic.png"
OUT = HERE / "shots" / "04_m15_jul28_forensic_ANNOTATED.png"
META = HERE / "shots" / "04_m15_jul28_forensic_ANNOTATED.json"

# 1920x1080 viewport shot. Time axis: 01:00 28 Jul → 09:00 30 Jul UTC.
PLOT_LEFT = 56
PLOT_RIGHT = 1766
CANDLE_TOP = 78
CANDLE_BOTTOM = 868
PRICE_TOP = 4130.0
PRICE_BOTTOM = 4010.0

VISIBLE_START = datetime(2026, 7, 28, 1, 0)
VISIBLE_END = datetime(2026, 7, 30, 9, 0)
BROKER_OFFSET = timedelta(hours=3)

EVENTS = [
    {
        "broker": datetime(2026, 7, 28, 3, 45),
        "label": "RANGE",
        "color": (25, 90, 185),
        "ohlc": {"O": 4065.51, "H": 4065.56, "L": 4057.75, "C": 4058.07},
        "level": None,
        "level_tag": None,
    },
    {
        "broker": datetime(2026, 7, 28, 4, 0),
        "label": "SWEEP",
        "color": (190, 30, 30),
        "ohlc": {"O": 4058.07, "H": 4060.32, "L": 4053.91, "C": 4058.08},
        "level": 4053.91,
        "level_tag": "4053.91",
    },
    {
        "broker": datetime(2026, 7, 28, 4, 15),
        "label": "DISPLACEMENT",
        "color": (170, 90, 0),
        "ohlc": {"O": 4058.08, "H": 4059.19, "L": 4046.38, "C": 4047.41},
        "level": 4046.38,
        "level_tag": "4046.38",
    },
    {
        "broker": datetime(2026, 7, 28, 6, 45),
        "label": "EXPANSION",
        "color": (10, 125, 65),
        "ohlc": {"O": 4048.41, "H": 4050.85, "L": 4048.12, "C": 4049.48},
        "level": None,
        "level_tag": None,
    },
]


def load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    names = (
        ["consolab.ttf", "consola.ttf"] if bold else ["consola.ttf", "arial.ttf"]
    )
    for name in names:
        try:
            return ImageFont.truetype(f"C:/Windows/Fonts/{name}", size)
        except OSError:
            continue
    return ImageFont.load_default()


def x_at(utc: datetime) -> float:
    span = (VISIBLE_END - VISIBLE_START).total_seconds()
    t = (utc - VISIBLE_START).total_seconds()
    return PLOT_LEFT + (t / span) * (PLOT_RIGHT - PLOT_LEFT)


def y_at(price: float) -> float:
    return CANDLE_TOP + (PRICE_TOP - price) / (PRICE_TOP - PRICE_BOTTOM) * (
        CANDLE_BOTTOM - CANDLE_TOP
    )


def dashed_h(draw, x1, x2, y, fill, width=1):
    x = min(x1, x2)
    end = max(x1, x2)
    while x < end:
        draw.line([(x, y), (min(x + 6, end), y)], fill=fill, width=width)
        x += 11


def dashed_v(draw, x, y1, y2, fill, width=2):
    y = min(y1, y2)
    end = max(y1, y2)
    while y < end:
        draw.line([(x, y), (x, min(y + 7, end))], fill=fill, width=width)
        y += 12


def main() -> None:
    base = Image.open(SRC).convert("RGBA")
    ov = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    f11 = load_font(13)
    f12b = load_font(14, bold=True)
    f15b = load_font(16, bold=True)

    records = []
    for ev in EVENTS:
        utc = ev["broker"] - BROKER_OFFSET
        x = max(PLOT_LEFT + 1, x_at(utc))
        color = ev["color"]
        dashed_v(d, x, CANDLE_TOP + 4, CANDLE_BOTTOM - 2, color + (220,), 2)
        records.append(
            {
                "label": ev["label"],
                "broker_time": ev["broker"].strftime("%Y-%m-%d %H:%M"),
                "utc_time": utc.strftime("%Y-%m-%d %H:%M"),
                "x_px": round(x, 1),
                "in_visible_window": VISIBLE_START <= utc <= VISIBLE_END,
                "ohlc_engine": ev["ohlc"],
                "level": ev["level"],
            }
        )
        if ev["level"] is not None:
            y = y_at(ev["level"])
            dashed_h(d, x, PLOT_RIGHT - 8, y, color + (200,), 2)
            # Arrow on the bar.
            d.polygon([(x, y), (x - 6, y - 9), (x + 6, y - 9)], fill=color + (240,))
            tag = ev["level_tag"]
            tx, ty = x + 10, y - 16
            tw = 8 * len(tag) + 10
            d.rectangle([(tx, ty), (tx + tw, ty + 16)], fill=(255, 255, 255, 230), outline=color)
            d.text((tx + 4, ty), tag, fill=color, font=f11)

    # Compact table in the empty upper-middle pane (no candles there).
    table = [
        "ENGINE BROKER  →  TV UTC     EVENT            ENGINE OHLC / LEVEL",
        "03:45          →  00:45      RANGE            O 4065.51  L 4057.75  C 4058.07",
        "04:00          →  01:00      SWEEP  ↓4053.91  O 4058.07  H 4060.32  L 4053.91  C 4058.08",
        "04:15          →  01:15      DISP   ↓4046.38  O 4058.08  H 4059.19  L 4046.38  C 4047.41",
        "06:45          →  03:45      EXPANSION        O 4048.41  H 4050.85  L 4048.12  C 4049.48",
        "",
        "Clock: broker UTC+3.  TV shot: UTC.  Window: 28 Jul 01:00 → 30 Jul 09:00 UTC.",
        "Marks only. No OB / FVG / SMC. No 4H. No trade inference.",
    ]
    tx0, ty0 = 520, 88
    tw, th = 980, 168
    d.rectangle([(tx0, ty0), (tx0 + tw, ty0 + th)], fill=(255, 255, 255, 236), outline=(30, 30, 30, 255), width=2)
    d.text((tx0 + 12, ty0 + 6), "FORENSIC  broker − 3h  ==  same physical M15 candle?", fill=(20, 20, 20), font=f15b)
    yy = ty0 + 28
    row_colors = [
        (20, 20, 20),
        EVENTS[0]["color"],
        EVENTS[1]["color"],
        EVENTS[2]["color"],
        EVENTS[3]["color"],
        (20, 20, 20),
        (40, 40, 40),
        (40, 40, 40),
    ]
    for line, col in zip(table, row_colors):
        d.text((tx0 + 12, yy), line, fill=col, font=f12b if line.startswith("0") or "ENGINE" in line else f11)
        yy += 16

    # Left-edge cluster tag (the three 01:00 bars are ~8px apart at this zoom).
    d.rectangle([(62, 255), (250, 292)], fill=(255, 255, 255, 230), outline=(30, 30, 30))
    d.text((68, 260), "01:00 UTC cluster", fill=(20, 20, 20), font=f12b)
    d.text((68, 276), "RANGE / SWEEP / DISP", fill=(20, 20, 20), font=f11)

    out = Image.alpha_composite(base, ov).convert("RGB")
    out.save(OUT, "PNG")
    META.write_text(
        json.dumps(
            {
                "source": SRC.name,
                "clock": "engine broker UTC+3 → TV UTC (−3h)",
                "visible_utc": "2026-07-28 01:00 → 2026-07-30 09:00",
                "events": records,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"wrote {OUT}")
    for rec in records:
        print(
            f"  {rec['label']:13} broker {rec['broker_time'][11:]}  "
            f"utc {rec['utc_time'][11:]}  x={rec['x_px']}  in={rec['in_visible_window']}"
        )


if __name__ == "__main__":
    main()
