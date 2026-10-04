# Plan — Program 4: Non-Directional-Target Probe (regime-conditioned consumption)

## Context

A long multi-LLM debate converged on one evidence-grounded conclusion: the binding
constraint is no longer "does intelligence compound" but **"does any reachable ontology
contain a durable mechanism worth compounding."** Program 1 (next-bar direction, M15
crypto) was KILLED after four falsifications (F-019/020/021/025); Program 2 (structural
asymmetry, F-026) and Program 3 (HTF, F-027) are frozen. The user chose the highest-prior
*new ontology*: **change the target from price direction to a non-directional state**
(volatility regime / regime-transition), reusing the frozen, trusted crypto data.

The prior is strong and already measured: `process_characterization` found volatility has
memory (`H_atr=0.885`) while direction does not (`H_returns=0.527`) — but flagged that at
N≈70k *statistically significant ≠ economically exploitable*. **This probe closes exactly
that gap.**

**Key design decision (do NOT deviate):** the existing economic spine (`forward_walk` →
`EdgeAggregator` → `QualificationGate` → G001) is irreducibly directional, and a spot/no-
options system has **no standalone non-directional payoff**. Therefore we do **not** fake a
"vol direction" through `forward_walk` (rejected: conflates forecast accuracy with P&L,
violates §6.5 Authority Ladder). Instead we measure the non-directional target's *economic
value through a directional consumer*: does conditioning a directional strategy on a
forward-regime forecast produce a cell that clears the unchanged M4 gate, beating the
*unconditioned* consumer and random/shuffled-regime controls? This is informative either way.

## Scope & invariants

- **Additive, isolated, measure-only.** All new code in `src/research/` + `src/interpreters/`.
  Zero changes to the live spine, `configs/production/*`, or the directional contracts
  (`Signal`, `forward_walk`, `QualificationGate` stay byte-for-byte unchanged → reused as-is).
- **No production config hash change** (research configs live under `configs/research/`).
- **Deterministic + no-lookahead** (the two load-bearing research invariants).
- **Grants no authority** (§6.5): a positive result is *information/usefulness*, never
  production weight, until a consumer demonstrates ΔG001 in shadow.

## What is REUSED (no rebuild)

| Need | Reuse | File |
|---|---|---|
| Directional outcome measurement | `forward_walk`, `Outcome`, `EdgeAggregator`, `EdgeReport` — UNCHANGED | `src/research/measurement/forward_walk.py`, `metrics.py`, `contracts.py` |
| Gate semantics (n / E[R] / PF / OOS-retention / permutation / BH) | `QualificationGate` + `evaluate_pre_bh` / `benjamini_hochberg` / `finalize` — UNCHANGED | `src/research/qualification.py` |
| 12bps cost | `CostModel` | `src/research/costs.py` |
| Consumers | existing hypotheses `mean_reversion`, `expansion_breakout`, `spine` | `src/research/hypotheses/` |
| Vol terciles / Hurst / Markov / entropy / permutation-null | `process_characterization`, `process_diagnostics`, `conditional_entropy_grid` | `src/research/` |
| Non-directional event schema | `InterpreterEvent(kind=OBSERVATION, direction=None)` + `BaseInterpreter` validation/determinism | `src/interpreters/contract.py` |
| CLI driver pattern (pool × scope × IS/OOS × BH) | mirror of `qualify_majors.py` | `scripts/research/qualify_majors.py` |

## What is BUILT (new, additive)

1. **`src/interpreters/regime_observer.py`** — an Interpreter emitting
   `EventKind.OBSERVATION` forward-regime events `{regime∈C/N/E, transition_predicted,
   confidence}`. Forecast uses **trailing-window** vol terciles + a Markov transition step
   (reusing `process_characterization` primitives). **Critical correctness point:** must NOT
   reuse the production `volatility_regime` global-percentile rank (F-029) — that is a
   whole-series statistic and would leak the future into the forecast target. Trailing-only.

2. **`src/research/regime_conditioning.py`** — the conditioning harness (the only genuinely
   new measurement). Given a consumer's per-instrument `Outcome`s and the regime-label series,
   it partitions outcomes by **predicted regime at entry bar** and runs *each cell* through the
   unchanged `EdgeAggregator` + `QualificationGate`. Emits a per-cell report + a verdict:
   - `REGIME_EXPLOITABLE` — a cell clears M4 *and* beats the unconditioned consumer's own E[R]
     *and* beats random-regime + shuffled-regime controls (permutation-significant, BH-survived,
     OOS-retained).
   - `REGIME_INFORMATIONAL` — vol predictable but no cell yields directional consumption edge
     (the expected null given F-020; a *new* high-value negative truth).
   Controls are pre-registered: (a) random regime labels (seeded), (b) shuffled regime
   (permutation null), (c) the unconditioned consumer (must beat its *own* baseline, not just
   a random control — closes the F-020 lesson that partitions inflate at large N).

3. **`scripts/research/qualify_regime_conditioning.py`** — thin CLI orchestrator (mirrors
   `qualify_majors.py`): consumers {mean_reversion, expansion_breakout, spine} × regime
   partition × controls, across crypto majors, per-instrument + pooled, IS/OOS, BH.

4. **`configs/research/research_config_regime.json`** — reuses `ResearchConfig`; adds regime
   params (tercile-window, forecast horizon, min cell samples, transition definition).

5. **Pre-registration doc** `docs/research-readiness/program-4-nondirectional-preregistration.md`
   — hypotheses, controls, verdict criteria, Research Envelope, written **before running**
   (repo discipline, per F-027/F-026). Include the calibration step (confirm the regime
   labeler reproduces the known `H_atr` memory on BNBUSDT before trusting it).

6. **Tests** — `tests/test_regime_observer.py` (determinism, no-lookahead assertion, OBSERVATION
   schema, no global-rank leak), `tests/test_regime_conditioning.py` (byte-identical report on
   fixed input, control behavior, confirms gate reuse not reimplementation).

## Verdict logic (mechanism-grounded, not parameter search)

Pre-registered economic rationale: **vol regime governs which directional style works** (mean-
reversion in compression/ranging, breakout in expansion). So the live test is whether routing
each toy consumer to its hypothesized-favorable regime cell lifts OOS E[R] over the
unconditioned consumer. This is a *mechanism* hypothesis (one experiment), not a sweep — if
the first pre-registered cell-mapping fails its controls, **do not** grid-search regimes
(that would be Program-1-style archaeology); freeze with `REGIME_INFORMATIONAL`.

## Governance / truth-maintenance follow-through (implement phase)

- Open **Program 4** in the Funding Ledger; register new finding **F-030** in
  `docs/current-findings.md` + the Repository Truths Index in `CLAUDE.md §6.2` (both verdicts
  pre-described; fill on result). Enforced by `tests/test_current_findings.py`.
- A `REGIME_EXPLOITABLE` result unlocks **Stage 4 = Truth Half-Life** (the debate's metric,
  premature until a positive truth exists). A `REGIME_INFORMATIONAL` result extends the
  negative-space map and redirects the *next* ontology toward execution/optionality (since it
  would prove the spot long/short model — not predictability — is the binding constraint).
- §6 SESSION LOG appended; memory file (`project` type) for the F-030 outcome.

## Verification

1. **Unit/determinism:** `pytest tests/test_regime_observer.py tests/test_regime_conditioning.py`
   — must pass incl. the no-lookahead and byte-identical-report assertions.
2. **Calibration gate (in pre-reg):** run the labeler on BNBUSDT, confirm it reproduces
   `H_atr≈0.885` vol-memory before any economic claim (instrument-validity check, as F-026 did).
3. **Determinism replay:** run `qualify_regime_conditioning.py` twice on the frozen majors data
   → byte-identical report JSON (reuse the existing full-artifact determinism gate, 2 instruments).
4. **Reuse proof:** test asserts `regime_conditioning` calls the real `QualificationGate` /
   `EdgeAggregator` (not a fork) — guards against silently reimplementing the gate.
5. **Full suite:** `pytest` — no new reds beyond the known-baseline set
   (`project_test_baseline_2026_06_12`).

## Critical files

- New: `src/interpreters/regime_observer.py`, `src/research/regime_conditioning.py`,
  `scripts/research/qualify_regime_conditioning.py`, `configs/research/research_config_regime.json`,
  `docs/research-readiness/program-4-nondirectional-preregistration.md`,
  `tests/test_regime_observer.py`, `tests/test_regime_conditioning.py`
- Touched (implement phase only): `docs/current-findings.md`, `CLAUDE.md §6.2`,
  `assistant_project.md`, `src/interpreters/__init__.py` / `src/research/__init__.py` (registration).
- Reused unchanged: `src/research/measurement/forward_walk.py`, `src/research/qualification.py`,
  `src/research/metrics.py`, `src/research/costs.py`, `src/research/contracts.py`,
  `src/interpreters/contract.py`, `src/interpreters/adapter.py`.
