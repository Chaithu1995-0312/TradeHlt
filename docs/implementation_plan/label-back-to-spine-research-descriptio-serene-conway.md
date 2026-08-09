# Fix F-038 — RR Fusion Gaussian-Duplicate Defect

## Context

The spine's fusion stack nominally runs 4 independent engines (CRT/Gaussian/ZoneGate/RR), but
F-038 (confirmed, CLAUDE.md repository-truths index) established that the RR slot has been
silently degrading to a **Gaussian duplicate**: the `RRFusionLayer`'s confidence gate almost
always fails, so it discards its own model and returns the Gaussian score verbatim. This means
fusion has effectively run with ≤2.5 independent signals since the layer was shipped, with
Gaussian double-weighted (once directly, once via the RR bypass) — silently biasing every fused
decision toward whatever Gaussian says, undetected until this audit.

Programs 1–2 of the spine edge-discovery effort (F-019…F-028) already concluded the upstream
entry signal carries ~0 standalone edge — so this is **not** a new edge-discovery program. It's
a fusion-integrity defect fix: restore an honest, correctly-weighted fusion before any further
spine work builds on top of a quietly-doubled Gaussian signal. Per CLAUDE.md §6.5 Authority
Ladder, RR fusion never demonstrated ΔG001 improvement — it has no claim to production authority
as-is, so removing it (Option A) is strictly evidence-aligned, not a downgrade.

**Root cause (confirmed via code read):**
- `engine_runner.py:698-709` (legacy path, active by default) calls `RRFusionLayer.score_dict()`,
  which only populates 3 of 38 canonical features (`rr_fusion.py:176-179`) → Mahalanobis
  confidence collapses to ~1e-88.
- The shipped mitigation (`engine_runner.rr_fusion.full_feature_vector`, default `false`) routes
  to `score()` with the full feature vector instead — but confidence is *still* ~5e-5, five
  orders below the `confidence_bypass_threshold=0.3` gate (`rr_pattern_miner.py:299-350`,
  `configs/production/v2_multi_2026_04.json` → `rr_model.confidence_bypass_threshold` /
  `mahal_clip`).
- Whenever confidence < threshold, `_passthrough()` (`rr_fusion.py:35-42`) fires: discards the
  model, returns `final_score = gaussian_score`, `confidence = 0.0`. This is the "duplicate."
- The underlying model (`models/rr_model.json`, trained 2026-05-24, filename hint
  `rr_model_202605_bnb_v2.json` suggests BNB-specific, LedoitWolf covariance with very tight
  precision ~2363) is out-of-distribution for live multi-instrument data even when fed correctly
  — feeding more features does not fix a miscalibrated/overfit covariance.

## Plan

### Phase 1 — Disable rr_fusion (ship now, low ceremony, zero blast radius)

A pure BEHAVIORAL config flip, already supported by existing short-circuit logic — **no engine
code changes required**.

1. **`configs/production/v2_multi_2026_04.json`** (the file `ACTIVE_VERSION` points to — verified
   via `configs/production/ACTIVE_VERSION` = `v2_multi_2026_04`): flip `rr_fusion.enabled` from
   `true` → `false`. Leave `model_path`/`threshold`/`full_feature_vector` untouched — minimizes
   diff and preserves the forensic trail of what Fix A attempted. This is hash-neutral if
   `rr_fusion` is a top-level section (not inside `params`) — confirm with
   `python scripts/maintenance/_compute_hash.py` after the edit; rehash only if required.
   - Only the active file needs this change. `v1_multi_2026_03*.json`, the `_archived_*` files,
     and `v3_multi_2026_06.json`/`v4_multi_2026_06.json` are out of scope: archived configs are
     preserved history (§6.2 rule 4 — never edit), and v3/v4 belong to a different code line
     (F-016: v4 loads only on the post-TP3 line; not active on `patch`).
   - Do **not** touch the `"... - deepdeektry.json"` variant — historical/non-canonical per
     existing truth-audit findings.

2. **Verify the disable path is already idempotent** (read-only check, no code change expected):
   confirm in `engine_runner.py` that `RRFusionLayer(enabled=...)` is constructed from this exact
   config key, and that when `enabled=False` → `is_loaded` stays `False` → the guard at
   `engine_runner.py:682` (`if self.rr_fusion and self.rr_fusion.is_loaded:`) never enters either
   branch, so `rr_result` (the genuine base `RREngine.compute()` output, line 678) flows through
   unmodified into fusion.

3. **Add a regression test** (extend `tests/test_engine_runner_rr_fusion.py`):
   - Build the runner with `rr_fusion.enabled=false`.
   - Assert `rr_result["score"]` equals the base `RREngine` output and that no `"rr_fusion"` key
     is injected (per `engine_runner.py:713-717`, only present inside the loaded-fusion branch).
   - Assert `self.rr_fusion is None` or `self.rr_fusion.is_loaded is False` per however the
     runner short-circuits construction.

4. **Parity/determinism proof** (follow the existing pattern in
   `tests/runtime/test_replay_determinism.py` / `tests/test_bitnet_parity.py`): run a fixed
   replay set through `EngineRunner` pre- and post-config-change and assert every output field
   *except* the RR slot (and anything causally downstream of the RR score, e.g. fused decision
   fields) is byte-identical. This is the parity-proof CLAUDE.md §6.5 requires for any migration.

5. **Findings update (same turn, per §6.2 Findings Mandate):** flip F-038's status in
   `docs/current-findings.md` — `Reversal:` line noting the fix shipped (disable, not retrain),
   and the table-row `Conf` stays `Likely`→ re-evaluate to `Certain` once the regression test +
   parity proof pass. Add a `📝 SESSION LOG ENTRY` per CLAUDE.md §7.4.

### Phase 2 — Optional follow-on: retrain/recalibrate (separate, gated, not blocking)

Only pursue if there's appetite to restore RR as a genuine 4th signal later. This is gated by
`promotion_manager` — no retrained model reaches production without an `APPROVE`d
`ValidationReport`.

1. New read-only script `scripts/validation/validate_rr_model_calibration.py`:
   - Loads the current model + a current multi-instrument eval dataset (via
     `config_layer/rr/rr_dataset_builder.load_dataset()`).
   - **Coverage check:** fraction of eval rows whose Mahalanobis `d_sq` (same formula,
     `rr_pattern_miner.py:322-337`) lands below `mahal_clip` pre-clip — quantifies how little of
     real data the trained covariance recognizes.
   - **Confidence distribution check:** histogram + assert ≥X% of in-distribution rows exceed
     `confidence_bypass_threshold` (X itself config-declared, not a magic number).
   - **Per-instrument breakdown:** same checks grouped by symbol, to confirm/deny the
     BNB-specific-overfit hypothesis.
   - **ΔG001 comparison:** run old vs. candidate model through the existing Goal Layer
     (`goal_report`) harness — no promotion without demonstrated ΔG001 improvement
     (Authority Ladder).
2. **Independent small fix** (ship regardless of whether retraining happens):
   `rr_pattern_miner.py:309-310` currently silently truncates an oversized feature vector
   (`features[:n]`). Replace with a hard `feature_schema`/version check that fails closed on
   mismatch instead of silently truncating — this is a latent correctness bug independent of the
   retraining question.
3. Any new `models/rr_model_{version}.json` goes through `ConfigValidator` →
   `PromotionManager.promote_*` before being copied to canonical `models/rr_model.json` — never
   hand-copied.

## Verification

- `pytest tests/test_engine_runner_rr_fusion.py -v` — new disable-path test green, existing
  fallback tests still green.
- Run the determinism/parity harness (`tests/runtime/test_replay_determinism.py` or equivalent)
  pre/post config change on a fixed replay set; diff must be empty outside the RR-derived fields.
- `python scripts/maintenance/_compute_hash.py` — confirm hash-neutral or correctly rehashed.
- Full `pytest` per `docs/reference/testing.md` pre-promotion regression command — confirm no
  unrelated breakage.
- Manually inspect one live-equivalent fusion run's log output to confirm `rr_fusion` no longer
  appears / RR score now differs from Gaussian score (proving real `RREngine` is back in play).
