# BitNet Lineage Audit

**Program:** Post-CH-002 model/training lineage (subsystem priority 4 — user-requested next)  
**Date (UTC):** 2026-07-09  
**Active config:** `v2_multi_2026_04`  
**Prerequisite:** `POST_CH002_BASELINE_DIFFERENTIAL = PASS` · CRT CLOSED  
**Authority:** observational — no retrain, no promote, no `use_bitnet` flip

---

## Verdict

```text
BITNET_LINEAGE_VERDICT = INERT + CONDITIONAL_SKEW
  LIVE_RUNTIME_ACTIVE_CONFIG = INERT (use_bitnet:false — F-004)
  TRAINED_ARTIFACT           = EXISTS (cwd model.json, legacy_6input)
  TRAIN_SERVE_IDENTITY       = SKEW if re-enabled (pipeline FM-021/020 train ≠ CRT FM-027/028 serve)
  CH002_IMPACT               = documented call-site map only; no live delta (gate off)
  REBUILD_REQUIRED           = NO for current production
                             = YES before any use_bitnet:true re-enable
  MARGINAL_OOS               = NO_AUTHORITY (inert; F-055 shadow of existing model non-improving)
```

**Spec DESIGN FROZEN through v1.2.1 (2026-07-21):** modernization MUST start from
[`docs/implementation_plan/bitnet-cpp-specification-v1-2026-07-21.md`](../implementation_plan/bitnet-cpp-specification-v1-2026-07-21.md)
— contracts A/B/C, hierarchy, backbone **family** `bb_bitlinear_res_v1` (L1: ternary residual,
final-latent heads, no LN). Numeric H/L/N_res/budgets are **versioned defaults** (L2 profile
`bitlinear_res_defaults_v1`), not architectural laws; artifacts must be self-describing. Phase 2b
deferred; C++/train/enable not authorized by spec alone. Audit remains observational.

---

## Naming hygiene (do not conflate)

| Name | What it actually is | This audit? |
|---|---|---|
| **BitNet 6-feature hard-reject** | `bitnet_score()` inside CRT `UltronRiskEngine` | **YES** |
| **BitNetRunner / export schema** | Alternate harness (`bitnet_runner.py`, `backtest_bitnet.py`, 24/38-dim export) | Documented, **not** CRT spine |
| **BitNetZoneGate** | ZoneGate registry scorer (`live_engine.py`) | **NO** — ZoneGate lineage |

---

## Dual-surface reality

| Surface | Entry | Active on spine? |
|---|---|---|
| **A — CRT hard-reject (production intent)** | `approve_with_soft_conf` → `bitnet_score` when `use_bitnet` | **NO** (`use_bitnet: false`) |
| **B — Dead `approve()` method** | Always maps FM→legacy + scores if cache present | **NO call sites** in live spine (F-004) |
| **C — BitNetRunner path** | `BitNetRunner(model_path)` + adaptive thresholds | **NO** on CRT/backtest_v2 journal path; separate CLI/harness |

---

## Lineage chain (11 slots)

### 1. Training population

| Item | Detail |
|---|---|
| Script | `scripts/training/train_bitnet.py` |
| Corpus | Historical OHLCV CSV(s) via `FeaturePipeline` |
| Population filter | Bars with **pipeline** `retest_depth > 0.05` (`train_bitnet.py:116-118`) — not CRT `TRADE_OPENED` |
| Warmup / horizon | `WARMUP=60`, forward window `MAX_FWD=40` |
| Existing artifact meta | cwd `model.json`: `trained_on=11884`, `epochs=50`, `architecture=6->16->8->1` |

**Not** trained from CRT `cached_features` / FM-027/028.

### 2. Feature identities (train time)

```text
FEATURE_KEYS = [
  body_ratio,           # FM-010 — Candle.body_ratio / pipeline
  retest_depth,         # FM-021 pipeline: |close−ema_fast|/(atr·close) clip[0,1]
  disp_strength,        # FM-020 pipeline: body_size/(atr·close) clip[0,3]
  atr,
  candles_since_retest,
  double_sweep,
]
```

Source: `train_bitnet.py:56-58`, `feature_pipeline.py:565-584`, `derived_math.retest_depth` / `disp_strength`.

### 3. Target / label

| Item | Definition |
|---|---|
| Win | Price hits `TP = close + 2·ATR` before `SL = close − 1·ATR` within 40 bars (`train_bitnet.py:129-138`) |
| Loss | SL hit first |
| Timeout | Dropped (no gradient) |
| Direction assumption | **Bullish-only** TP/SL geometry — no short-side mirror in this script |

**Label class:** synthetic ATR race — **not** journal `pnl_rr_net`, not `forward_walk(intrabar_fixed)`. Distinct from F-022 opportunity contamination, but still **not** a governed M4 economic label.

### 4. Dataset builder

| Step | Implementation |
|---|---|
| Features | `FeaturePipeline(df).run()` → row extract |
| Labels | In-script forward loop |
| Train loop | Pure numpy GD, MSE + sigmoid (`train_bitnet.py:152+`) |
| Output | Writes `model.json` (legacy schema: `layer1_w/b`, `layer2_w/b`, `out_w/b`) |

Related (not CRT path):
- `scripts/export/export_bitnet_model.py` — bitnet_v3 / export contract
- `scripts/export/generate_bootstrap_model.py` — random legacy weights

### 5. Artifact

| Path | Schema | Role | SHA-256 (2026-07-09) |
|---|---|---|---|
| **`model.json` (repo root / cwd)** | `legacy_6input` · feature_order matches FEATURE_KEYS | **Loaded by `bitnet_score()` default** | `ae85db1e…8aa9` |
| `results/model.json` | different (layers/weights/bias/scales) | Alternate / stale | `ad1002d3…515d` |
| `results/model_export_format.json` | export / multi-layer | `engine_runner.model_path` + BitNetRunner default | `d790e705…286c5` |
| `models/bitnet/bitnet_registry.json` | `{}` empty | **No governance registry** | — |
| `src/bitnet/bitnet_thresholds.json` | adaptive thresholds all 0.5 | Used by BitNetRunner only; CRT uses config `bitnet_main_threshold=0.55` | — |

**Fragility:** `BitNetModel()` defaults to **cwd-relative** `"model.json"`. No config key steers the CRT `bitnet_score` path. Empty bitnet registry = no promote/rollback surface for legacy 6-input.

### 6. Loader

| Path | Loader |
|---|---|
| CRT hard-reject | `_get_bitnet()` → `BitNetModel()` → cwd `model.json` → `forward(x)` legacy (`bitnet_inference.py:310-332`) |
| BitNetRunner | `BitNetModel(model_path)` + dim/name fail-closed (`bitnet_runner.py:40+`) |
| Normalize | `bitnet.model_contract.normalize_loaded` (schema detection, legacy emit) |

### 7. Inference inputs

#### CRT serve (when `use_bitnet` true) — **CH-002 map**

```text
CRT cached_features (post-CH-002):
  body_ratio
  displacement_retrace     # FM-027
  displacement_atr_ratio   # FM-028
  + atr, candles_since_retest, double_sweep

Call-site adapter (crt_engine_v2.py:1742-1746 / 1812-1815):
  retest_depth  ← displacement_retrace   (FM-027)
  disp_strength ← displacement_atr_ratio (FM-028)

bitnet_score hard keys (bitnet_inference.py:324-331):
  body_ratio, retest_depth, disp_strength, atr, candles_since_retest, double_sweep
```

#### Math mismatch under shared names (train vs serve)

| Legacy key | Train (pipeline) | Serve if enabled (CRT cache) |
|---|---|---|
| `retest_depth` | FM-021: `\|close−ema_fast\|/(atr·close)` clip[0,1] | FM-027: `\|retest.close−disp.open\|/\|disp.body\|` clip[0,1] |
| `disp_strength` | FM-020: `body/(atr·close)` clip[0,3] | FM-028: `candle_range/atr` (unclipped ATR multiple) |

**This is the primary train/serve skew.** CH-002 intentionally localized the rename at the call site so CRT cache stays honest — but **enabling BitNet without retrain feeds the model CRT geometry under training names that meant pipeline geometry.**

### 8. Output semantics

| Output | Meaning |
|---|---|
| Score ∈[0,1] | Sigmoid network confidence (“market state acceptable”) |
| Gate | Reject if `score < bitnet_main_threshold` (config **0.55**) |
| Reject reason | `RejectReason.LOW_SCORE` |
| Persistence | `state.bitnet_main_score` when path runs; journal may record `bitnet_score_at_entry` |

Not true RR, not p(win) under journal exits, not fusion engine vote.

### 9. Active config

| Key | Value | Section |
|---|---|---|
| `use_bitnet` | **`false`** | CRT / production params (`v2_multi_2026_04.json:252`) |
| `bitnet_main_threshold` | `0.55` | CRT params (`:206`) |
| `zone_cluster_threshold` | `0.25` | `engine_runner` — **ZoneGate**, not BitNet model |
| `engine_runner.model_path` | `results/model_export_format.json` | **Not** wired into CRT `bitnet_score` |

`active_models.yaml` bitnet block: `enabled: false`, `status: dormant`, findings `[F-004]`.

### 10. Runtime consumption

```text
CRT state machine → RETEST cache features (FM-027/028)
  → UltronRiskEngine.approve_with_soft_conf  (crt_engine_v2.py:2629 call site)
       if use_bitnet:
           map FM-027/028 → legacy keys
           bitnet_score → hard reject if < 0.55
       else:
           SKIP  ← ACTIVE CONFIG PATH
  → soft confirmation fusion G×C tiers
```

**Active patch:** BitNet never computes, never rejects, never persists a live score (F-004 branch-scope 2026-07-05). Post-CH-002 baseline parity was under this inert path.

`approve()` (~1778) still contains an **unguarded** BitNet block — **dead** (no spine call sites; F-004). If resurrected without `use_bitnet` guard, it would always score.

**Not in** `EXPECTED_ENGINES` / FusionEngine. Not a fourth fusion vote.

### 11. Marginal OOS value

| Claim | Status |
|---|---|
| Hard-reject improves expectancy on BNB gate-ON spine | **Unmeasured** under active config (inert) |
| Authority to enable | **None** without ΔG001 + clean train/serve identity (Authority Ladder §6.5) |
| Adaptive threshold (`bitnet_thresholds.json`) | Dormant / all 0.5; CRT uses fixed 0.55 (F-004) |
| CH-002 alone requires retrain | **No** for production (still off); **Yes** before re-enable |

---

## CH-002 impact assessment

| Question | Answer |
|---|---|
| Did CH-002 change live BitNet behavior? | **No** — `use_bitnet=false` |
| Is call-site map correct / localized? | **Yes** — FM keys on cache; legacy only at `bitnet_score` boundary |
| Does historical train corpus use FM-027/028? | **No** — pipeline FM-021/020 |
| If `use_bitnet` flipped true tomorrow without rebuild? | **SKEW / unsafe** — model sees CRT math under pipeline-trained names |
| Rebuild required now? | **NO** (inert) |
| Rebuild required before re-enable? | **YES** — retrain (or explicit adapter that maps pipeline keys, not CRT FM) + governed labels + ΔG001 |

Documented already in CH-002 impact `train_serve_skew` and F-050 residual.

---

## Rebuild / retrain matrix

| Action | Allowed now? | Condition |
|---|---|---|
| Retrain because CRT names changed | **NO** (gate off; no live consumer) | — |
| Flip `use_bitnet: true` | **NO** without program | Fix train/serve math identity + measure ΔG001 + promote path |
| Point CRT loader at config model_path | Hygiene only | Separate from economic enable |
| Populate `bitnet_registry.json` | Optional governance | Does not grant authority |
| ZoneGate retrain for BitNet rename | **N/A** | Different subsystem |

**Recommended re-enable recipe (future, not this audit):**
1. Decide training population: CRT RETEST emissions (FM-027/028 + body_ratio…) **or** pipeline 6-key — not both under one name.
2. Align `FEATURE_KEYS` / model input / call site to **one** ontology ID set.
3. Re-label with governed exit (`forward_walk` or explicit ATR policy documented as research-only).
4. Shadow measure on gate-ON BNB (and multi) vs baseline 11-trade ledger.
5. Promote only if ΔG001 + hard gates clear — Authority Ladder.

---

## Known gaps / non-blockers

1. **Empty registry** — no GOV-3 promote/rollback for BitNet artifacts.
2. **Cwd-relative load** — `bitnet_score` ignores `engine_runner.model_path`.
3. **Three model files on disk** with different hashes — ambiguous which is “the” artifact for non-CRT tools.
4. **`approve()` unguarded BitNet** — dead but hazardous if re-wired.
5. **Train label bullish-only ATR race** — weak economic target; not M4-grade.
6. **`active_models.yaml` feature list** still pre-CH-002 names — correct for *model* schema; should note CRT serve map in notes (doc hygiene, not runtime).
7. **BitNet V2 adaptive threshold** — Funding Ledger FROZEN (F-004).

---

## Key file map

| Role | Path |
|---|---|
| Inference (CRT) | `src/bitnet/bitnet_inference.py` — `bitnet_score`, `BitNetModel` |
| Runner (alt) | `src/bitnet/bitnet_runner.py` |
| CRT gate | `src/config_layer/crt_engine_v2.py` ~1733–1750, ~1799–1823, call ~2629 |
| Train | `scripts/training/train_bitnet.py` |
| Artifact (live default) | `model.json` (cwd) |
| Config | `configs/production/v2_multi_2026_04.json` — `use_bitnet`, `bitnet_main_threshold` |
| CH-002 skew | `docs/governance/build_manifests/CH-002-f050-emission-rename.impact.json` |
| Finding | `docs/current-findings.md` F-004, F-050 residual |
| Intent | `docs/topics/model-intent-and-feature-ownership.md` BitNet row |
| Registry YAML | `active_models.yaml` → `bitnet:` |
| Tests | `tests/test_bitnet_inference.py`, `tests/test_bitnet_parity.py` |

---

## Comparison to Gaussian audit (context)

| | Gaussian | BitNet |
|---|---|---|
| Active on spine | YES (heuristic) | NO |
| CH-002 live impact | INERT | INERT (gate off) |
| Train/serve skew if wrong path enabled | ML path uses pipeline (OK) | CRT map feeds **different math** under train names |
| Rebuild now | NO | NO |
| Rebuild before enable | N/A (already on heuristic) | **YES** if `use_bitnet` ever true |

---

## Final return

```text
BITNET_ACTIVE_ON_PATCH = false
BITNET_LINEAGE_STATUS  = INERT + CONDITIONAL_SKEW
REBUILD_REQUIRED_NOW   = NO
REBUILD_BEFORE_ENABLE  = YES
NEW_FINDINGS           = none (F-004 / F-050 already cover)
DO_NOT                 = retrain, flip use_bitnet, conflate BitNetZoneGate
NEXT_SUBSYSTEM         = ZoneGate (priority 2) or RR (priority 3) per original plan order
```

---

## Addendum 2026-07-18 — Shadow measurement of the CONDITIONAL_SKEW (F-055)

The audit above was observational (no `use_bitnet` flip). This addendum records the first **economic
measurement** of what enabling the existing model actually does, per the §6.5 Authority Ladder.

**Method.** A hash-neutral, non-active clone of the active config
(`configs/production/v2_multi_bitnet_shadow_2026_07.json`, `crt_engine.use_bitnet=true`, same
`model.json`) was run against the CRT spine and compared to the active gate-OFF config across
BNB/ETH/BTC/SOL. Because `use_bitnet` lives in `crt_engine` (not `params`), the config hash is
unchanged; the file is neither `ACTIVE_VERSION` nor promoted. Driver:
`scripts/research/bitnet_shadow_diagnostic.py`; expectancy taken from the spine's own governed ledger
(`SpineEntry.meta.backtest_pnl_rr_net`); artifacts under `results/bitnet/`.

**Result (pooled, book-level).** E_off=+0.156R (PF 1.29, n=26) → E_on=+0.023R (PF 1.04, n=24),
ΔE=**−0.133R**; **0/4 instruments improve** (BNB neutral ΔE=0; ETH/BTC INERT, 0 rejects; SOL HARMFUL
ΔE=−0.35R). Underpowered (pooled n<30 min-samples floor) → the magnitude is not a hard economic claim,
but the direction has no positive instrument and matches the entry-information null (F-019…F-041).

**Two mechanical notes.** (1) The gate is a **state-machine-perturbing VETO, not a filter**: on BNB it
fired 50 `LOW_SCORE` rejects yet net trades stayed 11→11, because a reject at
`crt_engine_v2.py:1960` **resets** the CRT state machine, so gate-ON is a divergent trajectory
(removed≠added), not a subset. (2) The 4th input `atr` is fed **raw/unnormalized** into the net, so
identical weights mean different things per instrument (BNB≈2.7 vs BTC≈hundreds) — a structural
scale-invariance defect independent of the F-050 label skew.

**Verdict.** No ΔG001 improvement ⇒ **no authority earned** (§6.5). `use_bitnet` stays `false` on the
active config. A governed retrain is **not** warranted on this evidence (null prior + not trainable at
~5-13 entries/instrument, F-019); revisit only if a future measurement is surprisingly positive.
Registered as **F-055**. This does NOT reopen the audit's CONDITIONAL_SKEW verdict — it quantifies it
as economically negative.
