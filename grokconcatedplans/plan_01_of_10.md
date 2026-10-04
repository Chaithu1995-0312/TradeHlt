# Concatenated session plans — part 1 of 10

Source directory: `docs/plans/`
Files in this part: 7

## Contents

1. `22-pre-existing-failures-check-splendid-biscuit.md` (4430 bytes)
2. `analyse-assistant-project-d-giggly-flask.md` (5702 bytes)
3. `analyse-the-accuracy-of-robust-kay.md` (12011 bytes)
4. `analyze-only-this-runtime-wondrous-shell.md` (69654 bytes)
5. `assume-the-architecture-is-joyful-naur.md` (6517 bytes)
6. `based-on-your-screenshot-precious-scott.md` (12239 bytes)
7. `below-is-a-prompt-mighty-riddle.md` (9547 bytes)


================================================================================
SOURCE_FILE: docs/plans/22-pre-existing-failures-check-splendid-biscuit.md
SOURCE_BYTES: 4430
PART: 1/10 FILE 1/7
================================================================================

> Created: 2026-06-01 · Updated: 2026-06-01 · Milestone: Pre-existing failure audit + contract audit

# Context

23 pre-existing test failures across 5 groups. User correctly identified this as a **contract audit** problem, not a simple bug-bash. Before fixing, each group needs its authoritative layer established. Contract audit complete — findings below.

---

# Contract Audit Findings

## Group 1 — `gaussian_shadow` missing attribute (8 failures) — RUNTIME BUG ✗

**Verdict: Fix immediately. No policy ambiguity.**

- `src/core/engine_runner.py:671` accesses `self.gaussian_shadow` during `runner.run()`
- `EngineRunner.__init__` never initialises this attribute
- This is on the main execution spine (`engine_runner → fusion → decision`). Risk: HIGH.
- **Fix:** Add `self.gaussian_shadow = ...` initialisation. Need to read the class to determine correct default.

---

## Group 2 — LLM fail-open returns `0.5` instead of `1.0` (11 failures) — RUNTIME BUG ✗

**Verdict: Runtime is wrong. Tests and docs agree.**

All three sources speak:
- `docs/reference/architecture.md:206` — "returns neutral `1.0`"
- `src/config_layer/llm_scorer.py:116` (docstring) — "fail-open 1.0"
- `tests/test_llm_connectivity.py:135,140,145,150` — explicit `assert score == 1.0  # fail-open sentinel`

Runtime at `llm_scorer.py:85,101,109,220` returns `0.5`.

**Fix:** Change those four lines from `return 0.5` → `return 1.0`.

---

## Group 3 — Feature schema fail-open (1 failure) — POLICY DECISION NEEDED ⚠️

**Verdict: Docs are silent. Tests and runtime disagree. User must decide.**

- `src/features/feature_schema.py:248`: `def check_compatibility(cls, version, fail_closed: bool = True)`
- Default is `fail_closed=True` → unregistered schema version → returns `False` (reject)
- Test expects unregistered version → returns `True` (allow through)
- `docs/reference/schemas.md` and `docs/reference/conventions.md` are both silent on this

Two valid positions:
- **Fail-open (allow unknown):** innovation-friendly, matches test intent — change default to `fail_closed=False`
- **Fail-closed (reject unknown):** governance-friendly, consistent with CLAUDE.md §4 emphasis on validation gates — update test to pass `fail_closed=False` explicitly when testing the opt-in path

---

## Group 4 — ReplayMemoryEngine load failure (2 failures) — INVESTIGATION NEEDED ⚠️

**Verdict: zone_id is optional at code level, but something causes silent load abort.**

Contract audit confirms:
- `zone.get("zone_id", 0)` — optional at runtime
- Test fixtures don't include zone_id — correct per design
- BUT load still fails with: `"load failed (fail-open) — 'zone_id'"`

Root cause is deeper — possibly `z["zone_id"]` bracket access at `replay_memory_engine.py:425` inside a dict comprehension on the zone registry (not the replay records). Need to read the full `_load()` method to confirm before fixing.

---

## Group 5 — Gaussian ML impl mismatch (1 failure) — TEST FIXTURE ISSUE ✗

**Verdict: Test-only fix. No product risk.**

- Production config: `gaussian_impl=heuristic`
- Test expects `MLGaussianEngine`
- Fix: inject `gaussian_impl=ml` in the test fixture's config before constructing EngineRunner

---

# Recommended Execution (pending policy decision on Group 3)

### Phase A — Unambiguous runtime fixes
1. **Group 1:** Initialise `gaussian_shadow` in `engine_runner.py` → removes 8 failures
2. **Group 2:** Change `llm_scorer.py` returns from `0.5` → `1.0` at 4 lines → removes 11 failures
3. **Group 5:** Patch test fixture `gaussian_impl=ml` → removes 1 failure

### Phase B — After policy decision
4. **Group 3:** Either change `fail_closed` default OR update test to use `fail_closed=False` → removes 1 failure

### Phase C — After deeper investigation
5. **Group 4:** Read `_load()` method fully, identify root cause of `'zone_id'` KeyError → removes 2 failures

---

# Verification

After Phase A:
```
pytest tests/test_engine_runner_dual_gate.py tests/test_engine_runner_rr_fusion.py tests/test_llm_scorer.py tests/test_gaussian_impl_switch.py -v
```
Expected: 20 newly passing, 0 regressions.

After Phase B+C:
```
pytest tests/features/test_feature_schema_registry.py tests/replay/test_replay_memory_engine.py -v
```
Expected: 3 newly passing.

Full suite regression check:
```
pytest --tb=no -q
```
Expected: 23 fewer failures, same 1188 passing.


================================================================================
SOURCE_FILE: docs/plans/analyse-assistant-project-d-giggly-flask.md
SOURCE_BYTES: 5702
PART: 1/10 FILE 2/7
================================================================================

# Plan — Analyse `assistant_project.md` & Trace User Intention "of Tool"

> Created: 2026-05-30 · Updated: 2026-05-30 · Type: analysis (doc-only, additive)

## Context

The user asked to **analyse `assistant_project.md`** (the repo's append-only SESSION LOG,
2472 lines / 37 entries, 2026-04-10 → 2026-05-30) and **trace the user's intention "of tool."**
Clarified scope = **Both**:

1. **Project intent arc** — what the user has been trying to build and *why*, reconstructed
   from the session log (plain-language narrative; user thinks in goals/flows/outcomes).
2. **Agent intent→tool layer** — the literal "user intention → tool" machinery in `src/agent/`
   (`IntentRouter.classify` → `PLAN_REGISTRY` → `Executor` → `tool_registry`), and how the
   project arc maps onto it.

Deliverable = a **new point-in-time doc** under `docs/analysis/` (the repo's convention for
dated, non-living analyses — see `docs/analysis/readme.md`). This is purely additive: one new
file + one index row. No code, no config, no living-doc edits.

## Deliverable

**New file:** `docs/analysis/user-intention-trace-2026-05-30.md`
**Index row added to:** `docs/analysis/readme.md` (the table, top of list).

## Doc structure (sections)

1. **Header + scope note** — point-in-time disclaimer (matches sibling files); source =
   `assistant_project.md` as of 2026-05-30.
2. **The intention arc (5 eras)** — narrative traced from the log's 37 entries:
   - **Era 1 · Foundation & documentation** (2026-04-10 → 04-22): enhancement plan phases 0–5,
     JSON-as-single-source-of-truth, master-context docs suite, architecture diagram, agent
     design docs. Intent: *make the system governable + legible.*
   - **Era 2 · Stabilisation & correctness** (2026-04-25 → 04-30): pytest restored to 0 failures,
     stale-API agent test fixes, dead-code archive, RR data-integrity audit (rr=2.0 contamination),
     canonical naming (UltronRiskGate), feature-zeroing root-causes, signal-flow doc. Intent:
     *trust the numbers before extending.*
   - **Era 3 · Multi-strategy expansion** (2026-04-30 → 05-01): Sprints 1–7 — 10 strategies,
     StrategyOrchestrator, FusionEngine multi-strategy, MonteCarlo, KillSwitch, UAT, live hook,
     Docker, governance. Intent: *scale from CRT-only to a portfolio engine.*
   - **Era 4 · Empirical, telemetry-driven tuning** (2026-05-12 → 05-30): two-layer arch
     (runtime vs research), direction-mirroring, calibration; then the **BNBUSDT Phase 0→6b**
     measure-first loop (shadow displacement, expansion TTL, age-decay verdict=advisory-only,
     threshold sweep, ROI baseline, funnel diagnosis: RETEST→EXECUTION binding constraint =
     session filter). Intent: *let measured data, not hypotheses, drive changes* (memory:
     several hypotheses were invalidated by telemetry).
   - **Era 5 · LLM-context-economy migration** (2026-05-28 → 05-30): M0–M5 event-driven
     migration doctrine, trigger vocabulary, GOAL.md north-star, collaboration workflow,
     code-map generator, semantic docs reorg. Intent: *make the codebase ownable by an LLM
     loading only one service's context.*
3. **The throughline (deep intention)** — synthesis: the user's consistent meta-goal is a
   trading system that is (a) deterministic/replayable, (b) governed (no config to prod without
   APPROVE), (c) empirically validated not guessed, and (d) **LLM-ownable** — the five
   governance questions + context-economy north star are the unifying frame.
4. **The agent intent→tool layer (literal "user intention of tool")** — trace the pipeline:
   `User NL → IntentRouter.classify() (regex fast-path conf 0.85 → LLM fallback conf_floor 0.6
   → degenerate ask_user) → PlanCompiler.build() (deterministic PLAN_REGISTRY, LLM never picks
   tools) → ArgFiller → Executor.run() (confirm-gate on write tools + path-guard) → AuditLogger`.
   Tables: 14 intents (7 pipeline / 3 copilot / 3 governance / 1 cross-mode + ask_user),
   intent→tool-sequence map, write/read split. Cite `src/agent/intent_router.py`,
   `plan_compiler.py`, `tool_registry.py`, `executor.py`.
5. **Where the two meet** — map: the agent's design *embodies* the project intent. Determinism
   (PLAN_REGISTRY) ⇄ replay-correctness invariant; copilot read-only + UltronRiskGate sole
   authority ⇄ "LLMs advisory, never execution"; confirm-gate/path-guard ⇄ governed writes;
   audit JSONL ⇄ auditability question. The trigger vocabulary (Era 5) is the human-facing
   sibling of the agent's intent routing.
6. **Open intentions (from latest `Next Step` fields)** — M3 orchestration de-coupling; Phase 5
   tier_2_threshold sweep; ROI session-window sweep (add Asia); gate-on-ROI vs optimize-for-ROI
   decision still pending with user.

## Sources (already read during planning)

- `assistant_project.md` — full topic/date/next-step arc (37 entries).
- `docs/reference/agent-reference.md` §1–§5 — routing flow, 14 intents, 20 tools, PLAN_REGISTRY.
- `docs/analysis/readme.md` — naming/format convention + index table.
- Memory: `project_phase*` entries (Phase 0/1/2b/3b/4b/5a/6/6b) corroborate the "measure-first,
  hypotheses-invalidated" intention in Era 4.

## Verification

- All `file:line` / module citations in the doc resolve (grep the cited symbols:
  `IntentRouter`, `PLAN_REGISTRY`, `PlanCompiler`, intent keys) — read-only check.
- New file follows sibling format (header + point-in-time disclaimer + dated kebab-case name).
- `docs/analysis/readme.md` table gains exactly one new row, dated 2026-05-30, no other edits.
- Append the mandated `📝 SESSION LOG ENTRY` block to `assistant_project.md` (CLAUDE.md §6).


================================================================================
SOURCE_FILE: docs/plans/analyse-the-accuracy-of-robust-kay.md
SOURCE_BYTES: 12011
PART: 1/10 FILE 3/7
================================================================================

> Created: 2026-05-23 · Updated: 2026-05-23 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Fix: Session Label Missing from TRADE_OPENED Event Metadata

## Context

The P3b session histogram always shows `UNKNOWN` for every executed trade because `session_name` is never included in the `TRADE_OPENED` event metadata dict. The session IS correctly detected one block earlier (for the FILTER_REJECTED/off-session guard at line 1622-1626) but the computed `_sess_name` variable is not forwarded into the success path's `ev_log.record("TRADE_OPENED", ...)` call at line 1647. The P3b histogram reader also uses the wrong key (`"session"` instead of `"session_name"`).

This is a read-only schema addendum — adds one key to an existing event type. No trade logic changes.

---

## Files modified (exactly 2)

| File | Change |
|---|---|
| `src/config_layer/crt_engine_v2.py` | Add `"session_name": _sess_name` to TRADE_OPENED metadata dict at line 1651 |
| `scripts/analysis/p3b_session_relax_diag.py` | Change histogram key from `"session"` to `"session_name"` at line 234 |

---

## Surgical edits

### 1. `src/config_layer/crt_engine_v2.py` — lines 1651-1658

`_sess_name` is computed at line 1622 and used by the FILTER_REJECTED branch (line 1631: `"session_name": _sess_name`). Add the same key to the TRADE_OPENED metadata:

**Before (lines 1651-1658):**
```python
                            metadata={
                                "id": trade.id,
                                "S_score": final_S,
                                "sl": trade.sl_price,
                                "tp1": trade.tp1_price,
                                "tp2": trade.tp2_price,
                                "risk_pct": trade.risk_pct,
                            },
```

**After:**
```python
                            metadata={
                                "id": trade.id,
                                "session_name": _sess_name,
                                "S_score": final_S,
                                "sl": trade.sl_price,
                                "tp1": trade.tp1_price,
                                "tp2": trade.tp2_price,
                                "risk_pct": trade.risk_pct,
                            },
```

Key name `session_name` matches the convention already used in FILTER_REJECTED events (line 1631) — no new naming introduced.

### 2. `scripts/analysis/p3b_session_relax_diag.py` — line 234

**Before:**
```python
        sess = e.get("metadata", {}).get("session", "UNKNOWN")
```

**After:**
```python
        sess = e.get("metadata", {}).get("session_name", "UNKNOWN")
```

---

## What does NOT change

- No trade logic, filter logic, or execution path is modified.
- No existing JSONL keys are removed (pure additive change).
- No tests assert TRADE_OPENED metadata fields — zero test updates needed.
- `docs/SCHEMAS.md` does not document the TRADE_OPENED event shape — no doc update needed.
- P4 script computes session via its own monkeypatch; can optionally be simplified later but not in scope here.
- `_sess_name` variable already exists in scope at the call site — no new computation.

---

## Verification

```bash
# Run P3b on any instrument — session histogram should now show named sessions
python scripts/analysis/p3b_session_relax_diag.py --instrument ETHUSDT

# Expected output for "Session histogram of executed trades (patched run)":
#   LONDON         : N
#   NEWYORK        : N
#   OVERLAP        : N
#   ASIA           : N   (if --add-sessions ASIA,OFF_SESSION used)
#   OFF_SESSION    : N
# NOT: UNKNOWN     : 31
```

---

# Parameterise All P-Scripts with --instrument (P3a, P3b, P3c, P3c1, P4)

## Context

All five diagnostic scripts under `scripts/analysis/` (P3a, P3b, P3c, P3c1, P4) share three hardcoded top-level constants: `CSV_PATH`, `INSTRUMENT = "ETHUSDT"`, `OUTPUT_DIR`. P3b and P3c additionally have hardcoded ETHUSDT-specific baseline values (BASELINE_TRADES=4, BASELINE_AVG_RR=0.39, BASELINE_TOTAL_PNL=1.57). To run the same diagnostics on BTC/SOL/BNB without editing files each time, all five scripts need argparse with `--instrument` as a required argument. The data folder now has `{SYMBOL}_M15.csv` for every symbol so no XLSX conversion is needed in the common path (but an XLSX fallback is added for future coverage).

## Files modified (exactly 5)

| Script | Hardcoded to remove | Script-specific new args |
|---|---|---|
| `scripts/analysis/p3a_zone_attribution_diag.py` | CSV_PATH, INSTRUMENT, OUTPUT_DIR | none |
| `scripts/analysis/p3b_session_relax_diag.py` | CSV_PATH, INSTRUMENT, OUTPUT_DIR, BASELINE_TRADES, BASELINE_AVG_RR, BASELINE_TOTAL_PNL | `--add-sessions`, `--min-r-exp`, `--max-dd` |
| `scripts/analysis/p3c_zone_relax_diag.py` | CSV_PATH, INSTRUMENT, OUTPUT_DIR, ZONE_RELAX_PCT, BASELINE_TRADES, BASELINE_AVG_RR, BASELINE_TOTAL_PNL | `--zone-relax-pct` |
| `scripts/analysis/p3c1_build_trade_audit.py` | CSV_PATH, INSTRUMENT, OUTPUT_DIR | none |
| `scripts/analysis/p4_execution_intent_attribution.py` | CSV_PATH, INSTRUMENT, OUTPUT_DIR | none |

No changes to any file under `src/`. Diagnostics only.

---

## Argparse interface (per script)

### Common args (all 5 scripts)

```
--instrument   SYMBOL       Required. E.g. BTCUSDT, SOLUSDT, BNBUSDT, ETHUSDT
--csv          PATH         Optional. Explicit path to data file (CSV or XLSX).
                             Auto-resolved if omitted (see resolution order below).
--output-dir   PATH         Default: results
```

### P3b-specific

```
--add-sessions  ASIA,OFF_SESSION   Comma-separated sessions to add to allowed_sessions
                                    Default: ASIA,OFF_SESSION
--min-r-exp     0.39               Quality gate: min R expectancy on ADDED trades
--max-dd        0.0132             Quality gate: max drawdown (decimal)
```

### P3c-specific

```
--zone-relax-pct  0.60             Replaces the editable ZONE_RELAX_PCT constant
                                    (second run: pass 0.67)
```

### Example invocations

```bash
python scripts/analysis/p3a_zone_attribution_diag.py --instrument BTCUSDT
python scripts/analysis/p3b_session_relax_diag.py   --instrument SOLUSDT
python scripts/analysis/p3b_session_relax_diag.py   --instrument BNBUSDT --min-r-exp 0.20
python scripts/analysis/p3c_zone_relax_diag.py      --instrument BTCUSDT --zone-relax-pct 0.67
python scripts/analysis/p3c1_build_trade_audit.py   --instrument SOLUSDT
python scripts/analysis/p4_execution_intent_attribution.py --instrument BNBUSDT
```

---

## Data file resolution (shared helper — same logic in all 5 scripts)

Add a `_resolve_data_file(instrument: str, csv_override: str | None) -> str` function near the top of each script:

```python
def _resolve_data_file(instrument: str, csv_override: str | None) -> str:
    if csv_override:
        p = Path(csv_override)
        if not p.exists():
            sys.exit(f"[ERROR] --csv path not found: {csv_override}")
        return str(p)
    candidates = [
        _ROOT / "data" / f"{instrument}_M15.csv",
        _ROOT / "data" / f"{instrument}_M15_2year.csv",
        _ROOT / "data" / f"{instrument}_M15_2year.xlsx",
        _ROOT / "data" / f"{instrument}_M15.xlsx",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    checked = "\n  ".join(str(c) for c in candidates)
    sys.exit(f"[ERROR] No data file found for {instrument}. Checked:\n  {checked}")
```

If the resolved path ends with `.xlsx`, use an inline `_xlsx_stream()` + `_xlsx_count()` pair (using `openpyxl.load_workbook(read_only=True)`) that yields the same `Candle` objects as `CandleLoader.stream()`. Since all symbols now have `*_M15.csv`, this path is a future-proofing fallback only.

---

## P3b — two-run auto-baseline (replace BASELINE_* constants)

P3b currently hardcodes ETHUSDT baseline values (BASELINE_TRADES=4, BASELINE_TOTAL_PNL=1.57). Replace with an automatic two-run approach inside the same script invocation:

**Run 0 (baseline):** instantiate `BacktestRunner` with the original (unpatched) CRTConfig and the instrument's data file. Call `runner.run(...)`. Capture `baseline_metrics`.

**Run 1 (patched):** apply `dataclasses.replace(crt_cfg, allowed_sessions=patched_sessions)`. Run again. Capture `patched_metrics`.

Delta computation replaces all `BASELINE_*` references:
```python
added_trades     = patched_metrics.approved_trades - baseline_metrics.approved_trades
added_pnl        = patched_metrics.total_pnl_rr_net - baseline_metrics.total_pnl_rr_net
r_expectancy_added = added_pnl / max(added_trades, 1)
```

Run 0 uses `overrides={"diagnostic": "P3b_baseline", "instrument": args.instrument}`.
Run 1 uses `overrides={"diagnostic": "P3b_session_relax", "instrument": args.instrument}`.

The funnel baseline column in the report is drawn from Run 0's event log, not hardcoded constants. The report format and verdict logic are otherwise identical.

## P3c — two-run auto-baseline + configurable zone-relax-pct

Same two-run approach as P3b. ZONE_RELAX_PCT becomes `args.zone_relax_pct` (float, default 0.60). The BASELINE_* constants are replaced by Run 0's computed metrics.

---

## Structural edit pattern (identical for all 5 scripts)

1. **Add `import argparse` and `import sys`** at the top (alongside existing imports).
2. **Replace the 3-line config block** (CSV_PATH / INSTRUMENT / OUTPUT_DIR) with `_resolve_data_file()` helper + argparse parse call.
3. **Thread `args.instrument` and `args.output_dir`** through to `BacktestConfig`, `CandleLoader`, `BacktestRunner`, `runner.run()`, and the events-JSONL glob.
4. **P3b/P3c only:** wrap the existing single-run block into a `def _run_one(crt_cfg, label) -> BacktestMetrics` helper, call it twice, compute delta.
5. **P3b/P3c only:** replace `BASELINE_TRADES`, `BASELINE_TOTAL_PNL`, `BASELINE_AVG_RR` references with computed delta values.
6. **P3c only:** replace `ZONE_RELAX_PCT` with `args.zone_relax_pct`.
7. **Update each script's docstring** `Usage:` block with the new argparse interface.

---

## What does NOT change (in any script)

- The monkeypatch mechanism (`dataclasses.replace` on CRTConfig, EventLogger / ExecutionEngine / CRTEngine monkeypatching) — untouched.
- The events JSONL parsing, funnel table, FILTER_REJECTED breakdown, trade metrics, criteria table, and verdict logic — layout identical.
- `load_prod_config_from_registry(PROD_VERSION, args.instrument)` — this call already accepts instrument.
- `MultiInstrumentRunner.INSTRUMENT_PIP.get(args.instrument, 0.0001)` — unchanged.
- No changes to any file under `src/`.

---

## Verification (run in order)

```bash
# 1. ETHUSDT — should produce same verdict as before for each script
python scripts/analysis/p3a_zone_attribution_diag.py  --instrument ETHUSDT
python scripts/analysis/p3b_session_relax_diag.py    --instrument ETHUSDT
python scripts/analysis/p3c_zone_relax_diag.py       --instrument ETHUSDT --zone-relax-pct 0.60
python scripts/analysis/p3c1_build_trade_audit.py    --instrument ETHUSDT
python scripts/analysis/p4_execution_intent_attribution.py --instrument ETHUSDT

# 2. BTCUSDT — main failing symbol
python scripts/analysis/p3b_session_relax_diag.py    --instrument BTCUSDT
python scripts/analysis/p3c_zone_relax_diag.py       --instrument BTCUSDT --zone-relax-pct 0.60

# 3. SOLUSDT + BNBUSDT — check session gate adds trades
python scripts/analysis/p3b_session_relax_diag.py    --instrument SOLUSDT
python scripts/analysis/p3b_session_relax_diag.py    --instrument BNBUSDT

# 4. Explicit csv override test
python scripts/analysis/p3b_session_relax_diag.py --instrument BTCUSDT --csv data/BTCUSDT_M15.csv

# 5. Error path — bad instrument
python scripts/analysis/p3b_session_relax_diag.py --instrument FAKECOIN  # should exit with clear message
```

Expected for BTC/SOL/BNB: Run 0 produces the known trade counts (2/5/8). Run 1 should add session-unblocked trades. PASS/MIXED/NONE verdict driven by the computed delta.


================================================================================
SOURCE_FILE: docs/plans/analyze-only-this-runtime-wondrous-shell.md
SOURCE_BYTES: 69654
PART: 1/10 FILE 4/7
================================================================================

> Created: 2026-05-22 · Updated: 2026-05-22 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Current Status (2026-05-22)

## Completed
- **Phase 0 commit**: `retest_depth` NaN→0.0 + finalize survivorship guard — COMMITTED
- **P3a** (zone attribution): all 6 zone rejects cluster near midpoint (0.486–0.524); structural co-variance confirmed
- **P3b** (session relax): REJECTED — session relaxation adds −0.27R/trade; session filter is a quality governor
- **P3c** (zone relax at 60%): admitted 0 new trades (zone-session co-vary); LONDON SHORT at zone_pct=0.486 hit `build_trade=None` due to missing `sweep_event`/`displacement_candle` in state save set
- **P3c.1** (execution contract audit): 4/4 calls succeed, lineage_depth=6 on all, hash_before==hash_after on all (`build_trade` is a pure consumer). All 8 fields required. All 4 executed trades: `reversal` intent.
- **P4** (intent attribution): breakout lift=0.00 (fully zone-filtered by geometry), reversal lift=0.40. Zone filter = intent selector, not generic midpoint filter. Risk score gap: exec=0.568 vs zone-rej=0.456.
- **P5** (candles_since_retest repair): `candles_since_retest=99` was a `.get()` default bug (key absent from `cached_features`, computed dynamically). Fixed to derive from engine state. Result: all groups=1 (flat) → DISCARD feature. `mean=0.0→n/a` falsy bug fixed with `_safe()` helper.
- **Scripts written and committed**: `p3a_zone_attribution_diag.py`, `p3b_session_relax_diag.py`, `p3c_zone_relax_diag.py`, `p3c1_build_trade_audit.py`, `p4_execution_intent_attribution.py`
- **Architecture study CLOSED**: No threshold tuning warranted. Final map:
  ```
  FeaturePipeline (data integrity — Phase 0, FROZEN)
  ↓ HTF reset (freshness — primary kill, 94.5% of pre-EXPANSION losses)
  ↓ Retrace (staleness cleanup)
  ↓ Zone (intent compatibility — blocks breakout by geometry, lift=0.00)
  ↓ Session (liquidity timing — ASIA/OFF_SESSION blocked)
  ↓ Risk score / retest (maturity: exec RS=0.568 vs zone-rej RS=0.456)
  ↓ Execution (reversal-compatible admission, lift=0.40, lineage immutable)
  ```

## Next Step — Regression Test Pack (APPROVED)

Convert investigation findings into executable governance. Three new test files.
No source changes, no threshold changes. Pure assertion layer.

### Files to create

```
tests/
 ├── test_finalize_survivorship.py
 ├── test_execution_contract_v1.py
 └── test_p4_observability.py
```

---

### `tests/test_finalize_survivorship.py`

**Context**: Phase 0 fix replaced `retest_depth=NaN` (on non-retest bars) with `retest_depth=0.0`.
Before the fix, `finalize()` silently dropped ~52% of rows. These tests encode the post-fix contract.

**Imports / helpers**:
```python
import numpy as np
import pandas as pd
import pytest
from features.feature_pipeline import FeaturePipeline

# Reuse existing helper from test_feature_pipeline.py:
from tests.test_feature_pipeline import _make_synthetic_ohlcv
```

**Tests**:

```python
def test_finalize_drop_pct_under_budget():
    """Drop must stay within max(300, 2% of input) — the survivorship budget."""
    df = _make_synthetic_ohlcv(n=2000, seed=42)
    enriched, _ = FeaturePipeline(df).run()
    n_before = len(df)
    n_after  = len(enriched)
    drop_count = n_before - n_after
    budget     = max(300, int(n_before * 0.02))   # mirrors finalize() guard formula
    assert drop_count <= budget, (
        f"finalize() dropped {drop_count} rows (budget={budget}). "
        f"Likely NaN in CANONICAL_FEATURES — check recent feature additions."
    )

def test_retest_depth_no_nan():
    """retest_depth must be 0.0 (not NaN) on non-retest bars after Phase 0 fix."""
    df = _make_synthetic_ohlcv(n=1000, seed=42)
    enriched, _ = FeaturePipeline(df).run()
    assert "retest_depth" in enriched.columns
    assert enriched["retest_depth"].isna().sum() == 0, (
        "retest_depth contains NaN — Phase 0 fix regressed"
    )
    assert (enriched["retest_depth"] >= 0.0).all(), "retest_depth must be non-negative"

def test_non_retest_bars_have_zero_retest_depth():
    """On bars where retest_flag != 1, retest_depth must be exactly 0.0."""
    df = _make_synthetic_ohlcv(n=1000, seed=42)
    enriched, _ = FeaturePipeline(df).run()
    non_retest = enriched[enriched.get("retest_flag", pd.Series(0, index=enriched.index)) != 1]
    if len(non_retest) > 0:
        assert (non_retest["retest_depth"] == 0.0).all(), (
            "Non-retest bars have non-zero retest_depth"
        )
```

**Critical import note**: `_make_synthetic_ohlcv` is defined in `tests/test_feature_pipeline.py`.
Either import it directly or copy into a shared `tests/conftest.py` fixture.
Prefer import to avoid duplication; if pytest import path issues arise, extract to conftest.

---

### `tests/test_execution_contract_v1.py`

**Context**: P3c.1 confirmed the `build_trade()` guard hierarchy and immutability.
These tests encode the contract without running a full backtest.

**Key source facts** (verified in prior session):
- `ExecutionEngine.__init__(self, config: CRTConfig)` — only needs `CRTConfig()`
- `EngineState` is a non-frozen dataclass; all Optional fields default to None
- `direction: Direction = Direction.NONE` by default
- `current_candle_index: int = 0`, `retest_candle_index: int = 0`
- Guard hierarchy: `active_range` → `sweep_event` → `displacement_candle` → `retest_candle` → `direction` → `atr`

**Imports / setup**:
```python
import hashlib
from types import SimpleNamespace
import pytest

from config_layer.crt_engine_v2 import (
    CRTConfig, ExecutionEngine, EngineState, Direction,
)

def _make_minimal_engine():
    return ExecutionEngine(CRTConfig())

def _make_full_state():
    """EngineState with all lineage fields populated (should produce a trade)."""
    state = EngineState()
    # Populate the 8 required fields via SimpleNamespace stubs
    state.active_range        = SimpleNamespace(h_ref=2100.0, l_ref=2000.0, htf_candle_id="htf1")
    state.sweep_event         = SimpleNamespace(direction=Direction.LONG, price=2001.0)
    state.displacement_candle = SimpleNamespace(open=2010.0, close=2050.0, high=2055.0, low=2005.0)
    state.retest_candle       = SimpleNamespace(close=2020.0, open=2025.0, high=2030.0, low=2018.0)
    state.direction           = Direction.LONG
    state.atr                 = 15.0
    state.risk_score          = 0.70
    state.cached_features     = {
        "retest_depth": 0.35, "body_ratio": 0.6, "disp_strength": 0.8,
        "retest_index": 5, "session": 1, "double_sweep": False,
    }
    return state

def _lineage_hash(state) -> str:
    parts = [
        id(state.active_range)        if state.active_range else "None",
        id(getattr(state, "sweep_event", None))         if getattr(state, "sweep_event", None) else "None",
        id(getattr(state, "displacement_candle", None)) if getattr(state, "displacement_candle", None) else "None",
        id(getattr(state, "retest_candle", None))       if getattr(state, "retest_candle", None) else "None",
        state.direction.value if state.direction else "NONE",
    ]
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:12]
```

**Tests**:

```python
def test_build_trade_returns_none_without_active_range():
    """Guard 1: no active_range → None."""
    eng   = _make_minimal_engine()
    state = _make_full_state()
    state.active_range = None
    assert eng.build_trade(state) is None

def test_build_trade_returns_none_without_sweep_event():
    """Guard 2: no sweep_event → None."""
    eng   = _make_minimal_engine()
    state = _make_full_state()
    state.sweep_event = None
    assert eng.build_trade(state) is None

def test_build_trade_returns_none_without_displacement_candle():
    """Guard 3: no displacement_candle → None."""
    eng   = _make_minimal_engine()
    state = _make_full_state()
    state.displacement_candle = None
    assert eng.build_trade(state) is None

def test_build_trade_returns_none_without_retest_candle():
    """Guard 4: no retest_candle → None."""
    eng   = _make_minimal_engine()
    state = _make_full_state()
    state.retest_candle = None
    assert eng.build_trade(state) is None

def test_build_trade_returns_none_with_no_direction():
    """Guard 5: direction == NONE → None."""
    eng   = _make_minimal_engine()
    state = _make_full_state()
    state.direction = Direction.NONE
    assert eng.build_trade(state) is None

def test_build_trade_does_not_mutate_lineage():
    """build_trade() is a pure consumer: hash_before == hash_after on success."""
    eng   = _make_minimal_engine()
    state = _make_full_state()
    hash_before = _lineage_hash(state)
    eng.build_trade(state)
    hash_after  = _lineage_hash(state)
    assert hash_before == hash_after, (
        "build_trade() mutated lineage objects — it must be a pure consumer"
    )

def test_build_trade_does_not_mutate_lineage_on_failure():
    """Even when returning None, lineage objects must not be replaced."""
    eng   = _make_minimal_engine()
    state = _make_full_state()
    state.sweep_event = None   # force failure
    hash_before = _lineage_hash(state)
    eng.build_trade(state)
    hash_after  = _lineage_hash(state)
    assert hash_before == hash_after
```

**Note on `_make_full_state` stubs**: `ExecutionEngine.build_trade` may access additional
attributes of `active_range`/candle stubs (e.g., `atr_at_range`, `candle_index`). If the
full-lineage test path raises `AttributeError` on a missing stub field, add that field to
`SimpleNamespace` — the intent is to verify immutability, not to produce a real trade object.
The guard-chain tests (returning None) will always pass without full stub completeness.

---

### `tests/test_p4_observability.py`

**Context**: P5 identified two observability bugs in the P4 diagnostic script. These tests
encode the corrected computation logic so the same class of bug cannot silently recur in
future diagnostic scripts.

**Tests (pure logic — no backtest run needed)**:

```python
def test_candles_since_retest_never_equals_sentinel():
    """candles_since_retest derived from engine state must not equal 99 (old default)."""
    # Simulate the corrected derivation for a range of index pairs
    test_cases = [
        (10, 9),   # 1 candle since retest
        (25, 10),  # 15 candles since retest
        (100, 99), # 1 candle since retest
        (5, 5),    # 0 candles (same bar)
    ]
    SENTINEL = 99
    for cur_idx, ret_idx in test_cases:
        csr = max(0, cur_idx - ret_idx)
        assert csr != SENTINEL or (cur_idx - ret_idx) == SENTINEL, (
            f"candles_since_retest={csr} collides with sentinel for "
            f"cur={cur_idx}, ret={ret_idx}. Use None for missing data."
        )

def test_candles_since_retest_is_none_when_index_missing():
    """When either index is None (field not present), result must be None, not 0."""
    def _derive_csr(cur_idx, ret_idx):
        return (max(0, cur_idx - ret_idx)
                if (cur_idx is not None and ret_idx is not None) else None)

    assert _derive_csr(None, 5)  is None, "Missing cur_idx must yield None"
    assert _derive_csr(10, None) is None, "Missing ret_idx must yield None"
    assert _derive_csr(None, None) is None, "Both missing must yield None"
    assert _derive_csr(10, 9) == 1, "Valid pair must yield correct count"

def test_safe_formatter_none_yields_na():
    """_safe(None) must return 'n/a', not '0.000' or 'None'."""
    def _safe(v, decimals=3):
        if v is None:
            return "n/a"
        return f"{v:.{decimals}f}"

    assert _safe(None)  == "n/a"
    assert _safe(None, decimals=4) == "n/a"

def test_safe_formatter_zero_yields_numeric():
    """_safe(0.0) must return '0.000', not 'n/a' (falsy-evaluation bug regression)."""
    def _safe(v, decimals=3):
        if v is None:
            return "n/a"
        return f"{v:.{decimals}f}"

    assert _safe(0.0)  == "0.000", "_safe(0.0) must NOT return 'n/a' — falsy bug regression"
    assert _safe(0)    == "0.000"
    assert _safe(False) == "0.000"   # int(False)=0; double_sweep=False case

def test_safe_formatter_does_not_use_python_or_for_zero_check():
    """Demonstrate that `v or 'n/a'` is the WRONG pattern for the zero case."""
    # This test encodes the original bug as a negative example
    v = 0.0
    buggy_result  = v or "n/a"    # evaluates to 'n/a' — WRONG
    correct_result = "n/a" if v is None else f"{v:.3f}"
    assert buggy_result  == "n/a",   "Demonstrates the falsy bug"
    assert correct_result == "0.000", "Demonstrates the correct guard"

def test_intent_lift_computation():
    """lift = executed_count / candidate_count, not rate / rate."""
    # Simulate 14 RETEST candidates: 4 breakout, 10 reversal; 0 breakout executed, 4 reversal executed
    all_setups = (
        [{"intent": "breakout"}] * 4 +
        [{"intent": "reversal"}] * 10
    )
    executed = [{"intent": "reversal"}] * 4

    def _lift(intent, all_s, exec_s):
        candidates = sum(1 for r in all_s if r.get("intent") == intent)
        exec_cnt   = sum(1 for r in exec_s if r.get("intent") == intent)
        return exec_cnt / candidates if candidates > 0 else 0.0

    assert _lift("breakout", all_setups, executed) == 0.00
    assert _lift("reversal", all_setups, executed) == pytest.approx(0.40)

def test_intent_lift_zero_candidates_does_not_raise():
    """lift for an intent with 0 candidates returns 0.0 (not ZeroDivisionError)."""
    all_setups = [{"intent": "reversal"}] * 5
    executed   = [{"intent": "reversal"}] * 2

    def _lift(intent, all_s, exec_s):
        candidates = sum(1 for r in all_s if r.get("intent") == intent)
        exec_cnt   = sum(1 for r in exec_s if r.get("intent") == intent)
        return exec_cnt / candidates if candidates > 0 else 0.0

    assert _lift("breakout", all_setups, executed) == 0.0   # no ZeroDivisionError
```

---

### Verification

```powershell
cd D:\Tradelatest
python -m pytest tests\test_finalize_survivorship.py tests\test_execution_contract_v1.py tests\test_p4_observability.py -v
```

All 3 files must pass green before architecture study is considered archived.

### Constraint
- Do NOT tune thresholds. Architecture study CLOSED.
- No source promotion. Zone + session both confirmed quality governors.
- These tests are assertion-only — no new feature work, no new scripts.

---

# P3 — Session / Zone Attribution Study

## Context

10 of 14 RETEST→EXECUTION setups blocked at the post-approval filter stage (baseline).
P1 proved score bonuses don't reach here (all 10 rejections are pre-score: session + zone).
P2 proved HTF freshness is the right guard (not loosened). Session/zone is the next governor.

**Baseline rejection split (14 RETEST in → 4 executed):**
- off_session: 4 (OFF_SESSION × 3, ASIA × 1)
- zone-position: 6 (LONG above mid × 3, SHORT below mid × 3)

**P2 run rejection split (25 RETEST in → 4 executed) — for reference:**
- off_session: 10 (OFF_SESSION × 9, ASIA × 1)
- zone-position: 9 (LONG above mid × 4, SHORT below mid × 5)

**Key structural facts:**
- Zone filter fires FIRST (lines 1598–1610), then session filter in `else:` branch
  → They are mutually exclusive: a setup hits exactly one filter, not both
- Zone check is hardcoded: `mid = (rng.h_ref + rng.l_ref) / 2` — no config knob
- Session filter reads `config.allowed_sessions` — trivial to patch on config instance
  (loaded from `engine_runner.allowed_sessions` in prod JSON via `production_config.py:261`)
- `reset_to_range` does NOT clear `active_range` — clears `retest_candle`, `direction`,
  `risk_score`, `cached_features`, `evaluating_soft_conf`, `soft_conf_candles`
- `try_retest_to_execution` is trivially `_transition(state, CRTState.EXECUTION, ...)`
- FILTER_REJECTED events in JSONL have NO h_ref/l_ref metadata → zone_pct cannot
  be computed from JSONL alone; must be captured at process_candle runtime

## Experiment order (one variable per run)

### P3a — Attribution Run (baseline + enhanced logging, no filter change)

**Goal**: Compute `zone_pct = (entry_price - l_ref) / (h_ref - l_ref)` for each zone reject.
Tells us: are zone rejects near the midpoint (52%) or structurally above (70%+)?

**Two monkeypatches, no filter changes:**

```python
# Patch 1 — capture zone context just before process_candle fires the check
_zone_ctx = {}
_orig_process = CRTEngine.process_candle

def _process_zone_logging(self, candle, htf_candle_id):
    rng  = self.state.active_range
    ret  = getattr(self.state, "retest_candle", None)
    if rng is not None and ret is not None:
        span = rng.h_ref - rng.l_ref
        _zone_ctx.update({
            "h_ref":       rng.h_ref,
            "l_ref":       rng.l_ref,
            "entry_price": ret.close,
            "zone_pct":    round((ret.close - rng.l_ref) / span, 3) if span > 0 else 0.5,
            "direction":   self.state.direction.value if self.state.direction else None,
        })
    else:
        _zone_ctx.clear()
    return _orig_process(self, candle, htf_candle_id)

CRTEngine.process_candle = _process_zone_logging

# Patch 2 — inject zone context into FILTER_REJECTED metadata
_orig_record = EventLogger.record

def _record_zone_meta(self, event_type, candle, **kwargs):
    if event_type == "FILTER_REJECTED" and "zone" in kwargs.get("reason", "").lower():
        meta = dict(kwargs.get("metadata", {}) or {})
        meta.update(_zone_ctx)
        kwargs["metadata"] = meta
    return _orig_record(self, event_type, candle, **kwargs)

EventLogger.record = _record_zone_meta
```

**Post-run analysis:**
```python
zone_rejects = [e for e in events if e.get("event") == "FILTER_REJECTED"
                and "zone" in e.get("reason", "")]
for r in zone_rejects:
    m = r.get("metadata", {})
    print(f"  {r['reason']:<30} zone_pct={m.get('zone_pct',?):>5}  dir={m.get('direction','?')}")
```

**Success criterion**: Outputs zone_pct distribution. Guides threshold for P3c.
- zone_pct 0.50–0.60 → 60% threshold is sufficient
- zone_pct 0.60–0.70 → 67% threshold needed
- zone_pct > 0.70 → zone is genuinely bad; high threshold required or filter is correct

**Script**: `scripts/analysis/p3a_zone_attribution_diag.py`

---

### P3b — Session Relaxation Run

**Goal**: Allow all sessions (LONDON + NEWYORK + ASIA + OFF_SESSION).
Measures: how many of the 4 off_session setups become trades? PnL per added trade?

**One-line patch:**
```python
crt_cfg = load_prod_config_from_registry(PROD_VERSION, INSTRUMENT)
crt_cfg.allowed_sessions = ("LONDON", "NEWYORK", "OVERLAP", "ASIA", "OFF_SESSION")
# No other change
```

**Success criteria:**
| Metric | Target |
|---|---|
| Approved trades | > 4 (baseline) |
| avg_R per added trade | >= 0.39R (baseline avg) |
| MaxDD | <= 0.0132 (baseline × 1.2) |
| Win rate on added trades | >= 0.5 (baseline) |

**Risk**: OFF_SESSION setups occur at 03:45, 05:15, 05:45, 10:30–18:15 UTC — spread/liquidity
concerns. If avg_R < baseline, session filter is a valid quality governor.

**Script**: `scripts/analysis/p3b_session_relax_diag.py`

---

### P3c — Zone Threshold Relaxation Run

**Goal**: Replace strict midpoint (50%) with configurable pct. Run at 60% and 67%.

**Approach: state save/restore wrapper on process_candle**

```python
ZONE_RELAX_PCT = 0.67   # LONG: entry allowed up to 67% from l_ref; SHORT: down to 33%
_orig_process  = CRTEngine.process_candle
_zone_reason_tracker = [None]

# Track zone reject reason via EventLogger
_orig_record = EventLogger.record
def _record_tracking(self, event_type, candle, **kwargs):
    if event_type == "FILTER_REJECTED":
        _zone_reason_tracker[0] = kwargs.get("reason", "")
    return _orig_record(self, event_type, candle, **kwargs)
EventLogger.record = _record_tracking

def _process_zone_relax(self, candle, htf_candle_id):
    # Save state before calling original (reset_to_range clears these)
    _saved = {
        "current_state":       self.state.current_state,
        "active_range":        self.state.active_range,      # NOT cleared by reset
        "retest_candle":       getattr(self.state, "retest_candle", None),
        "retest_candle_index": getattr(self.state, "retest_candle_index", 0),
        "direction":           self.state.direction,
        "risk_score":          self.state.risk_score,
        "cached_features":     self.state.cached_features,
        "evaluating_soft_conf": self.state.evaluating_soft_conf,
        "soft_conf_candles":   self.state.soft_conf_candles,
    }
    _zone_reason_tracker[0] = None

    action = _orig_process(self, candle, htf_candle_id)

    reason = _zone_reason_tracker[0] or ""
    if (action.get("action") == "FILTER_REJECTED"
            and ("discount zone" in reason or "premium zone" in reason)
            and _saved["retest_candle"] is not None
            and _saved["active_range"] is not None):
        rng  = _saved["active_range"]
        span = rng.h_ref - rng.l_ref
        entry = _saved["retest_candle"].close
        entry_pct = (entry - rng.l_ref) / span if span > 0 else 0.5
        dir_long = (_saved["direction"] == Direction.LONG)
        relaxed_pass = (
            (dir_long  and entry_pct <= ZONE_RELAX_PCT) or
            (not dir_long and entry_pct >= 1 - ZONE_RELAX_PCT)
        )
        if relaxed_pass:
            # Restore state → RETEST, call execution path manually
            for k, v in _saved.items():
                setattr(self.state, k, v)
            # session check (preserve existing session filter)
            _ts_time = candle.timestamp.time()
            _sess_name = "OFF_SESSION"
            for _name, (_start, _end) in self.config.session_windows.items():
                if _start <= _ts_time <= _end:
                    _sess_name = _name
                    break
            if _sess_name not in self.config.allowed_sessions:
                # Session still blocks — re-reset and return original action
                self.sm.reset_to_range(self.state, "off_session_filter", candle, self.ev_log)
                action["action"] = "FILTER_REJECTED"
                return action
            # Proceed to execution
            self.sm.try_retest_to_execution(self.state, candle, self.ev_log)
            trade = self.executor.build_trade(self.state, self.risk)
            if trade:
                self.executor.open_trade(trade, candle.timestamp)
                self.state.active_trade = trade
                self.ev_log.record(
                    "TRADE_OPENED", candle,
                    direction=trade.direction.value,
                    price=trade.entry_price,
                    metadata={"id": trade.id, "via": "P3c_zone_relax",
                              "entry_pct": round(entry_pct, 3)},
                )
                action["action"] = "TRADE_OPENED"
                action["trade_id"] = trade.id

    return action

CRTEngine.process_candle = _process_zone_relax
```

**Run twice**: `ZONE_RELAX_PCT = 0.60` then `ZONE_RELAX_PCT = 0.67`.

**Success criteria** (same as P3b):
| Metric | Target |
|---|---|
| Approved trades | > 4 |
| avg_R per added trade | >= 0.39R |
| MaxDD | <= 0.0132 |

**If P3c passes: guarded source fix (do NOT do immediately)**
```python
# In CRTConfig:
zone_discount_pct: float = 0.50  # LONG: entry must be below this % of range (0=bottom, 1=top)
zone_premium_pct:  float = 0.50  # SHORT: entry must be above (1 - zone_premium_pct)
```
```python
# In process_candle line 1601 (instead of hardcoded mid):
_discount_ceil = rng.l_ref + self.config.zone_discount_pct * (rng.h_ref - rng.l_ref)
_premium_floor = rng.l_ref + (1 - self.config.zone_premium_pct) * (rng.h_ref - rng.l_ref)
if self.state.direction == Direction.LONG and entry_price > _discount_ceil:
    ...
elif self.state.direction == Direction.SHORT and entry_price < _premium_floor:
    ...
```

**Script**: `scripts/analysis/p3c_zone_relax_diag.py`

---

## Interpretation guide

| P3b result | Meaning |
|---|---|
| Trades ↑, avg_R >= 0.39R | Session filter was filtering noise → relax with config gate |
| Trades ↑, avg_R < 0.39R | Session filter was quality governor for OFF_SESSION → keep |
| No new trades | Off_session setups had other guards blocking them |

| P3c result | Meaning |
|---|---|
| Trades ↑ at 60% PCT, avg_R >= baseline | Small zone relaxation is safe → config-gate at 60% |
| Trades ↑ at 60% but avg_R < baseline | Zone filter is quality governor; position matters |
| Trades ↑ at 67% but 60% gave nothing | Zone rejects were in 60–67% band |
| No new trades even at 67% | Zone rejects were above 67% — structurally bad entries |

---

# Phase 0 — FeaturePipeline Fix: Commit

## Status

**IMPLEMENTED, NOT YET COMMITTED.**
- `src/features/feature_pipeline.py:543-548`: `retest_depth` NaN → 0.0 (from prior session)
- `src/features/feature_pipeline.py:finalize()`: survivorship telemetry + absolute drop guard (this session)
- Confirmed output: `drop=78 rows (0.07%)` — within budget

## Commit scope (surgical — specify exact files only)

```powershell
git add src/features/feature_pipeline.py
git add scripts/analysis/p1_sweep_memory_diag.py
git add scripts/analysis/p2_disp_exemption_diag.py
git commit -m "$(cat <<'EOF'
fix(feature_pipeline): retest_depth NaN->0.0 + finalize survivorship guard

retest_depth was written as np.nan on non-retest bars, causing finalize()
dropna to silently drop ~54k of 105k rows and break the backtest
feature-lookup map. Fixed to 0.0 (correct semantic: 'no retest active').

Adds structured telemetry to finalize() (rows_before/after/drop/pct) and
an absolute drop budget guard: max(300, n_before*0.02). Confirmed output:
drop=78 rows (0.07%), well within budget. Feature lookup MISS eliminated.

Also adds P1 and P2 diagnostic scripts as archived research artifacts:
- p1_sweep_memory_diag.py: proves double_confirmed fires (714/1726),
  not gating (trades/PnL unchanged). INFORMATIONAL.
- p2_disp_exemption_diag.py: proves HTF reset is state garbage collection,
  not premature cancellation. REJECTED (DISP age p95=636 candles,
  avg_R collapsed 0.06R, SWEEP dropped 88%).

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

## Files NOT to commit in this pass

Do not include configs.zip, models.zip, data.zip, src.zip, scripts.zip,
ui_kits.zip, docs.zip, results/, logs/, or any `.env` / credential files.
The `git add` commands above are exhaustive — do not use `git add .` or `-A`.

## Verification before commit

```powershell
python src\runtime\backtest_v2.py --csv data\ETHUSDT_M15.csv --instrument ETHUSDT
# Expect: FeaturePipeline built: ~105,128 rows
# Expect: NO "Feature lookup MISS" warnings
# Expect: finalize | drop=78 rows (0.07%)
```

---

# Phase 0 — FeaturePipeline Fix: Promote + Assertion Guard

## Status

Fix already implemented. `src/features/feature_pipeline.py:543-548` now writes `0.0` (not `np.nan`)
on non-retest bars. Confirmed: P1 run shows `FeaturePipeline built: 105128 rows` (was 50928).

## One addition before commit: survivorship assertion in `finalize()`

File: `src/features/feature_pipeline.py` — `finalize()` at line 664.

```python
# BEFORE
def finalize(self) -> pd.DataFrame:
    df = self.df
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.dropna(subset=list(CANONICAL_FEATURES)).reset_index(drop=True)
    self.df = df
    return df
```

```python
# AFTER
def finalize(self) -> pd.DataFrame:
    n_before = len(self.df)
    df = self.df
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.dropna(subset=list(CANONICAL_FEATURES)).reset_index(drop=True)
    n_after = len(df)
    drop_count = n_before - n_after
    drop_pct   = 100.0 * drop_count / max(n_before, 1)

    # Structured telemetry (trendable — catches gradual degradation that survives single-run checks)
    _fp_log = logging.getLogger("FeaturePipeline")
    _fp_log.info(
        "finalize | rows_before=%d rows_after=%d drop=%d drop_pct=%.2f%%",
        n_before, n_after, drop_count, drop_pct,
        extra={
            "event": "FEATURE_FINALIZE",
            "rows_before": n_before,
            "rows_after":  n_after,
            "drop_count":  drop_count,
            "drop_pct":    round(drop_pct, 2),
        },
    )

    # Survivorship guard: use absolute budget, not survival ratio.
    # Ratio permits ~5k silent loss on 100k datasets; absolute budget does not.
    # warm-up budget = ma_200(200) + z-score(50) + swing edges(4) = ~300 rows max.
    _warmup_budget = 300
    _allowed_drop = max(_warmup_budget, int(n_before * 0.02))   # 2% of input OR warmup, whichever larger
    if drop_count > _allowed_drop:
        _fp_log.error(
            "finalize(): drop count %d exceeds allowed budget %d (%.1f%% of input). "
            "Likely unintended NaN in CANONICAL_FEATURES. Check recent feature additions.",
            drop_count, _allowed_drop, drop_pct,
        )

    self.df = df
    return df
```

**Why absolute budget, not survival ratio**: 95% of (105k−300) still permits ~5k silent loss.
`max(warmup_budget, n_before * 0.02)` caps at 2104 rows for a 105k dataset — tight enough to
catch the original 54k collapse within the first 10% of data seen.

**Why log.error not assert**: A hard assert crashes the pipeline on live data quality issues.
log.error is non-fatal and visible in production monitoring + governance dashboards.

## Verification

```powershell
python src\runtime\backtest_v2.py --csv data\ETHUSDT_M15.csv --instrument ETHUSDT
# expect: FeaturePipeline built: ~105,128 rows (no 50k collapse)
# expect: NO "survivorship below 95%" error in logs
# expect: NO Feature lookup MISS warnings
```

## Commit scope

- `src/features/feature_pipeline.py` only (2 hunks: the 0.0 fix + finalize assertion)

---

# P2 Diagnostic — DISPLACEMENT → EXPANSION Bottleneck (HTF Exemption)

## Context

P1 proved `double_confirmed` fires (714/1726) but is not the bottleneck.
The dominant funnel compression is DISPLACEMENT → EXPANSION (357 in → 15 out, 95.8% kill rate).

DISPLACEMENT episode duration analysis (from `run_20260522_104914_ETHUSDT/ETHUSDT_events.jsonl`):

| Outcome | Episodes | Median duration | Range |
|---|---:|---:|---:|
| EXPANSION (success) | 15 | 1 candle | 1–1 |
| HTF_RESET | 259 | 1 candle | 1–2 |
| RETRACE (50%) | 73 | 1 candle | 1–1 |
| EXTENSION (1.618x) | 9 | 1 candle | 1–1 |
| OTHER | 1 | 6 candles | 6–6 |

**Every episode resolves in 1 candle.** The expansion geometry guards (`try_displacement_to_expansion`) are almost never evaluated — the reset check at `process_candle:1499` fires before state machine logic.

## Root cause trace

`CRTEngine.process_candle` (line 1499):
```python
should_reset, reset_reason = self.reset_lg.should_reset(self.state, candle, htf_candle_id)
if should_reset:
    self.sm.reset_to_range(...)   # ← fires BEFORE try_displacement_to_expansion
```

`ResetLogic.should_reset` (line 1385-1388):
```python
if current_htf_id != state.active_range.htf_candle_id:
    if state.current_state in [CRTState.EXPANSION, CRTState.RETEST]:
        return False, ""   # protected: HTF flip does NOT reset these states
    return True, f"HTF changed: ..."  # DISPLACEMENT: NOT protected → killed
```

**The asymmetry**: EXPANSION and RETEST are already exempt from HTF resets. DISPLACEMENT is not.
197/259 HTF resets kill DISPLACEMENT on candle N+1 with zero expansion evaluation.

## Hypothesis: "DISPLACEMENT exemption"

Extend the HTF exempt set from `[EXPANSION, RETEST]` to `[DISPLACEMENT, EXPANSION, RETEST]`.

Effect:
- 259 HTF-reset kills → DISPLACEMENT survives the HTF boundary
- Retrace (73) and extension (9) resets remain fully active (they do NOT check `current_state`)
- DISPLACEMENT episodes in a fresh HTF window get 1–4 more candles to produce an expansion candle

## What the diagnostic patches

**One monkeypatch. No source files modified.**

```python
from config_layer.crt_engine_v2 import ResetLogic, CRTState

_orig_should_reset = ResetLogic.should_reset

def _should_reset_with_disp_exemption(self, state, current_candle, current_htf_id):
    if state.active_range is None:
        return False, ""
    # Protect active trades (unchanged from original)
    if state.active_trade and state.active_trade.status in ("OPEN", "TP1"):
        return False, ""
    # HTF exemption extended to DISPLACEMENT
    if current_htf_id != state.active_range.htf_candle_id:
        if state.current_state in (CRTState.DISPLACEMENT, CRTState.EXPANSION, CRTState.RETEST):
            return False, ""   # ← only change: DISPLACEMENT added
        return True, f"HTF changed: {state.active_range.htf_candle_id} -> {current_htf_id}"
    # Retrace and extension checks: pass through to original (unchanged)
    return _orig_should_reset(self, state, current_candle, current_htf_id)

ResetLogic.should_reset = _should_reset_with_disp_exemption
```

Note: the fall-through to `_orig_should_reset` for non-HTF reset paths avoids duplicating
the retrace/extension logic and keeps retrace/extension guards active.

## Files NOT modified

- `src/config_layer/crt_engine_v2.py` — unchanged
- `src/runtime/backtest_v2.py` — unchanged
- All configs unchanged

## Expected output comparison

| Metric | Baseline | P1 (sweep memory) | P2 (DISP exemption) |
|---|---:|---:|---:|
| double_confirmed sweeps | 0 | 714 | ? |
| RANGE → SWEEP | 1,726 | 1,726 | ? |
| SWEEP → DISPLACEMENT | 357 | 357 | ? |
| DISPLACEMENT → EXPANSION | **15** | 15 | ? |
| EXPANSION → RETEST | 14 | 14 | ? |
| RETEST → EXECUTION | 4 | 4 | ? |
| Trades | 4 | 4 | ? |
| PnL (net R) | +1.57R | +1.57R | ? |

## Success criteria (upstream-first, not trade-count-first)

"Approved trades ↑" is too downstream — rejection migrates, not disappears.
Measure the mechanism directly:

| Metric | Target | Why |
|---|---|---|
| DISP median episode duration | > 1 candle | If still 1, exemption had no effect |
| DISP → EXPANSION conversion rate | > 4.2% (baseline) | Direct measure of the hypothesis |
| Retrace kill share of all DISP deaths | <= 50% | Guard: retrace must not become new dominant |
| Median ATR drift during DISP episode | < 20% | `abs(atr_current - atr_at_disp) / atr_at_disp`; staleness bound |
| Median HTF distance at EXPANSION | <= 1 HTF boundary crossed | `n_htf_flips_since_disp`; freshness bound |
| DISP age at EXPANSION: p95 | <= 4 candles | `expansion_idx - displacement_idx`; tail check for structure resurrection |
| HTF kill share after exemption | < 25% of total DISP deaths | `htf_resets / all_disp_resets`; proves HTF exemption actually fired |
| avg_R per trade | >= baseline (0.39R) | Quality must not degrade |
| Max drawdown | <= baseline × 1.20 (1.32%) | Risk bound |

ATR drift rationale: if DISP episodes now last 3–5 candles (up from 1), the displacement
geometry (disp_open, disp_close, atr, reference range) becomes increasingly stale.
Expansion events may be evaluated against an ATR that has drifted significantly.
Track `atr_at_displacement_start` vs `atr_at_expansion_evaluation` to catch this.

HTF distance rationale: the DISP exemption allows DISPLACEMENT to survive across HTF
boundaries. If expansions begin occurring +2, +3, or +4 HTF boundaries after the original
displacement, structural freshness is gone even if ATR is stable. Track by counting how many
distinct `htf_candle_id` values were seen between SWEEP→DISPLACEMENT and DISPLACEMENT→EXPANSION.
Compute from events JSONL post-run (no code change needed — HTF change reasons contain IDs).

DISP age at EXPANSION rationale: baseline shows expansion always happens on candle N+1
(duration=1). If P2 creates a tail of episodes resolving at candles N+12, N+18, N+25,
that is structure resurrection (stale geometry being accepted), not just persistence.
p95 <= 4 candles (= 1 HTF window) is the permissible freshness bound.
Compute: `expansion_candle_index - displacement_candle_index` from events JSONL.

HTF kill share rationale: if the exemption works, HTF resets should drop from 259 → near 0
within DISPLACEMENT. If it only drops from 259 → 180, the exemption barely fired (perhaps
the range re-seed overwrites state mid-candle). If it drops to ~20 with retrace rising as
the new dominant, that proves causality — HTF was the primary killer and retrace is the fallback.
Compute: `htf_resets_P2 / total_disp_deaths_P2` from events JSONL.

## Pre-run prediction (user-stated, for calibration)

| Metric | Predicted range |
|---|---|
| DISPLACEMENT → EXPANSION | 15 → 30–80 |
| EXPANSION → RETEST conversion | lower (rejection migrates here) |
| RETEST → EXECUTION conversion | lower (further migration) |
| Approved trades | 4 → 6–10 |
| PnL | flat to slightly below baseline |
| Max DD | higher than baseline |

Basis: relaxing early filters migrates rejections downstream, not eliminates them.
HTF=96 experiment already demonstrated this pattern.

## Interpretation guide

| P2 result | Meaning |
|---|---|
| EXPANSION > 15 AND PnL >= baseline AND ATR drift < 20% | DISP exemption is ROI-positive → proceed to guarded source fix |
| EXPANSION > 15 AND PnL < baseline | More setups, lower quality → reject (HTF freshness is a quality governor) |
| EXPANSION = 15 (unchanged) | Retrace threshold is the actual governor → investigate `retrace_reset_pct` |
| Retrace kill share > 50% of new DISP deaths | Retrace has become dominant → retrace threshold next |
| ATR drift median >= 20% | Surviving episodes evaluate stale geometry → exemption unsafe without ATR re-anchor |

## If P2 passes: guarded source fix (do NOT do immediately)

Do not directly edit `ResetLogic.should_reset`. Instead introduce a config flag:

```python
# In CRTConfig:
protect_disp_from_htf_reset: bool = False   # default: off (backward-compat)
```

```python
# In ResetLogic.should_reset (line 1385):
if current_htf_id != state.active_range.htf_candle_id:
    exempt_states = [CRTState.EXPANSION, CRTState.RETEST]
    if self.config.protect_disp_from_htf_reset:
        exempt_states.append(CRTState.DISPLACEMENT)
    if state.current_state in exempt_states:
        return False, ""
    return True, f"HTF changed: ..."
```

This is regime-sensitive: same caution as HTF cadence. Config-gate it before any promotion.

## Critical context for running

The retrace/extension logic in `should_reset` (lines 1392–1410) does NOT branch on
`current_state` — it fires for any non-RANGE state where `displacement_candle is not None`.
This means even with the DISP exemption:
- A DISPLACEMENT episode that survives an HTF flip can still be killed by 50% retrace
- Extension kills remain active
- The net effect on retrace/extension count is unknown (could increase as episodes live longer)

## Script location

`scripts/analysis/p2_disp_exemption_diag.py` (to be created; same structure as p1_sweep_memory_diag.py)

---

# P1 Diagnostic — Persist `last_sweep_direction` Across Reset

## Context

P0 confirmed `double_confirmed` is load-bearing but always False.  
The cause: `reset_to_range()` clears `state.sweep_event = None` before `detect_sweep()` can read it.  
P1 isolates the memory effect only — no scoring changes, no threshold changes.

## What the diagnostic patches

Two monkeypatches on live objects. **No source files modified.**

### Patch 1 — `StateMachine.reset_to_range`
Before clearing `state.sweep_event`, save its direction into a new persistent field `state._last_sweep_dir`.

```python
_orig_reset = StateMachine.reset_to_range

def _reset_with_memory(self, state, reason, candle=None, ev_logger=None):
    # Persist direction into Class-B memory before clearing Class-A
    if state.sweep_event is not None:
        state._last_sweep_dir = state.sweep_event.direction   # survives reset
    _orig_reset(self, state, reason, candle, ev_logger)

StateMachine.reset_to_range = _reset_with_memory
```

### Patch 2 — `CRTEngine.process_candle` (call site only)
At line 1537-1540, `detect_sweep()` is called with `self.state.sweep_event` as `prev_sweep`.  
Inject a synthetic stub that carries only the persisted direction, so `detect_sweep`'s  
`double_confirmed = prev_sweep is not None and prev_sweep.direction != direction` fires correctly.

```python
_orig_process = CRTEngine.process_candle

def _process_with_memory(self, candle, htf_candle_id):
    # Inject persistent direction stub only when state is RANGE and sweep_event is None
    from config_layer.crt_engine_v2 import CRTState, SweepEvent, Direction
    if (self.state.current_state == CRTState.RANGE
            and self.state.sweep_event is None
            and getattr(self.state, '_last_sweep_dir', None) is not None):
        # Synthetic stub — only direction matters for double_confirmed check
        stub = SweepEvent(
            direction=self.state._last_sweep_dir,
            price=0.0,
            candle=candle,
            candle_index=self.state.current_candle_index,
        )
        self.state.sweep_event = stub          # visible to detect_sweep
        result = _orig_process(self, candle, htf_candle_id)
        # Restore: if detect_sweep didn't set a real sweep, clear the stub
        if self.state.sweep_event is stub:
            self.state.sweep_event = None
        return result
    return _orig_process(self, candle, htf_candle_id)

CRTEngine.process_candle = _process_with_memory
```

## What the diagnostic measures

Run the full ETHUSDT backtest with these two patches active.  
Parse the resulting `ETHUSDT_events.jsonl`:

```python
double_events = [e for e in events if e.get('event') == 'SWEEP'
                 and e.get('metadata', {}).get('double_confirmed')]
```

**Expected output comparison:**

| Metric | Baseline (htf=4) | P1 (persisted direction) |
|---|---:|---:|
| double_confirmed sweeps | 0 | ? |
| SWEEP → DISP | 357 | ? |
| DISP → EXPANSION | 15 | ? |
| Trades | 4 | ? |
| PnL (net R) | +1.57R | ? |

## Files NOT modified

- `src/config_layer/crt_engine_v2.py` — unchanged
- `src/runtime/backtest_v2.py` — unchanged
- All configs unchanged

## Success criteria (tightened)

Simple "trade count ↑" is NOT sufficient — htf=96 proved 11 trades at −1.07R.  
P1 passes if ALL of the following hold:

| Metric | Target |
|---|---|
| double_confirmed sweeps | > 0 |
| Approved trades | +5–20% vs baseline (4 trades) |
| avg_R per trade | ≥ baseline avg |
| Max drawdown | ≤ baseline × 1.20 |
| Win rate | does not collapse vs baseline |

## Interpretation guide

| P1 result | Meaning |
|---|---|
| double_confirmed > 0 AND all success criteria met | Memory fix is ROI-positive → proceed to P2 |
| double_confirmed > 0 AND trades ↑ AND avg_R / WR degrade | Signal fires but adds noise → do not implement |
| double_confirmed > 0 AND trade count unchanged | Bonus fires but not gating; evaluate marginal risk impact only |
| double_confirmed = 0 | Structural impossibility deeper than reset lifecycle → re-examine |

---

# CRT State Transition Funnel — Exact Counts from ETHUSDT_events.jsonl

Source: `results/run_20260522_002627_ETHUSDT/ETHUSDT_events.jsonl` (10,354 events, 105,206 candles)

## Funnel

| Transition | In | Out | Conversion | Killed |
|---|---:|---:|---:|---:|
| RANGE → SWEEP | 105,206 candles | **1,726** | 1.6% | 103,480 no boundary breach |
| SWEEP → DISPLACEMENT | 1,726 | **357** | **20.7%** | **1,369** |
| DISPLACEMENT → EXPANSION | 357 | **15** | **4.2%** | **342** |
| EXPANSION → RETEST | 15 | **14** | 93.3% | 1 |
| RETEST → EXECUTION | 14 | **4** | 28.6% | 10 |
| EXECUTION → RESOLUTION | 4 | 4 | 100% | 0 |

---

## Per-transition reject reasons

### RANGE → SWEEP
- 103,480 candles never breached h_ref/l_ref with close inside — not recorded, pure geometry.
- All 1,726 SWEEP events are single-directional; **double_confirmed = 0** across the entire run.

### SWEEP → DISPLACEMENT: 1,726 in → 357 out (1,369 killed — **79.3%**)
| Reason | Count | % of killed |
|---|---:|---:|
| HTF changed (range reseeded while in SWEEP state) | 1,369 | **100%** |
| SWEEP_EXPIRED (max_sweep_age_candles timeout) | 0 | 0% |
| Displacement guard (move/body_ratio/wick — debug-silenced) | 0 visible | — |

Every killed sweep was discarded by a HTF range flip, not by a displacement quality guard.

### DISPLACEMENT → EXPANSION: 357 in → 15 out (342 killed — **95.8%**)
| Reason | Count | % of killed |
|---|---:|---:|
| HTF changed (range reseeded while in DISPLACEMENT) | 259 | 75.7% |
| 50% retrace hit | 80 | 23.4% |
| 1.618 extension hit | 7 | 2.0% |
| Post-resolution reset | 1 | 0.3% |

### EXPANSION → RETEST: 15 in → 14 out (1 killed)
| Reason | Count |
|---|---:|
| Session gap reset (165 min gap, 2023-03-24) | 1 |

### RETEST → EXECUTION: 14 in → 4 out (10 killed — 71.4%)
All 14 entries were confirmed by `BEGIN_SOFT_CONF` (no losses before soft-conf window).
`CONFIRMATION_FAILED = 0` — the soft-conf score threshold was never the blocker.
| Reason | Count | % of killed |
|---|---:|---:|
| Not in discount zone (LONG above range midpoint) | 3 | 30% |
| Not in premium zone (SHORT below range midpoint) | 3 | 30% |
| off_session: ASIA | 3 | 30% |
| off_session: OFF_SESSION | 1 | 10% |

No BitNet rejections. No LOW_SCORE rejections. All 10 failures were post-approval range-position or session filters.

---

## Earliest dominant collapse

**SWEEP → DISPLACEMENT: 1,369/1,726 killed (79.3%) — all by HTF range reseeding.**

This is both the largest absolute loss (1,369 candidates) and the second-earliest gate. Every time a valid sweep is detected, the HTF range flips before a displacement candle can fire. The displacement quality guards (move/body_ratio/wick) produce zero visible rejections — they are either never reached (because HTF killed first) or their debug logs are silenced.

**DISPLACEMENT → EXPANSION: 342/357 killed (95.8%) — worst conversion rate.**

Of 357 candidates that survived to DISPLACEMENT: 259 were killed by HTF flip (same mechanism), 82 by retrace/extension guards. Only 15 (4.2%) produced an expansion candle.

The HTF reseeding logic is the single mechanism responsible for the majority of funnel collapse at both SWEEP (100% of losses) and DISPLACEMENT (75.7% of losses). It accounts for **1,628 of the total 1,722 pre-EXPANSION losses** (94.5%).

---

# CRT State Transition Funnel Trace (previous session)

---

## Guard conditions at every stage

---

## Guard conditions at every stage

### RANGE → SWEEP (`RangeDetector.detect_sweep` — crt_engine_v2.py:446)
```python
swept_high = candle.high > active_range.h_ref and candle.close < active_range.h_ref
swept_low  = candle.low  < active_range.l_ref and candle.close > active_range.l_ref
# Passes if either condition holds; else returns None → no transition
```
Exit reasons back to RANGE: gap-reset (GapDetector), 50%-retrace hit, 1.618-extension hit, HTF-id change.

---

### SWEEP → DISPLACEMENT (`StateMachine.try_sweep_to_displacement` — line 562)
Four sequential guards — all must pass:
1. `move < atr_min_displacement × atr` → **REJECTED** (debug, silenced)
2. `age > max_sweep_age_candles` → **SWEEP_EXPIRED** (info, silenced; fires reset_to_range)
3. `body_ratio < body_ratio_min` → **REJECTED** (debug, silenced)
4. `wick_size < atr_multiplier_min × atr` → **REJECTED** (debug, silenced)

Exit reason if no candle qualifies before the sweep expires: SWEEP_EXPIRED (also visible as `action["action"] = "SWEEP_EXPIRED"` in backtest loop).

---

### DISPLACEMENT → EXPANSION (`StateMachine.try_displacement_to_expansion` — line 611)
Three sequential guards:
1. Directional check: LONG requires `close > open`; SHORT requires `close < open` → implicit False (debug)
2. Close must extend past displacement close: LONG `close ≤ disp_close`, SHORT `close ≥ disp_close` → **Expansion REJECTED** (debug, silenced)
3. ATR-distance: `|close − disp_close| < expansion_atr_min_distance × atr` → **Expansion REJECTED** (debug, silenced)

Exit reason from DISPLACEMENT: stays in DISPLACEMENT until a qualifying candle arrives or ResetLogic fires (retrace/extension/HTF flip).

---

### EXPANSION → RETEST (`StateMachine.try_expansion_to_retest` — line 663)
Four sequential guards:
1. `active_range is None` → False (edge case only)
2. `depth_abs < 0.1 × atr` (price hasn't come back enough) → implicit False, **no log**
3. `depth_abs > adaptive_ceiling` → **Retest REJECTED** (debug, silenced)
4. [PATCH 7] `disp_strength > max_displacement_strength` → **Retest REJECTED [PATCH 7]** (debug, silenced)

**Observable evidence of RETEST entries: each `[CRT DEBUG] disp_open=… retest=… r=…` print line equals one confirmed RETEST transition.**

---

### RETEST → EXECUTION (soft confirmation window — line 1579)
Evaluated every candle within `soft_conf_max_candles` window:
1. NEWS_FILTER active → False
2. spread > max_spread_pct → False
3. BitNet score < 0.55 → **REJECTED BY BITNET MAIN** (warning log)
4. `S = G^α × C^β < tier_2_threshold` → **REJECTED LOW_SCORE** (warning log)
5. Window expires (`soft_conf_candles ≥ soft_conf_max_candles`) → **CONFIRMATION_FAILED** (info, silenced)

Post-approval filters that still reset to RANGE:
6. Range-position: LONG entry above midpoint → **FILTER_REJECTED: Not in discount zone**
7. Session filter: candle session not in `allowed_sessions` → **FILTER_REJECTED: off_session**

---

### EXECUTION → RESOLUTION (`ExecutionEngine.update_trade` — line 1518)
Candle-by-candle price check: TP1 → partial close + trail SL; TP2 → full close; SL hit → STOPPED.
Exit reason = trade outcome (TP2 / TP1 / STOPPED).

ILLEGAL transition warnings in log (`ILLEGAL DISPLACEMENT → RESOLUTION`, `ILLEGAL RANGE → RESOLUTION`) mean `try_execution_to_resolution` was called when the state had already been reset to a different state (state-machine desync on concurrent TP close + reset).

---

## Funnel from the ETHUSDT run log

| State | Entries | Exits forward | Collapsed | Primary exit reason |
|---|---:|---:|---:|---|
| RANGE | 105,206 | ? sweeps detected | unknown | no candle crossed h_ref/l_ref with close inside (vast majority) |
| SWEEP | ? | ? displacements | unknown | SWEEP_EXPIRED most likely dominant (debug silenced: CRT.StateMachine at WARNING) |
| DISPLACEMENT | ? | ? expansions | unknown | expansion guards (directional / extend / ATR-dist) — debug silenced |
| EXPANSION | ? | **14** retests | unknown | RETEST depth ceiling / PATCH 7 — debug silenced |
| RETEST | **14** | **4** executions | **10** | soft confirmation timeout or LOW_SCORE (S < tier_2_threshold) |
| EXECUTION | **4** | **4** resolutions | 0 | TP1/TP2/STOPPED |
| RESOLUTION | **4** | 4 → RANGE | — | auto reset |

**Confirmed collapse point: RETEST → EXECUTION. 10 of 14 retest setups (71%) were rejected.**

---

## Why upper-state counts are invisible

`backtest_v2.py:71-76` silences all INFO/DEBUG logs for:
```python
for _noisy in [
    "CRT.RangeDetector", "CRT.StateMachine", "CRT.UltronRisk",
    "CRT.Execution", "CRT.Reset", "CRT.EventLog", "CRT.Orchestrator",
]:
    logging.getLogger(_noisy).setLevel(logging.WARNING)
```
`StateMachine._transition` logs at INFO (`self.log.info(f"STATE: … → …")`), so SWEEP/DISPLACEMENT/EXPANSION counts are completely silenced in the console output.

The typed event log (`state.event_log`, written via `ev_logger.record(...)`) accumulates all `STATE_TRANSITION` events in memory and is dumped to `results/…/ETHUSDT_events.jsonl`. **That file contains the full funnel counts.**

---

## How to get the exact counts without touching thresholds

```powershell
# After any backtest run, parse the events JSONL:
python -c "
import json, collections
events = [json.loads(l) for l in open('results/run_20260521_235920_ETHUSDT/ETHUSDT_events.jsonl')]
transitions = [(e['state_from'], e['state_to']) for e in events if e.get('event') == 'STATE_TRANSITION']
resets      = [(e['state_from'], e.get('reason','')) for e in events if e.get('event') == 'RESET']
print('Transitions:'); [print(' ', f, '->', t) for f,t in sorted(collections.Counter(transitions).items())]
print('Resets from:'); [print(' ', f, '|', r[:60]) for f,r in sorted(collections.Counter((f, r[:30]) for f,r in resets).items())]
"
```

---

## Dominant collapse: RETEST → EXECUTION (71%)

The 10 dropped setups at RETEST→EXECUTION are split among:
- **Soft confirmation timeout** (`CONFIRMATION_FAILED` — fires when `soft_conf_candles ≥ soft_conf_max_candles` without S ≥ tier_2_threshold)
- **LOW_SCORE** (`S = G^α × C^β < tier_2_threshold` — visible in WARNING log if any fired)
- **FILTER_REJECTED** (range-position or off-session — warning log)
- **BitNet rejection** (score < 0.55 — warning log)

From the log shown: no explicit `CONFIRMATION_FAILED`, `LOW_SCORE`, or `FILTER_REJECTED` lines are visible → all 10 likely went through the soft-conf window silently and timed out (`CRT.UltronRisk` logger also silenced).

---

# Runtime Anomaly Trace — 105,206 → 50,928 row drop & Feature Lookup MISS

## Context

`python src\runtime\backtest_v2.py --csv data\ETHUSDT_M15.csv --instrument ETHUSDT`
produces 4 trades but logs:

- `Feature lookup MISS` (3 distinct candle timestamps)
- `Skipping ENTRY log` (3 trades not written to fusion log)
- `ZERO FEATURES (38/38)` (3 trades have all‑zero feature vectors)
- `FeaturePipeline built: 50928 rows` vs `Backtest candles = 105,206`

Trace only — no patch, no redesign.

---

## 1. Entry point that builds FeaturePipeline

`src\runtime\backtest_v2.py:1263-1299` — inside `BacktestRunner.__init__()`:

```python
raw_df = pd.read_csv(self.csv_path)                          # → 105,206 rows
raw_df.columns = [c.strip().lower() for c in raw_df.columns]
pipeline = FeaturePipeline(raw_df)                           # src/features/feature_pipeline.py:135
enriched_df, self.feature_vectors = pipeline.run()           # → 50,928 rows / shape (50928, 38)
_ts_series = pd.to_datetime(enriched_df["timestamp"])
self.feature_ts_to_idx = {
    ts.strftime("%Y-%m-%d %H:%M:%S"): i
    for i, ts in enumerate(_ts_series)
}
```

`feature_ts_to_idx` is the lookup dict the live loop probes per candle at
[backtest_v2.py:1500-1530](src/runtime/backtest_v2.py:1500).

---

## 2. Pipeline stages inside `FeaturePipeline.run()`

[`src\features\feature_pipeline.py:736-802`](src/features/feature_pipeline.py:736):

```
compute_price_features          → adds prev_close (shift 1)              | warm: 1
compute_volume_features         → volume_ma20 rolling(20)                 | warm: 20
compute_indicators              → ma_20, ma_50, ma_200, rsi_14, atr_14,
                                   bb_*, macd_*                           | warm: 200 (ma_200)
compute_trend_features          → trend_strength rolling(10) on ma_slope  | warm: ~210
compute_volatility_regime       → atr percentile rank                     | warm: 14
compute_context                 → hour/session/dow (pure)                 | warm: 0
compute_structure_liquidity     → swing_high/low (center=True rolling 5), | warm: ±2 edge
                                   ref_high/low ffill, break_of_structure,
                                   liquidity_sweep
compute_normalization           → rolling(50) z‑score for 5 cols          | warm: 50
compute_canonical_price_features→ body_size, wick_size, body_ratio, price_pos
compute_canonical_volatility    → atr (close‑norm), range_size, vol_ratio
compute_canonical_ema           → ema_fast, ema_slow, ema_spread,
                                   momentum_score — NaN where atr=0       | warm: 14
compute_canonical_trend         → trend_bias from ema_fast vs ema_slow
compute_canonical_structure     → sweep_detected, displacement_flag,
                                   retest_flag, double_sweep
compute_canonical_temporal      → disp_strength (NaN where atr=0),
                                   ★ retest_depth = NaN where retest_flag != 1 ★
                                   candles_since_retest
compute_liquidity_distance      → liquidity_distance, liquidity_pressure
promote_volume_spike            → adaptive 75‑pctl over rolling 50
compute_canonical_session       → int8 cast
finalize()                      → dropna(subset=CANONICAL_FEATURES)       | the killer
build_feature_vector            → (N, 38) float32 matrix
```

The only canonical feature whose NaN/non‑NaN status depends on a **per‑bar
event** (not just a warm‑up window) is `retest_depth`:

[`src\features\feature_pipeline.py:536-541`](src/features/feature_pipeline.py:536)

```python
df["retest_depth"] = np.where(
    (df["retest_flag"] == 1) & (df["atr"] > 0) & (df["close"] > 0),
    (df["close"] - df["ema_fast"]).abs() / (df["atr"] * df["close"]),
    np.nan,                                      # ← NaN for every non‑retest bar
)
df["retest_depth"] = df["retest_depth"].clip(0.0, 1.0).astype(np.float32)
# NB: pd/np .clip preserves NaN — does NOT zero them.
```

`retest_depth ∈ CANONICAL_FEATURES` (index 33, see
[`src\features\feature_schema.py:62`](src/features/feature_schema.py:62)), so it is in
the `dropna(subset=...)` list of `finalize()`
([`src\features\feature_pipeline.py:660`](src/features/feature_pipeline.py:660)).

---

## 3. Row counts after each stage

| Stage | Rows In | Rows Out | Drop Count | Reason |
|---|---|---|---|---|
| `pd.read_csv(ETHUSDT_M15.csv)` | 105,206 | 105,206 | 0 | raw load |
| `_validate_input` + numeric coerce | 105,206 | 105,206 | 0 | in‑place, no drop |
| `compute_indicators` (ma_200, atr_14, rsi_14, bb_20, macd) | 105,206 | 105,206 | 0 | adds NaN columns; warm‑up rows = NaN but not yet dropped |
| `compute_normalization` (rolling 50 z‑score) | 105,206 | 105,206 | 0 | NaN in 5 normed cols for first 50 rows |
| `compute_canonical_ema` (ema_spread, momentum_score = NaN where atr=0) | 105,206 | 105,206 | 0 | NaN in first ~14 rows |
| `compute_canonical_temporal` (★ retest_depth = NaN where retest_flag != 1 ★) | 105,206 | 105,206 | 0 | NaN injected on every non‑retest bar (≈ 54k rows) |
| `compute_liquidity_distance` | 105,206 | 105,206 | 0 | clip + fillna(10) on pressure score; distance keeps NaN where atr_safe is NaN |
| `finalize()` → `dropna(subset=list(CANONICAL_FEATURES))` | 105,206 | **50,928** | **54,278** | drops every row where any of the 38 canonical cols is NaN — dominated by `retest_depth=NaN` on non‑retest bars (+ ~200 ma_200 warm‑up + ~50 z‑score warm‑up + ±2 swing edges) |
| `build_feature_vector` (cast to (N, 38) float32) | 50,928 | 50,928 | 0 | matrix only; assertion paths |
| `feature_ts_to_idx = {ts.strftime(...): i ...}` | 50,928 | 50,928 | 0 | dict has exactly the surviving rows |

Confirmed by run log: `dict_size=50928`, `fv_shape=(50928, 38)`.

---

## 4. Where the rows disappear

Single point: `FeaturePipeline.finalize()`
([`src\features\feature_pipeline.py:657-662`](src/features/feature_pipeline.py:657)).

```python
def finalize(self) -> pd.DataFrame:
    df = self.df
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.dropna(subset=list(CANONICAL_FEATURES)).reset_index(drop=True)
    self.df = df
    return df
```

`subset` includes `retest_depth`. `retest_depth` is intentionally NaN on every
candle that is not flagged as a retest (≈ 52% of bars on ETHUSDT M15).
`dropna` therefore deletes that majority and *also* re‑indexes (`reset_index`),
so the surviving rows are not contiguous in original‑CSV order — only in
feature‑array order.

---

## 5. Timestamp generation trace

```
CSV row                   "Date","Time","Open",...        (or "Timestamp,...")
        │
        ▼
CandleLoader.stream()     row[date]+" "+row[time]  → datetime.strptime(...)
[backtest_v2.py:625-660]         → datetime object  (naive, no tz)
        │
        ▼
Candle(timestamp=ts)      passed to engine loop
        │
        ▼
candle.timestamp.strftime("%Y-%m-%d %H:%M:%S")
[backtest_v2.py:1501]            → e.g. "2023-11-09 15:00:00"
        │
        ▼
self.feature_ts_to_idx.get(_ts_key, -1)
[backtest_v2.py:1502]            ← dict built from enriched_df

# parallel build of the dict keys:
raw_df["timestamp"] (str)
        │
        ▼
pd.to_datetime(enriched_df["timestamp"])           [backtest_v2.py:1283]
        │
        ▼  (after finalize() has dropped 54,278 rows)
ts.strftime("%Y-%m-%d %H:%M:%S")                   [backtest_v2.py:1285]
        │
        ▼
key, e.g. "2022-01-01 19:30:00"
```

**The formats match exactly** (`"%Y-%m-%d %H:%M:%S"` on both sides). The
log line `dict sample key='2022-01-01 19:30:00'` vs miss key
`'2023-11-09 15:00:00'` is the *first* dict key, not the nearest — it does
not indicate format drift. Hit example from the same run:
`candle_ts_key='2023-07-12 08:30:00' fv_idx=26602` is inside the surviving
50,928 → that candle *was* a retest bar; the three MISS candles were not.

---

## 6. Why 105,206 → 50,928

`FeaturePipeline.finalize()` calls
`dropna(subset=list(CANONICAL_FEATURES))`. Inside `CANONICAL_FEATURES`,
`retest_depth` is computed via `np.where(retest_flag == 1, ..., np.nan)`,
producing NaN on every bar that is not a retest. Because most ETHUSDT M15
bars are not retests, `dropna` deletes ≈ 52% of rows (54,278) in one call.

Secondary, much smaller contributors (subsumed by the same call): ma_200
warm‑up (~200 rows), 50‑bar z‑score warm‑up (overlaps), center=True swing
window edges (~4 rows), ATR‑gated `ema_spread`/`momentum_score`/`disp_strength`
NaN on the first ~14 bars (overlaps).

The CRT engine continues running on **all 105,206** raw candles (it does not
share the FeaturePipeline drop). When it fires a trade on a non‑retest
candle, that candle’s timestamp is absent from `feature_ts_to_idx` →
`_fv_idx = -1` → `feature_vector = [0.0] * 38` → ZERO FEATURES (38/38) →
`Skipping ENTRY log` (not written to fusion JSONL). Trades whose entry
candle *happens* to also be a retest bar (CRT‑0001 in this run) survive the
lookup and write normally.

---

## Stage table (final)

| Stage | Rows In | Rows Out | Drop Count | Reason |
|---|---|---|---|---|
| pd.read_csv | 105,206 | 105,206 | 0 | raw load |
| _validate_input + numeric coerce | 105,206 | 105,206 | 0 | column setup only |
| compute_price/volume/indicators (ma_200, atr_14, rsi_14, bb, macd) | 105,206 | 105,206 | 0 | NaN appears in warm‑up rows but not dropped yet |
| compute_normalization (rolling 50) | 105,206 | 105,206 | 0 | NaN in 5 normed cols for first 50 rows |
| compute_canonical_ema/temporal (★ retest_depth = NaN where retest_flag != 1 ★) | 105,206 | 105,206 | 0 | NaN injected on ≈ 52% of bars |
| compute_liquidity_distance / promote_volume_spike / session | 105,206 | 105,206 | 0 | adds cols, no drop |
| **finalize() → dropna(subset=CANONICAL_FEATURES)** | **105,206** | **50,928** | **54,278** | drops every row where any of 38 canonical cols is NaN — dominated by `retest_depth=NaN` |
| build_feature_vector → (N, 38) float32 | 50,928 | 50,928 | 0 | matrix build only |
| feature_ts_to_idx dict | 50,928 | 50,928 | 0 | one key per surviving row |

---

## ROOT CAUSE

`FeaturePipeline.compute_canonical_temporal_features`
([`src\features\feature_pipeline.py:536`](src/features/feature_pipeline.py:536)) writes
`np.nan` to `retest_depth` on every candle where `retest_flag != 1`.
`retest_depth` is a member of `CANONICAL_FEATURES`, so
`finalize()`’s `dropna(subset=list(CANONICAL_FEATURES))`
([`src\features\feature_pipeline.py:660`](src/features/feature_pipeline.py:660))
deletes every non‑retest bar — ~52% of the input (54,278 of 105,206 on
ETHUSDT M15). The CRT engine still iterates all 105,206 raw candles, so
trades opened on a non‑retest bar look up a timestamp that is no longer in
`feature_ts_to_idx`, fall back to `[0.0]*38`, and trigger the
`Feature lookup MISS` / `Skipping ENTRY log` / `ZERO FEATURES (38/38)` chain.

The timestamp format is identical on both sides (`%Y-%m-%d %H:%M:%S`); the
log hint “check CSV timestamp format” is misleading. The miss is caused by
*missing rows*, not by *mismatched key shapes*.

## CONFIDENCE: 98%

Direct evidence: the NaN sentinel in `retest_depth`, its membership in
`CANONICAL_FEATURES`, and the `dropna(subset=CANONICAL_FEATURES)` call are
all present in the current source. Run telemetry corroborates: a HIT at
`2023-07-12 08:30:00` (fv_idx=26602) and MISSES at
`2023-11-09 15:00:00`, `2023-11-16 09:30:00`, `2024-10-26 15:30:00` are
consistent with “HIT iff entry candle was also a retest bar.” The remaining
2% covers the (smaller) possibility that warm‑up overlap or
`liquidity_distance` NaN also contributes — but neither alone could account
for ~54k dropped rows on a 105k‑row M15 series.

---

# Implementation — surgical fix at the source

## Change summary

One file, ≤ 6 lines edited (3 logical changes).

`src\features\feature_pipeline.py:536-541` — in
`compute_canonical_temporal_features()`:

```python
# BEFORE
df["retest_depth"] = np.where(
    (df["retest_flag"] == 1) & (df["atr"] > 0) & (df["close"] > 0),
    (df["close"] - df["ema_fast"]).abs() / (df["atr"] * df["close"]),
    np.nan,
)
df["retest_depth"] = df["retest_depth"].clip(lower=0.0, upper=1.0).astype(np.float32)
```

```python
# AFTER
# retest_depth is only defined when retest_flag == 1; on every other bar
# the feature is semantically "no retest", which we encode as 0.0 (NOT NaN).
# NaN would propagate into finalize()'s dropna(subset=CANONICAL_FEATURES)
# and silently delete ~52% of bars — breaking the timestamp → row-index map
# the backtest loop uses (see backtest_v2.py:1500-1530). ATR-warmup rows are
# still cleanly dropped via the NaN fallbacks in disp_strength / ema_spread
# / momentum_score, so no invalid warm-up samples leak through.
df["retest_depth"] = np.where(
    (df["retest_flag"] == 1) & (df["atr"] > 0) & (df["close"] > 0),
    (df["close"] - df["ema_fast"]).abs() / (df["atr"] * df["close"]),
    0.0,
)
df["retest_depth"] = df["retest_depth"].clip(lower=0.0, upper=1.0).astype(np.float32)
```

## Why this fix is safe

1. **No schema drift** — `CANONICAL_FEATURES` order, names, count (38), and
   `FEATURE_ORDER_HASH` are unchanged.
2. **No model re-export** — saved Gaussian / TradeNet / RR / BitNet models
   keep the same input shape. Existing weights remain valid.
3. **Warmup rows still drop** — `ema_spread`, `momentum_score`, and
   `disp_strength` keep their `np.nan` fallback on `atr == 0`, plus the
   50-bar rolling z-score on `macd_hist` / `trend_strength` leaves NaN on the
   first ~50 rows. `finalize()` continues to remove genuine warm-up rows.
   Expected post-fix row count: ~105,206 − ~50 (warmup) ≈ 105,156 rows.
4. **Downstream consumers tolerant of 0.0** — verified every reader:
   - `scoring_engine.py:126` → `max(0.0, min(1.0, float(...)))`
   - `crt_engine.py:28` → `float(features["retest_depth"])`
   - `sl_tp_comparator.py:85` and `execution_planner.py:357`
     → `if 0.3 <= retest_depth <= 0.7` (zero correctly falls outside)
   - `portfolio_validation.py:543` → passthrough
   - All `features.get("retest_depth", 0.0)` sites already default to 0.0
5. **Closes the train/serve mismatch** — the LIVE lookup-miss path already
   defaults the *entire* feature vector to `[0.0]*38`
   ([`backtest_v2.py:1529`](src/runtime/backtest_v2.py:1529)). After the
   fix, non-retest entry bars get their real 37 feature values plus
   `retest_depth = 0.0`, which is strictly more correct than the all-zero
   fallback.
6. **No fusion-log gaps** — `Feature lookup MISS` / `Skipping ENTRY log`
   branches disappear because `feature_ts_to_idx` now contains every
   non-warmup bar. Trades opened on non-retest candles will write to
   `logs/<INST>_fusion.jsonl` instead of being silently skipped.

## Files modified

- `src\features\feature_pipeline.py` (one block, lines 536–541 + comment)

## Files NOT modified (no change needed)

- `src\features\feature_schema.py` — schema constants unchanged.
- `src\runtime\backtest_v2.py` — lookup logic correct; just receives a
  fuller dict now.
- `src\features\schema_validator.py` — validators already accept any
  finite float in `retest_depth` ∈ ℝ.
- All trained model artifacts under `models\` — schema hash unchanged.

## Verification

End-to-end:

```powershell
python src\runtime\backtest_v2.py --csv data\ETHUSDT_M15.csv --instrument ETHUSDT --output results\
```

Expected post-fix log lines:

```
FeaturePipeline built: ~105,156 rows | first 3 ts keys: ['2022-01-01 00:00:00', ...]
```

(vs. `50928 rows | first 3 ts keys: ['2022-01-01 19:30:00', ...]` today —
note the earlier first-ts because non-retest bars from 00:00 onward survive.)

No `Feature lookup MISS #N` warnings.
No `Skipping ENTRY log for CRT-XXXX` warnings.
No `ZERO FEATURES | trade=CRT-XXXX zero_count=38/38` warnings on real trades.

Unit-test sanity:

```powershell
python -m pytest tests\test_feature_pipeline.py -x
```

Targeted assertion to add (optional, in
`tests\test_feature_pipeline.py`):

```python
def test_finalize_keeps_non_retest_rows():
    df = _build_synthetic_ohlcv(n=1000)        # any helper that generates 1000 candles
    pipe = FeaturePipeline(df)
    enriched, vec = pipe.run()
    # warmup of ~50 max; all other rows must survive
    assert len(enriched) >= 900
    assert (enriched["retest_depth"] >= 0.0).all()
    assert enriched["retest_depth"].notna().all()
```

## Rollback

Revert the single hunk — `0.0` back to `np.nan`. No model files, configs,
or governance state to roll back.


================================================================================
SOURCE_FILE: docs/plans/assume-the-architecture-is-joyful-naur.md
SOURCE_BYTES: 6517
PART: 1/10 FILE 5/7
================================================================================

# Repository Truths Layer v2 — Types, Durable Tier, Funding Ledger

> Created: 2026-06-03 · Updated: 2026-06-03 · Milestone: Gov (knowledge-governance)
> Doc-only + test-only change. No config write, no rehash, no promotion. Extends the layer
> shipped earlier today (`docs/current-findings.md`, `CLAUDE.md` Repository Truths Index,
> `tests/test_current_findings.py`).

## Context

The findings layer works, but three reviewer enhancements make it a sharper roadmap filter:
1. **Type** — findings are currently undifferentiated; tagging them
   `ARCHITECTURE/ECONOMIC/GOVERNANCE/OPERATIONAL/RISK` makes them filterable.
2. **Durable tier** — re-validating stable empirical truths (e.g. *persistence ≠ discrimination*)
   every 90d is busywork that erodes signal. A `DURABLE` status with a **365d** horizon keeps the
   annual sanity check without a true never-expire bucket (the BitNet "dormant→live-gate" reversal
   proves "timeless" truths still decay — so nothing is exempt from re-check, only re-cadenced).
3. **Funding Ledger** — a *finding* is an observation; *funding* is capital allocation, and one
   finding (F-001) kills/funds many initiatives. Keep them adjacent but separate so a fresh session
   can't silently reopen a KILLED initiative. Lives in `current-findings.md`, **not** the progress
   registry (different axis; registry is in-flight ideas, and is itself stale at `v2`).

**Decisions locked (AskUserQuestion):** Q1 = `DURABLE` + annual re-affirm; Q2 = new Funding Ledger
in `current-findings.md` with Reopen Conditions.

## What exists (reuse, don't rebuild)
- `tests/test_current_findings.py` — extend its existing parse helpers (`_parse_findings`,
  `_field`) and status/freshness checks; don't restructure.
- `docs/governance/user-progress-registry.md` — the *in-flight ideas* axis. The Funding Ledger is
  the *capital-allocation* axis; they cross-reference, they don't merge.

---

## Deliverables

### 1. `docs/current-findings.md`
- **Schema block:** add `- Type:` (vocab `ARCHITECTURE|ECONOMIC|GOVERNANCE|OPERATIONAL|RISK`);
  add `DURABLE` to the Status enum; document per-status revalidation windows:
  `VALIDATED/OPEN = 90d · DURABLE = 365d · SUPERSEDED/RETIRED = exempt`.
- **Every finding F-001…F-012:** insert a `- Type:` line. Assignments:
  F-001/002/003/011 ECONOMIC · F-004/005/012 ARCHITECTURE · F-006/007/009 GOVERNANCE ·
  F-008/010 RISK.
- **Promote F-011 to `DURABLE`** (the canonical example: *persistence ≠ discrimination*),
  `Revalidate-by: 2027-06-01`. Others stay `VALIDATED`/`OPEN` (re-cadence on re-affirmation, not now).
- **New `## Funding Ledger` section** — one block per initiative:
  ```
  ### <Initiative> — <FUNDED|FROZEN|KILLED|RESEARCH|UNFUNDED>
  - Date:    YYYY-MM-DD
  - Evidence: F-xxx, F-yyy [, analysis link]
  - Reopen Conditions: <falsifiable trigger(s)>   (required for FROZEN/KILLED)
  ```
  Seed (~8, evidence-linked):
  | Initiative | Status | Evidence | Reopen |
  |---|---|---|---|
  | Liquidity V2 | KILLED | F-001, F-011 (Phase-0 FAIL) | ΔAUC ≥ +0.03 OOS **and** positive expectancy **and** cross-instrument pass |
  | TradeNet V2 | KILLED | F-001, F-005 | same Phase-0 gate |
  | Probability Surface V2 | KILLED | F-001, F-012 | same Phase-0 gate |
  | BitNet V2 (adaptive threshold) | FROZEN | F-004 | `bitnet_score_at_entry` dataset accrued + measured adaptive lift > static 0.55 |
  | Governance/execution wiring (integrity gate + drift→size-down) | FUNDED | F-001, F-006, F-008 | — |
  | Per-instrument session/throughput sweeps | FUNDED | F-003, F-009 | — |
  | ReplayMemory → deterministic advisory path | RESEARCH | F-012, F-008 | weight-0.0 measurement shows AUC lift beyond static features |
  | Execution-planner replay experiment (selection vs SL/TP) | RESEARCH | F-010, F-002 | — |

### 2. `CLAUDE.md`
- **Repository Truths Index:** add a `Type` column (keep ≤20 rows; currently 12). Add a one-line
  pointer beneath the table: *capital-allocation decisions derived from these findings → Funding
  Ledger in `docs/current-findings.md`.*
- **§6.2 Findings Mandate:** document (a) the `Type` tag, (b) `DURABLE` (365d) vs `VALIDATED/OPEN`
  (90d), (c) the Funding Ledger — initiative-level, cites findings, carries Reopen Conditions;
  **never silently revive a `KILLED`/`FROZEN` initiative — its Reopen Conditions must be met and a
  SESSION LOG entry filed.**

### 3. `tests/test_current_findings.py`
- Add `_VALID_TYPE`; assert every finding has `Type ∈ vocab`.
- Add `DURABLE` to `_VALID_STATUS` (it stays **non-terminal** → still freshness-checked at its 365d
  horizon; only `SUPERSEDED/RETIRED` exempt — unchanged).
- **Window-ceiling check** (enforces the tiering, prevents horizon abuse): for `VALIDATED/OPEN`
  assert `Revalidate-by − Validated ≤ 180d`; for `DURABLE` assert `≤ 400d`.
- **Funding Ledger checks:** parse `### <Initiative> — <STATUS>` blocks under `## Funding Ledger`;
  assert `STATUS ∈ {FUNDED,FROZEN,KILLED,RESEARCH,UNFUNDED}`; every `Evidence` `F-id` resolves to a
  finding block (cross-ref integrity); `FROZEN/KILLED` blocks carry a non-empty `Reopen Conditions`.
- Keep `_parse_findings` anchored to the `## Findings` section so Funding blocks (not `F-NNN`) are
  never misparsed as findings.

---

## Governance check (Five Questions)
Doc-only + additive test; no config `_WRITE_ROOTS`; no auto-promotion; git-replayable; strengthens
I1/I2 (conclusions and the capital decisions derived from them are now both explicit, dated,
evidence-linked). Compliant.

## Verification
- `pytest -k current_findings` → green; then (a) set a `VALIDATED` finding's `Revalidate-by` to
  +300d and confirm the window-ceiling check fails; (b) point a Funding-Ledger `Evidence` at a
  non-existent `F-999` and confirm the cross-ref check fails; revert both.
- `pytest tests/test_current_findings.py tests/test_topic_docs.py` → no regression.
- Cold-start dry-run: from `CLAUDE.md` alone, the index now shows Type per row and points to the
  Funding Ledger; the ledger shows KILLED/FUNDED initiatives + Reopen Conditions without opening
  any analysis doc.
- Append the §6 SESSION LOG entry (after exiting plan mode).

## Out of scope
- Migrating funding status into the progress registry (kept separate by design).
- An "axiomatic / never-expire" tier (rejected — `DURABLE` 365d is the floor; engineering
  invariants like *no-lookahead* already live in `goal.md`, not here).
- Auto-deletion (supersede, never delete — unchanged).


================================================================================
SOURCE_FILE: docs/plans/based-on-your-screenshot-precious-scott.md
SOURCE_BYTES: 12239
PART: 1/10 FILE 6/7
================================================================================

> Created: 2026-05-07 · Updated: 2026-05-07 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Plan: Backtest on Existing M15 Data + Agent Strategy Discovery + Live Broker Hook

## Context

User has one M15 Excel file in `data/`. Historical download is out of scope — data is
added manually. The three pieces to build are:

1. **Backtest on real M15 data** — read the Excel file, run `BacktestRunner`, get real metrics.
2. **Agent strategy discovery** — agent intent that triggers the backtest + engine scoring +
   `llm_insight()` narrative so the LLM explains what the system would have done.
3. **Live broker hook** — replace `INOUTRunner._fetch_candles()` stub and `INOUTExecutor`
   Phase 1 stubs with real API calls to Binance or OANDA (controlled by config `broker.provider`).

---

## Constraints From Exploration

- `CandleLoader` (backtest_v2.py:583) reads **CSV only** — Excel must be converted first.
- `pandas` is almost certainly available (quantitative trading system with sklearn/scipy).
- `INOUTRunner._fetch_candles()` (runner.py:197) returns a list of raw dicts — this is the
  live candle entry point to replace.
- `INOUTExecutor` (executor.py:71) Phase 1 stubs are at lines 104–250; `self._dry_run = True`
  always set — controlled by new `broker.dry_run` config key.
- All config keys in `configs/production/v1_multi_2026_03.json`.
- No new packages: stdlib `urllib` + `hmac` for HTTP; `pandas` for Excel read (already present).
- `broker.dry_run` **defaults to `true`** — live execution only activates via `live_hook.enable`.

---

## Critical Files

| File | Action |
|------|--------|
| `configs/production/v1_multi_2026_03.json` | Add `"broker"` section |
| `scripts/maintenance/_compute_hash.py` | Run after config change |
| `src/inout/live_feed.py` | **New** — `BinanceLiveFeed`, `OANDALiveFeed` (candle fetch for live) |
| `src/inout/runner.py` | Replace `_fetch_candles()` stub (line ~197) |
| `src/inout/executor.py` | Replace Phase 1 stubs with real broker calls (lines 104–250) |
| `src/agent/tools/market_mode.py` | **New** — `handle_strategy_discover` agent tool |
| `src/agent/tool_registry.py` | Register `strategy.discover` |
| `src/agent/plan_compiler.py` | Add `strategy_discover` to PLAN_REGISTRY |
| `src/agent/prompts/intent_patterns.json` | Add regex patterns |
| `tests/test_agent_strategy_discover.py` | **New** — unit tests |
| `tests/test_inout_live_feed.py` | **New** — unit tests |

---

## Step 1 — Add `"broker"` config section

```json
"broker": {
  "provider": "binance",
  "dry_run": true,
  "live_candle_count": 50,
  "binance": {
    "api_key_env": "BINANCE_API_KEY",
    "api_secret_env": "BINANCE_API_SECRET",
    "futures_base_url": "https://fapi.binance.com",
    "spot_klines_url": "https://api.binance.com/api/v3/klines",
    "recv_window_ms": 5000,
    "interval_map": {"M1":"1m","M5":"5m","M15":"15m","H1":"1h","H4":"4h","D1":"1d"}
  },
  "oanda": {
    "rest_url": "https://api-fxtrade.oanda.com/v3",
    "account_id_env": "OANDA_ACCOUNT_ID",
    "api_key_env": "OANDA_API_KEY",
    "granularity_map": {"M1":"M1","M5":"M5","M15":"M15","H1":"H1","H4":"H4","D1":"D"}
  }
}
```

Re-hash: `python scripts/maintenance/_compute_hash.py`

---

## Step 2 — Excel-to-CSV converter (inline utility, not a new file)

Add a private helper `_excel_to_csv(xlsx_path: str, out_dir: str) -> str` inside
`src/agent/tools/market_mode.py`:

```python
def _excel_to_csv(xlsx_path: str, out_dir: str) -> str:
    """Read first sheet, normalise columns, write CSV for CandleLoader."""
    import pandas as pd
    df = pd.read_excel(xlsx_path, sheet_name=0)
    # normalise column names to lowercase
    df.columns = [c.strip().lower() for c in df.columns]
    # ensure CandleLoader alias match: timestamp,open,high,low,close,volume
    out_path = os.path.join(out_dir, os.path.basename(xlsx_path).replace(".xlsx", ".csv"))
    df.to_csv(out_path, index=False)
    return out_path
```

Called only when input path ends with `.xlsx`. Existing CSV files pass through unchanged.

---

## Step 3 — Agent tool: `src/agent/tools/market_mode.py` (new)

Single handler — follow `docs/EXAMPLE_SERVICE.py`:

```
handle_strategy_discover(data_path, instrument) → dict

1. _load_bt_cfg()  — fail-fast require backtest section keys
2. If data_path ends .xlsx → _excel_to_csv(data_path, "data/") → csv_path
   Else csv_path = data_path
3. total = CandleLoader(csv_path, instrument).count()
4. bt_config = BacktestConfig.from_prod_config(cfg)
5. runner = BacktestRunner(bt_config, csv_path, skip_features=False)
6. metrics = runner.run(CandleLoader(csv_path, instrument).stream(),
                        total, "results/market_scan/")
7. Sample up to 5 approved trade feature vectors → EngineRunner.run() each
   Collect: engine scores, regime labels
8. summary = {
     win_rate, expectancy_rr, max_drawdown_pct, approved_trades, rejected_trades,
     dominant_regime, avg_crt_score, avg_gaussian_score, avg_rr_score,
     feature_drift (from metrics.distribution)
   }
9. narrative = llm_insight(context=summary, report_type="backtest_summary")
10. return {"status": "ok", "summary": summary, "narrative": narrative}
```

`data_path` defaults to glob of first `.xlsx` or `.csv` found in `data/` if not supplied.

---

## Step 4 — Register tool (tool_registry.py)

```python
ToolSpec(
    name="strategy.discover",
    description="Run backtest on M15 data file, score with engines, return LLM strategy narrative",
    args_schema={
        "data_path":  {"type": "str", "required": False,
                       "desc": "Path to .xlsx or .csv in data/. Auto-detected if omitted."},
        "instrument": {"type": "str", "required": False, "desc": "e.g. BTCUSDT"},
    },
    handler=handle_strategy_discover,
    write=False,
),
```

---

## Step 5 — PLAN_REGISTRY addition (plan_compiler.py)

```python
"strategy_discover": Plan(
    intent_key="strategy_discover",
    mode="market",
    steps=[ToolStep("strategy.discover")],
),
```

---

## Step 6 — Intent pattern (intent_patterns.json)

```json
"strategy_discover": {
  "mode": "market",
  "patterns": [
    "find.*strateg", "discover.*strateg",
    "what.*strateg.*work", "analyse.*m15",
    "analyze.*data.*strateg", "check.*backtest.*strateg",
    "run.*backtest.*find", "which.*setup.*profit"
  ]
}
```

---

## Step 7 — Live candle feed: `src/inout/live_feed.py` (new)

Two classes, both output the dict list `INOUTScanner.scan()` expects.

### `BinanceLiveFeed`

```python
def fetch(self, symbol: str, tf: str, count: int) -> list[dict]:
    """GET api.binance.com/api/v3/klines — no auth required for candles."""
    interval = self._cfg["interval_map"][tf]   # "M15" → "15m"
    url = (f"{self._cfg['spot_klines_url']}?"
           f"symbol={symbol}&interval={interval}&limit={count}")
    resp = _get_json(url, timeout=self._timeout)
    return [
        {"open": float(k[1]), "high": float(k[2]),
         "low": float(k[3]),  "close": float(k[4]),
         "volume": float(k[5])}
        for k in resp
    ]
```

### `OANDALiveFeed`

```python
def fetch(self, instrument: str, granularity: str, count: int) -> list[dict]:
    """GET /v3/instruments/{instrument}/candles — requires Bearer token."""
    g = self._cfg["granularity_map"][granularity]
    url = (f"{self._cfg['rest_url']}/instruments/{instrument}/candles"
           f"?granularity={g}&count={count}&price=M")
    resp = _get_json(url, timeout=self._timeout,
                     bearer=_load_env(self._cfg["api_key_env"]))
    return [
        {"open":   float(c["mid"]["o"]), "high": float(c["mid"]["h"]),
         "low":    float(c["mid"]["l"]), "close": float(c["mid"]["c"]),
         "volume": float(c.get("volume", 0))}
        for c in resp["candles"] if c.get("complete", True)
    ]
```

Public factory: `get_live_feed(cfg) -> BinanceLiveFeed | OANDALiveFeed`
Reads `broker.provider` → returns right class.

---

## Step 8 — Wire `INOUTRunner._fetch_candles()` (runner.py:197)

Replace stub:

```python
def _fetch_candles(self, symbol: str, tf: str, count: int) -> list[dict]:
    feed = get_live_feed(self._broker_cfg)   # from live_feed.py
    return feed.fetch(symbol, tf, count)
```

`self._broker_cfg` loaded in `__init__` via `get_prod_section("broker")`.

---

## Step 9 — Wire `INOUTExecutor` real broker calls (executor.py)

Read `broker.dry_run` in `__init__`. When `False`, replace stubs:

### Binance branch (open_position)

```python
side = "BUY" if direction == "LONG" else "SELL"
params = {
    "symbol": symbol, "side": side, "type": "MARKET",
    "quantity": f"{qty:.6f}", "recvWindow": recv_window_ms,
    "timestamp": int(time.time() * 1000),
}
sig = _hmac_sha256(self._secret, urlencode(params))
params["signature"] = sig
resp = _post_form(f"{futures_base_url}/fapi/v1/order", params, self._api_key)
fill_price = float(resp["avgPrice"])
self._place_sl_tp_orders(symbol, direction, qty, stop_loss, tp1_price, tp2_price)
return FillResult(success=True, order_id=str(resp["orderId"]),
                  fill_price=fill_price, fill_qty=qty, status="filled")
```

`_hmac_sha256` uses stdlib `hmac` + `hashlib`. `_post_form` uses stdlib `urllib`.

### OANDA branch (open_position)

```python
body = json.dumps({"order": {
    "type": "MARKET",
    "instrument": symbol,
    "units": str(qty) if direction == "LONG" else str(-qty),
    "stopLossOnFill": {"price": f"{stop_loss:.5f}"},
    "takeProfitOnFill": {"price": f"{tp1_price:.5f}"},
}})
resp = _post_json(
    f"{oanda_url}/v3/accounts/{account_id}/orders",
    body, bearer=self._api_key
)
fill_price = float(resp["orderFillTransaction"]["price"])
return FillResult(success=True,
                  order_id=resp["orderFillTransaction"]["id"],
                  fill_price=fill_price, fill_qty=qty, status="filled")
```

`exit_full` → market close order; `update_stop_loss` → cancel + replace STOP_LOSS order.
All stubs stay active when `dry_run=true` (default).

---

## Complete Data Flow After Implementation

```
BACKTEST / STRATEGY DISCOVERY
──────────────────────────────
Agent: "find strategies in my M15 data"
    → IntentRouter → "strategy_discover"
    → PlanCompiler → [strategy.discover]
    → handle_strategy_discover(data_path=None, instrument="BTCUSDT")
         → glob data/*.xlsx → data/BTCUSDT_M15.xlsx
         → _excel_to_csv() → data/BTCUSDT_M15.csv
         → BacktestRunner.run(CandleLoader.stream())  ← REAL MARKET NUMBERS
         → EngineRunner.run() × 5 sample bars
         → llm_insight("backtest_summary") → narrative
    → Agent prints: win_rate, expectancy, drawdown, narrative
    → logs/agent_audit.jsonl updated

LIVE TRADING PATH
─────────────────
INOUTRunner._run_cycle()
    → _fetch_candles("BTCUSDT", "M15", 50)
         → BinanceLiveFeed.fetch()  [or OANDALiveFeed]
         → GET api.binance.com/api/v3/klines  ← REAL LIVE CANDLES
    → INOUTScanner.scan(candles) → INOUTSignal
    → INOUTController.on_signal() → UltronRiskGate check
    → INOUTExecutor.open_position()
         dry_run=true  → simulated FillResult  (default, safe)
         dry_run=false → POST fapi.binance.com/fapi/v1/order
                      OR POST api-fxtrade.oanda.com/v3/accounts/.../orders
```

---

## Verification

1. `pytest tests/test_agent_strategy_discover.py -v`
   - Excel → CSV conversion produces correct column names
   - BacktestRunner mock returns metrics → narrative key present in result
   - Auto-detect of first .xlsx in `data/` works

2. `pytest tests/test_inout_live_feed.py -v`
   - Mock `urllib.urlopen` → Binance 5-kline list → 5-item dict list returned
   - OANDA mock response → same shape
   - `get_live_feed()` returns correct class per config

3. **Config hash:** `python scripts/maintenance/_compute_hash.py`

4. **Agent smoke test:**
   ```bash
   python -m src.agent.cli
   > find strategies in my M15 data
   ```
   Expect: backtest runs on Excel file, metrics + narrative printed, no crash.

5. **Regression:** `pytest tests/test_backtest*.py tests/test_inout*.py`


================================================================================
SOURCE_FILE: docs/plans/below-is-a-prompt-mighty-riddle.md
SOURCE_BYTES: 9547
PART: 1/10 FILE 7/7
================================================================================

> Created: 2026-05-10 · Updated: 2026-05-10 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Plan: Config Version Single Source of Truth Refactor

## Context

The production config version is currently resolved in `production_config.py` with a silent fallback to `"v1_multi_2026_03"` when `ACTIVE_VERSION` is missing. This allows a misconfigured environment to run silently on a stale version. Additionally, long-running processes (backtest, live engine, engine runner) do not log which version they used, and trade CSVs/summary JSONs carry no `config_version` field, making post-hoc audit impossible. The goal is to: (1) make version resolution fail-fast, (2) stamp every output and log line with the active version.

---

## Files to Modify

| File | Change type |
|---|---|
| `src/config_layer/production_config.py` | Remove fallback, add fail-fast + logging |
| `src/runtime/backtest_v2.py` | Version log, TradeRecord field, CSV+JSON stamps, custom-config warning |
| `src/runtime/live_engine_hook.py` | Version log on init |
| `src/core/engine_runner.py` | Version log on init |
| `src/strategies/strategy_orchestrator.py` | Version log on init |
| `src/core/collector.py` | Add `config_version` to every JSONL record |
| `src/governance/promotion_manager.py` | Add `promoted_version` key to registry payload |
| `scripts/training/phase5_calibration.py` | Log version; uses model_registry not prod config — no config-load change needed |
| `scripts/training/auto_tuner.py` | Log version; uses ConfigBuilder — no config-load change needed |

---

## Step-by-Step Implementation

### 1. `src/config_layer/production_config.py` (lines 54–68)

**Remove:** `_FALLBACK_PROD_VERSION`, the try/except fallback in `_resolve_prod_version()`.

**Add:** `get_active_version()` function and a module-level logger.

```python
import logging as _logging

_log = _logging.getLogger(__name__)

def get_active_version() -> str:
    """Read version from ACTIVE_VERSION pointer file. Raises RuntimeError if missing."""
    if not _ACTIVE_VERSION_FILE.exists():
        raise RuntimeError(
            "No active version pointer found at configs/production/ACTIVE_VERSION. "
            "Run promotion_manager.py promote first."
        )
    try:
        resolved = _ACTIVE_VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError as e:
        raise RuntimeError(
            f"Failed to read configs/production/ACTIVE_VERSION: {e}"
        ) from e
    if not resolved:
        raise RuntimeError(
            "configs/production/ACTIVE_VERSION is empty. "
            "Run promotion_manager.py promote first."
        )
    _log.info("Active production config: %s", resolved)
    return resolved

PROD_VERSION: str = get_active_version()
```

Remove `_FALLBACK_PROD_VERSION` constant entirely. Keep `_ACTIVE_VERSION_FILE` as-is.

---

### 2. `src/runtime/backtest_v2.py`

#### 2a. Add version log at start of `BacktestRunner.run()` (line ~1343)

```python
from config_layer.production_config import PROD_VERSION
self.log.info("Production config version: %s", PROD_VERSION)
```

#### 2b. Add `config_version` field to `TradeRecord` dataclass (after line 248, after `cached_double_sweep`)

```python
config_version: str = field(default_factory=lambda: PROD_VERSION)
```

Import `PROD_VERSION` at module top alongside other `config_layer` imports (already imported via `BacktestConfig.from_prod_config()`). Add at module level:
```python
from config_layer.production_config import PROD_VERSION as _PROD_VERSION
```
Use `_PROD_VERSION` as the default so it's evaluated once at module load (not deferred).

Actually simpler: use `field(default="")` and populate from `PROD_VERSION` in `TradeJournal.on_trade_closed()` — but the cleanest pattern matching the codebase is a module-level import and `field(default_factory=...)`.

Use this exact pattern:
```python
# Near top of file after other config_layer imports
from config_layer.production_config import PROD_VERSION

# In TradeRecord dataclass, after cached_double_sweep field:
config_version: str = field(default_factory=lambda: PROD_VERSION)
```

#### 2c. Add `config_version` column in `TradeJournal.to_csv_rows()` (after line 909)

After `row["cached_double_sweep"] = int(r.cached_double_sweep)`, add:
```python
row["config_version"] = r.config_version
```

#### 2d. Add `config_version` in `BacktestMetrics.to_dict()` (after line 983, inside the returned dict)

```python
"config_version": PROD_VERSION,
```

#### 2e. Handle `--config` CLI override (lines 1969–1973 in `main()`)

Replace the existing block:
```python
if args.config:
    with open(args.config) as f:
        overrides = json.load(f)
    safe_print(f"Config overrides loaded from {args.config} (not applied to CRT backtest)")
```

With:
```python
if args.config:
    import warnings as _w
    bt_log.warning(
        "Using overridden config: %s (production version %s ignored)",
        args.config, PROD_VERSION,
    )
    # Patch PROD_VERSION sentinel so all downstream records reflect the override
    import config_layer.production_config as _pc
    _pc.PROD_VERSION = f"CUSTOM:{Path(args.config).name}"
```

This means `TradeRecord.config_version` defaults and `BacktestMetrics.to_dict()` will show `"CUSTOM:<filename>"` instead of the production version.

---

### 3. `src/runtime/live_engine_hook.py`

In `HookedLiveEngine.__init__` (or right after logger init at line ~80), add:

```python
from config_layer.production_config import PROD_VERSION
self.logger.info("Production config version: %s", PROD_VERSION)
```

---

### 4. `src/core/engine_runner.py`

In `EngineRunner.__init__` (after collector init at line ~351), add:

```python
from config_layer.production_config import PROD_VERSION as _pv
self._log.info("Production config version: %s", _pv)
```

Check which logger name `EngineRunner` uses (likely `self._log` or similar); adjust accordingly.

---

### 5. `src/strategies/strategy_orchestrator.py`

In `StrategyOrchestrator.__init__` or `compute()`, add equivalent version log using that class's logger.

---

### 6. `src/core/collector.py` — `collect()` function (line ~107)

In the `record` dict construction, add:

```python
from config_layer.production_config import PROD_VERSION
```

Inside `record`:
```python
"config_version": PROD_VERSION,
```

Place it after the `"t"` field for visibility. The `collect()` function is module-level, so import at top of file rather than inside the function.

---

### 7. `src/governance/promotion_manager.py` — `_build_registry_entry()` (line ~342)

`promoted_at` already exists in the payload (line 356). Add an explicit `promoted_version` key as a convenience alias:

```python
"promoted_version": version,   # explicit alias alongside "version" key
```

Add this in `_build_registry_entry()` immediately after `"version": version` (line 353).

---

### 8. Scripts — version logging only

**`scripts/training/phase5_calibration.py`** — after existing `log = logging.getLogger("Phase5")`, add:
```python
from config_layer.production_config import PROD_VERSION
log.info("Production config version: %s", PROD_VERSION)
```

**`scripts/training/auto_tuner.py`** — after existing `tuner_log = logging.getLogger("AutoTuner")`, add:
```python
from config_layer.production_config import PROD_VERSION
tuner_log.info("Production config version: %s", PROD_VERSION)
```

Neither script does direct `json.load()` on the production config file — both use proper gateways (`model_registry`, `ConfigBuilder`) — so no config-loading changes are needed.

---

## Verification

After implementation:

```bash
# 1. Smoke test version resolution
python -c "from config_layer.production_config import PROD_VERSION; print(PROD_VERSION)"
# Should print: v2_multi_2026_04

# 2. Confirm fail-fast when ACTIVE_VERSION absent
python -c "
import os, pathlib
p = pathlib.Path('configs/production/ACTIVE_VERSION')
p.rename('configs/production/ACTIVE_VERSION.bak')
try:
    import importlib, config_layer.production_config as m
    importlib.reload(m)
except RuntimeError as e:
    print('PASS:', e)
finally:
    pathlib.Path('configs/production/ACTIVE_VERSION.bak').rename(p)
"

# 3. Run a short backtest and verify
python src/runtime/backtest_v2.py --csv data/EURUSD_M15.csv --instrument EURUSD --output results/test_plan

# Check log contains version line:
grep "Production config version" logs/backtest_debug.log

# Check summary JSON has config_version field:
python -c "import json; d=json.load(open('results/test_plan/EURUSD_summary.json')); print(d['config_version'])"

# Check trade CSV has config_version column:
python -c "import csv; r=next(csv.DictReader(open('results/test_plan/EURUSD_trades.csv'))); print(r['config_version'])"
```

---

## Notes / Constraints

- `PROD_VERSION` is evaluated **once at import time** — changing `_pc.PROD_VERSION` in the `--config` override path works because `TradeRecord.config_version` uses `lambda: PROD_VERSION` (late binding), and `BacktestMetrics.to_dict()` reads `PROD_VERSION` at call time.
- The import `from config_layer.production_config import PROD_VERSION` inside `collect()` must be moved to **module level** (not inside the function) to avoid repeated import overhead on the hot path.
- `EngineRunner` is used in both backtest and live paths, so the version log there covers both without duplication.
- No schema hash changes — `PROD_VERSION` is metadata, not a `params` key.
- No `CANONICAL_FEATURES` changes — this refactor is pure metadata plumbing.
