"""Annotate shot 05: separate SWEEP / DISPLACEMENT bodies. No SMC/4H/trade."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
SRC = HERE / "shots" / "05_m15_jul28_displacement.png"
OUT = HERE / "shots" / "05_m15_jul28_displacement_ANNOTATED.png"
META = HERE / "shots" / "05_m15_jul28_displacement_ANNOTATED.json"

# Linear price scale across the full right axis (chart + volume).
PRICE_TOP = 4062.0
PRICE_BOTTOM = 4039.0
Y_TOP = 80
Y_BOTTOM = 1006

# 13 M15 bars, 01:00 UTC through 04:00 UTC inclusive.
BARS_UTC = [
    datetime(2026, 7, 28, 1, 0),
    datetime(2026, 7, 28, 1, 15),
    datetime(2026, 7, 28, 1, 30),
    datetime(2026, 7, 28, 1, 45),
    datetime(2026, 7, 28, 2, 0),
    datetime(2026, 7, 28, 2, 15),
    datetime(2026, 7, 28, 2, 30),
    datetime(2026, 7, 28, 2, 45),
    datetime(2026, 7, 28, 3, 0),
    datetime(2026, 7, 28, 3, 15),
    datetime(2026, 7, 28, 3, 30),
    datetime(2026, 7, 28, 3, 45),
    datetime(2026, 7, 28, 4, 0),
]
# Measured candle centers on this 1920x1080 capture (not even-spacing).
X_BY_UTC = {
    datetime(2026, 7, 28, 1, 0): 200,
    datetime(2026, 7, 28, 1, 15): 300,
    datetime(2026, 7, 28, 3, 45): 1595,
}

ENGINE = {
    "RANGE": {
        "utc": datetime(2026, 7, 28, 0, 45),
        "broker": datetime(2026, 7, 28, 3, 45),
        "ohlc": (4065.51, 4065.56, 4057.75, 4058.07),
        "color": (25, 90, 185),
        "on_shot": False,
    },
    "SWEEP": {
        "utc": datetime(2026, 7, 28, 1, 0),
        "broker": datetime(2026, 7, 28, 4, 0),
        "ohlc": (4058.07, 4060.32, 4053.91, 4058.08),
        "color": (190, 30, 30),
        "on_shot": True,
        "level": 4053.91,
    },
    "DISPLACEMENT": {
        "utc": datetime(2026, 7, 28, 1, 15),
        "broker": datetime(2026, 7, 28, 4, 15),
        "ohlc": (4058.08, 4059.19, 4046.38, 4047.41),
        "color": (170, 90, 0),
        "on_shot": True,
        "level": 4046.38,
    },
    "EXPANSION": {
        "utc": datetime(2026, 7, 28, 3, 45),
        "broker": datetime(2026, 7, 28, 6, 45),
        "ohlc": (4048.41, 4050.85, 4048.12, 4049.48),
        "color": (10, 125, 65),
        "on_shot": True,
    },
}


def font(size: int, bold: bool = False):
    name = "consolab.ttf" if bold else "consola.ttf"
    try:
        return ImageFont.truetype(f"C:/Windows/Fonts/{name}", size)
    except OSError:
        return ImageFont.load_default()


def x_of(utc: datetime) -> float:
    if utc in X_BY_UTC:
        return float(X_BY_UTC[utc])
    raise KeyError(f"no measured x for {utc}")


def y_of(price: float) -> float:
    return Y_TOP + (PRICE_TOP - price) / (PRICE_TOP - PRICE_BOTTOM) * (Y_BOTTOM - Y_TOP)


def dash_h(d, x1, x2, y, fill, w=1):
    x = min(x1, x2)
    end = max(x1, x2)
    while x < end:
        d.line([(x, y), (min(x + 5, end), y)], fill=fill, width=w)
        x += 10


def dash_v(d, x, y1, y2, fill, w=2):
    y = min(y1, y2)
    end = max(y1, y2)
    while y < end:
        d.line([(x, y), (x, min(y + 6, end))], fill=fill, width=w)
        y += 11


def main() -> None:
    base = Image.open(SRC).convert("RGBA")
    ov = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    f12 = font(13)
    f13b = font(14, bold=True)
    f15b = font(16, bold=True)

    records = []
    for name, ev in ENGINE.items():
        rec = {
            "label": name,
            "broker": ev["broker"].strftime("%Y-%m-%d %H:%M"),
            "utc": ev["utc"].strftime("%Y-%m-%d %H:%M"),
            "ohlc_engine": {
                "O": ev["ohlc"][0],
                "H": ev["ohlc"][1],
                "L": ev["ohlc"][2],
                "C": ev["ohlc"][3],
            },
            "on_shot": ev["on_shot"],
        }
        if not ev["on_shot"]:
            records.append(rec)
            continue
        x = x_of(ev["utc"])
        rec["x_px"] = round(x, 1)
        col = ev["color"]
        o, h, l, c = ev["ohlc"]
        dash_v(d, x, y_of(h) - 8, 860, col + (210,), 2)
        # High / low ticks.
        d.line([(x - 10, y_of(h)), (x + 10, y_of(h))], fill=col + (240,), width=2)
        d.line([(x - 10, y_of(l)), (x + 10, y_of(l))], fill=col + (240,), width=2)
        if ev.get("level") is not None:
            ylv = y_of(ev["level"])
            dash_h(d, x + 14, 1760, ylv, col + (200,), 2)
            tag = f"{ev['level']:.2f}"
            d.rectangle(
                [(x + 16, ylv - 16), (x + 16 + 8 * len(tag), ylv + 2)],
                fill=(255, 255, 255, 230),
                outline=col,
            )
            d.text((x + 20, ylv - 15), tag, fill=col, font=f12)

        # Tiny name tag at the top of the bar — keep OHLC in the table only.
        tag = name if name != "DISPLACEMENT" else "DISP"
        tw = 8 * len(tag) + 10
        d.rectangle(
            [(x - tw / 2, 86), (x + tw / 2, 104)],
            fill=(255, 255, 255, 235),
            outline=col,
            width=2,
        )
        d.text((x - tw / 2 + 5, 88), tag, fill=col, font=f13b)
        records.append(rec)

    # Table in the empty upper-right.
    tx0, ty0 = 620, 78
    d.rectangle([(tx0, ty0), (1320, 250)], fill=(255, 255, 255, 236), outline=(25, 25, 25), width=2)
    d.text((tx0 + 10, ty0 + 6), "SHOT 05  —  bar identity only", fill=(20, 20, 20), font=f15b)
    d.text((tx0 + 10, ty0 + 26), "UTC 01:00–04:00   =   broker 04:00–07:00   (−3h)", fill=(20, 20, 20), font=f12)
    rows = [
        "UTC    EVENT          ENGINE O / H / L / C",
        "00:45  RANGE          off-window (1 bar left of 01:00)",
        "01:00  SWEEP          4058.07  4060.32  4053.91  4058.08",
        "01:15  DISPLACEMENT   4058.08  4059.19  4046.38  4047.41",
        "03:45  EXPANSION      4048.41  4050.85  4048.12  4049.48",
        "No OB / FVG / SMC / 4H / trade reading.",
    ]
    yy = ty0 + 48
    colors = [
        (20, 20, 20),
        ENGINE["RANGE"]["color"],
        ENGINE["SWEEP"]["color"],
        ENGINE["DISPLACEMENT"]["color"],
        ENGINE["EXPANSION"]["color"],
        (60, 60, 60),
    ]
    for line, col in zip(rows, colors):
        d.text((tx0 + 10, yy), line, fill=col, font=f12)
        yy += 16

    out = Image.alpha_composite(base, ov).convert("RGB")
    out.save(OUT, "PNG")
    META.write_text(json.dumps({"source": SRC.name, "events": records}, indent=2), encoding="utf-8")
    print(f"wrote {OUT}")
    for r in records:
        print(r)


if __name__ == "__main__":
    main()
