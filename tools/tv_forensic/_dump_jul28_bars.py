from datetime import datetime, timedelta
from pathlib import Path

p = Path("data/XAUUSD_M15.csv")
with p.open(encoding="utf-8") as f:
    next(f)
    for line in f:
        if not (line.startswith("2026-07-27 2") or line.startswith("2026-07-28 0")):
            continue
        ts, o, h, l, c, v = line.strip().split(",")
        b = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        u = b - timedelta(hours=3)
        print(
            f"broker {ts}  utc {u.strftime('%Y-%m-%d %H:%M')}  "
            f"O {o} H {h} L {l} C {c}"
        )
