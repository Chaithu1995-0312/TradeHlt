# Plan: Reconcile the v1/v2 config-lineage divergence (governance trust)

> Created: 2026-06-02 · Updated: 2026-06-02 · Milestone: Production-governance integrity (backlog P1)
> Approach: **Option A — canonicalize the running config as governed (behavior-preserving).**

## Context — why this change

Production runs an **ungoverned config with stale validation evidence**, and the promotion
machinery is primed to silently overwrite it with a *different* lineage on the next promote.
All claims below were verified read-only against the live code/configs (2026-06-02):

1. **Ungoverned active.** `ACTIVE_VERSION` = `v2_multi_2026_04 - deepdeektry` (hand-named,
   spaces in filename). `configs/promotion_log.jsonl` has **0 entries** for it — the last
   *governed* promotion was the clean `v2_multi_2026_04` (config_id `..._candidate_1`).
2. **Stale validation evidence.** The file's actual `params` are
   `retest_depth_max=0.8 / retest_atr_depth_fraction=0.5 / body_ratio_min=0.3 /
   atr_multiplier_min=0.6 / expansion_atr_min_distance=0.3`, but its `validation_summary`
   describes `v2_multi_2026_04_candidate_1` (`final_score=0.5966`, `total_trades=36`) — the
   *earlier* governed promotion with different params. `validation_summary` carries **no
   params fingerprint** → nothing to compare against.
3. **Hash gap hides the desync.** `_verify_config_hash` hashes `params` against the stored
   hash only ([production_config.py:89-108](src/config_layer/production_config.py));
   `validation_summary` is outside the hash, and `get_prod_section` never verifies it at all.
4. **Merge-base foot-gun.** `_load_full_base_config`
   ([promotion_manager.py:440-493](src/governance/promotion_manager.py)) prefers
   `v1_multi_2026_03` (which carries all 6 rich sections); `_write_to_registry`
   ([:545-581](src/governance/promotion_manager.py)) merges new params onto that base **and
   flips `ACTIVE_VERSION`**. The active config has `engine_runner` but **none** of
   `strategy_orchestrator / cognitive_layer / replay_memory / tradenet_meta /
   market_state_cluster / drift_governance` (verified: v1 has all 6, active has 0). → the
   next governed promotion would re-add those sections + change params lineage + flip live in
   one un-asked-for step.
5. **Active silently disables subsystems.** `get_prod_section` **raises** on an absent section
   ([:366-371](src/config_layer/production_config.py)); the 6 missing sections mean those
   subsystems are off/defaulted in production today.

**Outcome wanted:** make the *currently-running* behavior governed and auditable, and remove
the lineage foot-gun — without changing trading behavior or invalidating the recent
ROI/session/OOS baselines (all measured on the deepdeektry params + lean sections).

## Approach — Option A (recommended), not B

- **A (this plan):** keep deepdeektry's params + lean sections, but make them *governed* —
  fresh validation matching the actual params, clean version name, `PROMOTED` log entry.
  Behavior-neutral. Fold in the already-APPROVE'd BNBUSDT/SOLUSDT session overrides (the
  staged `v3_multi_2026_06.json` work) so there is **one** clean governed config.
- **B (rejected here):** adopt v1's rich-section lineage as canonical — that re-enables
  orchestrator/cognitive/replay/etc., which is a *capability* change that alters behavior and
  invalidates current baselines. That re-enablement is the separate "unconsumed intelligence"
  thread; do it deliberately + validated, later — not folded into a governance fix.

## Steps

1. **Canonicalize → governed `v3_multi_2026_06` (behavior-preserving).**
   - Take the running params (+ BNB/SOL `allowed_sessions_overrides`, already validated
     APPROVE) and run `ConfigValidator.validate` across the production instrument set
     (session-override-aware path, already shipped).
   - Write a **fresh `validation_summary` that matches the actual params** (carry a params
     fingerprint — see Step 3), a clean filename (no spaces), and a `PROMOTED`
     `promotion_log.jsonl` entry.
   - **Regression guard (before any flip):** per-instrument backtest metrics of governed `v3`
     must match current deepdeektry behavior (trades/PF/DD within noise) — proves no silent
     change. Reuse the staged `results/validation/v3_multi_2026_06_report.json` evidence.
   - *Flipping `ACTIVE_VERSION` stays the operator's action* (consistent with the prior
     "validated-ready" boundary) — see Out of scope.

2. **Fix the merge-base foot-gun** — `_load_full_base_config` should prefer the **current
   ACTIVE governed config** as merge base (fall back to `v1_multi_2026_03` only if the active
   is sparse/missing `engine_runner`), and **log which base it used**. Future promotions then
   build on what is actually running, not a stale hardcoded v1.
   - File: [`src/governance/promotion_manager.py`](src/governance/promotion_manager.py)
     `_load_full_base_config` (`:440-493`) + the `_BASE_VERSION_FALLBACK` constant.

3. **Two governance guard tests** (`tests/`) — must **fail on current deepdeektry** and
   **pass on reconciled v3** (proves they catch the bug class):
   - **validation-freshness:** fail if `validation_summary` does not correspond to `params`
     (embed + compare a params fingerprint; reuse `_compute_params_hash`).
   - **governed-active:** assert `ACTIVE_VERSION`'s config has a matching `PROMOTED` entry in
     `promotion_log.jsonl`.

4. **Naming hygiene** — `ACTIVE_VERSION` must be a clean version key (no spaces / ad-hoc
   suffixes like `" - deepdeektry"`). Document the rule near the pointer loader
   (`get_active_version`, [production_config.py:60-82](src/config_layer/production_config.py)).

5. **Flag, do NOT silently do:** re-adding the 6 rich engine sections is a separate,
   deliberate, validated capability decision — track it against the evidence map, not here.

## Critical files
- [`src/config_layer/production_config.py`](src/config_layer/production_config.py) —
  `_verify_config_hash` (hash gap), `get_prod_section` (raises on missing),
  `get_active_version`/`PROD_VERSION`, `load_prod_config_from_registry`.
- [`src/governance/promotion_manager.py`](src/governance/promotion_manager.py) —
  `_load_full_base_config` (base preference), `_write_to_registry` (merge + ACTIVE flip),
  `_build_registry_entry`, `_log_event`.
- `configs/production/ACTIVE_VERSION`, `configs/promotion_log.jsonl`, the two
  `v2_multi_2026_04*.json`, `v1_multi_2026_03.json`, staged `v3_multi_2026_06.json`.
- New: `tests/test_governance_integrity_guards.py` (the two guards).

## Verification
- **Behavior-neutrality:** governed `v3` per-instrument backtest metrics ≈ current deepdeektry
  (diff trades/PF/DD within noise) before any flip.
- **Governance integrity:** `PromotionManager.load_version("v3_multi_2026_06")` passes;
  `validation_summary` params-fingerprint == `params`; new `PROMOTED` entry present.
- **Guards prove the bug class:** the two new tests FAIL on current deepdeektry (stale summary
  + ungoverned active) and PASS on reconciled v3.
- **No regressions:** full `pytest -q` green; `_load_full_base_config` base-selection is logged
  and picks the active governed config.
- **Self-doc:** SESSION LOG (§6) appended; touched topic docs synced (§6.1) —
  `config-validation.md`, `promotion-governance.md`.

## Out of scope
- **Flipping `ACTIVE_VERSION`** — operator action (governance gate), done after the
  behavior-neutrality + guard evidence is in hand.
- **Re-enabling the 6 rich engine sections** — separate validated capability decision.
- Drift→action, zone-expectancy weighting, Probability Surface, Trd-M6 — later priorities.
