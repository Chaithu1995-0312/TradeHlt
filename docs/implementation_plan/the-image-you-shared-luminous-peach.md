# Program 4b — Forward Markov Regime-Transition Forecast (crypto majors)

## Context

Program 8 (weekly CRT sweep) is closed (F-042, 0 PROMOTE). You asked to move next to "Program
4b: Transition Forecast," which I initially recommended from the Funding Ledger without
verifying its true status. Investigation surfaced a real doc-staleness issue worth stating
plainly before planning the build:

- The Funding Ledger's **"Program 4b: ... Regime TRANSITION Forecast (forward Markov P^H) —
  RESEARCH (pre-registration pending)"** entry (`docs/current-findings.md`, dated 2026-06-17)
  describes a **literal Markov transition-probability forecast** —
  `docs/research-readiness/program-4b-transition-preregistration.md` — whose own §8 build
  checklist says "a future session — NOT done here."
- **F-040** (2026-06-26, "Program 4 CLOSED") tested a **different construction** — an MTF
  candle-state conjunction (`docs/research/preregistration-program-4bcd.md`,
  `compression_breakout.py`) — and closed a differently-scoped "4b/4c/4d" grouping.
- These are **not the same hypothesis**: one is a literal trailing Markov `P_t^H`
  transition-matrix projection; the other is a compression→expansion conjunction test. The
  Markov-P^H construction was genuinely never built. The stale ledger entry needs a doc fix
  regardless of which way this new run resolves (§6.2 DOC_DRIFT, unambiguous, auto-fixable).
- The pre-registration reserves finding number **"F-031"** for the result — but F-031 has
  since been consumed by an unrelated governance finding. The real result will be **F-043**
  (next free after this session's own F-042).
- **Pre-registered economic prior** (stated before running, per E-001): F-040 already
  established that a related transition channel is informative but economically
  non-consumable because *"the binding constraint is the EXECUTION MODEL (spot long/short
  cannot express a long-vol payoff), not predictability."* Program 4b targets the same
  category of thing (anticipating a volatility-regime change) in the same spot-directional
  architecture, so the reasonable prior is it hits the same wall — expect
  `REGIME_INFORMATIONAL` / `REGIME_HARMFUL` / `REGIME_INSUFFICIENT` at best, not
  `REGIME_EXPLOITABLE`. This is recorded now, not after seeing results.

The pre-registration's design is **frozen** (§5, "changing any after a null is forbidden
archaeology") — this plan implements it as specified, it does not redesign it.

## What already exists and will be reused verbatim

| Concern | File:line |
|---|---|
| `RegimeLabeler` (current-level S_t, trailing terciles) | `src/interpreters/regime_observer.py:40-91` — reused AS-IS for the current-level series (both the calibration input and the new within-tercile-shuffle's stratifying key) |
| `regime_conditioning.evaluate_scope` (3×3 cross-matrix, M4 gate, BH, verdict rollup) | `src/research/regime_conditioning.py:238-395` — reused verbatim for the core gate; extended ADDITIVELY (see below), never behavior-changed for existing callers |
| `RegimeConfig` | `src/research/regime_conditioning.py:51-76` — reused as-is; `lag_k=8` set via config, no code change needed |
| `characterize()` / `ProcessManifest.hurst_atr` / `thesis_flags.volatility_persistent` | `src/research/process_characterization.py:238-310` — reused verbatim for the calibration gate |
| Program 4's toy consumers | `expansion_breakout`, `mean_reversion` (registered hypotheses) — **reused, NOT `compression_breakout`** (that belongs to the separate, already-closed F-040/candle-state pipeline — using it here would silently retest F-040's question under Program 4b's name) |
| Program 4's spine family | `configs/research/research_config_spine_majors.json`, consumer `spine` — reused verbatim, same as Program 4's driver |
| Driver structure to mirror | `scripts/research/qualify_regime_conditioning.py` (full file) — copy structure, not modify |
| Config structure to mirror | `configs/research/research_config_regime.json` — copy `harness`/`forward_walk`/`signal`/`costs`/`qualification`/`universe`/`regime` blocks verbatim |
| Falsification controls, `HypothesisRunner`, `QualConfig`, `benjamini_hochberg` | unchanged, same imports as the existing driver |
| No-lookahead test pattern to extend | `tests/test_regime_observer.py:53-71` (`test_no_lookahead_truncation_stable`, `test_no_global_rank_leak`) |
| Determinism/verdict test pattern to extend | `tests/test_regime_conditioning.py:58-76` (`_QCFG`/`_RCFG` fixtures, `_edge_scenario`/`_noise_scenario` planted-edge pattern) |

## Implementation steps

### 1. `MarkovRegimeForecaster` — the only genuinely new statistical engine
New class in `src/interpreters/regime_observer.py` (additive; `RegimeLabeler` untouched):
- Constructor: `atr_period` (reuse `RegimeLabeler`'s, default 14), `tercile_window` (480),
  `w_markov` (trailing transition-count window, 480), `h` (forecast horizon, 8). No config
  reads — constructor args only, mirroring `RegimeLabeler`.
- `forecast_series(candles) -> list[str | None]`: for each bar `t`, build the trailing
  transition-count matrix over the last `w_markov` **completed** transitions `τ→τ+1` with
  `τ+1 ≤ t` (using `RegimeLabeler.label_series(candles)` internally for `S_t`, reused
  verbatim — never reimplemented), row-normalize (rows with zero occurrences → uniform
  `[1/3,1/3,1/3]`), raise to the `h`-th power (`numpy.linalg.matrix_power`), project the
  current one-hot state `v_t`, and take `argmax` as `Ŝ_{t+h}` (confidence = `max` of the
  projected vector, exposed via a companion `confidence_series()` for diagnostics — not
  required by the gate). Returns `None` wherever the underlying `S_t` series is `None`
  (warmup) or the trailing transition window isn't yet full.
- **Docstring must state explicitly:** `forecast_series[t]` is the prediction MADE AT bar
  `t` for `t+h`, using only data through `t` — never the realized regime at `t+h`. This is
  the load-bearing no-lookahead property; the output is a drop-in replacement for
  `RegimeLabeler.label_series()`'s shape/semantics, so it plugs into `evaluate_scope()`
  unchanged.
- Pure, deterministic (no RNG), same trailing-only discipline as `RegimeLabeler`.

### 2. Within-tercile-shuffle control (the pre-registration's "5th control")
Additive changes to `src/research/regime_conditioning.py`:
- New function `_within_tercile_relabeler(universe, current_level_series, tag)`: for each
  instrument, group `universe[inst]` positions by their **current-level** label at
  `entry_index` (looked up from `current_level_series`, i.e. `RegimeLabeler`'s S_t — NOT the
  predicted label), then seeded-shuffle the **predicted** labels within each current-level
  group (mirrors `_shuffled_relabeler`'s per-instrument seeded-shuffle pattern, stratified
  by the extra series). This destroys transition-forecast information while preserving the
  current vol level — isolating whether an apparent edge is really just the (already-closed,
  F-030) level signal reappearing.
- Extend `evaluate_scope()` and `_consumer_verdict()` with a **new optional parameter**
  (`current_level_series: dict | None = None`, default `None`). When `None` (every existing
  Program-4 call site), behavior is byte-identical to today — protected by a regression test
  (§4). When supplied (Program 4b only), compute `S_within_tercile` analogously to how
  `S_lagged` is computed today, and fold a `level_redundant` check into the SAME
  `REGIME_REDUNDANT` verdict bucket (the pre-registration reuses Program 4's exact 5-verdict
  vocabulary, §4 of the pre-reg — no 6th verdict class). Record `S_within_tercile` /
  `level_redundant` as new, purely additive fields in the per-consumer output dict (parallel
  to the existing `S_lagged`/`redundant` fields) for transparency.

### 3. Hard calibration gate (harder than Program 4's advisory-only check)
In the new driver (not touching `qualify_regime_conditioning.py`): reuse
`process_characterization.characterize()` verbatim, but **raise** (`SystemExit` or
`RuntimeError`) if BNBUSDT's `hurst_atr` falls outside `[0.855, 0.915]` or
`thesis_flags["volatility_persistent"]` is `False` — per the pre-registration's "the CLI
raises... no economic claim runs on an instrument whose vol-memory prior isn't reproduced."

### 4. New config
`configs/research/research_config_regime_transition.json` (new file): copy
`research_config_regime.json`'s `harness`/`forward_walk`/`signal`/`costs`/`qualification`/
`universe`/`regime` blocks verbatim, with `regime.lag_k` set to `8` (= H, per the
pre-registration's explicit hardening — "lag_k = forecast horizon H"). Add a new top-level
`markov` block (read directly by the driver, not by `RegimeConfig.from_dict`, same pattern as
the existing `regime` block): `{"w_markov": 480, "h": 8, "hurst_atr_center": 0.885,
"hurst_atr_tolerance": 0.03}`. `research_config_spine_majors.json` is reused unchanged for the
spine family (no new file needed there).

### 5. New driver
`scripts/research/qualify_regime_transition.py` (new file, mirrors
`qualify_regime_conditioning.py`'s structure exactly):
- Build the current-level series (`RegimeLabeler`, reused) once per instrument, AND the
  predicted series (`MarkovRegimeForecaster.forecast_series`, new) once per instrument.
- Run the hard calibration gate (step 3) before any economic evaluation; abort on failure.
- Run both families exactly like Program 4's driver (`toy`: `expansion_breakout`,
  `mean_reversion`; `spine`: `spine`), across the same `MAJORS` scope
  (`BNBUSDT, ETHUSDT, BTCUSDT, SOLUSDT` + `POOLED`), passing the **predicted** label series
  as `evaluate_scope()`'s `label_series` argument and the **current-level** series as the new
  `current_level_series` argument.
- Output: `results/research/regime_transition/qualify_regime_transition.json` (deterministic
  body, no wall-clock) + `_manifest.json` (git commit + timestamp) — same two-file convention.
- Print the calibration line + verdict table, mirroring `_print_table` in the existing driver.

### 6. Tests (new, plus one regression addition to the existing suite)
- `tests/test_markov_regime_forecaster.py`: determinism; no-lookahead truncation (`forecast_
  series[:k+1]` invariant to appended future bars — mirrors `test_no_lookahead_truncation_
  stable`/`test_no_global_rank_leak`); trailing-window-only transition counting (a completed
  transition landing after `t` must not be counted at `t`); uniform-1/3 fallback for
  zero-occurrence rows; H-step projection correctness against a small hand-computed 3-state
  matrix (verify against `numpy.linalg.matrix_power` directly, not just end-to-end).
- `tests/test_regime_conditioning.py` additions: (a) a planted LEVEL-only edge (rr depends on
  current level; the predicted label carries zero incremental information) must resolve to
  `REGIME_REDUNDANT` via the within-tercile check, not `REGIME_EXPLOITABLE` — the core
  behavioral proof that the 5th control does its job; (b) **regression test**: calling
  `evaluate_scope()` WITHOUT `current_level_series` (Program 4's original signature) produces
  byte-identical output to before this change — protects F-030's reproducibility; (c)
  determinism test extended to the new optional-parameter path.

### 7. Execution + doc fixes + findings registration
1. **Doc-drift fix (unambiguous, auto-fixable per §6.2 gate calibration):** update the stale
   Funding Ledger "Program 4b" entry (`docs/current-findings.md`, 2026-06-17) — correct the
   reserved-number reference from F-031 (superseded) and mark it as about to be resolved by
   this run.
2. Write/confirm the E-001 six-question check inline, recording the stated prior (§ above)
   BEFORE running.
3. Run `python scripts/research/qualify_regime_transition.py`; inspect the verdict JSON.
4. Register the result as **F-043** in `docs/current-findings.md`, citing the calibration
   result, per-consumer/per-scope verdicts, and the within-tercile-shuffle outcome
   specifically (whether `level_redundant` fired).
5. Finalize the Funding Ledger "Program 4b" entry with the real outcome (status +
   Reopen Conditions, same format as Program 4/6b/8's entries) and add a Scope Matrix row.
6. Add the F-043 row to `CLAUDE.md` §4 Repository Truths Index.
7. Run `tests/test_current_findings.py` + the full `tests/research/` and regime-specific
   suites to confirm no regression.

## Critical files
- `src/interpreters/regime_observer.py` (edit — additive `MarkovRegimeForecaster` class)
- `src/research/regime_conditioning.py` (edit — additive `_within_tercile_relabeler` +
  optional `current_level_series` parameter on `evaluate_scope`/`_consumer_verdict`)
- `configs/research/research_config_regime_transition.json` (new)
- `scripts/research/qualify_regime_transition.py` (new)
- `tests/test_markov_regime_forecaster.py` (new), `tests/test_regime_conditioning.py` (edit —
  additions + regression test)
- `docs/current-findings.md` (edit — new F-043 finding + Program 4b Funding Ledger fix +
  Scope Matrix row), `CLAUDE.md` §4 (edit — new F-043 row)

## Verification
1. `pytest tests/test_markov_regime_forecaster.py tests/test_regime_observer.py
   tests/test_regime_conditioning.py -v` — all green, including the new regression test
   proving Program 4's original `evaluate_scope()` behavior is unchanged.
2. `pytest tests/research/ tests/test_current_findings.py -q` — full suite unaffected.
3. `python scripts/research/qualify_regime_transition.py` — runs end-to-end (raises cleanly
   if the calibration gate fails), writes both JSON files, prints calibration + verdict
   tables, exits 0.
4. Run the driver twice; diff the two JSON bodies — must be byte-identical.
5. `pytest tests/test_current_findings.py -q` — passes after F-043 is registered.
