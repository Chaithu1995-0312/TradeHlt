# Model Training Reference

> **What this covers:** how Tradelatest builds training data from historical outcomes,
> trains the scoring models, gates them on a **correlation** threshold, promotes them
> through the model registry, and loads them back into `backtest_v2`. This is the single
> training reference; it closes a documentation gap — the correlation-driven training loop
> lived only in code until now.
>
> **Scope note:** "training" here is **model** training (Gaussian / RR / Zone / TradeNet),
> which is separate from **config** promotion (`ConfigValidator` → `PromotionManager`, see
> [`governance.md`](governance.md)). Models go through `ModelRegistry`; configs go through
> the promotion log. They are independent gates.

---

## 1. What gets trained

| Model | Algorithm | Artifact / registry | Consumed by | Status |
|---|---|---|---|---|
| **Gaussian scorer** | Naïve-Bayes over `GAUSSIAN_SCHEMA` (**38-dim** at `SCHEMA_VERSION 3.0`, verified at runtime) | `models/gaussian_*.json` → `gaussian_registry.json` | `backtest_v2` calibrated scorer | Active |
| **RR model** | Ridge + GNB ensemble | `models/rr_model.json` + `rr_dataset.json` → `rr_registry.json` | `RRFusionLayer` | **Disabled** (`rr_fusion.enabled:false`); dataset quarantined — see [`../analysis/rr-data-integrity-audit-2026-04-30.md`](../analysis/rr-data-integrity-audit-2026-04-30.md) |
| **Zone Gate** | K-Means (8 clusters) | `zone_registry.json` → `zone_gate_registry.json` | Zone-gate engine | Active |
| **TradeNet** | PyTorch binary win/loss | `tradenet_registry.json` | optional | Requires Python 3.12 (torch) |
| **BitNet** | Pre-trained 1.58-bit GGUF (**inference-only — no training pipeline**) | `models/bitnet_*.gguf` | hard gate | Pre-trained |

**Feature-dimension is documented inconsistently — runtime truth is 38.**
`GAUSSIAN_SCHEMA.n_features = 38` at `SCHEMA_VERSION = 3.0` (`features/feature_schema.py`,
verified by a live calibration run: `model=38, schema=38`). One stale reference remains:
the `phase5_calibration.py` header docstring still says "32-dim" (out of date). Trust the runtime
value (38). All share the schema-hash baseline (see §6).

---

## 2. The correlation-driven training loop (the key concept)

Training **mines historical trade outcomes** and accepts a model only if its predictions
**correlate** with realised returns. The closed loop:

```
 backtest_v2.py  (FULL features, scorer_mode=static)
   │  candle-by-candle replay → risk_score per trade
   ▼
 results/.../<INSTR>_trades.csv         ← TradeRecord rows (features + pnl_rr_net label)
   │                              ── OR ──
 opportunity_scanner.py → logs/opportunities_*.jsonl   ← every historical TP/SL setup (unbiased)
   │
   ▼
 phase5_calibration.py --train         ← EVALUATOR, not a dataset builder
   │  mines pnl_rr_net labels → trains GaussianNBModel
   │  evaluate_gaussian(): corr_expected_rr = Pearson(predicted_RR, actual pnl_rr_net)
   │  GATE: APPROVED iff corr ≥ 0.10  AND  CV stable (std < 0.05)
   ▼
 models/gaussian_*.json  (+ integrate_scorer() patches _P5_PARAMS into backtest_v2.py)
   │  promotion → ModelRegistry (GOV-3 atomic, PROMOTION_MARGIN=2%)
   ▼
 backtest_v2.py  (scorer_mode=calibrated)
      loads CRTCalibratedScorer → core.model_registry.load_active_gaussian_scorer()
      per candle: scorer.compute(features) → risk_score
      diagnostic: DistributionAnalyser.score_outcome_corr = Pearson(risk_score, pnl_rr_net)
```

**Correlation thresholds** (`scripts/training/phase5_calibration.py:125`):
- `MIN_LOO_CORR_FOR_INTEGRATION = 0.10` — model must clear this to be integrated.
- `MIN_LOO_CORR_TO_SAVE = 0.05` — below this it isn't even saved.
- Verdict (`phase5_calibration.py:~673`): **APPROVED** (corr ≥ 0.10 & CV stable) /
  **UNSTABLE** (corr ≥ 0.10 but CV std ≥ 0.05) / **MARGINAL** (0 < corr < 0.10) /
  **REJECTED** (corr ≤ 0 — model degrades performance, never deploy).

`backtest_v2` reports the same idea as a run diagnostic:
`DistributionAnalyser._score_outcome_correlation` = `Pearson(risk_score, pnl_rr_net)`
([`backtest_v2.py:605`](../../src/runtime/backtest_v2.py)).

---

## 3. How `backtest_v2` consumes a trained model

`BacktestConfig.scorer_mode: "calibrated" | "static"`
([`backtest_v2.py:~147`](../../src/runtime/backtest_v2.py)).

- **`static`** → `CRTGaussianScorer()` (fixed `gaussian_scorer` config params; no trained model).
- **`calibrated`** (default) → `CRTCalibratedScorer()` → `core.model_registry.load_active_gaussian_scorer()`
  loads the registry's active `models/gaussian_*.json`. Invoked per candle via
  `self._scorer.compute(features, candle_idx, direction)` (`backtest_v2.py:~1461`).

CLI: `python src/runtime/backtest_v2.py --csv data/X.csv --instrument X --scorer calibrated`
(or `--scorer static` to bypass the trained model).

---

## 4. How `auto_tuner_multi` relates (and why its trades can't train models)

`auto_tuner_multi` **does not consume trained models** — it only sweeps CRT params via
`BacktestRunner`, and its fitness reads scalar metrics only
(`expectancy_rr`, `win_rate`, `trade_count_norm`, `drawdown`).

> ⚠️ **Its trade CSVs are NOT usable as training data.** The tuner runs with
> `skip_features=True` for speed ([`auto_tuner_multi.py:~365`](../../scripts/training/auto_tuner_multi.py)),
> so the `*_trades.csv` rows it writes have **zeroed feature columns**.
> `phase5_calibration.from_backtest_results()` explicitly **skips zero-feature rows**
> ([`phase5_calibration.py:347`](../../scripts/training/phase5_calibration.py)) — its own log says
> *"skipped N zero-feature rows … use backtest_v2.py [full-feature runs]."*

**Therefore, clean training data must come from one of:**
1. A **full-feature `backtest_v2` run** (no `skip_features`), or
2. **`opportunity_scanner`** → `logs/opportunities_*.jsonl` — the recommended, unbiased
   source: it labels *every* historical TP/SL setup, not just the trades that executed,
   so it produces far more samples than executed-trade history alone.

---

## 5. CLI commands (verbatim from [`cli-matrix.md`](cli-matrix.md))

> **Two usage gotchas (verified by running the chain):**
> 1. Run with **`PYTHONPATH=src`** — invoking `phase5_calibration.py` directly otherwise
>    fails with `ModuleNotFoundError: No module named 'features'`.
> 2. **`--train` requires an explicit model flag** (`--gaussian` or `--tradenet`); bare
>    `--train` errors out.
> 3. Pass **`--instrument <X>`** when calibrating — without it the auto-promote defaults the
>    active-pointer instrument (it can hijack another instrument's active Gaussian).

```bash
# 0. Pre-training baseline snapshot (schema hash + active models + config SHA-256)
python src/runtime/baseline_capture.py --label phase0 --output-dir results/baseline

# 1. Mine historical candles for ALL TP/SL opportunities (unbiased training source)
python scripts/research/opportunity_scanner.py --csv <csv> --instrument EURUSD \
    --tp-atr-mult 2.0 --sl-atr-mult 1.0 --max-forward-candles 40 --warmup-candles 30 \
    --output-dir logs                                   # → logs/opportunities_*.jsonl

# 2. Train + calibrate the Gaussian scorer on the mined opportunities
python scripts/training/phase5_calibration.py --opportunities <opportunities.jsonl> \
    --version <version> --train --train-ratio 0.7       # → models/gaussian_*.json
#    add --integrate to patch the scorer into backtest_v2, --promote to register it

# Alternative data source: train from full-feature backtest CSVs
python scripts/training/phase5_calibration.py --csv data/ --train

# Synthetic smoke test (CI)
python scripts/training/phase5_calibration.py --synthetic --train

# 3. Other models
python scripts/research/discover_zones.py --opportunities <f> --output models/zone_registry.json --n-clusters 8 --min-samples 15
python scripts/data/build_rr_dataset.py --output models/rr_dataset.json
python scripts/training/train_rr_model.py
python scripts/training/train_pipeline.py gaussian
py -3.12 scripts/training/train_pipeline.py tradenet --data data/training.json --output results/training_result.json

# 4. Verify the trained model in a full backtest
python src/runtime/backtest_v2.py --csv data/X.csv --instrument X --scorer calibrated
```

---

## 6. Data quality & schema invariants

- **Min samples:** `MIN_GAUSSIAN_SAMPLES = 20` (`phase5_calibration.py:58`);
  `dataset_validator` enforces `training.min_records_to_train` (200) /
  `min_records_recommend` (500). With too few samples the calibration gate cannot pass —
  this is why low trade frequency starves model training.
- **`dataset_validator`** pairs ENTRY+EXIT records, checks schema completeness, non-null /
  non-all-zero feature vectors, temporal ordering, and class balance (rejects degenerate
  all-zero-label datasets — the RR dataset's current failure mode).
- **Schema hash is load-bearing:** changing `CANONICAL_FEATURES` / `GAUSSIAN_SCHEMA`
  invalidates the baseline; re-run `baseline_capture.py --label <new>` before training
  (CLAUDE.md §4; [`../architecture/goal.md`](../architecture/goal.md) determinism invariant).

---

## 7. Model promotion governance

Distinct from config promotion. `core.model_registry`:
- **GOV-3 atomic write:** `.tmp` → `os.replace()`, in-process `RLock` + cross-process file
  lock, `_assert_single_active()` invariant.
- **`PROMOTION_MARGIN = 0.02`** — a new model must beat the active one by ≥ 2%.
- **Gaussian guards:** absolute floor (corr < 0 → REJECTED, not bypassable by `force`),
  regression guard (~1%), schema-version match. Active pointer is **per-instrument**
  (`__active__` map).

Promote after calibration with `--promote`, or via
`python scripts/training/train_pipeline.py gaussian --version <v> --force-promote`.

---

## 8. Known gaps / cautions

- **RR model is disabled** with a quarantined all-zero-label dataset; rebuild before relying
  on RR fusion. See [`../analysis/rr-data-integrity-audit-2026-04-30.md`](../analysis/rr-data-integrity-audit-2026-04-30.md).
- **No event-driven `TrainingTrigger`** — training is CLI/agent-invoked, not auto-triggered.
- **Agent surface covers tuning only** (`tune_only` … `full_pipeline`); the model-training
  phases (`phase5_calibration`, `discover_zones`, `build_rr_dataset`) are CLI-only — see
  [`agent-reference.md`](agent-reference.md).
- **TradeNet needs Python 3.12** (torch); the rest of the stack runs on >=3.10.
