# Configuration Authority Matrix

| Field | Value |
|---|---|
| Status | **ACTIVE (audit)** — Sources registered; field matrix filled; consolidation decisions **pending user joint review** |
| Date (UTC) | 2026-07-11 |
| Branch scope | `feature/truth-registry-v2` / `ACTIVE_VERSION=v2_multi_2026_04` |
| Authority | Observational / navigation only — **grants no promotion, retrain, or enablement** |
| Related | Lineage audits `*_lineage_audit.md` · F-004 · F-016 · F-036–F-041 · F-044–F-048 · F-050–F-051 |
| Non-goal | Do **not** invent a fourth peer layer beside WHO / HOW / WHAT |

---

## 0. Doctrine (frozen)

| Layer | Role | Canonical home | Runtime load? |
|---|---|---|---|
| **WHO** | Which model uses which feature / why; dual-track truth | `active_models.yaml` (repo root) | **Partial** — `state_contracts` load (Phase-1) + `valid_transitions` drive SM instance graph (Phase-Topology §13); narrative/detection blocks remain session-only |
| **HOW** | Thresholds, weights, switches, paths | `configs/production/{ACTIVE_VERSION}.json` via `ACTIVE_VERSION` | Yes |
| **WHAT** | Mathematical meaning of a quantity (FM-*) | `configs/formulas/market_ontology.yaml` → `src/features/registry/` + `features.fm_resolve` (Phase-2) | Indirect (registry dispatch; never `eval`) |

Everything else is a **pointer**, **version manifest**, **trained artifact**, **provenance sidecar**, or **research overlay** — not a peer of WHO/HOW/WHAT.

**Consolidation rule (when decisions land):** numbers → HOW · formulas → WHAT · narrative/reachability → WHO · version pointers → existing manifests (not a new mega-YAML).

---

## 1. Sources inventory (path-corrected)

User-supplied paths with actual repo paths. Two paths were wrong-by-one-directory.

| # | User path | Actual path | Exists | sha256[:16] | Role class |
|---|---|---|---|---|---|
| S1 | `configs/market_ontology.yaml` | **`configs/formulas/market_ontology.yaml`** | YES | `d0f49f99ff70270e` | WHAT (descriptive) + formula bind |
| S2 | `configs/active_models.yaml` | **`active_models.yaml`** | YES | `2857825af718b2e5` | WHO (descriptive; not runtime) |
| S3 | `configs/production/v2_multi_2026_04.json` | same | YES | `8f45c66c1175cf87` | HOW (active production) |
| S4 | `configs/production/ACTIVE_VERSION` | same | YES | `4bd5912b8195855d` | Tier-0 pointer → `v2_multi_2026_04` |
| S5 | `configs/promotion_log.jsonl` | same | YES | `c61189c3bc52e9aa` | Governance history (append-only) |
| S6 | `configs/research/research_config_spine.json` | same | YES | `6050f93f93ce22b8` | Research overlay; pins prod version |
| S7 | `models/zone_registry.json` | same | YES | `e73e08934add02c9` | **Runtime** ZoneGate geometry |
| S8 | `models/zone_gate_registry.json` | same | YES | `e6d36474edce31a7` | ZoneGate **version manifest** |
| S9 | `models/gaussian_registry.json` | same | YES | `393e84c06d5ce404` | Gaussian **ML** artifact registry |
| S10 | `models/rr_registry.json` | same | YES | `8cfb1c2da11d4040` | RR trained-model version registry |
| S11 | `models/rr_model.meta.json` | same | YES | `606ab9b476a315a7` | RR diagnostics / confidence-gate meta |
| S12 | `models/tradenet_registry.json` | same | YES | `b92ac8f2f3f79731` | TradeNet artifact registry |
| S13 | `models/bitnet/bitnet_registry.json` | same | YES empty `{}` | `44136fa355b3678a` | BitNet artifact registry (empty) |
| S14 | `src/bitnet/bitnet_thresholds.json` | same | YES | `6085fa295a253b4c` | Adaptive BitNet thresholds |

### 1.1 Linked sources (bridge gaps — not a fourth layer)

| Path | Why linked | sha256[:16] |
|---|---|---|
| `models/rr_model.json` | Config `rr_model.model_path` / `rr_fusion.model_path` | `6ed92d26ff612538` |
| `models/rr_model_202605_bnb_v2.json` | `rr_registry` active entry — **byte-identical** to `rr_model.json` | `6ed92d26ff612538` |
| `models/zone_registry.provenance.json` | PIT_UNCLEAN tag for S7 | `1a2b56b120a52af1` |
| `models/rr_model.provenance.json` | PIT_UNCLEAN tag for RR artifact | `0078314080cb914f` |
| `src/config_layer/production_config.py` | `get_active_version()` / load | — |
| `src/features/registry/_loader.py` | Ontology load path | — |
| `src/bitnet/bitnet_runner.py` | Loads S14 | — |
| `tests/test_zone_manifest_runtime_parity.py` | S7↔S8 invariant (F-041A) | — |
| `docs/governance/{gaussian,zonegate,rr,bitnet,tradenet}_lineage_audit.md` | Dual-track / mismatch proof | — |

### 1.2 Dead / missing references discovered while bridging

| Reference | Status | Implication |
|---|---|---|
| `models/registry.json` + `models/active.txt` (docstring in `model_registry.py`) | **MISSING** | Superseded pattern; per-model `*_registry.json` is the live pattern |
| `rr_model.dataset_path` → `models/rr_dataset.json` | **MISSING** on disk | Stale HOW pointer (rr_fusion already off) |
| `models/bitnet/bitnet_registry.json` | Empty `{}` | No artifact governance for BitNet yet |

---

## 2. System map (one configuration system)

```text
ACTIVE_VERSION (S4)
    │  get_active_version()  [production_config.py]
    ▼
v2_multi_2026_04.json (S3)  ── HOW ── thresholds / weights / flags / paths
    │
    ├─ engine_runner.zone_registry_path ──► zone_registry.json (S7)  [EXEC geometry]
    ├─ engine_runner.zone_mode / zone_gate.{top_k,cluster_*}
    ├─ engine_runner.gaussian_impl=heuristic  ──► HeuristicGaussianEngine + gaussian_scorer
    │         (does NOT load S9 for live score)
    ├─ engine_runner.rr_fusion.enabled=false + model_path ──► rr_model.json
    ├─ rr_model.* (confidence_gate, model_path, dataset_path)
    ├─ crt_engine.use_bitnet=false + bitnet_main_threshold=0.55
    ├─ engine_runner.zone_cluster_threshold=0.25
    └─ params.body_ratio_min=0.65  …

zone_gate_registry.json (S8) ──active:v2_gaussian_runtime_2026_07──► S7
    parity: tests/test_zone_manifest_runtime_parity.py (F-041A)

gaussian_registry.json (S9) ──active ML ETH/BNB──► trained artifacts  [INERT on heuristic]
rr_registry.json (S10) ──active:202605_bnb_v2──► rr_model_202605_bnb_v2.json ≡ rr_model.json
tradenet_registry.json (S12) ──active ETH──► .pth  [spine UNWIRED F-005]
bitnet_registry.json (S13) ──{}──

promotion_log.jsonl (S5)  ◄── PROMOTED / PROMOTION_FAILED audit
research_config_spine.json (S6) ──spine.prod_version──► must == S4
active_models.yaml (S2) ──DESCRIBES──► all of the above (WHO)
market_ontology.yaml (S1) ──DECLARES FM-*──► formula_registry / candle_math / derived_math
bitnet_thresholds.json (S14) ──BitNetRunner only──► per-instrument regime thresholds (default 0.5)
```

### 2.1 Active-version alignment (measured 2026-07-11)

| Pointer | Value | Status |
|---|---|---|
| S4 `ACTIVE_VERSION` | `v2_multi_2026_04` | EXEC Tier 0 |
| S3 `version` | `v2_multi_2026_04` | ALIGNED |
| S6 `spine.prod_version` | `v2_multi_2026_04` | ALIGNED |
| S5 latest successful PROMOTED | `v2_multi_2026_04` @ 2026-05-06T19:34:01Z (`config_hash` prefix `ba17ffb9…`) | Historical |
| S3 `config_hash` field | `7de09f62…` | **≠ last promotion hash** — treat as stale/unreconciled integrity pointer (document; no auto-rehash) |

---

## 3. Descriptive vs executable (file rollup)

| Source | Executable by spine runtime? | Class |
|---|---|---|
| S4 ACTIVE_VERSION | Yes (pointer) | POINTER |
| S3 production JSON | Yes | HOW EXEC |
| S7 zone_registry | Yes (geometry) | ARTIFACT EXEC |
| S8 zone_gate_registry | No scoring; yes promote/list + parity guard | MANIFEST |
| S9 gaussian_registry | Only if `gaussian_impl=ml` | MANIFEST (inert today) |
| S10 rr_registry | Training/promote; live fusion uses S3 path | MANIFEST |
| `rr_model.json` | Only if `rr_fusion.enabled` | ARTIFACT DEAD (path present) |
| S11 rr_model.meta | No | DIAGNOSTIC |
| S12 tradenet_registry | Only if TradeNet wired | MANIFEST DEAD |
| S13 bitnet_registry | Empty | EMPTY |
| S14 bitnet_thresholds | Yes for `BitNetRunner`; CRT hard-reject uses S3 when `use_bitnet` | EXEC (alternate path) |
| S1 ontology | Indirect via formula registry | WHAT |
| S2 active_models | No | WHO DESC |
| S5 promotion_log | No | AUDIT |
| S6 research spine | Yes for research harness only | RESEARCH OVERLAY |

---

## 4. Field-level authority matrix

**Cell labels:** `EXEC` · `DESC` · `MANIFEST` · `DEAD` · `CONFLICT` · `MISSING` · `N/A` · `ALIGNED`

**Decision column:** filled only after joint review — provisional suggestions are *recommendations*, not authority.

### Legend for Source columns

Abbreviated: `ont` S1 · `am` S2 · `prod` S3 · `AV` S4 · `plog` S5 · `spine` S6 · `zreg` S7 · `zman` S8 · `greg` S9 · `rreg` S10 · `rmeta` S11 · `treg` S12 · `breg` S13 · `bth` S14

### 4.1 Version / integrity

| # | Semantic | Live value(s) | ont | am | prod | AV | plog | spine | Other | Status | Decision (pending) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| R01 | Active production version id | `v2_multi_2026_04` | N/A | DESC (branch notes) | EXEC `version` | EXEC pointer | AUDIT PROMOTED | EXEC `spine.prod_version` | code `get_active_version` | **ALIGNED** | KEEP multi-pointer; optional ENFORCE_TEST spine↔AV |
| R02 | Config integrity hash | prod `7de09f62…` vs last promo `ba17ffb9…` | N/A | N/A | EXEC field | N/A | AUDIT historical hashes | N/A | `config_integrity` orphaned (F-006) | **CONFLICT** (stale hash chain) | DOCUMENT_ONLY now; rehash only under promotion lifecycle |
| R03 | Research↔prod pin | both `v2_multi_2026_04`; v4 not loadable on patch | N/A | DESC F-016 | N/A | EXEC | N/A | EXEC + note | — | **ALIGNED** + documented v2/v4 split | KEEP |

### 4.2 ZoneGate

| # | Semantic | Live value(s) | am | prod | zreg | zman | Status | Decision (pending) |
|---|---|---|---|---|---|---|---|---|
| R04 | Zone geometry artifact path | `models/zone_registry.json` | DESC `registry_file` | EXEC `zone_registry_path` | EXEC file | MANIFEST active→same path | **ALIGNED** (F-041A) | KEEP + existing parity test |
| R05 | Zone geometry content | 8 zones, schema `v2_gaussian`, feature_order 38, per-zone threshold `0.3` | DESC | N/A | EXEC centroids | MANIFEST n_zones/feature_order | ALIGNED content via path | KEEP; provenance PIT_UNCLEAN |
| R06 | Zone mode | `hard` | DESC | EXEC `zone_mode` | N/A | N/A | ALIGNED | KEEP |
| R07 | Zone knobs top_k / cluster_* | top_k=3, cluster_min_n=2, cluster_spread_max=0.15 | DESC F-036 INERT | EXEC (tunable) | N/A | N/A | **DEAD knobs** (ΔG001≡0) | DOCUMENT_ONLY / optional RETIRE from optimization narrative |
| R08 | Zone PIT provenance | PIT_UNCLEAN_CENTERED_SWINGS + global_batch_vol | DESC pit_provenance | N/A | sidecar | N/A | ALIGNED tag | KEEP sidecar; no promote |

### 4.3 Gaussian dual-track

| # | Semantic | Live value(s) | am | prod | greg | Status | Decision (pending) |
|---|---|---|---|---|---|---|---|
| R09 | Live Gaussian implementation | `heuristic` (3 features) | DESC runtime | EXEC `gaussian_impl` | N/A for live | **DUAL_TRACK truth** | KEEP dual-track; never merge into one “active gaussian” |
| R10 | Heuristic scorer params | retest/body/disp mu,s2; sigmoid; execute_p | DESC config_sections | EXEC `gaussian_scorer` | N/A | EXEC HOW | KEEP in HOW |
| R11 | ML Gaussian active artifacts | ETH `v5_auto_2026_06_eth`, BNB `p5_20260524T120449` + `__active__` map | DESC trained_registry | N/A (impl≠ml) | MANIFEST active | **INERT on spine** | DOCUMENT_ONLY; do not treat registry active as live |

### 4.4 RR three contracts

| # | Semantic | Live value(s) | am | prod | rreg | rmeta | Status | Decision (pending) |
|---|---|---|---|---|---|---|---|---|
| R12 | Live RR geometry | RREngine polarity ∈[0.5,1] on OHLC | DESC engine | fusion weight_rr | N/A | N/A | EXEC geometry | KEEP A-contract |
| R13 | RR fusion enable | `false` | DESC `rr_fusion_active:false` | EXEC `rr_fusion.enabled` | N/A | N/A | **DEAD path** (F-038) | KEEP disabled |
| R14 | RR trained model path | config `models/rr_model.json`; registry active `…_bnb_v2.json` | DESC | EXEC path | MANIFEST different path **same bytes** | points at `rr_model.json` | **PATH_SPLIT / CONTENT_ALIGNED** | DOCUMENT_ONLY or ENFORCE_TEST hash parity (not path rename required) |
| R15 | RR confidence bypass | `0.3` legacy_scalar; F-044 mis-scaled | DESC F-044 | EXEC `confidence_bypass_threshold` + `confidence_gate` | N/A | d_sq percentiles | **GATE_SKEW if re-enabled** | KEEP off; no re-enable without gate redesign |
| R16 | RR dataset path | `models/rr_dataset.json` | N/A | EXEC path | some entries have datasets | dataset name in meta | **MISSING file** | RETIRE/fix path when next HOW edit; not urgent (fusion off) |
| R17 | DecisionEngine `rr_threshold` | `1.5` vs polarity∈[0.5,1] | DESC F-048 | EXEC | N/A | N/A | **CONFLICT semantic** | DO NOT “fix” silently; F-048 open intent |
| R18 | Ultron `min_rr_ratio` | `1.5` true forward RR | DESC separate | EXEC | N/A | N/A | DISTINCT semantic | KEEP; never rename into DecisionEngine without design |

### 4.5 BitNet multi-threshold

| # | Semantic | Live value(s) | am | prod | bth | breg | Status | Decision (pending) |
|---|---|---|---|---|---|---|---|---|
| R19 | BitNet enable | `use_bitnet: false` | DESC dormant | EXEC | N/A | empty | **INERT** (F-004) | KEEP off |
| R20 | CRT hard-reject threshold | `bitnet_main_threshold: 0.55` | DESC `threshold: 0.55` | EXEC | N/A | N/A | DESC+EXEC align for CRT path | KEEP in HOW |
| R21 | Zone BitNet threshold | `zone_cluster_threshold: 0.25` | DESC config_sections | EXEC | N/A | N/A | Different consumer | KEEP named distinctly |
| R22 | Adaptive thresholds file | defaults 0.5 all regimes | N/A | optional path override | EXEC defaults | N/A | **Third number space** (0.5 ≠ 0.55) | DOCUMENT dual-surface; no merge until re-enable design |
| R23 | BitNet artifact registry | `{}` | N/A | N/A | N/A | EMPTY | Empty governance | DOCUMENT_ONLY / optional future manifest; **not** a new YAML authority |

### 4.6 Formulas / feature identities

| # | Semantic | Live value(s) | ont | am | prod | Status | Decision (pending) |
|---|---|---|---|---|---|---|---|
| R24 | `body_ratio` formula | FM-010 body/range [0,1] consumable; non-canonical live-hook GD-001 family | WHAT EXEC via registry | DESC | N/A formula | WHAT authoritative | KEEP ontology + registry; code owns non-canonic residual |
| R25 | `body_ratio_min` gate | prod `0.65`; ontology notes cite `0.70` as CRT displacement coherent gate | DESC note 0.70 | DESC | EXEC `params.body_ratio_min=0.65` | **DESC≠EXEC** threshold | HOW owns number; fix prose if needed (DOC_DRIFT), not invent third value |
| R26 | `disp_strength` / `retest_depth` names | FM-020/021 pipeline; FM-027/028 CRT emissions (CH-002); FM-029 rescale | WHAT multi-id | DESC F-050 | N/A | **RESOLVED by FM ids** | KEEP multi-id; never collapse names |
| R27 | CRT market states in ontology | 9 states **not** declared in ontology (by design) | OUT OF SCOPE | DESC state machine | crt_engine knobs | **NOT a gap** | KEEP algorithm vs formula boundary |

### 4.7 Fusion / TradeNet

| # | Semantic | Live value(s) | am | prod | treg | Status | Decision (pending) |
|---|---|---|---|---|---|---|---|
| R28 | Fusion weights | crt 0.4 / gaussian 0.2 / zone 0.2 / rr 0.2 | DESC | EXEC | N/A | EXEC HOW | KEEP |
| R29 | Fusion evaluate flags | `fusion_use_evaluate:false`, compare true | DESC | EXEC | N/A | EXEC | KEEP |
| R30 | Neural / TradeNet slot | neural_weight 0.4 in fusion; TradeNet ETH active in registry | DESC F-005 UNWIRED | EXEC weights present | MANIFEST active | **DEAD for spine** | DOCUMENT dual-track; no enable |

### 4.8 Research costs (overlay, not production HOW)

| # | Semantic | Live value(s) | spine | prod | Status | Decision (pending) |
|---|---|---|---|---|---|---|
| R31 | Round-trip cost | spine 12 bps | EXEC research | separate backtest/slippage | DISTINCT systems | KEEP separate |
| R32 | Spine SL/TP defaults | apply_signal_defaults false; scorer_mode calibrated | EXEC research | execution_planner / crt exits | DISTINCT | KEEP |

---

## 5. Registry overlap summary

| Registry | What `active` means today | What runtime actually uses | Safe consolidation target |
|---|---|---|---|
| zone_gate_registry | Points at runtime geometry file | Same file via prod path | **None** — already reconciled; keep parity test |
| gaussian_registry | ML artifact active per instrument | Heuristic scorer | Do **not** collapse; dual-track is truth |
| rr_registry | Versioned trained model | Path via prod; geometry always on | Optional hash-parity test; keep both names if content-identical |
| tradenet_registry | Trained .pth active | Unwired | Leave; no spine wiring |
| bitnet_registry | Empty | Thresholds in S14 + prod | Document empty; thresholds stay dual-surface until design |
| (legacy) registry.json | Missing | n/a | Document as superseded in code comments only when next touched |

---

## 6. What can be safely consolidated **into existing YAMLs** (candidates only)

> These are **candidates for joint review**, not approved edits.

| Candidate | Into | Risk if done naively |
|---|---|---|
| Document dual-track gaussian/rr/bitnet in one place | WHO (`active_models.yaml`) already mostly done | Overwriting EXEC numbers into WHO |
| Stale `dataset_path` / empty bitnet registry notes | HOW notes or WHO evidence notes | Touching prod JSON without rehash |
| Threshold synonym glossary (`rr_threshold` vs `min_rr_ratio` vs confidence bypass) | WHO or this matrix | Renaming production keys (breaks loaders) |
| Formula prose `0.70` vs `0.65` | WHAT note or HOW sole number | Changing gate value without economic proof |
| Mega `configs/unified.yaml` | **FORBIDDEN** | Creates fourth authority |

**Do not consolidate:** S7 geometry into production JSON; S1 formulas into production JSON; S9 ML registry into heuristic params.

---

## 7. Recommended next steps (user joint review)

1. Walk rows R01–R32; mark each Decision column `KEEP` / `SPLICE` / `RETIRE` / `ENFORCE_TEST` / `DOCUMENT_ONLY`.
2. Priority decisions:
   - **R14** RR path split: hash-parity test vs document-only
   - **R17** F-048 DecisionEngine `rr_threshold` intent
   - **R22** BitNet adaptive store permanence
   - **R02** config_hash vs promotion_log drift (integrity hygiene)
3. Only after decisions: optional parity tests (zone-style); still no fourth YAML.
4. Any HOW edit → promotion lifecycle / rehash; any WHAT formula change → parity + ownership lint.

---

## 8. Verification checklist (this audit)

| Check | Result 2026-07-11 |
|---|---|
| All 14 Sources exist | PASS |
| AV == prod.version == spine.prod_version | PASS (`v2_multi_2026_04`) |
| Zone manifest active → runtime file | PASS (`models/zone_registry.json`, sha `e73e0893…`) |
| RR registry active file hash == config model_path hash | PASS (both `6ed92d26…`) |
| Dual-track gaussian documented in active_models + lineage audit | PASS |
| No config/code mutation in this audit | PASS (docs only) |

---

## 9. Open questions for the user

1. RR registry vs config path: enforce hash parity (recommended) or path equality?
2. BitNet: keep S14 as permanent adaptive store, or fold defaults into production when/if re-enabled?
3. F-048: treat DecisionEngine `rr_threshold` as dormant-by-design or as a bug to remediate?
4. config_hash field vs promotion_log: schedule integrity reconciliation or leave as known drift under F-006 orphan class?

---

## 10. State → Feature → Model Executable Contract

| Field | Value |
|---|---|
| Status | **MAPPED** (executable code trace; observational) |
| Date (UTC) | 2026-07-11 |
| Code authority | `src/config_layer/crt_engine_v2.py`, `src/core/engine_runner.py`, `src/engines/crt_engine.py` |
| Authority | Navigation / contract only — **grants no enablement, retrain, or control-flow change** |
| Non-goal | No fourth YAML; no formulas in WHO; no numeric thresholds in WHO |

### 10.0 Two executable surfaces (do not conflate)

| Surface | Owner | Role |
|---|---|---|
| **A — CRT state spine** | `CRTEngine.process_candle` `crt_engine_v2.py:2283` | Owns `CRTState`, transitions, `TRADE_OPENED` |
| **B — Fusion EngineRunner** | `EngineRunner.run` `engine_runner.py:570` | Runs engines **unconditionally** on feature dict; **does not read `CRTState`** |

Fusion `crt_compute` (`engines/crt_engine.py:17`) is a **feature scorer** (`scoring_engine.compute_scores`), **not** the state machine.

### 10.1 Resolvers (executable proof)

| Resolver | Exists? | Evidence |
|---|---|---|
| **STATE → FEATURES** | **NO** | No `state_to_feature` / required-feature table; features computed inline in `try_*` / soft-conf |
| **STATE → MODELS** | **NO** | No state→engine dispatch; BitNet is config-gated inside soft-conf, not registry-resolved |
| **FEATURE → MODELS** | **NO** | Engines take feature dicts; no feature→model routing table |

Ontology registry (`FORMULA_REGISTRY`) is **not** loaded by CRT. CRT binds via **direct imports**:

```text
crt_engine_v2.py:31-32
  from features import candle_math as _cm
  from features import derived_math as _dm
```

FM math is **parity-aligned** with ontology/registry, but **runtime does not resolve FM IDs dynamically**.

### 10.2 FM binding table (quantities CRT actually uses)

| Quantity | FM ID | Ontology path | Formula (declared) | Impl binding | Runtime call site | Via registry? |
|---|---|---|---|---|---|---|
| `body_ratio` | **FM-010** | `feature_compositions.body_ratio` | body/range [0,1] | `candle_math.body_ratio` | `Candle.body_ratio` → `_cm.body_ratio` `:117-118` | **NO** — direct import |
| `candle_range` / hist. `wick_size` | **FM-002** | `primitives.candle_range` | high−low | `candle_math.candle_range` | `Candle.wick_size` → `_cm.candle_range` `:111-113` | **NO** |
| `body_size` | **FM-001** | `primitives.body_size` | \|close−open\| | `candle_math.body_size` | `Candle.body_size` `:107-108`; gates use `abs(close-open)` inline too | **NO** |
| `displacement_retrace` | **FM-027** | `derived_metrics.displacement_retrace` | cross-candle retrace | `derived_math.displacement_retrace` | `try_expansion_to_retest` `:1385-1389` | **NO** |
| `displacement_atr_ratio` | **FM-028** | `derived_metrics.displacement_atr_ratio` | range/ATR | `derived_math.displacement_atr_ratio` | retest guard `:1360`; cache `:1390-1393` | **NO** |
| Pipeline `disp_strength` | FM-020 | ontology | body/(atr·close) | `derived_math.disp_strength` | **Not used by CRT SM** | n/a on SM |
| Pipeline `retest_depth` | FM-021 | ontology | \|close−ema\|/(atr·close) | `derived_math.retest_depth` | **Not used by CRT SM** | n/a on SM |
| Soft-conf “ema momentum” | **CRT-local** | none | `(ema_f−ema_s)·dir/atr` | inline `:1667-1669` | **not** `_dm.ema_spread` | **NO** |
| Soft-conf “disp inherit” | **CRT-local** | none | `min(1, \|disp body\|/(1.5·ATR))` | inline `:1683-1686` | **not** FM-028 | **NO** |
| ATR | **CRT-local** | not FM | mean true range | `RangeDetector.compute_atr` `:1005-1018` | every candle `:2294` | **NO** |
| HTF range H/L/EQ | **CRT-local** | not FM | maxH/minL/(H+L)/2 | `detect_htf_range` `:988-1003` | init/reset | **NO** |
| RiskScore G weights | **CRT-local** | not FM | 0.35/0.25/0.20/0.20 hardcode | `RiskScore.final` `:216-222` | soft-conf path | **NO** |

### 10.3 Master table

| State | Raw Inputs | Required FM IDs | CRT-local Formulas | Config Keys | Outgoing Guards | Models Evaluated | Model Invocation Reason | State→Feature Resolver | State→Model Resolver | Decision Effect |
|---|---|---|---|---|---|---|---|---|---|---|
| **RANGE** | OHLCV; HTF id; `active_range`; optional `pending_displacement_*` | *(none required to enter/stay)* optional diagnostic wicks use FM-002/010 | ATR; range H/L/EQ; shadow TTL−1; sweep breach/reject; sweep taxonomy wicks | `atr_period`, `atr_buffer_multiplier`, `ema_fast`, `ema_slow`, `pending_displacement_ttl_candles`; global reset: `retrace_reset_pct`, `extension_reset_fib` | →SWEEP (`detect_sweep`+`try_range_to_sweep`); →SHADOW_PENDING if sweep dir matches pending; →RANGE via reset | **CRT SM only** (on spine). Fusion path: CRT-scorer/Gaussian/ZoneGate/RR **global if EngineRunner runs** | SM owns state; fusion engines **not state-gated** | **NO** | **NO** | Stay idle / open candidate; no trade |
| **SHADOW_PENDING** | stored `sweep_event`, `pending_displacement_*`, OHLCV mid vs range | *(none)* | SHADOW_LEAK dir check; HTF mid alignment | (pending TTL already set); shadow fields read from state | →SWEEP→EXPANSION (`try_shadow_pending_to_expansion` **skips** body/ATR strength); →RANGE on leak | CRT SM only (+ fusion global iff ER) | Shadow resume **bypasses** displacement model gates | **NO** | **NO** | Restore prior displacement into EXPANSION |
| **SWEEP** | OHLCV; `sweep_event`; ATR | **FM-010** body_ratio; **FM-002** as wick_size/range for size gate | `move=\|c-o\|`; age=`idx−sweep.idx` | `atr_min_displacement`, `body_ratio_min`, `atr_multiplier_min`, `max_sweep_age_candles` | →DISPLACEMENT if all gates; →RANGE if age expired | CRT SM only (+ fusion global iff ER) | No external model on transition | **NO** | **NO** | Confirm impulse candle or kill setup |
| **DISPLACEMENT** | OHLCV; `displacement_candle`; dir; ATR | *(no FM cache yet)* | dir candle; extend beyond disp.close; dist vs ATR | `expansion_atr_min_distance`; reset keys | →EXPANSION; →RANGE (reset HTF/retrace/ext) | CRT SM only | No model | **NO** | **NO** | Lock expansion structure |
| **EXPANSION** | OHLCV; range; disp; ATR; expansion entry idx/ts | **FM-028** on retest attempt; **FM-010** on TTL would_trade label | adaptive retest depth; `min_depth=0.1·ATR` **hardcoded**; TTL age candles/hours; freshness | `retest_depth_max`, `retest_atr_depth_fraction`, `max_displacement_strength`, `max_expansion_age_candles/hours`, `body_ratio_min` (TTL label) | →RETEST (`try_expansion_to_retest` + cache FM-027/028); →EXPIRED (TTL); →RANGE (reset; HTF protected while EXPANSION) | CRT SM only; **on retest entry** caches features for later BitNet | BitNet **not** scored in EXPANSION | **NO** | **NO** | Wait retest / expire / reset |
| **RETEST** | retest candle; cached_features; ATR; EMAs; range | **FM-010, FM-027, FM-028** (cache); BitNet maps 027/028→legacy names | Soft conf C (body/mom/dist/disp); G RiskScore; `S=G^α·C^β`; shadow age decay; zone mid filter; session filter | soft-conf: `conf_*`, `weak_link_weight`, `confirmation_body_min`, `retest_*`, `ema_*`, `tier_*`, `soft_conf_max_candles`, `score_decay_lambda`, `use_bitnet`, `bitnet_main_threshold`, `shadow_*`, `allowed_sessions`, `session_windows`, `sizing_bands` (via executor), SL/TP mults | →EXECUTION if approved; →RANGE on fail/timeout/filters | **CRT** risk/soft-conf; **BitNet** only if `use_bitnet` (else disabled); Gaussian/ZoneGate/RR **not** on SM soft-conf | BitNet: **after CRT emission of cache**, config-gated; not state-registry | **NO** | **NO** | Approve/reject trade open |
| **EXECUTION** | active `Trade`; OHLC for SL/TP touch | *(none new)* | intrabar SL/TP ordering; close-only alt | `exit_model` / env override; TP/SL mults already on trade | →RESOLUTION on STOPPED/TP1/TP2 then reset RANGE | CRT ExecutionEngine only | No fusion models | **NO** | **NO** | Manage open trade |
| **RESOLUTION** | trade close event | *(none)* | immediate `reset_to_range` after resolution | — | →RANGE | CRT only | Terminal lifecycle | **NO** | **NO** | Clear setup; cycle end |
| **EXPIRED** | prior expansion context | *(none for stay)* | one-candle soft archive | (TTL already fired) | →RANGE only | CRT only | Label archive | **NO** | **NO** | Soft archive then RANGE |

**Global-every-candle (all states on spine):** ATR buffer, `update_emas`, `ResetLogic.should_reset` (except protected trades / EXPANSION+RETEST HTF hold).

**Owner / file:line per state (executable):**

| State | Enum | Orchestration branch | Key transition / detection owners |
|---|---|---|---|
| RANGE | `CRTState.RANGE` `:66` | `process_candle` `:2360` | `detect_sweep` `:1020`; `try_range_to_sweep` `:1157`; `try_range_to_shadow_pending` `:1169` |
| SHADOW_PENDING | `:67` | `:2424` | `try_shadow_pending_to_expansion` `:1182` |
| SWEEP | `:68` | `:2482` | `try_sweep_to_displacement` `:1208` |
| DISPLACEMENT | `:69` | `:2519` | `try_displacement_to_expansion` `:1257` |
| EXPANSION | `:70` | `:2524` | `try_expansion_to_retest` `:1309`; TTL →EXPIRED `:2606` |
| EXPIRED | `:71` | `:2613` | `reset_to_range` after soft archive |
| RETEST | `:72` | soft-conf branch `:2618` (`evaluating_soft_conf`; state is RETEST) | `approve_with_soft_conf` `:1702`; `try_retest_to_execution` `:1428` |
| EXECUTION | `:73` | active-trade path `:2329` (before SM switch) | `ExecutionEngine.update_trade`; →RESOLUTION `:2349` |
| RESOLUTION | `:74` | transitional only | `try_execution_to_resolution` `:1438` then immediate reset |

**Legal graph:** `VALID_TRANSITIONS` `:1076-1086`.

**EngineRunner (surface B) — not CRT-state-conditional:**

| Model | Active config | Invocation |
|---|---|---|
| CRT scorer | always if ER.run | **Global**, feature-based — **not** SM state |
| Gaussian heuristic | `gaussian_impl=heuristic` | **Global** |
| ZoneGate | always in ER | **Global** (uses `zone_cluster_threshold` name; not BitNet model) |
| RR geometry | always in ER | **Global** |
| RR fusion | `enabled:false` | **Disabled** |
| TradeNet | unwired | **Unwired** |
| BitNet (CRT hard-reject) | `use_bitnet:false` | **Disabled** on SM; ER does not call `bitnet_score` |

### 10.4 Machine-oriented dependency table

| State | Dependency Type | Dependency ID | Declaration Authority | Executable Producer | Runtime Consumer | Runtime Loaded Dynamically? | Decision Reachable? |
|---|---|---|---|---|---|---|---|
| * | STRUCTURAL_ENUM | `CRTState.*` | code `crt_engine_v2.py:65` + DESC `active_models` | code | `StateMachine` / `process_candle` | **NO** | YES |
| * | STRUCTURAL_GRAPH | `VALID_TRANSITIONS` | code `:1076` + DESC am | code | `_transition` | **NO** | YES |
| RANGE | RAW_OHLCV | high,low,close,open | n/a | candle stream | `detect_sweep`, range | **NO** | YES |
| RANGE | STATE_HISTORY | `active_range`, pending_disp | code EngineState | prior SM | RANGE branch `:2360` | **NO** | YES |
| RANGE | CONFIG | `pending_displacement_ttl_candles` | HOW `crt_engine` | CRTConfig | TTL countdown | **NO** | YES (shadow path) |
| RANGE | CRT_LOCAL | ATR, range H/L/EQ | code only | `RangeDetector` | SM | **NO** | YES |
| SWEEP | FM | FM-010 | WHAT ontology | `_cm.body_ratio` | `try_sweep_to_displacement` | **NO** | YES |
| SWEEP | FM | FM-002 | WHAT | `_cm.candle_range` as wick_size | size gate | **NO** | YES |
| SWEEP | CONFIG | `body_ratio_min`,`atr_min_displacement`,`atr_multiplier_min`,`max_sweep_age_candles` | HOW params/crt_engine | CRTConfig | displacement gates | **NO** | YES |
| DISPLACEMENT | CONFIG | `expansion_atr_min_distance` | HOW | CRTConfig | expansion guard | **NO** | YES |
| EXPANSION | FM | FM-028 | WHAT | `_dm.displacement_atr_ratio` | retest overextension gate | **NO** | YES (blocks retest) |
| EXPANSION | CONFIG | `retest_depth_max`,`retest_atr_depth_fraction`,`max_displacement_strength`,`max_expansion_age_*` | HOW | CRTConfig | retest/TTL | **NO** | YES |
| EXPANSION | CRT_LOCAL | `min_depth=0.1*atr` | **code only** (not HOW) | hardcoded `:1334` | retest entry | **NO** | YES |
| EXPANSION→RETEST | FM | FM-027, FM-028, FM-010 | WHAT | `_dm` / `_cm` | `cached_features` `:1379-1402` | **NO** | YES (downstream) |
| RETEST | FM | FM-027/028/010 | WHAT | cache | soft-conf + BitNet map | **NO** | YES |
| RETEST | CRT_LOCAL | RiskScore 0.35/0.25/0.20/0.20; soft-conf C; S=G^αC^β | code (+ partial HOW weights) | `UltronRiskEngine` | approve_with_soft_conf | **NO** | YES |
| RETEST | CONFIG | conf_*, tier_*, soft_conf_max_candles, use_bitnet, bitnet_main_threshold, shadow_*, allowed_sessions, … | HOW | CRTConfig | soft-conf / filters | **NO** | YES |
| RETEST | MODEL | BitNet `bitnet_score` | HOW enable + S14/thresholds elsewhere | `bitnet_inference` | soft-conf if use_bitnet | **NO** (static import) | **CONDITIONAL** (off on active) |
| RETEST | MODEL | Gaussian/ZoneGate/RR/TradeNet | fusion HOW | EngineRunner | **not** SM RETEST | n/a on SM | **NO on SM**; YES on ER path only |
| EXECUTION | CONFIG | `exit_model`, SL/TP mults | HOW | CRTConfig / trade | `update_trade` | **NO** | YES |
| EXPIRED | CONFIG | (TTL from EXPANSION) | HOW | already applied | reset | **NO** | YES (lifecycle) |
| * (ER) | MODEL | crt_scorer, gaussian, zone_gate, rr | HOW engine_runner/fusion | EngineRunner.run `:597+` | fusion/decision | **NO** | YES if gate-ON; **independent of CRTState** |
| * (ER) | MODEL | rr_fusion | HOW enabled=false | RRFusionLayer | skipped | **NO** | NO (disabled) |
| * (ER) | MODEL | TradeNet | F-005 unwired | — | none | **NO** | NO |

### 10.5 A–G answers

#### A. State→feature dependencies already implicit in code

Hard-coded in SM (not a resolver):

- **SWEEP→DISPLACEMENT:** FM-010, FM-002 (+ raw move, ATR, sweep age history)
- **EXPANSION→RETEST:** adaptive depth (range size + ATR + config), FM-028 ceiling, then **emit** FM-027/028/010 into `cached_features`
- **RETEST soft-conf:** consumes cache + CRT-local soft-conf features (EMA mom, Gaussian depth decay, f_disp)
- **RANGE/SWEEP geometry:** raw OHLCV + range history; no FM IDs required to *enter* RANGE/SWEEP

#### B. State→model dependencies already implicit in code

- **BitNet:** only in `approve_with_soft_conf` / dead `approve` when cache keys present; gated by `use_bitnet` (soft-conf path). Implicit **RETEST-phase** only, not a registry.
- **No** SM branch invokes Gaussian, ZoneGate, RR, TradeNet.
- **EngineRunner:** all four EXPECTED_ENGINES **global**, **regardless of CRTState**.

#### C. Duplicated in `active_models.yaml`

- State list + `VALID_TRANSITIONS` (DESC mirror of code)
- Per-detection `config_keys` / logic / file_line for range/sweep/displacement/expansion/retest/expired
- Lifecycle notes for shadow/execution/resolution
- Soft-conf / scoring formula prose
- **Stale:** `cached_features_at_retest` still lists `retest_depth` / `disp_strength` — code emits **FM-027/028** names (CH-002). That is **duplicate authority with wrong keys**.
- Defaults in am (`body_ratio_min: 0.70`) can **≠** production HOW (`params.body_ratio_min: 0.65`)

#### D. Absent from all configuration surfaces

- **No** machine-readable required FM ID sets per state
- **No** eligible model IDs per state
- **No** STATE→FEATURE / STATE→MODEL / FEATURE→MODEL resolvers
- Hardcoded `min_depth = 0.1 * atr` (not in production JSON)
- Hardcoded RiskScore component weights 0.35/0.25/0.20/0.20 (not HOW)
- Soft-conf CRT-local f_mom / f_disp (not FM IDs, not ontology)

#### E. MINIMUM splice (no fourth YAML)

**`active_models.yaml` (WHO only — ids/refs, no formulas, no numbers):**

- Required: **state identities** (already), **legal transitions** (already), **required_fm[]**, **config_key *names*** (not values), **eligible_model_ids[]**
- Fix stale cache feature names → FM-027/028
- Strip or mark non-authoritative numeric `defaults:` under detection blocks

**`market_ontology.yaml` (WHAT only):**

- **Minimum = empty for Phase-1 dynamic loading** if FM-001/002/010/027/028 already registered (they are)
- Optional: tag `used_by_states: [SWEEP, EXPANSION, RETEST]` as **descriptive** only — not a loader
- Do **not** move CRT-local soft-conf formulas into ontology without new FM ids + registry callables

**Production config (HOW only):**

- **Minimum = no new keys** for byte-identical Phase-1
- Later (optional, non-Phase-1): externalize hardcoded `0.1*ATR` min_depth and RiskScore weights if desired — **not required** to declare state contracts

#### F. Remove or convert to references (avoid duplicate authority)

| Declaration | Action |
|---|---|
| am `defaults:` numeric thresholds | **Remove or mark non-authoritative**; reference HOW keys only |
| am `cached_features` legacy names | **Replace** with FM-027/028/010 references to ontology |
| am formula strings that restate RiskScore/soft-conf math | Convert to **refs** to code symbols / FM ids; don’t re-author formulas |
| Duplicate `config_keys` with embedded default numbers | Keep **names**; drop numbers from WHO |
| Do **not** remove VALID_TRANSITIONS from code | am stays DESC mirror or codegen later |

#### G. Smallest Phase-1 dynamic-loading implementation (behavior-preserving)

1. **Add closed Python registries** (code, not new YAML):
   - `STATE_REQUIRED_FM: dict[CRTState, tuple[str, ...]]`
   - `STATE_ELIGIBLE_MODELS: dict[CRTState, tuple[str, ...]]`
   - `STATE_CONFIG_KEYS: dict[CRTState, tuple[str, ...]]`
2. **Source the tables** by reading **only** additive fields from `active_models.yaml` (or start code-hardcoded with am DESC mirror for parity).
3. **Loaders:** resolve FM id → existing `FORMULA_REGISTRY` callable; resolve config key → existing `CRTConfig` / prod section; resolve model id → existing constructed engines (**no eval**).
4. **Call sites:** after existing transitions, **assert/log** contract satisfaction — **do not change branch conditions** in Phase-1.
5. **BitNet:** keep `if self.config.use_bitnet` gate; eligibility list may include `bitnet` for RETEST but loader respects HOW enable flag.
6. **Parity:** golden process_candle / backtest ledger **byte-identical** (assertions never fail-open into new rejects).

Phase-1 deliberately **does not** switch control flow to “load model because state said so” — it **declares** what code already does, then later phases may switch dispatch.

### 10.6 End tokens

```
STATE_FEATURE_DEPENDENCIES_MAPPED = YES
STATE_MODEL_DEPENDENCIES_MAPPED = YES
STATE_TO_FEATURE_RESOLVER_EXISTS = NO
STATE_TO_MODEL_RESOLVER_EXISTS = NO
FEATURE_TO_MODEL_RESOLVER_EXISTS = NO

MINIMUM_ACTIVE_MODELS_SPLICE = state_contracts{required_fm[],eligible_models[],config_key_names[]} + fix cache names to FM-027/028/010 + strip numeric defaults from WHO
MINIMUM_MARKET_ONTOLOGY_SPLICE = none required for Phase-1 (FM-001/002/010/027/028 already present); optional used_by_states DESC only
MINIMUM_PRODUCTION_CONFIG_SPLICE = none for byte-identical Phase-1

DUPLICATE_DECLARATIONS_TO_REMOVE_OR_REFERENCE = active_models numeric defaults; stale retest_depth/disp_strength cache names; re-authored formula strings → FM/code refs
PHASE_1_DYNAMIC_LOADING_SCOPE = closed code registries + am DESC contracts + assert-only wiring; no control-flow change; no new YAML; no formula/threshold move
BYTE_IDENTICAL_PARITY_REQUIREMENT = process_candle + gate-ON/OFF ledgers unchanged; contract checks non-mutating
UNRESOLVED_GAPS = hardcoded 0.1*ATR min_depth & RiskScore weights lack HOW keys; soft-conf f_mom/f_disp lack FM ids; fusion path CRT scorer ≠ SM (no state coupling); BitNet dual threshold surfaces; approve() BitNet path vs soft-conf use_bitnet inconsistency for dead path
```

---

## 11. Phase-1 State Contract Loading

| Field | Value |
|---|---|
| Implementation status | **COMPLETE** (validation-only; no control-flow / dispatch change) |
| Certification status | **COMPLETE** (2026-07-11 — isolated PRE/POST ledger parity after Gaussian interface fix) |
| Date (UTC) | 2026-07-11 |
| Authority | WHO declarations → typed runtime objects; Python remains executable SM/HOW/WHAT authority |

### 11.1 Schema added to `active_models.yaml`

Under `crt.runtime`:

- `state_contract_schema_version: "1.0"`
- `state_contracts:` — one block per CRT state with **only**:
  - `required_fm: [FM-…]`
  - `config_keys: [CRTConfig field names]`
  - `eligible_models: [active_models model ids]`

No numeric thresholds, no formulas, no expressions.

**Census-derived contents (§10):**

| State | required_fm | eligible_models (semantic only) |
|---|---|---|
| RANGE | [] | [] |
| SHADOW_PENDING | [] | [] |
| SWEEP | FM-002, FM-010 | [] |
| DISPLACEMENT | [] | [] |
| EXPANSION | FM-010, FM-028 | [] |
| RETEST | FM-010, FM-027, FM-028 | bitnet |
| EXECUTION | [] | [] |
| RESOLUTION | [] | [] |
| EXPIRED | [] | [] |

Also fixed `cached_features_at_retest` authoritative names → `displacement_retrace` (FM-027) / `body_ratio` (FM-010) / `displacement_atr_ratio` (FM-028).

### 11.2 Paths

| Artifact | Path |
|---|---|
| Schema (WHO) | `active_models.yaml` → `crt.runtime.state_contracts` |
| Loader | `src/config_layer/state_contract_loader.py` |
| Runtime types | `src/config_layer/state_contract.py` (`StateContract`, `StateContractBundle`) |
| CRT wiring | `CRTEngine.__init__` loads once; `get_state_contract()` inspects |
| Tests | `tests/test_state_contracts.py` |

### 11.3 Validation chain

1. Parse YAML `state_contracts` (fail-closed missing fields / unknown fields / bad types).
2. **State-set parity:** contract keys == `CRTState` names.
3. **Transition-graph parity:** `valid_transitions` == `VALID_TRANSITIONS` (declaration only; Python remains executable graph).
4. **FM resolution:** each `required_fm` exists in market ontology; primitive/derived impl in `FORMULA_REGISTRY`; compositions resolve numerator/denominator primitives; lifecycle ∈ {registered, parity_verified, consumable}.
5. **Config keys:** each key is a `CRTConfig` field (`CONFIG_KEY_EXISTS` or fail `CONFIG_KEY_MISSING`).
6. **Model IDs:** each `eligible_models` entry is a top-level model block in `active_models.yaml` (not meta/philosophy/feature_lineage). **No dispatch.**
7. Emit immutable `StateContractBundle` (MappingProxyType + frozen dataclasses). **No** parallel `STATE_REQUIRED_FM` constants.

### 11.4 Results (implementation)

| Check | Result |
|---|---|
| State set parity | **PASS** (9/9) |
| Transition graph parity | **PASS** |
| FM resolution | **PASS** (FM-002, FM-010, FM-027, FM-028) |
| Config-key resolution | **PASS** (all declared keys on CRTConfig) |
| Model-ID resolution | **PASS** (only `bitnet` on RETEST) |
| Negative tests | **PASS** (missing/extra state, unknown FM/config/model, graph mismatch, numeric/formula injection, schema version, …) |
| Unit suite | **PASS** (`tests/test_state_contracts.py` + `tests/test_crt_gaussian_scorer_direction_compat.py`) |
| process_candle dual-run fingerprint | **PASS** (identical action stream) |

### 11.4b Certification — Gaussian `direction` blocker + ledger parity

**Root cause (executable):**

| Item | Evidence |
|---|---|
| Caller | `BacktestRunner.run` `src/runtime/backtest_v2.py:2071-2072` always calls `self._scorer.compute(..., direction=_p5_dir)` |
| Duck-type (calibrated) | `CRTCalibratedScorer.compute(..., direction: str = "long")` `:1587-1588` → delegates |
| Duck-type (ML/heuristic engines) | `ml_gaussian_engine.py:123`, `heuristic_gaussian_engine.py:271` accept `direction` |
| Broken no-op | local `CRTGaussianScorer.compute(self, features, candle_idx)` **without** `direction` (`--scorer static`) |
| Failure class | **API_DRIFT / duck-type mismatch** (stale callee signature vs call-site + sibling scorers) |
| Pre-existing? | **YES** — same commit `b34d6a8` introduced call site + incomplete no-op signature (git show `b48d4d9:src/runtime/backtest_v2.py`); not introduced by Phase-1 |

**Minimal fix:** add `direction: str = "long"` to no-op `CRTGaussianScorer.compute` (ignored; still returns `None`). No scoring math change. Regression: `tests/test_crt_gaussian_scorer_direction_compat.py`.

**Isolated comparison methodology (correct PRE vs POST):**

| State | Worktree | Base commit | Delta |
|---|---|---|---|
| A PRE-PHASE-1 + fix | `D:\Tradelatest-pre-p1-cert` | `b48d4d9` | Gaussian no-op `direction` only (+ shared untracked `ohlcv_schema.py` needed to import HEAD backtest) |
| B POST-PHASE-1 + fix | `D:\Tradelatest-post-p1-cert` | `b48d4d9` | A + Phase-1 contracts/loader/CRT wiring only |

Command (identical both sides):

```text
py -3.12 src/runtime/backtest_v2.py --csv data/BNBUSDT_M15.csv --instrument BNBUSDT --output results/cert_bnb --scorer static
py -3.12 src/runtime/backtest_v2.py --csv data/XAUUSD_M15.csv --instrument XAUUSD --output results/cert_xau --scorer static
```

Config: `ACTIVE_VERSION=v2_multi_2026_04`. Corpus: junctioned `data/` from main.

**BNBUSDT parity (A vs B):**

| Artifact | Equal? | sha256[:16] |
|---|---|---|
| `BNBUSDT_trades.csv` | **YES** | `7b4e8e2db3801ea6` |
| `BNBUSDT_summary.json` | **YES** | `845a6d22f43332a6` |
| `BNBUSDT_report.txt` | **YES** | `0d84a4b466f13ac5` |

Headline: n_trades=11, WR=27.3%, PnL(net)=-4.25R, MaxDD=5.6% (both).

**XAUUSD parity (A vs B):**

| Artifact | Equal? | sha256[:16] |
|---|---|---|
| `XAUUSD_trades.csv` | **YES** | `3714c94e9ca6b8a3` |
| `XAUUSD_summary.json` | **YES** | `9d17b3161d3fee2b` |
| `XAUUSD_report.txt` | **YES** | `bebe730658b74b35` |

Headline: n_trades=1, WR=0%, PnL(net)=-0.04R (both).

**STATE_CONTRACT_BEHAVIOR_PARITY = PASS**

### 11.5 Explicit non-effects (Phase-1)

- Does **not** replace `_cm` / `_dm` direct calls.
- Does **not** dynamically execute `required_fm`.
- Does **not** state-dispatch Gaussian/ZoneGate/RR/BitNet/TradeNet.
- Does **not** couple EngineRunner to `CRTState`.
- Does **not** enable BitNet (`use_bitnet` remains HOW).

### 11.6 Deferred gaps (not Phase-1)

- Hardcoded `min_depth = 0.1 * ATR`
- Hardcoded RiskScore weights 0.35/0.25/0.20/0.20
- Soft-conf CRT-local f_mom / f_disp (no FM ids)
- True FM resolution through FORMULA_REGISTRY at call sites (Phase-2)
- State-aware model dispatch / shadow vs global EngineRunner (Phase-3; architecture decision A vs B open)
- WHO numeric defaults cleanup (Phase-4)
- Neutral market-state abstraction vs CRTState as model gate

### 11.7 Highest-leverage next step

**Phase-2 Option A implemented** — see §12 and [`phase_2_fm_resolution_design.md`](phase_2_fm_resolution_design.md). **Do not** start state→model dispatch or dynamic topology until CRTState-vs-neutral-state architecture is decided.

---

## 12. Phase-2 FM Resolution (Option A)

| Field | Value |
|---|---|
| Implementation status | **COMPLETE** (contract-aware resolve; no auto-run required_fm; no control-flow change) |
| Date (UTC) | 2026-07-11 |
| Plan export | [`docs/implementation_plan/phase1-state-contract-review-phase2-fm-resolution.md`](../implementation_plan/phase1-state-contract-review-phase2-fm-resolution.md) |
| Design | [`phase_2_fm_resolution_design.md`](phase_2_fm_resolution_design.md) Option A |

### 12.1 Paths

| Artifact | Path |
|---|---|
| Resolver | `src/features/fm_resolve.py` |
| CRT wiring | `crt_engine_v2.py` — `Candle.wick_size` (FM-002), `Candle.body_ratio` (FM-010), retest FM-027 emit, FM-028 guard+emit |
| Loader reuse | `state_contract_loader._resolve_fm` → `features.fm_resolve.resolve_fm` |
| Tests | `tests/test_fm_resolution_phase2.py` |

### 12.2 Authority rules held

- WHO declares `required_fm` only; never schedules execution.
- WHAT owns formula binding via ontology + FORMULA_REGISTRY / composition.
- Python call sites remain the only place that request computation.
- No `eval`; no fourth YAML; no topology/model dispatch.

### 12.3 Results

| Check | Result |
|---|---|
| FM-002/027/028 registry identity (`is`) | **PASS** (candle_math / derived_math) |
| FM-010 composition float parity vs `candle_math.body_ratio` | **PASS** |
| Contract membership assert (test surface) | **PASS** |
| process_candle dual-run fingerprint | **PASS** (identity) |
| Production config / ACTIVE_VERSION | **untouched** (hash-neutral) |

### 12.3b XAUUSD static ledger re-cert (2026-07-11)

**Command** (identical to §11.4b form):

```text
py -3.12 src/runtime/backtest_v2.py --csv data/XAUUSD_M15.csv --instrument XAUUSD --output results/cert_xau_phase2 --scorer static
```

Config: `ACTIVE_VERSION=v2_multi_2026_04`. Loader rewrote path to Phase-1 frozen candidate `data/mt5/XAUUSD_M15.csv` (47,275 candles).

**Headline (economic):** n_trades=1, WR=0.0%, PnL(net)=−0.04R (`avg_rr_net`/`total_pnl_rr_net`=−0.0383) — matches §11.4b Phase-1 cert prose.

**Primary parity (same-HEAD pre-Phase-2 baseline):**

Compared to `results/crt_xauusd_trace_run/baseline/run_20260711_182138_XAUUSD` (same branch tip **before** Phase-2 FM resolve wiring; same corpus/config/scorer):

| Artifact | Equal? | sha256[:16] |
|---|---|---|
| `XAUUSD_trades.csv` | **YES** | `c4a10db1206d6310` |
| `XAUUSD_summary.json` | **YES** | `06429f7bf18bfadb` |
| `XAUUSD_report.txt` | **YES** | `db51bf2a3b36e6ca` |

**PHASE2_XAU_STATIC_LEDGER_PARITY = PASS** (byte-identical trades/summary/report).

**Note on §11.4b absolute hashes** (`trades=3714c94e…`, `summary=9d17b316…`, `report=bebe7306…`): those pinned **isolated worktrees on base `b48d4d9` + Gaussian fix ± Phase-1 only**, not current HEAD. Current tip includes later feature-path work (e.g. FC1-A causal structure) so absolute hashes are **not expected to equal** those worktree pins. Economic headline remains aligned; same-HEAD PRE/POST is the valid Phase-2 gate.

**Phase-Topology:** still deferred — implement only on explicit user approval.

### 12.4 Explicit non-effects (Phase-2)

- Does **not** auto-execute `required_fm` lists.
- Does **not** load transitions as executable graph (Python remains authority).
- Does **not** dispatch models from `eligible_models`.
- Does **not** strip descriptive `detection.defaults` (Phase-6 cleanup).

### 12.5 Deferred (post Phase-2; Topology now §13)

- Detector/guard ID closed registries.
- Soft→hard contract membership on hot path.
- Residual direct `_cm.body_ratio` at TTL soft-label site (`crt_engine_v2` ~2585) — out of Phase-2 slice.
- Dropping code↔YAML transition parity (YAML-only authority without seed) — not in Phase-Topology slice.

---

## 13. Phase-Topology (dynamic state identity + legal transition graph)

| Field | Value |
|---|---|
| Implementation status | **COMPLETE** (WHO-loaded graph drives `StateMachine._transition`; guards unchanged) |
| Date (UTC) | 2026-07-11 |
| User approval | Explicit ("Approved" after XAU Phase-2 re-cert) |
| Plan | [`docs/implementation_plan/phase1-state-contract-review-phase2-fm-resolution.md`](../implementation_plan/phase1-state-contract-review-phase2-fm-resolution.md) (Phase-Topology) |

### 13.1 Design

```text
active_models.yaml  valid_transitions + state_contracts
        ↓  Phase-1 loader (parity vs CRTState / VALID_TRANSITIONS seed)
StateContractBundle.transitions
        ↓  state_topology.build_runtime_transition_graph_from_bundle
Mapping[CRTState, tuple[CRTState, ...]]
        ↓  injected into StateMachine.valid_transitions
StateMachine._transition  (instance graph authority)
```

| Layer | Role after Phase-Topology |
|---|---|
| WHO `valid_transitions` | Source of the **runtime** legal graph (via loader + topology builder) |
| `CRTState` enum | Structural state **identity** set (not dynamically invented) |
| Module `VALID_TRANSITIONS` | Seed + loader parity baseline; legacy SM fallback |
| Python `try_*` guards | Unchanged (still decide *when* to request a transition) |

### 13.2 Paths

| Artifact | Path |
|---|---|
| Topology builder | `src/config_layer/state_topology.py` |
| SM wiring | `StateMachine.__init__(valid_transitions=…)` / `_transition` uses instance graph |
| CRT wiring | `CRTEngine` loads contracts → builds graph → injects SM |
| Tests | `tests/test_state_topology_phase.py` |

### 13.3 Results

| Check | Result |
|---|---|
| Graph from production bundle ≡ module seed | **PASS** |
| CRTEngine.sm.valid_transitions is WHO-built graph | **PASS** |
| Restricted inject blocks module-legal edge | **PASS** (dynamism proof) |
| Unknown / incomplete state ids fail-closed | **PASS** |
| process_candle dual-run fingerprint | **PASS** |
| Unit suite (topology + contracts + FM + invariants) | **PASS** (64) |
| XAUUSD static ledger vs Phase-2 cert (`results/cert_xau_phase2`) | **PASS** (byte-identical trades/summary/report; sha `c4a10db1` / `06429f7b` / `db51bf2a`) |

### 13.4 Explicit non-effects

- Does **not** change detector/guard algorithms.
- Does **not** allow inventing states outside `CRTState`.
- Does **not** drop YAML↔code edge parity at load (seed still required).
- Does **not** dispatch models / execute formulas from YAML.
- force-reset (`reset_to_range`) still bypasses the graph by design.

### 13.5 Deferred

- YAML-only topology without code seed parity.
- Detector/guard ID registries (next conversation phase).
- Model dispatch from `eligible_models`.

---

## 14. Three-Authority Declaration Surplus Census (pointer)

| Field | Value |
|---|---|
| Status | **CENSUS_ONLY** (2026-07-11) — observational; no runtime mutation |
| Human | [`three_authority_declaration_surplus_census-2026-07-11.md`](three_authority_declaration_surplus_census-2026-07-11.md) |
| Machine | [`three_authority_declaration_surplus_census-2026-07-11.json`](three_authority_declaration_surplus_census-2026-07-11.json) |
| Scanner | `scripts/governance/three_authority_surplus_census.py` |
| Guard | `tests/test_three_authority_surplus_census.py` |

Headline: 9 detection defaults + 48 WHO threshold entries + 6 active-HOW≠WHO-default drifts + 17 formula-prose paths; clean `state_contracts` positive control; P1 candidates IC-001/IC-002/IC-008. **No fourth YAML.**

---

*End of matrix. This document is the single Sources + matrix home for the configuration-authority consolidation audit. It does not reverse findings and does not grant enablement authority.*
