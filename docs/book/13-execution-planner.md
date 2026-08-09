# Chapter 13 — The Execution Planner: From Decision to Order Geometry

**Part V — Execution**
Status of this chapter: Written (citation corrected + backtest/live scope narrowed, reconciliation pass 2026-08-07)

## Why this chapter exists

An ACCEPT from the Decision Engine (Chapter 12) is still just an approval — it's not yet an order.
Something has to turn "yes, trade this" into a concrete entry price, and classify *what kind* of
trade this is. This chapter covers that step, and flags two live, unresolved issues that anyone
touching this code should know about before assuming the geometry it produces is trustworthy.

## What problem it solves

Explains what `ExecutionPlannerV1_2` actually computes — and, just as importantly, what it
deliberately does *not* compute.

## What you need to already know

[Chapter 12](12-decision-engine.md) — the planner only runs on an ACCEPT decision.

## The idea

### A classifier, not a geometry engine

`src/config_layer/execution_planner.py`'s `ExecutionPlannerV1_2.plan()` is, at its core, an intent
classifier plus a gate. It sorts an accepted setup into one of four intents — BREAKOUT, PULLBACK,
LIQ_SWEEP, REVERSAL — derives an entry price appropriate to that intent, and delegates final
approval to `GateIntelligence`. **Stop-loss, take-profit, and reward:risk are explicitly not
computed here.** That geometry comes from a standalone pure function, `compute_crt_levels`, in
`src/core/gate_intelligence.py:24` (corrected citation — its docstring states it "mirrors
`crt_engine_v2.py`" the [CRT engine's](08-crt-state-machine.md) own SL/TP formula, and
`execution_planner.py`'s own module docstring points here too; it does not live inside
`crt_engine_v2.py` itself). CRT owns the SL/TP math conceptually because it's the module that
understands the structural levels (sweep point, displacement extent) the stop and target are
actually measured against — `compute_crt_levels` is the callable that mechanism is exposed through.

### An open architectural caveat: which config the planner's geometry actually sees

There is a documented split-brain in how `CRTConfig` gets resolved on the *programmatic* path
(tests, the tuner, embedders — anywhere `BacktestRunner(cfg)` is called with `crt_config=None`):
in that case, `ConfigBuilder.build()` runs with no overrides, and the router's hardcoded
FOREX/CRYPTO default profiles win — the production JSON config is never actually opened. Concretely,
`expansion_atr_min_distance` ends up at `0.08` on this path versus `0.30` in the production JSON — a
3.75× difference on the very gate that governs the DISPLACEMENT→EXPANSION transition
([Chapter 8](08-crt-state-machine.md)'s state machine). The CLI entry point is unaffected — this is
specifically a programmatic-construction gap. It's open, not yet fixed, and worth knowing about
before trusting a programmatically-run backtest's structural-gate behavior at face value.

### A second open caveat: SL geometry uses the wrong units — but only on the live path

A separate, confirmed issue concerns `compute_crt_levels` (`gate_intelligence.py:24`) itself: its
`sl = low - sl_atr_buffer * atr` (LONG case; mirrored for SHORT) formula treats its `atr` parameter
as an absolute price quantity, and multiplies it directly against `low`/`high`, which *are* absolute
prices. The function itself is unit-agnostic — the bug is entirely in what its callers pass as
`atr`. Tracing both callers precisely:

- **Backtest path — correct.** `crt_engine_v2.py::build_trade` (the canonical CRT state-machine
  path) computes `atr = state.atr_abs`, a field populated separately via
  `self.detector.compute_atr(candles, self.config.atr_period)` — genuinely absolute, in price units.
  The surrounding code even carries an explicit comment warning against confusing it with the
  close-relative feature (`crt_engine_v2.py:1118`: *"NOT FM-041: FM-041 `atr` is CLOSE-RELATIVE
  (atr_14_raw/close); state.atr_abs [is different]"*) — the backtest path was written with this
  exact confusion in mind and avoids it.
- **Live path — broken.** `live_engine_hook.py::_build_engine_input` (`:442`) instead reads
  `"atr": _require_feature_value(trade_data, "atr")` — the plain canonical feature, which per
  [Chapter 7](07-feature-pipeline.md) is close-relative (`atr_14_raw / close`), never converted to
  absolute. This value flows straight into `compute_crt_levels`'s `atr` parameter at
  `live_engine_hook.py:916`. On XAUUSD (~$2,000/oz) this produces stop-loss buffers roughly three
  orders of magnitude too small (sub-cent stops on LIQ_SWEEP entries), and the same unit confusion
  is implicated in unbounded position sizing downstream.

**The corrected scope, stated precisely: backtests are not affected by this defect** — every
Program 1–8 result in [Chapter 19](19-research-programs.md) and every backtest-based finding cited
throughout this book used the correct `state.atr_abs` path. The defect is real, confirmed from
source, and **currently unfixed**, but its blast radius is the live execution path only — which, per
F-010, has never been used to produce a verified PnL result anyway. It is not a hypothetical, and it
is not something this book fixes as a side effect of documenting it.

## Proposed remediation (Grok review pass — options only; no code in this book)

The review of this book correctly noted that flagging without a path feels passive. Below are
**proposal options with trade-offs**. None of these is authorized by this chapter: authority still
requires an explicit owner decision + construction protocol + parity proof
([Chapter 16](16-config-first-and-promotion.md) Authority Ladder).

### ATR unit mismatch — proposed options

Now that the exact broken call site is confirmed (`live_engine_hook.py::_build_engine_input:442`
feeding a relative feature into `gate_intelligence.py::compute_crt_levels`), and that
`crt_engine_v2.py` already maintains a correctly-absolute `state.atr_abs` for the same purpose on
the backtest path, the options below can be stated more concretely than a first pass could:

| Option | What it does | Pros | Cons / risks |
|---|---|---|---|
| **A. Multiply by close at the live call site** | In `_build_engine_input`, emit `atr_abs = atr_relative * close` instead of the raw relative feature, so `live_engine_hook.py:916` passes an absolute value into `compute_crt_levels` | Surgical — one function, one call site; matches the known closed form used elsewhere for FM-022/023-style defects (F-061); easy to parity-test against the backtest path's `state.atr_abs` | Must confirm no *other* live-path consumer relies on `engine_input["atr"]` staying relative; risk of double-scaling if any caller already converts |
| **B. Compute a true `atr_abs` on the live path** | Give the live hook its own `self.detector.compute_atr(...)`-equivalent, mirroring exactly what `crt_engine_v2.py` already does for backtests, instead of reusing the relative feature at all | Structurally matches the already-correct backtest path (same formula, same units, provably consistent); no derived-from-relative approximation | Needs the live hook to maintain its own rolling candle buffer for the ATR period, duplicating state the backtest engine already tracks |
| **C. Config-gated dual path** | `geometry_atr_basis: relative_legacy \| absolute_price` with default = current (broken) live behavior, byte-identical until flipped | Matches the F-061/F-066 pattern (strict require + default freeze); enables an A/B shadow before committing | Longer-lived dual code; still needs freeze-pin re-certification before activating; keeps a known-broken default live unless explicitly flipped |

**Recommended default for a future implement turn:** **B** is the cleanest fix in principle (it
makes the live path structurally identical to the already-correct backtest path, rather than
deriving an approximation from the relative feature) but costs more to implement. **A** is the
pragmatic near-term fix given `close` is already available at the live call site. Either way: land
behind a strict config key with the current (broken) behavior as the explicit, named default —
never a silent flip — prove parity against `crt_engine_v2.py`'s `state.atr_abs` values on historical
data, then open a shadow config and measure ΔG001 before any promotion. Since backtests are
unaffected by this bug (confirmed above), there is no backtest-ledger parity risk from *not* fixing
this immediately — the urgency is specific to live execution, which is not currently the production
path anyway (F-010).

### F-057 CRTConfig programmatic split-brain — proposed options

| Option | What it does | Pros | Cons / risks |
|---|---|---|---|
| **1. Always load ACTIVE_VERSION** | When `crt_config is None`, `BacktestRunner` / `ConfigBuilder` loads production JSON via `get_prod_config()` instead of bare FOREX/CRYPTO profiles | Closes the 3.75× `expansion_atr_min_distance` gap; CLI and programmatic paths agree | Any test that silently relied on hardcoded profiles will change behavior — needs a test inventory |
| **2. Fail-closed** | Raise if `crt_config is None` on programmatic construction | Forces every caller to be explicit | Breaks tuner/tests until each injects config; noisier migration |
| **3. Explicit profile enum** | Require `profile="production" \| "router_default"` — no implicit default | Makes the choice auditable | API churn; still easy to pick the wrong profile |

**Recommended default for a future implement turn:** **1 with a loud WARN log** on the migration
window, plus a focused regression that asserts programmatic build equals CLI-loaded production for
the structural gates that F-057 names. Treat as backtest Phase-2 work (as the finding already
scopes it) — not a silent one-line patch.

### What this book still will not do

These remediations are **not implemented by documenting them**. Implementing either issue is a
governed code change (construction protocol, tests, parity, owner approval on behavior change).
Status remains: **OPEN / awaiting decision**.

## Classification

| Concept | Status |
|---|---|
| `ExecutionPlannerV1_2.plan()` intent classification | Production |
| SL/TP geometry (`compute_crt_levels`, `gate_intelligence.py`) | Production, **known defect on the live call path only, unfixed** (ATR unit mismatch); backtest path (`crt_engine_v2.py::build_trade`, `state.atr_abs`) confirmed correct |
| Programmatic `CRTConfig` resolution (non-CLI paths) | Production, **known split-brain, OPEN** (F-057) |

## Authoritative sources

- `src/config_layer/execution_planner.py` — `ExecutionPlannerV1_2.plan()`.
- `src/core/gate_intelligence.py:24` — `compute_crt_levels`, the actual SL/TP/RR geometry function (owned by CRT conceptually, not the planner; not located in `crt_engine_v2.py` — corrected citation).
- `src/config_layer/crt_engine_v2.py::build_trade` (~line 2201) — the backtest path's own SL/TP construction, using the confirmed-correct `state.atr_abs`; `:1118` carries the explicit relative-vs-absolute warning comment.
- `src/runtime/live_engine_hook.py:442` (`_build_engine_input`) and `:916` (`compute_crt_levels` call) — the confirmed-broken live call site.
- `docs/topics/execution-planning.md` — the always-synced topic doc.
- `docs/current-findings.md` F-057 — the `CRTConfig` programmatic split-brain, in full.
- `docs/topics/ai-automation-agent.md` §GateIntelligence cross-references (if present) — the approval delegate.

## Unresolved questions

- **The ATR unit mismatch (live path only)** — identified, scoped, root-caused to the exact call
  sites above, proposed above (options A/B/C); still awaiting owner pick + implement authority.
  Rolled up in [A2](A2-unresolved-questions.md).
- **F-057's `CRTConfig` split-brain** — status OPEN; proposed options 1/2/3 above; still
  "backtest Phase 2" not implemented as of this writing.

---
**Previous:** [Chapter 12 — The Decision Engine](12-decision-engine.md) · **Next:** [Chapter 14 — Ultron Risk Gate](14-ultron-risk-gate.md)
**Related:** [Chapter 08 — The CRT State Machine](08-crt-state-machine.md) (owns the SL/TP math this chapter describes)
**Memory:** `docs/memory/architecture-memory.md`.
