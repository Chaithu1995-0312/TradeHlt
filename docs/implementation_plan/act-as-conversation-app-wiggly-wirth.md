# Strict mode for the identity-chain checker + finish CH-identity-chain-closure-v1

## Context

`CH-identity-chain-closure-v1` (Phase 3 closed identity chain) was built today between
21:12 and 21:43 by a concurrent session. Code and tests landed; the governance tail did not.

Two problems remain.

**1. The checker reports success for checks it never ran.** `check_run`
(`src/governance/identity_chain.py:396`) returns
`all(o.status != FAIL for o in outcomes)` — so an invariant whose input file was not
supplied is `SKIP`, and `SKIP` passes. Running the CLI with `--telemetry` alone prints
`identity chain: CLOSED` and exits 0, having verified 2 of 7 invariants. CI reads exit
codes, so a partially-wired run is indistinguishable from a closed one.

This is the repository's own recurring failure class — F-079 (absent key vs. status),
F-083 (a sealed contract declaring a measurement the run never executed), F-085 (a
fail-closed guard that was never reachable), F-056. Each time, a skipped validation was
indistinguishable from an absent one. The design intent ("graceful partial activation")
is legitimate for local step-by-step wiring; the defect is that the *summary line and
exit code* do not disclose partiality.

**2. Workstreams F/G/H of the manifest are unstarted**, so the change cannot reach its
declared completion criteria: `scripts/governance/identity_chain_check.py` is not SITS-
registered (0 occurrences in `script_registry_stubs.jsonl` and `script-matrix.md`) while
`test_script_registry.py` / `test_script_matrix_sync.py` sit in the manifest's
`required_checks_ack`; `docs/memory/identity-chain-memory.md` and the completion manifest
do not exist; `docs/reference/schemas.md` has no entry for `bar_identity.jsonl`.

Outcome: the checker tells the truth about its own coverage, and the change reaches a
validatable completion state.

Authority unchanged: report-only tooling plus governance metadata.
`production_behavior_changed: NO` still holds — nothing here touches the decision path,
ontology, registry, or trading math.

---

## Part 1 — `--require-all` / strict mode

### `src/governance/identity_chain.py`

Add a `require_all: bool = False` keyword to `check_run` (signature at `:354`). At the
return (`:396`):

- `require_all=False` (default) → `all(o.status != FAIL ...)` — **byte-identical to today**
- `require_all=True` → `all(o.status == PASS ...)` — a SKIP is a failure

Update the `check_run` docstring and the module-docstring "SKIP semantics" paragraph
(`:31-33`) to state both modes.

**Default stays off.** The permissive default is a declared contract of the in-flight
change ("graceful partial activation, e.g. telemetry-only at step 3"), and silently
inverting another authorized change's behaviour is exactly what §6.8 forbids. Strict is
opt-in; what changes unconditionally is disclosure.

### `scripts/governance/identity_chain_check.py`

- Add `--require-all` (`store_true`), passed through to `check_run`.
- Make the summary line disclose partiality in **both** modes:
  - all seven PASS → `identity chain: CLOSED (7/7 verified)`
  - skips present, non-strict → `identity chain: CLOSED (PARTIAL — N of 7 skipped, not verified)`
  - any FAIL, or skips under `--require-all` → `identity chain: VIOLATED (...)`
- Keep the literal tokens `CLOSED` / `VIOLATED` in the output: `tests/test_identity_chain.py:257`
  asserts `"VIOLATED" in r.stdout`.
- Update the module docstring's exit-code line to describe strict mode.

### `tests/test_identity_chain.py`

Extend the existing `TestCli` class (`:242`) and reuse its `_write_fixture` /
`_status_for` helpers — do not add a new file:

- `check_run(telemetry_path=...)` alone → `ok is True` non-strict, `ok is False` with
  `require_all=True`; the five SKIP outcomes are unchanged in both.
- Golden fixture (all five inputs) → `ok is True` under `require_all=True`.
- CLI: golden fixture + `--require-all` → exit 0; telemetry-only + `--require-all` →
  exit 1 and `VIOLATED` in stdout; telemetry-only without the flag → exit 0 but stdout
  contains `PARTIAL`.

---

## Part 2 — finish the manifest tail (workstreams F/G/H)

Ordered; each step's check must be green before the next.

**Step 0 — baseline first.** `python scripts/governance/construction_protocol.py check`,
record the failing set verbatim. The manifest's `rollback_boundary` claims 6 pre-existing
reds (incl. `test_doc_citations`, `test_session_log`); the completion criterion is
"identical or strictly fewer", which is unverifiable without a captured baseline. If the
observed baseline is not 6, report the discrepancy and stop rather than absorbing it.

**Step 1 — SITS registration** of `scripts/governance/identity_chain_check.py`:
`script_census.py --write-stubs` → `scripts/governance/seed_script_registry.py` →
`scripts/analysis/generate_script_matrix.py` (note: `generate_script_matrix.py` lives
under `scripts/analysis/`, not `scripts/governance/` as CLAUDE.md §2 implies).
**Hazard:** `--write-stubs` against an empty/truncated stubs file renumbers every `SCR`
id. Diff `script_registry_stubs.jsonl` before/after and confirm the only change is an
appended row. Green: `tests/test_script_registry.py`, `tests/test_script_matrix_sync.py`.

**Step 2 — `docs/memory/identity-chain-memory.md`** (new), following the §0 memory-doc
shape used by the existing `docs/memory/*-memory.md` files: purpose, contracts, entry/exit
points, reading order into source, coverage. Content: the frozen PK
`(instrument, timeframe, bar_open_ts, corpus_sha256)`, the alias spec, the
ALLOW/DENY join table, the id-mint authority table, the 7 invariants, and the SKIP-vs-strict
distinction from Part 1.

**Step 3 — `docs/reference/schemas.md` §9**: add the `bar_identity.jsonl` line schema and
the additive columns (`trade_id` on L8, `candidate_id` / `execution_intent_id` on
TradeRecord/trades.csv, labeler lineage columns). Any `path:line` citation added here is
checked in a ±30-line window by `tests/test_doc_citations.py`.

**Step 4 — `CH-identity-chain-closure-v1.completion.json`**, shape copied from
`docs/governance/build_manifests/CH-run-identity-range-folder-manifest.completion.json`.

**Step 5 — run the gates:** the 5 new test files; the 6 `required_checks_ack` tests; then
`construction_protocol.py validate-completion docs/governance/build_manifests/CH-identity-chain-closure-v1.completion.json`.

**Step 6 — §6 SESSION LOG entry** appended to `assistant_project.md` (codebase log; the
commit-msg hook requires a same-day entry for any `src/**` commit).

---

## Risks

- **Concurrent session.** The last write to these files was 21:43; quiet since. Re-stat
  every file in Part 1 immediately before editing and abort on any change — per §1.5
  preflight, a collision here invalidates the work rather than merging it.
- **Not a review of DeepSeek's code.** Part 1 changes one return expression and the CLI's
  output; the seven verifiers are untouched. Whether I1–I7 are individually correct is a
  separate question this plan does not answer.
- **Invariant I5 is untested against a real run.** All current evidence is a synthetic
  golden fixture. The first real `results/run_*` execution is where strict mode will
  actually bite, and may surface genuine drift.

## Verification

```bash
venv/Scripts/python.exe -m pytest -q tests/test_identity_chain.py tests/test_identity_spine.py tests/test_bar_clock_bridge.py tests/test_layer_trace_trade_id.py tests/test_telemetry_identity_closure.py
```

Then, on the golden fixture, confirm by hand that telemetry-only exits 0 and says
`PARTIAL`, and that adding `--require-all` exits 1 — the behaviour the whole change exists
to produce. Finally re-run `construction_protocol.py check` and diff the failing set
against the Step 0 baseline.
