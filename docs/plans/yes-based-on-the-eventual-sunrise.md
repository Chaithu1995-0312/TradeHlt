# Plan: Reconcile lineage onto v1 canonical + enable rich sections (Option B)

> Created: 2026-06-02 · Updated: 2026-06-02 · Milestone: Production-governance integrity + capability re-activation (P1)
> Decisions: **v1 rich-section lineage = canonical**; **keep validated permissive params + BNB/SOL session overrides**;
> **enable ALL rich sections.** Promotions stop at validated-ready (operator flips `ACTIVE_VERSION`).

## Context — why

The active config (`v2_multi_2026_04 - deepdeektry`) is a **governance bypass**: never promoted (0 `promotion_log` entries; git *"stable before rename"*), hand-edited permissive params (`0.8/0.3/0.6`), and a **stale `validation_summary`** describing the 2026-05-06 governed config (`0.2/0.65/1.0`, score 0.5966) — the integrity hash passes because it only hashes params↔params, so the desync is invisible. It also **omits six engine sections** v1 carries; `get_prod_section` *raises* on an absent section ([production_config.py:336-360](src/config_layer/production_config.py)), so those subsystems are off today.

Chosen direction: adopt **v1_multi_2026_03's full-section lineage as canonical**, carry the **validated permissive params + session overrides** (preserve throughput), and **enable all of v1's rich sections** — turning built-but-dormant intelligence on (the recurring evidence-map theme), under governance.

## What "enable all rich sections" actually does (precise — set expectations)

| Section | Effect when enabled | Decision impact | Action |
|---|---|---|---|
| **strategy_orchestrator** | 5th fusion input `weight_strategy_consensus` >0 (regime profiles 0.10–0.30); runs in **backtest + live** ([backtest_v2.py:1508](src/runtime/backtest_v2.py), [fusion_engine.py:156-158,378](src/core/fusion_engine.py)) | **REAL — changes decisions** | Validate + **regression-measure**; this is the main risk |
| **cognitive_layer** | engine_runner post-decision fire-and-forget emit → ReplayMemory/MarketState/HMF run as **telemetry** | None (sidecar, determinism-safe) | Enable; confirm off the deterministic path |
| **replay_memory** | feeds the cognitive sidecar (now with the 4 repaired per-instrument registries) | None until #6 deterministic wiring | Enable as telemetry; decision-influence stays in the #6 sub-plan |
| **drift_governance** | `replay_drift_governor` — replay package only, **not in spine** | None (won't gate trades) | Enable; note drift→trade-gating is the separate drift→action work |
| **market_state_cluster** | cognitive sidecar prior | None (sidecar) | Enable as telemetry |
| **tradenet_meta** | fusion neural slot is a **stub** ([fusion_engine.py:8](src/core/fusion_engine.py)) | None — **inert** | Enable config; flag that TradeNet is NOT plugged into fusion (separate work) |

Net behavior change = **strategy_orchestrator weight>0** (decisions) + sidecars running (telemetry). The other enables are inert/sidecar today — enabling them is honest config completeness, not new decision power.

## Plan

### B1 — Build the governed canonical candidate `v3_multi_2026_06`
- **Structural base = v1** (all engine sections). **Overlay:** permissive params (`0.8/0.3/0.6`), `retest_atr_depth_fraction=0.5`; `engine_runner.allowed_sessions_overrides` for BNBUSDT (`+ASIA +OFF_SESSION`) and SOLUSDT (validated in #2/#3).
- **Enable flags ON** for the six rich sections. For `strategy_consensus`, adopt v1's intended fusion weights (regime profiles / `weight_strategy_consensus`) — record the exact weight chosen.
- Fresh metadata: clean version key, `created_at`/`promoted_at`, and a **`validation_summary` regenerated from this candidate's own validation** (no stale copy).

### B2 — Validate + regression-measure (the gate)
- Run the override-aware `ConfigValidator.validate` across the production instrument set → require `APPROVE`.
- **Regression report (decision-change is expected here):** per-instrument trades/PF/DD/ROI of `v3` vs current deepdeektry, isolating the **orchestrator-on delta** (run orchestrator weight 0 vs intended weight). Surface the delta; if the orchestrator degrades an instrument, flag it rather than silently shipping.
- **Re-baseline note:** the prior ROI/session-sweep/OOS baselines were measured *without* the orchestrator — they must be **re-measured** on `v3` (the old numbers no longer describe production).

### B3 — Determinism / invariant safety
- Confirm `cognitive_layer`/`drift_governance`/`market_state` run **off the deterministic decision path** (engine_runner emit is post-decision fire-and-forget) → invariant #1 holds. `strategy_orchestrator` is deterministic (S1–S10 over the candle stream, seeded).
- Confirm invariant #2 (four engines) intact — orchestrator is a *5th* additive input, never replaces an engine; absent ⇒ weight 0, not partial fusion.

### B4 — Governance hardening (prevent recurrence)
- **`_load_full_base_config`** ([promotion_manager.py:451,466](src/governance/promotion_manager.py)): prefer the **current ACTIVE governed config** as merge base (v1 is correct *now* under Option B, but hardcoding it is the foot-gun); log the base used.
- **Two guard tests** (`tests/`): (a) **validation-freshness** — fail if `validation_summary` doesn't correspond to `params`; (b) **governed-active** — assert `ACTIVE_VERSION` has a `PROMOTED` entry in `promotion_log.jsonl`. Both should fail on the *current* deepdeektry and pass on `v3`.
- **Naming hygiene:** `ACTIVE_VERSION` must be a clean key (no spaces / ad-hoc suffixes).

### B5 — Stage (no live flip)
- Write `v3_multi_2026_06.json` + `promotion_log` PROMOTED entry. **Operator flips `ACTIVE_VERSION`** after reviewing the regression report (consistent with the prior boundary).

## Critical files
- [`src/governance/promotion_manager.py`](src/governance/promotion_manager.py) — base selection, write/log, ACTIVE flip.
- [`src/config_layer/production_config.py`](src/config_layer/production_config.py) — hash gap, `get_prod_section`, ACTIVE resolution.
- [`src/core/fusion_engine.py`](src/core/fusion_engine.py) — `weight_strategy_consensus` / regime profiles (orchestrator enable).
- [`configs/production/v1_multi_2026_03.json`](configs/production/v1_multi_2026_03.json) (structural base) → new `configs/production/v3_multi_2026_06.json`; `ACTIVE_VERSION`, `promotion_log.jsonl`.

## Verification
- `ConfigValidator` → `APPROVE` for `v3` with a **fresh** matching `validation_summary`.
- Regression report produced (v3 vs deepdeektry, orchestrator-on delta isolated); behavior change understood and accepted, not silent.
- New guard tests fail on deepdeektry, pass on `v3`; `load_version(v3)` clean.
- Full `pytest -q` green; determinism unaffected on the spine; `_load_full_base_config` logs its base.
- `ACTIVE_VERSION` unchanged until operator flip. SESSION LOG (§6) + topic sync (§6.1).

## Out of scope (separate, flagged)
- Flipping `ACTIVE_VERSION` (operator). ReplayMemory→decision wiring (#6 deterministic sub-plan). TradeNet→fusion (un-stub). Drift→trade-gating (drift→action). Re-tuning params.
