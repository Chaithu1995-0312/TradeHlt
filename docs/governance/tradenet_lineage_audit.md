# TradeNet Lineage Audit

**Program:** Post-CH-002 model/training lineage (subsystem priority 5 — user-requested)  
**Date (UTC):** 2026-07-09  
**Active config:** `v2_multi_2026_04`  
**Prerequisite:** `POST_CH002_BASELINE_DIFFERENTIAL = PASS` · CRT CLOSED  
**Authority:** observational — no retrain, no wire-up, no promote

---

## Verdict

```text
TRADENET_LINEAGE_VERDICT = INERT / UNWIRED
  LIVE_SPINE_CONSUMPTION = ZERO (F-005 Certain)
  ARTIFACTS              = EXIST (legacy v1 .pth; ETH active in registry; no BNB)
  V2_THREE_HEAD          = BUILT (code) · no production v2 JSON envelope on disk for majors
  TRAIN_LABELS           = CONTAMINATED_RISK (opportunities stream — F-022 class)
  CH002_IMPACT           = INERT (pipeline feature names; zero spine consumer)
  REBUILD_REQUIRED       = NO for current production
  MARGINAL_OOS           = NO_AUTHORITY (unwired → no ΔG001 possible)
```

---

## Dual-track + third surface (do not conflate)

| Track | What | On CRT→Fusion spine? |
|---|---|---|
| **A — Fusion neural socket** | `FusionEngine(neural_fn=…)` optional layer 2 | Socket exists; **EngineRunner never passes `neural_fn`** → always `None` |
| **B — TradeNet v2 inference** | `TradeNetV2` 3-head composite (`trade_net_v2.py`) | Built for the socket; **never constructed by EngineRunner** |
| **C — TradeNetMetaEngine** | Meta capital_quality blend around v1 TradeNet | Wired only via `CognitiveBus` sidecar (F-012) — **not** spine decision authority |
| **D — Legacy train_pipeline binary** | `run_training_pipeline` / fusion ENTRY+EXIT → binary label | Alternate train path; same registry family |

`EXPECTED_ENGINES = {crt, gaussian, zone_gate, rr}` — TradeNet is **not** an expected engine.

---

## Lineage chain (11 slots)

### 1. Training population

| Path | Population |
|---|---|
| **Primary v2** | `logs/**/opportunities*.jsonl` filtered by instrument (`train_trade_net_v2.py:_glob_opportunity_files`) |
| **Legacy binary** | Paired ENTRY/EXIT `*_fusion.jsonl` → `scripts/data/build_tradenet_dataset.py` → `train_pipeline.py tradenet` |
| Sample gate | Closed records only (`is_closed`); honors `training_trigger.min_new_samples` when wired |

**Not** CRT-only `TRADE_OPENED` journal. Opportunity stream is a **detection** corpus (F-022), not a verified trade ledger.

### 2. Feature identities

| Item | Detail |
|---|---|
| Dim | **38** — `CANONICAL_FEATURE_DIM` / `CANONICAL_FEATURES` |
| Extract | `extract_feature_vector(feats)` from record `features` dict |
| Names | Pipeline identities including `retest_depth` (FM-021), `disp_strength` (FM-020) |
| CRT FM-027/028 | **Not** TradeNet inputs |

CH-002 did not rename pipeline features → trained vectors stay name-aligned with FeaturePipeline.

### 3. Target / label

#### v2 three heads (`train_trade_net_v2.py:141-163`)

| Head | Definition |
|---|---|
| `p_tp1` / reaches_tp1 | outcome ∈ {TP1, TP2, TP1_HIT, TP2_HIT} |
| `p_tp2` / reaches_tp2 | outcome ∈ {TP2, TP2_HIT} |
| `p_survives_be` | `mfe >= \|entry−sl\|` (1R); missing `mfe` → 0 |

Composite (inference): `0.4·p_tp1 + 0.4·p_tp2 + 0.2·p_survives_be` (`trade_net_v2.py:45`, train script same weights).

#### Legacy v1

Binary win/loss from fusion EXIT pairing (`build_tradenet_dataset.py`).

**Label risk:** Opportunity `outcome` / `rr` fields are the F-022 class (36.8% self-consistency historically). F-041B showed re-derive via `forward_walk` flips SL rates. → treat economic claims as **CONTAMINATED** until re-label.

### 4. Dataset builder

| Builder | Role |
|---|---|
| `scripts/training/train_trade_net_v2.py` | Load opps → `filter_usable_records` → matrix + 3-head labels → train → register |
| `scripts/data/build_tradenet_dataset.py` | fusion JSONL → binary training.json |
| `src/training/train_pipeline.py` | Generic binary TradeNet train path |
| Shared enrichment | Stage-1 / master training JSONL may feed research, not required for spine |

### 5. Artifact

| Path | Form | Registry `active` | Notes |
|---|---|---|---|
| `models/tradenet_registry.json` | Manifest | — | 4 version keys; **no `__active__` map**; no BNBUSDT entry |
| `models/ETHUSDT/.../tradenet_v5_auto_2026_06_eth.pth` + `_scaler.json` | Legacy v1 | **`active: true`** · instrument ETHUSDT | Only active entry |
| `models/EURUSD/.../tradenet_v6_2026_05_eur.pth` | Legacy v1 | false | Experiment |
| Other registry rows | Point at missing/legacy roots | false | Stale paths possible |
| **v2 JSON envelopes** (`schema_version=tradenet_v2`) | — | none observed under `models/` for majors | Code supports them; disk is still .pth |

**BNB baseline instrument:** no TradeNet artifact. Even if wired, BNB would hit `TRADENET_MISSING` → `predict() → None`.

### 6. Loader

| Class | Resolve | Modes |
|---|---|---|
| `TradeNetV2` | path **or** `get_active_tradenet_version(instrument)` | `v2` numpy envelope · `legacy_v1` .pth+torch · `missing` |
| `TradeNetMetaEngine` | `get_active_tradenet()` + `load_model` / scaler | Fail-open capital_quality |
| Registry API | `model_registry.py` ~1479+ | `get_active_tradenet*` / `register_tradenet` |

Missing mode: emits `TRADENET_MISSING` CRITICAL once; `predict` returns `None` so fusion can renormalize **if** neural_fn were wired.

### 7. Inference inputs

```text
features: dict with full CANONICAL_FEATURES keys
  → extract_feature_vector → scale → trunk → heads
```

Pipeline `retest_depth` / `disp_strength` only. No CRT cache mapping (unlike BitNet).

### 8. Output semantics

| Mode | Output |
|---|---|
| v2 | `{tradenet_score, p_tp1, p_tp2, p_survives_be, schema_version}` |
| legacy v1 | composite = single sigmoid p_win; head fields `None` |
| missing | `None` |
| Meta engine | `capital_quality_score`, allocation tiers — **sidecar**, not fusion engine score |

Intended fusion role (docstring): optional neural layer weight alongside gaussian in `FusionEngine.evaluate()` — **not** one of the four `compute()` engines (crt/gaussian/zone/rr).

### 9. Active config

| Key | Value | Effect |
|---|---|---|
| `engine_runner.fusion_use_evaluate` | **`false`** | Live path uses multi-engine `compute()`, not neural evaluate path |
| `fusion_engine.neural_weight` | `0.4` | Only matters if `neural_fn` set **and** evaluate path used |
| TradeNet enable flag | **none** | No `use_tradenet` toggle — wiring is code-absent, not config-gated |
| `EXPECTED_ENGINES` | no tradenet | Completeness gate ignores it |

`active_models.yaml`: **no `tradenet:` section** (registry gap; F-005 only cross-ref under gaussian findings list).

### 10. Runtime consumption

```text
EngineRunner.__init__
  → FusionEngine(gaussian_adapter=…, neural_fn=DEFAULT None, …)   # engine_runner.py:406-410
  → never constructs TradeNetV2 / TradeNetMetaEngine

EngineRunner.run
  → engines crt/gaussian/zone_gate/rr
  → fusion.compute(engine_results)   # 4-engine blend; no neural_fn
  → DecisionEngine …

FusionEngine.evaluate (optional, config off)
  → gaussian_adapter + optional neural_fn + optional llm
  → would consume neural_fn IF provided — it is not
```

**Sidecar only:**

```text
CognitiveBus → TradeNetMetaEngine  (cognitive_bus.py:213-232)
  → F-012: zero spine consumption
```

Post-CH-002 BNB gate-ON baseline: 11 trades with **zero** TradeNet influence (parity vs pre-CH-002 confirms rename did not need TradeNet).

### 11. Marginal OOS value

| Claim | Status |
|---|---|
| TradeNet improves expectancy on live/gate-ON spine | **Unmeasurable** — not on path |
| Registry `active:true` on ETH | **Grants no production authority** (Authority Ladder; F-005) |
| Retrain/promote for CH-002 | **NO** — unwired + pipeline names unchanged |
| Wire-up justification | Requires clean labels + shadow ΔG001 + explicit product decision — **not** name cleanup |

**Verdict:** `NO_AUTHORITY` / `INERT`.

---

## CH-002 impact assessment

| Question | Answer |
|---|---|
| Does TradeNet read CRT FM-027/028? | **No** |
| Pipeline feature names after CH-002? | Unchanged (`retest_depth`/`disp_strength` = FM-021/020) |
| Live score delta from CH-002? | **None** (unwired) |
| Rebuild required now? | **NO** |
| Rebuild if ever wired? | Re-label first (F-022); prefer v2 envelopes; train per-instrument including BNB if BNB is the product surface |

Historical opportunity JSONL may still carry pre-CH-002 CRT **cache** field names in nested blobs — irrelevant until those fields are used as model inputs (they are not for the 38-dim pipeline extract).

---

## Qualification protocol (successor authority for wire-up)

**Authoritative path from INERT → production:**  
[`tradenet_qualification_protocol.md`](tradenet_qualification_protocol.md) (`TN_QUAL_V1`).

Defines: **GATE-0 label feasibility** (practical + worth it?) → clean-label generation
(`forward_walk` / F-022 ban) · retrain triggers · offline metrics · shadow (weight-0) · GATE-P
spine promotion. Publishing that protocol does **not** wire TradeNet; GATE-0 starts OPEN and
GATE-L is blocked until **FEASIBLE_GO**. This lineage audit remains the observational **AUDITED**
baseline.

## Rebuild / retrain / wire matrix

| Action | Allowed now? | Condition |
|---|---|---|
| Retrain because of CH-002 rename | **NO** | Unwired + pipeline math unchanged |
| Wire `neural_fn=TradeNetV2(...).predict` into EngineRunner | **NO** without program | **TN_QUAL_V1 GATE-P** (L→O→S→P) + construction protocol |
| Promote ETH active .pth to “production” | **NO** | Registry active ≠ spine authority |
| Train BNB model | Research only | Still no consumer; clean labels = GATE-L first |
| Add `tradenet:` to `active_models.yaml` | Doc hygiene OK | Does not wire spine |
| Use TradeNet for StructuredOpportunity features later | Deferred | Only after audits complete + contracts from verified interfaces |

---

## Known gaps / non-blockers

1. **F-005** — permanent empty neural socket (Certain).
2. **No BNB artifact** — baseline instrument uncovered.
3. **Disk = legacy .pth**; v2 three-head code exists but production envelopes not the active registry form.
4. **F-022 label contamination** on opportunity outcomes.
5. **`active_models.yaml` missing TradeNet section.**
6. **CognitiveBus meta** is a second, also non-spine, consumer (F-012).
7. **Broken registry paths** possible for inactive roots (`tradenet_v5_tradenet_2026_05_eur.pth` at models root may be missing).
8. **Docstring drift** in meta engine (“35-dim”) vs current 38.

---

## Key file map

| Role | Path |
|---|---|
| v2 inference | `src/training/trade_net_v2.py` |
| v2 train CLI | `scripts/training/train_trade_net_v2.py` |
| Legacy dataset | `scripts/data/build_tradenet_dataset.py` |
| Meta sidecar | `src/engines/tradenet_meta_engine.py` |
| Fusion socket | `src/core/fusion_engine.py` (`neural_fn`, `evaluate`) |
| Non-wiring | `src/core/engine_runner.py:406-410` |
| Registry | `models/tradenet_registry.json` · `model_registry.py` tradenet APIs |
| Cognitive bus | `src/cognitive/cognitive_bus.py` |
| Finding | `docs/current-findings.md` F-005 · F-012 · F-022 |
| Qualification protocol | [`tradenet_qualification_protocol.md`](tradenet_qualification_protocol.md) (`TN_QUAL_V1`) |
| Config | `v2_multi_2026_04.json` — `fusion_use_evaluate:false`, `neural_weight:0.4` |

---

## Comparison to BitNet / Gaussian

| | Gaussian | BitNet | TradeNet |
|---|---|---|---|
| On spine today | YES (heuristic) | NO (`use_bitnet`) | NO (never wired) |
| Artifact used live | mu/sigma registry | cwd model.json unused | ETH .pth unused |
| CH-002 skew risk | INERT | CONDITIONAL if enable | INERT |
| Rebuild now | NO | NO | NO |
| Lowest leverage | — | — | **Yes** (this audit confirms) |

---

## Final return

```text
TRADENET_SPINE_STATUS    = UNWIRED (F-005)
TRADENET_LINEAGE_STATUS  = INERT
REBUILD_REQUIRED_NOW     = NO
NEW_FINDINGS             = none
DO_NOT                   = retrain, wire neural_fn, promote ETH model, reopen CRT
PLAN_PROGRESS            = Gaussian + BitNet + TradeNet audits done;
                           still open: ZoneGate (pri 2), RR (pri 3)
```
