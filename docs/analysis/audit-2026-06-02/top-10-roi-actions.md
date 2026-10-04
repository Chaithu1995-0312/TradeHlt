# 8 · Top-10 Highest-ROI Actions + the Ordered Five

> Point-in-time audit, 2026-06-02. Ranked by (profitability impact ÷ effort), all sourced from the four
> verified constraints. **None of the top actions is "new intelligence."**

## The thesis in one line

> Across code + plans + the SESSION LOG, **nothing shows intelligence is the binding constraint.** The
> levers are governance integrity, throughput policy, measurement-consumption, and assumption calibration —
> and there is **already-built, validated, unused ROI** sitting in `v3`.

## Top 10 (ranked)

| # | Action | Constraint | Effort | Impact | Evidence |
|---|--------|-----------|:---:|:---:|----------|
| 1 | **Promote BNBUSDT V3 (governed)** — per-coin session override | C2 / ROI | LOW | **HIGH** | measured +4.91%→**+20.59%**, PF 1.79→2.54, 15→35 trades, DD~3% |
| 2 | **Close the governance bypass** — flip off ungoverned `deepdeektry`; make `config_integrity.py` a hard gate; hash the validation_summary lineage | C1 | LOW-MED | HIGH (protects all ROI) | guard exists & flags it; params↔params hash blind spot |
| 3 | **Fix the 14 standing bugs** — LLM fail-open `0.5`→`1.0` (`llm_scorer.py:85,101,109,220`); `gaussian_shadow` init (`engine_runner.py:671`) | C1 | LOW | MED (correctness) | `splendid-biscuit`; hot-path AttributeError swallowed |
| 4 | **Drift → size-down/skip** — act on the signal already detected | C3 | LOW | MED-HIGH (capital) | `live_engine_hook.py:676` detects, doesn't gate |
| 5 | **Give ConfigValidator full `crt_engine` fidelity** — stop the pessimistic 39-vs-35 / 0.98-vs-1.17 | C4 | MED | MED | `_params_to_crt_config` uses 5 flat params + DEFAULTS |
| 6 | **Persist `bitnet_score_at_entry`** to `TradeRecord` — unblock the adaptive-threshold loop | C3 | LOW | MED | `backtest_v2.py:200`; CSV 0× `bitnet_*` |
| 7 | **Fix feedback Break 2 + Break 3** — live feature vector + in-session hot reload | C3 | MED | MED (compounding) | `velvety-gosling` |
| 8 | **Calibrate the assumption-gates** — derive thresholds from data, not magic numbers | C4 | MED | MED | every gate is hardcoded |
| 9 | **Decide TP3/runner** — winners capped at TP2 (~+1.9R), no tail | C4 / ROI | MED | MED | `from-foamy-swan` |
| 10 | **Rule each sidecar in or out** — zone-expectancy, TradeNet stub, orchestrator consensus: wire-and-measure (weight 0.0) or shelve | C3 | MED | UNKNOWN→measured | inventory in deliverable 7 |

## Fold-in for the live/backtest gap

Several "high impact" numbers above are **backtest-measured**. `UltronRiskGate` + `ExecutionPlannerV1_2` are
live-only and not in the backtest spine, so live PnL is unverified. Action #1's cutover should be paired with
a short live/forward check before scaling size.

---

> **STATUS UPDATE 2026-06-03 — actions #1 & #2 executed.** Governed cutover done: `ACTIVE_VERSION` →
> **`v4_multi_2026_06`** = the running ml-Gaussian `deepdeektry` lineage + BNBUSDT all-sessions override
> (SOL excluded, PF~1). Validated APPROVE (BNB score 0.6458, 39 trades); both `config_integrity` guards
> now green (`active_version_is_governed=True`, `validation_summary_is_fresh=True`) — the ungoverned
> `deepdeektry` bypass is closed. Production-path ROI lineage = the +20.59% sweep. Repeatable script:
> `scripts/maintenance/_promote_v4_bnb_cutover.py`. **Remaining live caveat:** Ultron + ExecutionPlanner
> are live-only (not in the backtest spine) — pair with a short forward check before scaling size. #3–#5 open.

## If your goal is maximum profitability, do these next 5 things in order

1. **Promote BNBUSDT V3 through the governed path.** It is built, validated APPROVE, and *measured* at
   +4.91% → **+20.59%** (PF 1.79→2.54, 15→35 trades, DD ~3%). Hold SOL (PF ~1); keep ETH/BTC off. This is
   pure throughput-*policy* ROI — **no new code, no new intelligence.**
   *(Governed step: confirm the merge base is the section-superset, write a real `PROMOTED` entry, rehash,
   then flip `ACTIVE_VERSION`. Operator-authorized.)*

2. **Bring production back under governance.** Stop trading the ungoverned `deepdeektry`; make
   `config_integrity.py` (`validation_summary_is_fresh` + `active_version_is_governed`) a **hard
   pre-run/pre-promote gate**; extend `config_hash` to cover the validation_summary lineage so a stale
   summary can't pass again. (Doing #1 the governed way *is* the first instance of #2.)

3. **Make "enabled" mean "consumed," starting where it protects money.** Wire **drift → size-down/skip**
   (already detected, not acted on), and fix the 14 standing correctness bugs in the same pass. This is the
   cheapest capital protection available and removes hot-path fail-silent behavior.

4. **Make the validator tell the truth.** Close the `crt_engine`-fidelity gap (validate on the full engine
   section, not 5 flat params) and calibrate the hardcoded gate thresholds from data — so promotions reflect
   what the live engine actually does, not a pessimistic proxy.

5. **Extend the throughput-policy method, not the model.** Run per-instrument session-override sweeps wherever
   the production-path sweep supports it; treat the ~35-trade ceiling as a detection-supply/policy limit
   (upstream data + session policy). Only after #1–#4 are done — and a built signal has *earned* weight by
   measurement — consider any new intelligence.

> **Success criterion answered:** if all new feature development stopped for 30 days, the changes that most
> increase profitability are #1–#5 above — **promoting already-built ROI and fixing governance / throughput /
> measurement / assumptions.** Not one of them is new intelligence.
