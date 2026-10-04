# CRTStateResolver vs BacktestRunner — Economic Comparison (XAUUSD M15)

## Context

F-069 (previous program, complete and committed as `03c3dbf`) established that `CRTStateResolver`
cannot semantically reproduce `BacktestRunner` through configuration alone (88.16% agreement,
structurally config-unreachable EXPANSION-entry gap). The user now asks the natural follow-up:
**"which one is giving better results — run the latest report on MT5 XAUUSD and share it."**

Clarified with the user: "better results" can't mean trading performance for the resolver as-is,
because `CRTStateResolver` has no execution authority at all — it is a research-shadow classifier,
never a trading model (§6.5 Authority Ladder, CLAUDE.md). Confirmed deductively, not just
empirically: `_continuous_gates_pass`'s EXECUTION branch (`src/features/crt_state_resolver.py`)
requires a `score`/`risk_score`/`crt_score` feature absent from `CANONICAL_FEATURES`
(`src/features/feature_schema.py`) — resolver EXECUTION count is 0 in every measurement taken this
session (baseline, all 33 F-069 sweep candidates, Stage B). So a strict "same trigger rule"
comparison is a foregone conclusion before any code runs.

The user chose to proceed anyway with a **relaxed-trigger simulation**: trade the resolver's
**EXPANSION-entry** transitions (its most-populated non-trivial state) instead of EXECUTION,
explicitly as a *different* rule from the engine's own — not a replay of the same strategy — and
compare the resulting economics (win rate, PF, expectancy, drawdown) against the engine's real
trades on the same corpus. The goal is an honest, decisive answer the user can act on, not a
technically-correct-but-hollow "0 vs 1" restatement of the structural fact.

**Verified this session, foundational to the design:**
- Both existing `BacktestRunner` runs on this corpus (`results/run_20260805_105350_XAUUSD/` and
  `results/run_20260724_104845_XAUUSD/`) produce **exactly 1 real trade each** (`wc -l` = 2
  including header). The newer run's engine code/config predate its own run timestamp
  (`crt_engine_v2.py` 10:34:48 < run 10:53:50; `v2_multi_2026_04.json` Aug 2, well before) — it is
  current, trustworthy ground truth; **no fresh BacktestRunner run is needed.**
- A concurrent session's descriptive doc, `reports/crt_state_resolver_vs_backtest_runner_report.md`
  (correctly cites F-069's semantic-parity numbers), contains a **fabricated worked example**
  (entry=2352.10, sl=2350.21) that does **not** match the real trade row
  (`entry_raw=2318.21, sl=2317.4565714285714, direction=LONG, pnl_rr_net=-0.0383`, confirmed by
  reading the CSV directly). The new report must read the CSV directly and must not cite that doc's
  numbers.
- My original assumption that `BacktestRunner` uses `ExecutionPlannerV1_2`/`UltronRiskGate` was
  **wrong** — verified by direct grep: both classes are used only by the separate live-trading path
  (`src/runtime/live_engine_hook.py`) and are never imported by `backtest_v2.py`.
  `ExecutionPlannerV1_2` explicitly disclaims SL/TP in its own docstring and a self-test assertion.
  The real trade builder is `ExecutionEngine.build_trade()` in `src/config_layer/crt_engine_v2.py`.
- `CRTStateMemory.displacement_direction` (`crt_state_resolver.py:125`, set at DISPLACEMENT/SWEEP
  entry, carried into EXPANSION) is the principled, already-tracked direction source for the
  resolver arm — no new direction-inference rule needs to be invented.

## Design

### New script: `scripts/research/crt_resolver_economic_comparison.py`

Follows the established F-069 probe convention exactly (READ-ONLY docstring stating the trigger-rule
divergence up front, `_ROOT`/`sys.path` shim, `CERT_VERSION`, prediction-before-results discipline).

**Engine-side ledger** — `resolve_engine_ledger()`: reads
`results/run_20260805_105350_XAUUSD/XAUUSD_trades.csv` directly (default; `--force-fresh-run` escape
hatch re-runs `BacktestRunner` via the `detection_sweep.py:71-79` idiom
`ConfigBuilder.build("XAUUSD")` → `BacktestConfig.from_prod_config(...)` → `CandleLoader` →
`BacktestRunner(...).run(...)` if ever needed). No metric reinvention — the CSV's `pnl_rr_net` is
the engine's own already-costed truth.

**Resolver-side EXPANSION-entry adapter** — `CRTStateExpansionSignalSource`, following
`src/research/adapters/shape_signal_source.py`'s `_compute()` pattern (the closest existing
precedent for turning a bar-by-bar classifier into a signal source). Reuses
`scripts/research/crt_state_confusion_matrix.py::build_resolver_timeline`/`compute_enriched_frame`
for the resolver drive rather than reimplementing it, but must capture `resolver.memory` snapshots
per bar (needed for `displacement_direction` + `displacement_candle_index`), which
`build_resolver_timeline` doesn't expose — a short, locally-scoped per-bar loop mirroring it, with a
comment citing why. Detects **entry transitions** (`states[i]=="EXPANSION" and states[i-1]!=
"EXPANSION"`), not occupancy. SL mirrors the engine's shape — `disp_low - sl_atr_buffer*atr` (LONG)
— reading `sl_atr_buffer`/`tp1_atr_multiplier` from `ConfigBuilder.build("XAUUSD")` at runtime, never
hardcoded, so a future config change can't silently desync this script from the engine. TP is a
**single flat TP1 multiplier only** (no per-intent classification, no TP1-partial/breakeven-trail/TP2
two-leg structure) — an explicit, stated simplification, not an attempt at a byte-exact replay. Bars
with `displacement_direction == 0` (undetermined) or an inverted SL are **skipped and counted**, never
defaulted to a guessed direction.

**Measurement** — reuses existing, tested machinery, no reinvention:
- `src/research/measurement/forward_walk.py::forward_walk(signal, future, exit_model=
  "intrabar_fixed")` for the resolver arm, using the `atr=1.0` raw-price-distance trick already
  established by `src/research/adapters/spine_signal_source.py` (set `sl_atr_mult`/`tp_atr_mult` to
  the actual price distances, `atr=1.0`, so `Signal`'s ATR-multiple contract carries exact prices).
- `src/research/measurement/metrics.py::EdgeAggregator.aggregate(...)` for both arms — same
  win/PF/expectancy formulas as the engine's own (`net_rr > 0` convention matches), applied
  identically so the comparison table is apples-to-apples on the *math*, with cost-model choice
  stated explicitly (native engine cost vs. flat 12bps `DEFAULT_COST_MODEL` — report both, don't
  silently blend).
- `src/research/measurement/bootstrap.py::bootstrap_ci(...)` per arm on the mean net-R, deterministic
  seed shared across both arms. `n==1` (engine side) returns `(v, v)` by the module's own design —
  marked `"ci_degenerate": True"` in the report, not hidden.
- **Explicitly skip `src/research/qualification.py`'s full M4 gate** — its `min_samples`/OOS-split/
  permutation/BH-FDR machinery is built for multi-hypothesis discovery search, not a two-arm
  structural comparison, and would fail outright at n=1 in a way that misrepresents "no gate passed"
  as "rejected" rather than the true "insufficient data to gate at all."

### Report (`reports/crt_resolver_economic_comparison.md`)

Methodology-before-results structure (the pre-registration discipline, satisfied inline since the
script's logic is fixed code run once, not tuned after seeing numbers):
1. **Trigger rule stated for each arm** — engine = native EXECUTION branch (the real production
   rule); resolver = EXPANSION-entry, explicitly flagged as a *different, relaxed* rule, with the
   F-069 citation for why EXECUTION-triggered resolver trades are structurally impossible.
2. **SL/TP construction + simplifications stated** for each arm.
3. **Cost model choice stated** — both native and flat-12bps columns, not blended.
4. **Provenance** — which run directory was used and why, corpus path, resolver config state
   (current committed `market_crt_states.yaml`, untouched for this comparison).
5. **Comparison table**: n, wins, losses, win rate, PF, expectancy, max drawdown, bootstrap 95% CI,
   skip/reject counters.
6. **Epistemic Integrity caveat (Program E-001)** — explicit "INSUFFICIENT, no economic conclusion
   derivable at this sample size" framing for both arms (`MIN_CELL_N` precedent), stating plainly
   that the only decisive, non-statistical finding is structural: the engine can trade under its own
   rule and the resolver's native rule cannot, full stop — anything beyond that is illustrative, not
   a finding either direction.
7. **A note correcting the record** on the concurrent doc's fabricated worked-example numbers, so a
   future reader doesn't cite them as real.
8. **Authority footer** — grants no authority to modify resolver/engine/config regardless of outcome.

### Tests (`tests/research/test_crt_resolver_economic_comparison.py`)

Same `importlib.util.spec_from_file_location` + `sys.modules[name]=mod`-before-`exec_module` pattern
used throughout F-069's test files (proven working this session). Assertions on concrete values, not
just "no exception" (E-001 discipline):
- Entry-transition detector fires on transitions, not occupancy (synthetic state list).
- Direction inference is deterministic and correctly skips `displacement_direction==0`.
- SL construction matches the engine's formula byte-for-byte on a hand-built synthetic bar.
- Inverted-SL bars are rejected and counted, never silently kept.
- The real trades CSV parses to the expected concrete row (skip-if-absent fixture).
- `n=1` bootstrap CI returns a degenerate `(v, v)` and is marked as such in the output.
- Report generation places the methodology section before the comparison table.

### SITS registration (same turn)

`script_census.py --write-stubs` → overlay in `scripts/governance/seed_script_registry.py`
(category `RESEARCH_RUNNER`, `ttl_days=90`, `task_refs=["F-069","SITS"]`, purpose citing the
relaxed-trigger caveat) → `seed_script_registry.py` → `generate_script_matrix.py` →
`query_scripts.py --validate`.

### Explicitly out of scope (agreed)

No per-intent TP classification for the resolver arm (no `cached_features` equivalent in resolver
memory). No TP1-partial/breakeven-trail/TP2 replication. No M4 QualificationGate routing. No
modification to `CRTStateResolver` (re-derive displacement candle OHLC via raw row lookup instead).
No fresh `BacktestRunner` run unless the existing one proves stale (it doesn't). No promotion or
production-config change of any kind, regardless of the result.

## Verification

1. `pytest tests/research/test_crt_resolver_economic_comparison.py` — all pass, including the
   byte-for-byte SL formula check and the transition-vs-occupancy check.
2. Run `python scripts/research/crt_resolver_economic_comparison.py` — confirm it completes, emits
   both `results/analysis/crt_resolver_economic_comparison.LATEST.json` and
   `reports/crt_resolver_economic_comparison.md`, and the resolver arm's skip/reject counters plus
   engine arm's n=1 are visible and explained, not hidden.
2b. Sanity-check the resolver arm's trade count is in a plausible range given ~1,500-4,600 EXPANSION
    bars but far fewer *entry transitions* (sticky-dwell collapses many bars into one entry) —
    flag if it comes out at 0 or absurdly high before trusting the comparison table.
3. `python scripts/governance/query_scripts.py --validate` exits clean after SITS registration.
4. Read the generated report end-to-end for internal consistency (methodology matches what the code
   actually did; no leftover reference to the concurrent doc's fabricated numbers).
5. `SendUserFile` the finished `reports/crt_resolver_economic_comparison.md` to the user, with a
   short chat summary stating the headline structural fact first (engine can trade, resolver's
   native rule cannot) before the illustrative relaxed-trigger numbers.

## Out of scope

No changes to `src/features/crt_state_resolver.py`, `src/config_layer/crt_engine_v2.py`, or any
production config. No commit unless the user asks, matching this session's established convention.
