# Plan: Restructure & correct `active_models.yaml` into a 3-truth-layer registry

## Context

You asked (of three possible deliverables) for **(1) a CRT state-truth table** — State → Detection
function → Config keys → Default thresholds → OHLCV inputs — and **(2) a machine-readable model
registry handoff** so Claude gets active-model truth without documentation hunting.

Investigation shows **both already exist** in [`active_models.yaml`](../../active_models.yaml) — the
file CLAUDE.md declares is "loaded first in every Claude session." So this is not a build. But the
file has **drifted from the code** and, more importantly, **conflates three distinct kinds of truth**
into single fields — the flaw you identified. The fix is not "intent OR runtime" but a schema that
keeps them as separate layers, mapping onto the doctrine the repo already runs (§4.0 Runtime Truth
Precedence: Tier-0 runtime ≠ findings/research ≠ history/architecture).

**Intended outcome:** every model entry becomes self-documenting across three truth layers, so future
corrections are *additive, not destructive* — no architectural intent is lost, and no session
inherits a false "this is live / this is proven" belief.

## Backward-compat: SAFE (verified this session)

`grep active_models` over the repo → **zero `.py` matches**; only CLAUDE.md (a read reference) and
this plan cite it. **No loader, no test asserts on the YAML shape** — the structural refactor breaks
nothing. This resolves the "downstream tools assume the schema" risk.

## Target schema (per your recommendation)

Every model/engine entry is refactored to four layers:

```yaml
<model>:
  intent:    # Layer 1 — Architectural truth: what it was DESIGNED to answer (preserve, never delete)
  runtime:   # Layer 2 — Runtime truth: what actually EXECUTES today (engine, features, file:line, active)
  evidence:  # Layer 3 — Research truth: what SURVIVES evidence (findings, validated:true/false)
  status:    # rollup: e.g. active | orphaned | experimental | dormant
```

## Ground truth established this session (Layer-2/3 source)

- CRT = **9 states** (`RANGE, SHADOW_PENDING, SWEEP, DISPLACEMENT, EXPANSION, EXPIRED, RETEST,
  EXECUTION, RESOLUTION`); `VALID_TRANSITIONS` [`crt_engine_v2.py:1073`](../../src/config_layer/crt_engine_v2.py#L1073), enum :63. No `CANCELLED`.
- Live Gaussian = `HeuristicGaussianEngine.compute`, **3 features** — `src/engines/heuristic_gaussian_engine.py:305`. `v4_mirrored` (38-dim NB, 242k, corr 0.2066) is **experimental, not wired**.
- ZoneGate = full **38-vector** contract, fail-open 0.5 — `src/engines/zone_gate_engine.py:163`.
- RR = candle-polarity index on close/high/low, `min_rr` unused — `src/engines/rr_engine.py:45`.
- S1–S10 exist ([`strategy_orchestrator.py`](../../src/strategies/strategy_orchestrator.py)) but are
  **orphaned** — feed dormant `FusionEngine.fuse_strategy_results()`, not the spine.
- 4-engine fusion gate is **OFF in backtests** (`BACKTEST_ENGINE_GATE=0`, F-037); live runs it.

## Corrections (all 8 approved; refined per your review)

| # | Item | Correction under the layered schema |
|---|---|---|
| D1 | CRT state count | `states: 10` → **9** (matches `state_list` + code). |
| D2 | CRT detection | Split into **`detection` states** (range/sweep/displacement/expansion/retest/expired) — each gets `file_line`, `config_keys`, `defaults`, `ohlcv_inputs` verified vs code — **and `lifecycle` states**: `shadow_pending: {type: lifecycle_state}`, `execution: {type: terminal_execution_state}`, `resolution: {type: post_trade_state}`. **No invented detection rules** for lifecycle states. |
| D3 | Gaussian | Split into `runtime:` (`HeuristicGaussianEngine`, 3 feats, `file: …:305`, `active: true`) and `trained_registry:` (`v4_mirrored: {status: experimental, active: false, samples 242000, correlation 0.2066}`). **Both truths preserved.** |
| D4 | ZoneGate | `runtime.inputs` → full 38-canonical-vector + `fail_open: 0.5`; `evidence` → F-041 registry TruthConflict + label caveat. |
| D5 | RR | `runtime` → `type: geometric_filter`, `learning: false`, `min_rr: retained_but_unused`, inputs `[close, high, low]`; `evidence` → F-038. |
| D6 | Strategies S1–S10 | Add `status: orphaned`, `wiring: sidecar`, `participates_in_live_spine: false` (dormant `fuse_strategy_results`). |
| D7 | engine_runner / philosophy | **Keep** the intent questions; add `authority: {level: architectural_intent, validated: false, findings: [F-019, F-037, F-040, …]}`. Add F-037 note that fusion gate is OFF in backtests / ON live. **Philosophy preserved, annotated — not deleted.** |
| D8 | header | Refresh `Last verified against`; add cross-link to [`model-intent-and-feature-ownership.md`](../../docs/topics/model-intent-and-feature-ownership.md); document the 4-layer schema convention inline at the top so future edits stay additive. |

All are `DOC_DRIFT` (code is authority); no finding is reversed and this is **not** `ACTIVE_VERSION`
config → within §6.2 auto-fix calibration. D3 (Gaussian split) is the most consequential and is now
non-destructive by construction (both truths retained).

## Files

- **Edit:** [`active_models.yaml`](../../active_models.yaml) — full refactor to the 4-layer schema + all corrections.
- **Read to verify (no edit):** `crt_engine_v2.py` (per-state config keys/defaults/`file:line`),
  `heuristic_gaussian_engine.py`, `zone_gate_engine.py`, `rr_engine.py`,
  `docs/topics/model-intent-and-feature-ownership.md` (already-verified engine truth).
- **No new doc** (§6.2 existing-doc-first): topic doc owns feature-ownership; `active_models.yaml`
  owns the machine-readable registry.

## Out of scope (per your deliverable selection)

- Intent-vs-demonstrated-edge matrix (Model → target → labels → edge → F-id) — not chosen.
- Deep per-strategy S1–S10 documentation — only the layered status flag is added.

## Verification

1. `python -c "import yaml,sys; yaml.safe_load(open('active_models.yaml')); print('ok')"` — parses.
2. Every `runtime.file`/`file_line` resolves to the cited symbol (grep each).
3. `crt.states` (9) == `len(crt.state_list)` == `len(VALID_TRANSITIONS)` in code.
4. Confirm no code depends on the shape: re-run `grep -r active_models --include=*.py` → still 0.
   `pytest -k "active_models or model_registry" -q` (expected: no tests target this file).
5. §7.4 SESSION LOG entry to `assistant_project.md` + dated Discussion entry to the model-intent
   topic doc (§6.4), recording the drift + schema decision (§6.2 audit-trail).
