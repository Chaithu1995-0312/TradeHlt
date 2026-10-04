"""Annotate shot 06: RETEST / ENTRY / SL as separate M15 identities."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
SRC = HERE / "shots" / "06_m15_jul30_trade.png"
OUT = HERE / "shots" / "06_m15_jul30_trade_ANNOTATED.png"
META = HERE / "shots" / "06_m15_jul30_trade_ANNOTATED.json"

PRICE_TOP = 4062.0
PRICE_BOTTOM = 4041.0
Y_TOP = 80
Y_BOTTOM = 1004

# Measured candle centers on this 1920x1080 capture.
EVENTS = {
    "RETEST": {
        "utc": datetime(2026, 7, 30, 3, 45),
        "broker": datetime(2026, 7, 30, 6, 45),
        "x": 230,
        "ohlc": (4052.51, 4059.88, 4052.31, 4058.87),
        "level": 4058.87,
        "level_tag": "4058.87 RETEST close = ENTRY open",
        "draw_level": True,
        "color": (10, 125, 65),
    },
    "ENTRY": {
        "utc": datetime(2026, 7, 30, 4, 0),
        "broker": datetime(2026, 7, 30, 7, 0),
        "x": 545,
        "ohlc": (4058.87, 4060.18, 4052.77, 4053.37),
        "level": 4058.87,
        "level_tag": None,
        "draw_level": False,
        "color": (25, 90, 185),
    },
    "SL": {
        "utc": datetime(2026, 7, 30, 5, 0),
        "broker": datetime(2026, 7, 30, 8, 0),
        "x": 1665,
        "ohlc": (4046.07, 4046.16, 4041.75, 4045.97),
        "level": 4044.47,
        "level_tag": "SL 4044.47",
        "draw_level": True,
        "color": (190, 30, 30),
    },
}


def font(size: int, bold: bool = False):
    name = "consolab.ttf" if bold else "consola.ttf"
    try:
        return ImageFont.truetype(f"C:/Windows/Fonts/{name}", size)
    except OSError:
        return ImageFont.load_default()


def y_of(price: float) -> float:
    return Y_TOP + (PRICE_TOP - price) / (PRICE_TOP - PRICE_BOTTOM) * (Y_BOTTOM - Y_TOP)


def dash_h(d, x1, x2, y, fill, w=2):
    x = min(x1, x2)
    end = max(x1, x2)
    while x < end:
        d.line([(x, y), (min(x + 6, end), y)], fill=fill, width=w)
        x += 11


def dash_v(d, x, y1, y2, fill, w=2):
    y = min(y1, y2)
    end = max(y1, y2)
    while y < end:
        d.line([(x, y), (x, min(y + 7, end))], fill=fill, width=w)
        y += 12


def main() -> None:
    base = Image.open(SRC).convert("RGBA")
    ov = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    f12 = font(13)
    f13b = font(14, bold=True)
    f15b = font(16, bold=True)

    records = []
    for name, ev in EVENTS.items():
        x = ev["x"]
        col = ev["color"]
        o, h, l, c = ev["ohlc"]
        dash_v(d, x, y_of(h) - 10, 860, col + (220,), 2)
        d.line([(x - 12, y_of(h)), (x + 12, y_of(h))], fill=col + (240,), width=2)
        d.line([(x - 12, y_of(l)), (x + 12, y_of(l))], fill=col + (240,), width=2)
        if ev.get("draw_level") and ev.get("level_tag"):
            ylv = y_of(ev["level"])
            dash_h(d, 70, 1768, ylv, col + (190,), 2)
            tag = ev["level_tag"]
            tx, ty = (70, ylv - 18) if name == "SL" else (70, ylv + 6)
            d.rectangle(
                [(tx, ty), (tx + 8 * len(tag) + 12, ty + 16)],
                fill=(255, 255, 255, 235),
                outline=col,
            )
            d.text((tx + 4, ty), tag, fill=col, font=f12)

        tw = 8 * len(name) + 12
        d.rectangle(
            [(x - tw / 2, 86), (x + tw / 2, 106)],
            fill=(255, 255, 255, 235),
            outline=col,
            width=2,
        )
        d.text((x - tw / 2 + 6, 88), name, fill=col, font=f13b)
        records.append(
            {
                "label": name,
                "broker": ev["broker"].strftime("%Y-%m-%d %H:%M"),
                "utc": ev["utc"].strftime("%Y-%m-%d %H:%M"),
                "x_px": x,
                "ohlc_engine": {"O": o, "H": h, "L": l, "C": c},
                "level": ev["level"],
            }
        )

    tx0, ty0 = 780, 78
    d.rectangle(
        [(tx0, ty0), (1500, 248)],
        fill=(255, 255, 255, 236),
        outline=(25, 25, 25),
        width=2,
    )
    d.text((tx0 + 10, ty0 + 6), "SHOT 06  —  bar identity only", fill=(20, 20, 20), font=f15b)
    d.text(
        (tx0 + 10, ty0 + 26),
        "UTC 03:45–05:00  =  broker 06:45–08:00  (−3h)",
        fill=(20, 20, 20),
        font=f12,
    )
    rows = [
        "UTC    EVENT   ENGINE O / H / L / C              LEVEL",
        "03:45  RETEST  4052.51  4059.88  4052.31  4058.87   close 4058.87",
        "04:00  ENTRY   4058.87  4060.18  4052.77  4053.37   entry 4058.87",
        "04:15  (bar)   4053.36  4055.36  4051.05  4054.19",
        "04:30  (bar)   4054.19  4054.19  4047.77  4048.74",
        "04:45  (bar)   4048.74  4052.01  4044.48  4046.06",
        "05:00  SL      4046.07  4046.16  4041.75  4045.97   SL 4044.47",
        "ENTRY candle != SL candle. No OB / FVG / SMC / 4H / narrative.",
    ]
    colors = [
        (20, 20, 20),
        EVENTS["RETEST"]["color"],
        EVENTS["ENTRY"]["color"],
        (80, 80, 80),
        (80, 80, 80),
        (80, 80, 80),
        EVENTS["SL"]["color"],
        (40, 40, 40),
    ]
    yy = ty0 + 46
    for line, col in zip(rows, colors):
        d.text((tx0 + 10, yy), line, fill=col, font=f12)
        yy += 15

    out = Image.alpha_composite(base, ov).convert("RGB")
    out.save(OUT, "PNG")
    META.write_text(
        json.dumps({"source": SRC.name, "events": records}, indent=2),
        encoding="utf-8",
    )
    print(f"wrote {OUT}")
    for r in records:
        print(r)


if __name__ == "__main__":
    main()
