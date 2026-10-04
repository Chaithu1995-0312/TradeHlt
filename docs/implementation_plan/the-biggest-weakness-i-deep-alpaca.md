# Forensic Verdict — Feature-Math WHAT Layer, Gate 1 / Gate 2, GD-001…GD-010

> **This is a forensic verdict, not a design proposal.** It answers the ten audit axes and the
> closing questions: what is proven, what is broken, what is unproven, which findings are material,
> whether Gate 1 is complete, whether Gate 2 can be closed, whether GD-001/GD-002 should proceed to
> remediation, and the single highest-leverage next action.
>
> Every claim below was verified by reading source (file:line), not by trusting agent summaries,
> grep, or call graphs. Where I could not verify without executing code, I say so and mark it a
> required verification step (plan mode is read-only).

---

## Context

F-047 declared the market ontology "AUTHORITATIVE + ENFORCED," pinned 10 pre-existing feature-math
divergences (GD-001…GD-010), and Gate-2 Step 7c reported "0 decision flips / 39,456 score-gated →
DECISION-INERT." The audit's thesis: the project may have manufactured the *appearance* of
mathematical trustworthiness without guaranteeing research→backtest→live-decision consistency. I
traced the causal chain OHLCV → ontology → registry → candle_math/derived_math → live-hook/pipeline →
CRT/engines → fusion/decision, and stress-tested each checkpoint.

---

## Verdict summary

| # | Axis | Verdict |
|---|---|---|
| 1 | What was built vs plan | **Mostly proven.** Artifacts exist and match the plan. One headline overclaim (7c "DECISION-INERT"). |
| 2 | WHAT layer genuinely authoritative | **Partially.** Registry is real, non-`eval`'d, single-source per FM-ID. But "authoritative for *all* feature math" is stronger than the enforcement supports (axis 3). |
| 3 | Enforcement bypassable | **BROKEN (by design gaps).** Material false-negative classes confirmed from source. |
| 4 | Grandfather pins durable & truthful | **Proven.** Set-based ratchet is sound; manifest empty ⇒ CURRENT=ORIGINAL, consistent. One reproducibility caveat (Python-version-coupled fingerprints). |
| 5 | Adjudication verdicts source-correct | **Proven** for the sites I traced (GD-001/002/003/004/005/010). |
| 6 | Semantic classifications correct | **Proven.** `disp_strength`/wick/range collisions are genuine name collisions (distinct quantities), not formula bugs. Rename is the right remedy. |
| 7 | Gate 2 measured what it claims (value/score) | **Proven for value & score drift.** Injection reaches the real score boundary (`engine_runner.py:654`). |
| 8 | Step 7c state isolation causally valid | **Proven.** `deepcopy`-per-candle B-vs-B control genuinely isolates the adaptive controllers. |
| 9 | "Decision flip" is the real final decision | **Proven it captures final EXECUTE/REJECT — but NULL-BY-CONSTRUCTION.** See broken finding below. |
| 10 | Over-engineered vs edge discovery | **Yes, past this point.** High ROI already realized; further enforcement build-out is optimization theater. |

---

## The single most important finding (BROKEN)

**Gate-2 Step 7c's "0 decision flips → DECISION-INERT" is null-by-construction and cannot close Gate 2.**

- `reports/feature-math-decision-flip-probe.json`: `approve_current_A = 0`, `approve_canonical_B = 0`
  across all 70,002 candles. **Zero candles executed in either branch.**
- A flip requires `apA != apB` (`feature_math_decision_flip_probe.py:199`). With both approval counts
  identically 0, `flips = 0` is a **mathematical identity, independent of `body_ratio`**. The
  divergence could be arbitrarily large and the probe would still report 0 flips.
- The 39,456 "score-gated" denominator is **entirely rejects** (`reasonB_histogram`: `low_score`
  39,418, `invalid_session:asia` 23,346, `low_rr` 6,918, `ultron_gate:*` 320). None are executes.
- **Decisive corroboration:** the real research spine executes BNBUSDT **~11 times gate-ON / ~13
  gate-OFF** (per prior findings/memory). This harness executes **0 times**. The probe therefore does
  **not** reproduce the only candles where a score shift could change a trade — the ~11–13 live
  setups. It measures body_ratio sensitivity at a boundary that never fires an approval.
- The 7b score-drift probe already proved `body_ratio` moves the **CRT score ~96.7%** and the
  live value differs on 97% of bars, `>1` on 46%. So the value is score-material; 7c was supposed to
  show whether that reaches decisions. **It did not answer the question — it showed the harness
  reaches no decision.**

The adjudication doc's own caveat concedes this (`docs/analysis/feature-math-divergence-adjudication.md:148-152`:
*"does NOT reproduce the ~13 CRT-state-gated live setups where run() actually executes; a definitive
live-setup flip rate would need the CRT-spine harness"*). **But the top-line F-047 conclusion and the
memory entry both assert "DECISION-INERT" without that qualifier in the headline** — an E-001-class
overclaim: the honest statement is *"decision-flip UNPROVEN at the execution margin; 0 flips observed
in an all-candle harness that produced 0 executions."*

> Caught the system overclaiming: "DECISION-INERT" is doing more work than the data supports. The
> data supports "inert within a harness that approves nothing," which is materially weaker.

---

## What is PROVEN

- **Registry is real and non-`eval`'d.** `FORMULA_REGISTRY = {**PRIMITIVES, **DERIVED}` is a static
  name→callable dict (`src/features/registry/__init__.py:26`); dispatch is by `inspect.signature`
  matching, YAML is `safe_load`'d, no `eval`/`exec` anywhere. Canonical math is single-sourced in
  `src/features/candle_math.py` and `src/features/derived_math.py`.
- **Canonical `body_ratio` is coherent; the live-hook one is the bug.** `candle_math.body_ratio =
  body_size / candle_range` bounded [0,1] (`:57-58`), the only definition the `body_ratio >= 0.70`
  gate is coherent against. The divergent site `live_engine_hook.py:360-362` computes
  `body_ratio = body_size / wick_size` where `wick_size = total_wick` — **unbounded, incoherent with
  the gate.** This is a genuine correctness defect, not a stylistic one.
- **Injected value reaches the real score boundary.** `engine_runner.py:654` consumes `input_data`
  directly into `crt_compute`; gaussian/RR likewise. No recompute-override. The probe's injection is
  faithful *at the scoring level*.
- **State isolation is sound.** `deepcopy(runner_ref)` per candle isolates `AcceptanceController`/
  `ConvergenceController`/`DecisionEngine` dynamic-threshold state; the zone bypass is a **class-level**
  monkeypatch specifically to preserve deepcopy isolation (`:98-122`). No `__deepcopy__`/lock/global
  defeats it. The B-vs-B control is a valid marginal counterfactual.
- **Grandfather ratchet is a true set invariant.** `test_grandfather_set_monotonic` enforces
  `CURRENT ∪ RETIRED == ORIGINAL_BASELINE` and `CURRENT ∩ RETIRED == ∅` — not a count cap.
  `durable_key = sha256(rel, qualname, target, kind, ast.dump(rhs))[:16]` is content- and
  scope-sensitive (proven by `test_durable_key_is_content_and_scope_sensitive`). Manifest is empty
  ⇒ CURRENT = all 10 = ORIGINAL. Consistent.
- **Semantic classifications hold.** `disp_strength` collisions (GD-004 `scoring_engine` = `move/atr`;
  GD-005 `crt_engine` = `wick/atr`) are distinct quantities sharing a name with the FM-020 feature
  (`body/(atr*close)`, the pipeline column). These are name collisions → **rename** is behavior-neutral
  and correct. GD-003 (`body_size`) and GD-010 (`candle_range`) are byte-identical duplicates.

## What is BROKEN

- **Gate-2 7c null-by-construction** (above) — the load-bearing defect.
- **Enforcement lint has material false-negative classes** (`feature_math_lint.py`, confirmed from
  source `:319-325`, `:363-378`). New feature-math escapes the lint when written as:
  1. **DataFrame column assignment** `df["body_ratio"] = high - low` — Subscript target, never yielded
     by `_target_names`. (This is the *dominant* form in a pandas feature pipeline.)
  2. **Attribute assignment** `self.body_ratio = ...` — Attribute target, never yielded.
  3. **Augmented / walrus** `body_ratio += ...` / `body_ratio := ...` — only `Assign`/`AnnAssign`
     inspected.
  4. **Re-derivation into a non-registered variable name** `_br = body / tw` (then consumed) — filtered
     out at `:376` (`canon not in registered`).
  5. **Anything outside 5 dirs** (`research/`, `strategies/`, `analytics/`, `scripts/`, `tests/` all
     exempt) — the research pipeline that produced F-019…F-042 is **not** lint-covered.
  6. **A helper whose leaf name collides with a registered feature** (`_call_is_registry` whitelists
     any call whose leaf is a registered name) → a rogue local `def body_ratio(...)` is classed OK.
  → "The WHAT layer is ENFORCED" is true only for `Name`-target assignments in 5 dirs. The strong
  reading ("all feature math is governed") is **not supported**.

## What is UNPROVEN

- **Whether canonicalizing GD-001/GD-002 changes any real live decision.** The only artifact that
  claims to answer this is null-by-construction. Genuinely open.
- **Exhaustiveness of the 10-site census.** Gate 1 enumerated 10 sites *of the form the lint can see*.
  Given the false-negative classes above (esp. DataFrame writes and the exempt `research/` tree),
  there may be re-derivations the census never surfaced. "10 divergences total" is **not proven** —
  "10 divergences of the scannable form" is.
- **Live-path fidelity.** The probe bypasses the zone gate (matching *backtest*, not live) and injects
  a `trend_bias`-signed direction rather than the real CRT-determined direction. GD-001/002 live in
  the **live** hook (F-010-unverified, F-037: backtests bypass it). So even a corrected 7c measures a
  backtest-configured proxy of a live-only divergence.

---

## Answers to the closing questions

**Is Gate 1 complete?** — **Substantially, with one qualifier.** Classification and source-tracing of
the 10 sites are correct and durable. But Gate 1's *completeness* is bounded by the census
instrument, which has the false-negative classes above. Gate 1 is complete **for the scanned surface**;
it is **not proven exhaustive** over all repo feature-math. Downgrade the "authoritative for all
feature math" language to "authoritative for the governed FM-IDs; enforced against Name-target
re-derivation in 5 dirs."

**Can Gate 2 be closed?** — **No, not on the current artifact.** The 7c result is arithmetically
forced (0/0 approvals). Gate 2 closes only after the decision-flip is measured at candles where the
system actually executes.

**Should GD-001/GD-002 proceed to remediation?** — **Yes — it is a real correctness fix (the live
value is the incoherent one) — but the PATH depends on the missing test.** Remediation is *not*
byte-identical: it swaps the live value from `body/total_wick` to the canonical `body/candle_range`
(≈97% of bars change). So:
- If the decisive flip test (below) shows **0 flips at the real executions** → remediate freely
  (correct formula, behavior-neutral). Hash-neutral, no promotion gate.
- If it shows **any flip** → the fix **changes live trade decisions** → must go through the promotion
  gate with a `ValidationReport`, per §6.5 Authority Ladder and §4.0.
- Do **not** ship it blind on the strength of the null-by-construction 7c.

**Which findings are material?** — GD-001/GD-002 (the only non-equivalent, decision-reachable formula
divergence) and GD-004/GD-005 (decision-reachable name collisions, one a HARD REJECT). GD-003/010 are
immaterial (byte-identical). GD-006/007 are diagnostic-unreachable. GD-008/009 are dead code.

**Is the project over-engineered relative to edge discovery?** — **Yes, from here on.** The apparatus'
highest ROI is *already banked*: it demonstrated the features are not contaminated, which
**re-validates the F-019…F-042 falsification sweep** rather than overturning it (a null with a clear
conclusion = high knowledge-ROI, §6.1). But the binding constraint is repeatedly established as the
*execution model / entry-information null* (F-001, F-025, F-040), not feature correctness. Building
more enforcement (fixing the lint's blind spots, more pins, more governance) is **optimization theater
on a WHAT layer whose consumers have no demonstrated edge.** YAGNI applies: close Gate 2, do the cheap
hygiene, freeze the layer, redirect.

---

## Single highest-leverage next action

**Run the one decisive experiment: a CRT-spine decision-flip test at the ~11–13 real BNBUSDT
executions.** Not a redesign — a ~1-file bounded read-only probe:

- Take the CRT-spine setups that actually reach `EXECUTION` (already enumerated by the existing spine
  adapter / prior findings — reuse, don't rebuild).
- For each, evaluate `EngineRunner.run()` twice — canonical vs `body/total_wick` `body_ratio` — with
  the **same deepcopy isolation 7c already implements** (that machinery is correct and reusable).
- Record final EXECUTE/REJECT flips **on the executing candles only** (denominator = the ~11–13, not
  70,002).

This is small, deterministic, and **decisively closes or opens Gate 2**. Outcome routing:
- **0 flips** → Gate 2 closes honestly; GD-001/002 remediation is behavior-neutral; ship it +
  GD-004/005 renames + GD-008/009 dead-code deletion as one hygiene pass; **freeze the feature-math
  program**; correct the F-047/memory "DECISION-INERT" headline to the qualified statement.
- **≥1 flip** → GD-001/002 is live-material; remediation goes through the promotion gate; re-scope the
  finding.

Everything else in this space is lower leverage. Do **not** spend effort hardening the lint's
false-negatives unless a real DataFrame-write re-derivation is actually observed.

---

## Verification (how to check this verdict end-to-end)

1. **Reproduce the null-by-construction claim:** `type reports/feature-math-decision-flip-probe.json`
   → confirm `approve_current_A == 0` and `approve_canonical_B == 0`. If both are 0, `flips=0` is
   forced.
2. **Confirm the spine executes >0:** re-run the spine adapter on BNBUSDT (gate-ON) and confirm ~11
   executions — the count the 7c harness fails to reproduce.
3. **Reproduce the durable_keys** under `venv/Scripts/python.exe` (PyYAML + the interpreter the pins
   were minted on — `ast.dump` is version-sensitive): `python scripts/analysis/feature_math_lint.py
   --check`. All 10 pins should be present, 0 stale, floor green.
4. **Demonstrate a lint false-negative** (read-only, in a scratch file): a module under `src/engines/`
   containing `df["body_ratio"] = high - low` passes `--check` clean — proving the Subscript blind spot.
5. **Run the tests behind the layer:** `python -m pytest tests/test_feature_math_lint.py
   tests/test_feature_lineage.py -q` → the ratchet/lineage floor is green (this verifies the *pins*,
   not exhaustiveness).

---

## SESSION LOG (to persist to assistant_project.md on execution — plan mode blocked the write)

```
📝 SESSION LOG ENTRY
Date: 2026-07-08
Topic: Forensic audit of feature-math WHAT layer / Gate 1 / Gate 2 / GD-001..010
Decision/Output: Verdict — registry/pins/isolation PROVEN; enforcement has material false-negative
  classes (Subscript/Attribute/AugAssign/non-registered-name/out-of-5-dirs); Gate-2 7c is
  NULL-BY-CONSTRUCTION (0/0 approvals across 70,002 candles → flips=0 forced; spine executes ~11,
  harness executes 0) → Gate 2 cannot close; F-047/memory "DECISION-INERT" is an E-001 overclaim.
Belief Update / ROI / Goal:
  Goal: guarantee research→backtest→live decision consistency of feature math.
  Belief: the feature-math correctness question is NOT yet answered for the cases that matter;
    the apparatus' real ROI (re-validating the F-019..F-042 null sweep as non-artifactual) is banked.
  Knowledge ROI: high (identified the one load-bearing gap + the one decisive cheap test).
  Action: run the CRT-spine flip test on the ~11-13 real executions; then freeze the layer.
Open Questions: Do GD-001/002 flip any real live decision? Is the 10-site census exhaustive given
  the DataFrame-write / research/ blind spots?
Next Step: CRT-spine decision-flip probe (executing candles only); route remediation on its result.
```
