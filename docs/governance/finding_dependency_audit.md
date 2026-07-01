# Finding Dependency Audit

> **Purpose.** Meta-truths about truths — a catalog of *what kind of change* can invalidate each
> finding, and a prioritized replay program. This is **not** a findings file; it is a
> governance-adjacent index that answers "can I trust F-xxx after stabilization?"
>
> **See also:** [`current-findings.md`](../current-findings.md) (the truths themselves) ·
> [`EPISTEMIC_INTEGRITY.md`](EPISTEMIC_INTEGRITY.md) (governance rules) ·
> [`knowledge-map.md`](../knowledge-map.md) (record systems).
>
> **Created:** 2026-06-27 · **Audit snapshot:** run against `patch` branch HEAD
> `1a8a260314ffdaca0ef25a2278e8741c2de9ada9`.

---

## Dependency Taxonomy

### Replay Types

| Code | Name | Meaning | Work required |
|------|------|---------|---------------|
| **R0** | None | Finding survives any known change without re-measurement | 0 |
| **R1** | Code reachability | Verify the wiring, callsite, config path, or active status | Static code audit |
| **R2** | Economic | Re-measure outcomes (PF, expectancy, win-rate) under current truth standard | Run backtest |
| **R3** | Ontology | Requires a new execution architecture, market, or payoff theory to test | Build new system |

### Truth Epochs

| Epoch | Period | Exit Model | Key Event |
|-------|--------|------------|-----------|
| **E1** | Pre-2026-06-11 | Close-only | Session optimism, inflated PF — dead |
| **E2** | 2026-06-11 → stabilization | `intrabar_fixed` + 12bps | F-017 correction; current economic truth |
| **E3** | Post-stabilization | Same model, stabilized paths | 38-feature integration, fusion cleanup, reachability fixes, config corrections |

**E3 question:** Is E3 merely implementation cleanup (most E2 findings survive), or did it create a
new hypothesis universe? **F-019 is the detector**: if it still shows 0 PROMOTE, E3 = stabilized E2.
If it breaks, E3 = new economic universe.

---

## Phase A Result — Static Reachability Audit (2026-06-27)

Audit performed against working tree HEAD `1a8a260`. All 12 R1 findings checked via static code
inspection and config verification.

### F-004 · BitNet hard gate
| Replay type | Status | Detail |
|-------------|--------|--------|
| **R1** | **PASS** | Gate at `src/config_layer/crt_engine_v2.py:1804` — `bitnet_main_score < bitnet_main_threshold` (default 0.55) still rejects entries. Persisted at `src/runtime/backtest_v2.py:320`. Active config does NOT override `bitnet_main_threshold`. Still live. |

### F-005 · TradeNet v2 unwired
| Replay type | Status | Detail |
|-------------|--------|--------|
| **R1** | **PASS** | `src/core/fusion_engine.py:282` — `self.neural = neural_fn` (default `None`); EngineRunner never passes a neural_fn (zero matches for `neural_fn` in `engine_runner.py`). Fusion socket still empty. |

### F-006 · config_integrity orphaned
| Replay type | Status | Detail |
|-------------|--------|--------|
| **R1** | **PASS** | `src/governance/config_integrity.py` functions exist (`validation_summary_is_fresh`, `active_version_is_governed`, `audit`). Zero callers in `backtest_v2.py`, `live_engine_hook.py`, `promotion_manager.py`. Still orphaned. |

### F-008 · Drift not acted on
| Replay type | Status | Detail |
|-------------|--------|--------|
| **R1** | **PASS** | `src/runtime/live_engine_hook.py:615-619`: HARD drift logs `"Trade signal unreliable"`, trade proceeds. No block/size-down/reject after drift detection. KillSwitch is a separate mechanism (tripped state, not drift response). |

### F-012 · Sidecar components
| Replay type | Status | Detail |
|-------------|--------|--------|
| **R1** | **PASS** | Zero matches for `replay_memory`, `cognitive_bus`, `HMF` in `engine_runner.py` import or call sites. CognitiveBus is constructed only if config `cognitive_layer.enabled=true`. All sidecar-only. |

### F-013 · ExecutionLoop orphaned
| Replay type | Status | Detail |
|-------------|--------|--------|
| **R1** | **PASS** | Zero matches for `ExecutionLoop`, `Scanner`, `Ranker`, `SignalPool` in `engine_runner.py`. The multi-signal scan→allocate→ExecutionLoop path remains unwired. |

### F-016 · `patch` active config v2
| Replay type | Status | Detail |
|-------------|--------|--------|
| **R1** | **PASS** | Committed `configs/production/ACTIVE_VERSION` = `v2_multi_2026_04 - deepdeektry`; **working tree (uncommitted) = `v2_multi_2026_04`** (2026-06-27). Both are v2_multi_2026_04 *variants* (pre-TP3), so F-016's "active = v2, not v4" holds either way. Git log shows no v4 promotion on `patch`. Variant divergence is the F-038 residual `TruthConflict`. |

### F-018 · Config lags HEAD code
| Replay type | Status | Detail |
|-------------|--------|--------|
| **R1** | **PASS** | R1 sections (`dataset_integrity`, `uat`, `live_integration`) are present in the active config. R2 (`bitnet_main_threshold`, `hard_drift_z`, `soft_drift_z`) are wired. The residual F-016 split-brain persists. |

### F-037 · Spine CRT-only by design
| Replay type | Status | Detail |
|-------------|--------|--------|
| **R1** | **PASS** | `.env` contains `BACKTEST_ENGINE_GATE=0` (confirmed loaded by `dotenv`). `backtest_v2.py:1838` is the only path honoring this flag. Research spine = CRT-only. |

### F-038 · RR = Gaussian duplicate (Fix status)
| Replay type | Status | Detail |
|-------------|--------|--------|
| **R1** | **⚠ FLAG → ✅ RESOLVED (pending commit), 2026-06-27** | **Original (vs HEAD `1a8a260`, correct):** fix not deployed — committed `ACTIVE_VERSION` = `v2_multi_2026_04 - deepdeektry` → resolver loads `v2_multi_2026_04 - deepdeektry.json:50` (`enabled: true`), so the model still ran and rr_result == gaussian_score. **CORRECTED mis-citation:** the `:50`/`true` line is the **deepdeektry** file, NOT `v2_multi_2026_04.json` (whose `:34` is already `enabled: false`); the original row conflated the two `v2_multi_2026_04*` files. **Resolution:** the working tree flips `ACTIVE_VERSION` → `v2_multi_2026_04` (loads `v2_multi_2026_04.json`, `enabled: false`), deploying the fix — real **once committed**. Verification: `static`+`runtime` (`git show HEAD:configs/production/ACTIVE_VERSION` vs working tree; resolver `production_config.py:60`→`:116`). RESIDUAL: two config files disagree → user-gated `TruthConflict` (archive/keep deepdeektry). |

### F-039 · L3 pre-flight backtest_v2-only
| Replay type | Status | Detail |
|-------------|--------|--------|
| **R1** | **PASS** | Static census re-checked: only `backtest_v2.py` calls `validate_dataset`. Inline L1/L2 backstop in `CandleLoader.stream()` remains the universal integrity layer. No new CandleLoader instantiations found outside backtest_v2. |

### F-041 · ZoneGate manifest divergence
| Replay type | Status | Detail |
|-------------|--------|--------|
| **R1** | **PASS** | Config loads `models/zone_registry.json` (8 zones). Manifest `models/zone_gate_registry.json` exists with `active:true` → `models/BNBUSDT/.../zone_registry_BNBUSDT_202605_bnb_v1.json` (different sha256). Still divergent. |

---

## Phase A Summary

| Finding | R1 Result | Notes |
|---------|-----------|-------|
| F-004 | ✅ PASS | Gate still active |
| F-005 | ✅ PASS | neural_fn still None |
| F-006 | ✅ PASS | Still orphaned |
| F-008 | ✅ PASS | Still log-and-continue |
| F-012 | ✅ PASS | Sidecar-only confirmed |
| F-013 | ✅ PASS | ExecutionLoop unwired |
| F-016 | ✅ PASS | v2 config unchanged |
| F-018 | ✅ PASS | R1/R2 applied, residual gap |
| F-037 | ✅ PASS | BACKTEST_ENGINE_GATE=0 |
| **F-038** | **⚠ FLAG → ✅ RESOLVED (pending commit)** | Working-tree `ACTIVE_VERSION` flip deploys the fix; mis-citation corrected |
| F-039 | ✅ PASS | Census re-checked |
| F-041 | ✅ PASS | Divergence persists |

**~~One actionable finding from Phase A~~ → RESOLVED 2026-06-27 (Documentation Drift Protocol):**
F-038's deploy is achieved not by editing the config flag (already `false` in `v2_multi_2026_04.json:34`)
but by the `ACTIVE_VERSION` pointer: at HEAD it resolved to the `… - deepdeektry` variant
(`enabled: true`); the working tree flips it to `v2_multi_2026_04` (`enabled: false`). The original
"flip the flag in the active config" framing mis-cited the deepdeektry file as `v2_multi_2026_04.json`.
Remaining action is **committing** the `ACTIVE_VERSION` flip + a user decision on the residual
two-file `TruthConflict` (archive vs keep `… - deepdeektry.json`).

---

## Complete Per-Finding Record

### R0 — No replay required

| F-xxx | Rationale | Epoch |
|-------|-----------|-------|
| F-001 | Economic/governance diagnosis; watch condition: promote to R2 if 38-feature ownership materially changes expectancy | E1→E2 |
| F-010 | Structural gap (backtest vs live) — not replay-dependent | E2 |
| F-017 | IS the E2 correction point — terminal finding for session policy | E2 |
| F-022 | Artifact-explanation, not world-claim; describes how `opportunities.jsonl` was created | E2 |
| F-025 | Terminal exit finding; closes the exit-vs-entry question for E2 | E2 |
| F-026 | FROZEN underpowered — funnel completion (~1%) is a structural fact, not parameter-dependent | E2 |
| F-027 | Decisive null at H1/H4 (well-powered toy arm) | E2 |
| F-028 | FROZEN interpreter — REJECT verdict with worse-than-random controls is definitive | E2 |
| F-031 | Governance process finding (self-correction loop) | E2 |
| F-033 | Frozen perp corpus; funding-rate history cannot be changed by code | E2 |
| F-034 | Structural arithmetic (1-6 bps income < 24 bps cost); frozen data | E2 |
| F-036 | Gate-ON replication already done; non-pivotality confirmed by ablation | E2 |

### R1 — Code reachability (Phase A complete above)

| F-xxx | Status | Notes |
|-------|--------|-------|
| F-004 | ✅ PASS | Gate still live |
| F-005 | ✅ PASS | neural_fn None |
| F-006 | ✅ PASS | Orphaned |
| F-008 | ✅ PASS | Log-and-continue |
| F-012 | ✅ PASS | Sidecar |
| F-013 | ✅ PASS | Orphaned |
| F-016 | ✅ PASS | v2 config |
| F-018 | ✅ PASS | Remediated |
| F-037 | ✅ PASS | CRT-only |
| F-038 | ⚠ FLAG → ✅ RESOLVED (pending commit) | Working-tree `ACTIVE_VERSION` flip deploys; mis-citation corrected 2026-06-27 |
| F-039 | ✅ PASS | Census OK |
| F-041 | ✅ PASS | Divergent |

### R2 — Economic replay required

| F-xxx | Priority | Why | Status |
|-------|----------|-----|--------|
| **F-023** | **P0** | **Mandatory** — clusters used artifact trailing-stop labels (F-022). Labels do not reflect governing `intrabar_fixed` truth. Re-run clustering on intrabar labels. | **✅ SURVIVED 2026-06-27** — 4 clusters WR 0.334–0.343, mean_R ≈0, intrabar_fixed labels |
| **F-019** | **P1** | **Epoch-3 detector** — the single experiment that determines if stabilization created a new hypothesis universe. If still 0 PROMOTE, E3 = cleanup. If breaks, E3 = new economic world. | **✅ SURVIVED 2026-06-27** — 0 PROMOTE; toy+spine arms BYTE-IDENTICAL to baseline → E3 = cleanup |
| **F-021** | **P1** | Reject-reason census (SESSION 110/112, ZONE 0/110, SCORE 2/110) — may shift with score/zone changes from stabilization. | **✅ SURVIVED 2026-06-27** — SELECTION_IS_SESSION_ONLY (SESSION 112 p=0.0005, ZONE 0, SCORE 2 p=0.327) |
| F-009 | Low | Per-instrument doctrine structurally robust; specific PF numbers may shift | NOT DONE |
| F-011 | Low | DURABLE 1-yr window; specific AUC values would shift but core conclusion robust | NOT DONE |
| F-014 | Deferred | FROZEN until throughput improves (Phase B prerequisite) | NOT DONE |
| F-015 | Low | "Cheap levers spent" structurally robust; threshold numbers pre-intrabar | NOT DONE |
| F-020 | Low | Paired design robust; low reversal probability | NOT DONE |
| F-024 | Low | Partly mechanical + cross-instrument replicated | NOT DONE |
| F-029 | P2 | Extend gate-ON fusion path verification | NOT DONE |
| F-030 | Low | DETERMINISM verified; 0 exploitable robust | NOT DONE |
| F-032 | Low | Well-powered, DETERMINISM verified | NOT DONE |
| F-035 | Low | PF 0.02-0.10 far below gate | NOT DONE |

### R3 — Ontology replay (deferred)

| F-xxx | Trigger |
|-------|---------|
| F-040 | Only if a long-vol/straddle execution architecture is built (Program 4 CLOSED) |
| Programs 5/6 | Only if new market or new payoff theory |

---

## Highest-Leverage Replay Program

### Phase B — Economic Truth Audit (three findings)

| Step | Finding | What to do | Success criterion | Failure mode |
|------|---------|------------|-------------------|--------------|
| **B1** | **F-023** | Re-run KMeans k=4 clustering on the SAME 139,942 BNBUSDT opportunities but labelled under `intrabar_fixed` (governing exit). Compare win_rates per cluster. | All 4 clusters still show WR ≈ 0.34 ± 0.01, mean_R ≈ 0.000 ± 0.023 (conclusion survives) | A cluster shows materially different WR (>0.40 or < 0.28) → E3 = new economic universe |
| **B2** | **F-019** | Re-run `qualify_majors.json` (BNB/ETH/BTC/SOL, intrabar_fixed+12bps) on current stabilized codebase | Still 0 PROMOTE, toy ≈ random (delta 0 ± 0.05) | Any hypothesis clears M4 gate → E3 = new economic universe |
| **B3** | **F-021** | Recompute reject-reason decomposition (SESSION/ZONE/SCORE counts) on stabilized spine | SESSION still dominates (≥95%), ZONE 0 rejects, SCORE < 5 | SCORE or ZONE shows material binding → selection skill may exist |

### Phase C — Deferred
All R3 findings (F-040, Programs 4/5/6) — revisit only when new ontology or market.

---

## Meta-Finding

Finding validity depends on **three independent axes**:

1. **Exit epoch** (close-only → intrabar_fixed)
2. **Hypothesis epoch** (pre-stabilization hypothesis space → post-stabilization)
3. **Execution ontology** (spot directional → long-vol / market-neutral / carry-harvest)

Most systems track only `date validated`. This framework is stronger because it tracks *what kind of
change* can invalidate each truth — making the replay program pre-computed rather than ad-hoc.

---

## Audit Log

| Date | Auditor | Scope | Result |
|------|---------|-------|--------|
| 2026-06-27 | claude | Phase A (12 R1 findings) | 11/12 PASS; 1 FLAG (F-038) |
| 2026-06-27 | claude | F-038 drift reconciliation (Documentation Drift Protocol worked example) | FLAG → RESOLVED (pending commit). Cause: fix-edit landed on `v2_multi_2026_04.json` while HEAD `ACTIVE_VERSION` resolved to the `… - deepdeektry` variant (`enabled:true`); audit row also mis-cited deepdeektry's `:50` as `v2_multi_2026_04.json`. Previous belief: "fix not deployed / config flag still `true`". New reality: flag already `false` in `…_04.json:34`; deploy gated on committing the working-tree `ACTIVE_VERSION=v2_multi_2026_04` flip. Verification: static + runtime (`git show HEAD:…/ACTIVE_VERSION` vs working tree; resolver `production_config.py:60`→`:116`). Residual two-file `TruthConflict` → user-gated. |
| 2026-06-27 | claude | Residual two-config `TruthConflict` resolution (deepdeektry archive) | RESOLVED (user-approved archive). Cause: `v2_multi_2026_04 - deepdeektry.json` (`enabled:true`/`gaussian_impl:ml`) coexisted with canonical `v2_multi_2026_04.json` and was the stale pin of the DEFAULT research config (`research_config_spine.json:36`; `spine_signal_source.py:49`). New reality (stronger than expected): deepdeektry is **non-loadable on `patch`** — its `governance` section lacks the required `promotion_margin` key, so `ProductionSpineSource._compute_entries` fail-fasts at `model_registry.py:150`; the deepdeektry-pinned default research path was therefore already broken. Verification: runtime — deepdeektry raises `KeyError(promotion_margin)`; canonical `v2_multi_2026_04` runs the BNBUSDT spine clean (13 entries). Action: repointed `research_config_spine.json` → `v2_multi_2026_04`; `git mv` deepdeektry → `configs/production/v2_multi_2026_04_deepdeektry_archived_20260627_160227.json`. One runtime config truth remains. |
| 2026-06-27 | claude | Phase B — Economic Truth Audit (F-023 / F-019 / F-021 economic replays on stabilized HEAD) | **ALL THREE SURVIVE → Epoch-3 = stabilized Epoch-2** (stabilization created NO new economic universe). **B2/F-019** (the detector): 0 PROMOTE; toy **and** spine arms BYTE-IDENTICAL to the 2026-06-12 baseline (verdicts {11 REJECT, 4 INSUFFICIENT}); spine byte-identity corroborates F-037 (backtest gate-OFF → CRT-only; the F-038 rr_fusion disable never reaches research-spine entries). **B1/F-023**: 4 KMeans clusters WR 0.334–0.343, mean_R ≈0 under governing `intrabar_fixed` labels (n=139,942, sha f8bdabbe). **B3/F-021**: verdict SELECTION_IS_SESSION_ONLY (SESSION 112 p=0.0005, ZONE 0, SCORE 2 p=0.327). Artifacts: `results/research/{qualification_2026_06_27,bnbusdt_trade_anatomy_2026_06_27,phase_s_2026_06_27}/`. `current-findings.md` F-019/021/023 Updated + Revalidate-by→2026-09-25. No reversals; no new findings. |
| — | — | Phase C (R3 findings) | Not yet executed |