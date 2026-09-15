# Sealed-Contract Kit (`research.mc_kit`) — design, outcome, ROI

## Context

**Where we are.** Research-framework consolidation Phases 0–2 shipped (uncommitted; `.git/index.lock` untouched
per user): archive ledger + verifier, provenance-helper dedup (55 files), `research.qualify_matrix` (11 files).
Phase 2 measured a hard ceiling: the rest of the QUALIFY drivers is genuinely unique per program, so further
shrink needs **new shared logic**, which the consolidation rule forbade.

**User decision (2026-09-14).** New shared logic is allowed *if it moves the goal*; behavior must still never
change; know the outcome and ROI first. Two candidates were measured; user chose **B**:

| | A: QUALIFY scope runner | **B: sealed-contract kit (chosen)** |
|---|---|---|
| Serves | closed Programs 1–8 (F-019…F-043) | the active frontier (F-086…F-097: MC-* contracts) |
| Proof of "no behavior change" | synthetic only — 38/39 corpora clock-UNREVIEWED | **real**: every target reads `data/mt5/XAUUSD_M15.csv` (the 1 reviewed corpus) and 7 contracts have committed output artifacts to byte-compare |
| Size | −250…−400 lines | ≈ −250…−300 lines net (see ROI) |
| Future cost per research question | unchanged (nobody writes new QUALIFY drivers) | **≈ 60–120 lines instead of 260–450** |

**Why B serves the goal (CLAUDE.md §6.1 / F-001).** F-001: the binding constraint is throughput/governance,
not intelligence. Every new MC contract today is a hand-written 250–450-line driver that re-implements split,
embargo, purge, controls, gate and artifact writing — and that re-implementation is exactly where F-083 happened
(a sealed contract declared OOS + controls the driver never executed). A kit makes the next falsification
cheaper **and** makes the governed steps the default instead of something each author must remember.

## What the measurement found (evidence for the design)

Active pattern = two shapes, all on XAUUSD M15:

- **Trade contracts** — `src/research/mother_range/driver.py` (263), `src/research/sujan_crt/driver.py` (452):
  `validate_dataset → load_bars → detect candidates → split → Signal(entry/stop/target) → forward_walk +
  AdverseFill → ComponentCostModel.net_rr(exit_kind, direction) → stats → controls → gate/verdict →
  metrics.json / ledger.jsonl / split_manifest.json / report.md`. Only candidate detection is research-specific.
- **Prior contracts** — `src/research/evidence/{asymmetry_contract,magnitude_prior,rnet_overlay,mother_range_prior,visual_crt_prior}.py`
  (~1,300 lines): `unit rows (label join by (ts, side)) → timestamp split with embargo/purge → agree/disagree
  arm cells → sign-keeping verdict → fingerprint → artifacts → finalize_run`.

Exact duplicates found (AST fingerprint): `_stats` (MR nested ≡ SUJ), `_walk` c7be2db92a ×2, `load_bars`
df0a572077 ×2, `_parse_ts` 9cb6fe78b0 ×2, `verdict` ebffb2c684 ×3, `_arm_cells` 1a7aa4e6f6 ×2, `_sign` ×2,
`run` bodies ×2 (two pairs), the F-082 `_XAU_COST` ComponentCostModel literal ×2 in `src/`.

**Behavioral differences that must stay explicit, never unified silently** (each becomes a named parameter;
recorded, not fixed):
1. long_only control compares **gross** mean (mother_range) vs **net** mean (sujan_crt).
2. `tp_atr_mult = reward/risk` unguarded (MR, raises on risk=0) vs `if risk else 1.0` (SUJ).
3. `volume` required (MR, KeyError) vs `row.get("volume") or 0.0` (SUJ).
4. corpus sha hardcoded constant (MR) vs computed (SUJ).
5. Split schemes: timestamp holdout + one-open suppression (MR); index-fraction 0.75 + embargo + purge (SUJ);
   timestamp + embargo/purge window drop (priors).
6. Verdict vocabulary: `DIAGNOSTIC_PASS_NOT_ECONOMIC` (trade) vs `DIAGNOSTIC_PASS` / `DIAGNOSTIC_FAIL` (priors).
7. Trade drivers do NOT call `finalize_run` (no mt00/mt01/run_manifest); priors do. Adding it = new artifacts =
   behavior change → separate, user-gated item, not part of this work.
8. JSON serialization differs (`indent=2`, `default=str`, insertion-ordered keys) — byte identity depends on it.

Reuse, not rebuild: `research.evidence.run_close_out.finalize_run`, `research.measurement.forward_walk`
(`forward_walk`, `AdverseFill`), `research.costs.ComponentCostModel`, `research.contracts.Signal`,
`data_ingestion.dataset_integrity.validate_dataset`, `research.provenance.sha256_file` (Phase 1),
`research.measurement.mt00` (reads the artifact names — they are contractual).

## Design: `src/research/mc_kit/` (name verified collision-free)

Composable primitives, each reproducing an existing variant exactly; the variant is an explicit argument.
No monolithic runner is forced on existing drivers.

| Module | Functions | Absorbs |
|---|---|---|
| `bars.py` | `parse_ts_iso19(raw)`, `load_bars(path, bar_cls, *, parse_ts, volume: Literal["required","zero_default"])` | MR/SUJ/mrprior `load_bars`, `_parse_ts` |
| `trade.py` | `signal_from_levels(..., zero_risk: Literal["raise","tp_mult_1"])`, `walk_horizon(sig, bars, horizon, adverse, exit_model="intrabar_fixed")`, `exit_kind(outcome)`, `net_r(cost, rr, entry, risk, outcome, direction)` | `_signal`, `_walk`, inline exit-kind + netting |
| `stats.py` | `trade_stats(rows)`, `lag1_corr`, `effective_n`, `sign`, `arm_cells(rows, y_key)`, `sign_keeping_verdict(train_c, hold_c, min_n=30)` | `_stats`, SUJ autocorr helpers, prior `_sign`/`_arm_cells`/`verdict` |
| `splits.py` | `fraction_boundary(n_bars, frac, embargo, horizon)` → classifier + base manifest; `timestamp_embargo_purge(rows, holdout_start, embargo_bars, horizon_bars, bar_minutes)` → (train, hold, base manifest) | SUJ split/purge; prior `split_rows` (contract-specific manifest flags merged by caller, key order preserved) |
| `controls.py` | `long_only(templates, bars, walk, cost, basis: Literal["gross","net"])`, `random_entry(templates, eligible, n_seeds, base_seed, …)`, `matched_sample(pool, n, seed)` | MR/SUJ control loops |
| `gate.py` | `verdict_from_gate(n, checks, required, *, min_n=30, pass_label, fail_label="REJECT")` | MR/SUJ gate→verdict |
| `artifacts.py` | `write_json(path, obj, *, indent=2, default=None, sort_keys=False)`, `write_ledger_jsonl(path, rows)` | the metrics/ledger/split/fingerprint writes |
| `spec.py` | `TradeContractSpec` (frozen: contract_id, sem_id, corpus, instrument, horizon, split, cost, adverse, controls, gate) + `run_trade_contract(spec, detect, row_extra)` | the template a NEW trade contract uses |
| `research/costs.py` (extend) | `xau_measured_cost_model()` returning the F-082 literal | the duplicated `_XAU_COST` block |

## Execution (each step archived via `archive_manifest.snapshot()`, batch dirs `research_framework_phase3*_2026-09-14`)

**Step 0 — Baseline reproduction (read-only gate, decides scope).** On the current tree, re-run each of the 7
contracts that have committed artifacts (`docs/research-readiness/{sujan_crt, mother_range…, asymmetry,
magnitude_prior, rnet_overlay, mother_range_prior, visual_crt_prior}`) into a scratch dir; byte-compare
`metrics.json` / `ledger.jsonl` / `split_manifest.json` / `population_fingerprint.json` to the committed files;
record wall time. **A contract that does not reproduce BEFORE any edit is excluded** (reported as its own
drift, not fixed). **Kill criterion:** fewer than 3 reproduce → stop, report ROI as unverifiable.

**Step 1 — Build `mc_kit` primitives + parity floor.** `tests/research/test_mc_kit.py` pins every primitive
against verbatim copies of every variant it absorbs (same method as `test_provenance_helpers.py` /
`test_qualify_matrix.py`), including the 8 explicit differences above.

**Step 2 — Migrate trade contracts, one at a time** (`mother_range`, then `sujan_crt`): replace inline code with
primitives, keeping each driver's own choices; re-run; byte-identical to Step-0 outputs or revert that file.

**Step 3 — Migrate priors** (`mother_range_prior`, `visual_crt_prior`, `magnitude_prior`, `rnet_overlay`,
`asymmetry_contract`), same gate.

**Step 4 — Prove the template.** Acceptance test re-expresses `mother_range` purely as
`TradeContractSpec + detect_inside_close_entries` via `run_trade_contract` and must reproduce its committed
`metrics.json` byte-identically. This is the evidence that "next contract = spec + detector" is real, not a claim.

**Step 5 — Record ROI with numbers**: lines before/after per file; line count of the Step-4 spec re-expression
(= measured marginal cost of a new contract); SESSION LOG entry; memory update.

Out of scope (different shape, left local): `visual_crt/driver.py` + its `controls.py`/`measure.py`,
`context_attribution.py` (stratified permutation + BH), `rc003_distinct_object`. Behavioral fixes for
differences 1–8 are **not** made — listed for a user decision.

## Expected outcome and ROI

| Dimension | Estimate | How it will be measured |
|---|---|---|
| Size | ≈ −600 lines removed from ~2,010 in scope; kit ≈ +300–350 → **net ≈ −250…−300** | Step 5 line counts |
| Marginal cost of next trade contract | **≈ 60–120 lines** (detector already separate) vs 263–452 today, ≈ 70% less | Step 4 spec re-expression line count |
| Governance | split/embargo/purge/controls executed by default — closes the F-083 recurrence path for new contracts | Step 4 test + kit tests |
| Knowledge | 8 cross-contract inconsistencies made explicit (e.g. gross vs net long_only baseline) | recorded in plan/ledger; user decides fixes |
| Economic authority | **none** — no new result, no G001 claim (§6.5) | — |
| Risk | low: byte-identity on real reviewed corpus + committed artifacts; per-file revert | Step 0/2/3 gates |
| Cost | ~1 working session; Step 0 may be slow (SUJ `_atr_series` recomputes ATR over growing slices; 100-seed random control) | Step 0 wall time |

Honest caveat: **size ROI is modest**; the payoff is research throughput and fewer silent gaps, not line count.

## Verification

1. Step 0 table: 7 contracts × {reproduces?, wall time} before any edit.
2. `venv\Scripts\python.exe -m pytest tests/research/test_mc_kit.py tests/research/test_mother_range_prior.py tests/research/test_visual_crt_prior.py -q`
   plus existing sujan/mother_range tests.
3. Per migrated contract: SHA-256 of each artifact after == Step-0 committed baseline.
4. Step 4 acceptance test green.
5. `python scripts/maintenance/verify_archive_manifests.py` → 0 violations.
6. `python scripts/maintenance/check_governance_invariants.py --all` → failure set identical by test id to the
   post-Phase-2 run (12 failed / 567 passed).
7. `python -m research.measurement.mt00`-based probes still pass for contracts whose artifacts are unchanged.

## Standing constraints

No deletes; `.git/index.lock` untouched; no commits until the lock clears; no research configs, sealed MC
instances, corpora, or findings edited; no clock-review actions.
