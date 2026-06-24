# Plan — Link the Pipelines: "Spine-as-Hypothesis" (backconstruct a research forensics pipeline from the full backtest)

## Context — why this change

Today the BNBUSDT M15 conclusions ("volatility has memory, direction doesn't"; expansion edge
net E[R] = −0.439R; 0 BH-survivors) came **only** from `src/research/` running *toy* hypotheses
(`ExpansionBreakout`, `MeanReversion`) — simple `detect(window) -> Signal` functions that never
touch the production decision spine. The full production backtest (`backtest_v2.py` →
`EngineRunner` → CRT/Gaussian/Zone/RR → Fusion → RegimeGovernor → Decision → ExecutionPlanner →
UltronRiskGate) has **never been measured under the research truth standard** (intrabar_fixed
exits, 12 bps round-trip cost, beats-control, OOS retention, permutation + Benjamini-Hochberg FDR).

The two pipelines today share exactly **one** primitive — `CandleLoader`
(`runtime/backtest_v2.py:626`) — and are otherwise isolated *by design* (Edge Discovery Program /
Pipeline-A vs Pipeline-B doctrine). The question: **can we link them so the backtest "forces all
its layers and data" through, and reverse-construct a research forensics run whose hypothesis IS
the production spine?**

**Intended outcome:** a single new adapter (`SpineHypothesis`) that satisfies the research
`Hypothesis` Protocol but whose `detect()` is the full production spine. It plugs into the
*unchanged* research machinery — `HypothesisRunner` (forward-walk), `EdgeAggregator`,
`QualificationGate` (7 gates), and `forensics.py` (loss decomposition). Result: an apples-to-apples
answer to "does the real 8-layer system produce a *qualified* edge, or does it die under honest
exits + cost + controls just like the toy hypotheses?" — plus the same loss-mechanism decomposition
the forensics layer already produces.

## The key architectural insight

Both surfaces are signal generators with the **same shape**:

| | Research `Hypothesis.detect()` | Production spine entry |
|---|---|---|
| input | `window: list[Candle]`, `features`, `ctx` | candle stream + 35-dim CANONICAL_FEATURES |
| output | `list[Signal]` (entry, dir, `sl_atr_mult`, `tp_atr_mult`, `atr`) | `TRADE_OPENED` w/ price-based entry/SL/TP at `EXECUTE` |

So the spine **is** a hypothesis. The conversion is mechanical:
`sl_atr_mult = abs(entry - sl) / atr`, `tp_atr_mult = abs(tp - entry) / atr` — exactly the inverse
of how `ExecutionPlannerV1_2` derived the prices. Once wrapped, **zero changes** are needed to the
research measurement/qualification/forensics code: it already speaks `Signal`.

## Isolation direction (the one hard constraint)

The boundary must keep pointing **down the decision flow** (per `service-boundary-map.md` hard
rule + Goal invariant #5 "execution authority stays isolated"). So:

- **Research must NOT import the live spine upward.** The adapter is the only coupling, and it
  lives on the research side, importing the spine **through a thin callable interface**, not the
  reverse. The spine never learns research exists.
- Reuse the existing precedent: research already imports `CandleLoader` as an *allowed proven
  primitive* (local-scope import). `SpineHypothesis` extends that pattern — it imports the spine
  entry surface in local scope, behind a `SpineSignalSource` Protocol, so the dependency is
  invertible later (Trd-M4 `BacktestRunner` interface) without touching research call sites.

## Determinism reconciliation (research `detect()` must be PURE; the spine is stateful)

The research contract requires `detect()` to be pure/deterministic/no-lookahead. The spine has
stateful + non-deterministic parts. The adapter neutralizes each, all **already supported** by
existing config/flags — no spine code changes:

1. **LLM tie-breaker** → force neutral. `llm_inference_client` already returns `1.0` after
   `fail_count_disable`; adapter sets the disable path / `llama_gate` off so it is deterministically
   neutral (invariant #3: LLM is advice, never a trigger — satisfied by construction).
2. **Async CognitiveBus emission** (`engine_runner.py:1007`) → fire-and-forget; make it a no-op /
   disabled in adapter mode so it can't perturb timing or write side-channels.
3. **Adaptive controllers / belief tracker** → run with persistence disabled (fresh per run) so the
   run is a pure function of (candles, config). Seeded slippage is irrelevant here because the
   research forward-walk owns exits, not the spine.
4. **No-lookahead** → the spine is already streamed candle-by-candle with timestamp-keyed features
   (`backtest_v2.py:1731`); the adapter emits a `Signal` at the `EXECUTE` bar and hands
   `candles[entry_index+1:]` to `forward_walk()` — the existing `assert future.index > entry_index`
   guard enforces it.
5. **Features ("all data")** → today research passes `features={}`. The adapter precomputes the
   full 35-dim `CANONICAL_FEATURES` once via `FeaturePipeline` (timestamp-keyed, same as the
   backtest) and feeds them to the spine — this is the "force all data through" requirement.

## What gets built (the recommended shape)

A new isolated module set under `src/research/` (Pipeline-B side), spine untouched:

- `src/research/adapters/spine_signal_source.py` — `SpineSignalSource` Protocol +
  `ProductionSpineSource` impl: wraps `EngineRunner` + `CRTEngine` + `FeaturePipeline`, runs a
  window deterministically (LLM/async/adaptive neutralized), returns `(entry, dir, sl_px, tp_px,
  atr)` at `EXECUTE`, else nothing.
- `src/research/hypotheses/spine_hypothesis.py` — `SpineHypothesis` implementing the `Hypothesis`
  Protocol; `detect()` calls the source and converts price SL/TP → `sl_atr_mult`/`tp_atr_mult`
  `Signal`. `economic_rationale="production_spine_composite"`, `family="composite"`.
- `configs/research/research_config_spine.json` — research_config variant whose `signal` block
  defers to the spine (apply_signal_defaults=false) and points at the production config version to
  load (e.g. `v2_multi_2026_04`). Its own SHA-256 provenance flows into the edge_report.
- Register in `src/research/registry.py`; expose via existing `python -m research.cli
  run|qualify --hypothesis spine`. **No new CLI** — reuse `cli.py`.

Then the *unchanged* research stack produces, for the spine:
- `edge_report.json` (deterministic, byte-comparable) — spine's NET win-rate/PF/expectancy vs the
  same controls the toy hypotheses faced.
- `qualification_report.json` — does the spine PROMOTE / REJECT / INSUFFICIENT through all 7 gates
  (incl. beats-control + OOS + permutation + BH)?
- `forensics` decomposition — intrabar-damage matrix, loss mechanisms, opportunity profile,
  regime/session cuts — **on the real spine's trades**.

## Verification

- **Determinism:** run `--hypothesis spine` twice → byte-identical `edge_report.json`
  (the existing determinism guarantee; the adapter must add no wall-clock / unseeded RNG).
- **Equivalence sanity:** the spine adapter's entry bars + price SL/TP must reconcile against a
  normal `backtest_v2.py` run on the same CSV+config (same `TRADE_OPENED` timestamps, same SL/TP) —
  proves the adapter faithfully reproduces the spine, i.e. truly "forces all layers through."
- **Truth-standard parity:** confirm exit model = `intrabar_fixed` on both sides (already the
  governing model — `CRTConfig.exit_model` and `forward_walk.exit_model`), so the comparison to toy
  hypotheses is fair.
- **Governance scoring (Five Questions):** (1) deterministic ✓ (2) comparable ✓ (3) auditable via
  edge_report+manifest ✓ (4) LLM-reasonable ✓ (5) execution authority isolated — **must verify** no
  upward import and spine cannot be triggered by research. Append §6 SESSION LOG.

## Open forks (confirming with user before finalizing)

1. Deliverable shape: hypothetical **design doc only** vs design doc **+ buildable adapter plan**.
2. Target research artifact: **forensics decomposition**, **qualification gate**, or **both**.
