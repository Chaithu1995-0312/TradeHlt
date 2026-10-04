# ARCHIVED: src/inout/ — 2026-05-02

## Reason
Parallel execution pipeline that bypassed the canonical spine:
  EngineRunner → FusionEngine → DecisionEngine → ExecutionPlannerV1_2 → UltronRiskGate

Specific violations:
- `probability_engine.py` (47KB) — duplicate decision/probability logic, bypasses DecisionEngine
- `state_machine.py` — duplicate orchestration, bypasses live_engine_hook
- `controller.py`, `executor.py`, `runner.py` — alternative execution loop
- `scanner.py` — duplicates src/scanner/
- `db.py` — SQLite persistence, violates no-DB convention (CLAUDE.md §4)

## No production src/ importers at time of archival
Only `tests/inout/` referenced these modules.

## Replacement
All valid IO orchestration routes through:
  `src/runtime/live_engine_hook.py:HookedLiveEngine.process()`

## Tests
Move `tests/inout/` to `tests/archive/` or delete — these tests validate
the archived pipeline and should not run against production.
