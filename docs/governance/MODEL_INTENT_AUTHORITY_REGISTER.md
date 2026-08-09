# Model Intent Authority Register (MIAR)

**Status:** AUTHORITATIVE for model *intent* (why each component exists, boundaries, relations)  
**Created:** 2026-07-28 · **Updated:** 2026-07-28 (stage separation + locked vocabulary)  
**Machine-readable twin:** [`miar_registry.json`](miar_registry.json)  
**Enforcement (floor):** `tests/test_miar_registry.py`  

---

## 0. Authority hierarchy (non-optional)

| Rank | Layer | Authority for | Must not override |
|---:|---|---|---|
| **1** | **Market Ontology** (`configs/formulas/market_ontology.yaml` + registry) | *What* market concepts / formulas mean | — |
| **2** | **Feature Pipeline** (`feature_pipeline` / `CANONICAL_FEATURES`) | *How* OHLCV → canonical vector; dim/order | Ontology meaning of named features |
| **3** | **MIAR (this document + `miar_registry.json`)** | *Why* each model exists; ownership of questions; non-goals | Ontology math; canonical schema |
| **4** | **Model implementations** | Executable algorithms | Intent contracts (code follows MIAR) |
| **5** | **Backtest / Research** | Whether intent is achieved (ΔG001, falsification) | Semantics of models or ontology |

**Conflict rules**

1. Ontology wins on formula/meaning of market quantities.  
2. Feature schema wins on vector layout and feature *names*.  
3. **MIAR wins on model purpose, boundaries, and “who owns which market question.”**  
4. Implementation that contradicts MIAR is **Semantic Drift** (🟡), not a silent redefinition of intent.  
5. Research findings may **falsify** a hypothesis (update MIAR `falsification` / status) but may not invent a second intent for the same engine without a MIAR edit.  
6. `active_models.yaml` remains **runtime/evidence mirror** for models; on *intent* conflict with MIAR, **MIAR wins** and the yaml is updated the same turn (DOC_DRIFT).  
7. Topic [`docs/topics/model-intent-and-feature-ownership.md`](../topics/model-intent-and-feature-ownership.md) owns **feature×model ownership matrices**; MIAR owns **engine intent contracts**. Cross-link; do not duplicate full matrices here.

**Grants no promote authority.** Alignment 🟢 does not equal economic authority (§6.5 Authority Ladder).

---

## 0.1 Two families (non-optional separation)

| Family | Answers | May decide to trade? | Stage(s) |
|---|---|---|---|
| **Market-understanding models** | *What is the market?* | **Never** | Stage 1 |
| **Opportunity-understanding models** | *If I trade here, what should I expect?* | No (predict only) | Stage 2 |
| **Safety models** | *Is this unsafe?* | **Veto only** (never positive score contribution as purpose) | Stage 3 |
| **Decision models** | *Should we approve?* | Yes (approval only) | Stage 4 |
| **Execution models** | *How do we execute an approved trade?* | After approval only | Stage 5 |
| **Substrate** | Meaning + representation | No | Stage 0 |
| **Measurement / research** | Did intents achieve objectives? | No (must not redefine semantics) | Stage M |

**Hard rule:** A Stage-1 model that influences entry *only* via fusion must still declare non-goal **“never decide whether to trade.”** Fusion (Stage 4) is the sole owner of trade approval among scoring engines; Ultron/planner own economic execution gates after approval.

---

## 0.2 Canonical pipeline sequence (decision spine)

### Stage 0 — Substrate (not models)

| Order | Component | Canonical question |
|---:|---|---|
| 0a | Market Ontology | What market concepts exist? |
| 0b | Feature Pipeline | How is OHLCV mapped to the canonical representation? |

### Stage 1 — Market understanding (*What is the market?*)

Descriptive only. **Must never decide whether to trade.**

| Order | Model | Canonical question (locked) |
|---:|---|---|
| 1 | **CRT** | What structural state is the market in? |
| 2 | **Gaussian** | How statistically **conformant** is this state to previously observed states? |
| 3 | **ZoneGate** | Is this state occurring in a structurally valid location (zone neighbourhood)? |
| 4 | **RR Engine** | How strong is the candle **commitment** and geometric quality? |
| 5 | **Regime** | What market regime currently exists? |

Supporting dual-engine voters (trap / breakout) are Stage-1 adjuncts: they describe pattern pressure, not approval.

### Stage 2 — Opportunity understanding (*If I trade here, what should I expect?*)

First **predictive** models. Still must not alone approve execution.

| Order | Model | Canonical question (locked) |
|---:|---|---|
| 6 | **TradeNet** | What **expected trading outcomes** (discrete milestones) follow from this semantic market state? |
| 7 | **RR Trained** | What **learned reward behavior** is associated with this semantic state (parametric / historically trained), distinct from deterministic candle commitment? |

### Stage 3 — Safety

| Order | Model | Canonical question (locked) |
|---:|---|---|
| 8 | **BitNet** | Should this opportunity be **rejected** because the semantic state is unsafe? |

BitNet is a **veto**, not a positive fusion contribution by purpose.

### Stage 4 — Decision

| Order | Model | Canonical question (locked) |
|---:|---|---|
| 9 | **Fusion + DecisionEngine** (`decision_fusion`) | Given all evidence, should this trade be **approved** (resolve conflicts into one approval decision)? |

Fusion must **not** rediscover market structure; it only aggregates and adjudicates upstream evidence.

### Stage 5 — Execution

| Order | Model | Canonical question (locked) |
|---:|---|---|
| 10 | **Execution Planner** (+ execution intent lifecycle) | How should the **already approved** trade be executed (SL/TP/TTL/size intent)? |

### Stage M — Measurement (parallel, not in hot path)

| Component | Canonical question |
|---|---|
| Qualification Gate | Does a candidate edge survive pre-registered research gates? |
| Backtest Engine | What ledger does history produce under declared exits/costs? |
| Research / Hypothesis Runner | Do pre-registered hypotheses survive honest measurement? |

---

## 0.3 Locked vocabulary (semantic drift stop-list)

Every MIAR entry and implementation doc **must** use these meanings. Do not invent synonyms without a MIAR edit.

| Term | Canonical meaning |
|---|---|
| **Structure** | Current market organization inferred from OHLCV (CRT owns classification of structural *state*). |
| **Regime** | Persistent market behavior over a longer horizon than a single structure event. |
| **Familiarity / Conformity** | Statistical conformity of the current state to previously observed states (Gaussian). *Not* “likely profitable.” |
| **Similarity** | Distance between semantic market states (feature space). |
| **Zone** | Structural price / feature neighbourhood — **not** profitability. |
| **Commitment** | Strength of directional candle behavior (RR Engine polarity). |
| **Quality** | **Always qualified** (structural quality, execution quality, trade-outcome quality). Bare “quality” is forbidden in intents. |
| **Probability** | A **calibrated** chance an event occurs. Implies calibration; not an arbitrary score. |
| **Score** | Ordinal / utility value **without** probabilistic interpretation. |
| **Confidence** | Reliability of the **model’s own output**, not P(trade success). |
| **Expectancy** | Expected future outcome under the model’s assumptions (explicit units when used). |
| **Pattern** | A defined semantic configuration of OHLCV-derived features. |

**Never interchangeable:** Probability ≠ Score ≠ Confidence.

| Wrong | Right |
|---|---|
| Calling Gaussian output a probability of win | Call it a **score** (kernel conformity) unless calibrated as probability |
| Calling BitNet score “confidence of success” | Call it **acceptability score** / veto reliability |
| Calling RR polarity “reward:risk” | Call it **commitment** / geometric score |
| Calling TradeNet “quality” bare | Call **expected trading outcomes** / milestone probabilities (if calibrated) or scores (if not) |

---

## 0.4 Alignment workflow (one model at a time)

1. **Freeze** the semantic contract (this register + vocabulary) for **one** model.  
2. Reach complete agreement on intent, non-goals, stage family.  
3. **Audit** implementation against that contract (code-grounded).  
4. **Resolve** drift (code, consumer, or intent — never silent).  
5. **Lock** alignment status and move to the next model.

**Start with CRT** — foundation for structural reasoning; highest leverage for downstream contracts.

Order after CRT (recommended): Gaussian → ZoneGate → RR Engine → Regime → TradeNet → RR Trained → BitNet → Decision Fusion → Execution Planner → Measurement layers.

---

## 1. Alignment verdict vocabulary (exactly one per entry)

| Token | Name | Meaning |
|---|---|---|
| 🟢 | **ALIGNED** | Intent and executable path match; consumers use outputs as declared (or explicitly offline-only). |
| 🟡 | **SEMANTIC_DRIFT** | Implementation exists but diverges from declared intent or consumers reinterpret outputs. |
| 🔴 | **INTENT_MISSING** | Executable code exists without authoritative MIAR intent (should not remain after registration). |
| ⚫ | **DESIGN_ONLY** | Architecture/name documented; no (or no complete) executable path for the declared intent. |

**Implementation status:** `EXECUTABLE` · `PARTIAL` · `DESIGN_ONLY`

---

## 2. Contract schema (deterministic overlap detection)

Every MIAR entry **must** fill:

| Field | Purpose |
|---|---|
| `id` | Stable token (e.g. `crt`) |
| `stage` | `substrate` · `market_understanding` · `opportunity_understanding` · `safety` · `decision` · `execution` · `measurement` |
| `stage_order` | Integer order within the canonical sequence (null for substrate adjuncts as noted) |
| `intent` | **Single** market question answered (locked wording preferred) |
| `hypothesis` | Assumption under test |
| `inputs` | Evidence consumed (features / OHLCV / engine scores) |
| `outputs` | Produced artifacts |
| `semantic_meaning` | What the output *is* |
| `consumer` | Which component(s) read it |
| `authority_boundary` | Decisions it may influence |
| `explicit_non_goals` | What it must **never** do (anti-creep) |
| `dependencies` | Upstream MIAR ids / ontology / pipeline |
| `falsification` | Evidence that would invalidate purpose |
| `implementation_status` | EXECUTABLE / PARTIAL / DESIGN_ONLY |
| `alignment` | 🟢 / 🟡 / 🔴 / ⚫ |
| `primary_code` | file:symbol anchors |
| `notes` | Evidence, F-ids, caveats |

**Overlap rule (deterministic):** two entries conflict if they share the same **`intent` string** (normalized: lowercase, collapse whitespace) **and** both claim `authority_boundary` that includes a decision-affecting role, unless one lists the other under `dependencies` as the sole owner and itself as secondary consumer only. The market-question matrix (§4) must show **exactly one Owner** per row.

---

## 3. Register (17 engines, in sequence)

### 3.1 Market Ontology

| Field | Content |
|---|---|
| **id** | `market_ontology` |
| **intent** | What market concepts and formulas exist, with lineage? |
| **hypothesis** | A single semantic graph prevents formula re-derivation and silent meaning drift. |
| **inputs** | Research/code discoveries, governance adjudication |
| **outputs** | Canonical nodes (FM-*, states, geometries) in ontology YAML + registry |
| **semantic_meaning** | Permanent semantic authority for market quantities |
| **consumer** | Feature registry, CRT, all feature producers, MIAR (for concept names) |
| **authority_boundary** | Definition of *meaning* of features/states/formulas — not trade approve/reject |
| **explicit_non_goals** | Never compute live scores; never promote configs; never own fusion weights |
| **dependencies** | none (tier 1) |
| **falsification** | Two contradictory formulas for the same FM-id in production without adjudication |
| **implementation_status** | EXECUTABLE (`configs/formulas/market_ontology.yaml`, `src/features/registry/`) |
| **alignment** | 🟢 |
| **primary_code** | `configs/formulas/market_ontology.yaml` · `src/features/registry/` |

### 3.2 Feature Pipeline

| Field | Content |
|---|---|
| **id** | `feature_pipeline` |
| **intent** | How is OHLCV transformed into the single canonical feature representation? |
| **hypothesis** | One ordered vector (schema v4, dim=39) keeps all models comparable and PIT-governable. |
| **inputs** | OHLCV bars; `feature_pipeline` config periods |
| **outputs** | `CANONICAL_FEATURES` dict / vector; SCHEMA_HASH |
| **semantic_meaning** | Point-in-time (target) feature state of the market at bar *t* |
| **consumer** | All engines that read features; ZoneGate; TradeNet; training datasets |
| **authority_boundary** | Layout, names, compute path — not *why* a model uses a subset |
| **explicit_non_goals** | Never decide trades; never redefine FM identities (ontology); never own model intent |
| **dependencies** | `market_ontology` |
| **falsification** | Dual live vectors with different dim/order without schema version bump |
| **implementation_status** | EXECUTABLE |
| **alignment** | 🟢 (dim 39 live; residual PIT issues documented F-051 — quality, not intent mismatch) |
| **primary_code** | `src/features/feature_pipeline.py` · `src/features/feature_schema.py` |

### 3.3 CRT Engine (structure)

| Field | Content |
|---|---|
| **id** | `crt` |
| **stage** | `market_understanding` · order **1** |
| **intent** | What structural state is the market in? |
| **hypothesis** | Sweep→displacement→expansion→retest sequences mark actionable structure. |
| **inputs** | Raw OHLCV (+ internal EMA/ATR); fusion path also uses structure features |
| **outputs** | FSM state/actions; fusion `structure_rule_score` (separate path — see notes) |
| **semantic_meaning** | Structural classification / structure-rule score — **not** p(win) |
| **consumer** | Backtest/live spine TRADE_OPENED; fusion slot `crt` (score path); BitNet at approve if enabled |
| **authority_boundary** | Structure detection and structure-rule scoring; may open structural path to risk |
| **explicit_non_goals** | **Never** estimate win probability; **never** own economic RR; **never** classify statistical neighbourhood (ZoneGate); **never** decide whether to trade (Stage-1 hard rule §0 · added 2026-07-28) |
| **dependencies** | `feature_pipeline` (score path), `market_ontology` geometries |
| **falsification** | Structure completion adds no path asymmetry (e.g. F-026-class) → purpose as *edge source* weakened; structure *description* may remain |
| **implementation_status** | EXECUTABLE (dual surfaces: FSM + fusion scorer) |
| **alignment** | 🟡 — dual math paths (FSM vs `compute_scores` retest); score ≠ state |
| **primary_code** | `src/config_layer/crt_engine_v2.py` · `src/engines/crt_engine.py` · `src/engines/scoring_engine.py` |
| **notes** | MIAR treats FSM + fusion scorer as one *intent owner* with two outputs; do not invent a second owner. Freeze + code audit (steps 1–3): [`crt_intent_contract.md`](crt_intent_contract.md) — primary drift = spine `crt_engine_v2.py` self-approves/executes; alignment stays 🟡 pending step 4. |

### 3.4 Gaussian Engine

| Field | Content |
|---|---|
| **id** | `gaussian` |
| **stage** | `market_understanding` · order **2** |
| **intent** | How statistically **conformant** is this market state to previously observed market states (EMA/momentum axis)? |
| **hypothesis** | A kernel over EMA-spread + momentum measures conformity to a reference locus; design once aimed at success-matching — **must not** be read as calibrated win probability without recalibration. |
| **inputs** | `ema_fast`, `ema_slow`, `momentum_score` (live heuristic) |
| **outputs** | Conformity **score** ∈ [0,1] (`ema_momentum_kernel_score`) |
| **semantic_meaning** | Statistical **conformity score** (live: often near-constant, F-060) — **not** a probability, not entry permission |
| **consumer** | Fusion (`weight_gaussian`); misused as DecisionEngine `p_win` (**forbidden reinterpretation**) |
| **authority_boundary** | Stage-1 descriptive vote into fusion only |
| **explicit_non_goals** | **Never** decide whether to trade; **never** determine entries alone; **never** classify CRT structure; **never** claim **probability** without calibration |
| **dependencies** | `feature_pipeline` |
| **falsification** | Kernel non-pivotal / information-inert (F-060 class) → no fusion authority |
| **implementation_status** | EXECUTABLE (heuristic live; ML path partial/config-gated) |
| **alignment** | 🟡 — design “historically profitable” vs kernel symmetry + p_win consumer drift |
| **primary_code** | `src/engines/heuristic_gaussian_engine.py` · optional `ml_gaussian_engine.py` |

### 3.5 ZoneGate

| Field | Content |
|---|---|
| **id** | `zone_gate` |
| **stage** | `market_understanding` · order **3** |
| **intent** | Is this state occurring in a structurally valid location (zone neighbourhood)? |
| **hypothesis** | Feature-space zones encode past good/bad regions. |
| **inputs** | Full canonical vector + zone registry |
| **outputs** | `neighbourhood_quality_score`, pass/fail |
| **semantic_meaning** | Geometric neighbourhood quality — not structure FSM state |
| **consumer** | Fusion; DecisionEngine zone validity |
| **authority_boundary** | Soft/hard gate vote; F-036 non-pivotal on active fusion |
| **explicit_non_goals** | **Never** run CRT transitions; **never** estimate TP probabilities; **never** set SL/TP |
| **dependencies** | `feature_pipeline` |
| **falsification** | ΔG001≡0 / no honest zone edge (F-036, F-041B) |
| **implementation_status** | EXECUTABLE |
| **alignment** | 🟡 — intent ok; economic non-pivotality; label history contaminated |
| **primary_code** | `src/engines/zone_cluster_score.py` · `src/engines/live_engine.py` (BitNetZoneGate) |

### 3.6 TradeNet

| Field | Content |
|---|---|
| **id** | `tradenet` |
| **stage** | `opportunity_understanding` · order **6** |
| **intent** | What **expected trading outcomes** (discrete milestones) follow from the current semantic market state? |
| **hypothesis** | Canonical morphology predicts milestone outcomes (TP1/TP2/survive BE). |
| **inputs** | Full canonical vector (39 post-retrain envelopes) |
| **outputs** | Heads for milestones; composite only if defined as a **score** until calibrated as **probability** |
| **semantic_meaning** | Expected trading outcomes / milestone estimates — **not** structural quality, not continuous envelope |
| **consumer** | Designed: Fusion `neural_fn` / evaluate path; **actual:** offline only (F-005) |
| **authority_boundary** | None on live spine until TN_QUAL_V1 + ΔG001 |
| **explicit_non_goals** | **Never** classify market structure (CRT); **never** produce continuous MFE/MAE bands (Envelope); **never** hard-reject alone (BitNet) |
| **dependencies** | `feature_pipeline` |
| **falsification** | No discrimination under clean labels / TN_QUAL fail |
| **implementation_status** | PARTIAL (code + 39-dim shadow models; unwired) |
| **alignment** | 🟡 — intent clear; wiring missing; consumers absent on spine |
| **primary_code** | `src/training/trade_net_v2.py` |

### 3.7 RR Engine (deterministic)

| Field | Content |
|---|---|
| **id** | `rr_engine` |
| **stage** | `market_understanding` · order **4** |
| **intent** | How strong is the candle **commitment** and geometric quality? |
| **hypothesis** | Extreme closes signal directional commitment useful as a structural-geometry vote. |
| **inputs** | `high`, `low`, `close` |
| **outputs** | Commitment **score** (`candle_polarity` / `candle_structure_quality`) |
| **semantic_meaning** | Geometric **commitment** — **not** economic reward:risk, not a probability |
| **consumer** | Fusion slot `rr` (active) |
| **authority_boundary** | Fusion vote only; economic RR owned by Ultron after planner (F-048) |
| **explicit_non_goals** | **Never** identify breakouts; **never** compute forward RR from SL/TP; **never** replace Ultron min_rr |
| **dependencies** | OHLCV (via features or raw) |
| **falsification** | Polarity non-informative for selection (research) |
| **implementation_status** | EXECUTABLE |
| **alignment** | 🟡 — name “RR” vs polarity semantics (implementation honest; naming drift) |
| **primary_code** | `src/engines/rr_engine.py` |

### 3.8 RR Trained / NanoInference (parametric)

| Field | Content |
|---|---|
| **id** | `rr_trained` |
| **stage** | `opportunity_understanding` · order **7** |
| **intent** | What **learned reward behavior** is associated with this semantic market state (parametric model trained on historical labels), distinct from deterministic candle commitment? |
| **hypothesis** | Ridge+GNB on canonical features estimates reward-related quantities when in-distribution. |
| **inputs** | Feature vector (39-dim v39 model); gaussian score inputs when via fusion layer |
| **outputs** | `expected_rr` (expectancy-style), `probability_of_win` (only if treated as calibrated), blend **score**, **confidence** (self-reliability), `status` |
| **semantic_meaning** | Learned reward behavior + model **confidence** — **not** RR Engine commitment; **not** neighbour retrieval (“PatternMiner”) |
| **consumer** | `RRFusionLayer` only if `rr_fusion.enabled`; currently **disabled** |
| **authority_boundary** | None live; shadow/offline only |
| **explicit_non_goals** | **Never** claim to be KNN historical pattern mining; **never** set economic SL/TP alone |
| **dependencies** | `feature_pipeline`, `gaussian` (when fused) |
| **falsification** | Gate always bypasses / no ΔG001 (F-038, F-044) |
| **implementation_status** | PARTIAL (39-dim model + percentile gate ready; fusion off) |
| **alignment** | 🟡 — executable parametric stack; name “PatternMiner” implies retrieval (⚫ for retrieval intent) |
| **primary_code** | `src/config_layer/rr/rr_pattern_miner.py` (`RRPatternTrainer`, `NanoInferenceEngine`) · `rr_fusion.py` |
| **notes** | **`RRPatternMiner` as historical evidence engine = ⚫ DESIGN_ONLY** (no class, no retrieval). See prior existence audit. |

### 3.9 BitNet

| Field | Content |
|---|---|
| **id** | `bitnet` |
| **stage** | `safety` · order **8** |
| **intent** | Should this opportunity be rejected because the semantic state is unsafe? |
| **hypothesis** | Compact 6-feature gate separates toxic vs acceptable approve states. |
| **inputs** | Legacy6: body_ratio, retest_depth, disp_strength, atr, candles_since_retest, double_sweep |
| **outputs** | `state_acceptability_score` (locked term — **not** "confidence", per §0.3) |
| **semantic_meaning** | Hard-reject style safety score |
| **consumer** | UltronRiskEngine.approve* when `use_bitnet=true`; else inert |
| **authority_boundary** | Veto on approve path only (when enabled) |
| **explicit_non_goals** | **Never** optimize entries; **never** replace fusion; **never** estimate continuous envelopes |
| **dependencies** | CRT cached features / pipeline features |
| **falsification** | Enable harms book without filter benefit (F-055) |
| **implementation_status** | EXECUTABLE but **disabled** on active config |
| **alignment** | 🟢 for *contract* (gate when on); 🟡 for *active runtime* (inert while flag false — intentional) |
| **primary_code** | `src/bitnet/bitnet_inference.py` |

### 3.10 Trap Engine

| Field | Content |
|---|---|
| **id** | `trap` |
| **intent** | Is this a deception / trap pattern relative to dual-engine thresholds? |
| **hypothesis** | Sweep + displacement + trend configuration flags trap risk. |
| **inputs** | `sweep_detected`, `disp_strength`, `trend_bias` (and dual_engine knobs) |
| **outputs** | Trap score / side of dual engine |
| **semantic_meaning** | Deception-pattern vote for regime dual path |
| **consumer** | EngineRunner dual-engine / adapter path |
| **authority_boundary** | Contributes to dual-engine gating; not a fusion EXPECTED_ENGINE |
| **explicit_non_goals** | **Never** own CRT FSM; **never** estimate p_tp1 |
| **dependencies** | `feature_pipeline`, dual_engine config |
| **falsification** | Trap score never flips decisions |
| **implementation_status** | EXECUTABLE |
| **alignment** | 🟢 (specialized dual voter) |
| **primary_code** | `src/core/engine_runner.py` `trap_engine` · `src/engines/trap_validator_engine.py` |

### 3.11 Breakout Engine

| Field | Content |
|---|---|
| **id** | `breakout` |
| **intent** | Is breakout-style pressure present under dual-engine rules? |
| **hypothesis** | Trend/momentum/spread thresholds identify breakout regime votes. |
| **inputs** | trend_bias, momentum_score, ema_spread (dual_engine knobs) |
| **outputs** | Breakout score |
| **semantic_meaning** | Breakout-pressure vote — not full structure FSM |
| **consumer** | EngineRunner dual-engine |
| **authority_boundary** | Dual-engine only |
| **explicit_non_goals** | **Never** replace CRT expansion detection; **never** set RR |
| **dependencies** | `feature_pipeline` |
| **falsification** | Always pinned score (dimensional mix class defects) |
| **implementation_status** | EXECUTABLE |
| **alignment** | 🟡 — may be degenerate under FM-022/023 mix on crypto (F-061 class) |
| **primary_code** | `src/core/engine_runner.py` `breakout_engine` |

### 3.12 Regime Detection

| Field | Content |
|---|---|
| **id** | `regime` |
| **stage** | `market_understanding` · order **5** |
| **intent** | What market regime currently exists? |
| **hypothesis** | Regime modulates fusion weights / policy. |
| **inputs** | ema_spread, momentum_score, volatility_ratio (detect_regime) |
| **outputs** | Regime label string |
| **semantic_meaning** | Coarse regime label |
| **consumer** | Fusion regime weights (when regime provided); governors |
| **authority_boundary** | Weight selection, not entry ontology |
| **explicit_non_goals** | **Never** open trades; **never** compute structure states |
| **dependencies** | `feature_pipeline` |
| **falsification** | Regime always `"trend"` due to feature defects (F-061) |
| **implementation_status** | EXECUTABLE (multiple regime modules exist; spine uses engine_runner.detect_regime) |
| **alignment** | 🟡 — intent clear; crypto trend-pin risk |
| **primary_code** | `src/core/engine_runner.py` `detect_regime` · `src/regime/regime_classifier.py` (broader toolkit) |

### 3.13 Execution Intent

| Field | Content |
|---|---|
| **id** | `execution_intent` |
| **stage** | `execution` · order **10** |
| **intent** | How should the already-approved trade be executed / tracked (plan + intent lifecycle)? |
| **hypothesis** | Explicit intent FSM prevents ambiguous order lifecycle. |
| **inputs** | Decision/plan events |
| **outputs** | Intent state transitions (`ExecutionIntentV1`) |
| **semantic_meaning** | Execution lifecycle — not market structure |
| **consumer** | Live/journal paths |
| **authority_boundary** | Post-decision execution bookkeeping |
| **explicit_non_goals** | **Never** rescore market features; **never** re-run fusion |
| **dependencies** | `decision_fusion`, planner |
| **falsification** | Intent states unused on live path |
| **implementation_status** | PARTIAL / EXECUTABLE module exists; wiring path-dependent |
| **alignment** | 🟡 — module present; not the spine’s primary mental model for all modes |
| **primary_code** | `src/execution/execution_intent_v1_0.py` · `src/config_layer/execution_planner.py` |

### 3.14 Decision Fusion

| Field | Content |
|---|---|
| **id** | `decision_fusion` |
| **stage** | `decision` · order **9** |
| **intent** | Given all evidence, should this trade be **approved** (resolve potentially conflicting evidence into a single trade-approval decision)? |
| **hypothesis** | Explicit conflict resolution over specialized Stage-1/2/3 evidence improves selection vs any single engine. |
| **inputs** | Upstream **scores** / vetoes (crt, gaussian, zone, rr; optional opportunity/safety models when wired) |
| **outputs** | Approval decision + composite **score** (not a probability unless calibrated) |
| **semantic_meaning** | Trade-approval adjudication — not rediscovery of structure |
| **consumer** | ExecutionPlanner → UltronRiskGate |
| **authority_boundary** | Sole scoring-stack owner of **approval**; **not** economic min_rr (Ultron); **not** Stage-1 description |
| **explicit_non_goals** | **Never** rediscover market structure; **never** invent features; **never** (post F-048) own economic RR threshold; **never** reinterpret Gaussian score as probability |
| **dependencies** | `crt`, `gaussian`, `zone_gate`, `rr_engine` |
| **falsification** | Fusion non-pivotal or engines information-inert |
| **implementation_status** | EXECUTABLE (`FusionEngine` + `DecisionEngine`) |
| **alignment** | 🟡 — evaluate()/neural/LLM path dead; p_win fed from Gaussian |
| **primary_code** | `src/core/fusion_engine.py` · `src/core/decision_engine.py` · `src/core/engine_runner.py` |

### 3.15 Qualification Gate

| Field | Content |
|---|---|
| **id** | `qualification_gate` |
| **intent** | Does a candidate edge survive pre-registered statistical/economic gates for research promotion? |
| **hypothesis** | Formal gates (perm, BH, costs) prevent false promote. |
| **inputs** | Outcome samples, cost model, QualConfig |
| **outputs** | EdgeReport / promote-style statuses |
| **semantic_meaning** | Research qualification — not live bar score |
| **consumer** | Research pipelines; promotion managers (when wired) |
| **authority_boundary** | Research promotion recommendations only |
| **explicit_non_goals** | **Never** score live candles; **never** replace DecisionEngine |
| **dependencies** | Research outcomes, protocol |
| **falsification** | Gate always INSUFFICIENT or always PASS without power |
| **implementation_status** | EXECUTABLE (`src/research/qualification.py`) |
| **alignment** | 🟢 for research role |
| **primary_code** | `src/research/qualification.py` |

### 3.16 Backtest Engine

| Field | Content |
|---|---|
| **id** | `backtest` |
| **intent** | What ledger results from applying the spine (or CRT path) to historical OHLCV under declared exits/costs? |
| **hypothesis** | Deterministic replay measures whether intents achieve objectives. |
| **inputs** | OHLCV, production config, exit/cost model |
| **outputs** | Trades, metrics, events |
| **semantic_meaning** | Measurement of behaviour — must not redefine model semantics |
| **consumer** | Research, ConfigValidator, promotion evidence |
| **authority_boundary** | Measurement only; behaviour changes require config/code authority |
| **explicit_non_goals** | **Never** change ontology meaning mid-run; **never** invent a second feature schema |
| **dependencies** | All spine models as configured |
| **falsification** | Non-determinism / lookahead |
| **implementation_status** | EXECUTABLE |
| **alignment** | 🟢 for measurement role (F-037/F-058 gate-on/off epochs documented) |
| **primary_code** | `src/runtime/backtest_v2.py` `BacktestRunner` |

### 3.17 Research / Hypothesis Runner

| Field | Content |
|---|---|
| **id** | `research_runner` |
| **intent** | Do pre-registered hypotheses survive qualification under honest measurement? |
| **hypothesis** | Structured research (toy/spine/M4) compounds knowledge without contaminating production intent. |
| **inputs** | Protocols, candles, MIAR-aligned questions |
| **outputs** | Findings, edge reports, nulls |
| **semantic_meaning** | Epistemic updates — not production scores |
| **consumer** | Findings ledger, funding decisions |
| **authority_boundary** | Research authority only until promotion |
| **explicit_non_goals** | **Never** hot-patch production intent without MIAR edit; **never** silently enable fusion models |
| **dependencies** | MIAR, ontology, qualification_gate, backtest |
| **falsification** | Research pipeline cannot reproduce null/positive under protocol |
| **implementation_status** | EXECUTABLE (distributed: `src/research/*`, scripts/research) |
| **alignment** | 🟢 as a *role*; individual experiments vary |
| **primary_code** | `src/research/runner.py` · `src/research/qualification.py` · research scripts |

---

## 3A. Advisory sidecar register (4 — zero spine authority)

> **Registered 2026-07-29.** These four are **not** part of the 17-entry spine register and never
> will be without a qualification protocol. They are listed here because they are **EXECUTABLE**,
> they **do** consume specialist evidence, and their output is **decision-shaped** — which is
> exactly why they need explicit non-goals. Machine twin: `miar_registry.json` →
> `sidecar_entries` (+ the `sidecar_authority` rule block).

**The sidecar rule (binding):** a sidecar may observe any stage output and may write telemetry.
It may **never** appear in `EXPECTED_ENGINES`, never be returned by `EngineRunner.run()`, never
gate / size / veto / modify a decision, and never own a §4 market-question row. Registration here
**grants nothing** — promotion to a spine entry requires a qualification protocol plus measured
ΔG001 (the `TN_QUAL_V1` precedent). Evidence: **F-012**.

Why not `design_only_concepts` (§5)? That bucket is for concepts with no production-intent path
(Envelope, RRPatternMiner). These four *run*. Different problem, different register.

### 3A.1 Hierarchical Meta Fusion

| Field | Content |
|---|---|
| **id** | `hierarchical_meta_fusion` |
| **stage** | `measurement` · sidecar (no spine order) |
| **intent** | How much capital would this opportunity deserve if every intelligence layer were weighed together? |
| **hypothesis** | A weighted blend of zone, liquidity, RR, replay, market-state and TradeNet-meta evidence separates high- from low-allocation-quality opportunities. |
| **inputs** | zone score+passed · liquidity_pressure_score/distance · rr score + expected_rr · replay winrate/stability/density · cluster_confidence/state_persistence/trap_probability · tradenet_meta capital_quality_score/allocation_confidence |
| **outputs** | `opportunity_score` · `decision` (ALLOW/REDUCE/REJECT) · per-layer breakdown |
| **semantic_meaning** | Advisory capital-allocation quality score — decision-**shaped** telemetry, never a decision |
| **consumer** | `CognitiveBus._process` → `logs/cognitive_telemetry.jsonl` |
| **authority_boundary** | **NONE.** Never returned by `EngineRunner.run()` |
| **explicit_non_goals** | **Never** enter `EXPECTED_ENGINES`; **never** gate/size/veto/modify a live decision; **never** be read as a calibrated probability (`opportunity_score` is ordinal); **never** re-derive market structure; **never** become the sole consumer path for specialist evidence without a qualification protocol |
| **dependencies** | zone_gate, rr_engine, replay_memory, tradenet_meta |
| **falsification** | Layer weights never separate outcomes, or the blend tracks a single dominant layer (redundant meta-layer) |
| **implementation_status** | EXECUTABLE (gated by `cognitive_layer.enabled`) |
| **alignment** | 🟢 (contract says advisory-only; code is advisory-only) |
| **primary_code** | `src/core/hierarchical_meta_fusion.py` |

> ⚠️ **Load-bearing for design review.** HMF is *already* a meta-model that consumes specialist
> evidence rather than raw features — the exact shape proposed for the BitNet redesign. Any new
> evidence-consumer layer **must** state whether it absorbs, replaces, or is scoped against HMF,
> or the repository ships two dormant meta-layers doing the same job. See
> [`bitnet-design-specification.md`](../architecture/bitnet-design-specification.md).

### 3A.2 TradeNet Meta

| Field | Content |
|---|---|
| **id** | `tradenet_meta` |
| **stage** | `measurement` · sidecar |
| **intent** | What capital quality does the composite of prior engine outputs imply for this opportunity? |
| **hypothesis** | TradeNet's p_win, combined with replay/regime/liquidity meta-context, estimates allocation quality better than p_win alone. |
| **inputs** | TradeNet base p_win (35-dim) · gaussian · rr · zone · replay meta-context · regime · liquidity |
| **outputs** | `capital_quality_score` · `allocation_confidence` · authority tier (FULL/HALF/QUARTER) |
| **semantic_meaning** | Meta-cognition over engine outputs; an allocation-quality **score**, not a win probability |
| **consumer** | `HierarchicalMetaFusion` layer 6 |
| **authority_boundary** | **NONE.** Feeds an advisory sidecar only |
| **explicit_non_goals** | **Never** enter `EXPECTED_ENGINES`; **never** size a real position despite emitting an authority tier; **never** be read as p_win (it *consumes* p_win); **never** classify market structure |
| **dependencies** | tradenet, replay_memory |
| **falsification** | `capital_quality_score` adds nothing over the base p_win it wraps |
| **implementation_status** | EXECUTABLE |
| **alignment** | 🟢 |
| **primary_code** | `src/engines/tradenet_meta_engine.py` |

Wraps the same TradeNet artifact that is **UNWIRED** on the spine (F-005). Fail-safe: any
exception or 100 ms timeout → `allocation_confidence=0.0` / QUARTER; torch absent or no active
model → base p_win = 0.5.

### 3A.3 Replay Memory

| Field | Content |
|---|---|
| **id** | `replay_memory` |
| **stage** | `measurement` · sidecar |
| **intent** | What happened historically in market states similar to the current one? |
| **hypothesis** | Cluster-indexed historical opportunities, temporally decayed, provide a usable base rate for the current state. |
| **inputs** | Historical opportunity JSONL · cluster assignment · current semantic state |
| **outputs** | `historical_winrate` · `cluster_stability` · `replay_density` |
| **semantic_meaning** | Historical **base rate** over similar states — institutional memory, not a forecast |
| **consumer** | `CognitiveBus._process` · `ReplayDriftGovernor.audit` |
| **authority_boundary** | **NONE.** Read-only memory |
| **explicit_non_goals** | **Never** enter `EXPECTED_ENGINES`; **never** be read as a forward probability; **never** mutate state after construction; **never** source its base rate from an unvalidated outcome field |
| **dependencies** | feature_pipeline |
| **falsification** | Historical winrate over a cluster does not predict forward winrate for that cluster |
| **implementation_status** | EXECUTABLE |
| **alignment** | 🟡 **SEMANTIC_DRIFT** |
| **primary_code** | `src/replay/replay_memory_engine.py` |

> 🟡 **Why drift:** its source is the opportunity JSONL stream, which **F-022** established is a
> *detection* stream, not a trade ledger (outcome/rr only 36.8 % self-consistent). So
> `historical_winrate` is computed over contaminated labels. Harmless while sidecar-only —
> **blocking** for any promotion path.

### 3A.4 Cognitive Bus

| Field | Content |
|---|---|
| **id** | `cognitive_bus` |
| **stage** | `measurement` · sidecar |
| **intent** | What advisory intelligence can be derived asynchronously without ever touching the execution plane? |
| **hypothesis** | A decision snapshot can be enriched off the hot path with zero risk to determinism or latency. |
| **inputs** | `DecisionSnapshot` events emitted by EngineRunner |
| **outputs** | `logs/cognitive_telemetry.jsonl` · `logs/replay_queries.jsonl` |
| **semantic_meaning** | Asynchronous transport/orchestration for the advisory sidecar pipeline |
| **consumer** | Telemetry files only |
| **authority_boundary** | **NONE.** The `cognitive` key is deliberately absent from the `EngineRunner` return dict |
| **explicit_non_goals** | **Never** enter `EXPECTED_ENGINES`; **never** touch `EngineRunner.run()` internals; **never** return anything to the execution plane; **never** block the hot path; **never** let a sidecar exception propagate into a decision |
| **dependencies** | replay_memory, tradenet_meta, hierarchical_meta_fusion |
| **falsification** | Sidecar latency or exceptions observably perturb the spine ledger |
| **implementation_status** | EXECUTABLE (gated by `cognitive_layer.enabled`) |
| **alignment** | 🟢 |
| **primary_code** | `src/cognitive/cognitive_bus.py` |

Single background daemon thread, queue maxsize 500, WARNING above a 5 % drop rate. Backpressure
drops are **silent by design** — telemetry loss is preferred over spine interference.

---

## 4. Market-question ownership matrix

**Exactly one Owner per question.** Secondary consumers may *read* outputs; they must not redefine the question.

| Market Question | Owner (MIAR id) | Secondary Consumers |
|---|---|---|
| What concepts/formulas exist? | `market_ontology` | All producers |
| How is the canonical vector built? | `feature_pipeline` | All feature consumers |
| What structure is the market in? | `crt` | gaussian, tradenet, decision_fusion (as readers) |
| Is this state statistically familiar (EMA/momentum axis)? | `gaussian` | decision_fusion |
| Is this inside a valid feature-space zone? | `zone_gate` | decision_fusion |
| What is candle commitment geometry? | `rr_engine` | decision_fusion |
| What is model-based expected RR/win blend? | `rr_trained` | (none live) |
| Is this state semantically unsafe to approve? | `bitnet` | CRT approve path (when enabled) |
| What is P(trade milestones)? | `tradenet` | (none live) |
| What post-entry continuous bounds? | *(Envelope — **⚫ DESIGN_ONLY**, registered 2026-07-28; see §5)* | (none live) |
| Is trap pressure present? | `trap` | dual-engine |
| Is breakout pressure present? | `breakout` | dual-engine |
| What market regime exists? | `regime` | crt (context), decision_fusion weights |
| Should the setup pass decision gates? | `decision_fusion` | execution_intent, planner |
| What is the economic plan (SL/TP/RR)? | ExecutionPlanner + **UltronRiskGate** (not a MIAR scoring engine; risk layer) | live/backtest |
| Does research edge qualify? | `qualification_gate` | promotion |
| What ledger does history produce? | `backtest` | research, promotion |
| Do hypotheses survive honest tests? | `research_runner` | findings |

**Duplicate-ownership flags (current):**

- DecisionEngine treating **gaussian score as p_win** → secondary consumer **reinterpreting** gaussian output (🟡 on `gaussian` / `decision_fusion`).  
- Name **RR** for polarity vs economic RR (Ultron) → naming overlap, owners distinct if non-goals held.  
- **RRPatternMiner** as historical retrieval → **no owner row** (⚫ design only).

---

## 5. Rollup verdict table (17)

| # | id | alignment | implementation |
|---:|---|---|---|
| 1 | market_ontology | 🟢 | EXECUTABLE |
| 2 | feature_pipeline | 🟢 | EXECUTABLE |
| 3 | crt | 🟡 | EXECUTABLE |
| 4 | gaussian | 🟡 | EXECUTABLE |
| 5 | zone_gate | 🟡 | EXECUTABLE |
| 6 | tradenet | 🟡 | PARTIAL |
| 7 | rr_engine | 🟡 | EXECUTABLE |
| 8 | rr_trained | 🟡 | PARTIAL |
| 9 | bitnet | 🟢/🟡* | EXECUTABLE (inert default) |
| 10 | trap | 🟢 | EXECUTABLE |
| 11 | breakout | 🟡 | EXECUTABLE |
| 12 | regime | 🟡 | EXECUTABLE |
| 13 | execution_intent | 🟡 | PARTIAL |
| 14 | decision_fusion | 🟡 | EXECUTABLE |
| 15 | qualification_gate | 🟢 | EXECUTABLE |
| 16 | backtest | 🟢 | EXECUTABLE |
| 17 | research_runner | 🟢 | EXECUTABLE |

\*BitNet: contract 🟢 when enabled; active patch inert is intentional config, not missing intent.

**Special ⚫:** Historical-evidence **RRPatternMiner** (retrieval) — not in the 17 as an owner; documented as DESIGN_ONLY anti-concept under `rr_trained` notes.

**Special ⚫ (registered 2026-07-28):** **EnvelopeNet** (`envelope`) — post-entry continuous
bounds. Has an **executable OFFLINE path** (`research/envelope_offline/shadow.py` → four
independent heads `y_mfe_r` / `y_mae_r_heat` / `y_holding_bars` / `y_time_to_mfe`; runnable as
`model_id=envelope` in the `model_runners` harness) but is **DESIGN_ONLY with respect to its
production intent**: no wired consumer, `decision_weight` conceptually 0, no owner row in §4, no
measured ΔG001. Registered in [`miar_registry.json`](miar_registry.json) `design_only_concepts`
rather than as an 18th engine entry — it owns no production market question, so the 17-entry spine
register is unchanged. This closes the 🔴 INTENT_MISSING state (executable code with no
authoritative intent) flagged during the 2026-07-28 adapter-layer review. Promotion to a full
entry requires a qualification protocol **and** measured ΔG001 (the `TN_QUAL_V1` precedent for
TradeNet). Distinct from RRPatternMiner above, which has no executable path at all.

### 5A. Sidecar rollup (4 — §3A, zero spine authority)

| # | id | alignment | implementation | authority |
|---:|---|---|---|---|
| S1 | hierarchical_meta_fusion | 🟢 | EXECUTABLE (flag-gated) | NONE |
| S2 | tradenet_meta | 🟢 | EXECUTABLE | NONE |
| S3 | replay_memory | 🟡† | EXECUTABLE | NONE |
| S4 | cognitive_bus | 🟢 | EXECUTABLE (flag-gated) | NONE |

†`replay_memory` computes `historical_winrate` over the opportunity JSONL stream, which **F-022**
established is a *detection* stream and only 36.8 % self-consistent — contaminated labels.
Harmless while sidecar-only; **blocking** for any promotion path.

These four are **not** in the 17 and do not appear in §4 (they own no market question). The
zero-authority rule is enforced mechanically by `tests/test_miar_registry.py`
(`test_sidecar_has_zero_spine_authority`, `test_sidecar_owns_no_market_question`), not by prose.

---

## 6. Maintenance ritual

1. New model or new market question → add/adjust MIAR entry **before** wiring fusion.  
2. Code change that changes meaning of outputs → same-turn MIAR alignment review.  
3. Finding that falsifies hypothesis → update `falsification` + possibly demote authority_boundary; never silent-delete intent.  
4. Overlap: run matrix check (one Owner per question) in `tests/test_miar_registry.py`.  
5. Recompile portable mind after MIAR material edits (`Compile` trigger).
6. **New executable model → classify it before wiring:** owns a production market question →
   spine entry (§3); runs but has zero decision authority → sidecar (§3A); no executable path at
   all → `design_only_concepts` (§5). Never leave executable code with no registered intent.

---

## 7. Related documents

| Doc | Role vs MIAR |
|---|---|
| `configs/formulas/market_ontology.yaml` | Tier 1 — meaning of concepts |
| `src/features/feature_schema.py` | Tier 2 — vector law |
| `active_models.yaml` | Runtime/evidence mirror; subordinate on intent |
| `docs/topics/model-intent-and-feature-ownership.md` | Feature ownership matrices |
| `docs/analysis/model-intent-hypothesis-ontology-consumer-trace-2026-07-28.md` | Point-in-time deep trace |
| `docs/analysis/rr-pattern-miner-implementation-intent-audit-2026-07-28.md` | Proof retrieval RRPatternMiner is absent |
| `docs/architecture/model-responsibility-matrix.md` | Cross-model responsibility taxonomy — cites MIAR for every cell |
| `docs/architecture/intelligence-topology.md` | Layered topology (features → specialists → meta → fusion → decision) |
| `docs/architecture/bitnet-design-specification.md` | Proposal to move BitNet to consume specialist evidence (needs a MIAR amendment) |
| `docs/governance/bitnet_qualification_protocol.md` | `BN_QUAL_V1` gate ladder — how BitNet would earn spine authority |

---

**End of MIAR charter.** Machine-readable entries: `miar_registry.json`.
