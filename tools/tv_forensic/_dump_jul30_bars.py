from datetime import datetime, timedelta
from pathlib import Path

p = Path("data/XAUUSD_M15.csv")
with p.open(encoding="utf-8") as f:
    next(f)
    for line in f:
        if not line.startswith("2026-07-30 "):
            continue
        ts, o, h, l, c, v = line.strip().split(",")
        b = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        if b.hour < 6 or b.hour > 8:
            continue
        u = b - timedelta(hours=3)
        print(
            f"broker {ts}  utc {u.strftime('%H:%M')}  "
            f"O {o} H {h} L {l} C {c}"
        )
