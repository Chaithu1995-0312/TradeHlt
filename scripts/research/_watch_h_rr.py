"""Watch H-RR-THRESHOLD-001 until REPORT.md exists or processes die."""
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "research" / "h_rr_threshold_001"
REPORT = OUT / "REPORT.md"
ENTRIES = OUT / "entries.jsonl"


def hrr_pids() -> list[int]:
    try:
        import subprocess

        r = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | "
                "Where-Object { $_.CommandLine -match 'h_rr_threshold' } | "
                "Select-Object -ExpandProperty ProcessId",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        pids = []
        for line in (r.stdout or "").splitlines():
            line = line.strip()
            if line.isdigit():
                pids.append(int(line))
        return pids
    except Exception:
        return []


def main() -> int:
    t0 = time.time()
    last = ""
    while True:
        pids = hrr_pids()
        has_report = REPORT.exists()
        n_ent = 0
        if ENTRIES.exists():
            with open(ENTRIES, encoding="utf-8") as f:
                for n_ent, _ in enumerate(f, 1):
                    pass
        msg = f"t={time.time()-t0:.0f}s pids={pids} entries={n_ent} report={has_report}"
        if msg != last:
            print(msg, flush=True)
            last = msg
        if has_report:
            print("DONE", REPORT, flush=True)
            if (OUT / "report.json").exists():
                rep = json.loads((OUT / "report.json").read_text(encoding="utf-8"))
                print("program_verdict:", rep.get("program_verdict"), flush=True)
            return 0
        if not pids and not has_report:
            # give a short grace in case of write race
            time.sleep(5)
            if REPORT.exists():
                continue
            print("STOPPED_NO_REPORT", flush=True)
            print("artifacts:", list(OUT.iterdir()) if OUT.exists() else None, flush=True)
            return 2
        time.sleep(30)


if __name__ == "__main__":
    raise SystemExit(main())
