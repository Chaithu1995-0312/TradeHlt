# Plan: Prove no exits are evaluated on the entry bar

## Context
User rule: SL / TP1 / TP2 must never be evaluated on the bar the trade was entered.
Source check (read-only): this already holds — `forward_walk` always raises on a bar with
`index <= entry_index`; `multi_tp_walk` (both production and observable_only paths) and
`reference_walk` raise the same way **when `entry_index` is passed** and the bar carries
`.index`. Callers slice `candles[entry_index+1:]`. No behaviour change is needed; only a
proving test.

Known gap (report, do not change): `multi_tp_walk` / `reference_walk` with
`entry_index=None` have no guard — exclusion then relies on the caller's slice.

## Change
Add tests to `tests/research/test_observable_intrabar_order.py` (no `src/` edits):
1. For each walker × tie_break (`multi_tp_walk` production + observable_only,
   `reference_walk` observable_only, `forward_walk` default + observable_only): passing the
   entry bar (index == entry_index) as the first forward bar raises `ValueError` (lookahead).
2. Entry bar that touches SL, TP1 and TP2 is excluded by the slice: walking only the bars
   after it gives an outcome that ignores the entry bar's range (e.g. quiet forward bars ->
   TIMEOUT, not STOPPED/TP).

## Verification
`venv/Scripts/python.exe -m pytest tests/research/test_observable_intrabar_order.py -q`.
Append SESSION LOG entry to `assistant_project.md`.
