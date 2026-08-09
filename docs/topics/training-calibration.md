# Topic: Model Training & Calibration

> **Topic-visibility unit.** How models (Gaussian NB, TradeNet) are trained, gated by the Phase-5
> calibration check, and promoted through the model registry. Distinct from *config* promotion.
>
> Created: 2026-06-05 · Updated: 2026-07-22 · Status: living

## In plain language
Some engines use trained models. Training is **offline**: mine paired trade records → fit a model →
prove it actually correlates with outcomes (the **Phase-5 gate**: `corr ≥ 0.10`, low calibration error,
CV-stable) → register it → promote only if it beats the active model by a margin (GOV-3). The Gaussian
model is **live** (loaded per candle in the live engine); TradeNet is built but offline/unwired. There
is no automated live re-training loop (per F-001, that capability is unfunded).

## Code covered
- [`src/training/train_pipeline.py:224`](../../src/training/train_pipeline.py) — `run_gaussian_update` — the 8-step Gaussian update (validate → build → train → CV → Phase-5 gate → register → promote).
- [`src/training/trainer.py:287`](../../src/training/trainer.py) — `train_gaussian` — fit `GaussianNBModel` + scaler → (model, scaler, metrics).
- [`src/training/phase5_calibration.py:131`](../../src/training/phase5_calibration.py) — `make_calibration_fn` — binds model+scaler; `_run_gates()` at :95 is the 4 hard checks (incl. `min_corr` 0.10).
- [`src/core/model_registry.py`](../../src/core/model_registry.py) — `ModelRegistry` — GOV-3 atomic promotion (`PROMOTION_MARGIN` 2%).

## Ins / Outs
- **Ins:** `*_fusion.jsonl` paired trade logs (the clean training data), a target version label; config `get_prod_section("phase5_calibration")` + `get_prod_section("training")`.
- **Outs:** `models/gaussian_*.json` (+ scaler), an entry in `models/gaussian_registry.json`, and a result dict `{approved, promoted, metrics, verdict, gate_checks}`. Rejected calibration raises (no silent registration).

## Entry points & validations
- **Reached via:** `scripts/training/train_pipeline.py` / `auto_tuner_multi` (offline CLI). Agent tool `tuner.run_multi`.
- **Validated by:** the Phase-5 hard gate (corr ≥ 0.10, cal-error ≤ 0.25, CV-stable, ≥30 val samples); GOV-3 promotion margin; dataset_validator pre-checks. Distinct from config promotion ([`promotion-governance.md`](promotion-governance.md)).

## Tests
- [`tests/test_train_pipeline.py`](../../tests/test_train_pipeline.py) — pipeline with mock data.
- [`tests/test_gaussian_update_pipeline.py`](../../tests/test_gaussian_update_pipeline.py) — 8-step flow + gate.
- [`tests/test_phase5_calibration.py`](../../tests/test_phase5_calibration.py) — gate logic / hard-fail paths.
- [`tests/test_trainer.py`](../../tests/test_trainer.py), [`tests/test_evaluator.py`](../../tests/test_evaluator.py) — fit/predict, CV, eval margin.

## Fits in architecture
The offline counterpart to the runtime spine: it produces the models that [`scoring-engines.md`](scoring-engines.md)
(Gaussian) and [`bitnet-gate.md`](bitnet-gate.md) consume. Full reference: `docs/reference/training.md`.
Funding posture for new model tracks is KILLED/FROZEN per the Funding Ledger (F-001).

## Discussion (filled in-session)
- **Risks:** 2026-06-05 — active models are still v2.0 (35-feature) while the pipeline emits 38; a truncation/slice happens at inference — keep the schema-hash baseline in sync (see [`feature-schema.md`](feature-schema.md)).
- **Blockers:** 2026-06-05 — no live automated re-training loop (F-001); models are trained via manual/batch runs.
- **Need more info:** 2026-06-05 — TradeNet is built but unwired (F-005); confirm before investing in its training path.
- **2026-07-22 — TradeNet Qualification Protocol (`TN_QUAL_V1`):** governing path for any future TradeNet authority is now [`docs/governance/tradenet_qualification_protocol.md`](../governance/tradenet_qualification_protocol.md) — **GATE-0** label feasibility (practical + worth implementing?) before any clean-label builder; then GATE-L via `forward_walk(intrabar_fixed)` (stream `outcome` banned as primary y, F-022), retrain triggers, offline KEEP_CANDIDATE, weight-0 shadow + ΔG001, GATE-P spine wire. Does **not** wire `neural_fn` or reopen Funding Ledger production; lineage stays AUDITED/INERT. Sibling pattern: RR clean-label / F-059.
- **2026-07-22 — GATE-0 added:** lightweight feasibility assessment (G0-Q1…Q9) with verdicts FEASIBLE_GO / FEASIBLE_DEFER / INFEASIBLE_STOP; only FEASIBLE_GO unblocks GATE-L builder work.
