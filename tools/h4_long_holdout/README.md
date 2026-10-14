# H4 long-only 1.5R holdout (XAUUSD)

Record of one frozen rule, run once on unseen 2026 months. Published page: <https://claude.ai/artifact/HR2YurD39GWZd5QneVPjMJ> ("H4 Long Holdout Ledger").

- `declaration.json`: the frozen rule, data, windows and pass bar. sha256 `2c3016a147f26ab3285fb36309b5834d9d133ec35edb8c7a7ad9e7d54869027b`, logged in `assistant_project.md` before the run.
- `replica.py`: independent re-implementation of Codex's HTF-XAUUSD-RR-GRID-V1 rules. Matched Codex commit `f6a5076` on the July–August window: 66/66 H4 and 27/27 H8 candidates, same entry, stop and net R at 1.5R, 3R and 5R.
- `build_data.py`: per-trade and per-day records for Account A (under test) and Account B (kept for research) → `results/h4_long_holdout/holdout.json`.
- `render.py`: the page → `results/h4_long_holdout/report.html`.

Result: FAIL. Account A, 49 trades, 29% won, average −0.30R, −₹4,23,024, worst drop 44.1%. Gold fell from 4,541.96 to 4,156.91 over the test windows.

These test windows are now used for this rule; do not retune it or rerun it on them.

Rebuild (repo root):

```
venv\Scripts\python.exe tools\h4_long_holdout\build_data.py
venv\Scripts\python.exe tools\h4_long_holdout\render.py
```
