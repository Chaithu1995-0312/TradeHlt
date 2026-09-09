# Exit Geometry & Dynamic Stop Modifications — a decomposition

Backtest-only. Decompose **why** the oracle program's information never crosses zero, and measure
the one class of exit behaviour the repository has never built: causal dynamic stop policies on the
production two-target object.

---

## Context

The profitable-entry oracle program (2026-08-21) ended on a split result. Conjunctions of declared
states beat the base rate at a **6.2–7.6× excess over a measured block-permutation null** — real
information, not a multiple-comparisons artifact — while **0 of 84 state cells cleared zero** on the
net basis across all 8 arm×direction combinations. It left a narrow question:

> not *is there structure* (there is), but *why the structure will not cross zero* — exit geometry,
> cost, or the size of the information itself.

This program answers that by accounting, not by another search. Three things make it tractable now
and make it different from a re-run of F-025:

1. **Every exit analysis in this repo was measured on the wrong exit object.** `research/exit_grid.py`
   (F-025) and `research/forensics.py` both drive `forward_walk`, which models one TP, no partial and
   no trail. Production realises 50% at TP1, moves the stop to a **half-way trail**, and runs the
   remainder to TP2. `multi_tp_walk` now exists and is triangulated, so the real object is measurable
   for the first time.
2. **The cost basis changed.** `exit_grid.ceilings` computes `min_achievable_cost` from flat 12 bps.
   On XAUUSD that is ~11× the measured broker cost (F-082: 0.5394R vs 0.0477R). Every ceiling in the
   F-025 lineage inherits that. SEM-015 `ComponentCostModel` replaces it here.
3. **Production has exactly one dynamic stop** — the half-way trail at TP1 — and whether it helps has
   never been measured. The whole class (ratchet, breakeven-at-R, time-decay, chandelier) is absent
   for the two-target object.

**Scope note, not a correction.** F-025 was crypto-scoped, single-TP, flat-bps. This is XAUUSD,
two-target, measured-cost. Different object, different cost basis, different instrument — it neither
confirms nor overturns F-025, and will not cite it as support (§6.2).

**Authority.** Descriptive decomposition. `economic_claims_allowed: false`, no promotion, no fusion
weight, no G001, no `ACTIVE_VERSION` change. The 236-bar holdout **stays sealed** — mining happens on
TRAIN only and no cell is claimed as a forward result.

---

## Two constraints that govern the whole design

### 1. Intrabar path ambiguity — stops update on bar CLOSE only

A ratcheting stop **cannot be faithfully simulated from OHLC**. If the stop moves using bar *i*'s
high and bar *i*'s low also reaches the new level, the within-bar order is unknowable, and resolving
it favourably is silent optimism that compounds over every bar of every trade. Program 10
(`research/path/ambiguity_census.py`) already established this failure class for the *fixed*-stop
tie-break (population P1); for a ratchet it is strictly worse, because the ambiguity recurs on every
bar rather than only on spanning bars.

**Rule:** the stop level applied to bar *i* is a function of bars **≤ i−1** only. Enforced by test —
a policy that reads the current bar's high/low must fail. The same-bar-update variant is measured
once as a declared **optimism bound** so the size of the assumption is reported rather than hidden;
it is never the primary basis.

### 2. R is comparable across stop widths — but only under a stated assumption

`ComponentCostModel.cost_r` is `cost_price / risk_distance`. Under fixed-fractional sizing (position
size = risk budget ÷ risk distance), 1R is the same currency for every geometry, and that ratio is
exactly the fixed-fractional-correct cost. So E[R] **is** comparable across stop widths — this is the
assumption that licenses comparing a 0.5×ATR stop against a 3×ATR one at all, and it gets stated in
the report rather than assumed. Its limits get stated too: it ignores margin/capital constraints and
the differing absolute exposure a wider stop implies.

---

## Reuse (existing, verified — do not rebuild)

| Need | Existing | Note |
|---|---|---|
| Exit-agnostic MFE/MAE ceiling | `forward_walk.horizon_excursion` | tie-break immune by construction |
| Ceiling arithmetic + regime label | `exit_grid.ceilings`, `min_achievable_cost` | swap flat `CostModel` → `ComponentCostModel` |
| Capture ratio, loss-mechanism ranking | `forensics._opp_bundle`, `_loss_mechanisms`, `_classify` | `capture_ratio = realised / mfe_r` already implemented |
| Two-target production kernel | `research/oracle/multi_tp_walk.py` | triangulated; extend additively |
| Ratchet reference implementations | `forward_walk` `exit_model="trailing"`, `replay/timing_reconstructor.py` | two independent priors to cross-check a new ratchet against |
| Block bootstrap / permutation / partition | `research/oracle/scan.py` | `block_bootstrap_mean_ci`, `l3_permutation_null`, `partition`, `effective_n` |
| Labelling driver | `research/oracle/labeler.py` | `label_corpus` already takes geometry as parameters |
| Corpus | `results/research/bar_matrix/XAUUSD_M15/` (47,197×124), `oracle_labels/`, `oracle_scan/scan_report_train.json` | all on disk |

---

## Stages

### Stage A — Ceilings first (this is a gate, not a preamble)

Bound what *any* exit could achieve before searching the space. Reuse `horizon_excursion` over the
full oracle universe (every bar × both directions) with SEM-015 cost.

| Ceiling | Definition | Attainable? |
|---|---|---|
| perfect-foresight | `E[MFE_r] − min_cost` | No — requires knowing the path |
| **causal** | best E[R] over the policy grid, using only past bars | Yes, but mined (optimistic) |
| incumbent | production geometry's actual E | This is what runs today |

Plus the `capture_ratio` distribution (realised ÷ MFE) via `forensics._opp_bundle`, and the
loss-mechanism ranking, both stratified by exit reason.

**Gate:** if the perfect-foresight ceiling is ≤ 0 net of measured cost, then no exit policy of any
kind can help, the exit axis closes with a decisive answer, and Stages B–D are not run. F-025
measured `reality_gap` +4.16R on a different basis, so this probably won't fire — but computing it
first is what prevents a pointless search, and it is cheap.

### Stage B — Dynamic stop policy class (register **SEM-019** first, §6.6)

New `src/research/oracle/stop_policy.py`. A `StopPolicy` is a pure function
`(trade_state, bars_so_far) → new_stop`, causal by construction. `multi_tp_walk` gains one optional
`stop_policy=None` parameter; `None` reproduces today's behaviour byte-identically.

| Policy | Params | Why it's in the grid |
|---|---|---|
| `fixed` | — | **The control.** Measures whether *any* dynamic stop helps. |
| `production` | — | Today's half-way trail at TP1. The audit baseline. |
| `breakeven_at_r` | x ∈ {0.5, 1.0, 1.5} | The thing the config key `partial_tp_breakeven_enabled` claims to do but doesn't |
| `ratchet_r` | k ∈ {0.5, 1.0, 1.5} | Trail k×R behind the running extreme |
| `ratchet_atr` | k ∈ {1, 2, 3} | Chandelier; scale-invariant counterpart |
| `time_decay` | n ∈ {6, 18} | Targets F-024's asymmetry: losers resolve ~immediately, winners mature over ~90 min |

Invariants, each a test: a stop never moves **away** from price (widening risk is not a stop);
`production` + `fixed` reproduce existing labels exactly; a policy peeking at the current bar fails.

### Stage C — Geometry × policy sweep, with the controls that bind

Grid: `sl_geom{2} × tp1_mult × tp2_mult × partial_fraction{0, 0.25, 0.5, 0.75} × horizon{20,40,96} × policy`.
Compute is not the constraint (377k labels took 10.6s), so **multiplicity discipline matters more,
not less**: block bootstrap on every interval, block-permutation null on the sweep, primary arm
declared up front.

**Pre-declared, and load-bearing:** an *unconditionally* profitable cell is a **bug signal, not a
discovery**. Every-bar-both-directions expectancy should sit near −cost; a positive one is
investigated as a defect before it is reported. XAUUSD rose across the corpus, so passive
same-direction exposure (`long_only`) is the binding control, not zero — the oracle scan's 65 → 8
collapse under exactly this control is the precedent.

### Stage D — The interaction test (the payoff)

Take the oracle scan's informative cells (`l2_states_*.csv`, `l3_conjunctions_*.csv`, already on
disk) and compute E_net for each under every exit configuration. Two shapes, pre-declared:

- **LEVEL** — exit shifts base and cells alike; `Δ(cell − base)` is flat across configs ⇒ exit does
  not unlock the information, and the binding constraint is information size.
- **INTERACTION** — `Δ(cell − base)` varies with exit ⇒ a joint entry×exit configuration exists.

Statistic: variance of `(cell − base)` across exit configs, against the same quantity under
block-permuted labels. This is what separates "exit is a flat level shift" from "exit and entry
information interact" — and it is the question the oracle determination actually left open.

### Stage E — Report

`docs/analysis/exit-geometry-decomposition-2026-08-2X.md`, point-in-time. Descriptive. No F-id
registered without explicit sign-off. Assert the holdout was never read.

---

## Files

**New** — `src/research/oracle/stop_policy.py` · `scripts/research/exit_geometry_scan.py` ·
`tests/research/test_stop_policy.py` · `tests/research/test_exit_ceilings.py`

**Modified** — `src/research/oracle/multi_tp_walk.py` (one additive `stop_policy` param, default
`None`) · `configs/formulas/market_ontology.yaml` (**SEM-019** `DYNAMIC_STOP_POLICY`, **SEM-020**
`EXIT_CAPTURE_DECOMPOSITION`, in the non-frozen `execution_behaviours` section; SEM-018 is currently
the highest id) · SITS registration for the new runnable.

**Never touched** — `src/config_layer/crt_engine_v2.py`, `src/runtime/backtest_v2.py`, `src/core/*`,
`configs/production/*`, `ACTIVE_VERSION`, `research/exit_grid.py`, `forward_walk.py`.

---

## Verification

| Check | Pass condition |
|---|---|
| **Parity** | `stop_policy=None` reproduces the existing 377,256 labels byte-identically |
| **Causality** | a policy reading the current bar's high/low to set that bar's stop **fails** an explicit test |
| **Monotonicity** | no policy ever moves a stop away from price |
| **Ratchet cross-check** | new `ratchet_r` agrees with `forward_walk(exit_model="trailing")` under a degenerate single-TP config |
| **Ceiling sanity** | `E[MFE_r] ≥ E[R_gross]` in every cell — a violation is a bug, not a finding |
| **Drift control** | every cell reported against `long_only`, never against zero alone |
| **Null** | block-permutation null on both the sweep and the Stage-D interaction statistic |
| **Holdout** | asserted unread on the artifact, not left to discipline |
| **Ontology** | SEM-019/020 mutation-tested (missing field / bad `knowledge_status` / duplicate id all caught) |
| **Freeze pin** | `test_xauusd_window_vector_regression` + `test_schema_pins_match` still pass — this program must be vector-inert |

Run:
```bash
python scripts/research/exit_geometry_scan.py --instrument XAUUSD --stage ceilings
```
then `--stage sweep`, then `--stage interaction`. Floor:
`pytest tests/research/test_stop_policy.py tests/research/test_exit_ceilings.py tests/research/test_multi_tp_walk_parity.py tests/research/test_oracle_labeler.py`

---

## Risks

1. **Intrabar ambiguity favours ratchets** — the single largest way this program could manufacture a
   false result. Contained by the close-only update rule, with the same-bar variant measured as a
   declared bound.
2. **Mining an exit grid on outcome-labelled data** — hundreds of cells over overlapping labels.
   Contained by block bootstrap + permutation null + the bug-signal rule for unconditional positives.
3. **Drift masquerading as exit skill** — a wide stop and a long horizon on a rising instrument is
   beta. `long_only` is the binding control throughout.
4. **Ceiling optimism** — the perfect-foresight bound is not attainable and must never be quoted as
   headroom. Three ceilings are reported precisely so the attainable one is separable.
5. **Horizon confound** — a longer horizon changes cost (more swap nights) and outcome mix
   simultaneously. Both carried per cell; gross and net always reported side by side.
6. **A LEVEL result is the likely outcome**, and it is a real answer, not a failure — it would close
   the exit axis and localise the constraint to information size.
