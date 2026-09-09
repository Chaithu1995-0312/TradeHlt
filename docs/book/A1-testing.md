# Appendix A1 — Testing the System

Status of this chapter: Written

## Why this chapter exists

Nearly every earlier chapter cited a test file as part of a concept's "Authoritative sources" —
this appendix is the one place that explains how the test suite as a whole is organized, so those
citations make sense in context.

## What you need to already know

Any Part II–VIII chapter — this is reference material for all of them, not a narrative continuation.

## The idea

### Running it

`docs/reference/testing.md` documents running the entire suite, filtering by domain (illustrative
examples given for the Agent layer, Engine orchestration, Governance gates, the Execution Planner,
Risk gates, and the live-executor subpackage), running a single test, and running with coverage.

### Layout

The suite mirrors `src/`'s structure. Some domains live as dedicated subdirectories —
`tests/analytics/`, `tests/cognitive/`, `tests/config_layer/`, `tests/data_ingestion/`,
`tests/engines/`, `tests/events/`, `tests/exec_telemetry/`, `tests/execution/`, `tests/features/`,
`tests/governance/`, `tests/inout/`, `tests/interpreters/`, `tests/journal/`, `tests/mt5_analytics/`,
`tests/portfolio/`, `tests/regime/`, `tests/replay/`, `tests/research/`, `tests/runtime/` — while
others (Agent, most of Engine orchestration, Governance gates, Planner/Risk) live as flat `test_*.py`
files directly under `tests/`, not in a dedicated subdirectory. `tests/fixtures/`, `tests/golden/`,
`tests/harness/`, `tests/helpers/`, `tests/manual/`, `tests/production_configs/` hold shared test
infrastructure rather than test cases themselves.

### Semantic-auditor suites (`tests/Grok/`, `tests/Claude/`)

Two subdirectories are not organized by `src/` domain at all. They are **semantic auditors**: each
module is a lettered "family" that asks a journey / substitution / name-collision question the
domain floors do not, and each test carries a docstring in a fixed house style (a one-sentence
intent, then `Source:` and `Failure mode:` lines). Family letters are globally unique across the
two suites, so a merged view is unambiguous.

| Suite | Families | Asks about |
|---|---|---|
| `tests/Grok/` | A–I | CRT episode journeys · number provenance · dual-implementation parity · Semantic OS fail-closed grounding · config split-brain · unit/scale mismatch · time semantics · ingestion · parent/HTF graph split |
| `tests/Claude/` | J–M | directional displacement (F-074) · SMC primitives are features not states (F-076) · schema vs stale model artifact, fail-open vs fail-closed (F-076) · reachability is not certification (F-073 / F-075) |

They deliberately do **not** retread the YAML↔enum count floors, the golden tests, or the wiring
tests — a family is a *pin*, not the layer's only test. Neither suite modifies production code and
neither grants authority (no `ACTIVE_VERSION` change, no G001, no closure stamp).

Both are inventoried at pytest-**nodeid** grain — one row per test *case*, so a parametrized
family's individual cells stay visible — by
`scripts/analysis/test_functionality_excel.py`, which writes
`docs/analysis/grok_test_intent.xlsx` and `docs/analysis/claude_test_intent.xlsx` plus a pointer
sheet for each on the class-grain `docs/analysis/tests_functionality_inventory.xlsx`. Intent is
**extracted from the docstrings, never authored in Excel**: to change a row, fix the test's
docstring and regenerate. Design:
[`docs/implementation_plan/topic-ladder-and-grok-test-intent-excel.md`](../implementation_plan/topic-ladder-and-grok-test-intent-excel.md).

### Representative patterns

The reference doc documents four representative test-writing patterns (assertion-based, invariant-
based, parametrized, and registry-exhaustiveness testing), the conventions the suite enforces beyond
just passing (see [Chapter 3](03-how-this-book-fits.md)'s classification vocabulary — many of this
book's "AUDITED" and "CLOSED" statuses trace back to a specific test file asserting the boundary
they describe), and a guide for writing a new test.

### A doc-drift this appendix flagged — now fixed at the source (2026-08-07)

`docs/reference/testing.md`'s header used to state "116 files across 15 directories," recorded
2026-06-12. This book's first pass flagged it as stale but deliberately didn't touch the reference
doc. On a follow-up pass, a fresh, exact count was taken (excluding `__pycache__`, which is compiled
bytecode cache, not source) and `testing.md`'s header was corrected directly: **411 `.py` files
(415 including 4 fixture `.json` files) across 25 directories**, dated 2026-08-07.

Worth noting for anyone who read the first version of this appendix: its own **"~1,200+ files"**
estimate was itself wrong — it came from a directory count that, on inspection, was counting
`__pycache__`'s compiled `.pyc` artifacts alongside real source (a naive recursive count including
`__pycache__` does land near ~1,248 files across 54 directories, which is what produced that
figure). The corrected, `__pycache__`-excluded count above is the one now in `testing.md`. This is
its own small lesson in the same discipline [Chapter 7](07-feature-pipeline.md) demonstrates:
verify a number against the actual filesystem before repeating it, even when the number is one this
book generated itself.

## Classification

| Concept | Status |
|---|---|
| The test suite itself | Production, actively maintained |
| `docs/reference/testing.md`'s file-count header | **Fixed** (2026-08-07) — 411 `.py` files / 415 incl. fixtures, across 25 directories |
| `tests/Grok/` (families A–I) + `tests/Claude/` (families J–M) | Semantic auditors — advisory, grant no authority; not in GREEN_FLOOR |

## Authoritative sources

- `docs/reference/testing.md` — the full reference (running, config, layout, coverage expectations,
  patterns, conventions, CI/regression).
- `tests/conftest.py` — shared fixtures and pytest configuration hooks.
- `pyproject.toml` — the pytest configuration itself.
- `tests/Grok/__init__.py`, `tests/Claude/__init__.py` — each auditor suite's own doctrine.
- `scripts/analysis/test_functionality_excel.py` — the inventory generator for all three workbooks.
- `tests/test_grok_intent_workbook.py`, `tests/test_claude_intent_workbook.py` — the workbook floors.

## Unresolved questions

None — the count was re-verified directly against the filesystem (excluding `__pycache__`) and the
reference doc now matches it.

---
**Previous:** [Chapter 24 — Repository Encyclopedia](24-repository-encyclopedia.md) · **Next:** [Appendix A2 — Unresolved Questions](A2-unresolved-questions.md)
**Related:** [Chapter 03 — How This Book Fits](03-how-this-book-fits.md)
**Memory:** none dedicated.
