# Plan: Cross-Sectional Relative-Value — Program 5 (evidence-first, zero architecture)

## Context

Four advisory LLMs converged (conf 9.2–9.8) on one thesis: *architecture is not the
bottleneck — evidence is*; stop building, pivot to a NEW payoff structure. Ground-truthing
that advice against the repo (this session) produced two corrections per §6.2:

1. **The thesis is already the repo's own position.** F-019→F-031 + the §6.5 Authority
   Ladder ("Authority ≠ architecture") + the Program-1 closure already say: the next-bar
   directional ontology on M15 crypto-majors is falsified across 4+ programs; pivot to a
   genuinely different axis, never parameter archaeology. The advisors re-derived this.
2. **Their top pick (perps / funding-carry / basis) is DATA-BLOCKED.** Verified: `data/`
   holds crypto **spot** OHLCV only (BTC/ETH/BNB/SOL/XRP/DOGE, ~70,081 M15 bars each,
   2024-05-22→2026-05-21, byte-aligned range) + H1/H4 resampled; FX/metals are a 30-day
   snapshot. **Zero** funding/OI/liquidations/perp/basis/options/L2. Building a perps domain
   layer now = architecture for data we don't have (the exact failure mode they warn against).

**Decision (user, this session):** posture = **evidence-first, zero architecture**; axis =
**cross-sectional relative-value**. This is the cheapest genuinely-new (non-directional,
market-neutral) payoff structure: rank the 6 existing spot coins each bar, long the top,
short the bottom, hold a fixed horizon, measure the net long-short spread. It needs **no new
data** and breaks cleanly from the falsified single-name directional paradigm — every prior
falsification was *per-instrument directional*; cross-sectional dispersion is an untested channel.

**Intended outcome:** one pre-registered, deterministic research program through the existing
qualification kernel, yielding a registered finding (F-032). A clean null is a *successful*
experiment (§6.1) — high knowledge-ROI, closes "did we ever test cross-sectional?".

**Guardrails honored:** isolated in `src/research/` (never the live spine; spine stays the
hardcoded CRT/Gaussian/Zone/RR 4-engine path); pure/deterministic/no-lookahead; pre-registered
BEFORE running (E-001 ritual); grants NO authority (§6.5 — a PROMOTE earns *tunability/research*,
not fusion/production weight). **Not in scope:** `FULL_BUILD_SPECIFICATION.md` (the 220h
domain-first migration), any engine→plugin reorg, any domain abstraction, perp data acquisition.

## Reuse (do not reinvent)

| Need | Reuse | Path |
|---|---|---|
| Permutation null (one-sided, seeded) | `permutation_p_value` | `src/research/qualification.py:94` |
| Multiple-testing correction | `benjamini_hochberg` | `src/research/qualification.py:131` |
| Chronological IS/OOS split discipline | `_split_is_oos` pattern | `src/research/qualification.py:79` |
| Net-of-cost haircut | `CostModel` / `DEFAULT_ROUND_TRIP_BPS` (12bps) | `src/research/costs.py:18` |
| Deterministic cost/exit provenance in artifact | `provenance_block` | `src/research/provenance.py` |
| Seeded determinism convention, sorted iteration | `HypothesisRunner` pattern | `src/research/runner.py:61` |
| Candle loading | `CandleLoader` | `runtime/backtest_v2.py` (via runner._load_candles) |
| Driver shape (cohort run + BH + report) | `qualify_majors.py` | `scripts/research/qualify_majors.py` |

**Why a new module, not a new `Hypothesis`:** the existing `Hypothesis.detect()` →
`forward_walk()` path is single-instrument SL/TP geometry. A market-neutral fixed-horizon
spread has no per-leg SL/TP and its statistical unit is *one spread return per rebalance*, not
a trade Outcome. Forcing it through `forward_walk` would be a contortion. We instead reuse the
**statistical** primitives above on a native panel.

## Implementation

### 1. Pre-registration FIRST (E-001 ritual — before any measurement)
`docs/research-readiness/program-5-cross-sectional-preregistration.md`. Declare, locked:
- **Universe:** the 6 spot coins, M15, inner-joined on timestamp.
- **Signals (small cohort — NOT a sweep; BH guards it):** `XS_MOM` (rank by trailing return
  over L bars; long top-k / short bottom-k), `XS_REV` (short-horizon reversal — long losers /
  short winners), optionally `XS_VOL` (low-recent-vol long). 2–3 signals × at most 2 (L,H)
  settings each.
- **Controls (gate-4 must beat the WINNING control):** `random_selection` (seeded random
  k/k each side), `reversed_signal` (sign-flip — sign-noise guard), `long_only_beta` (is the
  spread just market beta?), `shuffled_rank` (destroy the ordering).
- **Gates:** reuse the 7-gate logic — n≥min, E_net>0, PF, beats-winning-control, IS&OOS>0 +
  retention, permutation p≤α, BH across the cohort. OOS = last 30% chronological.
- **Cost:** non-overlapping holds (rebalance every H bars ⇒ independent observations, full
  turnover); net spread = gross − 2·(12bps/1e4) per rebalance (each leg round-trips).
- **The 6 epistemic-integrity questions** (CLAUDE.md §6.2 ritual) answered for the headline claim.

### 2. Core module — `src/research/cross_sectional.py` (pure, stdlib + research-internal only)
- **Panel loader:** load each coin via the proven loader, inner-join on timestamp → aligned
  `dict[ts → {symbol: Candle}]`; assert equal length / no gaps (crypto is 24/7, range already
  verified identical).
- **Signal fns:** `xs_momentum(panel, t, L)`, `xs_reversal`, `xs_vol` → per-bar ranking using
  ONLY data ≤ t (no-lookahead invariant).
- **Portfolio former:** top-k long / bottom-k short, equal-weight, market-neutral.
- **Forward spread:** hold H bars (t+1…t+H), `mean(long fwd ret) − mean(short fwd ret)`, minus
  turnover cost → one net observation per non-overlapping rebalance.
- **Qualify fn:** assemble the net-return series per signal + each control; IS/OOS split;
  `permutation_p_value` vs winning control; assemble cohort p-values; `benjamini_hochberg`;
  emit verdict (PROMOTE / REJECT / INSUFFICIENT) in an EdgeReport-shaped dict.
- **Serialization:** deterministic, no wall-clock, `provenance_block` stamped — byte-comparable.

### 3. Driver — `scripts/research/qualify_cross_sectional.py`
Mirrors `qualify_majors.py`: build panel → run each signal + controls → gate → BH cohort →
write deterministic `results/research/cross_sectional_report.json` + human summary. `argparse`
thin wrapper (no business logic in the script, per §3.3).

### 4. Tests — `tests/research/test_cross_sectional.py`
- **Determinism:** two runs ⇒ byte-identical report (the kernel's load-bearing property).
- **No-lookahead:** signal at t independent of any data > t; hold uses strictly future bars.
- **Panel alignment:** join correctness; mismatched-length / gap ⇒ raise (fail-fast).
- **Control sanity:** `reversed_signal` E = −(signal E) within tolerance; `random_selection`
  E ≈ 0; market-neutral weights sum to 0.
- **Cost monotonicity:** higher bps ⇒ lower net E.

### 5. Register the finding (same turn as the run — Findings Mandate §6.2)
- Add **F-032** to `docs/current-findings.md` (Validated/Revalidate-by, non-empty Evidence =
  the report path + n + E_net + verdict, Confidence, Reversal if it overturns a prior belief).
- Add the F-032 row to the **Repository Truths Index** table in `CLAUDE.md §6.2` (the table is
  enforced ↔ the living doc by `tests/test_current_findings.py` — both or neither).
- Write a memory file `project_cross_sectional_program5.md` + index line in `MEMORY.md`.
- Run `Validate` (pytest per `docs/reference/testing.md` + the determinism check).
- Append the §7.4 SESSION LOG block to `assistant_project.md` (codebase log — this is governed code).

## Verification (end-to-end)

1. `python -m pytest tests/research/test_cross_sectional.py -q` → all green (determinism,
   no-lookahead, control sanity, cost monotonicity).
2. `python scripts/research/qualify_cross_sectional.py` twice → `diff` the two
   `cross_sectional_report.json` ⇒ byte-identical (determinism gate).
3. Inspect the report: per-signal n, E_net (IS/OOS), PF, baseline_delta vs winning control,
   permutation p, BH survivors, verdict. Confirm controls behave (reversed ≈ −signal,
   random ≈ 0).
4. `python -m pytest tests/test_current_findings.py tests/governance/test_epistemic_invariants.py -q`
   → F-032 index↔doc consistent + epistemic invariants hold.
5. Whole-suite smoke (no spine/trust regressions): the live spine files are untouched, so
   `tests/` spine/trust domains stay green (the change is additive under `src/research/`).

## Outcome interpretation (pre-committed, per Authority Ladder §6.5)
- **PROMOTE:** *information exists* → justifies docs/research/shadow measurement only; does
  NOT auto-earn fusion/sizing/production weight (that needs a measured ΔG001 consumer).
- **REJECT / INSUFFICIENT (likely, given F-019→F-031):** a clean null — register it, mark the
  cross-sectional channel tested, redirect. Either way the experiment succeeds.
