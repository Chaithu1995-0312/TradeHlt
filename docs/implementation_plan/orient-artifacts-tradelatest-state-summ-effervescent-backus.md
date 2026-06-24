# Plan: Make ZoneGate `k` configurable (config-first) + clean up the dead per-zone path

## Context

Conceptual discussion proposed switching ZoneGate from "per-zone threshold" gating to
kWTA / top-k "competition between zones." Grounding that against the real code shows the
live spine **already** does top-k (k=3) competitive aggregation — so the work is not a
re-architecture, it is two contained, doctrine-aligned cleanups:

1. **Externalize `k`** (currently hard-coded `3`) as a config-first BEHAVIORAL knob, default
   = current value, **byte-parity proven**. This is exactly the §6.5 "classify every constant"
   move (a top-k count is BEHAVIORAL → `CONFIG_WIRED`), giving optionality/measurability
   without claiming any new authority.
2. **Clean up the dead per-zone path** — the per-zone-threshold `allowed` decision in
   `BitNetZoneGate.check()` that the live spine never reads.

**Why this and not "install kWTA on the live gate":** ZoneGate is an entry/selection filter,
and the repo's evidence record (F-019…F-035, esp. **F-021** which killed "selection beyond
session" — ZONE produced 0 rejects) means new gating architecture has **no earned authority**
(§6.5 Authority Ladder). A config knob grants *tunability, never authority*. Default stays
identical, so live decisions do not change until evidence justifies a different `k`.

## Key finding — how the live ZoneGate actually decides today

- `BitNetZoneGate.check()` (`src/engines/live_engine.py:273-302`) scores the bar against **all**
  zones, computes a per-zone `allowed` (any zone over its own `threshold`), and returns
  `top_scores = sorted(all_scores, reverse=True)[:3]` plus `best_score`, `zone_id`, `reason`.
- The live spine `_zone_model_fn` (`src/core/engine_runner.py:596-615`) **ignores** the per-zone
  `allowed`/`reason`. It feeds `top_scores` into `compute_weighted_cluster_score()`
  (`src/engines/zone_gate_engine.py:106`, which itself applies a `>0.15` spread-rejection) and
  then `run_zone_gate_engine()` gates on the single global
  `engine_runner.bitnet_zone_threshold` (= `0.25` in the active `v2_multi_2026_04.json`).
- **Net live decision = `weighted_top-3_cluster_score ≥ bitnet_zone_threshold`.** The per-zone
  threshold path is computed-but-dead on the live spine.

The only hard-coded `k` is `[:3]` at `src/engines/live_engine.py:292`. A related magic number
`len(top_scores) >= 2` lives at `src/core/engine_runner.py:602`, and `0.15` (cluster spread)
lives in `compute_weighted_cluster_score`.

## Scope decision (chosen): A+B — configurable `k` + dead-code cleanup, recommend insertion point

**Recommended insertion point:** thread `k` through the gate constructor (mirrors the existing
`zone_min_samples` plumbing), single source of truth at `live_engine.py:292`. Do **not** change
the `engine_runner` aggregation math — it already consumes whatever `top_scores` it is given.

## Changes

### 1. Config: add the BEHAVIORAL knob (hash-neutral — `engine_runner` is not the `params` block)

`configs/production/v2_multi_2026_04.json` → `engine_runner` section (next to
`bitnet_zone_threshold`, `zone_gate_execution_mode`, `zone_mode`):

```json
"zone_gate_top_k": 3
```

Also add `zone_gate_top_k: 3` to `ENGINE_RUNNER_DEFAULTS` in `src/core/engine_runner.py`
(the defaults layer tests merge via `dict(ENGINE_RUNNER_DEFAULTS)`), so `_cfg_require` resolves
under test and live. **Default = 3 ⇒ byte-identical.** No `_compute_hash.py` rehash (the hash
covers the `params` block only; `engine_runner` edits are hash-neutral — confirm in verification).

> Optional, same-section, same byte-parity discipline (fold in or defer): `zone_cluster_min_n: 2`
> (replaces the `>= 2` magic at `engine_runner.py:602`) and `zone_cluster_spread_max: 0.15`
> (the spread constant in `compute_weighted_cluster_score`). `k` is the must-have; these two are
> the "classify every constant" tail and can be a follow-up to keep the parity diff minimal.

### 2. Thread `k` into the gate (fail-fast, no silent default — §6.5 A1 rule)

- `src/engines/live_engine.py`
  - `BitNetZoneGate.__init__`: read `self._top_n = int(_cfg.get("zone_gate_top_k", 3))` from the
    existing `config` dict (same `_cfg` already used for `zone_min_samples`).
  - Line 292: `top_scores = sorted(all_scores, reverse=True)[: self._top_n]`.
  - `get_zone_gate(path, min_samples, top_n=3)`: pass `top_n` into the
    `config={"zone_min_samples": ..., "zone_gate_top_k": top_n}` dict.
- `src/core/engine_runner.py:416`: pass
  `top_n=_cfg_require(self.config, "zone_gate_top_k", "engine_runner")` into `get_zone_gate(...)`,
  using the strict `_cfg_require` accessor already used for `bitnet_zone_threshold` (raises on a
  missing key — no `.get(key, literal)` soft default).

### 3. Dead-code cleanup — conservative, FLAGGED (do **not** mass-delete)

The per-zone `allowed`/`reason` is dead **on the live spine** but is part of the documented
public return contract of `check()` (`live_engine.py:84-86, 207-212`) and is referenced by the
manual `src/bitnet/_smoke_test.py` (via the disabled / missing-registry early-return branches).
`tests/test_zone_gate.py` exercises a *removed* `ZoneGate` class (all skipped) and does not pin
this path; `tests/test_zone_gate_instrumentation.py` only covers the module counters.

Recommended cleanup (truth-preserving, §6.2):
- **Keep** the `allowed`/`reason`/`zone_id`/`threshold` return fields (standalone-API contract).
- Add a short comment at the scoring loop documenting that the live spine bypasses per-zone
  `allowed` — the live decision is the cluster score vs the global `bitnet_zone_threshold`. This
  removes the *confusion* (the actual "dead code" smell) without breaking the contract.
- Name the `>= 2` magic via the optional `zone_cluster_min_n` knob above (if folded in).

> Decision to confirm at implementation time: keep-and-document (recommended) vs. fully removing
> the per-zone `allowed` computation. Removal would also require trimming the contract + the
> `_smoke_test.py` references; given zero active-test coverage either is mechanically safe, but
> keep-and-document is the lower-risk, append-discipline choice.

## Files touched

- `configs/production/v2_multi_2026_04.json` (add `zone_gate_top_k`)
- `src/core/engine_runner.py` (`ENGINE_RUNNER_DEFAULTS`, `get_zone_gate` call at ~416,
  optional `>= 2` → knob at ~602)
- `src/engines/live_engine.py` (`BitNetZoneGate.__init__`, `check()` line 292, `get_zone_gate`)
- (optional) `src/engines/zone_gate_engine.py` (`compute_weighted_cluster_score` spread knob)
- `tests/` — add a focused test that `zone_gate_top_k` flows through and that `k=3` reproduces
  the incumbent `top_scores`.

## Verification (byte-parity is the gate — §6.5)

1. **Determinism / byte-identical ledger on BNBUSDT + SOLUSDT** with default `k=3`: run the
   existing backtest on both instruments before/after the change and diff the trade ledger —
   must be byte-identical (the §6.5 parity proof). Use the established determinism/full-artifact
   gate (`metrics_oracle` / determinism harness) referenced in prior batches.
2. **Hash-neutrality**: confirm `configs/production/ACTIVE_VERSION` config SHA-256 is unchanged
   after the JSON edit (verify `engine_runner` is outside the hashed `params` block); if it
   *does* change, run `python scripts/maintenance/_compute_hash.py` and note it.
3. **Targeted pytest**: new knob-flow test + `tests/test_zone_gate_instrumentation.py` (counters
   unaffected) + `python src/bitnet/_smoke_test.py` (contract intact).
4. **Knob actually bites**: a quick run with `zone_gate_top_k: 1` should change `top_scores`
   length to 1 (and is expected to alter the cluster score) — confirms the wire is live, then
   revert to `3`.
5. **ORIENT_RUNTIME**: confirm `ACTIVE_VERSION` = `v2_multi_2026_04` (patch branch, per F-016)
   before/after so the edit lands on the right config.

## Doctrine notes

- Authority Ladder (§6.5): this grants **tunability, not authority**. Default unchanged ⇒ no
  live behavior change; `k` may only earn a non-default value via demonstrated ΔG001.
- Config-First A1 rule: strict `_require`/`_cfg_require`, no `get(key, literal)` soft default.
- §6.2 truth-maintenance: cleanup is keep-and-document (append-discipline), not silent deletion.
- SESSION LOG (§6) on implementation; if a finding flips, update `docs/current-findings.md`.
