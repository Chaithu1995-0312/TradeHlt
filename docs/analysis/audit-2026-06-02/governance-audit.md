# 5 · Governance Audit (Phase E-1) — Constraint 1

> Point-in-time audit, 2026-06-02. **Highest-priority section.** What blocks promotion, what *should* block
> production but doesn't, and which gates are evidence vs assumption.

## Finding 1 (CRITICAL) — the running config is ungoverned

`ACTIVE_VERSION` = **`v2_multi_2026_04 - deepdeektry`**. Evidence it bypassed governance:

| Signal | Evidence | Implication |
|--------|----------|-------------|
| No promotion record | `promotion_log.jsonl` last `PROMOTED` = plain `v2_multi_2026_04` (2026-05-06); deepdeektry file dated 05-30 | Never ran `PromotionManager.promote_*` |
| Hand-edited params | permissive `0.8 / 0.3 / 0.6` (vs governed `0.2 / 0.65 / 1.0`) | Acceptance loosened off-gate |
| Stale validation_summary | summary describes the 05-06 governed config (score 0.5966), not the live params | Audit trail lies about what's running |
| Hash blind spot | `config_hash` hashes **params↔params** only → passes despite the stale summary | Integrity check cannot see the desync |
| Name hygiene | space in the version key | Violates naming; symptom of manual creation |

**The machinery to catch this already exists and works:** `src/governance/config_integrity.py`
(`validation_summary_is_fresh` + `active_version_is_governed`, 7 tests) **correctly flags deepdeektry**
and passes `v3`. It is simply **not enforced as a gate**.

## What blocks PROMOTION (the gate, where it's used)

`PromotionManager` (`promotion_manager.py:138-170`) requires, in order:
1. `ValidationReport.decision == "APPROVE"` (HARD).
2. Re-run ConfigValidator to confirm the report isn't stale (HARD).
3. SHA-256 `config_hash` of params (embedded; verified on every `load_version`, mismatch → RuntimeError).
4. Merge onto the full base config (preserve all engine sections).
5. Flip `ACTIVE_VERSION` + write a `PROMOTED` event.

This is **strong** — when used. The defect is **operational, not architectural**: production was changed by
editing a file and pointing `ACTIVE_VERSION` at it, skipping steps 1-5.

## What *should* block production but doesn't

- The integrity guards (above) are **not invoked at startup or pre-trade** — an ungoverned config runs freely.
- `config_hash` does **not** cover the `validation_summary` lineage — so a stale/forged summary is invisible.

## Shadow / meta / portfolio governance — wiring status

| Component | Exists | Wired | Active | Role |
|-----------|:---:|:---:|:---:|------|
| ShadowPromotionGate | YES | promo-flow only | NO (runtime) | min_shadow_trades(30) + shadow_pnl>baseline (`shadow_promotion_gate.py:228`) |
| MetaGovernorExecutor | YES | NO (decision loop) | NO | BitNet meta-governance → `governance_audit.jsonl` only |
| PortfolioValidation | YES | YES | advisory | edge-universality, ≥2 instruments, corr>0.15 — **not a gate** |

## Gates: evidence vs assumption

| Gate / threshold | Value | Source | Evidence or Assumption? |
|------------------|-------|--------|-------------------------|
| min_trades_per_instrument | config | `config_validator.py` | **Assumption** (no calibration) |
| max_drawdown_pct | config | `config_validator.py` | **Assumption** |
| score_threshold (fitness) | config | `config_validator.py` | **Assumption** |
| max_score_std_dev | config | `config_validator.py` | **Assumption** |
| min_rr_ratio | 1.5 | `ultron_risk_gate.py:96` | **Assumption** (plausibly slippage-derived; not shown) |
| max_daily_loss_pct | 3.0 | `ultron_risk_gate.py:95` | **Assumption** |
| max_trades_per_day | 10 | `ultron_risk_gate.py:94` | **Assumption** |
| min_shadow_trades | 30 | `shadow_promotion_gate.py:49` | **Assumption** (sample-size heuristic) |
| zone_min_samples | 50 | `engine_runner.py:98` | **Assumption** |
| drift_threshold | 1.5 | `rr_fusion.py` | **Assumption** |
| portfolio corr predictive | >0.15 | `portfolio_validation.py:286` | **Assumption** |

**Every governance threshold is a hardcoded assumption** — the validator *enforces* them but nothing in-repo
*justifies* the values.

## Bottom line (C1)

Governance is **well-designed and currently bypassed**. The single highest-integrity action is to (a) bring
the running config back under the gate (promote a governed config — ideally `v3`, which both passes the
guards *and* carries the per-coin ROI) and (b) make `config_integrity.py` a hard pre-run/pre-promote gate so
an ungoverned config can never silently trade again. → [top-10-roi-actions.md](top-10-roi-actions.md) #1, #2.
