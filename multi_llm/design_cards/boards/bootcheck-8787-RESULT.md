# P2 boot-check result — 2026-09-18

**Status:** PASS (HTTP 200), then stopped.

## How
```text
set PYTHONPATH=D:\Tradelatest;D:\Tradelatest\src
python -c "from src.control_plane.server import run_server; run_server('127.0.0.1', 8787)"
```
GET `http://127.0.0.1:8787/` → **200**

## Notes
- `python -m src.control_plane.server` alone failed first (`ModuleNotFoundError: charts`) without `src` on PYTHONPATH; with path set, `-m` still hit runpy warning / flaky listen.
- Prefer `run_server(...)` call for local prep.
- **No Hot / no AWS / no live orders** exercised.
- Process stopped after check (do not leave plane running unless User asks).
