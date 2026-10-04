# Gaussian Implementation — Design Theory

**Mode:** design discussion only. No code, no config, no retrain proposed for execution.
**User decisions carried in:** direction = **Option B** (density/novelty re-found);
`p_win` sever = **theory level only, not scoped**; new requirement = **all three Gaussians run
as parallel models in backtest, each under its own contract, outputs monitored.**
**Sources:** read directly from the tree, not from memory or prior sessions.

---

## Context

The `gaussian` slot is one of four in `EXPECTED_ENGINES` (`src/core/engine_runner.py:54`), so
it runs on every decision and its absence is a hard reject. MIAR marks it
`alignment: SEMANTIC_DRIFT`. Reading the tree shows the name covers three structurally
incompatible objects, and that the live one is unparameterised. The user wants all three run
side by side and their outputs watched, with a density/novelty model (Option B) developed as
the intended end-state for the slot.

This document works out what B should be, and — more importantly — **where a three-model
parallel harness can actually live**, because the obvious host does not have the sample size
to support it.

---

## 1. The declared contract

From `docs/governance/MODEL_INTENT_AUTHORITY_REGISTER.md` §3.4 and `miar_registry.json`:

| Field | Value |
|---|---|
| stage / order | `market_understanding` · **2** (after CRT, before ZoneGate) |
| canonical question | "How statistically **conformant** is this market state to previously observed market states?" |
| output | `ema_momentum_kernel_score` ∈ [0,1] — a **score**, explicitly not a probability |
| authority | Stage-1 descriptive vote into fusion only |
| non-goals | never decide whether to trade · never determine entries alone · never classify CRT structure · **never claim probability without calibration** |
| falsification | kernel information-inert / non-pivotal (F-060) |

MIAR §1 states the vocabulary rule directly: *"Calling Gaussian output a probability of win →
call it a **score** (kernel conformity) unless calibrated as probability."*

---

## 2. Three objects, one name (verified from source)

### 2a. `HeuristicGaussianEngine` — live
`src/engines/heuristic_gaussian_engine.py:316-376`. Active via
`engine_runner.gaussian_impl: "heuristic"` on `v2_htfcrt_2026_08`.

```
x     = ((ema_fast - ema_slow)/ema_slow + tanh(momentum_score)) / 2
score = exp( -(x - mu)^2 / (2 sigma^2) )
```

μ/σ resolve through `_normalize_registry_entry` (`:46-57`), defaulting `mu=0.0, sigma=1.0`.
**Verified: 0 of 14 entries in `models/gaussian_registry.json` carry `mu` or `sigma`.** All
three `__active__` pointers (ETHUSDT, BNBUSDT, XAUUSD) resolve to entries that exist — the
load *succeeds* and still yields μ=0, σ=1. Live score is `exp(-x²/2)` on every instrument.
F-060, re-verified from the artifact rather than the finding.

**Domain:** any bar. Needs only `ema_fast`, `ema_slow`, `momentum_score`.

### 2b. `CRTGaussianScorer` — parameterised, unwired
`src/config_layer/crt_gaussian_scorer.py`. Four Gaussian kernels over
`displacement_retrace`, `body_ratio`, `displacement_atr_ratio` plus exponential time decay,
combined as `s_r^0.35 · s_b^0.30 · s_d^0.20 · s_t^0.15`, then a sigmoid to `p_win`. Its μ/σ²
**are** declared and non-default in the active config's `gaussian_scorer` section
(retest 0.237/0.040, body 0.847/0.021, disp 2.177/1.196, sigmoid_k 4.5).

`GaussianAdapter`'s docstring (`src/core/fusion_engine.py:224-239`) says it accepts
`CRTGaussianScorer` — but `engine_runner.py:413` wraps `self.gaussian`, the heuristic engine.

**Domain: RETEST bars only.** `extract_features` (`:178-213`) returns `None` unless
`state.displacement_candle` and `state.retest_candle` both exist. This is the hard constraint
on any parallel harness — see §4.

Also carries two unconditional `print()` calls on the scoring path (`:104`, `:138`).

### 2c. `MLGaussianEngine` — matches the stated intent
`src/engines/ml_gaussian_engine.py`. GaussianNB over the canonical vector, name-anchored
schema contract, fail-open to 0.5. A class-conditional Gaussian *is* a density over
previously observed states, so this is the only one of the three that literally answers the
MIAR question. Config-gated off.

**Domain:** any bar with a full canonical vector.

---

## 3. Option B — the density/novelty re-found (the chosen direction)

### 3.1 What B has to answer
"How conformant is this state to previously observed states" is a **density question**, not a
trend question. B estimates `p(state)` over a declared reference population and emits a
dof-normalised conformity. Novelty is its complement — that is the honest second output, and
it is genuinely useful even when conformity has no edge (a novelty spike is a legitimate
Stage-1 description).

### 3.2 The four constraints B must satisfy by construction

**C1 — Declared reference population.** "Previously observed states" is undefined in code.
All bars? CRT-committed bars? Winning trades? This decides whether B stays MIAR-legal: a
density over *all bars* is honest conformity; a density over *winners* is an outcome model
smuggled into a descriptive Stage-1 slot. F-060's third leg is exactly that failure — the
builder of record is `phase5_calibration.py`, training on raw `rr_achieved` from the F-022
stream (36.8% self-consistent). **This must be an ontology node (§6.6) before any math,
`UNKNOWN_*` if undecided.** Never a TODO.

**C2 — Dof-aware mapping, designed in.** Canonical surface is **48 dims at
`SCHEMA_VERSION 6.0`** (verified by import). F-044 is binding prior art: for a rank-*k*
Mahalanobis form, in-distribution `E[d²] = k`, so `exp(-d²/2)` floors at `exp(-k/2)` — at
rank 27 that was ~1.4e-6 and *no training point* cleared a 0.3 threshold. A model cannot be
OOD on its own training data, so the defect there was the gate, not the model, and retraining
could not fix it. **B must map through a χ² survival function or `d²/dof` from the first line
of code.** This also means B's output is naturally a tail probability ∈ [0,1] — which is a
*conformity* quantity, not a win probability, and therefore MIAR-legal by construction.

**C3 — Covariance conditioning.** 48 correlated dims will not admit a full-rank covariance
from any realistic sample. The existing artifacts already carry `zero_indices` handling (the
rank-27 case F-044 measured). B needs an explicit, declared choice — diagonal, shrunk
(Ledoit-Wolf), or an explicit low-rank projection — and the effective dof must be *recorded*
alongside the score, because C2's normalisation depends on it.

**C4 — Basis de-saturation.** `momentum_score` and `ema_spread` carry the FM-022/023
dimensional mix (F-061/F-064): `legacy ≡ corrected × close`. Measured:
`|tanh(momentum_score)| > 0.999` on 99.70–99.81% of XAUUSD bars, 98.8–99.9% on crypto. Any
density that includes those dims on the legacy basis is estimating a distribution over a
near-constant. The `feature_pipeline.normalization_basis` gate already exists with a
`corrected` arm, default off and byte-identical when off.

### 3.3 What B is *not*
Not a p_win. Not an entry filter. Not an authority claim. Under §6.5, a new model family earns
*tunability*, never authority — authority requires measured ΔG001 via the F-036/F-070 ablation
method (byte-diff entry ledger, gate-ON, non-vacuity guard).

---

## 4. The parallel-models requirement — and the constraint that decides its shape

### 4.1 The blocking structural fact
`backtest.engine_gate_enabled = true` on the active config, so EngineRunner **does** run in
backtest (F-070's epoch). But the call site is guarded:

> `src/runtime/backtest_v2.py:3419` — `if "TRADE_OPENED" in action and engine.state.active_trade:`
> … enclosing the EngineRunner gate at `:3586` (`veto_mode=post_commit`).

**All four engines, Gaussian included, are evaluated only on bars where the CRT state machine
has already committed a trade.** Measured population on that path: F-070 counted 30 committed
entries across all four crypto majors (BNB 13, ETH 5, BTC 5, SOL 7); XAUUSD is thinner still.

So the obvious host for a three-model comparison gives **n ≈ 3–30**. That is not a population
you can monitor three models on — it is below every power floor in the repo
(`QualConfig.min_samples`, the n≥30 gates in F-090/F-094).

### 4.2 The two candidate hosts, and what each one is for

| | **Host 1 — inside EngineRunner (extend `shadow_ml`)** | **Host 2 — standalone per-bar observation harness** |
|---|---|---|
| Population | TRADE_OPENED bars only (n ≈ 3–30) | Every bar × direction (n ≈ 47k XAUUSD; 94k–377k bar×direction, the F-086/F-097 population) |
| Answers | "what would each model have said on the trades we actually took" | "how do these three models behave, and do they agree" |
| Power | none | full |
| Decision relevance | direct | none — descriptive only |
| Precedent in tree | `gaussian_impl: shadow_ml` already does this for 2 of 3 (`engine_runner.py:330-341, 739-752`) — production score enters fusion, shadow attaches under `["shadow"]`, never in fusion, logged to `engines_raw` (`collector.py:137`) | F-086 / F-097 built exactly this shape (outcome-first inversion, 94,314 units) |
| Ledger risk | byte-identical if shadows stay out of fusion | zero — never touches the decision path |

**These are not alternatives; they answer different questions.** Monitoring three models'
*behaviour* is a descriptive comparison task and wants Host 2. Checking what they'd have said
on real entries wants Host 1 and will stay permanently underpowered — which is a finding, not
a failure.

### 4.3 The domain-disjointness problem
The three models do not share an input domain:

- heuristic → any bar (3 features)
- ML / B → any bar (full canonical vector)
- **`CRTGaussianScorer` → RETEST bars only**, because `extract_features` returns `None`
  without both `displacement_candle` and `retest_candle`

So "all three on every bar" is **not constructible as stated**. On a per-bar harness,
`CRTGaussianScorer` is `None` on the overwhelming majority of bars. The honest shape is a
**ragged panel**: three columns, with the CRT-scorer column populated only on its natural
domain, and that domain declared rather than papered over with a neutral 0.5 fill. Filling a
missing domain with a neutral value is the F-079/F-085 silent-gap class — a skipped
measurement made indistinguishable from an absent one.

### 4.4 Output comparability
The three outputs are not on a common scale and must not be differenced naively:

| Model | Output | Meaning |
|---|---|---|
| heuristic | `exp(-x²/2)` | kernel proximity on a trend axis |
| CRTGaussianScorer | weighted geometric mean + `p_win` sigmoid | setup geometry quality, then a probability head |
| ML / B | `sigmoid(expected_rr)` / χ² tail | learned reward map / conformity tail probability |

The existing shadow block computes `delta = shadow − production` and
`agreement = (both ≥ 0.5)` (`engine_runner.py:745-749`). Both are scale-assumptions that do
not hold across these three. A comparison metric has to be declared up front — rank
correlation over the shared domain, or per-model quantile transform before any delta — and
declared *before* the first run, not chosen after seeing the output.

---

## 5. Ambiguities requiring a decision (flagged, not resolved)

1. **Is B the third model or a fourth?** "All 3" could mean {heuristic, CRTGaussianScorer, ML}
   with B as a later replacement for ML, or {heuristic, CRTGaussianScorer, B} with ML retired.
   These give different harnesses.
2. **Host 1, Host 2, or both?** §4.2. Monitoring behaviour needs Host 2; Host 1 will stay at
   n≈30 permanently.
3. **What happens on `CRTGaussianScorer`'s missing domain?** §4.3 — `None`/absent (honest,
   ragged) vs neutral fill (silent-gap class). Recommendation: absent, explicitly typed.
4. **Does the fusion input change?** Keeping heuristic authoritative and shadowing the other
   two is byte-identical and extends an existing pattern. Making all three observational means
   freezing or replacing the `weight_gaussian: 0.2` input, which moves the ledger.
5. **Comparison metric**, declared before the run — §4.4.
6. **Persistence sink.** `engines_raw` (existing shadow path) vs a new JSONL. A new stream is
   a governed claim surface under §6.7 and needs a `CC-*` class in
   `docs/governance/jsonl_claim_catalog.yaml` before anything asserts what it proves.
7. **Reference population for B** — C1. Blocking for B specifically; not blocking for the
   heuristic/CRT-scorer columns.
8. **`CRTGaussianScorer`'s two `print()` calls** (`:104`, `:138`) — unconditional stdout; on a
   47k-bar harness that is ~94k lines. Unrelated to the design question, but it would have to
   be dealt with before any per-bar run.

---

## 6. Held at theory level by user decision

- **`p_win` sever.** `engine_runner.py:1017-1020` sets
  `p_win = engine_results["gaussian"]["score"]` and hands it to `DecisionEngine`, which
  thresholds it against `p_win_threshold` (`decision_engine.py:100,150`) and returns it as
  `confidence` (`:170`). A Stage-1 descriptive conformity number is the gating probability for
  the final approve/reject. MIAR names this exact path a **"forbidden reinterpretation"** in
  two places. **Documented as a named contract defect; no change scoped.**

## 7. Anti-scope (carried from `docs/implementation_plan/xauusd-gaussian-toward-economics-2026-07-23.md`)

- No retrain on F-022-derived labels.
- No `gaussian_impl=ml` flip. That program already ran end to end — E0/E1/E2 shipped, M4
  returned **0 PROMOTE**, `nb_top_decile` REJECT at E[R] = −0.25. `REGISTRY_ACTIVE ≠
  ECONOMIC_AUTHORITY`.
- No probability language in any output contract.
- No authority claim from a parallel-observation run. Agreement/disagreement between three
  models is information about the models, not about the market (§6.5 rung 1).

---

## Verification (if any of this is later executed)

- **Registry claim:** assert `mu`/`sigma` presence per entry in
  `models/gaussian_registry.json` — currently 0/14.
- **Host-1 population:** count EngineRunner invocations vs total bars in a backtest run —
  expect the `:3419` TRADE_OPENED guard to yield n ≈ 3–30.
- **Degeneracy:** score variance of `HeuristicGaussianEngine.compute` across the XAUUSD M15
  corpus under both `normalization_basis` arms.
- **Byte-identity:** if shadows are added inside EngineRunner, the entry ledger must be
  byte-identical to the pre-change run (F-036/F-070 method).
- **Floors:** `python scripts/maintenance/check_governance_invariants.py --all` — capture the
  baseline red count *before* touching anything; the green floor carries pre-existing failures
  on this branch.
