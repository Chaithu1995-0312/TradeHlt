# Plan — Reconcile + Measure Feature-Pipeline Lookahead (Option 1)

## Context

A long adversarial-design session proposed a "tiny BitNet swarm," narrowed it to one execution
model, then issued a **"FATAL center=True label-leakage — kill the model"** verdict and demanded a
repo-wide pipeline rewrite. Before acting, I verified every claim against the real code (3 Explore
sweeps). The verification **contradicts the FATAL framing** and reduces the actionable surface to a
small, evidence-first task. The user chose **Option 1: Reconcile + measure only** — no production
behavior change, no config-hash change.

### What verification established (ground truth)

| Claim in the audit | Reality in code | Verdict |
|---|---|---|
| `center=True` swing detection is FATAL leakage | Real (`feature_pipeline.py:343`), but the 2026-06-10 Backtest Trust Layer **already measured it** via the existing `TRUST_SWING_CAUSAL=1` toggle (`feature_pipeline.py:367-372`): 974/3000 swing flags shift yet BNBUSDT ledger is **byte-identical**, 0 edge inflation — the CRT entry path doesn't consume swing columns. Documented as finding **F1** in `docs/analysis/backtest-trust-audit-2026-06-10.md §4d`. | Adversarial "FATAL" is **DOC_DRIFT** vs validated evidence (CLAUDE.md §6.2). LIVE-UNSAFE flag still stands but is benign for backtest trade-generation. |
| Execution model is contaminated via `TradeRecord.features → dataset builder → tensor` | **No dataset builder reads `TradeRecord.features`.** Training (`scripts/training/train_trade_net_v2.py`) reads `opportunities_*.jsonl`. | Central contamination chain **does not exist**. |
| Need to design a BitNet.cpp execution successor | **TradeNet v2 already exists** (`src/training/trade_net_v2.py`): 3-head p_tp1/p_tp2/p_survives_be, already wired as a **soft `neural_fn`** (`make_neural_fn_v2`, `trainer.py:844`), not a hard gate. This is F-005 ("BUILT but unwired"). | Mostly rediscovery of existing artifacts. |
| (new, un-audited) `volatility_regime` global rank | Real: `atr_pct = df["atr_14"].rank(pct=True)` (`feature_pipeline.py:306`) — a **global** percentile (slice-length dependent), **not** trailing. It **is** consumed by an entry gate: `s05_grid.py:120` blocks LONG in TRENDING. F1 never covered this. | The **only genuinely new, decision-relevant** finding — worth measuring. |

**Authority-ladder note (CLAUDE.md §6.5):** these are *information*, not *authority*. This plan only
buys docs/research/measurement — it grants no production weight to anything. Production causal
conversion (Option 2) and TradeNet-v2 shadow-eval (Option 3) are **explicitly deferred**, gated on
Program B evidence.

## Scope — what this plan delivers

**Reconcile + measure only.** Three deliverables, in priority order. No `params`-block edit → **no
`_compute_hash.py` rehash**. All toggles default **OFF** (mirror `TRUST_SWING_CAUSAL`), so the active
config and live path are untouched. Run on the branch-active config per ORIENT_RUNTIME (CLAUDE.md
§4.0): `patch` → `v2_multi_2026_04`.

### Program A — Truth reconciliation (record the conflict; evidence wins)

1. **File finding F-029** in `docs/current-findings.md` mirroring the existing entry format
   (`### F-029 · …` with Type/Status/Confidence/Validated/Revalidate-by/Evidence/Supersedes/Reversal/
   Owner — see F-001 / F-028 as templates). Content: *feature-pipeline `center=True` swing lookahead
   is **benign for trade generation** (byte-identical ledger, BNBUSDT; extends trust-layer F1); the
   adversarial "FATAL" verdict is DOC_DRIFT against measured evidence. Carries an OPEN sub-thread:
   `volatility_regime` global-rank is decision-reachable (`s05_grid.py:120`) and **un-quantified** →
   Program B.* Status `VALIDATED`, Confidence `Likely` (BNBUSDT-only caveat), Evidence cites the
   trust-audit §4d + `feature_pipeline.py:306,343,367-372` + `s05_grid.py:120`.
2. **Add the F-029 row** to the CLAUDE.md §6.2 "Repository Truths Index" table (keeps
   `tests/test_current_findings.py::test_index_and_doc_agree_on_nonterminal_ids` green — every
   non-terminal finding must appear in both).
3. **Cross-link**, don't duplicate (§6.2 rule 1): add a one-line back-reference in the trust-audit
   doc's F1 section pointing to F-029, and note the adversarial thread as `SUPERSEDED`.

### Program B — Measure the `volatility_regime` global-rank (measure-only)

1. **Add a measure-only toggle** `TRUST_VOLREGIME_CAUSAL=1` in `feature_pipeline.py`
   `compute_volatility_regime` (the `:303-314` block), mirroring the `TRUST_SWING_CAUSAL` wrapper
   pattern at `:367-372`: when set, replace global `rank(pct=True)` with a **causal expanding/trailing**
   percentile (e.g. `expanding().rank(pct=True)` or a trailing-window rank). Default OFF → no hash
   change, no production/live effect.
2. **Run the WS4A-style A/B** on the active config: one baseline backtest, one with the env var set;
   reuse the existing measure-only flow (env-var + standard backtest harness, e.g.
   `scripts/analysis/session_sweep.py --instrument BNBUSDT` or the trust-audit driver) and compare
   ledgers. Verify byte-identity / quantify drift with `src/analytics/metrics_oracle.py` (`recompute`)
   and the determinism harness in `tests/runtime/test_replay_determinism.py`. Because
   `volatility_regime` is decision-reachable, expect this **may** change the ledger — that is the point.
3. **Record the result** by appending a short dated section to
   `docs/analysis/backtest-trust-audit-2026-06-10.md` (existing-doc-first) with the same metrics-table
   format as §4d, and update F-029's Evidence: byte-identical → confirm benign; changed → quantify Δ
   (trades / win-rate / PF / total-return) and flag it as a real slice-dependence to address before OOS.
4. **(Cheap strengthener)** Re-run the **existing** `TRUST_SWING_CAUSAL` F1 comparison cross-universe
   (ETH/BTC/SOL + one FX/metal) to retire the "single-instrument BNBUSDT" caveat on F1; fold the result
   into F-029's confidence.

### Deferred (NOT in this plan — gated on Program B evidence)

- **Option 2 — production causal conversion** of `center=True` / global-rank: only if Program B shows
  material decision drift. F1 currently shows ~0 ledger benefit; conversion forces rehash + repo-wide
  re-validation. Not justified yet.
- **Option 3 / Program C — TradeNet v2 shadow-eval** (F-005): separate, larger program; advisory-first
  per §6.5. Not started here.

## Files to modify

- `src/features/feature_pipeline.py` — add `TRUST_VOLREGIME_CAUSAL` measure-only toggle in
  `compute_volatility_regime` (`:303-314`), modeled on the `TRUST_SWING_CAUSAL` block (`:367-372`).
  **Reuse**, don't invent, the existing toggle idiom.
- `docs/current-findings.md` — add finding **F-029**.
- `CLAUDE.md` — add the F-029 row to the §6.2 Repository Truths Index.
- `docs/analysis/backtest-trust-audit-2026-06-10.md` — append the volatility_regime measurement
  section; add F1↔F-029 cross-reference.
- `assistant_project.md` — append the §6 `📝 SESSION LOG ENTRY` block (mandatory, every response).
- *(No new standalone docs; no `configs/` edits; no `_compute_hash.py` run.)*

## Verification

1. **Findings sync stays green:** `python -m pytest tests/test_current_findings.py -q` (proves F-029
   appears in both the living doc and the CLAUDE.md index).
2. **Toggle is inert by default (no production change):**
   `python -m pytest tests/runtime/test_replay_determinism.py tests/analytics/test_metrics_oracle_parity.py -q`
   must pass **with the env var unset** — confirms hash-neutral, behavior-neutral default.
3. **The measurement itself:** run the backtest twice (unset vs `TRUST_VOLREGIME_CAUSAL=1`) on the
   active config, diff the trade ledgers, and reconcile metrics via `metrics_oracle.recompute`. Capture
   the trades / win-rate / avg-RR / PF / max-DD / total-return table into the audit doc.
4. **Doctrine gate:** confirm no `configs/production/*` file changed and no hash recompute was needed
   (measure-only). Append the SESSION LOG entry with the `Belief Update / ROI / Goal` line.

## Success criteria

- F-029 filed and synced; the adversarial "FATAL center=True" claim is recorded as superseded
  DOC_DRIFT, not silently dropped (§6.2 rule 4: preserve history).
- `volatility_regime` global-rank effect is **measured** (byte-identical ⇒ benign like F1, or Δ
  quantified) — turning an unverified hunch into evidence.
- Zero production/config/hash change; all default-state gates green.
- Options 2 and 3 left explicitly parked with their reopen conditions stated.
